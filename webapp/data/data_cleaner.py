from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple


REFERENCE_DATE = dt.date(2024, 6, 14)
TRUTH_FILE = "player_totals_distances_roles.csv"
PLAYER_DATA_FILE = "player_data.csv"
TEAM_DATA_FILE = "team_data.csv"
TEAM_MATCHES_FILE = "team_matches.csv"
RAW_DATA_DIRNAME = "data_raw"
CLEAN_DATA_DIRNAME = "data_clean"
PROJECT_ROOT_MARKER = "Contextual-Football-Scouting"

# player_totals_distances_roles.csv is the source of truth for identities.
TEAM_ALIAS_TO_TRUTH = {
    "Turkiye": "Turkey",
    "Czechia": "Czech Republic",
}

# Manual aliases for the few transliteration/spelling mismatches.
TRUTH_PLAYER_ALIAS = {
    ("ukraine", "illia zabarnyi"): "ilya zabarnyi",
    ("denmark", "victor bernth kristansen"): "victor kristiansen",
    ("georgia", "heorhii tsitaishvili"): "giorgi tsitaishvili",
    ("albania", "taulant sulejmanov"): "taulant seferi",
}

_SPECIAL_CHAR_MAP = str.maketrans(
    {
        "ı": "i",
        "ø": "o",
        "ð": "d",
        "þ": "th",
        "ł": "l",
        "ß": "ss",
        "æ": "ae",
        "œ": "oe",
    }
)


@dataclass
class MatchCandidate:
    row: Dict[str, str]
    names_norm: Sequence[str]


def normalize_text(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""

    text = text.translate(_SPECIAL_CHAR_MAP)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def canonical_team_name(team_name: str) -> str:
    return TEAM_ALIAS_TO_TRUTH.get((team_name or "").strip(), (team_name or "").strip())


def project_scoped_path(path: Path) -> str:
    resolved = path.resolve()
    marker = PROJECT_ROOT_MARKER.casefold()
    for idx, part in enumerate(resolved.parts):
        if part.casefold() == marker:
            return "/".join(resolved.parts[idx:])

    tail = resolved.parts[-3:] if len(resolved.parts) >= 3 else resolved.parts
    return "/".join(tail)


def is_url_column(column_name: str) -> bool:
    return "url" in (column_name or "").strip().casefold()


def drop_url_columns(rows: Sequence[Dict[str, str]]) -> Tuple[List[Dict[str, str]], List[str]]:
    rows_list = list(rows)
    if not rows_list:
        return [], []

    dropped_columns = [name for name in rows_list[0].keys() if is_url_column(name)]
    if not dropped_columns:
        return rows_list, []

    dropped_set = set(dropped_columns)
    cleaned_rows = []
    for row in rows_list:
        cleaned_rows.append({key: value for key, value in row.items() if key not in dropped_set})

    return cleaned_rows, dropped_columns


def compute_age_on_date(date_of_birth: str, on_date: dt.date = REFERENCE_DATE) -> int:
    dob = dt.datetime.strptime(date_of_birth, "%Y-%m-%d").date()
    return on_date.year - dob.year - ((on_date.month, on_date.day) < (dob.month, dob.day))


def recalculate_age_column(
    rows: List[Dict[str, str]],
    on_date: dt.date = REFERENCE_DATE,
) -> Tuple[List[Dict[str, str]], int, int]:
    updated = 0
    skipped = 0

    for row in rows:
        dob = (row.get("date_of_birth") or "").strip()
        if not dob:
            skipped += 1
            continue
        try:
            age = compute_age_on_date(dob, on_date)
        except ValueError:
            skipped += 1
            continue

        if row.get("age") != str(age):
            row["age"] = str(age)
            updated += 1

    return rows, updated, skipped


def looks_like_full_name(value: str) -> bool:
    text = (value or "").strip()
    if len(text) < 5:
        return False
    tokens = text.split()
    return len(tokens) >= 2 and all(len(t) > 1 for t in tokens[:2])


def candidate_name_variants(player_row: Dict[str, str]) -> List[str]:
    raw = [
        player_row.get("player_name", ""),
        player_row.get("short_name", ""),
        player_row.get("display_name", ""),
    ]

    nationality = player_row.get("nationality", "")
    if looks_like_full_name(nationality):
        raw.append(nationality)

    variants = sorted({normalize_text(name) for name in raw if normalize_text(name)})
    return variants


def token_set(text: str) -> set[str]:
    return set((text or "").split())


def score_name_match(target_norm: str, candidate_norm_names: Sequence[str]) -> Tuple[float, str]:
    best_score = 0.0
    best_rule = "none"
    target_tokens = token_set(target_norm)

    for cand in candidate_norm_names:
        if not cand:
            continue

        if cand == target_norm:
            return 1.0, "exact"

        if target_norm.startswith(cand) or cand.startswith(target_norm):
            if 0.96 > best_score:
                best_score = 0.96
                best_rule = "prefix"

        cand_tokens = token_set(cand)
        inter = len(target_tokens & cand_tokens)
        if inter >= 2 and (target_tokens.issubset(cand_tokens) or cand_tokens.issubset(target_tokens)):
            if 0.94 > best_score:
                best_score = 0.94
                best_rule = "token_subset"

        fuzzy = SequenceMatcher(None, target_norm, cand).ratio()
        if fuzzy >= 0.90 and fuzzy > best_score:
            best_score = fuzzy
            best_rule = "fuzzy"

    return best_score, best_rule


def dedupe_rows_by_key(
    rows: Iterable[Dict[str, str]],
    key_fields: Sequence[str],
) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    kept: List[Dict[str, str]] = []
    duplicates: List[Dict[str, str]] = []
    seen = set()

    for row in rows:
        key = tuple((row.get(field) or "").strip() for field in key_fields)
        if key in seen:
            duplicates.append(row)
            continue
        seen.add(key)
        kept.append(row)

    return kept, duplicates


def read_csv_rows(path: Path, delimiter: str = ",") -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def write_csv_rows(
    path: Path,
    rows: Sequence[Dict[str, str]],
    fieldnames: Sequence[str],
    delimiter: str = ",",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter=delimiter)
        writer.writeheader()
        writer.writerows(rows)


def build_player_team_candidate_index(player_rows: Sequence[Dict[str, str]]) -> Dict[str, List[MatchCandidate]]:
    index: Dict[str, List[MatchCandidate]] = {}
    for row in player_rows:
        team_norm = normalize_text(canonical_team_name(row.get("source_team_name", "")))
        variants = candidate_name_variants(row)
        if not team_norm or not variants:
            continue
        index.setdefault(team_norm, []).append(MatchCandidate(row=row, names_norm=variants))
    return index


def build_truth_to_player_bridge(
    truth_rows: Sequence[Dict[str, str]],
    player_rows: Sequence[Dict[str, str]],
) -> Tuple[List[Dict[str, str]], Dict[str, Dict[str, str]], List[Dict[str, str]]]:
    team_index = build_player_team_candidate_index(player_rows)
    matched_truth_by_tm_player_id: Dict[str, Dict[str, str]] = {}
    bridge_rows: List[Dict[str, str]] = []
    unresolved: List[Dict[str, str]] = []

    used_tm_ids: set[str] = set()

    for truth in truth_rows:
        truth_team = canonical_team_name(truth.get("team", ""))
        truth_team_norm = normalize_text(truth_team)
        truth_player = (truth.get("player") or "").strip()
        truth_player_norm = normalize_text(truth_player)

        alias_key = (truth_team_norm, truth_player_norm)
        target_player_norm = TRUTH_PLAYER_ALIAS.get(alias_key, truth_player_norm)

        candidates = team_index.get(truth_team_norm, [])
        best: MatchCandidate | None = None
        best_score = 0.0
        best_rule = "none"
        tie = False

        for candidate in candidates:
            tm_id = (candidate.row.get("player_id") or "").strip()
            if not tm_id or tm_id in used_tm_ids:
                continue

            score, rule = score_name_match(target_player_norm, candidate.names_norm)
            if score > best_score + 1e-12:
                best = candidate
                best_score = score
                best_rule = rule
                tie = False
            elif abs(score - best_score) <= 1e-12 and score > 0:
                tie = True

        if best is not None and best_score >= 0.90 and not tie:
            tm_id = (best.row.get("player_id") or "").strip()
            used_tm_ids.add(tm_id)
            matched_truth_by_tm_player_id[tm_id] = {
                "truth_player_id": (truth.get("player_id") or "").strip(),
                "truth_player_name": truth_player,
                "truth_team_name": truth_team,
                "truth_team_id": "",
                "match_score": f"{best_score:.3f}",
                "match_rule": best_rule,
            }
            status = "matched"
            tm_player_id = tm_id
            tm_player_name = best.row.get("player_name", "")
            tm_team_name = best.row.get("source_team_name", "")
        else:
            status = "unmatched"
            tm_player_id = ""
            tm_player_name = ""
            tm_team_name = ""

            unresolved.append(
                {
                    "truth_team": truth_team,
                    "truth_player": truth_player,
                    "target_norm": target_player_norm,
                    "best_score": f"{best_score:.3f}",
                }
            )

        bridge_rows.append(
            {
                "truth_player_id": (truth.get("player_id") or "").strip(),
                "truth_player_name": truth_player,
                "truth_team_name": truth_team,
                "truth_team_id": "",
                "truth_team_norm": truth_team_norm,
                "truth_player_norm": truth_player_norm,
                "tm_player_id": tm_player_id,
                "tm_player_name": tm_player_name,
                "tm_team_name": tm_team_name,
                "match_score": f"{best_score:.3f}",
                "match_rule": best_rule,
                "status": status,
            }
        )

    return bridge_rows, matched_truth_by_tm_player_id, unresolved


def prepare_entity_files(
    data_dir: Path,
    output_dir: Path,
    recalc_age: bool,
) -> Dict[str, object]:
    truth_path = data_dir / TRUTH_FILE
    player_path = data_dir / PLAYER_DATA_FILE
    team_path = data_dir / TEAM_DATA_FILE
    matches_path = data_dir / TEAM_MATCHES_FILE

    for required in (truth_path, player_path, team_path, matches_path):
        if not required.exists():
            raise FileNotFoundError(f"Required file not found: {required}")

    truth_rows = read_csv_rows(truth_path, delimiter=";")
    player_rows = read_csv_rows(player_path, delimiter=",")
    team_rows = read_csv_rows(team_path, delimiter=",")
    match_rows = read_csv_rows(matches_path, delimiter=",")

    truth_rows, truth_url_columns = drop_url_columns(truth_rows)
    player_rows, player_url_columns = drop_url_columns(player_rows)
    team_rows, team_url_columns = drop_url_columns(team_rows)
    match_rows, match_url_columns = drop_url_columns(match_rows)

    truth_rows, truth_duplicates = dedupe_rows_by_key(truth_rows, ["player_id"])
    player_rows, player_duplicates = dedupe_rows_by_key(player_rows, ["player_id"])
    team_rows, team_duplicates = dedupe_rows_by_key(team_rows, ["team_id"])
    match_rows, match_duplicates = dedupe_rows_by_key(match_rows, ["team_id", "match_report_id"])

    for row in team_rows:
        row["canonical_team_name"] = canonical_team_name(row.get("team_name", ""))

    team_id_by_name_norm: Dict[str, str] = {}
    for row in team_rows:
        team_norm = normalize_text(row.get("canonical_team_name", ""))
        team_id = (row.get("team_id") or "").strip()
        if team_norm and team_id and team_norm not in team_id_by_name_norm:
            team_id_by_name_norm[team_norm] = team_id

    for row in truth_rows:
        canonical_team = canonical_team_name(row.get("team", ""))
        row["canonical_team_name"] = canonical_team
        row["team_id"] = team_id_by_name_norm.get(normalize_text(canonical_team), "")

    age_updates = 0
    age_skipped = 0
    if recalc_age:
        player_rows, age_updates, age_skipped = recalculate_age_column(player_rows, REFERENCE_DATE)

    bridge_rows, matched_truth_by_tm_player_id, unresolved = build_truth_to_player_bridge(truth_rows, player_rows)

    for bridge_row in bridge_rows:
        bridge_row["truth_team_id"] = team_id_by_name_norm.get(normalize_text(bridge_row.get("truth_team_name", "")), "")

    for match_info in matched_truth_by_tm_player_id.values():
        match_info["truth_team_id"] = team_id_by_name_norm.get(normalize_text(match_info.get("truth_team_name", "")), "")

    player_rows_clean = []
    for row in player_rows:
        tm_player_id = (row.get("player_id") or "").strip()
        truth_info = matched_truth_by_tm_player_id.get(tm_player_id)
        if not truth_info:
            continue

        enriched = dict(row)
        enriched["truth_player_id"] = truth_info["truth_player_id"]
        enriched["truth_player_name"] = truth_info["truth_player_name"]
        enriched["truth_team_name"] = truth_info["truth_team_name"]
        enriched["truth_team_id"] = truth_info["truth_team_id"]
        enriched["match_score"] = truth_info["match_score"]
        enriched["match_rule"] = truth_info["match_rule"]
        player_rows_clean.append(enriched)

    truth_teams = {canonical_team_name(row.get("team", "")) for row in truth_rows}
    truth_team_norm = {normalize_text(name) for name in truth_teams}

    team_rows_clean = [row for row in team_rows if normalize_text(row.get("canonical_team_name", "")) in truth_team_norm]

    valid_team_ids = {(row.get("team_id") or "").strip() for row in team_rows_clean}
    for row in match_rows:
        row["canonical_team_name"] = canonical_team_name(row.get("team_name", ""))
        row["canonical_home_team_name"] = canonical_team_name(row.get("home_team_name", ""))
        row["canonical_away_team_name"] = canonical_team_name(row.get("away_team_name", ""))

    match_rows_clean = []
    for row in match_rows:
        team_id = (row.get("team_id") or "").strip()
        home_team_id = (row.get("home_team_id") or "").strip()
        away_team_id = (row.get("away_team_id") or "").strip()
        if team_id not in valid_team_ids:
            continue
        if home_team_id and home_team_id not in valid_team_ids:
            continue
        if away_team_id and away_team_id not in valid_team_ids:
            continue
        match_rows_clean.append(row)

    output_dir.mkdir(parents=True, exist_ok=True)

    write_csv_rows(
        output_dir / "player_totals_distances_roles_clean.csv",
        truth_rows,
        fieldnames=list(truth_rows[0].keys()) if truth_rows else [],
        delimiter=";",
    )
    write_csv_rows(
        output_dir / "player_data_clean.csv",
        player_rows_clean,
        fieldnames=list(player_rows_clean[0].keys())
        if player_rows_clean
        else list(player_rows[0].keys())
        + ["truth_player_id", "truth_player_name", "truth_team_name", "truth_team_id", "match_score", "match_rule"],
        delimiter=",",
    )
    write_csv_rows(
        output_dir / "team_data_clean.csv",
        team_rows_clean,
        fieldnames=list(team_rows_clean[0].keys()) if team_rows_clean else list(team_rows[0].keys()) + ["canonical_team_name"],
        delimiter=",",
    )
    write_csv_rows(
        output_dir / "team_matches_clean.csv",
        match_rows_clean,
        fieldnames=list(match_rows_clean[0].keys())
        if match_rows_clean
        else list(match_rows[0].keys())
        + ["canonical_team_name", "canonical_home_team_name", "canonical_away_team_name"],
        delimiter=",",
    )
    write_csv_rows(
        output_dir / "player_bridge_clean.csv",
        bridge_rows,
        fieldnames=list(bridge_rows[0].keys()) if bridge_rows else [],
        delimiter=",",
    )

    report = {
        "data_dir": project_scoped_path(data_dir),
        "output_dir": project_scoped_path(output_dir),
        "truth_file": project_scoped_path(truth_path),
        "reference_date": REFERENCE_DATE.isoformat(),
        "rows": {
            "truth_in": len(read_csv_rows(truth_path, delimiter=";")),
            "truth_clean": len(truth_rows),
            "truth_with_team_id": sum(1 for row in truth_rows if (row.get("team_id") or "").strip()),
            "player_data_in": len(read_csv_rows(player_path, delimiter=",")),
            "player_data_clean": len(player_rows_clean),
            "team_data_in": len(read_csv_rows(team_path, delimiter=",")),
            "team_data_clean": len(team_rows_clean),
            "team_matches_in": len(read_csv_rows(matches_path, delimiter=",")),
            "team_matches_clean": len(match_rows_clean),
            "bridge_rows": len(bridge_rows),
        },
        "deduplicated_rows": {
            "truth": len(truth_duplicates),
            "player_data": len(player_duplicates),
            "team_data": len(team_duplicates),
            "team_matches": len(match_duplicates),
        },
        "url_columns_removed": {
            "truth": truth_url_columns,
            "player_data": player_url_columns,
            "team_data": team_url_columns,
            "team_matches": match_url_columns,
        },
        "bridge": {
            "matched": sum(1 for row in bridge_rows if row.get("status") == "matched"),
            "unmatched": sum(1 for row in bridge_rows if row.get("status") == "unmatched"),
            "unresolved_examples": unresolved[:25],
        },
        "age_recalculation": {
            "enabled": recalc_age,
            "updated": age_updates,
            "skipped": age_skipped,
        },
    }

    with (output_dir / "cleaning_report.json").open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)

    return report


def recalc_age_file(input_file: Path, output_file: Path, on_date: dt.date = REFERENCE_DATE) -> Dict[str, object]:
    rows = read_csv_rows(input_file, delimiter=",")
    rows, url_columns_removed = drop_url_columns(rows)
    rows, updated, skipped = recalculate_age_column(rows, on_date)
    fieldnames = list(rows[0].keys()) if rows else []
    write_csv_rows(output_file, rows, fieldnames=fieldnames, delimiter=",")
    return {
        "rows": len(rows),
        "updated": updated,
        "skipped": skipped,
        "url_columns_removed": url_columns_removed,
    }


def parse_reference_date(value: str) -> dt.date:
    return dt.datetime.strptime(value, "%Y-%m-%d").date()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare EURO CSV files for DB import using player_totals_distances_roles.csv as source of truth.",
    )
    data_root = Path(__file__).resolve().parent

    sub = parser.add_subparsers(dest="command", required=True)

    prepare_parser = sub.add_parser("prepare", help="Create cleaned CSV files and a bridge mapping table.")
    prepare_parser.add_argument(
        "--data-dir",
        type=Path,
        default=data_root / RAW_DATA_DIRNAME,
        help="Directory that contains the 4 entity CSV files.",
    )
    prepare_parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory for cleaned files (default: <data-root>/data_clean).",
    )
    prepare_parser.add_argument(
        "--no-age-recalc",
        action="store_true",
        help="Skip age recalculation in player_data_clean.csv.",
    )

    age_parser = sub.add_parser(
        "recalc-age",
        help="Recalculate player age values for a player_data CSV using 2024-06-14 (or a custom date).",
    )
    age_parser.add_argument(
        "--input-file",
        type=Path,
        default=data_root / RAW_DATA_DIRNAME / PLAYER_DATA_FILE,
        help="Input CSV path (player_data schema expected).",
    )
    age_parser.add_argument(
        "--output-file",
        type=Path,
        default=None,
        help="Output CSV path (default: overwrite input file).",
    )
    age_parser.add_argument(
        "--reference-date",
        type=parse_reference_date,
        default=REFERENCE_DATE,
        help="Reference date in YYYY-MM-DD format.",
    )

    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    data_root = Path(__file__).resolve().parent

    if args.command == "prepare":
        data_dir = args.data_dir.resolve()
        output_dir = args.output_dir.resolve() if args.output_dir else (data_root / CLEAN_DATA_DIRNAME)

        report = prepare_entity_files(
            data_dir=data_dir,
            output_dir=output_dir,
            recalc_age=not args.no_age_recalc,
        )
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return

    if args.command == "recalc-age":
        input_file = args.input_file.resolve()
        output_file = args.output_file.resolve() if args.output_file else input_file
        stats = recalc_age_file(input_file=input_file, output_file=output_file, on_date=args.reference_date)
        print(json.dumps(stats, indent=2, ensure_ascii=False))
        return


if __name__ == "__main__":
    main()
