# Research: Bomberman-Spielclient

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Datum**: 2026-09-23

Verbindliche Quelle für das Protokoll: `BOT_GUIDE.md` (Projektwurzel). Rendering-Hinweise sind
zusätzlich aus `VISUALIZER_GUIDE.md` §4 übernommen (dort für die WebSocket-UI beschrieben, die
Zeichentechnik gilt aber genauso für unseren pygame-Client). Client-Zusammenfassung:
[contracts/protocol.md](./contracts/protocol.md).

---

## R1 – Netzwerkempfang ohne Blockieren des Game-Loops

- **Decision**: Ein UDP-Socket (Standardbibliothek `socket`) im nicht-blockierenden Modus. Der
  Game-Loop läuft mit 60 FPS, liest pro Frame alle wartenden Datagramme (`recvfrom` bis
  `BlockingIOError`) und sendet danach genau ein Uplink-Paket.
- **Rationale**: Deckt sich mit `BOT_GUIDE.md` §8 („never block your receive loop; drain,
  decide, send"). Kein Thread, kein asyncio (Prinzip I).
- **Alternatives considered**: Empfangs-Thread + Queue (unnötige Nebenläufigkeit); asyncio
  (passt schlecht zum pygame-Loop).

## R2 – Zentrale Kodierung in `protocol.py`

- **Decision**: Alle Byte-Formate liegen in **einem** Modul: Aktionscodes, Frame-Typen, das
  2-Bit-Kachelgitter, die Datensätze (Player 11 B, Bomb 7 B, Flame 3 B, Power-up 5 B), die
  Delta-Tags `0x01`–`0x0C` und der 17-B-Regelblock. Kodierung mit `struct`, **little-endian**
  (`<`). Dekodierte Frames sind `dataclass`-Objekte.
- **Rationale**: Prinzip III (eine Stelle, die Bytes kennt) und Testbarkeit ohne pygame
  (Prinzip V). little-endian und Feldindizes sind in `BOT_GUIDE.md` §0 vorgegeben.
- **Alternatives considered**: Formate über mehrere Module verteilen (schwer wartbar); das
  Server-SDK `clients/python/` einbinden (widerspricht dem Lernziel; nur zum Abgleich).

## R3 – Uplink: 2-Byte-Paket mit Sequenz-Nibble

- **Decision**: Pro Tick genau ein Paket `[player_id][(seq << 4) | action]`. `seq` ist ein
  4-Bit-Zähler, der bei jedem Paket erhöht wird (`seq = (seq + 1) & 0x0F`). Ohne Eingabe wird
  `NOOP` gesendet.
- **Rationale**: `BOT_GUIDE.md` §4 – ohne wachsenden `seq` verwirft der Server Pakete als
  Duplikate; ohne regelmäßiges Senden gilt der Spieler in dem Tick als untätig.
- **Alternatives considered**: nur bei Tastendruck senden (Server sieht kein Lebenszeichen);
  `seq` konstant lassen (Pakete werden verworfen).

## R4 – Aktionscodes und Kombi-Aktionen

- **Decision**: `NOOP=0, UP=1, DOWN=2, LEFT=3, RIGHT=4, BOMB=5, UP+BOMB=6, DOWN+BOMB=7,
  LEFT+BOMB=8, RIGHT+BOMB=9, HELLO=15`. Codes 10–14 werden nicht verwendet.
- **Rationale**: Kombi-Aktionen 6–9 sind laut `BOT_GUIDE.md` §4/§7 die **einzige** Möglichkeit,
  im selben Tick eine Bombe zu legen und wegzugehen – zentral für das Überleben des Bots (SC-005).
- **Alternatives considered**: nur `BOMB` und dann im nächsten Tick laufen (führt oft zum Tod
  auf der eigenen Bombe).

## R5 – Anmeldung und Lobby (kein Spielername)

- **Decision**: Der Client sendet `HELLO` (`0xFF 0xFF`) und übernimmt die Spieler-ID (0–3) aus
  `ASSIGNED` (Byte 6). Ohne Antwort alle 500 ms wiederholen, Abbruch/Meldung nach 5 s. Bis zum
  Matchstart wird `LOBBY_STATUS` angezeigt.
- **Spielername**: Seit dem Server-Update (Commit „bots can name themselves in the hello
  packet") trägt das HELLO optional `len + Name` (≤ 24 Byte UTF-8). Vorher war der Uplink strikt
  2 Byte und Namen kamen nur per Moderator-`rename`; das gewinnt weiterhin. Der Client sendet
  `--name` (Standard „Carsten") im HELLO.
- **Rationale**: Entspricht dem echten Handshake; korrigiert die frühere Annahme, der Client
  schicke einen Namen.
- **Alternatives considered**: Name im Paket (technisch unmöglich).

## R6 – Zustand halten: Keyframe/Delta statt Resync

- **Decision**: `GameState` wird aus `KEYFRAME` vollständig gesetzt. Ein `DELTA` wird nur
  angewendet, wenn der gehaltene Tick exakt `delta.base_tick` ist; sonst verwerfen und auf das
  nächste `KEYFRAME` warten (kommt alle 30 Ticks ≈ 0,5 s). Frames mit älterem Tick werden
  ignoriert. `MATCH_INIT` liefert die statischen Daten (Karte, Regeln); geht es verloren, holt
  ein erneutes `HELLO` es nach.
- **Rationale**: Exakt `BOT_GUIDE.md` §6. Ein anforderbarer Resync existiert nicht (Uplink 2 B).
- **Alternatives considered**: Deltas puffern und Lücken füllen (der Guide warnt ausdrücklich
  davor – führt zu stillem Desync); eigener Resync (unmöglich).

## R7 – `TrackState`: das Kernstück der Verlustbehandlung

- **Decision**: Klasse `TrackState` mit `static` (aus `MATCH_INIT`), `state` (dynamisch) und
  `at_tick`. `on_frame(frame)`:
  - `MATCH_INIT` → `static` setzen, `state=None`.
  - `KEYFRAME` → `state` ersetzen, `at_tick = frame.tick`.
  - `DELTA` → nur wenn `at_tick == frame.base_tick`: Records anwenden, `at_tick = frame.tick`;
    sonst ignorieren.
  - Frame mit `tick < at_tick` → ignorieren.
  - `MATCH_END` → Ergebnis merken, zurück in Lobby-Anzeige.
- **Rationale**: 1:1 der Pseudocode aus `BOT_GUIDE.md` §6; reine Logik, ohne Netzwerk/pygame →
  gut mit pytest testbar (Prinzip V).

## R8 – Verbindungsüberwachung

- **Decision**: Kein Heartbeat nötig – im Match kommen 60 Frames/s (Delta jeden zweiten Tick,
  Keyframe alle 30 Ticks). Kommt 3 s lang **kein** Frame, zeigt der Client „Verbindung
  verloren" (FR-015). In der Lobby zählt `LOBBY_STATUS` (alle 30 Ticks) als Lebenszeichen.
- **Rationale**: Ergibt sich aus der Frame-Frequenz; kein zusätzliches Protokoll nötig (YAGNI).
- **Alternatives considered**: eigener Ping (Uplink zu schmal, unnötig).

## R9 – Kachelgitter (2 Bit pro Feld)

- **Decision**: Das Gitter kommt gepackt (2 Bit/Feld, row-major, low bits first). `protocol.py`
  entpackt es in `tiles[y][x]` mit `index = y*width + x`, `tile = (byte >> (index%4*2)) & 0b11`.
  Werte: `0` frei, `1` feste Wand, `2` Kiste. `tile_changes`/`TILE_SET` aktualisieren einzelne
  Felder (z. B. zerstörte Kiste → frei).
- **Rationale**: `BOT_GUIDE.md` §5.6. Das Gitter wird in Deltas nicht neu gesendet, daher müssen
  `TILE_SET`-Records auf das gehaltene Gitter angewendet werden.

## R10 – Darstellung mit den Team-Assets

- **Decision**: pygame-Fenster `Breite × 64` mal `Höhe × 64` px, geöffnet erst nach
  `MATCH_INIT`. `assets.py` lädt `spritesheet.png` + `atlas.json` einmal und schneidet Frames als
  `pygame.Surface` aus. Kein Smoothing (Pixelart); falls skaliert wird, nur ganzzahlig.
  Zeichenreihenfolge nach `VISUALIZER_GUIDE.md` §4.5: Boden → Kisten → Wände → Power-ups →
  Bomben → Flammen → Spieler (nach `y` sortiert) → Overlay. Sprites, die höher als 64 px sind,
  werden unten-mittig auf der Zelle verankert. Unbekannter Typ → Magenta-Platzhalter.
- **Vier Spielerfarben (Asset-Pack v2)**: Das zweite Asset-Paket liefert vier Figuren
  `player_{blue,red,yellow,purple}_*` (je 4 Richtungen × 4 Frames). Spieler-ID 0–3 wird fest
  auf diese Reihenfolge abgebildet; ein Marker ist nur noch für die eigene Figur nötig.
  (Das erste Paket hatte nur eine Figur; die damalige Marker-Lösung ist damit hinfällig.)
- **Rationale**: Assets sind bereits 64×64; die Zeichentechnik ist im Visualizer-Guide erprobt.
- **Alternatives considered**: Sprites per Farbton umfärben (macht Pixelart matschig, laut Guide).

## R10a – Animation und weiche Bewegung

- **Decision**:
  - Frame aus `atlas.json`-Gruppen; Zeit-basiert (`int(now*fps) % n`), außer beim Laufen.
  - **Laufrichtung** direkt aus dem `facing`/`dir`-Feld des Servers (kein Ableiten aus Bewegung).
  - **Lauf-Frame** aus `move_progress/move_total` (an die Simulation gekoppelt), nicht aus der Uhr.
  - **Weiche Bewegung** (optional, empfohlen): Position rückwärts vom Ziel interpolieren
    (`VISUALIZER_GUIDE.md` §4.2), weil `x`/`y` eines laufenden Spielers schon das Zielfeld sind.
    Ohne Interpolation „springt" die Figur ein Feld voraus.
  - **Explosion** aus Teilen zusammensetzen (center/arm/tip), alle mit gleichem Frame-Index,
    ~14 fps über 5 Frames; welche Felder tödlich sind, kommt aus `flames`.
- **Rationale**: Interpolation und Frame-Wahl sind reine Darstellung und ändern den Zustand nicht
  (Prinzip II). Die Formeln stehen fertig im Visualizer-Guide.
- **Alternatives considered**: an der Uhr hängende Animation (läuft laut Guide ungleichmäßig).

## R11 – Eingabe

- **Decision**: Der Game-Loop liest pro Tick `pygame.key.get_pressed()` und bildet die aktuell
  gedrückten Tasten auf einen Aktionscode ab: Pfeiltaste(n) + Leertaste → Kombi-Aktion 6–9,
  nur Leertaste → `BOMB`, nur Pfeil → Richtung, nichts → `NOOP`. Taste `B` schaltet den Modus um;
  im Bot-Modus werden Steuertasten ignoriert.
- **Rationale**: Passt zum „ein Paket pro Tick"-Modell (R3); Kombi-Aktionen fallen so natürlich
  an. Bewegungstempo bestimmt der Server.
- **Alternatives considered**: pro `KEYDOWN` senden (passt nicht zum Tick-Takt, verliert
  gehaltene Tasten).

## R12 – Bot-Strategie

- **Decision (v2, zeitbewusst)**: `decide(track, now) -> action_code` auf Basis eines
  Gefahren-Zeitmodells:
  1. **Gefahren-Zeitfenster je Zelle** `[start, ende]` (Ticks ab jetzt): aktive `flames`;
     Explosionen aller Bomben mit dem *aktuellen* `flame` des Besitzers (unbekannt →
     `rules.max_flame`), an Wänden/Kisten gestoppt; **Kettenreaktionen** per Fixpunkt (eine Bombe
     im Kreuz einer früher zündenden zündet mit); Sudden Death nach der **exakten Server-
     Reihenfolge** (`closing_order`: Innenzellen, außen → innen, im Uhrzeigersinn, 1 Zelle/6 Ticks).
  2. **Bewegungsmodell**: Schritt = `ticks_to_cross(speed)`; die Figur gilt ab Schrittbeginn als
     auf dem Zielfeld (BOT_GUIDE §7) → ein Feld muss ab Betreten bis zum Verlassen sicher sein.
  3. **Suche über (Zelle, Schritt)** inkl. Warten; erst laufen, dann warten. Ziel „Hafen" = Zelle,
     die ab Ankunft einen ganzen Zünd-+Flammenzyklus sicher bleibt. Ohne Hafen: Zug mit der
     längsten Überlebenszeit.
  4. Prioritäten: Hafen erreichen → **Bombe + Ausweichen**, wenn Kisten/Gegner im Radius liegen
     und die Flucht mit der eigenen Reichweite **rechtzeitig** gelingt (Simulation der neuen Bombe
     inkl. Kettenreaktion) → Ziel mit bestem Nutzen `Wert/(Schritte+1)` (Power-up Flamme 3 >
     Bombe 2,5 > Tempo 2; Bombenplatz nach Kisten/Gegnern) mit Hysterese; unbrauchbare
     Bombenplätze werden zeitweise gesperrt.
  5. Gleicher Server-Tick (eingefrorener Zustand nach verlorenem DELTA, bis zu 0,5 s) →
     **Koppelnavigation**: den zuletzt geplanten Pfad nach Wanduhr weiterlaufen (1 Schritt je
     `ticks_to_cross/60` s), **Bombe nie** wiederholen (Einmal-Aktion); neue Bombe erst nach
     `BOMB_ADD` oder 12 Ticks. Bei 10 % Verlust ist der Zustand ~50 % der Zeit eingefroren –
     ohne Koppelnavigation blieb der Bot nach dem ersten Fluchtschritt in der Bombenlinie stehen.
  7. **Gegner-Fähigkeiten**: Reichweite/Bombenanzahl aller Spieler kommen per `PLAYER_STATS`.
     Daraus **Bedrohungszonen** = Kreuzlinien jedes Gegners mit *freier* Bombe (Kapazität =
     `bombs_max` − aktive Bomben): dort nicht verweilen (Zielwert ×0,6), Flucht bevorzugt in
     einen Hafen außerhalb (≤ 2 Schritte Umweg), ohne Ziel aus der Linie treten. Eingekesselte
     Gegner (≤ 1 begehbarer Nachbar) in eigener Reichweite: Angriffswert +1,5.
  6. **Zähler-Alterung**: `fuse`/`ticks` kommen nur per KEYFRAME (alle 30 Ticks), DELTAs zählen
     nicht herunter → Restzeit = Wert − (Tick jetzt − Tick des Stempels), plus 4 Ticks
     Sicherheitsmarge für Latenz. Ohne das hielt der Bot Bomben bis 0,5 s zu lang für harmlos.
- **Rationale**: Die v1-Heuristik kannte keine Zeit (jede Bombe sofort tödlich, keine Ketten,
  Radius-Fallback 2, Flucht ohne Timing) – mit Power-ups (Radius bis 6) wird das fatal. Das
  Zeitmodell deckt FR-012–FR-014/SC-005 robust ab und bleibt reine, testbare Logik (~350 Zeilen).
- **Alternatives considered**: Minimax/Monte-Carlo über Gegnerzüge, Lernverfahren
  (überdimensioniert, Prinzip I); v1-Heuristik (zu trivial, s. o.).

## R13 – Test-Server (optional)

- **Decision**: Ein optionaler `tools/test_server.py`, der eine Teilmenge von `BOT_GUIDE.md`
  bedient (HELLO/ASSIGNED, MATCH_INIT, KEYFRAME/DELTA, Bewegung, Bomben), mit `--drop`/`--shuffle`
  für den Verlusttest (SC-003). **Primär** wird aber gegen die echte Team-Arena getestet
  (`just server`), da diese verfügbar ist.
- **Rationale**: Erlaubt Offline-Entwicklung und gezielte Verlusttests; die echte Arena bleibt
  Referenz.
- **Alternatives considered**: nur echte Arena (Verlust schwer reproduzierbar); kein Test-Server
  (dann keine deterministischen Verlusttests).

## R14 – Projekt-Setup

- **Decision**: `pyproject.toml` mit `pygame` (Laufzeit) und `pytest` (dev); Paket
  `src/bomberman_client/`; Start `python -m bomberman_client`. `argparse`: `--host`,
  `--port` (Default 47800), `--bot`, `--name` (lokal).
- **Rationale**: Standard-Layout, keine weiteren Tools nötig.
- **Alternatives considered**: Poetry/uv (nicht nötig); Startmenü (per Spec ausgeschlossen).
