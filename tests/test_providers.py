from tessera.world import Agent, WorldState, DataStore
from tessera.schema import ActionParams, AgentAction
from tessera.providers import MockProvider


def _world():
    return WorldState(
        agents=[Agent(id="eve", name="Eve", role="user")],
        data_stores=[DataStore(id="d1", name="X", sensitivity="public", encryption_key_id="k")],
    )


def test_mock_returns_default_idle_when_unscripted():
    p = MockProvider()
    action = p.get_action(_world().agents[0], _world(), "")
    assert action.tool == "idle"


def test_mock_plays_script_in_order_then_repeats_last():
    script = {
        "eve": [
            AgentAction(tool="probe_system", params=ActionParams(resource_id="d1", method="scan")),
            AgentAction(tool="access_resource", params=ActionParams(resource_id="d1", method="read")),
        ]
    }
    p = MockProvider(script=script)
    eve = _world().agents[0]
    assert p.get_action(eve, _world(), "").tool == "probe_system"
    assert p.get_action(eve, _world(), "").tool == "access_resource"
    assert p.get_action(eve, _world(), "").tool == "access_resource"  # past end → repeat last


def test_mock_returns_independent_copies():
    script = {"eve": [AgentAction(tool="access_resource", params=ActionParams(resource_id="d1"))]}
    p = MockProvider(script=script)
    eve = _world().agents[0]
    first = p.get_action(eve, _world(), "")
    first.params.resource_id = "mutated"
    assert p.get_action(eve, _world(), "").params.resource_id == "d1"
