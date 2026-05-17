"""Tests for blocked lanes functionality."""

from src.traffic_engine.domain.models import (
    BoundingBox,
    EdgeData,
    EdgeId,
    GeographicArea,
    NodeData,
    SimulationConfig,
    TopologyData,
    SimulationExecutionMode,
)
from src.traffic_engine.domain.simulation import NaSchSimulationModel


def test_blocked_lanes_in_config():
    """Test that blocked_lanes are stored in SimulationConfig."""
    blocked = {("A", "B", 0): [0, 1], ("B", "C", 0): [2]}
    config = SimulationConfig(
        initial_vehicles=10,
        max_vehicles=20,
        max_steps=100,
        spawn_rate=0.2,
        noise_prob=0.1,
        seed=42,
        tick_interval_ms=100,
        blocked_lanes=blocked,
    )
    assert config.blocked_lanes == blocked


def test_blocked_lanes_to_dict():
    """Test serialization of blocked_lanes."""
    blocked = {("A", "B", 0): [0, 1], ("B", "C", 0): [2]}
    config = SimulationConfig(
        initial_vehicles=10,
        max_vehicles=20,
        max_steps=100,
        spawn_rate=0.2,
        noise_prob=0.1,
        seed=42,
        tick_interval_ms=100,
        blocked_lanes=blocked,
    )
    d = config.to_dict()
    assert "blocked_lanes" in d
    assert d["blocked_lanes"]["A-B-0"] == [0, 1]
    assert d["blocked_lanes"]["B-C-0"] == [2]


def test_blocked_lanes_from_dict():
    """Test deserialization of blocked_lanes."""
    payload = {
        "initial_vehicles": 10,
        "max_vehicles": 20,
        "max_steps": 100,
        "spawn_rate": 0.2,
        "noise_prob": 0.1,
        "seed": 42,
        "tick_interval_ms": 100,
        "blocked_lanes": {"A-B-0": [0, 1], "B-C-0": [2]},
    }
    config = SimulationConfig.from_dict(payload)
    assert ("A", "B", 0) in config.blocked_lanes
    assert config.blocked_lanes[("A", "B", 0)] == [0, 1]
    assert config.blocked_lanes[("B", "C", 0)] == [2]


def test_nasch_model_respects_blocked_lanes():
    """Test that NaSchSimulationModel respects blocked_lanes during spawn."""
    # Create a simple topology
    nodes = {
        "A": NodeData(x=0.0, y=0.0, is_boundary=True),
        "B": NodeData(x=1.0, y=0.0, is_boundary=False),
    }
    edges = {
        ("A", "B", 0): EdgeData(
            length_m=1000.0,
            speed_kph=60.0,
            travel_time_sec=60.0,
            n_cells=100,
            vmax_cells=5,
            geometry_points=[(0.0, 0.0), (1.0, 0.0)],
            lanes=2,
        ),
    }
    topology = TopologyData(
        nodes=nodes,
        edges=edges,
        bbox=BoundingBox(min_x=0.0, max_x=1.0, min_y=0.0, max_y=0.0),
    )

    # Create config with lane 0 blocked
    config = SimulationConfig(
        initial_vehicles=5,
        max_vehicles=10,
        max_steps=10,
        spawn_rate=0.2,
        noise_prob=0.1,
        seed=42,
        tick_interval_ms=100,
        default_lanes=2,
        blocked_lanes={("A", "B", 0): [0]},
    )

    model = NaSchSimulationModel(seed=42)
    state = model.reset(topology=topology, config=config)

    # Verify that vehicles were spawned only in lane 1 (lane 0 is blocked)
    for vehicle in state.vehicles:
        if vehicle.edge == ("A", "B", 0):
            assert vehicle.lane == 1, f"Vehicle in edge ('A', 'B', 0) should be in lane 1, got {vehicle.lane}"


if __name__ == "__main__":
    test_blocked_lanes_in_config()
    test_blocked_lanes_to_dict()
    test_blocked_lanes_from_dict()
    test_nasch_model_respects_blocked_lanes()
    print("All tests passed!")
