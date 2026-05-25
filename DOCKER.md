# Docker — guia de uso en produccion

Esta guia describe como construir y operar la API de **traffic-engine** usando la imagen Docker provista por el `Dockerfile` de la raiz del repositorio. La intencion es que cualquier equipo consumidor pueda levantar la API en local con un solo comando, sin necesidad de instalar Python, dependencias nativas (GEOS, SpatialIndex) ni configurar entornos virtuales.

## TL;DR

```bash
cp .env.example .env       # ajusta credenciales si vas a exponer la API
docker compose up -d       # construye la imagen, corre tests, levanta mongo + api
curl http://127.0.0.1:8000/health
```

La API queda disponible en `http://127.0.0.1:8000`. Swagger UI en `/docs`.

---

## 1. Que incluye el build

El `Dockerfile` es **multi-stage** con tres etapas:

| Stage     | Proposito                                                                                   |
|-----------|---------------------------------------------------------------------------------------------|
| `builder` | Instala dependencias de runtime en un venv aislado (`/opt/venv`).                           |
| `test`    | Extiende `builder` con extras `[dev]` y ejecuta **toda la suite de `pytest`** dentro del contenedor. |
| `runtime` | Imagen final basada en `python:3.11-slim`. Copia solo el venv del builder + un marker de la etapa `test`. |

**Gate de tests:** el stage `runtime` hace `COPY --from=test /opt/build-meta/tests-passed`. Ese fichero **solo existe si `pytest` salio con codigo 0**, por lo que Docker se ve forzado a construir y pasar la etapa `test` antes de poder producir la imagen final. **Un test fallido = build fallido.**

La imagen final **no contiene** los tests, ni las dev-deps (pytest, mypy, black), ni las build-tools (`build-essential`, `libgeos-dev`). Esto la mantiene pequena y reduce la superficie de ataque.

---

## 2. Construir la imagen

### Build estandar

```bash
docker build -t traffic-engine:latest .
```

Esto corre los tres stages. Tarda mas la primera vez porque baja e instala `numpy`, `osmnx`, `fastapi`, etc. — builds subsecuentes aprovechan la cache de capas mientras no cambien `pyproject.toml` ni `src/`.

### Solo correr los tests (sin producir imagen runtime)

Util en CI o pre-commit hooks cuando solo quieres validar:

```bash
docker build --target test -t traffic-engine:test .
```

### Cambiar la version de Python

```bash
docker build --build-arg PYTHON_VERSION=3.12 -t traffic-engine:py312 .
```

### Build sin cache (cuando dependes de versiones flotantes)

```bash
docker build --no-cache -t traffic-engine:latest .
```

---

## 3. Levantar la API

### Opcion A — `docker compose` (recomendada, un solo comando)

El `docker-compose.yml` define dos servicios: `mongodb` y `api`. Levantarlos juntos:

```bash
docker compose up -d
```

- Construye la imagen `traffic-engine` si no existe.
- Espera a que MongoDB pase su healthcheck.
- Arranca la API en el puerto `8000` (override con `API_PORT` en `.env`).
- La API descubre Mongo via el alias de red `mongodb:27017` (el `MONGODB_URI` se sobrescribe a nivel de compose).

Verificacion:

```bash
docker compose ps
curl http://127.0.0.1:8000/health
docker compose logs -f api
```

Para detener:

```bash
docker compose down            # conserva el volumen de Mongo
docker compose down -v         # borra tambien el volumen
```

### Opcion B — `docker run` standalone

Si ya tienes un Mongo accesible (no necesariamente via compose):

```bash
docker run -d \
  --name traffic-engine-api \
  -p 8000:8000 \
  -e MONGODB_URI="mongodb://user:pass@host:27017/traffic_engine?authSource=traffic_engine" \
  -e MONGODB_DATABASE=traffic_engine \
  -e MONGODB_APP_NAME=traffic-engine-api \
  -e UVICORN_WORKERS=4 \
  traffic-engine:latest
```

---

## 4. Variables de entorno

Variables que la imagen consume:

| Variable             | Default            | Proposito                                                |
|----------------------|--------------------|----------------------------------------------------------|
| `MONGODB_URI`        | (obligatoria)      | Cadena de conexion completa a Mongo.                     |
| `MONGODB_DATABASE`   | `traffic_engine`   | Base de datos donde viven las colecciones.               |
| `MONGODB_APP_NAME`   | `traffic-engine-api` | Identifica la app en logs de Mongo.                    |
| `UVICORN_HOST`       | `0.0.0.0`          | Interfaz a escuchar dentro del contenedor.               |
| `UVICORN_PORT`       | `8000`             | Puerto interno.                                          |
| `UVICORN_WORKERS`    | `2`                | Procesos uvicorn. Ajusta a `2 * vCPU + 1` aprox.         |

Mantén `.env` fuera del control de versiones (ya esta en `.gitignore`). El `.dockerignore` tambien lo excluye del build context, asi que **no se hornea en la imagen**.

---

## 5. Healthcheck y observabilidad

La imagen incluye `HEALTHCHECK` nativo que hace `GET /health` cada 30s:

```bash
docker inspect --format='{{json .State.Health}}' traffic-engine-api | jq
```

Tambien puedes consultarlo manualmente:

```bash
curl -fsS http://127.0.0.1:8000/health
```

Logs estructurados de uvicorn van a `stdout` / `stderr`, capturables con `docker logs` o cualquier driver compatible (`journald`, `fluentd`, `awslogs`, etc.).

---

## 6. Deploy patterns

### Servidor unico con `docker compose`

El escenario mas comun para equipos de integracion: una VM con Docker, este repo clonado, `.env` configurado, y:

```bash
docker compose pull   # o `docker compose build` si construyes localmente
docker compose up -d
```

Para actualizaciones:

```bash
git pull
docker compose up -d --build
```

### Detras de un reverse proxy (nginx / traefik / caddy)

La API ya envia `--proxy-headers`, asi que `X-Forwarded-For` y `X-Forwarded-Proto` son honrados. Configura el reverse proxy para:

- Terminar TLS (la imagen no incluye certificados).
- Apuntar a `api:8000` (dentro de la red de compose) o `127.0.0.1:8000` (si el proxy esta en el host).
- Conservar headers para WebSocket en `/simulations/{id}/ws`.

### Kubernetes (esquema)

La imagen es stateless: cualquier orquestador funciona. Esquema minimo:

- `Deployment` con replicas N
- `Service` ClusterIP en puerto 8000
- `Secret` con `MONGODB_URI` montado como env
- `livenessProbe` / `readinessProbe` a `GET /health`
- `Ingress` para exponer

---

## 7. Solucion de problemas

| Sintoma                                               | Probable causa / fix                                                                                  |
|-------------------------------------------------------|-------------------------------------------------------------------------------------------------------|
| Build falla en stage `test`                           | Algun test fallo. Mira el output o reconstruye solo ese stage: `docker build --target test .`.        |
| `pip install` lento o tira timeout                    | Mirror lento. Usa `--build-arg PIP_INDEX_URL=...` o un proxy interno.                                 |
| Contenedor reinicia en loop                           | Revisa `docker compose logs api`. Lo mas comun: `MONGODB_URI` invalido o Mongo aun no listo.          |
| `curl /health` da `connection refused` desde el host  | Verifica `docker compose ps`. La API tarda ~10–20s en arrancar; el healthcheck tiene `start-period=20s`. |
| Imagen demasiado grande                               | Build context contaminado. Revisa que `.dockerignore` cubra `.venv/`, `cache/`, `assets/external/`.   |
| Permisos al escribir cache                            | El contenedor corre como UID 10001 (`app`). Si montas volumenes, asegura permisos compatibles.        |

---

## 8. Modo desarrollo con hot reload

Para devs que quieren editar codigo y ver cambios sin rebuildear la imagen cada vez, el repo incluye un overlay `docker-compose.dev.yml`:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
# o con Make:
make dev
```

Que hace el overlay:

- Monta `./src` dentro del contenedor como bind read-only.
- Setea `PYTHONPATH=/build/src` para que Python importe desde el mount en vez del paquete instalado en `/opt/venv` (PYTHONPATH se evalua antes de site-packages).
- Cambia el `command` para correr `uvicorn ... --reload --reload-dir /build/src`.
- Reduce workers a 1 (el watcher de reload solo tiene sentido con un proceso).
- Desactiva `restart` asi un crash es visible en consola.

NO usar en produccion: el overlay deshabilita workers paralelos y mantiene el codigo fuera de la imagen, sacrificando reproducibilidad y throughput a cambio de feedback rapido.

---

## 9. Integracion continua

El workflow `.github/workflows/docker-build.yml` corre en cada PR a `main`:

1. Buildea la imagen completa, lo que dispara el stage `test` (pytest dentro del contenedor).
2. Levanta el stack con `docker compose up -d`.
3. Espera a que el healthcheck del servicio `api` pase a `healthy`.
4. Hace `curl /health` desde el runner.
5. Tear down y limpieza.

Si cualquier paso falla, el job falla y bloquea el merge. El cache de capas vive en GitHub Actions (`type=gha`), asi que builds incrementales son rapidos.

Coexiste con `pr-tests.yml` (que corre `pytest` directo, mas rapido) — los dos juntos cubren feedback rapido + validacion end-to-end.

---

## 10. Decisiones de diseno

- **Multi-stage con test gate.** En vez de correr tests en un script aparte de CI, los amarramos al `docker build`. Cualquier intento de buildear la imagen final ejecuta la suite; no hay forma de publicar una imagen verde sin pasar tests.
- **Venv en `/opt/venv`.** Permite `COPY --from=builder /opt/venv` limpiamente al runtime sin arrastrar pip, compiladores ni headers de sistema.
- **Usuario no-root (`app`, UID 10001).** Reduce el blast radius de un RCE; permite montar volumenes con permisos predecibles.
- **`python:3.11-slim`.** Base oficial debian-slim, mantenida, mas rapida que 3.10 sin comprometer compatibilidad de deps.
- **`HEALTHCHECK` nativo.** Funciona con `docker`, `docker compose`, Swarm y la mayoria de orquestadores sin configuracion extra.
