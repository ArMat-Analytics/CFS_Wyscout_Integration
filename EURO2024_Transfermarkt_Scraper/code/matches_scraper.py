import argparse
import logging
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence
from urllib.parse import urljoin

from scraper_utils import (
    BASE_DOMAIN,
    clean_text,
    configure_logging,
    extract_first_group,
    extract_href,
    request_text,
    upsert_rows_to_csv,
)
from team_data_scraper import export_team_data_to_csv

LOGGER = logging.getLogger(__name__)

MATCH_FIELDNAMES = [
    "competition_id",
    "team_season",
    "team_id",
    "team_name",
    "fixtures_url",
    "matchday",
    "date",
    "time",
    "home_team_id",
    "home_team_name",
    "home_team_relative_url",
    "away_team_id",
    "away_team_name",
    "away_team_relative_url",
    "system_of_play",
    "coach_name",
    "coach_id",
    "coach_relative_url",
    "attendance",
    "result",
    "result_color",
    "match_report_id",
    "match_report_relative_url",
    "match_report_url",
]

MATCH_ERRORS_FIELDNAMES = ["competition_id", "team_season", "team_id", "team_name", "error"]


def read_team_sources(
    team_data_csv: str,
    teams_csv: str,
    participants_season: str,
    team_season: str,
    competition_id: str,
    team_id: Optional[str],
    delay: float,
) -> List[Dict[str, str]]:
    sources: List[Dict[str, str]] = []
    team_data_path = Path(team_data_csv)

    if team_data_path.exists():
        import csv

        with team_data_path.open("r", newline="", encoding="utf-8") as csv_file:
            reader = csv.DictReader(csv_file)
            for row in reader:
                if str(row.get("competition_id", "")).strip() != competition_id:
                    continue
                if str(row.get("team_season", "")).strip() != team_season:
                    continue
                current_team_id = str(row.get("team_id", "")).strip()
                if team_id and current_team_id != str(team_id).strip():
                    continue
                if not current_team_id.isdigit():
                    continue

                sources.append(
                    {
                        "competition_id": competition_id,
                        "team_season": team_season,
                        "team_id": current_team_id,
                        "team_name": str(row.get("team_name", "")).strip(),
                        "fixtures_url": str(row.get("fixtures_url", "")).strip(),
                    }
                )

    if not sources:
        LOGGER.info(
            "Team data source not available. Running team_data_scraper to build source CSV first."
        )
        export_team_data_to_csv(
            teams_csv=teams_csv,
            team_data_csv=team_data_csv,
            team_players_csv="data/team_players.csv",
            errors_csv="data/errors/team_errors.csv",
            participants_season=participants_season,
            team_season=team_season,
            competition_id=competition_id,
            team_id=team_id,
            request_delay_seconds=delay,
        )
        return read_team_sources(
            team_data_csv=team_data_csv,
            teams_csv=teams_csv,
            participants_season=participants_season,
            team_season=team_season,
            competition_id=competition_id,
            team_id=team_id,
            delay=delay,
        )

    return sources


def parse_euro_detailed_matches(html: str, competition_id: str) -> List[Dict[str, str]]:
    anchor_match = re.search(
        rf"<a\s+name=[\"']{re.escape(competition_id)}[\"'][^>]*>",
        html,
        flags=re.IGNORECASE,
    )
    if not anchor_match:
        raise RuntimeError(f"Unable to find competition anchor for {competition_id}.")

    section_html = html[anchor_match.start() :]
    table_match = re.search(r"<table[^>]*>(?P<table>.*?)</table>", section_html, flags=re.IGNORECASE | re.DOTALL)
    if not table_match:
        raise RuntimeError("Unable to find EURO match table inside fixtures page.")

    tbody_match = re.search(
        r"<tbody[^>]*>(?P<tbody>.*?)</tbody>",
        table_match.group("table"),
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not tbody_match:
        return []

    row_html_list = re.findall(
        r"<tr[^>]*>(.*?)</tr>",
        tbody_match.group("tbody"),
        flags=re.IGNORECASE | re.DOTALL,
    )

    rows: List[Dict[str, str]] = []
    for row_html in row_html_list:
        cell_htmls = re.findall(r"<td[^>]*>(.*?)</td>", row_html, flags=re.IGNORECASE | re.DOTALL)
        if len(cell_htmls) < 11:
            continue

        home_team_href = extract_href(cell_htmls[4])
        away_team_href = extract_href(cell_htmls[6])
        coach_href = extract_href(cell_htmls[8])
        report_href = extract_href(cell_htmls[10])

        combined_team_html = f"{cell_htmls[3]} {cell_htmls[4]} {cell_htmls[5]} {cell_htmls[6]}"
        home_team_id = extract_first_group(
            home_team_href + " " + combined_team_html,
            [r"/verein/(\d+)"],
        )
        away_team_id = extract_first_group(
            away_team_href + " " + combined_team_html,
            [r"/verein/(\d+)"],
        )
        coach_id = extract_first_group(coach_href + " " + cell_htmls[8], [r"/profil/trainer/(\d+)"])
        report_id = extract_first_group(
            report_href + " " + cell_htmls[10],
            [r"/spielbericht/(?:index/)?spielbericht/(\d+)"],
        )

        result_color = ""
        if "greentext" in cell_htmls[10]:
            result_color = "green"
        elif "redtext" in cell_htmls[10]:
            result_color = "red"
        elif "bluetext" in cell_htmls[10]:
            result_color = "blue"

        rows.append(
            {
                "matchday": clean_text(cell_htmls[0]),
                "date": clean_text(cell_htmls[1]),
                "time": clean_text(cell_htmls[2]),
                "home_team_id": home_team_id,
                "home_team_name": clean_text(cell_htmls[4]),
                "home_team_relative_url": home_team_href,
                "away_team_id": away_team_id,
                "away_team_name": clean_text(cell_htmls[6]),
                "away_team_relative_url": away_team_href,
                "system_of_play": clean_text(cell_htmls[7]),
                "coach_name": clean_text(cell_htmls[8]),
                "coach_id": coach_id,
                "coach_relative_url": coach_href,
                "attendance": clean_text(cell_htmls[9]),
                "result": clean_text(cell_htmls[10]),
                "result_color": result_color,
                "match_report_id": report_id,
                "match_report_relative_url": report_href,
                "match_report_url": urljoin(BASE_DOMAIN, report_href) if report_href else "",
            }
        )

    return rows


def scrape_home_matches_for_team(
    team_source: Dict[str, str],
    competition_id: str,
) -> List[Dict[str, str]]:
    team_id = str(team_source.get("team_id", "")).strip()
    team_name = str(team_source.get("team_name", "")).strip()
    fixtures_url = str(team_source.get("fixtures_url", "")).strip()

    if not fixtures_url:
        raise RuntimeError(f"Missing fixtures_url for team {team_name} ({team_id}).")

    fixtures_html = request_text(
        url=fixtures_url,
        headers={
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "referer": fixtures_url,
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "same-origin",
        },
        timeout=35,
        max_retries=4,
    )

    all_rows = parse_euro_detailed_matches(fixtures_html, competition_id=competition_id)

    home_rows: List[Dict[str, str]] = []
    for row in all_rows:
        home_team_id = str(row.get("home_team_id", "")).strip()
        if home_team_id and home_team_id != team_id:
            continue

        row["competition_id"] = competition_id
        row["team_season"] = str(team_source.get("team_season", "")).strip()
        row["team_id"] = team_id
        row["team_name"] = team_name
        row["fixtures_url"] = fixtures_url
        home_rows.append(row)

    return home_rows


def export_home_matches_to_csv(
    team_data_csv: str = "data/team_data.csv",
    teams_csv: str = "data/teams.csv",
    output_csv: str = "data/team_matches.csv",
    errors_csv: str = "data/errors/match_errors.csv",
    participants_season: str = "2024",
    team_season: str = "2024",
    competition_id: str = "EURO",
    team_id: Optional[str] = None,
    request_delay_seconds: float = 0.15,
) -> Dict[str, str]:
    team_sources = read_team_sources(
        team_data_csv=team_data_csv,
        teams_csv=teams_csv,
        participants_season=participants_season,
        team_season=team_season,
        competition_id=competition_id,
        team_id=team_id,
        delay=request_delay_seconds,
    )

    match_rows: List[Dict[str, str]] = []
    error_rows: List[Dict[str, str]] = []

    for index, team_source in enumerate(team_sources, start=1):
        current_team_id = str(team_source.get("team_id", "")).strip()
        current_team_name = str(team_source.get("team_name", "")).strip()

        LOGGER.info("Scraping home matches for %s (%s)", current_team_name, current_team_id)
        try:
            rows = scrape_home_matches_for_team(
                team_source=team_source,
                competition_id=competition_id,
            )
            match_rows.extend(rows)
        except Exception as exc:
            LOGGER.exception("Failed to scrape matches for team_id=%s", current_team_id)
            error_rows.append(
                {
                    "competition_id": competition_id,
                    "team_season": team_season,
                    "team_id": current_team_id,
                    "team_name": current_team_name,
                    "error": str(exc),
                }
            )

        if request_delay_seconds > 0 and index < len(team_sources):
            time.sleep(request_delay_seconds)

    matches_result = upsert_rows_to_csv(
        csv_path=output_csv,
        fieldnames=MATCH_FIELDNAMES,
        rows=match_rows,
        key_fields=["competition_id", "team_season", "team_id", "match_report_id"],
    )
    errors_result = upsert_rows_to_csv(
        csv_path=errors_csv,
        fieldnames=MATCH_ERRORS_FIELDNAMES,
        rows=error_rows,
        key_fields=["competition_id", "team_season", "team_id", "error"],
    )

    return {
        "teams_requested": str(len(team_sources)),
        "output_csv": output_csv,
        "errors_csv": errors_csv,
        "rows_total": str(matches_result["rows_total"]),
        "inserted": str(matches_result["inserted"]),
        "updated": str(matches_result["updated"]),
        "errors_rows_total": str(errors_result["rows_total"]),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Scrape EURO 2024 home matches for each team and update team_matches.csv incrementally."
        )
    )
    parser.add_argument(
        "--team-data-csv",
        default="data/team_data.csv",
        help="Input team data CSV (default: data/team_data.csv)",
    )
    parser.add_argument(
        "--teams-csv",
        default="data/teams.csv",
        help="Input teams CSV fallback (default: data/teams.csv)",
    )
    parser.add_argument(
        "--output",
        default="data/team_matches.csv",
        help="Output matches CSV path (default: data/team_matches.csv)",
    )
    parser.add_argument(
        "--errors-csv",
        default="data/errors/match_errors.csv",
        help="Output errors CSV path (default: data/errors/match_errors.csv)",
    )
    parser.add_argument(
        "--participants-season",
        default="2024",
        help="Participants season used for EURO teams (default: 2024)",
    )
    parser.add_argument(
        "--team-season",
        default="2024",
        help="Season used for team pages (default: 2024)",
    )
    parser.add_argument(
        "--competition-id",
        default="EURO",
        help="Transfermarkt competition id (default: EURO)",
    )
    parser.add_argument(
        "--team-id",
        default=None,
        help="Optional single team id.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.15,
        help="Delay in seconds between teams (default: 0.15)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    configure_logging(verbose=args.verbose)

    result = export_home_matches_to_csv(
        team_data_csv=args.team_data_csv,
        teams_csv=args.teams_csv,
        output_csv=args.output,
        errors_csv=args.errors_csv,
        participants_season=args.participants_season,
        team_season=args.team_season,
        competition_id=args.competition_id,
        team_id=args.team_id,
        request_delay_seconds=args.delay,
    )

    print(f"Teams requested: {result['teams_requested']}")
    print(f"Matches CSV: {result['output_csv']}")
    print(f"Errors CSV: {result['errors_csv']}")
    print(f"Rows total: {result['rows_total']}")
    print(f"Inserted: {result['inserted']}")
    print(f"Updated missing fields: {result['updated']}")
    print(f"Errors rows total: {result['errors_rows_total']}")
