# Tasks: Bomberman-Spielclient (Anmeldung, Spielfeld, Steuerung, Bot-Modus)

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Contract**: `BOT_GUIDE.md`

**Tests**: pytest für reine Logik (Protokoll, TrackState, GameState, Bot) ist per Constitution
(Prinzip V) verpflichtend und daher enthalten. Darstellung/Eingabe werden manuell geprüft
(quickstart.md), dafür gibt es keine automatischen Tests.

**Konventionen**: `[P]` = parallel möglich (andere Datei, keine offene Abhängigkeit).
Story-Label `[US1]/[US2]/[US3]` nur in den Story-Phasen.

---

## Phase 1: Setup

- [X] T001 Projekt `pyproject.toml` im Repo-Wurzelverzeichnis anlegen: Paket `bomberman-client`,
  Abhängigkeit `pygame>=2.6`, Dev-Abhängigkeit `pytest`, `requires-python = ">=3.12"`,
  Konsolen-/Modulstart `python -m bomberman_client`, src-Layout (`[tool.setuptools] packages`).
- [X] T002 Paketgerüst anlegen: `src/bomberman_client/__init__.py`, leere Module `protocol.py`,
  `state.py`, `track.py`, `net.py`, `assets.py`, `render.py`, `bot.py`, `main.py`,
  `__main__.py`; Verzeichnisse `tests/` und `tools/` mit `tests/__init__.py`.
- [X] T003 [P] Asset-Pfad-Konstante in `src/bomberman_client/assets.py` definieren
  (`ASSETS_DIR` zeigt auf `assets/`, aufgelöst relativ zum Repo-Wurzelverzeichnis).
- [X] T004 [P] `.gitignore` um `.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/` ergänzen.

---

## Phase 2: Foundational (blockierende Grundlage für alle Stories)

Reine Logik ohne pygame – bildet den Kern und wird von allen User Stories genutzt.

- [X] T005 [P] In `src/bomberman_client/protocol.py` die Konstanten definieren: `Action`
  (IntEnum `NOOP=0,UP=1,DOWN=2,LEFT=3,RIGHT=4,BOMB=5,UP_BOMB=6,DOWN_BOMB=7,LEFT_BOMB=8,
  RIGHT_BOMB=9,HELLO=15`) und `FrameType` (IntEnum `ASSIGNED=0x00,LOBBY_STATUS=0x01,
  MATCH_INIT=0x02,KEYFRAME=0x03,DELTA=0x04,MATCH_END=0x05`). Byte-Reihenfolge little-endian.
- [X] T006 [P] In `src/bomberman_client/protocol.py` `encode_action(player_id, action, seq) ->
  bytes` (2 Byte: `player_id`, `(seq & 0x0F) << 4 | action`) und `encode_hello() -> b"\xff\xff"`
  implementieren.
- [X] T007 In `src/bomberman_client/protocol.py` `decode(datagram) -> Frame | None` mit
  5-Byte-Kopf (`u8` Typ, `u32` Tick, little-endian); bei zu kurzem/unbekanntem Paket `None`
  (FR-006). `Frame`-Dataclass mit `type`, `tick`, `payload`.
- [X] T008 In `src/bomberman_client/protocol.py` die Frame-Nutzdaten dekodieren gemäß
  `BOT_GUIDE.md` §5: `ASSIGNED` (Spieler-ID Byte 6, Tickrate, max Spieler), `LOBBY_STATUS`
  (Zustand, belegte Slots, Countdown), `MATCH_END` (Grund, Gewinner, Ergebnisse).
- [X] T009 In `src/bomberman_client/protocol.py` das 2-Bit-Kachelgitter entpacken
  (`index = y*width+x`, `tile = (byte >> (index%4*2)) & 0b11`; `0` frei, `1` Wand, `2` Kiste)
  und `MATCH_INIT` dekodieren (Breite, Höhe, Gitter, Startzellen, 17-Byte-Regelblock).
- [X] T010 In `src/bomberman_client/protocol.py` `KEYFRAME` dekodieren: Player-Record (11 B:
  id, flags→alive/moving, x, y, facing, move_progress, bombs_max, flame, speed, score),
  Bomb (7 B), Flame (3 B: x,y,ticks – **jede Zelle tödlich**), PowerUp (5 B: id,x,y,kind), sowie
  `ticks_remaining`.
- [X] T011 In `src/bomberman_client/protocol.py` `DELTA` dekodieren: `base_tick` (u32),
  Record-Anzahl (u16) und die Tags `0x01`–`0x0C` (PLAYER_STATE/STATS, BOMB_ADD/REMOVE,
  EXPLOSION, TILE_SET, POWERUP_ADD/REMOVE, PLAYER_DEATH, FLAME_ADD/REMOVE, TIMER).
- [X] T012 [P] In `src/bomberman_client/state.py` die Dataclasses `Rules`, `MatchInfo`,
  `Player`, `Bomb`, `Flame`, `PowerUp`, `GameState` gemäß [data-model.md](./data-model.md)
  anlegen (Feldindizes; `facing` 0 down/1 up/2 left/3 right).
- [X] T013 In `src/bomberman_client/state.py` `GameState.apply_keyframe(frame)` (ersetzt
  players/bombs/flames/powerups vollständig, **kein** Merge) und `apply_delta(records, match)`
  (wendet Delta-Tags an; `TILE_SET` aktualisiert das Gitter in `MatchInfo`).
- [X] T014 In `src/bomberman_client/track.py` `TrackState` implementieren (`BOT_GUIDE.md` §6):
  `on_frame(frame, now)` – `MATCH_INIT` setzt `match`, `KEYFRAME` ersetzt `state` und
  `at_tick`, `DELTA` nur bei `base_tick == at_tick` anwenden (sonst verwerfen), Frames mit
  `tick < at_tick` verwerfen, `MATCH_END` merken; `phase`-Feld pflegen.
- [X] T015 [P] In `src/bomberman_client/net.py` `UdpClient` implementieren: nicht-blockierender
  UDP-Socket, `send(datagram)`, `receive_all() -> list[bytes]` (liest bis `BlockingIOError`),
  fester Server-Endpunkt; sendet/empfängt über denselben Socket (Identität an Adresse gebunden).
- [X] T016 [P] `tests/test_protocol.py`: `encode_action` (seq-Nibble, Wrap `& 0x0F`),
  Roundtrip Decode für jeden Frame-Typ, 2-Bit-Gitter-Entpacken, zu kurzes/unbekanntes Paket → `None`.
- [X] T017 [P] `tests/test_state.py`: `apply_keyframe` ersetzt vollständig; `apply_delta` mit
  `TILE_SET`, `BOMB_ADD/REMOVE`, `FLAME_ADD/REMOVE`, `PLAYER_DEATH`.
- [X] T018 [P] `tests/test_track.py`: Keyframe setzt `at_tick`; Delta mit passendem `base_tick`
  wird angewendet und erhöht `at_tick`; Delta mit falschem `base_tick` und älterer Tick werden
  verworfen; nach Verlust stellt das nächste Keyframe den Zustand wieder her.

**Checkpoint**: Protokoll, Zustand und Verlustbehandlung sind getestet und lauffähig (headless).

---

## Phase 3: User Story 1 - Anmelden, Lobby, Spielfeld sehen (P1) 🎯 MVP

**Goal**: Client meldet sich per `HELLO` an, zeigt die Lobby und im Match das Spielfeld
(64×64-Kacheln) an; verarbeitet Keyframe/Delta korrekt.

**Independent Test**: Gegen `just server` starten, in der Lobby erscheinen, Match starten lassen,
korrekte und flüssige Darstellung prüfen (quickstart.md Szenarien 1–3).

- [X] T019 [P] [US1] In `src/bomberman_client/assets.py` `load_sprites()` implementieren:
  `spritesheet.png` laden, Frames laut `atlas.json` als `pygame.Surface` ausschneiden, per
  Frame-Namen bereitstellen; kein Smoothing (Pixelart). Unbekannter Name → Magenta-Platzhalter.
- [X] T020 [P] [US1] In `src/bomberman_client/assets.py` Animationszugriff aus `atlas.json`
  bereitstellen (`frame_for(group, now)` bzw. `frame_for_progress(group, progress)`).
- [X] T021 [US1] In `src/bomberman_client/render.py` das Spielfeld zeichnen: Boden
  (`floor_0/1` abwechselnd), Kisten, Wände in der Reihenfolge aus `VISUALIZER_GUIDE.md` §4.5;
  Fenstergröße = Breite×64 × Höhe×64, geöffnet erst nach `MATCH_INIT` (FR-007).
- [X] T022 [US1] In `src/bomberman_client/render.py` Spieler, Bomben, Flammen und Power-ups
  zeichnen: Spieler nach `y` sortiert, Blickrichtung aus `facing`, **farbiger Marker unter den
  Füßen** je Spieler-ID (eine gemeinsame Figur), eigener Spieler hervorgehoben; Explosion aus
  center/arm/tip zusammensetzen. Sprites >64 px unten-mittig verankern.
- [X] T023 [US1] In `src/bomberman_client/render.py` die Lobby-Anzeige (belegte Plätze,
  Countdown) und das Overlay (Modus, Verbindung, Spielstatus) zeichnen (FR-019).
- [X] T024 [US1] In `src/bomberman_client/main.py` den Game-Loop (60 FPS) mit Zustandsautomat
  aufbauen: `CONNECTING` → `HELLO` senden und alle 500 ms wiederholen; `ASSIGNED` → `LOBBY`;
  `MATCH_INIT`+`KEYFRAME` → `PLAYING` und Fenster öffnen; pro Tick Frames via `TrackState`
  verarbeiten (FR-002, FR-004, FR-005).
- [X] T025 [US1] In `src/bomberman_client/main.py` Timeouts umsetzen: 5 s ohne `ASSIGNED` →
  `FAILED` mit Meldung (FR-003); 1 s ohne verwertbaren Zustand → erneutes `HELLO` (FR-005b);
  3 s ohne Frame → `CONNECTION_LOST` (FR-015); `MATCH_END`/`PLAYER_DEATH` anzeigen, danach
  zurück in die Lobby (FR-016).
- [X] T026 [US1] In `src/bomberman_client/main.py` pro Tick genau ein Uplink-Paket senden
  (in US1 `NOOP`) mit bei jedem Paket erhöhtem `seq`-Nibble (FR-009/010).
- [X] T027 [US1] In `src/bomberman_client/__main__.py` `argparse` umsetzen: `--host`,
  `--port` (Default 47800), `--bot`, `--name` (nur lokal), `Config` bauen und `main.run(config)`
  aufrufen (FR-001).
- [X] T028 [P] [US1] `tests/test_assets.py`: alle in `atlas.json` genannten Frames sind ladbar
  (pygame headless via `SDL_VIDEODRIVER=dummy`).
- [X] T029 [P] [US1] Optionalen `tools/test_server.py` (Minimalfassung) anlegen: beantwortet
  `HELLO` mit `ASSIGNED`, sendet `MATCH_INIT` (feste Karte) und periodisch `KEYFRAME`, damit US1
  ohne die echte Arena testbar ist.

**Checkpoint**: MVP – Anmeldung, Lobby und flüssige Spielfeldanzeige funktionieren.

---

## Phase 4: User Story 2 - Figur manuell steuern (P2)

**Goal**: Tastatureingaben werden pro Tick in genau eine Aktion (inkl. Kombi 6–9) umgesetzt.

**Independent Test**: Im Match Pfeiltasten/Leertaste drücken; Figur bewegt sich, Bomben
erscheinen (quickstart.md Szenario 4).

- [X] T030 [US2] In `src/bomberman_client/main.py` (bzw. Hilfsfunktion `input_to_action` in
  `main.py`) die aktuell gedrückten Tasten (`pygame.key.get_pressed()`) auf einen Aktionscode
  abbilden: Pfeil+Leertaste → Kombi 6–9, nur Leertaste → `BOMB`, nur Pfeil → Richtung, nichts →
  `NOOP` (FR-009/010).
- [X] T031 [US2] In `src/bomberman_client/main.py` im manuellen Modus die berechnete Aktion
  statt `NOOP` senden; sicherstellen, dass der angezeigte Zustand nicht clientseitig verändert
  wird (FR-011).
- [X] T032 [P] [US2] Optional `tools/test_server.py` erweitern: Bewegung und Bomben verarbeiten
  und im `KEYFRAME`/`DELTA` widerspiegeln, damit manuelle Steuerung sichtbar wird.
- [X] T033 [P] [US2] `tests/test_input.py`: `input_to_action` deckt alle Tastenkombinationen ab
  (reine Funktion, ohne pygame-Fenster).

**Checkpoint**: Das Spiel ist manuell spielbar.

---

## Phase 5: User Story 3 - Bot-Modus (P3)

**Goal**: Der Client spielt eigenständig, weicht Flammen aus und legt Bomben per Kombi-Aktion.

**Independent Test**: Im Bot-Modus laufen lassen; Figur überlebt meist, sprengt Kisten
(quickstart.md Szenarien 5–6).

- [X] T034 [P] [US3] In `src/bomberman_client/bot.py` Hilfsfunktionen: `walkable(match,x,y)`,
  `bfs(match,start,goal_pred,avoid)`, `danger_cells(track)` (aktive Flammen + vorhergesagte
  Bombenkreuze; Reichweite = `flame` des Besitzers, an Wänden/Kisten gestoppt).
- [X] T035 [US3] In `src/bomberman_client/bot.py` `decide(track, now) -> Action` gemäß
  [research.md R12](./research.md): Gefahr meiden → Bombe+Ausweichen neben Kiste/Gegner →
  sicheres Power-up holen → zur nächsten Kiste → sonst `NOOP` (FR-012/013/014); Regelkonstanten
  aus `MatchInfo.rules` lesen, nicht hartkodieren.
- [X] T036 [US3] In `src/bomberman_client/main.py` den Bot-Modus einbinden: im Bot-Modus
  `decide(...)` statt Tastatureingabe verwenden; Steuertasten ignorieren (US3 Sz. 4).
- [X] T037 [US3] In `src/bomberman_client/main.py` Moduswechsel per Taste `B` und Anzeige des
  aktiven Modus umsetzen; Anfangsmodus aus `Config.bot` (FR-018/019).
- [X] T038 [P] [US3] `tests/test_bot.py`: weicht Flamme aus; legt Kombi-Bombe neben Kiste nur,
  wenn danach ein sicheres Feld erreichbar ist; wartet (`NOOP`), wenn kein sicherer Zug existiert.

**Checkpoint**: Alle drei User Stories funktionieren; Modus per `B` umschaltbar.

---

## Phase 6: Polish & Cross-Cutting

- [X] T039 [P] `tools/test_server.py` um `--drop <p>` (Frames zufällig verwerfen) und
  `--shuffle` (Reihenfolge vertauschen) ergänzen (für SC-003/SC-004).
- [X] T040 [P] `README.md` (deutsch) im Repo-Wurzelverzeichnis: Installation, Start gegen
  `just server`, Startparameter, Steuerung, Bot-/Moduswechsel.
- [X] T041 Robustheit prüfen: absichtlich beschädigte Pakete einspeisen (Test-Server oder
  Unit-Test), sicherstellen dass `decode()` `None` liefert und der Loop weiterläuft (FR-006, SC-004).
- [X] T042 Quickstart-Szenarien 1–10 aus [quickstart.md](./quickstart.md) manuell durchspielen
  (bevorzugt gegen `just server`) und Ergebnisse festhalten.

---

## Dependencies & Reihenfolge

- **Setup (T001–T004)** vor allem anderen.
- **Foundational (T005–T018)** blockiert alle Stories. Innerhalb: T007 vor T008–T011; T012 vor
  T013; T013+T007 vor T014. Tests T016–T018 nach ihren Modulen.
- **US1 (T019–T029)** benötigt Foundational. **MVP-Grenze nach US1.**
- **US2 (T030–T033)** benötigt US1 (Game-Loop/Sende-Logik).
- **US3 (T034–T038)** benötigt US1 (Zustand/Loop); unabhängig von US2.
- **Polish (T039–T042)** zuletzt.

## Parallele Ausführung (Beispiele)

- Foundational: T005, T012, T015 parallel (verschiedene Dateien); danach T016, T017, T018 parallel.
- US1: T019/T020 (assets) parallel zu T028/T029 (Tests/Test-Server), bevor `render.py`/`main.py`
  darauf aufbauen.
- Stories US2 und US3 können nach US1 parallel von zwei Personen bearbeitet werden.

## Implementierungsstrategie

1. **MVP zuerst**: Setup + Foundational + US1 → anmelden, Lobby, Spielfeld sehen.
2. **Inkrementell**: US2 (manuelle Steuerung), dann US3 (Bot), dann Polish.
3. Jede Story ist einzeln gegen `just server` (oder den Test-Server) demonstrierbar.
