"""Filming day's takes, made into the video's pieces: captions, the badge, the robot and the TV side by side, the X clip.

Everything runs on this computer: the captions come from Andy's own hearing (Omnilingual ASR, the heyandy-voice
service), and nothing is uploaded. Takes and what's made from them go in film/ (git-ignored).

    uv run python scripts/make_film.py sync film/take1.mp4 --tv film/tv-take1.webm   # where the TV lines up
    uv run python scripts/make_film.py captions film/take1.mp4        # -> film/take1.srt: read it, fix any word
    uv run python scripts/make_film.py burn film/take1.mp4 --tv film/tv-take1.webm --tv-offset 0.8 --out film/find.mp4
    uv run python scripts/make_film.py burn film/take1.mp4 --start 12 --end 42 --shape square --out film/x-clip.mp4
    uv run python scripts/make_film.py cut film/cut.json --out film/andy.mp4   # the pieces and cards, one video, <= 3:00

One take in, one piece out, so the badge ("autonomous · uncut · 1× speed") is true by construction. A piece across a
time cut (the reminder, two minutes later) says so: --badge "autonomous · 1× speed · two minutes later".
--tv-offset is the second of the TV recording that matches the take's first frame. sync finds it: in filming mode
("Hey Andy, we're filming", then "take one") Andy claps (two short notes) and writes the clap's time to
film/takes.json; sync hears the clap in the camera's sound and reads when the TV recording started (record_tv.py's
.json), so the offset is measured, not guessed; it checks it against the TV's own "TAKE n" flash in its recording, and
prints the burn command, starting just after the clap so the piece starts clean.
Needs an ffmpeg with the subtitles and drawtext filters (Ubuntu's /usr/bin/ffmpeg has them; set FFMPEG otherwise).
"""
import argparse
import json
import os
import subprocess
import tempfile
import urllib.request
from pathlib import Path

import numpy as np

FFMPEG = os.environ.get("FFMPEG", "/usr/bin/ffmpeg")
FONTS = Path(__file__).resolve().parent.parent / "heyandy_meta" / "screen" / "fonts"
RATE = 16000
BADGE = "autonomous · uncut · 1× speed"
SHAPES = {"wide": (1920, 1080), "square": (1080, 1080), "vertical": (1080, 1920)}


def audio(path: Path) -> np.ndarray:
    """The take's sound as 16 kHz mono floats, held in memory only."""
    out = subprocess.run([FFMPEG, "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(RATE), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(out, dtype="<f4")


def speech_spans(samples: np.ndarray, rate: int = RATE, gap_s: float = 0.45, longest_s: float = 6.0) -> list[tuple]:
    """Where someone is speaking, in seconds: loud 30 ms frames, joined across short pauses, cut into caption-sized
    pieces (a line on screen should be readable in the time it's up)."""
    hop = int(rate * 0.03)
    n = len(samples) // hop
    if n == 0:
        return []
    rms = np.sqrt((samples[: n * hop].reshape(n, hop) ** 2).mean(axis=1))
    loud = rms > max(0.01, 0.15 * float(np.percentile(rms, 95)))
    spans, start = [], None
    for i, on in enumerate(list(loud) + [False]):
        if on and start is None:
            start = i
        elif not on and start is not None:
            spans.append([start * 0.03, i * 0.03])
            start = None
    joined = []
    for s in spans:
        if joined and s[0] - joined[-1][1] < gap_s:
            joined[-1][1] = s[1]
        else:
            joined.append(s)
    pieces = []
    for a, b in joined:
        if b - a < 0.25:
            continue  # a knock or a click, not a word
        k = int(np.ceil((b - a) / longest_s))
        pieces += [(round(a + (b - a) * j / k, 2), round(a + (b - a) * (j + 1) / k, 2)) for j in range(k)]
    return pieces


def find_clap(samples: np.ndarray) -> list[tuple[float, float]]:
    """Where Andy's clap is in a take's sound: (seconds, match 0 to 1), the best three (heyandy_meta/voice/earcons.py)."""
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from heyandy_meta.voice.earcons import RATE as EARCON_RATE, find

    assert EARCON_RATE == RATE
    return find(samples, "clap")


def flashes(video: Path, fps: int = 25) -> list[float]:
    """When the TV recording shows a "TAKE n" flash: the seconds where the whole screen turns to its inverse (each
    frame's mean brightness, from 16 by 9 grey pixels, far from the recording's usual)."""
    raw = subprocess.run([FFMPEG, "-v", "error", "-i", str(video), "-vf", f"fps={fps},scale=16:9,format=gray",
                          "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    means = np.frombuffer(raw, np.uint8).reshape(-1, 144).mean(axis=1)
    if not len(means):
        return []
    away = np.abs(means - np.median(means)) > 90
    return [round(i / fps, 2) for i in range(len(away)) if away[i] and (i == 0 or not away[i - 1])]


def sync(take_sound: np.ndarray, clap_wall: float, tv_started: float, tv_flashes: list[float] | None = None) -> dict:
    """The take's clap, lined up with the TV recording: the TV's second at the take's first frame (--tv-offset), and
    where to start the piece (just after the clap and the TV's flash)."""
    found = find_clap(take_sound)
    if not found:
        return {"error": "no clap in the take's sound"}
    at, match = found[0]
    sure = round(1 - (found[1][1] / match if len(found) > 1 else 0.0), 2)  # how far it stands above the next best
    tv_clap = clap_wall - tv_started  # the TV recording's second when Andy clapped
    out = {"clap": at, "match": match, "sure": sure, "tv_offset": round(tv_clap - at, 2), "start": round(max(at + 1.2, at - tv_clap + 0.1), 2)}
    if tv_flashes is not None:  # the TV's own flash: as the clap is sent, give or take a poll (the page asks every 0.4 s)
        near = [f - tv_clap for f in tv_flashes if -1.0 <= f - tv_clap <= 2.0]
        out["flash_after_clap"] = round(near[0], 2) if near else None
    return out


def without_clap(spans: list[tuple], clap_at: float | None, clap_s: float = 0.45) -> list[tuple]:
    """The speech spans with Andy's clap cut out (November 3, a dry run: Omnilingual ASR wrote "The world war I was
    problem" for its two notes, and the piece, starting just after the clap, would have shown it for half a second);
    speech that runs on past the clap keeps its part, if 0.3 s or more."""
    if clap_at is None:
        return list(spans)
    out, a0, b0 = [], clap_at - 0.05, clap_at + clap_s
    for a, b in spans:
        if b <= a0 or a >= b0:
            out.append((a, b))
            continue
        if a0 - a >= 0.3:
            out.append((a, a0))
        if b - b0 >= 0.3:
            out.append((b0, b))
    return out


def transcribe(samples: np.ndarray, url: str, language: str) -> str:
    req = urllib.request.Request(url.rstrip("/") + "/transcribe", data=samples.astype("<f4").tobytes(), method="POST",
                                 headers={"X-Sample-Rate": str(RATE), "X-Language": language})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)["text"]


def tidy(text: str) -> str:
    """The hearing writes lowercase without punctuation: a capital to start, and Andy's name and "I" capitalised."""
    words = [{"andy": "Andy", "i": "I", "i'm": "I'm", "i'll": "I'll", "i've": "I've"}.get(w, w) for w in text.split()]
    line = " ".join(words)
    return line[:1].upper() + line[1:]


def readable(lines: list[tuple], per_word_s: float = 0.3, least_s: float = 1.2) -> list[tuple]:
    """Keep each caption up long enough to read, into the pause after it but never over the next one."""
    out = []
    for i, (a, b, text) in enumerate(lines):
        nxt = lines[i + 1][0] if i + 1 < len(lines) else float("inf")
        want = a + max(least_s, per_word_s * len(text.split()))
        out.append((a, round(max(b, min(want, nxt - 0.05)), 2), text))
    return out


def stamp(t: float) -> str:
    ms = int(round(max(0.0, t) * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def srt(lines: list[tuple]) -> str:
    return "".join(f"{i}\n{stamp(a)} --> {stamp(b)}\n{text}\n\n" for i, (a, b, text) in enumerate(lines, 1))


def read_srt(text: str) -> list[tuple]:
    def secs(s):
        h, m, rest = s.strip().split(":")
        return int(h) * 3600 + int(m) * 60 + float(rest.replace(",", "."))

    lines = []
    for block in text.strip().split("\n\n"):
        rows = block.strip().splitlines()
        if len(rows) >= 3 and "-->" in rows[1]:
            a, b = rows[1].split("-->")
            lines.append((secs(a), secs(b), "\n".join(rows[2:])))
    return lines


def shifted(lines: list[tuple], start: float, end: float | None) -> list[tuple]:
    """The captions of a piece cut from start to end, timed from the piece's own first frame."""
    out = []
    for a, b, text in lines:
        if b <= start or (end is not None and a >= end):
            continue
        out.append((max(a, start) - start, (min(b, end) if end is not None else b) - start, text))
    return out


def fit(w: int, h: int) -> str:
    return f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black"


def quoted(path: Path) -> str:
    """A path inside an ffmpeg filter option."""
    return "'" + str(path).replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:") + "'"


def burn_command(take: Path, out: Path, tv: Path | None, tv_offset: float, start: float, end: float | None,
                 shape: str, subtitles: Path | None, badge_file: Path | None) -> list[str]:
    w, h = SHAPES[shape]
    cmd = [FFMPEG, "-v", "error", "-y", "-ss", str(start)] + (["-to", str(end)] if end is not None else [])
    cmd += ["-i", str(take)]
    if tv:
        cmd += ["-ss", str(max(0.0, tv_offset + start)), "-i", str(tv)]
        if shape == "wide":  # side by side: the robot on the left, the TV on the right
            graph = "[0:v]scale=-2:1080[a];[1:v]scale=-2:1080[b];[a][b]hstack=shortest=1,"
        else:  # one above the other for a phone: the robot on top
            graph = "[0:v]scale=1080:-2[a];[1:v]scale=1080:-2[b];[a][b]vstack=shortest=1,"
        graph += fit(w, h)
    else:
        graph = "[0:v]" + fit(w, h)
    size = round(h / 22 if shape == "wide" else w / 20)
    if subtitles:  # libass sizes captions on a 288-line canvas: pixels * 288 / height
        unit, px = 288 / h, (h / 18 if shape == "wide" else w / 13)  # large on a phone
        style = (f"FontName=Atkinson Hyperlegible Next,FontSize={px * unit:.1f},Outline={3 * unit:.2f},"
                 f"Shadow=0,BorderStyle=1,MarginV={round(h * 0.09 * unit)}")
        graph += f",subtitles={quoted(subtitles)}:fontsdir={quoted(FONTS)}:force_style='{style}'"
    if badge_file:
        graph += (f",drawtext=fontfile={quoted(FONTS / 'AtkinsonHyperlegibleNext.ttf')}:textfile={quoted(badge_file)}"
                  f":fontsize={round(size * 0.7)}:fontcolor=white:box=1:boxcolor=black@0.55:boxborderw={size // 3}"
                  f":x={size}:y={size}")
    cmd += ["-filter_complex", graph + "[v]", "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-crf", "18",
            "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart"]
    if end is not None:
        cmd += ["-t", str(end - start)]
    return cmd + [str(out)]


def probe(path: Path) -> dict:
    """A file's length in seconds and whether it has sound."""
    out = subprocess.run([FFMPEG.replace("ffmpeg", "ffprobe"), "-v", "error", "-show_entries", "format=duration:stream=codec_type",
                          "-of", "json", str(path)], capture_output=True, text=True, check=True).stdout
    info = json.loads(out)
    return {"seconds": float(info["format"]["duration"]),
            "sound": any(s_.get("codec_type") == "audio" for s_ in info.get("streams", []))}


def cut_command(pieces: list[dict], out: Path, size=(1920, 1080), fps: int = 30) -> list[str]:
    """One video from the pieces, in order: each scaled into 1920x1080 on the TV's ground, 30 frames a second, its sound
    (silence for a card, which has none) at 48 kHz stereo, trimmed if asked; then the whole one's loudness evened out to
    -16 LUFS, as video sites expect, so a quiet robot and a loud card don't jump."""
    w, h = size
    cmd, parts = [FFMPEG, "-v", "error", "-y"], []
    for i, p in enumerate(pieces):
        cmd += ["-i", str(p["path"])]
        start, end = p.get("start", 0.0), p.get("end") or p["seconds"]
        parts.append(f"[{i}:v]trim={start}:{end},setpts=PTS-STARTPTS,scale={w}:{h}:force_original_aspect_ratio=decrease,"
                     f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=0x0b110f,fps={fps},format=yuv420p,setsar=1[v{i}]")
        if p["sound"]:
            parts.append(f"[{i}:a]atrim={start}:{end},asetpts=PTS-STARTPTS,aresample=48000,"
                         f"aformat=sample_fmts=fltp:channel_layouts=stereo[a{i}]")
        else:
            parts.append(f"anullsrc=r=48000:cl=stereo,atrim=0:{end - start},aformat=sample_fmts=fltp[a{i}]")
    joined = "".join(f"[v{i}][a{i}]" for i in range(len(pieces)))
    parts.append(f"{joined}concat=n={len(pieces)}:v=1:a=1[v][a0]")
    parts.append("[a0]loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[a]")
    return cmd + ["-filter_complex", ";".join(parts), "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "18",
                  "-preset", "medium", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)]


def plan(path: Path) -> list[dict]:
    """film/cut.json: [{"path": "film/card-title.mp4", "label": "title"}, {"path": "film/find.mp4", "start": 0.4}, ...]
    (paths from the repository's top), each probed for its length and sound."""
    root = Path(__file__).resolve().parents[1]
    pieces = []
    for item in json.loads(path.read_text()):
        item = {"path": item} if isinstance(item, str) else dict(item)
        item["path"] = Path(item["path"]) if Path(item["path"]).is_absolute() else root / item["path"]
        if not item["path"].exists():
            raise SystemExit(f"no such piece: {item['path']}")
        item.update(probe(item["path"]))
        item.setdefault("label", item["path"].stem)
        pieces.append(item)
    return pieces


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="do", required=True)
    c = sub.add_parser("captions", help="write a take's captions (.srt) with Andy's hearing, to read and correct")
    c.add_argument("take", type=Path)
    c.add_argument("--voice-url", default="http://127.0.0.1:8092")
    c.add_argument("--language", default="eng_Latn", help="spa_Latn for a take in Spanish")
    y = sub.add_parser("sync", help="line the TV's recording up with a take, by the clap of 'take one' (filming mode)")
    y.add_argument("take", type=Path)
    y.add_argument("--tv", type=Path, required=True, help="the TV page's recording (scripts/record_tv.py), its .json beside it")
    y.add_argument("--take-number", type=int, help="which take in film/takes.json (default: the one in the TV recording)")
    y.add_argument("--takes", type=Path, default=Path(__file__).resolve().parents[1] / "film" / "takes.json")
    b = sub.add_parser("burn", help="make a piece: captions and badge burned in, the TV beside the robot")
    b.add_argument("take", type=Path)
    b.add_argument("--out", type=Path, required=True)
    b.add_argument("--tv", type=Path, help="the TV page's recording of the same take (scripts/record_tv.py)")
    b.add_argument("--tv-offset", type=float, default=0.0)
    b.add_argument("--start", type=float, default=0.0)
    b.add_argument("--end", type=float)
    b.add_argument("--shape", choices=SHAPES, default="wide", help="square or vertical for X")
    b.add_argument("--srt", type=Path, help="default: the take's own .srt, if there is one")
    b.add_argument("--badge", default=BADGE, help="'' for none")
    k = sub.add_parser("cut", help="the pieces and cards in order, one video: same size, sound evened out, <= 3:00")
    k.add_argument("plan", type=Path, help="film/cut.json: the pieces in order (see plan())")
    k.add_argument("--out", type=Path, required=True)
    k.add_argument("--limit", type=float, default=180.0, help="the rules' 3 minutes; it stops if the cut is longer")
    args = ap.parse_args()

    if args.do == "cut":
        pieces, at = plan(args.plan), 0.0
        for p in pieces:
            length = (p.get("end") or p["seconds"]) - p.get("start", 0.0)
            print(f"{int(at // 60)}:{at % 60:05.2f}  {p['label']:24} {length:5.1f} s{'' if p['sound'] else '  (silent: a card)'}")
            at += length
        print(f"{int(at // 60)}:{at % 60:05.2f}  the end")
        if at > args.limit:
            raise SystemExit(f"{at:.1f} s is over the {args.limit:.0f} s limit: trim a piece (\"end\" in the plan) first")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(cut_command(pieces, args.out), check=True)
        made = probe(args.out)
        print(f"made {args.out}: {made['seconds']:.1f} s, 1920x1080, sound evened out to -16 LUFS")
        return

    if args.do == "sync":
        started = json.loads(args.tv.with_suffix(".json").read_text())["started"]
        takes = [t for session in json.loads(args.takes.read_text())["sessions"] for t in session["takes"]]
        if args.take_number is not None:
            takes = [t for t in takes if t["take"] == args.take_number]
        takes = [t for t in takes if t["clap"] >= started] or takes  # clapped while the TV was recording
        if not takes:
            raise SystemExit(f"no take {args.take_number} in {args.takes}")
        t = min(takes, key=lambda t: abs(t["clap"] - started))
        r = sync(audio(args.take), t["clap"], started, flashes(args.tv))
        if "error" in r:
            raise SystemExit(r["error"] + ": was it filmed in filming mode, with 'take one' said on camera?")
        print(f"take {t['take']}: the clap at {r['clap']:.2f} s in {args.take.name} (sure {r['sure']:.0%}); "
              f"the TV recording's {t['clap'] - started:.2f} s")
        if r.get("flash_after_clap") is not None:  # the flash shows as the clap is sent; the speaker plays it ~0.65 s later
            x = r["flash_after_clap"]
            print(f"  checked: the TV's own flash is in its recording {abs(x):.2f} s {'before' if x < 0 else 'after'} the clap "
                  f"(expected within a second{'' if t.get('heard') else ': this clap was timed when sent, not heard'})")
        elif "flash_after_clap" in r:
            print("  the TV's flash isn't in its recording near the clap: was it recording then?")
        if r["sure"] < 0.3:
            print("  not sure: listen at that second for the two notes before using it")
        print(f"\n  uv run python scripts/make_film.py burn {args.take} --tv {args.tv} --tv-offset {r['tv_offset']} "
              f"--start {r['start']} --out film/take{t['take']}.mp4")
        return

    if args.do == "captions":
        sound = audio(args.take)
        lines = []
        claps = [at for at, match in find_clap(sound) if match >= 0.6]  # the take's own clap: 0.98, anything else ~0.3
        for a, b_ in without_clap(speech_spans(sound), claps[0] if claps else None):
            text = tidy(transcribe(sound[int(a * RATE): int(b_ * RATE)], args.voice_url, args.language))
            if text:
                lines.append((a, b_, text))
                print(f"{stamp(a)}  {text}")
        out = args.take.with_suffix(".srt")
        out.write_text(srt(readable(lines)), encoding="utf-8")
        print(f"\n{len(lines)} captions -> {out}: check every word before burning them in (names, Andy's own lines).")
        return

    srt_path = args.srt or (args.take.with_suffix(".srt") if args.take.with_suffix(".srt").exists() else None)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        subs = badge = None
        if srt_path:
            subs = Path(tmp) / "captions.srt"
            subs.write_text(srt(shifted(read_srt(srt_path.read_text(encoding="utf-8")), args.start, args.end)),
                            encoding="utf-8")
        if args.badge:
            badge = Path(tmp) / "badge.txt"
            badge.write_text(args.badge, encoding="utf-8")
        cmd = burn_command(args.take, args.out, args.tv, args.tv_offset, args.start, args.end, args.shape, subs, badge)
        subprocess.run(cmd, check=True)
    print(f"made {args.out} ({args.shape}{', captions' if srt_path else ''}{', badge' if args.badge else ''})")


if __name__ == "__main__":
    main()
