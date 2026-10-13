import json
from pathlib import Path
import tempfile
import unittest

from jarvis.commands import Command
from jarvis.deliberation import Deliberation


class FakeBrain:
    """Scripted stand-in for the local model inference worker."""
    def __init__(self, reply=None, error=False):
        self.reply, self.error, self.calls = reply, error, []
        self.timeout_seconds = 60

    def request(self, operation, cancelled, **data):
        self.calls.append((operation, data))
        if self.error:
            raise ValueError("worker down")
        return dict(self.reply or {})


class FakeActions:
    def __init__(self, base, brain=None, stats=None):
        self.base = str(base)
        self.brain = brain
        self.skills = None
        class _Cog:
            pass
        self.cognition = _Cog()
        self.cognition.stats = stats or {}
        self.cognition.recall = lambda goal, limit=3: {}
        self.cognition.effect_of = None


def engine(base, brain=None, stats=None, **options):
    return Deliberation(FakeActions(base, brain, stats), {"enabled": True, **options})


MODEL_DISAGREE = {"understanding": "make the importer faster", "recommendation": "stream rows in batches",
                  "reasoning": "it avoids loading the whole file into memory", "alternatives": [
                      {"approach": "add an index", "pros": "simple", "cons": "less impact"}],
                  "confidence": 0.8, "agrees_with_user": False, "claims": [
                      {"text": "file is large", "type": "assumption"}], "question": ""}
MODEL_AGREE = {"understanding": "x", "recommendation": "do it the way asked", "reasoning": "sound",
               "alternatives": [], "confidence": 0.8, "agrees_with_user": True, "claims": [], "question": ""}
MODEL_ASK = {"understanding": "x", "recommendation": "", "reasoning": "", "alternatives": [],
             "confidence": 0.3, "agrees_with_user": True, "claims": [], "question": "Which database do you mean?"}


class RiskTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.e = engine(Path(self.tmp.name))

    def test_high_risk_from_goal_text(self):
        for text in ("delete all the logs", "deploy to production", "transfer money to the vendor",
                     "print my api key"):
            self.assertEqual(self.e.classify_risk(Command("task", text)), "high", text)

    def test_high_risk_from_command_kind(self):
        self.assertEqual(self.e.classify_risk(Command("delete", "notes.txt")), "high")
        self.assertEqual(self.e.classify_risk(Command("whatsapp_send", "hi to Sam")), "high")

    def test_moderate_and_low(self):
        self.assertEqual(self.e.classify_risk(Command("task", "refactor the parser module")), "moderate")
        self.assertEqual(self.e.classify_risk(Command("ask", "research async libraries")), "low")


class OpinionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)

    def test_disagreement_proposes(self):
        e = engine(Path(self.tmp.name), FakeBrain(MODEL_DISAGREE))
        op = e.form_opinion("make the CSV importer faster", Command("task", "make the CSV importer faster"), lambda: False)
        self.assertFalse(op["agrees_with_user"])
        self.assertEqual(op["source"], "model")
        d = e.decide(op)
        self.assertTrue(d["propose"])
        self.assertIn("stream rows", d["message"])

    def test_agreement_low_friction_is_silent(self):
        e = engine(Path(self.tmp.name), FakeBrain(MODEL_AGREE))
        op = e.form_opinion("read a file and summarize it", Command("ask", "read a file and summarize it"), lambda: False)
        d = e.decide(op)
        self.assertFalse(d["propose"])
        self.assertFalse(d["note"])

    def test_ambiguous_question_proposes(self):
        e = engine(Path(self.tmp.name), FakeBrain(MODEL_ASK))
        op = e.form_opinion("clean up the database", Command("task", "clean up the database"), lambda: False)
        d = e.decide(op)
        self.assertTrue(d["propose"])
        self.assertIn("Which database", d["message"])

    def test_high_risk_agreement_defers_to_existing_gate(self):
        # High risk alone must NOT add a second confirmation: the existing approval gate handles it.
        e = engine(Path(self.tmp.name), FakeBrain(MODEL_AGREE))
        op = e.form_opinion("delete the old backups", Command("task", "delete the old backups"), lambda: False)
        self.assertEqual(op["risk"], "high")
        d = e.decide(op)
        self.assertFalse(d["propose"])
        self.assertFalse(d["note"])

    def test_high_risk_disagreement_still_proposes(self):
        # Example D: Jarvis disagrees on a consequential choice -> it speaks up and proposes.
        e = engine(Path(self.tmp.name), FakeBrain({**MODEL_DISAGREE, "recommendation": "benchmark a smaller model first"}))
        op = e.form_opinion("load the largest model into memory",
                            Command("task", "load the largest model into memory"), lambda: False)
        self.assertFalse(op["agrees_with_user"])
        self.assertTrue(e.decide(op)["propose"])

    def test_insufficient_info_sets_question(self):
        e = engine(Path(self.tmp.name), FakeBrain(MODEL_ASK))
        op = e.form_opinion("fix it", Command("task", "fix it"), lambda: False)
        self.assertTrue(op["question"])

    def test_model_failure_falls_back_to_heuristic(self):
        e = engine(Path(self.tmp.name), FakeBrain(error=True))
        op = e.form_opinion("optimize the project", Command("task", "optimize the project"), lambda: False)
        self.assertEqual(op["source"], "heuristic")
        self.assertIsInstance(op["confidence"], float)  # Never blocks; always returns a usable opinion.

    def test_no_brain_uses_heuristic(self):
        e = engine(Path(self.tmp.name), brain=None)
        op = e.form_opinion("optimize the project", Command("task", "optimize the project"), lambda: False)
        self.assertEqual(op["source"], "heuristic")

    def test_confidence_blends_learned_reliability(self):
        low = engine(Path(self.tmp.name), FakeBrain(MODEL_AGREE),
                     stats={"task": {"attempts": 10, "successes": 1}})
        high = engine(Path(self.tmp.name), FakeBrain(MODEL_AGREE),
                      stats={"task": {"attempts": 10, "successes": 9}})
        c_low = low.form_opinion("refactor module", Command("task", "refactor module"), lambda: False)["confidence"]
        c_high = high.form_opinion("refactor module", Command("task", "refactor module"), lambda: False)["confidence"]
        self.assertGreater(c_high, c_low)

    def test_reject_excludes_prior_approaches(self):
        brain = FakeBrain(MODEL_DISAGREE)
        e = engine(Path(self.tmp.name), brain)
        e.form_opinion("make it faster", Command("task", "make it faster"), lambda: False,
                       exclude=["stream rows in batches"])
        self.assertEqual(brain.calls[-1][1]["rejected_approaches"], ["stream rows in batches"])


class FeedbackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.e = engine(Path(self.tmp.name))

    def test_verdicts(self):
        cases = {"go ahead": "approve", "yes please": "approve", "do it": "approve",
                 "no, try something else": "reject", "i don't like that": "reject", "stop": "reject",
                 "whatever you think": "vague", "you decide": "vague", "do what's best": "vague",
                 "use rust instead": "refine"}
        for text, expected in cases.items():
            self.assertEqual(self.e.interpret_feedback(text)["verdict"], expected, text)

    def test_empty_is_refine(self):
        self.assertEqual(self.e.interpret_feedback("")["verdict"], "refine")


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.e = engine(Path(self.tmp.name))

    def test_record_and_outcome_roundtrip(self):
        op = {"goal": "g", "recommendation": "r", "alternatives": [{"approach": "a"}],
              "confidence": 0.7, "risk": "moderate", "source": "model"}
        did = self.e.record(op, {"propose": True}, "r", "proposed")
        self.e.record_outcome(did, True, "worked")
        rows = self.e.decisions()
        self.assertTrue(any(r.get("id") == did and r.get("chosen") == "r" for r in rows))
        self.assertTrue(any(r.get("id") == did and r.get("outcome") for r in rows))

    def test_ledger_rotates(self):
        self.e.ledger_max = 5
        for i in range(12):
            self.e.record({"goal": str(i), "recommendation": "x"}, {}, "x", "proposed")
        lines = Path(self.e.ledger_path).read_text(encoding="utf-8").splitlines()
        self.assertLessEqual(len(lines), 5)


if __name__ == "__main__":
    unittest.main()
