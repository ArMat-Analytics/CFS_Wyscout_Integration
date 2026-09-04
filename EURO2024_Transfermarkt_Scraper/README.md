# Contextual Football Scouting - Quick Scraper Guide

This repository contains 4 standalone scrapers and 1 master scraper.

All Python scripts are located in the `code/` directory.

All outputs are written to the `data/` directory and are updated incrementally.

Incremental update rule:
- Existing rows are not duplicated.
- Existing non-empty values are preserved.
- Missing values are filled when new data is available.

## Requirements

- Python 3.10+
- Internet access

Optional setup:

```bash
python -m venv .venv
.venv\Scripts\activate
```

## 1) teams_scraper.py

Purpose:
- Scrape all EURO 2024 participating teams from Transfermarkt.

Default output:
- `data/teams.csv`

Run:

```bash
python code/teams_scraper.py
```

Useful options:

```bash
python code/teams_scraper.py --season 2024 --competition-id EURO --output data/teams.csv
```

## 2) team_data_scraper.py

Purpose:
- Scrape team-level EURO data.
- Scrape team squad players used as input for player scraping.

Default outputs:
- `data/team_data.csv`
- `data/team_players.csv`
- `data/errors/team_errors.csv`

Run:

```bash
python code/team_data_scraper.py
```

Useful options:

```bash
python code/team_data_scraper.py --team-id 3262
```

## 3) matches_scraper.py

Purpose:
- Scrape EURO home matches for each team.
- Keep only rows where the source team is the home team.

Default outputs:
- `data/team_matches.csv`
- `data/errors/match_errors.csv`

Run:

```bash
python code/matches_scraper.py
```

Useful options:

```bash
python code/matches_scraper.py --team-id 3262
```

## 4) player_scraper.py

Purpose:
- Scrape normalized player datasets (no generic page labels or navigation text).
- Split repeated/multi-value domains into dedicated CSV files.

Default outputs:
- `data/player_data.csv`
- `data/player_transfer_history.csv`
- `data/player_market_value_history.csv`
- `data/player_national_career.csv`
- `data/player_absence_history.csv`
- `data/errors/player_errors.csv`

Run with team players source:

```bash
python code/player_scraper.py
```

Run for one player URL:

```bash
python code/player_scraper.py --player-url "https://www.transfermarkt.com/player-name/profil/spieler/12345"
```

## 5) main.py (Master Scraper)

Purpose:
- Run the full pipeline in this exact order:
  1. Teams (EURO participants)
  2. Team data + team players
  3. Team home matches
  4. Player datasets

Run full pipeline:

```bash
python code/main.py
```

Run pipeline for one team only:

```bash
python code/main.py --team-id 3262
```

## Notes

- The pipeline is configured for EURO 2024 by default:
  - `--competition-id EURO`
  - `--participants-season 2024`
  - `--team-season 2024`
- All scripts support incremental CSV updates.
- Use `--verbose` on any script for debug logs.
