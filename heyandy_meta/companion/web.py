"""Andy uses the web on the TV: "Andy, show me a banana bread recipe on the TV."

Meta's computer use (the Responses API's `computer` tool) drives a clean browser on this computer: no sign-ins, no
saved passwords, no downloads. Each step the model sees a screenshot of the web page (never the camera) and answers
with clicks, typing and scrolling; the TV shows every screenshot as it happens, with a dot where Andy clicks.

Every batch of actions comes with a safety check from the API; it's acknowledged only after this code has reviewed the
actions itself (`review`): nothing that looks like an email address, a phone or card number or a password is typed,
and a page that wants a sign-in, an account or a payment ends the run. Andy leaves those to the person.

Muse Wonder doesn't take the computer tool on our account yet (400 "Unsupported tool type"), so Muse Spark 1.3 runs the
loop, as Meta's docs allow.
"""
import base64
import queue
import time
import re
import threading
from dataclasses import dataclass, field
from urllib.parse import quote_plus, urlsplit

from ..budget import WEB_SEARCH, Budget, chat_cost
from ..models.retry import with_retry
from .answers import _citations, _final_text

MODEL = "muse-spark-1.3"
SIZE = (1280, 800)
START = "https://www.bing.com"
SEARCH = START + "/search?q="  # DuckDuckGo turns a headless browser away; Bing answers one that says it's Chrome
AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
INSTRUCTIONS = (
    "You are Andy, a small home robot, using a web browser shown on the person's TV so they can read along. Do what "
    "they asked, simply and quickly, in as few steps as you can; pick well-known, trustworthy sites. The browser starts "
    "on search results for their words: open the best result, so the TV shows the page itself, not a list of links. "
    "Use several actions in one turn when you can. The screenshot is the page only: to go to a web address or search "
    "again, press ctrl+l, type the address or the search words, and press Enter. Never sign in, create an "
    "account, buy anything, fill in forms other than a search box, or type personal details. Close pop-ups and cookie "
    "banners by declining. When the page shows what was asked, stop and reply with one or two short spoken sentences "
    "saying what's on the screen. No lists or markdown. Never give medical advice.")

PRIVATE = [re.compile(p, re.I) for p in (
    r"[\w.+-]+@[\w-]+\.[\w.]+",  # an email address
    r"(?:\d[ -]?){9,}",  # a phone or card number
    r"\bpass(?:word|code)\b|\bpin\b|\bssn\b|\bsocial security\b")]
WALLED = re.compile(r"(?:^|[/.?=&-])(?:log-?in|sign-?in|sign-?up|register|account|checkout|cart|basket|payment|billing|"
                    r"subscribe|auth)(?:$|[/.?=&-])", re.I)  # not "_": Wikipedia's Shopping_cart is a page about carts
KEYS = {"enter": "Enter", "return": "Enter", "tab": "Tab", "esc": "Escape", "escape": "Escape", "space": " ",
        "backspace": "Backspace", "delete": "Delete", "up": "ArrowUp", "down": "ArrowDown", "left": "ArrowLeft",
        "right": "ArrowRight", "pageup": "PageUp", "pagedown": "PageDown", "home": "Home", "end": "End",
        "ctrl": "Control", "control": "Control", "shift": "Shift", "alt": "Alt", "cmd": "Meta", "meta": "Meta"}
ALLOWED_COMBOS = {"Control+l", "Control+f", "Control+a", "Alt+ArrowLeft", "Shift+Tab"}


class Walled(Exception):
    """The page wants a sign-in, an account or a payment: the run stops there."""


def review(actions: list[dict], url: str) -> str | None:
    """Why these actions mustn't run, or None if they may. Checked before every safety check is acknowledged."""
    if WALLED.search(urlsplit(url).path + "?" + urlsplit(url).query):
        return "the page wants a sign-in, an account or a payment"
    for a in actions:
        if a.get("type") == "type":
            text = a.get("text") or ""
            if len(text) > 200 or any(p.search(text) for p in PRIVATE):
                return "it would type something personal"
        if a.get("type") == "keypress":
            keys = "+".join(_key(k) for k in a.get("keys") or [])
            if "+" in keys and keys not in ALLOWED_COMBOS:
                return f"an unexpected key combination ({keys})"
    return None


def _key(k: str) -> str:
    k = str(k)
    return KEYS.get(k.lower(), k if len(k) == 1 else k[:1].upper() + k[1:].lower())


def address(text: str) -> str:
    """What was typed after ctrl+l: a web address, or search words for the start page's search."""
    text = text.strip()
    if re.match(r"^(?:https?://)?[\w-]+(?:\.[\w-]+)+(?:[/?#]\S*)?$", text):
        return text if text.startswith("http") else "https://" + text
    return SEARCH + quote_plus(text)


def describe(a: dict) -> str:
    """One action in words, for the TV."""
    kind = a.get("type")
    if kind == "type":
        return f"Typing “{(a.get('text') or '')[:40]}”"
    return {"click": "Clicking", "double_click": "Clicking", "scroll": "Scrolling", "keypress": "Pressing a key",
            "drag": "Dragging", "move": "Moving", "wait": "Waiting for the page", "screenshot": "Looking"}.get(kind, kind)


class Browser:
    """A clean headless Chromium on its own thread (Playwright's sync API stays on the thread that made it)."""

    def __init__(self, size=SIZE, start: str = START):
        self.size, self.start = size, start
        self._jobs: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None
        self._typing: list[str] | None = None  # after ctrl+l: the address being typed

    def _run(self) -> None:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            ctx = browser.new_context(viewport={"width": self.size[0], "height": self.size[1]}, accept_downloads=False,
                                      locale="en-US", user_agent=AGENT)
            self.page = ctx.new_page()
            self.page.goto(self.start)
            while True:
                fn, args, done = self._jobs.get()
                if fn is None:
                    break
                try:
                    done.put((True, fn(*args)))
                except Exception as e:  # noqa: BLE001 - handed back to the caller
                    done.put((False, e))
            browser.close()

    def _call(self, fn, *args):
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
        done: queue.Queue = queue.Queue()
        self._jobs.put((fn, args, done))
        try:
            ok, out = done.get(timeout=60)
        except queue.Empty as e:
            raise TimeoutError("the browser didn't answer") from e
        if not ok:
            raise RuntimeError(f"the browser: {type(out).__name__}: {out}") from out
        return out

    def screenshot(self) -> bytes:
        return self._call(self._screenshot)

    def _screenshot(self) -> bytes:
        for _ in range(3):  # a page in the middle of a redirect can't be captured: a moment later it can
            try:
                return self.page.screenshot(type="jpeg", quality=70)
            except Exception:  # noqa: BLE001
                self.page.wait_for_timeout(1000)
        return self.page.screenshot(type="jpeg", quality=70)

    def url(self) -> str:
        return self._call(lambda: self.page.url)

    def execute(self, actions: list[dict]) -> None:
        self._call(self._execute, actions)

    def _execute(self, actions: list[dict]) -> None:
        page = self.page
        for a in actions:
            kind, x, y = a.get("type"), a.get("x"), a.get("y")
            if kind == "keypress":
                keys = "+".join(_key(k) for k in a.get("keys") or [])
                if keys == "Control+l":
                    self._typing = []
                elif keys == "Enter" and self._typing is not None:
                    page.goto(address("".join(self._typing)), wait_until="domcontentloaded")
                    self._typing = None
                elif keys == "Alt+ArrowLeft":
                    page.go_back(wait_until="domcontentloaded")
                elif keys:
                    page.keyboard.press(keys)
            elif kind == "type":
                if self._typing is not None:
                    self._typing.append(a.get("text") or "")
                else:
                    page.keyboard.type(a.get("text") or "", delay=15)
            elif kind in ("click", "double_click"):
                self._typing = None
                button = a.get("button") if a.get("button") in ("left", "right", "middle") else "left"
                (page.mouse.dblclick if kind == "double_click" else page.mouse.click)(x, y, button=button)
            elif kind == "scroll":
                page.mouse.move(x or self.size[0] / 2, y or self.size[1] / 2)
                page.mouse.wheel(a.get("scroll_x") or 0, a.get("scroll_y") or 0)
            elif kind == "move":
                page.mouse.move(x, y)
            elif kind == "drag":
                path = a.get("path") or []
                if path:
                    page.mouse.move(path[0]["x"], path[0]["y"])
                    page.mouse.down()
                    for p in path[1:]:
                        page.mouse.move(p["x"], p["y"])
                    page.mouse.up()
            elif kind == "wait":
                page.wait_for_timeout(1000)
        try:
            page.wait_for_load_state("domcontentloaded", timeout=5000)
        except Exception:  # noqa: BLE001 - a slow page: take the screenshot anyway
            pass
        page.wait_for_timeout(600)

    def home(self) -> None:
        self._call(lambda: self.page.goto(self.start))

    def open(self, url: str) -> None:
        self._typing = None
        self._call(lambda: (self.page.goto(url, wait_until="domcontentloaded"), self.page.wait_for_timeout(1500)))

    def search(self, words: str) -> None:
        """Start a request on the search results for its words: most requests then take a click or two."""
        self._typing = None
        self._call(lambda: (self.page.goto(address(words), wait_until="domcontentloaded"), self.page.wait_for_timeout(1500)))

    def close(self) -> None:
        if self._thread and self._thread.is_alive():
            self._jobs.put((None, (), None))


@dataclass
class Run:
    answer: str = ""
    steps: int = 0
    stopped: str = ""  # why the run ended early, in words
    response_id: str | None = None
    actions: list = field(default_factory=list)


def _shot(jpeg: bytes) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()


def use_the_web(client, browser: Browser, task: str, on_step=lambda jpeg, words, point: None,
                previous: str | None = None, budget: Budget | None = None, max_steps: int = 15,
                model: str = MODEL, effort: str = "low", within_s: float = 120.0, clock=time.monotonic) -> Run:
    """One request on the web, step by step. ``previous`` continues the last run ("scroll down", "go back")."""
    budget, run, end = budget or Budget(), Run(), clock() + within_s
    jpeg = browser.screenshot()
    on_step(jpeg, "Searching the web" if previous is None else "Looking at the page", None)
    if previous is None:
        request = [{"role": "user", "content": [{"type": "input_text", "text": task},
                                                {"type": "input_image", "image_url": _shot(jpeg)}]}]
        extra = {}
    else:  # the API takes a screenshot this way only in a run's first request; the model asks for a fresh one
        request, extra = [{"role": "user", "content": [{"type": "input_text", "text": task}]}], {"previous_response_id": previous}
    while True:
        budget.check(chat_cost(model, 3000, 1500))
        r = with_retry(lambda request=request, extra=extra: client.responses.create(
            model=model, instructions=INSTRUCTIONS, tools=[{"type": "computer"}], reasoning={"effort": effort},
            max_output_tokens=4000, input=request, **extra))
        usage = getattr(r, "usage", None)
        budget.record(model, chat_cost(model, getattr(usage, "input_tokens", 0) or 0,
                                       getattr(usage, "output_tokens", 0) or 0))
        run.response_id = r.id
        calls = [o for o in r.output if o.type == "computer_call"]
        said = " ".join(c.text for o in r.output if o.type == "message" for c in (o.content or [])
                        if getattr(c, "text", None))
        if not calls:
            run.answer = _spoken(said)
            return run
        if run.steps >= max_steps or clock() > end:
            run.stopped = "it was taking too long"
            run.answer = _spoken(said)
            return run
        call = calls[0]
        actions = [a.model_dump() if hasattr(a, "model_dump") else dict(a) for a in (getattr(call, "actions", None) or [])]
        why = review(actions, browser.url())
        if why:
            run.stopped = why
            return run
        run.steps += 1
        run.actions += actions
        point = next(((a["x"], a["y"]) for a in actions if a.get("type") in ("click", "double_click")), None)
        on_step(jpeg, " · ".join(dict.fromkeys(describe(a) for a in actions)), point)
        browser.execute(actions)
        why = review([], browser.url())
        if why:  # the click went to a sign-in or a payment page
            browser.execute([{"type": "keypress", "keys": ["alt", "left"]}])
            run.stopped = why
            return run
        jpeg = browser.screenshot()
        on_step(jpeg, "", None)
        checks = [c.model_dump() if hasattr(c, "model_dump") else dict(c)
                  for c in (getattr(call, "pending_safety_checks", None) or [])]
        output = {"type": "computer_call_output", "call_id": call.call_id,
                  "output": {"type": "computer_screenshot", "image_url": _shot(jpeg)}}
        if checks:  # reviewed above, in code, before any action ran
            output["acknowledged_safety_checks"] = [{"id": c["id"], "code": c.get("code"), "message": c.get("message")}
                                                    for c in checks]
        request, extra = [output], {"previous_response_id": r.id}


PICK = ("Find the single best web page to show on a TV for this request, from a well-known, trustworthy site, one that "
        "shows the thing itself (the recipe, the radar, the article), not a list of links: {task}{home} Reply with only "
        "that page's web address.")


def best_page(client, task: str, home: str = "", budget: Budget | None = None, model: str = MODEL) -> str | None:
    """Muse Spark's web search picks the page (about 5 s): much faster than clicking through search results."""
    budget = budget or Budget()
    budget.check(chat_cost(model, 6000, 1500) + 2 * WEB_SEARCH)
    r = with_retry(lambda: client.responses.create(
        model=model, input=PICK.format(task=task, home=f" (The person lives in {home}.)" if home else ""),
        tools=[{"type": "web_search"}], reasoning={"effort": "low"}, max_output_tokens=1500))
    usage = getattr(r, "usage", None)
    budget.record(model, chat_cost(model, getattr(usage, "input_tokens", 0) or 0, getattr(usage, "output_tokens", 0) or 0)
                  + WEB_SEARCH)
    said = re.search(r"https?://[^\s)\]>\"']+", _final_text(r))
    if said:
        return said.group().rstrip(".,")
    cited = _citations(r)
    return cited[0][1] if cited else None


SHOW = ("{task} The browser shows {url}. If the page already shows it, do nothing more: just say what's on the "
        "screen. Otherwise close pop-ups and scroll so it shows.")


def _spoken(text: str) -> str:
    text = re.sub(r"[*_#`>]+", "", text).strip()
    parts = re.split(r"(?<=[.!?])\s+", text)
    return " ".join(parts[-2:]) if len(parts) > 2 else text  # the last words are the answer, not the narration
