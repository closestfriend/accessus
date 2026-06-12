from pathlib import Path

from accessus.config import load_scenario


def test_load_default_scenario_builds_world():
    cfg = load_scenario(Path("configs/scenario_default.yaml"))
    assert cfg.name == "default"
    world = cfg.build_world()
    assert len(world.agents) == 5
    assert len(world.data_stores) == 4
    eve = world.get_agent("agent-5")
    assert eve.is_malicious is True
    assert "read:confidential" in eve.permissions  # the planted misconfiguration


def test_scenario_has_seed_and_ticks():
    cfg = load_scenario(Path("configs/scenario_default.yaml"))
    assert isinstance(cfg.seed, int)
    assert cfg.n_ticks >= 1
