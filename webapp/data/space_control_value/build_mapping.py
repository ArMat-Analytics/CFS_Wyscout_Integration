"""
Generate sc_player_mapping.json in the same folder.
Run this BEFORE import_space_control.py.

Usage:
    python build_mapping.py
"""
from __future__ import annotations

import csv
import json
import unicodedata
from pathlib import Path

ROOT     = Path(__file__).resolve().parents[3]
SC_CSV   = ROOT / "H1_Space_Control_and_Value" / "data" / "player_space_control_indices.csv"
DB_CSV   = Path(__file__).resolve().parents[1] / "data_clean" / "player_data_clean.csv"
OUT_FILE = Path(__file__).resolve().parent / "sc_player_mapping.json"

# Transfermarkt uses different team names than StatsBomb
TEAM_ALIAS = {
    "Turkey":         "Turkiye",
    "Czech Republic": "Czechia",
}

# Players known by nickname/short name in Transfermarkt
MANUAL_NAME: dict[tuple[str, str], str] = {
    ("Pedro González López",         "Spain"):    "Pedri",
    ("Rodrigo Hernández Cascante",   "Spain"):    "Rodri",
    ("Jorge Luiz Frello Filho",      "Italy"):    "Jorginho",
    ("Kléper Laveran Lima Ferreira", "Portugal"): "Pepe",
    ("Vitor Machado Ferreira",       "Portugal"): "Vitinha",
    ("Heorhii Tsitaishvili",         "Georgia"):  "Giorgi Tsitaishvili",
    ("Illia Zabarnyi",               "Ukraine"):  "Ilya Zabarnyi",
    ("Jeremy Doku",                  "Belgium"):  "Jérémy Doku",
    ("Che Adams",                    "Scotland"): "Ché Adams",
}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.lower().strip()


def main() -> None:
    # Load DB profiles: (player_name, source_team_name) -> player_id
    profiles: dict[tuple[str, str], str] = {}
    with open(DB_CSV, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            profiles[(r["player_name"], r["source_team_name"])] = r["player_id"]

    with open(SC_CSV, newline="", encoding="utf-8") as f:
        sc_rows = list(csv.DictReader(f))

    mapping: list[dict] = []
    matched = 0
    no_db = 0

    for r in sc_rows:
        sc_name, sc_team = r["player"], r["team"]
        db_team = TEAM_ALIAS.get(sc_team, sc_team)

        # 1. Exact match (with team alias)
        if (sc_name, db_team) in profiles:
            mapping.append({"sc_player": sc_name, "sc_team": sc_team, "db_player_id": profiles[(sc_name, db_team)]})
            matched += 1
            continue

        # 2. Manual nickname override
        override = MANUAL_NAME.get((sc_name, sc_team))
        if override and (override, db_team) in profiles:
            mapping.append({"sc_player": sc_name, "sc_team": sc_team, "db_player_id": profiles[(override, db_team)]})
            matched += 1
            continue

        # 3. Token-overlap fallback (same team, most shared name tokens)
        sc_parts = set(norm(sc_name).split())
        best_pid: str | None = None
        best_score = 0
        for (pn, pt), pid in profiles.items():
            if pt != db_team:
                continue
            score = len(sc_parts & set(norm(pn).split()))
            if score > best_score:
                best_score = score
                best_pid = pid

        if best_pid and best_score >= 1:
            mapping.append({"sc_player": sc_name, "sc_team": sc_team, "db_player_id": best_pid})
            matched += 1
        else:
            mapping.append({"sc_player": sc_name, "sc_team": sc_team, "db_player_id": None})
            no_db += 1
            print(f"  NO_DB: [{sc_name}] [{sc_team}]")

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=2, ensure_ascii=False)

    print(f"\nMatched: {matched}/272  |  No DB entry: {no_db}")
    print(f"Saved -> {OUT_FILE}")


if __name__ == "__main__":
    main()
