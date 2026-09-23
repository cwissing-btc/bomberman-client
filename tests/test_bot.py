"""Tests für die zeitbewusste Bot-Strategie (reine Logik, ohne pygame)."""

import pytest

from bomberman_client import bot
from bomberman_client.protocol import Action
from bomberman_client.state import (
    Bomb,
    Flame,
    GameState,
    MatchInfo,
    Player,
    PowerUp,
    Rules,
    POWERUP_FLAME,
    TILE_FREE,
    TILE_SOFT,
    TILE_WALL,
)
from bomberman_client.track import TrackState

MOVES = (Action.UP, Action.DOWN, Action.LEFT, Action.RIGHT)
BOMBS = (Action.BOMB, Action.UP_BOMB, Action.DOWN_BOMB, Action.LEFT_BOMB, Action.RIGHT_BOMB)


@pytest.fixture(autouse=True)
def _fresh_bot():
    bot.reset()


def make_track(state: GameState, my_id: int = 0, rules: Rules | None = None) -> TrackState:
    t = TrackState()
    t.state = state
    t.my_id = my_id
    if rules is not None:
        t.match = MatchInfo(state.width, state.height, [], rules, my_id)
    return t


def open_field(w: int, h: int) -> list[list[int]]:
    """Freies Feld mit umlaufender Wand."""
    tiles = [[TILE_FREE] * w for _ in range(h)]
    for x in range(w):
        tiles[0][x] = tiles[h - 1][x] = TILE_WALL
    for y in range(h):
        tiles[y][0] = tiles[y][w - 1] = TILE_WALL
    return tiles


def me_at(x, y, flame=2, bombs_max=1, speed=0):
    return Player(0, True, False, x, y, 0, 0, bombs_max, flame, speed, 0)


def enemy_at(pid, x, y, flame=2):
    return Player(pid, True, False, x, y, 0, 0, 1, flame, 0, 0)


# --- Grundverhalten (aus US3) --------------------------------------------------

def test_flees_from_flame():
    state = GameState(7, 3, open_field(7, 3))
    state.players[0] = me_at(3, 1)
    state.flames.append(Flame(3, 1, 10))
    assert bot.decide(make_track(state)) in MOVES


def test_places_bomb_next_to_crate_with_escape():
    state = GameState(7, 5, open_field(7, 5))
    state.tiles[2][4] = TILE_SOFT
    state.players[0] = me_at(3, 2)
    assert bot.decide(make_track(state)) in BOMBS[1:]      # Kombi-Aktion


def test_waits_when_no_safe_move():
    tiles = [[TILE_WALL] * 3, [TILE_WALL, TILE_FREE, TILE_WALL], [TILE_WALL] * 3]
    state = GameState(3, 3, tiles)
    state.players[0] = me_at(1, 1)
    state.flames.append(Flame(1, 1, 10))
    assert bot.decide(make_track(state)) == Action.NOOP


def test_moves_toward_crate_when_not_adjacent():
    state = GameState(9, 3, open_field(9, 3))
    state.tiles[1][6] = TILE_SOFT
    state.players[0] = me_at(2, 1)
    assert bot.decide(make_track(state)) == Action.RIGHT


def test_dead_player_does_nothing():
    state = GameState(5, 3, open_field(5, 3))
    p = me_at(2, 1)
    p.alive = False
    state.players[0] = p
    assert bot.decide(make_track(state)) == Action.NOOP


def test_does_not_bomb_without_escape():
    tiles = [[TILE_WALL] * 4,
             [TILE_WALL, TILE_FREE, TILE_SOFT, TILE_WALL],
             [TILE_WALL] * 4]
    state = GameState(4, 3, tiles)
    state.players[0] = me_at(1, 1, flame=3)
    assert bot.decide(make_track(state)) not in BOMBS


# --- Zeit, Radius, Kettenreaktion ------------------------------------------------

def test_chain_reaction_shortens_fuse():
    # A (Zündschnur 2) trifft B (Zündschnur 100) → B zündet mit A; B trifft (5,1).
    state = GameState(9, 3, open_field(9, 3))
    state.players[1] = enemy_at(1, 1, 1)                 # steht zufällig auf Bombe A
    state.bombs[1] = Bomb(1, 1, 1, 1, 2)
    state.bombs[2] = Bomb(2, 1, 3, 1, 100)
    intervals = bot._danger_intervals(state, Rules(), None)
    starts = [s for s, _ in intervals[(5, 1)]]
    # B zündet mit A (Tick 2, minus Sicherheitsmarge) – nicht erst bei ~100
    assert min(starts) == max(0, 2 - bot.SAFETY_MARGIN_TICKS)
    assert all(s < 90 for s in starts)


def test_stale_fuse_is_aged_by_elapsed_ticks():
    # Bombe mit fuse 100, gesehen bei Tick 0. Bei Tick 95 sind real nur noch 5 Ticks übrig.
    state = GameState(9, 3, open_field(9, 3))
    state.players[1] = enemy_at(1, 1, 1)
    state.bombs[1] = Bomb(1, 1, 1, 1, 100, seen_tick=0)
    fresh = bot._danger_intervals(state, Rules(), None, now_tick=0)
    aged = bot._danger_intervals(state, Rules(), None, now_tick=95)
    assert min(s for s, _ in fresh[(2, 1)]) == 100 - bot.SAFETY_MARGIN_TICKS
    assert min(s for s, _ in aged[(2, 1)]) == max(0, 5 - bot.SAFETY_MARGIN_TICKS)


def test_uses_owners_current_flame_radius():
    # Gegner hat per Power-up Reichweite 5: seine Bombe auf (1,1) erreicht (2..6,1).
    # (7,1) liegt außerhalb → dorthin fliehen. Mit Radius 2 gäbe es keinen Grund zu gehen.
    state = GameState(9, 3, open_field(9, 3))
    state.players[0] = me_at(5, 1)
    state.players[1] = enemy_at(1, 1, 1, flame=5)        # steht auf seiner Bombe
    state.bombs[1] = Bomb(1, 1, 1, 1, 50)
    assert bot.decide(make_track(state)) == Action.RIGHT


def test_unknown_owner_assumes_max_flame():
    state = GameState(9, 3, open_field(9, 3))
    state.bombs[1] = Bomb(1, 9, 1, 1, 50)                # Besitzer 9 unbekannt
    intervals = bot._danger_intervals(state, Rules(), None)
    assert (7, 1) in intervals                           # max_flame 6 → bis x=7


def test_runs_through_bomb_line_when_there_is_time():
    # Einziger Ausgang liegt hinter einer Bombenlinie, die erst in 60 Ticks zündet.
    # 4 Schritte à 8 Ticks = 32 Ticks → schaffbar → nach rechts durchlaufen.
    tiles = open_field(9, 5)
    for x in range(1, 8):
        tiles[2][x] = TILE_WALL                          # Trennwand ...
    tiles[2][7] = TILE_FREE                              # ... mit Durchgang bei x=7
    state = GameState(9, 5, tiles)
    state.players[0] = me_at(3, 1)
    state.players[1] = enemy_at(1, 1, 3, flame=6)
    state.bombs[1] = Bomb(1, 1, 1, 1, 60)                # trifft ganze Zeile y=1
    assert bot.decide(make_track(state)) == Action.RIGHT


def test_no_bomb_when_escape_is_too_slow():
    # 1 Feld breiter Gang, Reichweite 6: Flucht braucht 7 Schritte – Zündschnur 30 Ticks
    # reicht nur für 3 Schritte → keine Bombe.
    tiles = [[TILE_WALL] * 14, [TILE_WALL] + [TILE_FREE] * 12 + [TILE_WALL], [TILE_WALL] * 14]
    tiles[1][12] = TILE_SOFT
    state = GameState(14, 3, tiles)
    state.players[0] = me_at(11, 1, flame=6)
    slow = Rules(bomb_fuse_ticks=30)
    assert bot.decide(make_track(state, rules=slow)) not in BOMBS
    # Mit normaler Zündschnur (120 Ticks = 15 Schritte) ist dieselbe Bombe sicher legbar.
    bot.reset()
    assert bot.decide(make_track(state, rules=Rules())) in BOMBS[1:]


def test_bomb_action_is_not_repeated_blindly():
    # Gleicher Server-Tick (z. B. verlorenes DELTA): nur die Bewegung wiederholen, keine Bombe.
    state = GameState(7, 5, open_field(7, 5))
    state.tiles[2][4] = TILE_SOFT
    state.players[0] = me_at(3, 2)
    track = make_track(state)
    track.at_tick = 100
    first = bot.decide(track)
    assert first in BOMBS[1:]
    assert bot.decide(track) == bot._WITHOUT_BOMB[first]      # Wiederholung ohne Bombe
    track.at_tick = 102                                       # neuer Tick, BOMB_ADD fehlt noch
    assert bot.decide(track) not in BOMBS                     # Wartezeit → nicht nachlegen
    track.at_tick = 100 + bot.BOMB_COOLDOWN_TICKS
    assert bot.decide(track) in BOMBS[1:]                     # danach wieder erlaubt


def test_replay_follows_planned_path_by_wall_clock():
    # Bombe rechts neben Kiste: Plan = UP_BOMB nach (3,1), dann LEFT nach (2,1) aus der Linie.
    # Friert der Zustand ein, wird der Pfad nach Wanduhr weiterverfolgt (8 Ticks = 0,133 s).
    state = GameState(7, 5, open_field(7, 5))
    state.tiles[2][4] = TILE_SOFT
    state.players[0] = me_at(3, 2)
    track = make_track(state)
    track.at_tick = 100
    assert bot.decide(track, now=10.0) == Action.UP_BOMB
    assert bot.decide(track, now=10.0) == Action.UP          # Schritt 1 (ohne Bombe)
    assert bot.decide(track, now=10.2) == Action.LEFT        # Schritt 2 aus der Bombenlinie
    # Letzter Schritt: ab der zweiten Slot-Hälfte NOOP, damit die Figur nicht überschießt
    step_s = 8 / 60
    assert bot.decide(track, now=10.0 + 1 / 60 + step_s * 1.7) == Action.NOOP
    assert bot.decide(track, now=15.0) == Action.NOOP        # Plan abgearbeitet → warten


def test_threat_cells_use_enemy_flame_and_capacity():
    state = GameState(9, 3, open_field(9, 3))
    state.players[0] = me_at(6, 1)
    state.players[1] = enemy_at(1, 1, 1, flame=3)         # kann sofort bomben: Linie bis x=4
    assert (4, 1) in bot.threat_cells(state, 0) and (5, 1) not in bot.threat_cells(state, 0)
    state.bombs[7] = Bomb(7, 1, 3, 1, 100)                # seine einzige Bombe liegt schon
    assert bot.threat_cells(state, 0) == set()            # keine Kapazität → keine Bedrohung


def test_escape_prefers_haven_outside_enemy_line():
    # Flamme unter mir; vier gleich nahe Häfen. Gegner bei (1,1) mit Reichweite 2 deckt (2,1)
    # und (1,2) ab → nur unten oder rechts liegen außerhalb seiner Bombenlinie.
    state = GameState(5, 5, open_field(5, 5))
    state.players[0] = me_at(2, 2)
    state.players[1] = enemy_at(1, 1, 1, flame=2)
    state.flames.append(Flame(2, 2, 10))
    assert bot.decide(make_track(state)) in (Action.DOWN, Action.RIGHT)


def test_prefers_reachable_powerup():
    state = GameState(9, 5, open_field(9, 5))
    state.players[0] = me_at(2, 2)
    state.powerups[1] = PowerUp(1, 5, 2, POWERUP_FLAME)
    assert bot.decide(make_track(state)) == Action.RIGHT


def test_closing_order_matches_server():
    # 7x5 → 15 Innenzellen: oben → rechts → unten (rückwärts) → links (aufwärts) → innen
    order = bot.closing_order(7, 5)
    assert order[:5] == [(1, 1), (2, 1), (3, 1), (4, 1), (5, 1)]
    assert order[5:7] == [(5, 2), (5, 3)]
    assert order[7:11] == [(4, 3), (3, 3), (2, 3), (1, 3)]
    assert order[11] == (1, 2)
    assert order[12:] == [(2, 2), (3, 2), (4, 2)]


def test_sudden_death_moves_inward():
    # 30 Ticks vor Sudden Death: (1,1) schließt als Erstes (+30), (2,1) bei +36,
    # (1,2) erst bei +96. Kein Feld bleibt lange sicher → am längsten überlebt, wer nach
    # innen läuft; stehen bleiben wäre nach 30 Ticks tödlich.
    rules = Rules(round_time_ticks=10800, sudden_death_tick=7200)
    state = GameState(7, 5, open_field(7, 5))
    state.ticks_remaining = 10800 - (7200 - 30)
    state.players[0] = me_at(1, 1)
    assert bot.decide(make_track(state, rules=rules)) in (Action.RIGHT, Action.DOWN)
