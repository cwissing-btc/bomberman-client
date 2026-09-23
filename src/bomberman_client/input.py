"""Abbildung gedrückter Tasten auf einen Aktionscode (reine Logik, ohne pygame).

Getrennt von main.py, damit die Zuordnung ohne Fenster testbar ist (Prinzip V). main.py liest die
pygame-Tasten und ruft ``input_to_action`` mit einfachen Wahrheitswerten auf.
"""

from __future__ import annotations

from .protocol import Action


def input_to_action(up: bool, down: bool, left: bool, right: bool, bomb: bool) -> Action:
    """Ergibt genau eine Aktion pro Tick (FR-009/010).

    Richtung + Bombe ergibt die Kombi-Aktion (Bombe legen und im selben Tick weggehen,
    BOT_GUIDE.md §4). Bei gleichzeitig gedrückten Gegenrichtungen hat die zuerst geprüfte
    Achse Vorrang (oben vor unten, links vor rechts; vertikal vor horizontal).
    """
    direction = None
    if up:
        direction = "up"
    elif down:
        direction = "down"
    elif left:
        direction = "left"
    elif right:
        direction = "right"

    if bomb and direction == "up":
        return Action.UP_BOMB
    if bomb and direction == "down":
        return Action.DOWN_BOMB
    if bomb and direction == "left":
        return Action.LEFT_BOMB
    if bomb and direction == "right":
        return Action.RIGHT_BOMB
    if bomb:
        return Action.BOMB
    if direction == "up":
        return Action.UP
    if direction == "down":
        return Action.DOWN
    if direction == "left":
        return Action.LEFT
    if direction == "right":
        return Action.RIGHT
    return Action.NOOP
