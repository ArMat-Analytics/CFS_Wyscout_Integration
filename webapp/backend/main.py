"""
FastAPI backend for Contextual Football Scouting adapted for seasonal
aggregated data (Wyscout / wyscout_sample.csv), serving all REST endpoints
in-memory without requiring PostgreSQL/Supabase.
"""
from __future__ import annotations

import math
import os
from typing import List, Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import data_module as dm

app = FastAPI(title="Contextual Football Scouting API (Wyscout wyscout_sample.csv)")

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://localhost:5174",
        "http://127.0.0.1:5173", "http://127.0.0.1:5174",
        FRONTEND_URL,
    ],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

POOL = dm.DATA["pool"]
ALL_PLAYERS = dm.DATA["all_players"]
SIMILARITY = dm.DATA["similarity"]
SIMILARITY_DICT = dm.DATA.get("similarity_dict", {})


def clean(v):
    """NaN/inf -> None, numpy scalars -> native Python types for JSON serialization."""
    if v is None:
        return None
    if isinstance(v, (float, np.floating)):
        if math.isnan(v) or math.isinf(v):
            return None
        return float(v)
    if isinstance(v, (int, np.integer)):
        return int(v)
    if hasattr(v, "item"):
        val = v.item()
        if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
            return None
        return val
    return v


def row_to_dict(row: pd.Series) -> dict:
    return {k: clean(v) for k, v in row.to_dict().items()}


def find_by_player_id(player_id: int) -> Optional[pd.Series]:
    match = POOL[POOL["player_id"] == player_id]
    if not match.empty:
        return match.iloc[0]
    match_all = ALL_PLAYERS[ALL_PLAYERS["player_id"] == player_id]
    if not match_all.empty:
        return match_all.iloc[0]
    return None


router = APIRouter()

# ── health ───────────────────────────────────────────────────────────────────
@router.get("/")
def root():
    return {
        "status": "🟢 SUCCESS",
        "message": f"{len(POOL)} eligible players loaded from wyscout_sample.csv (in-memory, no DB)",
        "total_players": len(ALL_PLAYERS),
    }


# ── /teams/ ──────────────────────────────────────────────────────────────────
@router.get("/teams")
@router.get("/teams/")
def get_teams():
    teams = (
        POOL[["source_team_name"]]
        .drop_duplicates()
        .sort_values("source_team_name")
        .reset_index(drop=True)
    )
    return [
        {"team_id": i + 1, "team_name": row["source_team_name"], "logo_url": None}
        for i, row in teams.iterrows()
    ]


# ── /roles/ ──────────────────────────────────────────────────────────────────
@router.get("/roles")
@router.get("/roles/")
def get_roles():
    return sorted(POOL["primary_role"].dropna().unique().tolist())


# ── /players/ ────────────────────────────────────────────────────────────────
@router.get("/players")
@router.get("/players/")
def get_players(
    search: str = "",
    sort_by: str = "player_name",
    sort_order: str = "asc",
    teams: List[str] = Query(default=[]),
    age_min: Optional[int] = None,
    age_max: Optional[int] = None,
    macro_role: str = "",
    role: str = "",
    foot: str = "",
    val_pre_min: Optional[float] = None,
    val_pre_max: Optional[float] = None,
    val_post_min: Optional[float] = None,
    val_post_max: Optional[float] = None,
    val_diff_min: Optional[float] = None,
    val_diff_max: Optional[float] = None,
):
    df = POOL

    if search:
        df = df[df["player_name"].str.contains(search, case=False, na=False)]
    if teams:
        df = df[df["source_team_name"].isin(teams)]
    if age_min is not None and "Age" in df.columns:
        df = df[df["Age"] >= age_min]
    if age_max is not None and "Age" in df.columns:
        df = df[df["Age"] <= age_max]
    if macro_role:
        df = df[df["macro_role"] == macro_role]
    if role:
        df = df[df["primary_role"] == role]
    if foot:
        df = df[df["preferred_foot"] == foot.lower()]
    if val_pre_min is not None:
        df = df[df["val_pre_num"] >= val_pre_min]
    if val_pre_max is not None:
        df = df[df["val_pre_num"] <= val_pre_max]
    if val_post_min is not None:
        df = df[df["val_post_num"] >= val_post_min]
    if val_post_max is not None:
        df = df[df["val_post_num"] <= val_post_max]
    if val_diff_min is not None and val_diff_min > 0:
        df = df.iloc[0:0]
    if val_diff_max is not None and val_diff_max < 0:
        df = df.iloc[0:0]

    sort_map = {
        "player_name": "player_name", "primary_role": "primary_role", "age": "Age",
        "source_team_name": "source_team_name", "preferred_foot": "preferred_foot",
        "market_value_euros": "market_value_num",
        "market_value_before_euros": "val_pre_num", "market_value_after_euros": "val_post_num",
    }
    sort_col = sort_map.get(sort_by, "player_name")
    df = df.sort_values(sort_col, ascending=(sort_order != "desc"), na_position="last")

    cols = ["player_id", "player_name", "primary_role", "market_value_euros",
            "market_value_before_euros", "market_value_after_euros", "val_pre_num", "val_post_num", "Age",
            "source_team_name", "preferred_foot", "birth_country"]
    cols = [c for c in cols if c in df.columns]
    out = df[cols].rename(columns={"Age": "age"})
    return [row_to_dict(r) for _, r in out.iterrows()]


# ── /players/{id}/stats ──────────────────────────────────────────────────────
@router.get("/players/{player_id}/stats")
def get_player_stats(player_id: int):
    row = find_by_player_id(player_id)
    if row is None:
        return JSONResponse(status_code=404, content={"error": "Stats not found"})

    minutes = row["minutes_played"] or 1
    factor = minutes / 90.0

    return row_to_dict(pd.Series({
        "player_id": int(row["player_id"]),
        "player_name": row["player_name"],
        "source_team_name": row["source_team_name"],
        "birth_country": row.get("birth_country", "Unknown"),
        "age": row.get("Age"),
        "preferred_foot": row.get("preferred_foot"),
        "market_value_euros": row.get("market_value_euros") or row.get("market_value_before_euros"),
        "market_value_before_euros": row.get("market_value_before_euros"),
        "market_value_after_euros": row.get("market_value_after_euros"),
        "minutes_played": row.get("minutes_played"),
        "primary_role": row.get("primary_role"),
        "goals": row.get("Goals"),
        "xg_total": row.get("Expected goals"),
        "assists": row.get("Assists"),
        "key_passes": round((row.get("Key passes/90") or 0) * factor),
        "dribbles_successful": round((row.get("Dribbles/90") or 0) * factor * (row.get("Successful dribbles, %") or 0) / 100.0),
        "pass_completion_pct": row.get("Accurate passes, %"),
        "total_touches": round((row.get("Passes/90") or 0) * factor),
        "ball_recoveries": round((row.get("Successful defensive actions/90") or 0) * factor),
        "interceptions": round((row.get("Interceptions/90") or 0) * factor),
    }))


# ── /players/{id}/decision-quality ──────────────────────────────────────────
DQ_COLS = [
    "player_name", "source_team_name", "primary_role", "macro_role", "minutes_played",
    "n_decisions", "DQ_index", "value_impact",
    "pct__accuracy", "pct__worst_choice", "pct__elite_per90", "pct__poor_per90",
    "score", "avg_miss_cost", "elite_per90", "poor_per90", "accuracy_pct", "worst_choice_pct",
    "birth_country",
]
DQ_RENAME = {"player_name": "player", "source_team_name": "team"}


@router.get("/players/{player_id}/decision-quality")
def get_player_decision_quality(player_id: int):
    row = find_by_player_id(player_id)
    if row is None or "DQ_index" not in row:
        return JSONResponse(status_code=404, content={"error": "Decision Quality data not found"})
    available_cols = [c for c in DQ_COLS if c in row.index]
    return row_to_dict(row[available_cols].rename(DQ_RENAME))


# ── /players/{id}/off-ball (Deprecated / H3 Omitted) ─────────────────────────
@router.get("/players/{player_id}/off-ball")
def get_player_off_ball(player_id: int):
    return JSONResponse(status_code=404, content={"error": "Off-Ball Movement is not available (H3 omitted)"})


# ── /players/{id}/space-control ─────────────────────────────────────────────
SC_IDX_COLS = [
    "player_name", "source_team_name", "primary_role", "macro_role", "minutes_played",
    "coverage_pct", "player_id", "birth_country", "market_value_euros",
    "idx__PROGRESSION", "idx__DANGEROUSNESS", "idx__RECEPTION", "idx__GRAVITY", "idx__DEF",
    "pct__lb_geom_per90", "pct__lb_quality_per90", "pct__lb_epv_per90",
    "pct__successful_hull_penetrations_per90", "pct__defenders_bypassed_mean",
    "pct__epv_added_per90", "pct__epv_penetration_per90", "pct__epv_inside_circ_per90",
    "pct__epv_exit_per90", "pct__epv_outside_circ_per90", "pct__headers_per90",
    "pct__between_lines_pct", "pct__successful_hull_exits_per90", "pct__pressure_resistance_pct",
    "pct__gravity_proximity_pct", "pct__gravity_hull_pct", "pct__gravity_abs_m",
    "pct__interceptions_per90", "pct__duels_per90", "pct__defensive_duels_per90",
    "Age", "preferred_foot", "market_value_before_euros", "market_value_after_euros",
]
SC_IDX_RENAME = {"player_name": "player", "source_team_name": "team", "Age": "age"}

SC_AGG_COLS = [
    "player_name", "source_team_name", "primary_role", "macro_role", "minutes_played",
    "coverage_pct",
    "idx__PROGRESSION", "idx__DANGEROUSNESS", "idx__RECEPTION", "idx__GRAVITY", "idx__DEF",
    "pct__lb_geom_per90", "pct__lb_quality_per90", "pct__lb_epv_per90",
    "pct__epv_penetration_per90", "pct__epv_inside_circ_per90",
    # Core stats
    "lb_geom", "lb_quality", "lb_epv", "defenders_bypassed_mean",
    "penetration_n", "successful_hull_penetrations_n",
    "lb_geom_per90", "lb_quality_per90", "lb_epv_per90",
    "penetration_per90", "successful_hull_penetrations_per90",
    "lb_geom_pct", "lb_quality_pct", "lb_epv_pct", "penetration_completion_pct",
    "epv_penetration_sum", "epv_inside_circ_sum", "epv_exit_sum", "epv_outside_circ_sum",
    "epv_added_per90", "epv_penetration_per90", "epv_inside_circ_per90",
    "epv_exit_per90", "epv_outside_circ_per90",
    "between_lines_n", "pressure_resistance_n", "inside_circ_n",
    "between_lines_per90", "successful_hull_exits_per90", "inside_circ_per90",
    "between_lines_pct", "hull_exit_pct", "pressure_resistance_pct",
    "gravity_directional_m", "gravity_proximity_pct", "gravity_hull_pct",
    "interceptions_n", "interceptions_per90", "duels_n", "duels_per90",
    "defensive_duels_n", "defensive_duels_per90",
    "passes_analysed",
]
SC_AGG_RENAME = {"player_name": "player", "source_team_name": "team"}


@router.get("/players/{player_id}/space-control")
def get_player_space_control(player_id: int):
    row = find_by_player_id(player_id)
    if row is None or "idx__PROGRESSION" not in row:
        return {"indices": None, "aggregated": None}
    return {
        "indices": row_to_dict(row[SC_IDX_COLS].rename(SC_IDX_RENAME)),
        "aggregated": row_to_dict(row[SC_AGG_COLS].rename(SC_AGG_RENAME)),
    }


# ── /decision-quality/similar ───────────────────────────────────────────────
@router.get("/decision-quality/similar")
def get_similar_dq(macro_role: str, exclude_player: Optional[str] = None):
    try:
        df = POOL[POOL["macro_role"] == macro_role]
        if exclude_player:
            df = df[df["player_name"] != exclude_player]
        df = df.sort_values("player_name")
        return [row_to_dict(r[DQ_COLS].rename(DQ_RENAME)) for _, r in df.iterrows()]
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# ── /space-control/similar ──────────────────────────────────────────────────
FB_SIDE = {"LB": "L", "LWB": "L", "RB": "R", "RWB": "R"}


@router.get("/space-control/similar")
def get_similar_players(macro_role: str, exclude_player: Optional[str] = None, player_id: Optional[int] = None):
    try:
        df = POOL[POOL["macro_role"] == macro_role].copy()

        ref_row = None
        if player_id:
            ref_match = POOL[POOL["player_id"] == player_id]
            if not ref_match.empty:
                ref_row = ref_match.iloc[0]
            df = df[df["player_id"] != player_id]
        elif exclude_player:
            ref_match = POOL[POOL["player_name"] == exclude_player]
            if not ref_match.empty:
                ref_row = ref_match.iloc[0]
            df = df[df["player_name"] != exclude_player]

        # Full Back (FB): same side and same preferred foot
        if macro_role == "FB" and ref_row is not None:
            ref_side = FB_SIDE.get(ref_row.get("primary_position"))
            if ref_side:
                df = df[df["primary_position"].map(FB_SIDE) == ref_side]
            ref_foot = ref_row.get("preferred_foot")
            if ref_foot and ref_foot in ("right", "left"):
                df = df[df["preferred_foot"] == ref_foot]

        df = df.sort_values("player_name")
        rows = [row_to_dict(r[SC_IDX_COLS].rename(SC_IDX_RENAME)) for _, r in df.iterrows()]

        lookup_key = str(player_id) if player_id else exclude_player
        sim_lookup = SIMILARITY_DICT.get(lookup_key, {}) if lookup_key else {}
        if not sim_lookup and exclude_player:
            sim_lookup = SIMILARITY_DICT.get(exclude_player, {})

        for r in rows:
            s_score = sim_lookup.get(str(r.get("player_id")))
            if s_score is None:
                s_score = sim_lookup.get(r["player"])
            r["similarity_score"] = clean(s_score)

        rows.sort(key=lambda x: x["similarity_score"] if x["similarity_score"] is not None else -1.0, reverse=True)
        return rows
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# ── /space-control/aggregated ───────────────────────────────────────────────
@router.get("/space-control/aggregated")
def get_sc_aggregated(player: str, team: str):
    match = POOL[(POOL["player_name"] == player) & (POOL["source_team_name"] == team)]
    if match.empty:
        return None
    return row_to_dict(match.iloc[0][SC_AGG_COLS].rename(SC_AGG_RENAME))


# ── /space-control/search ───────────────────────────────────────────────────
@router.get("/space-control/search")
def search_space_control(
    macro_role: Optional[str] = None,
    role: Optional[str] = None,
    prog_min: Optional[float] = Query(None), prog_max: Optional[float] = Query(None),
    danger_min: Optional[float] = Query(None), danger_max: Optional[float] = Query(None),
    recep_min: Optional[float] = Query(None), recep_max: Optional[float] = Query(None),
    grav_min: Optional[float] = Query(None), grav_max: Optional[float] = Query(None),
):
    df = POOL
    if macro_role:
        df = df[df["macro_role"] == macro_role]
    if role:
        df = df[df["primary_role"] == role]
    if prog_min is not None:
        df = df[df["idx__PROGRESSION"] >= prog_min]
    if prog_max is not None:
        df = df[df["idx__PROGRESSION"] <= prog_max]
    if danger_min is not None:
        df = df[df["idx__DANGEROUSNESS"] >= danger_min]
    if danger_max is not None:
        df = df[df["idx__DANGEROUSNESS"] <= danger_max]
    if recep_min is not None:
        df = df[df["idx__RECEPTION"] >= recep_min]
    if recep_max is not None:
        df = df[df["idx__RECEPTION"] <= recep_max]
    if grav_min is not None:
        df = df[df["idx__GRAVITY"] >= grav_min]
    if grav_max is not None:
        df = df[df["idx__GRAVITY"] <= grav_max]

    avg = df[["idx__PROGRESSION", "idx__DANGEROUSNESS", "idx__RECEPTION", "idx__GRAVITY"]].mean(axis=1)
    df = df.assign(_avg=avg).sort_values("_avg", ascending=False)

    cols = ["player_name", "source_team_name", "player_id", "primary_role", "macro_role",
            "minutes_played", "idx__PROGRESSION", "idx__DANGEROUSNESS", "idx__RECEPTION",
            "idx__GRAVITY", "DQ_index", "birth_country", "market_value_euros"]
    cols = [c for c in cols if c in df.columns]
    out = df[cols].rename(columns={
        "player_name": "player", "source_team_name": "team",
    })
    out = out.assign(nation=out.get("birth_country", out["team"]))
    return [row_to_dict(r) for _, r in out.iterrows()]


# ── debug ────────────────────────────────────────────────────────────────────
@router.get("/debug")
@router.get("/debug/")
def debug():
    return {
        "status": "success",
        "pool_size": len(POOL),
        "sample_player": row_to_dict(POOL.iloc[0][["player_name", "source_team_name", "macro_role"]]),
    }


# Mount all endpoints under both root / and prefix /api
app.include_router(router)
app.include_router(router, prefix="/api")