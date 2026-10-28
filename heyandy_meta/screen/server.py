"""Serve the TV page on this computer only. It reads the screen state; nothing on the network can change it."""
import json
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


def page() -> str:
    html = files(__package__).joinpath("page.html").read_text()
    for part, colours in THEMES.items():
        for name, value in colours.items():
            html = html.replace("{{" + f"{part}_{name}" + "}}", value)
    return html.replace("{{outline}}", OUTLINE)


def serve(state: ScreenState, host: str = "127.0.0.1", port: int = 8765, scenes: dict | None = None,
          frame_ancestors: str = "'none'") -> ThreadingHTTPServer:
    """The TV page and its state, read-only. scenes (the public demo only): name -> a snapshot made on request, so
    each visitor picks a scene for themselves and nobody can change what anyone else sees."""
    body = page().encode()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            url = urlsplit(self.path)
            if url.path == "/":
                self._send(200, "text/html; charset=utf-8", body)
            elif url.path == "/state.json":
                pick = parse_qs(url.query).get("scene", [""])[0]
                snap = scenes[pick]() if scenes and pick in scenes else state.snapshot()
                if scenes:
                    snap["demo"] = list(scenes)
                self._send(200, "application/json", json.dumps(snap).encode())
            elif url.path == "/drawing.webp" and state.drawing_bytes():
                self._send(200, "image/webp", state.drawing_bytes())
            elif url.path == "/web.jpg" and state.web_bytes():
                self._send(200, "image/jpeg", state.web_bytes())
            elif url.path.startswith("/fonts/") and url.path[7:] in FONTS:  # served here: the TV asks nobody else
                self._send(200, FONTS[url.path[7:]], files(__package__).joinpath("fonts", url.path[7:]).read_bytes(),
                           cache="max-age=86400")
            else:
                self._send(404, "text/plain", b"not found")

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
