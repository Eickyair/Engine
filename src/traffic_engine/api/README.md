# Traffic Engine API

Las respuestas de topologia, schemas y steps pueden ser muy grandes; aqui se muestran recortadas, manteniendo la estructura que devuelve la API.

## GET `http://127.0.0.1:8000/health`

```json
{
  "status": "ok"
}
```

| Campo | Descripcion |
| --- | --- |
| `status` | Estado basico de salud de la API. `ok` indica que responde correctamente. |

## GET `http://127.0.0.1:8000/api/response-models.json`

Devuelve el esquema de todos los endpoints de la API extraido del OpenAPI en tiempo de ejecucion.

*Muestra recortada: la respuesta real incluye todos los endpoints registrados.*

```json
{
  "source": "/openapi.json",
  "endpoints": [
    {
      "path": "/geographic-areas",
      "method": "GET",
      "operation_id": "list_geographic_areas",
      "summary": null,
      "description": null,
      "parameters": [],
      "request_body": null,
      "responses": {
        "200": {
          "description": "Successful Response",
          "content_type": "application/json",
          "schema": {}
        }
      }
    }
  ]
}
```

| Campo | Descripcion |
| --- | --- |
| `source` | Ruta del documento OpenAPI del que se extrajeron los esquemas |
| `endpoints[].path` | Ruta del endpoint |
| `endpoints[].method` | Metodo HTTP en mayusculas |
| `endpoints[].operation_id` | Identificador de operacion generado por FastAPI |
| `endpoints[].parameters` | Lista de parametros de ruta, query o header |
| `endpoints[].request_body` | Esquema del cuerpo de la peticion, si aplica |
| `endpoints[].responses` | Mapa de codigo HTTP a esquema de respuesta |

## GET `http://127.0.0.1:8000/geographic-areas`

Devuelve un listado de areas geograficas preprocesadas, con la finalidad de tener un catalogo de colonias o alcaldias en donde ejecutar simulaciones.

```json
[
  {
    "area_id": "centro-hist-rico-cuauht-moc-ciudad-de-m-xico-mexico",
    "name": "Centro Histórico, Cuauhtémoc, Ciudad de México, Mexico",
    "created_at": "2026-05-08T04:58:39.192000",
    "node_count": 1107,
    "edge_count": 2167,
    "bbox": {
      "min_x": -99.1562441,
      "max_x": -99.1106279,
      "min_y": 19.4188572,
      "max_y": 19.4459433
    }
  },
  {
    "area_id": "colonia-roma-cuauht-moc-ciudad-de-m-xico-mexico",
    "name": "Colonia Roma, Cuauhtémoc, Ciudad de México, Mexico",
    "created_at": "2026-05-08T04:58:38.393000",
    "node_count": 348,
    "edge_count": 621,
    "bbox": {
      "min_x": -99.1765626,
      "max_x": -99.1537379,
      "min_y": 19.4105168,
      "max_y": 19.4257547
    }
  },
  {
    "area_id": "condesa-cuauht-moc-ciudad-de-m-xico-mexico",
    "name": "Condesa, Cuauhtémoc, Ciudad de México, Mexico",
    "created_at": "2026-05-08T04:58:38.593000",
    "node_count": 109,
    "edge_count": 194,
    "bbox": {
      "min_x": -99.1810924,
      "max_x": -99.1718043,
      "min_y": 19.4113775,
      "max_y": 19.4202306
    }
  }
]
```

| Campo | Descripcion |
| --- | --- |
| `area_id` | Identificador usado para consultar topologia o crear simulaciones. |
| `name` | Nombre legible del area geografica. |
| `created_at` | Fecha en que el area fue precargada o actualizada. |
| `node_count` | Total de nodos del grafo vial. |
| `edge_count` | Total de tramos o aristas del grafo vial. |
| `bbox` | Limites geograficos: `min_x`, `max_x`, `min_y`, `max_y`. |

## GET `http://127.0.0.1:8000/geographic-areas/condesa-cuauht-moc-ciudad-de-m-xico-mexico/topology`

Muestra la informacion del grafo con la que cuenta una determinada area geografica.

Muestra recortada: la respuesta real incluye todos los `nodes` y `edges` del area.

```json
{
  "area_id": "condesa-cuauht-moc-ciudad-de-m-xico-mexico",
  "name": "Condesa, Cuauhtémoc, Ciudad de México, Mexico",
  "created_at": "2026-05-08T04:58:38.593000",
  "node_count": 109,
  "edge_count": 194,
  "topology": {
    "nodes": {
      "30454718": {
        "x": -99.1762352,
        "y": 19.4155413,
        "is_boundary": false
      }
    },
    "edges": [
      {
        "u": "30454718",
        "v": "31062169",
        "key": 0,
        "length_m": 53.92959020046084,
        "speed_kph": 50.0,
        "travel_time_sec": 3.88293049443318,
        "n_cells": 7,
        "vmax_cells": 2,
        "lanes": 3,
        "lane_source": "lanes",
        "allows_lane_change": true,
        "direction": [
          "30454718",
          "31062169"
        ],
        "geometry_points": [
          [-99.1762352, 19.4155413],
          [-99.1760075, 19.4154282],
          [-99.1757802, 19.4153153]
        ]
      }
    ],
    "bbox": {
      "min_x": -99.1810924,
      "max_x": -99.1718043,
      "min_y": 19.4113775,
      "max_y": 19.4202306
    }
  }
}
```

| Campo | Descripcion |
| --- | --- |
| `area_id` | Identificador del area consultada. |
| `topology.nodes` | Diccionario de nodos; cada llave es el id del nodo. |
| `nodes.*.x` / `nodes.*.y` | Coordenadas del nodo. |
| `nodes.*.is_boundary` | Indica si el nodo esta en el borde del area. |
| `topology.edges` | Lista de tramos viales entre nodos. |
| `edges[].u` / `edges[].v` | Nodo origen y nodo destino del tramo. |
| `edges[].length_m` | Longitud del tramo en metros. |
| `edges[].n_cells` | Celdas discretizadas usadas por el modelo. |
| `edges[].lanes` | Numero de carriles del tramo. |
| `edges[].geometry_points` | Puntos geograficos para dibujar el tramo. |
| `topology.bbox` | Limites geograficos del grafo. |

## POST `http://127.0.0.1:8000/simulations`

Crea una nueva simulacion sobre un area geografica previamente cargada y la pone en estado `running` de inmediato.

- `404` — el `area_id` indicado no existe
- `422` — parametros de configuracion invalidos
- `429` — el servidor ha alcanzado el maximo de simulaciones concurrentes permitidas

Respuesta usando `area_id` valido `condesa-cuauht-moc-ciudad-de-m-xico-mexico`.

```json
{
  "simulation_id": "efa6f5be62084322babe09ccc9fc522e",
  "area_id": "condesa-cuauht-moc-ciudad-de-m-xico-mexico",
  "status": "running",
  "latest_step": 0,
  "created_at": "2026-05-09T14:18:21.219000",
  "updated_at": "2026-05-09T14:18:21.219000",
  "config": {
    "initial_vehicles": 3,
    "max_vehicles": 3,
    "max_steps": 3,
    "spawn_rate": 0.0,
    "noise_prob": 0.2,
    "seed": 21,
    "tick_interval_ms": 0,
    "execution_mode": "classic",
    "default_lanes": 1,
    "traffic_light_percentage": 0.0,
    "traffic_light_green_steps": 10,
    "traffic_light_red_steps": 10,
    "enable_lane_changes": false
  }
}
```

| Campo | Descripcion |
| --- | --- |
| `simulation_id` | Identificador de la simulacion creada. |
| `area_id` | Area geografica usada para ejecutar la simulacion. |
| `status` | Estado actual: `running`, `finished` o `cancelled`. |
| `latest_step` | Ultimo paso registrado al momento de responder. |
| `created_at` / `updated_at` | Fechas de creacion y ultima actualizacion. |
| `config.initial_vehicles` | Vehiculos iniciales. |
| `config.max_vehicles` | Maximo de vehiculos permitidos. |
| `config.max_steps` | Maximo de pasos a ejecutar. |
| `config.execution_mode` | Modo de simulacion: `classic` o `continuous`. |
| `config.tick_interval_ms` | Pausa entre pasos en milisegundos. |
| `config.traffic_light_*` | Configuracion de semaforos. |
| `config.enable_lane_changes` | Indica si se permiten cambios de carril. |

## GET `http://127.0.0.1:8000/simulations/efa6f5be62084322babe09ccc9fc522e`

El ultimo parametro es el id de la simulacion.

```json
{
  "simulation_id": "efa6f5be62084322babe09ccc9fc522e",
  "area_id": "condesa-cuauht-moc-ciudad-de-m-xico-mexico",
  "status": "finished",
  "latest_step": 3,
  "created_at": "2026-05-09T14:18:21.219000",
  "updated_at": "2026-05-09T14:18:21.219000",
  "config": {
    "initial_vehicles": 3,
    "max_vehicles": 3,
    "max_steps": 3,
    "spawn_rate": 0.0,
    "noise_prob": 0.2,
    "seed": 21,
    "tick_interval_ms": 0,
    "execution_mode": "classic",
    "default_lanes": 1,
    "traffic_light_percentage": 0.0,
    "traffic_light_green_steps": 10,
    "traffic_light_red_steps": 10,
    "enable_lane_changes": false
  }
}
```

| Campo | Descripcion |
| --- | --- |
| `simulation_id` | Identificador de la simulacion consultada. |
| `area_id` | Area sobre la que se ejecuto. |
| `status` | Estado actual de la simulacion. |
| `latest_step` | Ultimo paso generado. |
| `created_at` / `updated_at` | Fechas de creacion y actualizacion. |
| `config` | Parametros con los que fue creada la simulacion. |

## GET `http://127.0.0.1:8000/simulations/efa6f5be62084322babe09ccc9fc522e/steps`

Este endpoint esta pensado para recuperar la informacion una vez terminado todo el proceso.

Muestra recortada a un step, una celda y un vehiculo. La respuesta real puede incluir mas elementos en `cells`, `vehicles` y `traffic_lights`.

```json
[
  {
    "simulation_id": "efa6f5be62084322babe09ccc9fc522e",
    "step_number": 1,
    "metrics": {
      "step_number": 1,
      "total_vehicles": 3,
      "avg_speed_kph": 27.0,
      "density": 0.0008077544426494346,
      "throughput_veh_per_min": 0.0,
      "congestion_ratio": 0.0
    },
    "state": {
      "cells": [
        {
          "edge": ["30454718", "31062169", 0],
          "cell_position": 0,
          "lane_count": 3,
          "direction": ["30454718", "31062169"],
          "vehicles": []
        }
      ],
      "vehicles": [
        {
          "id": 1,
          "edge": ["994764200", "6394850142", 0],
          "x": -99.18031676985606,
          "y": 19.414195133728867,
          "velocity": 1,
          "speed_kph": 27.0,
          "wait_ticks": 0,
          "lane": 0,
          "cell_position": 1,
          "direction": ["994764200", "6394850142"],
          "is_changing_lane": false
        }
      ],
      "traffic_lights": []
    },
    "recorded_at": "2026-05-09T14:18:21.223000"
  }
]
```

| Campo | Descripcion |
| --- | --- |
| `simulation_id` | Simulacion a la que pertenece el paso. |
| `step_number` | Numero de paso dentro de la simulacion. |
| `metrics.total_vehicles` | Vehiculos considerados en el paso. |
| `metrics.avg_speed_kph` | Velocidad promedio en km/h. |
| `metrics.density` | Densidad calculada por el motor. |
| `metrics.congestion_ratio` | Proporcion estimada de congestion. |
| `state.cells` | Celdas del grafo discretizado. |
| `state.vehicles` | Vehiculos con posicion, velocidad, carril y direccion. |
| `state.traffic_lights` | Semaforos activos en el paso. |
| `recorded_at` | Fecha en que se registro el paso. |

## POST `http://127.0.0.1:8000/simulations/30d876c510944132bbe816f3ea80cf5b/cancel`

Es para cancelar una simulacion que esta en `running`.

```json
{
  "simulation_id": "30d876c510944132bbe816f3ea80cf5b",
  "requested": true
}
```

| Campo | Descripcion |
| --- | --- |
| `simulation_id` | Simulacion sobre la que se solicito cancelacion. |
| `requested` | `true` si la solicitud de cancelacion fue aceptada. |

## WS `ws://127.0.0.1:8000/simulations/{simulation_id}/ws`

Permite escuchar una simulacion en vivo. El `simulation_id` debe existir y la simulacion debe estar en estado `running`; si no existe o ya termino, el servidor cierra la conexion con `WS_1008_POLICY_VIOLATION`.

El WebSocket envia dos tipos de mensajes:

- `step`: se emite en cada avance de la simulacion.
- `status`: se emite al final, con `status` igual a `finished` o `cancelled`; despues de este evento la suscripcion se cierra.

### Evento `step`

Este evento incluye el estado completo del paso dentro de `step`. La muestra esta recortada a una celda, un vehiculo y un semaforo para que sea legible; en ejecuciones reales `cells`, `vehicles` y `traffic_lights` pueden traer muchos elementos.

```json
{
  "type": "step",
  "simulation_id": "efa6f5be62084322babe09ccc9fc522e",
  "status": "running",
  "step": {
    "simulation_id": "efa6f5be62084322babe09ccc9fc522e",
    "step_number": 1,
    "metrics": {
      "step_number": 1,
      "total_vehicles": 3,
      "avg_speed_kph": 27.0,
      "density": 0.0008077544426494346,
      "throughput_veh_per_min": 0.0,
      "congestion_ratio": 0.0
    },
    "state": {
      "step_number": 1,
      "vehicles": [
        {
          "id": 1,
          "edge": ["994764200", "6394850142", 0],
          "x": -99.18031676985606,
          "y": 19.414195133728867,
          "velocity": 1,
          "speed_kph": 27.0,
          "wait_ticks": 0,
          "lane": 0,
          "cell_position": 1,
          "direction": ["994764200", "6394850142"],
          "is_changing_lane": false
        }
      ],
      "total_vehicles": 3,
      "active_vehicles": 3,
      "density": 0.0008077544426494346,
      "cells": [
        {
          "edge": ["30454718", "31062169", 0],
          "cell_position": 0,
          "lane_count": 3,
          "direction": ["30454718", "31062169"],
          "vehicles": []
        }
      ],
      "traffic_lights": [
        {
          "node_id": "30454718",
          "x": -99.1762352,
          "y": 19.4155413,
          "state": "green",
          "applies_to": ["31062169"],
          "cycle": {
            "green_steps": 10,
            "red_steps": 10,
            "offset": 0
          }
        }
      ]
    },
    "recorded_at": "2026-05-09T14:18:21.223000"
  }
}
```

Campos principales de `step`:

| Campo | Descripcion |
| --- | --- |
| `type` | Tipo de evento; en este caso `step`. |
| `simulation_id` | Simulacion que emite el evento. |
| `status` | Estado durante el evento; normalmente `running`. |
| `step` | Contenedor del paso completo de simulacion. |
| `metrics.total_vehicles` | Vehiculos considerados en el paso. |
| `metrics.avg_speed_kph` | Velocidad promedio del paso en km/h. |
| `metrics.density` | Densidad vehicular calculada por el motor. |
| `metrics.throughput_veh_per_min` | Flujo estimado de vehiculos por minuto. |
| `metrics.congestion_ratio` | Proporcion de congestion estimada. |
| `state.vehicles` | Posicion, velocidad, carril y direccion de cada vehiculo activo. |
| `state.cells` | Celdas discretizadas por tramo; `vehicles` contiene ids de vehiculos en esa celda. |
| `state.traffic_lights` | Semaforos activos, si la simulacion fue creada con `traffic_light_percentage` mayor a `0`. |

### Evento `status`

Se envia cuando la simulacion termina o se cancela.

```json
{
  "type": "status",
  "simulation_id": "efa6f5be62084322babe09ccc9fc522e",
  "status": "finished"
}
```

| Campo | Descripcion |
| --- | --- |
| `type` | Tipo de evento; en este caso `status`. |
| `simulation_id` | Simulacion que termino o fue cancelada. |
| `status` | Estado final: `finished` o `cancelled`. |

Si se cancela una simulacion en curso, el evento final usa `status: "cancelled"`.

## WS `ws://127.0.0.1:8000/simulations/{simulation_id}/replay`

Reproduce todos los pasos ya grabados de una simulacion. El `simulation_id` identifica la simulacion a reproducir; si no existe, el servidor cierra la conexion con `WS_1008_POLICY_VIOLATION`. A diferencia del WebSocket en vivo, este endpoint acepta simulaciones en cualquier estado.

Envia todos los pasos almacenados como eventos `step` y termina con un evento `status`.

### Evento `step` (replay)

```json
{
  "type": "step",
  "simulation_id": "efa6f5be62084322babe09ccc9fc522e",
  "status": "finished",
  "step": {
    "simulation_id": "efa6f5be62084322babe09ccc9fc522e",
    "step_number": 1,
    "metrics": {
      "step_number": 1,
      "total_vehicles": 3,
      "avg_speed_kph": 27.0,
      "density": 0.0008077544426494346,
      "throughput_veh_per_min": 0.0,
      "congestion_ratio": 0.0
    },
    "state": {},
    "visualization": {}
  }
}
```

| Campo | Descripcion |
| --- | --- |
| `type` | Tipo de evento; en este caso `step` |
| `simulation_id` | Simulacion que se esta reproduciendo |
| `status` | Estado de la simulacion al momento de enviar el evento |
| `step` | Datos completos del paso grabado; misma estructura que `GET /steps` |

### Evento `status` (replay)

Se envia una vez que todos los pasos han sido emitidos.

```json
{
  "type": "status",
  "simulation_id": "efa6f5be62084322babe09ccc9fc522e",
  "status": "finished"
}
```

| Campo | Descripcion |
| --- | --- |
| `type` | Tipo de evento; en este caso `status` |
| `simulation_id` | Simulacion reproducida |
| `status` | Estado final: `finished` o `cancelled` |

Despues de enviar el evento `status` el servidor cierra la conexion normalmente.
