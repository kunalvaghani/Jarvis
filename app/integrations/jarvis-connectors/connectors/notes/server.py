"""Jarvis Notes: a read-only child of BaseConnector over one approved Markdown folder.

Run: python server.py --root "C:\\absolute\\approved_notes"
Without --root it uses JARVIS_NOTES_DIR, then demo_notes/ next to this file.
stdout is the MCP protocol stream; never print to it.
"""
import os
from pathlib import Path
import sys
from typing import Annotated

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # the jarvis-connectors folder
from jarvis_connector import BaseConnector, ConfinedRoot, Param, ToolError, tool  # noqa: E402

DEMO = Path(__file__).resolve().parent / 'demo_notes'
MAX_RETURN_CHARS = 3000  # fits the base result cap (see BaseConnector.max_result_chars)


class NotesConnector(BaseConnector):
    """Read-only access to Markdown notes in one approved folder."""
    name = 'jarvis-notes'
    version = '1.0.0'
    instructions = 'Read-only search over the user\'s approved Markdown notes folder.'

    @classmethod
    def add_arguments(cls, parser):
        parser.add_argument('--root', default=os.environ.get('JARVIS_NOTES_DIR', str(DEMO)),
                            help='Absolute path of the approved notes folder.')

    def configure(self, options):
        self.root = options.root

    def notes(self):
        # Built per call so a folder created or fixed after launch is picked up without a restart.
        return ConfinedRoot(self.root, {'.md'}, max_bytes=64 * 1024)

    @tool()
    def list_notes(self, limit: Annotated[int, Param('Maximum names to return.', minimum=1, maximum=100)] = 20) -> list[str]:
        """List Markdown note file names in the approved notes folder."""
        return self.notes().files()[:limit]

    @tool()
    def read_note(self, filename: Annotated[str, Param('A note file name such as ideas.md.', min_length=1, max_length=255)]) -> dict:
        """Read one Markdown note by file name from the approved notes folder."""
        content = self.notes().read_text(filename)
        return {'filename': filename, 'content': content[:MAX_RETURN_CHARS],
                'truncated': len(content) > MAX_RETURN_CHARS}

    @tool()
    def search_notes(self, query: Annotated[str, Param('Case-insensitive text to find.', min_length=1, max_length=120)],
                     max_results: Annotated[int, Param(minimum=1, maximum=50)] = 10) -> list[dict]:
        """Search the approved Markdown notes for notes containing every word of the query (any order, case-insensitive) and return short snippets."""
        words = query.casefold().split()
        if not words:
            raise ToolError('query must contain non-space text.')
        notes, matches = self.notes(), []
        for name in notes.files():
            try:
                content = notes.read_text(name)
            except ToolError:
                continue  # unreadable/non-UTF-8 notes are skipped, never fatal to a search
            folded = content.casefold()
            if all(word in folded for word in words):
                index = folded.find(words[0])
                left = max(0, index - 70)
                matches.append({'filename': name, 'snippet': content[left:index + 180][:250]})
                if len(matches) >= max_results:
                    break
        return matches


if __name__ == '__main__':
    sys.exit(NotesConnector.main())
