import json
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from jarvis import whatsapp as wa
from jarvis.commands import Command, parse


def item(kind, name, rect=(700, 100, 900, 120), el=None):
    return {"type": kind, "name": name, "rect": rect, "off": False, "el": el or Mock()}


CHAT_LIST = [
    item("grid", "Chat list"),
    item("row", "Jay Vaghani Thursday 👍 Pinned chat", (71, 118, 478, 203)),
    item("item", "Jay Vaghani Thursday 👍 Pinned chat"),
    item("item", "Jay Vaghani Thursday"),
    item("row", "3 unread messages Jay Patel 5:40 pm see you at 6", (71, 203, 478, 286)),
    item("item", "Jay Patel 5:40 pm"),
    item("row", "5 unread messages B.Tech AI-DS 2 Official 5:40 pm Abhi :  Ok Muted chat"),
    item("row", "Contacts"),
    item("row", "Jay Nakum"),
    item("row", "jay"),
]

CHAT = [
    item("button", "Resize the chat list panel", (488, 42, 515, 864)),
    item("button", "Profile details", (506, 54, 568, 99)),
    item("button", "Jay Patel click here for contact info", (566, 54, 1288, 99)),
    item("text", "Yesterday"),
    item("group", "Jay Patel:", (695, 100, 900, 140)),
    item("text", "Kal milte hai?"),
    item("text", "9:05 pm"),
    item("group", "You:", (1400, 150, 1800, 190)),
    item("text", "Haan pakka"),
    item("text", "9:06 pm"),
    item("group", "Delivered"),
    item("text", "2 unread messages"),
    item("group", "Jay Patel:"),
    item("text", "Kitne baje?"),
    item("text", "10:01 pm"),
    item("image", "👍"),
    item("text", "10:02 pm"),
    item("button", "Attach", (634, 1000, 690, 1056)),
    item("edit", "Type a message to Jay Patel", (753, 1012, 1834, 1043)),
]


class ParsingTests(unittest.TestCase):
    def test_parse_row(self):
        row = wa.parse_row("3 unread messages Jay Patel 5:40 pm see you at 6")
        self.assertEqual((row["name"], row["time"], row["unread"], row["preview"], row["group"]),
                         ("Jay Patel", "5:40 pm", 3, "see you at 6", False))
        group = wa.parse_row("5 unread messages B.Tech AI-DS 2 Official 5:40 pm Abhi :  Ok Muted chat")
        self.assertTrue(group["group"] and group["muted"])
        added = wa.parse_row("Family 10/09/2026 Karsh added +91 6356 618")
        self.assertTrue(added["group"])
        self.assertEqual(added["unread"], 0)  # A phone number is not an unread badge.

    def test_chat_rows_skip_cells_and_mark_contacts(self):
        rows = wa.chat_rows(CHAT_LIST)
        self.assertEqual([(r["name"], r["section"]) for r in rows],
                         [("Jay Vaghani", "Chats"), ("Jay Patel", "Chats"), ("B.Tech AI-DS 2 Official", "Chats"),
                          ("Jay Nakum", "Contacts"), ("jay", "Contacts")])

    def test_first_name_lists_everyone_full_name_is_decisive(self):
        rows = wa.chat_rows(CHAT_LIST)
        self.assertEqual([r["name"] for r in wa.match_contacts("Jay", rows)], ["Jay Vaghani", "Jay Patel", "Jay Nakum", "jay"])
        self.assertEqual([r["name"] for r in wa.match_contacts("jay patel", rows)], ["Jay Patel"])
        self.assertEqual([r["name"] for r in wa.match_contacts("jay vagani", rows)], ["Jay Vaghani"])
        self.assertEqual(wa.match_contacts("Rahul", rows), [])

    def test_messages_and_unread(self):
        found = wa.messages(CHAT)
        self.assertEqual([(m["sender"], m["text"], m["time"]) for m in found],
                         [("Jay Patel", "Kal milte hai?", "9:05 pm"), ("You", "Haan pakka", "9:06 pm"),
                          ("Jay Patel", "Kitne baje?", "10:01 pm"), ("Jay Patel", "👍", "10:02 pm")])
        self.assertEqual(found[1]["status"], "Delivered")
        self.assertEqual([m["text"] for m in found if m["unread"]], ["Kitne baje?", "👍"])

    def test_open_chat_identity_is_strict(self):
        self.assertTrue(wa.is_open(CHAT, "Jay Patel"))
        self.assertFalse(wa.is_open(CHAT, "Jay"))
        self_chat = [item("button", "Profile details"), item("button", "Kunal Vaghani (You) Message yourself"),
                     item("edit", "Type a message to Kunal Vaghani")]
        self.assertTrue(wa.is_open(self_chat, "Kunal Vaghani (You)"))
        self.assertFalse(wa.is_open(self_chat, "Kunal Vaghani"))  # A contact with the same saved name.
        group = [item("button", "Profile details"), item("button", "Family Mom, Dad, You"), item("edit", "Type a message to group Family")]
        self.assertTrue(wa.is_open(group, "Family"))


class CommandTests(unittest.TestCase):
    def test_send_and_reply_phrases(self):
        cases = {
            "Send a WhatsApp message to Jay saying I will be late.": ("whatsapp_send", "Jay", "I will be late", False),
            "message Jay Patel on WhatsApp that I'm coming at 6": ("whatsapp_send", "Jay Patel", "I'm coming at 6", False),
            'WhatsApp Rahul saying exactly "ok bro"': ("whatsapp_send", "Rahul", "ok bro", True),
            "ask mom on whatsapp if dinner is ready": ("whatsapp_send", "mom", "ask if dinner is ready", False),
            "send a message to Jay on WhatsApp": ("whatsapp_send", "Jay", "", False),
        }
        for spoken, (kind, who, what, verbatim) in cases.items():
            with self.subTest(spoken=spoken):
                command = parse(spoken)
                data = json.loads(command.extra)
                self.assertEqual((command.kind, command.value, data["instruction"], data["verbatim"]), (kind, who, what, verbatim))
        self.assertEqual(parse("reply to my whatsapp messages"), Command("whatsapp_reply", "", "{}"))
        self.assertEqual(parse("check whatsapp").kind, "whatsapp_reply")
        reply = parse("reply to Jay on whatsapp saying sure")
        self.assertEqual((reply.kind, reply.value, json.loads(reply.extra)["instruction"]), ("whatsapp_reply", "Jay", "sure"))

    def test_approval_words_and_other_apps(self):
        for spoken in ("approve", "Send it.", "pick up", "yes, send it"):
            self.assertEqual(parse(spoken), Command("approval_answer", "yes"), spoken)
        for spoken in ("Don't send it.", "decline", "reject", "hang up"):
            self.assertEqual(parse(spoken), Command("approval_answer", "no"), spoken)
        telegram = parse("message Rahul on telegram saying hi")
        self.assertEqual((telegram.kind, telegram.value, json.loads(telegram.extra)["app"]), ("messenger_send", "Rahul", "telegram"))

    def test_spoken_punctuation_no_longer_hides_player_commands(self):
        self.assertEqual(parse("Pause."), Command("click_control", "pause", "click"))
        self.assertEqual(parse("Play."), Command("click_control", "play", "click"))
        self.assertEqual(parse("Jarvis, pause please."), Command("click_control", "pause", "click"))
        self.assertEqual(parse("Can you pause it?"), Command("click_control", "pause", "click"))
        self.assertEqual(parse("Stop the video."), Command("media_control", "pause", "youtube"))
        self.assertEqual(parse("What's playing?"), Command("spotify_control", "status", "auto"))


class PromptTests(unittest.TestCase):
    def test_resolve(self):
        choice = wa.Prompt("Which Jay?", [{"label": "Jay Vaghani"}, {"label": "Jay Patel"}], "choice")
        self.assertTrue(choice.resolve("Jay Patel"))
        self.assertEqual(choice.answer, 1)
        confirm = wa.Prompt("Send?", [{"label": "Approve and send"}, {"label": "Cancel"}], "confirm", free_text=True)
        self.assertTrue(confirm.resolve("yes send it"))
        self.assertEqual(confirm.answer, 0)
        edit = wa.Prompt("Send?", [{"label": "Approve and send"}, {"label": "Cancel"}], "confirm", free_text=True)
        edit.resolve("make it shorter")
        self.assertEqual(edit.answer, "make it shorter")
        no = wa.Prompt("Send?", [{"label": "Approve and send"}, {"label": "Cancel"}], "confirm")
        no.resolve("no")
        self.assertEqual(no.answer, "no")

    def test_answers_reach_the_newest_prompt(self):
        actions = SimpleNamespace(whatsapp_prompts=[])
        self.assertFalse(wa.answer_prompt(actions, Command("approval_answer", "yes")))
        prompt = wa.Prompt("Which Jay?", [{"label": "Jay Vaghani"}, {"label": "Jay Patel"}], "choice")
        actions.whatsapp_prompts.append(prompt)
        self.assertTrue(wa.answer_prompt(actions, Command("choose_control", "2")))
        self.assertEqual(prompt.answer, 1)
        island = wa.Prompt("Send?", [{"label": "Approve and send"}, {"label": "Cancel"}], "confirm")
        actions.whatsapp_prompts.append(island)
        self.assertFalse(wa.answer_prompt(actions, Command("island_choice", "0", "other-token")))
        self.assertTrue(wa.answer_prompt(actions, Command("island_choice", "0", island.token)))
        call = wa.Prompt("Call", [{"label": "Answer"}, {"label": "Decline"}], "confirm")
        actions.whatsapp_prompts.append(call)
        self.assertTrue(wa.answer_prompt(actions, Command("approval_answer", "no")))
        self.assertEqual(call.answer, "no")
        snap = wa.snapshot(SimpleNamespace(whatsapp_prompts=[wa.Prompt("Send?", [{"label": "Approve and send", "context": "hi"}])]))
        self.assertEqual((snap["kind"], snap["options"][0]["context"]), ("whatsapp", "hi"))

    def test_submit_routes_answers_before_anything_else(self):
        from jarvis.actions import Actions
        actions = Actions.__new__(Actions)
        prompt = wa.Prompt("Send?", [{"label": "Approve and send"}, {"label": "Cancel"}], "confirm")
        actions.whatsapp_prompts, actions.approvals_waiting, actions.decision_handler = [prompt], 0, None
        Actions.submit(actions, Command("task", "yes send it", "unparsed"))
        self.assertEqual(prompt.answer, 0)
        decide = Mock()
        actions.whatsapp_prompts, actions.approvals_waiting, actions.decision_handler = [], 1, decide
        Actions.submit(actions, Command("approval_answer", "yes"))
        decide.assert_called_once_with(True)


class FlowTests(unittest.TestCase):
    def actions(self, answers):
        actions = SimpleNamespace(whatsapp_prompts=[], report=Mock(), config={}, desktop=Mock())

        def answer():
            for value in answers:
                while not actions.whatsapp_prompts:
                    time.sleep(.01)
                prompt = actions.whatsapp_prompts[-1]
                prompt.resolve(value)
                while prompt in actions.whatsapp_prompts:
                    time.sleep(.01)
        threading.Thread(target=answer, daemon=True).start()
        return actions

    def test_send_after_choice_edit_and_approval(self):
        actions = self.actions(["2", "make it shorter", "approve"])
        rows = [dict(wa.parse_row("Jay Vaghani Thursday hi"), section="Chats", el=Mock(), rect=(0, 0, 1, 1), label=""),
                dict(wa.parse_row("Jay Patel 5:40 pm ok"), section="Chats", el=Mock(), rect=(0, 0, 1, 1), label="")]
        with patch.object(wa, "physical"), patch.object(wa, "ensure_window", return_value=7), \
                patch.object(wa, "search", return_value=rows), patch.object(wa, "open_row", return_value="Jay Patel") as opened, \
                patch.object(wa, "clear_search"), patch.object(wa, "document"), patch.object(wa, "read", return_value=CHAT), \
                patch.object(wa, "draft", side_effect=["Running 10 minutes late, sorry!", "10 min late!"]) as drafted, \
                patch.object(wa, "type_draft") as typed, \
                patch.object(wa, "press_send", return_value={"time": "6:01 pm"}) as sent:
            result = wa.send_message(actions, "Jay", "tell him I'm running late", False, lambda: False)
        self.assertEqual(opened.call_args.args[1]["name"], "Jay Patel")
        self.assertEqual(drafted.call_args_list[1].args[4], "revise")
        typed.assert_called_once_with(actions, 7, "Jay Patel", "10 min late!", unittest.mock.ANY)
        sent.assert_called_once_with(7, "Jay Patel", "10 min late!")
        self.assertIn("Sent to Jay Patel", result)
        phases = [c.args[1]["phase"] for c in actions.report.call_args_list if c.args[0] == "media_card"]
        self.assertEqual(phases[:2], ["searching", "choose"])
        self.assertEqual(phases[-2:], ["sending", "sent"])

    def test_declined_preview_types_nothing(self):
        actions = self.actions(["don't send"])
        rows = [dict(wa.parse_row("Jay Patel 5:40 pm ok"), section="Chats", el=Mock(), rect=(0, 0, 1, 1), label="")]
        with patch.object(wa, "physical"), patch.object(wa, "ensure_window", return_value=7), \
                patch.object(wa, "search", return_value=rows), patch.object(wa, "open_row", return_value="Jay Patel"), \
                patch.object(wa, "clear_search"), patch.object(wa, "document"), patch.object(wa, "read", return_value=CHAT), \
                patch.object(wa, "type_draft") as typed, patch.object(wa, "press_send") as sent:
            result = wa.send_message(actions, "Jay Patel", "ok bro", True, lambda: False)
        typed.assert_not_called()
        sent.assert_not_called()
        self.assertIn("didn't send", result)

    def test_watcher_drafts_for_new_messages_only(self):
        actions = SimpleNamespace(config={"whatsapp": {}}, report=Mock(), submit=Mock())
        watcher = wa.Watcher(actions)
        first = [dict(wa.parse_row("2 unread messages Jay Patel 5:40 pm hi"))]
        later = [dict(wa.parse_row("3 unread messages Jay Patel 5:41 pm free tonight?"))]
        with patch("jarvis.window_focus.windows", side_effect=[[(1, "(2) WhatsApp")], [(1, "(3) WhatsApp")], [(1, "(3) WhatsApp")]]), \
                patch.object(wa, "unread_chats", side_effect=[first, later]):
            watcher.check_messages({})
            actions.submit.assert_not_called()  # What was unread at startup is not "new".
            watcher.check_messages({})
            watcher.check_messages({})  # No change: nothing more.
        self.assertEqual(actions.submit.call_count, 1)
        command = actions.submit.call_args.args[0]
        self.assertEqual((command.kind, command.value, json.loads(command.extra)["auto"]), ("whatsapp_reply", "Jay Patel", True))

    def test_incoming_call_answer_and_decline(self):
        for answer, button in (("yes", 1), ("decline", 2)):
            actions = self.actions([answer])
            found = ("Mammi", {"name": "Accept"}, {"name": "Decline"}, "voice")
            with patch.object(wa, "call_controls", return_value=found), patch.object(wa, "physical"), \
                    patch.object(wa, "press") as pressed:
                wa.handle_call(actions, found, threading.Event())
            self.assertIs(pressed.call_args.args[0], found[button])

    def test_unsupported_messenger_is_explained(self):
        from jarvis.messengers import send
        with self.assertRaisesRegex(ValueError, "isn't automated yet"):
            send(SimpleNamespace(), "Sam", {"app": "discord"})


class IslandTests(unittest.TestCase):
    def test_whatsapp_phases_render(self):
        from jarvis.island import MEDIA_HEIGHT, render_island
        for phase in ("searching", "choose", "drafting", "preview", "sending", "sent", "call", "message", "error"):
            image = render_island(560, MEDIA_HEIGHT, "WORKING", 1.1, "", 20, False, "", 1., wa.card(phase, "Jay Patel", "hi", "x"))
            self.assertEqual(image.size[1], MEDIA_HEIGHT)


if __name__ == "__main__":
    unittest.main()
