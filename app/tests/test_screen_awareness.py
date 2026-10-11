import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from jarvis import screen_awareness as sa
from jarvis.app_knowledge import AppKnowledge, inventory, profile_for
from jarvis.commands import Command, parse
from jarvis.ui_controls import UIControls

APP = Path(__file__).resolve().parent.parent
YT_TITLE = "Music - YouTube - Google Chrome"


def link(name, x=200, y=300, role="Hyperlink"):
    return {"name": name, "role": role, "rect": [x, y, x + 300, y + 40], "context": "", "id": [len(name)]}


VIDEOS = [link("Lofi hip hop radio - beats to relax/study to", y=300), link("Best English songs 2026 playlist", y=360),
          link("LOFI Girl - synthwave radio", y=420), link("Home", x=10, y=100, role="Button")]


class Fake:
    """Actions stand-in: records reports and submitted commands, runs queued screen actions inline."""
    def __init__(self, controls=VIDEOS, title=YT_TITLE):
        self.base = Path(tempfile.mkdtemp())
        self.apps = {}
        self.current_item, self.pending_tasks, self.whatsapp_prompts = None, [], []
        self.pending_question, self.dictation_active, self.approvals_waiting, self.task_active = None, False, 0, False
        self.reports, self.submitted = [], []
        self.calls = []
        self.title = title
        self.controls = controls

        def runner(request, cancelled=lambda: False):
            self.calls.append(request)
            if request["operation"] == "list":
                return {"controls": self.controls, "signature": "sig", "context": "ctx", "title": self.title}
            return {"message": "Selected " + request["control"]["name"]}
        self.ui = UIControls(SimpleNamespace(target=None), runner=runner)
        self.hands_free = Mock()
        self.hands_free_state = lambda: None
        self.knowledge = SimpleNamespace(submit=Mock())
        self.desktop = SimpleNamespace(target=None, capture=Mock(), type=Mock())
        self.screen = sa.ScreenAwareness(self, {"dwell_seconds": 0})
        self.screen.can_offer = lambda: True
        self.screen._front = lambda handle: None

    def _ui(self):
        return self.ui

    def report(self, kind, message=""):
        self.reports.append((kind, message))

    def submit(self, command):
        self.submitted.append(command)
        if command.kind == "screen_act":
            result = self.screen.act(json.loads(command.value))
            if result:
                self.reports.append(("spoken_reply", result))

    def offers(self):
        return [m for k, m in self.reports if k == "screen_offer"]

    def say(self, text):
        try:
            command = parse(text)
        except ValueError:
            command = Command("task", text, "unparsed")  # How the engine sends unrecognised speech.
        return self.screen.answer(command)

    def show(self, exe, title, window_class="Chrome_WidgetWin_1"):
        self.screen.observe(101, title, exe, window_class)
        self.screen.tick()
        deadline = time.time() + 3
        while self.screen.reading and time.time() < deadline:
            time.sleep(.01)


class KnowledgeTests(unittest.TestCase):
    def test_inventory_of_this_pc(self):
        apps = json.loads((APP / "config/config.json").read_text(encoding="utf-8"))["apps"]
        rows = inventory(apps)
        self.assertGreater(len(rows), 300)
        by = {r["name"]: r for r in rows}
        self.assertEqual((by["spotify"]["category"], by["notepad"]["category"], by["code"]["category"]), ("music", "notes", "code"))
        self.assertEqual(by["counter-strike global offensive"]["category"], "games")
        self.assertEqual(by["7-zip help"]["category"], "help")
        self.assertLess(sum(r["category"] == "other" for r in rows), 15)

    def test_profiles_pick_the_most_specific(self):
        self.assertEqual(profile_for("chrome.exe", YT_TITLE)["key"], "youtube")
        self.assertEqual(profile_for("chrome.exe", "News - Google Chrome")["key"], "browser")
        self.assertEqual(profile_for("C:/Windows/notepad.exe", "a.txt - Notepad")["key"], "notepad")
        self.assertEqual(profile_for("explorer.exe", "Documents", "CabinetWClass")["key"], "explorer")
        self.assertIsNone(profile_for("explorer.exe", "", "Shell_TrayWnd"))  # The taskbar isn't File Explorer.
        self.assertTrue(profile_for("WhatsApp.exe", "WhatsApp")["private"])

    def test_learns_button_names_only(self):
        k = AppKnowledge(tempfile.mkdtemp())
        controls = [{"name": "Play", "role": "Button"}, {"name": "Shuffle", "role": "Button"}, {"name": "Mum", "role": "ListItem"},
                    {"name": "me@mail.com", "role": "Button"}, {"name": "Messages (3)", "role": "Button"},
                    {"name": "secret", "role": "Edit", "password": True}, {"name": "Library", "role": "TabItem"}]
        self.assertEqual(k.learn("Spotify.exe", "Spotify", controls), 3)
        self.assertEqual(k.buttons("spotify"), ["Play", "Shuffle", "Library"])
        info = AppKnowledge(k.path.parent.parent).describe("Spotify.exe", "Spotify")  # Saved and reloaded.
        self.assertEqual(info["app"], "Spotify")
        self.assertIn("Play", info["buttons_seen"])
        self.assertIn("Main features", k.explain_current("Spotify.exe", "Spotify"))

    def test_helpers(self):
        titles = [c["name"] for c in VIDEOS[:3]]
        self.assertEqual(sa.match_titles("lofi", titles), [0, 2])
        self.assertEqual(sa.match_titles("the playlist one", titles), [1])
        self.assertEqual(sa.match_titles("despasito", ["Luis Fonsi - Despacito", "Shape of you"]), [0])  # Misheard spelling.
        self.assertEqual(sa.match_titles("zebra", titles), [])
        self.assertEqual(sa.safe_sum("25 times 4 plus 3"), ("25*4+3", 103))
        self.assertIsNone(sa.safe_sum("__import__('os')"))
        self.assertEqual(sa.ordinal("the second one"), 2)


class YouTubeTests(unittest.TestCase):
    def test_offer_yes_then_a_word_opens_that_video(self):
        a = Fake(controls=[VIDEOS[1], VIDEOS[2], VIDEOS[3]])
        a.show("chrome.exe", YT_TITLE)
        self.assertEqual(a.offers(), ["You're on YouTube. Want me to open one of the videos on screen? Just say a word from its title."])
        self.assertTrue(a.say("yes"))
        self.assertEqual(a.offers()[-1], "Which one? Say a word from its title.")
        self.assertTrue(a.say("lofi"))
        activated = [c for c in a.calls if c["operation"] == "activate"]
        self.assertEqual(activated[0]["control"]["name"], "LOFI Girl - synthwave radio")
        self.assertIn("Opening LOFI Girl", a.reports[-1][1])

    def test_word_straight_away_and_choosing_between_matches(self):
        a = Fake()
        a.show("chrome.exe", YT_TITLE)
        self.assertTrue(a.say("yes the lofi one"))
        self.assertIn("2 videos match 'the lofi one'", a.offers()[-1])
        self.assertTrue(a.say("the second one"))
        self.assertEqual([c for c in a.calls if c["operation"] == "activate"][0]["control"]["name"], "LOFI Girl - synthwave radio")

    def test_no_match_says_what_is_there(self):
        a = Fake()
        a.show("chrome.exe", YT_TITLE)
        a.say("yes")
        a.say("cricket")
        self.assertIn("None of the videos on screen has 'cricket'", a.reports[-1][1])
        self.assertFalse([c for c in a.calls if c["operation"] == "activate"])

    def test_no_three_times_mutes_and_other_requests_pass_through(self):
        a = Fake()
        for _ in range(3):
            a.screen.asked.clear()
            a.show("chrome.exe", YT_TITLE)
            self.assertTrue(a.say("no thanks"))
        self.assertIn("youtube", a.screen.muted)
        a.screen.asked.clear()
        before = len(a.offers())
        a.show("chrome.exe", YT_TITLE)
        self.assertEqual(len(a.offers()), before)
        b = Fake()
        b.show("chrome.exe", YT_TITLE)
        self.assertFalse(b.say("what is the weather in Toronto"))  # Its own request: handled normally.
        self.assertIsNone(b.screen.offer)

    def test_asks_once_per_app_and_only_when_idle(self):
        a = Fake()
        a.current_item = ("token", Command("task", "x"))
        a.show("chrome.exe", YT_TITLE)
        self.assertEqual(a.offers(), [])
        a.current_item = None
        a.screen.can_offer = lambda: False  # Microphone off or Jarvis talking.
        a.show("chrome.exe", YT_TITLE + " ")
        self.assertEqual(a.offers(), [])
        a.screen.can_offer = lambda: True
        a.show("chrome.exe", YT_TITLE + "  ")
        a.screen.offer = None
        a.show("chrome.exe", YT_TITLE + "   ")
        self.assertEqual(len(a.offers()), 1)  # Cooldown: not asked again straight away.


class OtherAppTests(unittest.TestCase):
    def test_notepad_yes_starts_hands_free_writing(self):
        a = Fake(controls=[{"name": "File", "role": "MenuItem", "rect": [0, 0, 10, 10]}], title="notes.txt - Notepad")
        a.show("notepad.exe", "notes.txt - Notepad", "Notepad")
        self.assertIn("Do you have something in mind to write?", a.offers()[0])
        a.say("yes")
        a.hands_free.assert_called_once_with(True)
        self.assertIn("Say 'stop writing'", a.reports[-1][1])

    def test_spotify_follow_up_becomes_a_play_command(self):
        a = Fake(controls=[{"name": "Play", "role": "Button", "rect": [0, 0, 10, 10]}], title="Spotify Premium")
        a.show("Spotify.exe", "Spotify Premium")
        a.say("yes")
        a.say("believer")
        played = [c for c in a.submitted if c.kind == "play_media"]
        self.assertEqual((played[0].value, played[0].extra), ("believer", "spotify"))

    def test_whatsapp_follow_up_message(self):
        a = Fake(controls=[{"name": "New chat", "role": "Button", "rect": [0, 0, 10, 10]}], title="WhatsApp")
        a.show("WhatsApp.exe", "WhatsApp")
        a.say("yes")
        a.say("mom saying I'll be late")
        sent = [c for c in a.submitted if c.kind == "whatsapp_send"]
        self.assertEqual(sent[0].value, "mom")
        self.assertIn("late", sent[0].extra)
        self.assertEqual(a.screen.knowledge.learned, {})  # Chat apps: labels are never kept.

    def test_mail_and_private_pages_get_no_questions(self):
        a = Fake(title="Inbox (3) - Gmail - Google Chrome")
        a.show("chrome.exe", "Inbox (3) - Gmail - Google Chrome")
        a.show("chrome.exe", "Sign in - Google Accounts - Google Chrome")
        self.assertEqual(a.offers(), [])

    def test_explorer_opens_the_named_item_and_refuses_unsafe(self):
        items = [link("budget 2026.xlsx", role="ListItem"), link("photos", role="ListItem", y=400), link("Delete", role="Button")]
        a = Fake(controls=items, title="Documents")
        a.show("explorer.exe", "Documents", "CabinetWClass")
        a.say("yes")
        a.say("budget")
        activated = [c for c in a.calls if c["operation"] == "activate"]
        self.assertEqual((activated[0]["control"]["name"], activated[0]["verb"]), ("budget 2026.xlsx", "open"))
        reply = a.screen._press({"mode": "click", "handle": 101, "detail": "delete"}, {"roles": ["Button"]}, lambda: False)
        self.assertIn("won't press it", reply)

    def test_calculator_types_the_sum(self):
        a = Fake(controls=[{"name": "Equals", "role": "Button", "rect": [0, 0, 1, 1]}], title="Calculator")
        a.show("CalculatorApp.exe", "Calculator")
        a.say("yes")
        a.say("25 times 4")
        a.desktop.type.assert_called_once()
        self.assertEqual(a.desktop.type.call_args[0][0], "25*4=")
        self.assertIn("is 100", a.reports[-1][1])

    def test_code_editor_answers_about_the_screen(self):
        a = Fake(controls=[{"name": "Run", "role": "Button", "rect": [0, 0, 1, 1]}], title="main.py - Jarvis - Visual Studio Code")
        a.show("Code.exe", "main.py - Jarvis - Visual Studio Code")
        a.say("yes")
        question, kwargs = a.knowledge.submit.call_args
        self.assertIn("code visible in this editor", question[0])
        self.assertEqual(kwargs, {"screen": True})

    def test_unknown_app_offers_learned_buttons(self):
        a = Fake(controls=[{"name": n, "role": "Button", "rect": [0, 0, 1, 1]} for n in ("Render", "Export", "Settings")], title="Tool")
        a.show("weirdtool.exe", "Tool", "X")
        self.assertIn("Want me to press something in weirdtool? I can see Render, Export, Settings", a.offers()[0])
        a.say("export")
        self.assertEqual([c for c in a.calls if c["operation"] == "activate"][0]["control"]["name"], "Export")

    def test_commands(self):
        a = Fake(controls=[{"name": "Play", "role": "Button", "rect": [0, 0, 1, 1]}], title="Spotify")
        a.screen.observe(101, "Spotify", "Spotify.exe", "x")
        self.assertIn("Spotify", a.screen.command("this_app"))
        self.assertIn("Play", a.screen.command("buttons"))
        a.screen.command("mute_app")
        self.assertIn("spotify", a.screen.muted)
        self.assertIn("won't ask", a.screen.command("pause"))
        self.assertFalse(a.screen.enabled)
        a.screen.command("resume")
        self.assertTrue(a.screen.enabled and not a.screen.muted)
        self.assertEqual(parse("what apps do I have").value, "apps")
        self.assertEqual(parse("what can you do here").value, "offer_now")
        self.assertEqual(parse("start dictation"), Command("write_help", "start"))


class HandsFreeWritingTests(unittest.TestCase):
    def test_latch_survives_keys_and_esc_stops(self):
        from jarvis.push_to_write import PushToWrite
        changes = []
        ptw = PushToWrite(lambda active, discarded: changes.append(active), send=lambda: None)
        ptw.latch(True)
        self.assertTrue(ptw.active.is_set())
        ptw.key(0x41, True)  # Typing on the keyboard doesn't end it.
        self.assertTrue(ptw.active.is_set())
        self.assertIsNotNone(ptw.latched_since())
        ptw.key(0x1B, True)
        self.assertFalse(ptw.active.is_set())
        self.assertIsNone(ptw.latched_since())
        self.assertEqual(changes, [True, False])

    def test_stop_phrase(self):
        from jarvis.audio import STOP_WRITING
        self.assertTrue(STOP_WRITING.search("stop writing"))
        self.assertTrue(STOP_WRITING.search("Jarvis, stop writing."))
        found = STOP_WRITING.search("see you tomorrow. Stop writing.")
        self.assertEqual("see you tomorrow. Stop writing."[:found.start()], "see you tomorrow")
        self.assertIsNone(STOP_WRITING.search("I will stop writing letters soon and call instead"))

    def test_actions_submit_routes_answers_to_the_offer(self):
        from jarvis.actions import Actions
        fake = Fake()
        a = Actions.__new__(Actions)
        a.whatsapp_prompts, a.screen = [], fake.screen
        a.screen.offer = {"key": "youtube", "mode": "video", "stage": "confirm", "handle": 101, "profile": "youtube",
                          "time": time.monotonic(), "title": YT_TITLE, "exe": "chrome.exe", "class": ""}
        a.submit(parse("yes"))
        self.assertEqual(fake.offers()[-1], "Which one? Say a word from its title.")


if __name__ == "__main__":
    unittest.main()
