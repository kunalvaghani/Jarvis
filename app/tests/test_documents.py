import json
import os
import tempfile
import threading
import time
import unittest
import zlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from jarvis import documents as dm
from jarvis import file_drop as fd
from jarvis.commands import Command, parse


def make_pdf(path, pages):
    """A real PDF with one text page per string (Helvetica), written by hand."""
    objects = ["<< /Type /Catalog /Pages 2 0 R >>", None, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for text in pages:
        lines = [text[i:i + 90] for i in range(0, len(text), 90)] or [""]
        stream = "BT /F1 10 Tf 40 800 Td 12 TL " + " ".join(
            "(" + line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") + ") '" for line in lines) + " ET"
        data = zlib.compress(stream.encode("latin-1"))
        objects.append(("stream", data))
        content = len(objects)
        objects.append("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> "
                       "/Contents " + str(content) + " 0 R >>")
        kids.append(str(len(objects)) + " 0 R")
    objects[1] = "<< /Type /Pages /Kids [" + " ".join(kids) + "] /Count " + str(len(kids)) + " >>"
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, item in enumerate(objects, 1):
        offsets.append(len(out))
        if isinstance(item, tuple):
            out += (str(number) + " 0 obj\n<< /Length " + str(len(item[1])) + " /Filter /FlateDecode >>\nstream\n").encode()
            out += item[1] + b"\nendstream\nendobj\n"
        else:
            out += (str(number) + " 0 obj\n" + item + "\nendobj\n").encode()
    xref = len(out)
    out += ("xref\n0 " + str(len(objects) + 1) + "\n0000000000 65535 f \n").encode()
    out += "".join("%010d 00000 n \n" % o for o in offsets).encode()
    out += ("trailer\n<< /Size " + str(len(objects) + 1) + " /Root 1 0 R >>\nstartxref\n" + str(xref) + "\n%%EOF\n").encode()
    Path(path).write_bytes(bytes(out))
    return Path(path)


BRIEF = ["Client brief for the Aurora website redesign. The client is Northwind Studio, based in Lyon.",
         "Budget: 12000 euros. The deadline for the first prototype is 14 November. Contact person: Claire Martin.",
         "Deliverables: a responsive landing page, a blog, and an English and French version of every page."]


class Model:
    def __init__(self):
        self.calls = []

    def __call__(self, system, payload, schema):
        self.calls.append((system[:30], payload))
        if schema is dm.GRAPH_SCHEMA:
            return {"entities": [{"name": "Claire Martin", "type": "person", "description": "Contact person at Northwind Studio."}],
                    "relations": [{"source": "Claire Martin", "target": "Northwind Studio", "relation": "works for"}]}
        if schema is fd.EMAIL_SCHEMA:
            return {"subject": "Aurora brief", "body": "Hi,\n\nHere is the brief, as promised.\n\nBest regards"}
        if system.startswith("You answer"):
            text = " ".join(e["text"] for e in payload["excerpts"])
            return "The deadline is 14 November (p. 2)." if "14 November" in text else "I couldn't find it."
        return "A client brief for a website redesign."


def library(model=None, options=None):
    base = Path(tempfile.mkdtemp())
    vault = base / "vault"
    reports = []
    actions = SimpleNamespace(base=str(base), report=lambda *a: reports.append(a), memory=SimpleNamespace(vault=str(vault)),
                              whatsapp_prompts=[], desktop=None)
    lib = dm.Library(actions, options or {}, model_chat=model or Model())
    actions.documents = lib
    return lib, actions, reports


class Reading(unittest.TestCase):
    def test_pdf_docx_and_text_are_read_with_pages(self):
        folder = Path(tempfile.mkdtemp())
        pages = dm.extract(make_pdf(folder / "brief.pdf", BRIEF))
        self.assertEqual([p for p, _ in pages], [1, 2, 3])
        self.assertIn("14 November", pages[1][1])
        import zipfile
        with zipfile.ZipFile(folder / "note.docx", "w") as archive:
            archive.writestr("word/document.xml", "<w:document><w:body><w:p><w:r><w:t>Hello</w:t></w:r></w:p>"
                                                  "<w:p><w:r><w:t>World &amp; more</w:t></w:r></w:p></w:body></w:document>")
        self.assertEqual(dm.extract(folder / "note.docx")[0][1], "Hello\nWorld & more")
        (folder / "a.md").write_text("# Title\ntext", encoding="utf-8")
        self.assertIn("Title", dm.extract(folder / "a.md")[0][1])
        self.assertEqual(dm.extract(folder / "photo.png"), [])

    def test_unreadable_files_say_why(self):
        folder = Path(tempfile.mkdtemp())
        empty = make_pdf(folder / "scan.pdf", ["", ""])
        with self.assertRaises(ValueError) as caught:
            dm.Document.build(empty)
        self.assertIn("scanned image", str(caught.exception))


class Indexing(unittest.TestCase):
    def test_light_mode_for_short_documents_answers_with_pages(self):
        lib, actions, _ = library()
        path = make_pdf(Path(tempfile.mkdtemp()) / "brief.pdf", BRIEF)
        document, reused = lib.add(path)
        self.assertFalse(reused)
        self.assertEqual(document.data["mode"], "light")
        self.assertIn("Northwind Studio", document.data["graph"]["entities"])
        context = document.context("When is the deadline for the prototype?")
        self.assertEqual(context["excerpts"][0]["page"], 2)
        self.assertEqual(lib.answer("When is the deadline?"), "The deadline is 14 November (p. 2).")
        self.assertIs(lib.wants("what is the budget in this pdf"), document)
        self.assertIs(lib.wants("who is Claire Martin"), document)       # A strong match routes without "pdf".
        self.assertIsNone(lib.wants("what's the weather tomorrow"))     # Unrelated questions go to the normal answer.

    def test_graph_mode_for_long_documents_grows_a_knowledge_graph(self):
        lib, _, _ = library(options={"graph_threshold_chars": 300, "graph_max_chunks": 4})
        path = make_pdf(Path(tempfile.mkdtemp()) / "long.pdf", BRIEF * 4)
        document, _ = lib.add(path)
        self.assertEqual(document.data["mode"], "graph")
        lib.workers[document.id].join(10)
        entity = document.data["graph"]["entities"]["Claire Martin"]
        self.assertEqual((entity["type"], entity["source"]), ("person", "model"))
        hits, facts, _ = document.neighbourhood("Who does Claire Martin work for?")
        self.assertIn("Claire Martin", hits)
        self.assertIn("Claire Martin — works for — Northwind Studio", facts)

    def test_session_then_long_term_memory_and_reconnect(self):
        lib, actions, _ = library()
        path = make_pdf(Path(tempfile.mkdtemp()) / "brief-client.pdf", BRIEF)
        document, _ = lib.add(path)
        lib.answer("When is the deadline?")
        self.assertTrue((lib.root / "session" / (document.id + ".json")).exists())  # Crash-safe session copy.
        self.assertIn("saved brief-client.pdf", dm.execute(actions, parse("done with the pdf"), lambda: False))
        self.assertFalse((lib.root / "session" / (document.id + ".json")).exists())
        saved = json.loads((lib.root / document.id / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["questions"][0]["q"], "When is the deadline?")
        note = next((Path(actions.memory.vault) / "Jarvis Documents").glob("brief-client*.md")).read_text(encoding="utf-8")
        self.assertIn("LightRAG-style", note)
        self.assertIn("When is the deadline?", note)
        # A new session: the same file reconnects, and the name finds it.
        again, _, _ = library()
        again.root = lib.root
        reloaded, reused = again.prepare(path)
        self.assertTrue(reused)
        self.assertEqual(reloaded.data["questions"][0]["a"], "The deadline is 14 November (p. 2).")
        self.assertEqual(again.find("brief client").id, document.id)
        self.assertIn("brief-client.pdf", dm.execute(again.actions, parse("what documents do you remember"), lambda: False))

    def test_a_crashed_session_is_saved_at_next_start(self):
        lib, actions, _ = library()
        document, _ = lib.add(make_pdf(Path(tempfile.mkdtemp()) / "brief.pdf", BRIEF))
        actions2 = SimpleNamespace(base=actions.base, report=actions.report, memory=actions.memory)
        restarted = dm.Library(actions2, {}, model_chat=Model())  # No close(): as after a crash.
        self.assertIn(document.id, restarted.remembered())

    def test_document_phrases(self):
        self.assertEqual(parse("ask the pdf what is the budget").kind, "doc_ask")
        self.assertEqual(parse("what does the document say about the deadline").kind, "doc_ask")
        self.assertEqual(parse("in the pdf, who is the contact").value, "who is the contact")
        self.assertEqual(parse("I'm done with the pdf").kind, "doc_end")
        self.assertEqual(parse("load the document brief client").kind, "doc_open")
        self.assertEqual(parse("open file notes dot txt").kind, "open_file")  # Opening a file is unchanged.


class DropFlow(unittest.TestCase):
    def flow(self, answers, files=None, **patches):
        lib, actions, reports = library()
        files = files or [str(make_pdf(Path(tempfile.mkdtemp()) / "brief-client.pdf", BRIEF))]
        script = list(answers)
        asked = []

        def ask(actions_, prompt, cancelled, speak=None):
            asked.append((prompt.question, speak, [o["label"] for o in prompt.options]))
            answer = script.pop(0)
            return answer if not isinstance(answer, str) or prompt.free_text else (prompt.resolve(answer) and prompt.answer)
        with patch("jarvis.whatsapp.ask", ask), patch.dict("os.environ", {}):
            extra = [patch(target, value) for target, value in patches.items()]
            for item in extra:
                item.start()
            try:
                reply = fd.handle(actions, files)
            finally:
                for item in extra:
                    item.stop()
        return reply, asked, reports, lib

    def test_ask_questions_indexes_and_focuses(self):
        reply, asked, reports, lib = self.flow(["ask questions"])
        self.assertIn("ready. What should I do with it?", asked[0][0])
        self.assertEqual(asked[0][2], ["Ask questions about it", "Send it on WhatsApp", "Send it by email", "Nothing for now"])
        self.assertIn("Ask me anything about brief-client.pdf", reply)
        self.assertEqual(lib.focused().name, "brief-client.pdf")
        phases = [r[1]["phase"] for r in reports if r[0] == "media_card"]
        self.assertEqual(phases[:2], ["eating", "ready"])
        self.assertTrue(all(r[1]["service"] == "buddy" for r in reports if r[0] == "media_card"))

    def test_whatsapp_asks_whom_and_message_then_sends_both(self):
        sent = {}

        def send_files(actions, to, paths, caption, cancelled):
            sent.update(to=to, paths=paths, caption=caption)
            return "Sent brief-client.pdf to Aashish on WhatsApp with your message."
        reply, asked, _, _ = self.flow(["whatsapp", "Aashish", "here is the brief, check it tonight"],
                                       **{"jarvis.whatsapp.send_files": send_files})
        self.assertEqual([q for q, _, _ in asked][1:], ["Who should I send brief-client.pdf to on WhatsApp?",
                                                        "Add a message with it? Type or say it — or say no."])
        self.assertEqual((sent["to"], sent["caption"]), ("Aashish", "here is the brief, check it tonight"))
        self.assertTrue(sent["paths"][0].endswith("brief-client.pdf"))
        self.assertTrue(reply.startswith("Sent"))
        _, _, _, _ = self.flow(["whatsapp", "Aashish", "no"], **{"jarvis.whatsapp.send_files": lambda a, t, p, c, x: sent.update(caption=c) or "Sent"})
        self.assertEqual(sent["caption"], "")  # "No" means no message, just the file.

    def test_email_recipient_or_blank_and_written_body_as_gmail_draft(self):
        drafted = {}

        def draft(base, to, subject, body, files):
            drafted.update(to=to, subject=subject, body=body, files=[Path(f).name for f in files])
            return "r123"
        reply, asked, _, _ = self.flow(["email", "hello at studio dot fr", "tell them it's the brief as promised"],
                                       **{"jarvis.gmail_api.configured": lambda base=None: True,
                                          "jarvis.gmail_api.draft_with_attachments": draft})
        self.assertEqual(drafted, {"to": "hello@studio.fr", "subject": "Aurora brief",
                                   "body": "Hi,\n\nHere is the brief, as promised.\n\nBest regards", "files": ["brief-client.pdf"]})
        self.assertIn("drafted the email to hello@studio.fr", reply)
        self.flow(["email", "no one", 0], **{"jarvis.gmail_api.configured": lambda base=None: True,
                                            "jarvis.gmail_api.draft_with_attachments": draft})
        self.assertEqual(drafted["to"], "")  # Blank recipient, body written automatically.
        self.flow(["email", "Aashish", "kunal at gmail dot com", 0], **{"jarvis.gmail_api.configured": lambda base=None: True,
                                                                         "jarvis.gmail_api.draft_with_attachments": draft})
        self.assertEqual(drafted["to"], "kunal@gmail.com")  # A bare name asks once more for an address.

    def test_files_that_are_not_text_can_still_be_sent(self):
        image = Path(tempfile.mkdtemp()) / "photo.png"
        image.write_bytes(b"\x89PNG\r\n")
        reply, asked, _, _ = self.flow(["nothing"], files=[str(image)])
        self.assertEqual(asked[0][2], ["Send it on WhatsApp", "Send it by email", "Nothing for now"])
        self.assertIn("keep photo.png in mind", reply)

    def test_spoken_addresses(self):
        self.assertEqual(fd.email_address("hello at studio dot fr"), "hello@studio.fr")
        self.assertEqual(fd.email_address("no one"), "")
        self.assertIsNone(fd.email_address("Aashish"))

    def test_gmail_message_carries_the_attachment(self):
        from email import message_from_bytes
        from jarvis.gmail_api import attachment_message
        path = make_pdf(Path(tempfile.mkdtemp()) / "brief.pdf", BRIEF)
        message = message_from_bytes(attachment_message("a@b.co", "Subject", "Body", [path]))
        parts = [p for p in message.walk() if p.get_filename()]
        self.assertEqual((parts[0].get_filename(), parts[0].get_content_type()), ("brief.pdf", "application/pdf"))
        self.assertEqual(parts[0].get_payload(decode=True), path.read_bytes())


class VoiceAnswers(unittest.TestCase):
    def test_free_text_questions_take_the_whole_sentence(self):
        from jarvis.engine import Engine
        sent = []
        engine = Engine(sent.append, lambda *a: None)
        engine.free_text = lambda: True
        engine.feed("Jarvis hello at studio dot fr", final=True)
        self.assertEqual(sent[-1], Command("whatsapp_answer", "hello at studio dot fr"))
        engine.feed("Jarvis open notepad and write hi", final=True)  # Not run as a command while a question waits.
        self.assertEqual(sent[-1], Command("whatsapp_answer", "open notepad and write hi"))
        engine.feed("Jarvis cancel", final=True)
        self.assertNotEqual(sent[-1].kind, "whatsapp_answer")  # Cancel still cancels.


@unittest.skipUnless(os.name == "nt", "Windows drag and drop")
class RealDrop(unittest.TestCase):
    def test_a_real_wm_dropfiles_reaches_the_island(self):
        import ctypes
        import struct
        import tkinter as tk
        root = tk.Tk()
        try:
            canvas = tk.Canvas(root, width=200, height=50)
            canvas.pack()
            root.update()
            got = []
            target = fd.DropTarget(root, [canvas], got.extend)
            self.assertTrue(target.active)
            files = [str(make_pdf(Path(tempfile.mkdtemp()) / "brief.pdf", BRIEF))]
            data = struct.pack("<IiiII", 20, 0, 0, 0, 1) + ("\0".join(files) + "\0\0").encode("utf-16-le")
            kernel = ctypes.windll.kernel32
            kernel.GlobalAlloc.restype = ctypes.c_void_p
            kernel.GlobalLock.restype = ctypes.c_void_p
            kernel.GlobalLock.argtypes = kernel.GlobalUnlock.argtypes = [ctypes.c_void_p]
            handle = kernel.GlobalAlloc(0x0042, len(data))
            ctypes.memmove(kernel.GlobalLock(handle), data, len(data))
            kernel.GlobalUnlock(handle)
            user = ctypes.windll.user32
            user.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p]
            user.SendMessageW(canvas.winfo_id(), fd.WM_DROPFILES, handle, None)
            deadline = time.monotonic() + 3
            while not got and time.monotonic() < deadline:
                root.update()
                target.poll()  # The island's frame loop does this.
            self.assertEqual(got, files)
            target.close()
            self.assertFalse(target.active)
        finally:
            root.destroy()


    def test_a_drop_inside_the_running_event_loop_does_not_crash(self):
        # 2026-10-12: dropping a file on the running island aborted Jarvis (Tk called from the window procedure).
        import subprocess
        import sys
        script = Path(__file__).parent / "fixtures" / "drop_in_mainloop.py"
        pdf = make_pdf(Path(tempfile.mkdtemp()) / "brief.pdf", BRIEF)
        done = subprocess.run([sys.executable, str(script), str(Path(__file__).parents[1]), str(pdf)], capture_output=True,
                              text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr[-800:])
        self.assertIn("RECEIVED", done.stdout)
        self.assertIn("CLEAN EXIT", done.stdout)
        self.assertNotIn("Fatal Python error", done.stderr)


class PipRendering(unittest.TestCase):
    def test_every_mood_and_card_renders(self):
        from PIL import Image, ImageDraw
        from jarvis.island import MEDIA_HEIGHT, animate_frame, render_island
        from jarvis.island_buddy import MOODS, draw_buddy, mood_for
        canvas = Image.new("RGB", (120, 120))
        for mood in MOODS:
            for moment in (0, .7, 2.3):
                draw_buddy(ImageDraw.Draw(canvas), 60, 60, 50, mood, moment, 1)
        self.assertEqual(mood_for("eating"), "eating")
        self.assertEqual(mood_for("sent"), "happy")
        for phase in ("hungry", "eating", "ready", "indexing", "thinking", "happy", "sad"):
            media = {"service": "buddy", "phase": phase, "title": "brief.pdf", "subtitle": "", "detail": "", "image": "",
                     "position": 0, "duration": 0, "at": 0}
            base = render_island(560, MEDIA_HEIGHT, "STANDBY", 1.2, "", 0, False, "", 1.5, media, buddy="idle")
            frame = animate_frame(base, 560, MEDIA_HEIGHT, "STANDBY", 1.4, 0, 1.5, media, "idle")
            self.assertEqual(frame.size, base.size)
        compact = render_island(402, 40, "STANDBY", 0, "", 0, False, "", 1., None, buddy="sleepy")
        self.assertEqual(compact.size, (402, 40))


if __name__ == "__main__":
    unittest.main()
