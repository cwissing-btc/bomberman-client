"""Einstiegspunkt: Startparameter einlesen und den Client starten (FR-001)."""

from __future__ import annotations

import argparse

from .main import Config, run


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="bomberman-client",
        description="Bomberman-Spielclient (UDP) für die Team-Arena.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Serveradresse (Default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=47800, help="UDP-Port (Default 47800)")
    parser.add_argument("--bot", action="store_true", help="Bot-Modus als Anfangsmodus")
    parser.add_argument("--name", default="Carsten",
                        help="Anzeigename, wird im HELLO an den Server gesendet (max. 24 Byte UTF-8)")
    args = parser.parse_args()
    run(Config(host=args.host, port=args.port, bot=args.bot, name=args.name))


if __name__ == "__main__":
    main()
