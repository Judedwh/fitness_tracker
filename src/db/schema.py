"""
db/schema.py
------------
Creates the SQLite database and all tables.
Run directly to initialise: python src/db/schema.py
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "gym.db"


def get_connection() -> sqlite3.Connection:
    """Return a connection to the SQLite database."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # lets you access columns by name
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialise_db() -> None:
    """Create all tables if they don't already exist."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        -- One row per unique workout session
        CREATE TABLE IF NOT EXISTS workouts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at  TEXT NOT NULL UNIQUE,   -- ISO timestamp from Strong
            name        TEXT NOT NULL,
            duration_mins INTEGER
        );

        -- One row per set logged
        CREATE TABLE IF NOT EXISTS sets (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            workout_id   INTEGER NOT NULL REFERENCES workouts(id),
            exercise     TEXT NOT NULL,
            set_order    INTEGER NOT NULL,
            weight_kg    REAL,
            reps         INTEGER,
            distance_m   REAL,
            seconds      REAL,
            notes        TEXT,
            rpe          REAL,
            -- Epley 1RM estimate: weight * (1 + reps/30)
            one_rm_kg    REAL GENERATED ALWAYS AS (
                CASE
                    WHEN reps > 0 AND weight_kg > 0
                    THEN ROUND(weight_kg * (1.0 + reps / 30.0), 1)
                    ELSE NULL
                END
            ) STORED
        );

        -- Lookup table — populated from data seen in imports
        CREATE TABLE IF NOT EXISTS exercises (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT NOT NULL UNIQUE,
            category      TEXT,   -- e.g. Push / Pull / Legs / Core
            primary_muscle TEXT
        );

        -- Track which CSV files have been ingested (avoid duplicates)
        CREATE TABLE IF NOT EXISTS import_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            filename    TEXT NOT NULL UNIQUE,
            imported_at TEXT NOT NULL DEFAULT (datetime('now')),
            rows_added  INTEGER
        );
    """)

    conn.commit()
    conn.close()
    print(f"✅ Database initialised at {DB_PATH}")


if __name__ == "__main__":
    initialise_db()
