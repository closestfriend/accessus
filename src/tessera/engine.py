from __future__ import annotations

import random
from pathlib import Path

from tessera.config import ScenarioConfig
from tessera.memory import MemoryStore
from tessera.policy import POLICY_VERSION, evaluate
from tessera.providers import LLMProvider
from tessera.schema import Event, LabelRow, Manifest, to_observable
from tessera.world import WorldState


def _format_memory_line(event: Event) -> str:
    pd = event.policy_decision
    outcome = "GRANT" if pd.permitted else "DENY"
    return f"t{event.tick}: {event.tool}({event.params.resource_id}) -> {outcome}"


def run(
    cfg: ScenarioConfig,
    provider: LLMProvider,
    out_dir: Path,
    n_ticks: int | None = None,
    snapshot_every: int = 1,
    write_observable: bool = False,
) -> Path:
    """Run the simulation and write a run directory. Returns the directory path."""
    n_ticks = n_ticks if n_ticks is not None else cfg.n_ticks
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    world: WorldState = cfg.build_world()
    rng = random.Random(cfg.seed)
    memories: dict[str, MemoryStore] = {a.id: MemoryStore() for a in world.agents}

    events_f = (out_dir / "events.jsonl").open("w")
    labels_f = (out_dir / "labels.jsonl").open("w")
    snaps_f = (out_dir / "world_snapshots.jsonl").open("w")
    obs_f = (out_dir / "observable.jsonl").open("w") if write_observable else None

    try:
        for tick in range(n_ticks):
            order = list(world.agents)
            rng.shuffle(order)  # seeded, deterministic scheduling
            for agent in order:
                action = provider.get_action(agent, world, memories[agent.id].context())
                decision = evaluate(action, agent, world)

                if decision.leaked and action.params.resource_id:
                    store = world.get_store(action.params.resource_id)
                    if store is not None:
                        store.is_leaked = True

                event = Event(
                    tick=tick,
                    agent_id=agent.id,
                    tool=action.tool,
                    params=action.params,
                    internal_thought=action.internal_thought,
                    policy_decision=decision,
                    malformed=action.malformed,
                )
                events_f.write(event.model_dump_json() + "\n")
                labels_f.write(
                    LabelRow(
                        tick=tick,
                        agent_id=agent.id,
                        is_malicious_agent=agent.is_malicious,
                        ground_truth_violation=decision.ground_truth_violation,
                        leaked=decision.leaked,
                    ).model_dump_json()
                    + "\n"
                )
                if obs_f is not None:
                    obs_f.write(to_observable(event).model_dump_json() + "\n")
                memories[agent.id].append(_format_memory_line(event))

            if tick % snapshot_every == 0:
                snaps_f.write(world.model_dump_json() + "\n")
    finally:
        events_f.close()
        labels_f.close()
        snaps_f.close()
        if obs_f is not None:
            obs_f.close()

    manifest = Manifest(
        scenario_name=cfg.name,
        seed=cfg.seed,
        provider=provider.name,
        model=cfg.model,
        n_ticks=n_ticks,
        agent_ids=[a.id for a in world.agents],
        policy_version=POLICY_VERSION,
    )
    (out_dir / "manifest.json").write_text(manifest.model_dump_json(indent=2))
    return out_dir
