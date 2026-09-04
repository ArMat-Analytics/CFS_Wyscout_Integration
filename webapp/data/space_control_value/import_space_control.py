"""
Import player_space_control_indices.csv and player_space_control_aggregated.csv
into Supabase (PostgreSQL).

Usage:
    python import_space_control.py
    python import_space_control.py --db-url "postgresql://..."
    python import_space_control.py --dry-run

Connection: reads SUPABASE_DB_URL or DATABASE_URL from environment,
or pass --db-url explicitly (same pattern as supabase_importer.py).
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path

# CSVs live in H1_Space_Control_and_Value/data/ (three levels up to repo root, then to H1_Space_Control_and_Value)
DATA_DIR = Path(__file__).resolve().parents[3] / "H1_Space_Control_and_Value" / "data"

# .env lives in webapp/backend/
ENV_FILE = Path(__file__).resolve().parents[2] / "backend" / ".env"

# ── DDL ───────────────────────────────────────────────────────────────────────

CREATE_INDICES = """
CREATE TABLE IF NOT EXISTS sc_indices (
    player                                  TEXT NOT NULL,
    team                                    TEXT NOT NULL,
    primary_role                            TEXT,
    macro_role                              TEXT,
    minutes_played                          NUMERIC,
    coverage_pct                            NUMERIC,
    pressure_resistance_n                   NUMERIC,
    gravity_composite_pct                   NUMERIC,
    gravity_directional_m                   NUMERIC,
    "idx__PROGRESSION"                      NUMERIC,
    "idx__DANGEROUSNESS"                    NUMERIC,
    "idx__RECEPTION"                        NUMERIC,
    "idx__GRAVITY"                          NUMERIC,
    pct__lb_geom_per90                      NUMERIC,
    pct__lb_quality_per90                   NUMERIC,
    pct__lb_epv_per90                       NUMERIC,
    pct__successful_hull_penetrations_per90 NUMERIC,
    pct__defenders_bypassed_mean            NUMERIC,
    pct__epv_added_per90                    NUMERIC,
    pct__epv_penetration_per90              NUMERIC,
    pct__epv_inside_circ_per90              NUMERIC,
    pct__epv_exit_per90                     NUMERIC,
    pct__epv_outside_circ_per90             NUMERIC, 
    pct__between_lines_pct                  NUMERIC,
    pct__successful_hull_exits_per90        NUMERIC,
    pct__pressure_resistance_pct            NUMERIC,
    pct__gravity_proximity_pct              NUMERIC,
    pct__gravity_hull_pct                   NUMERIC,
    pct__gravity_abs_m                      NUMERIC,
    db_player_id                            BIGINT,
    PRIMARY KEY (player, team)
);
"""

CREATE_AGGREGATED = """
DROP TABLE IF EXISTS sc_aggregated;
CREATE TABLE IF NOT EXISTS sc_aggregated (
    player                              TEXT NOT NULL,
    team                                TEXT NOT NULL,
    primary_role                        TEXT,
    macro_role                          TEXT,
    minutes_played                      NUMERIC,
    passes_total                        NUMERIC,
    passes_analysed                     NUMERIC,
    coverage_pct                        NUMERIC,
    gravity_hull_pct                    NUMERIC,
    gravity_proximity_pct               NUMERIC,
    gravity_composite_pct               NUMERIC,
    gravity_n                           NUMERIC,
    gravity_directional_m               NUMERIC,
    gravity_directional_n               NUMERIC,
    passes_op                           NUMERIC,
    lb_geom                             NUMERIC,
    lb_epv                              NUMERIC,
    lb_quality                          NUMERIC,
    epv_added_sum                       NUMERIC,
    epv_added_mean                      NUMERIC,
    defenders_bypassed_mean             NUMERIC,
    between_lines_n                     NUMERIC,
    successful_hull_penetrations_n      NUMERIC,
    pressure_resistance_n               NUMERIC,
    lb_geom_pct                         NUMERIC,
    lb_epv_pct                          NUMERIC,
    lb_quality_pct                      NUMERIC,
    between_lines_pct                   NUMERIC,
    hull_exit_n                         NUMERIC,
    hull_exit_pct                       NUMERIC,
    penetration_completion_pct          NUMERIC,
    pressure_resistance_pct             NUMERIC,
    epv_penetration_mean                NUMERIC,
    epv_penetration_sum                 NUMERIC,
    penetration_n                       NUMERIC,
    epv_inside_circ_mean                NUMERIC,
    epv_inside_circ_sum                 NUMERIC,
    inside_circ_n                       NUMERIC,
    epv_exit_mean                       NUMERIC,
    epv_exit_sum                        NUMERIC,
    exit_n                              NUMERIC,
    epv_outside_circ_mean               NUMERIC,
    epv_outside_circ_sum                NUMERIC,
    outside_circ_n                      NUMERIC,
    lb_geom_per90                       NUMERIC,
    lb_epv_per90                        NUMERIC,
    lb_quality_per90                    NUMERIC,
    epv_added_per90                     NUMERIC,
    epv_penetration_per90               NUMERIC,
    epv_inside_circ_per90               NUMERIC,
    epv_exit_per90                      NUMERIC,
    epv_outside_circ_per90              NUMERIC,
    penetration_per90                   NUMERIC,
    inside_circ_per90                   NUMERIC,
    exit_per90                          NUMERIC,
    outside_circ_per90                  NUMERIC,
    between_lines_per90                 NUMERIC,
    successful_hull_exits_per90         NUMERIC,
    successful_hull_penetrations_per90  NUMERIC,
    PRIMARY KEY (player, team)
);
"""

# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_env_file() -> None:
    """
    Manually parse webapp/backend/.env and inject variables into os.environ.
    This avoids any dependency on python-dotenv.
    """
    if not ENV_FILE.exists():
        return
    with open(ENV_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("\"'")  # remove surrounding quotes
            if key and key not in os.environ:   # don't override real env vars
                os.environ[key] = value


def resolve_db_url(explicit: str | None) -> str | None:
    if explicit:
        return explicit
    _load_env_file()   # load webapp/backend/.env before checking env vars
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

TEXT_COLS = {"player", "team", "primary_role", "macro_role"}


def _load_mapping() -> dict:
    """Load the SC->DB player id mapping from sc_player_mapping.json."""
    import json as _json
    mapping_path = Path(__file__).resolve().parent / "sc_player_mapping.json"
    if not mapping_path.exists():
        print("  ⚠ sc_player_mapping.json not found — db_player_id will be NULL for all rows")
        return {}
    with open(mapping_path, encoding="utf-8") as f:
        entries = _json.load(f)
    return {(e["sc_player"], e["sc_team"]): e["db_player_id"] for e in entries}


def load_indices(cur) -> int:
    path = DATA_DIR / "player_space_control_indices.csv"
    mapping = _load_mapping()
    count = 0
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            values = {k: (_safe(v) if k in TEXT_COLS else (None if _safe(v) is None else float(v)))
                      for k, v in row.items()}
            values["db_player_id"] = mapping.get((row["player"], row["team"]))
            cur.execute("""
                INSERT INTO sc_indices (
                    player, team, primary_role, macro_role,
                    minutes_played, coverage_pct,
                    pressure_resistance_n, gravity_composite_pct,
                    gravity_directional_m,
                    "idx__PROGRESSION", "idx__DANGEROUSNESS",
                    "idx__RECEPTION", "idx__GRAVITY",
                    pct__lb_geom_per90, pct__lb_quality_per90,
                    pct__lb_epv_per90,
                    pct__successful_hull_penetrations_per90,
                    pct__defenders_bypassed_mean,
                    pct__epv_added_per90, pct__epv_penetration_per90,
                    pct__epv_inside_circ_per90,
                    pct__epv_exit_per90,
                    pct__epv_outside_circ_per90,
                    pct__between_lines_pct, pct__successful_hull_exits_per90,
                    pct__pressure_resistance_pct,
                    pct__gravity_proximity_pct, pct__gravity_hull_pct,
                    pct__gravity_abs_m, db_player_id
                ) VALUES (
                    %(player)s, %(team)s, %(primary_role)s, %(macro_role)s,
                    %(minutes_played)s, %(coverage_pct)s,
                    %(pressure_resistance_n)s, %(gravity_composite_pct)s,
                    %(gravity_directional_m)s,
                    %(idx__PROGRESSION)s, %(idx__DANGEROUSNESS)s,
                    %(idx__RECEPTION)s, %(idx__GRAVITY)s,
                    %(pct__lb_geom_per90)s, %(pct__lb_quality_per90)s,
                    %(pct__lb_epv_per90)s,
                    %(pct__successful_hull_penetrations_per90)s,
                    %(pct__defenders_bypassed_mean)s,
                    %(pct__epv_added_per90)s, %(pct__epv_penetration_per90)s,
                    %(pct__epv_inside_circ_per90)s,
                    %(pct__epv_exit_per90)s,
                    %(pct__epv_outside_circ_per90)s,
                    %(pct__between_lines_pct)s, %(pct__successful_hull_exits_per90)s,
                    %(pct__pressure_resistance_pct)s,
                    %(pct__gravity_proximity_pct)s, %(pct__gravity_hull_pct)s,
                    %(pct__gravity_abs_m)s, %(db_player_id)s
                )
                ON CONFLICT (player, team) DO UPDATE SET
                    primary_role         = EXCLUDED.primary_role,
                    macro_role           = EXCLUDED.macro_role,
                    minutes_played       = EXCLUDED.minutes_played,
                    db_player_id         = EXCLUDED.db_player_id,
                    "idx__PROGRESSION"   = EXCLUDED."idx__PROGRESSION",
                    "idx__DANGEROUSNESS" = EXCLUDED."idx__DANGEROUSNESS",
                    "idx__RECEPTION"     = EXCLUDED."idx__RECEPTION",
                    "idx__GRAVITY"       = EXCLUDED."idx__GRAVITY",
                    pct__epv_exit_per90          = EXCLUDED.pct__epv_exit_per90,
                    pct__epv_outside_circ_per90  = EXCLUDED.pct__epv_outside_circ_per90
            """, values)
            count += 1
    return count


def load_aggregated(cur) -> int:
    path = DATA_DIR / "player_space_control_aggregated.csv"
    count = 0
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            values = {k: (_safe(v) if k in TEXT_COLS else (None if _safe(v) is None else float(v)))
                    for k, v in row.items()}
            cur.execute("""
                INSERT INTO sc_aggregated (
                    player, team, primary_role, macro_role, minutes_played,
                    passes_total, passes_analysed, coverage_pct,
                    gravity_hull_pct, gravity_proximity_pct, gravity_composite_pct,
                    gravity_n, gravity_directional_m, gravity_directional_n, passes_op,
                    lb_geom, lb_epv, lb_quality,
                    epv_added_sum, epv_added_mean, defenders_bypassed_mean,
                    between_lines_n, successful_hull_penetrations_n, pressure_resistance_n,
                    lb_geom_pct, lb_epv_pct, lb_quality_pct, between_lines_pct,
                    hull_exit_n, hull_exit_pct, penetration_completion_pct,
                    pressure_resistance_pct,
                    epv_penetration_mean, epv_penetration_sum, penetration_n,
                    epv_inside_circ_mean, epv_inside_circ_sum, inside_circ_n,
                    epv_exit_mean, epv_exit_sum, exit_n,
                    epv_outside_circ_mean, epv_outside_circ_sum, outside_circ_n,
                    lb_geom_per90, lb_epv_per90, lb_quality_per90,
                    epv_added_per90, epv_penetration_per90, epv_inside_circ_per90,
                    epv_exit_per90, epv_outside_circ_per90,
                    penetration_per90, inside_circ_per90, between_lines_per90,
                    exit_per90, outside_circ_per90,
                    successful_hull_exits_per90, successful_hull_penetrations_per90
                ) VALUES (
                    %(player)s, %(team)s, %(primary_role)s, %(macro_role)s,
                    %(minutes_played)s, %(passes_total)s, %(passes_analysed)s,
                    %(coverage_pct)s,
                    %(gravity_hull_pct)s, %(gravity_proximity_pct)s,
                    %(gravity_composite_pct)s,
                    %(gravity_n)s, %(gravity_directional_m)s,
                    %(gravity_directional_n)s, %(passes_op)s,
                    %(lb_geom)s, %(lb_epv)s, %(lb_quality)s,
                    %(epv_added_sum)s, %(epv_added_mean)s,
                    %(defenders_bypassed_mean)s,
                    %(between_lines_n)s, %(successful_hull_penetrations_n)s,
                    %(pressure_resistance_n)s,
                    %(lb_geom_pct)s, %(lb_epv_pct)s, %(lb_quality_pct)s,
                    %(between_lines_pct)s,
                    %(hull_exit_n)s, %(hull_exit_pct)s, %(penetration_completion_pct)s,
                    %(pressure_resistance_pct)s,
                    %(epv_penetration_mean)s, %(epv_penetration_sum)s,
                    %(penetration_n)s,
                    %(epv_inside_circ_mean)s, %(epv_inside_circ_sum)s,
                    %(inside_circ_n)s,
                    %(epv_exit_mean)s, %(epv_exit_sum)s, %(exit_n)s,
                    %(epv_outside_circ_mean)s, %(epv_outside_circ_sum)s,
                    %(outside_circ_n)s,
                    %(lb_geom_per90)s, %(lb_epv_per90)s, %(lb_quality_per90)s,
                    %(epv_added_per90)s, %(epv_penetration_per90)s,
                    %(epv_inside_circ_per90)s,
                    %(epv_exit_per90)s, %(epv_outside_circ_per90)s,
                    %(penetration_per90)s, %(inside_circ_per90)s,
                    %(between_lines_per90)s,
                    %(exit_per90)s, %(outside_circ_per90)s,
                    %(successful_hull_exits_per90)s,
                    %(successful_hull_penetrations_per90)s
                )
                ON CONFLICT (player, team) DO UPDATE SET
                    macro_role               = EXCLUDED.macro_role,
                    minutes_played           = EXCLUDED.minutes_played,
                    epv_added_per90          = EXCLUDED.epv_added_per90,
                    epv_exit_sum             = EXCLUDED.epv_exit_sum,
                    epv_exit_per90           = EXCLUDED.epv_exit_per90,
                    epv_outside_circ_sum     = EXCLUDED.epv_outside_circ_sum,
                    epv_outside_circ_per90   = EXCLUDED.epv_outside_circ_per90
            """, values)
            count += 1
    return count


# ── CLI ───────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import space control CSVs into Supabase.",
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
        help="Validate CSV files exist and print row counts without connecting.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()

    # Validate CSV files exist
    for name in ("player_space_control_indices.csv", "player_space_control_aggregated.csv"):
        p = DATA_DIR / name
        if not p.exists():
            raise SystemExit(f"Missing file: {p}")

    if args.dry_run:
        for name in ("player_space_control_indices.csv", "player_space_control_aggregated.csv"):
            rows = sum(1 for _ in open(DATA_DIR / name, encoding="utf-8")) - 1
            print(f"  {name}: {rows} rows")
        print("Dry run OK — no database connection made.")
        return

    db_url = resolve_db_url(args.db_url)
    if not db_url:
        raise SystemExit(
            "No database URL found.\n"
            "Options:\n"
            "  1. Pass --db-url 'postgresql://...'\n"
            "  2. Set SUPABASE_DB_URL in your environment\n"
            "  3. Set DATABASE_URL in your environment"
        )

    conn = get_connection(db_url)
    try:
        with conn:
            with conn.cursor() as cur:
                print("Creating tables if not exist…")
                cur.execute(CREATE_INDICES)
                cur.execute(CREATE_AGGREGATED)
                # Ensure db_player_id exists even if table was created in an older run
                cur.execute("ALTER TABLE sc_indices ADD COLUMN IF NOT EXISTS db_player_id BIGINT;")
                cur.execute("ALTER TABLE sc_aggregated ADD COLUMN IF NOT EXISTS epv_exit_mean NUMERIC;")
                cur.execute("ALTER TABLE sc_aggregated ADD COLUMN IF NOT EXISTS epv_exit_sum NUMERIC;")
                cur.execute("ALTER TABLE sc_aggregated ADD COLUMN IF NOT EXISTS exit_n NUMERIC;")
                cur.execute("ALTER TABLE sc_aggregated ADD COLUMN IF NOT EXISTS epv_outside_circ_mean NUMERIC;")
                cur.execute("ALTER TABLE sc_aggregated ADD COLUMN IF NOT EXISTS epv_outside_circ_sum NUMERIC;")
                cur.execute("ALTER TABLE sc_aggregated ADD COLUMN IF NOT EXISTS outside_circ_n NUMERIC;")
                cur.execute("ALTER TABLE sc_aggregated ADD COLUMN IF NOT EXISTS epv_exit_per90 NUMERIC;")
                cur.execute("ALTER TABLE sc_aggregated ADD COLUMN IF NOT EXISTS epv_outside_circ_per90 NUMERIC;")
                cur.execute("ALTER TABLE sc_aggregated ADD COLUMN IF NOT EXISTS exit_per90 NUMERIC;")
                cur.execute("ALTER TABLE sc_aggregated ADD COLUMN IF NOT EXISTS outside_circ_per90 NUMERIC;")
                cur.execute("ALTER TABLE sc_indices ADD COLUMN IF NOT EXISTS pct__epv_exit_per90 NUMERIC;")
                cur.execute("ALTER TABLE sc_indices ADD COLUMN IF NOT EXISTS pct__epv_outside_circ_per90 NUMERIC;")

                print("Importing sc_indices…")
                n = load_indices(cur)
                print(f"  → {n} rows inserted/updated")

                print("Importing sc_aggregated…")
                n = load_aggregated(cur)
                print(f"  → {n} rows inserted/updated")
    finally:
        conn.close()

    print("Done ✓")


if __name__ == "__main__":
    main()