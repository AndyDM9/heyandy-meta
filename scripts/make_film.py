"""Filming day's takes, made into the video's pieces: captions, the badge, the robot and the TV side by side, the X clip.

Everything runs on this computer: the captions come from Andy's own hearing (Omnilingual ASR, the heyandy-voice
service), and nothing is uploaded. Takes and what's made from them go in film/ (git-ignored).

    uv run python scripts/make_film.py captions film/take1.mp4        # -> film/take1.srt: read it, fix any word
    uv run python scripts/make_film.py burn film/take1.mp4 --tv film/tv-take1.webm --tv-offset 0.8 --out film/find.mp4
    uv run python scripts/make_film.py burn film/take1.mp4 --start 12 --end 42 --shape square --out film/x-clip.mp4

One take in, one piece out, so the badge ("autonomous · uncut · 1× speed") is true by construction. A piece across a
time cut (the reminder, two minutes later) says so: --badge "autonomous · 1× speed · two minutes later".
--tv-offset is the second of the TV recording that matches the take's first frame (Andy's first word is an easy mark).
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


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="do", required=True)
    c = sub.add_parser("captions", help="write a take's captions (.srt) with Andy's hearing, to read and correct")
    c.add_argument("take", type=Path)
    c.add_argument("--voice-url", default="http://127.0.0.1:8092")
    c.add_argument("--language", default="eng_Latn", help="spa_Latn for a take in Spanish")
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
    args = ap.parse_args()

    if args.do == "captions":
        sound = audio(args.take)
        lines = []
        for a, b_ in speech_spans(sound):
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
