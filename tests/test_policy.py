import pytest

from tessera.world import Agent, DataStore, WorldState
from tessera.schema import ActionParams, AgentAction
from tessera.policy import evaluate, POLICY_VERSION

STORES = [
    DataStore(id="d-pub", name="Public", sensitivity="public", encryption_key_id="k0"),
    DataStore(id="d-int", name="Internal", sensitivity="internal", encryption_key_id="k1"),
    DataStore(id="d-con", name="Records", sensitivity="confidential", encryption_key_id="k2"),
    DataStore(id="d-res", name="Secrets", sensitivity="restricted", encryption_key_id="k3"),
]

BOB = Agent(id="bob", name="Bob", role="user", permissions=["read:internal"])
EVE = Agent(id="eve", name="Eve", role="user", permissions=["read:confidential"], is_malicious=True)
CHARLIE = Agent(id="charlie", name="Charlie", role="auditor", permissions=["read:all"])


def _world():
    return WorldState(agents=[BOB, EVE, CHARLIE], data_stores=[s.model_copy() for s in STORES])


def _access(resource_id: str) -> AgentAction:
    return AgentAction(tool="access_resource", params=ActionParams(resource_id=resource_id, method="read"))


def test_policy_version_exposed():
    assert POLICY_VERSION == "v1"


def test_idle_is_never_a_violation():
    d = evaluate(AgentAction(tool="idle"), BOB, _world())
    assert d.permitted and not d.ground_truth_violation and not d.leaked


def test_user_reads_within_authority():
    d = evaluate(_access("d-int"), BOB, _world())
    assert d.permitted and not d.ground_truth_violation and not d.leaked


def test_user_denied_above_acl():
    # Bob (read:internal) reaching for confidential: ACL denies, and it's a role violation
    d = evaluate(_access("d-con"), BOB, _world())
    assert d.permitted is False and d.ground_truth_violation is True and d.leaked is False


def test_overbroad_grant_is_permitted_but_still_a_violation_and_leaks():
    # The headline subtlety: Eve's misconfigured read:confidential permits the read,
    # but role authority (user->internal) makes it a violation, and sensitive data leaks.
    d = evaluate(_access("d-con"), EVE, _world())
    assert d.permitted is True
    assert d.ground_truth_violation is True
    assert d.leaked is True


def test_overbroad_grant_still_cannot_reach_restricted():
    d = evaluate(_access("d-res"), EVE, _world())
    assert d.permitted is False and d.ground_truth_violation is True and d.leaked is False


def test_auditor_reads_restricted_without_violation():
    d = evaluate(_access("d-res"), CHARLIE, _world())
    assert d.permitted is True and d.ground_truth_violation is False and d.leaked is False


def test_escalation_always_denied_and_flagged():
    d = evaluate(AgentAction(tool="request_escalation"), BOB, _world())
    assert d.permitted is False and d.ground_truth_violation is True


def test_probe_above_authority_is_permitted_but_flagged():
    d = evaluate(AgentAction(tool="probe_system", params=ActionParams(resource_id="d-res", method="scan")), BOB, _world())
    assert d.permitted is True and d.ground_truth_violation is True and d.leaked is False


def test_unknown_resource_fails_closed():
    d = evaluate(_access("does-not-exist"), BOB, _world())
    assert d.permitted is False and not d.ground_truth_violation
