"""Is the cloud reachable? A TCP connection to the Model API's host, every few seconds; nothing is sent.

Andy works either way: offline, Muse Glimmer plans and talks, SAM 3.1 sees, and the TV says "Offline". Online, Muse
Spark can plan searches and look things up. Pulling the network cable mid-conversation is part of the demo.
"""
import socket
import threading
import time
from pathlib import Path

HOST, PORT = "api.meta.ai", 443


def reachable(host: str = HOST, port: int = PORT, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def wired(routes: str = "/proc/net/route", net: str = "/sys/class/net") -> bool | None:
    """Is the link out of this computer there, read on this computer (nothing sent)? False when no default route's
    link has a carrier (the cable pulled: at once; a moment later the route itself goes), None when it can't be read
    (not Linux), so the cloud check alone decides."""
    try:
        lines = Path(routes).read_text().splitlines()[1:]
    except OSError:
        return None
    links = {f[0] for f in (line.split() for line in lines) if len(f) > 2 and f[1] == "00000000"}
    up = []
    for link in links:
        try:
            up.append(Path(net, link, "carrier").read_text().strip() == "1")
        except OSError:  # no carrier to read (a tunnel): it counts as there
            up.append(True)
    return any(up)


def watch(on_change, stop: threading.Event, every_s: float = 10.0, check=reachable, link=wired,
          link_every_s: float = 1.0, clock=time.monotonic, fast_s: float = 30.0) -> None:
    """Call on_change(online) at the start and whenever it changes, until stop is set. The cloud is tried every
    ``every_s``. Where the link can be read (``wired``), it is read every ``link_every_s``: a pulled cable shows on the
    TV within a second (the demo's shot; November 3, it took up to 10 s), and for ``fast_s`` after the link comes back
    the cloud is tried at that pace too, until it answers (the address takes a few seconds to come)."""
    last, tried, back, was = None, float("-inf"), float("-inf"), None
    while True:
        there, t = link(), clock()
        if there is True and was is False:
            back = t  # plugged back in
        was = there
        if there is False:
            now = False
        elif there is None or last is None or t - tried >= every_s - 0.05 or (last is False and t - back <= fast_s):
            now, tried = check(), t
        else:
            now = last
        if now != last:
            on_change(now)
            last = now
        if stop.wait(every_s if there is None else link_every_s):
            return
