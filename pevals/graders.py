"""Deterministic graders. No model is involved in anything in this file.

Each grader takes one question (with its expected answer) and one system output
and returns a boolean or None (not applicable). Aggregation lives in report.py.
"""
from __future__ import annotations

import re

from . import schema


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", s.lower())).strip()


def schema_valid(raw: str) -> bool:
    return schema.parse(raw)[0] is not None


def success(q: dict, out: dict | None) -> bool:
    """Answerable: did not abstain and the answer contains every expected fact.
    Unanswerable: abstained."""
    if out is None:
        return False
    if not q["answerable"]:
        return out["abstain"]
    answer = norm(out["answer"])
    return not out["abstain"] and all(norm(f) in answer for f in q["expected_facts"])


def evidence_supported(q: dict, out: dict | None, docs: dict[str, str]) -> bool | None:
    """For answers given (not abstained): every quote appears verbatim in the doc it cites,
    and every expected fact appears in a quote from an expected doc. Citing the right page
    with the wrong sentence does not count. An answer to an unanswerable question cannot be
    supported. None when the system abstained or the output was invalid."""
    if out is None or out["abstain"]:
        return None
    if not out["citations"] or not q["answerable"]:
        return False
    for c in out["citations"]:
        if c["doc_id"] not in docs or not norm(c["quote"]) or norm(c["quote"]) not in norm(docs[c["doc_id"]]):
            return False
    quoted = " ".join(norm(c["quote"]) for c in out["citations"] if c["doc_id"] in q["expected_docs"])
    return all(norm(f) in quoted for f in q["expected_facts"])


def grade(q: dict, raw: str, docs: dict[str, str]) -> dict:
    out, reason = schema.parse(raw)
    return {
        "id": q["id"],
        "answerable": q["answerable"],
        "schema_valid": out is not None,
        "schema_error": reason,
        "abstained": bool(out and out["abstain"]),
        "success": success(q, out),
        "evidence_supported": evidence_supported(q, out, docs),
    }
