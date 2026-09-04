"""Player totals — UEFA Euro 2024.

Pulls every Euro 2024 match from StatsBomb Open Data and builds a per-player
tournament-level table with identity, counts, distance and derived stats.
Filters out players with < 90 minutes played.

Output:
    data/Euro2024_Player_Totals_Distances_Roles.csv
    data/Euro2024_Player_Totals_Distances_Roles.xlsx  (whitelist for the hull pipeline)
"""
import warnings

import pandas as pd
from statsbombpy import sb

from . import config

warnings.filterwarnings('ignore')


def main():
    print("Phase 1: Fetching all UEFA Euro 2024 matches...")
    euro_matches = sb.matches(competition_id=config.COMPETITION_ID,
                              season_id=config.SEASON_ID)
    match_id_list = euro_matches['match_id'].tolist()
    print(f"Found {len(match_id_list)} matches. Starting the Match-by-Match processing...\n")

    all_match_logs = []

    # PHASE 1: MATCH-BY-MATCH CALCULATION
    for idx, match_id in enumerate(match_id_list, 1):
        print(f"Processing match {idx}/{len(match_id_list)} (ID: {match_id})...")

        df = sb.events(match_id=match_id)
        df = df.dropna(subset=['player', 'player_id']).copy()

        # Remove penalty shootouts (period 5)
        if 'period' in df.columns:
            df = df[df['period'] != 5].copy()

        # Role extraction at match level (mode of tactical position)
        df_pos = df.dropna(subset=['position'])
        if not df_pos.empty:
            match_roles = df_pos.groupby('player_id')['position'].agg(
                lambda x: x.mode()[0] if not x.mode().empty else 'Unknown'
            ).reset_index()
            match_roles.rename(columns={'position': 'primary_role'}, inplace=True)
        else:
            match_roles = pd.DataFrame(columns=['player_id', 'primary_role'])

        # Default values for optional columns that may be missing in some matches
        optional_columns = {
            'under_pressure': False, 'pass_cross': False, 'pass_goal_assist': False,
            'pass_shot_assist': False, 'shot_outcome': '', 'dribble_outcome': '',
            'duel_type': '', 'duel_outcome': '', 'pass_through_ball': False,
            'pass_switch': False, 'pass_length': 0.0,
        }
        for col, default_val in optional_columns.items():
            if col not in df.columns:
                df[col] = default_val

        # Core event flags
        df['pass_attempted']      = (df['type'] == 'Pass').astype(int)
        df['pass_successful']     = ((df['type'] == 'Pass') & (df['pass_outcome'].isnull())).astype(int)
        df['pass_failed']         = ((df['type'] == 'Pass') & (df['pass_outcome'].notnull())).astype(int)
        df['pass_under_pressure'] = ((df['type'] == 'Pass') & (df['under_pressure'] == True)).astype(int)

        df['through_ball']        = ((df['type'] == 'Pass') & (df['pass_through_ball'] == True)).astype(int)
        df['switch_of_play']      = ((df['type'] == 'Pass') & (df['pass_switch'] == True)).astype(int)
        df['cross_attempted']     = ((df['type'] == 'Pass') & (df['pass_cross'] == True)).astype(int)
        df['assist']              = (df['pass_goal_assist'] == True).astype(int)
        df['key_pass']            = (df['pass_shot_assist'] == True).astype(int)

        df['carry']               = (df['type'] == 'Carry').astype(int)
        df['shot']                = (df['type'] == 'Shot').astype(int)
        df['shot_on_target']      = ((df['type'] == 'Shot') & (df['shot_outcome'].isin(['Goal', 'Saved']))).astype(int)
        df['goal']                = (df['shot_outcome'] == 'Goal').astype(int)

        df['dribble_attempted']   = (df['type'] == 'Dribble').astype(int)
        df['dribble_successful']  = ((df['type'] == 'Dribble') & (df['dribble_outcome'] == 'Complete')).astype(int)
        df['ball_recovery']       = (df['type'] == 'Ball Recovery').astype(int)
        df['interception']        = (df['type'] == 'Interception').astype(int)
        df['tackle_won']          = ((df['type'] == 'Duel') & (df['duel_type'] == 'Tackle') & (df['duel_outcome'] == 'Won')).astype(int)
        df['aerial_won']          = ((df['type'] == 'Duel') & (df['duel_type'] == 'Aerial') & (df['duel_outcome'] == 'Won')).astype(int)
        df['clearance']           = (df['type'] == 'Clearance').astype(int)
        df['block']               = (df['type'] == 'Block').astype(int)
        df['foul_committed']      = (df['type'] == 'Foul Committed').astype(int)
        df['foul_won']            = (df['type'] == 'Foul Won').astype(int)
        df['dispossessed']        = (df['type'] == 'Dispossessed').astype(int)
        df['miscontrol']          = (df['type'] == 'Miscontrol').astype(int)

        # Passing distance
        df['pass_distance_all'] = 0.0
        df.loc[df['type'] == 'Pass', 'pass_distance_all'] = pd.to_numeric(
            df['pass_length'], errors='coerce').fillna(0.0)

        mask_successful = (df['type'] == 'Pass') & (df['pass_outcome'].isnull())
        df['pass_distance_success'] = 0.0
        df.loc[mask_successful, 'pass_distance_success'] = df.loc[mask_successful, 'pass_distance_all']

        mask_failed = (df['type'] == 'Pass') & (df['pass_outcome'].notnull())
        df['pass_distance_failed'] = 0.0
        df.loc[mask_failed, 'pass_distance_failed'] = df.loc[mask_failed, 'pass_distance_all']

        # Match-level aggregation
        match_log = df.groupby(['team', 'player_id', 'player']).agg(
            minute_start=('minute', 'min'),
            minute_end=('minute', 'max'),
            total_touches=('id', 'count'),

            passes_attempted=('pass_attempted', 'sum'),
            passes_successful=('pass_successful', 'sum'),
            passes_failed=('pass_failed', 'sum'),
            passes_under_pressure=('pass_under_pressure', 'sum'),

            sum_dist_all=('pass_distance_all', 'sum'),
            sum_dist_success=('pass_distance_success', 'sum'),
            sum_dist_failed=('pass_distance_failed', 'sum'),

            through_balls=('through_ball', 'sum'),
            switches_of_play=('switch_of_play', 'sum'),
            crosses=('cross_attempted', 'sum'),
            assists=('assist', 'sum'),
            key_passes=('key_pass', 'sum'),
            carries=('carry', 'sum'),
            shots=('shot', 'sum'),
            shots_on_target=('shot_on_target', 'sum'),
            goals=('goal', 'sum'),
            xg_total=('shot_statsbomb_xg', 'sum'),
            dribbles_attempted=('dribble_attempted', 'sum'),
            dribbles_successful=('dribble_successful', 'sum'),
            ball_recoveries=('ball_recovery', 'sum'),
            interceptions=('interception', 'sum'),
            tackles_won=('tackle_won', 'sum'),
            aerials_won=('aerial_won', 'sum'),
            clearances=('clearance', 'sum'),
            blocks=('block', 'sum'),
            fouls_committed=('foul_committed', 'sum'),
            fouls_won=('foul_won', 'sum'),
            dispossessed=('dispossessed', 'sum'),
            miscontrols=('miscontrol', 'sum'),
        ).reset_index()

        match_log['minutes_played'] = match_log['minute_end'] - match_log['minute_start']
        match_log = match_log.drop(columns=['minute_start', 'minute_end'])

        # Attach role to each match log
        match_log = pd.merge(match_log, match_roles, on='player_id', how='left')
        all_match_logs.append(match_log)

    print("\nPhase 2: Aggregating Total Tournament Data by Player...")

    raw_tournament_db = pd.concat(all_match_logs)

    # Tournament-level role (mode across matches)
    tournament_roles = raw_tournament_db.groupby('player_id')['primary_role'].agg(
        lambda x: x.mode()[0] if not x.mode().empty else 'Unknown'
    ).reset_index()

    numeric_tournament_db = raw_tournament_db.drop(columns=['primary_role'])
    player_totals = numeric_tournament_db.groupby(['team', 'player_id', 'player']).sum().reset_index()
    player_totals = pd.merge(player_totals, tournament_roles, on='player_id', how='left')
    player_totals['player_id'] = player_totals['player_id'].astype(int)

    # Tournament averages and percentages
    player_totals['pass_completion_pct'] = (
        player_totals['passes_successful'] / player_totals['passes_attempted'] * 100
    ).fillna(0).round(1)
    player_totals['avg_dist_all_passes'] = (
        player_totals['sum_dist_all'] / player_totals['passes_attempted']
    ).fillna(0).round(2)
    player_totals['avg_dist_successful'] = (
        player_totals['sum_dist_success'] / player_totals['passes_successful']
    ).fillna(0).round(2)
    player_totals['avg_dist_failed'] = (
        player_totals['sum_dist_failed'] / player_totals['passes_failed']
    ).fillna(0).round(2)

    # 90-minute filter
    minute_threshold = 90
    final_dataset = player_totals[player_totals['minutes_played'] >= minute_threshold].copy()

    # Column ordering (with primary_role)
    ordered_columns = [
        'team', 'player_id', 'player', 'primary_role', 'minutes_played', 'total_touches',
        'passes_attempted', 'passes_successful', 'passes_failed',
        'pass_completion_pct', 'passes_under_pressure',
        'avg_dist_all_passes', 'avg_dist_successful', 'avg_dist_failed',
        'through_balls', 'switches_of_play', 'crosses', 'assists', 'key_passes', 'carries',
        'shots', 'shots_on_target', 'goals', 'xg_total',
        'dribbles_attempted', 'dribbles_successful',
        'ball_recoveries', 'interceptions', 'tackles_won', 'aerials_won',
        'clearances', 'blocks',
        'fouls_committed', 'fouls_won', 'dispossessed', 'miscontrols',
    ]
    final_dataset = final_dataset[ordered_columns]
    final_dataset = final_dataset.sort_values(by='total_touches', ascending=False)

    print("\n EURO 2024 PLAYER TOTALS COMPLETED ")
    print(f"Total players in tournament: {len(player_totals)}")
    print(f"Players kept (>= {minute_threshold} mins): {len(final_dataset)}")

    final_dataset.to_csv(config.TOTALS_CSV, index=False)
    final_dataset.to_excel(config.TOTALS_XLSX, index=False)
    print(f"Saved: {config.TOTALS_CSV}")
    print(f"Saved: {config.TOTALS_XLSX}")
    return final_dataset


if __name__ == "__main__":
    main()
