from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel

from accessus.world import Agent, DataStore, WorldState


class ScenarioConfig(BaseModel):
    name: str
    seed: int = 42
    n_ticks: int = 10
    model: str = "llama3.1:8b"
    agents: list[Agent]
    data_stores: list[DataStore]

    def build_world(self) -> WorldState:
        return WorldState(
            agents=[a.model_copy(deep=True) for a in self.agents],
            data_stores=[d.model_copy(deep=True) for d in self.data_stores],
        )


def load_scenario(path: Path) -> ScenarioConfig:
    data = yaml.safe_load(Path(path).read_text())
    return ScenarioConfig.model_validate(data)
