"""Dependency wiring for the FastAPI transport."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from ..application.use_cases import (
    BootstrapGeographicAreasUseCase,
    CancelSimulationUseCase,
    CreateSimulationUseCase,
    GetGeographicAreaUseCase,
    GetSimulationUseCase,
    ListGeographicAreasUseCase,
    ListSimulationStepsUseCase,
    RunSimulationUseCase,
)
from ..infrastructure import (
    InMemoryLiveEventBus,
    InProcessSimulationRuntime,
    MongoGeographicAreaRepository,
    MongoSimulationRepository,
    NagelCellularModel,
    OSMnxGeographicAreaSource,
    RandomTrafficLightProvider,
    ShortestPathRouteProvider,
    close_mongo_client,
)


@dataclass
class Container:
    bootstrap_geographic_areas: BootstrapGeographicAreasUseCase
    list_geographic_areas: ListGeographicAreasUseCase
    get_geographic_area: GetGeographicAreaUseCase
    create_simulation: CreateSimulationUseCase
    get_simulation: GetSimulationUseCase
    list_simulation_steps: ListSimulationStepsUseCase
    cancel_simulation: CancelSimulationUseCase
    event_bus: InMemoryLiveEventBus
    runtime: InProcessSimulationRuntime

    async def shutdown(self) -> None:
        await self.runtime.shutdown()
        close_mongo_client()


@lru_cache(maxsize=1)
def get_container() -> Container:
    area_repository = MongoGeographicAreaRepository()
    simulation_repository = MongoSimulationRepository()
    event_bus = InMemoryLiveEventBus()
    runtime = InProcessSimulationRuntime()
    run_simulation = RunSimulationUseCase(
        repository=simulation_repository,
        event_bus=event_bus,
        route_provider=ShortestPathRouteProvider(),
        cellular_model=NagelCellularModel(allow_lane_changes=True),
        traffic_light_provider=RandomTrafficLightProvider(),
    )
    return Container(
        bootstrap_geographic_areas=BootstrapGeographicAreasUseCase(
            source=OSMnxGeographicAreaSource(),
            repository=area_repository,
        ),
        list_geographic_areas=ListGeographicAreasUseCase(repository=area_repository),
        get_geographic_area=GetGeographicAreaUseCase(repository=area_repository),
        create_simulation=CreateSimulationUseCase(
            area_repository=area_repository,
            simulation_repository=simulation_repository,
            runtime=runtime,
            run_simulation=run_simulation,
        ),
        get_simulation=GetSimulationUseCase(repository=simulation_repository),
        list_simulation_steps=ListSimulationStepsUseCase(repository=simulation_repository),
        cancel_simulation=CancelSimulationUseCase(
            repository=simulation_repository,
            runtime=runtime,
        ),
        event_bus=event_bus,
        runtime=runtime,
    )
