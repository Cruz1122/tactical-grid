"use strict";

function isObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function assertStateShape(state) {
  if (!isObject(state) || !isObject(state.mapa) ||
      !Number.isInteger(state.mapa.filas) || !Number.isInteger(state.mapa.columnas) ||
      !Array.isArray(state.terreno) || !isObject(state.tipos_terreno) ||
      !Array.isArray(state.unidades) || !["A", "B"].includes(state.turno)) {
    throw new Error("El servidor devolvió un estado de partida incompleto.");
  }
  if (state.terreno.length !== state.mapa.filas ||
      state.terreno.some(row => !Array.isArray(row) || row.length !== state.mapa.columnas)) {
    throw new Error("El servidor devolvió un terreno con dimensiones incoherentes.");
  }
  for (const unit of state.unidades) {
    if (!isObject(unit) || typeof unit.id !== "string" || !["A", "B"].includes(unit.bando)) {
      throw new Error("El servidor devolvió una unidad con formato inválido.");
    }
  }
  return state;
}

function assertPresentationShape(presentation) {
  if (presentation == null) return null;
  if (!isObject(presentation) || typeof presentation.revision !== "string" ||
      !isObject(presentation.jaques) ||
      !isObject(presentation.recogida_autorizada) ||
      !Array.isArray(presentation.eventos_ultimo_turno)) {
    throw new Error("El servidor devolvió una proyección de presentación inválida.");
  }
  return presentation;
}

function assertSearchResultShape(result) {
  const optionalNumbers = [
    "moves", "cost", "states_generated", "states_expanded", "max_frontier",
    "elapsed_seconds", "candidates_discarded"
  ];
  if (!isObject(result) ||
      typeof result.found !== "boolean" ||
      typeof result.input_valid !== "boolean" ||
      !(result.error == null || typeof result.error === "string") ||
      !Array.isArray(result.path) ||
      result.path.some(step => !isObject(step) ||
        !Number.isInteger(step.fila) || !Number.isInteger(step.columna)) ||
      optionalNumbers.some(field => result[field] != null && typeof result[field] !== "number")) {
    throw new Error("El servidor devolvió un resultado de búsqueda con formato inválido.");
  }
  return result;
}

function assertAdversarialResultShape(result) {
  const metricFields = [
    "requested_depth", "depth_reached", "nodes_generated", "nodes_visited",
    "nodes_evaluated", "nodes_pruned"
  ];
  if (!isObject(result) || !("action" in result) || !["minimax", "alpha_beta"].includes(result.algorithm) ||
      !["normal", "reverse"].includes(result.action_order) ||
      !Number.isFinite(result.value) || !Number.isFinite(result.elapsed_seconds) ||
      result.elapsed_seconds < 0 ||
      metricFields.some(field => !Number.isSafeInteger(result[field]) || result[field] < 0)) {
    throw new Error("El servidor devolvió un resultado adversarial con formato inválido.");
  }
  const action = result.action;
  if (action != null && (!isObject(action) || !["move", "collect"].includes(action.type) ||
      typeof action.unit_id !== "string" ||
      (action.type === "move" && (!isObject(action.destination) ||
        !Number.isInteger(action.destination.fila) || !Number.isInteger(action.destination.columna))))) {
    throw new Error("El servidor devolvió una acción adversarial con formato inválido.");
  }
  return result;
}

function validateResponse(data) {
  if (!isObject(data)) throw new Error("La respuesta del servidor no es un objeto JSON.");
  if (data.state) assertStateShape(data.state);
  if (data.presentation) assertPresentationShape(data.presentation);
  return data;
}

function teamLabel(team) {
  return team === "A" ? "Blancas" : team === "B" ? "Negras" : "—";
}

function teamPhrase(team) {
  const label = teamLabel(team);
  return label === "—" ? "el bando en turno" : `las ${label}`;
}

function sentenceTeamPhrase(team) {
  const phrase = teamPhrase(team);
  return phrase.charAt(0).toUpperCase() + phrase.slice(1);
}

class ApiClient {
  static async request(path, payload = null, options = {}) {
    const config = payload === null ? {method: "GET"} : {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload)
    };
    if (options.signal) config.signal = options.signal;

    let response;
    try {
      response = await fetch(path, config);
    } catch (error) {
      if (error?.name === "AbortError") throw error;
      const networkError = new Error("No se puede conectar con Python; comprueba que el servidor esté activo.");
      networkError.code = "NETWORK_ERROR";
      networkError.responseLost = true;
      networkError.cause = error;
      throw networkError;
    }

    let data;
    try {
      data = await response.json();
    } catch (error) {
      const responseError = new Error(`HTTP ${response.status}: la respuesta del servidor no es JSON.`);
      responseError.code = `HTTP_${response.status}`;
      responseError.status = response.status;
      responseError.responseLost = true;
      responseError.cause = error;
      throw responseError;
    }
    if (!response.ok) {
      const detail = typeof data.detail === "string"
        ? data.detail
        : Array.isArray(data.detail)
          ? data.detail
              .map(item => typeof item === "string" ? item : item?.msg || JSON.stringify(item))
              .join(" ")
          : data.detail == null ? null : JSON.stringify(data.detail);
      const requestError = new Error(detail || `Error HTTP ${response.status}`);
      requestError.code = data.error || `HTTP_${response.status}`;
      requestError.status = response.status;
      throw requestError;
    }
    return validateResponse(data);
  }

  static async legalMoves(unitId, signal) {
    const query = new URLSearchParams({unit_id: unitId});
    const data = await this.request(`/api/legal-moves?${query.toString()}`, null, {signal});
    if (!Array.isArray(data.destinations) || !Array.isArray(data.normal) ||
        !Array.isArray(data.captures) || typeof data.allowed !== "boolean" ||
        typeof data.collect_allowed !== "boolean") {
      throw new Error("El servidor devolvió destinos legales con formato inválido.");
    }
    const validKinds = new Set(["normal", "capture", "collect"]);
    if (data.destinations.some(destination =>
      !isObject(destination) || !Number.isInteger(destination.row) ||
      !Number.isInteger(destination.column) || !validKinds.has(destination.kind))) {
      throw new Error("El servidor devolvió una acción legal con formato inválido.");
    }
    return data;
  }

  static async search(payload, signal) {
    const data = await this.request("/api/search", payload, {signal});
    return assertSearchResultShape(data.result);
  }

  static async adversarial(payload, signal) {
    const data = await this.request("/api/adversarial", payload, {signal});
    return assertAdversarialResultShape(data.result);
  }
}

class SoundBank {
  constructor() {
    this.enabled = false;
    this.context = null;
    this.master = null;
    this.scheduledUntil = 0;
    this.templates = {};
    this.soundAliases = {estandar: "rook"};
    for (const kind of ["knight", "rook", "bishop", "king", "queen", "estandar"]) {
      for (const event of ["move", "capture"]) {
        const key = `${event}_${kind}`;
        const assetKind = kind === "estandar" ? "rook" : kind;
        const audio = new Audio(`/assets/sounds/${event}_${assetKind}.ogg`);
        audio.preload = "auto";
        this.templates[key] = audio;
      }
    }
    this.templates.check_king = new Audio("/assets/sounds/check_king.ogg");
  }

  ensureContext() {
    if (this.context) return this.context;
    const Context = window.AudioContext || window.webkitAudioContext;
    if (!Context) return null;
    try {
      this.context = new Context();
      this.master = this.context.createGain();
      this.master.gain.value = .34;
      this.master.connect(this.context.destination);
      return this.context;
    } catch (error) {
      this.context = null;
      this.master = null;
      return null;
    }
  }

  setEnabled(value) {
    this.enabled = Boolean(value);
    if (!this.enabled) return;
    const context = this.ensureContext();
    if (context?.state === "suspended") context.resume().catch(() => {});
    this.play("ui_on", .36);
  }

  resolveKey(key) {
    const match = /^(move|capture)_(.+)$/.exec(key);
    if (!match) return key;
    return `${match[1]}_${this.soundAliases[match[2]] || match[2]}`;
  }

  patternFor(key) {
    if (key === "ui_on") return [[660, .06, 0, "sine"], [880, .09, .025, "sine"]];
    if (key.startsWith("capture_")) return [[220, .08, 0, "sawtooth"], [145, .13, .025, "square"]];
    if (key.startsWith("move_")) return [[360, .075, 0, "triangle"]];
    if (key === "pickup") return [[440, .07, 0, "sine"], [660, .11, .03, "sine"]];
    if (key === "drop") return [[330, .08, 0, "triangle"], [220, .11, .03, "triangle"]];
    if (key === "respawn") return [[300, .07, 0, "sine"], [470, .1, .03, "sine"]];
    if (key === "check_king") return [[520, .08, 0, "square"], [700, .12, .04, "square"]];
    if (key === "result_win") return [[523, .09, 0, "sine"], [659, .09, .05, "sine"], [784, .18, .05, "sine"]];
    if (key === "result_draw") return [[392, .12, 0, "triangle"], [330, .18, .06, "triangle"]];
    return null;
  }

  play(key, volume = .7) {
    if (!this.enabled) return;
    const context = this.ensureContext();
    const resolvedKey = this.resolveKey(key);
    const pattern = this.patternFor(resolvedKey);
    const template = this.templates[resolvedKey] || this.templates[key];
    if (!pattern && !template) return;
    if (!context || !this.master || !pattern) {
      if (!template) return;
      const audio = template.cloneNode();
      audio.volume = volume;
      audio.play().catch(() => {});
      return;
    }
    if (context.state === "suspended") context.resume().catch(() => {});
    let cursor = Math.max(context.currentTime + .01, this.scheduledUntil);
    for (const [frequency, duration, gap, type] of pattern) {
      const start = cursor + gap;
      const oscillator = context.createOscillator();
      const gain = context.createGain();
      oscillator.type = type;
      oscillator.frequency.setValueAtTime(frequency, start);
      gain.gain.setValueAtTime(.0001, start);
      gain.gain.exponentialRampToValueAtTime(Math.max(.001, volume), start + .008);
      gain.gain.exponentialRampToValueAtTime(.0001, start + duration);
      oscillator.connect(gain).connect(this.master);
      oscillator.start(start);
      oscillator.stop(start + duration + .02);
      cursor = start + duration;
    }
    this.scheduledUntil = cursor;
  }
}

const soundBank = new SoundBank();

class TacticalGridUI {
  constructor(scene) {
    this.scene = scene;
    this.lastResult = null;
    this.pickingTarget = false;
    this.mutationPending = false;
    this.desynchronized = false;
    this.stateEpoch = 0;
    this.legalRequestId = 0;
    this.legalController = null;
    this.lastPresentation = null;
    this.moveHistory = [];
    this.searchAlgorithm = "bfs";
    this.searchPending = false;
    this.searchController = null;
    this.searchRequestId = 0;
    this.adversarialPending = false;
    this.adversarialController = null;
    this.adversarialRequestId = 0;
    this.adversarialOptions = [];
    this.adversarialIndex = -1;
    this.adversarialRecommendation = null;
    this.autoPlayActive = false;
    this.autoPlayRunId = 0;
    this.autoPlayTimer = null;
    this.autoPlayWaitResolve = null;
    const el = id => document.getElementById(id);
    this.el = el;

    el("audioToggle").addEventListener("click", () => {
      const on = el("audioToggle").dataset.on !== "true";
      el("audioToggle").dataset.on = String(on);
      el("audioToggle").setAttribute("aria-pressed", String(on));
      el("audioToggle").setAttribute("aria-label", on ? "Desactivar sonido" : "Activar sonido");
      el("audioToggle").title = on ? "Desactivar sonido" : "Activar sonido";
      soundBank.setEnabled(on);
    });
    el("panelToggle").addEventListener("click", () => {
      const closed = el("uiPanel").classList.toggle("collapsed");
      document.body.classList.toggle("panel-collapsed", closed);
      el("panelToggle").setAttribute("aria-expanded", String(!closed));
      el("panelToggle").setAttribute("aria-label", closed ? "Mostrar controles" : "Ocultar controles");
      el("panelToggle").title = closed ? "Mostrar controles" : "Ocultar controles";
      window.setTimeout(() => this.scene.scale.refresh(), 220);
    });
    el("loadScenario").addEventListener("click", () => el("scenarioFile").click());
    el("scenarioFile").addEventListener("change", async event => {
      const file = event.target.files[0];
      if (!file) return;
      try {
        const scenario = JSON.parse(await file.text());
        await this.runMutation("/api/scenarios", {scenario, filename: file.name}, "state");
      } catch (error) {
        this.reportError(error);
      } finally {
        event.target.value = "";
      }
    });
    el("syncState").addEventListener("click", () => this.synchronizeState());
    el("restart").addEventListener("click", () => this.runMutation("/api/reset", {}, "state"));
    el("resultRestart").addEventListener("click", () => this.restartFromResult());
    el("resultClose").addEventListener("click", () => this.hideResultScreen());
    el("configureKings").addEventListener("click", () => this.configureKings());
    for (const card of document.querySelectorAll("[data-king-mode]")) {
      card.addEventListener("click", () => {
        if (card.disabled) return;
        el("kingMode").value = card.dataset.kingMode;
        this.updateKingInputs();
      });
    }
    for (const card of document.querySelectorAll("[data-search-algorithm]")) {
      card.addEventListener("click", () => {
        if (card.disabled) return;
        this.setSearchAlgorithm(card.dataset.searchAlgorithm);
      });
    }
    el("runSearch").addEventListener("click", () => this.search());
    el("clearSearch").addEventListener("click", () => this.clearSearchResult({announce: true}));
    el("runAdversarial").addEventListener("click", () => this.adversarial());
    el("applyAdversarial").addEventListener("click", () => this.applyAdversarialRecommendation());
    el("autoPlayToggle").addEventListener("click", () => this.toggleAutoPlay());
    el("clearAdversarial").addEventListener("click", () => this.clearAdversarialResult({announce: true}));
    el("adversarialPrevious").addEventListener("click", () => this.showAdversarialOption(this.adversarialIndex - 1));
    el("adversarialNext").addEventListener("click", () => this.showAdversarialOption(this.adversarialIndex + 1));
    el("adversarialOptions").addEventListener("click", event => {
      const option = event.target.closest("[data-adversarial-index]");
      if (option && this.el("adversarialOptions").contains(option)) {
        this.showAdversarialOption(Number(option.dataset.adversarialIndex));
      }
    });
    el("adversarialAlgorithm").addEventListener("change", () => {
      this.updateAdversarialControls();
      this.clearAdversarialResult();
    });
    for (const input of [el("adversarialDepth"), el("adversarialOrder")]) {
      input.addEventListener("input", () => this.clearAdversarialResult());
      input.addEventListener("change", () => this.clearAdversarialResult());
    }
    el("pickSearchTarget").addEventListener("click", () => this.setTargetPicking(!this.pickingTarget));
    el("searchUnit").addEventListener("change", () => {
      this.setTargetPicking(false, {announce: false});
      this.clearSearchResult();
    });
    for (const input of [el("searchTargetRow"), el("searchTargetCol")]) {
      input.addEventListener("input", () => {
        this.setTargetPicking(false, {announce: false});
        this.clearSearchResult();
      });
    }
    for (const input of [el("searchHeuristic"), el("searchBeamWidth")]) {
      input.addEventListener("input", () => this.clearSearchResult());
    }
    document.addEventListener("keydown", event => {
      if (event.key !== "Escape" || !this.pickingTarget) return;
      event.preventDefault();
      this.setTargetPicking(false);
    });
    this.setSearchAlgorithm("bfs");
    this.updateKingInputs();
    this.updateSearchControls();
    this.updateAdversarialControls();
  }

  setSearchAlgorithm(algorithm) {
    if (!["bfs", "dfs", "ucs", "astar", "beam"].includes(algorithm)) return;
    this.searchAlgorithm = algorithm;
    for (const card of document.querySelectorAll("[data-search-algorithm]")) {
      const selected = card.dataset.searchAlgorithm === algorithm;
      card.classList.toggle("is-selected", selected);
      card.setAttribute("aria-pressed", String(selected));
    }
    this.el("astarSearchOptions").hidden = algorithm !== "astar";
    this.el("beamSearchOptions").hidden = algorithm !== "beam";
    const result = this.el("searchResult");
    if (result && !result.hidden) this.clearSearchResult();
  }

  setTargetPicking(active, {announce = true} = {}) {
    const wasPicking = this.pickingTarget;
    const enabled = Boolean(active) && !this.searchPending && !this.mutationPending && !this.desynchronized;
    this.pickingTarget = enabled;
    const button = this.el("pickSearchTarget");
    button.classList.toggle("is-active", enabled);
    button.setAttribute("aria-pressed", String(enabled));
    this.el("pickSearchTargetLabel").textContent = enabled ? "Cancelar" : "Elegir";
    if (this.scene.game?.canvas) this.scene.game.canvas.style.cursor = enabled ? "crosshair" : "";
    if (!announce) return;
    if (enabled) {
      this.setActionHint("Selecciona una celda objetivo en el tablero.", {kind: "info"});
      this.say("Haz clic en una celda del tablero para fijar el objetivo de la búsqueda.");
    } else {
      this.setActionHint(this.defaultActionHint(
        this.scene.state,
        this.scene.state?.juego?.estado === "finalizado"
      ));
      if (wasPicking) this.say("Selección de objetivo cancelada.");
    }
  }

  setTarget(row, column) {
    if (!Number.isInteger(row) || !Number.isInteger(column) ||
        row < 0 || column < 0 || row >= this.scene.rows || column >= this.scene.cols) {
      return;
    }
    this.clearSearchResult();
    this.el("searchTargetRow").value = String(row);
    this.el("searchTargetCol").value = String(column);
    this.setTargetPicking(false, {announce: false});
    this.setActionHint(`Objetivo (${row}, ${column}) listo. Ejecuta la búsqueda.`, {kind: "info"});
    this.say(`Objetivo de búsqueda: fila ${row}, columna ${column}.`);
  }

  updateSearchUnits(state) {
    const select = this.el("searchUnit");
    const previous = select.value;
    const units = (state.unidades || []).filter(unit => unit.activo !== false);
    select.replaceChildren();
    if (units.length === 0) {
      const option = new Option("Sin unidades activas", "");
      option.disabled = true;
      option.selected = true;
      select.append(option);
      return;
    }
    for (const unit of units) {
      select.append(new Option(`${unit.id} · ${this.unitLabel(unit)}`, unit.id));
    }
    const preferred = [previous, state.prueba?.unidad_inicio]
      .find(id => units.some(unit => unit.id === id));
    select.value = preferred || units[0].id;
  }

  updateSearchTargetBounds(state) {
    const rows = state?.mapa?.filas ?? this.scene.rows;
    const columns = state?.mapa?.columnas ?? this.scene.cols;
    const rowInput = this.el("searchTargetRow");
    const columnInput = this.el("searchTargetCol");
    rowInput.max = String(Math.max(0, rows - 1));
    columnInput.max = String(Math.max(0, columns - 1));
    const row = this.parseCoordinate(rowInput.value);
    const column = this.parseCoordinate(columnInput.value);
    if (row !== null && column !== null && row < rows && column < columns) return;
    const testGoal = state?.prueba?.objetivo;
    const queen = state?.juego?.portador_recurso == null ? state?.recurso : null;
    const suggestion = [testGoal, queen, state?.bases?.B, state?.bases?.A].find(candidate =>
      candidate && Number.isInteger(candidate.fila) && Number.isInteger(candidate.columna) &&
      candidate.fila >= 0 && candidate.fila < rows &&
      candidate.columna >= 0 && candidate.columna < columns
    );
    rowInput.value = suggestion ? String(suggestion.fila) : "0";
    columnInput.value = suggestion ? String(suggestion.columna) : "0";
  }

  parseCoordinate(value) {
    const text = String(value ?? "").trim();
    if (!text) return null;
    const number = Number(text);
    return Number.isInteger(number) ? number : null;
  }

  readSearchTarget() {
    const row = this.parseCoordinate(this.el("searchTargetRow").value);
    const column = this.parseCoordinate(this.el("searchTargetCol").value);
    if (row === null || column === null) {
      return {error: "Escribe una fila y una columna enteras para el objetivo."};
    }
    const rows = this.scene.state?.mapa?.filas ?? 0;
    const columns = this.scene.state?.mapa?.columnas ?? 0;
    if (row < 0 || column < 0 || row >= rows || column >= columns) {
      return {
        error: `El objetivo debe estar dentro del mapa (filas 0–${Math.max(0, rows - 1)}, columnas 0–${Math.max(0, columns - 1)}).`
      };
    }
    return {row, column};
  }

  updateSearchControls() {
    const state = this.scene.state;
    const select = this.el("searchUnit");
    const hasUnit = Boolean(select?.value &&
      [...select.options].some(option => option.value === select.value));
    const locked = this.mutationPending || this.desynchronized || !state || !hasUnit;
    const busy = this.searchPending;
    for (const id of [
      "searchUnit", "searchTargetRow", "searchTargetCol", "searchHeuristic",
      "searchBeamWidth", "pickSearchTarget", "runSearch"
    ]) {
      const control = this.el(id);
      if (control) control.disabled = locked || busy;
    }
    for (const card of document.querySelectorAll("[data-search-algorithm]")) {
      card.disabled = locked || busy;
    }
    const runLabel = this.el("runSearchLabel");
    if (runLabel) runLabel.textContent = busy ? "Calculando ruta…" : "Ejecutar búsqueda";
    const result = this.el("searchResult");
    const clear = this.el("clearSearch");
    if (clear) clear.disabled = locked || busy || result.hidden;
    if (result) result.setAttribute("aria-busy", String(busy));
  }

  cancelSearch() {
    this.searchRequestId += 1;
    if (this.searchController) this.searchController.abort();
    this.searchController = null;
    this.searchPending = false;
    this.updateSearchControls();
  }

  clearSearchResult({announce = false} = {}) {
    const result = this.el("searchResult");
    result.hidden = true;
    result.removeAttribute("data-state");
    this.el("searchResultTitle").textContent = "—";
    this.el("searchMessage").textContent = "";
    this.el("searchMetrics").hidden = true;
    this.el("searchDiscardedMetric").hidden = true;
    this.el("searchDiscarded").textContent = "—";
    const path = this.el("searchPath");
    path.hidden = true;
    path.textContent = "";
    path.removeAttribute("title");
    this.scene.showSearchPath([]);
    this.updateSearchControls();
    if (announce) {
      this.setActionHint(this.defaultActionHint(
        this.scene.state,
        this.scene.state?.juego?.estado === "finalizado"
      ));
      this.say("Ruta sugerida eliminada.");
    }
  }

  formatSearchNumber(value) {
    if (!Number.isFinite(value)) return "—";
    return Number.isInteger(value) ? String(value) : String(Number(value.toFixed(2)));
  }

  formatSearchTime(seconds) {
    if (!Number.isFinite(seconds)) return "—";
    return seconds < 1 ? `${(seconds * 1000).toFixed(1)} ms` : `${seconds.toFixed(2)} s`;
  }

  renderSearchResult(result, context) {
    const algorithm = context.algorithm.toUpperCase();
    const target = `(${context.target.row}, ${context.target.column})`;
    const panel = this.el("searchResult");
    panel.hidden = false;
    this.el("searchMetrics").hidden = !result.input_valid;
    this.el("searchMoves").textContent = this.formatSearchNumber(result.moves);
    this.el("searchCost").textContent = this.formatSearchNumber(result.cost);
    this.el("searchGenerated").textContent = this.formatSearchNumber(result.states_generated);
    this.el("searchExpanded").textContent = this.formatSearchNumber(result.states_expanded);
    this.el("searchFrontier").textContent = this.formatSearchNumber(result.max_frontier);
    this.el("searchElapsed").textContent = this.formatSearchTime(result.elapsed_seconds);
    const discardedMetric = this.el("searchDiscardedMetric");
    discardedMetric.hidden = context.algorithm !== "beam" || !Number.isFinite(result.candidates_discarded);
    this.el("searchDiscarded").textContent = this.formatSearchNumber(result.candidates_discarded);
    const path = this.el("searchPath");
    path.hidden = true;
    path.textContent = "";
    path.removeAttribute("title");

    if (!result.input_valid) {
      panel.dataset.state = "error";
      this.el("searchResultTitle").textContent = "Entrada no válida";
      this.el("searchMessage").textContent = result.error || "El servidor rechazó los datos de la búsqueda.";
      this.scene.showSearchPath([]);
      this.say(result.error || "El servidor rechazó los datos de la búsqueda.", {
        title: `${algorithm} no pudo iniciar`,
        tone: "error"
      });
      this.updateSearchControls();
      return;
    }

    if (!result.found) {
      panel.dataset.state = "empty";
      this.el("searchResultTitle").textContent = "Sin ruta encontrada";
      const noRouteMessage = context.algorithm === "beam"
        ? `Beam agotó el haz sin conservar una ruta hasta ${target}; pudo descartar candidatos necesarios.`
        : `No existe una ruta legal desde ${context.unitId} hasta ${target}.`;
      this.el("searchMessage").textContent = noRouteMessage;
      this.scene.showSearchPath([]);
      this.setActionHint(noRouteMessage, {kind: "info"});
      this.say(noRouteMessage, {
        title: context.algorithm === "beam" ? "Haz agotado" : "Objetivo inalcanzable",
        tone: "info"
      });
      this.updateSearchControls();
      return;
    }

    panel.dataset.state = "found";
    this.el("searchResultTitle").textContent = `${algorithm} encontró una ruta`;
    if (context.algorithm === "bfs") {
      this.el("searchMessage").textContent = "BFS garantiza el menor número de movimientos en este escenario.";
    } else if (context.algorithm === "dfs") {
      this.el("searchMessage").textContent = "DFS devuelve la primera ruta encontrada; puede no ser la más corta.";
    } else if (context.algorithm === "ucs") {
      this.el("searchMessage").textContent =
        "Con costos de movimiento positivos, UCS prioriza el menor costo acumulado y garantiza una ruta de costo mínimo, sin heurística.";
    } else if (context.algorithm === "astar") {
      const heuristicName = context.heuristic === "second" ? "costo restante" : "Manhattan";
      this.el("searchMessage").textContent =
        `A* prioriza costo acumulado + heurística (${heuristicName}); la ruta depende de la heurística elegida.`;
    } else {
      this.el("searchMessage").textContent =
        `Beam conservó hasta ${context.k} estados por nivel. No garantiza una ruta ni la optimalidad.`;
    }
    const points = result.path.map(point => `${point.fila},${point.columna}`);
    if (points.length) {
      const fullPath = `Ruta: ${points.join(" → ")}`;
      path.textContent = points.length > 24
        ? `Ruta: ${points.slice(0, 12).join(" → ")} → … → ${points.slice(-6).join(" → ")}`
        : fullPath;
      path.title = fullPath;
      path.hidden = false;
    }
    this.scene.showSearchPath(result.path);
    const moves = result.moves ?? 0;
    const moveLabel = moves === 1 ? "movimiento" : "movimientos";
    const cost = this.formatSearchNumber(result.cost);
    this.setActionHint(
      `${algorithm}: ${moves} ${moveLabel} · costo ${cost}. La ruta se muestra en el tablero.`,
      {kind: "move"}
    );
    this.say(`${algorithm} encontró una ruta de ${moves} ${moveLabel} hasta ${target}.`, {
      title: "Ruta encontrada",
      tone: "success"
    });
    this.updateSearchControls();
  }

  showSearchProblem(title, message) {
    const panel = this.el("searchResult");
    panel.hidden = false;
    panel.dataset.state = "error";
    this.el("searchResultTitle").textContent = title;
    this.el("searchMessage").textContent = message;
    this.el("searchMetrics").hidden = true;
    const path = this.el("searchPath");
    path.hidden = true;
    path.textContent = "";
    path.removeAttribute("title");
    this.scene.showSearchPath([]);
    this.updateSearchControls();
    this.say(message, {title, tone: "error"});
  }

  async search() {
    if (this.autoPlayActive) this.stopAutoPlay({message: "Autojuego pausado para ejecutar otra búsqueda."});
    if (this.mutationPending || this.searchPending || this.desynchronized) return null;
    const unitId = this.el("searchUnit").value;
    if (!unitId) {
      this.showSearchProblem("Sin unidad", "No hay una unidad activa para iniciar la búsqueda.");
      return null;
    }
    const target = this.readSearchTarget();
    if (target.error) {
      this.showSearchProblem("Revisa el objetivo", target.error);
      return null;
    }
    const algorithm = this.searchAlgorithm;
    const heuristic = this.el("searchHeuristic").value;
    const k = Number(this.el("searchBeamWidth").value);
    if (algorithm === "beam" && (!Number.isSafeInteger(k) || k < 1)) {
      this.showSearchProblem("Ancho no válido", "El ancho del haz k debe ser un entero mayor que cero.");
      return null;
    }
    this.setTargetPicking(false, {announce: false});
    this.cancelAdversarial({clearResult: true});
    this.cancelSearch();
    this.clearSearchResult();
    const requestId = this.searchRequestId;
    const epoch = this.stateEpoch;
    const controller = new AbortController();
    this.searchController = controller;
    this.searchPending = true;
    this.updateSearchControls();
    this.setActionHint(`Calculando ruta con ${algorithm.toUpperCase()}…`, {kind: "move"});
    try {
      const payload = {
        algorithm,
        unit_id: unitId,
        goal: {row: target.row, column: target.column}
      };
      if (algorithm === "astar") payload.heuristic = heuristic;
      if (algorithm === "beam") payload.k = k;
      const result = await ApiClient.search(payload, controller.signal);
      if (requestId !== this.searchRequestId || epoch !== this.stateEpoch) return null;
      const context = {algorithm, unitId, target, heuristic, k};
      this.renderSearchResult(result, context);
      return result;
    } catch (error) {
      if (error?.name === "AbortError" || requestId !== this.searchRequestId) return null;
      this.showSearchProblem(
        "Búsqueda no completada",
        error?.message || "No se pudo ejecutar la búsqueda."
      );
      return null;
    } finally {
      if (requestId === this.searchRequestId) {
        this.searchController = null;
        this.searchPending = false;
        this.updateSearchControls();
      }
    }
  }

  updateAdversarialControls() {
    const state = this.scene.state;
    const locked = this.mutationPending || this.desynchronized || !state || this.adversarialPending || this.autoPlayActive;
    for (const id of ["adversarialAlgorithm", "adversarialDepth", "adversarialOrder", "runAdversarial"]) {
      const control = this.el(id);
      if (control) control.disabled = locked;
    }
    this.el("adversarialOrder").disabled = locked || this.el("adversarialAlgorithm").value !== "alpha_beta";
    this.el("runAdversarialLabel").textContent = this.adversarialPending ? "Analizando…" : "Analizar posición";
    const hasOptions = this.adversarialOptions.length > 0;
    this.el("adversarialPrevious").disabled = locked || !hasOptions || this.adversarialIndex <= 0;
    this.el("adversarialNext").disabled = locked || !hasOptions || this.adversarialIndex >= this.adversarialOptions.length - 1;
    this.el("applyAdversarial").disabled = locked || !this.adversarialRecommendation;
    this.el("clearAdversarial").disabled = locked || this.el("adversarialResult").hidden;
    const autoPlay = this.el("autoPlayToggle");
    this.el("autoPlayLabel").textContent = this.autoPlayActive
      ? "Pausar autojuego"
      : "Autojugar ambos bandos";
    autoPlay.setAttribute("aria-pressed", String(this.autoPlayActive));
    autoPlay.disabled = this.desynchronized || !state ||
      (this.mutationPending && !this.autoPlayActive) ||
      (this.adversarialPending && !this.autoPlayActive) ||
      (!this.autoPlayActive && state.juego?.estado !== "en_curso");
    this.el("autoPlayStatus").hidden = !this.el("autoPlayStatus").textContent;
    this.el("adversarialResult").setAttribute("aria-busy", String(this.adversarialPending));
  }

  setAutoPlayStatus(message) {
    const status = this.el("autoPlayStatus");
    status.textContent = message;
    status.hidden = !message;
  }

  resetAdversarialView() {
    this.adversarialOptions = [];
    this.adversarialIndex = -1;
    this.adversarialRecommendation = null;
    this.scene.clearAdversarialAction();
    this.el("adversarialResult").hidden = true;
    this.el("adversarialResult").removeAttribute("data-state");
    this.el("adversarialStatus").textContent = "";
    this.el("adversarialActionSummary").textContent = "";
    this.el("adversarialMetrics").hidden = true;
    this.el("adversarialOptions").replaceChildren();
    this.el("adversarialPosition").textContent = "0 / 0";
  }

  cancelAdversarial({clearResult = false} = {}) {
    this.adversarialRequestId += 1;
    if (this.adversarialController) this.adversarialController.abort();
    this.adversarialController = null;
    this.adversarialPending = false;
    if (clearResult) this.resetAdversarialView();
    this.updateAdversarialControls();
  }

  clearAdversarialResult({announce = false} = {}) {
    this.cancelAdversarial();
    this.resetAdversarialView();
    this.updateAdversarialControls();
    if (announce) this.say("Análisis adversarial eliminado.");
  }

  async loadAdversarialOptions(state, signal) {
    const units = state.unidades.filter(unit =>
      unit.activo !== false && unit.bando === state.turno
    );
    const responses = await Promise.all(units.map(unit => ApiClient.legalMoves(unit.id, signal)));
    const options = [];
    for (let index = 0; index < units.length; index++) {
      const unit = units[index];
      const response = responses[index];
      for (const destination of response.destinations) {
        const position = {fila: destination.row, columna: destination.column};
        const collect = destination.kind === "collect";
        options.push({
          action: collect
            ? {type: "collect", unit_id: unit.id}
            : {type: "move", unit_id: unit.id, destination: position},
          kind: destination.kind,
          unit,
          origin: {fila: unit.fila, columna: unit.columna},
          destination: position
        });
      }
    }
    options.sort((left, right) => {
      if (left.action.unit_id !== right.action.unit_id) {
        return left.action.unit_id < right.action.unit_id ? -1 : 1;
      }
      if (left.action.type !== right.action.type) return left.action.type === "collect" ? 1 : -1;
      return left.destination.fila - right.destination.fila ||
        left.destination.columna - right.destination.columna;
    });
    return {options, responses};
  }

  matchesAdversarialAction(option, action) {
    if (!option || !action || option.action.unit_id !== action.unit_id || option.action.type !== action.type) {
      return false;
    }
    return action.type === "collect" ||
      (option.action.destination.fila === action.destination.fila &&
       option.action.destination.columna === action.destination.columna);
  }

  formatAdversarialAction(action) {
    const unit = this.scene.state?.unidades?.find(candidate => candidate.id === action.unit_id);
    const label = `${action.unit_id}${unit ? ` · ${this.unitLabel(unit)}` : ""}`;
    if (action.type === "collect") return `${label}: recoger reina`;
    const origin = unit && Number.isInteger(unit.fila) && Number.isInteger(unit.columna)
      ? `(${unit.fila}, ${unit.columna}) → `
      : "";
    return `${label}: ${origin}(${action.destination.fila}, ${action.destination.columna})`;
  }

  renderAdversarialResult(result, options) {
    this.adversarialOptions = options;
    const panel = this.el("adversarialResult");
    panel.hidden = false;
    panel.dataset.state = result.action ? "found" : "empty";
    this.el("adversarialStatus").textContent = result.action
      ? `Recomendación de ${result.algorithm === "minimax" ? "Minimax" : "alfa-beta"}. Las opciones de abajo son acciones legales del turno, no ramas internas de búsqueda.`
      : "No hay recomendación: la posición es terminal o la profundidad solicitada es 0.";
    this.el("adversarialActionSummary").textContent = result.action
      ? this.formatAdversarialAction(result.action)
      : "Sin acción recomendada";
    this.el("adversarialValueLabel").textContent = `Valor · ${teamLabel(this.scene.state.turno)}`;
    this.el("adversarialValue").textContent = String(result.value);
    this.el("adversarialDepthRequested").textContent = String(result.requested_depth);
    this.el("adversarialDepthReached").textContent = String(result.depth_reached);
    this.el("adversarialGenerated").textContent = String(result.nodes_generated);
    this.el("adversarialVisited").textContent = String(result.nodes_visited);
    this.el("adversarialEvaluated").textContent = String(result.nodes_evaluated);
    this.el("adversarialPruned").textContent = String(result.nodes_pruned);
    this.el("adversarialElapsed").textContent = `${(result.elapsed_seconds * 1000).toFixed(2)} ms`;
    this.el("adversarialMetrics").hidden = false;

    const recommendedIndex = result.action
      ? options.findIndex(option => this.matchesAdversarialAction(option, result.action))
      : -1;
    this.adversarialRecommendation = recommendedIndex >= 0 ? options[recommendedIndex] : null;
    const list = this.el("adversarialOptions");
    list.replaceChildren();
    options.forEach((option, index) => {
      const item = document.createElement("li");
      const button = document.createElement("button");
      const actionType = option.kind === "capture" ? "capturar" :
        option.kind === "collect" ? "recoger reina" : "mover";
      const origin = `(${option.origin.fila}, ${option.origin.columna})`;
      const destination = `(${option.destination.fila}, ${option.destination.columna})`;
      button.type = "button";
      button.dataset.adversarialIndex = String(index);
      button.className = "adversarial-option";
      if (index === recommendedIndex) button.classList.add("is-recommended");
      button.setAttribute("aria-label", `${this.formatAdversarialAction(option.action)}; ${actionType}${index === recommendedIndex ? "; recomendada" : ""}`);
      const title = document.createElement("strong");
      title.textContent = `${option.unit.id} · ${this.unitLabel(option.unit)}`;
      const detail = document.createElement("span");
      detail.textContent = option.kind === "collect"
        ? `${origin} · Recoger reina`
        : `${origin} → ${destination} · ${actionType}`;
      button.append(title, detail);
      if (index === recommendedIndex) {
        const badge = document.createElement("em");
        badge.textContent = "Recomendada";
        button.append(badge);
      }
      item.append(button);
      list.append(item);
    });

    this.adversarialIndex = recommendedIndex;
    if (recommendedIndex >= 0) this.showAdversarialOption(recommendedIndex);
    else {
      this.scene.clearAdversarialAction();
      this.el("adversarialPosition").textContent = options.length ? `0 / ${options.length}` : "0 / 0";
    }
    if (result.action && recommendedIndex < 0) {
      this.el("adversarialStatus").textContent += " La recomendación no coincide con la lista legal consultada; no se resaltó como opción válida.";
    }
    this.updateAdversarialControls();
  }

  showAdversarialOption(index) {
    if (!Number.isInteger(index) || index < 0 || index >= this.adversarialOptions.length) return;
    this.adversarialIndex = index;
    const option = this.adversarialOptions[index];
    this.scene.showAdversarialAction(option);
    this.el("adversarialPosition").textContent = `${index + 1} / ${this.adversarialOptions.length}`;
    for (const button of this.el("adversarialOptions").querySelectorAll("[data-adversarial-index]")) {
      const selected = Number(button.dataset.adversarialIndex) === index;
      button.classList.toggle("is-current", selected);
      button.setAttribute("aria-current", String(selected));
    }
    this.updateAdversarialControls();
  }

  async applyAdversarialRecommendation() {
    if (!this.adversarialRecommendation || this.mutationPending || this.autoPlayActive) return null;
    return this.executeAdversarialAction(this.adversarialRecommendation);
  }

  async executeAdversarialAction(option, {preserveAutoPlay = false, quiet = false} = {}) {
    if (!option) return null;
    if (option.action.type === "collect") {
      return this.collectQueen(option.action.unit_id, {preserveAutoPlay, quiet});
    }
    return this.move(
      option.action.unit_id,
      option.action.destination.fila,
      option.action.destination.columna,
      {preserveAutoPlay, quiet}
    );
  }

  toggleAutoPlay() {
    if (this.autoPlayActive) {
      this.stopAutoPlay({message: "Autojuego pausado por el usuario.", announce: true});
      return;
    }
    this.startAutoPlay();
  }

  startAutoPlay() {
    const state = this.scene.state;
    if (this.mutationPending || this.adversarialPending || this.desynchronized ||
        !state || state.juego?.estado !== "en_curso") {
      this.setAutoPlayStatus("El autojuego requiere una partida en curso.");
      return;
    }
    this.autoPlayActive = true;
    const runId = ++this.autoPlayRunId;
    this.setAutoPlayStatus("Autopartida activa: ambos bandos analizarán y ejecutarán una jugada por turno.");
    this.updateAdversarialControls();
    this.say("Autopartida iniciada. Ambos bandos jugarán con el algoritmo y la profundidad seleccionados.", {
      title: "Autojuego iniciado", tone: "success"
    });
    this.runAutoPlay(runId);
  }

  stopAutoPlay({message = "Autojuego detenido.", announce = false} = {}) {
    if (!this.autoPlayActive) return false;
    this.autoPlayActive = false;
    this.autoPlayRunId += 1;
    if (this.autoPlayTimer !== null) window.clearTimeout(this.autoPlayTimer);
    this.autoPlayTimer = null;
    const resolveWait = this.autoPlayWaitResolve;
    this.autoPlayWaitResolve = null;
    if (resolveWait) resolveWait(false);
    if (this.adversarialPending) this.cancelAdversarial({clearResult: true});
    this.setAutoPlayStatus(message);
    this.updateAdversarialControls();
    if (announce) this.say(message, {title: "Autojuego pausado", tone: "info"});
    return true;
  }

  waitForAutoPlay(ms, runId) {
    if (!this.autoPlayActive || runId !== this.autoPlayRunId) return Promise.resolve(false);
    return new Promise(resolve => {
      this.autoPlayWaitResolve = resolve;
      this.autoPlayTimer = window.setTimeout(() => {
        this.autoPlayTimer = null;
        this.autoPlayWaitResolve = null;
        resolve(this.autoPlayActive && runId === this.autoPlayRunId);
      }, ms);
    });
  }

  async runAutoPlay(runId) {
    const isCurrent = () => this.autoPlayActive && runId === this.autoPlayRunId;
    try {
      while (isCurrent()) {
        const state = this.scene.state;
        if (!state || state.juego?.estado !== "en_curso") {
          this.stopAutoPlay({message: "La partida terminó. Autojuego detenido."});
          return;
        }
        const side = state.turno;
        this.setAutoPlayStatus(`Turno de ${teamLabel(side)}: calculando la jugada…`);
        const result = await this.adversarial();
        if (!isCurrent()) return;
        if (!result) {
          this.stopAutoPlay({message: "Autojuego detenido: no se pudo obtener una recomendación."});
          return;
        }
        if (!result.action) {
          this.stopAutoPlay({message: "Autojuego detenido: el algoritmo no recomendó una acción legal."});
          return;
        }
        const option = this.adversarialOptions.find(candidate =>
          this.matchesAdversarialAction(candidate, result.action)
        );
        if (!option) {
          this.stopAutoPlay({message: "Autojuego detenido: la recomendación no coincide con las acciones legales actuales."});
          return;
        }
        const description = this.formatAdversarialAction(result.action);
        this.setAutoPlayStatus(`${teamLabel(side)}: ${description}. Ejecutando en un momento…`);
        if (!await this.waitForAutoPlay(750, runId)) return;
        const data = await this.executeAdversarialAction(option, {preserveAutoPlay: true, quiet: true});
        if (!isCurrent()) return;
        if (!data) {
          this.stopAutoPlay({message: "Autojuego detenido: el servidor no confirmó la jugada."});
          return;
        }
        const nextState = this.scene.state;
        if (nextState?.juego?.estado === "finalizado") {
          this.stopAutoPlay({message: `Partida finalizada tras ${description}.`});
          return;
        }
        this.setAutoPlayStatus(`${teamLabel(side)} jugó ${description}. Turno de ${teamLabel(nextState?.turno)}.`);
        if (!await this.waitForAutoPlay(500, runId)) return;
      }
    } catch (error) {
      if (isCurrent()) this.stopAutoPlay({message: `Autojuego detenido: ${error?.message || "error inesperado"}.`});
    }
  }

  async adversarial() {
    if (this.mutationPending || this.adversarialPending || this.desynchronized || !this.scene.state) return null;
    const depthText = this.el("adversarialDepth").value.trim();
    const depth = Number(depthText);
    if (!depthText || !Number.isSafeInteger(depth) || depth < 0) {
      this.el("adversarialResult").hidden = false;
      this.el("adversarialResult").dataset.state = "error";
      this.el("adversarialStatus").textContent = "La profundidad debe ser un entero mayor o igual que cero.";
      this.el("adversarialMetrics").hidden = true;
      this.updateAdversarialControls();
      return null;
    }
    const algorithm = this.el("adversarialAlgorithm").value;
    const actionOrder = this.el("adversarialOrder").value;
    if (!["minimax", "alpha_beta"].includes(algorithm) ||
        (algorithm === "alpha_beta" && !["normal", "reverse"].includes(actionOrder))) {
      this.el("adversarialResult").hidden = false;
      this.el("adversarialResult").dataset.state = "error";
      this.el("adversarialStatus").textContent = "Selecciona un algoritmo y un orden de acciones válidos.";
      this.el("adversarialMetrics").hidden = true;
      this.updateAdversarialControls();
      return null;
    }

    this.setTargetPicking(false, {announce: false});
    this.cancelSearch();
    this.clearSearchResult();
    this.clearAdversarialResult();
    const state = this.scene.state;
    const requestId = this.adversarialRequestId;
    const epoch = this.stateEpoch;
    const controller = new AbortController();
    this.adversarialController = controller;
    this.adversarialPending = true;
    this.el("adversarialResult").hidden = false;
    this.el("adversarialResult").dataset.state = "loading";
    this.el("adversarialStatus").textContent = "Consultando Minimax y las acciones legales del turno…";
    this.updateAdversarialControls();
    try {
      const [result, legal] = await Promise.all([
        ApiClient.adversarial({
          algorithm,
          depth,
          action_order: algorithm === "alpha_beta" ? actionOrder : "normal"
        }, controller.signal),
        this.loadAdversarialOptions(state, controller.signal)
      ]);
      if (requestId !== this.adversarialRequestId || epoch !== this.stateEpoch) return null;
      const revisions = legal.responses
        .map(response => response.presentation?.revision)
        .filter(revision => typeof revision === "string");
      const knownRevision = this.lastPresentation?.revision;
      if ((knownRevision && revisions.some(revision => revision !== knownRevision)) ||
          new Set(revisions).size > 1) {
        const error = new Error("La partida cambió durante el análisis; se consultará el estado oficial.");
        error.stateChanged = true;
        throw error;
      }
      this.renderAdversarialResult(result, legal.options);
      return result;
    } catch (error) {
      if (error?.name === "AbortError" || requestId !== this.adversarialRequestId) return null;
      if (error?.stateChanged) {
        await this.reconcileOfficialState(error.message);
        return null;
      }
      this.resetAdversarialView();
      this.el("adversarialResult").hidden = false;
      this.el("adversarialResult").dataset.state = "error";
      this.el("adversarialStatus").textContent = error?.message || "No se pudo completar el análisis adversarial.";
      return null;
    } finally {
      if (requestId === this.adversarialRequestId) {
        this.adversarialController = null;
        this.adversarialPending = false;
        this.updateAdversarialControls();
      }
    }
  }

  updateKingInputs() {
    const mode = this.el("kingMode").value;
    this.el("automaticKings").hidden = mode !== "automatic";
    this.el("manualKings").hidden = mode !== "manual";
    this.el("kingCountA").disabled = mode !== "automatic";
    this.el("kingCountB").disabled = mode !== "automatic";
    this.el("manualKingsA").disabled = mode !== "manual";
    this.el("manualKingsB").disabled = mode !== "manual";
    for (const card of document.querySelectorAll("[data-king-mode]")) {
      const selected = card.dataset.kingMode === mode;
      card.classList.toggle("is-selected", selected);
      card.setAttribute("aria-checked", String(selected));
    }
  }

  pieceAsset(unit, fallbackTeam = "A") {
    const team = unit?.bando === "B" ? "b" : fallbackTeam === "B" ? "b" : "a";
    const kind = canonicalPieceType(unit?.tipo) || "estandar";
    const extension = kind === "estandar" ? "svg" : "png";
    const cacheBust = kind === "estandar" ? "?v=4" : "";
    return `/assets/pieces/${kind}_${team}.${extension}${cacheBust}`;
  }

  dismissToast(toast) {
    if (!toast?.isConnected || toast.classList.contains("is-leaving")) return;
    toast.classList.add("is-leaving");
    window.setTimeout(() => toast.remove(), 240);
  }

  say(text, options = {}) {
    const region = this.el("toastRegion");
    if (!region || !text) return;
    const toast = document.createElement("article");
    toast.className = "toast";
    toast.dataset.tone = options.tone || "info";
    const icon = document.createElement("div");
    icon.className = "toast-icon";
    if (options.asset) {
      const image = document.createElement("img");
      image.src = options.asset;
      image.alt = "";
      icon.append(image);
    } else {
      icon.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3a9 9 0 1 1 0 18 9 9 0 0 1 0-18Z"/><path d="M12 11v5m0-8h.01"/></svg>';
    }
    const copy = document.createElement("div");
    copy.className = "toast-copy";
    const title = document.createElement("strong");
    title.textContent = options.title || "TacticalGrid";
    const message = document.createElement("span");
    message.textContent = text;
    copy.append(title, message);
    const close = document.createElement("button");
    close.className = "toast-close";
    close.type = "button";
    close.setAttribute("aria-label", "Cerrar notificación");
    close.textContent = "×";
    close.addEventListener("click", () => this.dismissToast(toast));
    toast.append(icon, copy, close);
    region.append(toast);
    while (region.children.length > 4) region.firstElementChild.remove();
    window.setTimeout(() => this.dismissToast(toast), options.duration || 4200);
  }

  report() {}

  setActionHint(text, options = {}) {
    const hint = this.el("actionHint");
    if (!hint) return;
    const label = String(text ?? "");

    const kind = options.kind || (
      /turno de|selecciona (una ficha|primero una ficha)/i.test(label) ? "turn" :
      /captur|captura/i.test(label) ? "capture" :
      /reina/i.test(label) ? "queen" :
      /movimientos|mover|destinos/i.test(label) ? "move" :
      /terminada|comenzar/i.test(label) ? "info" : "info"
    );
    const team = options.team || (
      /\bBlancas\b/i.test(label) ? "A" : /\bNegras\b/i.test(label) ? "B" : ""
    );

    const icon = document.createElement("span");
    icon.className = "action-hint-icon";
    icon.dataset.kind = kind;
    icon.setAttribute("aria-hidden", "true");
    const asset = options.asset || (
      kind === "turn" ? `/assets/pieces/king_${team === "B" ? "b" : "a"}.png` :
      kind === "queen" ? "/assets/pieces/queen_a.png" : null
    );
    const iconPaths = {
      move: '<path d="M5 12h13m-5-5 5 5-5 5"/>',
      capture: '<path d="m6 6 12 12M18 6 6 18"/>',
      queen: '<path d="m5 18 2-9 5 4 5-4 2 9M7 18h10M8 21h8M7 9l-1-4 4 3 2-5 2 5 4-3-1 4"/>'
    };
    if (asset) {
      const image = document.createElement("img");
      image.src = asset;
      image.alt = "";
      icon.append(image);
    } else {
      icon.innerHTML = `<svg viewBox="0 0 24 24">${iconPaths[kind] || '<circle cx="12" cy="12" r="8"/><path d="M12 11v5m0-8v.1"/>'}</svg>`;
    }

    const copy = document.createElement("span");
    copy.className = "action-hint-copy";
    copy.textContent = label;
    hint.dataset.kind = kind;
    hint.dataset.team = team;
    hint.setAttribute("aria-label", label);
    hint.replaceChildren(icon, copy);
  }

  reportError(error) {
    if (error?.name === "AbortError") return;
    const isPending = error?.status === 501;
    this.say(isPending
      ? "Función pendiente de implementar en Python. No se modificó la partida."
      : (error?.message || "No se pudo completar la operación."), {title: "No se pudo completar", tone: "error"});
  }

  setInteractive(disabled) {
    const locked = disabled || this.desynchronized;
    for (const control of this.el("uiPanel").querySelectorAll("button, select, input")) {
      if (control.id !== "syncState" && control.id !== "autoPlayToggle") control.disabled = locked;
    }
    if (!disabled && !this.desynchronized) {
      this.updateKingInputs();
      const configurable = this.scene.state?.juego?.estado === "configuracion";
      for (const card of document.querySelectorAll("[data-king-mode]")) card.disabled = !configurable;
      this.el("configureKings").disabled = !configurable;
    }
    this.updateSyncButton();
    this.updateSearchControls();
    this.updateAdversarialControls();
    this.scene.setBusy(locked);
  }

  updateSyncButton() {
    const button = this.el("syncState");
    button.disabled = !this.desynchronized || this.mutationPending;
  }

  updateGameSummary(state) {
    const game = state.juego || {};
    this.el("gameStatus").textContent = game.estado === "finalizado"
      ? (game.resultado === "empate" ? "Empate" : `Victoria de ${teamPhrase(game.resultado)}`)
      : game.estado === "configuracion" ? "Configurando partida" : "Partida en curso";
  }

  updateGlobalStatus(state) {
    const turn = this.el("turn");
    turn.textContent = `Turno ${teamLabel(state.turno)}`;
    turn.dataset.team = state.turno;
    const carrierId = state.juego?.portador_recurso;
    const carrier = (state.unidades || []).find(unit => unit.id === carrierId);
    this.el("globalQueen").textContent = carrier ? `Con ${this.unitLabel(carrier)}` : "Disponible";
    for (const team of ["A", "B"]) {
      const count = (state.unidades || []).filter(unit => unit.bando === team && unit.activo !== false).length;
      this.el(`team${team}Count`).textContent = `${teamLabel(team)} ${count}`;
    }
  }

  positionLabel(position) {
    if (!position || !Number.isInteger(position.fila) || !Number.isInteger(position.columna)) return "";
    return `${position.fila},${position.columna}`;
  }

  recordTransition(events, previousState, currentState) {
    if (!previousState || !currentState) return;
    const previousUnits = new Map((previousState.unidades || []).map(unit => [unit.id, unit]));
    const currentUnits = new Map((currentState.unidades || []).map(unit => [unit.id, unit]));
    const capture = events.find(event => event.tipo === "captura");
    const pickup = events.find(event => event.tipo === "recogida");
    const queenReturned = events.some(event => event.tipo === "recurso_suelto");
    let unit;
    let title;
    let meta;

    if (capture) {
      unit = currentUnits.get(capture.atacante_id) || previousUnits.get(capture.atacante_id);
      const victim = previousUnits.get(capture.victima_id);
      const from = previousUnits.get(capture.atacante_id);
      title = `${this.unitLabel(unit)} capturó ${this.unitLabel(victim)}`;
      meta = `${this.positionLabel(from)} → ${this.positionLabel(capture.posicion)}${queenReturned ? " · reina reiniciada" : ""}`;
    } else if (pickup) {
      unit = currentUnits.get(pickup.unidad_id) || previousUnits.get(pickup.unidad_id);
      title = `${this.unitLabel(unit)} recogió la reina`;
      meta = `Casilla ${this.positionLabel(pickup.posicion)}`;
    } else {
      for (const [id, current] of currentUnits) {
        const previous = previousUnits.get(id);
        if (!previous || current.activo === false || previous.activo === false) continue;
        if (previous.fila !== current.fila || previous.columna !== current.columna) {
          unit = current;
          title = `${this.unitLabel(current)} se movió`;
          meta = `${previous.fila},${previous.columna} → ${current.fila},${current.columna}`;
          break;
        }
      }
    }
    if (!title) return;
    this.moveHistory.unshift({title, meta, unit, number: this.moveHistory.length + 1});
    this.renderHistory();
  }

  renderHistory() {
    const list = this.el("moveHistory");
    const empty = this.el("historyEmpty");
    const count = this.el("historyCount");
    list.replaceChildren();
    count.textContent = String(this.moveHistory.length);
    empty.hidden = this.moveHistory.length > 0;
    for (const entry of this.moveHistory.slice(0, 20)) {
      const item = document.createElement("li");
      item.className = "history-item";
      item.dataset.team = entry.unit?.bando || "";
      const darkPiece = entry.unit?.bando === "B";
      item.dataset.pieceTone = darkPiece ? "dark" : "light";
      const icon = document.createElement("span");
      icon.className = "history-piece";
      const image = document.createElement("img");
      image.src = this.pieceAsset(entry.unit);
      image.alt = "";
      icon.append(image);
      const copy = document.createElement("span");
      copy.className = "history-copy";
      const title = document.createElement("strong");
      title.textContent = entry.title;
      const meta = document.createElement("span");
      meta.textContent = `#${entry.number} · ${entry.meta}`;
      copy.append(title, meta);
      item.append(icon, copy);
      list.append(item);
    }
  }

  defaultActionHint(state, finished = false) {
    if (!state) return "Selecciona una ficha para comenzar.";
    if (finished) return "Partida terminada · puedes revisar el tablero o jugar de nuevo.";
    return `Turno de ${teamPhrase(state.turno)} · selecciona una ficha para ver sus movimientos.`;
  }

  renderWinnerPieces(state, result) {
    const container = this.el("winnerPieces");
    container.replaceChildren();
    container.setAttribute(
      "aria-label",
      result === "empate" ? "Fichas de la partida" : `Fichas de ${teamPhrase(result)}`
    );
    const winningTypes = (state.unidades || [])
      .filter(unit => unit.bando === result)
      .map(unit => canonicalPieceType(unit.tipo))
      .filter(Boolean);
    const types = [...new Set(winningTypes)];
    for (const fallback of ["knight", "rook", "bishop"]) {
      if (types.length >= 3) break;
      if (!types.includes(fallback)) types.push(fallback);
    }
    // The black victory composition should use the bishop artwork in place of
    // the generic standard token, which reads as an unfinished/placeholder
    // piece in the celebration row.
    const displayTypes = [...new Set(types.map(kind => (
      result === "B" && kind === "estandar" ? "bishop" : kind
    )))];
    for (const fallback of ["knight", "rook", "bishop"]) {
      if (displayTypes.length >= 3) break;
      if (!displayTypes.includes(fallback)) displayTypes.push(fallback);
    }
    const display = result === "empate"
      ? [["knight", "a"], ["rook", "a"], ["rook", "b"], ["knight", "b"]]
      : [[displayTypes[0], result], [displayTypes[1], result], ["queen", result], [displayTypes[2], result]];
    for (const [kind, sideOrTeam] of display) {
      // Use the same team-to-texture mapping as the board. This prevents the
      // result screen from silently swapping the winner's colors.
      const assetKey = result === "empate"
        ? `${kind}_${sideOrTeam}`
        : this.scene.assetKey(sideOrTeam, kind);
      const safeAssetKey = assetKey || `rook_${result === "B" ? "b" : "a"}`;
      const extension = kind === "estandar" ? "svg" : "png";
      const cacheBust = kind === "estandar" ? "?v=4" : "";
      const image = document.createElement("img");
      image.className = "winner-piece";
      image.src = `/assets/pieces/${safeAssetKey}.${extension}${cacheBust}`;
      image.alt = result === "empate" ? "Ficha de la partida" : `Ficha de ${teamPhrase(result)}`;
      image.addEventListener("error", () => {
        // Never leave the browser's broken-image glyph in the celebration.
        if (image.dataset.fallback === "true") {
          image.remove();
          return;
        }
        image.dataset.fallback = "true";
        const fallbackKey = result === "empate" ? "rook_a" : `rook_${result === "B" ? "b" : "a"}`;
        image.src = `/assets/pieces/${fallbackKey}.png`;
      }, {once: false});
      container.append(image);
    }
  }

  showResultScreen(state) {
    const result = state.juego?.resultado;
    if (!result) return;
    const screen = this.el("resultScreen");
    const wasHidden = screen.hidden;
    screen.hidden = false;
    screen.dataset.result = result;
    this.el("resultTitle").textContent = result === "empate" ? "Empate" : "¡Victoria!";
    this.el("resultMessage").textContent = result === "empate"
      ? `Empate: ${teamPhrase(state.turno)} se quedaron sin movimientos ni recogidas legales.`
      : `${sentenceTeamPhrase(result)} ganaron porque capturaron la reina y la llevaron a su base.`;
    this.renderWinnerPieces(state, result);
    const revision = this.lastPresentation?.revision;
    if (revision !== this.resultScreenRevision) {
      soundBank.play(result === "empate" ? "result_draw" : "result_win", .7);
      this.resultScreenRevision = revision;
    }
    if (wasHidden) this.el("resultRestart").focus();
  }

  unitLabel(unit) {
    if (!unit) return "La ficha";
    const names = {caballo: "Caballo", knight: "Caballo", torre: "Torre", rook: "Torre", alfil: "Alfil", bishop: "Alfil", estandar: "Ficha", rey: "Rey", king: "Rey"};
    return `${names[String(unit.tipo || "").toLowerCase()] || "Ficha"} de ${teamPhrase(unit.bando)}`;
  }

  showEventFeedback(events, previousState, currentState) {
    if (!Array.isArray(events) || events.length === 0) return false;
    const previousUnits = new Map((previousState?.unidades || []).map(unit => [unit.id, unit]));
    const currentUnits = new Map((currentState?.unidades || []).map(unit => [unit.id, unit]));
    const capture = events.find(event => event.tipo === "captura");
    const pickup = events.find(event => event.tipo === "recogida");
    const queenReturned = events.some(event => event.tipo === "recurso_suelto");
    if (capture) {
      const victim = previousUnits.get(capture.victima_id);
      const attacker = currentUnits.get(capture.atacante_id) || previousUnits.get(capture.atacante_id);
      this.say(queenReturned
        ? `${this.unitLabel(victim)} cayó ante ${this.unitLabel(attacker)} y la reina volvió a su punto inicial.`
        : `${this.unitLabel(victim)} cayó ante ${this.unitLabel(attacker)}.`, {
        title: queenReturned ? "Portadora capturada" : "Ficha capturada",
        tone: queenReturned ? "queen" : "capture",
        asset: queenReturned ? "/assets/pieces/queen_a.png" : this.pieceAsset(victim)
      });
    } else if (pickup) {
      const unit = currentUnits.get(pickup.unidad_id);
      this.say(`${this.unitLabel(unit)} ahora protege la reina.`, {
        title: "Reina recogida", tone: "queen", asset: "/assets/pieces/queen_a.png"
      });
    }
    return true;
  }

  hideResultScreen() {
    this.el("resultScreen").hidden = true;
    this.el("resultScreen").removeAttribute("data-result");
    this.resultScreenRevision = null;
  }

  updateState(state, source, presentation, animate = false) {
    assertStateShape(state);
    this.cancelSearch();
    this.clearSearchResult();
    this.cancelAdversarial({clearResult: true});
    this.setTargetPicking(false, {announce: false});
    const previousState = this.scene.state;
    this.stateEpoch += 1;
    this.lastPresentation = assertPresentationShape(presentation) || {
      jaques: {A: false, B: false},
      recogida_autorizada: {},
      eventos_ultimo_turno: []
    };
    this.scene.applyState(state, this.lastPresentation, animate);
    this.el("boardDimensions").textContent = `${state.mapa.filas} × ${state.mapa.columnas}`;
    if (source) this.el("source").textContent = source;
    this.updateGameSummary(state);
    this.updateGlobalStatus(state);
    const finished = state.juego?.estado === "finalizado";
    if (finished) this.showResultScreen(state);
    else this.hideResultScreen();
    this.setActionHint(this.defaultActionHint(state, finished));

    if (finished || !state.unidades.some(unit => unit.id === this.scene.selectedUnit && unit.activo !== false && unit.bando === state.turno)) {
      this.clearSelection();
    }
    this.updateKingModeFromState(state);
    this.updateSearchUnits(state);
    this.updateSearchTargetBounds(state);
    this.updateSearchControls();
    this.el("connection").hidden = true;
    if (animate) {
      this.recordTransition(this.lastPresentation.eventos_ultimo_turno, previousState, state);
      this.showEventFeedback(this.lastPresentation.eventos_ultimo_turno, previousState, state);
    }
  }

  updateKingModeFromState(state) {
    const kings = state.reyes;
    const kingList = kings ? Object.values(kings).flatMap(group => Array.isArray(group) ? group : []) : [];
    const mode = kingList.length === 0 ? "none" :
      kingList.every(king => typeof king.id === "string" && /_REY_\d+$/.test(king.id))
        ? "automatic"
        : "manual";
    this.el("kingMode").value = mode;
    this.updateKingInputs();
    const configurable = state.juego?.estado === "configuracion";
    for (const card of document.querySelectorAll("[data-king-mode]")) card.disabled = !configurable || this.mutationPending;
    this.el("configureKings").disabled = !configurable || this.mutationPending;
  }

  async initialize() {
    try {
      const data = await ApiClient.request("/api/state");
      this.updateState(data.state, data.source, data.presentation, false);
      this.renderHistory();
    } catch (error) {
      this.enterDesynchronized(error, "No se pudo cargar el estado inicial.");
    }
  }

  cancelLegalRequest() {
    this.legalRequestId += 1;
    if (this.legalController) this.legalController.abort();
    this.legalController = null;
  }

  async selectUnit(unitId) {
    if (this.mutationPending) return;
    const unit = this.scene.state?.unidades?.find(candidate => candidate.id === unitId);
    if (!unit || unit.activo === false || unit.bando !== this.scene.state.turno || this.scene.state.juego?.estado === "finalizado") {
      this.setActionHint("Esa ficha no pertenece al turno activo.");
      return;
    }
    this.scene.selectedUnit = unitId;
    this.scene.setLegalMoves([]);
    this.setActionHint("Consultando movimientos…", {
      kind: "move",
      asset: this.pieceAsset(unit)
    });
    this.scene.drawHighlights();
    await this.loadLegalMoves(unitId);
  }

  async loadLegalMoves(unitId) {
    this.cancelLegalRequest();
    const requestId = this.legalRequestId;
    const epoch = this.stateEpoch;
    const controller = new AbortController();
    this.legalController = controller;
    try {
      const data = await ApiClient.legalMoves(unitId, controller.signal);
      if (requestId !== this.legalRequestId || epoch !== this.stateEpoch || this.scene.selectedUnit !== unitId) return;
      const currentRevision = this.lastPresentation?.revision;
      const responseRevision = data.presentation?.revision;
      if (currentRevision && responseRevision && currentRevision !== responseRevision) {
        const reconciled = await this.reconcileOfficialState(
          "La partida cambió mientras se consultaban los destinos; se descartó esa respuesta."
        );
        if (reconciled) this.say("Estado actualizado; vuelve a seleccionar una unidad.");
        return;
      }
      this.scene.setLegalMoves(data.destinations);
      const collectAction = data.destinations.some(move => move.kind === "collect");
      const movementDestinations = data.destinations.filter(move => move.kind !== "collect");
      const pickupHint = collectAction
        ? " Haz clic en el marco dorado de esta ficha para recoger la reina; consume el turno."
        : "";
      const carrierHint = this.scene.state.juego?.portador_recurso === unitId
        ? " Esta ficha lleva la reina y tiene el único glow dorado."
        : "";
      const selectedUnit = this.scene.state?.unidades?.find(unit => unit.id === unitId);
      const selectedAsset = selectedUnit ? this.pieceAsset(selectedUnit) : null;
      if (!data.allowed) {
        this.setActionHint("Esa ficha no puede actuar en el turno actual.", {kind: "info", asset: selectedAsset});
      } else if (movementDestinations.length === 0 && !collectAction) {
        this.setActionHint("Esta ficha no tiene acciones legales en este turno.", {kind: "info", asset: selectedAsset});
      } else {
        const legend = collectAction
          ? "Verde = mover · rojo = capturar · dorado = recoger reina."
          : "Verde = mover · rojo = capturar.";
        this.setActionHint(`${legend}${carrierHint}${pickupHint}`, {
          kind: "move",
          asset: selectedAsset
        });
      }
    } catch (error) {
      if (error?.name !== "AbortError" && requestId === this.legalRequestId) this.reportError(error);
    } finally {
      if (this.legalController === controller) this.legalController = null;
    }
  }

  clearSelection() {
    this.cancelLegalRequest();
    this.scene.selectedUnit = null;
    this.scene.setLegalMoves([]);
    this.scene.drawHighlights();
    this.setActionHint(this.defaultActionHint(
      this.scene.state,
      this.scene.state?.juego?.estado === "finalizado"
    ));
  }

  async runRead(path, payload) {
    try {
      const data = await ApiClient.request(path, payload);
      if (data.result) {
        this.lastResult = data.result;
        this.scene.showSearchPath(data.result.path || data.result.camino || []);
      }
      this.report(data.result ?? data);
      this.say("Resultado recibido del servidor.");
      return data;
    } catch (error) {
      this.reportError(error);
      return null;
    }
  }

  async reconcileAfterLostResponse(error) {
    this.clearSelection();
    this.clearSearchResult();
    this.say("No se confirmó la respuesta; consultando el estado oficial. No se repetirá la acción.");
    const reconciled = await this.reconcileOfficialState(
      "No se pudo reconciliar el estado oficial tras la respuesta perdida."
    );
    if (reconciled) {
      this.say("Estado reconciliado. La acción no se repitió automáticamente.");
    } else {
      this.say(`${error.message} La interfaz quedó bloqueada; sincronízala antes de continuar.`);
    }
  }

  async reconcileOfficialState(failureMessage) {
    try {
      const data = await ApiClient.request("/api/state");
      this.desynchronized = false;
      this.updateState(data.state, data.source, data.presentation, false);
      return true;
    } catch (error) {
      this.enterDesynchronized(error, failureMessage);
      return false;
    }
  }

  enterDesynchronized(error, message) {
    if (this.autoPlayActive) this.stopAutoPlay({message: "Autojuego detenido: estado sin sincronizar."});
    this.desynchronized = true;
    this.cancelLegalRequest();
    this.cancelSearch();
    this.cancelAdversarial({clearResult: true});
    this.clearSearchResult();
    this.scene.selectedUnit = null;
    this.scene.setLegalMoves([]);
    this.scene.showSearchPath([]);
    this.scene.drawHighlights();
    this.el("connection").className = "connection-indicator";
    this.el("connection").textContent = "Estado sin sincronizar";
    this.el("connection").hidden = false;
    this.report({error: error?.code || "DESYNCHRONIZED", detail: error?.message || "No se pudo leer el estado oficial."});
    this.say(`${message} Usa «Sincronizar estado» para volver a consultar Python.`);
    this.setInteractive(false);
  }

  async synchronizeState() {
    if (this.mutationPending) return null;
    if (this.autoPlayActive) this.stopAutoPlay({message: "Autojuego detenido para sincronizar la partida."});
    this.cancelAdversarial({clearResult: true});
    this.mutationPending = true;
    this.setInteractive(true);
    const synchronizedState = await this.reconcileOfficialState(
      "No se pudo sincronizar el estado oficial."
    );
    this.mutationPending = false;
    this.setInteractive(false);
    return synchronizedState;
  }

  async runMutation(path, payload, expected = "result", {preserveAutoPlay = false, quiet = false} = {}) {
    if (!preserveAutoPlay && this.autoPlayActive) {
      this.stopAutoPlay({message: "Autojuego pausado por una acción manual."});
    }
    if (this.desynchronized) {
      this.say("La interfaz está desincronizada; sincroniza el estado antes de continuar.");
      return null;
    }
    if (this.mutationPending) {
      this.say("Hay una acción en curso; espera la confirmación del servidor.");
      return null;
    }
    this.cancelSearch();
    this.clearSearchResult();
    this.cancelAdversarial({clearResult: true});
    this.mutationPending = true;
    this.cancelLegalRequest();
    this.setInteractive(true);
    try {
      const data = await ApiClient.request(path, payload);
      if (path === "/api/reset" || path === "/api/scenarios") {
        this.moveHistory = [];
        this.renderHistory();
      }
      if (data.state) {
        this.updateState(data.state, data.source, data.presentation, path === "/api/move" || path === "/api/collect");
      }
      if (!quiet) this.report(data.result ?? data.state ?? data);
      return data;
    } catch (error) {
      if (error?.status === 409) {
        this.clearSelection();
        this.scene.showSearchPath([]);
        const reconciled = await this.reconcileOfficialState(
          "La acción se basó en un estado que cambió en el servidor."
        );
        if (reconciled) this.say("Estado actualizado; no se repitió la acción.");
      } else if (error?.responseLost) await this.reconcileAfterLostResponse(error);
      else this.reportError(error);
      return null;
    } finally {
      this.mutationPending = false;
      this.setInteractive(false);
    }
  }

  describeStateFeedback(data) {
    const events = data.presentation?.eventos_ultimo_turno || [];
    const result = data.state?.juego?.resultado;
    if (result) return `Partida finalizada: ${result === "empate" ? "empate" : `ganaron ${teamPhrase(result)}`}.`;
    if (events.some(event => event.tipo === "recurso_suelto")) {
      const queen = data.state?.recurso;
      const location = queen ? ` (${queen.fila}, ${queen.columna})` : "";
      return `Captura confirmada: la portadora fue capturada y la reina reapareció en su spawn original${location}. El spawn de la ficha capturada no cambió.`;
    }
    if (events.some(event => event.tipo === "captura")) return "Movimiento confirmado: captura registrada.";
    if (events.some(event => event.tipo === "reaparicion")) return "Movimiento confirmado: captura y reaparición registradas.";
    if (events.some(event => event.tipo === "recogida")) return "Recogida de la reina confirmada.";
    return "Estado confirmado por el servidor.";
  }

  async restartFromResult() {
    const data = await this.runMutation("/api/reset", {}, "state");
    if (data) this.hideResultScreen();
  }

  async move(unitId, row, column, options = {}) {
    return this.runMutation("/api/move", {
      unit_id: unitId,
      destination: {row, column},
      revision: this.lastPresentation?.revision || null
    }, "state", options);
  }

  async collectQueen(unitId = this.scene.selectedUnit, options = {}) {
    if (!unitId || !this.lastPresentation?.recogida_autorizada?.[unitId]) {
      this.setActionHint("Selecciona una ficha situada sobre la reina.");
      return null;
    }
    return this.runMutation("/api/collect", {
      unit_id: unitId,
      revision: this.lastPresentation?.revision || null
    }, "state", options);
  }

  parseManualKings(value, side) {
    const text = value.trim();
    if (!text) return [];
    return text.split(";").map((entry, index) => {
      const parts = entry.trim().split(",").map(Number);
      if (parts.length !== 2 || !parts.every(Number.isInteger) || parts.some(part => part < 0)) {
        throw new Error(`La posición manual ${side} #${index + 1} debe tener formato fila,columna.`);
      }
      return {row: parts[0], column: parts[1]};
    });
  }

  async configureKings() {
    const mode = this.el("kingMode").value;
    try {
      let payload;
      if (mode === "automatic") {
        payload = {
          mode,
          counts: {A: Number(this.el("kingCountA").value), B: Number(this.el("kingCountB").value)}
        };
      } else if (mode === "manual") {
        payload = {
          mode,
          kings: {
            A: this.parseManualKings(this.el("manualKingsA").value, "A"),
            B: this.parseManualKings(this.el("manualKingsB").value, "B")
          }
        };
      } else {
        payload = {mode: "none"};
      }
      await this.runMutation("/api/kings", payload, "state");
    } catch (error) {
      this.reportError(error);
    }
  }
}
