"""Use case for creating a running simulation and dispatching it asynchronously."""

from __future__ import annotations

from uuid import uuid4
from typing import Dict, List, Tuple

from ...config import (
    DEFAULT_INITIAL_VEHICLES,
    DEFAULT_MAX_STEPS,
    DEFAULT_MAX_VEHICLES,
    DEFAULT_NOISE_PROB,
    DEFAULT_SPAWN_RATE,
    DEFAULT_TICK_INTERVAL_MS,
)
from ...domain.exceptions import GeographicAreaNotFoundError, SimulationConfigurationError
from ...domain.models import (
    EdgeId,
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
        blocked_lanes: Dict[str, List[int]] | None = None,
    ) -> SimulationRecord:
        area = self.area_repository.get(area_id)
        if area is None:
            raise GeographicAreaNotFoundError(f"Geographic area '{area_id}' is not available.")

        normalized_default_lanes = max(1, default_lanes)
        if enable_lane_changes and normalized_default_lanes < 2:
            raise SimulationConfigurationError(
                "Lane changes require at least two lanes in the default lane configuration."
            )

        # Parse and validate blocked_lanes
        parsed_blocked_lanes: Dict[EdgeId, List[int]] = {}
        if blocked_lanes:
            for key_str, lane_indices in blocked_lanes.items():
                parts = key_str.split("-")
                if len(parts) != 3:
                    raise SimulationConfigurationError(
                        f"Invalid edge key format: '{key_str}'. Expected format: 'u-v-key'"
                    )
                try:
                    u, v = parts[0], parts[1]
                    k = int(parts[2])
                    edge_id: EdgeId = (u, v, k)
                    
                    # Validate edge exists
                    if edge_id not in area.topology.edges:
                        raise SimulationConfigurationError(
                            f"Edge '{key_str}' does not exist in geographic area '{area_id}'."
                        )
                    
                    edge_data = area.topology.edges[edge_id]
                    max_lane = max(1, edge_data.lanes)
                    
                    # Validate lane indices
                    for lane_idx in lane_indices:
                        if not 0 <= lane_idx < max_lane:
                            raise SimulationConfigurationError(
                                f"Lane {lane_idx} is invalid for edge '{key_str}'. "
                                f"Edge has {max_lane} lanes (0-{max_lane - 1})."
                            )
                    
                    parsed_blocked_lanes[edge_id] = lane_indices
                except (ValueError, IndexError) as exc:
                    raise SimulationConfigurationError(
                        f"Failed to parse edge key '{key_str}': {exc}"
                    ) from exc

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
                default_lanes=normalized_default_lanes,
                traffic_light_percentage=max(0.0, min(1.0, traffic_light_percentage)),
                traffic_light_green_steps=max(1, traffic_light_green_steps),
                traffic_light_red_steps=max(0, traffic_light_red_steps),
                enable_lane_changes=enable_lane_changes,
                blocked_lanes=parsed_blocked_lanes,
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
