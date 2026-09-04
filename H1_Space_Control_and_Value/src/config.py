"""Central configuration: paths, thresholds, role maps, pitch geometry."""
from pathlib import Path

# =============================================================================
# Paths
# =============================================================================
ROOT      = Path(__file__).resolve().parent.parent
DATA_DIR  = ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Inputs
EPV_GRID_PATH = DATA_DIR / "EPV_grid.csv"
TOTALS_CSV    = DATA_DIR / "Euro2024_Player_Totals_Distances_Roles.csv"
TOTALS_XLSX   = DATA_DIR / "Euro2024_Player_Totals_Distances_Roles.xlsx"

# Hull pipeline outputs
HULL_EVENTS_RAW     = DATA_DIR / "hull_events_raw.csv"
HULL_ZONE_BASELINES = DATA_DIR / "hull_zone_baselines.csv"
HULL_METRICS_AGG    = DATA_DIR / "hull_metrics_aggregated.csv"

# EPV / Line-breaker outputs
HULL_EVENTS_EPV = DATA_DIR / "hull_events_with_epv.csv"
HULL_EVENTS_LB  = DATA_DIR / "hull_events_lb.csv"

# Final aggregations
PLAYER_AGG_PATH     = DATA_DIR / "player_space_control_aggregated.csv"
PLAYER_INDICES_PATH = DATA_DIR / "player_space_control_indices.csv"

# Caches (gitignored)
OPP_CENTROIDS_CACHE = CACHE_DIR / "opp_centroids_cache.parquet"
OPP_POSITIONS_CACHE = CACHE_DIR / "opp_positions_cache.parquet"


# =============================================================================
# Pitch geometry — UEFA standard 105 x 68 m
# =============================================================================
PITCH_LENGTH_M = 105.0
PITCH_WIDTH_M  = 68.0

# Conversion from StatsBomb yard system (120 x 80) to meters
X_SCALE = PITCH_LENGTH_M / 120.0   # 0.875
Y_SCALE = PITCH_WIDTH_M  /  80.0   # 0.850


# =============================================================================
# Tournament identifiers
# =============================================================================
COMPETITION_ID = 55     # UEFA Euro
SEASON_ID      = 282    # Euro 2024


# =============================================================================
# Hull-metrics parameters
# =============================================================================
PRESSURE_RADIUS     = 2.5    # meters - "under pressure" threshold
PRESSURE_MIN        = 2      # min opponents within PRESSURE_RADIUS
K_NEAREST           = 4      # opponents used for the proximity signal
ZONE_X_BINS         = 12     # columns along the length (~8.75 m per zone)
ZONE_Y_BINS         = 8      # rows along the width    (~8.50 m per zone)
MIN_BASELINE_FRAMES = 10     # min frames (after LOO) to use the baseline
MIN_MINUTES         = 0      # filter on the totals file (0 = include everyone)


# =============================================================================
# Line-breaker parameters
# =============================================================================
BYPASS_THRESHOLD = 3      # number of opponents to bypass for a geom line-break
CORRIDOR_M       = 5.0    # corridor width along the pass line


# =============================================================================
# Analysis (indices, dashboard, validation)
# =============================================================================
ANALYSIS_MIN_MINUTES = 135   # filters out players with < 1.5 matches


# =============================================================================
# Role mapping: StatsBomb position -> macro-role
# =============================================================================
ROLE_MAP = {
    'Goalkeeper': 'GK',
    'Right Back': 'FB', 'Left Back': 'FB',
    'Right Wing Back': 'FB', 'Left Wing Back': 'FB',
    'Right Center Back': 'CB', 'Left Center Back': 'CB', 'Center Back': 'CB',
    'Right Defensive Midfield': 'CDM', 'Left Defensive Midfield': 'CDM',
    'Center Defensive Midfield': 'CDM',
    'Right Center Midfield': 'CM', 'Left Center Midfield': 'CM',
    'Center Midfield': 'CM',
    'Right Attacking Midfield': 'CAM', 'Left Attacking Midfield': 'CAM',
    'Center Attacking Midfield': 'CAM',
    'Right Midfield': 'WM', 'Left Midfield': 'WM',
    'Right Wing': 'W', 'Left Wing': 'W',
    'Right Center Forward': 'FW', 'Left Center Forward': 'FW',
    'Center Forward': 'FW',
    'Secondary Striker': 'FW', 'Striker': 'FW',
}

# Collapses small-sample groups for the analysis layer
ROLE_REMAP = {'CDM': 'MID', 'CM': 'MID', 'W': 'WIDE', 'WM': 'WIDE'}

MACRO_ROLES = ['CB', 'FB', 'MID', 'CAM', 'WIDE', 'FW']


def map_role(pos: str) -> str:
    """Map a StatsBomb position string to its macro-role label."""
    return ROLE_MAP.get(str(pos), 'OTHER')
