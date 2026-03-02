#!/usr/bin/env python3
"""
One-time setup for Anki Tracker.

Run this once to configure the git remote and install the Anki add-on.
Make sure Anki is closed before running.
"""

import shutil
import subprocess
import sys
from pathlib import Path

REPO_DIR = Path(__file__).parent.resolve()
ADDON_SRC = REPO_DIR / "addon"
ADDON_DEST = (
    Path.home() / ".var/app/net.ankiweb.Anki/data/Anki2/addons21/ankitracker"
)
GITHUB_REMOTE = "https://github.com/KoSGHOST7S/AnkiTracker.git"


def run(cmd: list, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kwargs)


def ok(msg: str) -> None:
    print(f"  ✓  {msg}")


def warn(msg: str) -> None:
    print(f"  ⚠  {msg}", file=sys.stderr)


def setup_git_remote() -> None:
    result = run(["git", "remote", "get-url", "origin"], cwd=REPO_DIR)
    if result.returncode == 0:
        ok(f"Git remote already set: {result.stdout.strip()}")
        return
    run(["git", "remote", "add", "origin", GITHUB_REMOTE], cwd=REPO_DIR)
    ok(f"Git remote set to {GITHUB_REMOTE}")


def setup_git_branch() -> None:
    run(["git", "branch", "-M", "main"], cwd=REPO_DIR)
    ok("Default branch set to 'main'")


def install_addon() -> None:
    if not ADDON_SRC.exists():
        warn(f"Add-on source not found at {ADDON_SRC}")
        return
    anki_addons_dir = ADDON_DEST.parent
    if not anki_addons_dir.exists():
        warn(
            f"Anki add-ons folder not found at {anki_addons_dir}\n"
            "     Make sure Anki has been opened at least once."
        )
        return
    if ADDON_DEST.exists():
        shutil.rmtree(ADDON_DEST)
    shutil.copytree(ADDON_SRC, ADDON_DEST)
    ok(f"Add-on installed to {ADDON_DEST}")


def check_git_config() -> bool:
    name = run(["git", "config", "user.name"]).stdout.strip()
    email = run(["git", "config", "user.email"]).stdout.strip()
    if name and email:
        ok(f"Git user: {name} <{email}>")
        return True
    print()
    warn("Git user not configured. Run these commands, then re-run setup.py:")
    print('       git config --global user.name "Your Name"')
    print('       git config --global user.email "you@example.com"')
    print("     (the email must match your GitHub account email)")
    return False


def make_initial_commit() -> None:
    result = run(["git", "log", "--oneline", "-1"], cwd=REPO_DIR)
    if result.returncode == 0 and result.stdout.strip():
        ok("Repo already has commits — skipping initial commit")
        return
    run(["git", "add", "."], cwd=REPO_DIR)
    run(
        ["git", "commit", "-m", "Initial commit — AnkiTracker setup"],
        cwd=REPO_DIR,
    )
    ok("Initial commit created")


def push_initial() -> None:
    result = run(["git", "push", "-u", "origin", "main"], cwd=REPO_DIR)
    if result.returncode == 0:
        ok("Pushed to GitHub")
    else:
        warn(f"Push failed: {result.stderr.strip()}")
        print("     You may need to authenticate. Try running:")
        print("       git push -u origin main")
        print("     If using HTTPS, set up a GitHub personal access token.")


def main() -> None:
    print("\nAnki Tracker Setup")
    print("=" * 40)

    setup_git_remote()
    setup_git_branch()
    install_addon()
    git_ok = check_git_config()

    if git_ok:
        make_initial_commit()
        push_initial()

    print("\n" + "=" * 40)
    print("Setup complete!\n")
    print("Next steps:")
    print("  1. Restart Anki for the add-on to load")
    print("  2. Study as usual, then close Anki")
    print("  3. Your stats will auto-commit to GitHub\n")
    print(f"  Repo: https://github.com/KoSGHOST7S/AnkiTracker")
    print()


if __name__ == "__main__":
    main()
