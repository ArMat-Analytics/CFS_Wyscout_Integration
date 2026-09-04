"""
urs.py — H3 Off-Ball Movement
Per-player aggregation of the off-ball KPIs and split-half reliability.

Three derived event-level signals per (event, candidate teammate):
    off_ball_value_i = xEPV_H2(target_i)                              # offered value
    urs_i            = xEPV_H2(target_i) * (1 - received_i)           # uncapitalised
    captured_i       = xEPV_H2(target_i) *      received_i            # realised

Aggregated per player on the H1 minutes pool (≥ 135 min, no GK):
    off_ball_potential_per90  = Σ off_ball_value / minutes * 90       # presence × quality
    urs_per90                 = Σ urs            / minutes * 90       # latent EPV / 90
    capitalization_rate       = Σ captured / Σ off_ball_value  ∈ [0,1]# realised share
    latency_rate              = 1 − capitalization_rate               # latent share

URS /90 is the H3 headline (single number that combines presence and latency
in EPV units, directly comparable with H1 / H2 numbers).  The radar uses
Potential, xEPV mean and Latency as the three independent angles.
"""

from __future__ import annotations

import logging
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

_H3_DIR = Path(__file__).resolve().parents[1]
if str(_H3_DIR) not in sys.path:
    sys.path.insert(0, str(_H3_DIR))

from src.config import (
    COMPETITION_ID, SEASON_ID,
    RECEIVED_WINDOW_S, MIN_MINUTES,
    XEPV_PARQUET, URS_CSV,
    PITCH_LENGTH, PITCH_WIDTH,
    X_SCALE, Y_SCALE,
    H1_PLAYER_AGG,
    load_h2_package,
)

logger = logging.getLogger(__name__)


def main() -> None:
    """Aggregate xEPV into per-player URS_per90 and save player_urs_aggregated.csv.

    Reads  : data/off_ball_xepv.parquet  (produced by xepv.main())
    Writes : data/player_urs_aggregated.csv
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from statsbombpy import sb

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s  %(levelname)s  %(message)s")

    if not XEPV_PARQUET.exists():
        raise FileNotFoundError(f"{XEPV_PARQUET} not found. Run xepv.main() first.")

    cand = pd.read_parquet(XEPV_PARQUET)
    logger.info("Loaded %d xEPV-confident rows", len(cand))

    matches = sb.matches(competition_id=COMPETITION_ID, season_id=SEASON_ID)

    if "received" not in cand.columns:
        raise ValueError(
            f"'received' column missing from {XEPV_PARQUET}. "
            "Re-run xepv.main() — it now writes the received flag too."
        )
    logger.info("received=True: %d / %d  (%.1f%%)",
                int(cand["received"].sum()), len(cand),
                100 * cand["received"].mean())

    # Two complementary signals per candidate:
    #   off_ball_value = xEPV — value of the run regardless of capitalisation
    #   urs            = xEPV · (1 − received) — the latent (non-served) share
    # xEPV already encodes upside vs turnover penalty (H2 design), so no
    # separate Pitch-Control filter is needed.
    cand["urs"] = cand["xepv"] * (1 - cand["received"].astype(float))
    cand["xepv_received"] = cand["xepv"] * cand["received"].astype(float)

    agg = (
        cand.groupby("player")
        .agg(
            team                   = ("team",          "first"),
            urs_sum                = ("urs",           "sum"),
            off_ball_potential_sum = ("xepv",          "sum"),
            off_ball_captured_sum  = ("xepv_received", "sum"),
            xepv_mean              = ("xepv",          "mean"),
            n_confident_candidates = ("xepv",          "count"),
            n_received             = ("received",      "sum"),
        )
        .reset_index()
    )
    agg["receiver_conf_rate"] = agg["n_received"] / agg["n_confident_candidates"]

    # ── Role + minutes: H1's player_space_control_aggregated.csv is THE source ──
    # H2 reads this exact file with these exact columns (decision_quality.py:
    # usecols player/team/primary_role/macro_role/minutes_played) and an inner
    # join + min_minutes filter. We mirror it byte-for-byte so H1/H2/H3 share an
    # identical 272-player pool AND an identical macro_role per player. Crucially
    # `macro_role` is read pre-computed — H1 derives it as the per-event role
    # MODE (aggregation.py), not from the nominal primary_role — so we must NOT
    # recompute it from primary_role here (that diverged on 11 players, e.g.
    # Bruno Fernandes CAM-nominal but MID by minutes played).
    if not H1_PLAYER_AGG.exists():
        raise FileNotFoundError(
            f"H1 player aggregate not found: {H1_PLAYER_AGG}\n"
            "URS aggregation requires H1's authoritative role/minutes table "
            "(player_space_control_aggregated.csv), the same file H2 reads."
        )
    h1 = pd.read_csv(
        H1_PLAYER_AGG,
        usecols=["player", "team", "primary_role", "macro_role", "minutes_played"],
    )
    logger.info("Loaded H1 player aggregate: %d players (GKs already dropped by H1)", len(h1))

    # Inner join → restrict to H1's pool exactly (mirrors H2's aggregate_players).
    # H1's file has already dropped goalkeepers, so no GK filter is needed here.
    agg = agg.merge(h1, on=["player", "team"], how="inner")

    # Apply the same minutes threshold as H2 (ANALYSIS_MIN_MINUTES = 135).
    eligible = agg["minutes_played"] >= MIN_MINUTES
    mins_safe = agg["minutes_played"].replace(0, np.nan)
    agg["urs_per90"] = np.where(
        eligible, agg["urs_sum"] / mins_safe * 90, np.nan,
    )
    agg["off_ball_potential_per90"] = np.where(
        eligible, agg["off_ball_potential_sum"] / mins_safe * 90, np.nan,
    )
    agg["n_confident_per90"] = np.where(
        eligible, agg["n_confident_candidates"] / mins_safe * 90, np.nan,
    )
    # capitalisation rate = captured / potential ∈ [0, 1]; what fraction of the
    # off-ball value the player generates ends up being realised by teammates.
    pot = agg["off_ball_potential_sum"]
    cap = agg["off_ball_captured_sum"]
    agg["capitalization_rate"] = np.where(
        eligible & (pot > 0),
        (cap / pot.replace(0, np.nan)).clip(lower=0.0, upper=1.0),
        np.nan,
    )
    # latency rate = 1 - capitalisation; the radar reads it directly so high
    # values consistently mean "more uncapitalised value".
    agg["latency_rate"] = np.where(
        eligible & agg["capitalization_rate"].notna(),
        1.0 - agg["capitalization_rate"], np.nan,
    )

    # Within-role percentiles for the radar / leaderboard. SAME recipe as
    # H1 (indices.build_pct_table) and H2 (decision_quality): a plain
    # groupby("macro_role")[col].rank(pct=True) * 100, rounded to 1 decimal.
    # Computed on the eligible pool only; ineligible rows stay NaN. No
    # minimum-group-size guard — H1/H2 don't have one, and pandas' rank
    # already skips NaN, so the six full role pools (min CAM ≈ 20) are safe.
    elig_idx = agg.index[eligible]

    def _pct_within_role(col: str, out_col: str) -> None:
        agg[out_col] = np.nan
        pct = (agg.loc[elig_idx]
                  .groupby("macro_role")[col]
                  .rank(pct=True)
                  .mul(100)
                  .round(1))
        agg.loc[pct.index, out_col] = pct

    _pct_within_role("urs_per90",                "urs_pct_within_role")
    _pct_within_role("off_ball_potential_per90", "potential_pct_within_role")
    _pct_within_role("xepv_mean",                "xepv_mean_pct_within_role")
    _pct_within_role("latency_rate",             "latency_pct_within_role")

    agg = agg.sort_values("urs_per90", ascending=False, na_position="last")

    URS_CSV.parent.mkdir(parents=True, exist_ok=True)
    agg.to_csv(URS_CSV, index=False)
    logger.info(
        "Saved %s  (%d rows, %d eligible >= %d min)",
        URS_CSV, len(agg), int(eligible.sum()), MIN_MINUTES,
    )


def show_uncapitalised_runs(player: str, n: int = 4) -> None:
    """Plot top-N highest-URS events for `player` (style: H1 show_line_breakers)."""
    import matplotlib.pyplot as plt
    from scipy.spatial import ConvexHull

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from statsbombpy import sb

    if not XEPV_PARQUET.exists():
        logger.error("%s not found — run xepv.main() first.", XEPV_PARQUET)
        return

    cand = pd.read_parquet(XEPV_PARQUET)
    if "urs" not in cand.columns:
        cand["urs"] = (cand["xepv"]
                       * (1 - cand.get("received", pd.Series(False, index=cand.index)).astype(float)))

    player_rows = cand[(cand["player"] == player) & cand["urs"].notna()].nlargest(n, "urs")
    if player_rows.shape[0] == 0:
        logger.warning("No rows for player: %s", player)
        return

    ncols = min(n, len(player_rows))
    fig, axes = plt.subplots(1, ncols, figsize=(6 * ncols, 6))
    if ncols == 1:
        axes = [axes]

    for ax, (_, row) in zip(axes, player_rows.iterrows()):
        events     = sb.events(match_id=row["match_id"])
        frames_raw = sb.frames(match_id=row["match_id"], fmt="dict")
        if not frames_raw:
            ax.set_title("No frame"); continue

        frames_list = frames_raw if isinstance(frames_raw, list) else list(frames_raw)
        frames: pd.DataFrame = pd.DataFrame(frames_list)
        frames = frames.explode("freeze_frame", ignore_index=True)
        frames = pd.concat(
            [frames.drop(columns=["freeze_frame"]),
             pd.json_normalize(frames["freeze_frame"])],
            axis=1,
        )
        event_col = "event_uuid" if "event_uuid" in frames.columns else "id"
        prow = events[events["id"] == row["event_id"]]
        if prow.shape[0] == 0:
            continue
        prow = prow.iloc[0]
        fr   = frames[frames[event_col] == row["event_id"]]

        ax.set_xlim(-3, PITCH_LENGTH + 3)
        ax.set_ylim(-3, PITCH_WIDTH + 3)
        ax.set_aspect("equal")
        _draw_pitch(ax)

        opp_pts = np.array([
            [loc[0] * X_SCALE, loc[1] * Y_SCALE]
            for loc in fr[fr["teammate"] == False]["location"].tolist()
            if loc is not None
        ], dtype=float)
        if opp_pts.shape[0] >= 3:
            try:
                hull = ConvexHull(opp_pts)
                ax.fill(opp_pts[hull.vertices, 0], opp_pts[hull.vertices, 1],
                        alpha=0.15, color="red")
                loop = np.append(hull.vertices, hull.vertices[0])
                ax.plot(opp_pts[loop, 0], opp_pts[loop, 1], "r--", lw=1.2, alpha=0.7)
            except Exception:
                pass

        # All visible teammates in a neutral grey — context only. We deliberately
        # do NOT colour them by xEPV: a second warm colour competed with both the
        # opponent block (red) and the highlighted candidate, and the gold arrow
        # already shows where the ball actually went. The eye should go straight
        # to the one player this panel is about: the uncapitalised candidate.
        for _, dot in fr[(fr["teammate"] == True) & (fr["actor"] == False)].iterrows():
            loc = dot["location"]
            if loc is None: continue
            xm, ym = loc[0] * X_SCALE, loc[1] * Y_SCALE
            ax.scatter(xm, ym, s=110, color="#bdbdbd",
                       edgecolors="white", linewidths=0.8, zorder=3)

        # The highlighted candidate: the teammate who made the high-value run that
        # was not served. Filled in the H3 family green so it stands clear of the
        # red opponent hull.
        ax.scatter(row["target_x_m"], row["target_y_m"],
                   s=240, color=H3_COLOR, edgecolors="black", linewidths=1.5, zorder=5)

        sx, sy = row["sender_x_m"], row["sender_y_m"]
        ax.scatter(sx, sy, s=150, color="cyan", edgecolors="black", linewidths=1.5, zorder=4)
        pend = prow.get("pass_end_location")
        if pend is not None:
            ax.annotate("", xy=(float(pend[0]) * X_SCALE, float(pend[1]) * Y_SCALE),
                        xytext=(sx, sy),
                        arrowprops=dict(arrowstyle="->", color="gold", lw=2))

        ax.set_title(
            f"{row['sender']}  {prow['minute']}'\n"
            f"xEPV={row['xepv']:.3f}  xpass={row.get('xpass', float('nan')):.2f}"
            f"  EPV={row.get('epv_target', float('nan')):.3f}\n"
            f"URS={row['urs']:.4f}  candidate: {player.split()[-1]}",
            fontsize=9,
        )

    fig.suptitle(f"Top-{n} uncapitalised runs — {player}", fontsize=13)
    fig.patch.set_facecolor("white")
    plt.tight_layout()
    plt.show()


def _player_minutes_from_events(match_ids: list[int]) -> pd.DataFrame:
    """Per-(player, team) minutes computed exactly like H1's player_totals.

    H1 formula (player_totals.py line 144):
        minutes_played_per_match = events.minute.max() - events.minute.min()
    Summed across the given match_ids. Names match H1's CSV column 'player'
    (StatsBomb full names from event['player']).
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from statsbombpy import sb

    rows = []
    for mid in match_ids:
        try:
            ev = sb.events(match_id=int(mid))
        except Exception:
            continue
        ev = ev.dropna(subset=["player"])
        per_match = (ev.groupby(["team", "player"])["minute"]
                       .agg(["min", "max"]).reset_index())
        per_match["minutes_played"] = per_match["max"] - per_match["min"]
        for _, r in per_match.iterrows():
            rows.append({"player": r["player"], "team": r["team"],
                         "minutes_played": float(r["minutes_played"])})

    return (pd.DataFrame(rows)
              .groupby(["player", "team"], as_index=False)
              .agg(minutes_played=("minutes_played", "sum")))


def split_half_reliability(min_minutes_per_half: int = 90) -> None:
    """Spearman rho between first-half and second-half URS_per90 rankings.

    Minutes per half are computed with the same H1 events-based formula
    (player_totals.py: minute.max - minute.min), so the split-half pool is
    consistent with the main URS pool. Player names already match H1
    (full names), so we join on (player, team) directly.
    """
    import matplotlib.pyplot as plt

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from statsbombpy import sb

    if not XEPV_PARQUET.exists():
        logger.error("%s not found — run xepv.main() first.", XEPV_PARQUET)
        return

    cand    = pd.read_parquet(XEPV_PARQUET)
    matches = sb.matches(competition_id=COMPETITION_ID, season_id=SEASON_ID)
    matches = matches.sort_values("match_date").reset_index(drop=True)
    mid_pt  = len(matches) // 2

    first_ids  = matches["match_id"].iloc[:mid_pt].tolist()
    second_ids = matches["match_id"].iloc[mid_pt:].tolist()

    if "urs" not in cand.columns:
        cand["urs"] = (cand["xepv"]
                       * (1 - cand.get("received", pd.Series(False, index=cand.index)).astype(float)))

    results: dict[str, pd.Series] = {}
    for label, half_ids in [("first", first_ids), ("second", second_ids)]:
        sub = cand[cand["match_id"].isin(half_ids)]
        agg = (sub.groupby(["player", "team"])
                  .agg(urs_sum=("urs", "sum")).reset_index())

        half_mins = _player_minutes_from_events(half_ids)
        agg = agg.merge(half_mins, on=["player", "team"], how="left")

        agg = agg[agg["minutes_played"].notna() &
                  (agg["minutes_played"] >= min_minutes_per_half)]
        agg["urs_per90"] = agg["urs_sum"] / agg["minutes_played"].replace(0, np.nan) * 90
        # one index key per player (player+team makes it unambiguous)
        results[label] = (agg.set_index(["player", "team"])["urs_per90"].dropna())

    common = results["first"].index.intersection(results["second"].index)
    if len(common) < 10:
        logger.warning("Only %d players in both halves.", len(common))
        return

    y1 = results["first"].loc[common]
    y2 = results["second"].loc[common]
    rho, pval = spearmanr(y1, y2)

    print("=" * 60)
    print("  URS_per90 — split-half reliability")
    print("=" * 60)
    print(f"  Matches first half  : {len(first_ids)}")
    print(f"  Matches second half : {len(second_ids)}")
    print(f"  Players in both     : {len(common)}")
    print(f"  Spearman rho        : {rho:.3f}")
    print(f"  p-value             : {pval:.4f}")
    if rho >= 0.50:
        print("  rho >= 0.50 — URS_per90 shows stable inter-half agreement.")
    else:
        print("  rho < 0.50 — investigate receiver-resolution noise.")
    print("=" * 60)

    fig, ax = plt.subplots(figsize=(7, 7))
    ax.scatter(y1, y2, s=40, alpha=0.6, edgecolors="white", linewidths=0.5)
    lim = max(y1.max(), y2.max()) * 1.05
    ax.plot([0, lim], [0, lim], "--", color="grey", lw=1.2)
    ax.set_xlabel("URS_per90 — first half", fontsize=11)
    ax.set_ylabel("URS_per90 — second half", fontsize=11)
    ax.set_title(f"Split-half reliability — URS_per90\nSpearman rho = {rho:.3f}  (n={len(common)})",
                 fontsize=12)
    plt.tight_layout()
    plt.show()

# Radar axes — same vocabulary as H2's viz.RADAR_AXES: (label, raw column,
# within-role percentile column). All three are "outside = better":
#   - Off-Ball Potential /90  -> presence × quality of off-ball exposure
#   - xEPV mean               -> quality of the average frame
#   - Latency (1 − Cap.)      -> latent (uncapitalised) share — high = more latent
# URS /90 is the headline INDEX (its within-role percentile), NOT a radar axis:
# URS = Potential × Latency, so an URS axis would be collinear with the other
# two. Off-Ball Potential is itself strongly correlated with URS (ρ ≈ 0.97,
# see §8.2) — kept on the radar because it is the most scout-readable volume
# axis (mirrors H2 keeping correlated axes and documenting it, rather than
# dropping readability). The radar decomposes the index; it does not repeat it.
RADAR_AXES = [
    ("Off-Ball Potential /90", "off_ball_potential_per90", "potential_pct_within_role"),
    ("xEPV mean",              "xepv_mean",                "xepv_mean_pct_within_role"),
    ("Latency (1 − Cap.)",     "latency_rate",             "latency_pct_within_role"),
]
H3_COLOR   = "#2ca02c"   # H3 family color (green; distinct from H1/H2 families)
H3_COLOR_B = "#d62728"   # second player in the head-to-head overlay


def _render_static(fig):
    """Emit a static PNG copy of a Plotly figure into the notebook output.

    Mirrors H2's viz helper. GitHub renders only embedded images in .ipynb
    cells, not Plotly's interactive HTML, so the static copy keeps the
    notebook viewable on github.com.
    """
    from IPython.display import Image, display
    display(Image(fig.to_image(format="png", scale=2)))


def _radar_hover(row, role: str) -> list[str]:
    """Per-axis hover: '<b>Label</b><br>Raw: X<br>Pct in ROLE: Y'.

    Same template as H2's viz._hover_for. Raw is the unflipped measurement.
    """
    hov = []
    for lab, raw_col, pct_col in RADAR_AXES:
        hov.append(
            f"<b>{lab}</b><br>Raw: {row[raw_col]:.3f}<br>"
            f"Pct in {role}: {row[pct_col]:.0f}")
    return hov


def off_ball_radar(players, urs_csv=None, show_static: bool = True, save: str | None = None):
    """Off-Ball 3-axis radar (Plotly), styled like H2's Decision-Quality radar.

    A headline INDEX (URS /90 within-role percentile) sits next to a within-role
    percentile radar that decomposes the profile behind it. Same chrome as H2's
    `viz.plot_dq_radar`: line width 2.5, fill opacity 0.35, radial range
    [0, 100] with ticks [20, 40, 60, 80], hover with raw + within-role
    percentile. A static PNG is emitted (`show_static`) so the .ipynb stays
    viewable on github.com.

    `players` may be a single name or a list/tuple (head-to-head overlay).
    Names must match the CSV `player` column (full StatsBomb names).
    """
    import plotly.graph_objects as go

    if isinstance(players, str):
        players = [players]
    csv_path = urs_csv if urs_csv is not None else URS_CSV
    df = pd.read_csv(csv_path)

    pct_cols = [pct for _, _, pct in RADAR_AXES]
    labels   = [lab for lab, _, _ in RADAR_AXES]

    rows = []
    for name in players:
        row = df[df["player"] == name]
        if row.empty:
            logger.warning("Player not found in %s: %s", csv_path, name)
            continue
        r = row.iloc[0]
        if r[pct_cols].isna().any():
            logger.warning("%s has NaN percentiles (likely below MIN_MINUTES).", name)
            continue
        rows.append((name, r))
    if not rows:
        return None

    labels_c = labels + [labels[0]]          # close the loop
    colors   = [H3_COLOR, H3_COLOR_B, "#1f77b4", "#9467bd"]

    fig = go.Figure()
    for i, (name, r) in enumerate(rows):
        role = r["macro_role"]
        vals = [0.0 if pd.isna(r[p]) else float(r[p]) for p in pct_cols]
        hov  = _radar_hover(r, role)
        col  = colors[i % len(colors)]
        fig.add_trace(go.Scatterpolar(
            r=vals + [vals[0]], theta=labels_c, fill="toself",
            name=f"{name} ({role})",
            hoverinfo="text", hovertext=hov + [hov[0]],
            line=dict(color=col, width=2.5),
            fillcolor=col, opacity=0.35,
            showlegend=len(rows) > 1,
        ))

    if len(rows) == 1:
        name, r = rows[0]
        role = r["macro_role"]
        idx = r.get("urs_pct_within_role", float("nan"))
        title = (f"<b>OFF-BALL MOVEMENT</b>  ·  URS idx {idx:.0f}/100"
                 f"<br><span style='font-size:12px;color:#666'>"
                 f"{name}  ·  {r['team']}  ·  {r['primary_role']} ({role})  ·  "
                 f"{int(r['minutes_played'])} min  ·  "
                 f"URS/90 = {r['urs_per90']:.3f}</span>")
    else:
        title = ("<b>OFF-BALL MOVEMENT</b>  ·  head-to-head"
                 "<br><span style='font-size:12px;color:#666'>"
                 "within-role percentiles</span>")

    fig.update_layout(
        title=title,
        polar=dict(
            radialaxis=dict(range=[0, 100], tickvals=[20, 40, 60, 80],
                            gridcolor="#ddd", tickfont=dict(size=9)),
            angularaxis=dict(tickfont=dict(size=11)),
        ),
        width=560, height=480, margin=dict(t=80, b=40, l=60, r=60),
    )
    if save:
        fig.write_image(save, scale=2)
    if show_static:
        _render_static(fig)
    return fig


def _draw_pitch(ax, color="black", lw=1.4):
    """Consistent pitch style matching H1/H2."""
    import matplotlib.patches as patches
    L, W = PITCH_LENGTH, PITCH_WIDTH
    ax.set_facecolor("#f5f5f5")
    ax.add_patch(patches.Rectangle((0, 0), L, W, color="white", zorder=0))
    ax.plot([0, L, L, 0, 0], [0, 0, W, W, 0], color=color, lw=lw)
    ax.plot([L/2, L/2], [0, W], color=color, lw=lw)
    ax.add_patch(patches.Circle((L/2, W/2), 9.15, fill=False, edgecolor=color, lw=lw))
    ax.add_patch(patches.Rectangle((0, (W-40.32)/2), 16.5, 40.32, fill=False, edgecolor=color, lw=lw))
    ax.add_patch(patches.Rectangle((L-16.5, (W-40.32)/2), 16.5, 40.32, fill=False, edgecolor=color, lw=lw))
    ax.set_xlim(-2, L+2); ax.set_ylim(-2, W+2)
    ax.set_aspect("equal")
    ax.set_xticks([]); ax.set_yticks([])
