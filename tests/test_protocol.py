"""Tests für die Byte-Kodierung/-Dekodierung (BOT_GUIDE.md)."""

import struct

from bomberman_client import protocol as p
from bomberman_client.protocol import Action, FrameType


def test_encode_action_packs_seq_and_action():
    assert p.encode_action(3, Action.RIGHT, 0) == bytes([3, 0x04])
    assert p.encode_action(3, Action.BOMB, 5) == bytes([3, (5 << 4) | 5])


def test_encode_action_seq_wraps_to_4_bits():
    # seq 17 -> 1 (& 0x0F)
    assert p.encode_action(0, Action.UP, 17) == bytes([0, (1 << 4) | 1])


def test_encode_hello():
    assert p.encode_hello() == b"\xff\xff"
    assert p.encode_hello("") == b"\xff\xff"
    assert p.encode_hello("   ") == b"\xff\xff"


def test_encode_hello_with_name():
    d = p.encode_hello("Carsten")
    assert d[:2] == b"\xff\xff" and d[2] == 7 and d[3:] == b"Carsten"


def test_encode_hello_name_truncated_at_char_boundary():
    d = p.encode_hello("ä" * 13)            # 26 Byte → auf 24 gekürzt = 12 ganze Zeichen
    assert d[2] == 24 and d[3:].decode("utf-8") == "ä" * 12
    assert len(d) == 3 + 24


def test_decode_too_short_returns_none():
    assert p.decode(b"") is None
    assert p.decode(b"\x00\x00") is None


def test_decode_unknown_frame_type_returns_none():
    assert p.decode(bytes([0x99, 0, 0, 0, 0])) is None


def _header(ftype, tick):
    return bytes([ftype]) + struct.pack("<I", tick)


def test_decode_assigned():
    d = _header(FrameType.ASSIGNED, 10) + bytes([1, 3, 60, 4])
    frame = p.decode(d)
    assert frame is not None
    assert frame.type == FrameType.ASSIGNED
    assert frame.tick == 10
    assert frame.data.player_id == 3
    assert frame.data.tick_rate == 60
    assert frame.data.max_players == 4


def test_decode_lobby():
    d = _header(FrameType.LOBBY_STATUS, 5) + bytes([0, 2, 4, 0b0011]) + struct.pack("<H", 0)
    frame = p.decode(d)
    assert frame.data.players_connected == 2
    slots = frame.data.slots()
    assert slots[0].connected and slots[1].connected and not slots[2].connected


def test_tiles_roundtrip():
    tiles = [[0, 1, 2], [2, 0, 1]]
    packed = p.pack_tiles(tiles, 3, 2)
    assert p.unpack_tiles(packed, 3, 2) == tiles


def test_decode_keyframe_roundtrip():
    width, height = 3, 2
    tiles = [[0, 1, 2], [2, 0, 1]]
    body = bytes([width, height]) + p.pack_tiles(tiles, width, height)
    # 1 player
    body += bytes([1])
    body += struct.pack("<BBBBBBBBB", 3, 0b11, 1, 1, 2, 4, 2, 3, 1) + struct.pack("<H", 120)
    # 1 bomb
    body += struct.pack("<H", 1) + struct.pack("<HBBBH", 9, 3, 1, 1, 77)
    # 1 flame
    body += struct.pack("<H", 1) + struct.pack("<BBB", 2, 0, 12)
    # 1 powerup
    body += struct.pack("<H", 1) + struct.pack("<HBBB", 4, 2, 1, 2)
    body += struct.pack("<I", 9566)
    d = _header(FrameType.KEYFRAME, 1234) + body

    frame = p.decode(d)
    assert frame is not None
    gs = frame.data
    assert gs.width == 3 and gs.height == 2
    assert gs.tiles == tiles
    assert gs.players[3].x == 1 and gs.players[3].flame == 3 and gs.players[3].score == 120
    assert gs.players[3].alive and gs.players[3].moving
    assert gs.bombs[9].fuse == 77
    assert gs.flames[0].ticks == 12
    assert gs.powerups[4].kind == 2
    assert gs.ticks_remaining == 9566


def test_decode_delta_records():
    body = struct.pack("<I", 1000) + struct.pack("<H", 2)
    body += bytes([0x06]) + struct.pack("<BBB", 4, 6, 0)          # TILE_SET
    body += bytes([0x0A]) + struct.pack("<BBB", 5, 5, 30)         # FLAME_ADD
    d = _header(FrameType.DELTA, 1001) + body
    frame = p.decode(d)
    assert frame.data.base_tick == 1000
    tags = [tag for tag, _ in frame.data.records]
    assert tags == [0x06, 0x0A]


def test_decode_match_end():
    body = bytes([0, 0]) + bytes([2])
    body += struct.pack("<BBH", 0, 1, 1300) + struct.pack("<BBH", 1, 2, 400)
    d = _header(FrameType.MATCH_END, 5000) + body
    frame = p.decode(d)
    assert frame.data.winner == 0
    assert len(frame.data.results) == 2
    assert frame.data.results[0].score == 1300
