"""EPV pipeline + grid sanity-check visualisation.

Two entry points:

    show_grid_diagnostic()   - plots the EPV grid in three colour scales
                                (linear / log / power) plus contour view, and
                                prints orientation / dynamic-range checks.
                                Use as a one-off sanity check on EPV_grid.csv.

    main()                    - enriches hull_events_raw.csv with EPV
                                features and FILTERS to open play (set
                                pieces are dropped). Output:
                                data/hull_events_with_epv.csv
"""
import time
import warnings

import matplotlib.patches as patches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LogNorm, PowerNorm
from statsbombpy import sb

try:
    from . import config
except ImportError:
    import config

warnings.filterwarnings('ignore')


# =============================================================================
# Bilinear EPV lookup
# =============================================================================
def _epv_at(epv_grid, x_m, y_m):
    if x_m is None or y_m is None or pd.isna(x_m) or pd.isna(y_m):
        return np.nan
    rows, cols = epv_grid.shape
    col_c = np.clip(x_m / config.PITCH_LENGTH_M * cols, 0, cols - 1.0001)
    row_c = np.clip(y_m / config.PITCH_WIDTH_M  * rows, 0, rows - 1.0001)
    col_lo, row_lo = int(col_c), int(row_c)
    fx, fy = col_c - col_lo, row_c - row_lo
    v_tl = epv_grid[row_lo,     col_lo]
    v_tr = epv_grid[row_lo,     col_lo + 1]
    v_bl = epv_grid[row_lo + 1, col_lo]
    v_br = epv_grid[row_lo + 1, col_lo + 1]
    return (v_tl * (1 - fx) * (1 - fy) + v_tr * fx * (1 - fy) +
            v_bl * (1 - fx) * fy       + v_br * fx * fy)


# =============================================================================
# Sanity-check visualisation of the EPV grid
# =============================================================================
def _draw_pitch(ax, color='black', lw=1.4):
    L, W = config.PITCH_LENGTH_M, config.PITCH_WIDTH_M
    ax.plot([0, L, L, 0, 0], [0, 0, W, W, 0], color=color, lw=lw)
    ax.plot([L/2, L/2], [0, W], color=color, lw=lw)
    ax.add_patch(patches.Circle((L/2, W/2), 9.15, fill=False, edgecolor=color, lw=lw))
    ax.add_patch(patches.Rectangle((0, (W-40.32)/2),       16.5, 40.32, fill=False, edgecolor=color, lw=lw))
    ax.add_patch(patches.Rectangle((L-16.5, (W-40.32)/2),  16.5, 40.32, fill=False, edgecolor=color, lw=lw))
    ax.add_patch(patches.Rectangle((0, (W-18.32)/2),        5.5, 18.32, fill=False, edgecolor=color, lw=lw))
    ax.add_patch(patches.Rectangle((L-5.5, (W-18.32)/2),    5.5, 18.32, fill=False, edgecolor=color, lw=lw))
    ax.plot(L/2, W/2, 'o', color=color, markersize=3)
    ax.set_xlim(-2, L+2); ax.set_ylim(-2, W+2)
    ax.set_aspect('equal'); ax.set_xticks([]); ax.set_yticks([])


def show_grid_diagnostic():
    """Plot the EPV grid in three colour scales and print sanity stats."""
    epv = pd.read_csv(config.EPV_GRID_PATH, header=None).values.astype(float)
    rows, cols = epv.shape

    print(f"EPV grid shape : {epv.shape}  (rows=Y/width, cols=X/length)")
    print(f"  min  = {epv.min():.4f}")
    print(f"  max  = {epv.max():.4f}")
    print(f"  mean = {epv.mean():.4f}")
    rmax, cmax = np.unravel_index(np.argmax(epv), epv.shape)
    x_peak = (cmax + 0.5) / cols * config.PITCH_LENGTH_M
    y_peak = (rmax + 0.5) / rows * config.PITCH_WIDTH_M
    print(f"  argmax at grid (row={rmax}, col={cmax}) -> "
          f"pitch (x~{x_peak:.1f} m, y~{y_peak:.1f} m)")
    print(f"  ratio max/min = {epv.max() / max(epv.min(), 1e-9):.1f}x  "
          f"(-> linear scale flattens everything except the peak)")

    fig, axes = plt.subplots(1, 3, figsize=(22, 6))

    # (1) Linear
    ax = axes[0]
    im = ax.imshow(epv, extent=(0, config.PITCH_LENGTH_M, 0, config.PITCH_WIDTH_M),
                   origin='lower', cmap='viridis', aspect='equal', alpha=0.92)
    _draw_pitch(ax, color='white', lw=1.3)
    ax.set_title('Linear  (absolute values)', fontsize=12)
    plt.colorbar(im, ax=ax, fraction=0.035, pad=0.02, label='EPV')

    # (2) Log
    ax = axes[1]
    im = ax.imshow(epv, extent=(0, config.PITCH_LENGTH_M, 0, config.PITCH_WIDTH_M),
                   origin='lower', cmap='viridis', aspect='equal', alpha=0.92,
                   norm=LogNorm(vmin=max(epv.min(), 1e-4), vmax=epv.max()))
    _draw_pitch(ax, color='white', lw=1.3)
    ax.set_title('Log  (structure across the whole pitch)', fontsize=12)
    plt.colorbar(im, ax=ax, fraction=0.035, pad=0.02, label='EPV (log)')

    # (3) Power (gamma=0.4)
    ax = axes[2]
    im = ax.imshow(epv, extent=(0, config.PITCH_LENGTH_M, 0, config.PITCH_WIDTH_M),
                   origin='lower', cmap='viridis', aspect='equal', alpha=0.92,
                   norm=PowerNorm(gamma=0.4, vmin=epv.min(), vmax=epv.max()))
    _draw_pitch(ax, color='white', lw=1.3)
    ax.set_title(r'PowerNorm $\gamma=0.4$  (compromise)', fontsize=12)
    plt.colorbar(im, ax=ax, fraction=0.035, pad=0.02, label='EPV')

    plt.suptitle('EPV grid - sanity check before Step 2A',
                 fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.show()

    # Contour with log-spaced levels
    fig, ax = plt.subplots(figsize=(12, 6))
    X = np.linspace(0, config.PITCH_LENGTH_M, cols)
    Y = np.linspace(0, config.PITCH_WIDTH_M,  rows)
    levels = np.geomspace(max(epv.min(), 1e-4), epv.max(), 14)
    cs = ax.contourf(X, Y, epv, levels=levels, cmap='viridis',
                     norm=LogNorm(levels[0], levels[-1]))
    ax.contour(X, Y, epv, levels=levels, colors='white', linewidths=0.4, alpha=0.6)
    _draw_pitch(ax, color='black', lw=1.3)
    ax.set_title('EPV isolines (geometric levels - log spacing)', fontsize=12)
    plt.colorbar(cs, ax=ax, fraction=0.035, pad=0.02, label='EPV')
    plt.tight_layout()
    plt.show()

    # Orientation sanity
    left_mean  = epv[:, :cols // 2].mean()
    right_mean = epv[:,  cols // 2:].mean()
    print(f"\nOrientation sanity check:")
    print(f"  left half  (defensive): mean EPV = {left_mean:.4f}")
    print(f"  right half (attacking): mean EPV = {right_mean:.4f}")
    if right_mean > left_mean:
        print("  OK: grid is oriented correctly (attack to the right).")
    else:
        print("  WARNING: EPV is higher on the left - check orientation!")

    thirds = [(0, cols // 3, 'defensive third'),
              (cols // 3, 2 * cols // 3, 'middle third'),
              (2 * cols // 3, cols, 'attacking third')]
    print(f"\nMean EPV by pitch third:")
    for a, b, name in thirds:
        print(f"  {name:20s}: {epv[:, a:b].mean():.4f}  (max = {epv[:, a:b].max():.4f})")


# =============================================================================
# EPV pipeline — enrich hull events with EPV features (open play only)
# =============================================================================
def main():
    print("\nSTEP 1 - Loading EPV grid")
    epv_grid = pd.read_csv(config.EPV_GRID_PATH, header=None).values.astype(float)

    print("\nSTEP 3 - Re-fetching pass coordinates and filtering Open Play")
    print("  (automatically excludes Corners, Free Kicks, Throw-ins and Kick-offs)")

    event_locations = {}
    open_play_ids   = set()
    unique_matches  = pd.read_csv(config.HULL_EVENTS_RAW)['match_id'].unique()

    t0 = time.time()
    for i, match_id in enumerate(unique_matches, 1):
        try:
            df_ev = sb.events(match_id=match_id)
            # Filter: 'type' must be Pass and 'pass_type' must be NaN (Open Play)
            # In StatsBomb set-piece passes always carry a value in 'pass_type'
            mask = (df_ev['type'] == 'Pass') & \
                   (df_ev['pass_type'].isna()) & \
                   (df_ev['location'].notna()) & \
                   (df_ev['pass_end_location'].notna())

            for _, r in df_ev[mask].iterrows():
                ev_id = r['id']
                start, end = r['location'], r['pass_end_location']
                open_play_ids.add(ev_id)
                event_locations[ev_id] = (
                    start[0] * config.X_SCALE, start[1] * config.Y_SCALE,
                    end[0]   * config.X_SCALE, end[1]   * config.Y_SCALE,
                )
        except Exception as e:
            print(f"  Match {match_id}: SKIP ({e})")
        if i % 10 == 0 or i == len(unique_matches):
            print(f"  [{i}/{len(unique_matches)}] matches processed... ({time.time()-t0:.1f}s)")

    print("\nSTEP 4 - Joining coordinates and computing EPV features")
    df_hull = pd.read_csv(config.HULL_EVENTS_RAW)

    # Hard filter: keep only the Open Play events we identified
    initial_len = len(df_hull)
    df_hull = df_hull[df_hull['event_id'].isin(open_play_ids)].reset_index(drop=True)
    print(f"  Removed {initial_len - len(df_hull)} set-piece events.")

    # Join coordinates
    def get_coords(ev_id):
        return event_locations.get(ev_id, (np.nan, np.nan, np.nan, np.nan))

    coords = df_hull['event_id'].apply(
        lambda eid: pd.Series(get_coords(eid),
                              index=['start_x_m', 'start_y_m', 'end_x_m', 'end_y_m'])
    )
    df_hull = pd.concat([df_hull, coords], axis=1)

    # Compute EPV
    df_hull['epv_start'] = df_hull.apply(
        lambda r: _epv_at(epv_grid, r['start_x_m'], r['start_y_m']), axis=1)
    df_hull['epv_end']   = df_hull.apply(
        lambda r: _epv_at(epv_grid, r['end_x_m'],   r['end_y_m']),   axis=1)
    df_hull['epv_added'] = df_hull['epv_end'] - df_hull['epv_start']

    # Re-identify geom_type on the clean (open-play) subset
    df_hull['geom_type'] = 'Other'
    df_hull.loc[(~df_hull['player_between_lines']) & df_hull['end_inside_hull'],
                'geom_type'] = 'Penetration (out->in)'
    df_hull.loc[df_hull['player_between_lines']  & (~df_hull['end_inside_hull']),
                'geom_type'] = 'Exit (in->out)'
    df_hull.loc[df_hull['player_between_lines']  &  df_hull['end_inside_hull'],
                'geom_type'] = 'Inside circulation (in->in)'
    df_hull.loc[(~df_hull['player_between_lines']) & (~df_hull['end_inside_hull']),
                'geom_type'] = 'Outside circulation (out->out)'

    df_hull.to_csv(config.HULL_EVENTS_EPV, index=False)
    print(f"\nDONE. File saved at: {config.HULL_EVENTS_EPV}")
    return df_hull

# =============================================================================
# Wrapper Class for H3 Off-Ball-movement
# =============================================================================
class EPVPipeline:
    def __init__(self):
        """Load the EPV grid into memory during class initialization."""
        self.grid = pd.read_csv(config.EPV_GRID_PATH, header=None).values.astype(float)

    def epv_at(self, x_m, y_m):
        """Return the interpolated EPV value for coordinates in meters."""
        return _epv_at(self.grid, x_m, y_m)

if __name__ == "__main__":
    main()
