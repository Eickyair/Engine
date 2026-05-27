"""In-process background runtime and live event bus."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any, AsyncIterator, Awaitable, Callable, DefaultDict


class InMemoryLiveEventBus:
    def __init__(self) -> None:
        self._subscribers: DefaultDict[str, list[asyncio.Queue[dict[str, Any]]]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def publish(self, simulation_id: str, event: dict[str, Any]) -> None:
        async with self._lock:
            subscribers = list(self._subscribers.get(simulation_id, []))
        for queue in subscribers:
            await queue.put(dict(event))

    async def _remove_queue(self, simulation_id: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
        async with self._lock:
            subscribers = self._subscribers.get(simulation_id, [])
            if queue in subscribers:
                subscribers.remove(queue)
            if not subscribers and simulation_id in self._subscribers:
                del self._subscribers[simulation_id]

    async def _add_queue(self, simulation_id: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
        async with self._lock:
            self._subscribers[simulation_id].append(queue)

    async def _subscribe(self, simulation_id: str) -> AsyncIterator[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        await self._add_queue(simulation_id, queue)
        try:
            while True:
                event = await queue.get()
                yield dict(event)
                if event.get("type") == "status":
                    break
        finally:
            await self._remove_queue(simulation_id, queue)

    def subscribe(self, simulation_id: str) -> AsyncIterator[dict[str, Any]]:
        return self._subscribe(simulation_id)


class InProcessSimulationRuntime:
    def __init__(self, max_concurrent: int = 50) -> None:
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._cancel_events: dict[str, asyncio.Event] = {}
        self._max_concurrent = max_concurrent

    @property
    def active_count(self) -> int:
        return sum(1 for t in self._tasks.values() if not t.done())

    def start(
        self,
        simulation_id: str,
        job_factory: Callable[[asyncio.Event], Awaitable[None]],
    ) -> None:
        cancel_event = asyncio.Event()
        self._cancel_events[simulation_id] = cancel_event
        task = asyncio.create_task(job_factory(cancel_event))
        self._tasks[simulation_id] = task
        task.add_done_callback(lambda finished, sid=simulation_id: self._cleanup_task(sid, finished))

    def cancel(self, simulation_id: str) -> bool:
        cancel_event = self._cancel_events.get(simulation_id)
        if cancel_event is None:
            return False
        cancel_event.set()
        return True

    def is_running(self, simulation_id: str) -> bool:
        task = self._tasks.get(simulation_id)
        return bool(task is not None and not task.done())

    async def shutdown(self) -> None:
        for cancel_event in self._cancel_events.values():
            cancel_event.set()
        tasks = list(self._tasks.values())
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()
        self._cancel_events.clear()

    def _cleanup_task(self, simulation_id: str, task: asyncio.Task[None]) -> None:
        self._tasks.pop(simulation_id, None)
        self._cancel_events.pop(simulation_id, None)
        try:
            task.result()
        except Exception:
            return
