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
    this.updateKingInputs();
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
      if (control.id !== "syncState") control.disabled = locked;
    }
    if (!disabled && !this.desynchronized) {
      this.updateKingInputs();
      const configurable = this.scene.state?.juego?.estado === "configuracion";
      for (const card of document.querySelectorAll("[data-king-mode]")) card.disabled = !configurable;
      this.el("configureKings").disabled = !configurable;
    }
    this.updateSyncButton();
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
    this.scene.showSearchPath([]);
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
    this.desynchronized = true;
    this.cancelLegalRequest();
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
    this.mutationPending = true;
    this.setInteractive(true);
    const synchronizedState = await this.reconcileOfficialState(
      "No se pudo sincronizar el estado oficial."
    );
    this.mutationPending = false;
    this.setInteractive(false);
    return synchronizedState;
  }

  async runMutation(path, payload, expected = "result") {
    if (this.desynchronized) {
      this.say("La interfaz está desincronizada; sincroniza el estado antes de continuar.");
      return null;
    }
    if (this.mutationPending) {
      this.say("Hay una acción en curso; espera la confirmación del servidor.");
      return null;
    }
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
      this.report(data.result ?? data.state ?? data);
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

  async move(unitId, row, column) {
    return this.runMutation("/api/move", {
      unit_id: unitId,
      destination: {row, column},
      revision: this.lastPresentation?.revision || null
    }, "state");
  }

  async collectQueen(unitId = this.scene.selectedUnit) {
    if (!unitId || !this.lastPresentation?.recogida_autorizada?.[unitId]) {
      this.setActionHint("Selecciona una ficha situada sobre la reina.");
      return null;
    }
    return this.runMutation("/api/collect", {
      unit_id: unitId,
      revision: this.lastPresentation?.revision || null
    }, "state");
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
