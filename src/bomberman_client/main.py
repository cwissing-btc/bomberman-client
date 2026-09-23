"""Game-Loop und Zustandsautomat des Clients (60 FPS).

US1: Anmelden (HELLO/ASSIGNED), Lobby anzeigen, Match darstellen (KEYFRAME/DELTA), Timeouts.
Pro Tick wird genau ein Uplink-Paket gesendet – in US1 stets NOOP (Steuerung folgt in US2,
Bot in US3). Der Sende-`seq` wird bei jedem Paket erhöht.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import pygame

from . import bot as bot_module
from .assets import TILE_SIZE, load_sprites
from .input import input_to_action
from .net import UdpClient
from .protocol import Action, decode, encode_action, encode_hello
from .render import Renderer
from .track import Phase, TrackState


def _read_action() -> Action:
    """Liest die aktuell gedrückten Tasten und bildet sie auf eine Aktion ab (US2)."""
    keys = pygame.key.get_pressed()
    return input_to_action(
        up=keys[pygame.K_UP],
        down=keys[pygame.K_DOWN],
        left=keys[pygame.K_LEFT],
        right=keys[pygame.K_RIGHT],
        bomb=keys[pygame.K_SPACE],
    )

TICK_RATE = 60
HELLO_INTERVAL = 0.5      # s zwischen HELLO-Wiederholungen
CONNECT_TIMEOUT = 5.0     # s ohne ASSIGNED → FAILED (FR-003)
NO_STATE_TIMEOUT = 1.0    # s ohne verwertbaren Zustand → erneutes HELLO (FR-005b)
LOST_TIMEOUT = 3.0        # s ohne Frame → Verbindung verloren (FR-015)
LOBBY_SIZE = (640, 360)


@dataclass
class Config:
    host: str
    port: int
    bot: bool = False
    name: str | None = None      # nur lokal/kosmetisch


def run(config: Config) -> None:
    pygame.init()
    pygame.display.set_caption("Bomberman Client")
    screen = pygame.display.set_mode(LOBBY_SIZE)
    assets = load_sprites()
    renderer = Renderer(assets)
    clock = pygame.time.Clock()

    net = UdpClient(config.host, config.port)
    track = TrackState()

    mode = "bot" if config.bot else "manual"   # per Taste B umschaltbar (FR-018)
    seq = 0
    board_size: tuple[int, int] | None = None
    start_time = time.monotonic()
    last_hello = 0.0
    match_init_time: float | None = None
    running = True

    net.send(encode_hello())

    while running:
        now = time.monotonic()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_b:
                mode = "manual" if mode == "bot" else "bot"   # Modus umschalten (FR-018)

        # 1) Empfangen und verarbeiten
        prev_at_tick = track.at_tick
        for datagram in net.receive_all():
            frame = decode(datagram)
            if frame is not None:
                track.on_frame(frame, now)
        track.check_connection(now, LOST_TIMEOUT)

        if track.match is not None and match_init_time is None:
            match_init_time = now
        if track.at_tick != prev_at_tick and track.state is not None:
            match_init_time = None  # Zustand ist eingetroffen

        # 2) Timeouts / Anmeldung
        if track.phase == Phase.CONNECTING:
            if now - start_time > CONNECT_TIMEOUT:
                track.phase = Phase.FAILED
            elif now - last_hello > HELLO_INTERVAL:
                net.send(encode_hello())
                last_hello = now
        elif track.state is None and match_init_time is not None \
                and now - match_init_time > NO_STATE_TIMEOUT:
            net.send(encode_hello())          # MATCH_INIT/KEYFRAME verpasst → erneut anfordern
            match_init_time = now

        # 3) Fenster an Kartengröße anpassen, sobald ein Zustand vorliegt
        if track.state is not None:
            desired = (track.state.width * TILE_SIZE, track.state.height * TILE_SIZE)
            if desired != board_size:
                screen = pygame.display.set_mode(desired)
                board_size = desired

        # 4) Uplink: 1 Paket pro Tick, sobald Spieler-ID bekannt
        if track.my_id is not None and track.phase in (Phase.LOBBY, Phase.PLAYING):
            action = Action.NOOP
            if track.phase == Phase.PLAYING:
                if mode == "bot":
                    action = bot_module.decide(track, now)      # Bot steuert (US3)
                else:
                    action = _read_action()                     # manuelle Steuerung (US2)
            net.send(encode_action(track.my_id, action, seq))
            seq += 1

        # 5) Darstellung je nach Phase
        _render(screen, renderer, track, config, mode, now)
        pygame.display.flip()
        clock.tick(TICK_RATE)

    net.close()
    pygame.quit()


def _render(screen, renderer: Renderer, track: TrackState, config: Config, mode: str,
            now: float) -> None:
    if track.phase == Phase.FAILED:
        renderer.render_center_message(screen, "Keine Verbindung",
                                       "Server antwortet nicht (kein ASSIGNED).")
    elif track.phase == Phase.CONNECTING:
        renderer.render_center_message(screen, "Verbinde …",
                                       f"{config.host}:{config.port}")
    elif track.phase == Phase.CONNECTION_LOST:
        renderer.render_center_message(screen, "Verbindung verloren",
                                       "Seit 3 s kein Frame empfangen.")
    elif track.phase == Phase.LOBBY:
        if track.lobby is not None:
            renderer.render_lobby(screen, track.lobby, track.my_id)
        else:
            renderer.render_center_message(screen, "Lobby",
                                           f"Spieler-ID {track.my_id}")
    elif track.phase == Phase.MATCH_OVER:
        _render_match_over(screen, renderer, track)
    elif track.phase == Phase.PLAYING and track.state is not None:
        renderer.render_game(screen, track.state, track.my_id, now)
        mode_label = "BOT" if mode == "bot" else "MANUELL"
        name = config.name or f"Spieler {track.my_id}"
        lines = [f"{name}  [{mode_label}]   (B = Modus wechseln)"]
        if mode == "manual":
            lines.append("Pfeiltasten = laufen, Leertaste = Bombe")
        if track.state.ticks_remaining:
            lines.append(f"Restzeit: {track.state.ticks_remaining // TICK_RATE}s")
        renderer.render_overlay(screen, lines)
    else:
        renderer.render_center_message(screen, "Warte auf Match …")


def _render_match_over(screen, renderer: Renderer, track: TrackState) -> None:
    result = track.result
    if result is None:
        renderer.render_center_message(screen, "Match beendet")
        return
    if result.winner == 0xFF:
        subtitle = "Unentschieden"
    else:
        subtitle = f"Sieger: Spieler {result.winner}"
    renderer.render_center_message(screen, "Match beendet", subtitle)
