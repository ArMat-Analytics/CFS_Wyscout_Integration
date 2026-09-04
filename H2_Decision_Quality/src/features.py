"""xPass feature engineering — curated set of 12 logical features.

Every feature is computed at t₀ (the freeze frame at the moment the sender
touches the ball). The same routine works for the chosen pass and for any
hypothetical alternative target, so features are directly comparable
between training (real passes) and inference (candidate passes). Each
helper takes the candidate target position explicitly — never reads
`pass.end_location` to avoid leakage of t₁ information.

Each feature carries a clear physical interpretation and an expected sign
(direction in which it pushes P(complete) up or down). The model can find
non-linear interactions between them automatically, but the individual
descriptions below summarise what each one captures by itself.

Feature list — 12 logical features, 13 model columns after one-hot
==================================================================

GEOMETRY OF THE PASS (4)
------------------------
1. pass_distance — meters; Euclidean sender → target.
   Longer passes give defenders more time to react and the ball more
   trajectory uncertainty. Strong negative effect on completion. Typical
   range 3–60 m, median ~13 m in elite football.

2. pass_angle_forward — degrees, 0..180, 0 = directly toward opponent goal.
   Forward passes are harder than lateral or backward ones (smaller
   windows, more committed defending). 0–60° = forward, 60–120° = lateral,
   120–180° = backward. Higher value → easier completion.

3. start_x — meters along the pitch length, sender's x position.
   Proxy for which third of the pitch the action is in. Passes from
   advanced positions (high start_x) face tighter defending in the
   final third, so the sign is mildly negative.

4. target_in_final_third — binary, 1 if target_x ≥ 70 m.
   Discrete companion to start_x focused on the receiver: final-third
   targets attract more pressure. Negative effect on completion.

DEFENDERS BLOCKING THE PASS LINE (3, all continuous)
-----------------------------------------------------
5. min_dist_def_to_receiver — meters; distance from the candidate target
   to the closest opponent at t₀.
   The single most informative signal: a free receiver is much easier to
   hit. Strong positive effect on completion. Range 0.5–25 m typical.

6. min_perp_dist_to_line — meters; smallest perpendicular distance of any
   in-segment opponent to the pass line. Sentinel `20 m` when no defender
   projects onto the segment (open lane).
   Captures whether the *trajectory* itself is contested, independent of
   what is around the receiver. Higher = clearer line. 

7. pass_lane_density_score — dimensionless; inverse-distance-weighted
   "gauntlet" score: `Σ 1 / (perp_dist + 0.5)` over in-segment defenders.
   Smooth complement to the discrete corridor counts: a defender 0.5 m
   off the line contributes 1.0, one 5 m off contributes 0.18, one 10 m
   off contributes 0.10. High score = busy lane → harder pass.

PRESSURE ON THE ACTOR (sender, 2)
---------------------------------
8. sender_pressure_count_25 — integer, opponents within 2.5 m of the
   sender. Same definition as H1's "under pressure" flag.
   Pressure on the passer affects technical execution: rushed passes
   are less accurate. Negative effect on completion.

9. min_dist_def_to_sender — meters; continuous companion to feature 8.
   When sender is alone the value can reach 30 m+; when surrounded it
   falls below 1 m. Higher = freer sender. Positive effect.

LOCAL DENSITY AROUND THE RECEIVER (2)
-------------------------------------
10. defender_density_3m_receiver — integer; opponents within 3 m of the
    candidate target. Captures the immediate crowd: a single defender at
    1.5 m is already disruptive. Negative effect.

11. teammate_density_5m_receiver — integer; teammates within 5 m of the
    target (excluding the candidate target itself).
    Receiver support — tells the model whether the would-be receiver has
    near-by options to lay off if pressed. Mildly positive effect.

PASS TYPE (1 logical, 2 model columns; Ground = baseline)
---------------------------------------------------------
12. pass_height_low / pass_height_high — binary indicators of pass height.
    Both 0 → Ground Pass (the baseline, ~88% of the corpus).
    Lofted passes (Low or High) introduce vertical-trajectory uncertainty
    and make first-touch reception harder. Negative effect for both
    indicators, with `high` typically carrying a stronger negative weight
    than `low` (more time in the air, harder reception).

Audit notes — features computed but excluded from FEATURE_COLS
==============================================================
* `defenders_in_corridor_5m`, `defenders_in_corridor_2m` — integer counts
  of defenders inside a hard-threshold band along the pass line.
  Redundant with the continuous `min_perp_dist_to_line` and
  `pass_lane_density_score`.
* `receiver_pressure_count_25` — redundant with `min_dist_def_to_receiver`
  in 95 % of the corpus (it is essentially a binary indicator that the min
  distance is below 2.5 m); logit coefficient = 0.005, pure noise.
* `pass_height_ground` — dropped to remove the perfect collinearity of
  three indicators that always sum to 1. Ground Pass is the implicit
  baseline; the remaining two indicators read as "Low / High vs Ground".

These four diagnostic columns are still computed and kept on the corpus
DataFrame for segmentation and inspection — they just do not feed the
model.

Geometry primitives (`count_bypassed`, `count_opponents_within`) live in
the local `src.geometry` module — they mirror H1's line-breaker primitives
to keep the definition of pressure (radius 2.5 m, threshold 2 opponents)
identical across the two projects.
"""
from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd

from . import config as cfg
from .geometry import count_bypassed, count_opponents_within


# Sentinel for `min_perp_dist_to_line` when no opponent projects onto the
# pass segment. 20 m is well past any plausible "blocking" distance — using
# a large finite value preserves the row instead of producing NaN.
_NO_DEFENDER_ON_LINE = 20.0


# Order MUST match what the model expects.
FEATURE_COLS: tuple[str, ...] = (
    "pass_distance",
    "pass_angle_forward",
    "start_x",
    "target_in_final_third",
    "min_dist_def_to_receiver",
    "min_perp_dist_to_line",
    "pass_lane_density_score",
    "sender_pressure_count_25",
    "min_dist_def_to_sender",
    "defender_density_3m_receiver",
    "teammate_density_5m_receiver",
    "pass_height_low",
    "pass_height_high",
)


# Extra columns produced by `compute_features` that are NOT used by the
# model but are kept on the corpus for diagnostics and segmentation
# (e.g. `metrics_by_segment` may slice on `pass_height_ground`).
EXTRA_DIAGNOSTIC_COLS: tuple[str, ...] = (
    "defenders_in_corridor_5m",
    "defenders_in_corridor_2m",
    "receiver_pressure_count_25",
    "pass_height_ground",
)


# =============================================================================
# Helpers
# =============================================================================
def _to_xy_array(points) -> np.ndarray:
    """Turn any iterable of (x, y) into a clean (N, 2) float array.

    Handles None / NaN scalar / empty list / numpy object arrays from parquet.
    """
    if points is None:
        return np.empty((0, 2))
    if isinstance(points, float) and np.isnan(points):
        return np.empty((0, 2))
    if hasattr(points, "__len__") and len(points) == 0:
        return np.empty((0, 2))
    return np.asarray(
        [[float(p[0]), float(p[1])] for p in points], dtype=float
    ).reshape(-1, 2)


def _min_perp_dist_to_line(sx: float, sy: float, tx: float, ty: float,
                            opp_xy: np.ndarray) -> float:
    """Min perpendicular distance from any in-segment opponent to the pass line.

    Continuous version of the discrete corridor counts. Only opponents whose
    foot projects strictly between sender and target contribute (an opponent
    behind the sender or past the target does not block the line). If no
    opponent projects onto the segment, returns `_NO_DEFENDER_ON_LINE` to
    avoid NaN — semantically "the line is wide open".
    """
    if opp_xy.shape[0] == 0:
        return _NO_DEFENDER_ON_LINE
    vx, vy = tx - sx, ty - sy
    L = (vx * vx + vy * vy) ** 0.5
    if L < 1e-9:
        return _NO_DEFENDER_ON_LINE
    ux = opp_xy[:, 0] - sx
    uy = opp_xy[:, 1] - sy
    proj = (ux * vx + uy * vy) / L
    perp = np.abs(ux * vy - uy * vx) / L
    in_segment = (proj > 0) & (proj < L)
    if not in_segment.any():
        return _NO_DEFENDER_ON_LINE
    return float(perp[in_segment].min())


def _pass_lane_density_score(sx: float, sy: float, tx: float, ty: float,
                              opp_xy: np.ndarray) -> float:
    """Inverse-distance-weighted "gauntlet" score along the pass line.

    For every in-segment opponent, contributes `1 / (perp_dist + 0.5)`. The
    +0.5 keeps the score finite when an opponent is exactly on the line.
    Unlike the integer corridor counts this is fully continuous, so a
    defender 1 m off the line contributes much more than one 8 m off — the
    gradient the model can learn is far smoother than a hard threshold.
    """
    if opp_xy.shape[0] == 0:
        return 0.0
    vx, vy = tx - sx, ty - sy
    L = (vx * vx + vy * vy) ** 0.5
    if L < 1e-9:
        return 0.0
    ux = opp_xy[:, 0] - sx
    uy = opp_xy[:, 1] - sy
    proj = (ux * vx + uy * vy) / L
    perp = np.abs(ux * vy - uy * vx) / L
    in_segment = (proj > 0) & (proj < L)
    if not in_segment.any():
        return 0.0
    return float((1.0 / (perp[in_segment] + 0.5)).sum())


def _angle_forward_deg(sx: float, sy: float, tx: float, ty: float) -> float:
    """Angle (deg, 0..180) between the pass vector and the +x direction.

    StatsBomb pitch is oriented attack-to-the-right after the H1 normalisation,
    so 0 = toward opponent goal, 180 = backwards. Returns NaN for zero length.
    """
    vx, vy = tx - sx, ty - sy
    L = (vx * vx + vy * vy) ** 0.5
    if L < 1e-9:
        return np.nan
    cos_t = max(-1.0, min(1.0, vx / L))
    return float(np.degrees(np.arccos(cos_t)))


def _one_hot_height(height) -> tuple[int, int, int]:
    """Map StatsBomb pass.height to (ground, low, high) indicators.

    NaN maps to ground (the modal category) so we never produce an all-zero
    one-hot vector.
    """
    if height is None or (isinstance(height, float) and pd.isna(height)):
        return (1, 0, 0)
    h = str(height)
    return (
        int(h == "Ground Pass"),
        int(h == "Low Pass"),
        int(h == "High Pass"),
    )


# =============================================================================
# Single-row feature builder
# =============================================================================
def compute_features(
    sender_xy: Sequence[float],
    target_xy: Sequence[float],
    teammates,
    opponents,
    pass_height="Ground Pass",
) -> dict:
    """Build the 13-feature row for a single (sender -> target) candidate.

    Parameters
    ----------
    sender_xy, target_xy
        Pitch coordinates in meters (x in [0, 105], y in [0, 68]).
    teammates, opponents
        Iterables of (x, y) in meters from the StatsBomb 360 frame.
        The sender (actor) must be excluded from `teammates`.
    pass_height
        StatsBomb pass.height value at training time. For hypothetical
        targets at inference time, default to ``Ground Pass``.

    Returns
    -------
    dict with one entry per name in `FEATURE_COLS`. Geometry-degenerate
    inputs (e.g. zero-length pass) yield NaN for the angle field.
    """
    sx, sy = float(sender_xy[0]), float(sender_xy[1])
    tx, ty = float(target_xy[0]), float(target_xy[1])

    opp = _to_xy_array(opponents)
    tm  = _to_xy_array(teammates)

    pass_distance         = float(np.hypot(tx - sx, ty - sy))
    pass_angle_forward    = _angle_forward_deg(sx, sy, tx, ty)
    start_x               = sx
    target_in_final_third = int(tx >= cfg.PITCH_LENGTH_M * 2.0 / 3.0)

    corr5 = count_bypassed(sx, sy, tx, ty, opp.tolist(), corridor_m=5.0)
    corr2 = count_bypassed(sx, sy, tx, ty, opp.tolist(), corridor_m=2.0)
    min_perp     = _min_perp_dist_to_line(sx, sy, tx, ty, opp)
    lane_density = _pass_lane_density_score(sx, sy, tx, ty, opp)

    if opp.shape[0] > 0:
        d_def_recv = float(np.linalg.norm(opp - np.array([tx, ty]), axis=1).min())
        d_def_send = float(np.linalg.norm(opp - np.array([sx, sy]), axis=1).min())
    else:
        d_def_recv = float(cfg.PITCH_LENGTH_M)
        d_def_send = float(cfg.PITCH_LENGTH_M)

    sender_press = count_opponents_within(np.array([sx, sy]), opp,
                                          radius=cfg.PRESSURE_RADIUS)
    recv_press   = count_opponents_within(np.array([tx, ty]), opp,
                                          radius=cfg.PRESSURE_RADIUS)
    def_dens     = count_opponents_within(np.array([tx, ty]), opp, radius=3.0)

    if tm.shape[0] > 0:
        d_tm = np.linalg.norm(tm - np.array([tx, ty]), axis=1)
        # exclude the receiver himself (the candidate target)
        tm_dens = int(((d_tm <= 5.0) & (d_tm > 1e-3)).sum())
    else:
        tm_dens = 0

    h_ground, h_low, h_high = _one_hot_height(pass_height)

    return {
        "pass_distance":                pass_distance,
        "pass_angle_forward":           pass_angle_forward,
        "start_x":                      start_x,
        "target_in_final_third":        target_in_final_third,
        "defenders_in_corridor_5m":     corr5,
        "defenders_in_corridor_2m":     corr2,
        "min_dist_def_to_receiver":     d_def_recv,
        "min_perp_dist_to_line":        min_perp,
        "pass_lane_density_score":      lane_density,
        "sender_pressure_count_25":     sender_press,
        "min_dist_def_to_sender":       d_def_send,
        "receiver_pressure_count_25":   recv_press,
        "defender_density_3m_receiver": def_dens,
        "teammate_density_5m_receiver": tm_dens,
        "pass_height_ground":           h_ground,
        "pass_height_low":              h_low,
        "pass_height_high":             h_high,
    }


# =============================================================================
# Build the training table — features for the chosen pass of every event
# =============================================================================
def features_for_chosen_pass(df_with_frames: pd.DataFrame,
                              progress_every: int = 5000) -> pd.DataFrame:
    """Compute the 13-feature row for every event in the corpus.

    The chosen-receiver position is read from the in-frame teammate at
    `chosen_teammate_idx` (set by `corpus.build_corpus`), so training and
    inference use the same routine on the same kind of input.

    Returns a DataFrame with `event_id`, `match_id`, `pass_complete`, and
    one column per name in `FEATURE_COLS`. Events with empty / unusable
    frames are silently skipped.
    """
    rows = []
    n = len(df_with_frames)
    for i, r in enumerate(df_with_frames.itertuples(index=False), 1):
        idx = int(getattr(r, "chosen_teammate_idx", -1))
        tm  = _to_xy_array(getattr(r, "teammates", None))
        if idx < 0 or tm.shape[0] == 0 or idx >= tm.shape[0]:
            continue
        target = tm[idx]
        feats = compute_features(
            sender_xy=(r.start_x_m, r.start_y_m),
            target_xy=target,
            teammates=tm,
            opponents=getattr(r, "opponents", None),
            pass_height=getattr(r, "pass_height", "Ground Pass"),
        )
        feats["event_id"]      = r.event_id
        feats["match_id"]      = r.match_id
        feats["pass_complete"] = int(getattr(r, "pass_complete", 0))
        rows.append(feats)
        if i % progress_every == 0:
            print(f"  features built: {i:,} / {n:,}")
    print(f"  features built: {n:,} / {n:,}")

    out = pd.DataFrame(rows)
    cols = ["event_id", "match_id", "pass_complete",
            *FEATURE_COLS, *EXTRA_DIAGNOSTIC_COLS]
    return out[cols]


# =============================================================================
# Alternatives table — features for every visible teammate as a candidate
# =============================================================================
def features_for_all_candidates(df_with_frames: pd.DataFrame,
                                 progress_every: int = 5000) -> pd.DataFrame:
    """Expand each event into one row per visible teammate candidate.

    For every event, iterates over all teammates in the 360 frame and treats
    each as a hypothetical target. The same `compute_features` routine is
    used as for the chosen pass, so the resulting features are directly
    comparable: ranking the rows of one event by predicted xPass is exactly
    the "ranking of decision options" the downstream xEPV / DQ index needs.

    Important convention — pass_height
    ----------------------------------
    Each candidate is scored under the height that the geometry implies:
    Ground Pass below `cfg.ALT_HEIGHT_DISTANCE_THRESHOLD_M` (default 30 m,
    where the corpus flips from majority-Ground to majority-High), High
    Pass above. The previous convention of forcing Ground everywhere
    inflated xPass on long forward candidates that no one would attempt on
    the ground (corpus: only 9% Ground at >=40 m). The chosen pass is also
    scored under the same rule so chosen-vs-alternatives stays apples-to-
    apples; the recorded actual height lives in `xpass_chosen_actual` on
    the corpus for reference.

    Returns
    -------
    DataFrame (long form) with one row per (event, candidate). Columns:
        event_id, match_id, pass_complete  (event-level)
        candidate_idx                      (0..N-1)
        is_chosen                          (bool)
        target_x_m, target_y_m             (candidate position in metres)
        *FEATURE_COLS                      (the 13 model features)
    """
    rows = []
    n = len(df_with_frames)
    for i, r in enumerate(df_with_frames.itertuples(index=False), 1):
        tm = _to_xy_array(getattr(r, "teammates", None))
        if tm.shape[0] == 0:
            continue
        opp = getattr(r, "opponents", None)
        chosen_idx = int(getattr(r, "chosen_teammate_idx", -1))
        for cand_idx, target in enumerate(tm):
            dist = float(np.hypot(target[0] - r.start_x_m,
                                  target[1] - r.start_y_m))
            height = ("High Pass"
                      if dist >= cfg.ALT_HEIGHT_DISTANCE_THRESHOLD_M
                      else "Ground Pass")
            feats = compute_features(
                sender_xy=(r.start_x_m, r.start_y_m),
                target_xy=target,
                teammates=tm,
                opponents=opp,
                pass_height=height,
            )
            feats["event_id"]      = r.event_id
            feats["match_id"]      = r.match_id
            feats["pass_complete"] = int(getattr(r, "pass_complete", 0))
            feats["candidate_idx"] = cand_idx
            feats["is_chosen"]     = bool(cand_idx == chosen_idx)
            feats["target_x_m"]    = float(target[0])
            feats["target_y_m"]    = float(target[1])
            rows.append(feats)
        if i % progress_every == 0:
            print(f"  events expanded: {i:,} / {n:,}")
    print(f"  events expanded: {n:,} / {n:,}  -> {len(rows):,} candidates")

    out = pd.DataFrame(rows)
    meta_cols = ["event_id", "match_id", "pass_complete",
                 "candidate_idx", "is_chosen", "target_x_m", "target_y_m"]
    return out[[*meta_cols, *FEATURE_COLS]]
