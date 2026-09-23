# Data Model: Bomberman-Spielclient

**Feature**: [spec.md](./spec.md) | **Protokoll**: [contracts/protocol.md](./contracts/protocol.md)
| **Contract**: `BOT_GUIDE.md`

Alle Modelle sind reine Python-Datenklassen ohne pygame- oder Socket-Abhängigkeit.

---

## Config

Startparameter (FR-001).

| Feld | Typ | Regel |
|---|---|---|
| `host` | str | Pflicht |
| `port` | int | Standard 47800 |
| `bot` | bool | Anfangsmodus; Standard `False` |
| `name` | str \| None | wird im HELLO übertragen (≤ 24 Byte UTF-8); Standard „Carsten" |

## Action (IntEnum)

`NOOP=0, UP=1, DOWN=2, LEFT=3, RIGHT=4, BOMB=5, UP_BOMB=6, DOWN_BOMB=7, LEFT_BOMB=8,
RIGHT_BOMB=9, HELLO=15`. Uplink-Byte: `(seq << 4) | action` (Codes: `BOT_GUIDE.md` §4).

## FrameType (IntEnum) und Frame

`ASSIGNED=0x00, LOBBY_STATUS=0x01, MATCH_INIT=0x02, KEYFRAME=0x03, DELTA=0x04, MATCH_END=0x05`.

`Frame` = dekodierter Downlink: `type`, `tick` und typabhängige Nutzdaten. Ungültige/zu kurze
Frames → `decode()` liefert `None` (FR-006).

## MatchInfo (aus MATCH_INIT)

| Feld | Typ | Bemerkung |
|---|---|---|
| `width`, `height` | int | Kartengröße (vom Server) |
| `tiles` | list[list[int]] | `tiles[y][x]`, entpackt aus dem 2-Bit-Gitter |
| `spawns` | list[(x, y)] | Startzellen je Spieler-ID |
| `rules` | Rules | Regelblock (17 B), s. u. |
| `my_id` | int | eigene Spieler-ID |

## Rules (Regelblock, nicht hartkodieren)

`bomb_fuse_ticks, flame_duration_ticks, ticks_per_cell, speed_step_ticks, start_bombs,
start_flame, max_flame, max_speed, powerup_chance_pct, round_time_ticks, sudden_death_tick`.
Ticks pro Feld bei Tempo *s*: `max(1, ticks_per_cell - speed_step_ticks * s)`.

## Player / Bomb / Flame / PowerUp (aus KEYFRAME, je Tick vollständig)

- **Player** (11 B): `id`, `alive`, `moving`, `x`, `y`, `facing` (0 down,1 up,2 left,3 right),
  `move_progress`, `bombs_max`, `flame` (Reichweite), `speed`, `score`.
- **Bomb** (7 B): `id`, `owner`, `x`, `y`, `fuse` (Rest-Ticks).
- **Flame** (3 B): `x`, `y`, `ticks`. **Jede gelistete Zelle ist tödlich.**
- **PowerUp** (5 B): `id`, `x`, `y`, `kind` (`0` extra Bombe, `1` größere Flamme, `2` Tempo).

## GameState

Vollständiger dynamischer Zustand eines Ticks. Wird nur durch Server-Frames verändert (FR-011).

| Feld | Typ |
|---|---|
| `players` | dict[int, Player] |
| `bombs` | dict[int, Bomb] |
| `flames` | list[Flame] |
| `powerups` | dict[int, PowerUp] |
| `ticks_remaining` | int |

- `apply_keyframe(frame)` – ersetzt alle Listen vollständig (kein Merge).
- `apply_delta(records)` – wendet Delta-Tags an: `PLAYER_STATE/STATS`, `BOMB_ADD/REMOVE`,
  `FLAME_ADD/REMOVE`, `TILE_SET` (aktualisiert das Kachelgitter in `MatchInfo`), `POWERUP_ADD/
  REMOVE`, `PLAYER_DEATH`, `EXPLOSION` (nur Animation), `TIMER`.

## TrackState (Verlustbehandlung – Kernstück)

Setzt `BOT_GUIDE.md` §6 um.

| Feld | Typ | Bemerkung |
|---|---|---|
| `match` | MatchInfo \| None | aus `MATCH_INIT` |
| `state` | GameState \| None | dynamischer Zustand |
| `at_tick` | int \| None | Tick, den `state` repräsentiert |
| `last_frame_time` | float | für „Verbindung verloren" (3 s) |
| `phase` | str | `connecting`, `lobby`, `playing`, `connection_lost`, `match_over`, `failed` |

`on_frame(frame, now)`:

| Frame | Ergebnis |
|---|---|
| `ASSIGNED` | `my_id` merken, `phase=lobby` |
| `LOBBY_STATUS` | Lobby-Anzeige aktualisieren |
| `MATCH_INIT` | `match` setzen, `state=None`, `phase=playing` |
| `KEYFRAME` | `state` ersetzen, `at_tick=frame.tick` |
| `DELTA` mit `base_tick == at_tick` | anwenden, `at_tick=frame.tick` |
| `DELTA` sonst, oder `tick < at_tick` | ignorieren (auf nächstes `KEYFRAME` warten) |
| `MATCH_END` | Ergebnis merken, `phase=match_over` |

## ClientState (Zustandsautomat)

```
        HELLO senden
 [CONNECTING] ─ASSIGNED─▶ [LOBBY] ─MATCH_INIT+KEYFRAME─▶ [PLAYING] ─MATCH_END─▶ [MATCH_OVER]
      │                      ▲                              │  ▲                     │
      │ 5 s kein ASSIGNED    └──────────────────────────── │  │ Frame              │ (zurück)
      ▼                        (neue Runde)                 ▼  │                    ▼
   [FAILED] (Meldung)                                 [CONNECTION_LOST] ◀───────── [LOBBY]
                                                      (3 s ohne Frame)
```

Im Zustand `PLAYING`: `mode ∈ {MANUAL, BOT}`, Umschalten mit `B` (FR-018/019).

## Bot

`decide(track, now) -> Action` – siehe [research.md R12](./research.md). Hilfen:
`danger_cells(track) -> set[(x,y)]` (Flammen + vorhergesagte Bombenkreuze),
`walkable(match, x, y) -> bool`, `bfs(match, start, goal_pred, avoid) -> list[(x,y)]`.

> **Power-ups**: Der Server kennt drei Arten (`0/1/2`); die Asset-Sprites `kick`/`remote`
> bleiben ungenutzt. **Namen** werden nie übertragen (Uplink 2 B).
