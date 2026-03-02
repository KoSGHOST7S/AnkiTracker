#!/usr/bin/env python3
"""
Anki study session tracker.

Reads today's review stats from the Anki database, updates README.md,
and commits + pushes to GitHub. Called automatically by the Anki add-on
when you close Anki.
"""

import json
import os
import shutil
import sqlite3
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ANKI_DB = Path.home() / ".var/app/net.ankiweb.Anki/data/Anki2/User 1/collection.anki2"
REPO_DIR = Path(__file__).parent.resolve()
README_PATH = REPO_DIR / "README.md"
SESSIONS_PATH = REPO_DIR / "sessions.json"
DB_COPY_PATH = REPO_DIR / ".tmp_collection.anki2"


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def copy_db() -> None:
    """Copy the Anki DB and any WAL/SHM files to avoid locking issues."""
    shutil.copy2(ANKI_DB, DB_COPY_PATH)
    for ext in ("-wal", "-shm"):
        src = ANKI_DB.parent / (ANKI_DB.name + ext)
        if src.exists():
            shutil.copy2(src, DB_COPY_PATH.parent / (DB_COPY_PATH.name + ext))


def cleanup_db_copy() -> None:
    for suffix in ("", "-wal", "-shm"):
        p = DB_COPY_PATH.parent / (DB_COPY_PATH.name + suffix)
        if p.exists():
            p.unlink()


def get_deck_names(conn: sqlite3.Connection) -> dict:
    """Return {deck_id: deck_name} — handles both old and new Anki schemas."""
    try:
        rows = conn.execute("SELECT id, name FROM decks").fetchall()
        return {row[0]: row[1] for row in rows}
    except sqlite3.OperationalError:
        pass
    row = conn.execute("SELECT decks FROM col").fetchone()
    if row:
        data = json.loads(row[0])
        return {int(k): v["name"] for k, v in data.items()}
    return {}


def get_today_stats(conn: sqlite3.Connection) -> list:
    """Return per-deck stats for cards reviewed today."""
    today_start_ms = int(
        datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000
    )
    deck_names = get_deck_names(conn)
    rows = conn.execute(
        """
        SELECT c.did, COUNT(*) AS cards, SUM(r.time) AS total_ms
        FROM revlog r
        JOIN cards c ON r.cid = c.id
        WHERE r.id >= ?
        GROUP BY c.did
        ORDER BY cards DESC
        """,
        (today_start_ms,),
    ).fetchall()
    return [
        {
            "deck": deck_names.get(did, f"Deck {did}"),
            "cards": cards,
            "time_ms": total_ms or 0,
        }
        for did, cards, total_ms in rows
    ]


# ---------------------------------------------------------------------------
# Session log helpers
# ---------------------------------------------------------------------------

def load_sessions() -> list:
    if SESSIONS_PATH.exists():
        return json.loads(SESSIONS_PATH.read_text()).get("sessions", [])
    return []


def save_sessions(sessions: list) -> None:
    SESSIONS_PATH.write_text(json.dumps({"sessions": sessions}, indent=2))


# ---------------------------------------------------------------------------
# README generation
# ---------------------------------------------------------------------------

def calculate_streak(sessions: list) -> int:
    dates = {s["date"] for s in sessions}
    today = date.today()
    streak = 0
    for i in range(len(dates) + 1):
        if (today - timedelta(days=i)).isoformat() in dates:
            streak += 1
        else:
            break
    return streak


def build_heatmap(sessions: list) -> str:
    """28-day emoji heatmap, 4 rows of 7 days (oldest top-left, today bottom-right)."""
    dates = {s["date"] for s in sessions}
    today = date.today()
    cells = [
        "🟩" if (today - timedelta(days=i)).isoformat() in dates else "⬜"
        for i in range(27, -1, -1)
    ]
    rows = ["".join(cells[i : i + 7]) for i in range(0, 28, 7)]
    return "\n".join(rows)


def build_readme(deck_stats: list, sessions: list) -> str:
    today_str = datetime.now().strftime("%a %b %-d, %Y")
    total_cards = sum(d["cards"] for d in deck_stats)
    total_ms = sum(d["time_ms"] for d in deck_stats)
    total_min = round(total_ms / 60000)

    streak = calculate_streak(sessions)
    streak_label = f"🔥 {streak} day{'s' if streak != 1 else ''}" if streak else "0 days"

    deck_rows = "\n".join(
        f"| {d['deck']} | {d['cards']} | {round(d['time_ms'] / 60000)} min |"
        for d in deck_stats
    )
    deck_rows += f"\n| **Total** | **{total_cards}** | **{total_min} min** |"

    all_time_cards = sum(s["cards"] for s in sessions)
    all_time_ms = sum(s.get("time_ms", 0) for s in sessions)
    all_time_hours = all_time_ms / 3600000
    heatmap = build_heatmap(sessions)

    if all_time_hours >= 1:
        total_time_label = f"{all_time_hours:.1f} hrs"
    else:
        total_time_label = f"{round(all_time_ms / 60000)} min"

    # Session history table — most recent first, last 30 sessions
    recent = sorted(sessions, key=lambda s: s["date"], reverse=True)[:30]
    history_rows = "\n".join(
        f"| {s['date']} | {s['cards']:,} | {s.get('time_ms', 0) / 3600000:.1f} hrs |"
        for s in recent
    )

    return f"""\
# Anki Study Tracker

A custom Python integration that automatically tracks my daily [Anki](https://apps.ankiweb.net/) flashcard sessions and commits the stats here after every study session. Built with a Python script that reads directly from Anki's SQLite database and a custom Anki add-on that triggers it on close — no manual steps required.

**Streak:** {streak_label}

### Last 28 days
{heatmap}

### Today — {today_str}
| Deck | Cards | Time |
|------|-------|------|
{deck_rows}

### All-time
- Total sessions: {len(sessions):,}
- Total cards reviewed: {all_time_cards:,}
- Total time studied: {total_time_label}

### Session history
| Date | Cards | Time |
|------|-------|------|
{history_rows}

---
*Auto-updated by [ankitracker](https://github.com/KoSGHOST7S/AnkiTracker)*
"""


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def git_commit_push(total_cards: int, num_decks: int) -> str:
    deck_word = "deck" if num_decks == 1 else "decks"
    msg = f"Study session: {total_cards} cards across {num_decks} {deck_word} [{date.today().isoformat()}]"
    subprocess.run(
        ["git", "add", "README.md", "sessions.json"],
        cwd=REPO_DIR,
        check=True,
    )
    subprocess.run(["git", "commit", "-m", msg], cwd=REPO_DIR, check=True)
    result = subprocess.run(["git", "push"], cwd=REPO_DIR, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"⚠  Push failed: {result.stderr.strip()}", file=sys.stderr)
        print("   Commit was saved locally. Run 'git push' manually when ready.", file=sys.stderr)
    return msg


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    if not ANKI_DB.exists():
        print(f"Error: Anki database not found at {ANKI_DB}", file=sys.stderr)
        sys.exit(1)

    copy_db()
    try:
        conn = sqlite3.connect(str(DB_COPY_PATH))
        deck_stats = get_today_stats(conn)
        conn.close()
    finally:
        cleanup_db_copy()

    if not deck_stats:
        print("No cards reviewed today. Nothing to commit.")
        sys.exit(0)

    today_iso = date.today().isoformat()
    sessions = load_sessions()

    existing = next((s for s in sessions if s["date"] == today_iso), None)
    total_today = sum(d["cards"] for d in deck_stats)
    time_today_ms = sum(d["time_ms"] for d in deck_stats)

    if existing:
        existing["cards"] = total_today
        existing["time_ms"] = time_today_ms
        existing["decks"] = [d["deck"] for d in deck_stats]
    else:
        sessions.append(
            {
                "date": today_iso,
                "cards": total_today,
                "time_ms": time_today_ms,
                "decks": [d["deck"] for d in deck_stats],
            }
        )

    save_sessions(sessions)
    README_PATH.write_text(build_readme(deck_stats, sessions))

    msg = git_commit_push(total_today, len(deck_stats))
    print(f"✓ {msg}")


if __name__ == "__main__":
    main()
