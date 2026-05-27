# Guía de Contribución

## Repositorios

| Repositorio | Rol |
| --- | --- |
| `https://github.com/Eickyair/Engine` | Repositorio de desarrollo activo. Aquí viven las ramas de funcionalidades y se integran los cambios. |
| `https://github.com/Tarffic-Simulator/Engine` | Repositorio oficial. Solo recibe PRs desde `Eickyair/Engine` cuando hay una versión estable. |

---

## Flujo de trabajo

```text
tu-rama-de-funcionalidad
        │
        ▼  Pull Request
 Eickyair/Engine:main  ──(versión estable)──▶  Tarffic-Simulator/Engine:main
```

### 1. Preparar tu entorno local

Clona el repositorio de desarrollo (no el oficial):

```bash
git clone https://github.com/Eickyair/Engine.git
cd Engine
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Crear una rama de funcionalidad

Crea tu rama a partir de `main` con un nombre descriptivo:

```bash
git checkout main
git pull origin main
git checkout -b feat/nombre-de-la-funcionalidad
```

**Convención de nombres de rama:**

| Prefijo | Uso |
| --- | --- |
| `feat/` | Nueva funcionalidad |
| `fix/` | Corrección de bug |
| `refactor/` | Cambio interno sin alterar comportamiento |
| `docs/` | Cambios exclusivos en documentación |
| `test/` | Añadir o corregir tests |
| `chore/` | Tareas de mantenimiento (dependencias, CI, etc.) |

### 3. Desarrollar y hacer commits

- Mantén cada commit atómico y con un mensaje claro en presente imperativo.
- No commitees archivos de entorno (`.env`, `.venv/`, `__pycache__/`).

```bash
git add .
git commit -m "feat: agregar endpoint de cancelación de simulación"
```

### 4. Abrir un Pull Request hacia `main`

1. Sube tu rama al repositorio:

   ```bash
   git push origin feat/nombre-de-la-funcionalidad
   ```

2. Abre un PR en `https://github.com/Eickyair/Engine` con destino `main`.
3. El cuerpo del PR se pre-rellena automáticamente con la plantilla de `.github/PULL_REQUEST_TEMPLATE.md`. **No la borres**: completa cada sección antes de publicar el PR.
   - **Descripción**: una o dos frases explicando qué cambia y por qué.
   - **Tipo de cambio**: marca la casilla que corresponde al prefijo de tu rama.
   - **Capas modificadas**: marca cada capa de Clean Architecture que tocaste.
   - **Checklist**: confirma que los tests pasan, que añadiste cobertura y que respetaste la separación de capas. No marques una casilla si no es cierto.
   - **Issue relacionado**: si tu PR cierra o está relacionado con un issue, escribe `Closes #<número>`.
4. El PR activa automáticamente la suite de tests (`pr-tests.yml`). El PR **no puede mergearse** si algún test falla.
5. Solicita revisión de al menos un colaborador.
6. Responde los comentarios de revisión con nuevos commits en la misma rama.

### 5. Merge a `main`

El responsable del repositorio realiza el merge una vez que:

- Todos los tests de CI pasan (el check verde es obligatorio).
- Al menos un colaborador aprobó el PR.
- No hay comentarios pendientes sin resolver.

---

## Estándares de código

Este proyecto sigue **Clean Architecture** con tres capas:

| Capa | Carpeta | Contenido |
| --- | --- | --- |
| Dominio | `src/traffic_engine/domain/` | Entidades, reglas de negocio, excepciones propias |
| Casos de uso | `src/traffic_engine/application/use_cases/` | Orquestación; sin dependencias de HTTP ni DB |
| Infraestructura | `src/traffic_engine/infrastructure/` | MongoDB, clientes externos, adaptadores |

**Reglas:**

- Usa type hints en todos los métodos públicos.
- Los casos de uso exponen un único método público (`execute` o `__call__`).
- No coloques lógica de negocio en infraestructura ni en la capa API.
- Usa excepciones de dominio propias (definidas en `domain/exceptions.py`) para errores de negocio.
- No abstraigas algo que solo tiene una implementación concreta.

---

## Tests

Ejecuta la suite completa antes de abrir tu PR:

```bash
pytest
```

- Los tests viven en `tests/`.
- Cada nueva funcionalidad debe incluir al menos un test que la cubra.
- Los tests de CI corren con Python 3.10 en Ubuntu. Asegúrate de que pasen en esa versión.

---

## Ciclo hacia el repositorio oficial

Cuando `Eickyair/Engine:main` acumule cambios suficientes para una versión estable:

1. El mantenedor del proyecto abre un PR desde `Eickyair/Engine:main` hacia `Tarffic-Simulator/Engine:main`.
2. Este PR es revisado y aprobado por los responsables del repositorio oficial.
3. Los colaboradores individuales **no** abren PRs directamente al repositorio oficial.

---

## Uso de IA generativa

Este proyecto incluye un prompt de agente en `.github/prompts/python-clean-architecture.prompt.md` diseñado para generar e implementar código Python respetando la arquitectura del proyecto. Está disponible en VS Code con la extensión GitHub Copilot.

### Cómo invocarlo

1. Abre el panel de chat de GitHub Copilot en VS Code.
2. Escribe `/Python-Clean-Architecture` o selecciónalo desde la lista de prompts.
3. El agente te pedirá dos entradas:
   - **Tarea**: describe el requerimiento, bug o refactor en lenguaje natural.
   - **Restricciones** *(opcional)*: criterios de aceptación, limitaciones técnicas o contexto adicional.
4. Si tienes código seleccionado en el editor al invocar el prompt, ese código se usa como contexto prioritario.

### Para qué sirve

- Implementar nuevos casos de uso o entidades de dominio.
- Refactorizar código existente sin romper la separación de capas.
- Generar adaptadores de infraestructura (repositorios, clientes externos).
- Añadir endpoints siguiendo los patrones de la capa API.

### Responsabilidad sobre el código generado

El código producido por la IA **es responsabilidad del colaborador que abre el PR**, no de la herramienta.

Antes de incluir código generado en un PR:

- Revisa que respeta la separación de capas definida en este archivo.
- Verifica que los tests pasan y añade cobertura si es necesario.
- No incluyas código que no entiendes: si algo no está claro, pregunta o reescríbelo.
- El checklist de la plantilla de PR aplica igual para código generado que para código escrito a mano.

---

## Preguntas o dudas

Abre un [issue](https://github.com/Eickyair/Engine/issues) en el repositorio de desarrollo antes de empezar a trabajar en algo significativo. Esto evita duplicar esfuerzos y permite alinear el diseño con el resto del equipo.
