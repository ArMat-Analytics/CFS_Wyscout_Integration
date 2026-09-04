"""Validation, H1 evidence and final export.

Public functions:

    construct_validity(pct)
        Cronbach's α per index/role + cross-correlation between indices +
        mother coverage check.

    h1_summary(df, pct)
        One-line quantitative summary of H1: for each composite index vs
        its single best naive proxy, prints Spearman ρ between the two
        rankings, mean |Δ percentile|, and % of pool with |Δ| > 20.

    naive_vs_contextual(df, pct)
        Prints h1_summary, then a 4-panel scatter of (naive percentile,
        contextual percentile) rankings + console head-to-head for MID +
        per-role overlap summary.

    scouting_discoveries(df, pct)
        For each composite index, computes the within-role rank shift
        delta = ctx_idx - naive_proxy_pct and shows the players with the
        largest positive (discoveries) and negative (overrated) shifts.

    export_indices_csv(df, pct, out_path=...)
        Persists the 4 composite indices and 14 within-role percentiles.
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.stats import spearmanr

from . import config
from .indices import RADAR_SPECS


def _render_static(fig):
    """Emit a static PNG copy of the figure into the notebook output.

    Why: GitHub renders only embedded images in .ipynb cells, not Plotly's
    interactive HTML. Emitting a PNG alongside the interactive view keeps the
    notebook viewable on github.com.
    """
    from IPython.display import Image, display
    display(Image(fig.to_image(format="png", scale=2)))


# =============================================================================
# Cronbach's α + cross-correlation between indices
# =============================================================================
def _cronbach_alpha(items_df: pd.DataFrame) -> float:
    """Standardised Cronbach's α on the items columns of a DataFrame."""
    items = items_df.dropna(axis=0, how="any")
    k = items.shape[1]
    if k < 2 or items.shape[0] < 5:
        return np.nan
    var_items = items.var(axis=0, ddof=1).sum()
    var_total = items.sum(axis=1).var(ddof=1)
    if var_total == 0:
        return np.nan
    return (k / (k - 1)) * (1 - var_items / var_total)


def construct_validity(pct: pd.DataFrame):
    print("=" * 86)
    print("  CONSTRUCT VALIDITY  -  Cronbach's α per index and role")
    print("=" * 86)
    print(f"  {'Index':<14s} {'CB':>7s} {'FB':>7s} {'MID':>7s} "
          f"{'CAM':>7s} {'WIDE':>7s} {'FW':>7s} {'AVG':>7s}")
    for theme, spec in RADAR_SPECS.items():
        cols = [f"{v}__p" for _, v, _ in spec]
        row = [theme]
        alphas = []
        for r in config.MACRO_ROLES:
            sub = pct[pct["macro_role"] == r][cols]
            a = _cronbach_alpha(sub)
            alphas.append(a if not np.isnan(a) else 0)
            row.append(f"{a:.2f}" if not np.isnan(a) else "  -")
        row.append(f"{np.mean(alphas):.2f}")
        print(f"  {row[0]:<14s} {row[1]:>7s} {row[2]:>7s} {row[3]:>7s} "
              f"{row[4]:>7s} {row[5]:>7s} {row[6]:>7s} {row[7]:>7s}")
    print("-" * 86)
    print("  Note on DANGEROUSNESS α: the four radar axes are additive EPV")
    print("  by-geom_type components of epv_added_per90, not manifestations")
    print("  of a latent style. DANGEROUSNESS is a magnitude index (single")
    print("  within-role percentile of epv_added_per90) and is NOT a")
    print("  reflective composite of those four axes - α is reported here")
    print("  only as a diagnostic on the radar's sub-components.")

    print("\n" + "=" * 86)
    print("  CROSS-CORRELATION BETWEEN INDICES  (target: |r| < 0.6)")
    print("=" * 86)
    idx_cols = [f"{n}_idx" for n in RADAR_SPECS]
    print("\n  ALL ROLES:")
    print(pct[idx_cols].corr().round(2).to_string())
    print("\n  MID:")
    print(pct[pct["macro_role"] == "MID"][idx_cols].corr().round(2).to_string())
    print("\n  CB:")
    print(pct[pct["macro_role"] == "CB"][idx_cols].corr().round(2).to_string())


# =============================================================================
# H1 evidence — naive vs contextual rankings
# =============================================================================
_ROLE_COLOR = {
    "CB":   "#1f77b4",
    "FB":   "#17becf",
    "MID":  "#2ca02c",
    "CAM":  "#ff7f0e",
    "WIDE": "#9467bd",
    "FW":   "#d62728",
}


def _role_pct(df: pd.DataFrame, col: str) -> pd.Series:
    return df.groupby("macro_role")[col].rank(pct=True) * 100


# Canonical naive proxy for each composite index. Used by h1_summary and by
# scouting_discoveries so the two consumers stay in sync.
#
# Note on the DANGEROUSNESS proxy: idx__DANGEROUSNESS is itself the within-role
# percentile of epv_added_per90, so using epv_added_per90 as its naive proxy
# would collapse the scatter onto the identity diagonal and force every Δ to
# zero. The H1 question for DANGEROUSNESS is therefore framed against a truly
# "naive" volume signal - passes /90 - so the comparison reads as: "do the
# highest-EPV players just play more passes, or does the threat ranking
# substantively re-order the leaderboard once EPV is accounted for?".
INDEX_PROXIES = [
    ("PROGRESSION",   "passes_per90",          "passes /90"),
    ("DANGEROUSNESS", "passes_per90",          "passes /90"),
    ("RECEPTION",     "between_lines_pct",     "between-lines %"),
    ("GRAVITY",       "gravity_proximity_pct", "gravity proximity %"),
]


def h1_summary(df: pd.DataFrame, pct: pd.DataFrame,
               min_minutes: int = config.ANALYSIS_MIN_MINUTES,
               big_shift: int = 20) -> pd.DataFrame:
    """Quantitative H1 evidence in a single 4-row table.

    For each composite index paired with its canonical naive proxy:

    * **Spearman ρ** between the within-role naive percentile and the
      contextual index. ρ close to 1 → the contextual ranking only
      reshuffles the naive view at the edges; ρ closer to 0 → the
      contextual view *substantively* re-orders the leaderboard.
    * **mean |Δ|** — the mean absolute rank shift in percentile points.
      A value of 15 means the average player moves 15 percentile points
      between the two views (with sign: ``Δ = ctx − naive``).
    * **% |Δ| > N** — share of the pool whose ranking shifts by more
      than ``big_shift`` percentile points (default 20). This is the
      scouting-relevant fraction: those are the players who would be
      *systematically* miscalled by a naive-only workflow.

    The four rows together form the headline numerical claim of H1. They
    are computed on the same filtered pool used by :func:`naive_vs_contextual`
    so the figures and the table tell the same story.

    Returns the summary as a ``DataFrame`` so callers can persist it.
    """
    df  = df.copy()
    pct = pct.copy()
    if min_minutes:
        keep = df["minutes_played"] >= min_minutes
        df, pct = df[keep].reset_index(drop=True), pct[keep].reset_index(drop=True)
    df["passes_per90"] = df["passes_total"] / df["minutes_played"] * 90

    for theme in RADAR_SPECS:
        df[f"{theme}_idx"] = pct[f"{theme}_idx"].values

    rows = []
    for idx, naive, label in INDEX_PROXIES:
        df[f"{naive}__p"] = _role_pct(df, naive)
        valid = df[[f"{naive}__p", f"{idx}_idx"]].dropna()
        rho, _ = spearmanr(valid[f"{naive}__p"], valid[f"{idx}_idx"])
        delta = (df[f"{idx}_idx"] - df[f"{naive}__p"]).dropna()
        rows.append({
            "Index"       : idx,
            "Naive proxy" : label,
            "n"           : int(len(delta)),
            "Spearman ρ"  : round(float(rho), 3),
            "mean |Δ|"    : round(float(delta.abs().mean()), 1),
            f"% |Δ|>{big_shift}": round(float((delta.abs() > big_shift).mean() * 100), 1),
        })
    table = pd.DataFrame(rows)

    print("=" * 86)
    print("  H1 QUANTITATIVE SUMMARY  -  contextual vs naive ranking, within macro-role")
    print("=" * 86)
    print(table.to_string(index=False))
    print("-" * 86)
    print("  rho close to 1   = contextual reshuffles only the edges of the naive ranking")
    print("  rho closer to 0  = the contextual view substantively re-orders the leaderboard")
    print(f"  mean |Δ|         = average rank shift, percentile points")
    print(f"  % |Δ|>{big_shift}          = share of players whose ranking moves > {big_shift} pp -")
    print(f"                     these are the scouting-relevant disagreements")
    print("=" * 86)
    return table


def naive_vs_contextual(df: pd.DataFrame, pct: pd.DataFrame,
                         min_minutes: int = config.ANALYSIS_MIN_MINUTES):
    """Quantitative summary + 4-panel scatter of naive (X) vs contextual (Y)
    within-role percentiles + console head-to-head for MID + per-role overlap
    summary.

    ``min_minutes`` filters out low-sample players before the comparison
    (default 135 = 1.5 matches).
    """
    # Headline numerical claim, printed before the figure.
    h1_summary(df, pct, min_minutes=min_minutes)

    df  = df.copy()
    pct = pct.copy()
    if min_minutes:
        keep = df["minutes_played"] >= min_minutes
        df, pct = df[keep].reset_index(drop=True), pct[keep].reset_index(drop=True)
    df["passes_per90"] = df["passes_total"] / df["minutes_played"] * 90

    # Carry the contextual indices over from pct (they live there)
    for theme in RADAR_SPECS:
        df[f"{theme}_idx"] = pct[f"{theme}_idx"].values

    comparisons = [
        ("Pass volume vs PROGRESSION",
         "passes_per90",                       "PROGRESSION_idx",
         "Naive: passes /90 (volume)",
         "Contextual: PROGRESSION index"),
        ("Raw line-breakers vs Quality line-breakers",
         "lb_geom_per90",                      "lb_quality_per90",
         "Naive: bold passes /90 (geom)",
         "Contextual: bold + value /90 (quality)"),
        ("Penetration count vs EPV-weighted penetration",
         "successful_hull_penetrations_per90", "epv_penetration_per90",
         "Naive: # penetrations /90",
         "Contextual: EPV on penetrations /90"),
        ("Pass volume vs DANGEROUSNESS",
         "passes_per90",                       "DANGEROUSNESS_idx",
         "Naive: passes /90 (volume)",
         "Contextual: DANGEROUSNESS index"),
    ]

    # Convert raw values to within-role percentiles
    for _, x_var, y_var, *_ in comparisons:
        if not x_var.endswith("_idx"):
            df[f"{x_var}__p"] = _role_pct(df, x_var)
        if not y_var.endswith("_idx"):
            df[f"{y_var}__p"] = _role_pct(df, y_var)

    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=[t for t, *_ in comparisons],
        horizontal_spacing=0.10, vertical_spacing=0.16,
    )
    for i, (_, x_var, y_var, x_lab, y_lab) in enumerate(comparisons):
        row, col = i // 2 + 1, i % 2 + 1
        x_col = x_var if x_var.endswith("_idx") else f"{x_var}__p"
        y_col = y_var if y_var.endswith("_idx") else f"{y_var}__p"

        for r, color in _ROLE_COLOR.items():
            sub = df[df["macro_role"] == r]
            fig.add_trace(go.Scatter(
                x=sub[x_col], y=sub[y_col], mode="markers",
                marker=dict(color=color, size=7, opacity=0.75,
                            line=dict(color="#333", width=0.4)),
                text=sub["player"],
                hovertemplate=("<b>%{text}</b><br>"
                               f"{x_lab}: " + "%{x:.1f}<br>"
                               f"{y_lab}: " + "%{y:.1f}<extra></extra>"),
                name=r, legendgroup=r, showlegend=(i == 0),
            ), row=row, col=col)

        fig.add_trace(go.Scatter(
            x=[0, 100], y=[0, 100], mode="lines",
            line=dict(color="#888", dash="dash", width=1),
            showlegend=False, hoverinfo="skip",
        ), row=row, col=col)
        fig.update_xaxes(title=x_lab, range=[-2, 102], gridcolor="#eee", row=row, col=col)
        fig.update_yaxes(title=y_lab, range=[-2, 102], gridcolor="#eee", row=row, col=col)

    fig.update_layout(
        title=("<b>H1 validation</b>  -  contextual rankings (Y) vs naive (X)  "
               "<span style='font-size:12px;color:#888'>"
               "(within-role percentiles)</span>"),
        height=900, width=1200, plot_bgcolor="white",
        margin=dict(t=110, b=70, l=80, r=120),
        legend=dict(title="Role", yanchor="top", y=1, xanchor="left", x=1.02),
    )
    fig.show()
    _render_static(fig)

    # --- Top-15 MID head-to-head ----------------------------------------
    role = "MID"
    sub  = df[df["macro_role"] == role].copy()
    naive_top = (sub.nlargest(15, "passes_per90")
                    [["player", "team", "passes_per90", "PROGRESSION_idx"]]
                    .reset_index(drop=True))
    ctx_top   = (sub.nlargest(15, "PROGRESSION_idx")
                    [["player", "team", "passes_per90", "PROGRESSION_idx"]]
                    .reset_index(drop=True))
    naive_set, ctx_set = set(naive_top["player"]), set(ctx_top["player"])
    overlap   = naive_set & ctx_set
    only_naive = sorted(naive_set - ctx_set)
    only_ctx   = sorted(ctx_set   - naive_set)

    print("=" * 86)
    print(f"  Top-15 {role}:  naive (passes /90)  vs  contextual (PROGRESSION idx)")
    print("=" * 86)
    print(f"  Overlap         : {len(overlap):2d}/15")
    print(f"  Only in naive   : {len(only_naive):2d} - {only_naive}")
    print(f"  Only contextual : {len(only_ctx):2d} - {only_ctx}")
    print("-" * 86)

    print(f"\n  TOP-15 BY NAIVE  (passes /90)\n")
    naive_top["also_in_ctx"] = naive_top["player"].isin(ctx_set)
    print(naive_top.round(1).to_string(index=False))
    print(f"\n  TOP-15 BY CONTEXTUAL  (PROGRESSION idx)\n")
    ctx_top["also_in_naive"] = ctx_top["player"].isin(naive_set)
    print(ctx_top.round(1).to_string(index=False))

    print("\n" + "=" * 86)
    print("  TOP-15 OVERLAP BETWEEN NAIVE AND CONTEXTUAL BY ROLE")
    print("=" * 86)
    print(f"  {'role':<6s} {'pool':>5s} {'overlap':>9s} "
          f"{'only naive':>12s} {'only ctx':>12s}")
    print("-" * 86)
    for r in config.MACRO_ROLES:
        s = df[df["macro_role"] == r]
        if len(s) < 15:
            print(f"  {r:<6s} {len(s):>5d}  (pool < 15, skipped)")
            continue
        a = set(s.nlargest(15, "passes_per90")["player"])
        b = set(s.nlargest(15, "PROGRESSION_idx")["player"])
        print(f"  {r:<6s} {len(s):>5d} {len(a & b):>9d} "
              f"{len(a - b):>12d} {len(b - a):>12d}")
    print("=" * 86)


# =============================================================================
# H1 evidence — scouting discoveries (rank-shift bar charts)
# =============================================================================
# INDEX_PROXIES is defined above (h1_summary section) and reused here so the
# two consumers stay in sync.


def _bar_panel(fig, row, col, sub_df, idx, naive, color_lookup, x_title):
    """Add a horizontal bar trace showing player names and rank shift."""
    fig.add_trace(go.Bar(
        y=sub_df["player"] + "  · " + sub_df["macro_role"],
        x=sub_df[f"delta_{idx}"],
        orientation="h",
        marker=dict(color=[color_lookup[r] for r in sub_df["macro_role"]],
                    line=dict(color="#222", width=0.5)),
        text=sub_df[f"delta_{idx}"].round(0).astype(int),
        textposition="outside",
        textfont=dict(size=10, color="#333"),
        customdata=np.column_stack([
            sub_df["team"],
            sub_df[f"{idx}_idx"].round(1),
            sub_df[f"{naive}__p"].round(1),
        ]),
        hovertemplate=("<b>%{y}</b><br>Team: %{customdata[0]}"
                       "<br>Contextual idx: %{customdata[1]}"
                       "<br>Naive pct: %{customdata[2]}"
                       "<br>Δ: %{x:.1f}<extra></extra>"),
        showlegend=False,
    ), row=row, col=col)
    fig.update_xaxes(title=x_title, row=row, col=col)
    fig.update_yaxes(automargin=True, row=row, col=col)


def scouting_discoveries(df: pd.DataFrame, pct: pd.DataFrame,
                          top_n: int = 12,
                          min_minutes: int = config.ANALYSIS_MIN_MINUTES):
    """Plot top-N positive (discoveries) and negative (overrated) rank shifts
    per composite index, plus a per-role console summary.

    ``min_minutes`` filters out low-sample players before the comparison.
    """
    df  = df.copy()
    pct = pct.copy()
    if min_minutes:
        keep = df["minutes_played"] >= min_minutes
        df, pct = df[keep].reset_index(drop=True), pct[keep].reset_index(drop=True)
    df["passes_per90"] = df["passes_total"] / df["minutes_played"] * 90

    for theme in RADAR_SPECS:
        df[f"{theme}_idx"] = pct[f"{theme}_idx"].values

    for idx, naive, _ in INDEX_PROXIES:
        if f"{naive}__p" not in df.columns:
            df[f"{naive}__p"] = _role_pct(df, naive)
        df[f"delta_{idx}"] = df[f"{idx}_idx"] - df[f"{naive}__p"]

    # Chart 1: discoveries (positive Δ)
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=[f"<b>{idx}</b>  -  naive proxy: {label}"
                        for idx, _, label in INDEX_PROXIES],
        horizontal_spacing=0.22, vertical_spacing=0.16,
    )
    for i, (idx, naive, _label) in enumerate(INDEX_PROXIES):
        row, col = i // 2 + 1, i % 2 + 1
        top = df.nlargest(top_n, f"delta_{idx}").iloc[::-1]
        _bar_panel(fig, row, col, top, idx, naive, _ROLE_COLOR,
                   "Δ percentile  (contextual − naive)")
    fig.update_layout(
        title=("<b>Scouting discoveries</b>  -  players surfaced by "
               "contextual indices but missed by naive stats"),
        height=950, width=1300, plot_bgcolor="#fafafa",
        margin=dict(t=110, b=60, l=80, r=60),
    )
    fig.show()
    _render_static(fig)

    # Chart 2: overrated (negative Δ)
    fig2 = make_subplots(
        rows=2, cols=2,
        subplot_titles=[f"<b>{idx}</b>  -  naive proxy: {label}"
                        for idx, _, label in INDEX_PROXIES],
        horizontal_spacing=0.22, vertical_spacing=0.16,
    )
    for i, (idx, naive, _label) in enumerate(INDEX_PROXIES):
        row, col = i // 2 + 1, i % 2 + 1
        bot = df.nsmallest(top_n, f"delta_{idx}").iloc[::-1]
        _bar_panel(fig2, row, col, bot, idx, naive, _ROLE_COLOR,
                   "Δ percentile  (contextual − naive)")
    fig2.update_layout(
        title=("<b>Naive overrating</b>  -  players whose naive rank is "
               "inflated by team context"),
        height=950, width=1300, plot_bgcolor="#fafafa",
        margin=dict(t=110, b=60, l=80, r=60),
    )
    fig2.show()
    _render_static(fig2)

    # Per-role top 3 discoveries
    print("=" * 92)
    print("  PER-ROLE TOP 3 DISCOVERIES BY INDEX  (largest positive Δ percentile)")
    print("=" * 92)
    for idx, naive, label in INDEX_PROXIES:
        print(f"\n  {idx}  (naive proxy: {label})")
        print("  " + "-" * 86)
        for r in config.MACRO_ROLES:
            s = df[df["macro_role"] == r]
            if len(s) < 5:
                continue
            top3 = s.nlargest(3, f"delta_{idx}")
            names = ", ".join(f"{p} (+{d:.0f})"
                              for p, d in zip(top3["player"], top3[f"delta_{idx}"]))
            print(f"  {r:<6s}: {names}")
    print("=" * 92)


# =============================================================================
# Final export
# =============================================================================
def export_indices_csv(df: pd.DataFrame, pct: pd.DataFrame,
                       out_path=config.PLAYER_INDICES_PATH):
    """Persist composite indices + within-role percentiles for every player.

    Identity / annotation columns are written at full precision so the
    values are byte-identical to ``player_space_control_aggregated.csv``.
    Composite indices and percentiles are bounded to [0, 100] and rounded
    to 2 decimals for readability (no real precision loss).
    """
    cols = ["player", "team", "primary_role", "macro_role", "minutes_played",
            "coverage_pct", "pressure_resistance_n",
            "gravity_composite_pct", "gravity_directional_m"]
    out = df[cols].copy()

    # Integer counts with possible NaNs -> nullable Int64 (so they save as
    # "10" not "10.0" in the CSV).
    out["pressure_resistance_n"] = out["pressure_resistance_n"].astype("Int64")

    # Composite indices and within-role percentiles, rounded to 2 decimals.
    for theme in RADAR_SPECS:
        out[f"idx__{theme}"] = pct[f"{theme}_idx"].round(2)
    radar_vars = [var for spec in RADAR_SPECS.values() for _, var, _ in spec]
    # Add the DANGEROUSNESS headline variable explicitly: it is the variable
    # that *forms* idx__DANGEROUSNESS but is not on the radar, so the loop
    # above would otherwise drop it from the export, making the CSV
    # insufficient to reconstruct the index downstream.
    from .indices import DANGEROUSNESS_HEADLINE_VAR
    if DANGEROUSNESS_HEADLINE_VAR not in radar_vars:
        radar_vars.append(DANGEROUSNESS_HEADLINE_VAR)
    for var in radar_vars:
        out[f"pct__{var}"] = pct[f"{var}__p"].round(2)

    idx_cols = [f"idx__{t}" for t in RADAR_SPECS]
    out["_sortkey"] = out[idx_cols].mean(axis=1)
    out = (out.sort_values(["macro_role", "_sortkey"], ascending=[True, False])
              .drop(columns=["_sortkey"]))

    out.to_csv(out_path, index=False)
    n_pct = len(radar_vars)
    print(f"✔ Saved {out_path}  -  {len(out)} rows × {len(out.columns)} columns")
    print(f"  Identity: 9   Indices: 4   Percentiles: {n_pct}")
    return out
