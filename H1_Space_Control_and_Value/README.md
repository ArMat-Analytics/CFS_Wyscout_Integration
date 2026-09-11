# H1 — Space Control and Value (Wyscout Integration)

> 🔗 **Corresponding README in original repository:** [Contextual-Football-Scouting/H1_Space_Control_and_Value/README.md](https://github.com/ArMat-Analytics/Contextual-Football-Scouting/blob/main/H1_Space_Control_and_Value/README.md)

---

## Changes in this Fork

This folder adapts **Hypothesis 1 (Space Control and Value)** from the original StatsBomb 360 tracking-data implementation to **Wyscout seasonal aggregated data (`webapp/backend/data/wyscout_sample.csv`)**:

1. **Shift to Statistical Proxies**:
   - **Original Implementation**: Constructed 360° convex hulls of the defensive block, line-breaking corridor passes, and event-level Expected Possession Value (EPV) grids from tracking freeze frames.
   - **Wyscout Fork Adaptation**: Replaces frame geometry with within-role percentiles of seasonal statistical proxies:
     - **PROGRESSION**: Mean percentile of `Progressive passes/90`, `Progressive runs/90`, and `Passes to final third/90`.
     - **DANGEROUSNESS**: Mean percentile of `Expected goals/90` and `Expected assists/90`.
     - **RECEPTION**: Mean percentile of `Touches in box/90`, `Received passes/90`, and `Deep completions/90`.
     - **GRAVITY**: Mean percentile of `Fouls suffered/90` and `Offensive duels/90` (proxy for defensive attention drawn).

2. **Pipeline Simplification**:
   - Replaced complex multi-stage event pipelines (hull metrics, directional gravity, line breakers) with standalone in-memory percentile computations.
   - Analysis migrated to `notebooks/H1-Space_Control_and_Value.ipynb` and `notebooks/H1-Variable_Redundancy_Analysis.ipynb`.
   - Removed 360-frame event cache requirements and external coordinate grids.
