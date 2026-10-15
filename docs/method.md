# Method notes

## Split discipline

- `dev` (16 questions) is for building systems and graders and for choosing settings.
- `heldout` (12 questions) is for the release decision only. Every candidate run on it is appended to `heldout-log.jsonl` in the results folder, and the report prints the count.
- Both splits were written together, before any system existed, from the same 8 help center pages. Question wording in held out was written to sound like customers rather than the docs, which is the realistic case and the reason a held out set exists.

## How the candidate setting was chosen

The offline candidate has one setting: abstain when the best matching sentence shares fewer than N content words with the question. On dev:

| N | Correct abstain (4 not covered) | False abstain (12 answerable) |
|---|---|---|
| 1 | 1 of 4 | 0 of 12 |
| 2 | 3 of 4 | 0 of 12 |
| 3 | 4 of 4 | 4 of 12 |

N = 2 was chosen on dev and fixed in `pevals/systems/offline.py` before held out was run for the first time. Held out then showed 2 of 9 false abstentions, which is why the release rule holds the candidate.

## Change log

- **2026-10-15, before first publish.** The evidence grader was tightened. It used to accept any verbatim quote from an expected page; it now also requires the quoted text to contain every expected fact, because citing the right page with the wrong sentence is not evidence. Systems and data were unchanged; results were regenerated with one held out run per variant.

## What a live run adds

The offline substitutes cannot paraphrase, so their failures are mostly retrieval failures. A live model will fail differently: answers that rephrase the expected fact (graded as a miss), quotes that are lightly edited (graded as unsupported), and refusals (graded as schema failures). Those are the cases worth reading row by row in `results/claude/*.jsonl` after the first live run.
