from __future__ import annotations

import socket
import time
from typing import Optional

LIMITED_BROADCAST = "255.255.255.255"

_addresses_cache: tuple[float, list[str]] = (0.0, [])


def local_ipv4_addresses(*, max_age_s: float = 30.0) -> list[str]:
    """Adresses IPv4 des interfaces locales (hors loopback/APIPA), mises en cache quelques secondes."""
    global _addresses_cache
    cached_at, cached = _addresses_cache
    if cached and time.monotonic() - cached_at < max_age_s:
        return list(cached)
    addresses: list[str] = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET, socket.SOCK_DGRAM):
            address = str(info[4][0])
            if address.startswith(("127.", "169.254.")) or address in addresses:
                continue
            addresses.append(address)
    except OSError:
        addresses = []
    _addresses_cache = (time.monotonic(), addresses)
    return list(addresses)


def send_broadcast(payload: bytes, port: int, target: str = LIMITED_BROADCAST) -> Optional[OSError]:
    """Envoie un datagramme en broadcast et renvoie la dernière erreur si aucun envoi n'a réussi.

    Sous Windows, un broadcast vers 255.255.255.255 ne sort que par l'interface par défaut.
    Pour fonctionner avec plusieurs cartes réseau (VPN, Hyper-V, VirtualBox…), on l'émet
    aussi depuis chaque adresse locale.
    """
    sources: list[Optional[str]] = [None]
    if target == LIMITED_BROADCAST:
        sources += local_ipv4_addresses()
    sent = False
    last_error: Optional[OSError] = None
    for source in sources:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                if source is not None:
                    sock.bind((source, 0))
                sock.sendto(payload, (target, port))
                sent = True
        except OSError as exc:
            last_error = exc
    return None if sent else last_error
