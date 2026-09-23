"""Tests für die Bot-Strategie (reine Logik, ohne pygame)."""

from bomberman_client import bot
from bomberman_client.protocol import Action
from bomberman_client.state import (
    Bomb,
    Flame,
    GameState,
    Player,
    PowerUp,
    TILE_FREE,
    TILE_SOFT,
    TILE_WALL,
)
from bomberman_client.track import TrackState


def make_track(state: GameState, my_id: int = 0) -> TrackState:
    t = TrackState()
    t.state = state
    t.my_id = my_id
    return t


def open_field(w: int, h: int) -> list[list[int]]:
    """Freies Feld mit umlaufender Wand."""
    tiles = [[TILE_FREE] * w for _ in range(h)]
    for x in range(w):
        tiles[0][x] = tiles[h - 1][x] = TILE_WALL
    for y in range(h):
        tiles[y][0] = tiles[y][w - 1] = TILE_WALL
    return tiles


def me_at(x, y, flame=2, bombs_max=1):
    return Player(0, True, False, x, y, 0, 0, bombs_max, flame, 0, 0)


def test_flees_from_flame():
    state = GameState(7, 3, open_field(7, 3))
    state.players[0] = me_at(3, 1)
    state.flames.append(Flame(3, 1, 10))       # steht in der Flamme
    action = bot.decide(make_track(state))
    # bewegt sich weg (nach links oder rechts), nicht NOOP/Bombe
    assert action in (Action.LEFT, Action.RIGHT, Action.UP, Action.DOWN)


def test_places_bomb_next_to_crate_with_escape():
    # 2D-Feld, damit ein Fluchtweg quer zur Bombenlinie existiert.
    state = GameState(7, 5, open_field(7, 5))
    state.tiles[2][4] = TILE_SOFT              # Kiste rechts neben der Figur
    state.players[0] = me_at(3, 2)
    action = bot.decide(make_track(state))
    # Kombi-Aktion: Bombe legen und ausweichen (Codes 6..9)
    assert action in (Action.UP_BOMB, Action.DOWN_BOMB, Action.LEFT_BOMB, Action.RIGHT_BOMB)


def test_waits_when_no_safe_move():
    # 1x1 begehbare Zelle, ringsum Wand, Figur steht in Gefahr → kein sicherer Zug
    tiles = [[TILE_WALL, TILE_WALL, TILE_WALL],
             [TILE_WALL, TILE_FREE, TILE_WALL],
             [TILE_WALL, TILE_WALL, TILE_WALL]]
    state = GameState(3, 3, tiles)
    state.players[0] = me_at(1, 1)
    state.flames.append(Flame(1, 1, 10))
    assert bot.decide(make_track(state)) == Action.NOOP


def test_moves_toward_crate_when_not_adjacent():
    state = GameState(9, 3, open_field(9, 3))
    state.tiles[1][6] = TILE_SOFT              # Kiste weiter rechts
    state.players[0] = me_at(2, 1)
    action = bot.decide(make_track(state))
    assert action == Action.RIGHT              # läuft Richtung Kiste


def test_dead_player_does_nothing():
    state = GameState(5, 3, open_field(5, 3))
    p = me_at(2, 1)
    p.alive = False
    state.players[0] = p
    assert bot.decide(make_track(state)) == Action.NOOP


def test_does_not_bomb_without_escape():
    # Figur in Sackgasse neben Kiste; nach eigener Bombe kein sicheres Nachbarfeld
    tiles = [[TILE_WALL, TILE_WALL, TILE_WALL, TILE_WALL],
             [TILE_WALL, TILE_FREE, TILE_SOFT, TILE_WALL],
             [TILE_WALL, TILE_WALL, TILE_WALL, TILE_WALL]]
    state = GameState(4, 3, tiles)
    state.players[0] = me_at(1, 1, flame=3)
    action = bot.decide(make_track(state))
    # kein Bombenwurf ohne Fluchtweg → keine Kombi-Aktion
    assert action not in (Action.BOMB, Action.UP_BOMB, Action.DOWN_BOMB,
                          Action.LEFT_BOMB, Action.RIGHT_BOMB)
