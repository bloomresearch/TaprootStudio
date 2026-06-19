# Taproot Studio — Phase 1 Plan (Foundation)

**Goal of Phase 1:** stand up the skeleton that makes everything else parallelizable —
the monorepo, the Electron shell hosting the existing IDE, an auto-spawned Python daemon
with a stable client contract, and the *thinnest possible* end-to-end path: open the app,
flip to the Agent Manager, run a one-node "agent" flow through the daemon against a provider,
and see streamed output.

Phase 1 is **not** about feature completeness. It is about de-risking the two scariest items
(Python-in-Electron packaging, React/React-Flow consolidation) and locking the contracts
(daemon API, data schema) that let the work split cleanly afterward.

> **Important head start:** the Geminode backend already ships a working **Python daemon foundation** at
> `packages/geminode-studio/backend` — a **FastAPI** server (`/workflow/execute`, `/workflow/resume`,
> `/workflow/models`, file upload, system-prompt/UI generation) over an **async `flowcore` engine**
> (work-queue traversal, multi-input joins, back-edge loops, UI pause/resume) with a `pytest` suite.
> It is **Gemini-only** and **stateless** (flows = JSON; no SQLAlchemy/vectors). So Phase 1 *adopts and
> extends* this rather than building the daemon/engine from scratch.

---

## Definition of Done (Phase 1)
- `pnpm`/workspace monorepo builds; `apps/desktop` (Electron) and `apps/daemon` (Python) both run.
- Electron launches → auto-spawns the daemon → health-check passes → graceful shutdown.
- Reaction Studio IDE renders inside the new shell (open project, file tree, Monaco, preview).
- Geminode flow editor renders inside a **flip** surface (Agent Manager), on the **consolidated**
  React + React Flow versions.
- Daemon exposes a versioned HTTP/WS API; a single-agent flow executes end-to-end against the
  **Gemini-first** provider layer and **streams** step output back to the UI.
- SQLAlchemy data layer with initial schema + migrations; flows persist in the daemon and are
  **linked** to a project (no file copy).
- CI runs lint + type-check + unit tests for both apps.

---

## Independent Work Streams

Streams are designed to **not collide** (separate directories / ownership). The only hard
ordering is the **Stream 0 contracts**, which must land first; after that, A–E proceed in parallel.

### Stream 0 — Contracts & Scaffolding *(must land first; small, blocking)*
Owner: lead. Everything else forks from here.
- [ ] Establish monorepo layout: `apps/desktop` (from `reaction-studio`), `apps/daemon` (Python),
      `packages/flow-editor` (from `geminode-studio` editor), `packages/ui` (shared neumorphic),
      `packages/shared-types`.
- [ ] Choose + configure JS workspace manager (pnpm recommended) and Python project (`uv`/Poetry).
- [ ] **Define the daemon API contract** (OpenAPI + WS event schema) and shared TS/Python types —
      run lifecycle, streaming step events, flow CRUD, provider config. **Start from the existing
      `backend/server/api` endpoints + the engine's emitted event types** (`step_start`,
      `thought_update`, `step_output`, `ui_pause`, `error`) rather than inventing from scratch.
- [ ] Relocate/adopt `packages/geminode-studio/backend` as the basis of `apps/daemon`.
- [ ] **Define the initial DB schema** (Section 6 of the vision) as the SQLAlchemy source of truth.
- [ ] CI pipeline skeleton (lint, type-check, tests for both apps).

> Deliverable: merged contracts. After this, A–E are independent.

### Stream A — Python Daemon Packaging & Lifecycle *(highest risk — start immediately)*
Files: `apps/daemon/**`, Electron main spawn logic.
- [ ] Take the **existing FastAPI server** (`backend/server`) as the daemon; add WS streaming + a
      versioned API surface per the Stream 0 contract (the SSE/event types already exist).
- [ ] Cross-platform interpreter strategy (embeddable Python / PyInstaller / `uv`) + bundling.
- [ ] Electron main: spawn daemon on launch, health-check, restart-on-crash, clean shutdown.
- [ ] Local-only binding + handshake/auth token between Electron and daemon.
- *Touches:* daemon dir + a narrow slice of Electron main. No overlap with renderer streams.

### Stream B — Electron Shell Adoption *(IDE backbone)*
Files: `apps/desktop/**` (renderer shell, excluding flow editor).
- [ ] Bring Reaction Studio in as `apps/desktop`; verify Electron build, `project-manager`,
      FileTree, Monaco, LiveCanvas preview (`component-server` plugin), Inspector all work.
- [ ] Carve out the **Agent Manager** region + the **flip** interaction shell (empty container
      that Stream C fills).
- [ ] Promote the neumorphic design system into `packages/ui` for reuse.
- *Touches:* desktop renderer chrome. No overlap with daemon or editor internals.

### Stream C — Flow Editor Port & React Consolidation
Files: `packages/flow-editor/**`.
- [ ] Extract Geminode's `@xyflow/react` editor (nodes, edges, NodeEditor) into `packages/flow-editor`.
- [ ] **Consolidate to one React version** (the shell's) and **one React Flow** (drop `reactflow@11`,
      standardize on `@xyflow/react`).
- [ ] Render the editor inside Stream B's flip surface with mock data (no daemon dependency yet).
- *Touches:* editor package only. Integrates with B via a stable prop interface.

### Stream D — Flow Execution Engine (Python) + Provider Layer
Files: `apps/daemon/flowcore/**`, `apps/daemon/providers/**`.
- [ ] **Adopt the existing `flowcore` engine** (do *not* re-port); keep its async work-queue, joins,
      back-edge loops, and UI pause/resume. Preserve the existing `pytest` suite as a regression net.
- [ ] **Extract a provider abstraction** behind the current Gemini node: one interface + **Gemini
      adapter** (OpenAI/Anthropic/Ollama stubbed). The node currently hard-binds `google-genai`.
- [ ] Wire step events over WS per the Stream 0 schema; run a single-agent flow end-to-end.
- *Touches:* daemon engine/providers. Depends on Stream 0 contract + Stream A server skeleton.
- *Note:* true **parallel fan-out**, **per-port async opt-in**, and a first-class **Loop node** are
  desired but **deferred to Phase 2+** (the engine is single-active-node today and that's fine for the
  Phase 1 end-to-end goal).

### Stream E — Data Layer (SQLAlchemy) + Flow Persistence
Files: `apps/daemon/db/**`.
- [ ] SQLAlchemy models for the Section 6 schema; SQLite default; migration tooling (Alembic).
- [ ] Flow CRUD + `PROJECT_FLOW_LINK` (enable/import-by-reference) endpoints.
- [ ] Import the existing `packages/geminode-studio/flows/*.json` presets as a smoke test (replacing
      the current stateless JSON-file loading path with the SQLAlchemy-backed store).
- *Touches:* daemon db package. Depends on Stream 0 schema.

---

## Dependency Graph

```mermaid
flowchart LR
    S0["Stream 0<br/>Contracts & Scaffolding"] --> A["A: Daemon Packaging & Lifecycle"]
    S0 --> B["B: Electron Shell Adoption"]
    S0 --> C["C: Flow Editor Port + React Consolidation"]
    S0 --> D["D: Execution Engine + Providers"]
    S0 --> E["E: Data Layer (SQLAlchemy)"]
    A --> INT["Integration:<br/>end-to-end single-agent run"]
    B --> INT
    C --> INT
    D --> INT
    E --> INT
```

---

## Explicitly Deferred to Phase 2+
- **Parallel branch execution** (concurrent `asyncio.gather` of ready nodes), **per-node/per-port
  async opt-in**, and a first-class **Loop node**.
- **Diff node** + composable human-in-the-loop approval gates (built on the existing `ui_interactive`
  pause/resume).
- The **Project Board** surface (projects/milestones/sprints/issues/blocking, live agent status,
  kanban + flow-graph layouts).
- The **5-surface swap-rotation workspace** + 3D mini-compass (Phase 1 can ship a single surface +
  the flip interaction).
- ECP engine (meta-RAG tool selection) and tool scenario embeddings.
- Custom Tool Builder panel (UI config + Python editor) and the built-in tool catalog.
- Agent node **states** (state machine + dynamic transition handles).
- RAG nodes + user-registered data sources.
- Per-tool subprocess/venv sandbox runtime (beyond a basic stub).
- Live mode / TTS / streaming audio re-homing.
- Non-Gemini provider adapters beyond stubs.

---

## Suggested First Two Weeks
1. Land **Stream 0** (contracts + scaffolding) — unblocks everyone.
2. In parallel, spike **Stream A** (Python-in-Electron) and **Stream C** (React consolidation) —
   the two highest-risk items. If either reveals a blocker, the plan adapts before broad work starts.
