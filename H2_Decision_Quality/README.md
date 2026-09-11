# H2 — Decision Quality (Wyscout Integration)

> 🔗 **Corresponding README in original repository:** [Contextual-Football-Scouting/H2_Decision_Quality/README.md](https://github.com/ArMat-Analytics/Contextual-Football-Scouting/blob/main/H2_Decision_Quality/README.md)

---

## Changes in this Fork

This folder adapts **Hypothesis 2 (Decision Quality)** from the original StatsBomb 360 tracking-data implementation to **Wyscout seasonal aggregated data (`webapp/backend/data/wyscout_sample.csv`)**:

1. **Shift to Statistical Proxies**:
   - **Original Implementation**: Trained a supervised Gradient Boosting model (`xPass`) on 30,913 freeze frames and reconstructed 222,274 in-frame alternative pass candidates to calculate decision regret and `xEPV` choice quality.
   - **Wyscout Fork Adaptation**: Replaces event-level alternative sets with a **Decision Quality Index (DQI) proxy** based on technical accuracy and creative risk execution from Wyscout data:
     - **Possession Accuracy**: `Accurate passes, %` (within-role percentile).
     - **Duel Robustness**: `Duels won, %` (within-role percentile).
     - **Risk Readings /90**: Incisive actions/90 (`Key passes/90` + `Smart passes/90`, within-role percentile).
     - **Risk Accuracy**: `Accurate progressive passes, %` (within-role percentile).
     - **Companion Value Impact**: Mean percentile of `Expected goals/90` and `Expected assists/90`.

2. **Pipeline Simplification**:
   - Consolidated the two original machine-learning notebooks into a single, self-contained notebook: `notebooks/H2-Decision_Quality.ipynb`.
   - Eliminated heavy dependencies on trained `.joblib` models, `alternatives.parquet` files, and raw 360-frame caches.
