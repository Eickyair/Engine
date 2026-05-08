"""Simulation abstractions and NaSch model implementation."""

from __future__ import annotations

import heapq
from math import hypot
from random import Random
from typing import Dict, List, Protocol

from ..config import CELL_SIZE_M, TICK_SECONDS
from .abstractions import CellularModel, RouteProvider
from .models import (
    CellSnapshot,
    EdgeData,
    EdgeId,
    SimulationExecutionMode,
    SimulationConfig,
    SimulationMetrics,
    SimulationState,
    TopologyData,
    TrafficLight,
    TrafficLightSnapshot,
    TrafficLightState,
    Vehicle,
    VehicleSnapshot,
)


class SimulationModel(Protocol):
    def reset(self, topology: TopologyData, config: SimulationConfig) -> SimulationState:
        ...

    def step(self) -> tuple[SimulationState, SimulationMetrics, bool]:
        ...


class NaSchSimulationModel:
    def __init__(
        self,
        seed: int,
        route_provider: RouteProvider | None = None,
        cellular_model: CellularModel | None = None,
        traffic_lights: List[TrafficLight] | None = None,
    ) -> None:
        self._random = Random(seed)
        self._route_provider = route_provider
        self._cellular_model = cellular_model
        self._traffic_lights = traffic_lights or []
        self._topology: TopologyData | None = None
        self._config: SimulationConfig | None = None
        self._edge_cells: Dict[EdgeId, List[List[int]]] = {}
        self._vehicles: Dict[int, Vehicle] = {}
        self._boundary_nodes: List[str] = []
        self._adjacency: Dict[str, List[EdgeId]] = {}
        self._traffic_lights_by_node: Dict[str, TrafficLight] = {}
        self._step_number = 0
        self._next_vehicle_id = 1
        self._last_removed = 0

    def reset(self, topology: TopologyData, config: SimulationConfig) -> SimulationState:
        self._topology = topology
        self._config = config
        self._edge_cells = {
            edge_id: [
                [0] * max(1, edge_data.n_cells)
                for _ in range(max(1, edge_data.lanes, config.default_lanes))
            ]
            for edge_id, edge_data in topology.edges.items()
        }
        self._vehicles = {}
        self._boundary_nodes = [
            node_id for node_id, node in topology.nodes.items() if node.is_boundary
        ] or list(topology.nodes.keys())
        self._adjacency = topology.outgoing_edges()
        self._traffic_lights_by_node = {
            traffic_light.node_id: traffic_light for traffic_light in self._traffic_lights
        }
        self._step_number = 0
        self._next_vehicle_id = 1
        self._last_removed = 0
        self._spawn_until(config.initial_vehicles)
        return self._build_state()

    def step(self) -> tuple[SimulationState, SimulationMetrics, bool]:
        if self._topology is None or self._config is None:
            raise RuntimeError("Simulation model must be reset before stepping.")

        vehicle_ids = list(self._vehicles.keys())
        self._random.shuffle(vehicle_ids)
        finished: List[int] = []
        speeds: List[int] = []

        for vehicle_id in vehicle_ids:
            vehicle = self._vehicles.get(vehicle_id)
            if vehicle is None:
                continue

            current_edge = vehicle.current_edge
            edge_data = self._topology.edges[current_edge]
            gap = self._gap_ahead(vehicle)
            available_lanes = len(self._edge_cells[current_edge])
            target_lane = self._resolve_lane(vehicle, available_lanes, gap)
            if target_lane != vehicle.lane:
                self._edge_cells[current_edge][vehicle.lane][vehicle.cell_pos] = 0
                vehicle.lane = target_lane
                self._edge_cells[current_edge][vehicle.lane][vehicle.cell_pos] = vehicle_id
                new_velocity = 0
            else:
                new_velocity = self._resolve_velocity(
                    vehicle=vehicle,
                    max_velocity=edge_data.vmax_cells,
                    gap_ahead=gap,
                    red_light_gap=self._red_light_gap(vehicle),
                )

            if new_velocity == 0:
                vehicle.wait_ticks += 1

            if new_velocity > 0:
                self._edge_cells[current_edge][vehicle.lane][vehicle.cell_pos] = 0
                target_position = vehicle.cell_pos + new_velocity
                edge_length = len(self._edge_cells[current_edge][vehicle.lane])

                while target_position >= edge_length:
                    overflow = target_position - edge_length
                    if vehicle.next_edge is None:
                        finished.append(vehicle_id)
                        break
                    vehicle.edge_idx += 1
                    current_edge = vehicle.current_edge
                    available_lanes = len(self._edge_cells[current_edge])
                    vehicle.lane = min(vehicle.lane, available_lanes - 1)
                    edge_length = len(self._edge_cells[current_edge][vehicle.lane])
                    target_position = overflow
                else:
                    clamped = min(target_position, edge_length - 1)
                    if self._edge_cells[current_edge][vehicle.lane][clamped] == 0:
                        vehicle.cell_pos = clamped
                        self._edge_cells[current_edge][vehicle.lane][clamped] = vehicle_id
                    else:
                        previous_edge = vehicle.current_edge
                        self._edge_cells[previous_edge][vehicle.lane][vehicle.cell_pos] = vehicle_id
                        new_velocity = 0

                vehicle.distance_traveled_m += new_velocity * CELL_SIZE_M
            else:
                self._edge_cells[current_edge][vehicle.lane][vehicle.cell_pos] = vehicle_id

            vehicle.velocity = new_velocity
            speeds.append(new_velocity)

        for vehicle_id in finished:
            self._vehicles.pop(vehicle_id, None)

        self._last_removed = len(finished)
        self._step_number += 1
        if self._config.execution_mode == SimulationExecutionMode.CONTINUOUS:
            self._spawn_from_rate()
        state = self._build_state()
        metrics = self._build_metrics(speeds=speeds)
        done = self._step_number >= self._config.max_steps
        return state, metrics, done

    def _spawn_from_rate(self) -> None:
        if self._config is None:
            return
        target = min(self._config.max_vehicles, len(self._vehicles) + int(self._config.spawn_rate * 10))
        if self._random.random() <= self._config.spawn_rate:
            target = min(self._config.max_vehicles, target + 1)
        self._spawn_until(target)

    def _spawn_until(self, target_count: int) -> None:
        attempts = 0
        while len(self._vehicles) < target_count and attempts < target_count * 8 + 8:
            attempts += 1
            route = self._random_route()
            if not route:
                continue
            start_edge = route[0]
            lane, start_pos = self._first_free_spawn_cell(start_edge)
            if lane is None:
                continue
            vehicle_id = self._next_vehicle_id
            self._next_vehicle_id += 1
            self._vehicles[vehicle_id] = Vehicle(
                vid=vehicle_id,
                route=route,
                cell_pos=start_pos,
                lane=lane,
            )
            self._edge_cells[start_edge][lane][start_pos] = vehicle_id

    def _random_route(self) -> List[EdgeId] | None:
        if self._topology is None or not self._boundary_nodes:
            return None
        if self._route_provider is not None:
            try:
                return self._route_provider.choose_route(self._topology, self._random)
            except Exception:
                return None
        if len(self._boundary_nodes) < 2:
            nodes = list(self._topology.nodes.keys())
        else:
            nodes = self._boundary_nodes

        for _ in range(20):
            origin, destination = self._random.sample(nodes, 2)
            path = self._shortest_edge_path(origin, destination)
            if len(path) >= 1:
                return path
        return None

    def _shortest_edge_path(self, origin: str, destination: str) -> List[EdgeId]:
        if self._topology is None:
            return []

        distances: Dict[str, float] = {origin: 0.0}
        previous: Dict[str, EdgeId] = {}
        heap: List[tuple[float, str]] = [(0.0, origin)]

        while heap:
            distance, node_id = heapq.heappop(heap)
            if node_id == destination:
                break
            if distance > distances.get(node_id, float("inf")):
                continue

            for edge_id in self._adjacency.get(node_id, []):
                edge = self._topology.edges[edge_id]
                next_node = edge_id[1]
                candidate = distance + edge.travel_time_sec
                if candidate >= distances.get(next_node, float("inf")):
                    continue
                distances[next_node] = candidate
                previous[next_node] = edge_id
                heapq.heappush(heap, (candidate, next_node))

        if destination not in previous:
            return []

        route: List[EdgeId] = []
        current = destination
        while current != origin:
            edge_id = previous[current]
            route.append(edge_id)
            current = edge_id[0]
        route.reverse()
        return route

    def _gap_ahead(self, vehicle: Vehicle) -> int:
        current_cells = self._edge_cells[vehicle.current_edge][vehicle.lane]
        position = vehicle.cell_pos

        for distance in range(1, len(current_cells) - position):
            if current_cells[position + distance] != 0:
                return distance - 1

        gap_in_edge = (len(current_cells) - 1) - position
        if vehicle.next_edge is None:
            return gap_in_edge

        next_lane = min(vehicle.lane, len(self._edge_cells[vehicle.next_edge]) - 1)
        next_cells = self._edge_cells[vehicle.next_edge][next_lane]
        for distance, value in enumerate(next_cells):
            if value != 0:
                return gap_in_edge + distance
        return gap_in_edge + len(next_cells)

    def _red_light_gap(self, vehicle: Vehicle) -> int | None:
        traffic_light = self._traffic_lights_by_node.get(vehicle.current_edge[1])
        if traffic_light is None:
            return None
        if traffic_light.state_at(self._step_number) != TrafficLightState.RED:
            return None
        edge_length = len(self._edge_cells[vehicle.current_edge][vehicle.lane])
        return max(0, edge_length - 1 - vehicle.cell_pos)

    def _resolve_lane(self, vehicle: Vehicle, available_lanes: int, gap: int) -> int:
        if self._cellular_model is None or self._config is None or not self._config.enable_lane_changes:
            return vehicle.lane
        if self._topology is None or not self._topology.edges[vehicle.current_edge].allows_lane_change:
            return vehicle.lane
        candidate = self._cellular_model.resolve_lane(vehicle, available_lanes, gap)
        if candidate == vehicle.lane or not 0 <= candidate < available_lanes:
            return vehicle.lane
        current_edge = vehicle.current_edge
        lane_cells = self._edge_cells[current_edge][candidate]
        start = max(0, vehicle.cell_pos - 1)
        end = min(len(lane_cells), vehicle.cell_pos + 2)
        if any(value != 0 for value in lane_cells[start:end]):
            return vehicle.lane
        return candidate

    def _resolve_velocity(
        self,
        vehicle: Vehicle,
        max_velocity: int,
        gap_ahead: int,
        red_light_gap: int | None,
    ) -> int:
        if self._cellular_model is not None and self._config is not None:
            return self._cellular_model.resolve_velocity(
                vehicle=vehicle,
                max_velocity=max_velocity,
                gap_ahead=gap_ahead,
                red_light_gap=red_light_gap,
                random=self._random,
                noise_prob=self._config.noise_prob,
            )
        new_velocity = min(vehicle.velocity + 1, max_velocity, gap_ahead)
        if red_light_gap is not None:
            new_velocity = min(new_velocity, max(0, red_light_gap - 1))
        if self._config is not None and new_velocity > 0 and self._random.random() < self._config.noise_prob:
            new_velocity -= 1
        return new_velocity

    def _first_free_spawn_cell(self, edge_id: EdgeId) -> tuple[int | None, int]:
        for lane, cells in enumerate(self._edge_cells[edge_id]):
            for index, value in enumerate(cells[:3]):
                if value == 0:
                    return lane, index
        return None, 0

    def _build_state(self) -> SimulationState:
        vehicles = [self._build_vehicle_snapshot(vehicle) for vehicle in self._vehicles.values()]
        active_vehicles = sum(1 for vehicle in self._vehicles.values() if vehicle.velocity > 0)
        return SimulationState(
            step_number=self._step_number,
            vehicles=vehicles,
            total_vehicles=len(vehicles),
            active_vehicles=active_vehicles,
            density=self._density(),
            cells=self._build_cell_snapshots(),
            traffic_lights=self._build_traffic_light_snapshots(),
        )

    def _build_metrics(self, speeds: List[int]) -> SimulationMetrics:
        total_vehicles = len(self._vehicles)
        avg_speed_cells = sum(speeds) / len(speeds) if speeds else 0.0
        avg_speed_kph = avg_speed_cells * CELL_SIZE_M * 3.6 / TICK_SECONDS
        stopped = sum(1 for vehicle in self._vehicles.values() if vehicle.velocity == 0)
        congestion_ratio = stopped / total_vehicles if total_vehicles else 0.0
        throughput = self._last_removed * 60.0 / TICK_SECONDS
        return SimulationMetrics(
            step_number=self._step_number,
            total_vehicles=total_vehicles,
            avg_speed_kph=avg_speed_kph,
            density=self._density(),
            throughput_veh_per_min=throughput,
            congestion_ratio=congestion_ratio,
        )

    def _density(self) -> float:
        occupied = sum(
            sum(1 for value in lane_cells if value != 0)
            for edge_lanes in self._edge_cells.values()
            for lane_cells in edge_lanes
        )
        total = sum(
            len(lane_cells)
            for edge_lanes in self._edge_cells.values()
            for lane_cells in edge_lanes
        )
        return occupied / total if total else 0.0

    def _build_vehicle_snapshot(self, vehicle: Vehicle) -> VehicleSnapshot:
        if self._topology is None:
            raise RuntimeError("Simulation model must be reset before building snapshots.")
        edge_data = self._topology.edges[vehicle.current_edge]
        x, y = interpolate_geometry_point(edge_data=edge_data, position=vehicle.cell_pos)
        speed_kph = vehicle.velocity * CELL_SIZE_M * 3.6 / TICK_SECONDS
        return VehicleSnapshot(
            id=vehicle.vid,
            edge=vehicle.current_edge,
            x=x,
            y=y,
            velocity=vehicle.velocity,
            speed_kph=speed_kph,
            wait_ticks=vehicle.wait_ticks,
            lane=vehicle.lane,
            cell_position=vehicle.cell_pos,
            direction=(vehicle.current_edge[0], vehicle.current_edge[1]),
        )

    def _build_cell_snapshots(self) -> List[CellSnapshot]:
        cells: List[CellSnapshot] = []
        for edge_id, edge_lanes in self._edge_cells.items():
            lane_count = len(edge_lanes)
            cell_count = max((len(lane_cells) for lane_cells in edge_lanes), default=0)
            for cell_position in range(cell_count):
                vehicles = [
                    lane_cells[cell_position]
                    for lane_cells in edge_lanes
                    if cell_position < len(lane_cells) and lane_cells[cell_position] != 0
                ]
                cells.append(
                    CellSnapshot(
                        edge=edge_id,
                        cell_position=cell_position,
                        lane_count=lane_count,
                        direction=(edge_id[0], edge_id[1]),
                        vehicles=vehicles,
                    )
                )
        return cells

    def _build_traffic_light_snapshots(self) -> List[TrafficLightSnapshot]:
        if self._topology is None:
            return []
        snapshots: List[TrafficLightSnapshot] = []
        for traffic_light in self._traffic_lights:
            node = self._topology.nodes.get(traffic_light.node_id)
            if node is None:
                continue
            snapshots.append(
                TrafficLightSnapshot(
                    node_id=traffic_light.node_id,
                    x=node.x,
                    y=node.y,
                    state=traffic_light.state_at(self._step_number),
                    applies_to=traffic_light.applies_to,
                    cycle=traffic_light.cycle,
                )
            )
        return snapshots


def interpolate_geometry_point(edge_data: EdgeData, position: int) -> tuple[float, float]:
    if not edge_data.geometry_points:
        return 0.0, 0.0
    if len(edge_data.geometry_points) == 1:
        return edge_data.geometry_points[0]

    clamped_position = max(0, min(position, edge_data.n_cells - 1))
    target_fraction = (clamped_position + 0.5) / max(1, edge_data.n_cells)
    segments: List[float] = []
    total_length = 0.0
    for start, end in zip(edge_data.geometry_points, edge_data.geometry_points[1:]):
        segment_length = hypot(end[0] - start[0], end[1] - start[1])
        segments.append(segment_length)
        total_length += segment_length

    if total_length == 0:
        return edge_data.geometry_points[0]

    remaining = total_length * target_fraction
    for index, segment_length in enumerate(segments):
        start = edge_data.geometry_points[index]
        end = edge_data.geometry_points[index + 1]
        if remaining <= segment_length:
            ratio = remaining / segment_length if segment_length else 0.0
            return (
                start[0] + (end[0] - start[0]) * ratio,
                start[1] + (end[1] - start[1]) * ratio,
            )
        remaining -= segment_length
    return edge_data.geometry_points[-1]
