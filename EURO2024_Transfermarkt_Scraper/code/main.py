import argparse
import logging

from matches_scraper import export_home_matches_to_csv
from player_scraper import export_players_to_csv
from scraper_utils import configure_logging
from team_data_scraper import export_team_data_to_csv
from teams_scraper import export_teams_to_csv

LOGGER = logging.getLogger(__name__)


def run_pipeline(
    teams_csv: str,
    team_data_csv: str,
    team_players_csv: str,
    team_errors_csv: str,
    team_matches_csv: str,
    match_errors_csv: str,
    player_data_csv: str,
    player_transfer_history_csv: str,
    player_market_value_history_csv: str,
    player_national_career_csv: str,
    player_absence_history_csv: str,
    player_errors_csv: str,
    participants_season: str,
    team_season: str,
    competition_id: str,
    team_id: str | None,
    teams_delay: float,
    team_data_delay: float,
    matches_delay: float,
    players_delay: float,
) -> dict:
    LOGGER.info("Step 1/4 - Scraping EURO participants teams")
    teams_result = export_teams_to_csv(
        output_csv=teams_csv,
        season=participants_season,
        competition_id=competition_id,
    )

    LOGGER.info("Step 2/4 - Scraping team data and team players")
    team_data_result = export_team_data_to_csv(
        teams_csv=teams_csv,
        team_data_csv=team_data_csv,
        team_players_csv=team_players_csv,
        errors_csv=team_errors_csv,
        participants_season=participants_season,
        team_season=team_season,
        competition_id=competition_id,
        team_id=team_id,
        request_delay_seconds=team_data_delay,
    )

    LOGGER.info("Step 3/4 - Scraping EURO home matches per team")
    matches_result = export_home_matches_to_csv(
        team_data_csv=team_data_csv,
        teams_csv=teams_csv,
        output_csv=team_matches_csv,
        errors_csv=match_errors_csv,
        participants_season=participants_season,
        team_season=team_season,
        competition_id=competition_id,
        team_id=team_id,
        request_delay_seconds=matches_delay,
    )

    LOGGER.info("Step 4/4 - Scraping player datasets")
    players_result = export_players_to_csv(
        team_players_csv=team_players_csv,
        player_data_csv=player_data_csv,
        transfer_history_csv=player_transfer_history_csv,
        market_value_history_csv=player_market_value_history_csv,
        national_career_csv=player_national_career_csv,
        absence_history_csv=player_absence_history_csv,
        errors_csv=player_errors_csv,
        competition_id=competition_id,
        team_season=team_season,
        team_id=team_id,
        request_delay_seconds=players_delay,
    )

    return {
        "teams": teams_result,
        "team_data": team_data_result,
        "matches": matches_result,
        "players": players_result,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Master scraper pipeline for EURO 2024: teams -> team data/players -> home matches -> player datasets."
        )
    )
    parser.add_argument("--teams-csv", default="data/teams.csv")
    parser.add_argument("--team-data-csv", default="data/team_data.csv")
    parser.add_argument("--team-players-csv", default="data/team_players.csv")
    parser.add_argument("--team-errors-csv", default="data/errors/team_errors.csv")
    parser.add_argument("--team-matches-csv", default="data/team_matches.csv")
    parser.add_argument("--match-errors-csv", default="data/errors/match_errors.csv")
    parser.add_argument("--player-data-csv", default="data/player_data.csv")
    parser.add_argument("--player-transfer-history-csv", default="data/player_transfer_history.csv")
    parser.add_argument("--player-market-value-history-csv", default="data/player_market_value_history.csv")
    parser.add_argument("--player-national-career-csv", default="data/player_national_career.csv")
    parser.add_argument("--player-absence-history-csv", default="data/player_absence_history.csv")
    parser.add_argument("--player-errors-csv", default="data/errors/player_errors.csv")

    parser.add_argument("--participants-season", default="2024")
    parser.add_argument("--team-season", default="2024")
    parser.add_argument("--competition-id", default="EURO")
    parser.add_argument("--team-id", default=None, help="Optional single team id for partial runs.")

    parser.add_argument("--teams-delay", type=float, default=0.0)
    parser.add_argument("--team-data-delay", type=float, default=0.15)
    parser.add_argument("--matches-delay", type=float, default=0.15)
    parser.add_argument("--players-delay", type=float, default=0.1)
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    configure_logging(verbose=args.verbose)

    results = run_pipeline(
        teams_csv=args.teams_csv,
        team_data_csv=args.team_data_csv,
        team_players_csv=args.team_players_csv,
        team_errors_csv=args.team_errors_csv,
        team_matches_csv=args.team_matches_csv,
        match_errors_csv=args.match_errors_csv,
        player_data_csv=args.player_data_csv,
        player_transfer_history_csv=args.player_transfer_history_csv,
        player_market_value_history_csv=args.player_market_value_history_csv,
        player_national_career_csv=args.player_national_career_csv,
        player_absence_history_csv=args.player_absence_history_csv,
        player_errors_csv=args.player_errors_csv,
        participants_season=args.participants_season,
        team_season=args.team_season,
        competition_id=args.competition_id,
        team_id=args.team_id,
        teams_delay=args.teams_delay,
        team_data_delay=args.team_data_delay,
        matches_delay=args.matches_delay,
        players_delay=args.players_delay,
    )

    print("Pipeline completed.")
    print(f"Teams CSV: {results['teams']['output_csv']}")
    print(f"Team data CSV: {results['team_data']['team_data_csv']}")
    print(f"Team players CSV: {results['team_data']['team_players_csv']}")
    print(f"Team matches CSV: {results['matches']['output_csv']}")
    print(f"Player data CSV: {results['players']['player_data_csv']}")
    print(f"Player transfer history CSV: {results['players']['transfer_history_csv']}")
    print(f"Player market value history CSV: {results['players']['market_value_history_csv']}")
    print(f"Player national career CSV: {results['players']['national_career_csv']}")
    print(f"Player absence history CSV: {results['players']['absence_history_csv']}")
