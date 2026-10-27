"""Serve the TV page on this computer only. It reads the screen state; nothing on the network can change it."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files

from .state import ScreenState

COLORS = {  # every text colour against the background is at least 7:1 (tested)
    "bg": "#0e1116", "text": "#f4f1ea", "muted": "#c9c3b8", "accent": "#ffd166", "cloud": "#9ad1ff", "outline": "#ffd166",
}


def page() -> str:
    html = files(__package__).joinpath("page.html").read_text()
    for name, value in COLORS.items():
        html = html.replace("{{" + name + "}}", value)
    return html


def serve(state: ScreenState, host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    body = page().encode()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/":
                self._send(200, "text/html; charset=utf-8", body)
            elif self.path == "/state.json":
                self._send(200, "application/json", json.dumps(state.snapshot()).encode())
            else:
                self._send(404, "text/plain", b"not found")

        def _send(self, code, kind, data):
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):  # no request logs: they would show when someone looked at the screen
            pass

    server = ThreadingHTTPServer((host, port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server
