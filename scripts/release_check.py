"""November 4 in one command: is everything the judges will open ready, and what's left to do?

The submission checklist's steps that can be checked are checked here, each as OK, TO DO (expected until the day: the
video's link, going public) or FAIL (fix before submitting):
- the code committed and pushed, and the tests passed on GitHub on that very commit;
- every figure says what its source says (scripts/claims.py), the results page is current, the shared-link card shows
  today's figures;
- no [bracket] left in the submission's text, and the README's video badge uncommented;
- no key anywhere in the history (the checklist's step 3);
- the links in the submission answer a visitor who isn't signed in (the repository, the Space, Andy's eyes);
- with --space, the Space as uploaded is exactly the build (scripts/verify_space.py).

    uv run python scripts/release_check.py            # about ten seconds; --space adds the upload's check
"""
import argparse
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
OK, TODO, FAIL = "OK", "TO DO", "FAIL"
# what a key looks like when it's really one (the docs name MODEL_API_KEY often; a value after it is what matters)
KEYS = r"MODEL_API_KEY=[A-Za-z0-9_\-]{16,}|hf_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9]{30,}"
LINKS = re.compile(r"https://(?:github\.com|huggingface\.co|[a-z0-9-]+\.static\.hf\.space)/[^\s)`>]*")


def git(*args, run=subprocess.run) -> str:
    # rstrip only: a porcelain status line starts with a space (" M README.md"), part of the file's place in the line
    return run(["git", *args], capture_output=True, text=True, cwd=ROOT).stdout.rstrip()


def committed(run=subprocess.run) -> tuple[str, str]:
    dirty = [line for line in git("status", "--porcelain", "--untracked-files=no", run=run).splitlines() if line]
    if dirty:
        return FAIL, f"{len(dirty)} changed file(s) not committed: " + ", ".join(line[3:] for line in dirty[:5])
    ahead = git("rev-list", "--count", "@{u}..HEAD", run=run)
    if ahead and ahead != "0":
        return FAIL, f"{ahead} commit(s) not pushed (git push)"
    return OK, f"clean, pushed ({git('rev-parse', '--short', 'HEAD', run=run)})"


def ci(run=subprocess.run) -> tuple[str, str]:
    head = git("rev-parse", "HEAD", run=run)
    out = run(["gh", "run", "list", "--commit", head, "--limit", "1", "--json", "status,conclusion"], capture_output=True,
              text=True, cwd=ROOT)
    if out.returncode != 0:
        return FAIL, f"can't ask GitHub: {out.stderr.strip()[:120]}"
    import json

    runs = json.loads(out.stdout or "[]")
    if not runs:
        return TODO, "no run on GitHub for this commit yet"
    status, conclusion = runs[0]["status"], runs[0]["conclusion"]
    if status != "completed":
        return TODO, f"the tests are still running on GitHub ({status})"
    return (OK, "the tests passed on GitHub, on this commit") if conclusion == "success" else (FAIL, f"GitHub: {conclusion}")


def figures() -> tuple[str, str]:
    import claims

    problems = claims.problems()
    return (OK, f"all {len(claims.FIGURES)} read from their sources") if not problems else (FAIL, problems[0][:160])


def results_page() -> tuple[str, str]:
    import results_index

    current = (results_index.RESULTS / "README.md").read_text() == results_index.build()
    return (OK, "made from today's files") if current else (FAIL, "out of date: uv run python scripts/results_index.py")


def card() -> tuple[str, str]:
    import social_card

    now, said = [list(f) for f in social_card.figures()], social_card.said()
    return (OK, "shows today's figures") if now == said else (FAIL, "out of date: uv run python scripts/social_card.py")


def brackets(text: str) -> list[str]:
    """Each [placeholder] left in the submission's own text (not a markdown link, not the note above the line), with
    the words just before it ("Video: [link]", "X: [link]")."""
    body = text.split("\n---\n", 1)[-1]
    return [(body[max(0, m.start() - 12):m.start()].split("·")[-1].strip() + " " + m.group(0)).strip()
            for m in re.finditer(r"\[[^\]\n]{1,40}\](?!\()", body)]


def submission_filled() -> tuple[str, str]:
    left = brackets((ROOT / "docs" / "submission.md").read_text())
    return (OK, "no bracket left") if not left else (TODO, "fill " + ", ".join(left) + " (docs/submission.md)")


def video_badge() -> tuple[str, str]:
    readme = (ROOT / "README.md").read_text()
    if "VIDEO_URL" in readme:
        return TODO, "uncomment the 'Watch the 3-minute video' badge under the hero, with the video's link"
    return OK, "the video badge is up"


def no_keys(run=subprocess.run) -> tuple[str, str]:
    found = git("log", "--all", "-E", "-G", KEYS, "--format=%h", run=run)
    return (OK, "none in any commit") if not found else (FAIL, "something like a key in " + ", ".join(found.split()[:5]))


def links(text: str, opener=urllib.request.urlopen) -> list[tuple[str, str, str]]:
    """Each public link in the submission, as a visitor who isn't signed in gets it."""
    rows = []
    for url in sorted(set(LINKS.findall(text))):
        url = url.rstrip(".,;")
        try:
            with opener(urllib.request.Request(url, method="GET", headers={"User-Agent": "release-check"}), timeout=20) as r:
                rows.append((OK, url, str(r.status)))
        except urllib.error.HTTPError as e:
            rows.append((TODO if e.code in (401, 404) else FAIL, url, f"{e.code}: still private?" if e.code in (401, 404)
                         else str(e.code)))
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            rows.append((FAIL, url, f"no answer: {e}"[:80]))
    return rows


def space() -> tuple[str, str]:
    if not (ROOT / "dist" / "space-static" / "index.html").exists():
        return TODO, "build it first: uv run python scripts/build_static_space.py --video <link> --clip film/robot.mp4"
    out = subprocess.run(["uvx", "--from", "huggingface_hub", "python", str(ROOT / "scripts" / "verify_space.py")],
                         capture_output=True, text=True, cwd=ROOT)
    last = " ".join(out.stdout.split()[-14:])
    return (OK, "the upload is the build") if out.returncode == 0 else (FAIL, last[:160])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--space", action="store_true", help="also check the Space as uploaded against the build")
    args = ap.parse_args()
    checks = [("the code committed and pushed", committed), ("the tests on GitHub", ci),
              ("every figure", figures), ("the results page", results_page), ("the shared-link card", card),
              ("the submission's brackets", submission_filled), ("the README's video", video_badge),
              ("keys in the history", no_keys)]
    if args.space:
        checks.append(("the Space as uploaded", space))
    rows = []
    for name, fn in checks:
        try:
            status, detail = fn()
        except Exception as e:  # noqa: BLE001 - a check that can't run is a failure, said as one
            status, detail = FAIL, f"{type(e).__name__}: {e}"[:160]
        rows.append(status)
        print(f"{status:6} {name}: {detail}", flush=True)
    for status, url, detail in links((ROOT / "docs" / "submission.md").read_text()):
        rows.append(status)
        print(f"{status:6} the link {url}: {detail}", flush=True)
    fails, todos = rows.count(FAIL), rows.count(TODO)
    print("\nREADY TO SUBMIT" if not fails and not todos else f"\nNOT YET: {fails} failing, {todos} to do")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
