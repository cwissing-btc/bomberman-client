#!/usr/bin/env python3
"""Minimaler Bomberman-Test-Server für die lokale Client-Entwicklung.

Bildet eine Teilmenge von BOT_GUIDE.md ab: HELLO→ASSIGNED, MATCH_INIT, KEYFRAME (alle 30 Ticks)
und DELTA (dazwischen), einfache Bewegung, Bomben und Flammen. NICHT der echte Server –
nur ein Entwicklungswerkzeug. Zum Testen von Paketverlust: --drop / --shuffle.

Start:  python tools/test_server.py --port 47800
"""

from __future__ import annotations

import argparse
import random
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import socket  # noqa: E402

from bomberman_client.protocol import Action, pack_tiles  # noqa: E402
from bomberman_client.state import TILE_FREE, TILE_SOFT, TILE_WALL  # noqa: E402

TICK_RATE = 60
W, H = 15, 13
FUSE = 120
FLAME_DUR = 30
RADIUS = 2


def build_map() -> list[list[int]]:
    tiles = [[TILE_FREE] * W for _ in range(H)]
    for y in range(H):
        for x in range(W):
            if x == 0 or y == 0 or x == W - 1 or y == H - 1 or (x % 2 == 0 and y % 2 == 0):
                tiles[y][x] = TILE_WALL
            elif random.random() < 0.55 and not ((x <= 2 and y <= 2)):
                tiles[y][x] = TILE_SOFT
    # Alle vier Startecken samt Nachbarfeldern freiräumen (wie der echte Kartengenerator)
    for (sx, sy) in ((1, 1), (W - 2, 1), (1, H - 2), (W - 2, H - 2)):
        for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
            x, y = sx + dx, sy + dy
            if 0 < x < W - 1 and 0 < y < H - 1 and tiles[y][x] != TILE_WALL:
                tiles[y][x] = TILE_FREE
    return tiles


SPAWNS = [(1, 1), (W - 2, 1), (1, H - 2), (W - 2, H - 2)]


TPC = 8  # Ticks pro Feld (wie rules_block ticks_per_cell)


class Player:
    def __init__(self, pid, x, y):
        self.id = pid
        self.alive = True
        self.x, self.y = x, y
        self.facing = 0
        self.flame = RADIUS
        self.moving = False     # Schritt läuft: Aktionen werden ignoriert (BOT_GUIDE §7)
        self.progress = 0


class Bomb:
    def __init__(self, bid, owner, x, y, flame=RADIUS):
        self.id = bid
        self.owner = owner
        self.x, self.y = x, y
        self.fuse = FUSE
        self.flame = flame


def rules_block() -> bytes:
    return (struct.pack("<HH", FUSE, FLAME_DUR)
            + struct.pack("<BBBBBBB", 8, 1, 1, RADIUS, 6, 3, 30)
            + struct.pack("<II", 10800, 7200))


def header(ftype, tick):
    return bytes([ftype]) + struct.pack("<I", tick)


class Server:
    def __init__(self, host, port, drop, shuffle):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((host, port))
        self.sock.setblocking(False)
        self.drop = drop
        self.shuffle = shuffle
        self.clients: dict[tuple, int] = {}
        self.players: dict[int, Player] = {}
        self.tiles = build_map()
        self.bombs: dict[int, Bomb] = {}
        self.flames: list[list] = []   # [x, y, ticks]
        self.next_bomb = 1
        self.tick = 0
        self.started = False
        # Für DELTA-Diffing: Zustand zum zuletzt gesendeten Frame
        self.last_sent = 0
        self.prev_players: dict[int, tuple] = {}
        self.prev_bombs: dict[int, tuple] = {}
        self.prev_flames: set[tuple[int, int]] = set()
        self.prev_tiles: list[list[int]] = []

    # --- Netzwerk --------------------------------------------------------
    def send(self, data, addr):
        if self.drop and random.random() < self.drop:
            return
        try:
            self.sock.sendto(data, addr)
        except OSError:
            pass

    def broadcast(self, data):
        for addr in list(self.clients):
            self.send(data, addr)

    def recv(self):
        out = []
        while True:
            try:
                data, addr = self.sock.recvfrom(2048)
            except (BlockingIOError, OSError):
                break
            out.append((data, addr))
        if self.shuffle and len(out) > 1:
            random.shuffle(out)
        return out

    # --- Frames ----------------------------------------------------------
    def assigned(self, pid):
        return header(0x00, self.tick) + bytes([1, pid, TICK_RATE, 4])

    def match_init(self, pid):
        body = bytes([1]) + struct.pack("<I", 42) + struct.pack("<Q", 12345)
        body += bytes([pid, 4, W, H]) + pack_tiles(self.tiles, W, H)
        for (sx, sy) in SPAWNS:
            body += bytes([sx, sy])
        body += rules_block()
        return header(0x02, self.tick) + body

    def keyframe(self):
        body = bytes([W, H]) + pack_tiles(self.tiles, W, H)
        body += bytes([len(self.players)])
        for p in self.players.values():
            flags = (1 if p.alive else 0) | (2 if p.moving else 0)
            body += struct.pack("<BBBBBBBBB", p.id, flags, p.x, p.y,
                                p.facing, p.progress, 1, p.flame, 0) + struct.pack("<H", 0)
        body += struct.pack("<H", len(self.bombs))
        for b in self.bombs.values():
            body += struct.pack("<HBBBH", b.id, b.owner, b.x, b.y, b.fuse)
        body += struct.pack("<H", len(self.flames))
        for f in self.flames:
            body += struct.pack("<BBB", f[0], f[1], f[2])
        body += struct.pack("<H", 0)  # keine Power-ups im Test-Server
        body += struct.pack("<I", max(0, 10800 - self.tick))
        return header(0x03, self.tick)  + body

    # --- DELTA (Diff gegen den zuletzt gesendeten Zustand) ---------------
    def snapshot_prev(self):
        self.prev_players = {p.id: (p.alive, p.x, p.y, p.facing, p.moving, p.progress)
                             for p in self.players.values()}
        self.prev_bombs = {b.id: (b.owner, b.x, b.y, b.fuse) for b in self.bombs.values()}
        self.prev_flames = {(f[0], f[1]) for f in self.flames}
        self.prev_tiles = [row[:] for row in self.tiles]

    def delta_records(self) -> bytes:
        recs = bytearray()
        count = 0
        # Spieler-Änderungen
        for p in self.players.values():
            cur = (p.alive, p.x, p.y, p.facing, p.moving, p.progress)
            if self.prev_players.get(p.id) != cur:
                flags = (1 if p.alive else 0) | (2 if p.moving else 0)
                recs += bytes([0x01, p.id, flags, p.x, p.y, p.facing, p.progress]); count += 1
        # Bomben hinzugefügt / entfernt
        for b in self.bombs.values():
            if b.id not in self.prev_bombs:
                recs += bytes([0x03]) + struct.pack("<HBBBH", b.id, b.owner, b.x, b.y, b.fuse)
                count += 1
        for bid in self.prev_bombs:
            if bid not in self.bombs:
                recs += bytes([0x04]) + struct.pack("<H", bid); count += 1
        # Flammen hinzugefügt / entfernt
        cur_flames = {(f[0], f[1]): f[2] for f in self.flames}
        for (x, y), ticks in cur_flames.items():
            if (x, y) not in self.prev_flames:
                recs += bytes([0x0A, x, y, ticks]); count += 1
        for (x, y) in self.prev_flames:
            if (x, y) not in cur_flames:
                recs += bytes([0x0B, x, y]); count += 1
        # Kacheländerungen (zerstörte Kisten)
        for y in range(H):
            for x in range(W):
                if self.prev_tiles and self.prev_tiles[y][x] != self.tiles[y][x]:
                    recs += bytes([0x06, x, y, self.tiles[y][x]]); count += 1
        return struct.pack("<H", count) + bytes(recs)

    def delta_frame(self):
        body = struct.pack("<I", self.last_sent) + self.delta_records()
        return header(0x04, self.tick) + body

    # --- Logik -----------------------------------------------------------
    def handle(self, data, addr):
        if data == b"\xff\xff":                      # HELLO
            if addr not in self.clients:
                pid = len(self.clients)
                if pid > 3:
                    return
                self.clients[addr] = pid
                self.players[pid] = Player(pid, *SPAWNS[pid])
            pid = self.clients[addr]
            self.send(self.assigned(pid), addr)
            self.send(self.match_init(pid), addr)
            self.started = True
            return
        if len(data) < 2 or addr not in self.clients:
            return
        action = data[1] & 0x0F
        p = self.players.get(self.clients[addr])
        if p is None or not p.alive:
            return
        self.apply_action(p, action)

    def apply_action(self, p, action):
        if p.moving:
            return                                   # Aktionen während eines Schritts ignorieren
        bomb = action in (Action.BOMB, Action.UP_BOMB, Action.DOWN_BOMB,
                          Action.LEFT_BOMB, Action.RIGHT_BOMB)
        has_active = any(b.owner == p.id for b in self.bombs.values())   # bombs_max = 1
        if bomb and not has_active and not any(
                b.x == p.x and b.y == p.y for b in self.bombs.values()):
            self.bombs[self.next_bomb] = Bomb(self.next_bomb, p.id, p.x, p.y, p.flame)
            self.next_bomb += 1
        move = {Action.UP: (0, -1, 1), Action.DOWN: (0, 1, 0),
                Action.LEFT: (-1, 0, 2), Action.RIGHT: (1, 0, 3),
                Action.UP_BOMB: (0, -1, 1), Action.DOWN_BOMB: (0, 1, 0),
                Action.LEFT_BOMB: (-1, 0, 2), Action.RIGHT_BOMB: (1, 0, 3)}.get(action)
        if move:
            dx, dy, facing = move
            p.facing = facing
            nx, ny = p.x + dx, p.y + dy
            occupied = any(o.alive and o.id != p.id and (o.x, o.y) == (nx, ny)
                           for o in self.players.values())
            if self.tiles[ny][nx] == TILE_FREE and not occupied and not any(
                    b.x == nx and b.y == ny for b in self.bombs.values()):
                p.x, p.y = nx, ny                    # Zielfeld gilt ab Schrittbeginn
                p.moving, p.progress = True, 0

    def step(self):
        for f in self.flames:
            f[2] -= 1
        self.flames = [f for f in self.flames if f[2] > 0]
        for p in self.players.values():              # Schritte fortschreiben (TPC Ticks/Feld)
            if p.moving:
                p.progress += 1
                if p.progress >= TPC:
                    p.moving, p.progress = False, 0
        for b in list(self.bombs.values()):
            b.fuse -= 1
            if b.fuse <= 0:
                self.detonate(b)
        for p in self.players.values():
            if p.alive and any(f[0] == p.x and f[1] == p.y for f in self.flames):
                p.alive = False
        self.tick += 1

    def detonate(self, b):
        if self.bombs.pop(b.id, None) is None:
            return                                   # bereits (per Kette) gezündet
        cells = [(b.x, b.y)]
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            for r in range(1, b.flame + 1):
                x, y = b.x + dx * r, b.y + dy * r
                if self.tiles[y][x] == TILE_WALL:
                    break
                cells.append((x, y))
                if self.tiles[y][x] == TILE_SOFT:
                    self.tiles[y][x] = TILE_FREE
                    break
        for (x, y) in cells:
            self.flames.append([x, y, FLAME_DUR])
        # Kettenreaktion: getroffene Bomben zünden im selben Tick mit (BOT_GUIDE §7)
        for other in list(self.bombs.values()):
            if (other.x, other.y) in cells:
                self.detonate(other)

    def run(self):
        print(f"Test-Server läuft auf {self.sock.getsockname()} (Strg+C beendet)")
        period = 1.0 / TICK_RATE
        next_t = time.monotonic()
        while True:
            for data, addr in self.recv():
                self.handle(data, addr)
            if self.started:
                self.step()
                # KEYFRAME alle 30 Ticks, dazwischen echte DELTAs gegen den zuletzt
                # gesendeten Zustand (base_tick = last_sent).
                if self.tick % 30 == 0 or not self.prev_tiles:
                    self.broadcast(self.keyframe())
                    self.snapshot_prev()
                    self.last_sent = self.tick
                else:
                    self.broadcast(self.delta_frame())
                    self.snapshot_prev()
                    self.last_sent = self.tick
            next_t += period
            time.sleep(max(0, next_t - time.monotonic()))


def main():
    ap = argparse.ArgumentParser(description="Minimaler Bomberman-Test-Server")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=47800)
    ap.add_argument("--drop", type=float, default=0.0, help="Anteil verworfener Pakete (0..1)")
    ap.add_argument("--shuffle", action="store_true", help="Reihenfolge eingehender Pakete mischen")
    ap.add_argument("--seed", type=int, default=None, help="Karten-Seed (reproduzierbare Karte)")
    args = ap.parse_args()
    if args.seed is not None:
        random.seed(args.seed)
    try:
        Server(args.host, args.port, args.drop, args.shuffle).run()
    except KeyboardInterrupt:
        print("\nBeendet.")


if __name__ == "__main__":
    main()
