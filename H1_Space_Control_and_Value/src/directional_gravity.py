"""Directional Gravity — extension of hull_metrics_aggregated.csv.

The composite gravity (hull + proximity) measures HOW COMPACT the defense
is when the player has the ball. Directional gravity measures WHETHER it
shifts toward the player.

Adds two columns to hull_metrics_aggregated.csv:
    gravity_directional_m  - signed displacement (m) of opponent centroid
                             towards the player, vs. the LOO baseline at the
                             same (match, zone). Positive => defenders
                             collapse onto the player.
    gravity_directional_n  - number of events with a usable LOO baseline.

Opponent centroids are cached on disk so re-runs are cheap.
"""
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from statsbombpy import sb

from . import config

warnings.filterwarnings('ignore')

MIN_BASELINE_N = 5
ZONES_X, ZONES_Y = config.ZONE_X_BINS, config.ZONE_Y_BINS


def main():
    # --- STEP 1: load events --------------------------------------------
    df_hull = pd.read_csv(config.HULL_EVENTS_RAW)
    df_hull['event_id'] = df_hull['event_id'].astype(str).str.strip()
    unique_matches = df_hull['match_id'].unique()
    print(f"Hull events: {len(df_hull):,}   Matches: {len(unique_matches)}")

    # --- STEP 2: opponent centroid per event (with on-disk cache) -------
    if Path(config.OPP_CENTROIDS_CACHE).exists():
        print(f"Loading cached centroids -> {config.OPP_CENTROIDS_CACHE}")
        df_cent = pd.read_parquet(config.OPP_CENTROIDS_CACHE)
    else:
        print("Downloading 360 frames and computing opponent centroids...")
        records, t0 = [], time.time()
        for i, mid in enumerate(unique_matches, 1):
            try:
                df_fr = sb.frames(match_id=mid)
                if df_fr is None or df_fr.empty:
                    continue
                col_id = next((c for c in ['event_uuid', 'id', 'event_id']
                               if c in df_fr.columns), None)
                if col_id is None:
                    continue
                df_fr[col_id] = df_fr[col_id].astype(str).str.strip()
                if 'teammate' not in df_fr.columns:
                    continue
                for ev_id, grp in df_fr.groupby(col_id):
                    opps = grp[grp['teammate'] == False]
                    locs = [loc for loc in opps['location'] if isinstance(loc, list)]
                    if len(locs) < 3:
                        continue
                    arr = np.array(locs, dtype=float)
                    records.append({
                        'match_id':       mid,
                        'event_id':       ev_id,
                        'opp_centroid_x': float(arr[:, 0].mean() * config.X_SCALE),
                        'opp_centroid_y': float(arr[:, 1].mean() * config.Y_SCALE),
                        'n_opp':          len(locs),
                    })
            except Exception as e:
                print(f"  match {mid}: SKIP ({e})")
            if i % 10 == 0 or i == len(unique_matches):
                print(f"  [{i}/{len(unique_matches)}]  elapsed {time.time()-t0:.1f}s")
        df_cent = pd.DataFrame(records)
        df_cent.to_parquet(config.OPP_CENTROIDS_CACHE, index=False)
        print(f"Cached -> {config.OPP_CENTROIDS_CACHE}")

    # --- STEP 3: join centroids + zone centers (meters) -----------------
    df = df_hull.merge(
        df_cent[['match_id', 'event_id', 'opp_centroid_x', 'opp_centroid_y']],
        on=['match_id', 'event_id'], how='left',
    )

    df['zone_cx_m'] = (df['player_zone_x'] + 0.5) * (config.PITCH_LENGTH_M / ZONES_X)
    df['zone_cy_m'] = (df['player_zone_y'] + 0.5) * (config.PITCH_WIDTH_M  / ZONES_Y)

    # --- STEP 4: baseline centroid per (match, zone) with LOO on the player
    bkey = ['match_id', 'player_zone_x', 'player_zone_y']
    pkey = bkey + ['player']

    g_b = df.groupby(bkey)
    df['_bsum_x'] = g_b['opp_centroid_x'].transform('sum')
    df['_bsum_y'] = g_b['opp_centroid_y'].transform('sum')
    df['_bcount'] = g_b['opp_centroid_x'].transform('count')

    g_p = df.groupby(pkey)
    df['_psum_x'] = g_p['opp_centroid_x'].transform('sum')
    df['_psum_y'] = g_p['opp_centroid_y'].transform('sum')
    df['_pcount'] = g_p['opp_centroid_x'].transform('count')

    df['_base_n']  = df['_bcount'] - df['_pcount']
    df['_base_cx'] = (df['_bsum_x'] - df['_psum_x']) / df['_base_n'].replace(0, np.nan)
    df['_base_cy'] = (df['_bsum_y'] - df['_psum_y']) / df['_base_n'].replace(0, np.nan)

    # --- STEP 5: directional gravity per event --------------------------
    vx = df['zone_cx_m']      - df['_base_cx']
    vy = df['zone_cy_m']      - df['_base_cy']
    L  = np.sqrt(vx ** 2 + vy ** 2)

    dx = df['opp_centroid_x'] - df['_base_cx']
    dy = df['opp_centroid_y'] - df['_base_cy']

    mask = (df['_base_n'] >= MIN_BASELINE_N) & (L > 0.5) & df['opp_centroid_x'].notna()
    df['gravity_dir_m'] = np.where(mask, (dx * vx + dy * vy) / L, np.nan)

    # --- STEP 6: aggregate per player -----------------------------------
    agg = (df.dropna(subset=['gravity_dir_m'])
             .groupby(['player', 'team'])['gravity_dir_m']
             .agg(gravity_directional_m='mean',
                  gravity_directional_n='count')
             .reset_index())

    # --- STEP 7: merge into hull_metrics_aggregated.csv (re-run safe) ---
    df_agg = pd.read_csv(config.HULL_METRICS_AGG)
    for c in ['gravity_directional_m', 'gravity_directional_n']:
        if c in df_agg.columns:
            df_agg = df_agg.drop(columns=[c])
    df_agg = df_agg.merge(agg, on=['player', 'team'], how='left')
    df_agg.to_csv(config.HULL_METRICS_AGG, index=False)

    print(f"\nDONE. gravity_directional_m added to: {config.HULL_METRICS_AGG}")
    cols_show = ['player', 'team', 'minutes_played', 'gravity_composite_pct',
                 'gravity_directional_m', 'gravity_directional_n']
    print("\nTop 10 by gravity_directional_m (min 100 baseline events):")
    print(df_agg.query('gravity_directional_n >= 100')
                 .sort_values('gravity_directional_m', ascending=False)[cols_show]
                 .head(10).to_string(index=False))
    return df_agg


if __name__ == "__main__":
    main()
