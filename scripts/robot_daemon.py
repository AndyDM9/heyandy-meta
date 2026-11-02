"""Pollen's Reachy Mini daemon, with the camera's feed to apps on this computer at another rate when asked.

Pollen's media server caps that feed at 10 frames a second (``IPC_FPS``, "it also paces every client"), though the
Lite's camera captures 1920x1080 at 60 (measured November 1: the daemon at 27% of one core). Andy finds things from
still frames, where 10 is plenty; the cup game follows cups crossing fast, and in simulated shuffles it picked the
right cup in 3 of 5 at 10 frames a second and lost them in all 4 at 5 (docs/research.md sections 18, 29). So
``HEYANDY_CAMERA_FPS=20`` (say) raises the cap for a test of the cup game. Off unless it's set: nothing changes for
the filming. Started by scripts/run-robot-daemon.sh only when HEYANDY_CAMERA_FPS is set.
"""
import os
import sys


def cap(env=os.environ) -> int | None:
    """The rate asked for, within what the camera does (1 to 60 frames a second); None: Pollen's own."""
    raw = env.get("HEYANDY_CAMERA_FPS", "").strip()
    if not raw:
        return None
    fps = int(raw)
    if not 1 <= fps <= 60:
        raise SystemExit(f"HEYANDY_CAMERA_FPS={raw}: the Lite's camera does 1 to 60 frames a second")
    return fps


def main() -> int:
    from reachy_mini.media import media_server

    fps = cap()
    if fps is not None:
        print(f"camera feed to local apps: {fps} frames a second (Pollen's default {media_server.IPC_FPS})", flush=True)
        media_server.IPC_FPS = fps  # read when the pipeline is built, in this same process
    from reachy_mini.daemon.app.main import main as daemon

    return daemon()


if __name__ == "__main__":
    sys.exit(main())
