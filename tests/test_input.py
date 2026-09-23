"""Tests für input_to_action (reine Logik, ohne pygame)."""

from bomberman_client.input import input_to_action
from bomberman_client.protocol import Action

N = dict(up=False, down=False, left=False, right=False, bomb=False)


def test_nothing_pressed_is_noop():
    assert input_to_action(**N) == Action.NOOP


def test_single_directions():
    assert input_to_action(**{**N, "up": True}) == Action.UP
    assert input_to_action(**{**N, "down": True}) == Action.DOWN
    assert input_to_action(**{**N, "left": True}) == Action.LEFT
    assert input_to_action(**{**N, "right": True}) == Action.RIGHT


def test_bomb_only():
    assert input_to_action(**{**N, "bomb": True}) == Action.BOMB


def test_combo_bomb_plus_direction():
    assert input_to_action(**{**N, "up": True, "bomb": True}) == Action.UP_BOMB
    assert input_to_action(**{**N, "down": True, "bomb": True}) == Action.DOWN_BOMB
    assert input_to_action(**{**N, "left": True, "bomb": True}) == Action.LEFT_BOMB
    assert input_to_action(**{**N, "right": True, "bomb": True}) == Action.RIGHT_BOMB


def test_vertical_has_priority_over_horizontal():
    assert input_to_action(**{**N, "up": True, "right": True}) == Action.UP


def test_opposing_directions_prefer_first_axis():
    # up + down -> up (oben zuerst geprüft); mit Bombe -> UP_BOMB
    assert input_to_action(**{**N, "up": True, "down": True}) == Action.UP
    assert input_to_action(**{**N, "left": True, "right": True, "bomb": True}) == Action.LEFT_BOMB
