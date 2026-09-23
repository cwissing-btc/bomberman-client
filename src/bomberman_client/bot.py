"""Einfacher Bot: wählt pro Zustand eine Aktion für die EIGENE Figur (Prinzip II).

Der Bot trifft keine Spielentscheidungen – er sagt nur Gefahr voraus, um zu wählen, *welche*
Aktion (dieselben Codes wie beim Menschen) er sendet. Strategie (research.md R12):
Gefahr meiden → Bombe+Ausweichen neben Kiste/Gegner → sicheres Power-up → zur nächsten Kiste →
sonst warten.
"""

from __future__ import annotations

from collections import deque

from .protocol import Action
from .state import TILE_FREE, TILE_SOFT, TILE_WALL, GameState
from .track import TrackState

DIRS = [(0, -1), (0, 1), (-1, 0), (1, 0)]
_STEP = {(0, -1): Action.UP, (0, 1): Action.DOWN, (-1, 0): Action.LEFT, (1, 0): Action.RIGHT}
_STEP_BOMB = {(0, -1): Action.UP_BOMB, (0, 1): Action.DOWN_BOMB,
              (-1, 0): Action.LEFT_BOMB, (1, 0): Action.RIGHT_BOMB}
_DEFAULT_RADIUS = 2


def walkable(state: GameState, x: int, y: int) -> bool:
    """Begehbar: freies Feld in Grenzen und keine Bombe darauf."""
    if not (0 <= x < state.width and 0 <= y < state.height):
        return False
    if state.tiles[y][x] != TILE_FREE:
        return False
    return not any(b.x == x and b.y == y for b in state.bombs.values())


def blast_cells(state: GameState, bx: int, by: int, radius: int) -> set[tuple[int, int]]:
    """Zellen, die eine Bombe auf (bx,by) mit Reichweite ``radius`` treffen würde."""
    cells = {(bx, by)}
    for dx, dy in DIRS:
        for r in range(1, radius + 1):
            x, y = bx + dx * r, by + dy * r
            if not (0 <= x < state.width and 0 <= y < state.height):
                break
            if state.tiles[y][x] == TILE_WALL:
                break
            cells.add((x, y))
            if state.tiles[y][x] == TILE_SOFT:
                break  # Kiste stoppt die Explosion (Zelle noch getroffen)
    return cells


def danger_cells(state: GameState) -> set[tuple[int, int]]:
    """Aktuell tödliche Flammen plus vorhergesagter Wirkungsbereich aller Bomben."""
    danger: set[tuple[int, int]] = {(f.x, f.y) for f in state.flames}
    for bomb in state.bombs.values():
        owner = state.players.get(bomb.owner)
        radius = owner.flame if owner else _DEFAULT_RADIUS
        danger |= blast_cells(state, bomb.x, bomb.y, radius)
    return danger


def bfs(state: GameState, start: tuple[int, int], goal_pred, avoid: set) -> list[tuple[int, int]]:
    """Kürzester Pfad (ohne Startzelle) zur ersten Zelle mit ``goal_pred``; sonst []."""
    queue = deque([start])
    came_from = {start: None}
    while queue:
        cur = queue.popleft()
        if cur != start and goal_pred(cur):
            path = []
            while cur != start:
                path.append(cur)
                cur = came_from[cur]
            path.reverse()
            return path
        cx, cy = cur
        for dx, dy in DIRS:
            nxt = (cx + dx, cy + dy)
            if nxt in came_from or nxt in avoid:
                continue
            if not walkable(state, nxt[0], nxt[1]):
                continue
            came_from[nxt] = cur
            queue.append(nxt)
    return []


def _has_soft_neighbor(state: GameState, cell: tuple[int, int]) -> bool:
    x, y = cell
    for dx, dy in DIRS:
        nx, ny = x + dx, y + dy
        if 0 <= nx < state.width and 0 <= ny < state.height and state.tiles[ny][nx] == TILE_SOFT:
            return True
    return False


def _adjacent_target(state: GameState, x: int, y: int, my_id: int) -> bool:
    """Steht die Figur neben einer Kiste oder einem lebenden Gegner?"""
    for dx, dy in DIRS:
        nx, ny = x + dx, y + dy
        if 0 <= nx < state.width and 0 <= ny < state.height:
            if state.tiles[ny][nx] == TILE_SOFT:
                return True
        for p in state.players.values():
            if p.id != my_id and p.alive and (p.x, p.y) == (nx, ny):
                return True
    return False


def _step_action(frm: tuple[int, int], to: tuple[int, int]) -> Action:
    return _STEP[(to[0] - frm[0], to[1] - frm[1])]


def decide(track: TrackState, now: float = 0.0) -> Action:
    """Wählt die nächste Aktion des Bots (FR-012/013/014)."""
    state = track.state
    if state is None or track.my_id is None:
        return Action.NOOP
    me = state.players.get(track.my_id)
    if me is None or not me.alive:
        return Action.NOOP

    danger = danger_cells(state)
    here = (me.x, me.y)

    # 1) In Gefahr → schnellstmöglich auf ein sicheres Feld
    if here in danger:
        path = bfs(state, here, lambda c: c not in danger, avoid=set())
        return _step_action(here, path[0]) if path else Action.NOOP

    # 2) Neben Kiste/Gegner und Bombe noch frei → Bombe legen und ausweichen.
    #    Der erste Schritt bleibt zwangsläufig in der Bombenlinie; entscheidend ist, dass von
    #    dort ein Weg AUS dem Explosionsbereich existiert (sonst nicht bomben).
    my_bombs = sum(1 for b in state.bombs.values() if b.owner == track.my_id)
    if my_bombs < max(1, me.bombs_max) and _adjacent_target(state, me.x, me.y, track.my_id):
        new_blast = blast_cells(state, me.x, me.y, me.flame or _DEFAULT_RADIUS)
        unsafe = new_blast | danger
        for dx, dy in DIRS:
            nx, ny = me.x + dx, me.y + dy
            if not walkable(state, nx, ny) or (nx, ny) in danger:
                continue
            if (nx, ny) not in unsafe or bfs(state, (nx, ny),
                                             lambda c: c not in unsafe, avoid=danger):
                return _STEP_BOMB[(dx, dy)]

    # 3) Sicher erreichbares Power-up einsammeln
    if state.powerups:
        targets = {(pu.x, pu.y) for pu in state.powerups.values()}
        path = bfs(state, here, lambda c: c in targets, avoid=danger)
        if path:
            return _step_action(here, path[0])

    # 4) Zur nächsten Kiste laufen (um sie später zu sprengen)
    path = bfs(state, here, lambda c: _has_soft_neighbor(state, c), avoid=danger)
    if path:
        return _step_action(here, path[0])

    # 5) Kein sinnvoller/sicherer Zug → warten
    return Action.NOOP
