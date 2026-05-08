"""FastAPI application entrypoint."""

from __future__ import annotations

from typing import Any

from fastapi.encoders import jsonable_encoder
from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect, status

from ..domain.exceptions import (
    GeographicAreaNotFoundError,
    SimulationCancellationError,
    SimulationConfigurationError,
    SimulationNotFoundError,
    SimulationNotReadyError,
)
from ..domain.models import SimulationExecutionMode
from .dependencies import Container, get_container
from .schemas import (
    BoundingBoxResponse,
    CancelSimulationResponse,
    CreateSimulationRequest,
    GeographicAreaTopologyResponse,
    GeographicAreaSummaryResponse,
    SimulationRecordResponse,
    SimulationStepResponse,
    TopologyEdgeResponse,
    TopologyNodeResponse,
    TopologyResponse,
)


def _record_response(record: Any) -> SimulationRecordResponse:
    return SimulationRecordResponse(
        simulation_id=record.simulation_id,
        area_id=record.area_id,
        status=record.status.value,
        latest_step=record.latest_step,
        created_at=record.created_at,
        updated_at=record.updated_at,
        config=record.config.to_dict(),
    )


def _topology_response(area: Any) -> GeographicAreaTopologyResponse:
    return GeographicAreaTopologyResponse(
        area_id=area.area_id,
        name=area.name,
        created_at=area.created_at,
        node_count=area.node_count,
        edge_count=area.edge_count,
        topology=TopologyResponse(
            nodes={
                node_id: TopologyNodeResponse(**node.to_dict())
                for node_id, node in area.topology.nodes.items()
            },
            edges=[
                TopologyEdgeResponse(**edge.to_dict(edge_id))
                for edge_id, edge in area.topology.edges.items()
            ],
            bbox=BoundingBoxResponse(**area.topology.bbox.to_dict()),
        ),
    )


def create_app() -> FastAPI:
    app = FastAPI(title="Traffic Engine API", version="0.1.0")

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        container = get_container()
        await container.shutdown()
        get_container.cache_clear()

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/geographic-areas", response_model=list[GeographicAreaSummaryResponse])
    async def list_geographic_areas(
        container: Container = Depends(get_container),
    ) -> list[GeographicAreaSummaryResponse]:
        areas = container.list_geographic_areas.execute()
        return [
            GeographicAreaSummaryResponse(
                area_id=area.area_id,
                name=area.name,
                created_at=area.created_at,
                node_count=area.node_count,
                edge_count=area.edge_count,
                bbox=BoundingBoxResponse(**area.topology.bbox.to_dict()),
            )
            for area in areas
        ]

    @app.get(
        "/geographic-areas/{area_id}/topology",
        response_model=GeographicAreaTopologyResponse,
    )
    async def get_geographic_area_topology(
        area_id: str,
        container: Container = Depends(get_container),
    ) -> GeographicAreaTopologyResponse:
        try:
            area = container.get_geographic_area.execute(area_id)
        except GeographicAreaNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return _topology_response(area)

    @app.post(
        "/simulations",
        response_model=SimulationRecordResponse,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_simulation(
        request: CreateSimulationRequest,
        container: Container = Depends(get_container),
    ) -> SimulationRecordResponse:
        try:
            record = container.create_simulation.execute(
                area_id=request.area_id,
                initial_vehicles=request.initial_vehicles,
                max_vehicles=request.max_vehicles,
                max_steps=request.max_steps,
                spawn_rate=request.spawn_rate,
                noise_prob=request.noise_prob,
                seed=request.seed,
                tick_interval_ms=request.tick_interval_ms,
                execution_mode=SimulationExecutionMode(request.execution_mode),
                default_lanes=request.default_lanes,
                traffic_light_percentage=request.traffic_light_percentage,
                traffic_light_green_steps=request.traffic_light_green_steps,
                traffic_light_red_steps=request.traffic_light_red_steps,
                enable_lane_changes=request.enable_lane_changes,
            )
        except GeographicAreaNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except SimulationConfigurationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return _record_response(record)

    @app.get("/simulations/{simulation_id}", response_model=SimulationRecordResponse)
    async def get_simulation(
        simulation_id: str,
        container: Container = Depends(get_container),
    ) -> SimulationRecordResponse:
        try:
            return _record_response(container.get_simulation.execute(simulation_id))
        except SimulationNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post(
        "/simulations/{simulation_id}/cancel",
        response_model=CancelSimulationResponse,
    )
    async def cancel_simulation(
        simulation_id: str,
        container: Container = Depends(get_container),
    ) -> CancelSimulationResponse:
        try:
            container.cancel_simulation.execute(simulation_id)
        except SimulationNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except SimulationCancellationError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return CancelSimulationResponse(simulation_id=simulation_id, requested=True)

    @app.get(
        "/simulations/{simulation_id}/steps",
        response_model=list[SimulationStepResponse],
    )
    async def list_simulation_steps(
        simulation_id: str,
        container: Container = Depends(get_container),
    ) -> list[SimulationStepResponse]:
        try:
            steps = container.list_simulation_steps.execute(simulation_id)
        except SimulationNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except SimulationNotReadyError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return [
            SimulationStepResponse(
                simulation_id=step.simulation_id,
                step_number=step.step_number,
                metrics=step.metrics.to_dict(),
                state=step.state.to_dict(),
                recorded_at=step.recorded_at,
            )
            for step in steps
        ]

    @app.websocket("/simulations/{simulation_id}/ws")
    async def simulation_ws(websocket: WebSocket, simulation_id: str) -> None:
        container = get_container()
        try:
            record = container.get_simulation.execute(simulation_id)
        except SimulationNotFoundError:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        if record.status.value != "running":
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        await websocket.accept()
        try:
            async for event in container.event_bus.subscribe(simulation_id):
                await websocket.send_json(jsonable_encoder(event))
        except WebSocketDisconnect:
            return

    return app


app = create_app()


def main() -> None:
    """Console script entrypoint placeholder for local development."""

