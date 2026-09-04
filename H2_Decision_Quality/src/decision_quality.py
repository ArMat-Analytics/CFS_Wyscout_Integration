"""H2 Decision Quality — the per-player index and website table.

The notebook is only an orchestrator: all the logic lives here.

The index
---------
Per event, `score` is the share of the in-frame alternatives whose xEPV is
at or below the xEPV of the pass the player actually chose (events with at
least 2 alternatives). The player `score` is the mean over their events.
The headline `DQ_index` is the within macro-role percentile of that score.

Why a within-event rank and not regret or absolute xEPV: it cancels the
pitch-zone value level (origin is constant inside an event) and it does not
punish players who operate where many options are valuable.

Storytelling companions: `score_sd` (event-to-event consistency, read with
n_decisions, not a ranking), `elite_per90` / `poor_per90` (count of
decisions above q90 / below q10 of the macro-role, per 90 minutes).

The decision-quality face is read as three distinct angles:
- `accuracy_pct`  — % of events the chosen pass IS the in-frame best
- `worst_choice_pct` — % of events it is the in-frame worst (mirror pair)
- `avg_miss_cost` — mean xEPV left on the table ON the events that were
  not optimal (severity of the mistake, not its frequency)

Radar axes
----------
The four-axis Decision Quality radar is shipped pre-computed as the
`pct__*` columns: within macro-role percentiles of accuracy_pct,
elite_per90, worst_choice_pct and poor_per90. accuracy / elite are used
directly; worst_choice / poor are mirrored (100 - percentile) so that on
every axis "further out = better". The site plots `pct__*` as-is and never
ranks anything itself — same contract as H1's indices CSV.

Pool
----
H1's 135-minute pool, one authoritative role per player from
`player_space_control_aggregated.csv`. No minimum pass count, so the H2
pool is identical to H1 (272 players); `n` is exposed so low-sample
players are visible.

Public API
----------
per_event_signals(alt, corpus_df, epv_grid) -> per-event DataFrame
aggregate_players(pe, roles)               -> per-player DataFrame
build(write=True)                          -> per-player DataFrame (+ csv)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as cfg
from . import xepv as _xepv

MIN_ALTERNATIVES = 2     # need >=2 alternatives for a meaningful rank

# Final column order of the website table.
OUTPUT_COLUMNS = [
    "player", "team", "primary_role", "macro_role", "minutes_played",
    "n_decisions",
    "DQ_index",                                   # headline percentile
    "score", "score_sd", "value_impact",
    "avg_miss_cost",                              # raw block
    "elite_per90", "poor_per90",                  # per 90
    "accuracy_pct", "worst_choice_pct",           # percentages (mirror pair)
    # Radar axes — within-role percentiles ready to plot (0-100).
    # The two "avoids" axes are already mirrored (100 - percentile) so that
    # on every axis "further out = better"; the site plots them directly.
    "pct__accuracy", "pct__worst_choice",
    "pct__elite_per90", "pct__poor_per90",
]


# ---------------------------------------------------------------------------
# Per-event signals
# ---------------------------------------------------------------------------
def per_event_signals(alt: pd.DataFrame,
                       corpus_df: pd.DataFrame,
                       epv_grid: np.ndarray) -> pd.DataFrame:
    """One row per usable event with the decision signals attached.

    `alt` is the long alternatives table; if it has no `xepv` column it is
    computed here via the project formula. `corpus_df` supplies the sender
    position (pass origin) and player/team for each event.
    """
    if "xepv" not in alt.columns:
        alt = _xepv.compute_xepv(alt, epv_grid)

    chosen_xepv = alt.loc[alt["is_chosen"]].set_index("event_id")["xepv"]

    a = alt.loc[~alt["is_chosen"], ["event_id", "xepv"]].copy()
    a["chosen"] = a["event_id"].map(chosen_xepv)
    a["beaten"] = (a["xepv"] <= a["chosen"]).astype(float)

    g = a.groupby("event_id")
    pe = pd.DataFrame({
        "chosen_xepv": chosen_xepv,
        "mean_alt":    g["xepv"].mean(),
        "max_alt":     g["xepv"].max(),
        "min_alt":     g["xepv"].min(),
        "n_alt":       g.size(),
        "score":       g["beaten"].mean(),
    })

    ctx = (corpus_df.drop_duplicates("event_id")
                    .set_index("event_id")[["player", "team"]])

    pe = pe.join(ctx[["player", "team"]])
    pe = pe[pe["n_alt"] >= MIN_ALTERNATIVES].copy()

    pe["delta_xepv"]  = pe["chosen_xepv"] - pe["mean_alt"]
    pe["beat_all"]    = (pe["chosen_xepv"] >= pe["max_alt"]).astype(int)
    # picked the single worst in-frame option (mirror of beat_all)
    pe["worst_pick"]  = (pe["chosen_xepv"] <= pe["min_alt"]).astype(int)
    # how much value the player left on the table WHEN not optimal
    # (NaN on optimal events so the player mean is "cost given a miss")
    miss = pe["max_alt"] - pe["chosen_xepv"]
    pe["miss_cost"]   = miss.where(pe["beat_all"] == 0)
    return pe


# ---------------------------------------------------------------------------
# Per-player aggregation + the single within-role percentile
# ---------------------------------------------------------------------------
def aggregate_players(pe: pd.DataFrame,
                      roles: pd.DataFrame,
                      min_minutes: int = cfg.ANALYSIS_MIN_MINUTES
                      ) -> pd.DataFrame:
    """Collapse per-event signals to one row per player and add DQ_index.

    `roles` is H1's per-player aggregate (authoritative role + minutes).
    The inner join + minutes filter reproduces H1's pool exactly.

    Elite / poor decisions are per-event flags thresholded on `score`
    (the within-event rank) at the q90 / q10 of that player's macro-role,
    computed on the role's event pool *before* aggregation. They become
    per-90 rates so the story reads as a count ("3 elite reads per 90'").
    """
    roles = roles[["player", "team", "primary_role",
                   "macro_role", "minutes_played"]]

    # Bring macro_role + minutes onto the event rows so the elite/poor
    # quantile is taken over the role's events, not the player means.
    pe = (pe.dropna(subset=["player"])
            .merge(roles, on=["player", "team"], how="inner"))
    pe = pe[pe["minutes_played"] >= min_minutes].copy()

    q_hi = pe.groupby("macro_role")["score"].transform(lambda s: s.quantile(0.90))
    q_lo = pe.groupby("macro_role")["score"].transform(lambda s: s.quantile(0.10))
    pe["is_elite"] = (pe["score"] >= q_hi).astype(int)
    pe["is_poor"]  = (pe["score"] <= q_lo).astype(int)

    dq = (pe.groupby(["player", "team"])
            .agg(n_decisions     =("score",       "size"),
                 score            =("score",       "mean"),
                 score_sd         =("score",       "std"),
                 value_impact     =("delta_xepv",  "mean"),
                 n_elite          =("is_elite",    "sum"),
                 n_poor           =("is_poor",     "sum"),
                 accuracy_pct     =("beat_all",    lambda s: 100 * s.mean()),
                 worst_choice_pct =("worst_pick",  lambda s: 100 * s.mean()),
                 avg_miss_cost    =("miss_cost",   "mean"))
            .reset_index())

    dq = dq.merge(roles, on=["player", "team"], how="inner")

    dq["elite_per90"] = dq["n_elite"] / dq["minutes_played"] * 90
    dq["poor_per90"]  = dq["n_poor"]  / dq["minutes_played"] * 90

    # headline percentile: within-role rank of Score (Design K headline)
    dq["DQ_index"] = (dq.groupby("macro_role")["score"]
                        .rank(pct=True).mul(100).round(1))

    # Radar axes: within-role percentiles of the four raw signals, ready to
    # plot. accuracy / elite are "higher is better" so the percentile is used
    # directly; worst_choice / poor are "lower is better" so the axis is
    # mirrored (100 - percentile) — this keeps "further out = better" on every
    # axis. Computed here so the site never has to rank anything itself.
    def _pctl(col: str) -> pd.Series:
        return dq.groupby("macro_role")[col].rank(pct=True).mul(100)

    dq["pct__accuracy"]     = _pctl("accuracy_pct").round(1)
    dq["pct__elite_per90"]  = _pctl("elite_per90").round(1)
    dq["pct__worst_choice"] = (100 - _pctl("worst_choice_pct")).round(1)
    dq["pct__poor_per90"]   = (100 - _pctl("poor_per90")).round(1)

    dq = dq.sort_values("DQ_index", ascending=False).reset_index(drop=True)
    return dq[OUTPUT_COLUMNS]


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------
def build(alt: pd.DataFrame | None = None,
          corpus_df: pd.DataFrame | None = None,
          epv_grid: np.ndarray | None = None,
          write: bool = True) -> pd.DataFrame:
    """End-to-end: load defaults if not supplied, return the player table.

    Writes `cfg.PLAYER_DQ_PATH` when `write` is True. Any argument can be
    passed in (e.g. an `alt` that already has xEPV from the notebook) to
    avoid recomputing.
    """
    if epv_grid is None:
        epv_grid = _xepv.load_epv_grid()
    if alt is None:
        alt = pd.read_parquet(cfg.ALTERNATIVES_PATH)
    if corpus_df is None:
        corpus_df = pd.read_csv(cfg.DQ_CORPUS_PATH,
                                usecols=["event_id", "player", "team",
                                         "start_x_m", "start_y_m"])
    roles = pd.read_csv(cfg.H1_PLAYER_AGG,
                        usecols=["player", "team", "primary_role",
                                 "macro_role", "minutes_played"])

    pe = per_event_signals(alt, corpus_df, epv_grid)
    dq = aggregate_players(pe, roles)

    if write:
        cfg.PLAYER_DQ_PATH.parent.mkdir(parents=True, exist_ok=True)
        dq.to_csv(cfg.PLAYER_DQ_PATH, index=False)
    return dq
