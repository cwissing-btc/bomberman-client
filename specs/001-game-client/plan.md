# Implementation Plan: Bomberman-Spielclient (Anmeldung, Spielfeld, Steuerung, Bot-Modus)

**Branch**: `001-game-client` | **Date**: 2026-09-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-game-client/spec.md`

## Summary

Ein pygame-Client, der sich per UDP (Standard-Port 47800) mit `HELLO` an der Team-Arena anmeldet,
die Lobby anzeigt und im Match die 60/s eintreffenden Frames verarbeitet: `KEYFRAME` ersetzt den
Zustand, `DELTA` wird nur auf exakt passendem `base_tick` angewendet, sonst wird auf das nächste
`KEYFRAME` gewartet (kein Resync). Gezeichnet wird mit den Team-Assets (64×64). Pro Tick sendet
der Client genau ein 2-Byte-Paket (Spieler-ID, `seq`-Nibble + Aktion) – aus der Tastatur oder vom
Bot, umschaltbar per `B`. Verbindliche Quelle ist `BOT_GUIDE.md`; die Kodierung liegt zentral in
`protocol.py`. Client-Zusammenfassung: [contracts/protocol.md](./contracts/protocol.md).

## Technical Context

**Language/Version**: Python 3.12+ (Entwicklungsumgebung: 3.14)

**Primary Dependencies**: pygame 2.6 (Darstellung, Eingabe); Standardbibliothek `socket`,
`struct`, `argparse`, `dataclasses`, `enum`, `json` (Atlas laden)

**Assets**: Vom Team in `assets/` (Pack v2: 121 Sprites, 64×64, RGBA, Spritesheet + `atlas.json`).
Vier Spielerfarben `player_{blue,red,yellow,purple}_*`, fest auf Spieler-ID 0–3 abgebildet; die
eigene Figur wird zusätzlich markiert. Zwei der fünf Power-up-Sprites (`kick`, `remote`) bleiben
ungenutzt.

**Storage**: N/A

**Testing**: pytest (Protokoll, TrackState, GameState, Bot); manuelle Prüfung von
Darstellung/Eingabe nach [quickstart.md](./quickstart.md)

**Target Platform**: Desktop (Linux; Windows/macOS sollten ohne Änderung laufen)

**Project Type**: Desktop-Anwendung (einzelnes Python-Paket) + optionaler Test-Server

**Performance Goals**: 60 FPS / 60 Ticks; alle eingetroffenen Datagramme pro Frame verarbeiten;
Tastendruck → Aktion im selben Tick

**Constraints**: Game-Loop darf nie auf das Netzwerk warten; Uplink genau 1 Paket/Tick mit
`seq`-Nibble; Delta nur bei passendem `base_tick`; Anmelde-Timeout 5 s; Verbindungsverlust nach 3 s

**Scale/Scope**: 1 Spieler pro Client (Slot 0–3); Kartengröße vom Server (Fenster erst nach
`MATCH_INIT`); ca. 8 Module, geschätzt 700–1000 Zeilen inkl. optionalem Test-Server

Alle Unbekannten sind in [research.md](./research.md) entschieden. Das Protokoll ist über
`BOT_GUIDE.md` verbindlich; offene Entwurfspunkte gibt es nicht mehr.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution v2.0.0

| Prinzip | Prüfung | Ergebnis |
|---|---|---|
| I. Einfachheit / YAGNI | Nur pygame + pytest; kein Thread, kein asyncio; fertige Team-Sprites; keine Plugin-/Konfigurationsschichten | ✅ PASS |
| II. Server = Quelle der Wahrheit | `GameState` ändert sich nur über Keyframe/Delta; keine Prediction; Bot wählt nur Aktionen; Interpolation/Frames sind reine Darstellung | ✅ PASS |
| III. Abgestimmtes Protokoll | Contract ist verbindlich (`BOT_GUIDE.md`); `contracts/protocol.md` fasst die client-relevanten Teile zusammen; Kodierung zentral in `protocol.py`, little-endian + Frame-Formate | ✅ PASS |
| IV. UDP-Realität | Keyframe/Delta nach `BOT_GUIDE.md` §6 (Delta nur bei passendem `base_tick`, sonst auf Keyframe warten), ältere Ticks verwerfen, `decode()` gibt bei Müll `None`, nicht-blockierender Socket, kein Resync | ✅ PASS |
| V. Pragmatisches Testen | pytest für `protocol`, `track`, `state`, `bot`; `assets.py`-Test „alle Atlas-Frames ladbar"; Rendering/Eingabe manuell per Quickstart | ✅ PASS |
| Technische Rahmenbedingungen | Python 3 + pygame, 64×64 px, UDP Port 47800, Host/Port per Parameter, getrennte Module, deutsche Doku | ✅ PASS |

**Re-Check nach Phase 1**: Das Design führt keine neuen Abhängigkeiten oder Abstraktionen ein.
Ergebnis: **PASS**. (Die frühere Auflage zu Prinzip III entfällt, da der Contract jetzt
verbindlich vorliegt.)

## Project Structure

### Documentation (this feature)

```text
BOT_GUIDE.md                   # Vom Team: VERBINDLICHER Protokoll-Contract (UDP-Spieler-Client)
VISUALIZER_GUIDE.md            # Vom Team: Referenz für die WebSocket-UI; §4 Rendering ist übertragbar
assets/                        # Vom Team: Sprites, Atlas, Vorschau – nur lesen

specs/001-game-client/
├── plan.md              # Dieser Plan
├── research.md          # Phase 0: Entscheidungen R1–R14
├── data-model.md        # Phase 1: Datenklassen, TrackState, Zustandsautomat
├── quickstart.md        # Phase 1: Start- und Validierungsanleitung
├── contracts/
│   └── protocol.md      # Phase 1: Client-Sicht auf BOT_GUIDE.md (verbindlich)
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
pyproject.toml                 # Paketdefinition, Abhängigkeiten pygame / pytest
src/bomberman_client/
├── __init__.py
├── __main__.py                # argparse → Config, startet main.run()
├── protocol.py                # Codes/Frame-Formate (little-endian), encode_action(), decode() – EINZIGE Byte-Stelle
├── track.py                   # TrackState: Keyframe/Delta, base_tick-Prüfung (BOT_GUIDE §6)
├── state.py                   # GameState, MatchInfo, Rules, Player/Bomb/Flame/PowerUp
├── net.py                     # UDP-Socket nicht-blockierend: send(), receive_all()
├── bot.py                     # decide(), danger_cells(), bfs()
├── assets.py                  # lädt spritesheet.png + atlas.json, liefert Frames/Animationen
├── render.py                  # pygame-Zeichnen: Kacheln, Spieler (mit Marker), Bomben, Flammen, Overlay, Lobby
└── main.py                    # Game-Loop (60/s), Zustandsautomat, Eingabe→Aktion, Modus-Umschaltung

tools/
└── test_server.py             # optionaler Mini-Server (Teilmenge von BOT_GUIDE.md; --drop, --shuffle)

tests/
├── test_protocol.py           # encode/decode, 2-Bit-Gitter, Regelblock, kaputte Pakete
├── test_track.py              # Keyframe ersetzt, Delta nur bei passendem base_tick, ältere Ticks
├── test_state.py              # Keyframe/Delta anwenden, tile_changes
└── test_bot.py                # Ausweichen, Bombe+Ausweichen (Kombi), Warten
```

**Structure Decision**: Ein einzelnes Python-Paket im `src`-Layout. Protokoll, TrackState,
Zustand und Bot sind reine Logik ohne pygame und damit testbar (Prinzip V). `net.py` kapselt nur
den Socket, `render.py`/`main.py` enthalten den pygame-Anteil. Der optionale Test-Server liegt in
`tools/`, weil er ein Entwicklungswerkzeug ist.

## Umsetzungsreihenfolge (Überblick für /speckit-tasks)

1. **Setup**: `pyproject.toml`, Paketgerüst, pytest läuft.
2. **Grundlage**: `protocol.py` und `track.py` mit Tests (werden von allen Stories gebraucht).
3. **US1 (P1)**: `track.py`, `state.py`, `net.py`, `assets.py`, `render.py`, `main.py`
   (HELLO/ASSIGNED, Lobby, MATCH_INIT, KEYFRAME/DELTA, Sprites zeichnen, Overlay, Timeouts);
   optional `tools/test_server.py`.
4. **US2 (P2)**: Tasteneingabe → Aktionscode (inkl. Kombi 6–9), 1 Paket/Tick mit `seq`-Nibble.
5. **US3 (P3)**: `bot.py` mit Tests; Moduswechsel mit `B`; Modusanzeige.
6. **Feinschliff**: optional `--drop`/`--shuffle` im Test-Server; Quickstart-Szenarien durchspielen
   (bevorzugt gegen die echte Arena `just server`).

## Complexity Tracking

Keine Verstöße gegen die Constitution. Tabelle entfällt.
