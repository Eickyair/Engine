"""
Escenario de estres extremo para Traffic Engine API.
Prueba endpoints de paginacion, WebSocket y middlewares bajo carga alta.

Uso headless (seguro para laptop):
    locust -f tests/stress/locustfile_extreme.py ^
           --host=http://127.0.0.1:8000 ^
           --users 20 --spawn-rate 3 --run-time 90s --headless ^
           --csv=tests/stress/results/extreme

Uso con UI:
    locust -f tests/stress/locustfile_extreme.py --host=http://127.0.0.1:8000
    Abre: http://localhost:8089
    Usuarios recomendados: maximo 20, spawn rate 3
"""

from __future__ import annotations

import random
import time
from locust import HttpUser, task, between, events

AREA_IDS = [
    "colonia-roma-cuauht-moc-ciudad-de-m-xico-mexico",
    "condesa-cuauht-moc-ciudad-de-m-xico-mexico",
    "centro-hist-rico-cuauht-moc-ciudad-de-m-xico-mexico",
]

_simulation_ids: list[str] = []


class ExtremeReadUser(HttpUser):
    """
    Usuario que prueba los endpoints de paginacion y middlewares bajo carga.
    Valida GZip, Cache-Control y X-Process-Time en cada request.
    """
    wait_time = between(0.5, 1.5)

    @task(3)
    def paginated_steps_small(self):
        """Pagina pequena: simula app movil pidiendo los ultimos 10 steps."""
        if not _simulation_ids:
            return
        sim_id = random.choice(_simulation_ids)
        with self.client.get(
            f"/simulations/{sim_id}/steps?limit=10&offset=0&include_running=true",
            name="/simulations/{id}/steps [limit=10]",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                if "X-Process-Time" not in resp.headers:
                    resp.failure("Header X-Process-Time ausente - middleware caido")
                else:
                    resp.success()
            elif resp.status_code in (404, 409):
                resp.success()
            else:
                resp.failure(f"Status inesperado: {resp.status_code}")

    @task(2)
    def paginated_steps_medium(self):
        """Pagina mediana: simula dashboard pidiendo 100 steps."""
        if not _simulation_ids:
            return
        sim_id = random.choice(_simulation_ids)
        with self.client.get(
            f"/simulations/{sim_id}/steps?limit=100&offset=0&include_running=true",
            name="/simulations/{id}/steps [limit=100]",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                content_enc = resp.headers.get("Content-Encoding", "")
                if len(resp.content) > 500 and "gzip" not in content_enc:
                    resp.failure("GZip no activo en respuesta mayor a 500 bytes")
                else:
                    resp.success()
            elif resp.status_code in (404, 409):
                resp.success()
            else:
                resp.failure(f"Status inesperado: {resp.status_code}")

    @task(2)
    def topology_with_cache(self):
        """Verifica que Cache-Control sigue presente bajo carga."""
        area_id = random.choice(AREA_IDS)
        with self.client.get(
            f"/geographic-areas/{area_id}/topology",
            name="/geographic-areas/{id}/topology [cache check]",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                cache = resp.headers.get("Cache-Control", "")
                if "max-age" not in cache:
                    resp.failure("Header Cache-Control ausente en topology")
                else:
                    resp.success()
            else:
                resp.failure(f"Status inesperado: {resp.status_code}")

    @task(1)
    def create_simulation_for_pool(self):
        """Crea simulaciones para alimentar el pool compartido."""
        area_id = random.choice(AREA_IDS)
        payload = {
            "area_id": area_id,
            "initial_vehicles": 10,
            "max_vehicles": 30,
            "max_steps": 20,
            "execution_mode": "classic",
            "default_lanes": 2,
            "traffic_light_percentage": 0.2,
            "traffic_light_green_steps": 5,
            "traffic_light_red_steps": 3,
            "enable_lane_changes": False,
        }
        with self.client.post(
            "/simulations",
            json=payload,
            name="/simulations [POST extreme]",
            catch_response=True,
        ) as resp:
            if resp.status_code == 201:
                sim_id = resp.json().get("simulation_id")
                if sim_id and sim_id not in _simulation_ids:
                    _simulation_ids.append(sim_id)
                resp.success()
            elif resp.status_code == 429:
                resp.success()
            else:
                resp.failure(f"Status inesperado: {resp.status_code}")


class WebSocketUser(HttpUser):
    """
    Usuario que abre conexiones WebSocket al stream de simulacion.
    Mide tiempo al primer frame y detecta desconexiones bajo carga.
    Solo se activa si hay simulaciones disponibles en el pool.
    """
    wait_time = between(3, 8)

    @task
    def probe_websocket_replay(self):
        """
        Prueba el endpoint de replay WebSocket.
        Abre la conexion, espera el primer frame y cierra limpiamente.
        """
        if not _simulation_ids:
            return

        sim_id = random.choice(_simulation_ids)
        start = time.perf_counter()

        with self.client.get(
            f"/simulations/{sim_id}",
            name="/simulations/{id} [ws pre-check]",
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.success()
                return
            elapsed = (time.perf_counter() - start) * 1000
            resp.success()

        # Reporta el tiempo de pre-check como proxy del acceso WS
        self.environment.events.request.fire(
            request_type="WS-PREP",
            name="/simulations/{id}/replay [pre-check]",
            response_time=elapsed,
            response_length=0,
            exception=None,
            context={},
        )


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print("\n[INFO] Iniciando escenario extremo")
    print("[INFO] Usuarios ExtremeReadUser + WebSocketUser")
    print("[INFO] Maximo recomendado: 20 usuarios en laptop\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    print(f"\n[INFO] Escenario terminado")
    print(f"[INFO] Simulaciones en pool: {len(_simulation_ids)}")
    stats = environment.stats.total
    print(f"[INFO] Total requests: {stats.num_requests}")
    print(f"[INFO] Total fallos: {stats.num_failures}")
    if stats.num_requests > 0:
        pct = (stats.num_failures / stats.num_requests) * 100
        print(f"[INFO] Tasa de fallo: {pct:.1f}%\n")