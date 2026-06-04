# Tessera

> A *tessera* was a Roman token that granted its holder access — to a banquet, a
> garrison, the games. Tessera the tool simulates LLM agents inside an
> access-controlled world and publishes a richly labeled dataset of who tried to
> reach what, what the rules allowed, and what actually leaked.

Tessera generates open datasets for two research tasks at once:
1. **Insider-threat detection** — can a detector spot the malicious agent from observable telemetry?
2. **Agent-safety / alignment** — does an LLM agent itself respect access controls under temptation?

The key to honest labels: the access decision is made by a **deterministic policy
engine** (ground truth), never by an LLM. Detectors only ever see the **observable
telemetry** view — never agents' internal thoughts or the ground-truth labels.

## Install

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
```

## Run

```bash
# No model needed — deterministic mock run:
.venv/bin/tessera run --provider mock --ticks 10 --observable --out runs/demo

# Real run with a local Ollama model:
ollama pull llama3.1:8b
.venv/bin/tessera run --provider ollama --ticks 25 --out runs/real

# Score it:
.venv/bin/python -m evals.detection runs/real
.venv/bin/python -m evals.agent_safety runs/real
.venv/bin/python -m evals.quality runs/real
```

## Dataset layout (one run = one directory)

| File | Contents |
|---|---|
| `manifest.json` | seed, model, provider, tick count, agent roster, policy version |
| `events.jsonl` | full record: tool call, internal thought, policy decision (ground truth) |
| `observable.jsonl` | the detector's view — no thoughts, no ground truth |
| `labels.jsonl` | derived ground-truth labels per action |
| `world_snapshots.jsonl` | periodic full world state |

## The three views

| Field | events.jsonl | observable.jsonl | agent prompt |
|---|:--:|:--:|:--:|
| tool / params / permitted | yes | yes | yes (own) |
| internal_thought | yes | no | yes (own) |
| leaked / ground_truth_violation | yes | no | no |
| is_malicious | labels.jsonl | no | no |

## Extending

Add a scenario YAML under `configs/`, or a new tool by extending `Tool` in
`schema.py` and the matching branch in `policy.py`. Ground-truth rules live in
`policy.py`; agent behavior is entirely model-driven via `agents.py`.

## License

MIT (see LICENSE).
