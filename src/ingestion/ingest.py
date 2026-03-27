"""
ingestion/ingest.py
-------------------
Ingests Strong app CSV exports into SQLite.

Usage:
    python src/ingestion/ingest.py                    # processes all new CSVs in data/exports/
    python src/ingestion/ingest.py --file path/to.csv # process a specific file
"""

import argparse
import re
import sqlite3
from pathlib import Path

import pandas as pd

# Add project root to path so we can import from src/
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.db.schema import get_connection, initialise_db

EXPORTS_DIR = Path(__file__).resolve().parents[2] / "data" / "exports"


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def parse_duration(duration_str: str) -> int | None:
    """
    Convert Strong's duration strings to total minutes.
    Examples: '54m' -> 54, '1h 23m' -> 83, '2h' -> 120
    """
    if not duration_str or pd.isna(duration_str):
        return None
    duration_str = str(duration_str).strip()
    hours = re.search(r"(\d+)h", duration_str)
    mins = re.search(r"(\d+)m", duration_str)
    total = 0
    if hours:
        total += int(hours.group(1)) * 60
    if mins:
        total += int(mins.group(1))
    return total if total > 0 else None


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise the raw Strong CSV into clean types."""
    df = df.copy()

    # Standardise column names
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # Parse date — Strong uses 'YYYY-MM-DD HH:MM:SS'
    df["date"] = pd.to_datetime(df["date"])

    # Duration string -> int (minutes)
    df["duration_mins"] = df["duration"].apply(parse_duration)

    # Numeric coercions
    df["weight"] = pd.to_numeric(df["weight"], errors="coerce")
    df["reps"] = pd.to_numeric(df["reps"], errors="coerce").astype("Int64")
    df["distance"] = pd.to_numeric(df["distance"], errors="coerce")
    df["seconds"] = pd.to_numeric(df["seconds"], errors="coerce")
    df["rpe"] = pd.to_numeric(df["rpe"], errors="coerce")

    # Clean text fields
    for col in ["notes", "workout_notes"]:
        if col in df.columns:
            df[col] = df[col].replace("", None).where(df[col].notna(), None)

    return df


# ---------------------------------------------------------------------------
# Ingestion logic
# ---------------------------------------------------------------------------

def ingest_file(csv_path: Path, conn: sqlite3.Connection) -> int:
    """
    Ingest a single Strong CSV into the database.
    Returns the number of sets inserted.
    """
    cursor = conn.cursor()

    # Check if already imported
    filename = csv_path.name
    cursor.execute("SELECT id FROM import_log WHERE filename = ?", (filename,))
    if cursor.fetchone():
        print(f"⏭️  Already imported: {filename} — skipping")
        return 0

    print(f"📂 Ingesting: {filename}")
    df = pd.read_csv(csv_path)
    df = clean_dataframe(df)

    rows_added = 0

    # Group by workout session (date + workout name uniquely identifies a session)
    session_groups = df.groupby(["date", "workout_name"])

    for (session_dt, workout_name), session_df in session_groups:
        session_str = session_dt.isoformat()
        duration_mins = session_df["duration_mins"].iloc[0]

        # Upsert workout row
        cursor.execute("""
            INSERT INTO workouts (started_at, name, duration_mins)
            VALUES (?, ?, ?)
            ON CONFLICT(started_at) DO NOTHING
        """, (session_str, workout_name, duration_mins))

        cursor.execute("SELECT id FROM workouts WHERE started_at = ?", (session_str,))
        workout_id = cursor.fetchone()[0]

        # Insert sets
        for _, row in session_df.iterrows():
            cursor.execute("""
                INSERT INTO sets (
                    workout_id, exercise, set_order, weight_kg, reps,
                    distance_m, seconds, notes, rpe
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                workout_id,
                row["exercise_name"],
                int(row["set_order"]) if pd.notna(row["set_order"]) else None,
                float(row["weight"]) if pd.notna(row["weight"]) else None,
                int(row["reps"]) if pd.notna(row["reps"]) else None,
                float(row["distance"]) if pd.notna(row["distance"]) else None,
                float(row["seconds"]) if pd.notna(row["seconds"]) else None,
                row.get("notes"),
                float(row["rpe"]) if pd.notna(row["rpe"]) else None,
            ))
            rows_added += 1

        # Upsert exercise lookup
        cursor.execute("""
            INSERT INTO exercises (name)
            VALUES (?)
            ON CONFLICT(name) DO NOTHING
        """, (row["exercise_name"],))

    # Log the import
    cursor.execute("""
        INSERT INTO import_log (filename, rows_added)
        VALUES (?, ?)
    """, (filename, rows_added))

    conn.commit()
    print(f"   ✅ Inserted {rows_added} sets from {len(session_groups)} sessions")
    return rows_added


def ingest_all(exports_dir: Path = EXPORTS_DIR) -> None:
    """Process all CSV files in the exports directory."""
    csv_files = sorted(exports_dir.glob("*.csv"))
    if not csv_files:
        print(f"No CSV files found in {exports_dir}")
        print("Export from Strong: Profile → Settings → Export Data → drop CSV in data/exports/")
        return

    initialise_db()
    conn = get_connection()

    total = 0
    for csv_path in csv_files:
        total += ingest_file(csv_path, conn)

    conn.close()
    print(f"\n🏁 Done. Total sets ingested this run: {total}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest Strong CSV exports into SQLite")
    parser.add_argument("--file", type=Path, help="Path to a specific CSV file to ingest")
    args = parser.parse_args()

    if args.file:
        initialise_db()
        conn = get_connection()
        ingest_file(args.file.resolve(), conn)
        conn.close()
    else:
        ingest_all()
