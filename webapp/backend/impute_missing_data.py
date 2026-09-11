"""
impute_missing_data.py — Impute missing/unavailable Foot and Market Value
in wyscout_sample.csv using machine learning models and realistic football heuristics.
"""
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingRegressor


def main():
    csv_path = Path("webapp/backend/data/wyscout_sample.csv")
    df = pd.read_csv(csv_path, low_memory=False)
    print(f"Loaded dataset: {df.shape} from {csv_path}")

    # Backup original before modifying
    backup_path = csv_path.with_name("wyscout_sample_raw.csv")
    if not backup_path.exists():
        df.to_csv(backup_path, index=False)
        print(f"Created backup at {backup_path}")

    # ──────────────────────────────────────────────────────────────────────────
    # 1. IMPUTE FOOT
    # ──────────────────────────────────────────────────────────────────────────
    known_mask = df["Foot"].astype(str).str.lower().isin(["right", "left", "both"])
    print(f"Foot: {known_mask.sum()} known, {(~known_mask).sum()} missing/unknown")

    # Feature extraction for Foot
    def get_foot_features(data: pd.DataFrame) -> pd.DataFrame:
        pos = data["Position"].astype(str)
        feats = pd.DataFrame(index=data.index)
        feats["is_lb"] = pos.str.contains(r"\bLB\b|\bLWB\b", regex=True).astype(float)
        feats["is_rb"] = pos.str.contains(r"\bRB\b|\bRWB\b", regex=True).astype(float)
        feats["is_lcb"] = pos.str.contains(r"\bLCB\b", regex=True).astype(float)
        feats["is_rcb"] = pos.str.contains(r"\bRCB\b", regex=True).astype(float)
        feats["is_lw"] = pos.str.contains(r"\bLW\b|\bLWF\b|\bLAMF\b", regex=True).astype(float)
        feats["is_rw"] = pos.str.contains(r"\bRW\b|\bRWF\b|\bRAMF\b", regex=True).astype(float)
        feats["is_cf"] = pos.str.contains(r"\bCF\b|\bSS\b", regex=True).astype(float)
        feats["is_gk"] = pos.str.contains(r"\bGK\b", regex=True).astype(float)
        feats["cross_l"] = pd.to_numeric(data["Crosses from left flank/90"], errors="coerce").fillna(0)
        feats["cross_r"] = pd.to_numeric(data["Crosses from right flank/90"], errors="coerce").fillna(0)
        feats["cross_l_acc"] = pd.to_numeric(data["Accurate crosses from left flank, %"], errors="coerce").fillna(0)
        feats["cross_r_acc"] = pd.to_numeric(data["Accurate crosses from right flank, %"], errors="coerce").fillna(0)
        return feats

    X_foot_train = get_foot_features(df[known_mask])
    y_foot_train = df.loc[known_mask, "Foot"].astype(str).str.lower()
    X_foot_missing = get_foot_features(df[~known_mask])

    clf_foot = RandomForestClassifier(n_estimators=150, max_depth=5, random_state=42)
    clf_foot.fit(X_foot_train, y_foot_train)

    imputed_feet = clf_foot.predict(X_foot_missing)
    # Apply deterministic overrides for pure LB/LWB and pure RB/RWB
    for idx, (orig_idx, row) in enumerate(df[~known_mask].iterrows()):
        pos = str(row["Position"])
        if pos in ["LB", "LWB"] or (pos.startswith("LB") and "RB" not in pos):
            imputed_feet[idx] = "left"
        elif pos in ["RB", "RWB"] or (pos.startswith("RB") and "LB" not in pos):
            imputed_feet[idx] = "right"

    df.loc[~known_mask, "Foot"] = imputed_feet
    print(f"Foot imputation complete. New distribution:\n{df['Foot'].value_counts()}")

    # ──────────────────────────────────────────────────────────────────────────
    # 2. IMPUTE MARKET VALUE
    # ──────────────────────────────────────────────────────────────────────────
    mv_num = pd.to_numeric(df["Market value"], errors="coerce").fillna(0)
    has_mv_mask = mv_num > 0
    print(f"\nMarket Value: {has_mv_mask.sum()} positive, {(~has_mv_mask).sum()} zero/missing")

    # Calculate team-level priors
    team_medians = df[has_mv_mask].groupby("Team")["Market value"].median()
    overall_median = df[has_mv_mask]["Market value"].median()

    def get_mv_features(data: pd.DataFrame) -> pd.DataFrame:
        feats = pd.DataFrame(index=data.index)
        feats["team_log_med"] = np.log(data["Team"].map(team_medians).fillna(overall_median))

        age = pd.to_numeric(data["Age"], errors="coerce").fillna(26)
        feats["age"] = age
        feats["age_diff_peak"] = (age - 26).clip(-8, 12)
        feats["age_sq"] = (age - 26) ** 2

        mins = pd.to_numeric(data["Minutes played"], errors="coerce").fillna(0)
        feats["log_mins"] = np.log1p(mins)
        feats["mins_ratio"] = (mins / 900.0).clip(upper=2.5)

        # Offensive impact
        feats["goals"] = pd.to_numeric(data["Goals"], errors="coerce").fillna(0)
        feats["xg"] = pd.to_numeric(data["Expected goals"], errors="coerce").fillna(0)
        feats["assists"] = pd.to_numeric(data["Assists"], errors="coerce").fillna(0)
        feats["xa"] = pd.to_numeric(data["Expected assists"], errors="coerce").fillna(0)

        # Quality metrics
        feats["passes90"] = pd.to_numeric(data["Passes/90"], errors="coerce").fillna(30)
        feats["prog_passes90"] = pd.to_numeric(data["Progressive passes/90"], errors="coerce").fillna(3)
        feats["key_passes90"] = pd.to_numeric(data["Key passes/90"], errors="coerce").fillna(0.3)
        feats["duels_pct"] = pd.to_numeric(data["Duels won, %"], errors="coerce").fillna(50)

        pos = data["Position"].astype(str)
        feats["is_fw"] = pos.str.contains(r"CF|SS|RW|LW|RWF|LWF", regex=True).astype(float)
        feats["is_mid"] = pos.str.contains(r"CMF|DMF|AMF|LAMF|RAMF", regex=True).astype(float)
        feats["is_def"] = pos.str.contains(r"CB|LB|RB|LCB|RCB|LWB|RWB", regex=True).astype(float)
        feats["is_gk"] = pos.str.contains(r"GK", regex=True).astype(float)
        return feats

    X_mv_train = get_mv_features(df[has_mv_mask])
    y_mv_train = np.log(pd.to_numeric(df.loc[has_mv_mask, "Market value"]))
    X_mv_missing = get_mv_features(df[~has_mv_mask])

    gbr = GradientBoostingRegressor(n_estimators=150, max_depth=3, learning_rate=0.08, random_state=42)
    gbr.fit(X_mv_train, y_mv_train)

    pred_log_mv = gbr.predict(X_mv_missing)
    raw_mv = np.exp(pred_log_mv)

    def round_market_value(val: float) -> int:
        val = max(50_000, float(val))
        if val < 200_000:
            return int(round(val / 25_000) * 25_000)
        elif val < 1_000_000:
            return int(round(val / 50_000) * 50_000)
        elif val < 3_000_000:
            return int(round(val / 100_000) * 100_000)
        elif val < 8_000_000:
            return int(round(val / 250_000) * 250_000)
        else:
            return int(round(val / 500_000) * 500_000)

    rounded_mv = [round_market_value(v) for v in raw_mv]
    df.loc[~has_mv_mask, "Market value"] = rounded_mv
    print("Market value imputation complete.")
    print(f"New Market Value summary:\n{df['Market value'].describe()}")

    # ──────────────────────────────────────────────────────────────────────────
    # 3. IMPUTE HEIGHT AND WEIGHT (WHERE 0)
    # ──────────────────────────────────────────────────────────────────────────
    zero_height = (df["Height"] <= 0) | df["Height"].isna()
    zero_weight = (df["Weight"] <= 0) | df["Weight"].isna()
    print(f"\nHeight: {zero_height.sum()} zeros, Weight: {zero_weight.sum()} zeros")

    pos_height_medians = {
        "GK": 188, "CB": 187, "LCB": 187, "RCB": 187,
        "LB": 178, "RB": 178, "LWB": 178, "RWB": 178,
        "DMF": 182, "CMF": 180, "LCMF": 180, "RCMF": 180,
        "AMF": 177, "LAMF": 176, "RAMF": 176, "LW": 177, "RW": 177,
        "CF": 185, "SS": 180,
    }
    pos_weight_medians = {
        "GK": 82, "CB": 80, "LCB": 80, "RCB": 80,
        "LB": 73, "RB": 73, "LWB": 72, "RWB": 72,
        "DMF": 76, "CMF": 74, "LCMF": 74, "RCMF": 74,
        "AMF": 71, "LAMF": 70, "RAMF": 70, "LW": 72, "RW": 72,
        "CF": 79, "SS": 75,
    }

    rng = np.random.default_rng(42)
    for idx in df[zero_height].index:
        p0 = str(df.loc[idx, "Position"]).split(",")[0].strip()
        h_base = pos_height_medians.get(p0, 181)
        df.loc[idx, "Height"] = int(h_base + rng.integers(-3, 4))

    for idx in df[zero_weight].index:
        p0 = str(df.loc[idx, "Position"]).split(",")[0].strip()
        w_base = pos_weight_medians.get(p0, 75)
        df.loc[idx, "Weight"] = int(w_base + rng.integers(-3, 4))

    # Save to wyscout_sample.csv
    df.to_csv(csv_path, index=False)
    print(f"\nSuccessfully saved updated dataset to {csv_path}")


if __name__ == "__main__":
    main()
