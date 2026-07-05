# belief-graph

An **epistemic belief graph** with **knowledge-gap detection**, exposed over **MCP**.

Unlike plain GraphRAG (which stores entities + relations extracted from text), this
stores *beliefs*: typed claims carrying **epistemic metadata** — `status`
(proposed / assumed / confirmed / locked / rejected / contradicted / stale),
`confidence`, provenance, and typed relationships. That metadata is what lets an
agent ask **"what don't I know that matters?"** and drive an informed conversation.

Built to power a self-driving scoping loop:

```
user turn ─▶ ingest() ─▶ recompute gaps ─▶ get_gaps()/suggest_questions()
   ▲                                                      │
   └───────────────  agent asks the top-ranked question  ◀┘
```

## Why this design

- **The gap engine is the product; the graph engine is a commodity.** All retrieval
  goes through a small `IGraphStore` interface, so the backend is swappable.
- **An append-only SQLite event log is the source of truth.** The graph store is a
  *derived projection* — fully auditable, time-travelable, and rebuildable from
  scratch (any backend, any time).
- **Engine-agnostic.** Ships with a zero-dependency local backend (NetworkX +
  tf-idf retrieval + PageRank centrality) and an experimental **Graphiti** backend
  (temporally-aware graph whose edge invalidation ≈ belief revision) using its
  embedded **Kùzu** driver — no Neo4j/Docker required.

## Architecture

```
                    ┌───────────────────────────────┐
   MCP client  ───▶ │  mcp_server (FastMCP, stdio)   │
 (Devin/Claude)     └───────────────┬───────────────┘
                                    ▼
                       ┌────────────────────────┐
                       │   BeliefGraphService    │  ingest / gaps / query / status
                       └───┬───────────┬─────────┘
                           ▼           ▼
              ┌────────────────┐   ┌──────────────────────┐
              │  EventLog       │   │  gaps engine          │
              │  (SQLite, SoT)  │   │  coverage/confidence/ │
              └───────┬─────────┘   │  structural/contra    │
                      │  project()  └──────────────────────┘
                      ▼
              ┌───────────────────────────────┐
              │  IGraphStore  (swappable)      │
              │  • LocalGraphStore (default)   │
              │  • GraphitiGraphStore (Kùzu)   │
              └───────────────────────────────┘
```

## Gap detection

`get_gaps` ranks gaps by **impact × uncertainty**:

| Kind | Fires when |
|------|-----------|
| `coverage` | an ontology topic has no *confirmed* belief |
| `confidence` | a central belief is still assumed / low-confidence |
| `missing_rationale` | a `decision` has no `derived_from` link |
| `unanswered_question` | an `open_question` has no incoming `answers` edge |
| `requirement_unaddressed` | a `requirement` has no decision addressing it |
| `contradiction` | two live beliefs are linked by `contradicts` |

Coverage is measured against a seed **ontology** (`ontology.py`) of topics a software
project usually must decide (runtime, storage, vectors, security, UI, testing, …).
Supply your own via the `ontology=` arg or the `add_topic` tool.

## Install

```bash
pip install -e .                    # core (local backend, no keys needed)
pip install -e ".[gemini]"          # + Gemini LLM belief extraction
pip install -e ".[graphiti,gemini]" # + Graphiti/Kùzu backend
pip install -e ".[dev]"             # + pytest
```

## Try it

```bash
python examples/seed_taproot.py   # seed locked decisions -> print gaps + questions
python examples/tool_demo.py      # exercise the MCP tools in-process
pytest -q                         # 11 tests, no external deps
```

## MCP tools

| Tool | Purpose |
|------|---------|
| `ingest(text, actor, turn_id)` | extract beliefs from a message, merge, auto-link answers |
| `get_gaps(top_k, kind)` | ranked knowledge gaps |
| `suggest_questions(top_k)` | top gaps phrased as questions to ask next |
| `query(text, top_k)` | retrieve most relevant beliefs |
| `add_belief(...)` / `add_edge(...)` | explicit graph edits |
| `set_status(belief_id, status, confidence)` | confirm / lock / reject a belief |
| `get_contradictions()` | live contradictions to resolve |
| `get_belief(belief_id)` | a belief + its neighbors |
| `stats()` | summary counts |

## Configuration (env)

| Var | Default | Meaning |
|-----|---------|---------|
| `BELIEFGRAPH_DB` | `belief_graph.db` | SQLite event-log path (`:memory:` for ephemeral) |
| `BELIEFGRAPH_BACKEND` | `local` | `local` or `graphiti` |
| `GEMINI_API_KEY` | – | enables LLM extraction; else deterministic rule-based fallback |

## Registering as an MCP server

**Devin** (org settings → MCP integrations) and **Claude Desktop**
(`claude_desktop_config.json`) use the same shape:

```json
{
  "mcpServers": {
    "belief-graph": {
      "command": "belief-graph-mcp",
      "env": {
        "BELIEFGRAPH_DB": "C:/path/to/belief_graph.db",
        "GEMINI_API_KEY": "..."
      }
    }
  }
}
```

(`belief-graph-mcp` is installed as a console script; or use
`python -m beliefgraph.mcp_server`.)

## Status & roadmap

- ✅ Local backend, event log, gap engine, MCP server, rule-based + Gemini extraction.
- 🧪 Graphiti/Kùzu backend is written but untested in CI (needs a key + native deps).
- ⏭️ Embedding-based retrieval + dedup, LLM-inferred contradiction/support edges,
  confidence decay, per-turn debounce/batching.

> Note: the stdio smoke test (`examples/mcp_smoke.py`) exercises the real transport
> but tool calls can block during teardown on Windows due to an `anyio` stdio quirk;
> `examples/tool_demo.py` verifies the tool layer reliably on all platforms.
