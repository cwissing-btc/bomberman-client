"""Binäres Protokoll Client ⇄ Server – die EINZIGE Stelle, die Bytes kennt.

Verbindliche Quelle: ``BOT_GUIDE.md`` (Projektwurzel). Alle Mehrbyte-Felder sind little-endian
(``<``), Koordinaten sind Feldindizes. Client-Zusammenfassung: ``specs/001-game-client/contracts/protocol.md``.

Uplink (Client → Server, 2 Byte): ``[player_id][(seq << 4) | action]``.
Downlink (Server → Client): 5-Byte-Kopf ``u8 frame_type`` + ``u32 tick``, dann Nutzdaten.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import IntEnum

from .state import Bomb, Flame, GameState, MatchInfo, Player, PowerUp, Rules


class Action(IntEnum):
    NOOP = 0
    UP = 1
    DOWN = 2
    LEFT = 3
    RIGHT = 4
    BOMB = 5
    UP_BOMB = 6
    DOWN_BOMB = 7
    LEFT_BOMB = 8
    RIGHT_BOMB = 9
    HELLO = 15


class FrameType(IntEnum):
    ASSIGNED = 0x00
    LOBBY_STATUS = 0x01
    MATCH_INIT = 0x02
    KEYFRAME = 0x03
    DELTA = 0x04
    MATCH_END = 0x05


# --- Uplink -----------------------------------------------------------------

def encode_action(player_id: int, action: int, seq: int) -> bytes:
    """2-Byte-Uplink-Paket. ``seq`` wird auf 4 Bit begrenzt."""
    return bytes([player_id & 0xFF, ((seq & 0x0F) << 4) | (int(action) & 0x0F)])


HELLO_NAME_MAX_BYTES = 24


def encode_hello(name: str | None = None) -> bytes:
    """HELLO = 0xFF 0xFF – optional gefolgt von Längenbyte + Name (UTF-8, max. 24 Byte, an
    Zeichengrenzen gekürzt; BOT_GUIDE.md „Naming yourself"). Ohne Namen bleibt es bei 2 Byte."""
    if not name or not name.strip():
        return b"\xff\xff"
    encoded = name.strip().encode("utf-8")
    if len(encoded) > HELLO_NAME_MAX_BYTES:
        # an Zeichengrenze kürzen: abgeschnittene Multibyte-Zeichen fallen weg
        encoded = encoded[:HELLO_NAME_MAX_BYTES].decode("utf-8", "ignore").encode("utf-8")
    return b"\xff\xff" + bytes([len(encoded)]) + encoded


# --- Downlink-Nutzdaten -----------------------------------------------------

@dataclass
class Assigned:
    player_id: int
    tick_rate: int
    max_players: int


@dataclass
class Slot:
    id: int
    connected: bool


@dataclass
class LobbyStatus:
    state: int          # 0 open,1 locked,2 countdown,3 running,4 match_over
    players_connected: int
    max_players: int
    slot_mask: int
    countdown_ticks: int

    def slots(self) -> list[Slot]:
        return [Slot(i, bool(self.slot_mask & (1 << i))) for i in range(self.max_players)]


@dataclass
class MatchEndResult:
    id: int
    placement: int
    score: int


@dataclass
class MatchEnd:
    reason: int         # 0 last_standing,1 timeout,2 aborted
    winner: int         # 0xFF = Unentschieden
    results: list[MatchEndResult]


@dataclass
class Delta:
    base_tick: int
    records: list[tuple]  # (tag, payload_dict)


@dataclass
class Frame:
    type: FrameType
    tick: int
    data: object | None   # Assigned | LobbyStatus | MatchInfo | GameState | Delta | MatchEnd


# --- Kachelgitter -----------------------------------------------------------

def unpack_tiles(packed: bytes, width: int, height: int) -> list[list[int]]:
    """Entpackt das 2-Bit-Kachelgitter (BOT_GUIDE.md §5.6) in tiles[y][x]."""
    tiles = [[0] * width for _ in range(height)]
    for y in range(height):
        for x in range(width):
            index = y * width + x
            byte = packed[index // 4]
            tiles[y][x] = (byte >> ((index % 4) * 2)) & 0b11
    return tiles


def pack_tiles(tiles: list[list[int]], width: int, height: int) -> bytes:
    """Gegenstück zu unpack_tiles (für den Test-Server)."""
    out = bytearray((width * height + 3) // 4)
    for y in range(height):
        for x in range(width):
            index = y * width + x
            out[index // 4] |= (tiles[y][x] & 0b11) << ((index % 4) * 2)
    return bytes(out)


# --- Dekodieren -------------------------------------------------------------

def decode(datagram: bytes) -> Frame | None:
    """Dekodiert ein Downlink-Datagramm. Bei Müll/zu kurz: ``None`` (FR-006)."""
    try:
        if len(datagram) < 5:
            return None
        ftype = datagram[0]
        tick = struct.unpack_from("<I", datagram, 1)[0]
        if ftype == FrameType.ASSIGNED:
            data = _decode_assigned(datagram)
        elif ftype == FrameType.LOBBY_STATUS:
            data = _decode_lobby(datagram)
        elif ftype == FrameType.MATCH_INIT:
            data = _decode_match_init(datagram)
        elif ftype == FrameType.KEYFRAME:
            data = _decode_keyframe(datagram)
        elif ftype == FrameType.DELTA:
            data = _decode_delta(datagram)
        elif ftype == FrameType.MATCH_END:
            data = _decode_match_end(datagram)
        else:
            return None  # unbekannter Frame-Typ
        if data is None:
            return None
        return Frame(FrameType(ftype), tick, data)
    except (struct.error, IndexError):
        return None


def _decode_assigned(d: bytes) -> Assigned | None:
    if len(d) < 9:
        return None
    return Assigned(player_id=d[6], tick_rate=d[7], max_players=d[8])


def _decode_lobby(d: bytes) -> LobbyStatus | None:
    if len(d) < 11:
        return None
    countdown = struct.unpack_from("<H", d, 9)[0]
    return LobbyStatus(state=d[5], players_connected=d[6], max_players=d[7],
                       slot_mask=d[8], countdown_ticks=countdown)


def _decode_rules(d: bytes, off: int) -> tuple[Rules, int]:
    fuse, flame_dur = struct.unpack_from("<HH", d, off)
    off += 4
    (tpc, sspt, sb, sf, mf, ms, pc) = struct.unpack_from("<BBBBBBB", d, off)
    off += 7
    round_len, sudden = struct.unpack_from("<II", d, off)
    off += 8
    rules = Rules(fuse, flame_dur, tpc, sspt, sb, sf, mf, ms, pc, round_len, sudden)
    return rules, off


def _decode_match_init(d: bytes) -> MatchInfo | None:
    # 5 Kopf, 5 version, 6 match_id u32, 10 seed u64, 18 my_id, 19 N, 20 W, 21 H
    if len(d) < 22:
        return None
    my_id = d[18]
    n = d[19]
    width = d[20]
    height = d[21]
    off = 22
    grid_len = (width * height + 3) // 4
    off += grid_len  # Kachelgitter wird über KEYFRAME übernommen; hier übersprungen
    spawns: list[tuple[int, int]] = []
    for _ in range(n):
        spawns.append((d[off], d[off + 1]))
        off += 2
    rules, off = _decode_rules(d, off)
    return MatchInfo(width=width, height=height, spawns=spawns, rules=rules, my_id=my_id)


def _decode_keyframe(d: bytes) -> GameState | None:
    if len(d) < 7:
        return None
    width = d[5]
    height = d[6]
    off = 7
    grid_len = (width * height + 3) // 4
    tiles = unpack_tiles(d[off:off + grid_len], width, height)
    off += grid_len

    players: dict[int, Player] = {}
    n_players = d[off]
    off += 1
    for _ in range(n_players):
        pid, flags, x, y, facing, prog, bmax, flame, speed = struct.unpack_from("<BBBBBBBBB", d, off)
        off += 9
        score = struct.unpack_from("<H", d, off)[0]
        off += 2
        players[pid] = Player(pid, bool(flags & 1), bool(flags & 2), x, y, facing,
                              prog, bmax, flame, speed, score)

    bombs: dict[int, Bomb] = {}
    n_bombs = struct.unpack_from("<H", d, off)[0]
    off += 2
    for _ in range(n_bombs):
        bid, owner, x, y, fuse = struct.unpack_from("<HBBBH", d, off)
        off += 7
        bombs[bid] = Bomb(bid, owner, x, y, fuse)

    flames: list[Flame] = []
    n_flames = struct.unpack_from("<H", d, off)[0]
    off += 2
    for _ in range(n_flames):
        x, y, ticks = struct.unpack_from("<BBB", d, off)
        off += 3
        flames.append(Flame(x, y, ticks))

    powerups: dict[int, PowerUp] = {}
    n_pu = struct.unpack_from("<H", d, off)[0]
    off += 2
    for _ in range(n_pu):
        pid, x, y, kind = struct.unpack_from("<HBBB", d, off)
        off += 5
        powerups[pid] = PowerUp(pid, x, y, kind)

    ticks_remaining = struct.unpack_from("<I", d, off)[0]
    return GameState(width, height, tiles, players, bombs, flames, powerups, ticks_remaining)


_DELTA_LAYOUT = {
    0x01: ("<BBBBBB", ("id", "flags", "x", "y", "dir", "progress")),
    0x02: ("<BBBBH", ("id", "bombs_max", "flame", "speed", "score")),
    0x03: ("<HBBBH", ("id", "owner", "x", "y", "fuse")),
    0x04: ("<H", ("id",)),
    0x05: ("<BBBBBB", ("x", "y", "up", "down", "left", "right")),
    0x06: ("<BBB", ("x", "y", "tile")),
    0x07: ("<HBBB", ("id", "x", "y", "kind")),
    0x08: ("<HB", ("id", "taken_by")),
    0x09: ("<BB", ("id", "killer")),
    0x0A: ("<BBB", ("x", "y", "ticks")),
    0x0B: ("<BB", ("x", "y")),
    0x0C: ("<I", ("ticks",)),
    0x0D: ("<BB", ("x", "y")),   # WALL_CLOSED (Sudden Death) – Feld wird zur festen Wand
}


def _decode_delta(d: bytes) -> Delta | None:
    if len(d) < 11:
        return None
    base_tick = struct.unpack_from("<I", d, 5)[0]
    count = struct.unpack_from("<H", d, 9)[0]
    off = 11
    records: list[tuple] = []
    for _ in range(count):
        tag = d[off]
        off += 1
        layout = _DELTA_LAYOUT.get(tag)
        if layout is None:
            return None  # unbekannter Tag → ganzes Delta verwerfen (FR-006)
        fmt, names = layout
        values = struct.unpack_from(fmt, d, off)
        off += struct.calcsize(fmt)
        records.append((tag, dict(zip(names, values))))
    return Delta(base_tick, records)


def _decode_match_end(d: bytes) -> MatchEnd | None:
    if len(d) < 8:
        return None
    reason = d[5]
    winner = d[6]
    count = d[7]
    off = 8
    results: list[MatchEndResult] = []
    for _ in range(count):
        pid, placement = d[off], d[off + 1]
        score = struct.unpack_from("<H", d, off + 2)[0]
        off += 4
        results.append(MatchEndResult(pid, placement, score))
    return MatchEnd(reason, winner, results)
