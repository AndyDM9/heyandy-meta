#!/usr/bin/env bash
# Pollen's Reachy Mini daemon (motors, camera, microphones, speaker) for the Lite on USB, from this repository's own
# environment (the robot extra installs it), so everything the robot needs is here.
set -euo pipefail
cd "$(dirname "$0")/.."
# The robot's camera arrives over WebRTC: GStreamer's webrtc element is a local build of gst-plugins-rs.
export GST_PLUGIN_PATH="$HOME/.local/gst-plugins-rs/lib/x86_64-linux-gnu/gstreamer-1.0${GST_PLUGIN_PATH:+:$GST_PLUGIN_PATH}"
# The robot's speaker: the card at full, its output at HEYANDY_SPEAKER_LEVEL (default 80%, -12 dB; 58% until November 3,
# when the founder couldn't hear Andy well across the room).
card=$(awk '/Reachy Mini Audio/ {print $1; exit}' /proc/asound/cards)
if [ -n "$card" ]; then
  amixer -q -c "$card" sset 'PCM',0 100% || true
  amixer -q -c "$card" sset 'PCM',1 "${HEYANDY_SPEAKER_LEVEL:-80}%" || true
fi
sink=$(pactl list short sinks 2>/dev/null | awk '/Reachy_Mini_Audio/ {print $2; exit}')
[ -n "$sink" ] && pactl set-sink-volume "$sink" 100% || true
# Through scripts/robot_daemon.py: the camera's and microphones' stream offered on this computer only (Pollen's would
# listen on every address); and HEYANDY_CAMERA_FPS (unset: Pollen's 10) raises the camera's feed to apps here.
exec .venv/bin/python scripts/robot_daemon.py --headless "$@"
