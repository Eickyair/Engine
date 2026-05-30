"""Application ports for repositories and runtime adapters."""

from __future__ import annotations

from asyncio import Event
from typing import Any, AsyncIterator, Awaitable, Callable, Protocol

from ..domain.models import GeographicArea, SimulationRecord, SimulationStep


class GeographicAreaRepository(Protocol):
    def save(self, area: GeographicArea) -> GeographicArea:
        ...

    def get(self, area_id: str) -> GeographicArea | None:
        ...

    def list(self) -> list[GeographicArea]:
        ...


class GeographicAreaSource(Protocol):
    def fetch(self, place_name: str, area_id: str | None = None) -> GeographicArea:
        ...


class SimulationRepository(Protocol):
    def create(self, record: SimulationRecord) -> SimulationRecord:
        ...

    def get(self, simulation_id: str) -> SimulationRecord | None:
        ...

    def update_status(self, simulation_id: str, status: str) -> SimulationRecord | None:
        ...

    def update_latest_step(self, simulation_id: str, latest_step: int) -> SimulationRecord | None:
        ...

    def append_step(self, step: SimulationStep) -> SimulationStep:
        ...

    def list_steps(
        self,
        simulation_id: str,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[SimulationStep]:
        ...


class LiveEventBus(Protocol):
    async def publish(self, simulation_id: str, event: dict[str, Any]) -> None:
        ...

    def subscribe(self, simulation_id: str) -> AsyncIterator[dict[str, Any]]:
        ...


class SimulationRuntime(Protocol):
    def start(
        self,
        simulation_id: str,
        job_factory: Callable[[Event], Awaitable[None]],
    ) -> None:
        ...

    def cancel(self, simulation_id: str) -> bool:
        ...

    def is_running(self, simulation_id: str) -> bool:
        ...

    @property
    def active_count(self) -> int:
        ...
