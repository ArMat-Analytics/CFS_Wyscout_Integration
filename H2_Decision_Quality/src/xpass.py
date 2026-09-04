"""xPass — P(complete | features), with three interchangeable models.

Three model families share one CV / OOF / diagnostics pipeline:

    "logit"           L2 logistic regression on standardised features.
                      Interpretable coefficients — the academic baseline.
    "logit_balanced"  Same logistic, with class_weight='balanced' to give
                      failed passes more influence on the loss.
    "gbm"             HistGradientBoostingClassifier (sklearn). Captures
                      non-linearities and feature interactions that the
                      linear model cannot. Trained with log-loss, usually
                      well-calibrated out of the box.

All three are evaluated with the same 5-fold GroupKFold split on `match_id`
so AUC / log-loss / Brier and the OOF probability vector are directly
comparable. `compare_models` runs the three side-by-side and returns one
table plus stacked OOF predictions for plotting.

Public API
----------
cross_validate(features_df, kind=...)      per-fold metrics
fit_full(features_df, kind=...)            train on all matches
predict_proba(model, features_df)          1-D ndarray
oof_predictions(features_df, kind=...)     features_df + xpass_oof + fold

coefficient_table(model)                   logistic only — odds ratios
metrics_by_segment(features_df, kind=...)  AUC etc. on sub-populations
decile_calibration(features_df, kind=...)  10-bin lift table
confusion_at_threshold(features_df, t,...) 2x2 + precision / recall

compare_models(features_df, kinds=...)     -> (metrics_df, oof_long_df)
plot_calibration(features_df, kind=...)    reliability diagram
plot_decile_calibration(features_df, ...)  bar chart of decile cal
plot_oof_distribution(features_df, ...)    histogram by class
plot_model_comparison(oof_long_df)         calibration overlay + OOF range

Calibrated production model
---------------------------
oof_predictions_calibrated(features_df, kind=...)  -> OOF + isotonic + clip
fit_calibrated(features_df, kind=...)              -> CalibratedXPass instance
calibration_summary(oof_calibrated)                -> raw vs calibrated stats
plot_calibration_effect(oof_calibrated)            -> before/after plot

`CalibratedXPass.predict_proba(features_df)` is the entry point downstream
modules (xEPV, decision-quality index) should use to obtain realistic,
bounded P(complete) values that avoid pathological 0 / 1 saturation.
"""
from __future__ import annotations

from typing import Sequence

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    brier_score_loss,
    log_loss,
    roc_auc_score,
)
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from . import config as cfg
from .features import FEATURE_COLS

_NUMERIC_COLS = [c for c in FEATURE_COLS if not c.startswith("pass_height_")]
_ONEHOT_COLS  = [c for c in FEATURE_COLS if c.startswith("pass_height_")]

MODEL_KINDS: tuple[str, ...] = ("logit", "logit_balanced", "gbm")


# =============================================================================
# Pipeline factory
# =============================================================================
def _make_pipeline(kind: str = "logit") -> Pipeline:
    """Build a fresh, untrained pipeline for the requested model family.

    The pre-processor is shared: numerical features are standardised,
    one-hot pass-height columns pass through. GBM does not need scaling
    but the cost is negligible and keeps the pipeline shape uniform.
    """
    pre = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), _NUMERIC_COLS),
            ("oh",  "passthrough",    _ONEHOT_COLS),
        ],
        remainder="drop",
    )
    if kind == "logit":
        clf = LogisticRegression(max_iter=2000, C=1.0, solver="lbfgs")
    elif kind == "logit_balanced":
        clf = LogisticRegression(max_iter=2000, C=1.0, solver="lbfgs",
                                  class_weight="balanced")
    elif kind == "gbm":
        clf = HistGradientBoostingClassifier(
            loss="log_loss",
            max_iter=400,
            learning_rate=0.05,
            max_leaf_nodes=31,
            min_samples_leaf=40,
            l2_regularization=1.0,
            early_stopping=False,
            random_state=0,
        )
    else:
        raise ValueError(f"unknown kind={kind!r} (expected one of {MODEL_KINDS})")
    return Pipeline([("pre", pre), ("clf", clf)])


# =============================================================================
# Cross-validation (group K-fold by match_id)
# =============================================================================
def cross_validate(features_df: pd.DataFrame,
                   kind: str = "logit",
                   n_splits: int = cfg.XPASS_CV_FOLDS,
                   verbose: bool = True) -> pd.DataFrame:
    """5-fold group CV with `match_id` as the group key.

    Returns one row per fold with AUC / log-loss / Brier / n_train / n_val.
    """
    df = features_df.dropna(subset=list(FEATURE_COLS) + ["pass_complete"]).copy()
    if df.empty:
        raise ValueError("No usable rows for xPass CV (all NaN after dropna).")

    X = df[list(FEATURE_COLS)]
    y = df["pass_complete"].astype(int).values
    groups = df["match_id"].values

    rows = []
    for fold, (tr, va) in enumerate(GroupKFold(n_splits=n_splits).split(X, y, groups), 1):
        pipe = _make_pipeline(kind).fit(X.iloc[tr], y[tr])
        p = pipe.predict_proba(X.iloc[va])[:, 1]
        auc = roc_auc_score(y[va], p)
        ll  = log_loss(y[va], p, labels=[0, 1])
        bs  = brier_score_loss(y[va], p)
        rows.append({"fold": fold, "n_train": len(tr), "n_val": len(va),
                     "auc": auc, "log_loss": ll, "brier": bs})
        if verbose:
            print(f"  [{kind:14s}] fold {fold}  n_val={len(va):5d}  "
                  f"AUC={auc:.3f}  log_loss={ll:.3f}  Brier={bs:.3f}")

    res = pd.DataFrame(rows)
    if verbose:
        print(f"  [{kind:14s}] mean AUC      : {res['auc'].mean():.3f} "
              f"+/- {res['auc'].std():.3f}")
        print(f"  [{kind:14s}] mean log_loss : {res['log_loss'].mean():.3f} "
              f"+/- {res['log_loss'].std():.3f}")
        print(f"  [{kind:14s}] mean Brier    : {res['brier'].mean():.3f} "
              f"+/- {res['brier'].std():.3f}")
    return res


# =============================================================================
# Final fit / persistence
# =============================================================================
def fit_full(features_df: pd.DataFrame,
             kind: str = "logit",
             save: bool = True) -> Pipeline:
    """Train on all matches and (optionally) persist to disk.

    Each `kind` is saved with a distinct filename so multiple models can
    coexist on disk for downstream comparison.
    """
    df = features_df.dropna(subset=list(FEATURE_COLS) + ["pass_complete"]).copy()
    pipe = _make_pipeline(kind).fit(df[list(FEATURE_COLS)],
                                     df["pass_complete"].astype(int).values)
    if save:
        path = _model_path(kind)
        joblib.dump(pipe, path)
        print(f"  saved: {path}")
    return pipe


def _model_path(kind: str):
    """One file per model family. Default kind keeps the original filename."""
    if kind == "logit":
        return cfg.XPASS_MODEL_PATH
    return cfg.XPASS_MODEL_PATH.with_name(
        cfg.XPASS_MODEL_PATH.stem + f"_{kind}" + cfg.XPASS_MODEL_PATH.suffix)


def load_model(kind: str = "logit") -> Pipeline:
    path = _model_path(kind)
    if not path.exists():
        raise FileNotFoundError(f"{path} not found — run fit_full(kind={kind!r}) first.")
    return joblib.load(path)


def predict_proba(model: Pipeline, features_df: pd.DataFrame) -> np.ndarray:
    """Return P(complete) for every row in `features_df`."""
    return model.predict_proba(features_df[list(FEATURE_COLS)])[:, 1]


# =============================================================================
# Out-of-fold predictions (used for every honest diagnostic below)
# =============================================================================
def oof_predictions(features_df: pd.DataFrame,
                    kind: str = "logit",
                    n_splits: int = cfg.XPASS_CV_FOLDS) -> pd.DataFrame:
    """Honest out-of-fold probabilities aligned with the input rows."""
    df = features_df.dropna(subset=list(FEATURE_COLS) + ["pass_complete"]).copy()
    X = df[list(FEATURE_COLS)]
    y = df["pass_complete"].astype(int).values
    groups = df["match_id"].values
    df["xpass_oof"] = np.nan
    df["fold"]      = -1
    for k, (tr, va) in enumerate(GroupKFold(n_splits=n_splits).split(X, y, groups), 1):
        pipe = _make_pipeline(kind).fit(X.iloc[tr], y[tr])
        df.iloc[va, df.columns.get_loc("xpass_oof")] = pipe.predict_proba(X.iloc[va])[:, 1]
        df.iloc[va, df.columns.get_loc("fold")]     = k
    return df


# =============================================================================
# Multi-model comparison
# =============================================================================
def compare_models(features_df: pd.DataFrame,
                   kinds: Sequence[str] = MODEL_KINDS,
                   n_splits: int = cfg.XPASS_CV_FOLDS,
                   verbose: bool = True) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run CV + OOF for every requested kind and aggregate the results.

    Returns
    -------
    metrics : DataFrame
        One row per model with mean / std AUC, mean log-loss, mean Brier,
        plus the OOF range diagnostic (5th/50th/95th percentile predicted
        probability and the share of predictions below 0.30 — a proxy for
        how well the model identifies risky passes).
    oof_long : DataFrame
        Stacked (long-form) OOF predictions: one row per (event, model)
        with columns event_id, match_id, pass_complete, xpass_oof, model.
        Convenient for overlay plots.
    """
    metrics_rows: list[dict] = []
    oof_frames:   list[pd.DataFrame] = []

    for kind in kinds:
        if verbose:
            print(f"\n=== {kind} ===")
        cv  = cross_validate(features_df, kind=kind, n_splits=n_splits,
                              verbose=verbose)
        oof = oof_predictions(features_df, kind=kind, n_splits=n_splits)
        p   = oof["xpass_oof"].values
        y   = oof["pass_complete"].astype(int).values

        metrics_rows.append({
            "model":             kind,
            "auc_mean":          cv["auc"].mean(),
            "auc_std":           cv["auc"].std(),
            "log_loss_mean":     cv["log_loss"].mean(),
            "brier_mean":        cv["brier"].mean(),
            "oof_p05":           float(np.percentile(p, 5)),
            "oof_p50":           float(np.percentile(p, 50)),
            "oof_p95":           float(np.percentile(p, 95)),
            "share_below_0.30":  float((p < 0.30).mean()),
            "share_below_0.50":  float((p < 0.50).mean()),
            "auc_global":        float(roc_auc_score(y, p)),
        })

        oof_long = oof[["event_id", "match_id", "pass_complete", "xpass_oof"]].copy()
        oof_long["model"] = kind
        oof_frames.append(oof_long)

    metrics  = pd.DataFrame(metrics_rows)
    oof_long = pd.concat(oof_frames, ignore_index=True)
    return metrics, oof_long


# =============================================================================
# Diagnostics (single model)
# =============================================================================
def coefficient_table(model: Pipeline) -> pd.DataFrame:
    """Coefficients on standardised inputs, sorted by absolute magnitude.

    Logistic only — raises on a non-linear classifier. Magnitude is
    comparable across numerical features because they share the same
    standardised scale; `odds_ratio = exp(coef)` is the multiplicative
    effect on the odds of completion for a one-sigma change.
    """
    clf = model.named_steps["clf"]
    if not isinstance(clf, LogisticRegression):
        raise TypeError(f"coefficient_table requires a LogisticRegression, "
                         f"got {type(clf).__name__}")
    pre = model.named_steps["pre"]
    feat_names: list[str] = []
    for name, _, cols in pre.transformers_:
        if name == "remainder":
            continue
        feat_names.extend(cols)
    coefs = clf.coef_[0]
    out = pd.DataFrame({
        "feature":    feat_names,
        "coef":       coefs,
        "abs_coef":   np.abs(coefs),
        "odds_ratio": np.exp(coefs),
    }).sort_values("abs_coef", ascending=False).reset_index(drop=True)
    out["intercept"] = clf.intercept_[0]
    return out


def metrics_by_segment(features_df: pd.DataFrame,
                       kind: str = "logit",
                       n_splits: int = cfg.XPASS_CV_FOLDS) -> pd.DataFrame:
    """OOF AUC / log-loss / Brier on meaningful sub-populations."""
    df = oof_predictions(features_df, kind=kind, n_splits=n_splits)
    rows = []

    def _row(name, mask):
        sub = df[mask]
        if sub["pass_complete"].nunique() < 2 or len(sub) < 50:
            return {
                "segment": name, "n": int(len(sub)),
                "completion_rate": float(sub["pass_complete"].mean()) if len(sub) else np.nan,
                "auc": np.nan, "log_loss": np.nan, "brier": np.nan,
            }
        return {
            "segment":         name,
            "n":               int(len(sub)),
            "completion_rate": float(sub["pass_complete"].mean()),
            "auc":             roc_auc_score(sub["pass_complete"], sub["xpass_oof"]),
            "log_loss":        log_loss(sub["pass_complete"], sub["xpass_oof"], labels=[0, 1]),
            "brier":           brier_score_loss(sub["pass_complete"], sub["xpass_oof"]),
        }

    rows.append(_row("ALL", pd.Series(True, index=df.index)))
    rows.append(_row("high_pressure (>=2 opp @ 2.5m sender)",
                     df["sender_pressure_count_25"] >= cfg.PRESSURE_MIN))
    rows.append(_row("low_pressure",
                     df["sender_pressure_count_25"] < cfg.PRESSURE_MIN))
    rows.append(_row("target_final_third",
                     df["target_in_final_third"] == 1))
    rows.append(_row("target_pre_final_third",
                     df["target_in_final_third"] == 0))
    rows.append(_row("short pass (<10m)",
                     df["pass_distance"] < 10))
    rows.append(_row("medium pass (10-25m)",
                     (df["pass_distance"] >= 10) & (df["pass_distance"] < 25)))
    rows.append(_row("long pass (>=25m)",
                     df["pass_distance"] >= 25))
    rows.append(_row("ground pass",
                     df["pass_height_ground"] == 1))
    rows.append(_row("low/high pass (lofted)",
                     df["pass_height_ground"] == 0))
    rows.append(_row("forward (angle <= 60deg)",
                     df["pass_angle_forward"] <= 60))
    rows.append(_row("sideways/back (angle > 60deg)",
                     df["pass_angle_forward"] > 60))
    return pd.DataFrame(rows)


def decile_calibration(features_df: pd.DataFrame,
                       kind: str = "logit",
                       n_bins: int = 10,
                       n_splits: int = cfg.XPASS_CV_FOLDS) -> pd.DataFrame:
    """Decile lift table: predicted vs observed completion rate per bin."""
    df = oof_predictions(features_df, kind=kind, n_splits=n_splits)
    df["bin"] = pd.qcut(df["xpass_oof"], q=n_bins, duplicates="drop",
                        labels=False) + 1
    g = df.groupby("bin").agg(
        n=("pass_complete", "size"),
        mean_pred=("xpass_oof", "mean"),
        obs_rate =("pass_complete", "mean"),
    ).reset_index()
    g["abs_gap"] = (g["mean_pred"] - g["obs_rate"]).abs()
    return g


def confusion_at_threshold(features_df: pd.DataFrame,
                           threshold: float = 0.5,
                           kind: str = "logit",
                           n_splits: int = cfg.XPASS_CV_FOLDS) -> pd.DataFrame:
    """2x2 confusion matrix at a hard threshold (default 0.5)."""
    df = oof_predictions(features_df, kind=kind, n_splits=n_splits)
    yhat = (df["xpass_oof"] >= threshold).astype(int)
    y = df["pass_complete"].astype(int)
    tp = int(((yhat == 1) & (y == 1)).sum())
    tn = int(((yhat == 0) & (y == 0)).sum())
    fp = int(((yhat == 1) & (y == 0)).sum())
    fn = int(((yhat == 0) & (y == 1)).sum())
    prec = tp / max(tp + fp, 1)
    rec  = tp / max(tp + fn, 1)
    spec = tn / max(tn + fp, 1)
    return pd.DataFrame({
        "metric": ["TP", "FP", "FN", "TN", "precision", "recall", "specificity"],
        "value":  [tp, fp, fn, tn, prec, rec, spec],
        "note":   ["", "", "", "",
                   "P(complete | predicted complete)",
                   "P(predicted complete | actually complete)",
                   "P(predicted incomplete | actually incomplete)"],
    })


# =============================================================================
# Plots
# =============================================================================
def plot_calibration(features_df: pd.DataFrame,
                     kind: str = "logit",
                     n_bins: int = 10,
                     n_splits: int = cfg.XPASS_CV_FOLDS):
    """Out-of-fold reliability diagram with quantile bins."""
    import matplotlib.pyplot as plt
    from sklearn.calibration import calibration_curve

    df = oof_predictions(features_df, kind=kind, n_splits=n_splits)
    y = df["pass_complete"].astype(int).values
    p = df["xpass_oof"].values
    frac_pos, mean_pred = calibration_curve(y, p, n_bins=n_bins, strategy="quantile")

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.plot([0, 1], [0, 1], "--", color="grey", lw=1, label="perfect calibration")
    ax.plot(mean_pred, frac_pos, "o-", color="#1f77b4", lw=2, label=f"xPass OOF ({kind})")
    ax.set_xlabel("predicted P(complete)")
    ax.set_ylabel("observed completion rate")
    ax.set_title(f"xPass calibration  ({kind}, {n_bins}-quantile bins, n={len(df):,}, "
                 f"AUC={roc_auc_score(y, p):.3f})")
    ax.legend(loc="upper left")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.set_aspect("equal")
    plt.tight_layout()
    return fig


def plot_decile_calibration(features_df: pd.DataFrame,
                            kind: str = "logit",
                            n_bins: int = 10,
                            n_splits: int = cfg.XPASS_CV_FOLDS):
    """Bar-style calibration: mean predicted vs observed rate per decile."""
    import matplotlib.pyplot as plt
    g = decile_calibration(features_df, kind=kind, n_bins=n_bins, n_splits=n_splits)
    fig, ax = plt.subplots(figsize=(9, 5))
    width = 0.4
    x = np.arange(len(g))
    ax.bar(x - width / 2, g["mean_pred"], width=width, label="mean predicted",
           color="#1f77b4")
    ax.bar(x + width / 2, g["obs_rate"], width=width, label="observed rate",
           color="#ff7f0e")
    for i, (mp, obs, n) in enumerate(zip(g["mean_pred"], g["obs_rate"], g["n"])):
        ax.text(i, max(mp, obs) + 0.02, f"n={n}", ha="center", fontsize=8,
                color="grey")
    ax.set_xticks(x)
    ax.set_xticklabels([f"d{int(b)}" for b in g["bin"]])
    ax.set_ylim(0, 1.08)
    ax.set_ylabel("completion rate")
    ax.set_title(f"xPass decile calibration  ({kind}, {n_bins} quantile bins)")
    ax.legend(loc="upper left")
    plt.tight_layout()
    return fig


def plot_oof_distribution(features_df: pd.DataFrame,
                          kind: str = "logit",
                          n_splits: int = cfg.XPASS_CV_FOLDS):
    """Histogram of OOF probabilities split by class."""
    import matplotlib.pyplot as plt
    df = oof_predictions(features_df, kind=kind, n_splits=n_splits)
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.hist(df.loc[df["pass_complete"] == 1, "xpass_oof"], bins=40,
            alpha=0.55, label="completed (y=1)", color="#2ca02c")
    ax.hist(df.loc[df["pass_complete"] == 0, "xpass_oof"], bins=40,
            alpha=0.55, label="not completed (y=0)", color="#d62728")
    ax.set_xlabel("OOF P(complete)")
    ax.set_ylabel("count")
    ax.set_title(f"xPass OOF probability split by outcome  ({kind}, n={len(df):,})")
    ax.legend(loc="upper center")
    plt.tight_layout()
    return fig


# =============================================================================
# Isotonic calibration + probability clipping
# =============================================================================
# Rationale
# ---------
# Even a model with strong AUC can produce probabilities that hug 0 / 1 — for
# example a 50 m High Pass to a free receiver makes the linear logit saturate
# to ~1.0, while the empirical completion rate of identical situations is
# closer to 0.85. Isotonic regression learns a monotone map raw -> real from
# the (raw_pred, label) pairs and corrects this. We then clip into a safe
# range to avoid pathological 0 / 1 values that would dominate downstream
# computations such as xEPV.
#
# Honesty note
# ------------
# Fitting isotonic on all out-of-fold predictions and their labels is
# mildly optimistic: each event's label has a small influence on its own
# calibrated probability through the isotonic step. In practice the bias is
# small (the isotonic has only a handful of effective degrees of freedom
# compared to the dataset size). The OOF predictions themselves remain fully
# honest. For a strict honest evaluation, one would split the OOF into halves
# and cross-fit the isotonic.
DEFAULT_CLIP: tuple[float, float] = (0.05, 0.99)
"""Default clip range for production probabilities — deliberately asymmetric.

Lower bound (0.05): protects from rare base-model saturations near 0 that
calibration alone cannot fully repair (the "Hernandez case" — a 9 m pass
with a defender 1.7 m from the receiver scored raw ~0.005 in the GBM, but
the empirical completion rate of similar situations is closer to 0.30).

Upper bound (0.99): empirical completion rate of the easiest decile is
~0.997, so anything above 0.99 carries no useful tactical signal. We do
NOT clip more aggressively at the top because the corpus is ~94% completed
passes and most predictions are genuinely high — collapsing them all to a
single ceiling would destroy the ranking between "easy" and "very easy"
alternatives, which the downstream xEPV / Decision Quality index needs to
choose the best receiver from a set of all-easy candidates.
"""


class _PlattCalibrator:
    """Sigmoid (Platt) calibration: ``p_cal = σ(a · logit(p_raw) + b)``.

    Smoother than isotonic at the extremes — fits a single 2-parameter
    monotone curve rather than a piecewise-constant step function. Useful
    when the raw probabilities saturate near 0 / 1 and an isotonic mapping
    would copy that saturation.
    """

    def __init__(self):
        self._a: float = 1.0
        self._b: float = 0.0

    @staticmethod
    def _logit(p: np.ndarray, eps: float = 1e-6) -> np.ndarray:
        p = np.clip(p, eps, 1 - eps)
        return np.log(p / (1 - p))

    def fit(self, p_raw: np.ndarray, y: np.ndarray) -> "_PlattCalibrator":
        from sklearn.linear_model import LogisticRegression as _LR
        z = self._logit(np.asarray(p_raw, dtype=float)).reshape(-1, 1)
        lr = _LR(C=1e6, solver="lbfgs", max_iter=1000).fit(z, y)
        self._a = float(lr.coef_[0, 0])
        self._b = float(lr.intercept_[0])
        return self

    def transform(self, p_raw: np.ndarray) -> np.ndarray:
        z = self._logit(np.asarray(p_raw, dtype=float))
        return 1.0 / (1.0 + np.exp(-(self._a * z + self._b)))


class _BetaCalibrator:
    """Beta calibration: ``p_cal = σ(a · log(p) - b · log(1-p) + c)``.

    Three-parameter generalisation of Platt's sigmoid (which is the
    special case a=b). Often the best of both worlds: smoother than
    isotonic but more flexible than sigmoid, since it can model
    asymmetric miscalibration (over-confident on one tail and under
    on the other). Reference: Kull, Filho, Flach (2017).
    """

    def __init__(self):
        self._a: float = 1.0
        self._b: float = 1.0
        self._c: float = 0.0

    def fit(self, p_raw: np.ndarray, y: np.ndarray) -> "_BetaCalibrator":
        from sklearn.linear_model import LogisticRegression as _LR
        eps = 1e-6
        p = np.clip(np.asarray(p_raw, dtype=float), eps, 1 - eps)
        X = np.column_stack([np.log(p), -np.log(1 - p)])
        lr = _LR(C=1e6, solver="lbfgs", max_iter=2000).fit(X, y)
        self._a = float(lr.coef_[0, 0])
        self._b = float(lr.coef_[0, 1])
        self._c = float(lr.intercept_[0])
        return self

    def transform(self, p_raw: np.ndarray) -> np.ndarray:
        eps = 1e-6
        p = np.clip(np.asarray(p_raw, dtype=float), eps, 1 - eps)
        z = self._a * np.log(p) + self._b * (-np.log(1 - p)) + self._c
        return 1.0 / (1.0 + np.exp(-z))


def _make_calibrator(method: str):
    if method == "isotonic":
        return IsotonicRegression(out_of_bounds="clip")
    if method == "sigmoid":
        return _PlattCalibrator()
    if method == "beta":
        return _BetaCalibrator()
    raise ValueError(f"unknown calibration method={method!r} "
                      f"(expected 'isotonic', 'sigmoid', or 'beta')")


class CalibratedXPass:
    """Calibrated production model: base classifier + calibrator + clip.

    Encapsulates the three-stage inference pipeline so downstream callers
    only need ``model.predict_proba(features_df)`` and get realistic,
    bounded probabilities.
    """

    def __init__(self,
                 base: Pipeline,
                 calibrator,
                 kind: str,
                 method: str,
                 clip: tuple[float, float] | None = DEFAULT_CLIP):
        self.base = base
        self.calibrator = calibrator
        self.kind = kind
        self.method = method
        self.clip = clip

    def predict_proba(self, features_df: pd.DataFrame) -> np.ndarray:
        raw = self.base.predict_proba(features_df[list(FEATURE_COLS)])[:, 1]
        cal = self.calibrator.transform(raw)
        if self.clip is not None:
            cal = np.clip(cal, self.clip[0], self.clip[1])
        return cal

    def predict_raw(self, features_df: pd.DataFrame) -> np.ndarray:
        """Pre-calibration probabilities — diagnostic only."""
        return self.base.predict_proba(features_df[list(FEATURE_COLS)])[:, 1]


def oof_predictions_calibrated(features_df: pd.DataFrame,
                                kind: str = "gbm",
                                method: str = "sigmoid",
                                n_splits: int = cfg.XPASS_CV_FOLDS,
                                clip: tuple[float, float] | None = DEFAULT_CLIP
                                ) -> pd.DataFrame:
    """OOF predictions + post-hoc calibration + optional clip.

    `method` is one of {'sigmoid', 'isotonic'}. Sigmoid (Platt) is the new
    default: it is smoother at the extremes and avoids the piecewise-step
    artefacts isotonic can introduce when raw probabilities saturate near
    0 / 1. Returns the standard OOF frame plus both raw and calibrated
    columns side by side (`xpass_oof_raw`, `xpass_oof`).
    """
    df = oof_predictions(features_df, kind=kind, n_splits=n_splits)
    raw = df["xpass_oof"].values
    y   = df["pass_complete"].astype(int).values

    cal_obj = _make_calibrator(method).fit(raw, y)
    cal = cal_obj.transform(raw)
    if clip is not None:
        cal = np.clip(cal, clip[0], clip[1])

    df["xpass_oof_raw"] = raw
    df["xpass_oof"]     = cal
    df.attrs["calibration_method"] = method
    return df


def fit_calibrated(features_df: pd.DataFrame,
                   kind: str = "gbm",
                   method: str = "sigmoid",
                   n_splits: int = cfg.XPASS_CV_FOLDS,
                   clip: tuple[float, float] | None = DEFAULT_CLIP,
                   save: bool = True) -> CalibratedXPass:
    """Build the production-ready calibrated model.

    Three steps:
      1. cross-validated OOF predictions (honest, used to train the calibrator)
      2. fit Platt sigmoid (or isotonic) on (raw_oof, label) pairs
      3. base model refit on ALL matches, packaged with the calibrator + clip
    """
    oof = oof_predictions(features_df, kind=kind, n_splits=n_splits)
    raw = oof["xpass_oof"].values
    y   = oof["pass_complete"].astype(int).values

    cal_obj = _make_calibrator(method).fit(raw, y)

    base = fit_full(features_df, kind=kind, save=False)
    model = CalibratedXPass(base=base, calibrator=cal_obj,
                             kind=kind, method=method, clip=clip)

    if save:
        path = cfg.XPASS_MODEL_PATH.with_name(
            cfg.XPASS_MODEL_PATH.stem + f"_{kind}_{method}"
            + cfg.XPASS_MODEL_PATH.suffix)
        joblib.dump(model, path)
        print(f"  saved calibrated model: {path}")
    return model


def compare_calibrators_holdout(features_df: pd.DataFrame,
                                 kind: str = "gbm",
                                 n_splits: int = cfg.XPASS_CV_FOLDS,
                                 clip: tuple[float, float] | None = DEFAULT_CLIP,
                                 random_state: int = 0
                                 ) -> pd.DataFrame:
    """Honest calibrator comparison via a 50/50 match-level holdout split.

    Fitting a calibrator on all OOF predictions and evaluating on the same
    OOF predictions is mildly optimistic — each event's label slightly
    informs its own calibrated probability through the calibrator.

    This routine eliminates that optimism: it splits the matches into two
    halves, fits each calibrator on half A's (raw, label) pairs and
    evaluates on half B's predictions, swaps, and combines the two halves.
    The reported log-loss / Brier are honest out-of-fold estimates over the
    full corpus.

    Returns one row per (raw + 3 calibrators) with AUC, log-loss, Brier,
    and saturation diagnostics.
    """
    oof = oof_predictions(features_df, kind=kind, n_splits=n_splits)
    raw      = oof["xpass_oof"].values
    y        = oof["pass_complete"].astype(int).values
    matches  = oof["match_id"].values

    rng = np.random.default_rng(random_state)
    unique_m = np.unique(matches)
    rng.shuffle(unique_m)
    half = len(unique_m) // 2
    set_A = set(unique_m[:half])
    in_A = np.isin(matches, list(set_A))
    in_B = ~in_A

    rows = [{
        "stage":            "raw",
        "method":           "—",
        "p05":              float(np.percentile(raw, 5)),
        "p50":              float(np.percentile(raw, 50)),
        "p95":              float(np.percentile(raw, 95)),
        "share_below_0.10": float((raw < 0.10).mean()),
        "share_above_0.97": float((raw > 0.97).mean()),
        "auc":              float(roc_auc_score(y, raw)),
        "log_loss":         float(log_loss(y, np.clip(raw, 1e-6, 1 - 1e-6),
                                            labels=[0, 1])),
        "brier":            float(brier_score_loss(y, raw)),
    }]

    for method in ("sigmoid", "isotonic", "beta"):
        cal = np.empty_like(raw, dtype=float)
        for tr, te in ((in_A, in_B), (in_B, in_A)):
            obj = _make_calibrator(method).fit(raw[tr], y[tr])
            cal[te] = obj.transform(raw[te])
        if clip is not None:
            cal = np.clip(cal, clip[0], clip[1])
        rows.append({
            "stage":            "holdout-cal",
            "method":           method,
            "p05":              float(np.percentile(cal, 5)),
            "p50":              float(np.percentile(cal, 50)),
            "p95":              float(np.percentile(cal, 95)),
            "share_below_0.10": float((cal < 0.10).mean()),
            "share_above_0.97": float((cal > 0.97).mean()),
            "auc":              float(roc_auc_score(y, cal)),
            "log_loss":         float(log_loss(y, np.clip(cal, 1e-6, 1 - 1e-6),
                                                labels=[0, 1])),
            "brier":            float(brier_score_loss(y, cal)),
        })
    return pd.DataFrame(rows)


def compare_calibrators(features_df: pd.DataFrame,
                        kind: str = "gbm",
                        n_splits: int = cfg.XPASS_CV_FOLDS,
                        clip: tuple[float, float] | None = DEFAULT_CLIP
                        ) -> pd.DataFrame:
    """Run isotonic + sigmoid on the same OOF and report the side-by-side stats.

    Use this once after `compare_models` to pick the calibrator that gives
    the most realistic distribution for the downstream xEPV / DQ index.
    """
    oof_raw = oof_predictions(features_df, kind=kind, n_splits=n_splits)
    raw = oof_raw["xpass_oof"].values
    y   = oof_raw["pass_complete"].astype(int).values

    rows = [{
        "stage":            "raw",
        "method":           "—",
        "p05":              float(np.percentile(raw, 5)),
        "p50":              float(np.percentile(raw, 50)),
        "p95":              float(np.percentile(raw, 95)),
        "share_below_0.10": float((raw < 0.10).mean()),
        "share_above_0.97": float((raw > 0.97).mean()),
        "auc":              float(roc_auc_score(y, raw)),
        "log_loss":         float(log_loss(y, np.clip(raw, 1e-6, 1 - 1e-6),
                                            labels=[0, 1])),
        "brier":            float(brier_score_loss(y, raw)),
    }]
    for method in ("sigmoid", "isotonic", "beta"):
        cal = _make_calibrator(method).fit(raw, y).transform(raw)
        if clip is not None:
            cal = np.clip(cal, clip[0], clip[1])
        rows.append({
            "stage":            "calibrated",
            "method":           method,
            "p05":              float(np.percentile(cal, 5)),
            "p50":              float(np.percentile(cal, 50)),
            "p95":              float(np.percentile(cal, 95)),
            "share_below_0.10": float((cal < 0.10).mean()),
            "share_above_0.97": float((cal > 0.97).mean()),
            "auc":              float(roc_auc_score(y, cal)),
            "log_loss":         float(log_loss(y, np.clip(cal, 1e-6, 1 - 1e-6),
                                                labels=[0, 1])),
            "brier":            float(brier_score_loss(y, cal)),
        })
    return pd.DataFrame(rows)


def calibration_summary(oof_calibrated: pd.DataFrame) -> pd.DataFrame:
    """Side-by-side stats of raw vs calibrated OOF probabilities.

    Use after `oof_predictions_calibrated`. Reports range percentiles,
    saturation share (above 0.99 / below 0.01) and global AUC for both.
    AUC of the calibrated probabilities is identical to the raw if the
    isotonic is strictly monotone (it always is here, by construction).
    """
    rows = []
    y = oof_calibrated["pass_complete"].astype(int).values
    for label, col in (("raw", "xpass_oof_raw"), ("calibrated", "xpass_oof")):
        p = oof_calibrated[col].values
        rows.append({
            "stage":             label,
            "p05":               float(np.percentile(p, 5)),
            "p50":               float(np.percentile(p, 50)),
            "p95":               float(np.percentile(p, 95)),
            "share_below_0.30":  float((p < 0.30).mean()),
            "share_above_0.99":  float((p > 0.99).mean()),
            "share_below_0.01":  float((p < 0.01).mean()),
            "auc":               float(roc_auc_score(y, p)),
            "log_loss":          float(log_loss(y, np.clip(p, 1e-6, 1 - 1e-6),
                                                 labels=[0, 1])),
            "brier":             float(brier_score_loss(y, p)),
        })
    return pd.DataFrame(rows)


def plot_calibration_effect(oof_calibrated: pd.DataFrame, n_bins: int = 10):
    """Two-panel before/after view of the isotonic correction.

    Left  : reliability curves — raw vs calibrated on the same axes.
    Right : OOF probability density — the saturation peak at 1.0 should
            shrink and the bulk should spread to the left after calibration.
    """
    import matplotlib.pyplot as plt
    from sklearn.calibration import calibration_curve

    y = oof_calibrated["pass_complete"].astype(int).values
    raw = oof_calibrated["xpass_oof_raw"].values
    cal = oof_calibrated["xpass_oof"].values

    fig, (ax_cal, ax_dist) = plt.subplots(1, 2, figsize=(14, 6))

    ax_cal.plot([0, 1], [0, 1], "--", color="grey", lw=1, label="perfect")
    for label, p, color in (("raw",        raw, "#d62728"),
                             ("calibrated", cal, "#2ca02c")):
        frac_pos, mean_pred = calibration_curve(y, p, n_bins=n_bins,
                                                 strategy="quantile")
        auc = roc_auc_score(y, p)
        ax_cal.plot(mean_pred, frac_pos, "o-", lw=2, color=color,
                    label=f"{label} (AUC={auc:.3f})")
    ax_cal.set_xlabel("predicted P(complete)")
    ax_cal.set_ylabel("observed completion rate")
    ax_cal.set_title("Calibration — before vs after isotonic")
    ax_cal.legend(loc="upper left")
    ax_cal.set_xlim(0, 1); ax_cal.set_ylim(0, 1); ax_cal.set_aspect("equal")

    ax_dist.hist(raw, bins=40, alpha=0.55, label="raw",
                 color="#d62728")
    ax_dist.hist(cal, bins=40, alpha=0.55, label="calibrated",
                 color="#2ca02c")
    ax_dist.set_xlabel("OOF P(complete)")
    ax_dist.set_ylabel("count")
    ax_dist.set_title("OOF distribution — before vs after isotonic")
    ax_dist.legend(loc="upper left")

    plt.tight_layout()
    return fig


# =============================================================================
# Multi-model comparison plots
# =============================================================================
def plot_model_comparison(oof_long: pd.DataFrame, n_bins: int = 10):
    """Two-panel comparison: calibration overlay + OOF distribution overlay.

    `oof_long` is the stacked DataFrame returned by `compare_models`.
    Left panel  : reliability curve per model on the same axes.
    Right panel : OOF predicted-probability density per model.
    """
    import matplotlib.pyplot as plt
    from sklearn.calibration import calibration_curve

    fig, (ax_cal, ax_dist) = plt.subplots(1, 2, figsize=(14, 6))

    palette = {"logit": "#1f77b4",
               "logit_balanced": "#ff7f0e",
               "gbm": "#2ca02c"}

    ax_cal.plot([0, 1], [0, 1], "--", color="grey", lw=1, label="perfect")
    for kind, sub in oof_long.groupby("model"):
        y = sub["pass_complete"].astype(int).values
        p = sub["xpass_oof"].values
        frac_pos, mean_pred = calibration_curve(y, p, n_bins=n_bins, strategy="quantile")
        auc = roc_auc_score(y, p)
        ax_cal.plot(mean_pred, frac_pos, "o-", lw=2,
                    color=palette.get(kind, "black"),
                    label=f"{kind}  (AUC={auc:.3f})")
        ax_dist.hist(p, bins=40, alpha=0.45, label=kind,
                     color=palette.get(kind, "black"))

    ax_cal.set_xlabel("predicted P(complete)")
    ax_cal.set_ylabel("observed completion rate")
    ax_cal.set_title("Calibration — model overlay")
    ax_cal.legend(loc="upper left")
    ax_cal.set_xlim(0, 1); ax_cal.set_ylim(0, 1); ax_cal.set_aspect("equal")

    ax_dist.set_xlabel("OOF P(complete)")
    ax_dist.set_ylabel("count")
    ax_dist.set_title("OOF prediction range — model overlay")
    ax_dist.legend(loc="upper left")

    plt.tight_layout()
    return fig


# =============================================================================
# SHAP explanations (optional dependency)
# =============================================================================
def shap_explain(model, features_df: pd.DataFrame,
                 sample_n: int | None = 2000,
                 random_state: int = 0):
    """Compute SHAP values for the GBM base of a CalibratedXPass.

    Returns the matplotlib summary figure plus the SHAP explainer object so
    the notebook can do extra plots (force / waterfall / dependence) without
    recomputing values. SHAP is an optional dependency — install via
    ``pip install shap`` and re-run if the import fails.

    Why on the BASE model (raw GBM) and not on the calibrated wrapper?
    Calibration is a monotone post-hoc map; SHAP attributions on the raw
    GBM logits are interpretable in the same direction as the final
    probability, while explaining a sigmoid wrapper would just inherit the
    GBM's attributions plus a constant scaling.
    """
    try:
        import shap
    except ImportError as e:
        raise ImportError(
            "shap is not installed. Run `pip install shap` and retry.") from e

    base = model.base if isinstance(model, CalibratedXPass) else model
    clf  = base.named_steps["clf"]
    pre  = base.named_steps["pre"]

    df = features_df.dropna(subset=list(FEATURE_COLS)).copy()
    if sample_n is not None and len(df) > sample_n:
        df = df.sample(sample_n, random_state=random_state)

    X_pre = pre.transform(df[list(FEATURE_COLS)])
    feat_names: list[str] = []
    for name, _, cols in pre.transformers_:
        if name == "remainder":
            continue
        feat_names.extend(cols)

    explainer  = shap.TreeExplainer(clf)
    shap_values = explainer.shap_values(X_pre)

    import matplotlib.pyplot as plt
    fig = plt.figure(figsize=(9, 7))
    shap.summary_plot(shap_values, X_pre, feature_names=feat_names, show=False)
    plt.tight_layout()
    return fig, explainer, shap_values
