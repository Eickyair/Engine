from datetime import datetime, timezone

from fastapi.testclient import TestClient

import traffic_engine.api.app as app_module
from traffic_engine.domain.exceptions import SimulationConfigurationError
from traffic_engine.domain.models import (
    GeographicArea,
    SimulationConfig,
    SimulationMetrics,
    SimulationRecord,
    SimulationState,
    SimulationStatus,
    SimulationStep,
    StepVisualization,
)


class FakeListAreasUseCase:
    def __init__(self, area: GeographicArea) -> None:
        self.area = area

    def execute(self):
        return [self.area]


class FakeCreateSimulationUseCase:
    def execute(self, area_id: str, **kwargs):
        if kwargs.get("enable_lane_changes") and kwargs.get("default_lanes") == 1:
            raise SimulationConfigurationError(
                "Lane changes require at least two lanes in the default lane configuration."
            )
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
    def execute(
        self,
        simulation_id: str,
        allow_running: bool = False,
        limit: int = 50,       # agregar
        offset: int = 0,       # agregar
    ):
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


def test_api_rejects_lane_changes_without_multiple_lanes() -> None:
    fake_container = type(
        "FakeContainer",
        (),
        {
            "create_simulation": FakeCreateSimulationUseCase(),
            "runtime": FakeRuntime(),
            "shutdown": FakeRuntime().shutdown,
        },
    )()

    app_module.app.dependency_overrides[app_module.get_container] = lambda: fake_container
    client = TestClient(app_module.app)

    response = client.post(
        "/simulations",
        json={
            "area_id": "roma-norte",
            "default_lanes": 1,
            "enable_lane_changes": True,
        },
    )

    app_module.app.dependency_overrides.clear()

    assert response.status_code == 422
    assert "at least two lanes" in response.json()["detail"]


def test_api_exposes_shareable_endpoint_schema_document() -> None:
    client = TestClient(app_module.app)

    response = client.get("/api/response-models.json")

    assert response.status_code == 200
    document = response.json()
    assert document["source"] == "/openapi.json"
    assert "models" not in document

    simulation_endpoint = next(
        endpoint
        for endpoint in document["endpoints"]
        if endpoint["path"] == "/simulations" and endpoint["method"] == "POST"
    )
    assert simulation_endpoint["request_body"]["schema"]["required"] == ["area_id"]
    assert simulation_endpoint["request_body"]["schema"]["properties"]["area_id"] == {
        "type": "string",
        "minLength": 1,
    }
    assert simulation_endpoint["responses"]["201"]["schema"]["properties"]["simulation_id"] == {
        "type": "string"
    }
    assert "$ref" not in str(simulation_endpoint)


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


def test_api_step_response_has_typed_metrics_and_visualization() -> None:
    class FakeStepsUseCase:
        def execute(
            self,
            simulation_id: str,
            allow_running: bool = False,
            limit: int = 50,       # agregar
            offset: int = 0,       # agregar
        ):
            metrics = SimulationMetrics(
                step_number=1, total_vehicles=2, avg_speed_kph=30.0,
                density=0.1, throughput_veh_per_min=5.0, congestion_ratio=0.0,
            )
            state = SimulationState(
                step_number=1, vehicles=[], total_vehicles=2,
                active_vehicles=2, density=0.1,
            )
            viz = StepVisualization(
                heat_density_points=[[19.43, -99.15, 1.0]],
                heat_speed_points=[[19.43, -99.15, 30.0]],
                flow_nodes=[],
                flow_edges=[{"edge": ["A", "B", 0], "count": 2}],
            )
            return [
                SimulationStep(
                    simulation_id=simulation_id, step_number=1,
                    metrics=metrics, state=state, visualization=viz,
                )
            ]

    fake_container = type(
        "FakeContainer",
        (),
        {
            "get_simulation": FakeGetSimulationUseCase(),
            "list_simulation_steps": FakeStepsUseCase(),
            "runtime": FakeRuntime(),
            "shutdown": FakeRuntime().shutdown,
        },
    )()

    app_module.app.dependency_overrides[app_module.get_container] = lambda: fake_container
    client = TestClient(app_module.app)
    response = client.get("/simulations/sim-001/steps")
    app_module.app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    step = body[0]

    assert step["metrics"]["avg_speed_kph"] == 30.0
    assert step["metrics"]["total_vehicles"] == 2
    assert "heat_density_points" not in step["metrics"]

    assert step["visualization"]["heat_density_points"] == [[19.43, -99.15, 1.0]]
    assert step["visualization"]["heat_speed_points"] == [[19.43, -99.15, 30.0]]
    assert step["visualization"]["flow_edges"][0]["count"] == 2
