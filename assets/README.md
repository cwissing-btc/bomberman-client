# Bomberman-Assets — 64×64 Pixel-Art

73 Sprites, komplett programmatisch erzeugt. Alles ist deterministisch:
gleicher Code → identische Pixel. Nichts wurde von Hand nachgemalt, alles
lässt sich über die Palette und die Zeichenfunktionen anpassen.

## Inhalt

```
spritesheet.png      512×640, 8 Spalten × 10 Zeilen, RGBA
atlas.json           Position jedes Frames + Animationsgruppen
preview.html         Alle Sprites, animiert, plus Spielszenen-Mockup
sprites/             Die 73 Einzel-PNGs (transparenter Hintergrund)
src/                 Der Generator (Python + Pillow)
```

`preview.html` ist eigenständig — Spritesheet ist als Data-URI eingebettet,
die Datei läuft ohne Server per Doppelklick.

## Sprite-Übersicht

| Gruppe | Frames | Namen |
|---|---|---|
| Boden | 2 | `floor_0`, `floor_1` (nahtlos kachelbar) |
| Feste Wand | 1 | `wall_solid` |
| Kiste | 1 + 4 | `crate`, `crate_break_0…3` |
| Spieler | 4 × 4 | `player_{down,up,left,right}_{0…3}` |
| Bombe | 4 | `bomb_0…3` (Zündschnur brennt sichtbar ab) |
| Explosion | 7 × 5 | `expl_{center,arm_h,arm_v,tip_up,tip_down,tip_left,tip_right}_{0…4}` |
| Power-ups | 5 × 2 | `item_{bomb_up,fire_up,speed_up,kick,remote}_{0,1}` |

### Explosion zusammensetzen

Die Explosion ist absichtlich in Teile zerlegt, damit beliebig lange
Feuerbalken aus denselben Kacheln entstehen. Für eine Reichweite von 2
nach rechts:

```
expl_center | expl_arm_h | expl_tip_right
```

`expl_center` enthält beide Balken in voller Stärke plus einen dickeren
Feuerball — dadurch gibt es an der Kreuzung keine Einschnürung. `expl_arm_h`
ist so gewellt, dass sich mehrere Kacheln nebeneinander nahtlos fügen.
Alle Teile eines Bildes müssen denselben Frame-Index benutzen.

## Atlas

```json
{
  "meta":   { "tileSize": 64, "size": {"w":512,"h":640}, "count": 73 },
  "frames": { "player_down_0": {"x":0,"y":128,"w":64,"h":64}, ... },
  "animations": {
    "player_walk_down": { "frames":["player_down_0", ...], "fps":10, "loop":true }
  }
}
```

22 Animationsgruppen mit empfohlener Framerate. Der Laufzyklus ist
`0 → 1 → 2 → 3` (Frame 0 und 2 sind Standposen, 1 und 3 die Durchgangsposen
mit angehobenem Bein) — bei 10 fps wirkt das Tempo passend zu einer
Bewegung von etwa 3 Tiles pro Sekunde.

## Ändern und neu erzeugen

```bash
cd src
pip install pillow
python3 generate.py ../          # überschreibt Sheet, Atlas, Vorschau, sprites/
```

Farben liegen zentral in `src/pixelart.py` im Dict `P`. Ein anderer
Spieleranzug ist ein Vierzeiler (`blu_d/blu_m/blu_l/blu_xl`) — alle 16
Spieler-Frames ziehen automatisch nach. Für mehrere Spielerfarben im
Mehrspielermodus lohnt es sich, `generate.py` um eine Schleife über
Farbvarianten zu erweitern.

Aufbau des Generators:

- `pixelart.py` — Canvas mit Pixelzugriff, Formen ohne Anti-Aliasing,
  Auto-Kontur, Schattierung, Palette
- `sprites_tiles.py` — Boden, Wand, Kiste
- `sprites_player.py` — Figur, 4 Richtungen × 4 Frames
- `sprites_bomb.py` — Bombe und Explosionsteile
- `sprites_items.py` — Power-up-Kapseln und Symbole
- `generate.py` — Sprite-Liste, Sheet, Atlas, Vorschau

## Technische Hinweise

- Alle Sprites sind exakt 64×64 mit Alphakanal, Ursprung oben links.
- Kein Anti-Aliasing an den Kanten — beim Skalieren im Spiel unbedingt
  `NEAREST` verwenden (WebGL: `gl.NEAREST`, CSS: `image-rendering: pixelated`,
  Canvas: `ctx.imageSmoothingEnabled = false`).
- Die Figur steht mit den Füßen auf etwa y = 60, der Bodenschatten liegt
  darunter. Wer Sprites am Tile-Boden ausrichtet, kann sie ohne Offset
  zeichnen.
- Die Kollisionsbox der Figur ist schmaler als das Sprite: etwa
  x 18…46, y 34…60. Der Kopf ragt bewusst darüber hinaus.
- Bodenkacheln haben eine dezente Fuge an zwei Kanten, damit beim Kacheln
  ein feines Gitter entsteht und die Spielfeldstruktur erkennbar bleibt.

Die Grafiken sind eigenständig entworfen und nicht aus einem bestehenden
Spiel übernommen — sie sind frei verwendbar. "Bomberman" selbst ist eine
Marke von Konami; für eine Veröffentlichung wäre also ein eigener Titel
sinnvoll.
