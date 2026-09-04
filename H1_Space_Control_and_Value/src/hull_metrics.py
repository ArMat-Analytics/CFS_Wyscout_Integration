"""Hull Metrics Pipeline — Euro 2024.

Core spatial pipeline. For every Pass with a 360 freeze frame, computes
geometric features over the convex hull of visible opponents and aggregates
them per player.

Outputs:
    data/hull_events_raw.csv         - one row per analysed pass
    data/hull_zone_baselines.csv     - tournament-level zonal baseline
    data/hull_metrics_aggregated.csv - one row per player

Metrics produced (rates in %, with n = sample size):
    M1. Between Lines %             - how often the player sits between the lines
    M2. Pressure Resistance %       - completion under pressure (>=2 opp within 2.5m)
    M3. Successful Hull Exit %      - clean ball-exits from inside the block
    M4. Successful Hull Penetration - passes from outside the block ending inside
    M5. Defensive Gravity (LOO)     - hull / proximity / composite signals
    Per-90 volumes for between-lines, hull exits, hull penetrations.

Gravity is computed in **leave-one-out** mode (the baseline excludes the
player's own passes), with a match-level baseline preferred and a
tournament-level fallback when the match-level has too few frames.
"""
import time
import warnings

import numpy as np
import pandas as pd
from scipy.spatial import ConvexHull
from statsbombpy import sb

from . import config
from .geometry import (
    to_meters,
    is_inside_hull,
    hull_area,
    count_opponents_within,
    mean_dist_k_nearest,
    get_zone,
)

warnings.filterwarnings('ignore')


def main():
    # =========================================================================
    # STEP 0 - Load player list from totals file
    # =========================================================================
    print("=" * 72)
    print("STEP 0 - Loading player list from totals file")
    print("=" * 72)

    df_totals = pd.read_excel(config.TOTALS_XLSX)
    if config.MIN_MINUTES > 0:
        df_totals = df_totals[df_totals['minutes_played'] >= config.MIN_MINUTES]

    target_players = df_totals['player'].dropna().unique().tolist()
    target_set     = set(target_players)
    minutes_lookup = dict(zip(df_totals['player'], df_totals['minutes_played']))
    roles_lookup   = (dict(zip(df_totals['player'], df_totals['primary_role']))
                      if 'primary_role' in df_totals.columns else {})
    teams_lookup   = (dict(zip(df_totals['player'], df_totals['team']))
                      if 'team' in df_totals.columns else {})

    print(f"Target players: {len(target_players)}  (MIN_MINUTES={config.MIN_MINUTES})")

    # =========================================================================
    # STEP 1 - Fetch match list for Euro 2024
    # =========================================================================
    print("\n" + "=" * 72)
    print("STEP 1 - Fetching Euro 2024 match list")
    print("=" * 72)

    matches   = sb.matches(competition_id=config.COMPETITION_ID,
                           season_id=config.SEASON_ID)
    match_ids = matches['match_id'].tolist()
    print(f"Matches to process: {len(match_ids)}")

    # =========================================================================
    # STEP 2 - Loop over matches: baseline (per pass) + features (target players)
    # =========================================================================
    # Baseline rows (one per Pass with a freeze frame):
    #   match_id, team_in_possession, passer, zone_x, zone_y,
    #   norm_hull_area, dist_k_nearest, n_opp
    #   -> the `passer` field enables leave-one-out at gravity time
    #
    # Event rows (one per pass by a target player with a freeze frame):
    #   hull features + topology (player_between_lines, end_inside_hull) +
    #   pressure + zone (for the join with the baseline)
    # =========================================================================
    print("\n" + "=" * 72)
    print("STEP 2 - Processing matches (events + 360 frames)")
    print("=" * 72)

    all_events_rows      = []
    all_baseline_rows    = []
    total_passes_counter = {}

    t0 = time.time()
    for i, match_id in enumerate(match_ids, 1):
        try:
            df_ev = sb.events(match_id=match_id)
            df_f  = sb.frames(match_id=match_id)
        except Exception as e:
            print(f"  [{i}/{len(match_ids)}] match {match_id}: SKIP ({e})")
            continue

        players_in_match = set(df_ev['player'].dropna().unique())
        targets_here     = target_set & players_in_match
        if not targets_here:
            continue

        # Pre-index freeze frames by event_id
        frames_by_id = ({eid: grp for eid, grp in df_f.groupby('id')}
                        if 'id' in df_f.columns and len(df_f) > 0 else {})

        # All Pass events (for the baseline) - keep passer for leave-one-out
        passes_all = df_ev[df_ev['type'] == 'Pass'][
            ['id', 'team', 'location', 'player']
        ].dropna(subset=['location', 'player'])

        # --- (a) Baseline: one row per Pass with freeze frame --------------
        for _, pr in passes_all.iterrows():
            eid    = pr['id']
            team   = pr['team']
            passer = pr['player']
            frame  = frames_by_id.get(eid)
            if frame is None or len(frame) == 0:
                continue
            opps = frame[frame['teammate'] == False]
            if len(opps) < 3:
                continue
            ball_m   = to_meters(pr['location'])
            opp_list = [to_meters(loc) for loc in opps['location'].tolist()]
            opp_m    = np.array([p for p in opp_list if p is not None])
            if len(opp_m) < 3:
                continue

            n_opp = len(opp_m)
            a     = hull_area(opp_m)
            d_k   = mean_dist_k_nearest(ball_m, opp_m, k=config.K_NEAREST)
            if np.isnan(a) or np.isnan(d_k):
                continue
            zone = get_zone(ball_m)
            if zone is None:
                continue

            all_baseline_rows.append({
                'match_id':           match_id,
                'team_in_possession': team,
                'passer':             passer,              # <- for LOO
                'ball_zone_x':        zone[0],
                'ball_zone_y':        zone[1],
                'norm_hull_area':     a / n_opp,           # m^2 per opponent
                'dist_k_nearest':     d_k,                  # m, mean of K nearest
                'n_opp':              n_opp,
            })

        # --- (b) + (c) Feature extraction for target players --------------
        passes_target = df_ev[
            (df_ev['type'] == 'Pass') & (df_ev['player'].isin(targets_here))
        ]

        # (c) Total pass count (denominator for coverage)
        for player, n in passes_target['player'].value_counts().items():
            total_passes_counter[player] = total_passes_counter.get(player, 0) + int(n)

        # (b) Feature extraction for passes with a freeze frame
        for _, row in passes_target.iterrows():
            ev_id = row['id']
            frame = frames_by_id.get(ev_id)
            if frame is None or len(frame) == 0:
                continue
            actor_row = frame[frame['actor'] == True]
            opps_rows = frame[frame['teammate'] == False]
            if len(actor_row) == 0 or len(opps_rows) < 3:
                continue

            player_pos = to_meters(actor_row.iloc[0]['location'])
            opp_list   = [to_meters(loc) for loc in opps_rows['location'].tolist()]
            opp_coords = np.array([p for p in opp_list if p is not None])
            end_point  = to_meters(row['pass_end_location'])
            if player_pos is None or end_point is None or len(opp_coords) < 3:
                continue

            try:
                _ = ConvexHull(opp_coords)
            except Exception:
                continue

            n_opp         = len(opp_coords)
            h_area        = hull_area(opp_coords)
            norm_hull     = h_area / n_opp if (not np.isnan(h_area) and n_opp > 0) else np.nan
            d_k           = mean_dist_k_nearest(player_pos, opp_coords, k=config.K_NEAREST)
            player_inside = is_inside_hull(opp_coords, player_pos)
            end_inside    = is_inside_hull(opp_coords, end_point)
            n_close       = count_opponents_within(player_pos, opp_coords,
                                                   radius=config.PRESSURE_RADIUS)
            player_zone   = get_zone(player_pos)

            all_events_rows.append({
                'match_id':              match_id,
                'event_id':              ev_id,
                'player':                row['player'],
                'team':                  row['team'],
                'minute':                row['minute'],
                'second':                row['second'],
                'position':              row.get('position', np.nan),
                # Hull metrics
                'hull_area_m2':          h_area,
                'n_opponents_in_frame':  n_opp,
                'norm_hull_area_m2':     norm_hull,          # key for Gravity
                'mean_dist_k_nearest':   d_k,                # key for Gravity
                # Hull topology
                'player_between_lines':  player_inside,
                'end_inside_hull':       end_inside,
                # Pressure
                'n_close_opp':           n_close,
                'under_pressure':        n_close >= config.PRESSURE_MIN,
                'pass_successful':       pd.isna(row['pass_outcome']),
                # Zone (for join with baseline)
                'player_zone_x':         player_zone[0] if player_zone else np.nan,
                'player_zone_y':         player_zone[1] if player_zone else np.nan,
            })

        if i % 5 == 0 or i == len(match_ids):
            elapsed = time.time() - t0
            print(f"  [{i}/{len(match_ids)}] matches processed ({elapsed:.0f}s)  "
                  f"pass rows: {len(all_events_rows)}  "
                  f"baseline rows: {len(all_baseline_rows)}")

    print(f"\nTotal pass rows collected (with 360):  {len(all_events_rows)}")
    print(f"Total baseline rows (Pass-only):       {len(all_baseline_rows)}")

    # =========================================================================
    # STEP 3 - Build baselines (match + tournament) with LOO support
    # =========================================================================
    # Strategy:
    #   To support leave-one-out efficiently we store SUMS and COUNTS (not means).
    #   At gravity time we just subtract the player's contributions and recompute
    #   the mean.
    # =========================================================================
    print("\n" + "=" * 72)
    print("STEP 3 - Building baselines and saving CSVs")
    print("=" * 72)

    df_events_raw   = pd.DataFrame(all_events_rows)
    df_baseline_raw = pd.DataFrame(all_baseline_rows)

    # Match-level baseline (sums)
    bl_match = (df_baseline_raw
        .groupby(['match_id', 'team_in_possession', 'ball_zone_x', 'ball_zone_y'])
        .agg(
            sum_hull_m=('norm_hull_area', 'sum'),
            sum_dist_m=('dist_k_nearest', 'sum'),
            n_m=('norm_hull_area', 'count'),
        )
        .reset_index()
    )

    # Tournament-level baseline (sums)
    bl_tourn = (df_baseline_raw
        .groupby(['team_in_possession', 'ball_zone_x', 'ball_zone_y'])
        .agg(
            sum_hull_t=('norm_hull_area', 'sum'),
            sum_dist_t=('dist_k_nearest', 'sum'),
            n_t=('norm_hull_area', 'count'),
        )
        .reset_index()
    )

    # Player contribution at match-level
    pl_match = (df_baseline_raw
        .groupby(['passer', 'match_id', 'team_in_possession',
                  'ball_zone_x', 'ball_zone_y'])
        .agg(
            sum_hull_pm=('norm_hull_area', 'sum'),
            sum_dist_pm=('dist_k_nearest', 'sum'),
            n_pm=('norm_hull_area', 'count'),
        )
        .reset_index()
    )

    # Player contribution at tournament-level
    pl_tourn = (df_baseline_raw
        .groupby(['passer', 'team_in_possession',
                  'ball_zone_x', 'ball_zone_y'])
        .agg(
            sum_hull_pt=('norm_hull_area', 'sum'),
            sum_dist_pt=('dist_k_nearest', 'sum'),
            n_pt=('norm_hull_area', 'count'),
        )
        .reset_index()
    )

    # Dict lookups for O(1) access in compute_gravity_v4
    bl_match_dict = {
        (r['match_id'], r['team_in_possession'], int(r['ball_zone_x']), int(r['ball_zone_y'])):
        (float(r['sum_hull_m']), float(r['sum_dist_m']), int(r['n_m']))
        for _, r in bl_match.iterrows()
    }
    bl_tourn_dict = {
        (r['team_in_possession'], int(r['ball_zone_x']), int(r['ball_zone_y'])):
        (float(r['sum_hull_t']), float(r['sum_dist_t']), int(r['n_t']))
        for _, r in bl_tourn.iterrows()
    }
    pl_match_dict = {
        (r['passer'], r['match_id'], r['team_in_possession'],
         int(r['ball_zone_x']), int(r['ball_zone_y'])):
        (float(r['sum_hull_pm']), float(r['sum_dist_pm']), int(r['n_pm']))
        for _, r in pl_match.iterrows()
    }
    pl_tourn_dict = {
        (r['passer'], r['team_in_possession'],
         int(r['ball_zone_x']), int(r['ball_zone_y'])):
        (float(r['sum_hull_pt']), float(r['sum_dist_pt']), int(r['n_pt']))
        for _, r in pl_tourn.iterrows()
    }

    # Save CSVs
    df_events_raw.to_csv(config.HULL_EVENTS_RAW, index=False)

    # Save a tournament-level baseline for transparency (means already computed)
    bl_tourn_save = bl_tourn.copy()
    bl_tourn_save['mean_norm_hull'] = bl_tourn_save['sum_hull_t'] / bl_tourn_save['n_t']
    bl_tourn_save['mean_dist_k']    = bl_tourn_save['sum_dist_t'] / bl_tourn_save['n_t']
    bl_tourn_save = bl_tourn_save[bl_tourn_save['n_t'] >= config.MIN_BASELINE_FRAMES][
        ['team_in_possession', 'ball_zone_x', 'ball_zone_y',
         'mean_norm_hull', 'mean_dist_k', 'n_t']
    ].rename(columns={'n_t': 'n_frames'})
    bl_tourn_save.to_csv(config.HULL_ZONE_BASELINES, index=False)

    print(f"hull_events_raw.csv:       {len(df_events_raw)} rows")
    print(f"hull_zone_baselines.csv:   {len(bl_tourn_save)} team-zone pairs "
          f"(tournament level, n>={config.MIN_BASELINE_FRAMES})")
    print(f"Match-level baseline:      {len(bl_match)} buckets (internal, for LOO)")

    # =========================================================================
    # STEP 4 - Aggregate per player (with Gravity LOO)
    # =========================================================================
    print("\n" + "=" * 72)
    print("STEP 4 - Aggregating metrics per player")
    print("=" * 72)

    def compute_gravity_v4(player_name, player_events):
        """Composite Defensive Gravity (LOO + two-level fallback).

        For every (match, zone) bucket of the player:
          1) Try the match-level baseline, subtracting the player's contributions.
             If remaining frames >= MIN_BASELINE_FRAMES -> use it.
          2) Otherwise try the tournament-level baseline, also LOO.
          3) Otherwise the bucket is dropped.

        Returns:
            (gravity_hull_pct, gravity_proximity_pct, gravity_composite_pct,
             n_passes_used)
        """
        pe = player_events.dropna(subset=['player_zone_x', 'player_zone_y',
                                          'norm_hull_area_m2', 'mean_dist_k_nearest'])
        if pe.empty:
            return np.nan, np.nan, np.nan, 0

        contribs = []
        for (match_id, zx, zy), grp in pe.groupby(['match_id', 'player_zone_x', 'player_zone_y']):
            team = grp['team'].iloc[0]
            zx_i, zy_i = int(zx), int(zy)

            bl_norm_hull = bl_dist_k = None

            # (1) Match-level baseline with LOO
            key_m = (match_id, team, zx_i, zy_i)
            bl_m  = bl_match_dict.get(key_m)
            if bl_m is not None:
                s_hull, s_dist, n = bl_m
                pm = pl_match_dict.get((player_name, match_id, team, zx_i, zy_i))
                if pm is not None:
                    sp_hull, sp_dist, sp_n = pm
                    s_hull -= sp_hull
                    s_dist -= sp_dist
                    n      -= sp_n
                if n >= config.MIN_BASELINE_FRAMES:
                    bl_norm_hull = s_hull / n
                    bl_dist_k    = s_dist / n

            # (2) Tournament-level fallback with LOO
            if bl_norm_hull is None:
                key_t = (team, zx_i, zy_i)
                bl_t  = bl_tourn_dict.get(key_t)
                if bl_t is None:
                    continue
                s_hull, s_dist, n = bl_t
                pt = pl_tourn_dict.get((player_name, team, zx_i, zy_i))
                if pt is not None:
                    sp_hull, sp_dist, sp_n = pt
                    s_hull -= sp_hull
                    s_dist -= sp_dist
                    n      -= sp_n
                if n < config.MIN_BASELINE_FRAMES:
                    continue
                bl_norm_hull = s_hull / n
                bl_dist_k    = s_dist / n

            # Guard
            if bl_norm_hull <= 0 or bl_dist_k <= 0:
                continue

            p_norm_hull = grp['norm_hull_area_m2'].mean()
            p_dist_k    = grp['mean_dist_k_nearest'].mean()
            if pd.isna(p_norm_hull) or pd.isna(p_dist_k):
                continue

            g_hull = (bl_norm_hull - p_norm_hull) / bl_norm_hull * 100
            g_prox = (bl_dist_k    - p_dist_k)    / bl_dist_k    * 100
            g_comp = 0.5 * g_hull + 0.5 * g_prox

            contribs.append({
                'n_passes': len(grp),
                'g_hull':   g_hull,
                'g_prox':   g_prox,
                'g_comp':   g_comp,
            })

        if not contribs:
            return np.nan, np.nan, np.nan, 0

        df_c    = pd.DataFrame(contribs)
        total_n = df_c['n_passes'].sum()
        w       = df_c['n_passes'] / total_n
        return (
            float((df_c['g_hull'] * w).sum()),
            float((df_c['g_prox'] * w).sum()),
            float((df_c['g_comp'] * w).sum()),
            int(total_n),
        )

    events_by_player = (dict(list(df_events_raw.groupby('player')))
                        if len(df_events_raw) else {})
    rows = []
    EMPTY = pd.DataFrame(columns=df_events_raw.columns)

    for player in target_players:
        pe              = events_by_player.get(player, EMPTY)
        passes_analysed = len(pe)
        passes_total    = total_passes_counter.get(player, 0)
        minutes         = minutes_lookup.get(player, np.nan)
        role            = roles_lookup.get(player, np.nan)
        team_from_file  = teams_lookup.get(player, np.nan)

        base = {
            'player':          player,
            'team':            team_from_file,
            'primary_role':    role,
            'minutes_played':  minutes,
            'passes_total':    passes_total,
            'passes_analysed': passes_analysed,
            'coverage_pct':    np.nan,
        }

        if passes_analysed == 0:
            rows.append({**base,
                'between_lines_pct':                  np.nan,
                'between_lines_n':                    0,
                'pressure_resistance_pct':            np.nan,
                'pressure_resistance_n':              0,
                'hull_exit_pct':                      np.nan,
                'hull_exit_n':                        0,
                'hull_penetration_pct':               np.nan,
                'hull_penetration_n':                 0,
                'gravity_hull_pct':                   np.nan,
                'gravity_proximity_pct':              np.nan,
                'gravity_composite_pct':              np.nan,
                'gravity_n':                          0,
                'between_lines_per90':                np.nan,
                'successful_hull_exits_per90':        np.nan,
                'successful_hull_penetrations_per90': np.nan,
            })
            continue

        team     = pe['team'].iloc[0]
        coverage = (passes_analysed / passes_total * 100) if passes_total > 0 else np.nan
        base['team']         = team
        base['coverage_pct'] = coverage

        # M1: Between Lines %
        btw_n  = int(pe['player_between_lines'].sum())
        m1_pct = btw_n / passes_analysed * 100

        # M2: Pressure Resistance % (successful passes under pressure)
        pe_press = pe[pe['under_pressure']]
        m2_n     = len(pe_press)
        m2_pct   = (pe_press['pass_successful'].sum() / m2_n * 100) if m2_n > 0 else np.nan

        # M3: Successful Hull Exit %
        pe_inside = pe[pe['player_between_lines']]
        m3_n      = len(pe_inside)
        m3_pct    = (((~pe_inside['end_inside_hull']) & pe_inside['pass_successful']).sum()
                     / m3_n * 100) if m3_n > 0 else np.nan

        # M4: Successful Hull Penetration %
        pe_outside = pe[~pe['player_between_lines']]
        m4_n       = len(pe_outside)
        m4_pct     = ((pe_outside['end_inside_hull'] & pe_outside['pass_successful']).sum()
                      / m4_n * 100) if m4_n > 0 else np.nan

        # M5: Defensive Gravity composite (LOO + two-level)
        g_hull, g_prox, g_comp, g_n = compute_gravity_v4(player, pe)

        # Per 90 volumes
        if pd.notna(minutes) and minutes > 0:
            per90 = lambda x: x / minutes * 90
            v1 = per90(btw_n)
            v2 = per90(int(((~pe_inside['end_inside_hull']) & pe_inside['pass_successful']).sum()))
            v3 = per90(int((pe_outside['end_inside_hull'] & pe_outside['pass_successful']).sum()))
        else:
            v1 = v2 = v3 = np.nan

        rows.append({**base,
            'between_lines_pct':                  m1_pct,
            'between_lines_n':                    btw_n,
            'pressure_resistance_pct':            m2_pct,
            'pressure_resistance_n':              m2_n,
            'hull_exit_pct':                      m3_pct,
            'hull_exit_n':                        m3_n,
            'hull_penetration_pct':               m4_pct,
            'hull_penetration_n':                 m4_n,
            'gravity_hull_pct':                   g_hull,
            'gravity_proximity_pct':              g_prox,
            'gravity_composite_pct':              g_comp,   # main metric
            'gravity_n':                          g_n,
            'between_lines_per90':                v1,
            'successful_hull_exits_per90':        v2,
            'successful_hull_penetrations_per90': v3,
        })

    df_agg = pd.DataFrame(rows)
    df_agg.to_csv(config.HULL_METRICS_AGG, index=False)
    print(f"\nhull_metrics_aggregated.csv: {len(df_agg)} players")

    # =========================================================================
    # STEP 5 - Summary preview (top 20 per passes_analysed)
    # =========================================================================
    print("\n" + "=" * 72)
    print("STEP 5 - Summary preview (top 20 per passes_analysed)")
    print("=" * 72)

    def fmt_pct(v, n=None, width=13):
        if pd.isna(v):
            return f"{'--':>{width}}"
        s = f"{v:>+6.1f}%" if n is None else f"{v:>5.1f}% (n={n})"
        return s.rjust(width)

    df_preview = df_agg.sort_values('passes_analysed', ascending=False).head(20)

    print(f"\n{'Player':<26} {'Role':<8} {'Min':>4}  "
          f"{'Anal':>5} {'Cov%':>5}  "
          f"{'BtwLin%':>13}  {'Press%':>13}  {'Exit%':>13}  "
          f"{'Pen%':>13}  {'Grav_H':>8}  {'Grav_P':>8}  {'Grav_C':>8}")
    print("-" * 185)
    for _, r in df_preview.iterrows():
        name  = str(r.get('player', ''))[:25]
        role  = str(r.get('primary_role', ''))[:8] if pd.notna(r.get('primary_role')) else ''
        mins  = f"{r['minutes_played']:.0f}" if pd.notna(r.get('minutes_played')) else '--'
        pana  = r.get('passes_analysed', 0)
        cov   = f"{r['coverage_pct']:.0f}" if pd.notna(r.get('coverage_pct')) else '--'
        print(f"{name:<26} {role:<8} {mins:>4}  "
              f"{pana:>5} {cov:>5}  "
              f"{fmt_pct(r.get('between_lines_pct'),       r.get('between_lines_n'))}  "
              f"{fmt_pct(r.get('pressure_resistance_pct'), r.get('pressure_resistance_n'))}  "
              f"{fmt_pct(r.get('hull_exit_pct'),           r.get('hull_exit_n'))}  "
              f"{fmt_pct(r.get('hull_penetration_pct'),    r.get('hull_penetration_n'))}  "
              f"{fmt_pct(r.get('gravity_hull_pct'),      width=8)}  "
              f"{fmt_pct(r.get('gravity_proximity_pct'), width=8)}  "
              f"{fmt_pct(r.get('gravity_composite_pct'), width=8)}")

    print(f"\n\n{'Player':<26} {'BtwLin/90':>12} {'Exits/90':>12} {'Penetr/90':>12}")
    print("-" * 68)
    for _, r in df_preview.iterrows():
        name = str(r.get('player', ''))[:25]
        f90  = lambda x: f"{x:>10.2f}" if pd.notna(x) else f"{'--':>10}"
        print(f"{name:<26} {f90(r.get('between_lines_per90'))}   "
              f"{f90(r.get('successful_hull_exits_per90'))}   "
              f"{f90(r.get('successful_hull_penetrations_per90'))}")

    # =========================================================================
    # STEP 6 - Sanity check on metric distributions
    # =========================================================================
    # Expected ranges (gut check):
    #   between_lines_pct        median ~5-15% (role-dependent)
    #   pressure_resistance%     median ~60-80%
    #   hull_exit_pct            median ~30-50%
    #   hull_penetration_pct     median ~5-15%
    #   gravity_composite_pct    median CLOSE TO ZERO (LOO is centered)
    # =========================================================================
    print("\n" + "=" * 72)
    print("STEP 6 - Sanity check on metric distributions")
    print("=" * 72)

    metric_cols = [
        'between_lines_pct',
        'pressure_resistance_pct',
        'hull_exit_pct',
        'hull_penetration_pct',
        'gravity_hull_pct',
        'gravity_proximity_pct',
        'gravity_composite_pct',
    ]

    print(f"\n{'Metric':<28} {'n_obs':>6} {'mean':>8} {'std':>8} "
          f"{'p5':>8} {'p50':>8} {'p95':>8}")
    print("-" * 82)
    for col in metric_cols:
        s = df_agg[col].dropna()
        if len(s) == 0:
            print(f"{col:<28} {'0':>6} {'--':>8} {'--':>8} {'--':>8} {'--':>8} {'--':>8}")
            continue
        print(f"{col:<28} {len(s):>6} "
              f"{s.mean():>+8.2f} {s.std():>8.2f} "
              f"{s.quantile(0.05):>+8.2f} {s.quantile(0.50):>+8.2f} {s.quantile(0.95):>+8.2f}")

    grav_cov = df_agg['gravity_n'].gt(0).sum()
    print(f"\nGravity coverage: {grav_cov}/{len(df_agg)} players with gravity computed "
          f"(median gravity_n = {df_agg['gravity_n'].median():.0f} passes)")

    print("\n" + "=" * 72)
    print(f"Pipeline complete. Processed {len(df_agg)} players.")
    print(f"Outputs: {config.HULL_EVENTS_RAW.name}  "
          f"{config.HULL_ZONE_BASELINES.name}  "
          f"{config.HULL_METRICS_AGG.name}")
    print("=" * 72)
    return df_agg


if __name__ == "__main__":
    main()
