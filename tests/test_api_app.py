from datetime import datetime, timezone

from fastapi.testclient import TestClient

import traffic_engine.api.app as app_module
from traffic_engine.domain.models import GeographicArea, SimulationConfig, SimulationRecord, SimulationStatus


class FakeListAreasUseCase:
    def __init__(self, area: GeographicArea) -> None:
        self.area = area

    def execute(self):
        return [self.area]


class FakeCreateSimulationUseCase:
    def execute(self, area_id: str, **kwargs):
        return SimulationRecord(
            simulation_id="sim-001",
            area_id=area_id,
            status=SimulationStatus.RUNNING,
            config=SimulationConfig(
                initial_vehicles=kwargs.get("initial_vehicles", 25),
                max_vehicles=kwargs.get("max_vehicles", 60),
                max_steps=kwargs.get("max_steps", 120),
                spawn_rate=kwargs.get("spawn_rate", 0.2),
                noise_prob=kwargs.get("noise_prob", 0.3),
                seed=kwargs.get("seed", 42),
                tick_interval_ms=kwargs.get("tick_interval_ms", 100),
            ),
        )


class FakeGetGeographicAreaUseCase:
    def __init__(self, area: GeographicArea) -> None:
        self.area = area

    def execute(self, area_id: str):
        assert area_id == self.area.area_id
        return self.area


class FakeGetSimulationUseCase:
    def execute(self, simulation_id: str):
        return SimulationRecord(
            simulation_id=simulation_id,
            area_id="roma-norte",
            status=SimulationStatus.RUNNING,
            config=SimulationConfig(
                initial_vehicles=25,
                max_vehicles=60,
                max_steps=120,
                spawn_rate=0.2,
                noise_prob=0.3,
                seed=42,
                tick_interval_ms=100,
            ),
        )


class FakeListSimulationStepsUseCase:
    def execute(self, simulation_id: str):
        from traffic_engine.domain.exceptions import SimulationNotReadyError

        raise SimulationNotReadyError("not ready")


class FakeCancelSimulationUseCase:
    def execute(self, simulation_id: str):
        return None


class FakeEventBus:
    async def publish(self, simulation_id: str, event: dict):
        return None

    def subscribe(self, simulation_id: str):
        async def _iterator():
            if False:
                yield {}
        return _iterator()


class FakeRuntime:
    async def shutdown(self):
        return None


def _sample_area() -> GeographicArea:
    from traffic_engine.domain.models import BoundingBox, EdgeData, NodeData, TopologyData

    return GeographicArea(
        area_id="roma-norte",
        name="Roma Norte",
        topology=TopologyData(
            nodes={"A": NodeData(x=-99.15, y=19.43, is_boundary=True)},
            edges={
                (
                    "A",
                    "A",
                    0,
                ): EdgeData(
                    length_m=10.0,
                    speed_kph=10.0,
                    travel_time_sec=1.0,
                    n_cells=1,
                    vmax_cells=1,
                    geometry_points=[(-99.15, 19.43), (-99.15, 19.43)],
                )
            },
            bbox=BoundingBox(min_x=-99.15, max_x=-99.15, min_y=19.43, max_y=19.43),
        ),
    )


def test_api_lists_areas_and_creates_simulation() -> None:
    fake_container = type(
        "FakeContainer",
        (),
        {
            "list_geographic_areas": FakeListAreasUseCase(_sample_area()),
            "get_geographic_area": FakeGetGeographicAreaUseCase(_sample_area()),
            "create_simulation": FakeCreateSimulationUseCase(),
            "get_simulation": FakeGetSimulationUseCase(),
            "list_simulation_steps": FakeListSimulationStepsUseCase(),
            "cancel_simulation": FakeCancelSimulationUseCase(),
            "event_bus": FakeEventBus(),
            "runtime": FakeRuntime(),
            "shutdown": FakeRuntime().shutdown,
        },
    )()

    app_module.app.dependency_overrides[app_module.get_container] = lambda: fake_container
    client = TestClient(app_module.app)

    list_response = client.get("/geographic-areas")
    topology_response = client.get("/geographic-areas/roma-norte/topology")
    create_response = client.post("/simulations", json={"area_id": "roma-norte"})
    steps_response = client.get("/simulations/sim-001/steps")

    app_module.app.dependency_overrides.clear()

    assert list_response.status_code == 200
    assert list_response.json()[0]["area_id"] == "roma-norte"
    assert topology_response.status_code == 200
    assert topology_response.json()["topology"]["edges"][0]["n_cells"] == 1
    assert topology_response.json()["topology"]["nodes"]["A"]["is_boundary"] is True
    assert create_response.status_code == 201
    assert create_response.json()["simulation_id"] == "sim-001"
    assert steps_response.status_code == 409


def test_websocket_serializes_datetime_events() -> None:
    class FakeDatetimeEventBus:
        def subscribe(self, simulation_id: str):
            async def _iterator():
                yield {
                    "type": "step",
                    "simulation_id": simulation_id,
                    "recorded_at": datetime.now(timezone.utc),
                }
                yield {
                    "type": "status",
                    "simulation_id": simulation_id,
                    "status": "finished",
                    "recorded_at": datetime.now(timezone.utc),
                }

            return _iterator()

    fake_container = type(
        "FakeContainer",
        (),
        {
            "get_simulation": FakeGetSimulationUseCase(),
            "event_bus": FakeDatetimeEventBus(),
            "runtime": FakeRuntime(),
            "shutdown": FakeRuntime().shutdown,
        },
    )()

    original_get_container = app_module.get_container
    app_module.get_container = lambda: fake_container
    try:
        client = TestClient(app_module.app)
        with client.websocket_connect("/simulations/sim-001/ws") as websocket:
            first_event = websocket.receive_json()
            second_event = websocket.receive_json()
    finally:
        app_module.get_container = original_get_container

    assert first_event["type"] == "step"
    assert isinstance(first_event["recorded_at"], str)
    assert second_event["type"] == "status"
    assert second_event["status"] == "finished"
    assert isinstance(second_event["recorded_at"], str)
