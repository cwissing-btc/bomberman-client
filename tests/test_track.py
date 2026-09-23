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
