"""Builder for validated simulation model configuration."""

from __future__ import annotations

from dataclasses import dataclass

from .abstractions import CellularModel, RouteProvider, TrafficLightProvider
from .exceptions import SimulationConfigurationError
from .models import SimulationConfig, SimulationExecutionMode


@dataclass(frozen=True)
class SimulationModelDefinition:
    config: SimulationConfig
    route_provider: RouteProvider
    cellular_model: CellularModel
    traffic_light_provider: TrafficLightProvider | None = None


class SimulationModelBuilder:
    def __init__(self, base_config: SimulationConfig) -> None:
        self._config = base_config
        self._mode: SimulationExecutionMode | None = None
        self._route_provider: RouteProvider | None = None
        self._cellular_model: CellularModel | None = None
        self._traffic_light_provider: TrafficLightProvider | None = None
        self._default_lanes = base_config.default_lanes

    def with_execution_mode(self, mode: SimulationExecutionMode) -> "SimulationModelBuilder":
        self._mode = mode
        return self

    def with_route_provider(self, provider: RouteProvider) -> "SimulationModelBuilder":
        self._route_provider = provider
        return self

    def with_cellular_model(self, model: CellularModel) -> "SimulationModelBuilder":
        self._cellular_model = model
        return self

    def with_traffic_light_provider(
        self,
        provider: TrafficLightProvider | None,
    ) -> "SimulationModelBuilder":
        self._traffic_light_provider = provider
        return self

    def with_default_lanes(self, lanes: int) -> "SimulationModelBuilder":
        self._default_lanes = lanes
        return self

    def build(self) -> SimulationModelDefinition:
        if self._mode is None:
            raise SimulationConfigurationError("Simulation execution mode is required.")
        if self._route_provider is None:
            raise SimulationConfigurationError("RouteProvider is required.")
        if self._cellular_model is None:
            raise SimulationConfigurationError("CellularModel is required.")
        if self._default_lanes < 1:
            raise SimulationConfigurationError("default_lanes must be greater than zero.")
        if self._config.enable_lane_changes and self._default_lanes < 2:
            raise SimulationConfigurationError(
                "Lane changes require at least two lanes in the default lane configuration."
            )
        config = SimulationConfig(
            initial_vehicles=self._config.initial_vehicles,
            max_vehicles=self._config.max_vehicles,
            max_steps=self._config.max_steps,
            spawn_rate=self._config.spawn_rate,
            noise_prob=self._config.noise_prob,
            seed=self._config.seed,
            tick_interval_ms=self._config.tick_interval_ms,
            execution_mode=self._mode,
            default_lanes=self._default_lanes,
            traffic_light_percentage=self._config.traffic_light_percentage,
            traffic_light_green_steps=self._config.traffic_light_green_steps,
            traffic_light_red_steps=self._config.traffic_light_red_steps,
            enable_lane_changes=self._config.enable_lane_changes,
        )
        return SimulationModelDefinition(
            config=config,
            route_provider=self._route_provider,
            cellular_model=self._cellular_model,
            traffic_light_provider=self._traffic_light_provider,
        )
