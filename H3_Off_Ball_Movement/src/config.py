"""
config.py — H3 Off-Ball Movement
Global constants, output paths, and H2 package loader for the H3 pipeline.

Path layout assumed on disk:
    Contextual-Football-Scouting/          <- REPO_ROOT
        H1_Space_Control_and_Value/src/    <- H1_SRC  (epv_pipeline, ...)
        H2_Decision_Quality/src/           <- H2_SRC  (features, xpass, ...)
        H3_Off_Ball_Movement/              <- H3_DIR
            src/config.py                 <- this file

H2 import strategy
------------------
H2_Decision_Quality uses a package layout: src/ is a sub-package with relative
imports (e.g. `from . import config`).  Importing via sys.path would collide
with H3_Off_Ball_Movement/src/ because both packages are named `src`.

Solution: load_h2_package() registers H2_Decision_Quality/src/ under the private
name `_dq_src` using importlib, resolving relative imports correctly with zero
sys.path collision.  Usage in any H3 module:

    from src.config import load_h2_package
    _h2 = load_h2_package()
    h2_features = _h2.features
    h2_xpass    = _h2.xpass
"""

from __future__ import annotations
import sys
import types
import importlib.util
from pathlib import Path

# ── Repo layout ────────────────────────────────────────────────────────────────
H3_DIR    = Path(__file__).resolve().parents[1]   # Off_Ball_Movement/
REPO_ROOT = H3_DIR.parent                         # Contextual-Football-Scouting/
H1_SRC    = REPO_ROOT / "H1_Space_Control_and_Value" / "src"
H2_SRC    = REPO_ROOT / "H2_Decision_Quality"        / "src"

# ── H1 package loader (collision-safe like H2) ────────────────────────────────
_H1_PKG_PRIVATE = "_scv_src"

if H1_SRC.exists():
    if _H1_PKG_PRIVATE not in sys.modules:
        # 1. Register a fake parent package
        pkg = types.ModuleType(_H1_PKG_PRIVATE)
        pkg.__path__ = [str(H1_SRC)]
        pkg.__package__ = _H1_PKG_PRIVATE
        sys.modules[_H1_PKG_PRIVATE] = pkg

        # 2. Load epv_pipeline inside the protected package
        full_name = f"{_H1_PKG_PRIVATE}.epv_pipeline"
        file_path = H1_SRC / "epv_pipeline.py"
        if file_path.exists():
            spec = importlib.util.spec_from_file_location(full_name, file_path)
            mod = importlib.util.module_from_spec(spec)
            mod.__package__ = _H1_PKG_PRIVATE  # This enables relative imports to work!
            sys.modules[full_name] = mod
            
            # 3. ALIAS: allows other scripts (e.g. candidates.py)
            #    to continue using "from epv_pipeline import EPVPipeline" without breaking.
            sys.modules["epv_pipeline"] = mod  
            
            spec.loader.exec_module(mod)

# ── StatsBomb competition identifiers (UEFA Euro 2024) ────────────────────────
COMPETITION_ID = 55
SEASON_ID      = 282

# ── Pitch dimensions (UEFA standard, metres) ──────────────────────────────────
PITCH_LENGTH = 105.0
PITCH_WIDTH  = 68.0

# ── StatsBomb -> metres conversion (same as H1 and H2) ───────────────────────
X_SCALE = PITCH_LENGTH / 120.0   # 0.875
Y_SCALE = PITCH_WIDTH  / 80.0    # 0.85

# ── EPV grid layout (32 x 50, inherited from H1) ──────────────────────────────
EPV_ROWS = 32
EPV_COLS = 50

# ── Receiver resolution ────────────────────────────────────────────────────────
# WINDOW_SECONDS = max staleness PER SIDE (s): the resolver estimates a
# teammate's position only from an event within this many seconds before OR
# after the pass. Calibrated in §1.6.1 (10-match sweep): at the chosen
# CONF_THR_M = 8 m, accuracy on confident dots rises as the window tightens
# (88% at 20 s -> 96% at 5 s) while the confident-candidate VOLUME stays flat
# (~1.0x across all W) — tighter = fresher position estimates at no volume cost.
# The full-pipeline URS/90 ranking is stable across W (Spearman rho 0.96 vs
# W=20), so 5 s is chosen for maximum per-candidate accuracy.
WINDOW_SECONDS = 5.0
# CONF_THR_M = max localisation residual (m) for a dot to count "confident".
# At 8 m the mean residual of confident dots is ~4 m and accuracy ~96%;
# tightening to 6 m does NOT raise accuracy but drops ~17% of candidates.
CONF_THR_M     = 8.0

# ── URS ───────────────────────────────────────────────────────────────────────
RECEIVED_WINDOW_S = 4.0
MIN_MINUTES       = 135

# ── Macro-role mapping (verbatim from H1/H2 config.py) ────────────────────────
# IMPORTANT: keys must match the StatsBomb position strings EXACTLY as they
# appear in H1's `primary_role` column — the Left/Right/Center variants
# ("Left Center Back", "Center Attacking Midfield", ...). A shortened key like
# "Center Back" silently sends every "Left/Right Center Back" to the default,
# which collapsed CB 61->9 and CAM 25->0 in earlier runs. Two-stage mapping
# (fine ROLE_MAP -> ROLE_REMAP) is identical to H1/H2, so H3's macro_role
# matches H2's 272-player pool exactly (CB 61, FB 56, MID 67, CAM 25, WIDE 29,
# FW 34).
ROLE_MAP = {
    "Goalkeeper"               : "GK",
    "Right Back"               : "FB",  "Left Back"                : "FB",
    "Right Wing Back"          : "FB",  "Left Wing Back"           : "FB",
    "Right Center Back"        : "CB",  "Left Center Back"         : "CB",
    "Center Back"              : "CB",
    "Right Defensive Midfield" : "CDM", "Left Defensive Midfield"  : "CDM",
    "Center Defensive Midfield": "CDM",
    "Right Center Midfield"    : "CM",  "Left Center Midfield"     : "CM",
    "Center Midfield"          : "CM",
    "Right Attacking Midfield" : "CAM", "Left Attacking Midfield"  : "CAM",
    "Center Attacking Midfield": "CAM",
    "Right Midfield"           : "WM",  "Left Midfield"            : "WM",
    "Right Wing"               : "W",   "Left Wing"                : "W",
    "Right Center Forward"     : "FW",  "Left Center Forward"      : "FW",
    "Center Forward"           : "FW",
    "Secondary Striker"        : "FW",  "Striker"                  : "FW",
}

# Collapses small-sample fine roles into the 6 analysis macro-roles (H1/H2).
ROLE_REMAP = {"CDM": "MID", "CM": "MID", "W": "WIDE", "WM": "WIDE"}

MACRO_ROLES = ["CB", "FB", "MID", "CAM", "WIDE", "FW"]

def map_role(position: str) -> str:
    """Map a StatsBomb position string to a macro-role label (same as H1/H2).

    Two-stage: fine ROLE_MAP then ROLE_REMAP (CDM/CM -> MID, W/WM -> WIDE).
    Unknown positions return 'OTHER' so they surface instead of silently
    becoming MID.
    """
    fine = ROLE_MAP.get(str(position), "OTHER")
    return ROLE_REMAP.get(fine, fine)

# ── Output paths ───────────────────────────────────────────────────────────────
DATA_DIR           = H3_DIR / "data"
CACHE_DIR          = DATA_DIR / "cache"
CANDIDATES_PARQUET = DATA_DIR / "off_ball_candidates.parquet"
XEPV_PARQUET       = DATA_DIR / "off_ball_xepv.parquet"
URS_CSV            = DATA_DIR / "player_urs_aggregated.csv"

# ── H2 outputs consumed by H3 (read-only) ─────────────────────────────────────
# Only the saved xPass model is needed: candidates.py recomputes xPass on the
# fly from the live freeze frames (StatsBomb regenerated every event UUID, so a
# merge on H2's frozen alternatives.parquet would yield zero rows — see
# candidates._score_candidates). The old alternatives / corpus-cache paths were
# removed with that fix.
H2_XPASS_MODEL   = H2_SRC.parent / "data" / "xpass_model_gbm_sigmoid.joblib"

# ── H1 outputs consumed by H3 (read-only) ─────────────────────────────────────
# Authoritative per-player aggregate: one role per player + minutes, the exact
# pool H2 inherits (135 min, 272 players). It carries `macro_role` already
# computed as the per-event role MODE (aggregation.py), NOT derived from the
# nominal primary_role — so a player who lined up mostly as MID despite a CAM
# label reads as MID. H3 reads this same file with the same columns H2 reads
# (decision_quality.py: usecols player/team/primary_role/macro_role/minutes),
# so all three hypotheses share a byte-identical 272-player role assignment.
H1_PLAYER_AGG    = REPO_ROOT / "H1_Space_Control_and_Value" / "data" / \
                   "player_space_control_aggregated.csv"
# Totals file (no macro_role column) — kept only as a fallback minutes source.
H1_PLAYER_TOTALS = REPO_ROOT / "H1_Space_Control_and_Value" / "data" / \
                   "Euro2024_Player_Totals_Distances_Roles.csv"

# ── H2 package loader ──────────────────────────────────────────────────────────
_H2_PKG_PRIVATE = "_dq_src"          # private name — never conflicts with anything
_H2_SUB_MODULES = ("config", "geometry", "features", "xpass", "xepv")

def load_h2_package():
    """Load H2_Decision_Quality/src/ as the private package `_dq_src`.

    Relative imports inside H2 (e.g. `from . import config`) resolve
    correctly because every sub-module is registered under `_dq_src.*`.
    This avoids any collision with H3_Off_Ball_Movement/src/.

    Returns the package object; access modules as attributes:
        h2 = load_h2_package()
        h2.features.features_for_all_candidates(df)
        h2.xpass.CalibratedXPass()
    """
    if _H2_PKG_PRIVATE in sys.modules:
        return sys.modules[_H2_PKG_PRIVATE]

    if not H2_SRC.exists():
        raise ImportError(
            f"H2 source directory not found: {H2_SRC}\n"
            "Update H2_SRC in H3_Off_Ball_Movement/src/config.py to match your layout."
        )

    # Register the package stub so relative imports resolve correctly.
    pkg = types.ModuleType(_H2_PKG_PRIVATE)
    pkg.__path__ = [str(H2_SRC)]
    pkg.__package__ = _H2_PKG_PRIVATE
    sys.modules[_H2_PKG_PRIVATE] = pkg

    for mod_name in _H2_SUB_MODULES:
        full_name = f"{_H2_PKG_PRIVATE}.{mod_name}"
        if full_name in sys.modules:
            continue
        file_path = H2_SRC / f"{mod_name}.py"
        if not file_path.exists():
            continue
        spec = importlib.util.spec_from_file_location(
            full_name, file_path,
            submodule_search_locations=[],
        )
        mod = importlib.util.module_from_spec(spec)
        mod.__package__ = _H2_PKG_PRIVATE
        sys.modules[full_name] = mod
        spec.loader.exec_module(mod)
        setattr(pkg, mod_name, mod)

    return pkg
