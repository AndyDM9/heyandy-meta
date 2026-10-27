"""Is the cloud reachable? A TCP connection to the Model API's host, every few seconds; nothing is sent.

Andy works either way: offline, Muse Glimmer plans and talks, SAM 3.1 sees, and the TV says "Offline". Online, Muse
Spark can plan searches and look things up. Pulling the network cable mid-conversation is part of the demo.
"""
import socket
import threading

HOST, PORT = "api.meta.ai", 443


def reachable(host: str = HOST, port: int = PORT, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def watch(on_change, stop: threading.Event, every_s: float = 10.0, check=reachable) -> None:
    """Call on_change(online) at the start and whenever it changes, until stop is set."""
    last = None
    while True:
        now = check()
        if now != last:
            on_change(now)
            last = now
        if stop.wait(every_s):
            return
