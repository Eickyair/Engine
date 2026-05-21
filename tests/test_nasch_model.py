from traffic_engine.domain.models import (
    BoundingBox,
    EdgeData,
    NodeData,
    SimulationConfig,
    SimulationMetrics,
    SimulationState,
    SimulationStep,
    StepVisualization,
    TopologyData,
)
from traffic_engine.domain.simulation import NaSchSimulationModel


def _topology() -> TopologyData:
    return TopologyData(
        nodes={
            "A": NodeData(x=-99.15, y=19.43, is_boundary=True),
            "B": NodeData(x=-99.14, y=19.43, is_boundary=False),
            "C": NodeData(x=-99.13, y=19.43, is_boundary=True),
        },
        edges={
            ("A", "B", 0): EdgeData(
                length_m=75.0,
                speed_kph=30.0,
                travel_time_sec=9.0,
                n_cells=10,
                vmax_cells=2,
                geometry_points=[(-99.15, 19.43), (-99.14, 19.43)],
            ),
            ("B", "C", 0): EdgeData(
                length_m=75.0,
                speed_kph=30.0,
                travel_time_sec=9.0,
                n_cells=10,
                vmax_cells=2,
                geometry_points=[(-99.14, 19.43), (-99.13, 19.43)],
            ),
        },
        bbox=BoundingBox(min_x=-99.15, max_x=-99.13, min_y=19.43, max_y=19.43),
    )


def _config(**overrides) -> SimulationConfig:
    values = dict(
        initial_vehicles=1,
        max_vehicles=2,
        max_steps=3,
        spawn_rate=0.0,
        noise_prob=0.0,
        seed=7,
        tick_interval_ms=0,
    )
    values.update(overrides)
    return SimulationConfig(**values)


def test_nasch_model_reset_and_step_returns_state_and_metrics() -> None:
    model = NaSchSimulationModel(seed=7)
    initial_state = model.reset(topology=_topology(), config=_config())

    state, metrics, visualization, done = model.step()

    assert initial_state.total_vehicles == 1
    assert state.step_number == 1
    assert metrics.step_number == 1
    assert 0.0 <= metrics.density <= 1.0
    assert done is False


def test_step_visualization_contains_one_heat_point_per_vehicle() -> None:
    model = NaSchSimulationModel(seed=7)
    model.reset(topology=_topology(), config=_config(initial_vehicles=1))

    _, _, visualization, _ = model.step()

    assert len(visualization.heat_density_points) == 1
    assert len(visualization.heat_speed_points) == 1
    lat, lon, weight = visualization.heat_density_points[0]
    assert isinstance(lat, float)
    assert isinstance(lon, float)
    assert weight == 1.0


def test_step_visualization_flow_edges_track_edge_occupancy() -> None:
    model = NaSchSimulationModel(seed=7)
    model.reset(topology=_topology(), config=_config(initial_vehicles=1))

    _, _, visualization, _ = model.step()

    assert len(visualization.flow_edges) >= 1
    entry = visualization.flow_edges[0]
    assert "edge" in entry
    assert "count" in entry
    assert entry["count"] >= 1


def test_step_updates_prev_vehicle_positions_after_each_step() -> None:
    model = NaSchSimulationModel(seed=7)
    model.reset(topology=_topology(), config=_config(initial_vehicles=1))

    state, _, _, _ = model.step()

    assert set(model._prev_vehicle_positions.keys()) == {v.id for v in state.vehicles}


def test_simulation_step_to_dict_includes_visualization_key() -> None:
    metrics = SimulationMetrics(
        step_number=1, total_vehicles=0, avg_speed_kph=0.0,
        density=0.0, throughput_veh_per_min=0.0, congestion_ratio=0.0,
    )
    state = SimulationState(
        step_number=1, vehicles=[], total_vehicles=0,
        active_vehicles=0, density=0.0,
    )
    viz = StepVisualization(
        heat_density_points=[[19.43, -99.15, 1.0]],
        heat_speed_points=[[19.43, -99.15, 30.0]],
        flow_nodes=[],
        flow_edges=[],
    )
    step = SimulationStep(
        simulation_id="sim-1", step_number=1,
        metrics=metrics, state=state, visualization=viz,
    )

    d = step.to_dict()

    assert "visualization" in d
    assert d["visualization"]["heat_density_points"] == [[19.43, -99.15, 1.0]]
    assert d["visualization"]["heat_speed_points"] == [[19.43, -99.15, 30.0]]
    assert "heat_density_points" not in d["metrics"]


def test_simulation_step_from_dict_backward_compat_without_visualization() -> None:
    payload = {
        "simulation_id": "sim-1",
        "step_number": 1,
        "metrics": {
            "step_number": 1, "total_vehicles": 0, "avg_speed_kph": 0.0,
            "density": 0.0, "throughput_veh_per_min": 0.0, "congestion_ratio": 0.0,
        },
        "state": {
            "step_number": 1, "vehicles": [], "total_vehicles": 0,
            "active_vehicles": 0, "density": 0.0, "cells": [], "traffic_lights": [],
        },
        # no "visualization" key — simulates old MongoDB documents
    }

    step = SimulationStep.from_dict(payload)

    assert isinstance(step.visualization, StepVisualization)
    assert step.visualization.heat_density_points == []
    assert step.visualization.heat_speed_points == []
    assert step.visualization.flow_nodes == []
    assert step.visualization.flow_edges == []


def test_step_visualization_round_trip() -> None:
    original = StepVisualization(
        heat_density_points=[[19.43, -99.15, 1.0], [19.44, -99.14, 1.0]],
        heat_speed_points=[[19.43, -99.15, 30.0]],
        flow_nodes=[{"node_id": "A", "count": 2, "x": -99.15, "y": 19.43}],
        flow_edges=[{"edge": ["A", "B", 0], "count": 1}],
    )

    restored = StepVisualization.from_dict(original.to_dict())

    assert restored.heat_density_points == original.heat_density_points
    assert restored.heat_speed_points == original.heat_speed_points
    assert restored.flow_nodes == original.flow_nodes
    assert restored.flow_edges == original.flow_edges
