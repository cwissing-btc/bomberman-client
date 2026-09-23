# Quickstart & Validierung: Bomberman-Spielclient

**Feature**: [spec.md](./spec.md) | **Contract**: `BOT_GUIDE.md` |
**Client-Sicht**: [contracts/protocol.md](./contracts/protocol.md)

## Voraussetzungen

- Python 3.12+ (entwickelt mit 3.14)
- Installation im Projektverzeichnis:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Falls sich `pygame` in der venv nicht bauen lässt (z. B. Python 3.14 ohne passendes Wheel),
das systemweit installierte `pygame` mitnutzen:

```bash
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install --no-build-isolation --no-deps -e .   # pytest ggf. separat/systemweit
```

## Automatische Tests

```bash
pytest
```

Erwartung: alle Tests grün (Protokoll, TrackState, GameState, Bot).

## Gegen die Team-Arena (empfohlen)

Die Arena laut `BOT_GUIDE.md` §10 starten und die Web-UI zum Starten/Moderieren nutzen:

```bash
just server        # Arena auf udp/47800, Web-UI auf http://127.0.0.1:8080
```

Client(s) starten:

```bash
python -m bomberman_client --host 127.0.0.1 --port 47800            # manuell
python -m bomberman_client --host 127.0.0.1 --port 47800 --bot      # Bot
```

In der Web-UI erscheinen die Clients in der Lobby; mit **Start** beginnt das Match (mindestens
2 Plätze belegt).

## Optional: eigener Test-Server

Für Verlusttests ohne die echte Arena:

```bash
python tools/test_server.py --port 47800 --drop 0.1 --shuffle
```

## Validierungsszenarien

| # | Schritt | Erwartetes Ergebnis | Bezug |
|---|---|---|---|
| 1 | Client starten (Arena läuft) | Erscheint in < 5 s in der Lobby, Spieler-ID sichtbar | US1, FR-002, SC-001 |
| 2 | Client starten, Arena **nicht** gestartet | Nach ~5 s Meldung „kein ASSIGNED / Server antwortet nicht" | FR-003 |
| 3 | Match in der Web-UI starten | Fenster öffnet in Kartengröße × 64 px, Spielfeld sichtbar | US1 Sz. 3, FR-007 |
| 4 | Pfeiltasten / Leertaste drücken | Figur bewegt sich, Bombe erscheint und explodiert | US2, FR-009/010 |
| 5 | Taste `B` drücken | Overlay zeigt „BOT"; Figur spielt selbst; Steuertasten wirkungslos. Erneut `B` → „MANUELL" | US3 Sz. 4–5, FR-018/019 |
| 6 | Bot-Client ~2 Minuten laufen lassen | Bombe per Kombi-Aktion legen und ausweichen; Figur überlebt meist | US3, SC-005 |
| 7 | Test-Server mit `--drop 0.1 --shuffle`, 5 min spielen | Kein Absturz; nach Verlust binnen 0,5 s (nächstes Keyframe) wieder korrekt; nie älterer Zustand | FR-005/005a, SC-003/004 |
| 8 | Arena/Test-Server während des Spiels beenden | Nach ~3 s Hinweis „Verbindung verloren" | FR-015 |
| 9 | Eigene Figur stirbt / Match endet | Status bzw. Ergebnis wird angezeigt, danach zurück in die Lobby | FR-016 |
| 10 | Fenster schließen | Client beendet sich sauber | Edge Case |

## Hinweis

Abweichungen vom Server-Verhalten werden nur in `protocol.py` angepasst; alle anderen Module
bleiben davon unberührt (zentrale Kodierung).
