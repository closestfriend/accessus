# Accessus

> *Accessus* is Latin for **the act of approaching, or being granted entry** —
> admittance. Accessus the tool simulates LLM agents inside an access-controlled
> world and publishes a richly labeled dataset of who tried to reach what, what
> the rules allowed, and what actually leaked.

Accessus generates open datasets for two research tasks at once:
1. **Insider-threat detection**: can a detector spot the malicious agent from observable telemetry?
2. **Agent-safety / alignment**: does an LLM agent itself respect access controls under temptation?

The key to honest labels: the access decision is made by a **deterministic policy
engine** (ground truth), never by an LLM. Detectors only ever see the **observable
telemetry** view: never agents' internal thoughts or the ground-truth labels.

## Install

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
```

The import name and CLI are both `accessus`.

## Run

```bash
# Deterministic mock run, no model needed:
.venv/bin/accessus run --provider mock --ticks 10 --observable --out runs/demo

# Real run with a local Ollama model:
ollama pull llama3.1:8b
.venv/bin/accessus run --provider ollama --ticks 25 --out runs/real

# Or sweep any model family via OpenRouter. Pass a current OpenRouter id with
# --model (overrides the scenario's `model:`); browse ids at openrouter.ai/models.
# NOTE: pick a model that will actually roleplay the malicious insider. Heavily
# safety-tuned models (e.g. gpt-5-mini, claude-haiku/sonnet) refuse and idle,
# yielding degenerate datasets with no attack signal. Less refusal-prone models
# (deepseek, qwen, gemini, essentialai) work better:
export OPENROUTER_API_KEY=sk-or-...
.venv/bin/accessus run --provider openrouter --model deepseek/deepseek-v4-flash --ticks 25 --out runs/real

# Score it:
.venv/bin/python -m accessus.evals.detection runs/real
.venv/bin/python -m accessus.evals.agent_safety runs/real
.venv/bin/python -m accessus.evals.quality runs/real
```

A published corpus lives under `datasets/` (see `datasets/v1_2026-06-11/DATASET.md`).

## Dataset layout (one run = one directory)

| File | Contents |
|---|---|
| `manifest.json` | seed, model, provider, tick count, agent roster, policy version |
| `events.jsonl` | full record: tool call, internal thought, policy decision (ground truth) |
| `observable.jsonl` | the detector's view: no thoughts, no ground truth |
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
`accessus/schema.py` and the matching branch in `accessus/policy.py`. Ground-truth
rules live in `policy.py`; agent behavior is entirely model-driven via `agents.py`.

## License

MIT (see LICENSE).
