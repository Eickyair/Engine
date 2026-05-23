"""Provider implementations for the simulation engine."""

from __future__ import annotations

import csv
import heapq
import io
import logging
import os
import time
import zipfile
from math import floor
from random import Random

from ..domain.exceptions import RouteSelectionError
from ..domain.models import EdgeId, SimulationConfig, TopologyData, TrafficLight, TrafficLightCycle, Vehicle

logger = logging.getLogger(__name__)

_GTFS_API_URL = "https://metrobus-gtfs.sinopticoplus.com/gtfs-api/partnerValidation"
_GTFS_BBOX_MARGIN = 0.008   # ~900 m de margen alrededor del grafo


class GTFSStopFetcher:
    """Descarga paradas de Metrobús desde el API GTFS con caché de 5 minutos."""

    _CACHE_TTL = 300

    def __init__(self) -> None:
        self._stops: list[tuple[float, float]] | None = None
        self._fetched_at: float = 0.0

    def get_stops(self) -> list[tuple[float, float]]:
        if self._stops is None or (time.monotonic() - self._fetched_at) > self._CACHE_TTL:
            self._stops = self._download()
            self._fetched_at = time.monotonic()
        return self._stops

    def _download(self) -> list[tuple[float, float]]:
        import requests  # opcional en runtime; no depende del resto del paquete

        credentials = {
            "usuario": os.environ.get("GTFS_USER", "rodri.mo7576"),
            "senha":   os.environ.get("GTFS_PASS", "15Sj98-fI$"),
        }
        auth = requests.post(_GTFS_API_URL, json=credentials, timeout=15)
        auth.raise_for_status()

        zip_resp = requests.get(auth.json()["urlStatic"], timeout=60)
        zip_resp.raise_for_status()

        stops: list[tuple[float, float]] = []
        with zipfile.ZipFile(io.BytesIO(zip_resp.content)) as zf:
            with zf.open("stops.txt") as raw:
                for row in csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig")):
                    try:
                        stops.append((float(row["stop_lat"]), float(row["stop_lon"])))
                    except (KeyError, ValueError):
                        continue

        logger.info("GTFS: %d paradas descargadas", len(stops))
        return stops


class GTFSTrafficLightProvider:
    """
    Coloca semáforos en los nodos más cercanos a las paradas reales de Metrobús.

    Implementa el mismo Protocol que RandomTrafficLightProvider — la firma
    provide(topology, config) es idéntica, por lo que es un drop-in replacement.

    Si el API GTFS falla o no hay paradas en el área del grafo, usa el
    proveedor de respaldo (por defecto RandomTrafficLightProvider).
    """

    def __init__(self, fallback: RandomTrafficLightProvider | None = None) -> None:
        self._fetcher = GTFSStopFetcher()
        self._fallback = fallback or RandomTrafficLightProvider()

    def provide(self, topology: TopologyData, config: SimulationConfig) -> list[TrafficLight]:
        try:
            lights = self._from_stops(topology, config)
            logger.info("GTFSTrafficLightProvider: %d semáforos desde paradas Metrobús", len(lights))
            return lights
        except Exception as exc:
            logger.warning("GTFS provider falló (%s) — usando fallback", exc)
            return self._fallback.provide(topology, config)

    def _from_stops(
        self, topology: TopologyData, config: SimulationConfig
    ) -> list[TrafficLight]:
        stops = self._fetcher.get_stops()

        bbox = topology.bbox
        m = _GTFS_BBOX_MARGIN
        in_bbox = [
            (lat, lon) for lat, lon in stops
            if (bbox.min_y - m) <= lat <= (bbox.max_y + m)
            and (bbox.min_x - m) <= lon <= (bbox.max_x + m)
        ]
        if not in_bbox:
            raise ValueError(
                f"Sin paradas GTFS en el área del grafo "
                f"(lat {bbox.min_y:.4f}–{bbox.max_y:.4f}, "
                f"lon {bbox.min_x:.4f}–{bbox.max_x:.4f})"
            )

        # Solo intersecciones válidas (grado >= 3) como candidatas
        valid = set(_valid_intersections(topology))
        node_coords = [
            (nid, nd.x, nd.y)
            for nid, nd in topology.nodes.items()
            if nid in valid
        ]
        if not node_coords:
            raise ValueError("No hay intersecciones válidas en la topología.")

        # Para cada parada en el bbox, encontrar el nodo más cercano
        selected: dict[str, bool] = {}
        for lat, lon in in_bbox:
            nearest = min(node_coords, key=lambda t: (t[1] - lon) ** 2 + (t[2] - lat) ** 2)
            selected[nearest[0]] = True

        incoming = _incoming_nodes(topology)
        cycle = TrafficLightCycle(
            green_steps=config.traffic_light_green_steps,
            red_steps=config.traffic_light_red_steps,
        )
        return [
            TrafficLight(
                node_id=nid,
                applies_to=sorted(incoming.get(nid, [])),
                cycle=cycle,
            )
            for nid in selected
        ]


class RandomTrafficLightProvider:
    def __init__(self, percentage: float | None = None, seed: int | None = None) -> None:
        self.percentage = percentage
        self.seed = seed

    def provide(self, topology: TopologyData, config: SimulationConfig) -> list[TrafficLight]:
        candidates = _valid_intersections(topology)
        if not candidates:
            return []
        percentage = _clamp_percentage(
            config.traffic_light_percentage if self.percentage is None else self.percentage
        )
        count = _round_half_up(len(candidates) * percentage)
        if count <= 0:
            return []
        random = Random(config.seed if self.seed is None else self.seed)
        selected = random.sample(candidates, min(count, len(candidates)))
        incoming = _incoming_nodes(topology)
        cycle = TrafficLightCycle(
            green_steps=config.traffic_light_green_steps,
            red_steps=config.traffic_light_red_steps,
        )
        return [
            TrafficLight(
                node_id=node_id,
                applies_to=sorted(incoming.get(node_id, [])),
                cycle=cycle,
            )
            for node_id in selected
        ]


class ShortestPathRouteProvider:
    def choose_route(self, topology: TopologyData, random: Random) -> list[EdgeId]:
        if not topology.edges:
            raise RouteSelectionError("The grid has no traversable cells.")
        boundary_nodes = [
            node_id for node_id, node in topology.nodes.items() if node.is_boundary
        ] or list(topology.nodes.keys())
        if len(boundary_nodes) < 2:
            raise RouteSelectionError("At least two valid traversable nodes are required.")

        for _ in range(20):
            origin, destination = random.sample(boundary_nodes, 2)
            route = self._shortest_edge_path(topology, origin, destination)
            if route:
                return self._select_parallel_edge_variants(topology, route, random)
        raise RouteSelectionError("No reachable origin/destination pair could be selected.")

    def _shortest_edge_path(
        self,
        topology: TopologyData,
        origin: str,
        destination: str,
    ) -> list[EdgeId]:
        adjacency = topology.outgoing_edges()
        distances: dict[str, float] = {origin: 0.0}
        previous: dict[str, EdgeId] = {}
        heap: list[tuple[float, str]] = [(0.0, origin)]

        while heap:
            distance, node_id = heapq.heappop(heap)
            if node_id == destination:
                break
            if distance > distances.get(node_id, float("inf")):
                continue
            for edge_id in adjacency.get(node_id, []):
                edge = topology.edges[edge_id]
                next_node = edge_id[1]
                candidate = distance + edge.travel_time_sec
                if candidate >= distances.get(next_node, float("inf")):
                    continue
                distances[next_node] = candidate
                previous[next_node] = edge_id
                heapq.heappush(heap, (candidate, next_node))

        if destination not in previous:
            return []

        route: list[EdgeId] = []
        current = destination
        while current != origin:
            edge_id = previous[current]
            route.append(edge_id)
            current = edge_id[0]
        route.reverse()
        return route

    def _select_parallel_edge_variants(
        self,
        topology: TopologyData,
        route: list[EdgeId],
        random: Random,
    ) -> list[EdgeId]:
        return [
            self._choose_parallel_edge(topology, edge_id, random)
            for edge_id in route
        ]

    def _choose_parallel_edge(
        self,
        topology: TopologyData,
        edge_id: EdgeId,
        random: Random,
    ) -> EdgeId:
        origin, destination, _ = edge_id
        candidates = [
            candidate_id
            for candidate_id in topology.edges
            if candidate_id[0] == origin and candidate_id[1] == destination
        ]
        if len(candidates) <= 1:
            return edge_id
        weights = [max(1, topology.edges[candidate_id].lanes) for candidate_id in candidates]
        return random.choices(candidates, weights=weights, k=1)[0]


class NagelCellularModel:
    def __init__(self, allow_lane_changes: bool = False) -> None:
        self.supports_lane_changes = allow_lane_changes

    def resolve_lane(self, vehicle: Vehicle, available_lanes: int, gap_ahead: int) -> int:
        if not self.supports_lane_changes or available_lanes < 2 or gap_ahead > 1:
            return vehicle.lane
        return min(available_lanes - 1, vehicle.lane + 1)

    def resolve_velocity(
        self,
        vehicle: Vehicle,
        max_velocity: int,
        gap_ahead: int,
        red_light_gap: int | None,
        random: Random,
        noise_prob: float,
    ) -> int:
        new_velocity = min(vehicle.velocity + 1, max_velocity, gap_ahead)
        if red_light_gap is not None:
            new_velocity = min(new_velocity, max(0, red_light_gap - 1))
        if new_velocity > 0 and random.random() < noise_prob:
            new_velocity -= 1
        return new_velocity


def _valid_intersections(topology: TopologyData) -> list[str]:
    incoming = _incoming_nodes(topology)
    outgoing = topology.outgoing_edges()
    valid: list[str] = []
    for node_id in topology.nodes:
        degree = len(incoming.get(node_id, [])) + len(outgoing.get(node_id, []))
        if degree >= 3:
            valid.append(node_id)
    return valid


def _incoming_nodes(topology: TopologyData) -> dict[str, set[str]]:
    incoming: dict[str, set[str]] = {node_id: set() for node_id in topology.nodes}
    for origin, destination, _ in topology.edges:
        incoming.setdefault(destination, set()).add(origin)
    return incoming


def _clamp_percentage(value: float) -> float:
    return max(0.0, min(1.0, value))


def _round_half_up(value: float) -> int:
    return int(floor(value + 0.5))
