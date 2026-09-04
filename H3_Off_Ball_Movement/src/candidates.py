"""
candidates.py — H3 Off-Ball Movement
Receiver resolution (v2, bracket interpolation) + xPass feature building.

H2 modules are loaded via config.load_h2_package() which registers
H2_Decision_Quality/src/ under the private name `_dq_src`, resolving
all relative imports without colliding with H3_Off_Ball_Movement/src/.
"""

from __future__ import annotations

import logging
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment

# ── Ensure H3_Off_Ball_Movement/ is on sys.path ───────────────────────────────
_H3_DIR = Path(__file__).resolve().parents[1]
if str(_H3_DIR) not in sys.path:
    sys.path.insert(0, str(_H3_DIR))

from src.config import (
    H1_SRC,
    COMPETITION_ID, SEASON_ID,
    WINDOW_SECONDS, CONF_THR_M,
    CANDIDATES_PARQUET, CACHE_DIR,
    H2_XPASS_MODEL,
    load_h2_package,
    X_SCALE, Y_SCALE
)

# ── H1 import — EPV grid (flat layout, already on sys.path via config) ────────
from epv_pipeline import EPVPipeline  # noqa: E402

# ── H2 imports via collision-safe loader ──────────────────────────────────────
# Mirrors H2 Section 8.1:
#   alts = h2_features.features_for_all_candidates(dq_corpus_fr)
#   alts['xpass'] = xpass_model.predict_proba(alts)
_h2          = load_h2_package()
h2_features  = _h2.features
h2_xpass     = _h2.xpass

# Alias that permits joblib to deserialize the xPass model saved in H2
sys.modules['src.xpass'] = h2_xpass
sys.modules['src.features'] = h2_features
# -----------------------------

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Receiver resolver v2 — bracket interpolation
# ─────────────────────────────────────────────────────────────────────────────

def _event_seconds(row) -> float:
    """Absolute match time in seconds (minute is monotonic across periods)."""
    return float(row["minute"]) * 60.0 + float(row["second"])


def _estimate_team_positions(
    events: pd.DataFrame,
    team: str,
    sender: str,
    t_pass: float,
    pass_idx: int,
    W: float = WINDOW_SECONDS,
    mode: str = "bracket",
) -> dict[str, np.ndarray]:
    """Estimate each teammate's position at the instant of the pass.

    Parameters
    ----------
    events   : full match event DataFrame from statsbombpy.
    team     : attacking team name.
    sender   : name of the player who has the ball (excluded from candidates).
    t_pass   : absolute time of the pass in seconds.
    pass_idx : integer index of the pass row in `events`.
    W        : max staleness window in seconds; players outside ±W are excluded.
    mode     : 'bracket' (v2, interpolate prev<->next) or
               'backward' (v1 baseline, last-known-location only).

    Returns
    -------
    dict mapping player name -> np.array([x, y]) for reliable positions only.
    """
    team_ev = events[(events["team"] == team) & (events["location"].notna())]
    out: dict[str, np.ndarray] = {}

    for player in team_ev["player"].dropna().unique():
        if player == sender:
            continue

        ev_p = team_ev[team_ev["player"] == player]
        prev = ev_p.iloc[[i for i in range(len(ev_p)) if ev_p.index[i] < pass_idx]][-1:] \
               if (ev_p.index < pass_idx).any() else ev_p.iloc[0:0]
        nxt  = ev_p.iloc[[i for i in range(len(ev_p)) if ev_p.index[i] > pass_idx]][:1] \
               if (ev_p.index > pass_idx).any() else ev_p.iloc[0:0]

        has_prev = len(prev) > 0
        has_next = (len(nxt) > 0) and (mode == "bracket")

        loc = None
        if has_prev and has_next:
            tp = _event_seconds(prev.iloc[0])
            tn = _event_seconds(nxt.iloc[0])
            lp = np.array(prev.iloc[0]["location"], dtype=float)
            ln = np.array(nxt.iloc[0]["location"], dtype=float)
            if min(t_pass - tp, tn - t_pass) <= W and tn > tp:
                frac = np.clip((t_pass - tp) / (tn - tp), 0.0, 1.0)
                loc  = lp + frac * (ln - lp)
        elif has_prev:
            tp = _event_seconds(prev.iloc[0])
            if (t_pass - tp) <= W:
                loc = np.array(prev.iloc[0]["location"], dtype=float)
        elif has_next:
            tn = _event_seconds(nxt.iloc[0])
            if (tn - t_pass) <= W:
                loc = np.array(nxt.iloc[0]["location"], dtype=float)

        if loc is not None:
            out[player] = loc

    return out


def resolve_receiver(
    events: pd.DataFrame,
    frames: pd.DataFrame,
    event_col: str,
    pass_uuid: str,
    W: float = WINDOW_SECONDS,
    conf_thr: float = CONF_THR_M,
    mode: str = "bracket",
) -> tuple[pd.DataFrame | None, str | None]:
    """Assign names to anonymous dots in a freeze frame.

    Returns
    -------
    (DataFrame with columns predicted_player / match_residual_m / confident /
     dist_to_pass_end,  name of the predicted spatial receiver)
    or (None, None) if the frame is unusable.
    """
    prow = events[events["id"] == pass_uuid]
    if prow.shape[0] == 0:
        return None, None
    prow = prow.iloc[0]
    end_loc = prow.get("pass_end_location")
    if end_loc is None:
        return None, None

    team, sender = prow["team"], prow["player"]
    pass_idx = events.index[events["id"] == pass_uuid][0]
    t_pass   = _event_seconds(prow)

    fr   = frames[frames[event_col] == pass_uuid]
    dots = fr[
        (fr["teammate"] == True) &
        (fr["actor"]    == False) &
        (fr["keeper"]   == False)
    ].copy()
    if dots.shape[0] == 0:
        return None, None

    named = _estimate_team_positions(events, team, sender, t_pass, pass_idx,
                                     W=W, mode=mode)
    if not named:
        return None, None

    names = list(named.keys())
    known = np.array([named[n] for n in names])
    anon  = np.array(dots["location"].tolist(), dtype=float)

    cost             = np.linalg.norm(known[:, None, :] - anon[None, :, :], axis=2)
    row_ind, col_ind = linear_sum_assignment(cost)

    dots = dots.reset_index(drop=True)
    dots["predicted_player"] = "Unknown"
    dots["match_residual_m"] = np.nan
    for r, c in zip(row_ind, col_ind):
        dots.loc[c, "predicted_player"] = names[r]
        dots.loc[c, "match_residual_m"] = cost[r, c]
    dots["confident"] = dots["match_residual_m"] <= conf_thr

    end_x, end_y = float(end_loc[0]), float(end_loc[1])
    dots["dist_to_pass_end"] = dots["location"].apply(
        lambda l: float(np.hypot(l[0] - end_x, l[1] - end_y))
    )
    dots = dots.sort_values("dist_to_pass_end").reset_index(drop=True)
    return dots, dots.iloc[0]["predicted_player"]


# ─────────────────────────────────────────────────────────────────────────────
# H2 xPass scoring — uses CalibratedXPass from H2_Decision_Quality.src.xpass.
# ─────────────────────────────────────────────────────────────────────────────

def _load_h2_xpass_model():
    """Load H2's calibrated GBM (persisted by H2 Section 6)."""
    import joblib
    if not H2_XPASS_MODEL.exists():
        raise FileNotFoundError(
            f"H2 model not found: {H2_XPASS_MODEL}\n"
            "Run H2 notebook Section 6 (fit_calibrated, save=True) first."
        )
    return joblib.load(H2_XPASS_MODEL)


def _score_candidates(frames_for_match: pd.DataFrame, xpass_model) -> pd.DataFrame:
    """Compute H2's calibrated xPass for every visible teammate, on the fly.

    Why not merge H2's alternatives.parquet?  StatsBomb periodically
    re-processes the open-data and regenerates every event UUID. H1/H2 were
    built from an earlier pull whose `event_id`s are frozen inside
    alternatives.parquet, while H3 reads the *current* `sb.events/frames`
    pull — so the two event_id spaces no longer intersect and an event_id
    merge yields zero rows. The fix is to stop joining on identity and
    recompute xPass from geometry: identical model, identical 13 features
    (H2 features.py), so the value attached to each candidate is exactly
    what H2 would attach. Robust to any future re-pull.

    Parameters
    ----------
    frames_for_match : one row per event with
        event_id, match_id, start_x_m, start_y_m (sender, metres),
        teammates / opponents (lists of (x, y) in metres).

    Returns
    -------
    DataFrame: event_id, target_x_m, target_y_m, xpass — one row per
    (event, visible teammate). Joined back to the confident dots on
    (event_id, rounded target coords), all within the same live pull so
    event_id matches by construction.
    """
    if frames_for_match.shape[0] == 0:
        return pd.DataFrame(columns=["event_id", "target_x_m", "target_y_m", "xpass"])

    # H2 Section 8.1 — same routine used to score alternatives in H2.
    alts = h2_features.features_for_all_candidates(frames_for_match)
    if alts.shape[0] == 0:
        return pd.DataFrame(columns=["event_id", "target_x_m", "target_y_m", "xpass"])

    feat_cols = list(h2_features.FEATURE_COLS)
    proba = xpass_model.predict_proba(alts[feat_cols])
    # CalibratedXPass.predict_proba may return a 2-column array (sklearn API);
    # take the positive class if so.
    alts["xpass"] = proba[:, 1] if getattr(proba, "ndim", 1) == 2 else proba

    return alts[["event_id", "target_x_m", "target_y_m", "xpass"]].copy()


# ─────────────────────────────────────────────────────────────────────────────
# Frame loading (loader pattern from H1's line_breaker.py)
# ─────────────────────────────────────────────────────────────────────────────

def _load_frames(match_id: int) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    """Return (events, frames, event_col) for one match.

    `frames` is always a plain pd.DataFrame — never a raw list/dict.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from statsbombpy import sb

    events     = sb.events(match_id=match_id)
    frames_raw = sb.frames(match_id=match_id, fmt="dict")

    if not frames_raw:
        return events, pd.DataFrame(), "event_uuid"

    frames_list = frames_raw if isinstance(frames_raw, list) else list(frames_raw)
    frames: pd.DataFrame = pd.DataFrame(frames_list)
    frames = frames.explode("freeze_frame", ignore_index=True)
    frames = pd.concat(
        [frames.drop(columns=["freeze_frame"]),
         pd.json_normalize(frames["freeze_frame"])],
        axis=1,
    )
    ec = "event_uuid" if "event_uuid" in frames.columns else "id"
    return events, frames, ec


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    """Run the full candidates pipeline over all 51 Euro 2024 matches.

    Writes data/off_ball_candidates.parquet.
    Schema: event_id, match_id, player, team, minute, second,
    sender, sender_x_m, sender_y_m, target_x_m, target_y_m,
    match_residual_m, confident, dist_to_pass_end, xpass.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from statsbombpy import sb

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s  %(levelname)s  %(message)s")

    CANDIDATES_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    xpass_model = _load_h2_xpass_model()

    # xPass is recomputed on the fly from the live freeze frames with H2's
    # saved CalibratedXPass model (see _score_candidates for why we no longer
    # merge alternatives.parquet — StatsBomb regenerated every event UUID, so
    # H2's frozen event_ids no longer match the live pull). Same model, same
    # 13 features: the value attached is exactly what H2 would attach.
    logger.info("xPass scored on the fly with H2's CalibratedXPass "
                "(event_id-independent; robust to StatsBomb re-pulls).")

    matches = sb.matches(competition_id=COMPETITION_ID, season_id=SEASON_ID)
    logger.info("Euro 2024 — %d matches to process", len(matches))

    all_rows: list[dict] = []
    for i, (_, m) in enumerate(matches.iterrows(), 1):
        mid  = m["match_id"]
        name = f"{m['home_team']} vs {m['away_team']}"
        logger.info("[%d/%d] %s  (id=%s)", i, len(matches), name, mid)
        try:
            events, frames, event_col = _load_frames(mid)
            if frames.shape[0] == 0:
                logger.warning("  No 360 frames — skipping")
                continue

            # Open play only — IDENTICAL filter to H1 (epv_pipeline.py): a pass
            # is open play iff `pass_type` is NaN. StatsBomb tags the restart
            # pass of every set piece (Corner / Free Kick / Throw-in / Kick Off
            # / Goal Kick) with a non-null pass_type, while the flowing play
            # that follows keeps pass_type = NaN. This is far more precise than
            # filtering on `play_pattern`, which stays "From Throw In/Free Kick"
            # for several open passes after the restart and would discard real
            # in-play actions. Keeping H3 on the same open-play subset as H1/H2
            # makes the three hypotheses comparable on one event universe.
            #
            # Headers excluded (H2 corpus.py EXCLUDE_BODY_PARTS): the off-ball
            # value is scored with H2's xPass, a foot-pass completion model. A
            # teammate reached by a header is outside that model's domain, so
            # its xPass/xEPV would be meaningless. ~1% of open-play passes.
            #
            # NOTE — H2's pass-into-space filter (PASS_INTO_SPACE_M) is
            # deliberately NOT applied here. In H2 "into space" means "no
            # identifiable receiver to grade the chosen pass against". H3 does
            # not grade the chosen pass: it grades EVERY confidently-localised
            # teammate dot in the frame as an off-ball candidate. A pass that
            # happens to go long still has well-positioned teammates worth
            # scoring, and the resolver's conf_thr (8 m) is already the per-
            # candidate quality gate. Dropping the whole frame on the chosen
            # pass's end location would discard legitimate off-ball candidates.
            passes = events[
                (events["type"] == "Pass") &
                (events["pass_type"].isna()) &
                (events["pass_body_part"].fillna("") != "Head") &
                (events["pass_end_location"].notna()) &
                (events["id"].isin(frames[event_col].unique())) &
                (events["position"] != "Goalkeeper")
            ]

            match_rows: list[dict] = []
            frame_rows: list[dict] = []   # one per event, fed to _score_candidates
            seen_events: set[str] = set()
            for _, p in passes.iterrows():
                dots, _ = resolve_receiver(events, frames, event_col, p["id"])
                if dots is None:
                    continue
                conf_dots = dots[dots["confident"]].copy()
                if conf_dots.shape[0] == 0:
                    continue

                sx = float(p["location"][0]) * X_SCALE
                sy = float(p["location"][1]) * Y_SCALE
                for _, dot in conf_dots.iterrows():
                    tx = float(dot["location"][0]) * X_SCALE
                    ty = float(dot["location"][1]) * Y_SCALE
                    match_rows.append({
                        "event_id"         : p["id"],
                        "match_id"         : mid,
                        "player"           : dot["predicted_player"],
                        "team"             : p["team"],
                        "minute"           : p["minute"],
                        "second"           : p["second"],
                        "sender"           : p["player"],
                        "sender_x_m"       : sx,
                        "sender_y_m"       : sy,
                        "target_x_m"       : tx,
                        "target_y_m"       : ty,
                        "match_residual_m" : dot["match_residual_m"],
                        "confident"        : dot["confident"],
                        "dist_to_pass_end" : dot["dist_to_pass_end"],
                        "received"         : False,
                    })

                # Build the per-event frame row once: every visible teammate /
                # opponent in metres, the sender at its start position. This is
                # what H2's features_for_all_candidates consumes (Section 8.1).
                if p["id"] not in seen_events:
                    seen_events.add(p["id"])
                    fr = frames[frames[event_col] == p["id"]]
                    tm = fr[(fr["teammate"] == True) & (fr["actor"] == False) &
                            (fr["keeper"] == False)]
                    opp = fr[(fr["teammate"] == False) & (fr["keeper"] == False)]
                    tm_xy = [(float(l[0]) * X_SCALE, float(l[1]) * Y_SCALE)
                             for l in tm["location"] if isinstance(l, list)]
                    opp_xy = [(float(l[0]) * X_SCALE, float(l[1]) * Y_SCALE)
                              for l in opp["location"] if isinstance(l, list)]
                    if tm_xy:
                        frame_rows.append({
                            "event_id"  : p["id"],
                            "match_id"  : mid,
                            "start_x_m" : sx,
                            "start_y_m" : sy,
                            "teammates" : tm_xy,
                            "opponents" : opp_xy,
                            # H2 feature builder reads these; not used by H3 xPass.
                            "chosen_teammate_idx": -1,
                            "pass_complete"      : 0,
                        })

            if not match_rows:
                continue

            df_match = pd.DataFrame(match_rows)
            df_match["_tx_r"] = df_match["target_x_m"].round(1)
            df_match["_ty_r"] = df_match["target_y_m"].round(1)

            # Score every visible teammate with H2's model, then attach the
            # candidate's xPass to its confident dot on (event_id, rounded
            # target coords). Both sides come from the SAME live pull, so
            # event_id matches by construction — no UUID drift possible.
            scored = _score_candidates(pd.DataFrame(frame_rows), xpass_model)
            scored["_tx_r"] = scored["target_x_m"].round(1)
            scored["_ty_r"] = scored["target_y_m"].round(1)
            df_match = df_match.merge(
                scored[["event_id", "_tx_r", "_ty_r", "xpass"]],
                on=["event_id", "_tx_r", "_ty_r"], how="left",
            )

            df_match = df_match.drop(columns=["_tx_r", "_ty_r"], errors="ignore")
            df_match = df_match[df_match["xpass"].notna()].copy()
            all_rows.extend(df_match.to_dict("records"))
            logger.info("  %d confident candidate rows added", len(df_match))

        except Exception as exc:
            logger.error("  Error on match %s: %s", mid, exc, exc_info=True)

    if not all_rows:
        logger.error("No candidate rows produced.")
        return

    out = pd.DataFrame(all_rows)
    out.to_parquet(CANDIDATES_PARQUET, index=False, engine="pyarrow", version="2.6")
    logger.info(
        "Saved %s  (%d rows, %d events, %d players)",
        CANDIDATES_PARQUET, len(out),
        out["event_id"].nunique(), out["player"].nunique(),
    )
