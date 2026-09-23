"""Tests für TrackState (BOT_GUIDE.md §6): Keyframe/Delta, base_tick-Prüfung."""

import struct

from bomberman_client import protocol as p
from bomberman_client.protocol import FrameType
from bomberman_client.track import Phase, TrackState


def header(ftype, tick):
    return bytes([ftype]) + struct.pack("<I", tick)


def keyframe(tick, ticks_remaining=0):
    width, height = 2, 1
    body = bytes([width, height]) + p.pack_tiles([[0, 0]], width, height)
    body += bytes([0])                       # 0 players
    body += struct.pack("<H", 0)             # 0 bombs
    body += struct.pack("<H", 0)             # 0 flames
    body += struct.pack("<H", 0)             # 0 powerups
    body += struct.pack("<I", ticks_remaining)
    return p.decode(header(FrameType.KEYFRAME, tick) + body)


def delta(tick, base_tick, records=b""):
    count = 0
    body = struct.pack("<I", base_tick) + struct.pack("<H", count) + records
    return p.decode(header(FrameType.DELTA, tick) + body)


def tile_delta(tick, base_tick, x, y, tile):
    body = struct.pack("<I", base_tick) + struct.pack("<H", 1)
    body += bytes([0x06]) + struct.pack("<BBB", x, y, tile)
    return p.decode(header(FrameType.DELTA, tick) + body)


def test_keyframe_sets_at_tick():
    t = TrackState()
    t.on_frame(keyframe(100), now=1.0)
    assert t.at_tick == 100
    assert t.phase == Phase.PLAYING


def test_delta_with_matching_base_tick_is_applied():
    t = TrackState()
    t.on_frame(keyframe(100), now=1.0)
    t.on_frame(tile_delta(101, base_tick=100, x=1, y=0, tile=2), now=1.1)
    assert t.at_tick == 101
    assert t.state.tile_at(1, 0) == 2


def test_delta_with_wrong_base_tick_is_discarded():
    t = TrackState()
    t.on_frame(keyframe(100), now=1.0)
    t.on_frame(tile_delta(103, base_tick=102, x=1, y=0, tile=2), now=1.1)  # Lücke
    assert t.at_tick == 100                 # unverändert
    assert t.state.tile_at(1, 0) == 0


def test_next_keyframe_recovers_after_gap():
    t = TrackState()
    t.on_frame(keyframe(100), now=1.0)
    t.on_frame(tile_delta(103, base_tick=102, x=1, y=0, tile=2), now=1.1)  # verworfen
    t.on_frame(keyframe(130), now=1.5)      # Erholung
    assert t.at_tick == 130


def test_older_tick_delta_ignored():
    t = TrackState()
    t.on_frame(keyframe(100), now=1.0)
    t.on_frame(delta(50, base_tick=49), now=1.1)
    assert t.at_tick == 100


def test_connection_lost_after_timeout():
    t = TrackState()
    t.on_frame(keyframe(100), now=1.0)
    t.check_connection(now=5.0, timeout=3.0)
    assert t.phase == Phase.CONNECTION_LOST


def test_assigned_moves_to_lobby():
    t = TrackState()
    d = header(FrameType.ASSIGNED, 1) + bytes([1, 2, 60, 4])
    t.on_frame(p.decode(d), now=0.5)
    assert t.my_id == 2
    assert t.phase == Phase.LOBBY


# --- Matchwechsel (Bot stand im 2. Match am Levelanfang still) ----------------------

def match_init(tick, match_id, my_id=0):
    """MATCH_INIT-Frame (BOT_GUIDE.md §5.3) für ein 2x1-Brett mit einem Spieler."""
    width, height = 2, 1
    body = bytes([1]) + struct.pack("<I", match_id) + struct.pack("<Q", 7)
    body += bytes([my_id, 1, width, height]) + p.pack_tiles([[0, 0]], width, height)
    body += bytes([0, 0])                                          # Spawn
    body += struct.pack("<HH", 120, 30) + struct.pack("<BBBBBBB", 8, 1, 1, 1, 6, 3, 30)
    body += struct.pack("<II", 10800, 7200)
    return p.decode(header(FrameType.MATCH_INIT, tick) + body)


def lobby_status(tick, state):
    body = bytes([state, 2, 4, 0b11]) + struct.pack("<H", 0)
    return p.decode(header(FrameType.LOBBY_STATUS, tick) + body)


def test_match_init_carries_match_id():
    frame = match_init(100, match_id=4711)
    assert frame.data.match_id == 4711


def test_repeated_match_init_keeps_state():
    """Der Server wiederholt MATCH_INIT auf 5 Ticks in Folge (Zustellgarantie). Dieselbe
    Match-ID darf den bereits gehaltenen Zustand nicht löschen – sonst steht der Client
    bis zum nächsten KEYFRAME (30 Ticks) ohne Zustand und der Bot am Start still."""
    t = TrackState()
    t.on_frame(match_init(100, match_id=1), 0.0)
    t.on_frame(keyframe(0), 0.0)
    t.on_frame(match_init(101, match_id=1), 0.0)         # Wiederholung
    assert t.state is not None and t.at_tick == 0
    t.on_frame(delta(1, base_tick=0), 0.0)
    assert t.at_tick == 1
    assert t.phase == Phase.PLAYING


def test_match_init_of_new_match_resets_state():
    t = TrackState()
    t.on_frame(match_init(100, match_id=1), 0.0)
    t.on_frame(keyframe(500), 0.0)
    t.on_frame(match_init(900, match_id=2), 0.0)         # neues Match
    assert t.state is None and t.at_tick is None
    assert t.match.match_id == 2
    t.on_frame(delta(501, base_tick=500), 0.0)           # Rest des alten Matches → verwerfen
    assert t.state is None
    t.on_frame(keyframe(0), 0.0)
    assert t.at_tick == 0 and t.phase == Phase.PLAYING


def test_lobby_status_while_playing_ends_the_match():
    """Moderator-„end" sendet kein MATCH_END; der folgende LOBBY_STATUS (match over / open)
    beendet das Match clientseitig, statt in PLAYING auf altem Zustand weiterzuspielen."""
    t = TrackState()
    t.on_frame(match_init(100, match_id=1), 0.0)
    t.on_frame(keyframe(500), 0.0)
    t.on_frame(lobby_status(530, state=4), 0.0)          # match over
    assert t.phase == Phase.MATCH_OVER
    t.on_frame(lobby_status(560, state=0), 0.0)          # open
    assert t.phase == Phase.LOBBY


def test_lobby_status_running_does_not_interrupt_match():
    t = TrackState()
    t.on_frame(match_init(100, match_id=1), 0.0)
    t.on_frame(keyframe(500), 0.0)
    t.on_frame(lobby_status(530, state=3), 0.0)          # running
    assert t.phase == Phase.PLAYING
