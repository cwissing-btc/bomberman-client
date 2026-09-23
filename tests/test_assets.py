"""Test: alle im Atlas genannten Frames sind ladbar (headless via SDL dummy)."""

import json
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from bomberman_client.assets import ASSETS_DIR, TILE_SIZE, load_sprites  # noqa: E402


def test_all_atlas_frames_loadable():
    pygame.display.init()
    pygame.display.set_mode((64, 64))
    try:
        assets = load_sprites()
        atlas = json.loads((ASSETS_DIR / "atlas.json").read_text(encoding="utf-8"))
        for name in atlas["frames"]:
            surf = assets.frame(name)
            assert surf.get_width() == TILE_SIZE
            assert surf.get_height() == TILE_SIZE
        # unbekannter Name → Platzhalter (kein KeyError)
        assert assets.frame("does_not_exist").get_size() == (TILE_SIZE, TILE_SIZE)
    finally:
        pygame.display.quit()
