#!/usr/bin/env python
"""Reproducible generator for Accessus dataset v1 (2026-06-11).

Sweeps the default scenario across 4 non-refusing generator models x 3 seeds
x 25 ticks, writing one labeled run directory per (model, seed) plus a
_summary.json with per-run quality/detection metrics.

Run from repo root (with accessus installed editable: `pip install -e .`):

    .venv/bin/python datasets/v1_2026-06-11/generate.py
"""
from __future__ import annotations

import json
from pathlib import Path

from accessus.cli import build_provider
from accessus.config import load_scenario
from accessus.engine import run
from accessus.evals.detection import detect_and_score
from accessus.evals.agent_safety import score_agent_safety
from accessus.evals.quality import compute_quality

OUT_ROOT = Path("datasets/v1_2026-06-11")
SCENARIO = Path("configs/scenario_default.yaml")
TICKS = 25
SEEDS = [42, 43, 44]
# (OpenRouter id, dir slug) — all verified non-refusing generators on 2026-06-11.
# NOTE: v1 shipped only deepseek (3 seeds) + rnj-1 (3 seeds) + qwen3.5-flash (2 seeds);
# qwen3.5-flash runs ~75 min/run (heavy reasoning tokens) so generation was cut short
# before gemini. Drop qwen3.5-flash for bulk runs; gemini is kept here for v1.1.
MODELS = [
    ("deepseek/deepseek-v4-flash", "deepseek-v4-flash"),
    ("essentialai/rnj-1-instruct", "rnj-1"),
    ("qwen/qwen3.5-flash-02-23", "qwen3.5-flash"),
    ("google/gemini-2.5-flash-lite", "gemini-flash-lite"),
]


def main() -> None:
    summary = []
    for model_id, slug in MODELS:
        for seed in SEEDS:
            cfg = load_scenario(SCENARIO).model_copy(update={"seed": seed})
            provider = build_provider("openrouter", cfg, model=model_id)
            out_dir = OUT_ROOT / f"{slug}_seed{seed}"
            print(f">>> {model_id}  seed={seed} -> {out_dir}", flush=True)
            try:
                run(cfg, provider, out_dir=out_dir, n_ticks=TICKS, write_observable=True)
            except Exception as e:  # one bad run shouldn't abort the sweep
                print(f"    FAILED: {e!r}", flush=True)
                summary.append({"model": model_id, "seed": seed, "error": repr(e)})
                continue

            events = [json.loads(x) for x in (out_dir / "events.jsonl").read_text().splitlines()]
            saf = score_agent_safety(out_dir)
            det = detect_and_score(out_dir)
            q = compute_quality(out_dir)
            row = {
                "model": model_id,
                "seed": seed,
                "dir": out_dir.name,
                "events": len(events),
                "refused": sum(e["refused"] for e in events),
                "malformed": sum(e["malformed"] for e in events),
                "violations": sum(r.violations for r in saf),
                "leaks": sum(r.leaks for r in saf),
                "escalations": sum(r.escalation_attempts for r in saf),
                "detection_f1": round(det.f1, 3),
                "detection_recall": round(det.recall, 3),
                "behavioral_divergence": round(q.behavioral_divergence, 3),
                "quality_passed": q.passed,
            }
            summary.append(row)
            print(f"    {row}", flush=True)

    (OUT_ROOT / "_summary.json").write_text(json.dumps(summary, indent=2))
    print(f"\nWrote {OUT_ROOT/'_summary.json'} ({len(summary)} runs)", flush=True)


if __name__ == "__main__":
    main()
