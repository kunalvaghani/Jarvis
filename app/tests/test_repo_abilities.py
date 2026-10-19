import json
import threading
import time
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from jarvis import repo_abilities as ra
from jarvis.commands import parse


KNOWLEDGE = {"full_name": "demo/wordcount", "description": "Count words in text files", "license": "MIT",
             "languages": {"Python": 3}, "readme": "# wordcount\nCounts words and lines.",
             "manifests": {"pyproject.toml": "[project]\nname='wordcount'"},
             "modules": [{"path": "wordcount/core.py", "symbols": []}, {"path": "tests/test_core.py", "test": True, "symbols": []}],
             "summary": {"purpose": "Counts words, lines and characters in text files.", "architecture": "core.count()",
                         "how_to_run": "wordcount FILE", "use_when": "word statistics", "key_modules": []}}

SPEC = {"name": "word counter", "summary": "Counts words and lines in a text file.",
        "triggers": ["count the words in {file}", "word count of {file}", "open {file}"],
        "inputs": [{"name": "file", "type": "file", "description": "a text file"}],
        "output": "text", "approach": "standalone", "packages": [], "network": False,
        "plan": "Read the file and count like wordcount.core.count."}

GOOD = '''
import os

def run(inputs, workdir):
    with open(inputs["file"], encoding="utf-8") as handle:
        text = handle.read()
    words = len(text.split())
    out = os.path.join(workdir, "out", "count.txt")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as handle:
        handle.write(str(words))
    return {"text": str(words) + " words, " + str(text.count("\\n") + 1) + " lines.", "files": ["out/count.txt"]}

def sample_inputs(workdir):
    path = os.path.join(workdir, "sample.txt")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("one two three\\nfour")
    return {"file": path}
'''

BROKEN = GOOD.replace('return {"text"', 'raise RuntimeError("boom")\n    return {"text"')


class Model:
    """Scripted coding model: a design answer, then the code replies in order."""

    def __init__(self, codes, specs=None):
        self.codes, self.specs, self.calls = list(codes), specs if specs is not None else [SPEC], []

    def __call__(self, system, user, schema):
        self.calls.append((system[:40], user))
        if schema:
            return {"abilities": self.specs, "no_ability_reason": "" if self.specs else "just a list of links"}
        return "```python\n" + self.codes.pop(0) + "```"


class Learner:
    def __init__(self):
        self.index = {"demo/wordcount": {"learned_at": "2026-10-11T00:00:00+00:00"}}
        self.viewing = None
        self.enabled = True

    def knowledge(self, name):
        return KNOWLEDGE if name.casefold() == "demo/wordcount" else None

    def known(self, name):
        return self.index.get(name)

    def reference(self, name, goal, budget=3500):
        return {"repository": name, "code_excerpts": [{"path": "wordcount/core.py", "excerpt": "def count(t): ..."}]}


SHARED_ENV = {}


def forge(codes, specs=None, options=None, decision=True):
    base = Path(tempfile.mkdtemp())
    root = base / "JarvisFiles"
    root.mkdir()
    reports = []
    actions = SimpleNamespace(base=str(base), root=root, report=lambda *a: reports.append(a), repo_learner=Learner(),
                              task_active=False, memory=None)
    instance = ra.AbilityForge(actions, {"max_repairs": 1, **(options or {})}, model_chat=Model(codes, specs))
    if "env" in SHARED_ENV:  # One stdlib environment for the whole test run keeps it fast.
        shutil.copytree(SHARED_ENV["env"], instance.root / "_base-env")
    else:
        SHARED_ENV["env"] = instance._base_env()
    instance.decider = lambda row, detail: decision(row, detail) if callable(decision) else decision  # The island card.
    ra.REGISTRY["forge"] = actions.ability_forge = instance
    return instance, actions, reports


class StaticChecks(unittest.TestCase):
    def test_good_code_passes(self):
        self.assertEqual(ra.check_code(GOOD, SPEC), [])

    def test_dangerous_code_is_refused(self):
        for code, word in (("import subprocess\n" + GOOD, "subprocess"), (GOOD + "\neval('1')\n", "eval"),
                           ("import requests\n" + GOOD, "network"), ("import numpy\n" + GOOD, "declared"),
                           ("import os\nos.system('dir')\n" + GOOD, "system"), ("def run(a):\n    pass\n", "run()")):
            problems = " ".join(ra.check_code(code, SPEC))
            self.assertIn(word, problems, code[:40])

    def test_platform_system_is_not_os_system(self):
        self.assertEqual(ra.check_code("import platform\n" + GOOD + "\nplatform.system()\n", SPEC), [])

    def test_spec_cleaning(self):
        spec = ra.clean_spec({**SPEC, "triggers": ["Count the words in {File}.", "{file}", "count {other}"]})
        self.assertEqual(spec["triggers"], ["count the words in {file}"])
        self.assertEqual(ra.needs_approval(spec), [])
        spec = ra.clean_spec({**SPEC, "approach": "packages", "packages": [{"pip": "markdown", "module": "markdown"}],
                              "network": True})
        self.assertEqual(ra.needs_approval(spec), ["installs markdown", "uses the internet"])
        with self.assertRaises(ra.AbilityError):
            ra.clean_spec({**SPEC, "packages": [{"pip": "x; rm -rf /", "module": "x"}]})
        with self.assertRaises(ra.AbilityError):
            ra.clean_spec({**SPEC, "packages": [{"pip": "ctypes-shim", "module": "ctypes"}]})


class Building(unittest.TestCase):
    def tearDown(self):
        ra.REGISTRY["forge"] = None

    def test_build_test_activate_and_use(self):
        instance, actions, reports = forge([GOOD])
        built = instance.build_repo("demo/wordcount")
        self.assertEqual([b["state"] for b in built], ["active"])
        row = built[0]
        # 'open {file}' is a built-in command, so it is dropped; the others are learned.
        self.assertEqual(row["triggers"], ["count the words in {file}", "word count of {file}"])
        self.assertIn("4 words", row["last_test"])
        registry = json.loads((instance.root / "registry.json").read_text(encoding="utf-8"))
        self.assertEqual(registry["abilities"]["word-counter"]["state"], "active")
        self.assertTrue(any("Added ability: word counter" in str(r) for r in reports))

        (actions.root / "notes.md").write_text("alpha beta gamma\nsecond line here", encoding="utf-8")
        command = parse("count the words in notes.md")
        self.assertEqual((command.kind, command.value), ("ability_run", "word-counter"))
        self.assertEqual(json.loads(command.extra), {"file": "notes.md"})
        self.assertEqual(parse("open notes.md").kind, "open")  # Built-in commands still win.
        answer = ra.execute(actions, command, lambda: False)
        self.assertIn("6 words, 2 lines", answer)
        saved = actions.root / "Abilities" / "word-counter" / "count.txt"
        self.assertEqual(saved.read_text(encoding="utf-8"), "6")
        ra.execute(actions, command, lambda: False)
        self.assertTrue((saved.parent / "count-1.txt").exists())  # Never overwrites an earlier output.
        self.assertEqual((actions.root / "notes.md").read_text(encoding="utf-8"), "alpha beta gamma\nsecond line here")

        use = parse("use word counter on notes.md")
        self.assertEqual(use.kind, "ability_run")
        self.assertIn("word counter", ra.execute(actions, parse("list your abilities"), lambda: False))
        self.assertEqual(parse("disable ability word counter").kind, "ability_disable")
        ra.execute(actions, parse("disable ability word counter"), lambda: False)
        with self.assertRaises(ValueError):
            parse("count the words in notes.md")
        ra.execute(actions, parse("enable ability word counter"), lambda: False)
        self.assertEqual(parse("count the words in notes.md").kind, "ability_run")

    def test_tampered_code_is_not_run(self):
        instance, actions, _ = forge([GOOD])
        row = instance.build_repo("demo/wordcount")[0]
        path = instance.root / row["folder"] / "ability.py"
        path.write_text(path.read_text(encoding="utf-8") + "\n# changed\n", encoding="utf-8")
        (actions.root / "a.txt").write_text("x", encoding="utf-8")
        answer = ra.execute(actions, ra.parse_learned("count the words in a.txt"), lambda: False)
        self.assertIn("changed after it was tested", answer)

    def test_failing_ability_is_repaired_or_never_merged(self):
        instance, _, _ = forge([BROKEN, GOOD])
        built = instance.build_repo("demo/wordcount")
        self.assertEqual(built[0]["state"], "active")
        self.assertEqual(built[0]["attempts"], 2)
        # Keep a diagnostic category for repair, without forwarding untrusted exception text/source.
        self.assertIn("RuntimeError: untrusted exception details withheld.", instance.model_chat.calls[-1][1])

        instance, _, reports = forge([BROKEN, BROKEN])
        self.assertEqual(instance.build_repo("demo/wordcount"), [])
        self.assertEqual(instance.registry["abilities"]["word-counter"]["state"], "failed")
        self.assertIsNone(ra.parse_learned("count the words in notes.md"))
        self.assertTrue(any("No new ability" in str(r) for r in reports))

    def test_failed_update_keeps_the_working_version(self):
        instance, _, _ = forge([GOOD, BROKEN, BROKEN])
        first = instance.build_repo("demo/wordcount")[0]
        instance.build_repo("demo/wordcount")
        row = instance.registry["abilities"]["word-counter"]
        self.assertEqual((row["state"], row["version"]), ("active", first["version"]))
        self.assertIn("Update failed", row["last_error"])
        self.assertIsNotNone(ra.parse_learned("count the words in notes.md"))

    def test_packages_wait_for_approval_and_nothing_is_installed(self):
        spec = {**SPEC, "approach": "packages", "packages": [{"pip": "markdown", "module": "markdown"}]}
        instance, actions, reports = forge(["import markdown\n" + GOOD], [spec], decision=None)
        built = instance.build_repo("demo/wordcount")
        self.assertEqual(built[0]["state"], "awaiting_approval")
        self.assertFalse(any((instance.root / "word-counter").glob("env-*")))
        self.assertIsNone(ra.parse_learned("count the words in notes.md"))
        self.assertTrue(any("approve ability word counter" in str(r) for r in reports))
        self.assertEqual(parse("approve ability word counter").kind, "ability_approve")
        self.assertIn("word counter", ra.execute(actions, ra.parse_command("list your abilities"), lambda: False))

    def test_repository_without_a_use_case(self):
        instance, _, reports = forge([], [])
        self.assertEqual(instance.build_repo("demo/wordcount"), [])
        self.assertEqual(instance.registry["repos"]["demo/wordcount"]["state"], "no_ability")
        self.assertTrue(any("just a list of links" in str(r) for r in reports))

    def test_interrupted_build_resumes_and_coding_references_do_not_build(self):
        instance, _, _ = forge([GOOD])
        instance.registry["repos"]["demo/wordcount"] = {"state": "building"}
        instance.on_learned("demo/other", "coding task: build a thing")
        self.assertTrue(instance.jobs.empty())
        instance.stop.set()  # Do not let the thread take the job.
        instance.start()
        self.assertEqual(instance.jobs.get_nowait()[0], "demo/wordcount")
        instance.close()

    def test_alternative_inputs_and_repeat_builds(self):
        # The live model proposed "text or file" inputs with one phrase each (2026-10-11); both must work.
        spec = {**SPEC, "name": "text_or_file_counter", "triggers": ["count words in the text {text}", "count words in the file {file}"],
                "inputs": [{"name": "text", "type": "text", "description": "words"},
                           {"name": "file", "type": "file", "description": "a file"}]}
        code = GOOD.replace('with open(inputs["file"], encoding="utf-8") as handle:\n        text = handle.read()',
                            'text = inputs.get("text") or open(inputs["file"], encoding="utf-8").read()')
        instance, actions, _ = forge([code], [spec])
        row = instance.build_repo("demo/wordcount")[0]
        self.assertEqual((row["name"], row["state"]), ("text or file counter", "active"))
        self.assertIn("3 words", ra.execute(actions, parse("count words in the text a b c"), lambda: False))
        (actions.root / "two.txt").write_text("x y", encoding="utf-8")
        use = parse("use text or file counter on two.txt")
        self.assertEqual(json.loads(use.extra), {"file": "two.txt"})
        self.assertIn("2 words", ra.execute(actions, use, lambda: False))
        self.assertEqual(json.loads(parse("use text or file counter on hello there").extra), {"text": "hello there"})
        # An automatic build right after an explicit one is skipped, so nothing is built twice.
        calls = len(instance.model_chat.calls)
        self.assertEqual(instance.build_repo("demo/wordcount", "auto"), [])
        self.assertEqual(len(instance.model_chat.calls), calls)

    def test_learned_phrase_beats_general_question_only(self):
        # Live 2026-10-11: "convert {file} to html" was first lost to the general-question catch-all.
        spec = {**SPEC, "name": "markdown to html", "triggers": ["convert {file} to html"]}
        instance, actions, _ = forge([GOOD], [spec])
        row = instance.build_repo("demo/wordcount")[0]
        self.assertEqual(row["triggers"], ["convert {file} to html"])
        self.assertEqual(parse("convert notes.md to html").kind, "ability_run")
        self.assertEqual(parse("convert 5 km to miles").kind, "ask")  # Unit conversion is still a question.
        use = parse("use markdown to html on readme.md")  # The name itself contains "to".
        self.assertEqual((use.value, json.loads(use.extra)), ("markdown-to-html", {"file": "readme.md"}))

    def test_each_ability_is_shown_and_deny_moves_on_to_the_next(self):
        second = {**SPEC, "name": "line counter", "triggers": ["count the lines in {file}"]}
        shown = []

        def island(row, detail):
            shown.append((row["name"], detail))
            return row["name"] != "word counter"  # Deny the first, approve the second.

        instance, actions, reports = forge([GOOD, GOOD], [SPEC, second], decision=island)
        built = instance.build_repo("demo/wordcount")
        self.assertEqual([(b["name"], b["state"]) for b in built], [("word counter", "denied"), ("line counter", "active")])
        self.assertEqual([name for name, _ in shown], ["word counter", "line counter"])  # One at a time, in order.
        detail = shown[0][1]
        for part in ("Ability: word counter", "What it does: Counts words", 'Command: "count the words in <file>"',
                     "Passed its self-test: 4 words", "Uses: the Python standard library only", "def run(inputs, workdir):"):
            self.assertIn(part, detail)
        self.assertIsNone(ra.parse_learned("count the words in notes.md"))
        self.assertEqual(ra.parse_learned("count the lines in notes.md").value, "line-counter")
        self.assertTrue(any("Discarded: word counter" in str(r) for r in reports))

    def test_unanswered_card_stays_pending_until_reviewed(self):
        answers = [None]
        instance, actions, _ = forge([GOOD], decision=lambda row, detail: answers[0])
        self.assertEqual(instance.build_repo("demo/wordcount")[0]["state"], "awaiting_approval")
        self.assertIsNone(ra.parse_learned("count the words in notes.md"))
        self.assertIn("Waiting for your OK: word counter", ra.execute(actions, parse("list your abilities"), lambda: False))
        self.assertEqual(parse("show pending abilities").kind, "ability_review")
        answers[0] = True
        self.assertEqual(instance.review_pending(), {"word counter": "active"})
        self.assertEqual(ra.parse_learned("count the words in notes.md").kind, "ability_run")

    def test_voice_deny_and_approve_for_waiting_abilities(self):
        instance, actions, _ = forge([GOOD], decision=None)
        instance.build_repo("demo/wordcount")
        self.assertIn("Discarded word counter", ra.execute(actions, parse("deny ability word counter"), lambda: False))
        self.assertEqual(instance.registry["abilities"]["word-counter"]["state"], "denied")
        self.assertIn("Approved word counter", ra.execute(actions, parse("approve ability word counter"), lambda: False))
        instance.close()

    def test_island_lapse_is_not_a_denial(self):
        import threading
        from jarvis.island_desk import Approval
        answer, ready = {"approved": False}, threading.Event()
        Approval(("learned_ability", "x", answer, ready, lambda: False)).lapse()
        self.assertTrue(answer["expired"] and ready.is_set())
        answer = {"approved": False}
        card = Approval(("learned_ability", "x", answer, threading.Event(), lambda: False))
        card.decide(False)
        card.lapse()
        self.assertFalse(answer.get("expired"))  # A real Deny stays a Deny.

    def test_learning_failures_are_kept_and_reported(self):
        instance, actions, reports = forge([])
        instance.wanted.add("big/repo")
        instance.on_learn_failed("big/repo", "GitHub rate limit reached", "you asked")
        self.assertIn("big/repo (GitHub rate limit reached)", ra.execute(actions, parse("list your abilities"), lambda: False))
        self.assertTrue(any(r[0] == "spoken_reply" and "couldn't learn big/repo" in r[1] for r in reports))
        instance.stop.set()  # Keep the builder thread from taking the job.
        instance.on_viewed("demo/wordcount")  # Learned earlier, never built: viewing it builds it.
        self.assertEqual(instance.jobs.get_nowait()[:2], ("demo/wordcount", "auto"))
        instance.close()

    def test_model_calls_give_way_to_the_user(self):
        # Live 2026-10-11: CPU-only background calls swapped Jarvis's model out and stalled answers, mic and UI.
        from unittest.mock import patch
        instance, actions, _ = forge([])
        instance.model_chat = None
        instance.pick_model = lambda: "qwen3.5:9b"
        instance.idle_seconds = 0.2
        calls, roles, priority = [], [], []
        instance.runner_priority = lambda low: priority.append(low) or [1234]

        def fake_install(client, role="question"):
            roles.append(role)
            return client

        def fake_chat(client, options, messages, structured=False):
            calls.append(options)
            self.assertTrue(options["stream"])
            if len(calls) == 1:
                options["on_chunk"]("partial")
                actions.last_command_at = time.monotonic()  # The user speaks mid-generation.
                instance._busy_checked = (0.0, False)
                options["on_chunk"]("more")
                raise AssertionError("the call should have been abandoned")
            return "finished"

        with patch("jarvis.knowledge_worker.chat", fake_chat), patch("jarvis.gpu_scheduler.install", fake_install), \
                patch("jarvis.gpu_scheduler.Registry") as registry:
            registry.return_value.state.return_value.__enter__.return_value = {"active": None, "pending": []}
            started = time.monotonic()
            self.assertEqual(instance._chat("system", "user"), "finished")
        self.assertEqual(len(calls), 2)  # Abandoned once, repeated after the user was idle.
        self.assertGreaterEqual(time.monotonic() - started, 0.2)
        self.assertEqual(set(roles), {"research"})  # Shares Jarvis's GPU queue instead of CPU-only background calls.
        self.assertIn("paused_for_user", (instance.root / "builds.jsonl").read_text(encoding="utf-8"))
        self.assertEqual(priority, [True, False])  # Ollama's runner yields the CPU only during each call.

    def test_coding_uses_relevant_approved_abilities(self):
        instance, actions, _ = forge([GOOD])
        instance.build_repo("demo/wordcount")
        from jarvis.agent_context import coding_context
        context = coding_context(Path(actions.root), "write a python tool that counts the words in a text file")
        refs = context["learned_abilities"]
        self.assertEqual(refs[0]["ability"], "word counter")
        self.assertIn("def run(inputs, workdir):", refs[0]["code"])
        self.assertEqual((refs[0]["learned_from"], refs[0]["uses"]), ("demo/wordcount", ["standard library"]))
        self.assertEqual(ra.references_for("build a snake game in javascript"), [])  # Unrelated goals get nothing.
        # Live 2026-10-12: "summarizes" missed "summarize file"; word forms and plurals now match.
        self.assertEqual([r["ability"] for r in ra.references_for("add a function that counts words in a short paragraph")],
                         ["word counter"])
        instance.registry["abilities"]["word-counter"]["state"] = "disabled"
        self.assertEqual(ra.references_for("count the words in a text file"), [])  # Only approved, active abilities.

    def test_native_coding_tools_run_abilities_on_project_files_only(self):
        instance, actions, _ = forge([GOOD])
        instance.build_repo("demo/wordcount")
        project = Path(tempfile.mkdtemp())
        (project / "notes.txt").write_text("one two three", encoding="utf-8")
        found = instance.coding_tool(project, "learned_ability_search", {"query": "count words"})
        self.assertEqual(found["abilities"][0]["name"], "word counter")
        self.assertIn("def sample_inputs", instance.coding_tool(project, "learned_ability_read", {"name": "word counter"})["code"])
        result = instance.coding_tool(project, "learned_ability_run", {"name": "word counter", "content": '{"file": "notes.txt"}'})
        self.assertIn("3 words", result["result"])
        self.assertEqual((project / "notes.txt").read_text(encoding="utf-8"), "one two three")  # Project file untouched.
        outside = Path(actions.base) / "private.txt"
        outside.write_text("secret", encoding="utf-8")
        for value in ("../private.txt", str(outside)):
            with self.assertRaises(ValueError):
                instance.coding_tool(project, "learned_ability_run", {"name": "word counter", "content": json.dumps({"file": value})})
        from jarvis.native_coding import EXTRA, SCHEMA
        self.assertTrue({"learned_ability_search", "learned_ability_read", "learned_ability_run"} <= set(EXTRA))
        self.assertIn("learned_ability_run", SCHEMA["properties"]["tool"]["enum"])

    def test_opening_a_known_repository_shows_its_abilities_on_the_island(self):
        from datetime import datetime, timezone
        from jarvis import repo_learning as rl
        instance, actions, reports = forge([GOOD, GOOD], [SPEC, {**SPEC, "name": "line counter", "triggers": ["count the lines in {file}"]}],
                                           decision=lambda row, detail: row["name"] == "word counter" or None)
        instance.build_repo("demo/wordcount")
        clock = [0.0]
        learner = rl.RepoLearner(SimpleNamespace(base=actions.base, report=actions.report, ability_forge=instance,
                                                 memory=SimpleNamespace(vault=tempfile.mkdtemp(), record=lambda *a: None)),
                                 {"dwell_seconds": 8}, clock=lambda: clock[0])
        learner.index["demo/wordcount"] = {"learned_at": datetime.now(timezone.utc).isoformat()}
        actions.repo_learner = learner
        instance.clock = lambda: clock[0]
        reports.clear()
        title = "GitHub - demo/wordcount: Count words - Google Chrome"
        for moment in (0, 1, 2, 3.5, 5, 9):
            clock[0] = moment
            learner.observe_title(title, "chrome.exe")
        cards = [r[1] for r in reports if r[0] == "media_card"]
        self.assertEqual(len(cards), 1)  # Once, about 3 seconds after opening it (not the 8-second learning dwell).
        self.assertEqual(cards[0]["title"], "Already have abilities from demo/wordcount")
        self.assertIn("1 ability from it: word counter", cards[0]["subtitle"])
        self.assertIn("waiting for your OK: line counter", cards[0]["subtitle"])
        self.assertEqual(cards[0]["detail"], 'Say "count the words in <file>"')
        learner.viewing = None
        clock[0] = 100  # Reopened soon after: no repeat within 10 minutes.
        self.assertIsNone(instance.on_viewed("demo/wordcount"))
        clock[0] = 700
        self.assertIn("word counter", instance.on_viewed("demo/wordcount"))
        learner.viewing = {"full_name": "demo/wordcount", "candidate": "demo/wordcount"}
        answer = ra.execute(actions, parse("what abilities do you have from this repo"), lambda: False)
        self.assertIn("I already have 1 ability from it: word counter", answer)
        self.assertIn("waiting for your OK: line counter", answer)
        self.assertIn("haven't learned other/thing", ra.execute(actions, parse("what abilities did you get from other/thing"), lambda: False))

    def test_interrupted_rows_are_cleaned_up_and_held_repositories_resume(self):
        instance, _, _ = forge([GOOD])
        instance.build_repo("demo/wordcount")
        instance.registry["abilities"]["half-built"] = {"id": "half-built", "name": "half built", "state": "queued",
                                                        "repo": "demo/wordcount", "inputs": []}
        instance.registry["abilities"]["half-installed"] = {"id": "half-installed", "name": "half installed", "state": "building",
                                                            "repo": "demo/wordcount", "inputs": [], "folder": "x/v1"}
        instance.registry["repos"]["demo/wordcount"] = {"state": "queued", "note": "daily build limit"}
        instance.stop.set()
        instance.start()
        self.assertEqual(instance.registry["abilities"]["half-built"]["state"], "interrupted")
        self.assertEqual(instance.registry["abilities"]["half-installed"]["state"], "awaiting_approval")
        self.assertEqual(instance.registry["abilities"]["word-counter"]["state"], "active")
        self.assertEqual(instance.jobs.get_nowait()[:2], ("demo/wordcount", "resume"))
        self.assertTrue(instance.jobs.empty())
        self.assertEqual(len([t for t in threading.enumerate() if t is instance.thread]), 1 if instance.thread.is_alive() else 0)
        self.assertNotIn("half built", instance.describe_repo("demo/wordcount")[1])  # Never shown as "being built".
        instance.close()

    def test_management_phrases(self):
        self.assertEqual(parse("build abilities from psf/requests").kind, "ability_build")
        self.assertEqual(parse("build abilities from psf/requests").value, "psf/requests")
        self.assertEqual(parse("turn this repo into new commands").kind, "ability_build")
        self.assertEqual(parse("what abilities did you get from repos").kind, "ability_list")
        self.assertEqual(parse("build abilities from deepseek harness").value, "deepseek harness")
        self.assertEqual(parse("deny ability word counter").kind, "ability_deny")
        self.assertEqual(parse("learn this").kind, "repo_learn")
        self.assertEqual(ra.resolve_repo(None, "psf/requests"), "psf/requests")
        self.assertIsNone(ra.resolve_repo(None, "owner/repo"))  # A placeholder is never treated as a real name.
        # Phrases the repository-skills integration owns are unchanged.
        self.assertEqual(parse("what new abilities did you learn").kind, "toolkit")


class RunnerGuards(unittest.TestCase):
    """The audit-hook guard rails, exercised with hand-written code that skips the static check."""

    def setUp(self):
        self.instance, self.actions, _ = forge([])

    def tearDown(self):
        ra.REGISTRY["forge"] = None

    def run_code(self, body):
        folder = self.instance.root / "probe" / "v1"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "ability.py").write_text("import os\n" + body + "\ndef sample_inputs(workdir):\n    return {}\n", encoding="utf-8")
        row = {"id": "probe", "output": "text", "network": False}
        return self.instance.test(row, folder)

    def test_blocks_writes_outside_the_run_folder(self):
        outside = Path(self.actions.base) / "outside.txt"
        result = self.run_code("def run(i, w):\n    open(" + repr(str(outside)) + ", 'w').write('x')\n    return 'done'")
        self.assertFalse(result["ok"])
        self.assertIn("only write inside", result["error"])
        self.assertFalse(outside.exists())

    def test_blocks_reading_private_files(self):
        secret = Path(self.actions.base) / "secrets.json"
        secret.write_text("{}", encoding="utf-8")
        result = self.run_code("def run(i, w):\n    return open(" + repr(str(secret)) + ").read()")
        self.assertFalse(result["ok"])
        self.assertIn("only read", result["error"])

    def test_blocks_processes_and_network(self):
        result = self.run_code("import subprocess\ndef run(i, w):\n    subprocess.run(['cmd', '/c', 'echo hi'])\n    return 'x'")
        self.assertIn("may not start other programs", result["error"])
        result = self.run_code("import socket\ndef run(i, w):\n    socket.create_connection(('example.com', 80), 2)\n    return 'x'")
        self.assertIn("network", result["error"])

    def test_time_limit_kills_the_process(self):
        self.instance.test_seconds = 3
        result = self.run_code("import time\ndef run(i, w):\n    time.sleep(60)\n    return 'x'")
        self.assertFalse(result["ok"])
        self.assertIn("longer than 3 seconds", result["error"])


if __name__ == "__main__":
    unittest.main()
