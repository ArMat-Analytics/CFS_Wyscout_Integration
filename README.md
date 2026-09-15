<div align="center">

<img src="docs/barca-innovation-hub-logo.jpg" alt="Contextual Football Scouting" width="160"/>

# Contextual Football Scouting (Wyscout Integration)

[![Fork of: Contextual-Football-Scouting](https://img.shields.io/badge/Fork%20of-Contextual--Football--Scouting-0284c7?logo=github)](https://github.com/ArMat-Analytics/Contextual-Football-Scouting)
[![License: MIT](https://img.shields.io/github/license/ArMat-Analytics/CFS_Wyscout_Integration?label=License)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.14.3-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-In--Memory-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=white)](https://react.dev)
[![Data: Wyscout](https://img.shields.io/badge/Data-Wyscout%20(wyscout__sample.csv)-0284c7)](webapp/backend/data/wyscout_sample.csv)

**Ranking players by *what they do with the space around them*, not by how much they touch the ball.**

*Matteo Vezzoli & Armando Mio — 2026*

</div>

---

> ℹ️ **Fork Notice**: This repository is a dedicated **fork** of **[Contextual Football Scouting](https://github.com/ArMat-Analytics/Contextual-Football-Scouting)**.  
> The complete theoretical framework, mathematical proofs, academic paper, and original tracking-data methodology (StatsBomb 360) are documented in the main repository:  
> 🔗 **Corresponding README in the original repository:** [Contextual-Football-Scouting/README.md](https://github.com/ArMat-Analytics/Contextual-Football-Scouting/blob/main/README.md)

---

## Changes in this Fork

This fork adapts the contextual scouting methodology to work with **Wyscout seasonal aggregated data (`webapp/backend/data/wyscout_sample.csv`)**:

1. **Wyscout Statistical Proxies**:
   - **[H1 — Space Control & Value](H1_Space_Control_and_Value/)**: Replaced 360° convex hull geometry with seasonal proxies for Progression (`Progressive passes/90`, `Progressive runs/90`, `Passes to final 3rd/90`), Reception (`Touches in box/90`, `Received passes/90`), Gravity (`Fouls suffered/90`, `Offensive duels/90`), and Dangerousness (`xG/90`, `xA/90`).
   - **[H2 — Decision Quality](H2_Decision_Quality/)**: Replaced event-level freeze-frame xPass/xEPV models with a Decision Quality Index (DQI) evaluated across Possession Accuracy, Duel Robustness, Risk Readings /90 (`Key passes/90` + `Smart passes/90`), and Risk Accuracy (`Accurate progressive passes, %`).
   - **H3 (Off-Ball Movement)**: Excluded, as off-ball runs and receiver resolution require spatial tracking coordinates not present in seasonal aggregated data.
   - **[H4 — Player Similarity](H4_Player_Similarity/)**: Replaced the 11-axis tracking DNA with an 8-axis orthogonal style DNA combining H1 and H2, computing within-role Euclidean distance look-alikes across 1,059 eligible players.

2. **100% In-Memory Full-Stack Webapp**:
   - Replaced PostgreSQL / Supabase and offline DB migration scripts with a lightweight in-memory **FastAPI backend** (`webapp/backend/data_module.py`) that loads `webapp/backend/data/wyscout_sample.csv` directly on startup.
   - Sub-5ms response times across all endpoints (`/players/`, `/similar/`, `/roles/`, and `/space-control/`).
   - Modern **React 19 + Vite frontend** with responsive radars, multi-criteria filtering, and head-to-head similarity overlays.

3. **Expanded Player Pool**:
   - Expanded the evaluation pool from 272 players (StatsBomb 360 minutes threshold) to **1,697 total players** (1,059 outfield players with $\ge 300$ minutes) from the Wyscout seasonal sample dataset.

---

<div align="center">

*Original Project: [ArMat-Analytics/Contextual-Football-Scouting](https://github.com/ArMat-Analytics/Contextual-Football-Scouting)*

</div>
