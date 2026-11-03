"""Serve the TV page on this computer only. It reads the screen state; nothing on the network can change it."""
import hmac
import ipaddress
import json
import secrets
import threading
from urllib.parse import parse_qs, urlsplit
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files

from .state import ScreenState

# Each part of the day's colours. Panels are frosted (the last two hex digits are their opacity); every text colour
# is at least 7:1 against a panel over each background it can sit on (tests/test_screen.py).
THEMES = {
    "day": {"ink": "#10241d", "muted": "#33493f", "accent": "#0d5a45", "cloud": "#0a4e86", "panel": "#fbfaf5e6",
            "solid": "#fbfaf5",
            "caption_bg": "#11201b", "caption": "#f6f3ea", "bg1": "#f4ebcf", "bg2": "#e6f0e6", "bg3": "#d9ebf0"},
    "morning": {"bg1": "#f6e7c8", "bg3": "#f3dccb"},
    "evening": {"bg1": "#f3d9c6", "bg3": "#e8d6e6"},
    "night": {"ink": "#f2efe6", "muted": "#c8c3b6", "accent": "#ffd27a", "cloud": "#a5d3ff", "panel": "#17202ae6",
              "solid": "#17202a",
              "caption_bg": "#070a0e", "caption": "#f2efe6", "bg1": "#1d2a3a", "bg2": "#121a24", "bg3": "#2a2238"},
}
OUTLINE = "#ffd166"  # the found thing's outline, drawn on the camera picture
FONTS = {name: "font/ttf" for name in ("AtkinsonHyperlegibleNext.ttf", "AtkinsonHyperlegibleMono.ttf")}


def _home_address(host_header: str) -> bool:
    """A TV elsewhere in the home asking by this computer's address: an address, not a name, so it can't be rebound."""
    host = host_header.rsplit(":", 1)[0].strip("[]") if host_header.count(":") <= 1 or host_header.startswith("[") \
        else host_header
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback


def page(token: str = "") -> str:
    """The TV's page. token: the settings' own key, made each time the TV starts and only written into this page, so
    only this page can change a setting (another site's page can't read it); empty, the TV changes nothing."""
    html = files(__package__).joinpath("page.html").read_text().replace("{{settings_token}}", token)
    for part, colours in THEMES.items():
        for name, value in colours.items():
            html = html.replace("{{" + f"{part}_{name}" + "}}", value)
    return html.replace("{{outline}}", OUTLINE)


def hood_json(state: ScreenState, sample: bool = False) -> dict:
    """What /hood shows: the turns' timings, numbers and models' names only. The public demo (no robot) shows a turn
    recorded on the robot, and says so."""
    if sample or state.hood is None:
        return {**json.loads(files(__package__).joinpath("hood_sample.json").read_text()), "sample": True}
    services = state.services() if callable(state.services) else []
    return {**state.hood.snapshot(), "services": services, "show_s": state.hood_left(), "sample": False}


def serve(state: ScreenState, host: str = "127.0.0.1", port: int = 8765, scenes: dict | None = None,
          frame_ancestors: str = "'none'", any_host: bool = False, listed: list | None = None,
          on_language=None, languages=()) -> ThreadingHTTPServer:
    """The TV page and its state, read-only but for one setting. scenes (the public demo only): name -> a snapshot
    made on request, so each visitor picks a scene for themselves and nobody can change what anyone else sees; listed:
    the ones the demo's bar offers (default all; the others are played when asked for, as a find in each of Andy's
    languages). on_language (Andy's own TV): the settings' language list switches Andy's language, as "Andy, speak
    Spanish" does; only from this page (its key, its own origin, JSON) and only to one of `languages`."""
    token = secrets.token_urlsafe(24) if on_language else ""
    body = page(token).encode()
    hood_page = files(__package__).joinpath("hood.html").read_text().encode()
    # Only asked for by its own name: a page that tricks a browser into "andy.localhost" (DNS rebinding) gets nothing,
    # because the TV's state holds the last camera picture. The public sample demo (any_host) has no pictures.
    hosts = ("127.0.0.1", "localhost", "[::1]", host)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            bound = self.server.server_address[1]  # the port it really got (0 asks for any)
            names = {f"{h}:{bound}" for h in hosts} | set(hosts)
            asked = (self.headers.get("Host") or "").lower()
            if not any_host and asked not in names and not _home_address(asked):
                return self._send(421, "text/plain", b"not this name")
            url = urlsplit(self.path)
            if url.path == "/":
                self._send(200, "text/html; charset=utf-8", body)
            elif url.path == "/state.json":
                pick = parse_qs(url.query).get("scene", [""])[0]
                snap = scenes[pick]() if scenes and pick in scenes else state.snapshot()
                if scenes:
                    snap["demo"] = list(listed or scenes)
                self._send(200, "application/json", json.dumps(snap).encode())
            elif url.path == "/hood":  # under the hood: each turn's stages and timings (screen/hood.py)
                self._send(200, "text/html; charset=utf-8", hood_page)
            elif url.path == "/hood.json":
                self._send(200, "application/json", json.dumps(hood_json(state, sample=bool(scenes))).encode())
            elif url.path == "/drawing.webp" and state.drawing_bytes():
                self._send(200, "image/webp", state.drawing_bytes())
            elif url.path == "/web.jpg" and state.web_bytes():
                self._send(200, "image/jpeg", state.web_bytes())
            elif url.path == "/room.bin" and state.room_bytes():  # the room's shape: millimetres, never a picture
                self._send(200, "application/octet-stream", state.room_bytes())
            elif url.path.startswith("/fonts/") and url.path[7:] in FONTS:  # served here: the TV asks nobody else
                self._send(200, FONTS[url.path[7:]], files(__package__).joinpath("fonts", url.path[7:]).read_bytes(),
                           cache="max-age=86400")
            else:
                self._send(404, "text/plain", b"not found")

        def do_POST(self):
            """The one setting the TV can change, Andy's language: from this page only. Its Host is one of the TV's own
            names (no rebinding), its Origin this TV (no other site), its body JSON (no plain form from elsewhere), with
            the key written into this page when the TV started (another site can't read it), and a language Andy has."""
            bound = self.server.server_address[1]
            names = {f"{h}:{bound}" for h in hosts} | set(hosts)
            asked = (self.headers.get("Host") or "").lower()
            if urlsplit(self.path).path != "/language" or not on_language or any_host:
                return self._send(404, "text/plain", b"not found")
            if asked not in names:
                return self._send(421, "text/plain", b"not this name")
            if (self.headers.get("Origin") or "").lower() != f"http://{asked}":
                return self._send(403, "text/plain", b"not from this page")
            if not (self.headers.get("Content-Type") or "").startswith("application/json"):
                return self._send(415, "text/plain", b"json only")
            size = int(self.headers.get("Content-Length") or 0)
            if not 0 < size <= 512:
                return self._send(413, "text/plain", b"too long")
            try:
                asked_for = json.loads(self.rfile.read(size))
                key, to = str(asked_for.get("token", "")), str(asked_for.get("to", ""))
            except (ValueError, AttributeError):
                return self._send(400, "text/plain", b"not json")
            if not hmac.compare_digest(key.encode(), token.encode()):
                return self._send(403, "text/plain", b"not this page's key")
            if to not in languages:
                return self._send(400, "text/plain", b"not one of Andy's languages")
            threading.Thread(target=on_language, args=(to,), daemon=True, name="tv-language").start()  # it speaks
            self._send(202, "application/json", b'{"ok": true}')

        def _send(self, code, kind, data, cache="no-store"):
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Cache-Control", cache)
            self.send_header("Content-Security-Policy", f"frame-ancestors {frame_ancestors}")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):  # no request logs: they would show when someone looked at the screen
            pass

    server = ThreadingHTTPServer((host, port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server
