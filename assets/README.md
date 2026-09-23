# Bomberman-Assets — 64×64 Pixel-Art

121 Sprites, komplett programmatisch erzeugt. Alles ist deterministisch:
gleicher Code → identische Pixel. Nichts wurde von Hand nachgemalt, alles
lässt sich über die Palette und die Zeichenfunktionen anpassen.

## Inhalt

```
spritesheet.png      512×1024, 8 Spalten × 16 Zeilen, RGBA
atlas.json           Position jedes Frames + Animationsgruppen
preview.html         Alle Sprites, animiert, plus Spielszenen-Mockup
sprites/             Die 121 Einzel-PNGs (transparenter Hintergrund)
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
| Spieler | 4 × 4 × 4 | `player_{blue,red,yellow,purple}_{down,up,left,right}_{0…3}` |
| Bombe | 4 | `bomb_0…3` (Zündschnur brennt sichtbar ab) |
| Explosion | 7 × 5 | `expl_{center,arm_h,arm_v,tip_up,tip_down,tip_left,tip_right}_{0…4}` |
| Power-ups | 5 × 2 | `item_{bomb_up,fire_up,speed_up,kick,remote}_{0,1}` |

### Spielerfarben

Vier Varianten: `blue`, `red`, `yellow`, `purple`. Jede hat eine eigene
Anzugrampe und eine kontrastierende Akzentfarbe an Schuhen und
Antennenspitze — also genau dort, wo bei 64px die Silhouette endet und das
Auge zuerst hinschaut.

Grün fehlt bewusst: der Boden ist grün, eine grüne Figur würde darin
untergehen. Die `grn_*`-Rampe liegt aber in der Palette bereit, falls du sie
trotzdem als fünfte Variante willst — ein Eintrag in `SUITS`.

Auf dem Helm sitzt ein weißes Band über die volle Helmbreite mit dem
Schriftzug **BTC** in einem 5×7-Bitmap-Font (`FONT` in
`src/sprites_player.py`). Versalien, weil Kleinbuchstaben bei 7px Höhe ihre
Punzen und Unterlängen verlieren — bei „btc" wären b und c kaum noch zu
unterscheiden.

Zwei Details, die beim Nachbauen leicht untergehen:

- Die Linksansicht entsteht durch Spiegeln der Rechtsansicht. Der Schriftzug
  wird deshalb **nach** dem Spiegeln gezeichnet, sonst stünde dort „CTB" in
  Spiegelschrift.
- Das Band wandert mit dem Kopfwippen des Laufzyklus mit. Bei festen
  Bildzeilen würde der Helm im Lauf unter dem Band durchrutschen.

Anderer Schriftzug: `_band_and_text(..., label="XYZ")` und die passenden
Glyphen in `FONT` ergänzen. Mehr als vier Zeichen werden bei 18px nutzbarer
Helmbreite allerdings eng.

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

Der Lauf räumt `sprites/` vorher auf, damit nach Umbenennungen keine
verwaisten PNGs liegen bleiben.

Farben liegen zentral in `src/pixelart.py` im Dict `P`, die Zuordnung zu den
Spielervarianten in `SUITS` in `src/sprites_player.py`. Eine fünfte Farbe ist
ein Eintrag dort — alle 16 Frames dieser Variante entstehen automatisch.

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
- Die vier Spielerfarben sind auch bei 1:1 auf dem grünen Spielfeld sicher
  auseinanderzuhalten; das weiße Helmband hilft zusätzlich, weil es jede
  Figur vom Hintergrund abhebt.
- Bodenkacheln haben eine dezente Fuge an zwei Kanten, damit beim Kacheln
  ein feines Gitter entsteht und die Spielfeldstruktur erkennbar bleibt.

Die Grafiken sind eigenständig entworfen und nicht aus einem bestehenden
Spiel übernommen — sie sind frei verwendbar. "Bomberman" selbst ist eine
Marke von Konami; für eine Veröffentlichung wäre also ein eigener Titel
sinnvoll.
