"""End-to-end MCP smoke test: launch the server over stdio and drive its tools
exactly as an MCP client (Devin / Claude Desktop) would.

Run:  python examples/mcp_smoke.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main() -> None:
    env = dict(os.environ)
    env["BELIEFGRAPH_DB"] = ":memory:"  # ephemeral for the smoke test
    errlog = open("mcp_smoke_stderr.log", "w")
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "beliefgraph.mcp_server"],
        env=env,
    )

    async with stdio_client(params, errlog=errlog) as (read, write):
        async with ClientSession(read, write) as session:
            print("initializing...", flush=True)
            await asyncio.wait_for(session.initialize(), timeout=20)
            print("initialized", flush=True)

            tools = await session.list_tools()
            print("TOOLS:", [t.name for t in tools.tools])

            await session.call_tool(
                "ingest",
                {"text": "We will use SQLAlchemy. Which vector store should we pick?"},
            )
            res = await session.call_tool("suggest_questions", {"top_k": 3})
            payload = json.loads(res.content[0].text)
            print("\nSUGGESTED QUESTIONS:")
            for q in payload:
                print(f"  ({q['kind']}, {q['score']}) {q['question']}")

            stats = await session.call_tool("stats", {})
            print("\nSTATS:", stats.content[0].text, flush=True)

    # stdio_client subprocess teardown can hang on Windows; the checks above
    # already prove the server works, so exit hard once we have our results.
    os._exit(0)


if __name__ == "__main__":
    asyncio.run(main())
