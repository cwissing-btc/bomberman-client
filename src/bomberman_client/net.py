"""UDP-Anbindung an den Server – nicht-blockierend, damit der Game-Loop nie wartet.

Es wird über denselben Socket gesendet und empfangen, weil der Server die Identität an die
Absenderadresse bindet (BOT_GUIDE.md §3).
"""

from __future__ import annotations

import socket


class UdpClient:
    def __init__(self, host: str, port: int) -> None:
        self.server = (host, port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setblocking(False)

    def send(self, datagram: bytes) -> None:
        try:
            self.sock.sendto(datagram, self.server)
        except OSError:
            # Verlust eines ausgehenden Pakets ist bei UDP normal; kein Retry (BOT_GUIDE §6).
            pass

    def receive_all(self) -> list[bytes]:
        """Liest alle aktuell wartenden Datagramme (bis der Puffer leer ist)."""
        out: list[bytes] = []
        while True:
            try:
                data, _addr = self.sock.recvfrom(4096)
            except BlockingIOError:
                break
            except OSError:
                break
            out.append(data)
        return out

    def close(self) -> None:
        self.sock.close()
