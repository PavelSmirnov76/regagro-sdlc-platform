"""End-to-end smoke check: launch the MCP server over stdio and call some tools.

Run from the ``mcp/`` directory::

    uv run python scripts/smoke.py

It connects as a real MCP client, lists the tools, and calls two read-only ones
(``allocate_id`` and ``validate_tree``) against the configured ``sdlc/`` tree.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main() -> None:
    # The engine is project-agnostic; smoke it against the bundled example tree
    # unless the caller already pointed SDLC_ROOT at a real project.
    repo = Path(__file__).resolve().parents[2]
    env = dict(os.environ)
    env.setdefault("SDLC_ROOT", str(repo / "examples" / "mini-sdlc"))
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "sdlc_mcp.server"],
        env=env,
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print(f"tools ({len(tools.tools)}):", ", ".join(t.name for t in tools.tools))

            prompts = await session.list_prompts()
            print("prompts:", ", ".join(p.name for p in prompts.prompts))

            alloc = await session.call_tool("allocate_id", {"artifact_type": "BT"})
            print("allocate_id BT ->", alloc.content[0].text)

            val = await session.call_tool("validate_tree", {})
            print("validate_tree ->", val.content[0].text[:200])


if __name__ == "__main__":
    asyncio.run(main())
