"use strict";
const PIECE_KEYS = ["king_a", "king_b", "queen_a", "queen_b", "rook_a", "rook_b", "bishop_a", "bishop_b", "knight_a", "knight_b"];
const PIECE_TEXTURE_TYPES = {caballo:"knight", torre:"rook", alfil:"bishop", rey:"king", reina:"queen"};
const PIECE_SOUND_TYPES = {caballo:"knight", torre:"rook", alfil:"bishop", rey:"king", reina:"queen"};

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
    this.pieceSprites = new Map();
    this.kingSprites = new Map();
    this.carrierSprites = new Map();
    this.selectedUnit = null;
    this.userSetTarget = false;
    this.path = [];
  }
  preload() {
    for (const name of PIECE_KEYS) {
      this.load.image(name, `/assets/pieces/${name}.png`);
      this.load.image(`outline_${name}`, `/assets/outlines/${name}.png`);
    }
  }
  create() {
    this.cameras.main.setBackgroundColor("#f2efe9");
    this.baseLayer = this.add.graphics().setDepth(0);
    this.stateLayer = this.add.graphics().setDepth(1);
    this.indicatorLayer = this.add.graphics().setDepth(2);
    this.pathLayer = this.add.graphics().setDepth(3);
    this.input.on("pointerdown", pointer => this.selectCell(pointer));
    this.ui = new TacticalGridUI(this);
    this.ui.initialize();
  }
  assetKey(team, pieceType) {
    const kind = PIECE_TEXTURE_TYPES[String(pieceType || "").toLowerCase()];
    if (!kind) return null;
    return `${kind}_${team === "B" ? "b" : "a"}`;
  }
  center(r, c) {
    return {x:this.boardX + (c + .5) * this.cell, y:this.boardY + (r + .5) * this.cell};
  }
  coordinate(value) {
    if (Array.isArray(value) && value.length === 2) return {fila:value[0], columna:value[1]};
    if (value && typeof value === "object" && "fila" in value && "columna" in value) return value;
    return null;
  }
  layout() {
    const margin = 70;
    this.cell = Math.min((960 - 2 * margin) / this.cols, (960 - 2 * margin) / this.rows);
    this.boardW = this.cell * this.cols;
    this.boardH = this.cell * this.rows;
    this.boardX = (960 - this.boardW) / 2;
    this.boardY = (960 - this.boardH) / 2;
  }
  applyState(state, animate = false) {
    if (!state?.mapa || !Array.isArray(state.terreno)) {
      this.ui.reportError(new Error("El servidor no devolvió un escenario con mapa y terreno.")); return;
    }
    const previous = this.state;
    const oldUnits = new Map((previous?.unidades || []).map(u => [u.id, u]));
    const resized = !previous || previous.mapa.filas !== state.mapa.filas || previous.mapa.columnas !== state.mapa.columnas;
    this.state = state;
    this.rows = state.mapa.filas;
    this.cols = state.mapa.columnas;
    this.layout();
    if (resized) this.clearPieces();
    this.drawBoard();
    this.drawState();
    this.renderKings();
    this.renderUnits(oldUnits, animate && !resized);
    this.renderQueen();
    this.drawHighlights();
    const before = previous?.juego?.jaques;
    const after = state.juego?.jaques;
    if (animate && before && after && ["A", "B"].some(k => after[k] === true && before[k] !== true)) {
      soundBank.play("check_king", .55);
    }
    if (animate && previous) {
      for (const event of state.juego?.eventos_ultimo_turno || []) {
        if (event.tipo !== "captura") continue;
        const attacker = state.unidades.find(u => u.id === event.atacante_id);
        if (attacker && PIECE_SOUND_TYPES[attacker.tipo]) soundBank.play(`capture_${PIECE_SOUND_TYPES[attacker.tipo]}`, .62);
      }
    }
  }
  clearPieces() {
    for (const group of [this.pieceSprites, this.kingSprites, this.carrierSprites]) {
      for (const sprite of group.values()) sprite.destroy();
      group.clear();
    }
    if (this.queenSprite) { this.queenSprite.destroy(); this.queenSprite = null; }
  }
  drawBoard() {
    const g = this.baseLayer;
    g.clear();
    const bx = this.boardX, by = this.boardY, c = this.cell;
    g.fillStyle(0xffffff, 1);
    g.fillRoundedRect(bx - 8, by - 8, this.boardW + 16, this.boardH + 16, 4);
    g.lineStyle(1, 0xbbb4aa, .85);
    g.strokeRoundedRect(bx - 8, by - 8, this.boardW + 16, this.boardH + 16, 4);
    for (let r = 0; r < this.rows; r++) {
      for (let col = 0; col < this.cols; col++) {
        const terrainId = this.state.terreno[r]?.[col];
        const terrain = this.state.tipos_terreno?.[terrainId];
        const blocked = terrain?.transitable === false;
        const queen = this.state.juego?.portador_recurso == null && this.coordinate(this.state.recurso);
        const isQueen = queen && queen.fila === r && queen.columna === col;
        let color = ((r + col) % 2 === 0) ? 0xece9e3 : 0xf8f6f2;
        if (blocked) color = 0xbb986a;
        if (isQueen) color = 0xd5b15a;
        const x = bx + col * c, y = by + r * c;
        g.fillStyle(color, 1);
        g.fillRect(x, y, c, c);
        if (!blocked && !isQueen && terrainId === "bosque") {
          g.fillStyle(0x86997a, .12);g.fillRect(x,y,c,c);
        } else if (!blocked && !isQueen && terrainId === "pantano") {
          g.fillStyle(0x76929d, .12);g.fillRect(x,y,c,c);
        } else if (!blocked && !isQueen && terrainId === "pasto") {
          g.fillStyle(0x9aaf7b, .08);g.fillRect(x,y,c,c);
        }
        if (blocked || isQueen) {
          g.lineStyle(1.2, blocked ? 0x987346 : 0xb58e2e, .7);
          g.strokeRect(x + 1, y + 1, Math.max(0,c - 2), Math.max(0,c - 2));
        }
      }
    }
    g.lineStyle(1, 0xa9a399, .2);
    for (let i = 0; i <= this.cols; i++) {
      const x = bx + i * c;g.lineBetween(x, by, x, by + this.boardH);
    }
    for (let i = 0; i <= this.rows; i++) {
      const y = by + i * c;g.lineBetween(bx, y, bx + this.boardW, y);
    }
    for (const team of ["A", "B"]) {
      const base = this.state.bases?.[team];
      if (!base) continue;
      const x = bx + base.columna*c, y = by + base.fila*c;
      g.fillStyle(team === "A" ? 0xb5d0e0 : 0xe4c5b1, .5);
      g.fillRect(x, y, c, c);
      g.lineStyle(1.2, team === "A" ? 0x8ba6b5 : 0xc39b83, .8);
      g.strokeRect(x + 1, y + 1, Math.max(0,c-2), Math.max(0,c-2));
    }
  }
  drawState() {
    const g = this.stateLayer;
    g.clear();
    for (const team of ["A", "B"]) {
      for (const king of this.state.reyes?.[team] || []) {
        const checked = this.state.juego?.jaques?.[team] === true;
        this.paintKingCell(g, king.fila, king.columna, checked);
      }
    }
  }
  paintKingCell(g, r, col, checked) {
    const x = this.boardX + col*this.cell, y = this.boardY + r*this.cell;
    const s = this.cell;
    g.fillStyle(checked ? 0xf2c8c5 : 0xdceaf4, 1);g.fillRect(x,y,s,s);
    g.lineStyle(1.2, checked ? 0xd69590 : 0xaac5d4, .86);
    g.strokeRect(x+1,y+1,Math.max(0,s-2),Math.max(0,s-2));
  }
  renderKings() {
    const seen = new Set();
    for (const team of ["A", "B"]) {
      for (const king of this.state.reyes?.[team] || []) {
        const id = `${team}:${king.id}`;seen.add(id);
        const key = this.assetKey(team, "rey"), pos = this.center(king.fila, king.columna);
        let sprite = this.kingSprites.get(id);
        if (!sprite) { sprite = this.add.image(pos.x,pos.y,key).setDepth(5);this.kingSprites.set(id,sprite); }
        sprite.setTexture(key).setDisplaySize(this.cell*.88,this.cell*.88).setPosition(pos.x,pos.y).setAlpha(.98);
      }
    }
    for (const [id,sprite] of this.kingSprites) if (!seen.has(id)) {sprite.destroy();this.kingSprites.delete(id);}
  }
  renderUnits(oldUnits, animate) {
    const alive = new Set();
    for (const unit of this.state.unidades || []) {
      const id = unit.id, previous = oldUnits.get(id);
      const active = unit.activo !== false && Number.isInteger(unit.fila) && Number.isInteger(unit.columna);
      const asset = this.assetKey(unit.bando, unit.tipo);
      if (!active) continue;
      alive.add(id);
      const point = this.center(unit.fila,unit.columna);
      let sprite = this.pieceSprites.get(id);
      const unknownType = !asset;
      if (sprite && Boolean(sprite.getData("unknownType")) !== unknownType) {
        sprite.destroy(); this.pieceSprites.delete(id); sprite = null;
      }
      if (!sprite) {
        sprite = asset ? this.add.image(point.x,point.y,asset).setDepth(5) :
          this.add.text(point.x,point.y,`${unit.bando}:${String(unit.tipo).slice(0,2)}`,
            {fontFamily:"system-ui",fontSize:`${Math.max(8,this.cell*.2)}px`,color:"#34434a",
             backgroundColor: "#f5ece0",padding:{x:2,y:2}}).setOrigin(.5).setDepth(5);
        sprite.setData("unknownType",unknownType);
        this.pieceSprites.set(id,sprite);
      }
      if (asset) sprite.setTexture(asset).setDisplaySize(this.cell*.92,this.cell*.92).setAlpha(1);
      else sprite.setFontSize(Math.max(8,this.cell*.2));
      const moved = animate && previous && previous.fila != null && previous.columna != null &&
        (previous.fila !== unit.fila || previous.columna !== unit.columna);
      if (moved) {
        this.tweens.killTweensOf(sprite);
        this.tweens.add({targets:sprite,x:point.x,y:point.y,duration:620,ease:"Cubic.InOut",
          onComplete:()=>soundBank.play(`move_${PIECE_SOUND_TYPES[unit.tipo]}`, .48)});
      } else { sprite.setPosition(point.x,point.y); }
      const hasQueen = this.state.juego?.portador_recurso === id;
      let outline = this.carrierSprites.get(id);
      if (hasQueen) {
        if (!outline) {
          outline = asset ? this.add.image(sprite.x,sprite.y,`outline_${asset}`).setDepth(4.7) :
            this.add.rectangle(sprite.x,sprite.y,this.cell*.95,this.cell*.95,0xd5b15a,.35).setDepth(4.7);
          this.carrierSprites.set(id,outline);
        }
        if (asset) outline.setDisplaySize(this.cell*1.02,this.cell*1.02);
        else outline.setSize(this.cell*.95,this.cell*.95);
        if (moved) {
          this.tweens.killTweensOf(outline);
          this.tweens.add({targets:outline,x:point.x,y:point.y,duration:620,ease:"Cubic.InOut"});
        } else { outline.setPosition(point.x,point.y); }
      } else if (outline) { outline.destroy();this.carrierSprites.delete(id); }
      if (hasQueen && previous && oldUnits.size && this.previousCarrier !== id)
        soundBank.play(`capture_${PIECE_SOUND_TYPES[unit.tipo]}`, .62);
    }
    this.previousCarrier = this.state.juego?.portador_recurso ?? null;
    for (const [id,sprite] of this.pieceSprites) if (!alive.has(id)) {
      sprite.destroy();this.pieceSprites.delete(id);
      const outline = this.carrierSprites.get(id);
      if (outline) {outline.destroy();this.carrierSprites.delete(id);}
    }
  }
  renderQueen() {
    const position = this.coordinate(this.state.recurso);
    const available = this.state.juego?.portador_recurso == null && position;
    if (!available) { if (this.queenSprite) this.queenSprite.setVisible(false);return; }
    const point = this.center(position.fila, position.columna);
    if (!this.queenSprite) this.queenSprite = this.add.image(point.x,point.y,"queen_a").setDepth(5);
    this.queenSprite.setPosition(point.x,point.y).setDisplaySize(this.cell*.92,this.cell*.92).setVisible(true);
  }
  showSearchPath(path) {
    this.path = Array.isArray(path) ? path : [];
    this.drawHighlights();
  }
  drawHighlights() {
    if (!this.indicatorLayer || !this.pathLayer) return;
    this.indicatorLayer.clear();
    this.pathLayer.clear();
    const coords = (this.path || []).map(v=>this.coordinate(v)).filter(Boolean);
    if (coords.length) {
      this.pathLayer.lineStyle(Math.max(2,this.cell*.08),0x6dab82,.88);
      for (let i=1;i<coords.length;i++) {
        const a=this.center(coords[i-1].fila,coords[i-1].columna);
        const b=this.center(coords[i].fila,coords[i].columna);
        this.pathLayer.lineBetween(a.x,a.y,b.x,b.y);
      }
      for (const cell of coords) {
        const p=this.center(cell.fila,cell.columna);
        this.pathLayer.fillStyle(0x6dab82,.55);this.pathLayer.fillCircle(p.x,p.y,Math.max(2,this.cell*.10));
      }
    }
    if (this.selectedUnit) {
      const unit = this.state.unidades.find(u => u.id === this.selectedUnit);
      if (unit && Number.isInteger(unit.fila)) {
        const x=this.boardX+unit.columna*this.cell,y=this.boardY+unit.fila*this.cell;
        this.indicatorLayer.lineStyle(2,0x6dab82,.95);
        this.indicatorLayer.strokeRoundedRect(x+2,y+2,this.cell-4,this.cell-4,4);
      }
    }
  }
  selectCell(pointer) {
    if (!this.state) return;
    const col=Math.floor((pointer.worldX-this.boardX)/this.cell);
    const row=Math.floor((pointer.worldY-this.boardY)/this.cell);
    if (row<0 || col<0 || row>=this.rows || col>=this.cols) return;
    if (this.ui.pickingTarget) { this.ui.setTarget(row,col);return; }
    const clicked = (this.state.unidades||[]).find(u => u.activo !== false && u.fila===row && u.columna===col);
    if (clicked && clicked.bando === this.state.turno) {
      this.selectedUnit = this.selectedUnit === clicked.id ? null : clicked.id;
      this.ui.el("unit").value = clicked.id;
      this.ui.say(this.selectedUnit ? `Seleccionada ${clicked.id}. Clic en destino para solicitar acción.` : "Selección cancelada.");
      this.drawHighlights();
      return;
    }
    if (this.selectedUnit) {
      const id = this.selectedUnit;
      this.selectedUnit = null;
      this.drawHighlights();
      this.ui.move(id,row,col);
    } else {
      this.ui.say(`Celda (${row}, ${col}). Selecciona primero una unidad del turno ${this.state.turno}.`);
    }
  }
}

new Phaser.Game({
  type:Phaser.AUTO, parent:"game", width:960, height:960,
  backgroundColor:"#f2efe9", antialias:true, pixelArt:false,
  resolution:Math.max(1,window.devicePixelRatio||1), audio:{noAudio:true},
  loader:{imageLoadType:"HTMLImageElement"}, banner:{hidePhaser:true},
  scene:TacticalGridScene,
  scale:{mode:Phaser.Scale.FIT,autoCenter:Phaser.Scale.CENTER_BOTH}
});
