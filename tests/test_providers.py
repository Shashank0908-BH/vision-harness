import json

import httpx
import pytest
from openai import OpenAI

from vision_harness.contracts import Answer
from vision_harness.demo import demo_plans
from vision_harness.providers.astra import Astra
from vision_harness.providers.evidence_budget import bounded_request, encoded_size
from vision_harness.providers.jev import Jev
from vision_harness.tracing import Trace


def test_astra_responses_wire_format(settings, tmp_path):
    def respond(request):
        data = json.loads(request.content)
        assert request.url.path == "/v1/responses"
        assert data["model"] == "gpt-6-astra"
        assert data["text"]["format"]["type"] == "json_schema"
        assert data["text"]["format"]["strict"] is True
        assert data["input"][0]["content"][1]["type"] == "input_image"
        assert "temperature" not in data
        answer = Answer(
            status="answered", value=2, explanation="fixture", evidence_ids=[], limitations=[]
        )
        return httpx.Response(
            200,
            json={
                "id": "resp_test",
                "object": "response",
                "created_at": 1,
                "status": "completed",
                "model": "gpt-6-astra",
                "output": [
                    {
                        "id": "msg_test",
                        "type": "message",
                        "status": "completed",
                        "role": "assistant",
                        "content": [
                            {
                                "type": "output_text",
                                "text": answer.model_dump_json(),
                                "annotations": [],
                            }
                        ],
                    }
                ],
                "usage": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
            },
        )

    client = OpenAI(
        api_key="test", http_client=httpx.Client(transport=httpx.MockTransport(respond))
    )
    provider = Astra(settings, Trace(tmp_path), client=client)
    answer = provider.answer(
        "Count",
        [{"type": "input_image", "image_url": "data:image/png;base64,fixture"}],
        {"evidence": []},
    )
    assert answer.value == 2
    assert list((tmp_path / "calls").glob("*.response.json"))


def test_jev_wire_format_and_separate_semantics(settings, tmp_path, monkeypatch):
    monkeypatch.delenv("JEV_API_KEY", raising=False)
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-jev-key")

    def respond(request):
        data = json.loads(request.content)
        assert request.headers["authorization"] == "Bearer test-jev-key"
        assert data["model"] == "jev-1.13.0"
        answers = {}
        for key, question in data["questions"].items():
            if question["type"] == "score":
                assert len(question["criteria"]) == 4
                answers[key] = {
                    "type": "score",
                    "score": 2.8,
                    "confidence": 0.6,
                    "probabilities": {"0": 0, "1": 0, "2": 0.2, "3": 0.8},
                }
            else:
                answers[key] = {"type": "noul", "noul": 0.7}
        return httpx.Response(
            200,
            json={
                "model": "jev-1.13.0",
                "answers": answers,
                "usage": {"input_tokens": 10, "output_tokens": 5},
            },
        )

    provider = Jev(
        settings, Trace(tmp_path), client=httpx.Client(transport=httpx.MockTransport(respond))
    )
    assert provider.assess({"observed": "test"}, demo_plans().candidates)[0].score == 2.8
    assert provider.review({"answer": "test"}).support_probability == 0.7
    assert "test-jev-key" not in "".join(p.read_text() for p in tmp_path.rglob("*.json"))


def test_jev_compacts_geometry_preserves_evidence_and_raw_trace(settings, tmp_path, monkeypatch):
    monkeypatch.setenv("JEV_API_KEY", "test-jev-key")
    components = [
        {
            "id": i,
            "area_pixels": i + 1,
            "touches_border": i == 0,
            "box": [1, 2, 3, 4],
            "centroid": [2.5, 4],
        }
        for i in range(500)
    ]
    state = {
        "answer": {"value": 500},
        "evidence": [
            {
                "evidence_id": "regions",
                "quality_flags": ["Not verified nuclei"],
                "measurements": {
                    "component_count": 500,
                    "foreground_fraction": 0.2,
                    "components": components,
                },
            }
        ],
    }

    def respond(request):
        data = json.loads(request.content)
        assert encoded_size(data) <= settings.limits.jev_max_request_bytes
        evidence = data["state"]["evidence"][0]
        assert evidence["quality_flags"] == ["Not verified nuclei"]
        m = evidence["measurements"]
        assert m["component_count"] == 500
        assert m["foreground_fraction"] == 0.2
        assert m["components_summary"]["area_pixels"]["total"] == 125250
        assert m["components_summary"]["border_touching_records"] == 1
        assert "components" not in m
        return httpx.Response(200, json={"answers": {"support": {"type": "noul", "noul": 0.1}}})

    provider = Jev(
        settings, Trace(tmp_path), client=httpx.Client(transport=httpx.MockTransport(respond))
    )
    assert provider.review(state).support_probability == 0.1
    assert len(state["evidence"][0]["measurements"]["components"]) == 500
    original = json.loads(next((tmp_path / "evidence").glob("*.json")).read_text())
    assert original["state"] == state


def test_jev_errors_are_recorded_and_do_not_hide_server_reason(settings, tmp_path, monkeypatch):
    monkeypatch.setenv("JEV_API_KEY", "test-jev-key")
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                400, json={"detail": {"error_type": "max_tokens_exceeded"}}
            )
        )
    )
    with pytest.raises(httpx.HTTPStatusError, match="max_tokens_exceeded"):
        Jev(settings, Trace(tmp_path), client=client).review({"answer": "test"})
    response = json.loads(next((tmp_path / "calls").glob("*.response.json")).read_text())
    assert response["http_status"] == 400
    assert response["detail"]["error_type"] == "max_tokens_exceeded"


def test_jev_budget_never_truncates_question_to_fit():
    request = {"state": {"evidence": []}, "questions": {"q": "x" * 30000}}
    with pytest.raises(ValueError, match="not truncated"):
        bounded_request(request, 24000)


@pytest.mark.parametrize(
    "failure", ["malformed", "max_output_tokens", "content_filter", "always_malformed"]
)
def test_astra_retains_failed_responses_and_bounds_format_retries(settings, tmp_path, failure):
    calls = []
    answer = Answer(
        status="answered", value=2, explanation="fixture", evidence_ids=[], limitations=[]
    )

    def respond(request):
        calls.append(json.loads(request.content))
        bad = len(calls) == 1 or failure == "always_malformed"
        incomplete = bad and failure in ("max_output_tokens", "content_filter")
        return httpx.Response(
            200,
            json={
                "id": "resp_test",
                "object": "response",
                "created_at": 1,
                "status": "incomplete" if incomplete else "completed",
                "incomplete_details": {"reason": failure} if incomplete else None,
                "model": "gpt-6-astra",
                "output": [
                    {
                        "id": "msg_test",
                        "type": "message",
                        "status": "incomplete" if incomplete else "completed",
                        "role": "assistant",
                        "content": [
                            {
                                "type": "output_text",
                                "text": "{" if bad else answer.model_dump_json(),
                                "annotations": [],
                            }
                        ],
                    }
                ],
                "usage": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
            },
        )

    client = OpenAI(
        api_key="test", http_client=httpx.Client(transport=httpx.MockTransport(respond))
    )
    provider = Astra(settings, Trace(tmp_path), client=client)
    if failure in ("content_filter", "always_malformed"):
        with pytest.raises(ValueError):
            provider.answer("Count", [], {})
    else:
        assert provider.answer("Count", [], {}).value == 2
    count = 1 if failure == "content_filter" else 2
    assert len(calls) == count
    assert len(list((tmp_path / "calls").glob("*.response.json"))) == count
    if failure == "max_output_tokens":
        assert calls[1]["max_output_tokens"] == 2 * calls[0]["max_output_tokens"]
    if count == 2:
        assert "compact JSON" in calls[1]["instructions"]
