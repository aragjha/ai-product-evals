# Eval report: dev split

> **fixture: deterministic offline substitute, not a model.** Dataset v1 (28a4a15c83da), 16 questions. Generated 2026-10-15T06:37:11+00:00.

| Metric | Baseline (offline-baseline) | Candidate (offline-candidate) |
|---|---|---|
| Success | 0.69 | 0.88 |
| Schema valid | 1.00 | 1.00 |
| Evidence supported (of answers given) | 0.69 | 0.85 |
| Answers given | 16 | 13 |
| Correct abstain (unanswerable) | 0.00 | 0.75 |
| False abstain (answerable) | 0.00 | 0.00 |
| Latency p50 ms | 0.71 | 0.52 |
| Latency p95 ms | 0.75 | 0.62 |
| Cost per 100 questions USD | 0.00 | 0.00 |

Baseline: always answers. Candidate: min_overlap=2.

## Decision: HOLD

| Check | Result | Value |
|---|---|---|
| decision made on the held out split | FAIL | split = dev |
| success does not drop | pass | 0.688 -> 0.875 |
| schema valid | pass | 1.0 |
| evidence supported | FAIL | 0.846 over 13 answers |
| false abstain within limit | pass | 0.0 |
| few new failures | pass | broke none |
| cost within budget | pass | $0.0 per 100 questions |
| p95 latency within budget | pass | 0.62 ms |

## Paired items

- Fixed by the candidate: d14, d15, d16
- Broken by the candidate: none
- Wrong in both: d11, d13

Candidate runs on the held out split logged in this folder: 1. More than one means the held out set may have been used for tuning.

## Judge scores (not used in the decision)

Not run. The judge is optional and needs a live key.
