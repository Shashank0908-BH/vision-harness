# Walk through one run

Open `examples/shapes.png`: it contains nine separate red circles on a white background. This is a development smoke example, not the held-out benchmark.

Run a standalone operation first:

```bash
uv run vision tool run components --request examples/components.json
```

The request selects red pixels using documented HSV thresholds, discards regions smaller than ten pixels, and counts the remaining 8-connected components. For this specific image the result is nine components. Open the saved mask and overlay to inspect what it counted. On an image with touching circles, the same operation can merge circles and be wrong about object count.

Next run the full harness:

```bash
uv run vision run --mode full --image examples/shapes.png \
  --prompt 'How many red circles are in this image? Return the count as a number.' --step
```

1. `input`: the runtime saves a normalized image and its hash.
2. `evidence`: fixed probes measure image properties without asking Astra.
3. `call_started` / `call_finished`: Astra receives the image, task, available tools and probe evidence. The provider request and actual response are saved separately under `calls/`.
4. `plans`: Astra proposes bounded methods, such as components or watershed, with assumptions and a preferred plan. Inspect `plans-1.json`.
5. `assessments`: Jev rates eligible methods against the shared rubric. Inspect the scores **and** distributions; these are not ground-truth accuracy.
6. `selection`: Python chooses a method or a bounded comparison. `--step` pauses before execution.
7. `tool_started` / `evidence`: OpenCV produces measurements, masks and overlays. You can inspect boxes and verify which pixels contributed to a count.
8. `candidate_answer`: Astra combines image input and evidence into the common answer format.
9. `answer_review`: Jev assesses support from the supplied evidence. It has not independently seen the image.
10. `final_answer`: the run finishes with an answer, abstention or error. A failed review may lead to a second round first.

Use `uv run vision replay runs/RUN_ID` for all events, or open individual JSON files in your editor. Replay makes no paid calls. The trace records observable requests, responses and operations; it does not expose private internal model reasoning.

## Where to look when something fails

| Symptom | First file or artifact to inspect |
|---|---|
| Wrong colored pixels selected | `artifacts/*-mask.png`, then `tools/opencv.py` thresholds and step arguments. |
| Count differs from visible objects | Components/boxes, touching-region assumptions and the chosen method. |
| Jev favors a poor plan | `calls/*.request.json`, shared rubric, capability descriptions, and unverified assumptions. |
| No method executes | `selection` event and configured fit/confidence thresholds. |
| Correct measurements but wrong answer | Astra answer request, image IDs, cited evidence and response. |
| Missing key or API failure | `doctor`, `error` event, model ID and `.env` variable names. Never print the key itself. |
| Harbor fails before inference | Trial log, Docker build/setup output, then `harbor_agent.py`. |
| Wrong benchmark grade | Verifier's expected answer, tolerance, and `evals/scoring.py`. |

## Make one controlled change

Keep the image, question and plan set fixed. Change one selection threshold or one rubric description, use a new output directory, and compare the trace. Record the reason before running the held-out split. Running a different candidate generator and a different selector simultaneously cannot identify which one caused a gain.

To detach OpenCV completely, use `vanilla`. To detach Jev, use `tools`. To test only Jev's methodology scoring, use `select`. To test only its final review, use `review`.
