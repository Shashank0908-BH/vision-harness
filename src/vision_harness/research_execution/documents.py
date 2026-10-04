"""Retrieve actual documentation and preserve a versioned evidence packet."""

import hashlib
import ipaddress
import re
import socket
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

import httpx

from ..tracing import write_json
from .contracts import UsageSet


def usage_excerpt(clean, limit):
    """Keep a labeled head and usage-related windows rather than only a page prefix."""
    if len(clean) <= limit:
        return clean
    windows = [(0, min(2500, limit))]
    terms = r"(?im)^(?:\s*def\s+(?:predict_instances|eval|normalize|imread|resize)|.*(?:parameters|inference|normaliz|pretrained|quickstart|getting started|example|axes|channels|diameter).{0,80}$)"
    remaining = limit - windows[0][1]
    for match in re.finditer(terms, clean):
        if remaining <= 0:
            break
        start = max(0, match.start()-150)
        if any(a <= start < b for a, b in windows):
            continue
        size = min(2400, remaining)
        windows.append((start, min(len(clean), start+size)))
        remaining -= size
    return "\n\n".join(f"[source characters {a}:{b}; other sections may be omitted]\n{clean[a:b]}" for a, b in sorted(windows))


def validate_public_url(url):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Documentation requires a public HTTPS URL without credentials")
    addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 443)
    if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
        raise ValueError("Documentation URL resolves to a non-public address")


def fetch_document(url, directory, char_limit):
    from bs4 import BeautifulSoup

    source_id = hashlib.sha256(url.encode()).hexdigest()[:16]
    record = {"source_id": source_id, "url": url, "status": "error"}
    try:
        current = url
        with httpx.Client(timeout=40, follow_redirects=False) as client:
            for _ in range(5):
                validate_public_url(current)
                with client.stream("GET", current, headers={"User-Agent": "VisionHarnessResearch/0.1"}) as response:
                    if response.is_redirect:
                        current = str(response.url.join(response.headers["location"]))
                        continue
                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "")
                    if "pdf" in content_type:
                        raise ValueError("PDF source retained as citation; this reader requires HTML/plain-text usage documentation")
                    raw = bytearray()
                    for chunk in response.iter_bytes():
                        raw.extend(chunk)
                        if len(raw) > 3_000_000:
                            raise ValueError("Documentation page exceeds 3MB retrieval budget")
                    break
            else:
                raise ValueError("Too many documentation redirects")
        text = bytes(raw).decode("utf-8", errors="replace")
        if "html" in content_type:
            soup = BeautifulSoup(text, "html.parser")
            for element in soup(["script", "style", "nav", "header", "footer"]):
                element.decompose()
            content = soup.find("main") or soup.find("article") or soup
            clean = content.get_text("\n", strip=True)
        else:
            clean = text  # Parsing Python/plain text as HTML can silently delete operators.
        (directory / f"{source_id}.txt").write_text(clean)
        # Keep the full retrieved page; explicitly label the model-facing excerpt.
        (directory / f"{source_id}.source").write_bytes(raw)
        record.update(status="retrieved", final_url=current,
                      sha256=hashlib.sha256(raw).hexdigest(), chars=len(clean),
                      excerpt=usage_excerpt(clean, char_limit), excerpt_truncated=len(clean)>char_limit,
                      excerpt_method="full text if within budget; otherwise source-located usage windows")
    except Exception as error:
        record["error"] = f"{type(error).__name__}: {error}"
    return record


def compile_usage(astra, task, candidates, packet, folder, policy):
    folder.mkdir(parents=True, exist_ok=True)
    urls = sorted({url for c in candidates for url in c.documentation_urls[:policy.max_document_pages_per_candidate]})
    with ThreadPoolExecutor(max_workers=4) as pool:
        docs = list(pool.map(lambda url: fetch_document(url, folder, policy.max_document_chars), urls))
    write_json(folder / "retrieval.json", docs)
    good = {d["source_id"] for d in docs if d["status"] == "retrieved"}
    if not good:
        raise ValueError("No usable model/library documentation was retrieved")
    usage = astra.structured(
        "Read the supplied documentation and extract precise executable usage contracts for every retained candidate. "
        "Reference only retrieved source IDs. Explicitly mark missing, truncated or conflicting required information; "
        "ready_for_trial means sufficient documentation to attempt and validate a bounded execution, NOT proven accuracy or guaranteed runtime. "
        "Set it false for unresolved model input/API incompatibility or genuinely missing scientific preprocessing semantics. "
        "Unknown acquisition calibration, unmeasured runtime, not-yet-inspected checkpoint files and possible biological errors are trial checks/limitations, not automatic blockers. "
        "For standard Python/NumPy operations such as unique positive-ID counting, shape/dtype assertions, JSON and NPZ I/O, "
        "ordinary API knowledge plus executable validation is sufficient; do not demand a separate web page for every basic function. "
        "For specialist model-specific arguments, use the actual retrieved documentation. "
        "Be concise: normally one or two sentences per contract field. Do not equate a summary with complete documentation coverage.",
        task.query, [], {"stage_packet": packet, "task": task.model_dump(),
                        "candidates": [c.model_dump() for c in candidates], "documents": docs}, UsageSet,
    )
    ids = [u.candidate_id for u in usage.contracts]
    if len(ids) != len(set(ids)) or set(ids) != {c.candidate_id for c in candidates}:
        raise ValueError("Usage contracts must cover every retained candidate exactly once")
    if any(not set(u.source_ids) <= good for u in usage.contracts):
        raise ValueError("Usage contract cites an unavailable source")
    for contract in usage.contracts:
        candidate = next(c for c in candidates if c.candidate_id == contract.candidate_id)
        own_sources = {d["source_id"] for d in docs if d["status"] == "retrieved"
                       and d["url"] in candidate.documentation_urls}
        if contract.ready_for_trial and not set(contract.source_ids) & own_sources:
            raise ValueError("Ready usage contract lacks retrieved documentation for this candidate")
    write_json(folder / "usage-contracts.json", usage.model_dump())
    return usage, docs
