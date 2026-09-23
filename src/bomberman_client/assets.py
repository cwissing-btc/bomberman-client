"""Laden und Bereitstellen der Team-Sprites (assets/spritesheet.png + atlas.json).

Alle Frames sind 64×64. Das Spritesheet wird einmal geladen und in einzelne Surfaces
geschnitten; der Zugriff erfolgt über den Frame-Namen. Animationen kommen aus atlas.json.
"""

from __future__ import annotations

import json
from pathlib import Path

import pygame

TILE_SIZE = 64

# assets/ liegt im Projektwurzelverzeichnis (drei Ebenen über dieser Datei:
# src/bomberman_client/assets.py -> Repo-Wurzel)
ASSETS_DIR = Path(__file__).resolve().parents[2] / "assets"

_MAGENTA = (255, 0, 255)


class Assets:
    def __init__(self, frames: dict[str, pygame.Surface], animations: dict[str, dict]) -> None:
        self.frames = frames
        self.animations = animations
        self._placeholder = pygame.Surface((TILE_SIZE, TILE_SIZE))
        self._placeholder.fill(_MAGENTA)

    def frame(self, name: str) -> pygame.Surface:
        """Frame nach Namen; unbekannt → Magenta-Platzhalter (FR-006/Edge Case)."""
        return self.frames.get(name, self._placeholder)

    def frame_for(self, group: str, now: float) -> pygame.Surface:
        """Zeitbasierter Animationsframe einer atlas-Gruppe."""
        anim = self.animations.get(group)
        if not anim:
            return self.frame(group)
        names = anim["frames"]
        fps = anim.get("fps", 10)
        idx = int(now * fps) % len(names)
        return self.frame(names[idx])

    def frame_for_progress(self, group: str, progress: float) -> pygame.Surface:
        """Animationsframe aus einem Fortschritt 0..1 (an die Simulation gekoppelt)."""
        anim = self.animations.get(group)
        if not anim:
            return self.frame(group)
        names = anim["frames"]
        idx = min(int(progress * len(names)), len(names) - 1)
        return self.frame(names[idx])


def load_sprites(assets_dir: Path | None = None) -> Assets:
    """Lädt Spritesheet + Atlas und schneidet alle Frames aus."""
    base = assets_dir or ASSETS_DIR
    atlas = json.loads((base / "atlas.json").read_text(encoding="utf-8"))
    sheet = pygame.image.load(str(base / "spritesheet.png")).convert_alpha()

    frames: dict[str, pygame.Surface] = {}
    for name, rect in atlas["frames"].items():
        surf = pygame.Surface((rect["w"], rect["h"]), pygame.SRCALPHA)
        surf.blit(sheet, (0, 0), (rect["x"], rect["y"], rect["w"], rect["h"]))
        frames[name] = surf

    return Assets(frames, atlas.get("animations", {}))
