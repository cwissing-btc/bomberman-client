# Protokoll Client ⇄ Server (Bomberman)

**Status**: ✅ **Verbindlich** – Quelle der Wahrheit ist `BOT_GUIDE.md` im Projektwurzel-
verzeichnis (vom Server-Team). Dieses Dokument fasst nur die **client-relevanten** Punkte
zusammen und legt fest, wie der Client sie umsetzt. Bei Widersprüchen gilt `BOT_GUIDE.md`.

**Protokoll-Version**: 1 | **Datum**: 2026-09-23

---

## 1. Eckdaten

| Punkt | Wert |
|---|---|
| Transport | UDP, Standard-Port **47800** |
| Byte-Reihenfolge | **little-endian** für alle Mehrbyte-Felder |
| Koordinaten | Feldindizes (keine Pixel), `(0,0)` oben links, `y` wächst nach unten |
| Tickrate | 60 Ticks/s |

## 2. Client → Server (Uplink, 2 Byte pro Tick)

```
Byte 0: Spieler-ID (0–3)
Byte 1: (seq << 4) | Aktionscode      seq = 4-Bit-Zähler, bei jedem Paket +1 (& 0x0F)
```

Aktionscodes (unteres Nibble):

| Code | Aktion | | Code | Aktion |
|---|---|---|---|---|
| 0 | `NOOP` | | 5 | `BOMB` |
| 1 | `UP` | | 6 | `UP+BOMB` |
| 2 | `DOWN` | | 7 | `DOWN+BOMB` |
| 3 | `LEFT` | | 8 | `LEFT+BOMB` |
| 4 | `RIGHT` | | 9 | `RIGHT+BOMB` |
| 15 | `HELLO` (Slot anfordern / `MATCH_INIT` neu anfordern) | | 10–14 | reserviert (Paket wird verworfen) |

**Client-Regeln** (aus `BOT_GUIDE.md` §4, §8):
- Genau **ein** Paket pro Tick; ohne Eingabe `NOOP` senden (Lebenszeichen).
- `seq`-Nibble bei jedem Paket erhöhen, sonst verwirft der Server Pakete als Duplikate.
- Anmeldung: `0xFF 0xFF` (`HELLO`) senden, bis `ASSIGNED` kommt; bei Ausbleiben alle 500 ms
  wiederholen. Dasselbe `HELLO` fordert bei Bedarf `MATCH_INIT` erneut an.
- Identität ist an die Absenderadresse gebunden: **immer über denselben Socket/Port** senden
  und empfangen.

## 3. Server → Client (Downlink)

5-Byte-Kopf: `u8 frame_type` + `u32 tick`, danach frameabhängige Nutzdaten.

| Typ | Name | Client-relevant |
|---|---|---|
| `0x00` | `ASSIGNED` | eigene Spieler-ID (Byte 6), Tickrate, max. Spieler |
| `0x01` | `LOBBY_STATUS` | Lobby-Zustand, belegte Slots, Countdown – für die Lobby-Anzeige |
| `0x02` | `MATCH_INIT` | statische Matchdaten: Breite, Höhe, Kachelgitter, Startzellen, Regelblock |
| `0x03` | `KEYFRAME` | vollständiger dynamischer Zustand (alle 30 Ticks + zu Matchbeginn) |
| `0x04` | `DELTA` | Änderungen ab `base_tick` (jeden zweiten Tick) |
| `0x05` | `MATCH_END` | Grund, Gewinner-ID, Platzierungen |

Datensatz-Formate (Player 11 B, Bomb 7 B, Flame 3 B, Power-up 5 B, Delta-Tags `0x01`–`0x0D`,
2-Bit-Kachelgitter): siehe `BOT_GUIDE.md` §5. Der Client kapselt **alle** diese Formate in
`protocol.py`.

**Gegen den Server-Quellcode verifiziert (2026-09-23, jegollub-btc/bomberman):**
- Alle Byte-Layouts stimmen exakt mit `crates/bomber-protocol` überein (little-endian,
  Frame-Kopf 5 B, Keyframe/Delta/Uplink, Tile-Codes 0/1/2, Power-up 0/1/2, Richtung
  0 down/1 up/2 left/3 right).
- **Regelblock ist 19 B, nicht 17 B**: Der Server-Encoder schreibt 2+2+1+1+1+1+1+1+1+4+4 = 19
  Bytes. `RULES_ENCODED_LEN = 17` im Server und die „17 bytes" in `BOT_GUIDE.md` §5.8 sind falsch
  (harmlos, da Encoder/Decoder symmetrisch sind). Unser Client liest korrekt 19 B.
- **`WALL_CLOSED` (`0x0D`)**: zusätzliches Delta-Record für Sudden Death (Feld → feste Wand). War
  in `BOT_GUIDE.md` nicht als eigener Tag gelistet; im Client ergänzt.

## 4. Verlustbehandlung (verbindlich, `BOT_GUIDE.md` §6)

- Ein `DELTA` wird **nur** angewendet, wenn der Client den Zustand exakt zu dessen `base_tick`
  hält; sonst verwerfen und auf das nächste `KEYFRAME` warten (kommt alle 30 Ticks ≈ 0,5 s).
- Ein `KEYFRAME` ist immer vertrauenswürdig und ersetzt den Zustand.
- Frames mit älterem Tick als der gehaltene Zustand ignorieren.
- **Kein Resync anforderbar** – der Uplink ist nur 2 Byte. (Ausnahme: `HELLO` fordert
  `MATCH_INIT` erneut an, falls es ganz verpasst wurde.)

## 5. Spielregeln, die den Client betreffen

- **Tödlich sind ausschließlich `FLAME_ADD`-Zellen** (nicht die `EXPLOSION`-Form – die ist nur
  für die Animation). Der Bot MUSS Flammenzellen als Gefahr behandeln.
- **Facing** im Player-Record (`0` down, `1` up, `2` left, `3` right) bestimmt direkt das
  Spieler-Sprite; die Laufrichtung muss **nicht** aus der Bewegung abgeleitet werden.
- `move_progress`/`moving` zeigen eine laufende Bewegung; ein Schritt ist nicht unterbrechbar.
- Kombi-Aktionen `6`–`9` (Bombe + Schritt im selben Tick) sind die einzige Möglichkeit, sicher
  wegzulaufen, nachdem man eine Bombe gelegt hat.
- Regelkonstanten (Zündzeit, Flammendauer, Tempo, Reichweiten, Rundenlänge, Sudden-Death)
  kommen aus dem Regelblock in `MATCH_INIT` – **nicht** hartkodieren.

## 6. Sicherheitshinweis (Bezug zur früheren „Hacking-Idee“)

`BOT_GUIDE.md` §3 hält fest: Die Spieler-ID ist an die Absenderadresse gebunden, und Pakete,
deren `player_id` nicht zur Adresse passt, werden verworfen. Der Server verhindert damit
bereits von sich aus, dass ein Client einen anderen Spieler fernsteuert. Ein solches Feature
ist also weder nötig noch möglich – gutes Beispiel für serverseitige Autorität (Prinzip II).

## 7. Was der Client NICHT nutzt (bewusst, YAGNI)

- Power-up-Arten `kick`/`remote` aus den Assets: Der Server kennt nur `0` extra Bombe,
  `1` größere Flamme, `2` Tempo. Die beiden übrigen Sprites bleiben ungenutzt.
- RNG-Seed / match id aus `MATCH_INIT`: für die reine Darstellung nicht nötig.
- Reference-SDKs (`clients/python/`) des Servers: Wir schreiben `protocol.py` selbst (Lernziel);
  das SDK dient höchstens als Vergleich.
