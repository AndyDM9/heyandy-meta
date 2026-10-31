"""Andy in your pocket: a phone on the home network, paired once, asks Andy from any room and sees the find.

Off unless Andy is started with --remote. It answers only devices on the home network (private addresses), and
nothing at all, not even what Andy is doing, until the phone is paired: "Andy, connect my phone" shows a web address and
six numbers on the TV for three minutes (five wrong tries end them); the phone that types them gets a key, kept in a
cookie only it sends (SameSite=Strict, HttpOnly). Only each key's SHA-256 is written down (remote.json, readable by its
owner only); "forget my phones" removes them all. A request from the phone is a turn like any other: Andy finds and
points in the room and says the answer there; the phone shows the words, the found picture and the privacy receipt.
"""
import hashlib
import hmac
import ipaddress
import json
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path

from ..private import write_private
from .server import FONTS, OUTLINE

CODE_SECONDS = 180
TRIES = 5
COOKIE = "andy_remote"
MAX_BODY = 4096


class Pairing:
    def __init__(self, path: Path | str, clock=time.time):
        self.path, self.clock, self._lock = Path(path), clock, threading.Lock()
        data = json.loads(self.path.read_text()) if self.path.exists() else {}
        self._keys: list[str] = list(data.get("keys", []))  # SHA-256 of each paired phone's key
        self._code: tuple[str, float, int] | None = None  # (six numbers, until, wrong tries)

    def new_code(self) -> str:
        """Six numbers for the TV, good for CODE_SECONDS."""
        with self._lock:
            code = f"{secrets.randbelow(10 ** 6):06d}"
            self._code = (code, self.clock() + CODE_SECONDS, 0)
            return code

    def code_left(self) -> float:
        return max(0.0, self._code[1] - self.clock()) if self._code else 0.0

    def pair(self, code: str) -> str | None:
        """A key for the phone that typed the right numbers in time; None otherwise (and a try used)."""
        with self._lock:
            if not self._code or self.clock() > self._code[1]:
                return None
            right, until, tries = self._code
            if not hmac.compare_digest(str(code).strip(), right):
                self._code = (right, until, tries + 1) if tries + 1 < TRIES else None
                return None
            self._code = None  # one phone per code
            key = secrets.token_urlsafe(32)
            self._keys.append(hashlib.sha256(key.encode()).hexdigest())
            self._save()
            return key

    def knows(self, key: str | None) -> bool:
        if not key:
            return False
        digest = hashlib.sha256(key.encode()).hexdigest()
        return any(hmac.compare_digest(digest, k) for k in self._keys)

    def phones(self) -> int:
        return len(self._keys)

    def forget_all(self) -> int:
        with self._lock:
            n, self._keys, self._code = len(self._keys), [], None
            self._save()
            return n

    def _save(self) -> None:
        write_private(self.path, json.dumps({"keys": self._keys}))


def phone_state(snap: dict) -> dict:
    """What the phone sees of the TV's state: what Andy is doing and saying, the find, the receipt. No reminders list,
    no memory panels, no web pages: the find and the words are what a phone in another room needs."""
    out = {k: snap.get(k) for k in ("state", "head", "caption", "looking_for", "running", "seconds", "lang")}
    p = snap.get("picture")
    if p and not p.get("trails"):
        out["picture"] = {k: p.get(k) for k in ("src", "width", "height", "box", "outline", "scale", "label", "words",
                                                "aim_deg", "metres")}
    out["sent"] = [{"to": o["to"], "words": o["words"]} for o in snap.get("outbox") or []]
    out["models"] = [m["name"] for m in snap.get("models") or []]
    out["lost"] = [x["thing"] for x in snap.get("lost") or []]  # what Andy is still looking for: the words only
    return out


def serve_remote(state, pairing: Pairing, ask, host: str, port: int = 8766) -> ThreadingHTTPServer:
    """The phone's page and its three calls: /pair, /state and /ask (ask(text) -> "ok" or "busy")."""
    page = files(__package__).joinpath("remote.html").read_text().replace("{{outline}}", OUTLINE).encode()
    names: set[str] = set()  # this computer's own address and port: filled in once the port is known

    class Handler(BaseHTTPRequestHandler):
        def _home(self) -> bool:  # a device on the home network, asking by this computer's own address
            try:
                ip = ipaddress.ip_address(self.client_address[0])
            except ValueError:
                return False
            return (ip.is_private or ip.is_loopback) and (self.headers.get("Host") or "").lower() in names

        def _key(self) -> str | None:
            for part in (self.headers.get("Cookie") or "").split(";"):
                name, _, value = part.strip().partition("=")
                if name == COOKIE:
                    return value
            return None

        def do_GET(self):
            if not self._home():
                return self._send(403, "text/plain", b"home network only")
            path = self.path.split("?")[0]
            if path == "/":
                return self._send(200, "text/html; charset=utf-8", page)
            if path.startswith("/fonts/") and path[7:] in FONTS:
                return self._send(200, FONTS[path[7:]], files(__package__).joinpath("fonts", path[7:]).read_bytes(),
                                  cache="max-age=86400")
            if path == "/state":
                if not pairing.knows(self._key()):
                    return self._json(401, {"paired": False})
                return self._json(200, {"paired": True, **phone_state(state.snapshot())})
            self._send(404, "text/plain", b"not found")

        def do_POST(self):
            if not self._home():
                return self._send(403, "text/plain", b"home network only")
            origin = self.headers.get("Origin")
            if origin and origin.split("://", 1)[-1].lower() not in names:  # a page elsewhere can't ask Andy
                return self._json(403, {"error": "not from Andy's own page"})
            n = int(self.headers.get("Content-Length") or 0)
            if not 0 < n <= MAX_BODY:
                return self._json(413, {"error": "too large or empty"})
            try:
                body = json.loads(self.rfile.read(n))
            except ValueError:
                return self._json(400, {"error": "not JSON"})
            if self.path == "/pair":
                key = pairing.pair(str(body.get("code", ""))[:12])
                if not key:
                    return self._json(403, {"paired": False})
                return self._json(200, {"paired": True},
                                  cookie=f"{COOKIE}={key}; Max-Age=31536000; Path=/; HttpOnly; SameSite=Strict")
            if self.path == "/ask":
                if not pairing.knows(self._key()):
                    return self._json(401, {"paired": False})
                text = " ".join(str(body.get("text", "")).split())[:200]
                if not text:
                    return self._json(400, {"error": "say something"})
                return self._json(200, {"answer": ask(text)})
            self._json(404, {"error": "not found"})

        def _json(self, code, body, cookie=None):
            self._send(code, "application/json", json.dumps(body).encode(), cookie=cookie)

        def _send(self, code, kind, data, cache="no-store", cookie=None):
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Cache-Control", cache)
            self.send_header("Content-Security-Policy", "frame-ancestors 'none'")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            if cookie:
                self.send_header("Set-Cookie", cookie)
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):  # no request logs: they would show when someone asked what
            pass

    server = ThreadingHTTPServer((host, port), Handler)
    bound = server.server_address[1]
    names.update({f"{host}:{bound}", host, f"127.0.0.1:{bound}", f"localhost:{bound}"})
    threading.Thread(target=server.serve_forever, daemon=True, name="remote").start()
    return server


def home_address() -> str | None:
    """This computer's address on the home network (the one its default route leaves by), if it's a private one."""
    import socket

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.0.2.1", 9))  # no packet is sent: this only picks the interface
        ip = s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()
    return ip if ipaddress.ip_address(ip).is_private and not ipaddress.ip_address(ip).is_loopback else None
