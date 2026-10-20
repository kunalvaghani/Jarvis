"""Owned test-only MCP child: record a single fixture write, then disconnect."""
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'integrations/jarvis-connectors'))
from jarvis_connector import BaseConnector, tool


class Fixture(BaseConnector):
    name='spotify-disconnect-fixture'
    @classmethod
    def add_arguments(cls, parser):
        parser.add_argument('--marker',required=True)
    def configure(self, options):
        self.marker=Path(options.marker)
    @tool(access='write', idempotent=False)
    def write_once(self) -> dict:
        """Write one owned fixture marker, then disconnect before acknowledging."""
        with self.marker.open('a',encoding='ascii') as out:out.write('attempt\n')
        os._exit(9)
    @tool()
    def health(self) -> dict:
        """Read-only fixture health."""
        return {'ok':True}


if __name__=='__main__':Fixture.main()
