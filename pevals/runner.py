"""Run one system variant over one split, grade every item, and save rows plus a summary."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import time
from pathlib import Path

from . import data, graders, report

AVG_OUTPUT_TOKENS = 150  # used only for the pre run cost estimate


def make_system(system: str, variant: str, model: str | None = None, client=None):
    if system == "offline":
        from .systems.offline import OfflineSystem
        return OfflineSystem(variant)
    if system == "claude":
        from .systems.claude import ClaudeSystem
        return ClaudeSystem(variant, model=model, client=client)
    raise SystemExit(f"Unknown system '{system}'. Use offline or claude.")


def system_version(sys_obj) -> str:
    if hasattr(sys_obj, "system_prompt"):
        return "prompt sha256 " + hashlib.sha256(sys_obj.system_prompt.encode()).hexdigest()[:12]
    from .systems import offline
    return f"min_overlap={offline.CANDIDATE_MIN_OVERLAP}" if sys_obj.variant == "candidate" else "always answers"


def estimate_cost(sys_obj, n_questions: int) -> float:
    """Rough upper estimate before a live run: 4 characters per token."""
    from .pricing import cost_usd
    prompt_chars = len(getattr(sys_obj, "system_prompt", "")) + len(getattr(sys_obj, "docs", "")) + 200
    return cost_usd(sys_obj.model, n_questions * prompt_chars // 4, n_questions * AVG_OUTPUT_TOKENS)


def run(system: str, variant: str, split: str, out_dir: Path, model: str | None = None,
        max_cost_usd: float = 1.0, client=None) -> dict:
    qs = data.questions(split)
    docs = data.corpus()
    sys_obj = make_system(system, variant, model, client)
    rows, spent = [], 0.0
    for q in qs:
        t0 = time.perf_counter()
        raw, usage = sys_obj.answer(q["question"])
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        spent += usage["cost_usd"]
        rows.append({"id": q["id"], "question": q["question"], "raw": raw, "latency_ms": latency_ms,
                     "usage": usage, "grade": graders.grade(q, raw, docs)})
        if spent > max_cost_usd:
            raise SystemExit(f"Stopped: spent ${spent:.4f}, over --max-cost-usd {max_cost_usd}. Partial rows not saved.")

    meta = {
        "system": system, "variant": variant, "split": split, "model": sys_obj.model,
        "system_version": system_version(sys_obj), "label": sys_obj.label,
        "dataset": "v1", "dataset_sha": data.dataset_sha(),
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    }
    summary = {"meta": meta, "metrics": report.metrics(rows), "items": [r["grade"] for r in rows]}
    d = out_dir / system
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{variant}-{split}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (d / f"{variant}-{split}.json").write_text(json.dumps(summary, indent=2) + "\n")
    if split == "heldout":
        with (out_dir / "heldout-log.jsonl").open("a") as f:
            f.write(json.dumps({k: meta[k] for k in ("generated", "system", "variant", "model", "system_version",
                                                     "dataset_sha")}) + "\n")
    return summary
