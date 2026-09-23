"""Verlustbehandlung nach BOT_GUIDE.md §6.

Ein KEYFRAME ersetzt den Zustand und ist immer vertrauenswürdig. Ein DELTA wird NUR angewendet,
wenn der gehaltene Tick exakt dessen ``base_tick`` entspricht – sonst verworfen und auf das
nächste KEYFRAME gewartet. Es gibt keinen anforderbaren Resync (Uplink ist 2 Byte).
"""

from __future__ import annotations

from .protocol import (
    Assigned,
    Delta,
    Frame,
    FrameType,
    LobbyStatus,
    MatchEnd,
)
from .state import GameState, MatchInfo

LOBBY_RUNNING = 3      # LOBBY_STATUS.state (BOT_GUIDE.md §5.2)
LOBBY_MATCH_OVER = 4


class Phase:
    CONNECTING = "connecting"
    LOBBY = "lobby"
    PLAYING = "playing"
    CONNECTION_LOST = "connection_lost"
    MATCH_OVER = "match_over"
    FAILED = "failed"


class TrackState:
    def __init__(self) -> None:
        self.phase: str = Phase.CONNECTING
        self.my_id: int | None = None
        self.match: MatchInfo | None = None
        self.state: GameState | None = None
        self.at_tick: int | None = None
        self.lobby: LobbyStatus | None = None
        self.result: MatchEnd | None = None
        self.last_frame_time: float | None = None

    def on_frame(self, frame: Frame, now: float) -> None:
        """Verarbeitet genau ein dekodiertes Downlink-Frame."""
        self.last_frame_time = now

        if frame.type == FrameType.ASSIGNED:
            assigned: Assigned = frame.data  # type: ignore[assignment]
            self.my_id = assigned.player_id
            if self.phase in (Phase.CONNECTING, Phase.CONNECTION_LOST):
                self.phase = Phase.LOBBY

        elif frame.type == FrameType.LOBBY_STATUS:
            lobby: LobbyStatus = frame.data  # type: ignore[assignment]
            self.lobby = lobby
            if self.phase != Phase.PLAYING:
                self.phase = Phase.LOBBY
            elif lobby.state != LOBBY_RUNNING:
                # Während eines laufenden Matches sendet der Server keinen LOBBY_STATUS. Kommt
                # einer, ist das Match vorbei – auch ohne MATCH_END (Moderator-„end" sendet
                # keins). Sonst bliebe der Client in PLAYING und spielte auf altem Zustand weiter.
                self.phase = Phase.MATCH_OVER if lobby.state == LOBBY_MATCH_OVER else Phase.LOBBY

        elif frame.type == FrameType.MATCH_INIT:
            info: MatchInfo = frame.data  # type: ignore[assignment]
            repeat = (self.match is not None and self.match.match_id == info.match_id
                      and self.state is not None)
            self.match = info
            self.phase = Phase.PLAYING
            if not repeat:
                # Neues Match: alles Dynamische verwerfen, auf das erste KEYFRAME warten.
                # MATCH_INIT wird 5 Ticks in Folge wiederholt (Zustellgarantie); dieselbe Match-ID
                # darf den bereits gehaltenen Zustand nicht löschen – sonst stünde der Client bis
                # zum nächsten KEYFRAME (30 Ticks) ohne Zustand und der Bot am Start still.
                self.state = None
                self.at_tick = None
                self.result = None

        elif frame.type == FrameType.KEYFRAME:
            self.state = frame.data  # type: ignore[assignment]
            self.at_tick = frame.tick
            self.phase = Phase.PLAYING
            # Zähler-Stempel: fuse/ticks gelten zu diesem Tick (DELTAs zählen sie nicht herunter)
            for bomb in self.state.bombs.values():
                bomb.seen_tick = frame.tick
            for flame in self.state.flames:
                flame.seen_tick = frame.tick

        elif frame.type == FrameType.DELTA:
            delta: Delta = frame.data  # type: ignore[assignment]
            if self.state is not None and self.at_tick == delta.base_tick:
                self.state.apply_delta(delta.records, frame.tick)
                self.at_tick = frame.tick
            # sonst: Lücke → verwerfen, auf nächstes KEYFRAME warten

        elif frame.type == FrameType.MATCH_END:
            self.result = frame.data  # type: ignore[assignment]
            self.phase = Phase.MATCH_OVER

    def check_connection(self, now: float, timeout: float = 3.0) -> None:
        """Setzt ``phase`` auf CONNECTION_LOST, wenn ``timeout`` s kein Frame kam."""
        if self.phase in (Phase.PLAYING, Phase.LOBBY) and self.last_frame_time is not None:
            if now - self.last_frame_time > timeout:
                self.phase = Phase.CONNECTION_LOST
