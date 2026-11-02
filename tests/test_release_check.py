"""November 4 in one command (scripts/release_check.py): what's ready, what's left, what's wrong."""
import re
import sys
import urllib.error
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import release_check as rc  # noqa: E402


def test_each_bracket_left_is_named_by_what_it_is_for():
    text = "*Fill in the [brackets] on the day.*\n\n---\n\nVideo: [link] · X: [link] · Code: [the repo](https://x.y)\n"
    assert rc.brackets(text) == ["Video: [link]", "X: [link]"]  # the note above the line and a real link aren't
    assert rc.brackets("note\n\n---\n\nall filled in\n") == []


def test_a_key_is_one_with_a_value():
    keys = re.compile(rc.KEYS)
    assert keys.search("MODEL_API_KEY=" + "a1B2" * 6) and keys.search("hf_" + "Ab3" * 12) and keys.search("sk-" + "x" * 32)
    for doc in ("set MODEL_API_KEY in ~/.config/heyandy-meta/env", "MODEL_API_KEY=... (chmod 600)",
                'KEYS = re.compile(r"MODEL_API_KEY=|hf_[A-Za-z0-9]{20,}")', "hf_hub_download"):
        assert not keys.search(doc), doc


def test_links_as_a_visitor_who_isnt_signed_in_gets_them():
    text = ("Live demo: https://huggingface.co/spaces/heyandy-ai/andy (eyes: https://heyandy-ai-andy.static.hf.space/eyes.html)"
            " · Code: https://github.com/AndyDM9/heyandy-meta · down: https://github.com/x/broken.")
    answers = {"https://huggingface.co/spaces/heyandy-ai/andy": 200, "https://heyandy-ai-andy.static.hf.space/eyes.html": 401,
               "https://github.com/AndyDM9/heyandy-meta": 404, "https://github.com/x/broken": 500}

    class Ctx:
        def __init__(self, req, timeout):
            self.code = answers[req.full_url]
            if self.code != 200:
                raise urllib.error.HTTPError(req.full_url, self.code, "", {}, None)

        def __enter__(self):
            return NS(status=self.code)

        def __exit__(self, *a):
            return False

    rows = {url: status for status, url, _ in rc.links(text, opener=Ctx)}
    assert rows == {"https://huggingface.co/spaces/heyandy-ai/andy": rc.OK, "https://heyandy-ai-andy.static.hf.space/eyes.html": rc.TODO,
                    "https://github.com/AndyDM9/heyandy-meta": rc.TODO, "https://github.com/x/broken": rc.FAIL}


def fake_git(outputs):
    def run(cmd, **kw):
        key = " ".join(cmd[1:3])
        return NS(stdout=outputs.get(key, ""), returncode=0, stderr="")
    return run


def test_uncommitted_or_unpushed_work_fails():
    assert rc.committed(fake_git({"status --porcelain": " M README.md"}))[0] == rc.FAIL
    assert rc.committed(fake_git({"rev-list --count": "2"}))[0] == rc.FAIL
    assert rc.committed(fake_git({"rev-list --count": "0", "rev-parse --short": "abc1234"}))[0] == rc.OK


def test_the_tests_must_have_passed_on_this_very_commit():
    def gh(answer):
        def run(cmd, **kw):
            return NS(stdout=answer if cmd[0] == "gh" else "abc", returncode=0, stderr="")
        return run
    assert rc.ci(gh('[{"status": "completed", "conclusion": "success"}]'))[0] == rc.OK
    assert rc.ci(gh('[{"status": "completed", "conclusion": "failure"}]'))[0] == rc.FAIL
    assert rc.ci(gh('[{"status": "in_progress", "conclusion": null}]'))[0] == rc.TODO
    assert rc.ci(gh("[]"))[0] == rc.TODO


def test_git_itself_finds_a_key_committed_anywhere_in_the_history(tmp_path):
    import subprocess

    def g(*args):
        return subprocess.run(["git", *args], cwd=tmp_path, capture_output=True, text=True, check=True).stdout

    g("init", "-q")
    g("config", "user.email", "t@example.com")
    g("config", "user.name", "t")
    (tmp_path / "a.md").write_text("set MODEL_API_KEY in your env\n")
    g("add", "a.md")
    g("commit", "-qm", "docs")
    assert g("log", "--all", "-E", "-G", rc.KEYS, "--format=%h") == ""
    (tmp_path / "a.md").write_text("MODEL_API_KEY=" + "Zx9" * 8 + "\n")
    g("commit", "-qam", "oops")
    (tmp_path / "a.md").write_text("gone\n")
    g("commit", "-qam", "removed, but still in the history")
    found = g("log", "--all", "-E", "-G", rc.KEYS, "--format=%s").split("\n")
    assert "oops" in found
