"""
Import player_decision_quality.csv into Supabase (PostgreSQL).

Usage:
    python import_decision_quality.py
    python import_decision_quality.py --db-url "postgresql://..."
    python import_decision_quality.py --dry-run

Connection: reads SUPABASE_DB_URL or DATABASE_URL from environment,
or pass --db-url explicitly (same pattern as import_space_control.py).
"""
from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path

# CSV lives in H2_Decision_Quality/data/
DATA_DIR = Path(__file__).resolve().parents[3] / "H2_Decision_Quality" / "data"
CSV_NAME = "player_decision_quality.csv"

# .env lives in webapp/backend/
ENV_FILE = Path(__file__).resolve().parents[2] / "backend" / ".env"

# ── DDL ───────────────────────────────────────────────────────────────────────

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS player_decision_quality (
    player              TEXT    NOT NULL,
    team                TEXT    NOT NULL,
    primary_role        TEXT,
    macro_role          TEXT,
    minutes_played      NUMERIC,
    n_decisions         NUMERIC,

    -- Headline + companion
    "DQ_index"          NUMERIC,
    value_impact        NUMERIC,

    -- Radar axes (percentile within-role 0-100, already mirrored where needed)
    pct__accuracy       NUMERIC,
    pct__worst_choice   NUMERIC,
    pct__elite_per90    NUMERIC,
    pct__poor_per90     NUMERIC,

    -- Core stats — Raw
    score               NUMERIC,
    score_sd            NUMERIC,
    avg_miss_cost       NUMERIC,

    -- Core stats — Per 90
    elite_per90         NUMERIC,
    poor_per90          NUMERIC,

    -- Core stats — Percentages
    accuracy_pct        NUMERIC,
    worst_choice_pct    NUMERIC,

    PRIMARY KEY (player, team)
);
"""

# ── Helpers ───────────────────────────────────────────────────────────────────

TEXT_COLS = {"player", "team", "primary_role", "macro_role"}

# All numeric columns expected from the CSV.
# Any extra columns in the CSV are silently ignored.
NUMERIC_COLS = {
    "minutes_played", "n_decisions",
    "DQ_index", "value_impact",
    "pct__accuracy", "pct__worst_choice", "pct__elite_per90", "pct__poor_per90",
    "score", "score_sd", "avg_miss_cost",
    "elite_per90", "poor_per90",
    "accuracy_pct", "worst_choice_pct",
}


def _load_env_file() -> None:
    """Parse webapp/backend/.env and inject into os.environ (no python-dotenv needed)."""
    if not ENV_FILE.exists():
        return
    with open(ENV_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key   = key.strip()
            value = value.strip().strip("\"'")
            if key and key not in os.environ:
                os.environ[key] = value


def resolve_db_url(explicit: str | None) -> str | None:
    if explicit:
        return explicit
    _load_env_file()
    return os.getenv("SUPABASE_DB_URL") or os.getenv("DATABASE_URL")


def get_connection(db_url: str):
    try:
        import psycopg2
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency 'psycopg2-binary'. Install with: pip install psycopg2-binary"
        ) from exc
    return psycopg2.connect(db_url)


def _safe(v: str) -> str | None:
    """Return None for empty/nan strings so psycopg2 inserts NULL."""
    return None if v.strip() in ("", "nan", "NaN", "None") else v


# ── Import logic ──────────────────────────────────────────────────────────────

def load_decision_quality(cur) -> int:
    path = DATA_DIR / CSV_NAME
    count = 0

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        csv_cols = set(reader.fieldnames or [])

        # Warn about any expected numeric columns missing from the CSV
        missing = NUMERIC_COLS - csv_cols - TEXT_COLS
        if missing:
            print(f"  ⚠ These columns are missing from the CSV and will be NULL: {sorted(missing)}")

        for row in reader:
            # Build values dict: text cols as strings, numeric cols as float (or None)
            values: dict = {}
            for k, v in row.items():
                if k in TEXT_COLS:
                    values[k] = _safe(v)
                elif k in NUMERIC_COLS:
                    safe = _safe(v)
                    values[k] = float(safe) if safe is not None else None
                # extra CSV columns not in our schema are skipped

            # Fill any schema columns absent from CSV with None
            for col in TEXT_COLS | NUMERIC_COLS:
                if col not in values:
                    values[col] = None

            cur.execute("""
                INSERT INTO player_decision_quality (
                    player, team, primary_role, macro_role,
                    minutes_played, n_decisions,
                    "DQ_index", value_impact,
                    pct__accuracy, pct__worst_choice,
                    pct__elite_per90, pct__poor_per90,
                    score, score_sd, avg_miss_cost,
                    elite_per90, poor_per90,
                    accuracy_pct, worst_choice_pct
                ) VALUES (
                    %(player)s, %(team)s, %(primary_role)s, %(macro_role)s,
                    %(minutes_played)s, %(n_decisions)s,
                    %(DQ_index)s, %(value_impact)s,
                    %(pct__accuracy)s, %(pct__worst_choice)s,
                    %(pct__elite_per90)s, %(pct__poor_per90)s,
                    %(score)s, %(score_sd)s, %(avg_miss_cost)s,
                    %(elite_per90)s, %(poor_per90)s,
                    %(accuracy_pct)s, %(worst_choice_pct)s
                )
                ON CONFLICT (player, team) DO UPDATE SET
                    primary_role     = EXCLUDED.primary_role,
                    macro_role       = EXCLUDED.macro_role,
                    minutes_played   = EXCLUDED.minutes_played,
                    n_decisions      = EXCLUDED.n_decisions,
                    "DQ_index"       = EXCLUDED."DQ_index",
                    value_impact     = EXCLUDED.value_impact,
                    pct__accuracy    = EXCLUDED.pct__accuracy,
                    pct__worst_choice = EXCLUDED.pct__worst_choice,
                    pct__elite_per90 = EXCLUDED.pct__elite_per90,
                    pct__poor_per90  = EXCLUDED.pct__poor_per90,
                    score            = EXCLUDED.score,
                    score_sd         = EXCLUDED.score_sd,
                    avg_miss_cost    = EXCLUDED.avg_miss_cost,
                    elite_per90      = EXCLUDED.elite_per90,
                    poor_per90       = EXCLUDED.poor_per90,
                    accuracy_pct     = EXCLUDED.accuracy_pct,
                    worst_choice_pct = EXCLUDED.worst_choice_pct
            """, values)
            count += 1

    return count


# ── CLI ───────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import player_decision_quality.csv into Supabase.",
    )
    parser.add_argument(
        "--db-url",
        type=str,
        default=None,
        help="Postgres connection URL. If omitted, uses SUPABASE_DB_URL or DATABASE_URL.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate CSV file exists and print row count without connecting.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()

    path = DATA_DIR / CSV_NAME
    if not path.exists():
        raise SystemExit(f"Missing file: {path}")

    if args.dry_run:
        rows = sum(1 for _ in open(path, encoding="utf-8")) - 1
        print(f"  {CSV_NAME}: {rows} rows")

        # Also print column names so you can verify the mapping
        with open(path, encoding="utf-8") as f:
            cols = csv.DictReader(f).fieldnames or []
        print(f"  Columns found: {cols}")

        known   = TEXT_COLS | NUMERIC_COLS
        extra   = set(cols) - known
        missing = NUMERIC_COLS - set(cols)
        if extra:
            print(f"  ℹ Extra columns (ignored): {sorted(extra)}")
        if missing:
            print(f"  ⚠ Missing columns (will be NULL): {sorted(missing)}")

        print("Dry run OK — no database connection made.")
        return

    db_url = resolve_db_url(args.db_url)
    if not db_url:
        raise SystemExit(
            "No database URL found.\n"
            "Options:\n"
            "  1. Pass --db-url 'postgresql://...'\n"
            "  2. Set SUPABASE_DB_URL in your environment\n"
            "  3. Add SUPABASE_DB_URL to webapp/backend/.env"
        )

    conn = get_connection(db_url)
    try:
        with conn:
            with conn.cursor() as cur:
                print("Creating table if not exists…")
                cur.execute(CREATE_TABLE)

                print("Importing player_decision_quality…")
                n = load_decision_quality(cur)
                print(f"  → {n} rows inserted/updated")
    finally:
        conn.close()

    print("Done ✓")


if __name__ == "__main__":
    main()