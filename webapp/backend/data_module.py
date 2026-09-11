"""
data_module.py — Self-contained data layer adapted for
seasonal aggregated data (Wyscout / wyscout_sample.csv).

Loads wyscout_sample.csv ONCE upon module import and computes, in-memory (no database required),
all scouting indices:
  - H1 Space Control (Progression, Dangerousness, Reception, Gravity)
  - H2 Decision Quality (DQ Index, Value Impact)
  - H4 Player Similarity (8-axis style DNA + within-role nearest neighbors)

Prepares the exact dictionary structures expected by the FastAPI backend
and frontend components.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


def _resolve_data_path() -> Path:
    """Resolve dynamic relative path to wyscout_sample.csv with robust fallbacks."""
    env_path = os.getenv("DATA_PATH")
    if env_path and Path(env_path).exists():
        return Path(env_path)

    current_file = Path(__file__).resolve()
    candidates = [
        current_file.parent / "data" / "wyscout_sample.csv",
        current_file.parent / "wyscout_sample.csv",
        current_file.parent.parent.parent / "data" / "wyscout_sample.csv",
        Path("data/wyscout_sample.csv"),
        Path("../../data/wyscout_sample.csv"),
        Path("../data/wyscout_sample.csv"),
        # Fallback to euro.csv if present
        current_file.parent / "data" / "euro.csv",
        current_file.parent / "euro.csv",
        current_file.parent.parent.parent / "data" / "euro.csv",
        Path("data/euro.csv"),
        Path("../../data/euro.csv"),
        Path("../data/euro.csv"),
    ]
    for p in candidates:
        if p.exists():
            return p
    return current_file.parent / "data" / "wyscout_sample.csv"


# Trigger fresh load of wyscout_sample.csv with imputed Foot and Market Value
DATA_PATH = _resolve_data_path()
MIN_MINUTES = 300  # Consistent criterion with adapted H1-H4 notebooks

# ── Roles: Wyscout code -> macro role -> standardized role label ─────────
MACRO_MAP = {
    "GK": "GK",
    "CB": "CB", "LCB": "CB", "RCB": "CB",
    "LB": "FB", "RB": "FB", "LWB": "FB", "RWB": "FB",
    "DMF": "MID", "LDMF": "MID", "RDMF": "MID", "CMF": "MID", "LCMF": "MID", "RCMF": "MID",
    "AMF": "CAM",
    "LAMF": "WIDE", "RAMF": "WIDE", "LW": "WIDE", "RW": "WIDE", "LWF": "WIDE", "RWF": "WIDE",
    "CF": "FW", "SS": "FW",
}
PRIMARY_ROLE_LABEL = {
    "GK": "Goalkeeper",
    "CB": "Center Back", "LCB": "Left Center Back", "RCB": "Right Center Back",
    "LB": "Left Back", "RB": "Right Back", "LWB": "Left Wing Back", "RWB": "Right Wing Back",
    "DMF": "Center Defensive Midfield", "LDMF": "Left Defensive Midfield", "RDMF": "Right Defensive Midfield",
    "CMF": "Left Center Midfield", "LCMF": "Left Center Midfield", "RCMF": "Right Center Midfield",
    "AMF": "Center Attacking Midfield", "LAMF": "Left Attacking Midfield", "RAMF": "Right Attacking Midfield",
    "LW": "Left Wing", "RW": "Right Wing", "LWF": "Left Wing", "RWF": "Right Wing",
    "CF": "Center Forward", "SS": "Center Forward",
}
FOOT_LABEL = {
    "right": "right", "left": "left", "both": "both",
}

ROLE_ORDER = ["CB", "FB", "MID", "CAM", "WIDE", "FW"]


def format_market_value(v) -> str | None:
    if v is None or (isinstance(v, float) and pd.isna(v)) or v == 0:
        return None
    try:
        v = float(v)
    except (ValueError, TypeError):
        return None
    if v <= 0:
        return None
    if v >= 1_000_000:
        return f"€{v / 1_000_000:.2f}M"
    if v >= 1_000:
        return f"€{v / 1_000:.0f}K"
    return f"€{v:.0f}"


def _pct(frame: pd.DataFrame, col: str) -> pd.Series:
    ranked = frame.groupby("macro_role")[col].rank(pct=True) * 100
    return ranked.fillna(50.0)


def _load_base() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH, low_memory=False)
    df.columns = [str(c).strip() for c in df.columns]

    pos_col = "Position" if "Position" in df.columns else [c for c in df.columns if "pos" in c.lower()][0]
    foot_col = "Foot" if "Foot" in df.columns else [c for c in df.columns if "foot" in c.lower()][0]

    primary_position = df[pos_col].apply(lambda p: str(p).split(",")[0].strip())
    macro_role = primary_position.map(MACRO_MAP).fillna("MID")
    primary_role = primary_position.map(PRIMARY_ROLE_LABEL).fillna("Left Center Midfield")
    minutes_played = pd.to_numeric(df.get("Minutes played", 0), errors="coerce").fillna(0).astype(int)
    preferred_foot = df[foot_col].astype(str).str.lower().map(FOOT_LABEL)
    player_id = df.index.astype(int) + 1
    player_name = df.get("Player", pd.Series("Unknown", index=df.index)).fillna("Unknown")
    source_team_name = df.get("Team", pd.Series("Unknown", index=df.index)).fillna("Unknown")

    mv_col = "Market value" if "Market value" in df.columns else [c for c in df.columns if "market" in c.lower()][0]
    mv_fmt = df[mv_col].apply(format_market_value) if mv_col in df.columns else pd.Series(None, index=df.index)
    val_pre_num = pd.to_numeric(df[mv_col], errors="coerce").fillna(0.0) if mv_col in df.columns else pd.Series(0.0, index=df.index)

    key_passes = pd.to_numeric(df.get("Key passes/90"), errors="coerce").fillna(0)
    smart_passes = pd.to_numeric(df.get("Smart passes/90"), errors="coerce").fillna(0)
    incisive_actions90 = key_passes + smart_passes

    birth_col = "Birth country" if "Birth country" in df.columns else [c for c in df.columns if "birth" in c.lower()][0] if any("birth" in c.lower() for c in df.columns) else None
    pass_col = "Passport country" if "Passport country" in df.columns else None
    if birth_col:
        birth_country_raw = df[birth_col].fillna(df[pass_col] if pass_col else "Unknown").fillna("Unknown")
    elif pass_col:
        birth_country_raw = df[pass_col].fillna("Unknown")
    else:
        birth_country_raw = pd.Series("Unknown", index=df.index)
    birth_country = birth_country_raw.apply(lambda c: str(c).split(",")[0].strip() if pd.notna(c) and str(c).strip() != "" else "Unknown")

    new_cols = pd.DataFrame({
        "primary_position": primary_position,
        "macro_role": macro_role,
        "primary_role": primary_role,
        "minutes_played": minutes_played,
        "preferred_foot": preferred_foot,
        "player_id": player_id,
        "player_name": player_name,
        "source_team_name": source_team_name,
        "birth_country": birth_country,
        "market_value_euros": mv_fmt,
        "market_value_num": val_pre_num,
        "market_value_before_euros": mv_fmt,
        "market_value_after_euros": mv_fmt,
        "val_pre_num": val_pre_num,
        "val_post_num": val_pre_num,
        "incisive_actions90": incisive_actions90,
    }, index=df.index)

    return pd.concat([df, new_cols], axis=1).copy()


def _add_space_control(pool: pd.DataFrame) -> pd.DataFrame:
    PROG_MAP = {
        "pct__lb_geom_per90": "Progressive passes/90",
        "pct__lb_quality_per90": "Accurate progressive passes, %",
        "pct__lb_epv_per90": "Passes to final third/90",
        "pct__successful_hull_penetrations_per90": "Passes to penalty area/90",
        "pct__defenders_bypassed_mean": "Progressive runs/90",
    }
    DANGER_MAP = {
        "pct__epv_penetration_per90": "Expected goals/90",
        "pct__epv_inside_circ_per90": "Expected assists/90",
        "pct__epv_exit_per90": "Key passes/90",
        "pct__epv_outside_circ_per90": "Touches in box/90",
        "pct__headers_per90": "Head goals/90",
    }
    RECEP_MAP = {
        "pct__between_lines_pct": "Touches in box/90",
        "pct__successful_hull_exits_per90": "Received passes/90",
        "pct__pressure_resistance_pct": "Deep completions/90",
    }
    GRAV_MAP = {
        "pct__gravity_proximity_pct": "Fouls suffered/90",
        "pct__gravity_hull_pct": "Offensive duels/90",
    }
    DEF_MAP = {
        "pct__interceptions_per90": "Interceptions/90",
        "pct__duels_per90": "Duels/90",
        "pct__defensive_duels_per90": "Defensive duels/90",
    }

    new_cols = {}
    for group in (PROG_MAP, DANGER_MAP, RECEP_MAP, GRAV_MAP, DEF_MAP):
        for pct_col, src_col in group.items():
            new_cols[pct_col] = _pct(pool, src_col)

    pct_df = pd.DataFrame(new_cols, index=pool.index)
    pool = pd.concat([pool, pct_df], axis=1)

    pool["pct__gravity_abs_m"] = pool[["pct__gravity_proximity_pct", "pct__gravity_hull_pct"]].mean(axis=1).fillna(50.0)
    pool["pct__epv_added_per90"] = pool[list(DANGER_MAP.keys())].mean(axis=1).fillna(50.0)

    pool["idx__PROGRESSION"] = pool[["pct__lb_geom_per90", "pct__defenders_bypassed_mean", "pct__lb_epv_per90"]].mean(axis=1).fillna(50.0)
    pool["idx__DANGEROUSNESS"] = pool[["pct__epv_penetration_per90", "pct__epv_inside_circ_per90"]].mean(axis=1).fillna(50.0)
    pool["idx__RECEPTION"] = pool[["pct__between_lines_pct", "pct__successful_hull_exits_per90", "pct__pressure_resistance_pct"]].mean(axis=1).fillna(50.0)
    pool["idx__GRAVITY"] = pool[["pct__gravity_proximity_pct", "pct__gravity_hull_pct"]].mean(axis=1).fillna(50.0)

    def_weighted_cb = (
        0.5 * pool["pct__defensive_duels_per90"]
        + 0.25 * pool["pct__interceptions_per90"]
        + 0.25 * pool["pct__duels_per90"]
    )
    pool["idx__DEF"] = np.where(
        pool["macro_role"] == "CB",
        def_weighted_cb,
        pool[list(DEF_MAP.keys())].mean(axis=1).fillna(50.0),
    )
    pool["coverage_pct"] = 100.0

    factor = pool["minutes_played"] / 90.0
    acc = pd.to_numeric(pool.get("Accurate passes, %"), errors="coerce").fillna(0)
    passes90 = pd.to_numeric(pool.get("Passes/90"), errors="coerce").replace(0, np.nan)

    # Core stats
    prog_passes90 = pd.to_numeric(pool.get("Progressive passes/90"), errors="coerce").fillna(0)
    prog_acc = pd.to_numeric(pool.get("Accurate progressive passes, %"), errors="coerce").fillna(0)
    p3rd90 = pd.to_numeric(pool.get("Passes to final third/90"), errors="coerce").fillna(0)
    pbox90 = pd.to_numeric(pool.get("Passes to penalty area/90"), errors="coerce").fillna(0)
    xg90 = pd.to_numeric(pool.get("Expected goals/90"), errors="coerce").fillna(0)
    xa90 = pd.to_numeric(pool.get("Expected assists/90"), errors="coerce").fillna(0)
    keyp90 = pd.to_numeric(pool.get("Key passes/90"), errors="coerce").fillna(0)
    box_touches90 = pd.to_numeric(pool.get("Touches in box/90"), errors="coerce").fillna(0)
    rcv_passes90 = pd.to_numeric(pool.get("Received passes/90"), errors="coerce").fillna(0)
    deep_rcv90 = pd.to_numeric(pool.get("Deep completions/90"), errors="coerce").fillna(0)
    intercep90 = pd.to_numeric(pool.get("Interceptions/90"), errors="coerce").fillna(0)
    duels90 = pd.to_numeric(pool.get("Duels/90"), errors="coerce").fillna(0)
    def_duels90 = pd.to_numeric(pool.get("Defensive duels/90"), errors="coerce").fillna(0)
    runs90 = pd.to_numeric(pool.get("Progressive runs/90"), errors="coerce").fillna(0)

    pool["lb_geom_per90"] = prog_passes90
    pool["lb_quality_per90"] = prog_passes90 * prog_acc / 100.0
    pool["lb_epv_per90"] = p3rd90
    pool["lb_geom"] = (pool["lb_geom_per90"] * factor).round()
    pool["lb_quality"] = (pool["lb_quality_per90"] * factor).round()
    pool["lb_epv"] = (pool["lb_epv_per90"] * factor).round()
    pool["defenders_bypassed_mean"] = runs90
    pool["penetration_per90"] = pbox90
    pool["penetration_n"] = (pool["penetration_per90"] * factor).round()
    pool["successful_hull_penetrations_per90"] = pool["penetration_per90"] * acc / 100.0
    pool["successful_hull_penetrations_n"] = (pool["successful_hull_penetrations_per90"] * factor).round()
    pool["lb_geom_pct"] = (pool["lb_geom_per90"] / passes90 * 100.0).fillna(0.0)
    pool["lb_quality_pct"] = (pool["lb_quality_per90"] / passes90 * 100.0).fillna(0.0)
    pool["lb_epv_pct"] = (pool["lb_epv_per90"] / passes90 * 100.0).fillna(0.0)
    pool["penetration_completion_pct"] = acc

    pool["epv_penetration_per90"] = xg90
    pool["epv_inside_circ_per90"] = xa90
    pool["epv_exit_per90"] = keyp90
    pool["epv_outside_circ_per90"] = box_touches90
    pool["epv_added_per90"] = pool[["epv_penetration_per90", "epv_inside_circ_per90", "epv_exit_per90", "epv_outside_circ_per90"]].sum(axis=1)
    pool["epv_penetration_sum"] = (pool["epv_penetration_per90"] * factor).round(1)
    pool["epv_inside_circ_sum"] = (pool["epv_inside_circ_per90"] * factor).round(1)
    pool["epv_exit_sum"] = (pool["epv_exit_per90"] * factor).round(1)
    pool["epv_outside_circ_sum"] = (pool["epv_outside_circ_per90"] * factor).round(1)

    pool["between_lines_per90"] = box_touches90
    pool["between_lines_n"] = (pool["between_lines_per90"] * factor).round()
    pool["between_lines_pct"] = (pool["between_lines_per90"] / passes90 * 100.0).fillna(0.0)
    pool["successful_hull_exits_per90"] = rcv_passes90
    pool["hull_exit_pct"] = acc
    pool["inside_circ_per90"] = rcv_passes90
    pool["inside_circ_n"] = (pool["inside_circ_per90"] * factor).round()
    pool["pressure_resistance_per90"] = deep_rcv90
    pool["pressure_resistance_n"] = (pool["pressure_resistance_per90"] * factor).round()
    pool["pressure_resistance_pct"] = acc

    pool["gravity_proximity_pct"] = pool["pct__gravity_proximity_pct"]
    pool["gravity_hull_pct"] = pool["pct__gravity_hull_pct"]
    pool["gravity_directional_m"] = ((pool["pct__gravity_proximity_pct"] - 50.0) / 10.0).round(2)

    pool["interceptions_per90"] = intercep90
    pool["interceptions_n"] = (pool["interceptions_per90"] * factor).round()
    pool["duels_per90"] = duels90
    pool["duels_n"] = (pool["duels_per90"] * factor).round()
    pool["defensive_duels_per90"] = def_duels90
    pool["defensive_duels_n"] = (pool["defensive_duels_per90"] * factor).round()

    raw_passes90 = pd.to_numeric(pool.get("Passes/90"), errors="coerce").fillna(0)
    pool["passes_analysed"] = (raw_passes90 * factor).round()

    return pool.copy()


def _add_decision_quality(pool: pd.DataFrame) -> pd.DataFrame:
    pool["pct__accuracy"] = _pct(pool, "Accurate passes, %")
    pool["pct__worst_choice"] = _pct(pool, "Duels won, %")
    pool["pct__elite_per90"] = _pct(pool, "incisive_actions90")
    pool["pct__poor_per90"] = _pct(pool, "Accurate progressive passes, %")

    pool["DQ_index"] = pool[["pct__accuracy", "pct__worst_choice", "pct__elite_per90", "pct__poor_per90"]].mean(axis=1).fillna(50.0)
    if "pct__epv_penetration_per90" in pool.columns and "pct__epv_inside_circ_per90" in pool.columns:
        pool["value_impact"] = pool[["pct__epv_penetration_per90", "pct__epv_inside_circ_per90"]].mean(axis=1).fillna(50.0).round(1)
    else:
        pool["value_impact"] = pool["pct__accuracy"].round(1)

    pool["accuracy_pct"] = pd.to_numeric(pool.get("Accurate passes, %"), errors="coerce").fillna(0.0).round(1)
    pool["worst_choice_pct"] = pd.to_numeric(pool.get("Duels won, %"), errors="coerce").fillna(0.0).round(1)
    pool["elite_per90"] = pool["incisive_actions90"].round(2)
    pool["poor_per90"] = pd.to_numeric(pool.get("Accurate progressive passes, %"), errors="coerce").fillna(0.0).round(1)
    pool["score"] = (pool["DQ_index"] / 100.0).round(2)
    pool["avg_miss_cost"] = np.nan
    passes90 = pd.to_numeric(pool.get("Passes/90"), errors="coerce").fillna(0)
    pool["n_decisions"] = (passes90 * pool["minutes_played"] / 90.0).round().astype(int)
    return pool.copy()


def _build_similarity(pool: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, dict[str, float]]]:
    """H4 — 8-axis DNA (4 H1 + 4 H2) and Euclidean similarity computation."""
    dna_cols = [
        "idx__PROGRESSION", "idx__DANGEROUSNESS", "idx__RECEPTION", "idx__GRAVITY",
        "pct__accuracy", "pct__worst_choice", "pct__elite_per90", "pct__poor_per90",
    ]
    d_max = np.sqrt(len(dna_cols) * (100.0 ** 2))

    rows = []
    sim_dict: dict[str, dict[str, float]] = {}

    for role, grp in pool.groupby("macro_role"):
        matrix = grp[dna_cols].astype(float).fillna(50.0).to_numpy()
        names = grp["player_name"].tolist()
        teams = grp["source_team_name"].tolist()
        pids = grp["player_id"].tolist()
        n = len(grp)

        for i in range(n):
            p_src = names[i]
            t_src = teams[i]
            pid_src = pids[i]
            id_key = str(pid_src)
            if p_src not in sim_dict:
                sim_dict[p_src] = {}
            if id_key not in sim_dict:
                sim_dict[id_key] = {}

            diff = matrix - matrix[i]
            dist = np.sqrt((diff ** 2).sum(axis=1))
            sim = np.clip((1.0 - dist / d_max) * 100.0, 0.0, 100.0)

            for j in range(n):
                if i == j:
                    continue
                p_neigh = names[j]
                pid_neigh = pids[j]
                s_val = round(float(sim[j]), 2)
                sim_dict[p_src][p_neigh] = s_val
                sim_dict[id_key][str(pid_neigh)] = s_val
                rows.append({
                    "source_player": p_src, "source_team": t_src, "source_player_id": pid_src,
                    "neighbour_player": p_neigh, "neighbour_team": teams[j], "neighbour_player_id": pid_neigh,
                    "similarity": s_val,
                })

    return pd.DataFrame(rows), sim_dict


def build_dataset() -> dict:
    df = _load_base()

    pool = df[df["macro_role"] != "GK"].copy()
    pool = pool[pool["minutes_played"] >= MIN_MINUTES].copy()

    pool = _add_space_control(pool)
    pool = _add_decision_quality(pool)

    similarity_df, sim_dict = _build_similarity(pool)

    return {
        "all_players": df,
        "pool": pool,
        "similarity": similarity_df,
        "similarity_dict": sim_dict,
    }


DATA = build_dataset()
