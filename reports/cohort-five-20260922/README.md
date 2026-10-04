# Five-task live comparison

Highest observed accuracy: Vanilla Astra, Astra + OpenCV, Tools + Jev selection, Full harness (5/5 correct).

Among the accuracy leaders, Vanilla Astra had the lowest observed mean runtime (6.4s). This cohort shows no accuracy benefit from the added layers when vanilla already answers every task correctly.

One attempt per preselected test-split task, five modes, 25 trials. This is an exploratory result; it does not establish general superiority.

| Mode | Correct | Abstentions | Errors | Mean runtime | Astra tokens in/out | Jev tokens in/out |
|---|---:|---:|---:|---:|---:|---:|
| Vanilla Astra | 5/5 | 0 | 0 | 6.4s | 3422/605 | 0/0 |
| Astra + OpenCV | 5/5 | 0 | 0 | 24.2s | 18889/4409 | 0/0 |
| Tools + Jev selection | 5/5 | 0 | 0 | 23.7s | 23722/4092 | 9452/178 |
| Tools + Jev review | 4/5 | 0 | 1 | 40.2s | 18884/4094 | 9676/100 |
| Full harness | 5/5 | 0 | 0 | 25.3s | 22805/4172 | 22336/274 |

## Task-by-task answers

| Task | Expected | Vanilla Astra | Astra + OpenCV | Tools + Jev selection | Tools + Jev review | Full harness |
|---|---|---|---|---|---|---|
| Separated-circle counting | 12 | PASS: 12.0 (answered) | PASS: 12.0 (answered) | PASS: 12.0 (answered) | PASS: 12.0 (answered) | PASS: 12.0 (answered) |
| Color-filtered counting | 4 | PASS: 4.0 (answered) | PASS: 4.0 (answered) | PASS: 4.0 (answered) | PASS: 4.0 (answered) | PASS: 4.0 (answered) |
| Left/right position | right | PASS: right (answered) | PASS: right (answered) | PASS: right (answered) | PASS: right (answered) | PASS: right (answered) |
| Pixel distance | 273.80467490530543 | PASS: 273.8 (answered) | PASS: 273.8047 (answered) | PASS: 273.805 (answered) | PASS: 273.805 (answered) | PASS: 273.805 (answered) |
| Touching-circle counting | 10 | PASS: 10.0 (answered) | PASS: 10.0 (answered) | PASS: 10.0 (answered) | FAIL: None (error) | PASS: 10.0 (answered) |

## Interpretation

Counts and position are exact; distance permits ±2 pixels. Both the initial verifier and this report's independent re-scoring agree. All failures and abstentions are retained.

Plans are independently generated in each mode. Added model calls, competing methods, and review retries change compute. Compare accuracy and time together; do not attribute a difference solely to Jev's selector.

Token counts are separated by provider and show recorded usage only. A failed response parse can leave a started call without recorded usage; totals are then lower bounds. Check started_calls versus calls in results.json. Dollar cost is not estimated because versioned pricing is not configured.

## Traces

Run `uv run harbor view jobs/cohort-five-20260922-v2` for the full viewer. The HTML report links each trial's JSON trajectory, event log and artifact directory.

## Preflight correction

An initial five-trial baseline batch exposed a harness validator bug: it rejected citations to the image actually supplied. The failed batch is preserved separately. The validator was fixed for all modes and the complete comparison restarted; task selection, prompts, model settings and grading were unchanged. These test-split examples were therefore seen during infrastructure debugging.
