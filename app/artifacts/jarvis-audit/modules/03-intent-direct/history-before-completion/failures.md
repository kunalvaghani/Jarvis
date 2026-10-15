# Baseline and diagnosis

Initial module assertions: **8 failed, 6 passed in 4.51 seconds**, [baseline XML](baseline.xml). Five implementation failures: temporal spreadsheet fell into generic app open, sound-down-notch and pause-current phrases were unknown, separator comma leaked into the Notepad target, and corrected tab-close phrase was unknown.

Three baseline failures were fixture errors: two tests omitted the fake desktop required for foreground capture, and one used the wrong Spotify volume function signature. They were corrected without production changes. A later compound test expected verbatim write_text despite the established compose_text policy for bare type hello; it now accepts the existing safe composed/verbatim route while still asserting order, content and bound target. That fixture correction is not a production fix.

Final targeted and full XML contain passing runs. No live Chrome, audio, shortcut or typing experiment took place. Generic fault/concurrency/security/resource catalog expectations lacking dedicated executed assertions remain NOT RUN. Unsupported Python 3.10, hard cognition parser-hang containment, task-ID agreement and repository ability isolation remain broader release risks.

The latest-file test's administrative case-ID label was removed during the full run because its body only proves safe routing, not complete ambiguity resolution. Its unchanged assertion body was rerun in the final targeted suite. The full XML may retain its earlier name; the reconciler authorizes case IDs only from the dedicated final targeted XML, so that incidental name cannot grant JRV-03-005 a PASS.
