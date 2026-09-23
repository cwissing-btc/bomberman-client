# Bomberman-Client

Ein pygame-Client für die Bomberman-Arena des Teams. Er meldet sich per UDP am Server an, zeigt
das Spielfeld an und lässt sich manuell oder von einem einfachen Bot steuern.

Verbindliche Schnittstelle: **`BOT_GUIDE.md`** (im Projektwurzelverzeichnis). Die Design-Dokumente
liegen unter `specs/001-game-client/` (Spec, Plan, Protokoll-Zusammenfassung, Aufgaben).

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Falls sich `pygame` in der venv nicht bauen lässt (z. B. Python 3.14 ohne passendes Wheel), das
systemweite `pygame` mitnutzen:

```bash
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install --no-build-isolation --no-deps -e .   # pytest ggf. systemweit vorhanden
```

## Starten

```bash
python -m bomberman_client --host 127.0.0.1 --port 47800 --name Carsten
```

| Parameter | Bedeutung | Standard |
|-----------|-----------|----------|
| `--host`  | Serveradresse | `127.0.0.1` |
| `--port`  | UDP-Port | `47800` |
| `--bot`   | im Bot-Modus starten | aus |
| `--name`  | Anzeigename, wird im HELLO übertragen (max. 24 Byte UTF-8) | `Carsten` |

Ein Match startet erst, wenn in der Moderations-Web-UI (Standard `http://127.0.0.1:8080`)
**Start** gedrückt wird und mindestens zwei Spieler verbunden sind.

## Steuerung

| Taste | Aktion |
|-------|--------|
| Pfeiltasten | laufen (hoch/runter/links/rechts) |
| Leertaste | Bombe legen (mit Richtung = Bombe legen und ausweichen) |
| `B` | zwischen manuellem Modus und Bot-Modus umschalten |
| Fenster schließen | Client beenden |

## Bot-Modus

Der Bot steuert nur die **eigene** Figur und plant **zeitbewusst**:

- Jede Zelle bekommt Gefahren-Zeitfenster: aktive Flammen, vorhergesagte Explosionen aller
  Bomben mit dem **aktuellen Radius des jeweiligen Besitzers** (Power-ups vergrößern ihn; bei
  unbekanntem Besitzer gilt das Regel-Maximum), **Kettenreaktionen** und die exakte
  Sudden-Death-Reihenfolge des Servers.
- Die Wegsuche läuft über (Zelle, Zeit) mit der eigenen Schrittdauer (Speed-Power-up) und kennt
  Warten als Zug – so rennt er durch eine Bombenlinie, wenn die Zeit reicht, und bleibt weg,
  wenn nicht.
- Bomben legt er nur, wenn es lohnt (Kisten/Gegner im Radius) **und** die Flucht in der
  Zündzeit gelingt – auch bei großem eigenen Radius. Immer per Kombi-Aktion (Bombe + Schritt).
- Ziele: Power-ups (Flamme > Bombe > Tempo) und Bombenplätze mit vielen Kisten/Gegnern, mit
  Hysterese gegen Hin-und-her-Laufen.
- Gegner-Fähigkeiten: Reichweite und freie Bomben jedes Gegners ergeben **Bedrohungszonen**
  (was er *jetzt* treffen könnte) – dort verweilt der Bot nicht, flieht lieber in Häfen
  außerhalb und schlägt bei eingekesselten Gegnern in eigener Reichweite bevorzugt zu.
- Robust bei Paketverlust: Zähler (Zündschnur, Flammen) werden um die vergangenen Ticks
  gealtert, es gilt eine Sicherheitsmarge, und bei eingefrorenem Zustand (verlorenes DELTA)
  läuft er den bereits zeitlich geprüften Pfad per **Koppelnavigation** nach Wanduhr weiter –
  ohne je blind eine weitere Bombe zu legen.

Die Regelkonstanten liest er aus `MATCH_INIT` – nichts ist hartkodiert.

## Tests

```bash
pytest
```

Getestet werden Protokoll, Zustandsverwaltung (Keyframe/Delta), Verlustbehandlung, Eingabe und
Bot-Logik. Darstellung und Eingabe werden manuell geprüft (siehe
`specs/001-game-client/quickstart.md`).

## Lokaler Test-Server

Für Entwicklung ohne die echte Arena liegt ein minimaler Test-Server bei:

```bash
python tools/test_server.py --port 47800            # normal
python tools/test_server.py --port 47800 --drop 0.1 --shuffle   # mit Paketverlust
```

Er bildet eine Teilmenge des Protokolls ab (HELLO/ASSIGNED, MATCH_INIT, KEYFRAME + echte DELTAs,
Bewegung, Bomben, Flammen) und startet das Match automatisch, sobald ein Spieler verbunden ist.

## Aufbau

```
src/bomberman_client/
  protocol.py   Byte-Kodierung (little-endian), Frames, 2-Bit-Kachelgitter  ← einzige Byte-Stelle
  state.py      GameState, MatchInfo, Rules, Player/Bomb/Flame/PowerUp
  track.py      TrackState: Keyframe/Delta-Verlustbehandlung (BOT_GUIDE.md §6)
  net.py        nicht-blockierender UDP-Socket
  input.py      Tasten → Aktion
  bot.py        Bot-Strategie (decide, BFS, Gefahrenfelder)
  assets.py     lädt spritesheet.png + atlas.json
  render.py     pygame-Darstellung
  main.py       Game-Loop (60/s), Zustandsautomat
tools/test_server.py   minimaler Test-Server
tests/                 pytest
assets/                Team-Sprites (64×64)
```

## Hinweise zur echten Arena

Verifiziert gegen den Server (jegollub-btc/bomberman), byteweise und live: alle Layouts stimmen
überein. Zwei ursprünglich gemeldete Doku-Fehler des Servers (Regelblock 17 statt 19 Bytes;
`WALL_CLOSED`/`0x0D` undokumentiert) sind im Server-Update vom 2026-09-23 behoben – der Client
behandelte beides bereits korrekt.
