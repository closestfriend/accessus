# src/tessera/cli.py
from __future__ import annotations

import argparse
from pathlib import Path

from tessera.config import load_scenario
from tessera.engine import run
from tessera.providers import MockProvider, OllamaProvider


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tessera")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="run a simulation and write a labeled dataset")
    run_p.add_argument("--config", type=Path, default=Path("configs/scenario_default.yaml"))
    run_p.add_argument("--out", type=Path, default=Path("runs/latest"))
    run_p.add_argument("--provider", choices=["mock", "ollama"], default="ollama")
    run_p.add_argument("--ticks", type=int, default=None, help="override scenario n_ticks")
    run_p.add_argument("--observable", action="store_true", help="also write observable.jsonl")

    args = parser.parse_args(argv)
    if args.command == "run":
        cfg = load_scenario(args.config)
        provider = MockProvider() if args.provider == "mock" else OllamaProvider(cfg.model)
        out = run(cfg, provider, out_dir=args.out, n_ticks=args.ticks, write_observable=args.observable)
        print(f"Run written to {out}")
        return 0
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
