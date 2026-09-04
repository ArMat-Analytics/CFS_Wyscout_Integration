from __future__ import annotations

import argparse
import csv
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Sequence, Tuple


CLEAN_DATA_DIRNAME = "data_clean"


@dataclass(frozen=True)
class ForeignKeySpec:
    column: str
    ref_table: str
    ref_column: str


@dataclass(frozen=True)
class TableSpec:
    csv_file: str
    delimiter: str
    table_name: str
    bigint_columns: frozenset[str]
    primary_key: Tuple[str, ...] = ()
    foreign_keys: Tuple[ForeignKeySpec, ...] = ()
    indexes: Tuple[Tuple[str, ...], ...] = ()


TABLE_SPECS: Tuple[TableSpec, ...] = (
    TableSpec(
        csv_file="team_data_clean.csv",
        delimiter=",",
        table_name="teams",
        bigint_columns=frozenset({"team_id"}),
        primary_key=("team_id",),
    ),
    TableSpec(
        csv_file="team_matches_clean.csv",
        delimiter=",",
        table_name="team_matches",
        bigint_columns=frozenset({"match_report_id", "team_id", "home_team_id", "away_team_id"}),
        primary_key=("match_report_id",),
        foreign_keys=(
            ForeignKeySpec("team_id", "teams", "team_id"),
            ForeignKeySpec("home_team_id", "teams", "team_id"),
            ForeignKeySpec("away_team_id", "teams", "team_id"),
        ),
        indexes=(("team_id",), ("home_team_id",), ("away_team_id",)),
    ),
    TableSpec(
        csv_file="player_totals_distances_roles_clean.csv",
        delimiter=";",
        table_name="player_totals",
        bigint_columns=frozenset({"player_id", "team_id"}),
        primary_key=("player_id",),
        foreign_keys=(ForeignKeySpec("team_id", "teams", "team_id"),),
        indexes=(("team_id",),),
    ),
    TableSpec(
        csv_file="player_data_clean.csv",
        delimiter=",",
        table_name="player_profiles",
        bigint_columns=frozenset({"player_id", "source_team_id", "truth_player_id", "truth_team_id"}),
        primary_key=("player_id",),
        foreign_keys=(
            ForeignKeySpec("source_team_id", "teams", "team_id"),
            ForeignKeySpec("truth_team_id", "teams", "team_id"),
            ForeignKeySpec("truth_player_id", "player_totals", "player_id"),
        ),
        indexes=(("source_team_id",), ("truth_team_id",), ("truth_player_id",)),
    ),
    TableSpec(
        csv_file="player_bridge_clean.csv",
        delimiter=",",
        table_name="player_bridge",
        bigint_columns=frozenset({"truth_player_id", "truth_team_id", "tm_player_id"}),
        foreign_keys=(
            ForeignKeySpec("truth_team_id", "teams", "team_id"),
            ForeignKeySpec("truth_player_id", "player_totals", "player_id"),
            ForeignKeySpec("tm_player_id", "player_profiles", "player_id"),
        ),
        indexes=(("truth_team_id",), ("truth_player_id",), ("tm_player_id",)),
    ),
)


def quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def qualified_table(schema: str, table: str) -> str:
    return f"{quote_ident(schema)}.{quote_ident(table)}"


def load_headers(csv_path: Path, delimiter: str) -> Sequence[str]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle, delimiter=delimiter)
        header = next(reader, None)
    if not header:
        raise ValueError(f"Missing header row in {csv_path}")
    return [col.strip() for col in header]


def build_create_table_sql(schema: str, spec: TableSpec, headers: Sequence[str]) -> str:
    columns_sql = []
    for header in headers:
        column_type = "BIGINT" if header in spec.bigint_columns else "TEXT"
        columns_sql.append(f"{quote_ident(header)} {column_type}")

    constraints_sql = []
    if spec.primary_key:
        pk_cols = ", ".join(quote_ident(col) for col in spec.primary_key)
        constraints_sql.append(f"PRIMARY KEY ({pk_cols})")

    for fk in spec.foreign_keys:
        fk_col = quote_ident(fk.column)
        ref_table = qualified_table(schema, fk.ref_table)
        ref_col = quote_ident(fk.ref_column)
        constraints_sql.append(f"FOREIGN KEY ({fk_col}) REFERENCES {ref_table} ({ref_col})")

    full_body = ",\n  ".join(columns_sql + constraints_sql)
    return f"CREATE TABLE IF NOT EXISTS {qualified_table(schema, spec.table_name)} (\n  {full_body}\n);"


def build_index_sql(schema: str, table_name: str, columns: Sequence[str]) -> str:
    index_name = f"idx_{table_name}_{'_'.join(columns)}"
    if len(index_name) > 63:
        index_name = index_name[:63]

    cols = ", ".join(quote_ident(col) for col in columns)
    return (
        f"CREATE INDEX IF NOT EXISTS {quote_ident(index_name)} "
        f"ON {qualified_table(schema, table_name)} ({cols});"
    )


def ensure_clean_files(clean_dir: Path, table_specs: Iterable[TableSpec]) -> None:
    missing = [str((clean_dir / spec.csv_file).resolve()) for spec in table_specs if not (clean_dir / spec.csv_file).exists()]
    if missing:
        msg = "Missing clean CSV files:\n- " + "\n- ".join(missing)
        raise FileNotFoundError(msg)


def resolve_db_url(explicit_db_url: str | None) -> str | None:
    if explicit_db_url:
        return explicit_db_url
    return os.getenv("SUPABASE_DB_URL") or os.getenv("DATABASE_URL")


def get_connection(db_url: str):
    try:
        import psycopg2
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency 'psycopg2-binary'. Install with: pip install psycopg2-binary"
        ) from exc

    return psycopg2.connect(db_url)


def import_clean_data(
    db_url: str,
    clean_dir: Path,
    schema: str,
    replace: bool,
    append: bool,
) -> None:
    headers_by_table: Dict[str, Sequence[str]] = {}
    for spec in TABLE_SPECS:
        csv_path = clean_dir / spec.csv_file
        headers_by_table[spec.table_name] = load_headers(csv_path, spec.delimiter)

    conn = get_connection(db_url)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(f"CREATE SCHEMA IF NOT EXISTS {quote_ident(schema)};")

                if replace:
                    for spec in reversed(TABLE_SPECS):
                        cur.execute(f"DROP TABLE IF EXISTS {qualified_table(schema, spec.table_name)} CASCADE;")

                for spec in TABLE_SPECS:
                    cur.execute(build_create_table_sql(schema, spec, headers_by_table[spec.table_name]))

                if not append:
                    for spec in TABLE_SPECS:
                        cur.execute(f"TRUNCATE TABLE {qualified_table(schema, spec.table_name)} RESTART IDENTITY CASCADE;")

                for spec in TABLE_SPECS:
                    csv_path = clean_dir / spec.csv_file
                    columns_sql = ", ".join(quote_ident(col) for col in headers_by_table[spec.table_name])
                    copy_sql = (
                        f"COPY {qualified_table(schema, spec.table_name)} ({columns_sql}) "
                        f"FROM STDIN WITH (FORMAT CSV, HEADER TRUE, DELIMITER '{spec.delimiter}', QUOTE '\"', NULL '')"
                    )
                    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
                        cur.copy_expert(copy_sql, handle)

                for spec in TABLE_SPECS:
                    for index_columns in spec.indexes:
                        cur.execute(build_index_sql(schema, spec.table_name, index_columns))
    finally:
        conn.close()


def build_parser() -> argparse.ArgumentParser:
    data_root = Path(__file__).resolve().parent

    parser = argparse.ArgumentParser(
        description="Import clean CSV files into Supabase as a relational PostgreSQL schema.",
    )
    parser.add_argument(
        "--db-url",
        type=str,
        default=None,
        help="Supabase Postgres connection URL. If omitted, uses SUPABASE_DB_URL or DATABASE_URL.",
    )
    parser.add_argument(
        "--clean-dir",
        type=Path,
        default=data_root / CLEAN_DATA_DIRNAME,
        help="Directory containing *_clean.csv files.",
    )
    parser.add_argument(
        "--schema",
        type=str,
        default="public",
        help="Destination PostgreSQL schema.",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Drop and recreate target tables before import.",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append rows instead of truncating target tables before import.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate files and show import plan without connecting to Supabase.",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    clean_dir = args.clean_dir.resolve()
    ensure_clean_files(clean_dir, TABLE_SPECS)

    if args.dry_run:
        print("Dry run succeeded. Import plan:")
        for spec in TABLE_SPECS:
            headers = load_headers(clean_dir / spec.csv_file, spec.delimiter)
            print(f"- {spec.csv_file} -> {args.schema}.{spec.table_name} ({len(headers)} columns)")
        return

    db_url = resolve_db_url(args.db_url)
    if not db_url:
        raise SystemExit("Missing database URL. Use --db-url or set SUPABASE_DB_URL (or DATABASE_URL).")

    import_clean_data(
        db_url=db_url,
        clean_dir=clean_dir,
        schema=args.schema,
        replace=args.replace,
        append=args.append,
    )
    print("Import completed successfully.")


if __name__ == "__main__":
    main()
