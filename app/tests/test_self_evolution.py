import json
from pathlib import Path
import tempfile
import unittest

from jarvis.self_evolution import CapabilityGapDetector, SelfEvolution, SafeEvolutionManager


class Clock:
    def __init__(self):
        self.t = 1000.0
    def __call__(self):
        return self.t
    def advance(self, dt):
        self.t += dt


class FakeLearner:
    def __init__(self, found=("octo/win-automation",), index=None):
        self.enabled = True
        self.index = dict(index or {})
        self.found = found
        self.searched, self.learned = [], []
    def search(self, query, language=""):
        self.searched.append(query)
        return [{"full_name": name} for name in self.found]
    def learn(self, full_name, reason="asked", cancelled=lambda: False, info=None, role="research"):
        self.learned.append((full_name, reason))
        self.index[full_name] = {"learned_at": "now"}
        return self.index[full_name]


class FakeDelib:
    def __init__(self, rows):
        self.rows = rows
    def decisions(self, limit=20):
        return self.rows[-limit:]


class FakeActions:
    def __init__(self, base, learner=None, stats=None, delib_rows=None, history=None):
        self.base = str(base)
        self.repo_learner = learner
        class _Cog: pass
        self.cognition = _Cog(); self.cognition.stats = stats or {}
        self.deliberation = FakeDelib(delib_rows or [])
        self.command_history = history or []
        self.memory = None
        self.approvals = []
        self._approved = True
    def _approve(self, kind, detail, cancelled):
        self.approvals.append((kind, detail))
        if not self._approved:
            raise ValueError("Action cancelled; approval was not given.")


def engine(base, **kw):
    clock = kw.pop("clock", Clock())
    actions = kw.pop("actions", None) or FakeActions(base, **kw)
    opts = {"idle_seconds": 10, "min_available_mb": 0, "max_cpu_percent": 100, "cooldown_seconds": 0}
    se = SelfEvolution(actions, opts, notify=lambda k, m: se.cards.append((k, m)), busy=lambda: actions_busy["v"], clock=clock)
    se.cards = []
    se.clock_obj = clock
    return se


actions_busy = {"v": False}


class GapDetectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)

    def test_detects_unreliable_action(self):
        a = FakeActions(Path(self.tmp.name), stats={"run_command": {"attempts": 6, "failures": 4, "last_failure": "exit 1"}})
        gaps = CapabilityGapDetector(a).detect()
        self.assertTrue(any(g["kind"] == "reliability" and "run_command" in g["subject"] for g in gaps))

    def test_detects_recurring_failures_and_requests(self):
        a = FakeActions(Path(self.tmp.name),
                        delib_rows=[{"goal": "organize my windows", "outcome": {"ok": False}},
                                    {"goal": "organize my windows", "outcome": {"ok": False}}],
                        history=["compare two folders"] * 3)
        gaps = CapabilityGapDetector(a).detect()
        kinds = {g["kind"] for g in gaps}
        self.assertIn("recurring-failure", kinds)
        self.assertIn("recurring-request", kinds)

    def test_no_fabrication_when_empty(self):
        self.assertEqual(CapabilityGapDetector(FakeActions(Path(self.tmp.name))).detect(), [])


class BacklogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        actions_busy["v"] = False

    def test_refresh_scores_dedups_and_persists(self):
        se = engine(Path(self.tmp.name), stats={"run_command": {"attempts": 5, "failures": 4}})
        se.refresh_backlog()
        se.refresh_backlog()  # Idempotent: no duplicate signatures.
        sigs = [i["signature"] for i in se.backlog]
        self.assertEqual(len(sigs), len(set(sigs)))
        self.assertTrue(all("score" in i for i in se.backlog))
        self.assertTrue((Path(self.tmp.name) / ".jarvis-runtime/self-evolution/backlog.json").is_file())

    def test_crash_safe_reload(self):
        base = Path(self.tmp.name)
        se = engine(base, stats={"click_control": {"attempts": 8, "failures": 5}})
        se.refresh_backlog()
        count = len(se.backlog)
        se2 = SelfEvolution(FakeActions(base), {"idle_seconds": 10})
        self.assertEqual(len(se2.backlog), count)  # Backlog survived a fresh instance (restart).

    def test_explore_seeds_a_job_when_idle_with_no_gaps(self):
        # A healthy system with no detected gaps should still queue an exploratory topic.
        se = engine(Path(self.tmp.name))  # no seeded stats -> no gaps
        se.refresh_backlog()
        pending = [i for i in se.backlog if i.get("status") == "pending"]
        self.assertTrue(pending, "idle with no gaps should still seed an exploratory learning job")
        self.assertEqual(pending[0]["kind"], "explore")

    def test_real_gaps_outrank_exploration(self):
        se = engine(Path(self.tmp.name), stats={"run_command": {"attempts": 6, "failures": 5}})
        se.refresh_backlog()
        self.assertNotEqual(se.next_job()["kind"], "explore")  # A real weakness is prioritized over exploring.

    def test_explore_can_be_disabled(self):
        se = SelfEvolution(FakeActions(Path(self.tmp.name)), {"explore": False, "idle_seconds": 10})
        se.refresh_backlog()
        self.assertEqual([i for i in se.backlog if i.get("status") == "pending"], [])

    def test_next_job_prefers_highest_score(self):
        se = engine(Path(self.tmp.name))
        se.backlog = [{"signature": "a", "status": "pending", "score": 1, "created": "x"},
                      {"signature": "b", "status": "pending", "score": 9, "created": "x"}]
        self.assertEqual(se.next_job()["signature"], "b")


class IdleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        actions_busy["v"] = False

    def test_not_idle_until_quiet(self):
        se = engine(Path(self.tmp.name))
        se.note_activity()
        self.assertFalse(se._idle())          # Just had activity.
        se.clock_obj.advance(11)
        self.assertTrue(se._idle())           # Quiet past idle_seconds.
        actions_busy["v"] = True
        self.assertFalse(se._idle())          # Busy with a user task.
        actions_busy["v"] = False

    def test_note_activity_interrupts(self):
        se = engine(Path(self.tmp.name))
        se._interrupt = False
        se.note_activity()
        self.assertTrue(se._cancelled())


class RunJobTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        actions_busy["v"] = False

    def test_learns_new_repo(self):
        learner = FakeLearner(found=("octo/win-automation",))
        se = engine(Path(self.tmp.name), actions=FakeActions(Path(self.tmp.name), learner=learner,
                     stats={"click_control": {"attempts": 8, "failures": 6}}))
        se.refresh_backlog()
        job = se.next_job()
        result = se.run_job(job)
        self.assertEqual(result["status"], "learned")
        self.assertEqual(learner.learned[0][0], "octo/win-automation")
        self.assertEqual(learner.learned[0][1], "self-evolution")
        self.assertTrue(any(k == "media_card" for k, _ in se.cards))

    def test_skips_already_learned(self):
        learner = FakeLearner(found=("octo/win-automation",), index={"octo/win-automation": {}})
        se = engine(Path(self.tmp.name), actions=FakeActions(Path(self.tmp.name), learner=learner,
                     stats={"click_control": {"attempts": 8, "failures": 6}}))
        se.refresh_backlog()
        result = se.run_job(se.next_job())
        self.assertEqual(result["status"], "exhausted")
        self.assertEqual(learner.learned, [])  # Never re-learned an existing revision.

    def test_disabled_learner_skips_gracefully(self):
        learner = FakeLearner(); learner.enabled = False
        se = engine(Path(self.tmp.name), actions=FakeActions(Path(self.tmp.name), learner=learner,
                     stats={"click_control": {"attempts": 8, "failures": 6}}))
        se.refresh_backlog()
        self.assertEqual(se.run_job(se.next_job())["status"], "skipped")


class IslandCardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        actions_busy["v"] = False

    def test_emits_learning_cards_with_what(self):
        learner = FakeLearner(found=("octo/win-tools",))
        se = engine(Path(self.tmp.name), actions=FakeActions(Path(self.tmp.name), learner=learner,
                     stats={"click_control": {"attempts": 8, "failures": 6}}))
        se.refresh_backlog()
        se.run_job(se.next_job())
        evolve = [m for k, m in se.cards if k == "media_card" and isinstance(m, dict) and m.get("service") == "evolve"]
        self.assertTrue(evolve, "no Learning (evolve) island cards emitted")
        self.assertTrue(any(m.get("title", "").startswith("Learning:") for m in evolve))
        self.assertTrue(any(m.get("phase") == "learned" for m in evolve))

    def test_island_renders_evolve_card(self):
        from jarvis.island import MEDIA_HEIGHT, render_island
        from jarvis.media_player import card
        for phase in ("learning", "learned", "notice"):
            img = render_island(560, MEDIA_HEIGHT, "STANDBY", 1.2, "", 0, False, "", 1.,
                                card("evolve", phase, "Learning: slugify", "from un33k/python-slugify", detail="Reading"))
            self.assertEqual(img.size[1], MEDIA_HEIGHT)


class SafeEvolutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        (self.base / "jarvis").mkdir()
        self.target = self.base / "jarvis" / "demo_module.py"
        self.target.write_text("VALUE = 1\n", encoding="utf-8")
        self.actions = FakeActions(self.base)
        self.mgr = SafeEvolutionManager(self.actions, {"enabled": True})

    def test_propose_rejects_protected_and_nonjarvis_and_bad_syntax(self):
        with self.assertRaises(ValueError):
            self.mgr.propose("jarvis/security_policy.py", "x = 1\n")      # protected name
        with self.assertRaises(ValueError):
            self.mgr.propose("config/config.json", "x = 1\n")            # not jarvis source
        (self.base / "jarvis" / "security_policy.py").write_text("x=1\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.mgr.propose("jarvis/demo_module.py", "def broken(:\n")  # invalid syntax

    def test_deploy_requires_passing_tests_then_approval_backup_and_rollback(self):
        meta = self.mgr.propose("jarvis/demo_module.py", "VALUE = 2\n", rationale="bump")
        pid = meta["id"]
        with self.assertRaises(ValueError):
            self.mgr.deploy(pid)  # Not tested yet.
        folder = self.mgr.directory / pid
        m = json.loads((folder / "meta.json").read_text())
        m["tested"] = {"ok": True, "detail": "passed"}
        (folder / "meta.json").write_text(json.dumps(m), encoding="utf-8")
        # Approval refused -> no deploy.
        self.actions._approved = False
        with self.assertRaises(ValueError):
            self.mgr.deploy(pid)
        self.assertEqual(self.target.read_text(), "VALUE = 1\n")
        # Approval granted -> deploys with backup, then rollback restores.
        self.actions._approved = True
        self.mgr.deploy(pid)
        self.assertEqual(self.target.read_text(), "VALUE = 2\n")
        self.assertEqual(self.actions.approvals[-1][0], "self_modification")
        self.mgr.rollback(pid)
        self.assertEqual(self.target.read_text(), "VALUE = 1\n")


if __name__ == "__main__":
    unittest.main()
