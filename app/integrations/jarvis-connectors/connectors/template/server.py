"""Template for a new Jarvis connector. Copy this folder, rename the class and tools.

Checklist for a new child:
1. Set a unique ``name``; give every tool a docstring and typed parameters.
2. Bound inputs with ``Param`` and keep results small (``max_result_chars``).
3. Reach files only through ``ConfinedRoot``; reach apps through their own API.
4. Mark tools that change anything ``access='write'``; they stay hidden unless
   the connector is launched with ``--allow-write``. Verify the postcondition
   (read back what you wrote) and refuse to overwrite unless that is the job.
5. Raise ``ToolError`` for expected failures; never print to stdout.
"""
from pathlib import Path
import platform
import sys
from typing import Annotated

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # the jarvis-connectors folder
from jarvis_connector import BaseConnector, ConfinedRoot, Param, ToolError, tool  # noqa: E402


class ExampleConnector(BaseConnector):
    """Example connector: one read tool and one opt-in write tool."""
    name = 'jarvis-example'
    version = '0.1.0'

    @classmethod
    def add_arguments(cls, parser):
        parser.add_argument('--workspace', default='', help='Absolute folder the write example may create files in.')

    def configure(self, options):
        self.workspace = options.workspace

    @tool()
    def get_system_name(self) -> str:
        """Return this computer's name and operating system."""
        return platform.node() + ' (' + platform.system() + ' ' + platform.release() + ')'

    @tool()
    def add_numbers(self, a: float, b: float) -> float:
        """Add two numbers."""
        return a + b

    @tool(access='write')
    def create_text_file(self, filename: Annotated[str, Param('New .txt file name.', min_length=5, max_length=100)],
                         text: Annotated[str, Param(max_length=20000)]) -> dict:
        """Create a new .txt file in the approved workspace. Never overwrites an existing file."""
        folder = ConfinedRoot(self.workspace, {'.txt'})
        folder.path_for_new(filename).write_text(text, encoding='utf-8')  # refuses existing names
        written = folder.read_text(filename)  # postcondition: read back what was written
        if written != text:
            raise ToolError('Wrote ' + filename + ' but the read-back did not match; inspect it before retrying.')
        return {'filename': filename, 'characters': len(written)}


if __name__ == '__main__':
    sys.exit(ExampleConnector.main())
