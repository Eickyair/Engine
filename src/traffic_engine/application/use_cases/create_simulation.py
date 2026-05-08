"""Use case for creating a running simulation and dispatching it asynchronously."""

from __future__ import annotations

from uuid import uuid4

from ...config import (
    DEFAULT_INITIAL_VEHICLES,
    DEFAULT_MAX_STEPS,
    DEFAULT_MAX_VEHICLES,
    DEFAULT_NOISE_PROB,
    DEFAULT_SPAWN_RATE,
    DEFAULT_TICK_INTERVAL_MS,
)
from ...domain.exceptions import GeographicAreaNotFoundError
from ...domain.models import (
    GeographicArea,
    SimulationConfig,
    SimulationExecutionMode,
    SimulationRecord,
    SimulationStatus,
)
from ..ports import GeographicAreaRepository, SimulationRepository, SimulationRuntime
from .run_simulation import RunSimulationUseCase


class CreateSimulationUseCase:
    def __init__(
        self,
        area_repository: GeographicAreaRepository,
        simulation_repository: SimulationRepository,
        runtime: SimulationRuntime,
        run_simulation: RunSimulationUseCase,
    ) -> None:
        self.area_repository = area_repository
        self.simulation_repository = simulation_repository
        self.runtime = runtime
        self.run_simulation = run_simulation

    def execute(
        self,
        area_id: str,
        *,
        initial_vehicles: int = DEFAULT_INITIAL_VEHICLES,
        max_vehicles: int = DEFAULT_MAX_VEHICLES,
        max_steps: int = DEFAULT_MAX_STEPS,
        spawn_rate: float = DEFAULT_SPAWN_RATE,
        noise_prob: float = DEFAULT_NOISE_PROB,
        seed: int = 42,
        tick_interval_ms: int = DEFAULT_TICK_INTERVAL_MS,
        execution_mode: SimulationExecutionMode = SimulationExecutionMode.CONTINUOUS,
        default_lanes: int = 1,
        traffic_light_percentage: float = 0.0,
        traffic_light_green_steps: int = 10,
        traffic_light_red_steps: int = 10,
        enable_lane_changes: bool = False,
    ) -> SimulationRecord:
        area = self.area_repository.get(area_id)
        if area is None:
            raise GeographicAreaNotFoundError(f"Geographic area '{area_id}' is not available.")

        record = SimulationRecord(
            simulation_id=uuid4().hex,
            area_id=area.area_id,
            status=SimulationStatus.RUNNING,
            config=SimulationConfig(
                initial_vehicles=initial_vehicles,
                max_vehicles=max(max_vehicles, initial_vehicles),
                max_steps=max_steps,
                spawn_rate=spawn_rate,
                noise_prob=noise_prob,
                seed=seed,
                tick_interval_ms=tick_interval_ms,
                execution_mode=execution_mode,
                default_lanes=max(1, default_lanes),
                traffic_light_percentage=max(0.0, min(1.0, traffic_light_percentage)),
                traffic_light_green_steps=max(1, traffic_light_green_steps),
                traffic_light_red_steps=max(0, traffic_light_red_steps),
                enable_lane_changes=enable_lane_changes,
            ),
        )
        stored = self.simulation_repository.create(record)
        self.runtime.start(
            stored.simulation_id,
            job_factory=lambda cancel_event: self.run_simulation.execute(
                record=stored,
                area=area,
                cancel_event=cancel_event,
            ),
        )
        return stored
