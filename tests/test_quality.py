from pathlib import Path

from tessera.config import load_scenario
from tessera.schema import ActionParams, AgentAction
from tessera.providers import MockProvider
from tessera.engine import run
from evals.quality import distinct_n, compute_quality


def test_distinct_n_measures_diversity():
    assert distinct_n(["a b c", "d e f"], 2) == 1.0  # all bigrams unique
    assert distinct_n(["a a a a"], 2) < 0.5           # "a a" repeated
    assert distinct_n([], 2) == 1.0                   # empty → not penalized


def test_degenerate_all_idle_run_fails_gate(tmp_path: Path):
    cfg = load_scenario(Path("configs/scenario_default.yaml"))
    out = run(cfg, MockProvider(), out_dir=tmp_path, n_ticks=6)  # everyone idles
    report = compute_quality(out)
    assert report.passed is False
    assert any("divergence" in f for f in report.failures)


def test_varied_run_passes_gate(tmp_path: Path):
    cfg = load_scenario(Path("configs/scenario_default.yaml"))
    provider = MockProvider(
        script={
            "agent-5": [  # Eve cycles distinct actions; benign agents idle → high divergence
                AgentAction(tool="probe_system", params=ActionParams(resource_id="data-4", method="scan")),
                AgentAction(tool="access_resource", params=ActionParams(resource_id="data-3", method="read")),
                AgentAction(tool="request_escalation"),
            ]
        }
    )
    out = run(cfg, provider, out_dir=tmp_path, n_ticks=6)
    report = compute_quality(out)
    assert report.behavioral_divergence > 0.15
    assert report.passed is True
