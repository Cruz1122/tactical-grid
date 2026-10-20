"use strict";

class ApiClient {
  static async request(path, payload = null) {
    const config = payload === null ? {method: "GET"} : {
      method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload)
    };
    let response;
    try { response = await fetch(path, config); }
    catch { throw new Error("No se puede conectar con Python. Abre el frontend desde http://127.0.0.1:8000/"); }
    let data;
    try { data = await response.json(); }
    catch { throw new Error(`HTTP ${response.status}: la respuesta del servidor no es JSON.`); }
    if (!response.ok) {
      const error = new Error(((typeof data.detail === "string") ? data.detail : null) || `Error HTTP ${response.status}`);
      error.code = data.error || `HTTP_${response.status}`;
      error.status = response.status;
      throw error;
    }
    return data;
  }
}

class SoundBank {
  constructor() {
    this.enabled = false;
    this.templates = {};
    for (const kind of ["knight", "rook", "bishop", "king", "queen"]) {
      for (const event of ["move", "capture"]) {
        const key = `${event}_${kind}`;
        const audio = new Audio(`/assets/sounds/${key}.ogg`);
        audio.preload = "auto";
        this.templates[key] = audio;
      }
    }
    this.templates.check_king = new Audio("/assets/sounds/check_king.ogg");
  }
  setEnabled(value) { this.enabled = Boolean(value); }
  play(key, volume = .7) {
    if (!this.enabled || !this.templates[key]) return;
    const audio = this.templates[key].cloneNode();
    audio.volume = volume;
    audio.play().catch(() => {});
  }
}

const soundBank = new SoundBank();

class TacticalGridUI {
  constructor(scene) {
    this.scene = scene;
    this.lastResult = null;
    this.pickingTarget = false;
    const el = id => document.getElementById(id);
    this.el = el;
    el("audioToggle").addEventListener("click", () => {
      const on = el("audioToggle").dataset.on !== "true";
      el("audioToggle").dataset.on = String(on);
      el("audioToggle").textContent = on ? "SONIDO · ON" : "SONIDO · OFF";
      soundBank.setEnabled(on);
    });
    el("panelToggle").addEventListener("click", () => {
      const closed = el("uiPanel").classList.toggle("collapsed");
      el("panelToggle").setAttribute("aria-expanded", String(!closed));
    });
    el("loadScenario").addEventListener("click", () => el("scenarioFile").click());
    el("scenarioFile").addEventListener("change", async e => {
      const file = e.target.files[0];
      if (!file) return;
      try {
        const scenario = JSON.parse(await file.text());
        await this.execute("/api/scenarios", {scenario, filename: file.name}, "state");
      } catch (error) { this.reportError(error); }
      finally { e.target.value = ""; }
    });
    el("restart").addEventListener("click", () => this.execute("/api/reset", {}, "state"));
    el("pickTarget").addEventListener("click", () => {
      this.pickingTarget = !this.pickingTarget;
      el("pickTarget").textContent = this.pickingTarget ? "Cancelar" : "Elegir";
      this.say(this.pickingTarget ? "Selecciona una celda objetivo en el tablero." : "Selección de objetivo cancelada.");
    });
    el("runSearch").addEventListener("click", () => this.search());
    el("runAdversarial").addEventListener("click", () => this.execute("/api/adversarial", {
      algorithm: el("adversarial").value,
      depth: Number(el("depth").value),
      action_order: el("order").value
    }, "result"));
    el("runVerify").addEventListener("click", () => this.execute("/api/verify", {kind:"state"}, "result"));
    el("runTest").addEventListener("click", () => this.execute("/api/test", {
      algorithm: el("algorithm").value,
      k: Number(el("beamK").value), heuristic: el("heuristic").value,
      depth: Number(el("depth").value), action_order: el("order").value
    }, "auto"));
    el("algorithm").addEventListener("change", () => this.updateInputs());
    this.updateInputs();
  }
  updateInputs() {
    const kind = this.el("algorithm").value;
    this.el("heuristic").disabled = kind !== "astar";
    this.el("beamK").disabled = kind !== "beam";
  }
  say(text) { this.el("toast").textContent = text; }
  report(object) { this.el("result").textContent = JSON.stringify(object, null, 2); }
  reportError(error) {
    const isPending = error.status === 501;
    this.report({error: error.code || "ERROR", detail: error.message});
    this.say(isPending ? "Función pendiente de implementar en Python. No se modificó la partida." : error.message);
  }
  updateState(state, source, animate = false) {
    this.scene.applyState(state, animate);
    this.el("turn").textContent = `Turno · ${state.turno ?? "—"}`;
    this.el("boardDimensions").textContent = `${state.mapa.filas} × ${state.mapa.columnas}`;
    if (source) this.el("source").textContent = `Escenario: ${source}`;
    const selected = this.el("unit").value;
    this.el("unit").replaceChildren();
    for (const unit of state.unidades || []) {
      const option = new Option(`${unit.id} · ${unit.tipo}`, unit.id);
      this.el("unit").append(option);
    }
    if ([...this.el("unit").options].some(o => o.value === selected)) this.el("unit").value = selected;
    const p = state.prueba?.objetivo || state.recurso;
    if (p && !this.scene.userSetTarget) this.setTarget(p.fila, p.columna, false);
    this.el("connection").className = "status connected";
    this.el("connection").textContent = "Python conectado";
  }
  setTarget(row, column, user = true) {
    this.el("targetRow").value = row;
    this.el("targetCol").value = column;
    if (user) this.scene.userSetTarget = true;
    this.pickingTarget = false;
    this.el("pickTarget").textContent = "Elegir";
    this.say(`Objetivo: (${row}, ${column}).`);
  }
  async initialize() {
    try {
      const data = await ApiClient.request("/api/state");
      this.updateState(data.state, data.source, false);
      this.say("Tablero conectado.");
    } catch (err) {
      this.el("connection").className = "status error";
      this.el("connection").textContent = err.message;
      this.reportError(err);
    }
  }
  async execute(path, payload, expected = "result") {
    try {
      const data = await ApiClient.request(path, payload);
      if (data.state) this.updateState(data.state, data.source, path === "/api/move");
      if (data.result) {
        this.lastResult = data.result;
        this.scene.showSearchPath((data.result.path || data.result.camino || []));
      }
      this.report(data.result ?? data.state ?? data);
      this.say(expected === "state" || (expected === "auto" && data.state) ? "Estado recibido del servidor." : "Resultado del algoritmo recibido del servidor.");
      return data;
    } catch (err) { this.reportError(err); return null; }
  }
  async move(unitId, row, column) {
    return this.execute("/api/move", {unit_id:unitId, destination:{row, column}}, "state");
  }
  async search() {
    const unitId = this.el("unit").value;
    const row = Number(this.el("targetRow").value);
    const column = Number(this.el("targetCol").value);
    if (!Number.isInteger(row) || !Number.isInteger(column) || row < 0 || column < 0 ||
        row >= this.scene.rows || column >= this.scene.cols) {
      this.reportError(new Error("El objetivo debe estar dentro del mapa.")); return;
    }
    return this.execute("/api/search", {
      algorithm: this.el("algorithm").value,
      unit_id: unitId, goal:{row, column},
      heuristic:this.el("heuristic").value, k: Number(this.el("beamK").value)
    });
  }
}
