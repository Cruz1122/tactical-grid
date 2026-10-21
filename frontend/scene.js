"use strict";

const PIECE_KINDS = ["king", "queen", "rook", "bishop", "knight", "estandar"];
const PIECE_TEXTURE_ALIASES = {
  king: "king", rey: "king",
  queen: "queen", reina: "queen",
  rook: "rook", torre: "rook",
  bishop: "bishop", alfil: "bishop",
  knight: "knight", caballo: "knight",
  estandar: "estandar", estándar: "estandar", standard: "estandar", ficha: "estandar", unidad_estandar: "estandar"
};
const PIECE_SOUND_TYPES = {
  king: "king", rey: "king",
  queen: "queen", reina: "queen",
  rook: "rook", torre: "rook",
  bishop: "bishop", alfil: "bishop",
  knight: "knight", caballo: "knight",
  estandar: "rook"
};
const KNOWN_TERRAIN_STYLES = {
  camino: {fill: 0xf8f6f2, accent: 0xd9d2c8, pattern: 0},
  pasto: {fill: 0xe7eedb, accent: 0x8ea96f, pattern: 1},
  bosque: {fill: 0xcbd9c1, accent: 0x718d6a, pattern: 2},
  pantano: {fill: 0xc7dadd, accent: 0x668b96, pattern: 0},
  muro: {fill: 0xbb986a, accent: 0x987346, pattern: 3}
};
const TERRAIN_PALETTE = [
  [0xe5e0d8, 0x9b8e80], [0xe2ead7, 0x7d986b], [0xdbe7e8, 0x648992],
  [0xeee1cf, 0xb18155], [0xe1dff0, 0x8379a5], [0xe9e5c9, 0xa48d53]
];

function canonicalPieceType(value) {
  const normalized = String(value || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[\s-]+/g, "_");
  return PIECE_TEXTURE_ALIASES[normalized] || null;
}

function soundType(value) {
  return PIECE_SOUND_TYPES[String(value || "").toLowerCase()] || null;
}

class TacticalGridScene extends Phaser.Scene {
  constructor() {
    super("TacticalGrid");
    this.rows = 20;
    this.cols = 20;
    this.boardX = 70;
    this.boardY = 70;
    this.cell = 41;
    this.boardW = 820;
    this.boardH = 820;
    this.state = null;
    this.presentation = null;
    this.pieceSprites = new Map();
    this.kingSprites = new Map();
    this.carrierGlows = new Map();
    this.carrierQueenSprites = new Map();
    this.selectedUnit = null;
    this.legalMoves = [];
    this.userSetTarget = false;
    this.path = [];
    this.adversarialAction = null;
    this.busy = false;
    this.boardSignature = null;
    this.terrainStyles = {};
    this.terrainLabels = [];
    this.moveCostLabels = [];
    this.reducedMotion = Boolean(window.matchMedia?.("(prefers-reduced-motion: reduce)").matches);
  }

  preload() {
    for (const kind of PIECE_KINDS) {
      for (const team of ["a", "b"]) {
        const key = `${kind}_${team}`;
        const extension = kind === "estandar" ? "svg" : "png";
        const cacheBust = kind === "estandar" ? "?v=4" : "";
        this.load.image(key, `/assets/pieces/${key}.${extension}${cacheBust}`);
      }
    }
  }

  create() {
    this.cameras.main.setBackgroundColor("#f2efe9");
    this.baseLayer = this.add.graphics().setDepth(0);
    this.stateLayer = this.add.graphics().setDepth(1);
    this.indicatorLayer = this.add.graphics().setDepth(2);
    this.pathLayer = this.add.graphics().setDepth(3);
    this.adversarialLayer = this.add.graphics().setDepth(4.8);
    this.actionLayer = this.add.graphics().setDepth(7);
    this.input.on("pointerdown", pointer => this.selectCell(pointer));
    this.ui = new TacticalGridUI(this);
    this.ui.initialize();
  }

  setBusy(value) {
    this.busy = Boolean(value);
    this.drawHighlights();
  }

  assetKey(team, pieceType) {
    const kind = canonicalPieceType(pieceType);
    if (!kind) return null;
    return `${kind}_${team === "B" ? "b" : "a"}`;
  }

  center(row, column) {
    return {
      x: this.boardX + (column + .5) * this.cell,
      y: this.boardY + (row + .5) * this.cell
    };
  }

  queenCornerPosition(point) {
    return {
      x: point.x + this.cell * .23,
      y: point.y - this.cell * .23
    };
  }

  coordinate(value) {
    if (Array.isArray(value) && value.length === 2) return {fila: value[0], columna: value[1]};
    if (value && typeof value === "object") {
      const fila = value.fila ?? value.row;
      const columna = value.columna ?? value.column;
      if (Number.isInteger(fila) && Number.isInteger(columna)) return {fila, columna};
    }
    return null;
  }

  layout() {
    const margin = 70;
    this.cell = Math.min((960 - 2 * margin) / Math.max(1, this.cols), (960 - 2 * margin) / Math.max(1, this.rows));
    this.boardW = this.cell * this.cols;
    this.boardH = this.cell * this.rows;
    this.boardX = (960 - this.boardW) / 2;
    this.boardY = (960 - this.boardH) / 2;
  }

  stateBoardSignature(state) {
    return JSON.stringify({
      mapa: state.mapa,
      tipos_terreno: state.tipos_terreno,
      terreno: state.terreno,
      bases: state.bases,
      recurso: state.recurso,
      portadorRecurso: state.juego?.portador_recurso ?? null
    });
  }

  applyState(state, presentation, animate = false) {
    this.clearAdversarialAction();
    if (!state?.mapa || !Array.isArray(state.terreno)) {
      this.ui.reportError(new Error("El servidor no devolvió un escenario con mapa y terreno."));
      return;
    }
    const previous = this.state;
    const previousPresentation = this.presentation;
    const oldUnits = new Map((previous?.unidades || []).map(unit => [unit.id, unit]));
    const boardSignature = this.stateBoardSignature(state);
    const resized = !previous || previous.mapa.filas !== state.mapa.filas || previous.mapa.columnas !== state.mapa.columnas;
    this.state = state;
    this.presentation = presentation || null;
    this.rows = state.mapa.filas;
    this.cols = state.mapa.columnas;
    this.layout();
    if (resized) this.clearPieces();
    if (this.boardSignature !== boardSignature) {
      this.boardSignature = boardSignature;
      this.terrainStyles = this.buildTerrainStyles();
      this.drawBoard();
    }
    this.drawState();
    this.renderKings();
    this.renderUnits(oldUnits, animate && !resized);
    this.renderQueen();
    this.drawHighlights();
    if (animate && previous) this.playPresentation(presentation, previous, previousPresentation);
  }

  clearPieces() {
    for (const group of [this.pieceSprites, this.kingSprites, this.carrierGlows, this.carrierQueenSprites]) {
      for (const sprite of group.values()) {
        this.tweens.killTweensOf(sprite);
        sprite.destroy();
      }
      group.clear();
    }
    if (this.queenSprite) {
      this.tweens.killTweensOf(this.queenSprite);
      this.queenSprite.destroy();
      this.queenSprite = null;
    }
  }

  hash(value) {
    let result = 2166136261;
    for (const character of String(value)) {
      result ^= character.charCodeAt(0);
      result = Math.imul(result, 16777619);
    }
    return result >>> 0;
  }

  buildTerrainStyles() {
    const catalog = this.state?.tipos_terreno || {};
    const ids = Object.keys(catalog).sort();
    const styles = {};
    ids.forEach((terrainId, index) => {
      const definition = catalog[terrainId] || {};
      if (KNOWN_TERRAIN_STYLES[terrainId]) {
        styles[terrainId] = {...KNOWN_TERRAIN_STYLES[terrainId], walkable: definition.transitable !== false};
        return;
      }
      const palette = TERRAIN_PALETTE[(this.hash(terrainId) + index) % TERRAIN_PALETTE.length];
      styles[terrainId] = {
        fill: palette[0], accent: palette[1], pattern: this.hash(terrainId) % 3,
        walkable: definition.transitable !== false
      };
    });
    return styles;
  }

  drawTerrainTexture(graphics, row, column, style, terrainId, x, y) {
    const seed = this.hash(`${terrainId}:${row}:${column}`);
    const accent = style.accent;
    if (!style.walkable) {
      graphics.lineStyle(1, accent, .42);
      graphics.lineBetween(x + 3, y + this.cell - 3, x + this.cell - 3, y + 3);
      if ((seed & 1) === 1) graphics.lineBetween(x + 3, y + 3, x + this.cell - 3, y + this.cell - 3);
      return;
    }
    graphics.fillStyle(accent, .12);
    if (style.pattern === 0) {
      for (let offset = 7 + (seed % 7); offset < this.cell; offset += 14) {
        graphics.fillCircle(x + offset, y + 8 + ((seed >> 4) % 9), Math.max(1, this.cell * .025));
      }
    } else if (style.pattern === 1) {
      graphics.lineStyle(Math.max(1, this.cell * .02), accent, .2);
      graphics.lineBetween(x + 5, y + this.cell - 5, x + this.cell - 5, y + 5);
    } else {
      graphics.lineStyle(Math.max(1, this.cell * .02), accent, .18);
      graphics.lineBetween(x + 4, y + this.cell * .35, x + this.cell * .35, y + 4);
      graphics.lineBetween(x + this.cell * .58, y + this.cell - 4, x + this.cell - 4, y + this.cell * .58);
    }
  }

  clearTerrainLabels() {
    for (const label of this.terrainLabels) label.destroy();
    this.terrainLabels = [];
  }

  terrainLabelName(terrainId) {
    const knownNames = {
      camino: "CAMINO",
      pasto: "PASTO",
      bosque: "BOSQUE",
      pantano: "PANTANO",
      muro: "MURO"
    };
    if (knownNames[terrainId]) return knownNames[terrainId];
    return String(terrainId || "TERRENO")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[_-]+/g, " ")
      .toUpperCase();
  }

  terrainLabelCost(definition) {
    const cost = definition?.costo;
    if (!Number.isFinite(cost)) return "—";
    return Number.isInteger(cost) ? String(cost) : String(Number(cost.toFixed(1)));
  }

  drawTerrainLabels() {
    this.clearTerrainLabels();
    const catalog = this.state?.tipos_terreno || {};
    const fontSize = Math.max(7, Math.min(12, this.cell * .23));
    for (let row = 0; row < this.rows; row++) {
      for (let column = 0; column < this.cols; column++) {
        const terrainId = this.state.terreno[row]?.[column];
        // Camino is the neutral floor; labeling every one of those cells would
        // bury the board under repeated metadata. Special terrain keeps its
        // identity and cost visible directly on the tile.
        if (!terrainId || terrainId === "camino") continue;
        const definition = catalog[terrainId] || {};
        const label = definition.transitable === false
          ? this.terrainLabelName(terrainId)
          : `${this.terrainLabelName(terrainId)}\n⚖ ${this.terrainLabelCost(definition)}`;
        const text = this.add.text(
          this.boardX + (column + .5) * this.cell,
          this.boardY + (row + .5) * this.cell,
          label,
          {
            fontFamily: "Space Grotesk, system-ui, sans-serif",
            fontSize: `${fontSize}px`,
            fontStyle: "bold",
            color: definition.transitable === false ? "#5b3029" : "#173f45",
            align: "center",
            lineSpacing: -1,
            stroke: "#ffffff",
            strokeThickness: Math.max(1, Math.round(this.cell * .04)),
            shadow: {offsetX: 0, offsetY: 1, color: "#ffffff", blur: 2, stroke: true, fill: true}
          }
        );
        text.setOrigin(.5).setAngle(-22).setDepth(1.5).setAlpha(.98);
        this.terrainLabels.push(text);
      }
    }
  }

  drawBoard() {
    const graphics = this.baseLayer;
    graphics.clear();
    this.drawTerrainLabels();
    const {boardX: bx, boardY: by, cell} = this;
    graphics.fillStyle(0xffffff, 1);
    graphics.fillRoundedRect(bx - 8, by - 8, this.boardW + 16, this.boardH + 16, 4);
    graphics.lineStyle(1, 0xbbb4aa, .85);
    graphics.strokeRoundedRect(bx - 8, by - 8, this.boardW + 16, this.boardH + 16, 4);
    const queen = this.state.juego?.portador_recurso == null ? this.coordinate(this.state.recurso) : null;
    for (let row = 0; row < this.rows; row++) {
      for (let column = 0; column < this.cols; column++) {
        const terrainId = this.state.terreno[row]?.[column];
        const style = this.terrainStyles[terrainId] || KNOWN_TERRAIN_STYLES.camino;
        const isQueen = queen && queen.fila === row && queen.columna === column;
        const x = bx + column * cell;
        const y = by + row * cell;
        const fill = isQueen
          ? 0xd5b15a
          : ((row + column) % 2 === 0 ? style.fill : this.shade(style.fill, 1.04));
        graphics.fillStyle(fill, 1);
        graphics.fillRect(x, y, cell, cell);
        if (!isQueen) this.drawTerrainTexture(graphics, row, column, style, terrainId, x, y);
        if (!style.walkable || isQueen) {
          graphics.lineStyle(1.2, isQueen ? 0xb58e2e : style.accent, .7);
          graphics.strokeRect(x + 1, y + 1, Math.max(0, cell - 2), Math.max(0, cell - 2));
        }
      }
    }
    graphics.lineStyle(1, 0xa9a399, .2);
    for (let index = 0; index <= this.cols; index++) {
      const x = bx + index * cell;
      graphics.lineBetween(x, by, x, by + this.boardH);
    }
    for (let index = 0; index <= this.rows; index++) {
      const y = by + index * cell;
      graphics.lineBetween(bx, y, bx + this.boardW, y);
    }
    for (const team of ["A", "B"]) {
      const base = this.state.bases?.[team];
      if (!base) continue;
      const x = bx + base.columna * cell;
      const y = by + base.fila * cell;
      graphics.fillStyle(team === "A" ? 0xb5d0e0 : 0xe4c5b1, .5);
      graphics.fillRect(x, y, cell, cell);
      graphics.lineStyle(1.2, team === "A" ? 0x8ba6b5 : 0xc39b83, .8);
      graphics.strokeRect(x + 1, y + 1, Math.max(0, cell - 2), Math.max(0, cell - 2));
    }
  }

  shade(color, factor) {
    const red = Math.min(255, Math.round(((color >> 16) & 255) * factor));
    const green = Math.min(255, Math.round(((color >> 8) & 255) * factor));
    const blue = Math.min(255, Math.round((color & 255) * factor));
    return (red << 16) | (green << 8) | blue;
  }

  drawState() {
    const graphics = this.stateLayer;
    graphics.clear();
    for (const team of ["A", "B"]) {
      for (const king of this.state.reyes?.[team] || []) {
        this.paintKingCell(graphics, king.fila, king.columna, this.presentation?.jaques?.[team] === true);
      }
    }
  }

  paintKingCell(graphics, row, column, checked) {
    const x = this.boardX + column * this.cell;
    const y = this.boardY + row * this.cell;
    graphics.fillStyle(checked ? 0xf2c8c5 : 0xdceaf4, 1);
    graphics.fillRect(x, y, this.cell, this.cell);
    graphics.lineStyle(1.2, checked ? 0xd69590 : 0xaac5d4, .86);
    graphics.strokeRect(x + 1, y + 1, Math.max(0, this.cell - 2), Math.max(0, this.cell - 2));
  }

  renderKings() {
    const seen = new Set();
    for (const team of ["A", "B"]) {
      for (const [index, king] of (this.state.reyes?.[team] || []).entries()) {
        const id = `${team}:${king.id || index}`;
        seen.add(id);
        const key = this.assetKey(team, "rey");
        const position = this.center(king.fila, king.columna);
        let sprite = this.kingSprites.get(id);
        if (!sprite) {
          sprite = this.add.image(position.x, position.y, key).setDepth(5);
          this.kingSprites.set(id, sprite);
        }
        sprite.setTexture(key).setDisplaySize(this.cell * .88, this.cell * .88).setPosition(position.x, position.y).setAlpha(.98);
      }
    }
    for (const [id, sprite] of this.kingSprites) {
      if (!seen.has(id)) {
        sprite.destroy();
        this.kingSprites.delete(id);
      }
    }
  }

  renderUnits(oldUnits, animate) {
    const alive = new Set();
    const groundQueen = this.state.juego?.portador_recurso == null
      ? this.coordinate(this.state.recurso)
      : null;
    for (const unit of this.state.unidades || []) {
      const id = unit.id;
      const previous = oldUnits.get(id);
      const active = unit.activo !== false && Number.isInteger(unit.fila) && Number.isInteger(unit.columna);
      if (!active) continue;
      alive.add(id);
      const position = this.center(unit.fila, unit.columna);
      const sharesQueenCell = Boolean(
        groundQueen && groundQueen.fila === unit.fila && groundQueen.columna === unit.columna
      );
      const visualPosition = sharesQueenCell
        ? {x: position.x - this.cell * .16, y: position.y + this.cell * .14}
        : position;
      const asset = this.assetKey(unit.bando, unit.tipo);
      const unknownType = !asset;
      let sprite = this.pieceSprites.get(id);
      if (sprite && Boolean(sprite.getData("unknownType")) !== unknownType) {
        this.tweens.killTweensOf(sprite);
        sprite.destroy();
        this.pieceSprites.delete(id);
        sprite = null;
      }
      if (!sprite) {
        sprite = asset
          ? this.add.image(position.x, position.y, asset).setDepth(5)
          : this.add.text(position.x, position.y, `${teamLabel(unit.bando)}:${String(unit.tipo).slice(0, 2)}`, {
            fontFamily: "system-ui", fontSize: `${Math.max(8, this.cell * .2)}px`, color: "#34434a",
            backgroundColor: "#f5ece0", padding: {x: 2, y: 2}
          }).setOrigin(.5).setDepth(5);
        sprite.setData("unknownType", unknownType);
        this.pieceSprites.set(id, sprite);
      }
      if (asset) {
        sprite.setTexture(asset)
          .setDisplaySize(this.cell * (sharesQueenCell ? .76 : .92), this.cell * (sharesQueenCell ? .76 : .92))
          .setAlpha(1);
      }
      else sprite.setFontSize(Math.max(8, this.cell * .2));
      const moved = animate && previous && Number.isInteger(previous.fila) && Number.isInteger(previous.columna) &&
        (previous.fila !== unit.fila || previous.columna !== unit.columna);
      const movementSound = soundType(unit.tipo);
      if (moved && !this.reducedMotion) {
        this.tweens.killTweensOf(sprite);
        this.tweens.add({
          targets: sprite, x: visualPosition.x, y: visualPosition.y, duration: 620, ease: "Cubic.InOut",
          onComplete: () => movementSound && soundBank.play(`move_${movementSound}`, .48)
        });
      } else {
        sprite.setPosition(visualPosition.x, visualPosition.y);
        if (moved && movementSound) soundBank.play(`move_${movementSound}`, .48);
      }

      const hasQueen = this.state.juego?.portador_recurso === id;
      let carriedQueen = this.carrierQueenSprites.get(id);
      if (hasQueen) {
        const carriedQueenPosition = this.queenCornerPosition(visualPosition);
        if (!carriedQueen) {
          carriedQueen = this.add.image(
            carriedQueenPosition.x,
            carriedQueenPosition.y,
            "queen_a"
          ).setDepth(6.35);
          this.carrierQueenSprites.set(id, carriedQueen);
        }
        carriedQueen
          .setTexture("queen_a")
          .setDisplaySize(this.cell * .36, this.cell * .36)
          .clearTint()
          .setVisible(true);
        if (moved && !this.reducedMotion) {
          this.tweens.killTweensOf(carriedQueen);
          this.tweens.add({
            targets: carriedQueen,
            x: carriedQueenPosition.x,
            y: carriedQueenPosition.y,
            duration: 620,
            ease: "Cubic.InOut"
          });
        } else {
          carriedQueen.setPosition(carriedQueenPosition.x, carriedQueenPosition.y);
        }
      } else if (carriedQueen) {
        this.tweens.killTweensOf(carriedQueen);
        carriedQueen.destroy();
        this.carrierQueenSprites.delete(id);
      }

      let glow = this.carrierGlows.get(id);
      if (hasQueen) {
        if (!glow) {
          glow = this.add.graphics().setDepth(4.4);
          this.carrierGlows.set(id, glow);
          if (!this.reducedMotion) {
            this.tweens.add({
              targets: glow,
              alpha: {from: .62, to: 1},
              duration: 720,
              ease: "Sine.InOut",
              yoyo: true,
              repeat: -1
            });
          }
        }
        const glowX = visualPosition.x - this.cell * .53;
        const glowY = visualPosition.y - this.cell * .53;
        glow.clear();
        glow.fillStyle(0xf1c34b, .22);
        glow.fillRoundedRect(glowX, glowY, this.cell * 1.06, this.cell * 1.06, this.cell * .16);
        glow.lineStyle(Math.max(2, this.cell * .06), 0xd28e1e, .98);
        glow.strokeRoundedRect(glowX, glowY, this.cell * 1.06, this.cell * 1.06, this.cell * .16);
        glow.setVisible(true);
      } else if (glow) {
        this.tweens.killTweensOf(glow);
        glow.destroy();
        this.carrierGlows.delete(id);
      }
    }
    for (const [id, sprite] of this.pieceSprites) {
      if (!alive.has(id)) {
        sprite.destroy();
        this.pieceSprites.delete(id);
        const glow = this.carrierGlows.get(id);
        if (glow) {
          this.tweens.killTweensOf(glow);
          glow.destroy();
          this.carrierGlows.delete(id);
        }
        const carriedQueen = this.carrierQueenSprites.get(id);
        if (carriedQueen) {
          this.tweens.killTweensOf(carriedQueen);
          carriedQueen.destroy();
          this.carrierQueenSprites.delete(id);
        }
      }
    }
  }

  renderQueen() {
    const position = this.coordinate(this.state.recurso);
    const available = this.state.juego?.portador_recurso == null && position;
    if (!available) {
      if (this.queenSprite) this.queenSprite.setVisible(false);
      return;
    }
    const point = this.center(position.fila, position.columna);
    const occupant = (this.state.unidades || []).find(unit =>
      unit.activo !== false && unit.fila === position.fila && unit.columna === position.columna
    );
    const overlapping = Boolean(occupant);
    const queenCorner = this.queenCornerPosition(point);
    const queenX = overlapping ? queenCorner.x : point.x;
    const queenY = overlapping ? queenCorner.y : point.y;
    const queenSize = overlapping ? this.cell * .62 : this.cell * .82;
    if (!this.queenSprite) this.queenSprite = this.add.image(queenX, queenY, "queen_a");
    this.queenSprite
      .setDepth(6.3)
      .setPosition(queenX, queenY)
      .setDisplaySize(queenSize, queenSize)
      .clearTint()
      .setVisible(true);
  }

  showSearchPath(path) {
    this.path = Array.isArray(path) ? path : [];
    this.drawHighlights();
  }

  clearAdversarialAction() {
    this.adversarialAction = null;
    this.adversarialLayer?.clear();
  }

  showAdversarialAction(option) {
    this.adversarialAction = option || null;
    if (!this.adversarialLayer) return;
    this.adversarialLayer.clear();
    if (!option) return;
    const origin = this.coordinate(option.origin);
    const destination = this.coordinate(option.destination);
    if (!origin || !destination) return;
    const originX = this.boardX + origin.columna * this.cell;
    const originY = this.boardY + origin.fila * this.cell;
    const target = this.center(destination.fila, destination.columna);
    const collect = option.kind === "collect";
    const capture = option.kind === "capture";
    const color = collect ? 0xd0a83c : capture ? 0xb9504d : 0x28766e;
    this.adversarialLayer.lineStyle(Math.max(2.5, this.cell * .08), 0x276d78, .98);
    this.adversarialLayer.strokeRoundedRect(originX + 2, originY + 2, this.cell - 4, this.cell - 4, 5);
    if (origin.fila === destination.fila && origin.columna === destination.columna) {
      this.adversarialLayer.lineStyle(Math.max(3, this.cell * .09), color, .98);
      this.adversarialLayer.strokeCircle(target.x, target.y, this.cell * .34);
      return;
    }
    this.adversarialLayer.fillStyle(color, .22);
    this.adversarialLayer.fillRoundedRect(
      this.boardX + destination.columna * this.cell + 3,
      this.boardY + destination.fila * this.cell + 3,
      this.cell - 6,
      this.cell - 6,
      5
    );
    this.adversarialLayer.lineStyle(Math.max(2.5, this.cell * .08), color, .98);
    this.adversarialLayer.strokeRoundedRect(
      this.boardX + destination.columna * this.cell + 3,
      this.boardY + destination.fila * this.cell + 3,
      this.cell - 6,
      this.cell - 6,
      5
    );
  }

  setLegalMoves(moves) {
    this.legalMoves = Array.isArray(moves) ? moves : [];
    this.drawHighlights();
  }

  clearMoveCostLabels() {
    for (const label of this.moveCostLabels) label.destroy();
    this.moveCostLabels = [];
  }

  terrainCostAt(position) {
    const terrainId = this.state?.terreno?.[position.fila]?.[position.columna];
    const cost = this.state?.tipos_terreno?.[terrainId]?.costo;
    return Number.isFinite(cost) ? cost : null;
  }

  movementCost(move) {
    const position = this.coordinate(move);
    const unit = this.state?.unidades?.find(candidate => candidate.id === this.selectedUnit);
    if (!position || !unit || !Number.isInteger(unit.fila) || !Number.isInteger(unit.columna)) return null;
    const kind = canonicalPieceType(unit.tipo);
    if (kind === "knight" || kind === "estandar") return this.terrainCostAt(position);

    const rowStep = Math.sign(position.fila - unit.fila);
    const columnStep = Math.sign(position.columna - unit.columna);
    let row = unit.fila + rowStep;
    let column = unit.columna + columnStep;
    let total = 0;
    while (true) {
      const cost = this.terrainCostAt({fila: row, columna: column});
      if (!Number.isFinite(cost)) return null;
      total += cost;
      if (row === position.fila && column === position.columna) return total;
      row += rowStep;
      column += columnStep;
    }
  }

  formatMovementCost(cost) {
    if (!Number.isFinite(cost)) return "—";
    return Number.isInteger(cost) ? String(cost) : String(Number(cost.toFixed(1)));
  }

  findLegalMove(row, column) {
    return this.legalMoves.find(move => {
      const position = this.coordinate(move);
      return position?.fila === row && position?.columna === column;
    }) || null;
  }

  drawHighlights() {
    if (!this.indicatorLayer || !this.pathLayer || !this.actionLayer) return;
    this.indicatorLayer.clear();
    this.pathLayer.clear();
    this.actionLayer.clear();
    this.clearMoveCostLabels();
    const pathCoordinates = (this.path || []).map(value => this.coordinate(value)).filter(Boolean);
    if (pathCoordinates.length) {
      this.pathLayer.lineStyle(Math.max(2, this.cell * .08), 0x6dab82, .88);
      for (let index = 1; index < pathCoordinates.length; index++) {
        const start = this.center(pathCoordinates[index - 1].fila, pathCoordinates[index - 1].columna);
        const end = this.center(pathCoordinates[index].fila, pathCoordinates[index].columna);
        this.pathLayer.lineBetween(start.x, start.y, end.x, end.y);
      }
      for (const cell of pathCoordinates) {
        const point = this.center(cell.fila, cell.columna);
        this.pathLayer.fillStyle(0x6dab82, .55);
        this.pathLayer.fillCircle(point.x, point.y, Math.max(2, this.cell * .1));
      }
    }
    if (this.selectedUnit) {
      const unit = this.state?.unidades?.find(candidate => candidate.id === this.selectedUnit);
      const carriesQueen = this.state?.juego?.portador_recurso === this.selectedUnit;
      const hasCollectAction = this.legalMoves.some(move => move.kind === "collect");
      if (unit && Number.isInteger(unit.fila) && unit.fila >= 0 && !carriesQueen && !hasCollectAction) {
        const x = this.boardX + unit.columna * this.cell;
        const y = this.boardY + unit.fila * this.cell;
        this.indicatorLayer.lineStyle(2, 0x376c84, .98);
        this.indicatorLayer.strokeRoundedRect(x + 2, y + 2, this.cell - 4, this.cell - 4, 4);
      }
    }
    if (this.busy) return;
    for (const move of this.legalMoves) {
      const position = this.coordinate(move);
      if (!position) continue;
      const point = this.center(position.fila, position.columna);
      const collect = move.kind === "collect";
      const capture = move.kind === "capture";
      if (collect) {
        this.indicatorLayer.fillStyle(0xd0a83c, .25);
        this.indicatorLayer.fillCircle(point.x, point.y, Math.max(6, this.cell * .22));
        this.indicatorLayer.lineStyle(Math.max(2, this.cell * .055), 0xb58e2e, .98);
        this.indicatorLayer.strokeRoundedRect(
          this.boardX + position.columna * this.cell + 3,
          this.boardY + position.fila * this.cell + 3,
          this.cell - 6,
          this.cell - 6,
          Math.max(4, this.cell * .12)
        );

        // Keep the pickup action visible above the queen and the selected piece.
        const cellX = this.boardX + position.columna * this.cell;
        const cellY = this.boardY + position.fila * this.cell;
        const badgeX = cellX + this.cell * .17;
        const badgeY = cellY + this.cell * .17;
        const badgeRadius = Math.max(7, this.cell * .105);
        this.actionLayer.fillStyle(0x8b6418, .98);
        this.actionLayer.fillCircle(badgeX, badgeY, badgeRadius);
        this.actionLayer.lineStyle(Math.max(1.5, this.cell * .025), 0xfff8dc, .98);
        this.actionLayer.strokeCircle(badgeX, badgeY, badgeRadius);
        this.actionLayer.lineBetween(
          badgeX,
          badgeY + this.cell * .055,
          badgeX,
          badgeY - this.cell * .045
        );
        this.actionLayer.lineBetween(
          badgeX,
          badgeY - this.cell * .045,
          badgeX - this.cell * .045,
          badgeY + this.cell * .005
        );
        this.actionLayer.lineBetween(
          badgeX,
          badgeY - this.cell * .045,
          badgeX + this.cell * .045,
          badgeY + this.cell * .005
        );
        continue;
      }
      this.indicatorLayer.lineStyle(1.5, capture ? 0x9c3939 : 0x347054, .82);
      this.indicatorLayer.strokeRect(
        this.boardX + position.columna * this.cell + 3,
        this.boardY + position.fila * this.cell + 3,
        this.cell - 6,
        this.cell - 6
      );
      const costLabel = this.add.text(point.x, point.y, this.formatMovementCost(this.movementCost(move)), {
        fontFamily: "Space Grotesk, system-ui, sans-serif",
        fontSize: `${Math.max(9, this.cell * .25)}px`,
        fontStyle: "bold",
        color: capture ? "#8f3434" : "#1d5d4d",
        stroke: "#ffffff",
        strokeThickness: Math.max(1, Math.round(this.cell * .045)),
        shadow: {offsetX: 0, offsetY: 1, color: "#ffffff", blur: 2, stroke: true, fill: true}
      });
      costLabel.setOrigin(.5).setDepth(4.2);
      this.moveCostLabels.push(costLabel);
    }
  }

  pulseCell(positionValue, color) {
    const position = this.coordinate(positionValue);
    if (!position) return;
    const point = this.center(position.fila, position.columna);
    const pulse = this.add.graphics().setDepth(4.9);
    pulse.lineStyle(Math.max(2, this.cell * .06), color, .9);
    pulse.strokeCircle(point.x, point.y, this.cell * .25);
    if (this.reducedMotion) {
      this.time.delayedCall(120, () => pulse.destroy());
      return;
    }
    this.tweens.add({
      targets: pulse, scaleX: 1.7, scaleY: 1.7, alpha: 0, duration: 380, ease: "Cubic.Out",
      onComplete: () => pulse.destroy()
    });
  }

  playPresentation(presentation, previous, previousPresentation) {
    const events = presentation?.eventos_ultimo_turno || [];
    for (const event of events) {
      if (event.tipo === "captura") {
        this.pulseCell(event.posicion, 0xc55f5a);
        const attacker = this.state.unidades.find(unit => unit.id === event.atacante_id);
        const kind = attacker && soundType(attacker.tipo);
        if (kind) soundBank.play(`capture_${kind}`, .62);
      } else if (event.tipo === "reaparicion") {
        this.pulseCell(event.posicion, 0x5b9a78);
        soundBank.play("respawn", .52);
      } else if (event.tipo === "recogida" || event.tipo === "recurso_suelto") {
        if (event.tipo === "recurso_suelto") this.pulseCell(event.posicion, 0xd0a83c);
        soundBank.play(event.tipo === "recogida" ? "pickup" : "drop", .58);
      } else if (event.tipo === "resultado") {
        const position = event.resultado === "empate"
          ? {fila: Math.floor(this.rows / 2), columna: Math.floor(this.cols / 2)}
          : this.state.bases?.[event.resultado];
        this.pulseCell(position, 0x557b8f);
      }
    }
    const beforeChecks = previousPresentation?.jaques || previous?.juego?.jaques || {};
    const afterChecks = presentation?.jaques || {};
    if (["A", "B"].some(side => afterChecks[side] === true && beforeChecks[side] !== true)) {
      soundBank.play("check_king", .55);
    }
  }

  selectCell(pointer) {
    if (!this.state || this.busy) return;
    const column = Math.floor((pointer.worldX - this.boardX) / this.cell);
    const row = Math.floor((pointer.worldY - this.boardY) / this.cell);
    if (row < 0 || column < 0 || row >= this.rows || column >= this.cols) return;
    if (this.ui.pickingTarget) {
      this.ui.setTarget(row, column);
      return;
    }
    const clicked = (this.state.unidades || []).find(unit =>
      unit.activo !== false && unit.fila === row && unit.columna === column
    );
    if (this.selectedUnit) {
      const move = this.findLegalMove(row, column);
      if (move) {
        const unitId = this.selectedUnit;
        if (move.kind === "collect") this.ui.collectQueen(unitId);
        else this.ui.move(unitId, row, column);
        return;
      }
    }
    if (clicked && clicked.bando === this.state.turno) {
      if (this.selectedUnit === clicked.id) {
        this.ui.clearSelection();
      } else {
        this.selectedUnit = clicked.id;
        this.ui.selectUnit(clicked.id);
        this.drawHighlights();
      }
      return;
    }
    if (this.selectedUnit) {
      this.ui.setActionHint("Ese destino no está entre los movimientos legales.");
      return;
    }
    this.ui.setActionHint(`Selecciona primero una ficha de ${teamPhrase(this.state.turno)}.`);
  }
}

new Phaser.Game({
  type: Phaser.AUTO,
  parent: "game",
  width: 960,
  height: 960,
  backgroundColor: "#f2efe9",
  antialias: true,
  pixelArt: false,
  resolution: Math.max(1, window.devicePixelRatio || 1),
  audio: {noAudio: true},
  loader: {imageLoadType: "HTMLImageElement"},
  banner: {hidePhaser: true},
  scene: TacticalGridScene,
  // The layout owns centering. Phaser must not add a second auto-center margin
  // on top of the CSS grid, otherwise the board drifts toward the panel.
  scale: {mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.NO_CENTER}
});
