# Traffic Engine

API de simulacion de trafico basada en FastAPI, NaSch y MongoDB.

## Requisitos

- Python 3.10 o superior
- Docker y Docker Compose
- Acceso a internet si vas a precargar areas con OSMnx

## Variables de entorno

1. Crea tu archivo local:

```bash
cp .env.example .env
```

1. Ajusta al menos estas variables antes de usar produccion:

- `MONGO_ROOT_PASSWORD`
- `MONGO_APP_PASSWORD`
- `MONGODB_URI`

La API lee la conexion Mongo desde `.env` usando `MONGODB_URI`, `MONGODB_DATABASE` y `MONGODB_APP_NAME`.

## Desarrollo

### 1. Crear y activar entorno virtual

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
```

### 2. Levantar MongoDB local

```bash
docker compose up -d mongodb
docker compose ps mongodb
```

Mongo se inicializa con:

- autenticacion habilitada
- usuario de aplicacion dedicado
- colecciones base: `geographic_areas`, `simulations`, `simulation_steps`
- indices unicos para areas, simulaciones y pasos

### 3. Precargar areas geograficas en Mongo

Carga el set por defecto de CDMX:

```bash
python scripts/init_mongo_geodata.py
```

El bootstrap reemplaza cada area por `area_id`, por lo que puedes volver a ejecutarlo para actualizar documentos antiguos. La topologia persistida incluye `lanes`, `lane_source` y `allows_lane_change` por cada tramo, datos que el motor usa para simular multiples carriles y posibles cambios de carril.

O carga areas explicitas:

```bash
python scripts/init_mongo_geodata.py \
  "Colonia Roma, Cuauhtemoc, Ciudad de Mexico, Mexico" \
  "Condesa, Cuauhtemoc, Ciudad de Mexico, Mexico"
```

### 4. Levantar la API en modo desarrollo

```bash
uvicorn traffic_engine.api.app:app --host 127.0.0.1 --port 8000 --reload
```

Puntos utiles:

- Swagger UI: `http://127.0.0.1:8000/docs`
- OpenAPI: `http://127.0.0.1:8000/openapi.json`
- Healthcheck: `http://127.0.0.1:8000/health`

### 5. Abrir la mini UI de simulacion

Con Mongo y la API levantados, abre una webapp local de un solo script:

```bash
python scripts/mini_simulation_ui.py --api-url http://127.0.0.1:8000
```

La interfaz queda disponible en `http://127.0.0.1:8501`. Permite seleccionar un area geografica, elegir el modelo de simulacion (`continuous` o `classic`), configurar carriles, cambio de carril y semaforos, cargar el grafo discretizado, iniciar una simulacion y observar los vehiculos en vivo por WebSocket.

### 6. Ejecutar pruebas focalizadas

```bash
pytest tests/test_nasch_model.py tests/test_simulation_extensibility.py tests/test_use_cases.py tests/test_api_app.py
```

## Produccion

La forma mas simple de operar este repo hoy es dejar Mongo en Docker y ejecutar la API con Uvicorn en modo multiproceso.

### 1. Preparar entorno

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install .
```

### 2. Configurar variables reales

- copia `.env.example` a `.env`
- cambia credenciales por valores fuertes
- confirma que `MONGODB_URI` apunta al host y puerto correctos

### 3. Levantar MongoDB

```bash
docker compose up -d mongodb
```

### 4. Precargar datos si el ambiente esta vacio

```bash
python scripts/init_mongo_geodata.py
```

### 5. Levantar la API en modo produccion

```bash
uvicorn traffic_engine.api.app:app --host 0.0.0.0 --port 8000 --workers 4 --proxy-headers
```

Notas operativas:

- ajusta `--workers` segun CPU y memoria disponibles
- publica la API detras de un reverse proxy si va a exponerse a internet
- mantén `.env` fuera del control de versiones
- el WebSocket de simulaciones vive en `/simulations/{simulation_id}/ws`

## Parar servicios

Parar solo Mongo y conservar datos:

```bash
docker compose down
```

Parar Mongo y borrar el volumen local:

```bash
docker compose down -v
```

## Endpoints principales

- `GET /health`
- `GET /geographic-areas`
- `GET /geographic-areas/{area_id}/topology`
- `POST /simulations`
- `GET /simulations/{simulation_id}`
- `POST /simulations/{simulation_id}/cancel`
- `GET /simulations/{simulation_id}/steps`
- `WS /simulations/{simulation_id}/ws`

### Parametros utiles de `POST /simulations`

Ademas de `area_id`, el request permite configurar variantes del motor:

- `execution_mode`: `continuous` para spawn/despawn dinamico, o `classic` para mantener solo los vehiculos iniciales.
- `default_lanes`: numero de carriles por segmento cuando el dato de la topologia no especifica otro valor.
- `enable_lane_changes`: habilita la politica de cambio de carril del modelo celular.
- `traffic_light_percentage`: porcentaje de intersecciones validas que reciben semaforo aleatorio, entre `0.0` y `1.0`.
- `traffic_light_green_steps` y `traffic_light_red_steps`: ciclo de cada semaforo en steps.

Los steps devueltos por REST o WebSocket incluyen `state.cells`, `state.vehicles` con carril/celda/direccion, y `state.traffic_lights` con estado y ciclo para renderizar la UI.
