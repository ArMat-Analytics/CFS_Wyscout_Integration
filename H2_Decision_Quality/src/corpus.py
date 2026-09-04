"""H2 corpus construction.

Starts from H1's `hull_events_lb.csv` and adds what xPass needs that H1 did
not persist:

    * pass.height                                    — model feature
    * pass.body_part                                  — header exclusion
    * detailed pass.outcome                           — richer label audit
    * full 360 freeze frame (TEAMMATES + opponents)   — receiver position

H1 only cached opponents (line-breaker geometry). H2 needs teammate locations
to identify the chosen receiver in the frame, so we re-fetch the frames once
and cache the merged (teammates, opponents) view in `frames360_cache.parquet`.

Entry points
------------
fetch_pass_meta(force_refresh=False)   -> pass_meta_cache.parquet
fetch_frames360(force_refresh=False)   -> frames360_cache.parquet
build_corpus(force_refresh=False)      -> dq_corpus.csv (slim CSV)
load_corpus_with_frames()              -> CSV + frames re-attached
"""
from __future__ import annotations

import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from . import config as cfg


# Silence the "credentials were not supplied" notice from statsbombpy:
warnings.filterwarnings("ignore", message="credentials were not supplied")


# =============================================================================
# StatsBomb pass metadata fetch (height, body_part, detailed outcome)
# =============================================================================
def fetch_pass_meta(force_refresh: bool = False) -> pd.DataFrame:
    """Re-pull StatsBomb pass metadata for every event in `hull_events_lb.csv`.

    H1 only persisted a binary `pass_successful`. xPass needs the explicit
    `pass_height` (Ground Pass / Low Pass / High Pass) and `pass_body_part`
    (to drop headers). The detailed `pass_outcome` is kept for label audits.
    """
    if cfg.PASS_META_CACHE.exists() and not force_refresh:
        return pd.read_parquet(cfg.PASS_META_CACHE)

    from statsbombpy import sb

    lb = pd.read_csv(cfg.HULL_EVENTS_LB, usecols=["match_id", "event_id"])
    lb["event_id"] = lb["event_id"].astype(str).str.strip()
    target_ids = set(lb["event_id"])

    rows: list[pd.DataFrame] = []
    matches = sorted(lb["match_id"].unique())
    t0 = time.time()
    for i, match_id in enumerate(matches, 1):
        try:
            ev = sb.events(match_id=match_id)
        except Exception as e:
            print(f"  match {match_id}: SKIP ({e})")
            continue
        ev = ev[ev["type"] == "Pass"].copy()
        if ev.empty:
            continue
        ev["id"] = ev["id"].astype(str).str.strip()
        ev = ev[ev["id"].isin(target_ids)]
        if ev.empty:
            continue
        cols = {
            "id":             "event_id",
            "pass_height":    "pass_height",
            "pass_outcome":   "pass_outcome",
            "pass_body_part": "pass_body_part",
            "pass_technique": "pass_technique",
        }
        for src in cols:
            if src not in ev.columns:
                ev[src] = np.nan
        rows.append(ev[list(cols)].rename(columns=cols))
        if i % 10 == 0 or i == len(matches):
            print(f"  pass meta [{i}/{len(matches)}]  elapsed {time.time()-t0:.1f}s")

    out = (pd.concat(rows, ignore_index=True) if rows
           else pd.DataFrame(columns=["event_id", "pass_height", "pass_outcome",
                                      "pass_body_part", "pass_technique"]))
    out["event_id"] = out["event_id"].astype(str).str.strip()
    out.to_parquet(cfg.PASS_META_CACHE, index=False)
    print(f"  saved: {cfg.PASS_META_CACHE}  ({len(out):,} rows)")
    return out


# =============================================================================
# StatsBomb 360 frames fetch (teammates + opponents in pitch meters)
# =============================================================================
def fetch_frames360(force_refresh: bool = False) -> pd.DataFrame:
    """Re-pull StatsBomb 360 freeze-frames for every event in the H1 corpus.

    Returns one row per event with two columns of (x, y) tuples in meters:
    `teammates` (excluding the actor) and `opponents`. The actor's location
    is the sender start position already stored in `hull_events_lb.csv`.
    """
    if cfg.FRAMES360_CACHE.exists() and not force_refresh:
        return pd.read_parquet(cfg.FRAMES360_CACHE)

    from statsbombpy import sb

    lb = pd.read_csv(cfg.HULL_EVENTS_LB, usecols=["match_id", "event_id"])
    lb["event_id"] = lb["event_id"].astype(str).str.strip()
    target_ids = set(lb["event_id"])

    rows: list[dict] = []
    matches = sorted(lb["match_id"].unique())
    t0 = time.time()
    for i, match_id in enumerate(matches, 1):
        try:
            fr = sb.frames(match_id=match_id)
        except Exception as e:
            print(f"  match {match_id}: SKIP ({e})")
            continue
        if fr is None or fr.empty:
            continue
        col_id = next((c for c in ("event_uuid", "id", "event_id") if c in fr.columns), None)
        if col_id is None or "teammate" not in fr.columns or "location" not in fr.columns:
            continue
        fr[col_id] = fr[col_id].astype(str).str.strip()
        fr = fr[fr[col_id].isin(target_ids)]
        if fr.empty:
            continue
        actor_col = "actor" if "actor" in fr.columns else None
        for ev_id, grp in fr.groupby(col_id):
            if actor_col is not None:
                grp = grp[~grp[actor_col].fillna(False).astype(bool)]
            tm  = grp[grp["teammate"] == True]
            opp = grp[grp["teammate"] == False]
            tm_xy  = [(float(loc[0]) * cfg.X_SCALE, float(loc[1]) * cfg.Y_SCALE)
                      for loc in tm["location"]  if isinstance(loc, list)]
            opp_xy = [(float(loc[0]) * cfg.X_SCALE, float(loc[1]) * cfg.Y_SCALE)
                      for loc in opp["location"] if isinstance(loc, list)]
            rows.append({"event_id": ev_id, "teammates": tm_xy, "opponents": opp_xy})
        if i % 10 == 0 or i == len(matches):
            print(f"  frames360 [{i}/{len(matches)}]  elapsed {time.time()-t0:.1f}s")

    out = pd.DataFrame(rows)
    out["event_id"] = out["event_id"].astype(str).str.strip()
    out.to_parquet(cfg.FRAMES360_CACHE, index=False)
    print(f"  saved: {cfg.FRAMES360_CACHE}  ({len(out):,} rows)")
    return out


# =============================================================================
# Helpers
# =============================================================================
def _xpass_label(outcome) -> int:
    """Label = 1 if the pass was completed, 0 otherwise.

    StatsBomb encodes a completed pass with `pass.outcome == NaN`; any other
    value (Incomplete, Out, Pass Offside, Unknown, Injury Clearance) means
    the pass did not reach a teammate of the sender.
    """
    return int(pd.isna(outcome) or str(outcome).strip().lower() == "complete")


def _to_xy_array(points) -> np.ndarray:
    """Convert any iterable of (x, y) into a clean (N, 2) float array.

    Robust to:
      * None or NaN scalar  -> empty (0, 2)
      * empty list / array  -> empty (0, 2)
      * lists of tuples     -> reshaped (N, 2)
      * numpy object arrays from parquet round-trip -> reshaped (N, 2)
    """
    if points is None:
        return np.empty((0, 2))
    if isinstance(points, float) and np.isnan(points):
        return np.empty((0, 2))
    if hasattr(points, "__len__") and len(points) == 0:
        return np.empty((0, 2))
    return np.asarray([[float(p[0]), float(p[1])] for p in points], dtype=float).reshape(-1, 2)


def _min_dist(point_xy, others) -> float:
    arr = _to_xy_array(others)
    if arr.shape[0] == 0:
        return np.nan
    return float(np.linalg.norm(arr - np.asarray(point_xy, dtype=float), axis=1).min())


# =============================================================================
# Corpus assembly
# =============================================================================
def build_corpus(force_refresh: bool = False) -> pd.DataFrame:
    """Build the H2 working table and persist it to `dq_corpus.csv`.

    Steps
    -----
    1. Load `hull_events_lb.csv` (H1).
    2. Merge `pass_meta_cache` (pass_height, body_part, detailed outcome).
    3. Merge `frames360_cache` (teammates + opponents in meters).
    4. Apply exclusions:
         (a) headers (body_part == 'Head')
         (b) pass-into-space (no in-frame teammate within PASS_INTO_SPACE_M
             of pass.end_location)
         (c) events without a usable 360 frame
    5. Compute the xPass label and the chosen-receiver index in the frame.
    """
    print("Loading H1 corpus")
    lb = pd.read_csv(cfg.HULL_EVENTS_LB)
    lb["event_id"] = lb["event_id"].astype(str).str.strip()
    print(f"  rows                  : {len(lb):,}")

    print("Pass metadata")
    meta = fetch_pass_meta(force_refresh=force_refresh)
    df = lb.merge(meta, on="event_id", how="left")

    print("360 frames (teammates + opponents)")
    frames = fetch_frames360(force_refresh=force_refresh)
    df = df.merge(frames, on="event_id", how="left")

    print("Filtering exclusions")
    n_initial = len(df)

    is_header = df["pass_body_part"].fillna("").isin(cfg.EXCLUDE_BODY_PARTS)
    df = df[~is_header].copy()
    print(f"  headers removed       : {is_header.sum():,}")

    if cfg.EXCLUDE_GK_SENDERS:
        is_gk = df["position"] == "Goalkeeper"
        df = df[~is_gk].copy()
        print(f"  GK senders removed    : {is_gk.sum():,}")

    has_frame = df["teammates"].apply(
        lambda v: isinstance(v, (list, np.ndarray)) and len(v) > 0)
    n_no_frame = (~has_frame).sum()
    df = df[has_frame].copy()

    pis = df.apply(
        lambda r: _min_dist((r["end_x_m"], r["end_y_m"]), r["teammates"]) > cfg.PASS_INTO_SPACE_M,
        axis=1,
    )
    pis = pis.fillna(True)
    n_pis = int(pis.sum())
    df = df[~pis].copy()
    print(f"  pass-into-space (>{cfg.PASS_INTO_SPACE_M:.0f}m): {n_pis:,}")
    print(f"  no-frame removed      : {n_no_frame:,}")
    print(f"  retained              : {len(df):,} / {n_initial:,} ({len(df) / n_initial:.1%})")

    df["pass_complete"] = df["pass_outcome"].apply(_xpass_label).astype(int)

    def _chosen_idx(row):
        arr = _to_xy_array(row["teammates"])
        if arr.shape[0] == 0:
            return -1
        d = np.linalg.norm(arr - np.array([row["end_x_m"], row["end_y_m"]]), axis=1)
        return int(d.argmin())

    df["chosen_teammate_idx"] = df.apply(_chosen_idx, axis=1)
    df["n_teammates_in_frame"]  = df["teammates"].apply(lambda v: len(_to_xy_array(v)))
    df["n_opponents_in_frame"]  = df["opponents"].apply(lambda v: len(_to_xy_array(v)))

    slim_cols = [c for c in df.columns if c not in ("teammates", "opponents")]
    df[slim_cols].to_csv(cfg.DQ_CORPUS_PATH, index=False)
    print(f"Saved corpus            : {cfg.DQ_CORPUS_PATH}  ({len(df):,} rows)")
    return df


def load_corpus_with_frames() -> pd.DataFrame:
    """Reload `dq_corpus.csv` and re-attach `teammates` / `opponents`.

    Arrays are normalised once here to clean (N, 2) float ndarrays — every
    downstream consumer (features, viz, compare) can then assume a single
    well-formed shape and skip ad-hoc defensive coercion.

    Also computes `chosen_teammate_dist_m` on the fly: the distance from the
    chosen teammate's t₀ position to `pass.end_location`. This is a key
    diagnostic for the "chosen-receiver selection" data-leakage check —
    completed passes should have small distances (the receiver was where
    the ball ended up); failed passes with large distances signal that the
    closest-teammate heuristic likely picked the wrong intended target.
    """
    if not Path(cfg.DQ_CORPUS_PATH).exists():
        raise FileNotFoundError(
            f"{cfg.DQ_CORPUS_PATH} not found — run build_corpus() first.")
    df = pd.read_csv(cfg.DQ_CORPUS_PATH)
    df["event_id"] = df["event_id"].astype(str).str.strip()
    frames = pd.read_parquet(cfg.FRAMES360_CACHE)
    frames["event_id"] = frames["event_id"].astype(str).str.strip()
    merged = df.merge(frames, on="event_id", how="left")
    merged["teammates"] = merged["teammates"].apply(_to_xy_array)
    merged["opponents"] = merged["opponents"].apply(_to_xy_array)

    def _chosen_dist(row) -> float:
        tm = row["teammates"]
        idx = int(row.get("chosen_teammate_idx", -1))
        if idx < 0 or tm.shape[0] == 0 or idx >= tm.shape[0]:
            return float("nan")
        return float(np.linalg.norm(
            tm[idx] - np.array([row["end_x_m"], row["end_y_m"]])))

    merged["chosen_teammate_dist_m"] = merged.apply(_chosen_dist, axis=1)
    return merged


if __name__ == "__main__":
    build_corpus()
