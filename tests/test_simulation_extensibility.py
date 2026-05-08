from random import Random

import networkx as nx
import pytest

from traffic_engine.domain.exceptions import RouteSelectionError, SimulationConfigurationError
from traffic_engine.domain.models import (
    BoundingBox,
    EdgeData,
    NodeData,
    SimulationConfig,
    SimulationExecutionMode,
    TopologyData,
)
from traffic_engine.domain.simulation import NaSchSimulationModel
from traffic_engine.domain.simulation_builder import SimulationModelBuilder
from traffic_engine.infrastructure.providers import (
    NagelCellularModel,
    RandomTrafficLightProvider,
    ShortestPathRouteProvider,
)
from traffic_engine.infrastructure.topology_source import OSMnxGeographicAreaSource


def _intersection_topology() -> TopologyData:
    return TopologyData(
        nodes={
            "A": NodeData(x=0.0, y=0.0, is_boundary=True),
            "B": NodeData(x=1.0, y=0.0, is_boundary=False),
            "C": NodeData(x=2.0, y=0.0, is_boundary=True),
            "D": NodeData(x=1.0, y=1.0, is_boundary=True),
        },
        edges={
            ("A", "B", 0): EdgeData(10.0, 30.0, 1.0, 4, 2, [(0.0, 0.0), (1.0, 0.0)]),
            ("B", "C", 0): EdgeData(10.0, 30.0, 1.0, 4, 2, [(1.0, 0.0), (2.0, 0.0)]),
            ("D", "B", 0): EdgeData(10.0, 30.0, 1.0, 4, 2, [(1.0, 1.0), (1.0, 0.0)]),
        },
        bbox=BoundingBox(min_x=0.0, max_x=2.0, min_y=0.0, max_y=1.0),
    )


def _config(**overrides) -> SimulationConfig:
    values = {
        "initial_vehicles": 1,
        "max_vehicles": 5,
        "max_steps": 3,
        "spawn_rate": 1.0,
        "noise_prob": 0.0,
        "seed": 4,
        "tick_interval_ms": 0,
    }
    values.update(overrides)
    return SimulationConfig(**values)


def test_random_traffic_light_provider_handles_percentages_and_rounding() -> None:
    topology = _intersection_topology()
    provider = RandomTrafficLightProvider(percentage=0.10, seed=1)

    lights = provider.provide(topology, _config(traffic_light_green_steps=3, traffic_light_red_steps=2))

    assert len(lights) == 0
    assert RandomTrafficLightProvider(percentage=1.0).provide(topology, _config())
    assert RandomTrafficLightProvider(percentage=0.0).provide(topology, _config()) == []


def test_route_provider_reports_grid_without_traversable_cells() -> None:
    topology = TopologyData(
        nodes={"A": NodeData(x=0.0, y=0.0, is_boundary=True)},
        edges={},
        bbox=BoundingBox(min_x=0.0, max_x=0.0, min_y=0.0, max_y=0.0),
    )

    with pytest.raises(RouteSelectionError):
        ShortestPathRouteProvider().choose_route(topology, Random(1))


def test_builder_requires_mode_and_validates_lane_configuration() -> None:
    builder = (
        SimulationModelBuilder(_config(default_lanes=1, enable_lane_changes=True))
        .with_route_provider(ShortestPathRouteProvider())
        .with_cellular_model(NagelCellularModel(allow_lane_changes=True))
    )

    with pytest.raises(SimulationConfigurationError):
        builder.build()

    with pytest.raises(SimulationConfigurationError):
        builder.with_execution_mode(SimulationExecutionMode.CONTINUOUS).build()


def test_classic_mode_does_not_spawn_after_initialization_and_emits_ui_payload() -> None:
    topology = _intersection_topology()
    config = _config(
        execution_mode=SimulationExecutionMode.CLASSIC,
        initial_vehicles=1,
        max_vehicles=5,
        spawn_rate=1.0,
        default_lanes=2,
        traffic_light_percentage=1.0,
        traffic_light_green_steps=1,
        traffic_light_red_steps=10,
    )
    traffic_lights = RandomTrafficLightProvider(percentage=1.0, seed=2).provide(topology, config)
    model = NaSchSimulationModel(
        seed=config.seed,
        route_provider=ShortestPathRouteProvider(),
        cellular_model=NagelCellularModel(allow_lane_changes=True),
        traffic_lights=traffic_lights,
    )
    initial_state = model.reset(topology=topology, config=config)

    state, _, _ = model.step()

    assert initial_state.total_vehicles == 1
    assert state.total_vehicles <= 1
    assert state.cells
    assert all(cell.lane_count == 2 for cell in state.cells)
    assert state.traffic_lights
    assert state.vehicles[0].lane >= 0
    assert state.vehicles[0].direction is not None


def test_edge_lane_metadata_round_trips_for_storage() -> None:
    edge = EdgeData(
        length_m=20.0,
        speed_kph=30.0,
        travel_time_sec=2.4,
        n_cells=3,
        vmax_cells=2,
        geometry_points=[(0.0, 0.0), (1.0, 0.0)],
        lanes=3,
        lane_source="lanes",
        allows_lane_change=True,
    )

    restored = EdgeData.from_dict(edge.to_dict(("A", "B", 0)))

    assert restored.lanes == 3
    assert restored.lane_source == "lanes"
    assert restored.allows_lane_change is True


def test_osmnx_topology_source_persists_lanes_from_osm_edges() -> None:
    graph = nx.MultiDiGraph()
    graph.add_node("A", x=0.0, y=0.0)
    graph.add_node("B", x=1.0, y=0.0)
    graph.add_edge(
        "A",
        "B",
        key=0,
        length=30.0,
        speed_kph=30.0,
        travel_time=3.6,
        lanes="2;3",
    )

    topology = OSMnxGeographicAreaSource()._to_topology(graph)
    edge = topology.edges[("A", "B", 0)]

    assert edge.lanes == 3
    assert edge.lane_source == "lanes"
    assert edge.allows_lane_change is True
