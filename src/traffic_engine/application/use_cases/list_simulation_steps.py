"""Use case for retrieving persisted simulation steps."""

from __future__ import annotations

from ...domain.exceptions import SimulationNotFoundError, SimulationNotReadyError
from ...domain.models import SimulationStatus, SimulationStep
from ..ports import SimulationRepository


class ListSimulationStepsUseCase:
    def __init__(self, repository: SimulationRepository) -> None:
        self.repository = repository

    def execute(
        self,
        simulation_id: str,
        allow_running: bool = False,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[SimulationStep]:
        record = self.repository.get(simulation_id)
        if record is None:
            raise SimulationNotFoundError(f"Simulation '{simulation_id}' does not exist.")
        if record.status == SimulationStatus.RUNNING and not allow_running:
            raise SimulationNotReadyError(
                "Simulation steps are available through REST only after the simulation finishes or is cancelled."
            )
        return self.repository.list_steps(simulation_id, limit=limit, offset=offset)

