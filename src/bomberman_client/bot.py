"""Zeitbewusster Bot: wählt pro Zustand eine Aktion für die EIGENE Figur (Prinzip II).

Der Bot trifft keine Spielentscheidungen – er sagt Gefahr voraus, um zu wählen, *welche* Aktion
(dieselben Codes wie beim Menschen) er sendet. Alle Regelkonstanten kommen aus ``MATCH_INIT``.

Modell
------
* Jede Zelle bekommt **Gefahren-Zeitfenster** ``[start, ende]`` (Ticks ab jetzt):
  aktive Flammen, vorhergesagte Explosionen aller Bomben (mit dem *aktuellen* Radius des
  jeweiligen Besitzers – Power-ups vergrößern ihn), **Kettenreaktionen** (eine Bombe im Radius
  einer früher zündenden zündet mit) und die Sudden-Death-Ringe.
* Bewegung: Ein Schritt dauert ``ticks_to_cross(speed)`` Ticks. Beim Server gilt die Figur ab
  Schrittbeginn als auf dem Zielfeld → ein Feld muss ab dem Moment sicher sein, in dem der
  Schritt startet, bis man es wieder verlassen kann.
* Wegsuche über (Zelle, Zeit) inkl. **Warten** als Zug. Ein „sicherer Hafen" ist eine Zelle, die
  ab Ankunft für einen ganzen Zünd-+Flammenzyklus ungefährlich bleibt.

Prioritäten: überleben → bomben (wenn lohnend UND Flucht *rechtzeitig* machbar) → Ziel
ansteuern (Power-up > Bombenplatz mit vielen Kisten/Gegnern) → warten.
"""

from __future__ import annotations

from collections import deque

from .protocol import Action
from .state import (
    POWERUP_EXTRA_BOMB,
    POWERUP_FLAME,
    POWERUP_SPEED,
    TILE_FREE,
    TILE_SOFT,
    TILE_WALL,
    GameState,
    Rules,
)
from .track import TrackState

DIRS = [(0, -1), (0, 1), (-1, 0), (1, 0)]
_STEP = {(0, -1): Action.UP, (0, 1): Action.DOWN, (-1, 0): Action.LEFT, (1, 0): Action.RIGHT}
_STEP_BOMB = {(0, -1): Action.UP_BOMB, (0, 1): Action.DOWN_BOMB,
              (-1, 0): Action.LEFT_BOMB, (1, 0): Action.RIGHT_BOMB}

INF = 1 << 30
K_MAX = 20                      # Planungstiefe in Schritten
SUDDEN_DEATH_TICKS_PER_CELL = 6  # BOT_GUIDE.md §7
_POWERUP_VALUE = {POWERUP_FLAME: 3.0, POWERUP_EXTRA_BOMB: 2.5, POWERUP_SPEED: 2.0}
_HYSTERESIS = 1.25              # Bonus für das zuletzt verfolgte Ziel (kein Flip-Flop)
BOMB_COOLDOWN_TICKS = 12        # nach einem Bombenbefehl auf BOMB_ADD warten, statt nachzulegen
MOVE_SETTLE_TICKS = 2           # nach einer gesendeten Bewegung so lange nicht bomben
SD_PREP_TICKS = 20 * 60         # so lange vor Sudden Death beginnt der Rückzug vom Rand
SD_DEEP_TICKS = 8 * 60          # „tiefer" Hafen: wird frühestens in 8 s zugemauert

# Bombe ist eine Einmal-Aktion: bei unverändertem Zustand nur die Bewegung wiederholen.
_WITHOUT_BOMB = {Action.BOMB: Action.NOOP, Action.UP_BOMB: Action.UP,
                 Action.DOWN_BOMB: Action.DOWN, Action.LEFT_BOMB: Action.LEFT,
                 Action.RIGHT_BOMB: Action.RIGHT}

_TICKS_PER_SECOND = 60          # feste Tickrate des Servers (BOT_GUIDE.md)

# Gedächtnis zwischen Ticks: zuletzt geplanter Pfad (für Koppelnavigation bei eingefrorenem
# Zustand), letztes Ziel, gesperrte Plätze, wann zuletzt eine Bombe angefordert wurde.
_memo: dict = {}


def reset() -> None:
    """Gedächtnis löschen (z. B. für Tests oder ein neues Match)."""
    _memo.clear()
    _memo.update({"tick": None, "action": Action.NOOP, "plan": [], "plan_start": None,
                  "plan_t0": 0.0, "plan_step_s": 8 / _TICKS_PER_SECOND, "plan_delay_s": 0.0,
                  "target": None, "banned": {}, "bomb_sent_tick": None,
                  "last_move_tick": None, "match_id": None})


reset()


# --- Geometrie ---------------------------------------------------------------

def walkable(state: GameState, x: int, y: int) -> bool:
    """Begehbar: freies Feld in Grenzen und keine Bombe darauf."""
    if not (0 <= x < state.width and 0 <= y < state.height):
        return False
    if state.tiles[y][x] != TILE_FREE:
        return False
    return not any(b.x == x and b.y == y for b in state.bombs.values())


def blast_cells(state: GameState, bx: int, by: int, radius: int) -> set[tuple[int, int]]:
    """Zellen, die eine Bombe auf (bx,by) mit Reichweite ``radius`` trifft (Kreuz, an Wand
    gestoppt; eine Kiste wird noch getroffen und stoppt dann)."""
    cells = {(bx, by)}
    for dx, dy in DIRS:
        for r in range(1, max(1, radius) + 1):
            x, y = bx + dx * r, by + dy * r
            if not (0 <= x < state.width and 0 <= y < state.height):
                break
            tile = state.tiles[y][x]
            if tile == TILE_WALL:
                break
            cells.add((x, y))
            if tile == TILE_SOFT:
                break
    return cells


def danger_cells(state: GameState) -> set[tuple[int, int]]:
    """Kompatibilitäts-Helfer: alle Zellen, die jetzt oder künftig gefährlich sind."""
    return set(_danger_intervals(state, Rules(), None).keys())


# --- Gefahrenmodell ----------------------------------------------------------

def _match_tick(state: GameState, rules: Rules, now_tick: int = 0) -> int | None:
    """Aktueller Match-Tick. Der Frame-Tick IST der Match-Tick (der Server vergleicht
    ``game.tick`` mit ``sudden_death_tick``) – ``ticks_remaining`` ist nur per Keyframe aktuell
    und bis zu 29 Ticks veraltet (ein Bot starb dadurch exakt auf der nächsten Spiral-Zelle)."""
    if now_tick:
        return now_tick
    if not rules.round_time_ticks or not state.ticks_remaining:
        return None
    return rules.round_time_ticks - state.ticks_remaining


def _radius_of(state: GameState, owner_id: int, rules: Rules) -> int:
    owner = state.players.get(owner_id)
    # Unbekannter Besitzer → konservativ das Regel-Maximum annehmen (Power-ups!)
    return owner.flame if owner else rules.max_flame


SAFETY_MARGIN_TICKS = 6   # Latenz + Jitter (~3 Frames): Gefahr früher/länger annehmen


def _remaining(value: int, seen_tick: int, now_tick: int) -> int:
    """Restzeit eines Zählers, gealtert um die seit dem Stempel vergangenen Ticks.

    KEYFRAMEs kommen nur alle 30 Ticks und DELTAs zählen fuse/ticks nicht herunter – ohne
    Alterung hielte der Bot eine Bombe bis zu 0,5 s länger für harmlos, als sie ist."""
    return max(0, value - max(0, now_tick - seen_tick))


def _danger_intervals(state: GameState, rules: Rules,
                      extra_bomb: tuple[tuple[int, int], int] | None,
                      now_tick: int = 0) -> dict:
    """Zelle → Liste von (start, ende) in Ticks ab jetzt, in denen die Zelle tödlich ist.

    ``extra_bomb`` = (Zelle, Radius) simuliert eine eigene, jetzt gelegte Bombe.
    ``now_tick`` = aktueller Server-Tick (zum Altern der Zähler).
    """
    iv: dict[tuple[int, int], list[tuple[int, int]]] = {}
    margin = SAFETY_MARGIN_TICKS

    def add(cell, s, e):
        iv.setdefault(cell, []).append((max(0, s), e))

    for f in state.flames:
        add((f.x, f.y), 0, _remaining(f.ticks, f.seen_tick, now_tick) + margin)

    # Bomben inkl. Kettenreaktion: det = min(eigene Zündzeit, Zündzeit jeder Bombe, deren
    # Explosion mich erreicht) – bis Fixpunkt.
    specs: list[list] = []          # [zelle, det, blast]
    for b in state.bombs.values():
        specs.append([(b.x, b.y), _remaining(b.fuse, b.seen_tick, now_tick),
                      blast_cells(state, b.x, b.y, _radius_of(state, b.owner, rules))])
    if extra_bomb is not None:
        cell, radius = extra_bomb
        specs.append([cell, rules.bomb_fuse_ticks, blast_cells(state, cell[0], cell[1], radius)])
    changed = True
    while changed:
        changed = False
        for a in specs:
            for b in specs:
                if a is not b and b[0] in a[2] and a[1] < b[1]:
                    b[1] = a[1]
                    changed = True
    for cell, det, blast in specs:
        for c in blast:
            add(c, det - margin, det + rules.flame_duration_ticks + margin)

    _sudden_death_intervals(state, rules, add, now_tick)
    return iv


_closing_cache: dict[tuple[int, int], list[tuple[int, int]]] = {}


def closing_order(width: int, height: int) -> list[tuple[int, int]]:
    """Exakte Sudden-Death-Reihenfolge des Servers (bomber-domain ``closing_order``):
    Innenzellen, äußerster Ring zuerst, im Uhrzeigersinn ab (1,1). Zelle ``i`` wird bei
    ``sudden_death_tick + 6*i`` zur Wand."""
    key = (width, height)
    if key in _closing_cache:
        return _closing_cache[key]
    top, bottom, left, right = 1, height - 2, 1, width - 2
    order: list[tuple[int, int]] = []
    while top <= bottom and left <= right:
        for x in range(left, right + 1):
            order.append((x, top))
        for y in range(top + 1, bottom + 1):
            order.append((right, y))
        if top < bottom:
            for x in range(right - 1, left - 1, -1):
                order.append((x, bottom))
        if left < right:
            for y in range(bottom - 1, top, -1):
                order.append((left, y))
        top, bottom, left, right = top + 1, bottom - 1, left + 1, right - 1
    _closing_cache[key] = order
    return order


def _sudden_death_intervals(state: GameState, rules: Rules, add, now_tick: int = 0) -> None:
    """Jede Innenzelle wird ab ihrem exakten Schließzeitpunkt dauerhaft tödlich."""
    total = rules.round_time_ticks
    match_tick = _match_tick(state, rules, now_tick)
    if not total or rules.sudden_death_tick >= total or match_tick is None:
        return
    now_tick = match_tick
    horizon = rules.bomb_fuse_ticks * 4
    for i, cell in enumerate(closing_order(state.width, state.height)):
        start = rules.sudden_death_tick + SUDDEN_DEATH_TICKS_PER_CELL * i - now_tick
        if start > horizon:
            break
        add(cell, start, INF)


def bomb_capacity(state: GameState, player_id: int) -> int:
    """Wie viele Bomben der Spieler gerade noch legen kann (bombs_max − aktive Bomben)."""
    p = state.players.get(player_id)
    if p is None:
        return 0
    active = sum(1 for b in state.bombs.values() if b.owner == player_id)
    return max(0, max(1, p.bombs_max) - active)


def threat_cells(state: GameState, my_id: int) -> set[tuple[int, int]]:
    """Zellen, die ein lebender Gegner mit freier Bombe *sofort* treffen könnte (sein Kreuz mit
    seiner aktuellen Reichweite). Keine sichere Gefahr, aber kein Ort zum Verweilen."""
    cells: set[tuple[int, int]] = set()
    for p in state.players.values():
        if p.id == my_id or not p.alive or bomb_capacity(state, p.id) == 0:
            continue
        cells |= blast_cells(state, p.x, p.y, p.flame)
    return cells


def is_cornered(state: GameState, x: int, y: int) -> bool:
    """Höchstens ein begehbares Nachbarfeld → kaum Fluchtwege (lohnendes Ziel)."""
    return sum(1 for dx, dy in DIRS if walkable(state, x + dx, y + dy)) <= 1


class _World:
    """Sicht des Bots auf einen Zustand: Passierbarkeit, Gefahren-Zeitfenster, Bedrohungszonen."""

    def __init__(self, state: GameState, rules: Rules, my_id: int,
                 extra_bomb: tuple[tuple[int, int], int] | None = None,
                 now_tick: int = 0) -> None:
        self.state = state
        self.rules = rules
        self.blocked: set[tuple[int, int]] = {(b.x, b.y) for b in state.bombs.values()}
        if extra_bomb is not None:
            self.blocked.add(extra_bomb[0])
        for p in state.players.values():
            if p.id != my_id and p.alive:
                self.blocked.add((p.x, p.y))
        self.intervals = _danger_intervals(state, rules, extra_bomb, now_tick)
        self.threat = threat_cells(state, my_id)      # Gegner-Reichweiten (Power-ups!)
        # Sudden Death: wann (relativ, Ticks) jede Innenzelle zugemauert wird
        self.closing: dict[tuple[int, int], int] = {}
        self.sd_prep = False
        match_tick = _match_tick(state, rules, now_tick)
        if match_tick is not None and rules.sudden_death_tick < rules.round_time_ticks:
            for i, cell in enumerate(closing_order(state.width, state.height)):
                self.closing[cell] = rules.sudden_death_tick + SUDDEN_DEATH_TICKS_PER_CELL * i - match_tick
            self.sd_prep = rules.sudden_death_tick - match_tick <= SD_PREP_TICKS
        # Ein Hafen ist so lange sicher, wie ein voller Zünd- + Flammenzyklus dauert.
        self.haven_ticks = rules.bomb_fuse_ticks + rules.flame_duration_ticks + 10

    def passable(self, cell: tuple[int, int]) -> bool:
        x, y = cell
        return (0 <= x < self.state.width and 0 <= y < self.state.height
                and self.state.tiles[y][x] == TILE_FREE and cell not in self.blocked)

    def safe(self, cell: tuple[int, int], t0: int, t1: int) -> bool:
        for s, e in self.intervals.get(cell, ()):
            if s <= t1 and e >= t0:
                return False
        return True

    def haven(self, cell: tuple[int, int], t: int) -> bool:
        return self.safe(cell, t, t + self.haven_ticks)

    def quiet_haven(self, cell: tuple[int, int], t: int) -> bool:
        """Hafen außerhalb jeder gegnerischen Bombenlinie."""
        return cell not in self.threat and self.haven(cell, t)

    def time_to_close(self, cell: tuple[int, int]) -> int:
        """Ticks, bis Sudden Death die Zelle zumauert (INF = nie/unbekannt)."""
        return self.closing.get(cell, INF)

    def deep_haven(self, cell: tuple[int, int], t: int) -> bool:
        """Hafen, der auch vom einrückenden Rand noch lange verschont bleibt."""
        return self.haven(cell, t) and self.time_to_close(cell) - t >= SD_DEEP_TICKS

    def lethal_from(self, cell: tuple[int, int], t: int) -> int:
        """Erster Tick ≥ t, ab dem die Zelle tödlich ist (INF = nie)."""
        first = INF
        for s, e in self.intervals.get(cell, ()):
            if e >= t:
                first = min(first, max(s, t))
        return first


# --- Zeitbewusste Suche --------------------------------------------------------

def _search(world: _World, start: tuple[int, int], t_free: int, step: int, goal,
            k_max: int = K_MAX):
    """Breitensuche über (Zelle, Schritt). Warten ist ein Zug (gleiche Zelle).

    ``goal(cell, t)`` → True beendet die Suche. Liefert ``(pfad, gefunden)``; ohne Treffer ist
    ``pfad`` der Weg zum Zustand, der am längsten überlebt (Fallback).
    Ein Feld muss sicher sein ab dem Moment, in dem man es betritt, bis man es wieder
    verlassen kann (BOT_GUIDE.md §7: ein Schritt bindet sofort ans Zielfeld).
    """
    start_state = (start, 0)
    parent: dict = {start_state: None}
    queue = deque([start_state])
    deepest = start_state
    while queue:
        cell, k = queue.popleft()
        t = t_free + k * step
        if goal(cell, t):
            return _extract_path(parent, (cell, k)), True
        if k > deepest[1]:
            deepest = (cell, k)
        if k >= k_max:
            continue
        t2 = t + step
        # Erst laufen, dann warten: Wer einen Zustand zuerst erreicht, prägt den Pfad – und
        # frühes Loslaufen lässt mehr Zeitreserve als Abwarten.
        for dx, dy in DIRS:
            n = (cell[0] + dx, cell[1] + dy)
            nxt = (n, k + 1)
            if nxt in parent or not world.passable(n) or not world.safe(n, t, t2):
                continue
            parent[nxt] = (cell, k)
            queue.append(nxt)
        nxt = (cell, k + 1)
        if nxt not in parent and world.safe(cell, t, t2):      # warten
            parent[nxt] = (cell, k)
            queue.append(nxt)
    return _extract_path(parent, deepest), False


def _extract_path(parent: dict, node) -> list[tuple[int, int]]:
    path = []
    while parent[node] is not None:
        path.append(node[0])
        node = parent[node]
    path.reverse()
    return path


def _escape_path(world: _World, start: tuple[int, int], t_free: int, step: int):
    """Nächster Hafen – bevorzugt außerhalb gegnerischer Bombenlinien, wenn das höchstens zwei
    Schritte mehr kostet. Liefert (pfad, gefunden)."""
    path, found = _search(world, start, t_free, step, lambda c, t: world.haven(c, t))
    if found and world.sd_prep:
        deep, ok = _search(world, start, t_free, step, lambda c, t: world.deep_haven(c, t))
        if ok and len(deep) <= len(path) + 3:
            return deep, True                  # Rand rückt ein: lieber weiter nach innen
    if found and world.threat:
        quiet, ok = _search(world, start, t_free, step, lambda c, t: world.quiet_haven(c, t))
        if ok and len(quiet) <= len(path) + 2:
            return quiet, True
    return path, found


def _latest_closing_path(world: _World, start: tuple[int, int], t_free: int, step: int):
    """Rückfallebene für Sudden Death: Pfad zur sicher erreichbaren Zelle, die am spätesten
    zugemauert wird (relativ zur Ankunft) – wenn kein „tiefer" Hafen mehr existiert."""
    start_state = (start, 0)
    parent: dict = {start_state: None}
    queue = deque([start_state])
    best = (world.time_to_close(start) - t_free, start_state)
    while queue:
        cell, k = queue.popleft()
        t = t_free + k * step
        margin = world.time_to_close(cell) - t
        if margin > best[0] and world.safe(cell, t, t + step):
            best = (margin, (cell, k))
        if k >= K_MAX:
            continue
        for dx, dy in DIRS:
            n = (cell[0] + dx, cell[1] + dy)
            nxt = (n, k + 1)
            if nxt in parent or not world.passable(n) or not world.safe(n, t, t + step):
                continue
            parent[nxt] = (cell, k)
            queue.append(nxt)
    return _extract_path(parent, best[1]) if best[1] != start_state else []


def _first_action(start: tuple[int, int], path: list[tuple[int, int]]) -> Action:
    if not path or path[0] == start:
        return Action.NOOP
    return _STEP[(path[0][0] - start[0], path[0][1] - start[1])]


# --- Zielbewertung -------------------------------------------------------------

def _target_values(world: _World, me, enemies) -> dict[tuple[int, int], float]:
    """Wert je Zelle: Power-up dort, oder guter Bombenplatz (Kisten/Gegner im eigenen Radius)."""
    state = world.state
    vals: dict[tuple[int, int], float] = {}
    for pu in state.powerups.values():
        c = (pu.x, pu.y)
        if world.passable(c):
            vals[c] = max(vals.get(c, 0.0), _POWERUP_VALUE.get(pu.kind, 1.5))
    enemy_cells = {(e.x, e.y) for e in enemies}
    banned = _memo["banned"]
    for y in range(state.height):
        for x in range(state.width):
            c = (x, y)
            if c in banned or not world.passable(c):
                continue
            blast = blast_cells(state, x, y, me.flame)
            crates = sum(1 for (bx, by) in blast if state.tiles[by][bx] == TILE_SOFT)
            hit = [e for e in enemy_cells if e in blast]
            v = 0.0
            if crates:
                v = 1.0 + 0.5 * (crates - 1)
            if hit:
                v = max(v, 2.0 + 0.5 * len(hit))
                if any(is_cornered(state, ex, ey) for ex, ey in hit):
                    v += 1.5                       # Gegner ohne Fluchtweg: jetzt zuschlagen
            if v:
                if c in world.threat:
                    v *= 0.6                        # in gegnerischer Bombenlinie nicht verweilen
                if world.sd_prep:
                    # Zellen, die bald zugemauert werden, verlieren an Wert (Rand meiden)
                    v *= min(1.0, max(0.15, world.time_to_close(c) / SD_PREP_TICKS))
                vals[c] = max(vals.get(c, 0.0), v)
    return vals


def _plan_target(world: _World, me, step: int, t_free: int, enemies) -> list[tuple[int, int]]:
    """Pfad zum lohnendsten Ziel: Nutzen = Wert / (Schritte + 1), Hysterese fürs letzte Ziel.
    Leer, wenn es kein sicher erreichbares Ziel gibt."""
    vals = _target_values(world, me, enemies)
    if not vals:
        return []
    start = (me.x, me.y)
    vmax = max(vals.values()) * _HYSTERESIS
    best_util, best_path, best_cell = 0.0, None, None

    start_state = (start, 0)
    parent: dict = {start_state: None}
    queue = deque([start_state])
    while queue:
        cell, k = queue.popleft()
        t = t_free + k * step
        if vmax / (k + 1) <= best_util:
            break                                     # keine Verbesserung mehr möglich
        v = vals.get(cell)
        if v and cell != start and world.safe(cell, t, t + 2 * step):
            if cell == _memo["target"]:
                v *= _HYSTERESIS
            util = v / (k + 1)
            if util > best_util:
                best_util, best_path, best_cell = util, _extract_path(parent, (cell, k)), cell
        if k >= K_MAX:
            continue
        t2 = t + step
        for dx, dy in DIRS:
            n = (cell[0] + dx, cell[1] + dy)
            nxt = (n, k + 1)
            if nxt in parent or not world.passable(n) or not world.safe(n, t, t2):
                continue
            parent[nxt] = (cell, k)
            queue.append(nxt)
        nxt = (cell, k + 1)
        if nxt not in parent and world.safe(cell, t, t2):
            parent[nxt] = (cell, k)
            queue.append(nxt)

    if best_path is None:
        return []
    _memo["target"] = best_cell
    return best_path


def _plan_attack(state: GameState, rules: Rules, me, enemies, step: int,
                 now_tick: int):
    """Bombe legen + ausweichen, wenn es sich lohnt UND die Flucht rechtzeitig gelingt.

    Liefert ``(Aktion, Pfad)`` oder ``None``. ``(NOOP, [])`` bedeutet: guter Platz, aber es
    wurde eben noch eine Bewegung gesendet – erst zur Ruhe kommen, dann bomben (sonst würde die
    Bombe auf dem Zielfeld eines vom Server gerade noch angenommenen Schritts landen)."""
    my_bombs = sum(1 for b in state.bombs.values() if b.owner == me.id)
    if my_bombs >= max(1, me.bombs_max):
        return None
    sent = _memo["bomb_sent_tick"]
    if sent is not None and now_tick - sent < BOMB_COOLDOWN_TICKS:
        return None        # Bombe bereits angefordert – erst auf BOMB_ADD / Ablauf warten
    cur = (me.x, me.y)
    blast = blast_cells(state, cur[0], cur[1], me.flame)
    crates = sum(1 for (bx, by) in blast if state.tiles[by][bx] == TILE_SOFT)
    hits = sum(1 for e in enemies if (e.x, e.y) in blast)
    burned = sum(1 for pu in state.powerups.values() if (pu.x, pu.y) in blast)
    if crates + 3 * hits - burned < 1:
        return None

    world = _World(state, rules, me.id, extra_bomb=(cur, me.flame), now_tick=now_tick)
    best = None                                   # (Länge, Richtung, Gesamtpfad ab cur)
    for dx, dy in DIRS:
        n = (cur[0] + dx, cur[1] + dy)
        if not world.passable(n) or not world.safe(n, 0, step):
            continue
        path, found = _escape_path(world, n, 0, step)
        if found and (best is None or len(path) < best[0]):
            best = (len(path), (dx, dy), [n] + path)
    if best is None:
        return None
    last_move = _memo["last_move_tick"]
    if last_move is not None and now_tick - last_move < MOVE_SETTLE_TICKS:
        return Action.NOOP, []                    # Latenz-Wettlauf vermeiden: erst stehen
    return _STEP_BOMB[best[1]], best[2]


# --- Entscheidung ----------------------------------------------------------------

def decide(track: TrackState, now: float = 0.0) -> Action:
    """Wählt die nächste Aktion des Bots (FR-012/013/014)."""
    state = track.state
    if state is None or track.my_id is None:
        return Action.NOOP
    me = state.players.get(track.my_id)
    if me is None or not me.alive:
        return Action.NOOP
    _forget_previous_match(track)
    if track.at_tick is not None and track.at_tick == _memo["tick"]:
        action = _replay(now)  # eingefrorener Zustand (z. B. verlorenes DELTA): Plan weiterlaufen
        if action in _STEP.values():
            _memo["last_move_tick"] = track.at_tick
        return action

    action, path, start, step, t_free = _decide(
        state, track.match.rules if track.match else Rules(), me, track.at_tick)
    _memo.update({"tick": track.at_tick, "action": action, "plan": path, "plan_start": start,
                  "plan_t0": now, "plan_step_s": step / _TICKS_PER_SECOND,
                  "plan_delay_s": t_free / _TICKS_PER_SECOND})
    if action in _WITHOUT_BOMB and track.at_tick is not None:
        _memo["bomb_sent_tick"] = track.at_tick
    if action in _STEP.values() and track.at_tick is not None:
        _memo["last_move_tick"] = track.at_tick
    return action


def _forget_previous_match(track: TrackState) -> None:
    """Neues Match (andere Match-ID oder Tick springt zurück) → Gedächtnis löschen.

    Alle gemerkten Ticks (``bomb_sent_tick``, ``last_move_tick``, Sperren) beziehen sich auf den
    Match-Tick, der pro Match bei 0 beginnt. Reste aus dem Vormatch (z. B. Bombe bei Tick 4000)
    ließen den Bot im nächsten Match minutenlang nicht bomben („Cooldown“ 4000 − 30 < 12) und
    auf gesperrten Plätzen stehen – beobachtet als „Bot bleibt am Levelanfang stehen“."""
    match_id = track.match.match_id if track.match is not None else None
    new_match = match_id != _memo["match_id"]
    went_back = (track.at_tick is not None and _memo["tick"] is not None
                 and track.at_tick < _memo["tick"])
    if new_match or went_back:
        reset()
        _memo["match_id"] = match_id


def _replay(now: float) -> Action:
    """Koppelnavigation: Ohne neuen Server-Zustand den zuletzt geplanten (zeitlich geprüften)
    Pfad nach Wanduhr weiterverfolgen – ein Schritt je ``plan_step_s``. Eine Bombe wird dabei
    nie erneut gelegt (Einmal-Aktion); nach dem Pfadende wird gewartet."""
    plan = _memo["plan"]
    if not plan:
        return Action.NOOP
    # Laufender Schritt (t_free) verzögert den Start; ein Tick Nachlauf, damit die Wiedergabe
    # nie dem Server vorauseilt (zu frühe Richtung würde einen Schritt überspringen).
    elapsed = now - _memo["plan_t0"] - _memo.get("plan_delay_s", 0.0) - 1 / _TICKS_PER_SECOND
    idx = int(max(0.0, elapsed) / _memo["plan_step_s"])
    if idx >= len(plan):
        return Action.NOOP
    # Letzter Schritt: Richtung nur in der ersten Slot-Hälfte senden. Ein zu spätes NOOP ist
    # gefährlich (Server nimmt die Richtung nach Schrittende erneut an → ein Feld zu weit, ggf.
    # ins Feuer), ein zu frühes NOOP ist harmlos (wird im laufenden Schritt ignoriert).
    if idx == len(plan) - 1:
        frac = (max(0.0, elapsed) - idx * _memo["plan_step_s"]) / _memo["plan_step_s"]
        if frac > 0.5:
            return Action.NOOP
    prev = _memo["plan_start"] if idx == 0 else plan[idx - 1]
    nxt = plan[idx]
    if nxt == prev:
        return Action.NOOP                            # geplantes Warten
    return _STEP[(nxt[0] - prev[0], nxt[1] - prev[1])]


def _decide(state: GameState, rules: Rules, me, at_tick) -> Action:
    step = rules.ticks_to_cross(me.speed)
    t_free = max(0, step - me.move_progress) if me.moving else 0
    enemies = [p for p in state.players.values() if p.id != me.id and p.alive]
    now_tick = at_tick or 0
    world = _World(state, rules, me.id, now_tick=now_tick)
    cur = (me.x, me.y)

    # abgelaufene Sperren für Bombenplätze löschen
    if at_tick is not None:
        _memo["banned"] = {c: t for c, t in _memo["banned"].items() if t > at_tick}

    # 1) Überleben: Ist mein Feld kein sicherer Hafen, sofort zum nächsten Hafen.
    if not world.haven(cur, t_free):
        path, found = _escape_path(world, cur, t_free, step)
        if found or path:
            return _first_action(cur, path), path, cur, step, t_free
        return Action.NOOP, [], cur, step, t_free      # eingeschlossen – nichts hilft mehr

    # 2) Angriff: Bombe legen + ausweichen (nur im Stand möglich).
    if t_free == 0:
        attack = _plan_attack(state, rules, me, enemies, step, now_tick)
        if attack is not None:
            action, path = attack
            return action, path, cur, step, t_free
        # Ich stehe auf einem angepeilten Bombenplatz, kann hier aber nicht sicher bomben →
        # Platz vorübergehend sperren, sonst stünde ich hier fest.
        if cur == _memo["target"] and at_tick is not None:
            _memo["banned"][cur] = at_tick + rules.bomb_fuse_ticks
            _memo["target"] = None

    # 3) Ziel ansteuern (Power-up, Bombenplatz mit Kisten/Gegnern)
    path = _plan_target(world, me, step, t_free, enemies)
    if not path and world.sd_prep and world.time_to_close(cur) < SD_DEEP_TICKS:
        # Kein Ziel und mein Feld wird bald zugemauert: rechtzeitig nach innen ziehen –
        # notfalls zur Zelle, die am spätesten schließt.
        path, found = _search(world, cur, t_free, step, lambda c, t: world.deep_haven(c, t))
        if not found:
            path = _latest_closing_path(world, cur, t_free, step)
    if not path and cur in world.threat:
        # Kein Ziel, aber ich stehe in einer gegnerischen Bombenlinie: lieber heraustreten.
        path, found = _search(world, cur, t_free, step, lambda c, t: world.quiet_haven(c, t))
        if not found:
            path = []
    return _first_action(cur, path), path, cur, step, t_free
