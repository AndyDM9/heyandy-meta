#!/usr/bin/env bash
# Before the robot's daemon starts: wait (up to $1 seconds, default 900) until the camera and the sound card are there
# AND this user may open them. The daemon looks for them once as it starts; started before the login that grants
# access (if the user isn't in the video and audio groups), it runs with no camera and Andy is blind.
limit="${1:-900}"
for _ in $(seq "$limit"); do
  for c in /dev/v4l/by-id/*Reachy_Mini_Camera*index0; do
    for a in /dev/snd/by-id/*Reachy_Mini_Audio*; do
      [ -r "$c" ] && [ -r "$a" ] && exit 0
    done
  done
  sleep 1
done
echo "No access to the robot's camera or sound card after ${limit} s; starting the daemon anyway."
exit 0
