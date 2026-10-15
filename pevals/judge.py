"""Optional model judge for answer clarity. Live only, never in CI, never in the release decision.

Deterministic checks say whether an answer is right and grounded. The judge only adds
a 1 to 5 clarity score, saved separately so the two kinds of evidence never mix.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from .pricing import cost_usd

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {"score": {"type": "integer"}, "reason": {"type": "string"}},
    "required": ["score", "reason"],
    "additionalProperties": False,
}

JUDGE_PROMPT = """You rate how clear a support answer is for a customer. Ignore whether it is correct; another check covers that.
5 = direct, plain, complete in one read. 3 = understandable but padded or indirect. 1 = confusing.
Return JSON: "score" (integer 1 to 5) and "reason" (one sentence)."""


def run(rows_path: Path, model: str | None = None, client=None) -> dict:
    model = model or os.environ.get("PEVALS_JUDGE_MODEL", "claude-sonnet-5-5")
    if client is None:
        try:
            import anthropic
        except ImportError:
            raise SystemExit("The judge needs the SDK: pip install anthropic")
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise SystemExit("Set ANTHROPIC_API_KEY (see .env.example) to run the judge.")
        client = anthropic.Anthropic()
    scores, cost = [], 0.0
    for line in rows_path.read_text().splitlines():
        row = json.loads(line)
        if not row["grade"]["schema_valid"] or row["grade"]["abstained"]:
            continue
        answer = json.loads(row["raw"])["answer"]
        resp = client.messages.create(
            model=model, max_tokens=500, system=JUDGE_PROMPT,
            messages=[{"role": "user", "content": f"Question: {row['question']}\nAnswer: {answer}"}],
            output_config={"format": {"type": "json_schema", "schema": JUDGE_SCHEMA}},
        )
        cost += cost_usd(model, resp.usage.input_tokens, resp.usage.output_tokens)
        text = next((b.text for b in resp.content if b.type == "text"), "{}")
        s = json.loads(text).get("score")
        if isinstance(s, int) and 1 <= s <= 5:
            scores.append({"id": row["id"], "score": s})
    result = {"label": "measured: live model judge", "model": model, "n": len(scores),
              "mean": sum(x["score"] for x in scores) / len(scores) if scores else 0.0,
              "cost_usd": round(cost, 6), "scores": scores}
    rows_path.with_suffix(".judge.json").write_text(json.dumps(result, indent=2) + "\n")
    return result
