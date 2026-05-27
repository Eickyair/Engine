"""Simulation abstractions and NaSch model implementation."""

from __future__ import annotations

import heapq
from math import hypot
from random import Random
from typing import Any, Dict, List, Protocol

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
    StepVisualization,
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

    def step(self) -> tuple[SimulationState, SimulationMetrics, StepVisualization, bool]:
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
        self._blocked_lanes: Dict[EdgeId, List[int]] = {}
        self._step_number = 0
        self._next_vehicle_id = 1
        self._last_removed = 0
        self._prev_vehicle_positions: Dict[int, tuple[float, float]] = {}

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
        self._blocked_lanes = config.blocked_lanes or {}
        self._step_number = 0
        self._next_vehicle_id = 1
        self._last_removed = 0
        self._prev_vehicle_positions = {}
        self._spawn_until(config.initial_vehicles)
        return self._build_state()

    def step(self) -> tuple[SimulationState, SimulationMetrics, bool]:
        if self._topology is None or self._config is None:
            raise RuntimeError("Simulation model must be reset before stepping.")

        vehicle_ids = list(self._vehicles.keys())
        self._random.shuffle(vehicle_ids)
        finished: List[int] = []
        speeds: List[int] = []
        excluded_edges = self._fully_blocked_edges()

        for vehicle_id in vehicle_ids:
            vehicle = self._vehicles.get(vehicle_id)
            if vehicle is None:
                continue

            # Dynamic rerouting: if any remaining edge in the route is fully blocked, replan
            remaining_route = vehicle.route[vehicle.edge_idx + 1:]
            if any(edge_id in excluded_edges for edge_id in remaining_route):
                self._replan_route(vehicle, excluded_edges)

            current_edge = vehicle.current_edge
            blocked_lanes_on_edge = self._blocked_lanes.get(current_edge, [])

            # If vehicle is in a blocked lane, force a lane change
            if vehicle.lane in blocked_lanes_on_edge:
                available_lanes = len(self._edge_cells[current_edge])
                found_lane = None
                for lane_idx in range(available_lanes):
                    if lane_idx not in blocked_lanes_on_edge:
                        if self._edge_cells[current_edge][lane_idx][vehicle.cell_pos] == 0:
                            found_lane = lane_idx
                            break

                if found_lane is not None:
                    self._edge_cells[current_edge][vehicle.lane][vehicle.cell_pos] = 0
                    vehicle.lane = found_lane
                    self._edge_cells[current_edge][vehicle.lane][vehicle.cell_pos] = vehicle_id
                else:
                    # All lanes blocked or full: expel vehicle
                    self._edge_cells[current_edge][vehicle.lane][vehicle.cell_pos] = 0
                    finished.append(vehicle_id)
                    continue

            vehicle.is_changing_lane = vehicle.lane_change_ticks_remaining > 0
            vehicle.lane_change_ticks_remaining = max(
                0,
                vehicle.lane_change_ticks_remaining - 1,
            )

            current_edge = vehicle.current_edge
            edge_data = self._topology.edges[current_edge]
            gap = self._gap_ahead(vehicle)
            available_lanes = len(self._edge_cells[current_edge])
            target_lane = self._resolve_lane(vehicle, available_lanes, gap)
            if target_lane != vehicle.lane:
                self._edge_cells[current_edge][vehicle.lane][vehicle.cell_pos] = 0
                vehicle.lane = target_lane
                vehicle.is_changing_lane = True
                vehicle.lane_change_ticks_remaining = 3
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
                # If stuck at boundary because next edge is fully blocked, expel vehicle
                if vehicle.next_edge is not None:
                    next_edge = vehicle.next_edge
                    next_blocked = self._blocked_lanes.get(next_edge, [])
                    if next_edge in self._topology.edges:
                        next_edge_data = self._topology.edges[next_edge]
                        next_effective_lanes = max(1, next_edge_data.lanes, self._config.default_lanes)
                        if all(i in next_blocked for i in range(next_effective_lanes)):
                            edge_length = len(self._edge_cells[current_edge][vehicle.lane])
                            if vehicle.cell_pos >= edge_length - 1:
                                self._edge_cells[current_edge][vehicle.lane][vehicle.cell_pos] = 0
                                finished.append(vehicle_id)
                                continue

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
                    blocked_lanes_on_edge = self._blocked_lanes.get(current_edge, [])

                    preferred_lane = min(vehicle.lane, available_lanes - 1)
                    if preferred_lane not in blocked_lanes_on_edge:
                        vehicle.lane = preferred_lane
                    else:
                        found_lane = None
                        for lane_idx in range(available_lanes):
                            if lane_idx not in blocked_lanes_on_edge:
                                found_lane = lane_idx
                                break
                        if found_lane is not None:
                            vehicle.lane = found_lane
                        else:
                            finished.append(vehicle_id)
                            break

                    edge_length = len(self._edge_cells[current_edge][vehicle.lane])
                    target_position = overflow
                else:
                    clamped = min(target_position, edge_length - 1)
                    if self._edge_cells[current_edge][vehicle.lane][clamped] == 0:
                        vehicle.cell_pos = clamped
                        self._edge_cells[current_edge][vehicle.lane][clamped] = vehicle_id
                    else:
                        # Target cell occupied: revert edge_idx
                        vehicle.edge_idx -= 1
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
        current_positions = {v.id: (v.x, v.y) for v in state.vehicles}
        flow_nodes = self._build_flow_nodes(current_positions)
        self._prev_vehicle_positions = current_positions
        metrics = self._build_metrics(speeds=speeds)
        visualization = self._build_visualization(state=state, flow_nodes=flow_nodes)
        done = self._step_number >= self._config.max_steps
        return state, metrics, visualization, done

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

    def _fully_blocked_edges(self) -> set:
        result: set = set()
        if not self._config or not self._topology:
            return result
        for edge_id, blocked_lanes_list in self._blocked_lanes.items():
            if edge_id not in self._topology.edges:
                continue
            edge_data = self._topology.edges[edge_id]
            effective_lanes = max(1, edge_data.lanes, self._config.default_lanes)
            if all(lane_idx in blocked_lanes_list for lane_idx in range(effective_lanes)):
                result.add(edge_id)
        return result

    def _random_route(self) -> List[EdgeId] | None:
        if self._topology is None or not self._boundary_nodes:
            return None

        excluded = self._fully_blocked_edges()

        if self._route_provider is not None:
            try:
                route = self._route_provider.choose_route(
                    self._topology, self._random, excluded_edges=excluded
                )
                if route and not any(edge_id in excluded for edge_id in route):
                    return route
            except Exception:
                pass

        if len(self._boundary_nodes) < 2:
            nodes = list(self._topology.nodes.keys())
        else:
            nodes = self._boundary_nodes

        for _ in range(20):
            origin, destination = self._random.sample(nodes, 2)
            path = self._shortest_edge_path(origin, destination, excluded_edges=excluded)
            if len(path) >= 1:
                return path
        return None

    def _shortest_edge_path(
        self,
        origin: str,
        destination: str,
        excluded_edges: set | None = None,
    ) -> List[EdgeId]:
        if self._topology is None:
            return []

        excluded = excluded_edges or set()
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
                if edge_id in excluded:
                    continue
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

    def _replan_route(self, vehicle: Vehicle, excluded: set) -> bool:
        if self._topology is None:
            return False
        destination = vehicle.route[-1][1]
        current_node = vehicle.current_edge[1]
        if current_node == destination:
            return False
        new_path = self._shortest_edge_path(current_node, destination, excluded_edges=excluded)
        if new_path:
            vehicle.route = vehicle.route[:vehicle.edge_idx + 1] + new_path
            return True
        return False

    def _effective_lane_on_next_edge(self, vehicle: Vehicle) -> int | None:
        """Return the lane the vehicle will occupy on its next edge, respecting blocked lanes.

        Returns None if all lanes on the next edge are blocked.
        """
        next_edge = vehicle.next_edge
        if next_edge is None:
            return None
        available_lanes = len(self._edge_cells[next_edge])
        blocked = self._blocked_lanes.get(next_edge, [])
        preferred = min(vehicle.lane, available_lanes - 1)
        if preferred not in blocked:
            return preferred
        for lane_idx in range(available_lanes):
            if lane_idx not in blocked:
                return lane_idx
        return None

    def _gap_ahead(self, vehicle: Vehicle) -> int:
        current_cells = self._edge_cells[vehicle.current_edge][vehicle.lane]
        position = vehicle.cell_pos

        for distance in range(1, len(current_cells) - position):
            if current_cells[position + distance] != 0:
                return distance - 1

        gap_in_edge = (len(current_cells) - 1) - position
        if vehicle.next_edge is None:
            return gap_in_edge

        next_lane = self._effective_lane_on_next_edge(vehicle)
        if next_lane is None:
            return gap_in_edge
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
        blocked_lanes = self._blocked_lanes.get(vehicle.current_edge, [])
        if candidate in blocked_lanes:
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
        edge_lanes = self._edge_cells[edge_id]
        entry_window = min(3, max((len(cells) for cells in edge_lanes), default=0))
        blocked_lanes = self._blocked_lanes.get(edge_id, [])
        for index in range(entry_window):
            for lane, cells in enumerate(edge_lanes):
                if lane not in blocked_lanes and index < len(cells) and cells[index] == 0:
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

    def _build_visualization(
        self,
        state: SimulationState,
        flow_nodes: List[Dict[str, Any]],
    ) -> StepVisualization:
        heat_density_points = []
        heat_speed_points = []
        flow_edges: Dict[EdgeId, int] = {}
        for vehicle in state.vehicles:
            heat_density_points.append([vehicle.y, vehicle.x, 1.0])
            heat_speed_points.append([vehicle.y, vehicle.x, max(1.0, float(vehicle.speed_kph))])
            flow_edges[vehicle.edge] = flow_edges.get(vehicle.edge, 0) + 1
        return StepVisualization(
            heat_density_points=heat_density_points,
            heat_speed_points=heat_speed_points,
            flow_nodes=flow_nodes,
            flow_edges=[
                {"edge": list(edge_id), "count": count}
                for edge_id, count in flow_edges.items()
            ],
        )

    def _build_flow_nodes(
        self,
        current_positions: Dict[int, tuple[float, float]],
    ) -> List[Dict[str, float]]:
        if self._topology is None:
            return []
        boundary_nodes = [
            node_id for node_id in self._boundary_nodes if node_id in self._topology.nodes
        ]
        if not boundary_nodes:
            return []
        counts: Dict[str, int] = {node_id: 0 for node_id in boundary_nodes}
        prev_ids = set(self._prev_vehicle_positions.keys())
        current_ids = set(current_positions.keys())
        new_ids = current_ids - prev_ids
        gone_ids = prev_ids - current_ids

        candidates: List[tuple[float, float]] = []
        for vid in new_ids:
            pos = current_positions.get(vid)
            if pos:
                candidates.append(pos)
        for vid in gone_ids:
            pos = self._prev_vehicle_positions.get(vid)
            if pos:
                candidates.append(pos)

        for x, y in candidates:
            nearest = self._nearest_boundary_node(x, y, boundary_nodes)
            if nearest is not None:
                counts[nearest] += 1

        return [
            {
                "node_id": node_id,
                "count": counts[node_id],
                "x": float(self._topology.nodes[node_id].x),
                "y": float(self._topology.nodes[node_id].y),
            }
            for node_id in boundary_nodes
        ]

    def _nearest_boundary_node(
        self,
        x: float,
        y: float,
        boundary_nodes: List[str],
    ) -> str | None:
        if self._topology is None:
            return None
        best_node = None
        best_distance = float("inf")
        for node_id in boundary_nodes:
            node = self._topology.nodes.get(node_id)
            if node is None:
                continue
            distance = (node.x - x) ** 2 + (node.y - y) ** 2
            if distance < best_distance:
                best_distance = distance
                best_node = node_id
        return best_node

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
            is_changing_lane=vehicle.is_changing_lane,
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
