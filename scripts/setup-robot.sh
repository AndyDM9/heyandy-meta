#!/usr/bin/env bash
# The robot's side of Andy, once, on the computer the Reachy Mini Lite is plugged into (no sudo except where shown).
#   1. GStreamer's WebRTC and RTP plugins from gst-plugins-rs 0.14.5 (Pollen's daemon needs webrtcsrc/webrtcsink for
#      the robot's camera and microphones, even on this computer; Pollen pins 0.14.5). Needs Rust (rustup). Installed
#      under ~/.local/gst-plugins-rs, where scripts/run-robot-daemon.sh and deploy/heyandy-app.service look.
#   2. Pollen's recorded-emotions library, fetched now so Andy never waits on the network for it.
#   3. The robot's daemon as a user service (deploy/heyandy-robot.service), started at boot.
# The user needs the dialout (motor port), video and audio groups:
#   sudo usermod -aG dialout,video,audio "$USER"     (then log out and in, or restart)
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$HOME/.local/src/gst-plugins-rs"
PREFIX="$HOME/.local/gst-plugins-rs"
DEST="$PREFIX/lib/x86_64-linux-gnu/gstreamer-1.0"

if ! GST_PLUGIN_PATH="$DEST" gst-inspect-1.0 webrtcsrc >/dev/null 2>&1; then
  [ -d "$SRC" ] || git clone https://gitlab.freedesktop.org/gstreamer/gst-plugins-rs.git "$SRC"
  git -C "$SRC" -c advice.detachedHead=false checkout 0.14.5
  command -v cargo-cinstall >/dev/null || cargo install --locked cargo-c --version 0.10.22+cargo-0.96.0
  STAGE="$(mktemp -d)"
  trap 'rm -rf "$STAGE"' EXIT
  # Built to a staging folder and each library moved in with a rename, so a daemon already running keeps its copy.
  (cd "$SRC" && cargo cinstall -p gst-plugin-webrtc --prefix="$STAGE" --release)
  (cd "$SRC" && cargo cinstall -p gst-plugin-rtp --prefix="$STAGE" --release)  # rtpgccbwe, for webrtcsink
  mkdir -p "$DEST"
  for lib in "$STAGE"/lib/x86_64-linux-gnu/gstreamer-1.0/*.so; do
    cp "$lib" "$DEST/.$(basename "$lib").new" && mv -f "$DEST/.$(basename "$lib").new" "$DEST/$(basename "$lib")"
  done
fi
GST_PLUGIN_PATH="$DEST" gst-inspect-1.0 webrtcsrc >/dev/null && echo "GStreamer webrtc: ready in $DEST"

cd "$HERE"
uv sync -q --extra dev --extra robot --extra browse
uv run python -c "from reachy_mini.motion.recorded_move import RecordedMoves; \
print(len(RecordedMoves('pollen-robotics/reachy-mini-emotions-library').list_moves()), 'recorded emotions ready')"

systemctl --user link "$HERE/deploy/heyandy-robot.service"
systemctl --user daemon-reload
systemctl --user enable --now heyandy-robot
echo "The robot's daemon is running (heyandy-robot). Next: scripts/setup-local-models.sh, scripts/setup-depth.sh."
