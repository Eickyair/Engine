"""Use case that executes a NaSch simulation in the background."""

from __future__ import annotations

import asyncio
from asyncio import Event
from typing import Any

from ...domain.abstractions import CellularModel, RouteProvider, TrafficLightProvider
from ...domain.models import GeographicArea, SimulationRecord, SimulationStatus, SimulationStep
from ...domain.simulation_builder import SimulationModelBuilder
from ...domain.simulation import NaSchSimulationModel
from ..ports import LiveEventBus, SimulationRepository


class RunSimulationUseCase:
    def __init__(
        self,
        repository: SimulationRepository,
        event_bus: LiveEventBus,
        route_provider: RouteProvider,
        cellular_model: CellularModel,
        traffic_light_provider: TrafficLightProvider | None = None,
    ) -> None:
        self.repository = repository
        self.event_bus = event_bus
        self.route_provider = route_provider
        self.cellular_model = cellular_model
        self.traffic_light_provider = traffic_light_provider

    async def execute(
        self,
        record: SimulationRecord,
        area: GeographicArea,
        cancel_event: Event,
    ) -> None:
        definition = (
            SimulationModelBuilder(record.config)
            .with_execution_mode(record.config.execution_mode)
            .with_route_provider(self.route_provider)
            .with_cellular_model(self.cellular_model)
            .with_traffic_light_provider(
                self.traffic_light_provider
                if record.config.traffic_light_percentage > 0.0
                else None
            )
            .with_default_lanes(record.config.default_lanes)
            .build()
        )
        traffic_lights = (
            definition.traffic_light_provider.provide(area.topology, definition.config)
            if definition.traffic_light_provider is not None
            else []
        )
        model = NaSchSimulationModel(
            seed=definition.config.seed,
            route_provider=definition.route_provider,
            cellular_model=definition.cellular_model,
            traffic_lights=traffic_lights,
        )
        model.reset(topology=area.topology, config=definition.config)
        final_status = SimulationStatus.FINISHED

        try:
            for _ in range(record.config.max_steps):
                if cancel_event.is_set():
                    final_status = SimulationStatus.CANCELLED
                    break

                state, metrics, done = model.step()
                step = SimulationStep(
                    simulation_id=record.simulation_id,
                    step_number=state.step_number,
                    metrics=metrics,
                    state=state,
                )
                self.repository.append_step(step)
                self.repository.update_latest_step(record.simulation_id, latest_step=state.step_number)
                await self.event_bus.publish(
                    record.simulation_id,
                    {
                        "type": "step",
                        "simulation_id": record.simulation_id,
                        "status": SimulationStatus.RUNNING.value,
                        "step": step.to_dict(),
                    },
                )

                if done:
                    break

                if record.config.tick_interval_ms > 0:
                    try:
                        await asyncio.wait_for(
                            cancel_event.wait(),
                            timeout=record.config.tick_interval_ms / 1000,
                        )
                    except TimeoutError:
                        pass
                    if cancel_event.is_set():
                        final_status = SimulationStatus.CANCELLED
                        break
        finally:
            if cancel_event.is_set() and final_status == SimulationStatus.FINISHED:
                final_status = SimulationStatus.CANCELLED
            self.repository.update_status(record.simulation_id, status=final_status.value)
            await self.event_bus.publish(
                record.simulation_id,
                {
                    "type": "status",
                    "simulation_id": record.simulation_id,
                    "status": final_status.value,
                },
            )
