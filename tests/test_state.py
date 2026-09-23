"""Tests für GameState.apply_delta (Keyframe-Ersetzung wird über decode getestet)."""

from bomberman_client.state import Bomb, Flame, GameState, Player, TILE_FREE, TILE_SOFT, TILE_WALL


def make_state():
    tiles = [[TILE_SOFT, TILE_FREE], [TILE_FREE, TILE_FREE]]
    gs = GameState(width=2, height=2, tiles=tiles)
    gs.players[0] = Player(0, True, False, 0, 0, 0, 0, 1, 1, 0, 0)
    return gs


def test_tile_set_updates_grid():
    gs = make_state()
    gs.apply_delta([(0x06, {"x": 0, "y": 0, "tile": TILE_FREE})])
    assert gs.tile_at(0, 0) == TILE_FREE


def test_bomb_add_and_remove():
    gs = make_state()
    gs.apply_delta([(0x03, {"id": 9, "owner": 0, "x": 1, "y": 1, "fuse": 100})], tick=500)
    assert 9 in gs.bombs and gs.bombs[9].fuse == 100
    assert gs.bombs[9].seen_tick == 500                  # Stempel für die Zähler-Alterung
    gs.apply_delta([(0x04, {"id": 9})])
    assert 9 not in gs.bombs


def test_flame_add_and_remove():
    gs = make_state()
    gs.apply_delta([(0x0A, {"x": 1, "y": 0, "ticks": 30})])
    assert any((f.x, f.y) == (1, 0) for f in gs.flames)
    gs.apply_delta([(0x0B, {"x": 1, "y": 0})])
    assert not gs.flames


def test_player_death_sets_alive_false():
    gs = make_state()
    gs.apply_delta([(0x09, {"id": 0, "killer": 0xFF})])
    assert gs.players[0].alive is False


def test_player_state_updates_position():
    gs = make_state()
    gs.apply_delta([(0x01, {"id": 0, "flags": 0b11, "x": 1, "y": 0, "dir": 3, "progress": 2})])
    assert (gs.players[0].x, gs.players[0].y) == (1, 0)
    assert gs.players[0].facing == 3 and gs.players[0].moving


def test_wall_closed_makes_tile_solid():
    gs = make_state()
    gs.apply_delta([(0x0D, {"x": 1, "y": 1})])   # Sudden Death
    assert gs.tile_at(1, 1) == TILE_WALL


def test_unknown_tag_is_ignored():
    gs = make_state()
    gs.apply_delta([(0xEE, {"foo": 1})])  # darf nicht crashen
    assert gs.players[0].alive
