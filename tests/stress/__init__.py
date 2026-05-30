"""
Prueba de estrés para Traffic Engine API.

Uso con UI (recomendado para baseline):
    locust -f tests/stress/locustfile.py --host=http://127.0.0.1:8000
    Abre: http://localhost:8089

Uso headless (para guardar CSV):
    locust -f tests/stress/locustfile.py --host=http://127.0.0.1:8000 ^
           --users 10 --spawn-rate 2 --run-time 60s --headless ^
           --csv=tests/stress/results/baseline
"""

from locust import HttpUser, task, between, constant
import random

# IDs reales cargados por init_mongo_geodata.py
AREA_IDS = [
    "colonia-roma-cuauht-moc-ciudad-de-m-xico-mexico",
    "condesa-cuauht-moc-ciudad-de-m-xico-mexico",
    "centro-hist-rico-cuauht-moc-ciudad-de-m-xico-mexico",
]

# Guarda IDs de simulaciones creadas para reutilizarlas
_created_simulation_ids: list[str] = []


class LightUser(HttpUser):
    """
    Usuario que solo consulta endpoints de lectura (GET).
    Simula el consumo de la app móvil.
    Seguro para laptops: pocas peticiones, espera entre requests.
    """
    wait_time = between(1, 3)  # espera 1-3s entre requests

    @task(5)
    def health(self):
        self.client.get("/health", name="/health")

    @task(10)
    def list_areas(self):
        self.client.get("/geographic-areas", name="/geographic-areas")

    @task(3)
    def get_topology(self):
        area_id = random.choice(AREA_IDS)
        self.client.get(
            f"/geographic-areas/{area_id}/topology",
            name="/geographic-areas/{area_id}/topology",
        )

    @task(4)
    def get_simulation_if_exists(self):
        if not _created_simulation_ids:
            return
        sim_id = random.choice(_created_simulation_ids)
        self.client.get(
            f"/simulations/{sim_id}",
            name="/simulations/{simulation_id}",
        )

    @task(2)
    def list_steps_if_exists(self):
        if not _created_simulation_ids:
            return
        sim_id = random.choice(_created_simulation_ids)
        self.client.get(
            f"/simulations/{sim_id}/steps",
            name="/simulations/{simulation_id}/steps",
        )


class WriteUser(HttpUser):
    """
    Usuario que crea simulaciones.
    Usa wait_time largo para no saturar la CPU.
    Máximo recomendado: 3-5 usuarios de este tipo.
    """
    wait_time = between(5, 10)  # espera más para no saturar

    @task
    def create_simulation(self):
        area_id = random.choice(AREA_IDS)
        payload = {
            "area_id": area_id,
            "initial_vehicles": 20,
            "max_vehicles": 50,
            "max_steps": 30,
            "execution_mode": "classic",
            "default_lanes": 2,
            "traffic_light_percentage": 0.3,
            "traffic_light_green_steps": 5,
            "traffic_light_red_steps": 3,
            "enable_lane_changes": False,
        }
        with self.client.post(
            "/simulations",
            json=payload,
            name="/simulations [POST]",
            catch_response=True,
        ) as resp:
            if resp.status_code == 201:
                sim_id = resp.json().get("simulation_id")
                if sim_id and sim_id not in _created_simulation_ids:
                    _created_simulation_ids.append(sim_id)
                resp.success()
            elif resp.status_code == 429:
                # Capacidad excedida — es esperado bajo carga, no es falla
                resp.success()
            else:
                resp.failure(f"Error inesperado: {resp.status_code}")