"""H4 Player Similarity — the player DNA and the within-role similarity model.

The notebook is only an orchestrator: all the logic lives here.

The idea
--------
Each player is represented by an 11-dimensional **DNA vector** of within-role
percentile axes drawn from the three completed studies (see `config.DNA_AXES`):
H1 space-control indices, H2 decision-quality axes, H3 off-ball axes. We then
measure how similar two players are by the distance between their DNA vectors,
**within macro-role only** — a CB is compared with CBs, a CAM with CAMs.

Why within-role, and why these axes
-----------------------------------
The whole project reads within role, and the axes are *within-role* percentiles,
so a percentile in one role is not comparable to the same percentile in another;
cross-role distances on these coordinates would be ill-defined. Within role they
are directly comparable. The DNA keeps each study's component axes and drops the
headline aggregates (DQ_index, URS/90) because those are functions — a rank, or
Potential × Latency — of axes already present, i.e. redundant by construction.

Why similarity and not clustering
---------------------------------
The original proposal framed H4 as clustering players into archetypes. On this
single-tournament sample clustering is degenerate: cross-role it simply
rediscovers the positional labels, and within-role the pools
are too small (20–65 players) for stable clusters. 

Distance and score
-------------------
Default distance is Euclidean in the 11-D percentile space. The raw distance is
turned into a 0–100 **similarity score** (100 = identical profile) by
`score = (1 - dist / dist_max) * 100`, where `dist_max = sqrt(n_axes) * 100` is
the largest possible distance between two percentile vectors. Cosine distance is
offered as an alternative for robustness checks.

Public API
----------
load_dna()                                  -> per-player DNA DataFrame (+ role)
similarity_score(dist, n_axes)              -> 0–100 score from a distance
neighbours(dna, player, team, ...)          -> that player's ranked neighbours
build_similarity_table(dna, top_k, metric)  -> long (source, neighbour, score) table
axis_redundancy(dna)                        -> within-role |Spearman| matrix of axes
build(write=True)                           -> (dna, similarity_table) (+ csvs)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as cfg


# ---------------------------------------------------------------------------
# DNA assembly
# ---------------------------------------------------------------------------
def load_dna() -> pd.DataFrame:
    """Join the three studies into one per-player DNA table.

    Returns the identity columns (`player`, `team`, `macro_role`) plus the 11
    `cfg.DNA_AXES`, each expressed as a **within-role percentile (0–100)**.

    Why re-percentile every axis. The H2 and H3 axes already ship as within-role
    percentiles, but H1's indices (`idx__*`) are composite normalised scores with
    a smaller, non-uniform spread. Mixing the two scales would let the percentile
    axes dominate the Euclidean distance and let H1's spatial axes — Gravity
    especially — count for far less than one eleventh. Re-ranking *every* axis to
    a within-role percentile puts all eleven on one uniform 0–100 scale, so each
    contributes equally to the distance by construction. The three pools are H1's
    272-player pool, so the inner join on (player, team) keeps every player; any
    stray NaN is filled with the within-role median before ranking.
    """
    h1 = pd.read_csv(cfg.H1_INDICES, usecols=cfg.KEY + [cfg.ROLE_COL] + cfg.H1_AXES)
    h2 = pd.read_csv(cfg.H2_DQ,      usecols=cfg.KEY + cfg.H2_AXES)
    h3 = pd.read_csv(cfg.H3_URS,     usecols=cfg.KEY + cfg.H3_AXES)

    dna = (h1.merge(h2, on=cfg.KEY, how="inner")
             .merge(h3, on=cfg.KEY, how="inner"))

    for c in cfg.DNA_AXES:
        dna[c] = dna.groupby(cfg.ROLE_COL)[c].transform(lambda s: s.fillna(s.median()))
        # uniform within-role percentile (0–100) so every axis weighs equally
        dna[c] = dna.groupby(cfg.ROLE_COL)[c].rank(pct=True) * 100.0

    # attach the clean Transfermarkt display name (Pedri, Rodri, …) for readable
    # output; falls back to the StatsBomb name if the mapping is unavailable.
    names = load_display_names()
    if names is not None:
        dna = dna.merge(names, on=cfg.KEY, how="left")
    dna["display"] = dna.get("display", pd.Series(index=dna.index, dtype=object))
    dna["display"] = dna["display"].fillna(dna["player"])

    return dna.reset_index(drop=True)


def load_display_names() -> pd.DataFrame | None:
    """Clean Transfermarkt display names keyed on (player, team).

    Maps each StatsBomb (player, team) to its Transfermarkt `player_name`
    (e.g. 'Pedro González López' → 'Pedri') via the project mapping. Returns
    None if the source files are not present.
    """
    import json
    if not (cfg.TM_MAPPING.exists() and cfg.TM_PLAYER_DATA.exists()):
        return None
    mp = pd.DataFrame(json.loads(cfg.TM_MAPPING.read_text()))
    mp["db_player_id"] = mp["db_player_id"].astype(str)
    pdc = pd.read_csv(cfg.TM_PLAYER_DATA, usecols=["player_id", "player_name"])
    pdc["player_id"] = pdc["player_id"].astype(str)
    m = mp.merge(pdc, left_on="db_player_id", right_on="player_id", how="left")
    return m.rename(columns={"sc_player": "player",
                             "sc_team": "team",
                             "player_name": "display"})[["player", "team", "display"]]


# ---------------------------------------------------------------------------
# Market values (optional) — for the value-arbitrage use case
# ---------------------------------------------------------------------------
def _parse_money(x) -> float:
    """Parse a Transfermarkt money string ('€80.00M', '€18,00M', '€300,00K')
    into euros as a float. Returns NaN on anything unparseable."""
    if not isinstance(x, str):
        return np.nan
    s = x.replace("€", "").replace(" ", "").upper()
    mult = 1.0
    if s.endswith("M"):
        mult, s = 1e6, s[:-1]
    elif s.endswith("K"):
        mult, s = 1e3, s[:-1]
    # the scraper mixes '.' and ',' as the decimal/thousands mark; keep the last
    # separator as decimal, drop the rest
    s = s.replace(".", "X").replace(",", "X")
    if "X" in s:
        head, _, tail = s.rpartition("X")
        s = head.replace("X", "") + "." + tail
    try:
        return float(s) * mult
    except ValueError:
        return np.nan


def load_market_values() -> pd.DataFrame | None:
    """Per-player pre- and post-Euro market values in euros, keyed on (player,
    team) to match the DNA. Returns None if the source files are not present.

    Pre-Euro is the value the analysis should use: the DNA is built on Euro 2024
    performance, so pairing it with the *post*-Euro value would leak the
    tournament back into the price. The post-Euro value is returned alongside
    purely so the arbitrage can be back-tested (did the cheap look-alike's price
    actually rise?).
    """
    import json
    if not (cfg.TM_MAPPING.exists() and cfg.TM_PLAYER_DATA.exists()):
        return None

    mp = pd.DataFrame(json.loads(cfg.TM_MAPPING.read_text()))
    mp["db_player_id"] = mp["db_player_id"].astype(str)

    pdc = pd.read_csv(cfg.TM_PLAYER_DATA,
                      usecols=["player_id",
                               "market_value_before_euros",
                               "market_value_after_euros"])
    pdc["player_id"] = pdc["player_id"].astype(str)

    m = mp.merge(pdc, left_on="db_player_id", right_on="player_id", how="left")
    m["mv_pre"]  = m["market_value_before_euros"].map(_parse_money)
    m["mv_post"] = m["market_value_after_euros"].map(_parse_money)
    return m.rename(columns={"sc_player": "player", "sc_team": "team"})[
        ["player", "team", "mv_pre", "mv_post"]]


# ---------------------------------------------------------------------------
# Distance → score
# ---------------------------------------------------------------------------
def similarity_score(dist: np.ndarray, n_axes: int) -> np.ndarray:
    """Map a Euclidean distance in percentile space to a 0–100 score.

    The largest possible distance between two vectors of `n_axes` percentiles
    (each in [0, 100]) is sqrt(n_axes) * 100, so dividing by it gives a
    normalised [0, 1] dissimilarity; 1 minus that, times 100, is the score
    (100 = identical, 0 = maximally different).
    """
    dist_max = np.sqrt(n_axes) * 100.0
    return (1.0 - dist / dist_max) * 100.0


def _distances(mat: np.ndarray, vec: np.ndarray, metric: str) -> np.ndarray:
    """Distance from every row of `mat` to `vec` under `metric`."""
    if metric == "euclidean":
        return np.sqrt(((mat - vec) ** 2).sum(axis=1))
    if metric == "cosine":
        # cosine *distance* in [0, 2]; rescaled to a comparable 0–100 score below
        a = mat / (np.linalg.norm(mat, axis=1, keepdims=True) + 1e-9)
        b = vec / (np.linalg.norm(vec) + 1e-9)
        return 1.0 - a @ b
    raise ValueError(f"unknown metric: {metric!r}")


# ---------------------------------------------------------------------------
# Neighbours for one player
# ---------------------------------------------------------------------------
def neighbours(dna: pd.DataFrame,
               player: str,
               team: str | None = None,
               top_k: int | None = None,
               metric: str = "euclidean") -> pd.DataFrame:
    """The `top_k` most similar players to one player, within his macro-role.

    Matches `player` (and `team` if given) by exact value; falls back to a
    case-insensitive substring match on `player` so notebook calls can pass a
    short name. Returns neighbour rows with a `similarity` column, sorted high
    to low.
    """
    if team is not None:
        row = dna[(dna["player"] == player) & (dna["team"] == team)]
    else:
        row = dna[dna["player"] == player]
        if row.empty:
            # substring match on the StatsBomb name or the clean display name,
            # so callers can pass "Pedri", "Rodri", "Jorginho", etc.
            mask = dna["player"].str.contains(player, case=False, na=False)
            if "display" in dna.columns:
                mask = mask | dna["display"].str.contains(player, case=False, na=False)
            row = dna[mask]
    if row.empty:
        raise KeyError(f"player not found: {player!r}")
    row = row.iloc[0]

    pool = dna[(dna[cfg.ROLE_COL] == row[cfg.ROLE_COL]) &
               (dna["player"] != row["player"])].copy()

    dist = _distances(pool[cfg.DNA_AXES].to_numpy(float),
                      row[cfg.DNA_AXES].to_numpy(float), metric)
    if metric == "euclidean":
        pool["similarity"] = similarity_score(dist, len(cfg.DNA_AXES))
    else:  # cosine distance in [0, 2] → 0–100 score
        pool["similarity"] = (1.0 - dist / 2.0) * 100.0

    pool = pool.sort_values("similarity", ascending=False)
    if top_k:
        pool = pool.head(top_k)
    out_cols = ["player", "team", cfg.ROLE_COL, "similarity"]
    if "display" in pool.columns:
        out_cols.insert(1, "display")
    return pool[out_cols].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Full similarity table (every player → its top-k neighbours)
# ---------------------------------------------------------------------------
def build_similarity_table(dna: pd.DataFrame,
                           top_k: int | None = None,
                           metric: str = "euclidean") -> pd.DataFrame:
    """Long table of each player's within-role neighbours, ranked by similarity.

    With `top_k=None` (the default for the shipped artefact) it stores **every**
    same-role opponent for each player, so the website can sort by score and show
    as many as it likes in the "Compare With" picker. Pass an integer to keep
    only the top-`top_k` per player (handy for compact notebook views).

    Columns: source_player, source_team, macro_role, neighbour_player,
    neighbour_team, similarity, rank. This is the artefact the website backend
    reads to fill `similarity_score`.
    """
    out = []
    for _, r in dna.iterrows():
        nb = neighbours(dna, r["player"], r["team"], top_k=top_k, metric=metric)
        keep = ["player", "team", "similarity"]
        nb = nb[keep].rename(columns={"player": "neighbour_player",
                                      "team": "neighbour_team"})
        nb["source_player"] = r["player"]
        nb["source_team"]   = r["team"]
        nb["macro_role"]    = r[cfg.ROLE_COL]
        nb["rank"]          = np.arange(1, len(nb) + 1)
        out.append(nb)

    cols = ["source_player", "source_team", "macro_role",
            "neighbour_player", "neighbour_team", "similarity", "rank"]
    return pd.concat(out, ignore_index=True)[cols]


# ---------------------------------------------------------------------------
# Validation helper — axis redundancy
# ---------------------------------------------------------------------------
def axis_redundancy(dna: pd.DataFrame) -> pd.DataFrame:
    """Within-role |Spearman| correlation matrix of the 11 DNA axes.

    Each axis is ranked within macro-role, then correlated across the pooled
    within-role ranks (the same recipe used in H2/H3). High off-diagonal values
    flag axes that carry overlapping information and so double-count in the
    Euclidean distance. Returned as absolute correlations, diagonal zeroed.
    """
    wr = dna.copy()
    for c in cfg.DNA_AXES:
        wr[c] = wr.groupby(cfg.ROLE_COL)[c].rank(pct=True)
    M = wr[cfg.DNA_AXES].corr(method="spearman").abs()
    vals = M.to_numpy().copy()
    np.fill_diagonal(vals, 0.0)
    out = pd.DataFrame(vals, index=cfg.DNA_LABELS, columns=cfg.DNA_LABELS)
    return out.round(2)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------
def build(top_k: int | None = None,
          metric: str = "euclidean",
          write: bool = True) -> tuple[pd.DataFrame, pd.DataFrame]:
    """End-to-end: assemble the DNA and the similarity table, return both.

    By default (`top_k=None`) the similarity table holds **all** within-role
    pairs, so the website can rank and page through them; the website backend
    reads `cfg.SIMILARITY_PATH` to fill `similarity_score`. Writes `cfg.DNA_PATH`
    and `cfg.SIMILARITY_PATH` when `write` is True.
    """
    dna = load_dna()
    sim = build_similarity_table(dna, top_k=top_k, metric=metric)

    if write:
        cfg.DATA_DIR.mkdir(parents=True, exist_ok=True)
        dna.to_csv(cfg.DNA_PATH, index=False)
        sim.to_csv(cfg.SIMILARITY_PATH, index=False)
    return dna, sim
