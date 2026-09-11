# Web Platform (Wyscout Integration)

> 🔗 **Corresponding README in original repository:** [Contextual-Football-Scouting/webapp/README.md](https://github.com/ArMat-Analytics/Contextual-Football-Scouting/blob/main/webapp/README.md)

---

## Changes in this Fork

This directory houses the full-stack web application adapted for **Wyscout seasonal aggregated data (`data/wyscout_sample.csv`)**:

1. **100% In-Memory Backend (No External Database)**:
   - **Original Implementation**: Required a PostgreSQL / Supabase database instance, SQL schema migrations, and manual CSV import scripts (`supabase_importer.py`, `import_decision_quality.py`, `import_off_ball.py`, etc.).
   - **Wyscout Fork Adaptation**: Operates completely in-memory. The FastAPI backend (`webapp/backend/data_module.py`) ingests `data/wyscout_sample.csv` upon startup, computing all within-role percentiles, DQI metrics, and pairwise similarity lookups in RAM with sub-5ms latency.

2. **Expanded Player Pool**:
   - Scales the interactive platform from the original 272 tournament players to **1,697 total players** (1,059 outfield players meeting the $\ge 300$ minutes threshold).

3. **Frontend Refinements**:
   - Upgraded to React 19 and Vite with unified environment resolution (`webapp/backend/.env`).
   - Removed legacy tracking components (H3 Off-Ball movement sections, Supabase client code).
   - Display surfaces the Wyscout proxy families: Space Control (H1), Decision Quality (H2), and 8-axis Style DNA (H4).

---

## Quick Start

```bash
# 1. Start Backend (FastAPI)
cd webapp/backend
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000

# 2. Start Frontend (React 19)
cd webapp/frontend
npm install
npm run dev
```
