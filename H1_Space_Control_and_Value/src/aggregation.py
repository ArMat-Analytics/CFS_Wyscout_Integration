"""Player aggregation — final per-player table.

Builds player_space_control_aggregated.csv by joining:
    - identity + gravity from hull_metrics_aggregated.csv  (passed through)
    - hull rates recomputed on open play from hull_events_lb.csv
    - line-breaker counts and EPV statistics

Hull percentage rates (between_lines_pct, hull_exit_pct, pressure_resistance_pct)
and the corresponding per-90 volumes are computed on the open-play subset to
avoid set-piece dilution of the denominators. Penetration rate is split into
its two atomic components: penetration_per90 (attempts) and
successful_hull_penetrations_per90 (successful out->in passes), with a clean
penetration_completion_pct (= successful / attempts) replacing the old
hull_penetration_pct that mixed selectivity and completion.
Gravity columns are passed through unchanged from the LOO upstream pipeline.

Filtering rules:
    - GKs dropped (no macro_role after the LB filter).
    - Small-sample CDM/CM -> MID and W/WM -> WIDE.
    - Players with minutes_played < ANALYSIS_MIN_MINUTES (default 135 = 1.5
      matches) are dropped: below that threshold the percentage rates are
      dominated by noise and the percentile rankings are unreliable.

Output:
    data/player_space_control_aggregated.csv
"""
import numpy as np
import pandas as pd

from . import config


def _safe_pct(num, den):
    return num / den.replace(0, np.nan) * 100


def main():
    df_lb  = pd.read_csv(config.HULL_EVENTS_LB)
    df_agg = pd.read_csv(config.HULL_METRICS_AGG)
    print(f"LB events: {len(df_lb):,}   Players (hull_agg): {len(df_agg):,}")

    # --- 0) GK filter and macro-role grouping -----------------------------
    df_lb = df_lb[df_lb['macro_role'] != 'GK'].copy()
    df_lb['macro_role'] = df_lb['macro_role'].replace(config.ROLE_REMAP)

    role_mode = (df_lb.groupby(['player', 'team'])['macro_role']
                       .agg(lambda s: s.mode().iloc[0] if not s.mode().empty else 'OTHER')
                       .reset_index())

    # --- 1) Per-event boolean flags --------------------------------------
    df_lb['_succ_hull_exit'] = ( df_lb['player_between_lines']
                                & ~df_lb['end_inside_hull']
                                &  df_lb['pass_successful'])
    df_lb['_succ_hull_pen']  = (~df_lb['player_between_lines']
                                &  df_lb['end_inside_hull']
                                &  df_lb['pass_successful'])
    df_lb['_not_between']    = ~df_lb['player_between_lines']
    df_lb['_succ_press']     =  df_lb['under_pressure'] & df_lb['pass_successful']

    # --- 2) Per-player aggregation on the open-play subset ---------------
    g = df_lb.groupby(['player', 'team'])
    stats = g.agg(
        passes_op               = ('event_id',                 'count'),
        # Line-breaker counts (denominator: passes_op)
        lb_geom                 = ('is_line_breaker_geom',     'sum'),
        lb_epv                  = ('is_line_breaker_epv',      'sum'),
        lb_quality              = ('is_line_breaker_quality',  'sum'),
        # EPV summaries
        epv_added_sum           = ('epv_added',                'sum'),
        epv_added_mean          = ('epv_added',                'mean'),
        defenders_bypassed_mean = ('defenders_bypassed',       'mean'),
        # Hull-event counts (numerators / denominators for the rates below)
        between_lines_n                = ('player_between_lines', 'sum'),
        pressure_resistance_n          = ('under_pressure',       'sum'),
        _succ_hull_exit_n              = ('_succ_hull_exit',      'sum'),
        successful_hull_penetrations_n = ('_succ_hull_pen',       'sum'),
        _succ_press_n                  = ('_succ_press',          'sum'),
    ).reset_index()

    # Line-breaker rates (open play)
    stats['lb_geom_pct']    = _safe_pct(stats['lb_geom'],    stats['passes_op'])
    stats['lb_epv_pct']     = _safe_pct(stats['lb_epv'],     stats['passes_op'])
    stats['lb_quality_pct'] = _safe_pct(stats['lb_quality'], stats['passes_op'])

    # Hull rates on OPEN PLAY
    stats['between_lines_pct']       = _safe_pct(stats['between_lines_n'],     stats['passes_op'])
    stats['hull_exit_n']             = stats['between_lines_n']  # by definition
    stats['hull_exit_pct']           = _safe_pct(stats['_succ_hull_exit_n'],   stats['between_lines_n'])
    stats['pressure_resistance_pct'] = _safe_pct(stats['_succ_press_n'],       stats['pressure_resistance_n'])

    # --- 3) EPV by geom_type --------------------------------------------
    pen_mask = df_lb['geom_type'] == 'Penetration (out->in)'
    pen = (df_lb[pen_mask]
             .groupby(['player', 'team'])['epv_added']
             .agg(epv_penetration_mean='mean',
                  epv_penetration_sum='sum',
                  penetration_n='count')
             .reset_index())
    stats = stats.merge(pen, on=['player', 'team'], how='left')

    # Penetration completion rate: successful out->in passes / out->in attempts.
    # Pure technical-quality signal, separated from selectivity (which lives in
    # penetration_per90 and the radar). Replaces the old hull_penetration_pct
    # that mixed both signals through the broader 'passes from outside' denominator.
    stats['penetration_completion_pct'] = _safe_pct(
        stats['successful_hull_penetrations_n'], stats['penetration_n'])

    ins_mask = df_lb['geom_type'] == 'Inside circulation (in->in)'
    ins = (df_lb[ins_mask]
             .groupby(['player', 'team'])['epv_added']
             .agg(epv_inside_circ_mean='mean',
                  epv_inside_circ_sum='sum',
                  inside_circ_n='count')
             .reset_index())
    stats = stats.merge(ins, on=['player', 'team'], how='left')

    exit_mask = df_lb['geom_type'] == 'Exit (in->out)'
    exi = (df_lb[exit_mask]
             .groupby(['player', 'team'])['epv_added']
             .agg(epv_exit_mean='mean',
                  epv_exit_sum='sum',
                  exit_n='count')
             .reset_index())
    stats = stats.merge(exi, on=['player', 'team'], how='left')

    out_mask = df_lb['geom_type'] == 'Outside circulation (out->out)'
    out = (df_lb[out_mask]
             .groupby(['player', 'team'])['epv_added']
             .agg(epv_outside_circ_mean='mean',
                  epv_outside_circ_sum='sum',
                  outside_circ_n='count')
             .reset_index())
    stats = stats.merge(out, on=['player', 'team'], how='left')

    # --- 4) Bring minutes in for per-90 conversion ----------------------
    mins = df_agg[['player', 'team', 'minutes_played']].drop_duplicates()
    stats = stats.merge(mins, on=['player', 'team'], how='left')

    per90_pairs = [
        ('lb_geom',             'lb_geom_per90'),
        ('lb_epv',              'lb_epv_per90'),
        ('lb_quality',          'lb_quality_per90'),
        ('epv_added_sum',       'epv_added_per90'),
        ('epv_penetration_sum', 'epv_penetration_per90'),
        ('epv_inside_circ_sum', 'epv_inside_circ_per90'),
        ('epv_exit_sum',        'epv_exit_per90'),
        ('epv_outside_circ_sum','epv_outside_circ_per90'),
        ('penetration_n',       'penetration_per90'),
        ('inside_circ_n',       'inside_circ_per90'),
        ('exit_n',              'exit_per90'),
        ('outside_circ_n',      'outside_circ_per90'),
        # Hull volumes (open play)
        ('between_lines_n',     'between_lines_per90'),
        ('_succ_hull_exit_n',              'successful_hull_exits_per90'),
        ('successful_hull_penetrations_n', 'successful_hull_penetrations_per90'),
    ]
    for src_col, new_col in per90_pairs:
        stats[new_col] = stats[src_col] / stats['minutes_played'].replace(0, np.nan) * 90

    stats = stats.drop(columns=['_succ_hull_exit_n', '_succ_press_n',
                                'minutes_played'])

    # --- 5) Add macro_role ----------------------------------------------
    stats = stats.merge(role_mode, on=['player', 'team'], how='left')

    # --- 6) Sanity check: open-play vs all-passes hull rates ------------
    print("\n" + "=" * 78)
    print(" SANITY CHECK  -  open-play rates  vs  all-passes rates")
    print("=" * 78)
    print(f"  {'metric':<26s}{'mean Δ':>10s}{'median Δ':>12s}{'max |Δ|':>10s}{'corr':>8s}")
    _old = (df_agg[['player', 'team',
                    'between_lines_pct', 'hull_exit_pct',
                    'pressure_resistance_pct']]
              .rename(columns={c: c + '__old' for c in
                      ['between_lines_pct', 'hull_exit_pct',
                       'pressure_resistance_pct']}))
    _chk = stats[['player', 'team',
                  'between_lines_pct', 'hull_exit_pct',
                  'pressure_resistance_pct']].merge(
                _old, on=['player', 'team'], how='left')
    for m in ['between_lines_pct', 'hull_exit_pct',
              'pressure_resistance_pct']:
        d    = _chk[m] - _chk[m + '__old']
        corr = _chk[[m, m + '__old']].corr().iloc[0, 1]
        print(f"  {m:<26s}{d.mean():>10.2f}{d.median():>12.2f}"
              f"{d.abs().max():>10.2f}{corr:>8.3f}")
    print("-" * 78)
    print(" Read: small Δ + corr > 0.95 -> recomputation tracks the old rate; the")
    print(" set-piece bias is real but moderate, and is now removed from the rates.")
    print("=" * 78)

    # --- 7) Final merge -------------------------------------------------
    legacy_hull = ['between_lines_pct', 'between_lines_n', 'between_lines_per90',
                   'hull_exit_pct', 'hull_exit_n', 'successful_hull_exits_per90',
                   'hull_penetration_pct', 'hull_penetration_n', 'successful_hull_penetrations_per90',
                   'pressure_resistance_pct', 'pressure_resistance_n']
    df_agg = df_agg.drop(columns=[c for c in legacy_hull if c in df_agg.columns])

    collide = [c for c in stats.columns if c in df_agg.columns and c not in ('player', 'team')]
    if collide:
        df_agg = df_agg.drop(columns=collide)

    df_full = df_agg.merge(stats, on=['player', 'team'], how='left')

    before  = len(df_full)
    df_full = df_full[df_full['macro_role'].notna()].reset_index(drop=True)
    dropped_gk = before - len(df_full)

    # Apply the analysis minute-filter so every downstream consumer sees a
    # consistent pool. Below this threshold the percentage rates and the
    # within-role percentiles are dominated by noise.
    before  = len(df_full)
    df_full = (df_full[df_full['minutes_played'] >= config.ANALYSIS_MIN_MINUTES]
               .reset_index(drop=True))
    dropped_min = before - len(df_full)

    # The macro_role.notna() filter primarily drops goalkeepers (the LB
    # pipeline assigns macro_role=GK and we strip them above). It also
    # protects against the theoretical case of a player whose only
    # analyzed passes were set pieces (so they have no entry in
    # hull_events_lb.csv). On Euro 2024 that case is empty: every
    # outfielder in hull_metrics_aggregated.csv has at least one
    # open-play LB event.
    print(f"\nDropped {dropped_gk} rows (goalkeepers).")
    print(f"Dropped {dropped_min} rows (minutes_played < {config.ANALYSIS_MIN_MINUTES}).")

    df_full.to_csv(config.PLAYER_AGG_PATH, index=False)
    print(f"\nSaved: {config.PLAYER_AGG_PATH}")
    print(f"  {len(df_full):,} players × {len(df_full.columns)} columns")
    print("\nmacro_role distribution:")
    print(df_full['macro_role'].value_counts().to_string())

    # Quick top-10 print
    top_cols = ['player', 'team', 'primary_role', 'macro_role', 'minutes_played',
                'between_lines_pct', 'gravity_composite_pct', 'gravity_directional_m',
                'lb_geom_per90', 'lb_quality_per90', 'epv_penetration_mean']
    top_cols = [c for c in top_cols if c in df_full.columns]
    print("\nTop 10 by lb_quality_per90 (open play):")
    print(df_full.sort_values('lb_quality_per90', ascending=False)[top_cols]
                  .head(10).to_string(index=False))
    return df_full


if __name__ == "__main__":
    main()
