"""Offline substitutes for a baseline and a candidate system.

These are not language models. They are two small deterministic retrievers that
let the whole harness run with no key and no cost, and that fail in the same ways
a model prompt can fail (answering when it should abstain, abstaining when it
should answer). Results from them are labelled "fixture" everywhere.

baseline:  answer with the best matching sentence, always.
candidate: same retrieval, but abstain when the best match is weak.
"""
from __future__ import annotations

import json
import re

from .. import data

STOP = set("""a an the is are was be been do does did can could will would should i my me you your we our it its
of to in on at for from by with and or not no how what which who when where why there this that these those
any every one get got have has if into up out about than then so as just more most much many lumen""".split())

# Set on the dev split only (see docs/method.md). Never tuned on held out.
CANDIDATE_MIN_OVERLAP = 2


def _stem(w: str) -> str:
    return w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w


def tokens(s: str) -> set[str]:
    return {_stem(w) for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in STOP}


def best_sentence(question: str, version: str = "v1") -> tuple[int, str, str]:
    q = tokens(question)
    scored = [(len(q & tokens(sent)), doc_id, sent) for doc_id, sent in data.sentences(version)]
    return max(scored, key=lambda t: t[0])  # first best on ties, so the result is stable


class OfflineSystem:
    label = "fixture: deterministic offline substitute, not a model"

    def __init__(self, variant: str):
        if variant not in ("baseline", "candidate"):
            raise SystemExit(f"Unknown variant '{variant}'.")
        self.variant = variant
        self.model = f"offline-{variant}"

    def answer(self, question: str) -> tuple[str, dict]:
        score, doc_id, sent = best_sentence(question)
        if self.variant == "candidate" and score < CANDIDATE_MIN_OVERLAP:
            out = {"answer": "The help center does not answer this.", "abstain": True, "citations": []}
        else:
            out = {"answer": sent, "abstain": False, "citations": [{"doc_id": doc_id, "quote": sent}]}
        return json.dumps(out), {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
