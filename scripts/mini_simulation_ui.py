"""Mini web UI for running and watching Traffic Engine simulations.

This script intentionally uses only the Python standard library. It serves a
small HTML/JavaScript app and proxies REST calls to the FastAPI backend so the
browser does not need CORS configuration.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, cast


INDEX_HTML = r"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Traffic Engine Mini UI</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <style>
    :root {
      --bg: #f7f8fa;
      --panel: #ffffff;
      --line: #d8dee8;
      --text: #1c2430;
      --muted: #667085;
      --primary: #2364aa;
      --primary-dark: #174b83;
      --danger: #b42318;
      --danger-bg: #fee4e2;
      --ok: #067647;
      --shadow: 0 12px 32px rgba(16, 24, 40, 0.08);
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--text);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    .app {
      display: grid;
      grid-template-columns: minmax(300px, 360px) minmax(0, 1fr);
      min-height: 100vh;
    }

    aside {
      background: var(--panel);
      border-right: 1px solid var(--line);
      padding: 20px;
      overflow-y: auto;
    }

    main {
      display: grid;
      grid-template-rows: auto minmax(0, 1fr);
      min-width: 0;
    }

    .topbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 14px 18px;
      background: rgba(255, 255, 255, 0.9);
      border-bottom: 1px solid var(--line);
    }

    h1 {
      margin: 0 0 18px;
      font-size: 22px;
      line-height: 1.2;
    }

    h2 {
      margin: 22px 0 12px;
      font-size: 14px;
      text-transform: uppercase;
      letter-spacing: 0;
      color: var(--muted);
    }

    label {
      display: block;
      margin: 12px 0 6px;
      font-size: 13px;
      font-weight: 650;
      color: #344054;
    }

    select, input {
      width: 100%;
      min-height: 38px;
      border: 1px solid #c7d0dd;
      border-radius: 6px;
      background: #fff;
      color: var(--text);
      padding: 8px 10px;
      font: inherit;
    }

    input[type="range"] { padding: 0; }

    .grid2 {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
    }

    button {
      border: 0;
      border-radius: 6px;
      min-height: 40px;
      padding: 9px 12px;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
    }

    button:disabled { cursor: not-allowed; opacity: 0.55; }

    .primary { background: var(--primary); color: #fff; }
    .primary:hover:not(:disabled) { background: var(--primary-dark); }
    .secondary { background: #eef2f6; color: #263241; }
    .danger { background: var(--danger-bg); color: var(--danger); }

    .actions {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
      margin-top: 16px;
    }

    .status {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      min-width: 0;
      color: var(--muted);
      font-size: 13px;
    }

    .dot {
      width: 9px;
      height: 9px;
      border-radius: 999px;
      background: #98a2b3;
      flex: 0 0 auto;
    }

    .dot.running { background: #1570ef; }
    .dot.finished { background: var(--ok); }
    .dot.error { background: var(--danger); }

    .stats {
      display: grid;
      grid-template-columns: repeat(6, minmax(110px, 1fr));
      gap: 10px;
      padding: 12px 18px;
      background: #fff;
      border-bottom: 1px solid var(--line);
    }

    .stat {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px 12px;
      background: #fbfcfe;
    }

    .stat span {
      display: block;
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 2px;
    }

    .stat strong {
      display: block;
      font-size: 20px;
      line-height: 1.2;
      overflow-wrap: anywhere;
    }

    .map-wrap {
      position: relative;
      min-height: 0;
      padding: 18px;
    }

    #map {
      width: 100%;
      height: calc(100vh - 122px);
      min-height: 420px;
      background: #ffffff;
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      overflow: hidden;
    }

    .leaflet-container {
      font: inherit;
      color: var(--text);
    }

    .leaflet-control-attribution {
      font-size: 10px;
    }

    .traffic-light-tooltip {
      border: 0;
      border-radius: 5px;
      background: rgba(28, 36, 48, 0.92);
      color: #ffffff;
      font-size: 11px;
      font-weight: 700;
      box-shadow: none;
      padding: 3px 6px;
    }

    .vehicle-marker {
      border: 2px solid #ffffff;
      box-shadow: 0 2px 8px rgba(28, 36, 48, 0.22);
    }

    .hint {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
      margin: 10px 0 0;
    }

    .api {
      font-size: 12px;
      color: var(--muted);
      overflow-wrap: anywhere;
      padding: 9px 10px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fbfcfe;
    }

    .check-row {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-top: 12px;
      color: #344054;
      font-size: 13px;
      font-weight: 650;
    }

    .check-row input {
      width: 18px;
      min-height: 18px;
      flex: 0 0 auto;
    }

    .model-preview {
      margin-top: 12px;
      padding: 10px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fbfcfe;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.4;
    }

    @media (max-width: 900px) {
      .app { grid-template-columns: 1fr; }
      aside { border-right: 0; border-bottom: 1px solid var(--line); }
      .stats { grid-template-columns: repeat(2, minmax(120px, 1fr)); }
      #map { height: 62vh; }
    }
  </style>
</head>
<body>
  <div class="app">
    <aside>
      <h1>Traffic Engine</h1>
      <div id="apiBox" class="api">Conectando...</div>

      <h2>Area</h2>
      <label for="areaSelect">Datos geograficos</label>
      <select id="areaSelect"></select>
      <p id="areaMeta" class="hint"></p>
      <button id="reloadBtn" class="secondary" type="button">Recargar areas</button>

      <h2>Modelo</h2>
      <label for="executionMode">Modo de ejecucion</label>
      <select id="executionMode">
        <option value="continuous">Continuo: spawn/despawn dinamico</option>
        <option value="classic">Clasico: vehiculos iniciales</option>
      </select>
      <div class="grid2">
        <div>
          <label for="defaultLanes">Carriles</label>
          <input id="defaultLanes" type="number" min="1" value="1" />
        </div>
        <div>
          <label for="trafficLightGreen">Verde</label>
          <input id="trafficLightGreen" type="number" min="1" value="10" />
        </div>
      </div>
      <div class="grid2">
        <div>
          <label for="trafficLightRed">Rojo</label>
          <input id="trafficLightRed" type="number" min="0" value="10" />
        </div>
        <div>
          <label for="trafficLightPercentage">Semaforos <span id="trafficLightValue">25%</span></label>
          <input id="trafficLightPercentage" type="range" min="0" max="1" step="0.01" value="0.25" />
        </div>
      </div>
      <label class="check-row" for="enableLaneChanges">
        <input id="enableLaneChanges" type="checkbox" />
        Cambio de carril
      </label>
      <div id="modelPreview" class="model-preview"></div>

      <h2>Simulacion</h2>
      <div class="grid2">
        <div>
          <label for="initialVehicles">Iniciales</label>
          <input id="initialVehicles" type="number" min="0" value="25" />
        </div>
        <div>
          <label for="maxVehicles">Max vehiculos</label>
          <input id="maxVehicles" type="number" min="1" value="60" />
        </div>
      </div>
      <div class="grid2">
        <div>
          <label for="maxSteps">Steps</label>
          <input id="maxSteps" type="number" min="1" value="120" />
        </div>
        <div>
          <label for="tickInterval">Tick ms</label>
          <input id="tickInterval" type="number" min="0" value="100" />
        </div>
      </div>
      <label for="spawnRate">Spawn rate <span id="spawnValue">0.20</span></label>
      <input id="spawnRate" type="range" min="0" max="1" step="0.01" value="0.2" />
      <label for="noiseProb">Ruido <span id="noiseValue">0.30</span></label>
      <input id="noiseProb" type="range" min="0" max="1" step="0.01" value="0.3" />
      <label for="seed">Seed</label>
      <input id="seed" type="number" value="42" />

      <div class="actions">
        <button id="startBtn" class="primary" type="button">Iniciar</button>
        <button id="cancelBtn" class="danger" type="button" disabled>Cancelar</button>
      </div>
      <p class="hint">El mapa usa el endpoint de topologia y los vehiculos llegan por WebSocket mientras la simulacion esta running.</p>
    </aside>

    <main>
      <div class="topbar">
        <div class="status"><span id="statusDot" class="dot"></span><span id="statusText">Listo</span></div>
        <div id="simulationLabel" class="status">Sin simulacion activa</div>
      </div>
      <section class="stats">
        <div class="stat"><span>Step</span><strong id="stepStat">0</strong></div>
        <div class="stat"><span>Vehiculos</span><strong id="vehiclesStat">0</strong></div>
        <div class="stat"><span>Velocidad media</span><strong id="speedStat">0 km/h</strong></div>
        <div class="stat"><span>Congestion</span><strong id="congestionStat">0%</strong></div>
        <div class="stat"><span>Semaforos</span><strong id="trafficLightsStat">0</strong></div>
        <div class="stat"><span>Modelo</span><strong id="modelStat">Continuo</strong></div>
      </section>
      <div class="map-wrap">
        <div id="map"></div>
      </div>
    </main>
  </div>

  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script>
    const $ = (id) => document.getElementById(id);

    let config = null;
    let areas = [];
    let topology = null;
    let vehicles = [];
    let trafficLights = [];
    let metrics = null;
    let simulationId = null;
    let socket = null;
    let pollTimer = null;
    let activeModelConfig = null;
    let map = null;
    let edgeLayer = null;
    let vehicleLayer = null;
    let trafficLightLayer = null;

    function setStatus(text, mode = "") {
      $("statusText").textContent = text;
      $("statusDot").className = `dot ${mode}`.trim();
    }

    function setBusy(isBusy) {
      $("startBtn").disabled = isBusy;
      $("cancelBtn").disabled = !isBusy;
      $("areaSelect").disabled = isBusy;
    }

    function numberValue(id) {
      return Number($(id).value);
    }

    function boolValue(id) {
      return $(id).checked;
    }

    function modelConfigFromControls() {
      return {
        execution_mode: $("executionMode").value,
        default_lanes: numberValue("defaultLanes"),
        enable_lane_changes: boolValue("enableLaneChanges"),
        traffic_light_percentage: numberValue("trafficLightPercentage"),
        traffic_light_green_steps: numberValue("trafficLightGreen"),
        traffic_light_red_steps: numberValue("trafficLightRed"),
      };
    }

    function modelLabel(modelConfig) {
      const mode = modelConfig.execution_mode === "classic" ? "Clasico" : "Continuo";
      const lanes = `${modelConfig.default_lanes} carril${modelConfig.default_lanes === 1 ? "" : "es"}`;
      const laneChanges = modelConfig.enable_lane_changes ? "cambio activo" : "sin cambios";
      const lights = `${Math.round(modelConfig.traffic_light_percentage * 100)}% semaforos`;
      return `${mode}, ${lanes}, ${laneChanges}, ${lights}`;
    }

    function updateModelPreview() {
      const modelConfig = modelConfigFromControls();
      $("trafficLightValue").textContent = `${Math.round(modelConfig.traffic_light_percentage * 100)}%`;
      $("modelPreview").textContent = modelLabel(modelConfig);
      if (!activeModelConfig) {
        $("modelStat").textContent = modelConfig.execution_mode === "classic" ? "Clasico" : "Continuo";
      }
    }

    async function apiFetch(path, options = {}) {
      const headers = Object.assign({ "Content-Type": "application/json" }, options.headers || {});
      const response = await fetch(`/api${path}`, Object.assign({}, options, { headers }));
      const text = await response.text();
      let payload = null;
      if (text) {
        try { payload = JSON.parse(text); } catch { payload = text; }
      }
      if (!response.ok) {
        const detail = payload && payload.detail ? payload.detail : text || response.statusText;
        throw new Error(detail);
      }
      return payload;
    }

    function initMap() {
      if (map || !window.L) return;
      map = L.map("map", {
        preferCanvas: false,
        zoomControl: true,
        attributionControl: true,
      });
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 20,
        attribution: "&copy; OpenStreetMap contributors",
      }).addTo(map);
      map.createPane("roadsPane");
      map.createPane("vehiclesPane");
      map.createPane("trafficLightsPane");
      map.getPane("roadsPane").style.zIndex = 410;
      map.getPane("vehiclesPane").style.zIndex = 620;
      map.getPane("trafficLightsPane").style.zIndex = 700;
      edgeLayer = L.layerGroup().addTo(map);
      vehicleLayer = L.layerGroup().addTo(map);
      trafficLightLayer = L.layerGroup().addTo(map);
      map.setView([19.412, -99.165], 13);
    }

    function toLatLng(point) {
      return [point[1], point[0]];
    }

    function topologyBounds() {
      const box = topology.topology.bbox;
      return L.latLngBounds([box.min_y, box.min_x], [box.max_y, box.max_x]);
    }

    function renderTopology() {
      initMap();
      edgeLayer.clearLayers();
      if (!topology) return;
      for (const edge of topology.topology.edges) {
        if (!edge.geometry_points || edge.geometry_points.length < 2) continue;
        const lanes = edge.lanes || 1;
        const points = edge.geometry_points.map(toLatLng);
        const color = edge.allows_lane_change ? "#475467" : "#98a2b3";
        L.polyline(points, {
          pane: "roadsPane",
          color,
          weight: Math.max(2, Math.min(8, lanes + 2)),
          opacity: 0.82,
          lineCap: "round",
          lineJoin: "round",
        }).bindTooltip(`${lanes} carril${lanes === 1 ? "" : "es"}`, { sticky: true }).addTo(edgeLayer);
      }
      map.fitBounds(topologyBounds(), { padding: [24, 24], maxZoom: 17 });
      renderDynamicLayers();
    }

    function renderDynamicLayers() {
      initMap();
      vehicleLayer.clearLayers();
      trafficLightLayer.clearLayers();

      for (const light of trafficLights) {
        const state = light.state === "red" ? "red" : "green";
        const label = state === "red" ? "Rojo" : "Verde";
        if (!Number.isFinite(light.x) || !Number.isFinite(light.y)) continue;
        L.circleMarker([light.y, light.x], {
          pane: "trafficLightsPane",
          radius: 9,
          color: "#ffffff",
          weight: 3,
          fillColor: state === "red" ? "#d92d20" : "#079455",
          fillOpacity: 1,
          opacity: 1,
        })
          .bindTooltip(`Semaforo ${label}`, {
            permanent: true,
            direction: "top",
            offset: [0, -10],
            className: "traffic-light-tooltip",
          })
          .addTo(trafficLightLayer);
      }

      for (const vehicle of vehicles) {
        const stopped = vehicle.velocity === 0;
        const fillColor = stopped ? "#d92d20" : vehicle.speed_kph > 25 ? "#079455" : "#1570ef";
        L.circleMarker([vehicle.y, vehicle.x], {
          pane: "vehiclesPane",
          radius: stopped ? 6.5 : 5.5,
          color: "#ffffff",
          weight: 2,
          fillColor,
          fillOpacity: 0.95,
          className: "vehicle-marker",
        }).addTo(vehicleLayer);
      }
    }

    function renderStats(step) {
      const state = step ? step.state : null;
      const currentMetrics = step ? step.metrics : metrics;
      $("stepStat").textContent = step ? step.step_number : "0";
      $("vehiclesStat").textContent = state ? state.total_vehicles : vehicles.length;
      $("speedStat").textContent = currentMetrics ? `${currentMetrics.avg_speed_kph.toFixed(1)} km/h` : "0 km/h";
      $("congestionStat").textContent = currentMetrics ? `${(currentMetrics.congestion_ratio * 100).toFixed(0)}%` : "0%";
      $("trafficLightsStat").textContent = state ? (state.traffic_lights || []).length : trafficLights.length;
    }

    function applyStep(step) {
      vehicles = step.state.vehicles || [];
      trafficLights = step.state.traffic_lights || [];
      metrics = step.metrics || null;
      renderStats(step);
      renderDynamicLayers();
    }

    async function loadAreas() {
      setStatus("Cargando areas...");
      areas = await apiFetch("/geographic-areas");
      const select = $("areaSelect");
      select.innerHTML = "";
      for (const area of areas) {
        const option = document.createElement("option");
        option.value = area.area_id;
        option.textContent = `${area.name} (${area.node_count} nodos, ${area.edge_count} aristas)`;
        select.appendChild(option);
      }
      if (!areas.length) {
        $("areaMeta").textContent = "No hay areas precargadas en Mongo.";
        setStatus("Sin areas", "error");
        return;
      }
      await loadTopology(select.value);
      setStatus("Listo", "finished");
    }

    async function loadTopology(areaId) {
      topology = await apiFetch(`/geographic-areas/${encodeURIComponent(areaId)}/topology`);
      vehicles = [];
      trafficLights = [];
      metrics = null;
      if (!simulationId) {
        activeModelConfig = null;
      }
      const box = topology.topology.bbox;
      $("areaMeta").textContent = `${topology.node_count} nodos, ${topology.edge_count} aristas. BBox ${box.min_x.toFixed(4)}, ${box.min_y.toFixed(4)} a ${box.max_x.toFixed(4)}, ${box.max_y.toFixed(4)}.`;
      renderStats(null);
      renderTopology();
    }

    function closeSocket() {
      if (socket) {
        socket.onclose = null;
        socket.close();
        socket = null;
      }
    }

    async function pollFinishedSteps() {
      if (!simulationId) return;
      try {
        const record = await apiFetch(`/simulations/${encodeURIComponent(simulationId)}`);
        if (record.status !== "running") {
          window.clearInterval(pollTimer);
          pollTimer = null;
          setBusy(false);
          setStatus(record.status, record.status === "finished" ? "finished" : "error");
          try {
            const steps = await apiFetch(`/simulations/${encodeURIComponent(simulationId)}/steps`);
            if (steps.length) applyStep(steps[steps.length - 1]);
          } catch (error) {
            console.warn(error);
          }
        }
      } catch (error) {
        console.warn(error);
      }
    }

    function connectSimulationStream(id) {
      closeSocket();
      const wsBase = config.ws_base_url.replace(/\/$/, "");
      socket = new WebSocket(`${wsBase}/simulations/${encodeURIComponent(id)}/ws`);
      socket.onopen = () => setStatus("Streaming en vivo", "running");
      socket.onmessage = (message) => {
        const event = JSON.parse(message.data);
        if (event.type === "step" && event.step) {
          applyStep(event.step);
        }
        if (event.type === "status") {
          setStatus(event.status, event.status === "finished" ? "finished" : "error");
          setBusy(false);
          closeSocket();
        }
      };
      socket.onerror = () => setStatus("WebSocket no disponible", "error");
      socket.onclose = () => {
        if (!pollTimer && simulationId) {
          pollTimer = window.setInterval(pollFinishedSteps, 1200);
        }
      };
    }

    async function startSimulation() {
      const areaId = $("areaSelect").value;
      if (!areaId) return;
      setBusy(true);
      setStatus("Creando simulacion...", "running");
      const body = {
        area_id: areaId,
        initial_vehicles: numberValue("initialVehicles"),
        max_vehicles: numberValue("maxVehicles"),
        max_steps: numberValue("maxSteps"),
        spawn_rate: numberValue("spawnRate"),
        noise_prob: numberValue("noiseProb"),
        seed: numberValue("seed"),
        tick_interval_ms: numberValue("tickInterval"),
        ...modelConfigFromControls(),
      };
      try {
        await loadTopology(areaId);
        const record = await apiFetch("/simulations", { method: "POST", body: JSON.stringify(body) });
        simulationId = record.simulation_id;
        activeModelConfig = record.config || body;
        $("simulationLabel").textContent = simulationId;
        $("modelStat").textContent = activeModelConfig.execution_mode === "classic" ? "Clasico" : "Continuo";
        $("modelPreview").textContent = modelLabel(activeModelConfig);
        connectSimulationStream(simulationId);
      } catch (error) {
        setBusy(false);
        activeModelConfig = null;
        setStatus(error.message, "error");
      }
    }

    async function cancelSimulation() {
      if (!simulationId) return;
      setStatus("Cancelando...", "running");
      try {
        await apiFetch(`/simulations/${encodeURIComponent(simulationId)}/cancel`, { method: "POST" });
        activeModelConfig = null;
      } catch (error) {
        setStatus(error.message, "error");
      }
    }

    function bindControls() {
      $("reloadBtn").addEventListener("click", () => loadAreas().catch((error) => setStatus(error.message, "error")));
      $("areaSelect").addEventListener("change", (event) => loadTopology(event.target.value).catch((error) => setStatus(error.message, "error")));
      $("startBtn").addEventListener("click", startSimulation);
      $("cancelBtn").addEventListener("click", cancelSimulation);
      $("spawnRate").addEventListener("input", () => $("spawnValue").textContent = Number($("spawnRate").value).toFixed(2));
      $("noiseProb").addEventListener("input", () => $("noiseValue").textContent = Number($("noiseProb").value).toFixed(2));
      ["executionMode", "defaultLanes", "trafficLightGreen", "trafficLightRed", "trafficLightPercentage", "enableLaneChanges"].forEach((id) => {
        $(id).addEventListener("input", updateModelPreview);
        $(id).addEventListener("change", updateModelPreview);
      });
      window.addEventListener("resize", () => map && map.invalidateSize());
    }

    async function boot() {
      bindControls();
      if (!window.L) {
        setStatus("Leaflet no pudo cargarse", "error");
        return;
      }
      initMap();
      config = await fetch("/config").then((response) => response.json());
      $("apiBox").textContent = `API: ${config.api_base_url}`;
      updateModelPreview();
      await loadAreas();
    }

    boot().catch((error) => setStatus(error.message, "error"));
  </script>
</body>
</html>
"""


class MiniUiServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address: tuple[str, int],
        request_handler_class: type[BaseHTTPRequestHandler],
        api_base_url: str,
        ws_base_url: str,
    ) -> None:
        super().__init__(server_address, request_handler_class)
        self.api_base_url = api_base_url.rstrip("/")
        self.ws_base_url = ws_base_url.rstrip("/")


class MiniUiHandler(BaseHTTPRequestHandler):
    @property
    def app_server(self) -> MiniUiServer:
        return cast(MiniUiServer, self.server)

    def do_GET(self) -> None:
        if self.path in {"/", "/index.html"}:
            self._send_html(INDEX_HTML)
            return
        if self.path == "/config":
            self._send_json(
                {
                    "api_base_url": self.app_server.api_base_url,
                    "ws_base_url": self.app_server.ws_base_url,
                }
            )
            return
        if self.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        if self.path.startswith("/api/"):
            self._proxy_rest("GET")
            return
        self._send_error(404, "Not found")

    def do_POST(self) -> None:
        if self.path.startswith("/api/"):
            self._proxy_rest("POST")
            return
        self._send_error(404, "Not found")

    def _proxy_rest(self, method: str) -> None:
        parsed = urllib.parse.urlsplit(self.path)
        api_path = parsed.path.removeprefix("/api") or "/"
        target = urllib.parse.urlunsplit(
            urllib.parse.urlsplit(self.app_server.api_base_url)._replace(
                path=api_path,
                query=parsed.query,
                fragment="",
            )
        )
        body = None
        if method in {"POST", "PUT", "PATCH"}:
            content_length = int(self.headers.get("Content-Length", "0") or "0")
            body = self.rfile.read(content_length) if content_length else b""
        headers = {"Accept": "application/json"}
        content_type = self.headers.get("Content-Type")
        if content_type:
            headers["Content-Type"] = content_type

        request = urllib.request.Request(target, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = response.read()
                self.send_response(response.status)
                self.send_header("Content-Type", response.headers.get("Content-Type", "application/json"))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(payload)
        except urllib.error.HTTPError as exc:
            payload = exc.read()
            self.send_response(exc.code)
            self.send_header("Content-Type", exc.headers.get("Content-Type", "application/json"))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)
        except urllib.error.URLError as exc:
            self._send_error(502, f"Could not reach API at {self.app_server.api_base_url}: {exc.reason}")

    def _send_html(self, html: str) -> None:
        payload = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _send_json(self, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status_code: int, detail: str) -> None:
        body = json.dumps({"detail": detail}).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        sys.stderr.write("[mini-ui] " + format % args + "\n")


def _default_ws_url(api_base_url: str) -> str:
    parsed = urllib.parse.urlsplit(api_base_url)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return urllib.parse.urlunsplit((scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve the Traffic Engine mini simulation UI.")
    parser.add_argument("--host", default="127.0.0.1", help="Host for this mini UI server.")
    parser.add_argument("--port", type=int, default=8501, help="Port for this mini UI server.")
    parser.add_argument(
        "--api-url",
        default="http://127.0.0.1:8000",
        help="Base URL of the FastAPI Traffic Engine API.",
    )
    parser.add_argument(
        "--ws-url",
        default=None,
        help="Base WebSocket URL of the FastAPI Traffic Engine API.",
    )
    parser.add_argument("--open", action="store_true", help="Open the browser after startup.")
    parser.add_argument("--check", action="store_true", help="Validate configuration and exit.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    api_base_url = args.api_url.rstrip("/")
    ws_base_url = (args.ws_url or _default_ws_url(api_base_url)).rstrip("/")
    if args.check:
        print(f"Mini UI ok. API={api_base_url} WS={ws_base_url}")
        return

    server = MiniUiServer((args.host, args.port), MiniUiHandler, api_base_url, ws_base_url)
    url = f"http://{args.host}:{args.port}"
    print(f"Traffic Engine mini UI: {url}")
    print(f"REST API proxy target: {api_base_url}")
    print(f"WebSocket target: {ws_base_url}")
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping mini UI.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
