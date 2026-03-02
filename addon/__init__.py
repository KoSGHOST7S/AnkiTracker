"""
AnkiTracker — GitHub Study Logger

Hooks into Anki's profile_will_close event and calls the tracker script
on the host system via flatpak-spawn (required to escape Flatpak's sandbox).
"""

import os
import subprocess
from datetime import datetime

from aqt import gui_hooks

TRACKER_SCRIPT = os.path.expanduser("~/Desktop/ankitracker/track.py")
# Anki's own data dir — always writable from inside the Flatpak sandbox
LOG_FILE = os.path.expanduser("~/.var/app/net.ankiweb.Anki/data/ankitracker.log")


def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a") as f:
        f.write(f"[{ts}] {msg}\n")


def on_profile_will_close() -> None:
    log("profile_will_close fired")
    try:
        cmd = ["flatpak-spawn", "--host", "/usr/bin/python3", TRACKER_SCRIPT]
        log(f"running: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        log(f"exit code: {result.returncode}")
        if result.stdout:
            log(f"stdout: {result.stdout.strip()}")
        if result.stderr:
            log(f"stderr: {result.stderr.strip()}")
    except Exception as e:
        log(f"exception: {e}")


gui_hooks.profile_will_close.append(on_profile_will_close)
log("AnkiTracker add-on loaded")
