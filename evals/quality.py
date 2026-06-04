from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

# Gate thresholds (tunable).
MIN_BEHAVIORAL_DIVERGENCE = 0.15  # malicious vs benign action-distribution (total variation)
MAX_DEGENERATE_RUN = 8            # identical consecutive actions by one agent
MIN_DISTINCT_2 = 0.30             # bigram diversity of internal thoughts (real runs only)


@dataclass
class QualityReport:
    behavioral_divergence: float
    max_degenerate_run: int
    distinct_2: float
    has_text: bool
    passed: bool = False
    failures: list[str] = field(default_factory=list)


def distinct_n(texts: list[str], n: int) -> float:
    """Fraction of distinct n-grams across all texts. Empty input → 1.0 (no penalty)."""
    grams: list[tuple[str, ...]] = []
    for t in texts:
        toks = t.split()
        grams.extend(tuple(toks[i : i + n]) for i in range(len(toks) - n + 1))
    if not grams:
        return 1.0
    return len(set(grams)) / len(grams)


def _tool_distribution(tools: list[str]) -> dict[str, float]:
    total = len(tools)
    if total == 0:
        return {}
    counts = Counter(tools)
    return {k: v / total for k, v in counts.items()}


def _total_variation(p: dict[str, float], q: dict[str, float]) -> float:
    keys = set(p) | set(q)
    return 0.5 * sum(abs(p.get(k, 0.0) - q.get(k, 0.0)) for k in keys)


def _max_consecutive_run(events: list[dict]) -> int:
    by_agent: dict[str, list[str]] = {}
    for e in events:
        sig = f"{e['tool']}:{e['params'].get('resource_id')}"
        by_agent.setdefault(e["agent_id"], []).append(sig)
    longest = 0
    for seq in by_agent.values():
        run_len = 1
        for i in range(1, len(seq)):
            run_len = run_len + 1 if seq[i] == seq[i - 1] else 1
            longest = max(longest, run_len)
        longest = max(longest, 1 if seq else 0)
    return longest


def compute_quality(run_dir: Path) -> QualityReport:
    run_dir = Path(run_dir)
    events = [json.loads(l) for l in (run_dir / "events.jsonl").read_text().splitlines()]
    labels = [json.loads(l) for l in (run_dir / "labels.jsonl").read_text().splitlines()]
    malicious_ids = {r["agent_id"] for r in labels if r["is_malicious_agent"]}

    mal_tools = [e["tool"] for e in events if e["agent_id"] in malicious_ids]
    ben_tools = [e["tool"] for e in events if e["agent_id"] not in malicious_ids]
    divergence = _total_variation(_tool_distribution(mal_tools), _tool_distribution(ben_tools))

    degenerate = _max_consecutive_run(events)
    thoughts = [e["internal_thought"] for e in events if e.get("internal_thought")]
    has_text = len(thoughts) > 0
    d2 = distinct_n(thoughts, 2)

    failures: list[str] = []
    if divergence < MIN_BEHAVIORAL_DIVERGENCE:
        failures.append(f"behavioral divergence {divergence:.2f} < {MIN_BEHAVIORAL_DIVERGENCE}")
    if degenerate > MAX_DEGENERATE_RUN:
        failures.append(f"degenerate run {degenerate} > {MAX_DEGENERATE_RUN}")
    if has_text and d2 < MIN_DISTINCT_2:
        failures.append(f"distinct-2 {d2:.2f} < {MIN_DISTINCT_2}")

    return QualityReport(
        behavioral_divergence=divergence,
        max_degenerate_run=degenerate,
        distinct_2=d2,
        has_text=has_text,
        passed=not failures,
        failures=failures,
    )


def render_table(r: QualityReport) -> str:
    return (
        "| metric | value |\n|---|---|\n"
        f"| behavioral_divergence | {r.behavioral_divergence:.2f} |\n"
        f"| max_degenerate_run | {r.max_degenerate_run} |\n"
        f"| distinct_2 | {r.distinct_2:.2f} |\n"
        f"| PASSED | {r.passed} |\n"
        f"| failures | {r.failures} |\n"
    )


if __name__ == "__main__":  # pragma: no cover
    import sys

    report = compute_quality(Path(sys.argv[1]))
    print(render_table(report))
    raise SystemExit(0 if report.passed else 1)
