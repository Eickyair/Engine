---
description: "Genera documentación de un endpoint de la API Traffic Engine en el estilo del proyecto: encabezado METHOD + URL, descripción breve en español, ejemplo JSON recortado si es grande, tabla de campos | Campo | Descripcion |"
name: "Documentar endpoint de API"
argument-hint: "Describe el endpoint: método, ruta, qué hace y campos relevantes"
agent: "agent"
tools: [codebase, read_file]
---

Genera la sección de documentación para el endpoint indicado, siguiendo **estrictamente** el estilo del proyecto Traffic Engine.

## Reglas de estilo

1. **Encabezado**: `## METHOD \`url completa\`` — usa la URL base `http://127.0.0.1:8000` salvo que se indique otra.
2. **Descripción**: Una o dos frases en español, sin tecnicismos innecesarios. Si el endpoint requiere un parámetro en la URL, menciona brevemente qué representa.
3. **Nota de recorte** (solo si la respuesta puede ser muy grande): agrega una línea en cursiva antes del bloque JSON:
   > *Muestra recortada: la respuesta real incluye todos los `<elementos>` del área.*
4. **Ejemplo JSON**: bloque ` ```json ` con una respuesta real o representativa; recórtala si tiene colecciones grandes (máximo 1–2 elementos ilustrativos).
5. **Tabla de campos**: inmediatamente después del JSON, una tabla Markdown con dos columnas: `| Campo | Descripcion |`. Sigue estas convenciones:
   - Los nombres de campo van entre backticks: `` `campo` ``.
   - Campos anidados: `` `padre.hijo` `` o `` `padre[].hijo` ``.
   - Campos alternativos en la misma fila: `` `campo_a` / `campo_b` ``.
   - Descripciones cortas, en español, sin punto final.
   - Si un campo tiene valores enumerados, listarlos: `` `running`, `finished` o `cancelled` ``.
6. **WebSocket**: si el endpoint es WS (`ws://...`), documenta por separado cada tipo de evento con sub-encabezado `### Evento \`type\``, su propio JSON de ejemplo y su propia tabla de campos. Indica también las condiciones de cierre de la conexión.
7. **Idioma**: todo el texto en español, igual que el resto del archivo.
8. **Sin secciones extra**: no agregues introducciones, conclusiones ni secciones que no aparezcan en el estilo de referencia.

## Inputs esperados

Proporciona cualquier combinación de los siguientes datos sobre el endpoint:

- Método HTTP y ruta (p. ej. `POST /simulations`)
- Descripción funcional de qué hace
- Cuerpo de request (si aplica)
- Ejemplo de respuesta JSON (completo o parcial)
- Lista de campos importantes con su significado

Si falta información, infiere valores representativos del contexto del proyecto (simulaciones de tráfico, áreas geográficas, vehículos) y marca con `<!-- TODO: verificar -->` los valores que asumiste.

## Ejemplo de salida esperada

```markdown
## POST `http://127.0.0.1:8000/simulations`

Crea una nueva simulación sobre un área geográfica previamente cargada y la pone en estado `running` de inmediato.

\```json
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
    "max_steps": 3
  }
}
\```

| Campo | Descripcion |
| --- | --- |
| `simulation_id` | Identificador de la simulación creada |
| `area_id` | Área geográfica usada para ejecutar la simulación |
| `status` | Estado actual: `running`, `finished` o `cancelled` |
| `latest_step` | Último paso registrado al momento de responder |
| `created_at` / `updated_at` | Fechas de creación y última actualización |
| `config.initial_vehicles` | Vehículos iniciales en la simulación |
| `config.max_vehicles` | Máximo de vehículos permitidos |
| `config.max_steps` | Máximo de pasos a ejecutar |
```

---

Ahora genera la documentación para el siguiente endpoint:

$args
