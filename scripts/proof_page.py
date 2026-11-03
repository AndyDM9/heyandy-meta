"""Andy, measured: the public demo's page of every scorecard, made from the same files as evals/results/README.md.

Each scorecard's latest result (its numbers large), what it measures, the command that runs it again, its file and the
earlier runs kept beside it, in the results page's sections (on the robot, simulated, privacy and safety, languages, in
the browser); above them, the claims check (scripts/claims.py: every figure in the submission, the system card and the
README read from its file, and how many disagree) and the shared card's figures. Static: made when the Space is built.

    uv run python scripts/proof_page.py      # -> dist/proof.html, to look at; the Space's build writes its own
"""
import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
REPO = "https://github.com/AndyDM9/heyandy-meta/blob/main/evals/results/"


def rich(text: str) -> str:
    """A result's text, escaped, its **numbers** made strong (the only mark the results use)."""
    return re.sub(r"\*\*(.+?)\*\*", r'<strong>\1</strong>', html.escape(text))


def anchor(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def tiles() -> list[tuple[str, str]]:
    """The headline figures: the shared card's three, and the open weights' check, each read from its file."""
    import claims
    import social_card

    out = [tuple(f) for f in social_card.figures()]
    w = claims.summary(claims.newest("open-weights-all"))
    if w["every file matches"]:
        out.append((f"{w['matched']} of {w['files']}", "open-weight files byte for byte what Meta published"))
    return out


def checked() -> tuple[int, int]:
    """(figures in the documents read from their files, how many disagree), as the claims check finds them now."""
    import claims

    return len(claims.FIGURES), len(claims.problems())


def page() -> str:
    from results_index import cards

    sections = [(title, rows) for title, rows in cards() if rows]
    figures, wrong = checked()
    total = sum(len(rows) for _, rows in sections)
    nav = "".join(f'<a href="#{anchor(t)}">{html.escape(t)} <span>{len(rows)}</span></a>' for t, rows in sections)
    tile = "".join(f"<li><b>{html.escape(big)}</b><span>{html.escape(small)}</span></li>" for big, small in tiles())
    body = []
    for title, rows in sections:
        items = []
        for c in rows:
            earlier = (f'<span class="earlier">{len(c["earlier"])} earlier run{"s" if len(c["earlier"]) != 1 else ""} kept</span>'
                       if c["earlier"] else "")
            run = (f"<code>{html.escape(c['how'])}</code>" if not c["how"].startswith("a one-off")
                   else html.escape(c["how"]))
            items.append(f"""<article>
  <h3>{html.escape(c['title'])}</h3>
  <p class="what">{html.escape(c['what'])}</p>
  <p class="result">{rich(c['result'])}</p>
  <footer><span class="run">{run}</span><a href="{REPO}{html.escape(c['file'])}">{html.escape(c['file'])}</a>{earlier}</footer>
</article>""")
        body.append(f'<section id="{anchor(title)}" aria-labelledby="h-{anchor(title)}"><h2 id="h-{anchor(title)}">'
                    f'{html.escape(title)}</h2><div class="grid">{"".join(items)}</div></section>')
    verdict = ("none disagrees" if wrong == 0 else f"{wrong} disagree{'s' if wrong == 1 else ''}: being fixed")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Andy, measured</title>
<link rel="icon" href="data:,">
<style>
  @font-face {{ font-family: "Atkinson Next"; src: url("fonts/AtkinsonHyperlegibleNext.ttf"); font-weight: 200 800; }}
  @font-face {{ font-family: "Atkinson Mono"; src: url("fonts/AtkinsonHyperlegibleMono.ttf"); font-weight: 200 800; }}
  :root {{ --ground: #0b110f; --panel: #142019; --panel2: #1b2a22; --ink: #f5f3ef; --soft: rgba(245, 243, 239, 0.72);
          --rule: rgba(245, 243, 239, 0.14); --gold: #ffcf5c; }}
  * {{ box-sizing: border-box; }}
  html {{ scroll-behavior: smooth; }}
  @media (prefers-reduced-motion: reduce) {{ html {{ scroll-behavior: auto; }} }}
  body {{ margin: 0; background: radial-gradient(ellipse at 80% -10%, #1d2a24, var(--ground) 60%); background-color: var(--ground);
         color: var(--ink); font: 400 clamp(16px, 1.1vw, 19px)/1.45 "Atkinson Next", sans-serif; padding: 4vh max(16px, 5vw) 6vh; }}
  a {{ color: inherit; text-underline-offset: 0.2em; }}
  a:focus-visible {{ outline: 3px solid var(--gold); outline-offset: 3px; border-radius: 4px; }}
  .back {{ color: var(--soft); margin: 0 0 2vh; font-size: 0.95em; display: flex; flex-wrap: wrap; gap: 0.4em 1.4em; }}
  h1 {{ font-size: clamp(40px, 5.6vw, 92px); line-height: 0.98; letter-spacing: -0.03em; margin: 0; }}
  h1 em {{ font-style: normal; color: var(--gold); }}
  .lede {{ color: var(--soft); font-size: clamp(17px, 1.4vw, 24px); max-width: 62ch; margin: 2vh 0 0; }}
  .claims {{ margin: 3.4vh 0 0; padding: 1.4em 1.6em; border-radius: 18px; background: var(--panel); border: 1px solid var(--rule);
            display: flex; flex-wrap: wrap; align-items: baseline; gap: 0.4em 1.2em; max-width: 78rem; }}
  .claims b {{ font: 700 clamp(30px, 3vw, 48px)/1 "Atkinson Mono", monospace; color: var(--gold); }}
  .claims span {{ flex: 1 1 26rem; color: var(--soft); }}
  .claims span strong {{ color: var(--ink); }}
  ul.tiles {{ list-style: none; padding: 0; margin: 3.4vh 0 0; display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 2.4vw; }}
  ul.tiles li {{ border-top: 3px solid var(--gold); padding-top: 0.9em; color: var(--soft); }}
  ul.tiles b {{ display: block; font: 700 clamp(30px, 3vw, 52px)/1.05 "Atkinson Mono", monospace; color: var(--ink); margin-bottom: 0.3em; }}
  nav.jump {{ position: sticky; top: 0; z-index: 2; display: flex; flex-wrap: wrap; gap: 0.5em; margin: 4vh calc(-1 * max(16px, 5vw)) 0;
             padding: 1em max(16px, 5vw); background: rgba(11, 17, 15, 0.92); backdrop-filter: blur(6px); border-bottom: 1px solid var(--rule); }}
  nav.jump a {{ text-decoration: none; padding: 0.55em 1em; border-radius: 99em; border: 1px solid var(--rule); background: var(--panel2);
               font-weight: 650; min-height: 44px; display: inline-flex; align-items: center; gap: 0.5em; }}
  nav.jump a span {{ font: 700 0.85em/1 "Atkinson Mono", monospace; color: var(--gold); }}
  section {{ margin-top: 5vh; scroll-margin-top: 90px; }}
  h2 {{ font-size: clamp(24px, 2.2vw, 36px); margin: 0 0 2vh; letter-spacing: -0.01em; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 25rem), 1fr)); gap: 1.4vw; }}
  article {{ background: var(--panel); border: 1px solid var(--rule); border-radius: 18px; padding: 1.3em 1.4em 1.1em;
             display: flex; flex-direction: column; gap: 0.6em; }}
  article h3 {{ margin: 0; font-size: 1.2em; }}
  .what {{ margin: 0; color: var(--soft); font-size: 0.92em; }}
  .result {{ margin: 0.2em 0 0; font-size: 1.02em; flex: 1; }}
  .result strong {{ font: 700 1.3em/1.2 "Atkinson Mono", monospace; color: var(--gold); }}
  article footer {{ display: flex; flex-wrap: wrap; gap: 0.4em 1em; align-items: center; padding-top: 0.8em; border-top: 1px solid var(--rule);
                    color: var(--soft); font-size: 0.82em; }}
  article footer code {{ font-family: "Atkinson Mono", monospace; color: var(--ink); background: var(--panel2); padding: 0.15em 0.45em; border-radius: 6px; }}
  article footer a {{ font-family: "Atkinson Mono", monospace; }}
  body > footer {{ margin-top: 6vh; color: var(--soft); font-size: 0.92em; max-width: 78rem; }}
  @media (max-width: 900px) {{ ul.tiles {{ grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 5vw; }} .grid {{ gap: 3vw; }}
    ul.tiles b {{ white-space: nowrap; font-size: clamp(22px, 6.6vw, 40px); }} }}
</style>
</head>
<body>
<header>
<nav class="back" aria-label="Andy's pages"><a href="./">← Andy's front door</a><a href="hood.html">Under the hood</a><a href="eyes.html?find">Andy's eyes</a></nav>
<h1>Andy, <em>measured.</em></h1>
<p class="lede">Every scorecard Andy has run: its latest result, what it measures, the command that runs it again, and
  its file. Failures stay: an earlier run is kept beside the latest. Pictures and sounds are never kept, only words,
  numbers and timings.</p>
<p class="claims"><b>{figures}</b><span><strong>figures</strong> in the submission, the system card and the README,
  each read from its file here by <code>scripts/claims.py</code>: <strong>{verdict}</strong>, checked when this page
  was made and by a test on every push.</span></p>
<ul class="tiles" aria-label="Headline figures">{tile}</ul>
</header>
<nav class="jump" aria-label="Sections">{nav}</nav>
<main>{"".join(body)}</main>
<footer><p>{total} scorecards. Their files are in the repository's <a href="{REPO.rsplit('/blob/', 1)[0]}/tree/main/evals/results">evals/results</a>,
  the same page as markdown in its README. Built by HeyAndy, Inc. for Meta's Global AI Developer Hackathon; every model Andy
  runs is Meta's. Andy gives no health advice.</p></footer>
</body>
</html>
"""


if __name__ == "__main__":
    out = ROOT / "dist" / "proof.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(page())
    print(f"wrote {out}")
