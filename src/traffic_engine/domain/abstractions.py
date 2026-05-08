"""Domain protocols for extensible traffic simulation components."""

from __future__ import annotations

from random import Random
from typing import Protocol

from .models import EdgeId, SimulationConfig, TopologyData, TrafficLight, Vehicle


class TrafficLightProvider(Protocol):
    def provide(self, topology: TopologyData, config: SimulationConfig) -> list[TrafficLight]:
        ...


class RouteProvider(Protocol):
    def choose_route(self, topology: TopologyData, random: Random) -> list[EdgeId]:
        ...


class CellularModel(Protocol):
    def resolve_lane(self, vehicle: Vehicle, available_lanes: int, gap_ahead: int) -> int:
        ...

    def resolve_velocity(
        self,
        vehicle: Vehicle,
        max_velocity: int,
        gap_ahead: int,
        red_light_gap: int | None,
        random: Random,
        noise_prob: float,
    ) -> int:
        ...
