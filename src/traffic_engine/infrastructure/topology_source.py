"""OSMnx-backed geographic area preprocessor."""

from __future__ import annotations

import re
from typing import Any, cast

import networkx as nx
import osmnx as ox

from ..config import CELL_SIZE_M, V_MAX_CELLS
from ..domain.models import BoundingBox, EdgeData, GeographicArea, NodeData, TopologyData


def _slugify(value: str) -> str:
    lowered = value.lower().strip()
    lowered = re.sub(r"[^a-z0-9]+", "-", lowered)
    return lowered.strip("-")


def _parse_speed_kph(raw_value: Any) -> float:
    if isinstance(raw_value, (int, float)):
        return float(raw_value)
    if isinstance(raw_value, list) and raw_value:
        return _parse_speed_kph(raw_value[0])
    if isinstance(raw_value, str):
        token = raw_value.split()[0].strip()
        try:
            return float(token)
        except ValueError:
            return 30.0
    return 30.0


def _parse_lanes(raw_value: Any, default: int = 1) -> tuple[int, str]:
    if raw_value is None:
        return default, "default"
    if isinstance(raw_value, (int, float)):
        return max(1, int(raw_value)), "osm"
    if isinstance(raw_value, list):
        parsed = [_parse_lanes(value, default=default)[0] for value in raw_value if value is not None]
        if parsed:
            return max(parsed), "osm"
        return default, "default"
    if isinstance(raw_value, str):
        matches = re.findall(r"\d+(?:\.\d+)?", raw_value)
        if matches:
            return max(1, int(max(float(match) for match in matches))), "osm"
    return default, "default"


def _edge_lanes(data: dict[str, Any]) -> tuple[int, str]:
    for key in ("lanes", "lanes:forward", "lanes:backward"):
        lanes, source = _parse_lanes(data.get(key))
        if source == "osm":
            return lanes, key
    return 1, "default"


def _speed_to_vmax(speed_kph: float) -> int:
    cells_per_second = speed_kph / 3.6 / CELL_SIZE_M
    return max(1, min(V_MAX_CELLS, round(cells_per_second)))


class OSMnxGeographicAreaSource:
    def __init__(self) -> None:
        ox.settings.use_cache = True

    def fetch(self, place_name: str, area_id: str | None = None) -> GeographicArea:
        graph = ox.graph_from_place(place_name, network_type="drive")
        graph = self._prepare_graph(graph)
        graph = self._largest_strong_component(graph)
        topology = self._to_topology(graph)
        return GeographicArea(
            area_id=area_id or _slugify(place_name),
            name=place_name,
            topology=topology,
        )

    def _prepare_graph(self, graph: nx.MultiDiGraph) -> nx.MultiDiGraph:
        add_edge_speeds = getattr(ox, "add_edge_speeds", None)
        if add_edge_speeds is None:
            add_edge_speeds = getattr(getattr(ox, "routing", None), "add_edge_speeds")
        add_edge_travel_times = getattr(ox, "add_edge_travel_times", None)
        if add_edge_travel_times is None:
            add_edge_travel_times = getattr(getattr(ox, "routing", None), "add_edge_travel_times")
        graph = add_edge_speeds(graph)
        graph = add_edge_travel_times(graph)
        return graph

    def _largest_strong_component(self, graph: nx.MultiDiGraph) -> nx.MultiDiGraph:
        if graph.number_of_nodes() == 0:
            return graph
        component = max(nx.strongly_connected_components(graph), key=len)
        return cast(nx.MultiDiGraph, graph.subgraph(component).copy())

    def _to_topology(self, graph: nx.MultiDiGraph) -> TopologyData:
        nodes = {
            str(node_id): NodeData(
                x=float(data["x"]),
                y=float(data["y"]),
                is_boundary=graph.degree(node_id) <= 2,
            )
            for node_id, data in graph.nodes(data=True)
        }
        x_values = [node.x for node in nodes.values()]
        y_values = [node.y for node in nodes.values()]
        bbox = BoundingBox(
            min_x=min(x_values),
            max_x=max(x_values),
            min_y=min(y_values),
            max_y=max(y_values),
        )
        edges = {}
        for u, v, key, data in graph.edges(keys=True, data=True):
            speed_kph = _parse_speed_kph(data.get("speed_kph", data.get("maxspeed", 30.0)))
            lanes, lane_source = _edge_lanes(data)
            length_m = float(data.get("length", 50.0))
            travel_time_sec = float(data.get("travel_time", length_m / max(speed_kph / 3.6, 1e-6)))
            geometry = data.get("geometry")
            if geometry is not None and hasattr(geometry, "coords"):
                points = [(float(x), float(y)) for x, y in geometry.coords]
            else:
                points = [
                    (float(graph.nodes[u]["x"]), float(graph.nodes[u]["y"])),
                    (float(graph.nodes[v]["x"]), float(graph.nodes[v]["y"])),
                ]
            edges[(str(u), str(v), int(key))] = EdgeData(
                length_m=length_m,
                speed_kph=speed_kph,
                travel_time_sec=travel_time_sec,
                n_cells=max(1, int(length_m / CELL_SIZE_M)),
                vmax_cells=_speed_to_vmax(speed_kph),
                geometry_points=points,
                lanes=lanes,
                lane_source=lane_source,
                allows_lane_change=lanes > 1,
            )
        return TopologyData(nodes=nodes, edges=edges, bbox=bbox)
