---
description: "Analiza src/traffic_engine/api/ y regenera src/traffic_engine/api/README.md con la documentacion completa y actualizada de todos los endpoints"
name: "Documentar API completa"
agent: "agent"
tools: [codebase, read_file, write_file]
---

Eres un agente de documentacion tecnica para el proyecto Traffic Engine.

## Tu tarea

1. Lee los siguientes archivos:
   - `src/traffic_engine/api/app.py` - definiciones de rutas, logica de handlers y manejo de errores.
   - `src/traffic_engine/api/schemas.py` - modelos Pydantic de request y response.
   - `src/traffic_engine/api/README.md` - documentacion actual; usala como referencia de ejemplos JSON reales ya disponibles.

2. Identifica **todos** los endpoints del proyecto:
   - Rutas HTTP (`@app.get`, `@app.post`, etc.).
   - Endpoints WebSocket (`@app.websocket`).

3. Genera la documentacion completa de cada endpoint siguiendo las reglas de estilo definidas mas abajo.

4. Sobrescribe `src/traffic_engine/api/README.md` con el resultado final. No dejes secciones vacias ni endpoints sin documentar.

---

## Reglas de estilo

1. **Encabezado de archivo**: primera linea siempre `# Traffic Engine API`, seguida de una linea introductoria en cursiva si aplica.
2. **Encabezado de endpoint**: `## METHOD \`url completa\`` - usa la URL base `http://127.0.0.1:8000` para HTTP y `ws://127.0.0.1:8000` para WebSocket.
3. **Descripcion**: una o dos frases en espanol, sin tecnicismos innecesarios. Si el endpoint tiene un parametro de ruta, menciona brevemente que representa.
4. **Errores documentados**: si el handler lanza excepciones mapeadas a codigos HTTP (404, 409, 422, 429, etc.), agregaelos como lista breve despues de la descripcion. Formato: `- \`404\` - descripcion del error`.
5. **Nota de recorte** (solo si la respuesta puede ser muy grande): agrega una linea en cursiva antes del bloque JSON.
6. **Ejemplo JSON**: bloque de codigo `json` con una respuesta real tomada del README actual cuando exista, o representativa si no hay. Recortala si tiene colecciones grandes (maximo 1-2 elementos ilustrativos).
7. **Tabla de campos**: inmediatamente despues del JSON, tabla Markdown `| Campo | Descripcion |`. Convenciones:
   - Nombres de campo entre backticks.
   - Campos anidados: padre.hijo o padre[].hijo.
   - Campos alternativos en la misma fila: campo_a / campo_b.
   - Descripciones cortas, en espanol, sin punto final.
   - Valores enumerados listados explicitamente.
8. **WebSocket**: documenta cada tipo de evento con sub-encabezado `### Evento type`, su propio JSON de ejemplo y su propia tabla de campos. Indica las condiciones de cierre de la conexion.
9. **Idioma**: todo el texto en espanol.
10. **Sin secciones extra**: no agregues introducciones, conclusiones ni secciones que no sigan el estilo de referencia.

---

## Orden de los endpoints en el documento

Documentalos en este orden:

1. `GET /health`
2. `GET /api/response-models.json`
3. `GET /geographic-areas`
4. `GET /geographic-areas/{area_id}/topology`
5. `POST /simulations`
6. `GET /simulations/{simulation_id}`
7. `POST /simulations/{simulation_id}/cancel`
8. `GET /simulations/{simulation_id}/steps`
9. `WS /simulations/{simulation_id}/ws`
10. `WS /simulations/{simulation_id}/replay`

Si encuentras endpoints adicionales en `app.py` que no esten en esta lista, agregaelos al final respetando el mismo estilo.
