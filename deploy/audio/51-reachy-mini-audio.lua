-- WirePlumber 0.4: the robot's audio device is the robot daemon's, never the desktop's (research.md section 77).
-- Lowest priority, so the desktop never picks it as a default; held at the daemon's 16 kHz; never suspended, so its
-- interface isn't switched when idle. Not installed by default; with heyandy-desktop-fallback.conf:
--   install -D -m 644 deploy/audio/51-reachy-mini-audio.lua ~/.config/wireplumber/main.lua.d/51-reachy-mini-audio.lua
--   then the restarts in heyandy-desktop-fallback.conf.
rule = {
  matches = {
    { { "node.name", "matches", "alsa_output.usb-Pollen_Robotics_Reachy_Mini_Audio*" } },
    { { "node.name", "matches", "alsa_input.usb-Pollen_Robotics_Reachy_Mini_Audio*" } },
  },
  apply_properties = {
    ["priority.session"] = 1,
    ["priority.driver"] = 1,
    ["audio.rate"] = 16000,
    ["session.suspend-timeout-seconds"] = 0,
  },
}
table.insert(alsa_monitor.rules, rule)
