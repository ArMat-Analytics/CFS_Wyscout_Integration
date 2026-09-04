import argparse
import logging
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple
from urllib.parse import urljoin

from scraper_utils import (
    BASE_DOMAIN,
    clean_text,
    configure_logging,
    extract_first_group,
    extract_href,
    find_first_navigation_link,
    read_csv_rows,
    request_json,
    request_text,
    upsert_rows_to_csv,
)
from teams_scraper import fetch_euro_teams

LOGGER = logging.getLogger(__name__)

TEAM_DATA_FIELDNAMES = [
    "competition_id",
    "participants_season",
    "team_season",
    "team_id",
    "team_name",
    "team_relative_url",
    "fixtures_relative_url",
    "fixtures_url",
    "squad_relative_url",
    "squad_url",
    "competition_label",
    "current_label",
    "current_matches",
    "current_wins",
    "current_draws",
    "current_losses",
    "current_points_per_game",
    "current_goals_for_against",
    "current_avg_attendance",
    "overall_label",
    "overall_matches",
    "overall_wins",
    "overall_draws",
    "overall_losses",
    "overall_points_per_game",
    "overall_goals_for_against",
    "overall_avg_attendance",
]

TEAM_PLAYERS_FIELDNAMES = [
    "competition_id",
    "team_season",
    "team_id",
    "team_name",
    "player_id",
    "player_name",
    "player_relative_url",
    "player_url",
    "squad_number",
    "position",
    "age",
    "market_value",
]

TEAM_ERRORS_FIELDNAMES = [
    "competition_id",
    "team_season",
    "team_id",
    "team_name",
    "error",
]


def parse_row_cells(row_html: str) -> List[str]:
    cell_htmls = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row_html, flags=re.IGNORECASE | re.DOTALL)
    return [clean_text(cell) for cell in cell_htmls]


def ensure_detailed_fixtures_link(fixtures_relative_link: str, team_season: str) -> str:
    base_link = fixtures_relative_link.split("#", maxsplit=1)[0].rstrip("/")

    if "/saison_id/" not in base_link:
        base_link = f"{base_link}/saison_id/{team_season}"

    if "/plus/1" not in base_link:
        base_link = f"{base_link}/plus/1"

    return base_link


def ensure_squad_link(team_relative_url: str, squad_relative_link: str, team_season: str) -> str:
    base_link = squad_relative_link.strip()
    if not base_link:
        base_link = team_relative_url.replace("/startseite/", "/kader/")

    base_link = base_link.split("#", maxsplit=1)[0].rstrip("/")

    if "/saison_id/" not in base_link:
        base_link = f"{base_link}/saison_id/{team_season}"

    if "/plus/1" not in base_link:
        base_link = f"{base_link}/plus/1"

    return base_link


def parse_euro_summary_table(html: str, competition_id: str, team_season: str) -> Dict[str, str]:
    header_anchor_match = re.search(
        rf"<a[^>]+href=[\"']([^\"']*/wettbewerb/{re.escape(competition_id)}/saison_id/{re.escape(team_season)}[^\"']*)[\"'][^>]*>(?P<header_text>.*?)</a>",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not header_anchor_match:
        raise RuntimeError(
            f"Unable to find EURO summary table for competition={competition_id} and season={team_season}."
        )

    header_anchor_start = header_anchor_match.start()
    table_start = html.rfind("<table", 0, header_anchor_start)
    if table_start < 0:
        raise RuntimeError("Unable to locate team summary table start.")

    table_end = html.find("</table>", header_anchor_start)
    if table_end < 0:
        raise RuntimeError("Unable to locate team summary table end.")

    summary_table_html = html[table_start : table_end + len("</table>")]
    relative_header_start = header_anchor_start - table_start
    summary_from_target_header = summary_table_html[relative_header_start:]

    current_row_match = re.search(
        r"</th>\s*</tr>\s*</thead>\s*<tbody[^>]*>\s*<tr[^>]*>(?P<current>.*?)</tr>\s*</tbody>",
        summary_from_target_header,
        flags=re.IGNORECASE | re.DOTALL,
    )
    overall_row_match = re.search(
        r"<tfoot[^>]*>\s*<tr[^>]*>.*?</tr>\s*<tr[^>]*>(?P<overall>.*?)</tr>",
        summary_from_target_header,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if not current_row_match or not overall_row_match:
        raise RuntimeError("Summary rows are not available for this team in EURO section.")

    header_text = clean_text(header_anchor_match.group("header_text"))
    current_cells = parse_row_cells(current_row_match.group("current"))
    overall_cells = parse_row_cells(overall_row_match.group("overall"))

    if len(current_cells) < 8 or len(overall_cells) < 8:
        raise RuntimeError("Unexpected summary table structure.")

    return {
        "competition_label": header_text,
        "current_label": current_cells[0],
        "current_matches": current_cells[1],
        "current_wins": current_cells[2],
        "current_draws": current_cells[3],
        "current_losses": current_cells[4],
        "current_points_per_game": current_cells[5],
        "current_goals_for_against": current_cells[6],
        "current_avg_attendance": current_cells[7],
        "overall_label": overall_cells[0],
        "overall_matches": overall_cells[1],
        "overall_wins": overall_cells[2],
        "overall_draws": overall_cells[3],
        "overall_losses": overall_cells[4],
        "overall_points_per_game": overall_cells[5],
        "overall_goals_for_against": overall_cells[6],
        "overall_avg_attendance": overall_cells[7],
    }


def parse_team_players_from_squad_html(
    squad_html: str,
    team_context: Dict[str, str],
    competition_id: str,
    team_season: str,
) -> List[Dict[str, str]]:
    players_by_id: Dict[str, Dict[str, str]] = {}

    # Player rows contain nested tables, so we capture rows by looking ahead to the next odd/even row.
    row_html_list = [
        match.group("row")
        for match in re.finditer(
            r"<tr\s+class=[\"'](?:odd|even)[\"'][^>]*>(?P<row>.*?)</tr>\s*(?=<tr\s+class=[\"'](?:odd|even)[\"'][^>]*>|</tbody>)",
            squad_html,
            flags=re.IGNORECASE | re.DOTALL,
        )
    ]

    if not row_html_list:
        row_html_list = re.findall(r"<tr[^>]*>(.*?)</tr>", squad_html, flags=re.IGNORECASE | re.DOTALL)

    for row_html in row_html_list:
        if "/spieler/" not in row_html:
            continue

        player_relative_url = extract_first_group(
            row_html,
            [r'href="([^"]+/profil/spieler/\d+[^"]*)"'],
            use_dotall=True,
        )
        if not player_relative_url:
            continue

        player_id = extract_first_group(player_relative_url, [r"/spieler/(\d+)"])
        if not player_id:
            continue

        player_name = clean_text(
            extract_first_group(
                row_html,
                [
                    r'href="[^"]+/profil/spieler/\d+[^"]*"[^>]*>(.*?)</a>',
                ],
                use_dotall=True,
            )
        )

        squad_number = clean_text(
            extract_first_group(
                row_html,
                [
                    r"class=rn_nummer>(.*?)</div>",
                    r"rueckennummer[^>]*>\s*([^<]+)\s*</td>",
                ],
                use_dotall=True,
            )
        )
        position = clean_text(
            extract_first_group(
                row_html,
                [
                    r'<table[^>]*class="inline-table"[^>]*>.*?<tr>\s*<td[^>]*>\s*<a[^>]*>.*?</a>\s*</td>\s*</tr>\s*<tr>\s*<td[^>]*>\s*(.*?)\s*</td>\s*</tr>',
                    r'rueckennummer[^>]*title="([^"]+)"',
                ],
                use_dotall=True,
            )
        )
        age = extract_first_group(row_html, [r"\((\d{1,2})\)"])
        market_value = clean_text(
            extract_first_group(
                row_html,
                [
                    r'<td[^>]*class="rechts[^"]*hauptlink[^"]*"[^>]*>.*?<a[^>]*>(.*?)</a>',
                    r'<td[^>]*class="rechts[^"]*hauptlink[^"]*"[^>]*>(.*?)</td>',
                ],
                use_dotall=True,
            )
        )

        players_by_id[player_id] = {
            "competition_id": competition_id,
            "team_season": team_season,
            "team_id": team_context.get("team_id", ""),
            "team_name": team_context.get("team_name", ""),
            "player_id": player_id,
            "player_name": player_name,
            "player_relative_url": player_relative_url,
            "player_url": urljoin(BASE_DOMAIN, player_relative_url),
            "squad_number": squad_number,
            "position": position,
            "age": age,
            "market_value": market_value,
        }

    return sorted(players_by_id.values(), key=lambda row: int(row["player_id"]))


def load_teams(
    source_teams_csv: str,
    participants_season: str,
    competition_id: str,
    team_id: Optional[str],
) -> List[Dict[str, str]]:
    source_file = Path(source_teams_csv)
    teams: List[Dict[str, str]] = []

    if source_file.exists():
        _, rows = read_csv_rows(source_teams_csv)
        for row in rows:
            if str(row.get("competition_id", "")).strip() != competition_id:
                continue
            if str(row.get("season", "")).strip() != participants_season:
                continue
            if not str(row.get("team_id", "")).strip().isdigit():
                continue
            teams.append(
                {
                    "team_id": str(row.get("team_id", "")).strip(),
                    "team_name": str(row.get("team_name", "")).strip(),
                    "team_relative_url": str(row.get("team_relative_url", "")).strip(),
                }
            )

    if not teams:
        teams = fetch_euro_teams(season=participants_season, competition_id=competition_id)

    if team_id:
        teams = [row for row in teams if str(row.get("team_id", "")).strip() == str(team_id).strip()]
        if not teams:
            raise RuntimeError(f"No team found for team_id={team_id}.")

    return teams


def scrape_team_data(
    team: Dict[str, str],
    participants_season: str,
    team_season: str,
    competition_id: str,
) -> Tuple[Dict[str, str], List[Dict[str, str]]]:
    team_id = str(team.get("team_id", "")).strip()
    team_name = str(team.get("team_name", "")).strip()
    team_relative_url = str(team.get("team_relative_url", "")).strip()

    referer = urljoin(BASE_DOMAIN, f"{team_relative_url}/saison_id/{team_season}/plus/1")
    sub_navigation = request_json(
        url=f"{BASE_DOMAIN}/navigation/getSubNavigation",
        params={"controller": "verein", "season": team_season, "id": team_id},
        headers={
            "accept": "*/*",
            "referer": referer,
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
        },
        timeout=30,
        max_retries=4,
    )

    fixtures_relative_url = find_first_navigation_link(
        payload=sub_navigation,
        tracks=["fixtures"],
        texts=["fixtures"],
        path_fragments=["/spielplan/verein/"],
    )

    squad_relative_url = ""
    try:
        squad_relative_url = find_first_navigation_link(
            payload=sub_navigation,
            tracks=["squad"],
            texts=["squad"],
            path_fragments=["/kader/verein/"],
        )
    except RuntimeError:
        LOGGER.debug("Squad link not found in navigation for team_id=%s. Falling back to derived URL.", team_id)

    detailed_fixtures_relative_url = ensure_detailed_fixtures_link(fixtures_relative_url, team_season)
    detailed_squad_relative_url = ensure_squad_link(team_relative_url, squad_relative_url, team_season)

    fixtures_url = urljoin(BASE_DOMAIN, detailed_fixtures_relative_url)
    squad_url = urljoin(BASE_DOMAIN, detailed_squad_relative_url)

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

    squad_html = request_text(
        url=squad_url,
        headers={
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "referer": fixtures_url,
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "same-origin",
        },
        timeout=35,
        max_retries=4,
    )

    summary = parse_euro_summary_table(
        html=fixtures_html,
        competition_id=competition_id,
        team_season=team_season,
    )

    team_data_row = {
        "competition_id": competition_id,
        "participants_season": participants_season,
        "team_season": team_season,
        "team_id": team_id,
        "team_name": team_name,
        "team_relative_url": team_relative_url,
        "fixtures_relative_url": detailed_fixtures_relative_url,
        "fixtures_url": fixtures_url,
        "squad_relative_url": detailed_squad_relative_url,
        "squad_url": squad_url,
        **summary,
    }

    team_players_rows = parse_team_players_from_squad_html(
        squad_html=squad_html,
        team_context=team,
        competition_id=competition_id,
        team_season=team_season,
    )

    return team_data_row, team_players_rows


def export_team_data_to_csv(
    teams_csv: str = "data/teams.csv",
    team_data_csv: str = "data/team_data.csv",
    team_players_csv: str = "data/team_players.csv",
    errors_csv: str = "data/errors/team_errors.csv",
    participants_season: str = "2024",
    team_season: str = "2024",
    competition_id: str = "EURO",
    team_id: Optional[str] = None,
    request_delay_seconds: float = 0.15,
) -> Dict[str, str]:
    teams = load_teams(
        source_teams_csv=teams_csv,
        participants_season=participants_season,
        competition_id=competition_id,
        team_id=team_id,
    )

    team_data_rows: List[Dict[str, str]] = []
    team_players_rows: List[Dict[str, str]] = []
    error_rows: List[Dict[str, str]] = []

    for index, team in enumerate(teams, start=1):
        current_team_id = str(team.get("team_id", "")).strip()
        current_team_name = str(team.get("team_name", "")).strip()
        LOGGER.info("Scraping team data for %s (%s)", current_team_name, current_team_id)

        try:
            team_data_row, current_players = scrape_team_data(
                team=team,
                participants_season=participants_season,
                team_season=team_season,
                competition_id=competition_id,
            )
            team_data_rows.append(team_data_row)
            team_players_rows.extend(current_players)
        except Exception as exc:
            LOGGER.exception("Team scraping failed for team_id=%s", current_team_id)
            error_rows.append(
                {
                    "competition_id": competition_id,
                    "team_season": team_season,
                    "team_id": current_team_id,
                    "team_name": current_team_name,
                    "error": str(exc),
                }
            )

        if request_delay_seconds > 0 and index < len(teams):
            time.sleep(request_delay_seconds)

    team_data_result = upsert_rows_to_csv(
        csv_path=team_data_csv,
        fieldnames=TEAM_DATA_FIELDNAMES,
        rows=team_data_rows,
        key_fields=["competition_id", "team_season", "team_id"],
    )
    team_players_result = upsert_rows_to_csv(
        csv_path=team_players_csv,
        fieldnames=TEAM_PLAYERS_FIELDNAMES,
        rows=team_players_rows,
        key_fields=["competition_id", "team_season", "team_id", "player_id"],
    )
    errors_result = upsert_rows_to_csv(
        csv_path=errors_csv,
        fieldnames=TEAM_ERRORS_FIELDNAMES,
        rows=error_rows,
        key_fields=["competition_id", "team_season", "team_id", "error"],
    )

    return {
        "teams_requested": str(len(teams)),
        "team_data_csv": team_data_csv,
        "team_players_csv": team_players_csv,
        "errors_csv": errors_csv,
        "team_data_rows_total": str(team_data_result["rows_total"]),
        "team_data_inserted": str(team_data_result["inserted"]),
        "team_data_updated": str(team_data_result["updated"]),
        "team_players_rows_total": str(team_players_result["rows_total"]),
        "team_players_inserted": str(team_players_result["inserted"]),
        "team_players_updated": str(team_players_result["updated"]),
        "errors_rows_total": str(errors_result["rows_total"]),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Scrape EURO 2024 team-level data and team squads, then update CSV outputs incrementally."
        )
    )
    parser.add_argument(
        "--teams-csv",
        default="data/teams.csv",
        help="Input teams CSV path (default: data/teams.csv)",
    )
    parser.add_argument(
        "--team-data-csv",
        default="data/team_data.csv",
        help="Output team data CSV path (default: data/team_data.csv)",
    )
    parser.add_argument(
        "--team-players-csv",
        default="data/team_players.csv",
        help="Output team players CSV path (default: data/team_players.csv)",
    )
    parser.add_argument(
        "--errors-csv",
        default="data/errors/team_errors.csv",
        help="Output team errors CSV path (default: data/errors/team_errors.csv)",
    )
    parser.add_argument(
        "--participants-season",
        default="2024",
        help="Season used for EURO participants endpoint (default: 2024)",
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
        help="Optional single team id to scrape.",
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

    result = export_team_data_to_csv(
        teams_csv=args.teams_csv,
        team_data_csv=args.team_data_csv,
        team_players_csv=args.team_players_csv,
        errors_csv=args.errors_csv,
        participants_season=args.participants_season,
        team_season=args.team_season,
        competition_id=args.competition_id,
        team_id=args.team_id,
        request_delay_seconds=args.delay,
    )

    print(f"Teams requested: {result['teams_requested']}")
    print(f"Team data CSV: {result['team_data_csv']}")
    print(f"Team players CSV: {result['team_players_csv']}")
    print(f"Errors CSV: {result['errors_csv']}")
    print(f"Team data rows total: {result['team_data_rows_total']}")
    print(f"Team data inserted: {result['team_data_inserted']}")
    print(f"Team data updated missing fields: {result['team_data_updated']}")
    print(f"Team players rows total: {result['team_players_rows_total']}")
    print(f"Team players inserted: {result['team_players_inserted']}")
    print(f"Team players updated missing fields: {result['team_players_updated']}")
    print(f"Errors rows total: {result['errors_rows_total']}")
