"""Unified test suite for blocked lanes functionality and routing constraints."""

import pytest
from traffic_engine.domain.models import (
    BoundingBox,
    EdgeData,
    EdgeId,
    GeographicArea,
    NodeData,
    SimulationConfig,
    TopologyData,
    SimulationExecutionMode,
)
from traffic_engine.domain.simulation import NaSchSimulationModel


# ==============================================================================
# 1. BASIC CONFIGURATION & SERIALIZATION TESTS
# ==============================================================================

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
    assert d["blocked_lanes"]["A|B|0"] == [0, 1]
    assert d["blocked_lanes"]["B|C|0"] == [2]


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

    for vehicle in state.vehicles:
        if vehicle.edge == ("A", "B", 0):
            assert vehicle.lane == 1, f"Vehicle in edge ('A', 'B', 0) should be in lane 1, got {vehicle.lane}"


# ==============================================================================
# 2. INTEGRATION TESTS WITH REALISTIC FLOW & FORMATS
# ==============================================================================

def test_realistic_blocked_lanes_scenario():
    """Simulates a realistic scenario: 3-lane highway, middle lane blocked, vehicles adapt."""
    nodes = {
        "A": NodeData(x=0.0, y=0.0, is_boundary=True),
        "B": NodeData(x=1.0, y=0.0, is_boundary=False),
        "C": NodeData(x=2.0, y=0.0, is_boundary=False),
    }
    edges = {
        ("A", "B", 0): EdgeData(
            length_m=1000.0,
            speed_kph=80.0,
            travel_time_sec=45.0,
            n_cells=100,
            vmax_cells=6,
            geometry_points=[(0.0, 0.0), (1.0, 0.0)],
            lanes=3,
        ),
        ("B", "C", 0): EdgeData(
            length_m=1000.0,
            speed_kph=80.0,
            travel_time_sec=45.0,
            n_cells=100,
            vmax_cells=6,
            geometry_points=[(1.0, 0.0), (2.0, 0.0)],
            lanes=3,
        ),
    }
    topology = TopologyData(
        nodes=nodes,
        edges=edges,
        bbox=BoundingBox(min_x=0.0, max_x=2.0, min_y=0.0, max_y=0.0),
    )

    blocked_lanes = {("B", "C", 0): [1]}

    config = SimulationConfig(
        initial_vehicles=15,
        max_vehicles=30,
        max_steps=100,
        spawn_rate=0.15,
        noise_prob=0.2,
        seed=42,
        tick_interval_ms=100,
        default_lanes=3,
        blocked_lanes=blocked_lanes,
    )

    model = NaSchSimulationModel(seed=42)
    state = model.reset(topology=topology, config=config)

    vehicles_in_blocked_lane = 0

    for step in range(100):
        state, metrics, _, done = model.step()

        for vehicle in state.vehicles:
            edge = vehicle.edge
            if edge in blocked_lanes:
                blocked_lanes_for_edge = blocked_lanes[edge]
                if vehicle.lane in blocked_lanes_for_edge:
                    vehicles_in_blocked_lane += 1

    assert vehicles_in_blocked_lane == 0, (
        f"Found {vehicles_in_blocked_lane} instances of vehicles in blocked lanes."
    )


def test_blocked_lane_count_display():
    """Test that config.blocked_lanes can be properly reported to UI."""
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
            lanes=4,
        ),
    }
    topology = TopologyData(
        nodes=nodes,
        edges=edges,
        bbox=BoundingBox(min_x=0.0, max_x=1.0, min_y=0.0, max_y=0.0),
    )

    blocked_lanes = {("A", "B", 0): [0, 2, 3]}

    config = SimulationConfig(
        initial_vehicles=20,
        max_vehicles=40,
        max_steps=50,
        spawn_rate=0.2,
        noise_prob=0.1,
        seed=42,
        tick_interval_ms=100,
        default_lanes=4,
        blocked_lanes=blocked_lanes,
    )

    config_dict = config.to_dict()
    assert "blocked_lanes" in config_dict
    assert "A|B|0" in config_dict["blocked_lanes"]
    assert config_dict["blocked_lanes"]["A|B|0"] == [0, 2, 3]

    total_blocked = sum(len(lanes) for lanes in blocked_lanes.values())
    assert total_blocked == 3


# ==============================================================================
# 3. MOVEMENT & INTER-EDGE TRAVERSAL TESTS
# ==============================================================================

def test_vehicle_avoids_blocked_lane_when_spawning():
    """Test that vehicles spawn only in non-blocked lanes."""
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
            lanes=3,
        ),
    }
    topology = TopologyData(
        nodes=nodes,
        edges=edges,
        bbox=BoundingBox(min_x=0.0, max_x=1.0, min_y=0.0, max_y=0.0),
    )

    config = SimulationConfig(
        initial_vehicles=10,
        max_vehicles=20,
        max_steps=10,
        spawn_rate=0.2,
        noise_prob=0.0,
        seed=42,
        tick_interval_ms=100,
        default_lanes=3,
        blocked_lanes={("A", "B", 0): [0, 2]},
    )

    model = NaSchSimulationModel(seed=42)
    state = model.reset(topology=topology, config=config)

    for vehicle in state.vehicles:
        if vehicle.edge == ("A", "B", 0):
            assert vehicle.lane == 1, f"Expected vehicle in lane 1, got {vehicle.lane}"


def test_vehicle_changes_lane_when_blocked():
    """Test that vehicles move to available lanes when their current lane is blocked."""
    nodes = {
        "A": NodeData(x=0.0, y=0.0, is_boundary=True),
        "B": NodeData(x=1.0, y=0.0, is_boundary=False),
        "C": NodeData(x=2.0, y=0.0, is_boundary=False),
    }
    edges = {
        ("A", "B", 0): EdgeData(
            length_m=500.0,
            speed_kph=60.0,
            travel_time_sec=30.0,
            n_cells=50,
            vmax_cells=5,
            geometry_points=[(0.0, 0.0), (1.0, 0.0)],
            lanes=2,
            allows_lane_change=False,
        ),
        ("B", "C", 0): EdgeData(
            length_m=500.0,
            speed_kph=60.0,
            travel_time_sec=30.0,
            n_cells=50,
            vmax_cells=5,
            geometry_points=[(1.0, 0.0), (2.0, 0.0)],
            lanes=2,
        ),
    }
    topology = TopologyData(
        nodes=nodes,
        edges=edges,
        bbox=BoundingBox(min_x=0.0, max_x=2.0, min_y=0.0, max_y=0.0),
    )

    config = SimulationConfig(
        initial_vehicles=3,
        max_vehicles=10,
        max_steps=50,
        spawn_rate=0.0,
        noise_prob=0.0,
        seed=42,
        tick_interval_ms=100,
        default_lanes=2,
        blocked_lanes={("B", "C", 0): [0]},
    )

    model = NaSchSimulationModel(seed=42)
    state = model.reset(topology=topology, config=config)

    for _ in range(30):
        state, metrics, _, done = model.step()
        for vehicle in state.vehicles:
            blocked_lanes = config.blocked_lanes.get(vehicle.edge, [])
            if blocked_lanes:
                assert vehicle.lane not in blocked_lanes, (
                    f"Vehicle {vehicle.id} is in blocked lane {vehicle.lane} on edge {vehicle.edge}"
                )


def test_all_lanes_blocked_vehicle_stays_put():
    """Test that if all lanes are blocked on next edge, vehicle cannot proceed."""
    nodes = {
        "A": NodeData(x=0.0, y=0.0, is_boundary=True),
        "B": NodeData(x=1.0, y=0.0, is_boundary=False),
        "C": NodeData(x=2.0, y=0.0, is_boundary=False),
    }
    edges = {
        ("A", "B", 0): EdgeData(
            length_m=100.0,
            speed_kph=60.0,
            travel_time_sec=6.0,
            n_cells=10,
            vmax_cells=5,
            geometry_points=[(0.0, 0.0), (1.0, 0.0)],
            lanes=1,
        ),
        ("B", "C", 0): EdgeData(
            length_m=500.0,
            speed_kph=60.0,
            travel_time_sec=30.0,
            n_cells=50,
            vmax_cells=5,
            geometry_points=[(1.0, 0.0), (2.0, 0.0)],
            lanes=1,
        ),
    }
    topology = TopologyData(
        nodes=nodes,
        edges=edges,
        bbox=BoundingBox(min_x=0.0, max_x=2.0, min_y=0.0, max_y=0.0),
    )

    config = SimulationConfig(
        initial_vehicles=1,
        max_vehicles=10,
        max_steps=100,
        spawn_rate=0.0,
        noise_prob=0.0,
        seed=42,
        tick_interval_ms=100,
        default_lanes=1,
        blocked_lanes={("B", "C", 0): [0]},
    )

    model = NaSchSimulationModel(seed=42)
    state = model.reset(topology=topology, config=config)

    for step in range(100):
        state, metrics, _, done = model.step()
        for vehicle in state.vehicles:
            assert vehicle.edge != ("B", "C", 0), (
                f"Vehicle should not be on fully blocked edge B->C at step {step}"
            )


def test_moving_vehicle_stops_when_all_lanes_blocked_mid_edge():
    """A vehicle already on an edge where all lanes get blocked must be expelled immediately."""
    nodes = {
        "A": NodeData(x=0.0, y=0.0, is_boundary=True),
        "B": NodeData(x=1.0, y=0.0, is_boundary=True),
    }
    edges = {
        ("A", "B", 0): EdgeData(
            length_m=500.0,
            speed_kph=60.0,
            travel_time_sec=30.0,
            n_cells=50,
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

    config = SimulationConfig(
        initial_vehicles=2,
        max_vehicles=5,
        max_steps=200,
        spawn_rate=0.0,
        noise_prob=0.0,
        seed=42,
        tick_interval_ms=100,
        default_lanes=2,
        blocked_lanes={},
    )
    model = NaSchSimulationModel(seed=42)
    model.reset(topology=topology, config=config)

    for _ in range(5):
        state, _, _, _ = model.step()

    assert any(v.velocity > 0 for v in state.vehicles)
    vehicles_on_edge = [v for v in state.vehicles if v.edge == ("A", "B", 0)]
    assert vehicles_on_edge

    model._blocked_lanes = {("A", "B", 0): [0, 1]}
    state, _, _, _ = model.step()

    still_on_blocked = [v for v in state.vehicles if v.edge == ("A", "B", 0)]
    assert not still_on_blocked


def test_gap_ahead_uses_effective_lane_on_next_edge():
    """_gap_ahead must respect the lane the vehicle will actually use, taking blocks into account."""
    nodes = {
        "A": NodeData(x=0.0, y=0.0, is_boundary=True),
        "B": NodeData(x=0.5, y=0.0, is_boundary=False),
        "C": NodeData(x=1.0, y=0.0, is_boundary=True),
    }
    edges = {
        ("A", "B", 0): EdgeData(
            length_m=500.0,
            speed_kph=60.0,
            travel_time_sec=30.0,
            n_cells=50,
            vmax_cells=5,
            geometry_points=[(0.0, 0.0), (0.5, 0.0)],
            lanes=1,
        ),
        ("B", "C", 0): EdgeData(
            length_m=500.0,
            speed_kph=60.0,
            travel_time_sec=30.0,
            n_cells=50,
            vmax_cells=5,
            geometry_points=[(0.5, 0.0), (1.0, 0.0)],
            lanes=2,
        ),
    }
    topology = TopologyData(
        nodes=nodes,
        edges=edges,
        bbox=BoundingBox(min_x=0.0, max_x=1.0, min_y=0.0, max_y=0.0),
    )

    config = SimulationConfig(
        initial_vehicles=1,
        max_vehicles=1,
        max_steps=200,
        spawn_rate=0.0,
        noise_prob=0.0,
        seed=42,
        tick_interval_ms=100,
        default_lanes=2,
        blocked_lanes={("B", "C", 0): [0]},
    )
    model = NaSchSimulationModel(seed=42)
    model.reset(topology=topology, config=config)

    obstacle_pos = 3
    model._edge_cells[("B", "C", 0)][1][obstacle_pos] = 999

    vehicle = list(model._vehicles.values())[0]
    assert vehicle.lane == 0

    gap = model._gap_ahead(vehicle)
    expected_max_gap = 52 + 5

    assert gap <= expected_max_gap


# ==============================================================================
# 4. EDGE KEY FORMAT TESTING (UNAMBIGUOUS PIPES)
# ==============================================================================

def test_pipe_separated_format_is_unambiguous():
    """Verify that pipe-separated format "u|v|k" has no ambiguity with dashes."""
    test_cases = [
        ("a|b|0", "a", "b", 0),
        ("a-b|c|0", "a-b", "c", 0),
        ("node-1|node-2|1", "node-1", "node-2", 1),
        ("CdMx-N|CdMx-S|1", "CdMx-N", "CdMx-S", 1),
        ("x-y-z|w-q|2", "x-y-z", "w-q", 2),
    ]

    for client_format, exp_u, exp_v, exp_k in test_cases:
        parts = client_format.split("|")
        assert len(parts) == 3
        u, v, k_str = parts
        k = int(k_str)
        assert u == exp_u
        assert v == exp_v
        assert k == exp_k


def test_blocked_lanes_format_roundtrip_unambiguous():
    """Verify pipe-separated format roundtrip behaves flawlessly."""
    client_keys = [
        "node-1|node-2|0",
        "CdMx-N|CdMx-S|1",
        "a-b-c|d-e|2",
        "x|y|0",
    ]

    for client_key in client_keys:
        parts = client_key.split("|")
        u, v, k_str = parts
        reconstructed_key = f"{u}|{v}|{k_str}"
        assert reconstructed_key == client_key


def test_pipe_format_handles_all_edge_cases():
    """Verify that pipe format handles all possible node name patterns."""
    edge_cases = [
        "node-1-with-many-dashes|node-2-with-many-dashes|0",
        "a|b|0",
        "node-1-2-3-4-5|node-6-7-8|1",
        "CdMx-NORTE|CdMx-SUR|2",
        "highway-I-25|highway-I-70|0",
    ]

    for edge_format in edge_cases:
        parts = edge_format.split("|")
        assert len(parts) == 3
        u, v, k_str = parts
        assert u
        assert v
        assert k_str.isdigit()


# ==============================================================================
# 5. FULLY BLOCKED EDGES DETECTION & MISMATCHED LANES
# ==============================================================================

def test_fully_blocked_edges_with_mismatched_lane_counts():
    """Verify detection when physical lanes count differs from default configuration."""
    nodes = {
        "A": NodeData(x=0.0, y=0.0, is_boundary=True),
        "B": NodeData(x=1.0, y=0.0, is_boundary=True),
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
    config = SimulationConfig(
        initial_vehicles=10,
        max_vehicles=20,
        max_steps=100,
        spawn_rate=0.2,
        noise_prob=0.1,
        seed=42,
        tick_interval_ms=100,
        default_lanes=4,
        blocked_lanes={("A", "B", 0): [0, 1, 2, 3]},
    )
    model = NaSchSimulationModel(seed=42, traffic_lights=[])
    model.reset(topology, config)
    fully_blocked = model._fully_blocked_edges()
    assert ("A", "B", 0) in fully_blocked


def test_partially_blocked_edges_not_detected_as_full():
    """Verify that partial blockage does not trigger a full block detection."""
    nodes = {
        "A": NodeData(x=0.0, y=0.0, is_boundary=True),
        "B": NodeData(x=1.0, y=0.0, is_boundary=True),
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
    config = SimulationConfig(
        initial_vehicles=10,
        max_vehicles=20,
        max_steps=100,
        spawn_rate=0.2,
        noise_prob=0.1,
        seed=42,
        tick_interval_ms=100,
        default_lanes=4,
        blocked_lanes={("A", "B", 0): [0, 1, 2]},
    )
    model = NaSchSimulationModel(seed=42, traffic_lights=[])
    model.reset(topology, config)
    fully_blocked = model._fully_blocked_edges()
    assert ("A", "B", 0) not in fully_blocked


def test_fully_blocked_with_same_lane_counts():
    """Verify basic fully blocked edge detection when lanes equal default."""
    nodes = {
        "A": NodeData(x=0.0, y=0.0, is_boundary=True),
        "B": NodeData(x=1.0, y=0.0, is_boundary=True),
    }
    edges = {
        ("A", "B", 0): EdgeData(
            length_m=1000.0,
            speed_kph=60.0,
            travel_time_sec=60.0,
            n_cells=100,
            vmax_cells=5,
            geometry_points=[(0.0, 0.0), (1.0, 0.0)],
            lanes=3,
        ),
    }
    topology = TopologyData(
        nodes=nodes,
        edges=edges,
        bbox=BoundingBox(min_x=0.0, max_x=1.0, min_y=0.0, max_y=0.0),
    )
    config = SimulationConfig(
        initial_vehicles=10,
        max_vehicles=20,
        max_steps=100,
        spawn_rate=0.2,
        noise_prob=0.1,
        seed=42,
        tick_interval_ms=100,
        default_lanes=3,
        blocked_lanes={("A", "B", 0): [0, 1, 2]},
    )
    model = NaSchSimulationModel(seed=42, traffic_lights=[])
    model.reset(topology, config)
    fully_blocked = model._fully_blocked_edges()
    assert ("A", "B", 0) in fully_blocked


# ==============================================================================
# 6. DYNAMIC ROUTE REPLANNING TESTS
# ==============================================================================

def test_dynamic_route_replanning_on_blocked_edge():
    """Test that a vehicle dynamically replans its route if an upcoming edge is fully blocked."""
    nodes = {
        "A": NodeData(x=0.0, y=0.0, is_boundary=True),
        "B": NodeData(x=1.0, y=0.0, is_boundary=False),
        "C": NodeData(x=2.0, y=0.0, is_boundary=False),
        "D": NodeData(x=3.0, y=0.0, is_boundary=True),
    }
    edges = {
        ("A", "B", 0): EdgeData(
            length_m=100.0,
            speed_kph=60.0,
            travel_time_sec=6.0,
            n_cells=10,
            vmax_cells=2,
            geometry_points=[(0.0, 0.0), (1.0, 0.0)],
            lanes=1,
        ),
        ("B", "C", 0): EdgeData(
            length_m=100.0,
            speed_kph=60.0,
            travel_time_sec=6.0,
            n_cells=10,
            vmax_cells=2,
            geometry_points=[(1.0, 0.0), (2.0, 0.0)],
            lanes=1,
        ),
        ("C", "D", 0): EdgeData(
            length_m=100.0,
            speed_kph=60.0,
            travel_time_sec=6.0,
            n_cells=10,
            vmax_cells=2,
            geometry_points=[(2.0, 0.0), (3.0, 0.0)],
            lanes=1,
        ),
        ("B", "D", 0): EdgeData(
            length_m=150.0,
            speed_kph=60.0,
            travel_time_sec=9.0,
            n_cells=15,
            vmax_cells=2,
            geometry_points=[(1.0, 0.0), (3.0, 0.0)],
            lanes=1,
        ),
    }
    topology = TopologyData(
        nodes=nodes,
        edges=edges,
        bbox=BoundingBox(min_x=0.0, max_x=3.0, min_y=0.0, max_y=0.0),
    )

    config = SimulationConfig(
        initial_vehicles=1,
        max_vehicles=1,
        max_steps=50,
        spawn_rate=0.0,
        noise_prob=0.0,
        seed=42,
        tick_interval_ms=10,
        default_lanes=1,
        blocked_lanes={},
    )

    model = NaSchSimulationModel(seed=42)
    state = model.reset(topology=topology, config=config)

    vehicle = list(model._vehicles.values())[0]
    vehicle.route = [("A", "B", 0), ("B", "C", 0), ("C", "D", 0)]

    assert vehicle.current_edge == ("A", "B", 0)

    model._blocked_lanes = {("B", "C", 0): [0]}

    state, _, _, _ = model.step()

    assert ("B", "C", 0) not in vehicle.route, "Vehicle should have bypassed blocked edge ('B', 'C', 0)"
    assert vehicle.route[-1] == ("B", "D", 0) or vehicle.route[-1][1] == "D", "Vehicle route should still reach destination node D"


# ==============================================================================
# 7. BUILDER INTEGRITY TESTS
# ==============================================================================

def test_builder_retains_blocked_lanes():
    """Verify that SimulationModelBuilder retains the blocked_lanes configuration."""
    from traffic_engine.domain.simulation_builder import SimulationModelBuilder
    from traffic_engine.infrastructure.providers import (
        ShortestPathRouteProvider,
        NagelCellularModel,
    )

    blocked = {("A", "B", 0): [0, 1]}
    base_config = SimulationConfig(
        initial_vehicles=10,
        max_vehicles=20,
        max_steps=100,
        spawn_rate=0.2,
        noise_prob=0.1,
        seed=42,
        tick_interval_ms=100,
        blocked_lanes=blocked,
    )

    builder = (
        SimulationModelBuilder(base_config)
        .with_execution_mode(SimulationExecutionMode.CONTINUOUS)
        .with_route_provider(ShortestPathRouteProvider())
        .with_cellular_model(NagelCellularModel())
    )

    definition = builder.build()
    assert definition.config.blocked_lanes == blocked
