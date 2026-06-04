from tessera.memory import MemoryStore


def test_recent_is_capped_at_max_recent():
    m = MemoryStore(max_recent=3)
    for i in range(5):
        m.append(f"event {i}")
    assert m.recent() == ["event 2", "event 3", "event 4"]


def test_context_includes_summary_then_recent():
    m = MemoryStore(max_recent=2)
    m.append("did a thing")
    m.set_summary("agent has been probing restricted data")
    ctx = m.context()
    assert "Summary: agent has been probing restricted data" in ctx
    assert "did a thing" in ctx
    assert ctx.index("Summary:") < ctx.index("did a thing")


def test_empty_context_is_empty_string():
    assert MemoryStore().context() == ""
