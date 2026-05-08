"""Domain entities for geographic areas and NaSch simulations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Iterable, List, Tuple


NodeId = str
EdgeId = Tuple[NodeId, NodeId, int]
Coordinates = Tuple[float, float]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class BoundingBox:
    min_x: float
    max_x: float
    min_y: float
    max_y: float

    def to_dict(self) -> Dict[str, float]:
        return {
            "min_x": self.min_x,
            "max_x": self.max_x,
            "min_y": self.min_y,
            "max_y": self.max_y,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "BoundingBox":
        return cls(
            min_x=float(payload["min_x"]),
            max_x=float(payload["max_x"]),
            min_y=float(payload["min_y"]),
            max_y=float(payload["max_y"]),
        )


@dataclass(frozen=True)
class NodeData:
    x: float
    y: float
    is_boundary: bool

    def to_dict(self) -> Dict[str, Any]:
        return {"x": self.x, "y": self.y, "is_boundary": self.is_boundary}

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "NodeData":
        return cls(
            x=float(payload["x"]),
            y=float(payload["y"]),
            is_boundary=bool(payload.get("is_boundary", False)),
        )


@dataclass(frozen=True)
class EdgeData:
    length_m: float
    speed_kph: float
    travel_time_sec: float
    n_cells: int
    vmax_cells: int
    geometry_points: List[Coordinates]
    lanes: int = 1
    lane_source: str = "default"
    allows_lane_change: bool = True

    def to_dict(self, edge_id: EdgeId) -> Dict[str, Any]:
        return {
            "u": edge_id[0],
            "v": edge_id[1],
            "key": edge_id[2],
            "length_m": self.length_m,
            "speed_kph": self.speed_kph,
            "travel_time_sec": self.travel_time_sec,
            "n_cells": self.n_cells,
            "vmax_cells": self.vmax_cells,
            "lanes": self.lanes,
            "lane_source": self.lane_source,
            "allows_lane_change": self.allows_lane_change,
            "direction": [edge_id[0], edge_id[1]],
            "geometry_points": [list(point) for point in self.geometry_points],
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "EdgeData":
        return cls(
            length_m=float(payload["length_m"]),
            speed_kph=float(payload["speed_kph"]),
            travel_time_sec=float(payload["travel_time_sec"]),
            n_cells=int(payload["n_cells"]),
            vmax_cells=int(payload["vmax_cells"]),
            geometry_points=[(float(x), float(y)) for x, y in payload["geometry_points"]],
            lanes=max(1, int(payload.get("lanes", 1))),
            lane_source=str(payload.get("lane_source", "default")),
            allows_lane_change=bool(payload.get("allows_lane_change", True)),
        )


@dataclass(frozen=True)
class TopologyData:
    nodes: Dict[NodeId, NodeData]
    edges: Dict[EdgeId, EdgeData]
    bbox: BoundingBox

    def outgoing_edges(self) -> Dict[NodeId, List[EdgeId]]:
        adjacency: Dict[NodeId, List[EdgeId]] = {node_id: [] for node_id in self.nodes}
        for edge_id in self.edges:
            adjacency.setdefault(edge_id[0], []).append(edge_id)
        return adjacency

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": {node_id: data.to_dict() for node_id, data in self.nodes.items()},
            "edges": [edge.to_dict(edge_id) for edge_id, edge in self.edges.items()],
            "bbox": self.bbox.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "TopologyData":
        nodes = {node_id: NodeData.from_dict(node) for node_id, node in payload["nodes"].items()}
        edges: Dict[EdgeId, EdgeData] = {}
        for edge_payload in payload["edges"]:
            edge_id: EdgeId = (
                str(edge_payload["u"]),
                str(edge_payload["v"]),
                int(edge_payload["key"]),
            )
            edges[edge_id] = EdgeData.from_dict(edge_payload)
        return cls(nodes=nodes, edges=edges, bbox=BoundingBox.from_dict(payload["bbox"]))


@dataclass(frozen=True)
class GeographicArea:
    area_id: str
    name: str
    topology: TopologyData
    created_at: datetime = field(default_factory=utc_now)
    schema_version: int = 2

    @property
    def node_count(self) -> int:
        return len(self.topology.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.topology.edges)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "area_id": self.area_id,
            "name": self.name,
            "created_at": self.created_at,
            "schema_version": self.schema_version,
            "topology": self.topology.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "GeographicArea":
        return cls(
            area_id=str(payload["area_id"]),
            name=str(payload["name"]),
            created_at=payload.get("created_at") or utc_now(),
            schema_version=int(payload.get("schema_version", 1)),
            topology=TopologyData.from_dict(payload["topology"]),
        )


class SimulationStatus(str, Enum):
    RUNNING = "running"
    FINISHED = "finished"
    CANCELLED = "cancelled"


class SimulationExecutionMode(str, Enum):
    CLASSIC = "classic"
    CONTINUOUS = "continuous"


class TrafficLightState(str, Enum):
    GREEN = "green"
    RED = "red"


@dataclass(frozen=True)
class TrafficLightCycle:
    green_steps: int
    red_steps: int

    def state_at(self, step_number: int) -> TrafficLightState:
        if self.red_steps <= 0:
            return TrafficLightState.GREEN
        total = max(1, self.green_steps + self.red_steps)
        position = step_number % total
        if position < self.green_steps:
            return TrafficLightState.GREEN
        return TrafficLightState.RED

    def to_dict(self) -> Dict[str, int]:
        return {"green_steps": self.green_steps, "red_steps": self.red_steps}

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "TrafficLightCycle":
        return cls(
            green_steps=max(1, int(payload.get("green_steps", 10))),
            red_steps=max(0, int(payload.get("red_steps", 10))),
        )


@dataclass(frozen=True)
class TrafficLight:
    node_id: NodeId
    cycle: TrafficLightCycle
    applies_to: List[NodeId]

    def state_at(self, step_number: int) -> TrafficLightState:
        return self.cycle.state_at(step_number)

    def to_dict(self, step_number: int | None = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "node_id": self.node_id,
            "applies_to": list(self.applies_to),
            "cycle": self.cycle.to_dict(),
        }
        if step_number is not None:
            payload["state"] = self.state_at(step_number).value
        return payload

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "TrafficLight":
        return cls(
            node_id=str(payload["node_id"]),
            applies_to=[str(node_id) for node_id in payload.get("applies_to", [])],
            cycle=TrafficLightCycle.from_dict(payload.get("cycle", {})),
        )


@dataclass(frozen=True)
class SimulationConfig:
    initial_vehicles: int
    max_vehicles: int
    max_steps: int
    spawn_rate: float
    noise_prob: float
    seed: int
    tick_interval_ms: int
    execution_mode: SimulationExecutionMode = SimulationExecutionMode.CONTINUOUS
    default_lanes: int = 1
    traffic_light_percentage: float = 0.0
    traffic_light_green_steps: int = 10
    traffic_light_red_steps: int = 10
    enable_lane_changes: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "initial_vehicles": self.initial_vehicles,
            "max_vehicles": self.max_vehicles,
            "max_steps": self.max_steps,
            "spawn_rate": self.spawn_rate,
            "noise_prob": self.noise_prob,
            "seed": self.seed,
            "tick_interval_ms": self.tick_interval_ms,
            "execution_mode": self.execution_mode.value,
            "default_lanes": self.default_lanes,
            "traffic_light_percentage": self.traffic_light_percentage,
            "traffic_light_green_steps": self.traffic_light_green_steps,
            "traffic_light_red_steps": self.traffic_light_red_steps,
            "enable_lane_changes": self.enable_lane_changes,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "SimulationConfig":
        return cls(
            initial_vehicles=int(payload["initial_vehicles"]),
            max_vehicles=int(payload["max_vehicles"]),
            max_steps=int(payload["max_steps"]),
            spawn_rate=float(payload["spawn_rate"]),
            noise_prob=float(payload["noise_prob"]),
            seed=int(payload["seed"]),
            tick_interval_ms=int(payload["tick_interval_ms"]),
            execution_mode=SimulationExecutionMode(
                payload.get("execution_mode", SimulationExecutionMode.CONTINUOUS.value)
            ),
            default_lanes=max(1, int(payload.get("default_lanes", 1))),
            traffic_light_percentage=float(payload.get("traffic_light_percentage", 0.0)),
            traffic_light_green_steps=max(1, int(payload.get("traffic_light_green_steps", 10))),
            traffic_light_red_steps=max(0, int(payload.get("traffic_light_red_steps", 10))),
            enable_lane_changes=bool(payload.get("enable_lane_changes", False)),
        )


@dataclass
class Vehicle:
    vid: int
    route: List[EdgeId]
    edge_idx: int = 0
    cell_pos: int = 0
    velocity: int = 0
    lane: int = 0
    distance_traveled_m: float = 0.0
    wait_ticks: int = 0

    @property
    def current_edge(self) -> EdgeId:
        return self.route[self.edge_idx]

    @property
    def next_edge(self) -> EdgeId | None:
        next_index = self.edge_idx + 1
        if next_index >= len(self.route):
            return None
        return self.route[next_index]


@dataclass(frozen=True)
class VehicleSnapshot:
    id: int
    edge: EdgeId
    x: float
    y: float
    velocity: int
    speed_kph: float
    wait_ticks: int
    lane: int = 0
    cell_position: int = 0
    direction: Tuple[NodeId, NodeId] | None = None
    is_changing_lane: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "edge": list(self.edge),
            "x": self.x,
            "y": self.y,
            "velocity": self.velocity,
            "speed_kph": self.speed_kph,
            "wait_ticks": self.wait_ticks,
            "lane": self.lane,
            "cell_position": self.cell_position,
            "direction": list(self.direction or (self.edge[0], self.edge[1])),
            "is_changing_lane": self.is_changing_lane,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "VehicleSnapshot":
        return cls(
            id=int(payload["id"]),
            edge=(str(payload["edge"][0]), str(payload["edge"][1]), int(payload["edge"][2])),
            x=float(payload["x"]),
            y=float(payload["y"]),
            velocity=int(payload["velocity"]),
            speed_kph=float(payload["speed_kph"]),
            wait_ticks=int(payload["wait_ticks"]),
            lane=int(payload.get("lane", 0)),
            cell_position=int(payload.get("cell_position", 0)),
            direction=(
                str(payload.get("direction", payload["edge"])[0]),
                str(payload.get("direction", payload["edge"])[1]),
            ),
            is_changing_lane=bool(payload.get("is_changing_lane", False)),
        )


@dataclass(frozen=True)
class CellSnapshot:
    edge: EdgeId
    cell_position: int
    lane_count: int
    direction: Tuple[NodeId, NodeId]
    vehicles: List[int]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "edge": list(self.edge),
            "cell_position": self.cell_position,
            "lane_count": self.lane_count,
            "direction": list(self.direction),
            "vehicles": list(self.vehicles),
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "CellSnapshot":
        edge = (str(payload["edge"][0]), str(payload["edge"][1]), int(payload["edge"][2]))
        direction = payload.get("direction", payload["edge"])
        return cls(
            edge=edge,
            cell_position=int(payload["cell_position"]),
            lane_count=max(1, int(payload["lane_count"])),
            direction=(str(direction[0]), str(direction[1])),
            vehicles=[int(vehicle_id) for vehicle_id in payload.get("vehicles", [])],
        )


@dataclass(frozen=True)
class TrafficLightSnapshot:
    node_id: NodeId
    x: float
    y: float
    state: TrafficLightState
    applies_to: List[NodeId]
    cycle: TrafficLightCycle

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "x": self.x,
            "y": self.y,
            "state": self.state.value,
            "applies_to": list(self.applies_to),
            "cycle": self.cycle.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "TrafficLightSnapshot":
        return cls(
            node_id=str(payload["node_id"]),
            x=float(payload["x"]),
            y=float(payload["y"]),
            state=TrafficLightState(payload["state"]),
            applies_to=[str(node_id) for node_id in payload.get("applies_to", [])],
            cycle=TrafficLightCycle.from_dict(payload.get("cycle", {})),
        )


@dataclass(frozen=True)
class SimulationState:
    step_number: int
    vehicles: List[VehicleSnapshot]
    total_vehicles: int
    active_vehicles: int
    density: float
    cells: List[CellSnapshot] = field(default_factory=list)
    traffic_lights: List[TrafficLightSnapshot] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_number": self.step_number,
            "vehicles": [vehicle.to_dict() for vehicle in self.vehicles],
            "total_vehicles": self.total_vehicles,
            "active_vehicles": self.active_vehicles,
            "density": self.density,
            "cells": [cell.to_dict() for cell in self.cells],
            "traffic_lights": [traffic_light.to_dict() for traffic_light in self.traffic_lights],
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "SimulationState":
        return cls(
            step_number=int(payload["step_number"]),
            vehicles=[VehicleSnapshot.from_dict(vehicle) for vehicle in payload["vehicles"]],
            total_vehicles=int(payload["total_vehicles"]),
            active_vehicles=int(payload["active_vehicles"]),
            density=float(payload["density"]),
            cells=[CellSnapshot.from_dict(cell) for cell in payload.get("cells", [])],
            traffic_lights=[
                TrafficLightSnapshot.from_dict(traffic_light)
                for traffic_light in payload.get("traffic_lights", [])
            ],
        )


@dataclass(frozen=True)
class SimulationMetrics:
    step_number: int
    total_vehicles: int
    avg_speed_kph: float
    density: float
    throughput_veh_per_min: float
    congestion_ratio: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_number": self.step_number,
            "total_vehicles": self.total_vehicles,
            "avg_speed_kph": self.avg_speed_kph,
            "density": self.density,
            "throughput_veh_per_min": self.throughput_veh_per_min,
            "congestion_ratio": self.congestion_ratio,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "SimulationMetrics":
        return cls(
            step_number=int(payload["step_number"]),
            total_vehicles=int(payload["total_vehicles"]),
            avg_speed_kph=float(payload["avg_speed_kph"]),
            density=float(payload["density"]),
            throughput_veh_per_min=float(payload["throughput_veh_per_min"]),
            congestion_ratio=float(payload["congestion_ratio"]),
        )


@dataclass(frozen=True)
class SimulationRecord:
    simulation_id: str
    area_id: str
    status: SimulationStatus
    config: SimulationConfig
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    latest_step: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "simulation_id": self.simulation_id,
            "area_id": self.area_id,
            "status": self.status.value,
            "config": self.config.to_dict(),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "latest_step": self.latest_step,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "SimulationRecord":
        return cls(
            simulation_id=str(payload["simulation_id"]),
            area_id=str(payload["area_id"]),
            status=SimulationStatus(payload["status"]),
            config=SimulationConfig.from_dict(payload["config"]),
            created_at=payload.get("created_at") or utc_now(),
            updated_at=payload.get("updated_at") or utc_now(),
            latest_step=int(payload.get("latest_step", 0)),
        )


@dataclass(frozen=True)
class SimulationStep:
    simulation_id: str
    step_number: int
    metrics: SimulationMetrics
    state: SimulationState
    recorded_at: datetime = field(default_factory=utc_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "simulation_id": self.simulation_id,
            "step_number": self.step_number,
            "metrics": self.metrics.to_dict(),
            "state": self.state.to_dict(),
            "recorded_at": self.recorded_at,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "SimulationStep":
        return cls(
            simulation_id=str(payload["simulation_id"]),
            step_number=int(payload["step_number"]),
            metrics=SimulationMetrics.from_dict(payload["metrics"]),
            state=SimulationState.from_dict(payload["state"]),
            recorded_at=payload.get("recorded_at") or utc_now(),
        )


def count_boundary_nodes(nodes: Iterable[NodeData]) -> int:
    return sum(1 for node in nodes if node.is_boundary)
