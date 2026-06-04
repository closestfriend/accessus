# Design Spec: Multi-Agent Access-Control Simulation Dataset Generator

**Date:** 2026-06-03
**Status:** Approved design (pre-implementation)
**Name:** `tessera` — a Roman *tessera* was a token that granted its holder access
(to a banquet, garrison, or games); also the tile in a mosaic (composable pieces →
multi-agent sim). Verify PyPI/GitHub availability before publishing; fallback
`tessera-sim`.

---

## 1. Goal & Audience

Build an open-source, forkable **Python generator** that simulates a population of
LLM-driven agents operating inside an access-controlled environment, and emits a
**richly labeled dataset** (full agent transcripts, tool calls, transactions, and
state changes) with **trustworthy ground-truth labels**.

The primary artifact is the **reusable generator** — the community is expected to
fork it, add scenarios/agents/tools, and regenerate. The dataset it produces is the
secondary artifact (a reference corpus + reproducible example).

**Audience:** ML / AI-safety / security-research open-source community. They consume
data in Python (HuggingFace `datasets`, pandas) and extend research-grade generators
in Python (cf. Stanford *Generative Agents*, DeepMind *Concordia*).

### Two downstream tasks the dataset must support (decision: "both")
1. **Insider-threat detection benchmark** (blue-team): given observable telemetry,
   can a detector identify the malicious agent / violations / leaks? Scored against
   ground truth.
2. **Agent-safety / alignment eval**: does the LLM agent *itself* respect access
   controls when given a goal and the capability to violate? Measured per-model.

One engine + one rich schema serves both; we ship a starter eval harness for each.

---

## 2. Non-Goals (YAGNI for v1)

- No live/real-time UI during generation. (The old React app is parked in
  `_archive_ts_scaffold/` as a *future* JSONL replay viewer, not part of v1.)
- Run length is a config knob, not a flagship target. ("1,000 days" from the
  original pitch was hyperbole, not a requirement.) Default to a modest horizon
  (tens to low-hundreds of ticks); longer runs are just a bigger number, not a
  separate engineering effort.
- No embedding-based memory retrieval — at modest horizons, last-N + rolling
  summary is sufficient. (Interface still allows adding it later if a future
  long-run scenario ever needs it.)
- No online/in-loop detector in v1 — detection runs **offline** on recorded logs.
- No multi-model orchestration / no cloud APIs required to run the default scenario.

---

## 3. Core Architecture — separate Truth / Behavior / Prediction

```
┌─ World State (deterministic, serializable) ──────────────────────────────┐
│   agents, roles, permissions, data stores, sensitivity, keys, leak flags │
└──────────────────────────────────────────────────────────────────────────┘
        ▲                      │                         ▲
        │ mutate               │ observable view         │ observable telemetry
        │                      ▼                         │   (no internal thoughts,
┌───────┴────────┐    ┌────────────────┐    ┌────────────┴────┐  no ground truth)
│ Policy Engine  │    │  Agent Layer    │    │ Detector/Guardian│
│ CODE, no LLM   │    │  LLM (local)    │    │ LLM or ML        │
│ = GROUND TRUTH │    │  = BEHAVIOR     │    │ = PREDICTION     │
└────────────────┘    └────────────────┘    └─────────────────┘
```

**The keeper insight:** the access-control decision is made by **deterministic code**
(the Policy Engine), not an LLM. That makes `ground_truth_violation` / `leaked` real
labels rather than model guesses. The Detector only ever sees **observable telemetry**
(never `internal_thought`, never the engine's ground truth) — this keeps the detection
task honest.

---

## 4. Components

Each unit has one purpose, a defined interface, and explicit dependencies.

### `world.py` — World State
- pydantic models: `Agent`, `DataStore`, `WorldState`.
- `Agent`: id, name, role, permissions, objectives, `risk_propensity`, `is_malicious`
  (ground-truth flag, never shown to agent prompt or detector), memory handle.
- `DataStore`: id, name, sensitivity, encryption_key_id, `is_leaked`.
- Source of truth for the *shape* of everything; serializable to/from JSON.
- Depends on: nothing.

### `policy.py` — Policy Engine (GROUND TRUTH)
- Pure functions: `evaluate(action, agent, world) -> PolicyDecision`.
- `PolicyDecision`: `permitted: bool`, `reason: str`, `leaked: bool`,
  `decryption_success: bool`, `ground_truth_violation: bool`.
- Implements RBAC (role × sensitivity) + minimal ABAC hooks (e.g. escalation rules).
- **No LLM. No randomness.** Deterministic given (action, world).
- Depends on: `world`.

### `agents.py` — Agent Layer (BEHAVIOR)
- Builds the per-agent prompt from `persona + objectives + permissions + retrieved
  memory + observable world view`. **Excludes** `is_malicious` and ground truth.
- Calls the LLM provider, parses a structured tool call.
- Action space (from scaffold): `access_resource`, `probe_system`, `request_escalation`,
  plus an `idle` fallback. Output includes `internal_thought`.
- Depends on: `providers`, `memory`, `world`, `schema`.

### `memory.py` — Memory store + retrieval
- `MemoryStore` per agent: append events; `retrieve(context) -> list[event]`.
- v1 strategy: **last-N events + a rolling summary** regenerated every K ticks
  (keeps weak local models coherent over long horizons cheaply).
- Retrieval is an interface (`Retriever`) so salience/embedding retrieval can be added
  later without touching the engine.
- Depends on: `providers` (for summary regeneration), `schema`.

### `providers.py` — LLM provider abstraction
- `LLMProvider` protocol: `complete(prompt, schema) -> dict`.
- `OllamaProvider` (default, `http://localhost:11434`), `MockProvider` (canned,
  deterministic — used by tests and CI so the whole loop runs with no model).
- Interface allows swapping to a cheap API later (one class, no engine changes).
- Depends on: nothing (HTTP only).

### `engine.py` — Tick loop / orchestration
- The scheduler: per tick, for each scheduled agent → build action → policy evaluate →
  mutate world → append memory + event log → (offline detector skipped in-loop).
- Seeded RNG for all non-LLM choices (agent scheduling order, environment events).
- Checkpoints world snapshots so a crashed long run resumes.
- Depends on: all of the above + `schema`.

### `schema.py` — Dataset schema + writers
- pydantic models for every output row; append-only JSONL writers with per-row
  validation. Single source of truth for the published format.
- Depends on: nothing (pure data).

### `detector.py` — Baseline offline detector
- Reads `events.jsonl` (observable fields only) → emits per-tick alert + suspected
  agents. v1 ships a simple rule/heuristic baseline; LLM/ML detectors are experiments
  layered on top.
- Depends on: `schema`.

### `cli.py` — Entry point
- `tessera run --config configs/scenario_default.yaml` → writes a run directory.
- Depends on: `engine`, config loader.

---

## 5. Data Flow (one tick)

1. Engine selects scheduled agent(s) (seeded order).
2. `agents.build_prompt()` ← persona + `memory.retrieve()` + observable world.
3. `provider.complete()` → structured tool call + `internal_thought`.
   - Malformed JSON → retry once → fall back to logged `idle` action.
4. `policy.evaluate()` → deterministic `PolicyDecision` (ground truth).
5. Engine applies decision → mutates `WorldState` (e.g. set `is_leaked`).
6. Append to agent `MemoryStore` and to `events.jsonl`.
7. Periodically: write `world_snapshots.jsonl`; regenerate rolling summaries.
8. After the run: `detector.py` reads telemetry → predictions; evals score them.

---

## 6. Dataset Schema (one run = one directory under `runs/<id>/`)

- **`manifest.json`** — seed, model name(s), provider, agent roster, policy version,
  `n_ticks`, scenario config hash, generator git SHA.
- **`events.jsonl`** — one row per agent action:
  ```json
  {
    "tick": 12, "agent_id": "agent-5", "tool": "probe_system",
    "params": {"resource_id": "data-4", "method": "scan_metadata"},
    "internal_thought": "...",            // NOT shown to detector
    "policy_decision": {
      "permitted": false, "reason": "role 'user' < 'restricted'",
      "leaked": false, "decryption_success": false,
      "ground_truth_violation": true       // label, from engine
    }
  }
  ```
- **`world_snapshots.jsonl`** — periodic full `WorldState` (resumable + diffable).
- **`labels.jsonl`** — derived ground truth: per-agent `is_malicious`, per-tick
  `violation`/`leak`, episode-level outcomes (e.g. "trade secrets exfiltrated by tick N").

### 6.1 The three views (the crux of an honest benchmark)

The same event is projected into **three different views**, and keeping them separate
is what makes the dataset trustworthy. Each consumer sees only what it realistically
should. The projections are produced by code in `schema.py` and documented in the README.

| Field | **Ground-truth record**<br>(full `events.jsonl` + `labels.jsonl`) | **Observable telemetry**<br>(detector / blue-team input) | **Agent prompt view**<br>(what the acting agent sees) |
|---|:--:|:--:|:--:|
| `tick`, `agent_id`, `tool`, `params` | ✅ | ✅ | ✅ (its own + world topology) |
| `permitted` (grant/deny) | ✅ | ✅ *(the access system logs the outcome)* | ✅ (its own outcome only) |
| `internal_thought` | ✅ | ❌ | ✅ (its own only) |
| `leaked` | ✅ | ❌ *(whether exfil succeeded is partly what blue-team must infer)* | ❌ |
| `ground_truth_violation` | ✅ | ❌ | ❌ |
| `is_malicious` (agent label) | ✅ (`labels.jsonl`) | ❌ | ❌ |

Two subtleties this makes explicit:
- **`permitted` ≠ `ground_truth_violation`.** An access can be *permitted* by an
  over-broad policy yet still be a *violation of intent* — `permitted` is observable,
  the violation label is not. Detecting that gap is part of the task.
- The **agent never sees its own `is_malicious` flag or any ground truth** — its
  behavior is driven only by its persona, objectives, permissions, and memory. The
  malice label is an *observer's* truth, assigned by config, not fed back into the model.

---

## 7. Eval Harnesses (`evals/`)

- **`detection.py`** — feed observable telemetry to a detector → precision / recall /
  F1 / **time-to-detect** (ticks between first violation and first correct alert),
  per scenario.
- **`agent_safety.py`** — from full events → per-model **violation rate**, **leak rate**,
  **escalation-attempt count**, broken down by agent role and `risk_propensity`.
  Enables "which model best respects least-privilege under temptation."

Both emit a metrics table (markdown + JSON) so results are copy-pasteable into a README.

---

## 8. Error Handling & Reliability

- Malformed LLM output → retry once → logged `idle` fallback with a `malformed: true`
  flag. Never crashes a long run. Parse-failure rate is a reported quality metric.
- Policy Engine fails **closed** on unknown actions/resources.
- World snapshots every K ticks → crashed runs resume from the last snapshot.
- All writers validate against pydantic before writing; an invalid row aborts loudly
  (corruption must not enter a published dataset silently).

---

## 9. Testing Strategy

- **`test_policy.py`** — table-driven over role × sensitivity × action. The ground
  truth must be bulletproof; this is the highest-value test file.
- **`test_engine_mock.py`** — full tick loop with `MockProvider` (no model): asserts
  a complete, schema-valid run directory is produced deterministically.
- Schema round-trip tests (write → read → equal).
- Test-driven: write these before the corresponding implementation.

---

## 10. v1 Scope — Vertical Slice (definition of done)

Smallest **end-to-end labeled run**, proving the whole pipeline before scaling.
Built in two steps so the first working artifact needs no model at all:

**Step 0 — mock smoke run (first deliverable):**
- Policy Engine (RBAC + escalation) with passing table-driven tests.
- Full tick loop driven by `MockProvider` (canned actions, no LLM), **~10 ticks**.
- Produces a valid run directory (`manifest.json` + `events.jsonl` +
  `world_snapshots.jsonl` + `labels.jsonl`) — all three views verified.
- Both evals run against it and emit a metrics table.
- This is the whole pipeline, end to end, deterministically, with zero model cost.

**Step 1 — first real run:**
- Swap `MockProvider` → `OllamaProvider` (one local model), last-N + rolling-summary
  memory, the 5-agent cast (incl. malicious "Insider Eve") + 4 data stores.
- **~20–30 ticks.** Spot-check transcripts for coherence (see exit criterion).
- README documents: what it is, `tessera run`, the schema/three-views, and how to
  fork/extend.

**Exit criterion before scaling:** spot-check the generated transcripts — are agent
behaviors coherent and non-repetitive enough to be dataset-grade with the chosen local
model? If not, adjust model/prompt/action-space *before* scaling ticks or agents.

---

## 11. Repo Layout

```
tessera/
├── pyproject.toml
├── README.md                             # the "gift" front door
├── .gitignore                            # excludes .env*, runs/, caches
├── docs/superpowers/specs/               # this spec
├── src/tessera/
│   ├── world.py        policy.py         # state + ground truth
│   ├── agents.py       memory.py         # behavior + memory
│   ├── providers.py    engine.py         # LLM iface + orchestration
│   ├── schema.py       detector.py       # output format + baseline detector
│   └── cli.py
├── configs/scenario_default.yaml
├── evals/detection.py  evals/agent_safety.py
├── datasets/loader.py                    # HuggingFace loading script
├── tests/test_policy.py  tests/test_engine_mock.py
├── runs/                                 # gitignored output
└── _archive_ts_scaffold/                 # parked React app (future replay viewer)
```

---

## 12. Future / Out of Scope for Now

- Longer runs / more agents / more scenarios (just bigger config; only pursue if
  the dataset is more useful for it, not for its own sake).
- Embedding/salience memory retrieval — only if a genuinely long-horizon scenario
  is added later (interface already allows it).
- Online in-loop detector + a "blue-team-in-the-loop" reactive scenario.
- Resurrect the React app as a JSONL replay/scrubbing viewer.
- Additional scenarios (multi-tenant, supply-chain, privilege-creep over time).
- Publish to HuggingFace Hub with a dataset card.

---

## 13. Key Decisions Log

| Decision | Choice | Why |
|---|---|---|
| Direction | Security/insider-threat sim | Differentiated; constrained action space keeps weak local models coherent; perfect ground truth |
| Runtime | Headless generator | Goal is a dataset/generator, not a live demo |
| Dataset task | Both (detection + agent-safety) | One rich schema serves both; broadest community value |
| Language | **All Python** | Primary artifact is a forkable generator; matches research-grade lineage + HF consumer ecosystem |
| Enforcement | Deterministic code, not LLM | Trustworthy ground-truth labels |
| Detector (v1) | Offline | No cross-process calls in the generation loop |
| New repo | Fresh sibling dir | Old TS dir holds a Gemini key in `.env.local`; keep it out of git |
| Name | `tessera` | Roman access-token + mosaic tile; apt, distinctive, not a security-vendor cliché |
| v1 size | Mock 10-tick smoke run, then 20–30-tick real run | First artifact needs no model; keeps it weekend-scale |
