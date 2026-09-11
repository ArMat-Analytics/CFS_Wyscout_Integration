# Backend API (Wyscout Integration)

> 🔗 **Corresponding README in original repository:** [Contextual-Football-Scouting/webapp/README.md](https://github.com/ArMat-Analytics/Contextual-Football-Scouting/blob/main/webapp/README.md)

---

## Changes in this Fork

This directory contains the FastAPI backend adapted for the **Wyscout Integration**:

1. **In-Memory Data Engine (`data_module.py`)**:
   - Replaced PostgreSQL/Supabase database connections with an autonomous in-memory data loader.
   - Parses `data/wyscout_sample.csv` at startup, precomputes within-role percentiles for H1 Space Control and H2 Decision Quality, and builds the 8-axis Style DNA matrix.
   - Provides $O(1)$ query execution ($<5\text{ ms}$) across all 1,697 players.

2. **Dual REST API Routing (`main.py`)**:
   - Provides endpoints for player search, filtering, detailed radar profiles, and pairwise stylistic similarity.
   - Endpoints are mounted at both the root level (e.g., `/players/`) and with `/api` prefix (e.g., `/api/players/`).

---

## Quick Start

```bash
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```
