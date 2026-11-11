"""Executable specification of the local audio interface (#25). NOT firmware.

Models what the glasses must do with an installed voice catalog and incoming
suggestions, so the rules in docs/protocol/audio-local.md are testable on a
computer. The real arbitration and playback belong to #18 (ESP32, C++).
Vibration is outside this model: nothing here may gate or delay it.
"""
