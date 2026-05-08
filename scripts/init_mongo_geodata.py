"""Initialize MongoDB with preprocessed geographic areas from OSMnx."""

from __future__ import annotations

import argparse

from traffic_engine.application.use_cases import BootstrapGeographicAreasUseCase
from traffic_engine.infrastructure import MongoGeographicAreaRepository, OSMnxGeographicAreaSource


DEFAULT_AREAS = [
    "Colonia Roma, Cuauhtémoc, Ciudad de México, Mexico",
    "Condesa, Cuauhtémoc, Ciudad de México, Mexico",
    "Centro Histórico, Cuauhtémoc, Ciudad de México, Mexico",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download OSM road networks and persist preprocessed geographic areas in MongoDB.",
    )
    parser.add_argument(
        "areas",
        nargs="*",
        help="Optional place names to bootstrap. Defaults to a curated CDMX list.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    place_names = args.areas or DEFAULT_AREAS
    use_case = BootstrapGeographicAreasUseCase(
        source=OSMnxGeographicAreaSource(),
        repository=MongoGeographicAreaRepository(),
    )
    areas = use_case.execute(place_names)
    for area in areas:
        multi_lane_edges = sum(1 for edge in area.topology.edges.values() if edge.lanes > 1)
        print(
            f"{area.area_id}: {area.name} | nodes={area.node_count} | "
            f"edges={area.edge_count} | multi_lane_edges={multi_lane_edges}"
        )


if __name__ == "__main__":
    main()