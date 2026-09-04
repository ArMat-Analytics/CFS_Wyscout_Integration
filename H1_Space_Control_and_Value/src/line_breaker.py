"""Line Breaker pipeline.

Tags every open-play pass in hull_events_with_epv.csv with three line-breaker
flags and a macro-role.

Definitions:
    is_line_breaker_geom    - successful pass that bypasses >=3 opponents
                              inside a 5 m corridor along the pass line.
    is_line_breaker_epv     - successful pass with epv_added above the
                              role-specific 75th-percentile of positive epv_added.
    is_line_breaker_quality - boolean intersection at event level: geom AND epv
                              (the "clean" line-breakers - bold AND high value).

Output:
    data/hull_events_lb.csv  -  open-play passes with all flags + defenders_bypassed.

The optional plotting block at the bottom of main() draws the first six Kroos
line-breakers as a visual sanity check.
"""
import time
import warnings
from pathlib import Path

import matplotlib.patches as patches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.spatial import ConvexHull
from statsbombpy import sb

from . import config
from .geometry import count_bypassed

warnings.filterwarnings('ignore')


def _normalize_positions(d):
    """Ensure list[tuple[float, float]] (avoids ValueError with numpy arrays)."""
    return {str(k).strip(): [(float(p[0]), float(p[1])) for p in v]
            for k, v in d.items() if v is not None and len(v) > 0}


def _draw_pitch_local(ax):
    ax.set_facecolor('#f0f0f0')
    ax.add_patch(patches.Rectangle((0, 0), 105, 68, color='white', zorder=0))
    ax.plot([0, 105, 105, 0, 0], [0, 0, 68, 68, 0], color="black", lw=1.5)
    ax.plot([52.5, 52.5], [0, 68], color="black", lw=1.5)
    ax.add_patch(patches.Rectangle((0,    13.84),    16.5, 40.32, fill=False, color="black", lw=1.2))
    ax.add_patch(patches.Rectangle((88.5, 13.84),    16.5, 40.32, fill=False, color="black", lw=1.2))
    ax.add_patch(patches.Circle((52.5, 34), 9.15, fill=False, color="black", lw=1.2))
    ax.set_aspect('equal'); ax.set_xticks([]); ax.set_yticks([])


def _plot_lb_example(row, opps, n_count):
    fig, ax = plt.subplots(figsize=(11, 7))
    _draw_pitch_local(ax)
    if opps is not None and len(opps) >= 3:
        pts = np.array(opps, dtype=float)
        try:
            hull = ConvexHull(pts)
            for simplex in hull.simplices:
                ax.plot(pts[simplex, 0], pts[simplex, 1],
                        color='red', lw=2, linestyle='--', zorder=2)
            ax.fill(pts[hull.vertices, 0], pts[hull.vertices, 1],
                    color='red', alpha=0.1, zorder=1)
        except Exception:
            pass
    ax.annotate("", xy=(row['end_x_m'], row['end_y_m']),
                xytext=(row['start_x_m'], row['start_y_m']),
                arrowprops=dict(arrowstyle="->", color="#D4AF37", lw=3,
                                mutation_scale=25),
                zorder=4)
    ax.scatter(row['start_x_m'], row['start_y_m'], color='#00BFFF', s=150,
               edgecolors='black', lw=2, zorder=5)
    if opps is not None and len(opps) > 0:
        pts = np.array(opps, dtype=float)
        ax.scatter(pts[:, 0], pts[:, 1], color='black', s=40,
                   edgecolors='white', zorder=3)
    ax.set_title(
        f"{row['player']} LINE BREAKER #{n_count}   ({row['macro_role']})\n"
        f"Bypassed: {int(row['defenders_bypassed'])}   "
        f"EPV+: {row['epv_added']:.4f}   "
        f"role threshold: {row['epv_threshold_role']:.4f}"
    )
    plt.show()


def show_line_breakers(player_name: str,
                       n: int = 4,
                       kind: str = "quality"):
    """Replay-style plot of a player's line-breakers, loaded from cache.

    Re-uses ``hull_events_lb.csv`` and ``opp_positions_cache.parquet`` produced
    by :func:`main`, so no StatsBomb re-fetch is needed: the call returns in
    under a second on a typical laptop.

    Each panel shows:

    * the **opponent convex hull** (red dashed polygon, light fill) at the
      moment of the pass, drawn from the 360 freeze frame;
    * the **passer's location** (cyan dot) and the **pass vector**
      (gold arrow);
    * every **opponent in the frame** (black dot);
    * a **header line** with the role-specific EPV threshold, the actual
      EPV added, and how many defenders the pass bypassed inside the 5 m
      corridor.

    This is the visual proof that the line-breaker definition is doing
    what it says: a "quality" line-breaker is simultaneously bold (≥ 3
    opponents bypassed inside a 5 m corridor) and threat-positive (EPV
    added above the role's 75th percentile).

    Parameters
    ----------
    player_name : str
        Substring match (case-insensitive) on the StatsBomb ``player``
        column of ``hull_events_lb.csv``.
    n : int, default 4
        Maximum number of examples to plot.
    kind : {"quality", "geom", "epv"}, default "quality"
        Which line-breaker flag to filter on. ``"quality"`` is the
        intersection (geom AND EPV) and is the recommended view for
        H1 illustration; ``"geom"`` shows raw bold passes (some of
        which lack value); ``"epv"`` shows high-EPV passes (some of
        which are not geometrically bold).
    """
    flag_col = {
        "quality": "is_line_breaker_quality",
        "geom"   : "is_line_breaker_geom",
        "epv"    : "is_line_breaker_epv",
    }.get(kind)
    if flag_col is None:
        raise ValueError(f"kind must be one of: quality, geom, epv (got {kind!r})")

    df = pd.read_csv(config.HULL_EVENTS_LB)
    df["event_id"] = df["event_id"].astype(str).str.strip()
    sub = df[df["player"].str.contains(player_name, na=False, case=False)
             & (df[flag_col] == True)]
    if sub.empty:
        print(f"No '{kind}' line-breakers found for '{player_name}'.")
        print(f"  Hint: total events for that player = "
              f"{(df['player'].str.contains(player_name, na=False, case=False)).sum()}")
        return
    sub = sub.head(n)

    if not Path(config.OPP_POSITIONS_CACHE).exists():
        print(f"Missing cache: {config.OPP_POSITIONS_CACHE}")
        print("  Run line_breaker.main() once to populate it.")
        return
    opp_df = pd.read_parquet(config.OPP_POSITIONS_CACHE)
    opp_df["event_id"] = opp_df["event_id"].astype(str).str.strip()
    opp_positions = _normalize_positions(
        {row["event_id"]: row["positions"] for _, row in opp_df.iterrows()})

    print(f"Plotting {len(sub)} '{kind}' line-breaker(s) for "
          f"{sub['player'].iloc[0]}  ({sub['team'].iloc[0]})  "
          f"role={sub['macro_role'].iloc[0]}")
    for i, (_, r) in enumerate(sub.iterrows(), 1):
        _plot_lb_example(r, opp_positions.get(str(r["event_id"]), []), i)


def main(plot_examples: bool = True):
    # --- STEP 1: Load & clean ------------------------------------------------
    print("\nSTEP 1 - Loading and cleaning data...")
    df = pd.read_csv(config.HULL_EVENTS_EPV)
    df['event_id']   = df['event_id'].astype(str).str.strip()
    df['macro_role'] = df['position'].apply(config.map_role)
    print(f"  Events: {len(df):,}   roles: {df['macro_role'].value_counts().to_dict()}")

    # --- STEP 2: Download/load 360 frames (with cache) ----------------------
    print("\nSTEP 2 - Downloading/loading 360 frames...")
    if Path(config.OPP_POSITIONS_CACHE).exists():
        df_opp = pd.read_parquet(config.OPP_POSITIONS_CACHE)
        opp_positions = {row['event_id']: row['positions']
                         for _, row in df_opp.iterrows()}
    else:
        opp_positions = {}
        unique_matches = df['match_id'].unique()
        t0 = time.time()
        for i, match_id in enumerate(unique_matches, 1):
            try:
                df_frames = sb.frames(match_id=match_id)
                if df_frames is None or df_frames.empty:
                    continue
                col_id = next((c for c in ['event_uuid', 'id', 'event_id']
                               if c in df_frames.columns), None)
                if not col_id:
                    continue
                df_frames[col_id] = df_frames[col_id].astype(str).str.strip()
                if 'teammate' not in df_frames.columns:
                    continue
                for ev_id, grp in df_frames.groupby(col_id):
                    opps = grp[grp['teammate'] == False]
                    coords = [(loc[0] * config.X_SCALE, loc[1] * config.Y_SCALE)
                              for loc in opps['location'] if isinstance(loc, list)]
                    if len(coords) > 0:
                        opp_positions[ev_id] = coords
            except Exception as e:
                print(f"  match {match_id}: SKIP ({e})")
            if i % 10 == 0 or i == len(unique_matches):
                print(f"  [{i}/{len(unique_matches)}]  elapsed {time.time()-t0:.1f}s")
        (pd.DataFrame([{'event_id': k, 'positions': v}
                       for k, v in opp_positions.items()])
           .to_parquet(config.OPP_POSITIONS_CACHE, index=False))

    # Normalize ONCE: list[tuple[float, float]] for every event
    opp_positions = _normalize_positions(opp_positions)
    print(f"  Events with 360 frame: {len(opp_positions):,}")

    # --- STEP 3: Count bypassed defenders (5 m corridor) -------------------
    print("\nSTEP 3 - Geometric computation of defenders_bypassed...")
    df['defenders_bypassed'] = df.apply(
        lambda r: count_bypassed(
            r['start_x_m'], r['start_y_m'], r['end_x_m'], r['end_y_m'],
            opp_positions.get(str(r['event_id']))),
        axis=1,
    )

    # --- STEP 4: Role-aware EPV thresholds (75th percentile by role) -------
    print("\nSTEP 4 - Computing role-aware EPV thresholds...")
    is_success = (df['pass_successful'] == True)
    pos_mask   = is_success & (df['epv_added'] > 0)
    role_thr   = (df.loc[pos_mask]
                    .groupby('macro_role')['epv_added']
                    .quantile(0.75)
                    .to_dict())
    global_thr = df.loc[pos_mask, 'epv_added'].quantile(0.75)
    print("  Per-role thresholds (75th pct.):")
    for r, t in sorted(role_thr.items()):
        print(f"    {r:6s}  {t:.4f}")
    print(f"  Global fallback: {global_thr:.4f}")
    df['epv_threshold_role'] = df['macro_role'].map(role_thr).fillna(global_thr)

    # --- STEP 5: Line-breaker flags ----------------------------------------
    df['is_line_breaker_epv']     = is_success & (df['epv_added'] >= df['epv_threshold_role'])
    df['is_line_breaker_geom']    = is_success & (df['defenders_bypassed'] >= config.BYPASS_THRESHOLD)
    df['is_line_breaker_quality'] = df['is_line_breaker_geom'] & df['is_line_breaker_epv']
    df['is_line_breaker']         = df['is_line_breaker_geom']   # main definition

    # --- STEP 6: Report ----------------------------------------------------
    print("\n" + "=" * 52)
    print(" LINE BREAKER REPORT (Open Play, successful passes)")
    print("=" * 52)
    print(f"  total events                       : {len(df):,}")
    print(f"  line breakers (geom, DEFINITION)   : {df['is_line_breaker_geom'].sum():,}")
    print(f"  | quality (geom + EPV above thr.)  : {df['is_line_breaker_quality'].sum():,}")
    print(f"  EPV signal (standalone)            : {df['is_line_breaker_epv'].sum():,}")
    quality_rate = (df['is_line_breaker_quality'].sum() /
                    max(df['is_line_breaker_geom'].sum(), 1) * 100)
    print(f"  quality rate (quality/geom)        : {quality_rate:.1f}%")

    # --- STEP 7: Save ------------------------------------------------------
    df.to_csv(config.HULL_EVENTS_LB, index=False)
    print(f"\nSaved: {config.HULL_EVENTS_LB}")

    # --- STEP 8 (optional): Kroos visualisation ----------------------------
    if plot_examples:
        kroos_events = df[df['player'].str.contains("Kroos", na=False)
                          & df['is_line_breaker']].head(6)
        for i, (_, r) in enumerate(kroos_events.iterrows(), 1):
            _plot_lb_example(r, opp_positions.get(str(r['event_id']), []), i)

    return df


if __name__ == "__main__":
    main()
