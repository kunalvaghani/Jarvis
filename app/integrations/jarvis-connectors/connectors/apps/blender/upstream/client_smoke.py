"""Real MCP stdio discovery; supports MCP SDK 2 Client or v1 ClientSession."""
import asyncio
import sys
from pathlib import Path
from blender_connector.catalog import ACTIONS

async def main():
    from mcp import StdioServerParameters
    params=StdioServerParameters(command=sys.executable,args=[str(Path(__file__).parent/'server.py')])
    try:
        from mcp import Client
    except ImportError:
        from mcp.client.stdio import stdio_client
        from mcp import ClientSession
        async with stdio_client(params) as (read,write):
            async with ClientSession(read,write) as session:
                await session.initialize()
                result=await session.list_tools()
                names={x.name for x in result.tools}
    else:
        async with Client(params) as client:
            result=await client.list_tools()
            names={x.name for x in result.tools}
    expected={'blender_'+name for name in ACTIONS}|{'blender_bridge_health','blender_wait_job','blender_job_status'}
    missing=expected-names
    if missing:raise RuntimeError(f'Missing tools: {sorted(missing)}')
    print(f'PASS: {len(expected)} Blender MCP tools discovered via stdio.')

if __name__=='__main__':asyncio.run(main())
