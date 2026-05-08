"""Initial provider implementations for the simulation engine."""

from __future__ import annotations

import heapq
from math import floor
from random import Random

from ..domain.exceptions import RouteSelectionError
from ..domain.models import EdgeId, SimulationConfig, TopologyData, TrafficLight, TrafficLightCycle, Vehicle


class RandomTrafficLightProvider:
    def __init__(self, percentage: float | None = None, seed: int | None = None) -> None:
        self.percentage = percentage
        self.seed = seed

    def provide(self, topology: TopologyData, config: SimulationConfig) -> list[TrafficLight]:
        candidates = _valid_intersections(topology)
        if not candidates:
            return []
        percentage = _clamp_percentage(
            config.traffic_light_percentage if self.percentage is None else self.percentage
        )
        count = _round_half_up(len(candidates) * percentage)
        if count <= 0:
            return []
        random = Random(config.seed if self.seed is None else self.seed)
        selected = random.sample(candidates, min(count, len(candidates)))
        incoming = _incoming_nodes(topology)
        cycle = TrafficLightCycle(
            green_steps=config.traffic_light_green_steps,
            red_steps=config.traffic_light_red_steps,
        )
        return [
            TrafficLight(
                node_id=node_id,
                applies_to=sorted(incoming.get(node_id, [])),
                cycle=cycle,
            )
            for node_id in selected
        ]


class ShortestPathRouteProvider:
    def choose_route(self, topology: TopologyData, random: Random) -> list[EdgeId]:
        if not topology.edges:
            raise RouteSelectionError("The grid has no traversable cells.")
        boundary_nodes = [
            node_id for node_id, node in topology.nodes.items() if node.is_boundary
        ] or list(topology.nodes.keys())
        if len(boundary_nodes) < 2:
            raise RouteSelectionError("At least two valid traversable nodes are required.")

        for _ in range(20):
            origin, destination = random.sample(boundary_nodes, 2)
            route = self._shortest_edge_path(topology, origin, destination)
            if route:
                return route
        raise RouteSelectionError("No reachable origin/destination pair could be selected.")

    def _shortest_edge_path(
        self,
        topology: TopologyData,
        origin: str,
        destination: str,
    ) -> list[EdgeId]:
        adjacency = topology.outgoing_edges()
        distances: dict[str, float] = {origin: 0.0}
        previous: dict[str, EdgeId] = {}
        heap: list[tuple[float, str]] = [(0.0, origin)]

        while heap:
            distance, node_id = heapq.heappop(heap)
            if node_id == destination:
                break
            if distance > distances.get(node_id, float("inf")):
                continue
            for edge_id in adjacency.get(node_id, []):
                edge = topology.edges[edge_id]
                next_node = edge_id[1]
                candidate = distance + edge.travel_time_sec
                if candidate >= distances.get(next_node, float("inf")):
                    continue
                distances[next_node] = candidate
                previous[next_node] = edge_id
                heapq.heappush(heap, (candidate, next_node))

        if destination not in previous:
            return []

        route: list[EdgeId] = []
        current = destination
        while current != origin:
            edge_id = previous[current]
            route.append(edge_id)
            current = edge_id[0]
        route.reverse()
        return route


class NagelCellularModel:
    def __init__(self, allow_lane_changes: bool = False) -> None:
        self.supports_lane_changes = allow_lane_changes

    def resolve_lane(self, vehicle: Vehicle, available_lanes: int, gap_ahead: int) -> int:
        if not self.supports_lane_changes or available_lanes < 2 or gap_ahead > 0:
            return vehicle.lane
        return min(available_lanes - 1, vehicle.lane + 1)

    def resolve_velocity(
        self,
        vehicle: Vehicle,
        max_velocity: int,
        gap_ahead: int,
        red_light_gap: int | None,
        random: Random,
        noise_prob: float,
    ) -> int:
        new_velocity = min(vehicle.velocity + 1, max_velocity, gap_ahead)
        if red_light_gap is not None:
            new_velocity = min(new_velocity, max(0, red_light_gap - 1))
        if new_velocity > 0 and random.random() < noise_prob:
            new_velocity -= 1
        return new_velocity


def _valid_intersections(topology: TopologyData) -> list[str]:
    incoming = _incoming_nodes(topology)
    outgoing = topology.outgoing_edges()
    valid: list[str] = []
    for node_id in topology.nodes:
        degree = len(incoming.get(node_id, [])) + len(outgoing.get(node_id, []))
        if degree >= 3:
            valid.append(node_id)
    return valid


def _incoming_nodes(topology: TopologyData) -> dict[str, set[str]]:
    incoming: dict[str, set[str]] = {node_id: set() for node_id in topology.nodes}
    for origin, destination, _ in topology.edges:
        incoming.setdefault(destination, set()).add(origin)
    return incoming


def _clamp_percentage(value: float) -> float:
    return max(0.0, min(1.0, value))


def _round_half_up(value: float) -> int:
    return int(floor(value + 0.5))
