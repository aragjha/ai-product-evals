import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from pevals import data, graders, report, runner

DOCS = data.corpus()
Q_ANS = {"id": "t1", "question": "How long do deleted notes stay in Trash?", "answerable": True,
         "expected_facts": ["30 days"], "expected_docs": ["trash"]}
Q_UNANS = {"id": "t2", "question": "Is there a dark mode?", "answerable": False,
           "expected_facts": [], "expected_docs": []}
GOOD = json.dumps({"answer": "They stay for 30 days.", "abstain": False,
                   "citations": [{"doc_id": "trash", "quote": "Deleted notes stay in Trash for 30 days."}]})
ABSTAIN = json.dumps({"answer": "Not covered.", "abstain": True, "citations": []})
RULE = json.loads((data.ROOT / "config" / "release_rule.json").read_text())


class Graders(unittest.TestCase):
    def test_good_answer_passes_everything(self):
        g = graders.grade(Q_ANS, GOOD, DOCS)
        self.assertTrue(g["schema_valid"] and g["success"] and g["evidence_supported"])

    def test_schema_failures(self):
        for raw in ("not json", "[]", json.dumps({"answer": "x", "abstain": "no", "citations": []}),
                    json.dumps({"answer": "x", "abstain": False, "citations": [], "extra": 1}),
                    json.dumps({"answer": "x", "abstain": False, "citations": [{"doc_id": "trash"}]})):
            g = graders.grade(Q_ANS, raw, DOCS)
            self.assertFalse(g["schema_valid"], raw)
            self.assertFalse(g["success"])

    def test_missing_fact_is_not_success(self):
        raw = json.dumps({"answer": "For a while.", "abstain": False,
                          "citations": [{"doc_id": "trash", "quote": "Deleted notes stay in Trash for 30 days."}]})
        self.assertFalse(graders.grade(Q_ANS, raw, DOCS)["success"])

    def test_paraphrased_quote_is_not_evidence(self):
        raw = json.dumps({"answer": "30 days.", "abstain": False,
                          "citations": [{"doc_id": "trash", "quote": "Notes are kept in Trash for 30 days."}]})
        g = graders.grade(Q_ANS, raw, DOCS)
        self.assertTrue(g["success"])
        self.assertFalse(g["evidence_supported"])

    def test_quote_from_the_wrong_doc_is_not_evidence(self):
        raw = json.dumps({"answer": "30 days.", "abstain": False,
                          "citations": [{"doc_id": "billing", "quote": "Deleted notes stay in Trash for 30 days."}]})
        self.assertFalse(graders.grade(Q_ANS, raw, DOCS)["evidence_supported"])

    def test_right_doc_wrong_sentence_is_not_evidence(self):
        raw = json.dumps({"answer": "30 days.", "abstain": False,
                          "citations": [{"doc_id": "trash", "quote": "You can empty Trash early from the Trash menu."}]})
        self.assertFalse(graders.grade(Q_ANS, raw, DOCS)["evidence_supported"])

    def test_answering_an_unanswerable_question_fails(self):
        g = graders.grade(Q_UNANS, GOOD, DOCS)
        self.assertFalse(g["success"])
        self.assertFalse(g["evidence_supported"])

    def test_abstaining_is_right_only_when_unanswerable(self):
        self.assertTrue(graders.grade(Q_UNANS, ABSTAIN, DOCS)["success"])
        g = graders.grade(Q_ANS, ABSTAIN, DOCS)
        self.assertFalse(g["success"])
        self.assertIsNone(g["evidence_supported"])


def _row(q, raw, cost=0.0, ms=1.0):
    return {"id": q["id"], "raw": raw, "latency_ms": ms,
            "usage": {"input_tokens": 10, "output_tokens": 5, "cost_usd": cost}, "grade": graders.grade(q, raw, DOCS)}


def _summary(rows, split="heldout", model="offline-x", system="offline"):
    return {"meta": {"split": split, "model": model, "system": system}, "metrics": report.metrics(rows),
            "items": [r["grade"] for r in rows]}


class MetricsAndDecision(unittest.TestCase):
    def test_metric_definitions(self):
        m = report.metrics([_row(Q_ANS, GOOD), _row(Q_ANS, ABSTAIN), _row(Q_UNANS, ABSTAIN), _row(Q_UNANS, GOOD)])
        self.assertEqual(m["success_rate"], 0.5)
        self.assertEqual(m["false_abstain_rate"], 0.5)
        self.assertEqual(m["correct_abstain_rate"], 0.5)
        self.assertEqual(m["answered"], 2)
        self.assertEqual(m["evidence_support_rate"], 0.5)

    def test_cost_per_100(self):
        m = report.metrics([_row(Q_ANS, GOOD, cost=0.01), _row(Q_UNANS, ABSTAIN, cost=0.03)])
        self.assertEqual(m["cost_per_100_usd"], 2.0)

    def test_paired_fixed_and_broke(self):
        base = _summary([_row(Q_ANS, GOOD), _row(Q_UNANS, GOOD)])
        cand = _summary([_row(Q_ANS, ABSTAIN), _row(Q_UNANS, ABSTAIN)])
        p = report.paired(base, cand)
        self.assertEqual((p["fixed"], p["broke"]), (["t2"], ["t1"]))

    def test_clean_candidate_ships(self):
        base = _summary([_row(Q_ANS, GOOD), _row(Q_UNANS, GOOD)])
        cand = _summary([_row(Q_ANS, GOOD), _row(Q_UNANS, ABSTAIN)])
        self.assertEqual(report.decide(base, cand, RULE)["decision"], "SHIP")

    def test_dev_split_cannot_ship(self):
        base = _summary([_row(Q_ANS, GOOD), _row(Q_UNANS, GOOD)], split="dev")
        cand = _summary([_row(Q_ANS, GOOD), _row(Q_UNANS, ABSTAIN)], split="dev")
        self.assertEqual(report.decide(base, cand, RULE)["decision"], "HOLD")

    def test_over_budget_candidate_holds(self):
        base = _summary([_row(Q_ANS, GOOD), _row(Q_UNANS, GOOD)])
        cand = _summary([_row(Q_ANS, GOOD, cost=1.0), _row(Q_UNANS, ABSTAIN, cost=1.0)])
        d = report.decide(base, cand, RULE)
        self.assertEqual(d["decision"], "HOLD")
        self.assertIn("cost within budget", [c["check"] for c in d["checks"] if not c["pass"]])


class Dataset(unittest.TestCase):
    def test_manifest_matches(self):
        self.assertEqual(data.check_manifest(), [])

    def test_splits_do_not_overlap(self):
        dev, held = data.questions("dev"), data.questions("heldout")
        self.assertFalse({q["id"] for q in dev} & {q["id"] for q in held})
        self.assertFalse({q["question"] for q in dev} & {q["question"] for q in held})

    def test_every_expected_fact_is_in_an_expected_doc(self):
        for split in data.SPLITS:
            for q in data.questions(split):
                text = " ".join(graders.norm(DOCS[d]) for d in q["expected_docs"])
                for f in q["expected_facts"]:
                    self.assertIn(graders.norm(f), text, q["id"])


class FakeClient:
    def __init__(self, text, input_tokens=1000, output_tokens=100, stop_reason="end_turn"):
        self.calls = []
        self._resp = SimpleNamespace(content=[SimpleNamespace(type="text", text=text)], stop_reason=stop_reason,
                                     usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens))
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kw):
        self.calls.append(kw)
        return self._resp


class LiveSystemsWithFakeClient(unittest.TestCase):
    def test_claude_system_sends_schema_and_records_cost(self):
        from pevals.systems.claude import ClaudeSystem
        fake = FakeClient(GOOD)
        s = ClaudeSystem("candidate", model="claude-opus-5-5", client=fake)
        raw, usage = s.answer(Q_ANS["question"])
        self.assertEqual(raw, GOOD)
        self.assertEqual(usage["cost_usd"], 0.006)  # 1000 * 4 / 1e6 + 100 * 20 / 1e6
        kw = fake.calls[0]
        self.assertEqual(kw["output_config"]["format"]["type"], "json_schema")
        self.assertIn('<doc id="trash">', kw["messages"][0]["content"])

    def test_refusal_is_graded_as_a_failure(self):
        from pevals.systems.claude import ClaudeSystem
        s = ClaudeSystem("candidate", client=FakeClient("", stop_reason="refusal"))
        raw, _ = s.answer("x")
        self.assertFalse(graders.grade(Q_ANS, raw, DOCS)["schema_valid"])

    def test_runner_stops_at_the_budget(self):
        fake = FakeClient(GOOD, input_tokens=200_000, output_tokens=0)  # $0.80 per call on opus pricing
        with tempfile.TemporaryDirectory() as d, self.assertRaises(SystemExit):
            runner.run("claude", "candidate", "dev", Path(d), model="claude-opus-5-5", max_cost_usd=1.0, client=fake)
        self.assertEqual(len(fake.calls), 2)

    def test_judge_is_saved_separately_and_skips_abstentions(self):
        from pevals import judge
        with tempfile.TemporaryDirectory() as d:
            rows = Path(d) / "candidate-dev.jsonl"
            rows.write_text("".join(json.dumps({"id": r["id"], "question": "q", "raw": r["raw"], "grade": r["grade"]}) + "\n"
                                    for r in (_row(Q_ANS, GOOD), _row(Q_UNANS, ABSTAIN))))
            fake = FakeClient(json.dumps({"score": 4, "reason": "clear"}))
            r = judge.run(rows, model="claude-sonnet-5-5", client=fake)
            self.assertEqual((r["n"], r["mean"], len(fake.calls)), (1, 4.0, 1))
            self.assertTrue((Path(d) / "candidate-dev.judge.json").exists())


class OfflinePath(unittest.TestCase):
    def test_demo_reproduces_saved_results_without_the_sdk(self):
        from pevals.__main__ import main
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stdout(io.StringIO()):
            main(["demo", "--out", d, "--check"])
            self.assertTrue((Path(d) / "report-offline-heldout.md").exists())
        self.assertNotIn("anthropic", sys.modules)

    def test_live_run_refuses_without_confirmation(self):
        from pevals.__main__ import main
        with tempfile.TemporaryDirectory() as d, self.assertRaises(SystemExit), contextlib.redirect_stdout(io.StringIO()):
            main(["run", "--system", "claude", "--out", d])


if __name__ == "__main__":
    unittest.main()
