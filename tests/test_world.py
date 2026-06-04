from tessera.world import Agent, DataStore, WorldState, SENSITIVITY_ORDER


def test_sensitivity_order_is_monotonic():
    assert SENSITIVITY_ORDER["public"] < SENSITIVITY_ORDER["internal"]
    assert SENSITIVITY_ORDER["confidential"] < SENSITIVITY_ORDER["restricted"]


def test_world_lookup_helpers():
    world = WorldState(
        agents=[Agent(id="a1", name="Alice", role="admin")],
        data_stores=[DataStore(id="d1", name="Public", sensitivity="public", encryption_key_id="k1")],
    )
    assert world.get_agent("a1").name == "Alice"
    assert world.get_store("d1").sensitivity == "public"
    assert world.get_agent("nope") is None
    assert world.get_store("nope") is None


def test_agent_defaults():
    a = Agent(id="a1", name="Eve", role="user")
    assert a.permissions == [] and a.objectives == []
    assert a.risk_propensity == 0.0 and a.is_malicious is False
