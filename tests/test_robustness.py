"""T041: Der Client darf durch beschädigte/zufällige Pakete nicht abstürzen (FR-006, SC-004)."""

import os
import random
import struct

from bomberman_client.protocol import decode, FrameType
from bomberman_client.track import TrackState


def test_decode_never_raises_on_random_bytes():
    rng = random.Random(1234)
    for _ in range(5000):
        n = rng.randint(0, 40)
        data = bytes(rng.randrange(256) for _ in range(n))
        result = decode(data)          # darf nie eine Exception werfen
        assert result is None or hasattr(result, "type")


def test_decode_truncated_frames_return_none():
    # Gültiger Kopf, aber Nutzdaten abgeschnitten → None statt Absturz
    for ftype in (FrameType.ASSIGNED, FrameType.MATCH_INIT, FrameType.KEYFRAME,
                  FrameType.DELTA, FrameType.MATCH_END, FrameType.LOBBY_STATUS):
        header = bytes([ftype]) + struct.pack("<I", 5)
        assert decode(header) is None
        assert decode(header + b"\x01") is None


def test_track_survives_stream_of_garbage():
    track = TrackState()
    rng = random.Random(42)
    for _ in range(2000):
        data = os.urandom(rng.randint(0, 30))
        fr = decode(data)
        if fr is not None:
            track.on_frame(fr, now=1.0)   # darf nie crashen
    # Zustand bleibt konsistent (kein halbkaputter Zustand)
    assert track.phase in (
        "connecting", "lobby", "playing", "connection_lost", "match_over", "failed"
    )


def test_delta_with_unknown_record_tag_is_discarded_cleanly():
    # base_tick + count=1 + unbekannter Tag 0x7F → ganzes Delta wird verworfen (None)
    body = struct.pack("<I", 10) + struct.pack("<H", 1) + bytes([0x7F, 0, 0])
    data = bytes([FrameType.DELTA]) + struct.pack("<I", 11) + body
    assert decode(data) is None
