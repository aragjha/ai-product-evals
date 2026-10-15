"""The answer contract every system must return, and a stdlib validator for it."""
from __future__ import annotations

import json

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "abstain": {"type": "boolean"},
        "citations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"doc_id": {"type": "string"}, "quote": {"type": "string"}},
                "required": ["doc_id", "quote"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["answer", "abstain", "citations"],
    "additionalProperties": False,
}


def parse(raw: str) -> tuple[dict | None, str]:
    """Return (output, "") when raw is valid JSON matching OUTPUT_SCHEMA, else (None, reason)."""
    try:
        out = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as e:
        return None, f"not JSON: {e}"
    if not isinstance(out, dict):
        return None, "not an object"
    if set(out) != {"answer", "abstain", "citations"}:
        return None, f"wrong keys: {sorted(out)}"
    if not isinstance(out["answer"], str) or not isinstance(out["abstain"], bool):
        return None, "answer must be a string and abstain a boolean"
    if not isinstance(out["citations"], list):
        return None, "citations must be a list"
    for c in out["citations"]:
        if not isinstance(c, dict) or set(c) != {"doc_id", "quote"} or not all(isinstance(v, str) for v in c.values()):
            return None, "each citation needs exactly doc_id and quote as strings"
    return out, ""
