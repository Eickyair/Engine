import asyncio

import pytest

from traffic_engine.application.use_cases import CancelSimulationUseCase, CreateSimulationUseCase
from traffic_engine.domain.exceptions import SimulationCancellationError, SimulationConfigurationError
from traffic_engine.domain.models import GeographicArea, SimulationRecord, SimulationStatus


class FakeAreaRepository:
    def __init__(self, area: GeographicArea) -> None:
        self.area = area

    def save(self, area: GeographicArea) -> GeographicArea:
        self.area = area
        return area

    def get(self, area_id: str) -> GeographicArea | None:
        if self.area.area_id == area_id:
            return self.area
        return None

    def list(self) -> list[GeographicArea]:
        return [self.area]


class FakeSimulationRepository:
    def __init__(self) -> None:
        self.records: dict[str, SimulationRecord] = {}

    def create(self, record: SimulationRecord) -> SimulationRecord:
        self.records[record.simulation_id] = record
        return record

    def get(self, simulation_id: str) -> SimulationRecord | None:
        return self.records.get(simulation_id)

    def update_status(self, simulation_id: str, status: str) -> SimulationRecord | None:
        record = self.records.get(simulation_id)
        if record is None:
            return None
        updated = SimulationRecord(
            simulation_id=record.simulation_id,
            area_id=record.area_id,
            status=SimulationStatus(status),
            config=record.config,
            created_at=record.created_at,
            updated_at=record.updated_at,
            latest_step=record.latest_step,
        )
        self.records[simulation_id] = updated
        return updated

    def update_latest_step(self, simulation_id: str, latest_step: int) -> SimulationRecord | None:
        record = self.records.get(simulation_id)
        if record is None:
            return None
        updated = SimulationRecord(
            simulation_id=record.simulation_id,
            area_id=record.area_id,
            status=record.status,
            config=record.config,
            created_at=record.created_at,
            updated_at=record.updated_at,
            latest_step=latest_step,
        )
        self.records[simulation_id] = updated
        return updated

    def append_step(self, step):
        return step

    def list_steps(self, simulation_id: str):
        return []


class FakeRuntime:
    def __init__(self) -> None:
        self.started: list[str] = []
        self.cancelled: list[str] = []

    def start(self, simulation_id, job_factory) -> None:
        self.started.append(simulation_id)
        cancel_event = asyncio.Event()
        coroutine = job_factory(cancel_event)
        coroutine.close()

    def cancel(self, simulation_id: str) -> bool:
        self.cancelled.append(simulation_id)
        return True

    def is_running(self, simulation_id: str) -> bool:
        return simulation_id not in self.cancelled


class FakeRunSimulationUseCase:
    async def execute(self, record, area, cancel_event) -> None:
        return None


def _sample_area() -> GeographicArea:
    from traffic_engine.domain.models import BoundingBox, EdgeData, NodeData, TopologyData

    return GeographicArea(
        area_id="roma-norte",
        name="Roma Norte",
        topology=TopologyData(
            nodes={
                "A": NodeData(x=-99.15, y=19.43, is_boundary=True),
                "B": NodeData(x=-99.14, y=19.43, is_boundary=True),
            },
            edges={
                (
                    "A",
                    "B",
                    0,
                ): EdgeData(
                    length_m=75.0,
                    speed_kph=30.0,
                    travel_time_sec=9.0,
                    n_cells=10,
                    vmax_cells=2,
                    geometry_points=[(-99.15, 19.43), (-99.14, 19.43)],
                )
            },
            bbox=BoundingBox(min_x=-99.15, max_x=-99.14, min_y=19.43, max_y=19.43),
        ),
    )


def test_create_simulation_dispatches_runtime_and_stores_running_record() -> None:
    area_repository = FakeAreaRepository(_sample_area())
    simulation_repository = FakeSimulationRepository()
    runtime = FakeRuntime()
    use_case = CreateSimulationUseCase(
        area_repository=area_repository,
        simulation_repository=simulation_repository,
        runtime=runtime,
        run_simulation=FakeRunSimulationUseCase(),
    )

    record = use_case.execute(area_id="roma-norte", initial_vehicles=3, max_steps=5)

    assert record.status == SimulationStatus.RUNNING
    assert runtime.started == [record.simulation_id]
    assert simulation_repository.get(record.simulation_id) is not None


def test_create_simulation_rejects_lane_changes_without_multiple_lanes_before_runtime() -> None:
    area_repository = FakeAreaRepository(_sample_area())
    simulation_repository = FakeSimulationRepository()
    runtime = FakeRuntime()
    use_case = CreateSimulationUseCase(
        area_repository=area_repository,
        simulation_repository=simulation_repository,
        runtime=runtime,
        run_simulation=FakeRunSimulationUseCase(),
    )

    with pytest.raises(SimulationConfigurationError):
        use_case.execute(
            area_id="roma-norte",
            default_lanes=1,
            enable_lane_changes=True,
        )

    assert runtime.started == []
    assert simulation_repository.records == {}


def test_cancel_simulation_rejects_non_running_record() -> None:
    repository = FakeSimulationRepository()
    runtime = FakeRuntime()
    running_record = CreateSimulationUseCase(
        area_repository=FakeAreaRepository(_sample_area()),
        simulation_repository=repository,
        runtime=runtime,
        run_simulation=FakeRunSimulationUseCase(),
    ).execute(area_id="roma-norte")
    repository.update_status(running_record.simulation_id, SimulationStatus.FINISHED.value)

    use_case = CancelSimulationUseCase(repository=repository, runtime=runtime)

    with pytest.raises(SimulationCancellationError):
        use_case.execute(running_record.simulation_id)
