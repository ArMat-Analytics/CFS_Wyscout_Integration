# Frontend Application (Wyscout Integration)

> 🔗 **Corresponding README in original repository:** [Contextual-Football-Scouting/webapp/README.md](https://github.com/ArMat-Analytics/Contextual-Football-Scouting/blob/main/webapp/README.md)

---

## Changes in this Fork

This directory contains the React 19 + Vite dashboard adapted for the **Wyscout Integration**:

1. **Interface & Metric Updates**:
   - **Home Page**: Updated with fork attribution, direct link to the original repository, and a concise summary of the Wyscout proxy integration.
   - **Player Cards & Radars**: Visualizes Wyscout proxy indices for Space Control (H1) and Decision Quality (H2), alongside raw seasonal metrics.
   - **Similar Players (H4)**: Displays the 8-axis stylistic DNA radar overlays and look-alikes.
   - **Removed Legacy Features**: Removed H3 Off-Ball Movement tabs and sections (which required tracking coordinates).

2. **Standalone Client Architecture**:
   - Built on React 19, TypeScript, Tailwind CSS, and Recharts.
   - Operates completely decoupled from external cloud databases, fetching directly from the local FastAPI in-memory backend.

---

## Quick Start

```bash
npm install
npm run dev
```

The frontend will run on `http://localhost:5173`.
