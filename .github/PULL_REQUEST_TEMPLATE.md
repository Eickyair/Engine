<!-- markdownlint-disable MD041 -->
## Descripción

<!-- Explica qué cambia este PR y por qué. Una o dos frases son suficientes. -->

## Tipo de cambio

<!-- Marca con una X lo que aplica. -->

- [ ] `feat` — Nueva funcionalidad
- [ ] `fix` — Corrección de bug
- [ ] `refactor` — Cambio interno sin alterar comportamiento
- [ ] `test` — Añadir o corregir tests
- [ ] `docs` — Documentación
- [ ] `chore` — Mantenimiento (dependencias, CI, configuración)

## Capas modificadas

<!-- Marca las capas de Clean Architecture que toca este PR. -->

- [ ] `domain/` — Entidades o reglas de negocio
- [ ] `application/use_cases/` — Casos de uso
- [ ] `infrastructure/` — Adaptadores externos (MongoDB, clientes, etc.)
- [ ] `api/` — Endpoints o schemas
- [ ] `tests/` — Suite de tests

## Checklist

- [ ] Los tests existentes pasan (`pytest`).
- [ ] Agregué al menos un test para los cambios introducidos.
- [ ] No hay lógica de negocio en infraestructura ni en la capa API.
- [ ] Los métodos públicos nuevos tienen type hints.
- [ ] No introduje dependencias externas en `domain/`.

## Issue relacionado

<!-- Si aplica: "Closes #<número>" o "Relacionado con #<número>" -->
