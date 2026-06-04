from __future__ import annotations


class MemoryStore:
    """Per-agent episodic memory: last-N events plus a rolling summary.

    The rolling summary is set externally (engine regenerates it every K ticks,
    via the provider for real runs). Retrieval is intentionally simple for v1;
    swap in salience/embedding retrieval later without changing this interface.
    """

    def __init__(self, max_recent: int = 5) -> None:
        self.max_recent = max_recent
        self._events: list[str] = []
        self.summary: str = ""

    def append(self, line: str) -> None:
        self._events.append(line)

    def set_summary(self, summary: str) -> None:
        self.summary = summary

    def recent(self) -> list[str]:
        return self._events[-self.max_recent :]

    def context(self) -> str:
        parts: list[str] = []
        if self.summary:
            parts.append(f"Summary: {self.summary}")
        parts.extend(self.recent())
        return "\n".join(parts)
