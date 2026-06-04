import json
from pathlib import Path

from tessera.config import load_scenario
from tessera.schema import ActionParams, AgentAction, Event, ObservableEvent, Manifest
from tessera.providers import MockProvider
from tessera.engine import run


def _scripted_provider() -> MockProvider:
    # Eve performs the over-broad confidential read (a permitted violation that leaks),
    # then requests escalation. Everyone else idles.
    return MockProvider(
        script={
            "agent-5": [
                AgentAction(tool="access_resource", params=ActionParams(resource_id="data-3", method="read")),
                AgentAction(tool="request_escalation"),
            ]
        }
    )


def test_run_writes_all_four_files(tmp_path: Path):
    cfg = load_scenario(Path("configs/scenario_default.yaml"))
    out = run(cfg, _scripted_provider(), out_dir=tmp_path, n_ticks=2)
    for name in ("manifest.json", "events.jsonl", "world_snapshots.jsonl", "labels.jsonl"):
        assert (out / name).exists(), f"missing {name}"


def test_manifest_is_valid_and_records_config(tmp_path: Path):
    cfg = load_scenario(Path("configs/scenario_default.yaml"))
    out = run(cfg, _scripted_provider(), out_dir=tmp_path, n_ticks=2)
    manifest = Manifest.model_validate_json((out / "manifest.json").read_text())
    assert manifest.n_ticks == 2
    assert manifest.provider == "mock"
    assert manifest.policy_version == "v1"
    assert set(manifest.agent_ids) == {f"agent-{i}" for i in range(1, 6)}


def test_events_are_schema_valid_and_capture_the_leak(tmp_path: Path):
    cfg = load_scenario(Path("configs/scenario_default.yaml"))
    out = run(cfg, _scripted_provider(), out_dir=tmp_path, n_ticks=2)
    events = [Event.model_validate_json(line) for line in (out / "events.jsonl").read_text().splitlines()]
    leaks = [e for e in events if e.policy_decision.leaked]
    assert len(leaks) == 1
    leak = leaks[0]
    assert leak.agent_id == "agent-5"
    assert leak.policy_decision.permitted is True
    assert leak.policy_decision.ground_truth_violation is True


def test_observable_view_has_no_ground_truth(tmp_path: Path):
    cfg = load_scenario(Path("configs/scenario_default.yaml"))
    out = run(cfg, _scripted_provider(), out_dir=tmp_path, n_ticks=2, write_observable=True)
    raw_lines = (out / "observable.jsonl").read_text().splitlines()
    for line in raw_lines:
        d = json.loads(line)
        assert "internal_thought" not in d and "policy_decision" not in d
        ObservableEvent.model_validate(d)  # parses against the observable schema


def test_run_is_deterministic_with_same_seed(tmp_path: Path):
    cfg = load_scenario(Path("configs/scenario_default.yaml"))
    a = run(cfg, _scripted_provider(), out_dir=tmp_path / "a", n_ticks=3)
    b = run(cfg, _scripted_provider(), out_dir=tmp_path / "b", n_ticks=3)
    assert (a / "events.jsonl").read_text() == (b / "events.jsonl").read_text()


def test_leak_marks_store_in_snapshot(tmp_path: Path):
    cfg = load_scenario(Path("configs/scenario_default.yaml"))
    out = run(cfg, _scripted_provider(), out_dir=tmp_path, n_ticks=2)
    snapshots = (out / "world_snapshots.jsonl").read_text().splitlines()
    final = json.loads(snapshots[-1])
    leaked = [s for s in final["data_stores"] if s["is_leaked"]]
    assert any(s["id"] == "data-3" for s in leaked)
