import csv
import html
import json
import logging
import random
import re
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE_DOMAIN = "https://www.transfermarkt.com"

BASE_HEADERS = {
    "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
    "cache-control": "no-cache",
    "origin": BASE_DOMAIN,
    "pragma": "no-cache",
}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:147.0) Gecko/20100101 Firefox/147.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
]

TAG_RE = re.compile(r"<[^>]+>")


def configure_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    if logging.getLogger().handlers:
        logging.getLogger().setLevel(level)
        return

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )


def request_text(
    url: str,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 30,
    max_retries: int = 4,
) -> str:
    request_url = url
    if params:
        query = urlencode(params, doseq=True)
        separator = "&" if "?" in request_url else "?"
        request_url = f"{request_url}{separator}{query}"

    merged_headers = {
        **BASE_HEADERS,
        "user-agent": random.choice(USER_AGENTS),
    }
    if headers:
        merged_headers.update(headers)

    retryable_status = {429, 500, 502, 503, 504}
    last_error: Optional[Exception] = None

    for attempt in range(max_retries + 1):
        req = Request(url=request_url, headers=merged_headers, method="GET")
        try:
            with urlopen(req, timeout=timeout) as response:
                return response.read().decode("utf-8", errors="replace")
        except HTTPError as exc:
            if exc.code in retryable_status and attempt < max_retries:
                time.sleep(0.7 * (2**attempt))
                continue
            body = exc.read().decode("utf-8", errors="replace")
            last_error = RuntimeError(f"HTTP {exc.code} from {request_url}: {body[:300]}")
            break
        except URLError as exc:
            if attempt < max_retries:
                time.sleep(0.7 * (2**attempt))
                continue
            last_error = RuntimeError(f"Network error from {request_url}: {exc.reason}")
            break

    if last_error:
        raise last_error
    raise RuntimeError(f"Request failed with unknown error: {request_url}")


def request_json(
    url: str,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 30,
    max_retries: int = 4,
) -> Any:
    text = request_text(
        url=url,
        params=params,
        headers=headers,
        timeout=timeout,
        max_retries=max_retries,
    )
    return json.loads(text)


def clean_text(html_fragment: str) -> str:
    text = TAG_RE.sub(" ", html_fragment)
    text = html.unescape(text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_first_group(
    text: str,
    patterns: Sequence[str],
    use_dotall: bool = False,
) -> str:
    flags = re.IGNORECASE | (re.DOTALL if use_dotall else 0)
    for pattern in patterns:
        match = re.search(pattern, text, flags=flags)
        if match:
            return match.group(1).strip()
    return ""


def extract_href(html_fragment: str) -> str:
    return extract_first_group(html_fragment, [r'href="([^"]+)"'])


def extract_id_from_path(path: str, pattern: str) -> str:
    return extract_first_group(path, [pattern])


def to_csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float, str)):
        return str(value)
    return json.dumps(value, ensure_ascii=False)


def ensure_parent_dir(file_path: str) -> None:
    Path(file_path).parent.mkdir(parents=True, exist_ok=True)


def read_csv_rows(csv_path: str) -> Tuple[List[str], List[Dict[str, str]]]:
    file = Path(csv_path)
    if not file.exists():
        return [], []

    with file.open("r", newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        rows = [dict(row) for row in reader]
        return list(reader.fieldnames or []), rows


def _build_key(row: Dict[str, str], key_fields: Sequence[str]) -> Tuple[str, ...]:
    return tuple(str(row.get(field, "")).strip() for field in key_fields)


def _merge_row_prefer_existing(
    existing_row: Dict[str, str],
    new_row: Dict[str, str],
    fieldnames: Sequence[str],
) -> Dict[str, str]:
    merged = {field: existing_row.get(field, "") for field in fieldnames}
    for field in fieldnames:
        incoming = new_row.get(field, "")
        current = merged.get(field, "")

        # Update only missing values: keep existing non-empty values stable.
        if not current and incoming:
            merged[field] = incoming

    return merged


def upsert_rows_to_csv(
    csv_path: str,
    fieldnames: Sequence[str],
    rows: Iterable[Dict[str, Any]],
    key_fields: Sequence[str],
) -> Dict[str, Any]:
    ensure_parent_dir(csv_path)

    existing_fieldnames, existing_rows = read_csv_rows(csv_path)
    incoming_rows = list(rows)

    merged_fieldnames: List[str] = []
    for field in list(existing_fieldnames) + list(fieldnames):
        if field and field not in merged_fieldnames:
            merged_fieldnames.append(field)

    for row in incoming_rows:
        for key in row.keys():
            if key not in merged_fieldnames:
                merged_fieldnames.append(key)

    for key_field in key_fields:
        if key_field not in merged_fieldnames:
            merged_fieldnames.append(key_field)

    existing_by_key: Dict[Tuple[str, ...], Dict[str, str]] = {}
    existing_without_key: List[Dict[str, str]] = []

    for row in existing_rows:
        normalized = {field: to_csv_value(row.get(field, "")) for field in merged_fieldnames}
        row_key = _build_key(normalized, key_fields)
        if any(row_key):
            if row_key not in existing_by_key:
                existing_by_key[row_key] = normalized
            else:
                existing_by_key[row_key] = _merge_row_prefer_existing(
                    existing_row=existing_by_key[row_key],
                    new_row=normalized,
                    fieldnames=merged_fieldnames,
                )
        else:
            existing_without_key.append(normalized)

    inserted = 0
    updated = 0
    skipped = 0

    for row in incoming_rows:
        normalized = {field: to_csv_value(row.get(field, "")) for field in merged_fieldnames}
        row_key = _build_key(normalized, key_fields)
        if not any(row_key):
            skipped += 1
            continue

        existing = existing_by_key.get(row_key)
        if existing is None:
            existing_by_key[row_key] = normalized
            inserted += 1
            continue

        merged = _merge_row_prefer_existing(
            existing_row=existing,
            new_row=normalized,
            fieldnames=merged_fieldnames,
        )
        if merged != existing:
            updated += 1
        else:
            skipped += 1
        existing_by_key[row_key] = merged

    keyed_rows = sorted(
        existing_by_key.values(),
        key=lambda row: tuple(row.get(field, "") for field in key_fields),
    )
    output_rows = existing_without_key + keyed_rows

    with open(csv_path, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=merged_fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    return {
        "path": csv_path,
        "rows_total": len(output_rows),
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
    }


def find_first_navigation_link(
    payload: Any,
    tracks: Sequence[str],
    texts: Sequence[str],
    path_fragments: Sequence[str],
) -> str:
    tracks_set = {value.lower() for value in tracks}
    texts_set = {value.lower() for value in texts}
    path_fragments_set = {value.lower() for value in path_fragments}

    def _walk(node: Any) -> Optional[str]:
        if isinstance(node, dict):
            text = str(node.get("text", "")).strip().lower()
            track = str(node.get("track", "")).strip().lower()
            link = node.get("link")

            if isinstance(link, str) and link.startswith("/"):
                lower_link = link.lower()
                if track in tracks_set or text in texts_set:
                    return link
                if any(fragment in lower_link for fragment in path_fragments_set):
                    return link

            for value in node.values():
                found = _walk(value)
                if found:
                    return found
            return None

        if isinstance(node, list):
            for item in node:
                found = _walk(item)
                if found:
                    return found
            return None

        return None

    found = _walk(payload)
    if not found:
        raise RuntimeError("Unable to find expected navigation link in sub-navigation payload.")
    return found
