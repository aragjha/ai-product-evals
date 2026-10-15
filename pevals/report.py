"""Metrics, the paired baseline versus candidate comparison, and the release decision."""
from __future__ import annotations

import json
from pathlib import Path

from .pricing import known

# Metrics that must reproduce exactly on a rerun of a deterministic system.
DETERMINISTIC = ("n", "success_rate", "schema_valid_rate", "evidence_support_rate", "answered",
                 "correct_abstain_rate", "false_abstain_rate", "cost_usd")


def _rate(num: int, den: int) -> float | None:
    return round(num / den, 3) if den else None


def _pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    v = sorted(values)
    return v[min(len(v) - 1, round(p * (len(v) - 1)))]


def metrics(rows: list[dict]) -> dict:
    g = [r["grade"] for r in rows]
    answerable = [x for x in g if x["answerable"]]
    unanswerable = [x for x in g if not x["answerable"]]
    supported = [x["evidence_supported"] for x in g if x["evidence_supported"] is not None]
    cost = round(sum(r["usage"]["cost_usd"] for r in rows), 6)
    lat = [r["latency_ms"] for r in rows]
    return {
        "n": len(g),
        "success_rate": _rate(sum(x["success"] for x in g), len(g)),
        "schema_valid_rate": _rate(sum(x["schema_valid"] for x in g), len(g)),
        "answered": len(supported),
        "evidence_support_rate": _rate(sum(supported), len(supported)),
        "correct_abstain_rate": _rate(sum(x["abstained"] for x in unanswerable), len(unanswerable)),
        "false_abstain_rate": _rate(sum(x["abstained"] for x in answerable), len(answerable)),
        "latency_ms_p50": _pct(lat, 0.5),
        "latency_ms_p95": _pct(lat, 0.95),
        "input_tokens": sum(r["usage"]["input_tokens"] for r in rows),
        "output_tokens": sum(r["usage"]["output_tokens"] for r in rows),
        "cost_usd": cost,
        "cost_per_100_usd": round(cost * 100 / len(g), 4) if g else 0.0,
    }


def paired(base: dict, cand: dict) -> dict:
    """Same questions, both systems: which items the candidate fixed and which it broke."""
    b = {x["id"]: x["success"] for x in base["items"]}
    c = {x["id"]: x["success"] for x in cand["items"]}
    if set(b) != set(c):
        raise SystemExit("Baseline and candidate were run on different questions; cannot pair them.")
    return {"fixed": sorted(i for i in b if not b[i] and c[i]),
            "broke": sorted(i for i in b if b[i] and not c[i]),
            "both_fail": sorted(i for i in b if not b[i] and not c[i])}


def decide(base: dict, cand: dict, rule: dict) -> dict:
    mb, mc = base["metrics"], cand["metrics"]
    p = paired(base, cand)
    checks = [
        ("decision made on the held out split", cand["meta"]["split"] == rule["decide_on_split"],
         f"split = {cand['meta']['split']}"),
        ("success does not drop", (mc["success_rate"] - mb["success_rate"]) >= rule["min_success_delta"],
         f"{mb['success_rate']} -> {mc['success_rate']}"),
        ("schema valid", mc["schema_valid_rate"] >= rule["min_schema_valid_rate"], f"{mc['schema_valid_rate']}"),
        ("evidence supported", (mc["evidence_support_rate"] or 0) >= rule["min_evidence_support_rate"],
         f"{mc['evidence_support_rate']} over {mc['answered']} answers"),
        ("false abstain within limit", (mc["false_abstain_rate"] or 0) <= rule["max_false_abstain_rate"],
         f"{mc['false_abstain_rate']}"),
        ("few new failures", len(p["broke"]) <= rule["max_new_failures"], f"broke {p['broke'] or 'none'}"),
        ("cost within budget", mc["cost_per_100_usd"] <= rule["max_cost_per_100_usd"],
         f"${mc['cost_per_100_usd']} per 100 questions"),
        ("p95 latency within budget", mc["latency_ms_p95"] <= rule["max_p95_latency_ms"],
         f"{mc['latency_ms_p95']} ms"),
    ]
    if not known(cand["meta"]["model"]) and cand["meta"]["system"] != "offline":
        checks.append(("model has a known price", False, cand["meta"]["model"]))
    failed = [c for c in checks if not c[1]]
    return {"decision": "SHIP" if not failed else "HOLD",
            "checks": [{"check": c[0], "pass": c[1], "value": c[2]} for c in checks],
            "paired": p}


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def _fmt(v) -> str:
    if v is None:
        return "n/a"
    return f"{v:.2f}" if isinstance(v, float) else str(v)


ROWS = [
    ("Success", "success_rate"), ("Schema valid", "schema_valid_rate"),
    ("Evidence supported (of answers given)", "evidence_support_rate"), ("Answers given", "answered"),
    ("Correct abstain (unanswerable)", "correct_abstain_rate"), ("False abstain (answerable)", "false_abstain_rate"),
    ("Latency p50 ms", "latency_ms_p50"), ("Latency p95 ms", "latency_ms_p95"),
    ("Cost per 100 questions USD", "cost_per_100_usd"),
]


def markdown(base: dict, cand: dict, decision: dict, heldout_runs: int | None = None, judge: dict | None = None) -> str:
    mb, mc, meta = base["metrics"], cand["metrics"], cand["meta"]
    out = [f"# Eval report: {meta['split']} split", "",
           f"> **{meta['label']}.** Dataset {meta['dataset']} ({meta['dataset_sha']}), {mc['n']} questions."
           f" Generated {meta['generated']}.", "",
           f"| Metric | Baseline ({base['meta']['model']}) | Candidate ({meta['model']}) |", "|---|---|---|"]
    out += [f"| {label} | {_fmt(mb[k])} | {_fmt(mc[k])} |" for label, k in ROWS]
    out += ["", f"Baseline: {base['meta']['system_version']}. Candidate: {meta['system_version']}.", "",
            f"## Decision: {decision['decision']}", "", "| Check | Result | Value |", "|---|---|---|"]
    out += [f"| {c['check']} | {'pass' if c['pass'] else 'FAIL'} | {c['value']} |" for c in decision["checks"]]
    p = decision["paired"]
    out += ["", "## Paired items", "",
            f"- Fixed by the candidate: {', '.join(p['fixed']) or 'none'}",
            f"- Broken by the candidate: {', '.join(p['broke']) or 'none'}",
            f"- Wrong in both: {', '.join(p['both_fail']) or 'none'}"]
    if heldout_runs is not None:
        out += ["", f"Candidate runs on the held out split logged in this folder: {heldout_runs}."
                " More than one means the held out set may have been used for tuning."]
    out += ["", "## Judge scores (not used in the decision)", ""]
    out += [judge_section(judge)] if judge else ["Not run. The judge is optional and needs a live key."]
    return "\n".join(out) + "\n"


def judge_section(judge: dict) -> str:
    return (f"{judge['label']}. Judge model {judge['model']}, {judge['n']} answers scored 1 to 5 for clarity:"
            f" mean {judge['mean']:.2f}. Kept apart from the deterministic checks above.")
