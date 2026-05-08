"""Pydantic schemas for the FastAPI transport."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BoundingBoxResponse(BaseModel):
    min_x: float
    max_x: float
    min_y: float
    max_y: float


class GeographicAreaSummaryResponse(BaseModel):
    area_id: str
    name: str
    created_at: datetime
    node_count: int
    edge_count: int
    bbox: BoundingBoxResponse


class TopologyNodeResponse(BaseModel):
    x: float
    y: float
    is_boundary: bool


class TopologyEdgeResponse(BaseModel):
    u: str
    v: str
    key: int
    length_m: float
    speed_kph: float
    travel_time_sec: float
    n_cells: int
    vmax_cells: int
    lanes: int = 1
    lane_source: str = "default"
    allows_lane_change: bool = True
    direction: list[str] | None = None
    geometry_points: list[list[float]]


class TopologyResponse(BaseModel):
    nodes: dict[str, TopologyNodeResponse]
    edges: list[TopologyEdgeResponse]
    bbox: BoundingBoxResponse


class GeographicAreaTopologyResponse(BaseModel):
    area_id: str
    name: str
    created_at: datetime
    node_count: int
    edge_count: int
    topology: TopologyResponse


class CreateSimulationRequest(BaseModel):
    area_id: str = Field(min_length=1)
    initial_vehicles: int = Field(default=25, ge=0)
    max_vehicles: int = Field(default=60, ge=1)
    max_steps: int = Field(default=120, ge=1)
    spawn_rate: float = Field(default=0.2, ge=0.0, le=1.0)
    noise_prob: float = Field(default=0.3, ge=0.0, le=1.0)
    seed: int = 42
    tick_interval_ms: int = Field(default=100, ge=0)
    execution_mode: str = Field(default="continuous", pattern="^(classic|continuous)$")
    default_lanes: int = Field(default=1, ge=1)
    traffic_light_percentage: float = Field(default=0.0, ge=0.0, le=1.0)
    traffic_light_green_steps: int = Field(default=10, ge=1)
    traffic_light_red_steps: int = Field(default=10, ge=0)
    enable_lane_changes: bool = False


class SimulationRecordResponse(BaseModel):
    simulation_id: str
    area_id: str
    status: str
    latest_step: int
    created_at: datetime
    updated_at: datetime
    config: dict[str, Any]


class SimulationStepResponse(BaseModel):
    simulation_id: str
    step_number: int
    metrics: dict[str, Any]
    state: dict[str, Any]
    recorded_at: datetime


class CancelSimulationResponse(BaseModel):
    simulation_id: str
    requested: bool
