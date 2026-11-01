"""Filming mode on the robot: "we're filming", then takes; each take's clap timed by Andy's own microphones.

The app is built as the service builds it (the voice too) with a scratch memory and takes log. Each "take N" plays the
clap on the robot's speaker; the time it was sent and the time Andy's microphones heard it are kept, with whether it
was heard at all (a take whose clap isn't heard keeps the time it was sent, as before).

    systemctl --user stop heyandy-app
    GST_PLUGIN_PATH=~/.local/gst-plugins-rs/lib/x86_64-linux-gnu/gstreamer-1.0 uv run python -m evals.filming --takes 6
    systemctl --user start heyandy-app
"""
import argparse
import json
import tempfile
import threading
import time
from pathlib import Path

from heyandy_meta.__main__ import build


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--takes", type=int, default=6)
    ap.add_argument("--out", default="evals/results")
    args = ap.parse_args()
    data = tempfile.mkdtemp(prefix="andy-film-")
    andy = build(argparse.Namespace(
        data=data, robot=True, voice=True, no_cloud=True, offline=False,
        no_local_agent=True, glimmer="http://127.0.0.1:8080/v1", guard="http://127.0.0.1:8094",
        sam="http://127.0.0.1:8090", voice_url="http://127.0.0.1:8092", depth="http://127.0.0.1:8096",
        voice_name="eng", home="", staged_scene=False))
    andy.film_log = Path(data) / "takes.json"
    hearing = threading.Event()  # the microphones run, as the voice loop runs them in the service

    def ear():
        for samples, flag, yaw in andy.body.listen(hearing):
            andy.ear(samples, flag, yaw)

    threading.Thread(target=ear, daemon=True).start()
    time.sleep(4.0)
    on = andy.hear("Hey Andy, we're filming")
    takes = []
    for n in range(1, args.takes + 1):
        started = time.monotonic()
        said = andy.hear(f"take {n}")
        took = time.monotonic() - started
        take = andy.filming["takes"][-1]
        sent = take["clap"]
        time.sleep(3.0)  # the clap is found in the microphones' sound meanwhile
        takes.append({"take": n, "said": said, "turn_s": round(took, 2), "heard": take["heard"],
                      "heard_after_sent_s": round(take["clap"] - sent, 3) if take["heard"] else None,
                      "match": take.get("match"),
                      "flash": andy.screen.flashes})
        print(json.dumps(takes[-1]))
    cut = andy.hear("cut")
    wrap = andy.hear("that's a wrap")
    hearing.set()
    log = json.loads(andy.film_log.read_text())
    out = Path(args.out) / f"filming-{time.strftime('%Y%m%d-%H%M')}.json"
    result = {"when": time.strftime("%Y-%m-%d %H:%M"), "film_on": on, "takes": takes, "cut": cut, "wrap": wrap,
              "heard": sum(t["heard"] for t in takes), "of": len(takes), "log": log}
    out.write_text(json.dumps(result, indent=1))
    print(on, "|", cut, "|", wrap)
    print(f"heard {result['heard']} of {result['of']}; saved {out}")


if __name__ == "__main__":
    main()
