import argparse
import logging
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

from scraper_utils import BASE_DOMAIN, configure_logging, request_json, upsert_rows_to_csv

LOGGER = logging.getLogger(__name__)

TM_API_BASE = "https://tmapi-alpha.transfermarkt.technology"

API_HEADERS = {
    "accept": "application/json",
    "origin": BASE_DOMAIN,
    "referer": f"{BASE_DOMAIN}/",
}

EURO_2024_START = date(2024, 6, 14)
EURO_2024_END = date(2024, 7, 14)

PLAYER_DATA_FIELDNAMES = [
    "competition_id",
    "team_season",
    "source_team_id",
    "source_team_name",
    "player_id",
    "player_name",
    "short_name",
    "display_name",
    "date_of_birth",
    "age",
    "place_of_birth",
    "nationality",
    "gender",
    "height_m",
    "preferred_foot",
    "position_group",
    "position",
    "first_side_position",
    "2024_club_id",
    "market_value_before_euros",
    "market_value_before_euros_date",
    "market_value_after_euros",
    "market_value_after_euros_date",
    "contract_until",
    "consultant_agency",
    "profile_relative_url",
    "profile_url",
    "portrait_url",
]

TRANSFER_HISTORY_FIELDNAMES = [
    "competition_id",
    "team_season",
    "source_team_id",
    "source_team_name",
    "player_id",
    "transfer_id",
    "date",
    "season_id",
    "season_label",
    "source_club_id",
    "destination_club_id",
    "market_value_at_transfer",
    "fee",
    "age",
    "transfer_type",
    "transfer_type_label",
    "fee_description",
    "transfer_relative_url",
    "transfer_url",
]

MARKET_VALUE_HISTORY_FIELDNAMES = [
    "competition_id",
    "team_season",
    "source_team_id",
    "source_team_name",
    "player_id",
    "season_id",
    "club_id",
    "age",
    "market_value",
    "determined",
]

NATIONAL_CAREER_FIELDNAMES = [
    "competition_id",
    "team_season",
    "source_team_id",
    "source_team_name",
    "player_id",
    "national_team_id",
    "games_played",
    "goals_scored",
    "shirt_number",
    "is_captain",
    "debut",
    "debut_coach_id",
    "debut_game_id",
    "career_state",
]

ABSENCE_HISTORY_FIELDNAMES = [
    "competition_id",
    "team_season",
    "source_team_id",
    "source_team_name",
    "player_id",
    "absence_id",
    "name",
    "competition_id_absence",
    "season_id",
    "start",
    "end",
    "missed_games",
    "possible_missing_games",
    "days",
    "returning_days",
]

PLAYER_ERRORS_FIELDNAMES = [
    "competition_id",
    "team_season",
    "source_team_id",
    "source_team_name",
    "player_id",
    "player_url",
    "error",
]


@dataclass(frozen=True)
class PlayerContext:
    competition_id: str
    team_season: str
    source_team_id: str
    source_team_name: str
    player_id: str
    player_name: str
    player_url: str


def money_to_string(value: Any) -> str:
    if not isinstance(value, dict):
        return ""

    compact = value.get("compact")
    if isinstance(compact, dict):
        compact_value = (
            f"{compact.get('prefix', '')}{compact.get('content', '')}{compact.get('suffix', '')}".strip()
        )
        if compact_value:
            return compact_value

    compact_value = (
        f"{value.get('compact_prefix', '')}{value.get('compact_content', '')}{value.get('compact_suffix', '')}".strip()
    )
    if compact_value:
        return compact_value

    raw_value = value.get("value")
    raw_currency = value.get("currency", "")
    if raw_value is None:
        return ""
    return f"{raw_value} {raw_currency}".strip()


def money_from_parent(parent: Any, prefix: str) -> str:
    if not isinstance(parent, dict):
        return ""

    nested = parent.get(prefix)
    nested_value = money_to_string(nested)
    if nested_value:
        return nested_value

    compact_value = (
        f"{parent.get(prefix + '_compact_prefix', '')}"
        f"{parent.get(prefix + '_compact_content', '')}"
        f"{parent.get(prefix + '_compact_suffix', '')}"
    ).strip()
    if compact_value:
        return compact_value

    value = parent.get(prefix + "_value")
    currency = parent.get(prefix + "_currency", "")
    if value is None:
        return ""
    return f"{value} {currency}".strip()


def extract_player_id_from_url(player_url: str) -> str:
    parsed = urlparse(player_url)
    path = parsed.path or ""

    import re

    match = re.search(r"/spieler/(\d+)", path)
    if not match:
        raise ValueError("Unable to extract player id from URL.")

    return match.group(1)


def normalize_player_url(url_or_relative: str) -> str:
    url_or_relative = str(url_or_relative).strip()
    if not url_or_relative:
        return ""
    if url_or_relative.startswith("http://") or url_or_relative.startswith("https://"):
        return url_or_relative
    return urljoin(BASE_DOMAIN, url_or_relative)


def parse_iso_date(value: str) -> Optional[date]:
    raw_value = str(value).strip()
    if not raw_value:
        return None

    try:
        return datetime.fromisoformat(raw_value.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return datetime.strptime(raw_value[:10], "%Y-%m-%d").date()
        except ValueError:
            return None


def extract_market_value_snapshots(market_payload: Any) -> List[Dict[str, Any]]:
    data = market_payload.get("data", {}) if isinstance(market_payload, dict) else {}
    history = data.get("history", []) if isinstance(data.get("history"), list) else []

    snapshots: List[Dict[str, Any]] = []
    for item in history:
        if not isinstance(item, dict):
            continue

        market_value = item.get("marketValue", {}) if isinstance(item.get("marketValue"), dict) else {}
        determined = str(market_value.get("determined", "")).strip() or str(item.get("determined", "")).strip()
        determined_date = parse_iso_date(determined)
        if determined_date is None:
            continue

        snapshots.append(
            {
                "determined_date": determined_date,
                "determined": determined,
                "club_id": str(item.get("clubId", "")).strip(),
                "market_value": money_to_string(market_value),
            }
        )

    snapshots.sort(key=lambda row: row["determined_date"])
    return snapshots


def get_snapshot_before(snapshots: List[Dict[str, Any]], target: date) -> Optional[Dict[str, Any]]:
    candidates = [row for row in snapshots if row["determined_date"] <= target]
    if not candidates:
        return None
    return max(candidates, key=lambda row: row["determined_date"])


def get_snapshot_after(snapshots: List[Dict[str, Any]], target: date) -> Optional[Dict[str, Any]]:
    candidates = [row for row in snapshots if row["determined_date"] >= target]
    if not candidates:
        return None
    return min(candidates, key=lambda row: row["determined_date"])


def load_player_contexts(
    team_players_csv: str,
    competition_id: str,
    team_season: str,
    team_id: Optional[str],
    player_id: Optional[str],
    player_url: Optional[str],
) -> List[PlayerContext]:
    if player_url:
        resolved_player_id = player_id or extract_player_id_from_url(player_url)
        return [
            PlayerContext(
                competition_id=competition_id,
                team_season=team_season,
                source_team_id=str(team_id or ""),
                source_team_name="",
                player_id=str(resolved_player_id),
                player_name="",
                player_url=normalize_player_url(player_url),
            )
        ]

    source_path = Path(team_players_csv)
    if not source_path.exists():
        raise RuntimeError(
            f"Missing player source CSV: {team_players_csv}. Run team_data_scraper first."
        )

    import csv

    contexts_by_player_id: Dict[str, PlayerContext] = {}
    with source_path.open("r", newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            if str(row.get("competition_id", "")).strip() != competition_id:
                continue
            if str(row.get("team_season", "")).strip() != team_season:
                continue

            current_team_id = str(row.get("team_id", "")).strip()
            if team_id and current_team_id != str(team_id).strip():
                continue

            current_player_id = str(row.get("player_id", "")).strip()
            if not current_player_id.isdigit():
                continue
            if player_id and current_player_id != str(player_id).strip():
                continue

            current_player_url = normalize_player_url(
                row.get("player_url") or row.get("player_relative_url") or ""
            )
            if not current_player_url:
                continue

            contexts_by_player_id[current_player_id] = PlayerContext(
                competition_id=competition_id,
                team_season=team_season,
                source_team_id=current_team_id,
                source_team_name=str(row.get("team_name", "")).strip(),
                player_id=current_player_id,
                player_name=str(row.get("player_name", "")).strip(),
                player_url=current_player_url,
            )

    contexts = sorted(contexts_by_player_id.values(), key=lambda row: int(row.player_id))
    if not contexts:
        raise RuntimeError("No player contexts found with current filters.")

    return contexts


def get_json(url: str, params: Optional[Dict[str, Any]] = None, optional: bool = False) -> Any:
    try:
        return request_json(
            url=url,
            params=params,
            headers=API_HEADERS,
            timeout=30,
            max_retries=4,
        )
    except Exception:
        if optional:
            LOGGER.warning("Optional endpoint failed: %s", url)
            return {}
        raise


def fetch_player_payloads(player_id: str) -> Dict[str, Any]:
    payloads: Dict[str, Any] = {}

    payloads["profile"] = get_json(
        url=f"{TM_API_BASE}/players",
        params={"ids[]": player_id},
        optional=False,
    )
    payloads["transfer_history"] = get_json(
        url=f"{TM_API_BASE}/transfer/history/player/{player_id}",
        optional=False,
    )
    payloads["market_value_history"] = get_json(
        url=f"{TM_API_BASE}/player/{player_id}/market-value-history",
        optional=False,
    )
    payloads["national_career_history"] = get_json(
        url=f"{TM_API_BASE}/player/{player_id}/national-career-history",
        optional=False,
    )
    payloads["absence_history"] = get_json(
        url=f"{TM_API_BASE}/player/{player_id}/absence",
        params={"onlyCurrent": "false"},
        optional=True,
    )

    return payloads


def parse_profile_row(context: PlayerContext, profile_payload: Any, market_payload: Any) -> Dict[str, str]:
    profile_data = []
    if isinstance(profile_payload, dict):
        raw_data = profile_payload.get("data", [])
        if isinstance(raw_data, list):
            profile_data = raw_data

    profile = profile_data[0] if profile_data else {}
    if not isinstance(profile, dict):
        profile = {}

    life_dates = profile.get("lifeDates", {}) if isinstance(profile.get("lifeDates"), dict) else {}
    birth_place = (
        profile.get("birthPlaceDetails", {})
        if isinstance(profile.get("birthPlaceDetails"), dict)
        else {}
    )
    nationality_details = (
        profile.get("nationalityDetails", {})
        if isinstance(profile.get("nationalityDetails"), dict)
        else {}
    )
    attributes = profile.get("attributes", {}) if isinstance(profile.get("attributes"), dict) else {}
    current_club_id = ""
    club_assignments = profile.get("clubAssignments", []) if isinstance(profile.get("clubAssignments"), list) else []
    for assignment in club_assignments:
        if not isinstance(assignment, dict):
            continue
        if str(assignment.get("type", "")).lower() == "current":
            current_club_id = str(assignment.get("clubId", "")).strip()
            break

    preferred_foot = ""
    preferred_foot_dict = attributes.get("preferredFoot")
    if isinstance(preferred_foot_dict, dict):
        preferred_foot = str(preferred_foot_dict.get("name", "")).strip()
    if not preferred_foot:
        preferred_foot = str(attributes.get("preferredFootId", "")).strip()

    position = ""
    position_dict = attributes.get("position")
    if isinstance(position_dict, dict):
        position = str(position_dict.get("name", "")).strip()

    first_side_position = ""
    first_side_position_dict = attributes.get("firstSidePosition")
    if isinstance(first_side_position_dict, dict):
        first_side_position = str(first_side_position_dict.get("name", "")).strip()

    snapshots = extract_market_value_snapshots(market_payload)
    before_euros = get_snapshot_before(snapshots, EURO_2024_START)
    after_euros = get_snapshot_after(snapshots, EURO_2024_END)

    season_2024_club_id = ""
    if before_euros:
        season_2024_club_id = str(before_euros.get("club_id", "")).strip()
    elif after_euros:
        season_2024_club_id = str(after_euros.get("club_id", "")).strip()
    else:
        season_2024_club_id = current_club_id

    profile_relative_url = str(profile.get("relativeUrl", "")).strip()

    return {
        "competition_id": context.competition_id,
        "team_season": context.team_season,
        "source_team_id": context.source_team_id,
        "source_team_name": context.source_team_name,
        "player_id": context.player_id,
        "player_name": str(profile.get("name", "")).strip() or context.player_name,
        "short_name": str(profile.get("shortName", "")).strip(),
        "display_name": str(profile.get("displayName", "")).strip(),
        "date_of_birth": str(life_dates.get("dateOfBirth", "")).strip(),
        "age": str(life_dates.get("age", "")).strip(),
        "place_of_birth": str(birth_place.get("placeOfBirth", "")).strip(),
        "nationality": str(nationality_details.get("passportName", "")).strip(),
        "gender": str(birth_place.get("gender", "")).strip(),
        "height_m": str(attributes.get("height", "")).strip(),
        "preferred_foot": preferred_foot,
        "position_group": str(attributes.get("positionGroupName", "")).strip(),
        "position": position,
        "first_side_position": first_side_position,
        "2024_club_id": season_2024_club_id,
        "market_value_before_euros": str(before_euros.get("market_value", "")).strip() if before_euros else "",
        "market_value_before_euros_date": str(before_euros.get("determined", "")).strip() if before_euros else "",
        "market_value_after_euros": str(after_euros.get("market_value", "")).strip() if after_euros else "",
        "market_value_after_euros_date": str(after_euros.get("determined", "")).strip() if after_euros else "",
        "contract_until": str(attributes.get("contractUntil", "")).strip(),
        "consultant_agency": str(
            (attributes.get("consultantAgency") or {}).get("name", "")
            if isinstance(attributes.get("consultantAgency"), dict)
            else ""
        ).strip(),
        "profile_relative_url": profile_relative_url,
        "profile_url": urljoin(BASE_DOMAIN, profile_relative_url) if profile_relative_url else context.player_url,
        "portrait_url": str(profile.get("portraitUrl", "")).strip(),
    }


def parse_transfer_rows(context: PlayerContext, transfer_payload: Any) -> List[Dict[str, str]]:
    data = transfer_payload.get("data", {}) if isinstance(transfer_payload, dict) else {}
    history = data.get("history", {}) if isinstance(data.get("history"), dict) else {}
    terminated = history.get("terminated", []) if isinstance(history.get("terminated"), list) else []

    rows: List[Dict[str, str]] = []
    for item in terminated:
        if not isinstance(item, dict):
            continue

        details = item.get("details", {}) if isinstance(item.get("details"), dict) else {}
        source = item.get("transferSource", {}) if isinstance(item.get("transferSource"), dict) else {}
        destination = (
            item.get("transferDestination", {}) if isinstance(item.get("transferDestination"), dict) else {}
        )
        transfer_type = item.get("typeDetails", {}) if isinstance(item.get("typeDetails"), dict) else {}

        season_label = ""
        season_details = details.get("season", {}) if isinstance(details.get("season"), dict) else {}
        if season_details:
            season_label = str(season_details.get("display", "")).strip()

        transfer_relative_url = str(item.get("relativeUrl", "")).strip()

        rows.append(
            {
                "competition_id": context.competition_id,
                "team_season": context.team_season,
                "source_team_id": context.source_team_id,
                "source_team_name": context.source_team_name,
                "player_id": context.player_id,
                "transfer_id": str(item.get("id", "")).strip(),
                "date": str(details.get("date", "")).strip(),
                "season_id": str(details.get("seasonId", "")).strip(),
                "season_label": season_label,
                "source_club_id": str(source.get("clubId", "")).strip(),
                "destination_club_id": str(destination.get("clubId", "")).strip(),
                "market_value_at_transfer": money_to_string(details.get("marketValue")),
                "fee": money_to_string(details.get("fee")),
                "age": str(details.get("age", "")).strip(),
                "transfer_type": str(transfer_type.get("type", "")).strip(),
                "transfer_type_label": str(transfer_type.get("name", "")).strip(),
                "fee_description": str(transfer_type.get("feeDescription", "")).strip(),
                "transfer_relative_url": transfer_relative_url,
                "transfer_url": urljoin(BASE_DOMAIN, transfer_relative_url) if transfer_relative_url else "",
            }
        )

    return rows


def parse_market_value_rows(context: PlayerContext, market_payload: Any) -> List[Dict[str, str]]:
    data = market_payload.get("data", {}) if isinstance(market_payload, dict) else {}
    history = data.get("history", []) if isinstance(data.get("history"), list) else []

    rows: List[Dict[str, str]] = []
    for item in history:
        if not isinstance(item, dict):
            continue

        market_value = item.get("marketValue", {}) if isinstance(item.get("marketValue"), dict) else {}
        rows.append(
            {
                "competition_id": context.competition_id,
                "team_season": context.team_season,
                "source_team_id": context.source_team_id,
                "source_team_name": context.source_team_name,
                "player_id": context.player_id,
                "season_id": str(item.get("seasonId", "")).strip(),
                "club_id": str(item.get("clubId", "")).strip(),
                "age": str(item.get("age", "")).strip(),
                "market_value": money_to_string(market_value),
                "determined": str(market_value.get("determined", "")).strip(),
            }
        )

    return rows


def parse_national_career_rows(context: PlayerContext, national_payload: Any) -> List[Dict[str, str]]:
    data = national_payload.get("data", {}) if isinstance(national_payload, dict) else {}
    history = data.get("history", []) if isinstance(data.get("history"), list) else []

    rows: List[Dict[str, str]] = []
    for item in history:
        if not isinstance(item, dict):
            continue

        national_team_id = str(item.get("clubId", "")).strip()
        # Keep national team rows aligned with the EURO source team.
        if context.source_team_id and national_team_id and national_team_id != context.source_team_id:
            continue

        rows.append(
            {
                "competition_id": context.competition_id,
                "team_season": context.team_season,
                "source_team_id": context.source_team_id,
                "source_team_name": context.source_team_name,
                "player_id": context.player_id,
                "national_team_id": national_team_id,
                "games_played": str(item.get("gamesPlayed", "")).strip(),
                "goals_scored": str(item.get("goalsScored", "")).strip(),
                "shirt_number": str(item.get("shirtNumber", "")).strip(),
                "is_captain": "true" if bool(item.get("isCaptain")) else "false",
                "debut": str(item.get("debut", "")).strip(),
                "debut_coach_id": str(item.get("debutCoachId", "")).strip(),
                "debut_game_id": str(item.get("debutGameId", "")).strip(),
                "career_state": str(item.get("careerState", "")).strip(),
            }
        )

    return rows


def parse_absence_rows(context: PlayerContext, absence_payload: Any) -> List[Dict[str, str]]:
    data = absence_payload.get("data", {}) if isinstance(absence_payload, dict) else {}
    absences = data.get("absences", []) if isinstance(data.get("absences"), list) else []

    rows: List[Dict[str, str]] = []
    for item in absences:
        if not isinstance(item, dict):
            continue

        duration = item.get("durationDetails", {}) if isinstance(item.get("durationDetails"), dict) else {}

        rows.append(
            {
                "competition_id": context.competition_id,
                "team_season": context.team_season,
                "source_team_id": context.source_team_id,
                "source_team_name": context.source_team_name,
                "player_id": context.player_id,
                "absence_id": str(item.get("absenceId", "")).strip(),
                "name": str(item.get("name", "")).strip(),
                "competition_id_absence": str(item.get("competitionId", "")).strip(),
                "season_id": str(item.get("seasonId", "")).strip(),
                "start": str(item.get("start", "")).strip(),
                "end": str(item.get("end", "")).strip(),
                "missed_games": str(item.get("missedGamesCount", "")).strip(),
                "possible_missing_games": str(item.get("possibleMissingGamesCount", "")).strip(),
                "days": str(duration.get("days", "")).strip(),
                "returning_days": str(duration.get("returningDays", "")).strip(),
            }
        )

    return rows


def export_players_to_csv(
    team_players_csv: str = "data/team_players.csv",
    player_data_csv: str = "data/player_data.csv",
    transfer_history_csv: str = "data/player_transfer_history.csv",
    market_value_history_csv: str = "data/player_market_value_history.csv",
    national_career_csv: str = "data/player_national_career.csv",
    absence_history_csv: str = "data/player_absence_history.csv",
    errors_csv: str = "data/errors/player_errors.csv",
    competition_id: str = "EURO",
    team_season: str = "2024",
    team_id: Optional[str] = None,
    player_id: Optional[str] = None,
    player_url: Optional[str] = None,
    request_delay_seconds: float = 0.1,
) -> Dict[str, str]:
    contexts = load_player_contexts(
        team_players_csv=team_players_csv,
        competition_id=competition_id,
        team_season=team_season,
        team_id=team_id,
        player_id=player_id,
        player_url=player_url,
    )

    player_rows: List[Dict[str, str]] = []
    transfer_rows: List[Dict[str, str]] = []
    market_value_rows: List[Dict[str, str]] = []
    national_rows: List[Dict[str, str]] = []
    absence_rows: List[Dict[str, str]] = []
    error_rows: List[Dict[str, str]] = []

    for index, context in enumerate(contexts, start=1):
        LOGGER.info(
            "Scraping player %s (%s) from team %s",
            context.player_name or context.player_id,
            context.player_id,
            context.source_team_name or context.source_team_id,
        )

        try:
            payloads = fetch_player_payloads(context.player_id)
            player_rows.append(parse_profile_row(context, payloads["profile"], payloads["market_value_history"]))
            transfer_rows.extend(parse_transfer_rows(context, payloads["transfer_history"]))
            market_value_rows.extend(parse_market_value_rows(context, payloads["market_value_history"]))
            national_rows.extend(parse_national_career_rows(context, payloads["national_career_history"]))
            absence_rows.extend(parse_absence_rows(context, payloads.get("absence_history", {})))
        except Exception as exc:
            LOGGER.exception("Player scraping failed for player_id=%s", context.player_id)
            error_rows.append(
                {
                    "competition_id": context.competition_id,
                    "team_season": context.team_season,
                    "source_team_id": context.source_team_id,
                    "source_team_name": context.source_team_name,
                    "player_id": context.player_id,
                    "player_url": context.player_url,
                    "error": str(exc),
                }
            )

        if request_delay_seconds > 0 and index < len(contexts):
            time.sleep(request_delay_seconds)

    player_result = upsert_rows_to_csv(
        csv_path=player_data_csv,
        fieldnames=PLAYER_DATA_FIELDNAMES,
        rows=player_rows,
        key_fields=["competition_id", "team_season", "player_id"],
    )
    transfer_result = upsert_rows_to_csv(
        csv_path=transfer_history_csv,
        fieldnames=TRANSFER_HISTORY_FIELDNAMES,
        rows=transfer_rows,
        key_fields=["competition_id", "team_season", "player_id", "transfer_id"],
    )
    market_value_result = upsert_rows_to_csv(
        csv_path=market_value_history_csv,
        fieldnames=MARKET_VALUE_HISTORY_FIELDNAMES,
        rows=market_value_rows,
        key_fields=["competition_id", "team_season", "player_id", "season_id", "club_id", "determined"],
    )
    national_result = upsert_rows_to_csv(
        csv_path=national_career_csv,
        fieldnames=NATIONAL_CAREER_FIELDNAMES,
        rows=national_rows,
        key_fields=["competition_id", "team_season", "player_id", "national_team_id", "career_state"],
    )
    absence_result = upsert_rows_to_csv(
        csv_path=absence_history_csv,
        fieldnames=ABSENCE_HISTORY_FIELDNAMES,
        rows=absence_rows,
        key_fields=["competition_id", "team_season", "player_id", "absence_id"],
    )
    errors_result = upsert_rows_to_csv(
        csv_path=errors_csv,
        fieldnames=PLAYER_ERRORS_FIELDNAMES,
        rows=error_rows,
        key_fields=["competition_id", "team_season", "player_id", "error"],
    )

    return {
        "players_requested": str(len(contexts)),
        "player_data_csv": player_data_csv,
        "transfer_history_csv": transfer_history_csv,
        "market_value_history_csv": market_value_history_csv,
        "national_career_csv": national_career_csv,
        "absence_history_csv": absence_history_csv,
        "errors_csv": errors_csv,
        "player_rows_total": str(player_result["rows_total"]),
        "player_rows_inserted": str(player_result["inserted"]),
        "transfer_rows_total": str(transfer_result["rows_total"]),
        "market_value_rows_total": str(market_value_result["rows_total"]),
        "national_rows_total": str(national_result["rows_total"]),
        "absence_rows_total": str(absence_result["rows_total"]),
        "errors_rows_total": str(errors_result["rows_total"]),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Scrape EURO 2024 player data and save normalized datasets to separate CSV files."
        )
    )
    parser.add_argument(
        "--team-players-csv",
        default="data/team_players.csv",
        help="Input team players CSV (default: data/team_players.csv)",
    )
    parser.add_argument(
        "--player-data-csv",
        default="data/player_data.csv",
        help="Output player data CSV (default: data/player_data.csv)",
    )
    parser.add_argument(
        "--transfer-history-csv",
        default="data/player_transfer_history.csv",
        help="Output transfer history CSV (default: data/player_transfer_history.csv)",
    )
    parser.add_argument(
        "--market-value-history-csv",
        default="data/player_market_value_history.csv",
        help="Output market value history CSV (default: data/player_market_value_history.csv)",
    )
    parser.add_argument(
        "--national-career-csv",
        default="data/player_national_career.csv",
        help="Output national career CSV (default: data/player_national_career.csv)",
    )
    parser.add_argument(
        "--absence-history-csv",
        default="data/player_absence_history.csv",
        help="Output absence history CSV (default: data/player_absence_history.csv)",
    )
    parser.add_argument(
        "--errors-csv",
        default="data/errors/player_errors.csv",
        help="Output player errors CSV (default: data/errors/player_errors.csv)",
    )
    parser.add_argument(
        "--competition-id",
        default="EURO",
        help="Competition id tag for output rows (default: EURO)",
    )
    parser.add_argument(
        "--team-season",
        default="2024",
        help="Team season tag for output rows (default: 2024)",
    )
    parser.add_argument(
        "--team-id",
        default=None,
        help="Optional single team id filter.",
    )
    parser.add_argument(
        "--player-id",
        default=None,
        help="Optional single player id filter.",
    )
    parser.add_argument(
        "--player-url",
        default=None,
        help="Optional direct player URL (overrides team players source).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.1,
        help="Delay in seconds between players (default: 0.1)",
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

    result = export_players_to_csv(
        team_players_csv=args.team_players_csv,
        player_data_csv=args.player_data_csv,
        transfer_history_csv=args.transfer_history_csv,
        market_value_history_csv=args.market_value_history_csv,
        national_career_csv=args.national_career_csv,
        absence_history_csv=args.absence_history_csv,
        errors_csv=args.errors_csv,
        competition_id=args.competition_id,
        team_season=args.team_season,
        team_id=args.team_id,
        player_id=args.player_id,
        player_url=args.player_url,
        request_delay_seconds=args.delay,
    )

    print(f"Players requested: {result['players_requested']}")
    print(f"Player data CSV: {result['player_data_csv']}")
    print(f"Transfer history CSV: {result['transfer_history_csv']}")
    print(f"Market value history CSV: {result['market_value_history_csv']}")
    print(f"National career CSV: {result['national_career_csv']}")
    print(f"Absence history CSV: {result['absence_history_csv']}")
    print(f"Errors CSV: {result['errors_csv']}")
    print(f"Player rows total: {result['player_rows_total']}")
    print(f"Player rows inserted: {result['player_rows_inserted']}")
    print(f"Transfer rows total: {result['transfer_rows_total']}")
    print(f"Market value rows total: {result['market_value_rows_total']}")
    print(f"National rows total: {result['national_rows_total']}")
    print(f"Absence rows total: {result['absence_rows_total']}")
    print(f"Errors rows total: {result['errors_rows_total']}")
