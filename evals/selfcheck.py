"""Andy's check of itself, on the robot: once as it is, once with a service stopped on purpose (--stop heyandy-depth).

The app is built as the service builds it (the voice too) with a scratch memory; "are you OK?" is asked and the parts,
their timings and what Andy said are kept. With --stop, that service is stopped first and started again after.

    systemctl --user stop heyandy-app
    GST_PLUGIN_PATH=~/.local/gst-plugins-rs/lib/x86_64-linux-gnu/gstreamer-1.0 uv run python -m evals.selfcheck --stop heyandy-depth
    systemctl --user start heyandy-app
"""
import argparse
import json
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from heyandy_meta.__main__ import build


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stop", default="", help="a service to stop for the second check (started again after)")
    ap.add_argument("--out", default="evals/results")
    args = ap.parse_args()
    andy = build(argparse.Namespace(
        data=tempfile.mkdtemp(prefix="andy-check-"), robot=True, voice=True, no_cloud=True, offline=False,
        no_local_agent=True, glimmer="http://127.0.0.1:8080/v1", guard="http://127.0.0.1:8094",
        sam="http://127.0.0.1:8090", voice_url="http://127.0.0.1:8092", depth="http://127.0.0.1:8096",
        voice_name="eng", home="", staged_scene=False))
    hearing = threading.Event()  # the microphones feed Andy's ear, as the voice loop does in the service

    def ear():
        for samples, flag, yaw in andy.body.listen(hearing):
            andy.ear(samples, flag, yaw)

    threading.Thread(target=ear, daemon=True).start()
    time.sleep(6.0)
    runs = []
    for stopped in ["", args.stop] if args.stop else [""]:
        if stopped:
            subprocess.run(["systemctl", "--user", "stop", stopped], check=True)
        try:
            started = time.monotonic()
            with andy.lock:
                said = andy.hear("Hey Andy, are you OK?")
            runs.append({"stopped": stopped or None, "said": said, "seconds": round(time.monotonic() - started, 1),
                         "parts": andy.screen.snapshot()["checked"]})
            print(json.dumps(runs[-1], indent=1))
        finally:
            if stopped:
                subprocess.run(["systemctl", "--user", "start", stopped], check=True)
    hearing.set()
    out = Path(args.out) / f"selfcheck-{time.strftime('%Y%m%d-%H%M')}.json"
    out.write_text(json.dumps({"when": time.strftime("%Y-%m-%d %H:%M"), "runs": runs}, indent=1))
    print(f"saved {out}")


if __name__ == "__main__":
    main()
