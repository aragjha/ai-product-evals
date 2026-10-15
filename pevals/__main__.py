"""Command line: python -m pevals <command>."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import data, report, runner

ROOT = data.ROOT
RULE = ROOT / "config" / "release_rule.json"


def _heldout_runs(out: Path) -> int:
    log = out / "heldout-log.jsonl"
    if not log.exists():
        return 0
    return sum(json.loads(line)["variant"] == "candidate" for line in log.read_text().splitlines() if line.strip())


def _judge(out: Path, system: str, variant: str, split: str) -> dict | None:
    p = out / system / f"{variant}-{split}.judge.json"
    return json.loads(p.read_text()) if p.exists() else None


def write_report(out: Path, system: str, split: str) -> dict:
    base = report.load(out / system / f"baseline-{split}.json")
    cand = report.load(out / system / f"candidate-{split}.json")
    rule = json.loads(RULE.read_text())
    decision = report.decide(base, cand, rule)
    md = report.markdown(base, cand, decision, _heldout_runs(out), _judge(out, system, "candidate", split))
    (out / f"report-{system}-{split}.md").write_text(md)
    return decision


def _confirm_live(a, n_runs: int) -> None:
    sys_obj = runner.make_system("claude", "candidate", a.model)
    est = runner.estimate_cost(sys_obj, len(data.questions("dev")) + len(data.questions("heldout"))) * n_runs / 2
    print(f"Live run on {sys_obj.model}: estimated about ${est:.2f}, hard stop at ${a.max_cost_usd:.2f} per variant and split.")
    if not a.yes:
        raise SystemExit("Add --yes to spend this. Nothing was called.")


def cmd_check_data(a):
    changed = data.check_manifest()
    if changed:
        raise SystemExit(f"Dataset v1 changed since MANIFEST.json: {changed}. Make a new version instead of editing v1.")
    print(f"Dataset v1 matches MANIFEST.json ({data.dataset_sha()}).")


def cmd_run(a):
    if a.system == "claude":
        _confirm_live(a, 1)
    s = runner.run(a.system, a.variant, a.split, Path(a.out), a.model, a.max_cost_usd)
    print(json.dumps(s["metrics"], indent=2))


def cmd_compare(a):
    d = write_report(Path(a.out), a.system, a.split)
    print(f"{d['decision']}  ->  {Path(a.out) / f'report-{a.system}-{a.split}.md'}")
    for c in d["checks"]:
        print(f"  {'pass' if c['pass'] else 'FAIL'}  {c['check']}: {c['value']}")


def cmd_judge(a):
    from . import judge
    if not a.yes:
        raise SystemExit("The judge makes live calls. Add --yes to spend.")
    r = judge.run(Path(a.out) / a.system / f"{a.variant}-{a.split}.jsonl", a.model)
    print(f"Judge mean {r['mean']:.2f} over {r['n']} answers, ${r['cost_usd']:.4f}")


def cmd_demo(a):
    """Baseline and candidate on dev, then held out, then the release decision."""
    cmd_check_data(a)
    out = Path(a.out)
    if a.system == "claude":
        _confirm_live(a, 4)
    for split in ("dev", "heldout"):
        for variant in ("baseline", "candidate"):
            runner.run(a.system, variant, split, out, a.model, a.max_cost_usd)
    for split in ("dev", "heldout"):
        base = report.load(out / a.system / f"baseline-{split}.json")
        cand = report.load(out / a.system / f"candidate-{split}.json")
        print(f"\n{split} ({cand['meta']['label']})")
        print(f"  {'metric':<38}{'baseline':>10}{'candidate':>11}")
        for label, k in report.ROWS:
            print(f"  {label:<38}{report._fmt(base['metrics'][k]):>10}{report._fmt(cand['metrics'][k]):>11}")
    write_report(out, a.system, "dev")
    d = write_report(out, a.system, "heldout")
    print(f"\nRelease decision on held out: {d['decision']}")
    for c in d["checks"]:
        print(f"  {'pass' if c['pass'] else 'FAIL'}  {c['check']}: {c['value']}")
    print(f"Report: {out / f'report-{a.system}-heldout.md'}")
    if a.check:
        drift = []
        for split in ("dev", "heldout"):
            for variant in ("baseline", "candidate"):
                name = f"{a.system}/{variant}-{split}.json"
                saved, now = report.load(ROOT / "results" / name), report.load(out / name)
                for k in report.DETERMINISTIC:
                    if saved["metrics"][k] != now["metrics"][k]:
                        drift.append((name, k, saved["metrics"][k], now["metrics"][k]))
                if saved["items"] != now["items"]:
                    drift.append((name, "items", "", ""))
        if drift:
            print(f"FAIL: results differ from results/: {drift}")
            sys.exit(1)
        print("OK: deterministic metrics and per item grades match results/")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="pevals", description="Baseline versus candidate evals for a grounded answer task.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p, variant=True, split=True):
        p.add_argument("--system", default="offline", choices=["offline", "claude"])
        p.add_argument("--out", default="out")
        if variant:
            p.add_argument("--variant", default="candidate", choices=["baseline", "candidate"])
        if split:
            p.add_argument("--split", default="dev", choices=list(data.SPLITS))
        p.add_argument("--model", default=None)
        p.add_argument("--max-cost-usd", type=float, default=1.0, help="hard stop per variant and split (live only)")
        p.add_argument("--yes", action="store_true", help="confirm spending on a live run")

    p = sub.add_parser("check-data", help="verify the dataset matches its manifest")
    p.set_defaults(fn=cmd_check_data)
    p = sub.add_parser("run", help="run one variant on one split")
    common(p)
    p.set_defaults(fn=cmd_run)
    p = sub.add_parser("compare", help="baseline versus candidate report and release decision")
    common(p, variant=False)
    p.set_defaults(fn=cmd_compare)
    p = sub.add_parser("judge", help="optional live clarity judge, reported separately")
    common(p)
    p.set_defaults(fn=cmd_judge)
    p = sub.add_parser("demo", help="both variants, both splits, then the decision")
    common(p, variant=False, split=False)
    p.add_argument("--check", action="store_true", help="exit 1 if results differ from results/")
    p.set_defaults(fn=cmd_demo)

    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
