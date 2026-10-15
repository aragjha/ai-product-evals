# Eval report: heldout split

> **fixture: deterministic offline substitute, not a model.** Dataset v1 (28a4a15c83da), 12 questions. Generated 2026-10-15T06:37:11+00:00.

| Metric | Baseline (offline-baseline) | Candidate (offline-candidate) |
|---|---|---|
| Success | 0.42 | 0.58 |
| Schema valid | 1.00 | 1.00 |
| Evidence supported (of answers given) | 0.42 | 0.57 |
| Answers given | 12 | 7 |
| Correct abstain (unanswerable) | 0.00 | 1.00 |
| False abstain (answerable) | 0.00 | 0.22 |
| Latency p50 ms | 0.53 | 0.46 |
| Latency p95 ms | 0.53 | 0.53 |
| Cost per 100 questions USD | 0.00 | 0.00 |

Baseline: always answers. Candidate: min_overlap=2.

## Decision: HOLD

| Check | Result | Value |
|---|---|---|
| decision made on the held out split | pass | split = heldout |
| success does not drop | pass | 0.417 -> 0.583 |
| schema valid | pass | 1.0 |
| evidence supported | FAIL | 0.571 over 7 answers |
| false abstain within limit | FAIL | 0.222 |
| few new failures | pass | broke ['h01'] |
| cost within budget | pass | $0.0 per 100 questions |
| p95 latency within budget | pass | 0.53 ms |

## Paired items

- Fixed by the candidate: h10, h11, h12
- Broken by the candidate: h01
- Wrong in both: h03, h04, h07, h08

Candidate runs on the held out split logged in this folder: 1. More than one means the held out set may have been used for tuning.

## Judge scores (not used in the decision)

Not run. The judge is optional and needs a live key.
