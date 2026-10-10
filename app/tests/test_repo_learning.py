import io
import json
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from jarvis import repo_learning as rl
from jarvis.commands import Command, parse


def make_zip(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, text in files.items():
            archive.writestr("demo-main/" + path, text)
    return buffer.getvalue()


SAMPLE = make_zip({
    "README.md": "# Demo\nA tiny snake game.\n\nRun: open index.html",
    "package.json": '{"name": "demo", "scripts": {"start": "vite"}}',
    "src/main.js": "import { Snake } from './snake.js'\nexport function start(canvas) {\n  return new Snake(canvas)\n}\n",
    "src/snake.js": "export class Snake {\n  constructor(c) { this.c = c }\n}\nexport const step = (s, dir) => s\n",
    "app.py": "def serve(port: int = 8000):\n    '''Serve the game.'''\n    return port\n\nclass Store:\n    def save(self, x):\n        pass\n",
    "tests/test_app.py": "def test_serve():\n    assert True\n",
    "node_modules/x/index.js": "function hidden() {}",
    "logo.png": "\x89PNG",
})


class Summary:
    def __init__(self):
        self.calls = []

    def __call__(self, system, payload, schema):
        self.calls.append(payload)
        if "best" in schema.get("required", []):
            return {"best": [c["index"] for c in payload["candidates"] if c["repository"] == "demo/snake"]}
        if "query" in schema.get("required", []):
            return {"query": "snake game canvas", "language": "JavaScript"}
        return {"purpose": "A small snake game on an HTML canvas.", "architecture": "main.js starts a Snake.",
                "how_to_run": "open index.html", "key_modules": [{"path": "src/main.js", "role": "entry"}],
                "patterns": ["requestAnimationFrame loop"], "use_when": "building canvas games",
                "keywords": ["snake", "game", "canvas"]}


def learner(chat=None, http=None, options=None):
    reports = []
    actions = SimpleNamespace(base=tempfile.mkdtemp(), report=lambda *a: reports.append(a),
                              memory=SimpleNamespace(vault=tempfile.mkdtemp(), record=lambda *a: None))
    instance = rl.RepoLearner(actions, {"dwell_seconds": 0, **(options or {})}, http=http, model_chat=chat or Summary())
    instance.cache = Path(tempfile.mkdtemp())
    return instance, reports


class AnalysisTests(unittest.TestCase):
    def test_zip_analysis_is_multilanguage_and_skips_vendor(self):
        facts = rl.analyze_zip(SAMPLE)
        paths = [m["path"] for m in facts["modules"]]
        self.assertNotIn("node_modules/x/index.js", paths)
        self.assertEqual(set(facts["languages"]), {"JavaScript", "Python"})
        main = next(m for m in facts["modules"] if m["path"] == "src/main.js")
        self.assertEqual(main["symbols"][0]["name"], "start")
        self.assertIn("./snake.js", main["imports"])
        snake = next(m for m in facts["modules"] if m["path"] == "src/snake.js")
        self.assertEqual([s["name"] for s in snake["symbols"]], ["Snake", "step"])
        app = next(m for m in facts["modules"] if m["path"] == "app.py")
        self.assertEqual(app["symbols"][0]["signature"], "serve(port: int=8000)")
        self.assertTrue(app["entry"])
        self.assertTrue(facts["has_tests"])
        self.assertIn("package.json", facts["manifests"])
        self.assertIn("tiny snake game", facts["readme"])

    def test_browser_titles(self):
        self.assertEqual(rl.title_repo("psf/requests: A simple HTTP library - Google Chrome"), "psf/requests")
        self.assertEqual(rl.title_repo("api.py at main · psf/requests - Google Chrome"), "psf/requests")
        self.assertEqual(rl.title_repo("GitHub - psf/requests: HTTP - Google Chrome"), "psf/requests")
        self.assertIsNone(rl.title_repo("Reddit - r/python: hot - Google Chrome"))
        self.assertIsNone(rl.title_repo("settings/profile - Google Chrome"))


class LearningTests(unittest.TestCase):
    def http_for(self, info, archive=SAMPLE):
        http = Mock()

        def get(url, params=None, headers=None, timeout=None, stream=False):
            response = Mock(status_code=200)
            response.raise_for_status = lambda: None
            if "codeload" in url:
                response.iter_content = lambda size: [archive]
            elif "/search/" in url:
                response.json = lambda: {"items": [dict(info, full_name="other/finance-tool", description="stock charts"),
                                                   info, dict(info, full_name="c/snake-clone", description="snake game")]}
            else:
                response.json = lambda: info
            return response
        http.get.side_effect = get
        return http

    INFO = {"full_name": "demo/snake", "html_url": "https://github.com/demo/snake", "description": "Snake game on canvas",
            "stargazers_count": 120, "size": 50, "default_branch": "main", "topics": ["game"], "license": {"spdx_id": "MIT"}}

    def test_learn_saves_note_index_cache_and_cards(self):
        instance, reports = learner(http=self.http_for(self.INFO))
        row = instance.learn("demo/snake", "you viewed it")
        self.assertEqual(row["purpose"], "A small snake game on an HTML canvas.")
        note = (instance.vault / "demo__snake.md").read_text(encoding="utf-8")
        self.assertIn("## Architecture", note)
        self.assertIn("`src/main.js`", note)
        self.assertIn("demo/snake", json.loads((instance.vault / "index.json").read_text(encoding="utf-8"))["repos"])
        self.assertTrue(any((instance.cache / "demo__snake" / "files").iterdir()))
        phases = [a[1]["phase"] for a in reports if a[0] == "media_card"]
        self.assertEqual((phases[0], phases[-1]), ("learning", "learned"))
        self.assertTrue(all(a[1]["service"] == "github" for a in reports if a[0] == "media_card"))

    def test_prepare_searches_then_reuses_memory(self):
        chat = Summary()
        http = self.http_for(self.INFO)
        instance, reports = learner(chat=chat, http=http)
        refs = instance.prepare("create a snake game in javascript with canvas", lambda: False)
        self.assertEqual(refs[0]["repository"], "demo/snake")  # The model's pick, not the finance tool.
        self.assertTrue(refs[0]["code_excerpts"])
        calls = http.get.call_count
        again = instance.prepare("make a snake game with canvas and a score", lambda: False)
        self.assertEqual(again[0]["repository"], "demo/snake")
        self.assertEqual(http.get.call_count, calls)  # Saved memory: no network the second time.
        self.assertEqual(instance.index["demo/snake"]["used_for"][-1], "make a snake game with canvas and a score")
        self.assertEqual(instance.prepare("fix the typo in readme", lambda: False), [])  # No references needed.

    def test_browsing_queues_after_dwell_and_verifies(self):
        instance, _ = learner(http=self.http_for(self.INFO), options={"dwell_seconds": 0})
        clock = [100.]
        instance.clock = lambda: clock[0]
        instance.observe_title("demo/snake: Snake game - Google Chrome", "chrome.exe")
        clock[0] += 1
        instance.observe_title("demo/snake: Snake game - Google Chrome", "chrome.exe")
        deadline = time.time() + 5
        while instance.jobs.empty() and time.time() < deadline:
            time.sleep(.05)
        self.assertEqual(instance.jobs.get_nowait(), ("demo/snake", "you viewed it"))
        instance.observe_title("notes/todo: x - Notepad", "notepad.exe")  # Not a browser: ignored.
        self.assertEqual(instance.viewing["candidate"], "demo/snake")

    def test_commands(self):
        self.assertEqual(parse("learn this repo"), Command("repo_learn", ""))
        self.assertEqual(parse("learn https://github.com/psf/requests"), Command("repo_learn", "psf/requests"))
        self.assertEqual(parse("what repos have you learned"), Command("repo_list", ""))
        self.assertEqual(parse("what is this repo about"), Command("repo_explain", ""))
        self.assertEqual(parse("forget the repo psf/requests"), Command("repo_forget", "psf/requests"))


class ContextTests(unittest.TestCase):
    def test_situation_combines_contexts(self):
        from jarvis.context_hub import situation
        instance, _ = learner()
        instance.viewing = {"candidate": "demo/snake", "full_name": "demo/snake", "since": 0, "learned": False, "queued": True}
        instance.current = "demo/snake"
        prompt = SimpleNamespace(question="Send this WhatsApp message to Jay?")
        curator = SimpleNamespace(enabled=True, lock=__import__("threading").RLock(),
                                  turns=[{"q": "draft an email to my boss"}, {"q": "play nadan parinde"}], summaries=[])
        actions = SimpleNamespace(repo_learner=instance, task_state=SimpleNamespace(snapshot=lambda: {"status": "running", "goal": "build a site", "kind": "code_task"}),
                                  pending_tasks=[("t", Command("task", "open notepad"))], whatsapp_prompts=[prompt],
                                  pending_question=None, last_media="spotify", projects=None, curator=curator, weather_watch=None)
        found = situation(actions, "what is this repo about")
        self.assertEqual(found["viewing_repository"], {"repository": "demo/snake", "learned": False})
        self.assertEqual(found["background_learning"]["now"], "demo/snake")
        self.assertEqual(found["current_task"]["goal"], "build a site")
        self.assertEqual(found["queued_tasks"], ["open notepad"])
        self.assertIn("WhatsApp", found["waiting_for_your_answer"])
        self.assertEqual(found["recent_topics"], ["draft an email to my boss", "play nadan parinde"])
        self.assertEqual(found["media"]["service"], "spotify")


class IslandTests(unittest.TestCase):
    def test_github_card(self):
        from jarvis.island import MEDIA_HEIGHT, render_island
        from jarvis.media_player import card
        for phase in ("learning", "learned", "error"):
            image = render_island(560, MEDIA_HEIGHT, "WORKING", 1., "", 10, False, "", 1.,
                                  card("github", phase, "psf/requests", "HTTP for humans", "", 0, 0, "Understanding the code"))
            self.assertEqual(image.size[1], MEDIA_HEIGHT)


if __name__ == "__main__":
    unittest.main()


class PlanRepairTests(unittest.TestCase):
    def test_unowned_split_becomes_one_worker(self):
        from jarvis.codex_workload import collapse_unowned_split
        plan = {"files": [{"path": "index.html"}, {"path": "game.js"}, {"path": "test_game.py"}],
                "checks": [{"kind": "python_tests", "path": "test_game.py"}, {"kind": "browser", "path": "index.html"}],
                "tasks": [{"key": "html", "goal": "markup", "paths": ["index.html"], "dependencies": [], "check_indices": [0]},
                          {"key": "js", "goal": "logic", "paths": ["game.js"], "dependencies": [], "check_indices": [0]},
                          {"key": "test", "goal": "tests", "paths": ["test_game.py"], "dependencies": [], "check_indices": [0]}]}
        merged, changed = collapse_unowned_split(plan)
        self.assertTrue(changed)
        self.assertEqual(merged["tasks"][0]["paths"], ["index.html", "game.js", "test_game.py"])
        self.assertEqual(merged["tasks"][0]["check_indices"], [0, 1])
        owned = {"files": plan["files"][:2] + [{"path": "test_a.py"}],
                 "checks": [{"kind": "python_tests", "path": "test_a.py"}],
                 "tasks": [{"key": "a", "paths": ["index.html", "test_a.py"], "check_indices": [0]},
                           {"key": "b", "paths": ["game.js"], "check_indices": [0]}]}
        self.assertTrue(collapse_unowned_split(owned)[1])
        valid = {"files": [{"path": "a.py"}, {"path": "test_a.py"}, {"path": "b.py"}, {"path": "test_b.py"}],
                 "checks": [{"kind": "python_tests", "path": "test_a.py"}, {"kind": "python_tests", "path": "test_b.py"}],
                 "tasks": [{"key": "a", "paths": ["a.py", "test_a.py"], "check_indices": [0]},
                           {"key": "b", "paths": ["b.py", "test_b.py"], "check_indices": [1]}]}
        self.assertFalse(collapse_unowned_split(valid)[1])  # Already valid: parallel workers are kept.
