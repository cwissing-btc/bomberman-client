#!/usr/bin/env python3
"""Erzeugt alle Bomberman-Assets: Einzel-PNGs, Spritesheet, Atlas, Vorschau.

Aufruf:
    python3 generate.py [zielordner]

Alles ist deterministisch -- gleicher Code, gleiche Pixel. Farben aendern:
Palette in pixelart.py anpassen und neu laufen lassen.
"""

import base64
import json
import os
import sys
from datetime import date

from PIL import Image

import sprites_tiles as T
import sprites_player as PL
import sprites_bomb as B
import sprites_items as I

TILE = 64
SHEET_COLS = 8


# ------------------------------------------------------- Sprite-Definitionen --

def build_sprites():
    """Liefert [(name, PIL.Image)] in Sheet-Reihenfolge."""
    out = []

    # Kacheln
    for v in range(2):
        out.append((f"floor_{v}", T.floor_tile(v).img))
    out.append(("wall_solid", T.wall_solid().img))
    out.append(("crate", T.crate().img))
    for f in range(4):
        out.append((f"crate_break_{f}", T.crate_break(f).img))

    # Spieler: vier Farbvarianten x vier Richtungen x vier Frames
    for v in PL.VARIANTS:
        for d in PL.DIRECTION_NAMES:
            for f in range(4):
                out.append((f"player_{v}_{d}_{f}", PL.player(v, d, f).img))

    # Bombe
    for f in range(B.BOMB_FRAMES):
        out.append((f"bomb_{f}", B.bomb(f).img))

    # Explosion
    for part, fn in B.EXPLOSION_PARTS.items():
        for f in range(B.EXPL_FRAMES):
            out.append((f"{part}_{f}", fn(f).img))

    # Power-ups
    for name in I.ITEM_NAMES:
        for f in range(I.ITEM_FRAMES):
            out.append((f"{name}_{f}", I.item(name, f).img))

    return out


def build_animations():
    anims = {}
    for v in PL.VARIANTS:
        for d in PL.DIRECTION_NAMES:
            anims[f"player_{v}_walk_{d}"] = {
                "frames": [f"player_{v}_{d}_{f}" for f in range(4)],
                "fps": 10, "loop": True,
            }
            anims[f"player_{v}_idle_{d}"] = {
                "frames": [f"player_{v}_{d}_0"], "fps": 1, "loop": True,
            }
    anims["bomb_tick"] = {
        "frames": [f"bomb_{f}" for f in range(B.BOMB_FRAMES)],
        "fps": 8, "loop": True,
    }
    anims["crate_break"] = {
        "frames": [f"crate_break_{f}" for f in range(4)],
        "fps": 12, "loop": False,
    }
    for part in B.EXPLOSION_PARTS:
        anims[part] = {
            "frames": [f"{part}_{f}" for f in range(B.EXPL_FRAMES)],
            "fps": 14, "loop": False,
        }
    for name in I.ITEM_NAMES:
        anims[f"{name}_hover"] = {
            "frames": [f"{name}_{f}" for f in range(I.ITEM_FRAMES)],
            "fps": 3, "loop": True,
        }
    return anims


# ------------------------------------------------------------------- Ausgabe --

def write_all(outdir):
    sprites = build_sprites()
    sprite_dir = os.path.join(outdir, "sprites")
    os.makedirs(sprite_dir, exist_ok=True)

    # Alte PNGs entfernen: sonst bleiben nach einer Umbenennung Leichen
    # liegen, die im Atlas nicht mehr vorkommen.
    wanted = {f"{name}.png" for name, _ in sprites}
    for old in os.listdir(sprite_dir):
        if old.endswith(".png") and old not in wanted:
            os.remove(os.path.join(sprite_dir, old))

    # Einzeldateien
    for name, img in sprites:
        img.save(os.path.join(outdir, "sprites", f"{name}.png"))

    # Spritesheet
    rows = (len(sprites) + SHEET_COLS - 1) // SHEET_COLS
    sheet = Image.new("RGBA", (SHEET_COLS * TILE, rows * TILE), (0, 0, 0, 0))
    frames = {}
    for i, (name, img) in enumerate(sprites):
        x, y = (i % SHEET_COLS) * TILE, (i // SHEET_COLS) * TILE
        sheet.alpha_composite(img, (x, y))
        frames[name] = {"x": x, "y": y, "w": TILE, "h": TILE}
    sheet_path = os.path.join(outdir, "spritesheet.png")
    sheet.save(sheet_path)

    atlas = {
        "meta": {
            "image": "spritesheet.png",
            "size": {"w": sheet.width, "h": sheet.height},
            "tileSize": TILE,
            "count": len(sprites),
            "generated": date.today().isoformat(),
            "note": "Alle Frames 64x64, Ursprung oben links, Alpha-Kanal.",
            "playerVariants": PL.VARIANTS,
        },
        "frames": frames,
        "animations": build_animations(),
    }
    with open(os.path.join(outdir, "atlas.json"), "w", encoding="utf-8") as fh:
        json.dump(atlas, fh, indent=2, ensure_ascii=False)

    write_preview(outdir, sheet_path, atlas)
    return sprites, atlas


def write_preview(outdir, sheet_path, atlas):
    with open(sheet_path, "rb") as fh:
        b64 = base64.b64encode(fh.read()).decode("ascii")
    html = PREVIEW_HTML.replace("__ATLAS__", json.dumps(atlas)) \
                       .replace("__SHEET__", b64)
    with open(os.path.join(outdir, "preview.html"), "w", encoding="utf-8") as fh:
        fh.write(html)


PREVIEW_HTML = r"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bomberman Assets</title>
<style>
  :root{
    --bg:#15161f; --panel:#1e2030; --panel2:#262940; --line:#343854;
    --ink:#e9ecf6; --muted:#9aa2bd; --accent:#5e9eee;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);
       font:15px/1.55 ui-sans-serif,system-ui,"Segoe UI",Roboto,sans-serif}
  .wrap{max-width:1100px;margin:0 auto;padding:32px 16px 80px}
  h1{font-size:26px;margin:0 0 4px}
  h2{font-size:17px;margin:38px 0 12px;color:var(--accent);
     border-bottom:1px solid var(--line);padding-bottom:6px}
  p.sub{color:var(--muted);margin:0 0 20px}
  .bar{display:flex;gap:18px;align-items:center;flex-wrap:wrap;
       background:var(--panel);border:1px solid var(--line);
       border-radius:10px;padding:12px 16px;margin-bottom:8px}
  label{font-size:13px;color:var(--muted);display:flex;gap:8px;align-items:center}
  input[type=range]{width:150px}
  .grid{display:flex;flex-wrap:wrap;gap:14px}
  .cell{background:var(--panel);border:1px solid var(--line);border-radius:10px;
        padding:10px;text-align:center}
  .spr{image-rendering:pixelated;background-repeat:no-repeat;margin:0 auto}
  .cap{font-size:11px;color:var(--muted);margin-top:8px;
       font-family:ui-monospace,Menlo,Consolas,monospace;word-break:break-all}
  canvas{image-rendering:pixelated;border-radius:10px;border:1px solid var(--line);
         max-width:100%}
  .chk{background-image:
        linear-gradient(45deg,#00000022 25%,transparent 25%,transparent 75%,#00000022 75%),
        linear-gradient(45deg,#00000022 25%,transparent 25%,transparent 75%,#00000022 75%);
       background-size:16px 16px;background-position:0 0,8px 8px;
       background-color:#2b2f45}
</style>
</head>
<body>
<div class="wrap">
  <h1>Bomberman-Assets &middot; 64&times;64</h1>
  <p class="sub">Alle Sprites aus <code>spritesheet.png</code>, Positionen aus
     <code>atlas.json</code>. Nichts ist skaliert eingebettet &ndash; die Vorschau
     zoomt nur per CSS mit <code>image-rendering: pixelated</code>.</p>

  <div class="bar">
    <label>Zoom
      <input id="zoom" type="range" min="1" max="6" step="1" value="3">
      <span id="zoomv">3&times;</span>
    </label>
    <label>Tempo
      <input id="speed" type="range" min="1" max="24" step="1" value="10">
      <span id="speedv">10 fps</span>
    </label>
    <label><input id="anim" type="checkbox" checked> Animation</label>
  </div>

  <h2>Spielszene</h2>
  <canvas id="scene" width="832" height="448"></canvas>

  <h2>Animationen</h2>
  <div class="grid" id="anims"></div>

  <h2>Alle Einzelframes</h2>
  <div class="grid" id="all"></div>
</div>

<script>
const ATLAS = __ATLAS__;
const SHEET = "data:image/png;base64,__SHEET__";
const T = ATLAS.meta.tileSize;

let zoom = 3, fps = 10, playing = true, tick = 0;

function sprEl(name, z){
  const d = document.createElement('div');
  const f = ATLAS.frames[name];
  d.className = 'spr chk';
  d.style.width = (T*z)+'px'; d.style.height = (T*z)+'px';
  d.style.backgroundImage = `url(${SHEET})`;
  d.style.backgroundSize = (ATLAS.meta.size.w*z)+'px '+(ATLAS.meta.size.h*z)+'px';
  d.style.backgroundPosition = `-${f.x*z}px -${f.y*z}px`;
  d.dataset.name = name;
  return d;
}

// --- Animationsgalerie -------------------------------------------------
const animCells = [];
const animsBox = document.getElementById('anims');
for (const [key, a] of Object.entries(ATLAS.animations)){
  if (a.frames.length < 2) continue;
  const cell = document.createElement('div');
  cell.className = 'cell';
  const s = sprEl(a.frames[0], zoom);
  cell.appendChild(s);
  const cap = document.createElement('div');
  cap.className = 'cap'; cap.textContent = key+' ('+a.frames.length+')';
  cell.appendChild(cap);
  animsBox.appendChild(cell);
  animCells.push({el:s, frames:a.frames});
}

// --- Alle Frames -------------------------------------------------------
const allBox = document.getElementById('all');
const allCells = [];
for (const name of Object.keys(ATLAS.frames)){
  const cell = document.createElement('div');
  cell.className = 'cell';
  const s = sprEl(name, 2);
  cell.appendChild(s);
  const cap = document.createElement('div');
  cap.className = 'cap'; cap.textContent = name;
  cell.appendChild(cap);
  allBox.appendChild(cell);
  allCells.push(s);
}

function setFrame(el, name, z){
  const f = ATLAS.frames[name];
  el.style.backgroundPosition = `-${f.x*z}px -${f.y*z}px`;
}
function applyZoom(){
  for (const c of animCells){
    c.el.style.width = (T*zoom)+'px'; c.el.style.height = (T*zoom)+'px';
    c.el.style.backgroundSize = (ATLAS.meta.size.w*zoom)+'px '+(ATLAS.meta.size.h*zoom)+'px';
    setFrame(c.el, c.el.dataset.name, zoom);
  }
}

// --- Spielszene auf Canvas --------------------------------------------
const cv = document.getElementById('scene');
const ctx = cv.getContext('2d');
ctx.imageSmoothingEnabled = false;
const sheetImg = new Image();
sheetImg.src = SHEET;

const COLS = 13, ROWS = 7;
// 0 Boden, 1 Wand, 2 Kiste
const MAP = [];
for (let y=0;y<ROWS;y++){
  const row=[];
  for (let x=0;x<COLS;x++){
    if (x%2===1 && y%2===1) row.push(1);
    else if ((x+y*3)%5===0 && !(x<2&&y<2)) row.push(2);
    else row.push(0);
  }
  MAP.push(row);
}

function draw(name, gx, gy, sc){
  const f = ATLAS.frames[name];
  ctx.drawImage(sheetImg, f.x, f.y, T, T, gx, gy, T*sc, T*sc);
}

function renderScene(){
  if (!sheetImg.complete) return;
  const sc = 1;
  ctx.clearRect(0,0,cv.width,cv.height);
  for (let y=0;y<ROWS;y++) for (let x=0;x<COLS;x++)
    draw('floor_'+((x+y)%2), x*T, y*T, sc);
  for (let y=0;y<ROWS;y++) for (let x=0;x<COLS;x++){
    if (MAP[y][x]===1) draw('wall_solid', x*T, y*T, sc);
    if (MAP[y][x]===2) draw('crate', x*T, y*T, sc);
  }
  // Explosionskreuz aus Einzelteilen zusammengesetzt
  const ef = tick % 5;
  draw('expl_center_'+ef, 8*T, 3*T, sc);
  draw('expl_arm_h_'+ef,  7*T, 3*T, sc);
  draw('expl_tip_left_'+ef, 6*T, 3*T, sc);
  draw('expl_arm_v_'+ef,  8*T, 2*T, sc);
  draw('expl_tip_up_'+ef, 8*T, 1*T, sc);

  draw('bomb_'+(tick%4), 2*T, 4*T, sc);
  draw('item_fire_up_'+(tick%2), 4*T, 2*T, sc);
  draw('item_speed_up_'+(tick%2), 10*T, 5*T, sc);
  draw('player_blue_right_'+(tick%4), 3*T, 2*T, sc);
  draw('player_red_down_'+(tick%4), 0*T, 0*T, sc);
  draw('player_yellow_up_'+(tick%4), 11*T, 1*T, sc);
  draw('player_purple_left_'+(tick%4), 10*T, 3*T, sc);
  draw('crate_break_'+Math.min(3, tick%6), 5*T, 5*T, sc);
}
sheetImg.onload = renderScene;

// --- Takt --------------------------------------------------------------
let last = 0;
function loop(ts){
  if (playing && ts-last > 1000/fps){
    last = ts; tick++;
    for (const c of animCells) setFrame(c.el, c.frames[tick % c.frames.length], zoom);
    for (const c of animCells) c.el.dataset.name = c.frames[tick % c.frames.length];
    renderScene();
  }
  requestAnimationFrame(loop);
}
requestAnimationFrame(loop);

document.getElementById('zoom').oninput = e => {
  zoom = +e.target.value; document.getElementById('zoomv').textContent = zoom+'×';
  applyZoom();
};
document.getElementById('speed').oninput = e => {
  fps = +e.target.value; document.getElementById('speedv').textContent = fps+' fps';
};
document.getElementById('anim').onchange = e => { playing = e.target.checked; };
applyZoom();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "out"
    os.makedirs(target, exist_ok=True)
    sprites, atlas = write_all(target)
    print(f"{len(sprites)} Sprites -> {target}")
    print(f"Sheet: {atlas['meta']['size']['w']}x{atlas['meta']['size']['h']}")
    print(f"Animationen: {len(atlas['animations'])}")
