"""Pollen's Reachy Mini daemon, its camera's and microphones' stream offered on this computer only; and the camera's
feed to apps here at another rate when asked.

The stream: Pollen's media server starts webrtcsink's own signalling server, the door a WebRTC client knocks on for
the camera's picture and the microphones' sound, and webrtcsink listens on every address unless told otherwise
(0.0.0.0:8443): anyone on the home network could have asked for them. Found November 3 (a review of Andy's ports;
`ss -ltn` showed 0.0.0.0:8443, and the system card says nothing of Andy's is on the network). Everything that uses it
is on this computer and connects to 127.0.0.1:8443 (the daemon's own relay, its dashboard through it) or localhost, so
it's told 127.0.0.1. scripts/preflight.py checks it.

Remote access through Pollen's cloud, off: finding this computer's Hugging Face login, Pollen's daemon registers the
robot with its central signalling relay (pollen-robotics-reachy-mini-central.hf.space), so the owner's account could
open the camera's and microphones' stream from anywhere, through TURN servers on the internet. Andy never uses it
(everything of Andy's is on this computer), and its promise is that pictures and voice stay home, so the relay never
starts. Found November 3: its log since October 30 shows the relay running and no stream ever opened, local or remote.

The rate:

Pollen's media server caps that feed at 10 frames a second (``IPC_FPS``, "it also paces every client"), though the
Lite's camera captures 1920x1080 at 60 (measured November 1: the daemon at 27% of one core). Andy finds things from
still frames, where 10 is plenty; the cup game follows cups crossing fast, and in simulated shuffles it picked the
right cup in 3 of 5 at 10 frames a second and lost them in all 4 at 5 (docs/research.md sections 18, 29). So
``HEYANDY_CAMERA_FPS=20`` (say) raises the cap for a test of the cup game. Off unless it's set: nothing changes for
the filming. scripts/run-robot-daemon.sh starts the daemon through this file.
"""
import os
import sys

LOCAL = "127.0.0.1"  # where the stream's signalling server listens: this computer only


def cap(env=os.environ) -> int | None:
    """The rate asked for, within what the camera does (1 to 60 frames a second); None: Pollen's own."""
    raw = env.get("HEYANDY_CAMERA_FPS", "").strip()
    if not raw:
        return None
    fps = int(raw)
    if not 1 <= fps <= 60:
        raise SystemExit(f"HEYANDY_CAMERA_FPS={raw}: the Lite's camera does 1 to 60 frames a second")
    return fps


def local_only(media_server, host: str = LOCAL) -> None:
    """Pollen's media server, made to start its stream's signalling server on this computer only. Raises if Pollen's
    code no longer has the step it wraps, so the daemon doesn't start offering the stream to the network unnoticed."""
    server = media_server.GstMediaServer
    made = server._configure_webrtc  # AttributeError: Pollen changed it; better not to start than to start wide open
    if getattr(made, "local_only", None) == host:
        return

    def configure(self, pipeline):
        sink = made(self, pipeline)
        sink.set_property("signalling-server-host", host)  # before the pipeline plays, when the server starts
        return sink

    configure.local_only = host
    server._configure_webrtc = configure


def no_remote(daemon_module) -> None:
    """Pollen's daemon, made never to start its central signalling relay (remote access through Pollen's cloud). Raises
    if Pollen's code no longer has the step it replaces, so the relay doesn't start unnoticed."""
    daemon = daemon_module.Daemon
    if not hasattr(daemon, "_start_central_signaling_relay"):  # Pollen changed it: better not to start than to start open
        raise AttributeError("Pollen's daemon has no _start_central_signaling_relay: check how it starts its relay")

    async def off(self) -> None:
        self.logger.info("remote access through Pollen's cloud: off (scripts/robot_daemon.py)")

    off.no_remote = True
    daemon._start_central_signaling_relay = off


def main() -> int:
    from reachy_mini.daemon import daemon as daemon_module
    from reachy_mini.media import media_server

    local_only(media_server)
    no_remote(daemon_module)
    print(f"the camera's and microphones' stream: offered on {LOCAL} only; remote access through Pollen's cloud: off",
          flush=True)
    fps = cap()
    if fps is not None:
        print(f"camera feed to local apps: {fps} frames a second (Pollen's default {media_server.IPC_FPS})", flush=True)
        media_server.IPC_FPS = fps  # read when the pipeline is built, in this same process
    from reachy_mini.daemon.app.main import main as daemon

    return daemon()


if __name__ == "__main__":
    sys.exit(main())
