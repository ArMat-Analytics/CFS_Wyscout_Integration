"""validate_receiver_resolution.py — H3 Off-Ball Movement
Full-tournament gate (spec §8.4–§8.5): run the receiver resolver against
StatsBomb's ground-truth `pass_recipient` across every Euro 2024 match
and report global accuracy, confident share, and accuracy-on-confident.

The accuracy-on-confident is the headline number for the thesis: if it
clears 85% we keep Tier 1 (per-player URS ranking); otherwise we fall
back to Tier 2 (zone/role aggregates).
"""

from __future__ import annotations

import logging
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

_H3_DIR = Path(__file__).resolve().parents[1]
if str(_H3_DIR) not in sys.path:
    sys.path.insert(0, str(_H3_DIR))

from src.config import (COMPETITION_ID, SEASON_ID, DATA_DIR,
                        WINDOW_SECONDS, CONF_THR_M)
from src.candidates import resolve_receiver

logger = logging.getLogger(__name__)


def _load_frames(match_id: int) -> tuple[pd.DataFrame, str | None]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from statsbombpy import sb

    raw = sb.frames(match_id=match_id, fmt="dict")
    if not raw:
        return pd.DataFrame(), None
    fr = pd.DataFrame(raw).explode("freeze_frame", ignore_index=True)
    fr = pd.concat(
        [fr.drop(columns=["freeze_frame"]),
         pd.json_normalize(fr["freeze_frame"])],
        axis=1,
    )
    event_col = "event_uuid" if "event_uuid" in fr.columns else "id"
    return fr, event_col


def main(per_match: int = 40,
         W: float = WINDOW_SECONDS,
         conf_thr: float = CONF_THR_M,
         modes: tuple[str, ...] = ("backward", "bracket"),
         seed: int = 42) -> None:
    """Evaluate v1 (backward / LKL) and v2 (bracket interpolation) on every match.

    Parameters
    ----------
    per_match : int   — sampled complete passes per match (uniform shuffle).
    W         : float — staleness window (seconds).
    conf_thr  : float — Hungarian residual threshold for 'confident' assignments.
    modes     : tuple — resolver variants to evaluate.
    """
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s  %(levelname)s  %(message)s")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from statsbombpy import sb

    matches = sb.matches(competition_id=COMPETITION_ID, season_id=SEASON_ID)
    logger.info("Matches in competition: %d", len(matches))

    rng = np.random.default_rng(seed)
    per_match_rows: list[dict] = []
    all_rows: list[dict] = []

    for i, m in matches.iterrows():
        mid = int(m["match_id"])
        try:
            ev = sb.events(match_id=mid)
        except Exception as e:
            logger.warning("skip events %d: %s", mid, e)
            continue
        fr, ev_col = _load_frames(mid)
        if fr.empty:
            continue

        # Validate on the SAME event universe the production pipeline uses
        # (candidates.main): open play only (pass_type NaN, H1's filter),
        # non-header (H2's EXCLUDE_BODY_PARTS), non-GK senders. Measuring
        # accuracy on a different universe than the one the resolver actually
        # runs on would make the headline number describe a sample the metric
        # never sees.
        passes = ev[(ev["type"] == "Pass") & (ev["pass_type"].isna())].copy()
        passes = passes[passes["pass_recipient"].notna() &
                        (passes["pass_body_part"].fillna("") != "Head") &
                        passes["pass_end_location"].notna() &
                        passes["id"].isin(fr[ev_col].unique()) &
                        (passes["position"] != "Goalkeeper")]
        if len(passes) == 0:
            continue

        sample_n = min(per_match, len(passes))
        idx = rng.choice(len(passes), size=sample_n, replace=False)
        sample = passes.iloc[idx]

        counts = {mode: dict(n=0, ok=0, conf_n=0, conf_ok=0) for mode in modes}
        for _, p in sample.iterrows():
            truth = p["pass_recipient"]
            for mode in modes:
                df_r, pred = resolve_receiver(
                    ev, fr, ev_col, p["id"], W=W, conf_thr=conf_thr, mode=mode,
                )
                if df_r is None:
                    continue
                hit  = (pred == truth)
                conf = bool(df_r.iloc[0]["confident"])
                c = counts[mode]
                c["n"] += 1; c["ok"] += hit
                if conf:
                    c["conf_n"] += 1; c["conf_ok"] += hit
                all_rows.append({"match_id": mid, "mode": mode,
                                 "correct": bool(hit), "confident": conf})

        row = {"match": f"{m['home_team'][:14]} vs {m['away_team'][:14]}",
               "match_id": mid,
               "n_sampled": sample_n}
        for mode in modes:
            c = counts[mode]
            row[f"{mode}_n"]            = c["n"]
            row[f"{mode}_acc"]          = c["ok"] / c["n"]              if c["n"]      else np.nan
            row[f"{mode}_conf_share"]   = c["conf_n"] / c["n"]          if c["n"]      else np.nan
            row[f"{mode}_acc_conf"]     = c["conf_ok"] / c["conf_n"]    if c["conf_n"] else np.nan
        per_match_rows.append(row)

        logger.info("  match %2d/%d  %-30s  v2 acc=%.1f%%  conf=%.1f%%  acc|conf=%.1f%%",
                    i + 1, len(matches), row["match"],
                    100 * row.get("bracket_acc", np.nan),
                    100 * row.get("bracket_conf_share", np.nan),
                    100 * row.get("bracket_acc_conf", np.nan))

    per_match_df = pd.DataFrame(per_match_rows)
    all_df       = pd.DataFrame(all_rows)

    # Headline numbers, per mode
    print("\n" + "=" * 72)
    print(f"  RECEIVER RESOLUTION — {len(per_match_df)} matches, sampled "
          f"~{per_match} passes / match, W={W}s, conf_thr={conf_thr}m")
    print("=" * 72)
    for mode in modes:
        s = all_df[all_df["mode"] == mode]
        if s.empty:
            print(f"  {mode:8s}: n/a"); continue
        conf = s[s["confident"]]
        g_acc = s["correct"].mean()
        c_sh  = s["confident"].mean()
        c_acc = conf["correct"].mean() if len(conf) else np.nan
        print(f"  {mode:8s}:  global acc {g_acc:.1%}   conf share {c_sh:.1%}   "
              f"acc-on-confident {c_acc:.1%}")
    print("=" * 72)

    v2_conf = all_df[(all_df["mode"] == "bracket") & all_df["confident"]]
    v2_acc_conf = v2_conf["correct"].mean() if len(v2_conf) else 0.0
    print()
    if v2_acc_conf >= 0.85:
        print(f"  Tier 1 OK — URS per-player ranking is defensible "
              f"(acc-on-confident = {v2_acc_conf:.1%} >= 85%).")
    else:
        print(f"  Tier 2 fallback — acc-on-confident = {v2_acc_conf:.1%} < 85%; "
              f"aggregate URS by zone/role.")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    per_match_df.to_csv(DATA_DIR / "receiver_resolution_per_match.csv", index=False)
    all_df.to_csv(DATA_DIR / "receiver_resolution_all_passes.csv", index=False)
    print(f"\nSaved: {DATA_DIR / 'receiver_resolution_per_match.csv'}")
    print(f"Saved: {DATA_DIR / 'receiver_resolution_all_passes.csv'}")


if __name__ == "__main__":
    main()
