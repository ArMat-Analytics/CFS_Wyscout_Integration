"""xepv.py — H3 Off-Ball Movement

For each confident teammate candidate emitted by the receiver resolver,
attach the H2 xEPV value of the hypothetical pass that would have served
them. H3 reuses H2's `compute_xepv` directly:

    xEPV = xpass · EPV(target) - (1 - xpass) · scale · EPV(mirror)

Same calibrated value H2 attaches to every pass alternative; here we read
it from the receiver perspective ("value if this target had been played").
Aggregating its non-realised share gives URS in `urs.py`; the full sum
gives the Off-Ball Potential. No separate Pitch-Control surface is needed
because the second term already encodes the turnover penalty.

Inputs  : data/off_ball_candidates.parquet (must have xpass, target_x_m,
          target_y_m, confident; produced by candidates.main()).
Outputs : data/off_ball_xepv.parquet  with epv_target, epv_mirror, xepv,
          received columns added.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pandas as pd

_H3_DIR = Path(__file__).resolve().parents[1]
if str(_H3_DIR) not in sys.path:
    sys.path.insert(0, str(_H3_DIR))

from src.config import (
    CANDIDATES_PARQUET, XEPV_PARQUET,
    COMPETITION_ID, SEASON_ID, RECEIVED_WINDOW_S,
    load_h2_package,
)

logger = logging.getLogger(__name__)


def _flag_received(df: pd.DataFrame,
                   ev_cache: dict[int, pd.DataFrame]) -> pd.Series:
    """Mark each candidate as received=True if the next ball-touch within
    RECEIVED_WINDOW_S seconds belongs to them. Mirrors urs._flag_received.
    """
    received = pd.Series(False, index=df.index)
    for match_id, grp in df.groupby("match_id"):
        if match_id not in ev_cache:
            continue
        ev = ev_cache[match_id].copy()
        ev["t_abs"] = ev["minute"].astype(float) * 60.0 + ev["second"].astype(float)
        for idx, row in grp.iterrows():
            t0   = float(row["minute"]) * 60.0 + float(row["second"])
            cand = row["player"]
            future = ev[(ev["t_abs"] > t0) &
                        (ev["t_abs"] <= t0 + RECEIVED_WINDOW_S)]
            if future.shape[0] > 0 and future.iloc[0].get("player") == cand:
                received.at[idx] = True
    return received


def main() -> None:
    """Attach H2's xEPV (and the `received` flag) to every confident candidate.

    Reads  : data/off_ball_candidates.parquet
    Writes : data/off_ball_xepv.parquet  with the added columns:
             epv_target, epv_mirror, xepv, received.
    """
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s  %(levelname)s  %(message)s")

    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from statsbombpy import sb

    if not CANDIDATES_PARQUET.exists():
        raise FileNotFoundError(
            f"{CANDIDATES_PARQUET} not found. Run candidates.main() first."
        )

    cands = pd.read_parquet(CANDIDATES_PARQUET)
    logger.info("Loaded %d candidate rows", len(cands))

    for col in ("xpass", "target_x_m", "target_y_m", "confident"):
        if col not in cands.columns:
            raise ValueError(
                f"Column '{col}' missing from {CANDIDATES_PARQUET}. "
                "Re-run candidates.main()."
            )

    # Keep only confident candidates: resolver §8.5 reports 91.8% acc-on-confident
    # on the 51-match harness, vs 18.6% on non-confident — including the rest
    # would import noise correlated with the very behaviour URS measures.
    before = len(cands)
    cands  = cands[cands["confident"] & cands["xpass"].notna()].copy()
    logger.info("Kept %d confident candidates (dropped %d non-confident / NaN xpass)",
                len(cands), before - len(cands))

    # H2's xEPV layer attaches epv_target, epv_mirror, xepv.
    h2   = load_h2_package()
    grid = h2.xepv.load_epv_grid()
    out  = h2.xepv.compute_xepv(cands, grid)

    # received flag: was this candidate the actual next ball-touch?
    logger.info("Computing 'received' flag from StatsBomb events...")
    ev_cache: dict[int, pd.DataFrame] = {}
    for mid in out["match_id"].unique():
        try:
            ev_cache[int(mid)] = sb.events(match_id=int(mid))
        except Exception:
            pass
    out["received"] = _flag_received(out, ev_cache)
    logger.info("received=True: %d / %d  (%.1f%%)",
                int(out["received"].sum()), len(out),
                100 * out["received"].mean())

    XEPV_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    # Pin parquet format version so any pyarrow >= 8 can read the file
    # (avoids "Repetition level histogram size mismatch" across kernels).
    out.to_parquet(XEPV_PARQUET, index=False, engine="pyarrow", version="2.6")
    logger.info(
        "Saved %s  (%d rows)  xEPV mean=%.4f  [min=%.4f, max=%.4f]",
        XEPV_PARQUET, len(out),
        float(out["xepv"].mean()), float(out["xepv"].min()), float(out["xepv"].max()),
    )
