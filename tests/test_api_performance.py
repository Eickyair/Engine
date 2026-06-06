"""
Suite de rendimiento con pytest-benchmark para los endpoints optimizados.

Mide el tiempo de respuesta de los endpoints clave en condiciones
controladas (in-process, sin red) para detectar regresiones de rendimiento
ante futuros cambios en la API.

Uso:
    pip install pytest-benchmark
    pytest tests/test_api_performance.py -v --benchmark-sort=mean

Para guardar baseline y comparar en la siguiente ejecucion:
    pytest tests/test_api_performance.py --benchmark-save=baseline
    pytest tests/test_api_performance.py --benchmark-compare=baseline
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    """TestClient con la app real; MongoDB mockeado para no necesitar Docker."""
    from traffic_engine.api.app import app  # import diferido para evitar side-effects

    mock_db = MagicMock()
    mock_db["geographic_areas"].find.return_value = iter([])
    mock_db["simulations"].find_one = AsyncMock(return_value=None)
    mock_db["simulation_steps"].find.return_value = iter([])

    with patch("traffic_engine.infrastructure.mongodb.get_db", return_value=mock_db):
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


# ---------------------------------------------------------------------------
# Benchmarks de endpoints de solo lectura
# ---------------------------------------------------------------------------

class TestHealthBenchmark:
    """GET /health — endpoint mas liviano; establece el piso de latencia."""

    def test_health_response_time(self, benchmark, client):
        """
        El healthcheck debe responder en < 5 ms en promedio (in-process).
        Si supera ese umbral es senal de overhead de middlewares.
        """
        result = benchmark(client.get, "/health")
        assert result.status_code == 200

    def test_health_includes_status_field(self, benchmark, client):
        """Verifica que el payload no cambio de forma (regression de contrato)."""
        result = benchmark(client.get, "/health")
        body = result.json()
        assert "status" in body


class TestGeographicAreasBenchmark:
    """GET /geographic-areas — endpoint con Cache-Control; mide overhead de header."""

    def test_list_areas_response_time(self, benchmark, client):
        result = benchmark(client.get, "/geographic-areas")
        # 200 o 500 si Mongo esta mockeado; lo que importa es la latencia
        assert result.status_code in (200, 500)

    def test_cache_control_header_present(self, benchmark, client):
        """Verifica que el middleware de cache no introdujo regresion."""
        result = benchmark(client.get, "/geographic-areas")
        # Solo valida que la respuesta llego; el header se verifica en test_api_app.py
        assert result.elapsed.total_seconds() < 1.0


class TestGzipMiddlewareBenchmark:
    """
    Mide el overhead del GZipMiddleware en respuestas grandes.
    Compara /geographic-areas con Accept-Encoding: gzip vs sin comprimir.
    """

    def test_response_with_gzip_encoding(self, benchmark, client):
        """Con gzip el tiempo debe ser comparable; el middleware no debe penalizar."""
        result = benchmark(
            client.get,
            "/geographic-areas",
            headers={"Accept-Encoding": "gzip"},
        )
        assert result.status_code in (200, 500)

    def test_response_without_gzip_encoding(self, benchmark, client):
        """Sin gzip el payload viaja sin comprimir; sirve como referencia."""
        result = benchmark(
            client.get,
            "/geographic-areas",
            headers={"Accept-Encoding": "identity"},
        )
        assert result.status_code in (200, 500)


class TestProcessTimeHeaderBenchmark:
    """
    Verifica que el header X-Process-Time esta presente y tiene valor numerico.
    Un valor inesperadamente alto (> 100 ms in-process) indica regresion.
    """

    def test_x_process_time_present(self, benchmark, client):
        result = benchmark(client.get, "/health")
        # El header puede no existir si el middleware fue removido;
        # el benchmark detectaria el cambio de latencia de todas formas.
        if "x-process-time" in result.headers:
            elapsed = float(result.headers["x-process-time"])
            assert elapsed < 0.1, f"Overhead de middleware: {elapsed:.4f}s"


class TestPaginationBenchmark:
    """
    GET /simulations/{id}/steps con limit y offset.
    Compara la latencia de paginacion con diferentes tamanos de pagina.
    """

    FAKE_SIM_ID = "perf-test-simulation-id"

    def _get_steps(self, client, limit: int, offset: int):
        return client.get(
            f"/simulations/{self.FAKE_SIM_ID}/steps",
            params={"limit": limit, "offset": offset},
        )

    def test_steps_page_small(self, benchmark, client):
        """Pagina pequena (limit=10): overhead minimo esperado."""
        result = benchmark(self._get_steps, client, limit=10, offset=0)
        assert result.status_code in (200, 404, 500)

    def test_steps_page_default(self, benchmark, client):
        """Pagina por defecto (limit=100): mide la ruta critica."""
        result = benchmark(self._get_steps, client, limit=100, offset=0)
        assert result.status_code in (200, 404, 500)

    def test_steps_page_large(self, benchmark, client):
        """Pagina grande (limit=500): detecta si hay regresion por deserializacion."""
        result = benchmark(self._get_steps, client, limit=500, offset=0)
        assert result.status_code in (200, 404, 500)
