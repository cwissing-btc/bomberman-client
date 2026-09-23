"""Darstellung mit pygame. Zeichnet nur den vom Server erhaltenen Zustand (Prinzip II).

Zeichenreihenfolge nach VISUALIZER_GUIDE.md §4.5: Boden → Kisten → Wände → Power-ups → Bomben →
Flammen → Spieler (nach y sortiert) → Overlay. Alle Assets sind 64×64, kein Smoothing (Pixelart).
"""

from __future__ import annotations

import pygame

from .assets import TILE_SIZE, Assets
from .state import (
    GameState,
    POWERUP_EXTRA_BOMB,
    POWERUP_FLAME,
    POWERUP_SPEED,
    TILE_FREE,
    TILE_SOFT,
    TILE_WALL,
)

# Spieler-ID → Farbvariante der Figur (Asset-Pack v2: player_{blue,red,yellow,purple}_*)
PLAYER_SPRITE = ["blue", "red", "yellow", "purple"]
PLAYER_COLORS = [(70, 130, 240), (230, 70, 70), (235, 200, 60), (170, 80, 220)]
_FACING_GROUP = {0: "down", 1: "up", 2: "left", 3: "right"}
_POWERUP_GROUP = {
    POWERUP_EXTRA_BOMB: "item_bomb_up_hover",
    POWERUP_FLAME: "item_fire_up_hover",
    POWERUP_SPEED: "item_speed_up_hover",
}
_BG = (24, 24, 28)
_TEXT = (235, 235, 235)


class Renderer:
    def __init__(self, assets: Assets) -> None:
        self.assets = assets
        if not pygame.font.get_init():
            pygame.font.init()
        self.font = pygame.font.SysFont("monospace", 18)
        self.big = pygame.font.SysFont("monospace", 32, bold=True)

    # --- Match ---------------------------------------------------------------

    def render_game(self, surface: pygame.Surface, gs: GameState, my_id: int | None,
                    now: float) -> None:
        surface.fill(_BG)
        self._draw_tiles(surface, gs, now)
        for pu in gs.powerups.values():
            self._blit(surface, self.assets.frame_for(
                _POWERUP_GROUP.get(pu.kind, "item_bomb_up_hover"), now), pu.x, pu.y)
        for bomb in gs.bombs.values():
            self._blit(surface, self.assets.frame_for("bomb_tick", now), bomb.x, bomb.y)
        for flame in gs.flames:
            self._blit(surface, self.assets.frame_for("expl_center", now), flame.x, flame.y)
        for player in sorted(gs.players.values(), key=lambda p: p.y):
            if player.alive:
                self._draw_player(surface, player, my_id, now)

    def _draw_tiles(self, surface: pygame.Surface, gs: GameState, now: float) -> None:
        for y in range(gs.height):
            for x in range(gs.width):
                floor = "floor_1" if (x + y) % 2 else "floor_0"
                self._blit(surface, self.assets.frame(floor), x, y)
                tile = gs.tiles[y][x]
                if tile == TILE_SOFT:
                    self._blit(surface, self.assets.frame("crate"), x, y)
                elif tile == TILE_WALL:
                    self._blit(surface, self.assets.frame("wall_solid"), x, y)
                elif tile not in (TILE_FREE, TILE_SOFT, TILE_WALL):
                    self._blit(surface, self.assets.frame("__unknown__"), x, y)

    def _draw_player(self, surface: pygame.Surface, player, my_id, now: float) -> None:
        # Eigene Figur hervorheben (die Farbe trägt die Figur selbst)
        if player.id == my_id:
            cx = player.x * TILE_SIZE + TILE_SIZE // 2
            cy = player.y * TILE_SIZE + TILE_SIZE - 8
            pygame.draw.ellipse(surface, _TEXT, (cx - 20, cy - 8, 40, 16), 2)
        # Figur: Farbvariante nach Spieler-ID, Blickrichtung aus facing
        color = PLAYER_SPRITE[player.id % len(PLAYER_SPRITE)]
        direction = _FACING_GROUP.get(player.facing, "down")
        if player.moving:
            group = f"player_{color}_walk_{direction}"
            progress = (player.move_progress % 8) / 8.0
            sprite = self.assets.frame_for_progress(group, progress)
        else:
            sprite = self.assets.frame_for(f"player_{color}_idle_{direction}", now)
        self._blit(surface, sprite, player.x, player.y)

    def _blit(self, surface: pygame.Surface, sprite: pygame.Surface, gx: int, gy: int) -> None:
        # Sprites unten-mittig auf der Zelle verankern (VISUALIZER_GUIDE.md §4.5)
        rect = sprite.get_rect()
        px = gx * TILE_SIZE + (TILE_SIZE - rect.width) // 2
        py = gy * TILE_SIZE + (TILE_SIZE - rect.height)
        surface.blit(sprite, (px, py))

    # --- Overlays ------------------------------------------------------------

    def render_overlay(self, surface: pygame.Surface, lines: list[str]) -> None:
        y = 6
        for line in lines:
            shadow = self.font.render(line, True, (0, 0, 0))
            text = self.font.render(line, True, _TEXT)
            surface.blit(shadow, (9, y + 1))
            surface.blit(text, (8, y))
            y += 22

    def render_center_message(self, surface: pygame.Surface, title: str,
                              subtitle: str = "") -> None:
        surface.fill(_BG)
        w, h = surface.get_size()
        t = self.big.render(title, True, _TEXT)
        surface.blit(t, (w // 2 - t.get_width() // 2, h // 2 - t.get_height()))
        if subtitle:
            s = self.font.render(subtitle, True, _TEXT)
            surface.blit(s, (w // 2 - s.get_width() // 2, h // 2 + 8))

    def render_lobby(self, surface: pygame.Surface, lobby, my_id: int | None) -> None:
        surface.fill(_BG)
        states = {0: "offen", 1: "gesperrt", 2: "Countdown", 3: "läuft", 4: "beendet"}
        title = self.big.render("Lobby", True, _TEXT)
        surface.blit(title, (24, 20))
        info = f"Status: {states.get(lobby.state, '?')}   " \
               f"Spieler: {lobby.players_connected}/{lobby.max_players}"
        if lobby.state == 2:
            info += f"   Start in {lobby.countdown_ticks // 60 + 1}s"
        surface.blit(self.font.render(info, True, _TEXT), (24, 70))
        y = 110
        for slot in lobby.slots():
            marker = "→ " if slot.id == my_id else "  "
            status = "belegt" if slot.connected else "frei"
            color = PLAYER_COLORS[slot.id % len(PLAYER_COLORS)] if slot.connected else (120, 120, 120)
            pygame.draw.rect(surface, color, (24, y + 2, 16, 16))
            surface.blit(self.font.render(f"{marker}Platz {slot.id}: {status}", True, _TEXT),
                         (48, y))
            y += 28
        hint = "Warte auf Matchstart durch den Moderator …"
        surface.blit(self.font.render(hint, True, (170, 170, 170)), (24, y + 16))
