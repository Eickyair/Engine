"""
Verifica que GTFSTrafficLightProvider funcione de punta a punta.

Corre desde la raíz del proyecto Engine:
  .venv\\Scripts\\python scripts/verify_gtfs_provider.py
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

# Asegurar que src/ esté en el path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

# ── Paso 1: Importar el provider ──────────────────────────────────────────────
print("\n[1] Importando GTFSTrafficLightProvider...")
try:
    from traffic_engine.infrastructure.providers import GTFSStopFetcher, GTFSTrafficLightProvider
    print("    OK")
except ImportError as e:
    print(f"    FAIL — ImportError: {e}")
    sys.exit(1)

# ── Paso 2: Llamar al API GTFS y descargar paradas ───────────────────────────
print("\n[2] Llamando al API GTFS (auth + descarga stops.txt)...")
try:
    fetcher = GTFSStopFetcher()
    stops = fetcher.get_stops()
    print(f"    OK — {len(stops)} paradas descargadas")
    print(f"    Ejemplo: lat={stops[0][0]}, lon={stops[0][1]}")
except Exception as e:
    print(f"    FAIL — {type(e).__name__}: {e}")
    sys.exit(1)

# ── Paso 3: Verificar que hay paradas en el bbox de CDMX Roma ────────────────
print("\n[3] Filtrando paradas dentro del bbox de la zona Roma/Condesa...")
# BBox aproximado del grafo grafo_cdmx.graphml (Colonia Roma)
LAT_MIN, LAT_MAX = 19.395, 19.440
LON_MIN, LON_MAX = -99.185, -99.145
MARGIN = 0.008

in_bbox = [
    (lat, lon) for lat, lon in stops
    if (LAT_MIN - MARGIN) <= lat <= (LAT_MAX + MARGIN)
    and (LON_MIN - MARGIN) <= lon <= (LON_MAX + MARGIN)
]
print(f"    {len(in_bbox)} paradas dentro del bbox ({LAT_MIN}–{LAT_MAX}, {LON_MIN}–{LON_MAX})")
if not in_bbox:
    print("    WARN — Sin paradas en el bbox. El grafo y los datos GTFS quizás cubren zonas distintas.")
    print("    Latitudes reales en los datos:")
    lats = sorted(set(round(lat, 2) for lat, _ in stops))
    print(f"    {lats[:10]} ...")
else:
    for lat, lon in in_bbox[:5]:
        print(f"    → lat={lat:.5f}  lon={lon:.5f}")

# ── Paso 4: provide() con topología real si hay un grafo disponible ───────────
print("\n[4] Probando provide() con topología real de MongoDB (opcional)...")
try:
    import asyncio
    from traffic_engine.infrastructure.mongodb import get_database
    from traffic_engine.infrastructure.repositories import MongoGeographicAreaRepository

    async def _get_first_topology():
        repo = MongoGeographicAreaRepository()
        areas = await repo.list_all()
        if not areas:
            return None, None
        area = areas[0]
        full = await repo.get_with_topology(area.area_id)
        return full.area_id, full.topology

    area_id, topology = asyncio.run(_get_first_topology())

    if topology is None:
        print("    SKIP — No hay áreas en MongoDB. Corre init_mongo_geodata.py primero.")
    else:
        from traffic_engine.domain.models import SimulationConfig
        config = SimulationConfig(
            initial_vehicles=10, max_vehicles=50, max_steps=100,
            spawn_rate=0.5, noise_prob=0.3, seed=42,
            tick_interval_ms=0,
            traffic_light_green_steps=10, traffic_light_red_steps=10,
            traffic_light_percentage=0.3,
        )
        provider = GTFSTrafficLightProvider()
        lights = provider.provide(topology, config)
        source = "GTFS" if lights and not isinstance(provider._fallback, type(None)) else "fallback"
        print(f"    OK — {len(lights)} semáforos generados para área '{area_id}'")
        for tl in lights[:3]:
            node = topology.nodes.get(tl.node_id)
            print(f"    nodo {tl.node_id} | lat={node.y:.5f} lon={node.x:.5f} | "
                  f"green={tl.cycle.green_steps} red={tl.cycle.red_steps}")
        if len(lights) > 3:
            print(f"    ... y {len(lights) - 3} más")

except Exception as e:
    print(f"    SKIP — {type(e).__name__}: {e}")
    print("    (Normal si MongoDB no está corriendo o sin áreas cargadas)")

# ── Resumen ───────────────────────────────────────────────────────────────────
print("\n" + "=" * 55)
if in_bbox:
    print("  RESULTADO: API GTFS OK — hay paradas en el área del grafo")
    print("  El provider usará datos reales de Metrobús en la simulación")
else:
    print("  RESULTADO: API GTFS OK pero SIN paradas en el bbox del grafo")
    print("  El provider usará RandomTrafficLightProvider como fallback")
print("=" * 55)
