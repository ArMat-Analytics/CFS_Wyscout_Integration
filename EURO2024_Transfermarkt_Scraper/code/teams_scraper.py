import argparse
import logging
import re
from html import unescape
from typing import Dict, List
from urllib.parse import urljoin

from scraper_utils import (
    BASE_DOMAIN,
    configure_logging,
    find_first_navigation_link,
    request_json,
    request_text,
    upsert_rows_to_csv,
)

LOGGER = logging.getLogger(__name__)

TEAM_FIELDNAMES = [
    "competition_id",
    "season",
    "team_id",
    "team_name",
    "team_relative_url",
    "team_url",
]


def parse_teams_from_participants_html(html: str) -> List[Dict[str, str]]:
    anchor_pattern = re.compile(
        r'<a\b[^>]*\bhref="(?P<href>/[^"]+/startseite/verein/(?P<team_id>\d+)[^"]*)"[^>]*>',
        flags=re.IGNORECASE,
    )
    title_pattern = re.compile(r'title="(?P<title>[^"]+)"', flags=re.IGNORECASE)

    teams_by_id: Dict[str, Dict[str, str]] = {}
    for anchor_match in anchor_pattern.finditer(html):
        anchor_html = anchor_match.group(0)
        title_match = title_pattern.search(anchor_html)
        if not title_match:
            continue

        team_id = anchor_match.group("team_id")
        team_relative_url = unescape(anchor_match.group("href")).strip()
        team_name = unescape(title_match.group("title")).strip()
        if not team_name:
            continue

        teams_by_id[team_id] = {
            "team_id": team_id,
            "team_name": team_name,
            "team_relative_url": team_relative_url,
            "team_url": urljoin(BASE_DOMAIN, team_relative_url),
        }

    teams = sorted(teams_by_id.values(), key=lambda row: int(row["team_id"]))
    if not teams:
        raise RuntimeError("No teams found in EURO participants page.")

    return teams


def fetch_euro_teams(
    season: str = "2024",
    competition_id: str = "EURO",
) -> List[Dict[str, str]]:
    referer = (
        f"{BASE_DOMAIN}/europameisterschaft/gesamtspielplan/"
        f"pokalwettbewerb/{competition_id}/saison_id/{season}"
    )

    sub_navigation = request_json(
        url=f"{BASE_DOMAIN}/navigation/getSubNavigation",
        params={"controller": "pokalwettbewerb", "season": season, "id": competition_id},
        headers={
            "accept": "*/*",
            "referer": referer,
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
        },
        timeout=30,
        max_retries=4,
    )

    participants_relative_link = find_first_navigation_link(
        payload=sub_navigation,
        tracks=["participants"],
        texts=["participants"],
        path_fragments=["/teilnehmer", "/participants"],
    )
    participants_url = urljoin(BASE_DOMAIN, participants_relative_link)

    html = request_text(
        url=participants_url,
        headers={
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "referer": referer,
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "same-origin",
        },
        timeout=35,
        max_retries=4,
    )

    teams = parse_teams_from_participants_html(html)
    for row in teams:
        row["competition_id"] = competition_id
        row["season"] = season

    return teams


def export_teams_to_csv(
    output_csv: str = "data/teams.csv",
    season: str = "2024",
    competition_id: str = "EURO",
) -> Dict[str, str]:
    LOGGER.info("Fetching EURO teams (season=%s, competition_id=%s)", season, competition_id)
    teams = fetch_euro_teams(season=season, competition_id=competition_id)

    csv_result = upsert_rows_to_csv(
        csv_path=output_csv,
        fieldnames=TEAM_FIELDNAMES,
        rows=teams,
        key_fields=["competition_id", "season", "team_id"],
    )

    result = {
        "output_csv": output_csv,
        "teams_found": str(len(teams)),
        "rows_total": str(csv_result["rows_total"]),
        "inserted": str(csv_result["inserted"]),
        "updated": str(csv_result["updated"]),
        "skipped": str(csv_result["skipped"]),
    }

    LOGGER.info(
        "Teams CSV updated: %s (total=%s, inserted=%s, updated=%s, skipped=%s)",
        output_csv,
        result["rows_total"],
        result["inserted"],
        result["updated"],
        result["skipped"],
    )
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scrape EURO 2024 participating teams from Transfermarkt and update a CSV incrementally."
    )
    parser.add_argument(
        "--output",
        default="data/teams.csv",
        help="Output CSV path (default: data/teams.csv)",
    )
    parser.add_argument(
        "--season",
        default="2024",
        help="Participants season used by Transfermarkt for EURO 2024 (default: 2024)",
    )
    parser.add_argument(
        "--competition-id",
        default="EURO",
        help="Transfermarkt competition id (default: EURO)",
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

    output = export_teams_to_csv(
        output_csv=args.output,
        season=args.season,
        competition_id=args.competition_id,
    )

    print(f"Teams CSV: {output['output_csv']}")
    print(f"Teams found: {output['teams_found']}")
    print(f"Rows total: {output['rows_total']}")
    print(f"Inserted: {output['inserted']}")
    print(f"Updated missing fields: {output['updated']}")
    print(f"Skipped unchanged: {output['skipped']}")
