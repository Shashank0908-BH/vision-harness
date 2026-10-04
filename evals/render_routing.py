"""Small offline review page built only from scored results and saved evidence."""

import html
import json
import shutil
from pathlib import Path

from evals.routing import REPORT, RUNS
from vision_harness.tracing import write_json


def esc(value):
    return html.escape(str(value), quote=True)


def render():
    data = json.loads((REPORT / "results.json").read_text())
    assert round(data["metrics"]["harness_with_review"]["mape_percent"], 2) == 5.71, "Update this cohort-specific interpretation before rendering another result"
    table = []
    for name, metric in data["metrics"].items():
        value = f'{metric["mape_percent"]:.2f}%' if metric["mape_percent"] is not None else "Incomplete"
        table.append(f'<tr><td>{esc(name.replace("_", " "))}</td><td>{metric["completed"]}/{metric["total"]}</td><td>{value}</td><td>{metric["exact"]}</td></tr>')
    pages = []
    for number, row in enumerate(data["rows"], 1):
        task = row["id"]
        target = REPORT / "artifacts" / task
        target.mkdir(parents=True, exist_ok=True)
        shutil.copy2(row["image"], target / "original.png")
        route = RUNS / task / "routing"
        for name in ("decision.json", "proposal.json", "intent.json", "review.json", "answer.json", "manifest.json"):
            if (route / name).exists():
                shutil.copy2(route / name, target / name)
        cards = []
        for pid, count in row["procedure_counts"].items():
            worker = route / "specialists" / pid
            if count is None:
                cards.append(f'<article><h3>{esc(pid)}</h3><p>No usable measurement. Inspect the preserved run error.</p></article>')
                continue
            destination = target / pid
            destination.mkdir(exist_ok=True)
            for name in ("evidence.json", "instances.json", "labels.npz", "worker-result.json", "request.json", "worker.log"):
                shutil.copy2(worker / name, destination / name)
            shutil.copy2(route / "artifacts" / (pid + "-overlay.png"), destination / "overlay.png")
            ape = abs(count-row["expected"]) / row["expected"] * 100
            cards.append(f'<article><h3>{esc(pid)} · {count} instances</h3><p>Count error {ape:.2f}%</p><a href="artifacts/{task}/{pid}/overlay.png"><img loading="lazy" src="artifacts/{task}/{pid}/overlay.png" alt="{esc(pid)} instance overlay"></a><p><a href="artifacts/{task}/{pid}/evidence.json">Evidence</a> · <a href="artifacts/{task}/{pid}/instances.json">Geometry</a> · <a href="artifacts/{task}/{pid}/labels.npz">Instance map</a></p></article>')
        decision = row["decision"] or {}
        score_rows = []
        for assessment in decision.get("assessments", []):
            score_rows.append(f'<tr><td>{esc(assessment["plan_id"])}</td><td>{assessment["score"]:.2f}</td><td>{assessment["confidence"]:.2f}</td></tr>')
        final = row["harness"]
        pages.append(f'''<section class="task" id="task-{number}" {'hidden' if number > 1 else ''}>
          <p class="eyebrow">Task {number} / {len(data['rows'])} · {esc(task)}</p>
          <h2>Reference count: {row['expected']}</h2><p class="filename">{esc(row['source_filename'])}</p>
          <div class="grid"><article><a href="artifacts/{task}/original.png"><img src="artifacts/{task}/original.png" alt="Original fluorescence microscopy image"></a></article>
          <article><h3>Frozen decision</h3><p>Astra preference: <b>{esc(decision.get('astra_preferred_id'))}</b><br>Jev selection: <b>{esc(decision.get('selected_id'))}</b></p>
          <div class="scroll"><table><thead><tr><th>Procedure</th><th>Score / 3</th><th>Jev confidence</th></tr></thead><tbody>{''.join(score_rows)}</tbody></table></div>
          <p>These judgments preceded inference and label access. Confidence is not count accuracy.</p>
          <p><a href="artifacts/{task}/decision.json">Full frozen decision</a> · <a href="artifacts/{task}/proposal.json">Astra proposals</a></p></article></div>
          <div class="notice"><b>Final harness:</b> {esc(final['status'])}, count {esc(final.get('value'))}; review <b>{esc(final['review_status'])}</b>, support {esc(final.get('review_support'))}.<br>
          <b>Fresh vanilla:</b> {esc(row['vanilla']['status'])}, count {esc(row['vanilla'].get('value'))}.</div>
          <p>{esc(final.get('explanation', final.get('error', '')))}</p>
          <p>{esc(' '.join(final.get('limitations', [])))}</p>
          <details><summary>Final answer and separate review record</summary><pre>{esc(json.dumps(final, indent=2))}</pre></details>
          <h3>Every fixed procedure, evaluated after the selected answer</h3><div class="grid">{''.join(cards)}</div>
          <p><a href="../../{RUNS}/{task}/routing/trajectory.json">Local routing Harbor trace</a> · <a href="../../{RUNS}/{task}/vanilla/trajectory.json">Local vanilla Harbor trace</a></p>
        </section>''')
    nav = ''.join(f'<button data-page="{n}" aria-pressed="{str(n == 1).lower()}">{n}</button>' for n in range(1, len(pages)+1))
    diagnostics = data["routing_diagnostics"]
    content = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Specialist routing · BBBC039 review</title>
<style>:root{color-scheme:light;--ink:#192c36;--accent:#075e68}*{box-sizing:border-box}body{margin:0;background:#f5f7f6;color:var(--ink);font:16px/1.6 system-ui,sans-serif}main{max-width:1160px;margin:auto;padding:40px 22px}h1{font-size:clamp(2rem,5vw,3.3rem);line-height:1.1;max-width:850px}h2{font-size:1.7rem}h3{line-height:1.3}a{color:var(--accent);text-underline-offset:3px}p,td,th,.filename{overflow-wrap:anywhere}.eyebrow{color:#4a6269;font-weight:700;letter-spacing:.08em;text-transform:uppercase}.notice{padding:18px 22px;border-left:4px solid #b97816;background:#fff4dc;border-radius:4px}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}article{background:white;border:1px solid #d6e0df;padding:18px;border-radius:12px;min-width:0}img{width:100%;height:auto;border-radius:6px;background:#0b1215}table{width:100%;border-collapse:collapse;background:white}th,td{text-align:left;padding:12px;border-bottom:1px solid #dce4e4}th{background:#e6eeee;word-break:normal;overflow-wrap:normal}.scroll{overflow:auto}nav{display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:20px 0;position:sticky;top:0;background:#f5f7f6;z-index:1}button{border:1px solid #8da4a5;background:white;color:var(--ink);border-radius:7px;padding:10px 17px;font:inherit;cursor:pointer}button[aria-pressed=true]{background:var(--accent);color:white}pre{white-space:pre-wrap;overflow-wrap:anywhere;padding:18px;background:#edf1f0;border-radius:8px;font-size:13px}summary{cursor:pointer;padding:14px 0}footer{margin-top:50px;border-top:1px solid #ccd8d7;padding-top:20px}@media(max-width:700px){main{padding:25px 14px}.grid{grid-template-columns:1fr}th,td{padding:9px;font-size:14px}}[hidden]{display:none!important}</style>
<main><p class="eyebrow">Vision harness · routing v1 · 22 September 2026</p><h1>Can a router choose the right specialist?</h1>
<p>Six additional official BBBC039 test images. Two pretrained model families, four registered procedures, one frozen Astra preference and a Jev score for every eligible procedure.</p>
<div class="notice"><b>This is a new review policy.</b> The final harness preserves grounded estimates with a separate <em>supported</em> or <em>caution</em> label. Historical full-harness runs required review approval to return a count. Their completion rates are not directly comparable.</div>
<h2>What this run established</h2><p>The specialist capability is useful, but this routing policy did not beat vanilla Astra. Cellpose-SAM was the best fixed procedure at <b>4.23%</b> mean count error; vanilla scored <b>5.44%</b> and the final routed harness <b>5.71%</b>. All six routed results carry a caution flag. Jev selected a best-performing procedure on two of six images. These are exploratory results on this cohort, not universal model rankings.</p><h2>Measured results</h2><p>Lower count MAPE is better. A value is shown only when an arm returned all six numerical results. Matching a total count does not establish that every predicted nucleus is correctly segmented.</p>
<div class="scroll"><table><thead><tr><th>Arm</th><th>Numeric results</th><th>Count MAPE</th><th>Exact</th></tr></thead><tbody>''' + ''.join(table) + '''</tbody></table></div>
<p>Astra-preferred and Jev-selected measurement rows are routing diagnostics using the frozen choices. They are not additional answer-generation runs. All other procedure results were withheld from the chosen answer.</p>
<p>''' + esc(json.dumps(diagnostics)) + '''</p><p>Review statuses: ''' + esc(json.dumps(data['review_counts'])) + '''.</p>
<h2>Inspect the evidence</h2><p>Select an image to compare its original pixels, measured masks, routing scores and final answer. Overlays open at full resolution.</p><nav aria-label="Benchmark images"><span>Image</span>''' + nav + '''<span id="page-status" aria-live="polite">1 / 6</span></nav>''' + ''.join(pages) + '''
<footer><h2>Scope and reproduction</h2><p>These are real benchmark images, with reference counts decoded from published annotations only after inference. The previous cohort was excluded. Public pretrained-data exposure is unknown; this is a small exploratory test, not independent validation of a universal router. Derived count MAPE is not the published BBBC039 segmentation metric.</p><p>The specialists ran in separate native environments on the Mac; Astra and Jev used hosted APIs. Harbor ATIF traces were exported and validated. This was not a Harbor container evaluation. Jev received structured evidence, not image pixels.</p><p><a href="selection.json">Frozen protocol</a> · <a href="results.json">All numerical results</a> · <a href="final-score.md">Score table</a> · <a href="../../docs/model-routing.md">File map, commands and architecture</a> · <a href="https://bbbc.broadinstitute.org/BBBC039">Official dataset</a></p></footer></main>
<script>document.querySelectorAll('[data-page]').forEach(b=>b.addEventListener('click',()=>{const n=b.dataset.page;document.querySelectorAll('.task').forEach(s=>s.hidden=s.id!=='task-'+n);document.querySelectorAll('[data-page]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));document.getElementById('page-status').textContent=n+' / '+document.querySelectorAll('.task').length;}));</script></html>'''
    (REPORT / "index.html").write_text(content)
    research = Path("runs/research-routing-20260922")
    if (research / "result.json").exists():
        destination = Path("reports/model-research-20260922")
        destination.mkdir(exist_ok=True)
        for name in ("result.json", "sources.json", "proposals.json", "research-notes.md"):
            shutil.copy2(research / name, destination / name)
        write_json(destination / "provenance.json", {"run": str(research), "status": "live discovery and Jev scoring completed", "advisory_only": True, "source_validation": "cited URLs occur in actual search trace; this does not verify every claim or license interpretation"})
    print(f"Rendered {REPORT / 'index.html'}")


if __name__ == "__main__":
    render()
