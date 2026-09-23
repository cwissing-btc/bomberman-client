"""Datenmodell des Spielzustands.

Reine Datenklassen ohne pygame- oder Socket-Abhängigkeit (Constitution Prinzip V).
Der Zustand wird ausschließlich aus Server-Frames abgeleitet (Prinzip II): Ein KEYFRAME
ersetzt ihn vollständig, ein DELTA verändert einzelne Teile.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Feldtypen im 2-Bit-Kachelgitter (BOT_GUIDE.md §5.6)
TILE_FREE = 0
TILE_WALL = 1
TILE_SOFT = 2  # Kiste

# Power-up-Arten (BOT_GUIDE.md §5.4)
POWERUP_EXTRA_BOMB = 0
POWERUP_FLAME = 1
POWERUP_SPEED = 2


@dataclass
class Rules:
    """Regelblock aus MATCH_INIT (BOT_GUIDE.md §5.7) – nicht hartkodieren."""

    bomb_fuse_ticks: int = 120
    flame_duration_ticks: int = 30
    ticks_per_cell: int = 8
    speed_step_ticks: int = 1
    start_bombs: int = 1
    start_flame: int = 1
    max_flame: int = 6
    max_speed: int = 3
    powerup_chance_pct: int = 30
    round_time_ticks: int = 10800
    sudden_death_tick: int = 7200

    def ticks_to_cross(self, speed: int) -> int:
        return max(1, self.ticks_per_cell - self.speed_step_ticks * speed)


@dataclass
class MatchInfo:
    """Statische Matchdaten aus MATCH_INIT."""

    width: int
    height: int
    spawns: list[tuple[int, int]]
    rules: Rules
    my_id: int


@dataclass
class Player:
    id: int
    alive: bool
    moving: bool
    x: int
    y: int
    facing: int  # 0 down, 1 up, 2 left, 3 right
    move_progress: int
    bombs_max: int
    flame: int
    speed: int
    score: int


@dataclass
class Bomb:
    id: int
    owner: int
    x: int
    y: int
    fuse: int


@dataclass
class Flame:
    x: int
    y: int
    ticks: int


@dataclass
class PowerUp:
    id: int
    x: int
    y: int
    kind: int


@dataclass
class GameState:
    """Vollständiger, renderbarer Zustand eines Ticks."""

    width: int
    height: int
    tiles: list[list[int]]  # tiles[y][x]
    players: dict[int, Player] = field(default_factory=dict)
    bombs: dict[int, Bomb] = field(default_factory=dict)
    flames: list[Flame] = field(default_factory=list)
    powerups: dict[int, PowerUp] = field(default_factory=dict)
    ticks_remaining: int = 0

    def tile_at(self, x: int, y: int) -> int:
        if 0 <= y < self.height and 0 <= x < self.width:
            return self.tiles[y][x]
        return TILE_WALL

    def set_tile(self, x: int, y: int, tile: int) -> None:
        if 0 <= y < self.height and 0 <= x < self.width:
            self.tiles[y][x] = tile

    def apply_delta(self, records: list[tuple]) -> None:
        """Wendet die Delta-Records eines DELTA-Frames an (BOT_GUIDE.md §5.5).

        Jedes Record ist ein Tupel ``(tag, payload_dict)`` aus ``protocol.decode``.
        Unbekannte Tags werden ignoriert (FR-006).
        """
        for tag, r in records:
            if tag == 0x01:  # PLAYER_STATE
                p = self.players.get(r["id"])
                if p is not None:
                    p.alive = bool(r["flags"] & 1)
                    p.moving = bool(r["flags"] & 2)
                    p.x, p.y = r["x"], r["y"]
                    p.facing = r["dir"]
                    p.move_progress = r["progress"]
                else:
                    self.players[r["id"]] = Player(
                        r["id"], bool(r["flags"] & 1), bool(r["flags"] & 2),
                        r["x"], r["y"], r["dir"], r["progress"], 1, 1, 0, 0,
                    )
            elif tag == 0x02:  # PLAYER_STATS
                p = self.players.get(r["id"])
                if p is not None:
                    p.bombs_max = r["bombs_max"]
                    p.flame = r["flame"]
                    p.speed = r["speed"]
                    p.score = r["score"]
            elif tag == 0x03:  # BOMB_ADD
                self.bombs[r["id"]] = Bomb(r["id"], r["owner"], r["x"], r["y"], r["fuse"])
            elif tag == 0x04:  # BOMB_REMOVE
                self.bombs.pop(r["id"], None)
            elif tag == 0x06:  # TILE_SET
                self.set_tile(r["x"], r["y"], r["tile"])
            elif tag == 0x07:  # POWERUP_ADD
                self.powerups[r["id"]] = PowerUp(r["id"], r["x"], r["y"], r["kind"])
            elif tag == 0x08:  # POWERUP_REMOVE
                self.powerups.pop(r["id"], None)
            elif tag == 0x09:  # PLAYER_DEATH
                p = self.players.get(r["id"])
                if p is not None:
                    p.alive = False
            elif tag == 0x0A:  # FLAME_ADD
                self.flames.append(Flame(r["x"], r["y"], r["ticks"]))
            elif tag == 0x0B:  # FLAME_REMOVE
                self.flames = [f for f in self.flames if (f.x, f.y) != (r["x"], r["y"])]
            elif tag == 0x0C:  # TIMER
                self.ticks_remaining = r["ticks"]
            elif tag == 0x0D:  # WALL_CLOSED (Sudden Death) → Feld wird feste Wand
                self.set_tile(r["x"], r["y"], TILE_WALL)
            # 0x05 EXPLOSION: nur Animation, kein Zustand
