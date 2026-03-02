"""
AnkiTracker — GitHub Study Logger

Hooks into Anki's profile_will_close event and calls the tracker script
on the host system via flatpak-spawn (required to escape Flatpak's sandbox).
"""

import os
import subprocess

from aqt import gui_hooks

TRACKER_SCRIPT = os.path.expanduser("~/Desktop/ankitracker/track.py")


def on_profile_will_close() -> None:
    try:
        subprocess.Popen(
            ["flatpak-spawn", "--host", "python3", TRACKER_SCRIPT],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


gui_hooks.profile_will_close.append(on_profile_will_close)
