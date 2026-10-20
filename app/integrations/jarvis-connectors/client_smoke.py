"""Official MCP SDK v2 client smoke test against a connector (needs `pip install -r requirements.txt`).

Usage: python client_smoke.py [connectors/notes/server.py] [--runtime sdk|builtin]
Launches the connector as a stdio subprocess, discovers tools and runs one call.
"""
import asyncio
from pathlib import Path
import sys

from mcp import Client, StdioServerParameters  # SDK v2 API; v1 uses ClientSession instead

HERE = Path(__file__).resolve().parent


async def main(server, runtime):
    parameters = StdioServerParameters(command=sys.executable, args=[str(server), '--runtime', runtime])
    async with Client(parameters) as client:
        names = {tool.name for tool in (await client.list_tools()).tools}
        assert {'list_notes', 'read_note', 'search_notes'} <= names, names
        result = await client.call_tool('search_notes', {'query': 'local connector'})
        if result.is_error:
            raise RuntimeError('MCP tool returned an error: ' + str(result))
        print('PASS: ' + runtime + ' runtime connected, tools discovered, search returned:', result)


if __name__ == '__main__':
    target = Path(next((a for a in sys.argv[1:] if not a.startswith('--')), HERE / 'connectors' / 'notes' / 'server.py'))
    mode = 'builtin' if '--runtime' in sys.argv and sys.argv[sys.argv.index('--runtime') + 1] == 'builtin' else 'sdk'
    asyncio.run(main(target, mode))
