"""Exercise the MCP tool layer in-process (no transport) — reliable everywhere.

Calls the registered FastMCP tools exactly as a client would, but via
`mcp.call_tool`, which sidesteps OS-specific stdio quirks.

Run:  python examples/tool_demo.py
"""

from __future__ import annotations

import asyncio
import json
import os

os.environ.setdefault("BELIEFGRAPH_DB", ":memory:")

from beliefgraph.mcp_server import mcp  # noqa: E402


def _unwrap(result) -> object:
    # FastMCP.call_tool returns (content_blocks, structured_result).
    if isinstance(result, tuple) and len(result) == 2:
        value = result[1]
    else:
        block = result[0]
        text = getattr(block, "text", None)
        value = json.loads(text) if text else block
    # FastMCP wraps non-dict returns as {"result": ...}
    if isinstance(value, dict) and set(value.keys()) == {"result"}:
        return value["result"]
    return value


async def main() -> None:
    await mcp.call_tool(
        "ingest",
        {"text": "We will use SQLAlchemy for storage. Which vector DB should we pick? "
                 "Maybe security needs a sandbox."},
    )
    print("STATS:", _unwrap(await mcp.call_tool("stats", {})))

    print("\nTOP GAPS:")
    for g in _unwrap(await mcp.call_tool("get_gaps", {"top_k": 6})):
        print(f"  [{g['score']:>5}] {g['kind']:22} {g['description']}")

    print("\nSUGGESTED QUESTIONS:")
    for q in _unwrap(await mcp.call_tool("suggest_questions", {"top_k": 4})):
        print(f"  ({q['kind']}, {q['score']}) {q['question']}")


if __name__ == "__main__":
    asyncio.run(main())
