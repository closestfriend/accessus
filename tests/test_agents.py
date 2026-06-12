from accessus.world import Agent, DataStore, WorldState
from accessus.agents import build_prompt, parse_action


def _world():
    return WorldState(
        agents=[Agent(id="eve", name="Eve", role="user", permissions=["read:internal"],
                      objectives=["exfiltrate"], is_malicious=True)],
        data_stores=[DataStore(id="data-4", name="Trade Secrets", sensitivity="restricted", encryption_key_id="k")],
    )


def test_prompt_includes_objectives_tools_and_resources_but_not_malice_label():
    world = _world()
    prompt = build_prompt(world.agents[0], world, memory_context="t0: idle")
    assert "exfiltrate" in prompt
    assert "data-4" in prompt and "restricted" in prompt
    assert "access_resource" in prompt and "request_escalation" in prompt
    assert "t0: idle" in prompt
    assert "is_malicious" not in prompt and "malicious" not in prompt.lower()


def test_parse_valid_action():
    action = parse_action({"tool": "access_resource",
                           "params": {"resource_id": "data-4", "method": "read"},
                           "internal_thought": "go"})
    assert action.tool == "access_resource"
    assert action.params.resource_id == "data-4"
    assert action.malformed is False


def test_parse_malformed_falls_back_to_idle():
    action = parse_action({"not": "valid"})
    assert action.tool == "idle"
    assert action.malformed is True
