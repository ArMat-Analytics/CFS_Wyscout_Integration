# H4 — Player Similarity (Wyscout Integration)

> 🔗 **Corresponding README in original repository:** [Contextual-Football-Scouting/H4_Player_Similarity/README.md](https://github.com/ArMat-Analytics/Contextual-Football-Scouting/blob/main/H4_Player_Similarity/README.md)

---

## Changes in this Fork

This folder adapts **Hypothesis 4 (Player Similarity)** from the original implementation to **Wyscout seasonal aggregated data (`webapp/backend/data/wyscout_sample.csv`)**:

1. **8-Axis Stylistic DNA**:
   - **Original Implementation**: Assembled an 11-axis DNA vector by joining outputs across H1 (Space Control), H2 (Decision Quality), and H3 (Off-Ball Movement tracking runs).
   - **Wyscout Fork Adaptation**: Constructs an **8-axis orthogonal style DNA** generated directly from `webapp/backend/data/wyscout_sample.csv`:
     - **4 Space Control Axes (H1)**: Progression, Dangerousness, Reception, Gravity.
     - **4 Decision Quality Axes (H2)**: Possession Accuracy, Duel Robustness, Risk Readings, Risk Accuracy.
     - *(H3 Off-Ball metrics are excluded due to the absence of raw player tracking trajectories in seasonal data).*

2. **Autonomous & In-Memory Pipeline**:
   - Maintains the within-role normalized Euclidean distance metric and invariant 0–100 similarity score.
   - Computes DNA vectors and pairwise nearest neighbours directly on-the-fly in `notebooks/H4-Player_Similarity.ipynb` and `src/similarity.py` without requiring intermediate CSV files from other hypothesis folders.
   - Expanded to 1,059 eligible outfield players ($\ge 300$ minutes).
