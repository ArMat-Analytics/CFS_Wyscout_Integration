"""Dashboard prototypes — 4 views over the composite indices.

    player_profile(query, df, pct)    - 4-panel radar of the indices
    head_to_head(q1, q2, df, pct)     - overlaid radar (same role recommended)
    role_leaderboard(role, theme, df, pct, ...) - top-N within role
    role_archetypes(role, x, y, df, pct, ...)   - 2D scatter for cluster discovery
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from . import config
from .indices import RADAR_SPECS, percentile_matrix


def _render_static(fig):
    """Emit a static PNG copy of the figure into the notebook output.

    Why: GitHub renders only embedded images in .ipynb cells, not Plotly's
    interactive HTML. Emitting a PNG alongside the interactive view keeps the
    notebook viewable on github.com.
    """
    from IPython.display import Image, display
    display(Image(fig.to_image(format="png", scale=2)))


_ROLE_COLOR = {
    "CB":   "#1f77b4",
    "FB":   "#17becf",
    "MID":  "#2ca02c",
    "CAM":  "#ff7f0e",
    "WIDE": "#9467bd",
    "FW":   "#d62728",
}
_THEME_COLOR = {
    "PROGRESSION":   "#2ca02c",
    "DANGEROUSNESS": "#d62728",
    "RECEPTION":     "#ff7f0e",
    "GRAVITY":       "#9467bd",
}


# =============================================================================
# Helpers
# =============================================================================
def _resolve(df, query):
    """Find the unique player matching a substring (case-insensitive)."""
    mask = df["player"].str.contains(query, case=False, na=False, regex=False)
    m = df[mask]
    if m.empty:
        print(f"[ERR] No match for '{query}'"); return None
    if len(m) > 1:
        print(f"[ERR] Multiple matches for '{query}' - be more specific:")
        print(m[["player", "team", "primary_role", "minutes_played"]].to_string(index=False))
        return None
    return m.index[0]


def _gravity_icon(v):
    if pd.isna(v):
        return "•"
    return "↑" if v > 0.1 else ("↓" if v < -0.1 else "•")


def _quality_tag(p):
    """Reliability of the player's data (coverage + small-n flags)."""
    cov  = p.get("coverage_pct", np.nan)
    n_pr = p.get("pressure_resistance_n", np.nan)
    flags = []
    if pd.notna(cov):
        if cov < 50:
            flags.append(f"⚠ low coverage ({cov:.0f}%)")
        elif cov < 70:
            flags.append(f"medium coverage ({cov:.0f}%)")
    if pd.notna(n_pr) and n_pr < 8:
        flags.append(f"⚠ pressure-test n={int(n_pr)}")
    return " | ".join(flags) if flags else "ok"


def _similar_players(idx, pct, k=3):
    """Find the k nearest peers (within macro_role) by Euclidean distance."""
    role  = pct.loc[idx, "macro_role"]
    peers = pct.index[pct["macro_role"] == role].tolist()
    matrix = percentile_matrix(pct)
    target = matrix[idx]
    dists  = []
    for j in peers:
        if j == idx:
            continue
        d = float(np.sqrt(np.nansum((matrix[j] - target) ** 2)))
        dists.append((j, d))
    dists.sort(key=lambda x: x[1])
    return dists[:k]


# =============================================================================
# Player profile — 4-panel radar
# =============================================================================
def player_profile(query: str, df: pd.DataFrame, pct: pd.DataFrame):
    idx = _resolve(df, query)
    if idx is None:
        return
    p, pp = df.loc[idx], pct.loc[idx]

    idxs    = {t: pp[f"{t}_idx"] for t in RADAR_SPECS}
    sign_ic = _gravity_icon(p["gravity_directional_m"])

    axes = []
    for theme, spec in RADAR_SPECS.items():
        for lab, var, _ in spec:
            axes.append((f"{lab} [{theme[:4]}]", pp[f"{var}__p"]))
    axes = [(n, v) for n, v in axes if not pd.isna(v)]
    axes.sort(key=lambda x: x[1], reverse=True)
    sim = _similar_players(idx, pct, k=3)

    print("=" * 86)
    print(f"  {p['player']}  -  {p['team']}")
    print(f"  Role: {p['primary_role']} ({p['macro_role']})   Minutes: {int(p['minutes_played'])}")
    print(f"  Quality: {_quality_tag(p)}")
    print("-" * 86)
    print(f"  PROGRESSION    {idxs['PROGRESSION']:5.1f}/100       "
          f"DANGEROUSNESS  {idxs['DANGEROUSNESS']:5.1f}/100")
    print(f"  RECEPTION      {idxs['RECEPTION']:5.1f}/100       "
          f"GRAVITY        {idxs['GRAVITY']:5.1f}/100 {sign_ic}")
    pr_pct = p.get("pressure_resistance_pct", np.nan)
    pr_n   = p.get("pressure_resistance_n",   np.nan)
    gc     = p.get("gravity_composite_pct",   np.nan)
    if pd.notna(pr_pct) and pd.notna(pr_n):
        print(f"  pressure-resist (annot)     {pr_pct:5.1f}%  on n={int(pr_n)}")
    if pd.notna(gc):
        print(f"  gravity_composite (derived) {gc:+5.1f}%  [mean of hull+proximity, off-radar]")
    print("-" * 86)
    print(f"  TOP STRENGTHS (percentile within {p['macro_role']}):")
    for n, v in axes[:3]:
        print(f"    + {n:<32s}  {v:5.1f}")
    print(f"  TOP WEAKNESSES:")
    for n, v in axes[-3:]:
        print(f"    - {n:<32s}  {v:5.1f}")
    print("-" * 86)
    print(f"  MOST SIMILAR (within {p['macro_role']}):")
    for j, d in sim:
        print(f"    ~ {df.loc[j, 'player']:<25s} ({df.loc[j, 'team']:<15s}  dist={d:5.1f})")
    print("=" * 86)

    theme_list = list(RADAR_SPECS.keys())
    fig = make_subplots(
        rows=2, cols=2,
        specs=[[{"type": "polar"}, {"type": "polar"}],
               [{"type": "polar"}, {"type": "polar"}]],
        subplot_titles=[
            f"<b>{t}</b><br><span style='font-size:11px;color:#666'>"
            f"idx {idxs[t]:.0f}/100"
            f"{' ' + sign_ic if t == 'GRAVITY' else ''}</span>"
            for t in theme_list
        ],
        horizontal_spacing=0.14, vertical_spacing=0.18,
    )
    for i, theme in enumerate(theme_list):
        row = i // 2 + 1
        col = i % 2 + 1
        spec  = RADAR_SPECS[theme]
        color = _THEME_COLOR[theme]
        labs, vals, hov = [], [], []
        for lab, var, base in spec:
            v = pp[f"{var}__p"]
            labs.append(lab)
            vals.append(0 if pd.isna(v) else v)
            h = f"<b>{lab}</b><br>Raw: {p[var]:.2f}<br>Pct in {p['macro_role']}: {v:.0f}"
            if base is not None and base in p.index and not pd.isna(p[base]):
                h += f"<br>n = {int(p[base])}"
            hov.append(h)
        labs.append(labs[0]); vals.append(vals[0]); hov.append(hov[0])
        fig.add_trace(go.Scatterpolar(
            r=vals, theta=labs, fill="toself",
            hoverinfo="text", hovertext=hov,
            line=dict(color=color, width=2.5),
            fillcolor=color, opacity=0.35, showlegend=False,
        ), row=row, col=col)

    fig.update_layout(
        title=(f"<b>{p['player']}</b>  ·  {p['team']}  ·  "
               f"{p['primary_role']} ({p['macro_role']})  ·  "
               f"{int(p['minutes_played'])} min"),
        height=900, width=1200,
        margin=dict(t=110, b=40, l=60, r=60),
    )
    for pol in ["polar", "polar2", "polar3", "polar4"]:
        # polar2 is the DANGEROUSNESS subplot (4 axes). With 4 categorical axes
        # the default layout puts one axis exactly at 90° (top), which collides
        # with the subplot title. Rotate the angular axis by 45° so the four
        # axes sit on the diagonals (NE/NW/SW/SE), keeping the top clear.
        angular = dict(gridcolor="#ddd", tickfont=dict(size=10))
        if pol == "polar2":
            angular["rotation"] = 45
        fig.update_layout({pol: dict(
            radialaxis=dict(range=[0, 100], tickvals=[20, 40, 60, 80],
                            gridcolor="#ddd", tickfont=dict(size=9)),
            angularaxis=angular,
        )})
    fig.show()
    _render_static(fig)


# =============================================================================
# Head-to-head — 4-panel radar, overlaid
# =============================================================================
def head_to_head(q1: str, q2: str, df: pd.DataFrame, pct: pd.DataFrame):
    i1, i2 = _resolve(df, q1), _resolve(df, q2)
    if i1 is None or i2 is None:
        return
    p1, p2   = df.loc[i1],  df.loc[i2]
    pp1, pp2 = pct.loc[i1], pct.loc[i2]
    if p1["macro_role"] != p2["macro_role"]:
        print(f"[WARN] Different roles ({p1['macro_role']} vs {p2['macro_role']}): "
              "percentiles are computed within different role pools. Read with caution.")

    print("=" * 86)
    print(f"  HEAD-TO-HEAD:  {p1['player']}  vs  {p2['player']}")
    print(f"                 {p1['team']:<25s}  {p2['team']}")
    print(f"                 {p1['macro_role']} · {int(p1['minutes_played'])}m         "
          f"{p2['macro_role']} · {int(p2['minutes_played'])}m")
    print("-" * 86)
    print(f"  {'Index':<14s}{p1['player'][:20]:>22s}   {p2['player'][:20]:>22s}    Winner")
    for theme in RADAR_SPECS:
        v1, v2 = pp1[f"{theme}_idx"], pp2[f"{theme}_idx"]
        w = p1["player"] if v1 > v2 else p2["player"]
        print(f"  {theme:<14s}{v1:>22.1f}   {v2:>22.1f}    {w[:18]} (+{abs(v1 - v2):.1f})")
    print("=" * 86)

    C1, C2 = "#1f77b4", "#d62728"
    theme_list = list(RADAR_SPECS.keys())
    fig = make_subplots(
        rows=2, cols=2,
        specs=[[{"type": "polar"}, {"type": "polar"}],
               [{"type": "polar"}, {"type": "polar"}]],
        subplot_titles=theme_list,
        horizontal_spacing=0.14, vertical_spacing=0.18,
    )
    for i, theme in enumerate(theme_list):
        row = i // 2 + 1
        col = i % 2 + 1
        spec = RADAR_SPECS[theme]
        labs = [lab for lab, _, _ in spec]
        v1s = [0 if pd.isna(pp1[f"{var}__p"]) else pp1[f"{var}__p"] for _, var, _ in spec]
        v2s = [0 if pd.isna(pp2[f"{var}__p"]) else pp2[f"{var}__p"] for _, var, _ in spec]
        labs_c = labs + [labs[0]]
        v1s_c  = v1s  + [v1s[0]]
        v2s_c  = v2s  + [v2s[0]]
        fig.add_trace(go.Scatterpolar(
            r=v1s_c, theta=labs_c, fill="toself",
            name=p1["player"], legendgroup="p1", showlegend=(i == 0),
            line=dict(color=C1, width=2.8), fillcolor=C1, opacity=0.30,
        ), row=row, col=col)
        fig.add_trace(go.Scatterpolar(
            r=v2s_c, theta=labs_c, fill="toself",
            name=p2["player"], legendgroup="p2", showlegend=(i == 0),
            line=dict(color=C2, width=2.8), fillcolor=C2, opacity=0.30,
        ), row=row, col=col)

    role_str = (p1["macro_role"]
                + (f"/{p2['macro_role']}" if p1["macro_role"] != p2["macro_role"] else ""))
    fig.update_layout(
        title=f"<b>Head-to-head</b> · {p1['player']} vs {p2['player']} · {role_str}",
        height=900, width=1200,
        margin=dict(t=110, b=80, l=60, r=60),
        legend=dict(orientation="h", yanchor="bottom", y=-0.05,
                    xanchor="center", x=0.5),
    )
    for pol in ["polar", "polar2", "polar3", "polar4"]:
        # polar2 is the DANGEROUSNESS subplot (4 axes). With 4 categorical axes
        # the default layout puts one axis exactly at 90° (top), which collides
        # with the subplot title. Rotate the angular axis by 45° so the four
        # axes sit on the diagonals (NE/NW/SW/SE), keeping the top clear.
        angular = dict(gridcolor="#ddd", tickfont=dict(size=10))
        if pol == "polar2":
            angular["rotation"] = 45
        fig.update_layout({pol: dict(
            radialaxis=dict(range=[0, 100], tickvals=[20, 40, 60, 80],
                            gridcolor="#ddd", tickfont=dict(size=9)),
            angularaxis=angular,
        )})
    fig.show()
    _render_static(fig)


# =============================================================================
# Role leaderboard
# =============================================================================
def role_leaderboard(role: str, theme: str, df: pd.DataFrame, pct: pd.DataFrame,
                     top_n: int = 15,
                     min_minutes: int = config.ANALYSIS_MIN_MINUTES):
    if role not in _ROLE_COLOR:
        print(f"[ERR] Invalid role '{role}'. Use: {list(_ROLE_COLOR)}"); return
    if theme not in RADAR_SPECS:
        print(f"[ERR] Invalid theme '{theme}'. Use: {list(RADAR_SPECS)}"); return

    pool = pct[(pct["macro_role"] == role)
               & (pct["minutes_played"] >= min_minutes)].copy()
    if pool.empty:
        print(f"[ERR] No {role} player with min >= {min_minutes}"); return

    idx_col = f"{theme}_idx"
    pool = pool.sort_values(idx_col, ascending=True).tail(top_n)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=pool[idx_col],
        y=pool["player"] + "  ·  " + pool["team"],
        orientation="h",
        text=pool[idx_col].round(0).astype(int),
        textposition="inside",
        textfont=dict(color="white", size=11),
        marker=dict(color=_THEME_COLOR[theme], line=dict(color="#222", width=0.5)),
        customdata=pool["minutes_played"].astype(int),
        hovertemplate=("<b>%{y}</b><br>"
                       f"{theme} idx: " + "%{x:.1f}<br>"
                       "Minutes: %{customdata}<extra></extra>"),
    ))
    n_pool = int(((pct["macro_role"] == role)
                  & (pct["minutes_played"] >= min_minutes)).sum())
    fig.update_layout(
        title=(f"<b>Top {top_n} {role} by {theme}</b>  "
               f"<span style='font-size:12px;color:#888'>"
               f"(within-role composite percentile, min {min_minutes} min · "
               f"eligible pool = {n_pool})</span>"),
        xaxis=dict(title=f"{theme} index (0–100)", range=[0, 100]),
        yaxis=dict(title="", automargin=True),
        height=max(420, 32 * top_n),
        width=1150,
        plot_bgcolor="#fafafa",
        margin=dict(t=80, b=60, l=40, r=60),
    )
    fig.show()
    _render_static(fig)


# =============================================================================
# Role archetypes — 2D scatter
# =============================================================================
QUAD_LABELS = {
    ("PROGRESSION", "DANGEROUSNESS"): {
        "CB":   {"TR": "Total ball-playing CB",   "TL": "xT specialist",          "BR": "Pure volume",                 "BL": "Stopper"},
        "FB":   {"TR": "Total FB",                "TL": "Creative FB",            "BR": "Volume FB",                   "BL": "Complement"},
        "MID":  {"TR": "Total midfielder",        "TL": "xT regista",             "BR": "Volume midfielder",           "BL": "Second pivot"},
        "CAM":  {"TR": "Total #10",               "TL": "Pure playmaker",         "BR": "Volume finisher",             "BL": "Shadow striker"},
        "WIDE": {"TR": "Total winger",            "TL": "xT winger",              "BR": "Workhorse winger",            "BL": "Complement winger"},
        "FW":   {"TR": "Total #9",                "TL": "Refined finisher",       "BR": "Build-up #9",                 "BL": "Target man"},
    },
    ("PROGRESSION", "GRAVITY"): {
        "CB":   {"TR": "Modern libero",           "TL": "High-gravity CB",        "BR": "Deep-lying playmaker",        "BL": "Stopper"},
        "FB":   {"TR": "Total FB",                "TL": "Presence FB",            "BR": "Playmaking FB",               "BL": "Complement"},
        "MID":  {"TR": "Box-to-box",              "TL": "Holding magnet",         "BR": "Deep-lying playmaker",        "BL": "Second pivot"},
        "CAM":  {"TR": "Complete #10",            "TL": "Box fantasista",         "BR": "Advanced playmaker",          "BL": "Complement"},
        "WIDE": {"TR": "Total winger",            "TL": "Pulling forward winger", "BR": "Build-up winger",             "BL": "Complement winger"},
        "FW":   {"TR": "Modern center-forward",   "TL": "Box finisher",           "BR": "False 9 / playmaking #9",     "BL": "Target man"},
    },
    ("RECEPTION", "DANGEROUSNESS"): {
        "MID":  {"TR": "Between-lines #10",       "TL": "Episodic creator",       "BR": "Pure receiver",               "BL": "Plain distributor"},
        "CAM":  {"TR": "Total #10",               "TL": "Wide fantasista",        "BR": "Lay-off shadow striker",      "BL": "Complement"},
    },
}


def role_archetypes(role: str, x_theme: str = "PROGRESSION", y_theme: str = "DANGEROUSNESS",
                    df: pd.DataFrame = None, pct: pd.DataFrame = None,
                    min_minutes: int = config.ANALYSIS_MIN_MINUTES,
                    label_top_n: int = 6):
    if role not in _ROLE_COLOR:
        print(f"[ERR] Invalid role '{role}'."); return
    if x_theme not in RADAR_SPECS or y_theme not in RADAR_SPECS:
        print(f"[ERR] Invalid theme. Use: {list(RADAR_SPECS)}"); return
    if x_theme == y_theme:
        print(f"[ERR] x_theme and y_theme must differ"); return

    sub = pct[(pct["macro_role"] == role)
              & (pct["minutes_played"] >= min_minutes)].copy()
    if sub.empty:
        print(f"[ERR] No {role} player with min >= {min_minutes}"); return

    labmap = QUAD_LABELS.get((x_theme, y_theme), {}).get(role)
    if labmap is None:
        labmap = {"TR": f"High {x_theme[:4]}+High {y_theme[:4]}",
                  "TL": f"Low {x_theme[:4]}+High {y_theme[:4]}",
                  "BR": f"High {x_theme[:4]}+Low {y_theme[:4]}",
                  "BL": f"Low {x_theme[:4]}+Low {y_theme[:4]}"}

    x_col, y_col = f"{x_theme}_idx", f"{y_theme}_idx"

    hover_txt = (
        sub["player"] + "<br>" + sub["team"] + " · " + sub["primary_role"]
        + "<br>Min: "          + sub["minutes_played"].astype(int).astype(str)
        + "<br>" + x_theme[:4] + " " + sub[x_col].round(0).astype(int).astype(str)
        + " · "  + y_theme[:4] + " " + sub[y_col].round(0).astype(int).astype(str)
    )

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=sub[x_col], y=sub[y_col],
        mode="markers",
        marker=dict(
            size=np.clip(sub["minutes_played"] / 8, 8, 44),
            color=_ROLE_COLOR[role],
            line=dict(color="#222", width=0.8),
            opacity=0.75,
        ),
        text=hover_txt,
        hovertemplate="<b>%{text}</b><extra></extra>",
        showlegend=False,
    ))

    sub = sub.copy()
    sub["_sum"] = sub[x_col] + sub[y_col]
    tops = pd.concat([
        sub.nlargest(max(label_top_n, 3), "_sum"),
        sub.nlargest(3, x_col),
        sub.nlargest(3, y_col),
    ]).drop_duplicates()
    fig.add_trace(go.Scatter(
        x=tops[x_col], y=tops[y_col],
        mode="text",
        text=tops["player"].apply(lambda s: s.split()[-1]),
        textposition="top center",
        textfont=dict(size=10, color="#111"),
        showlegend=False, hoverinfo="skip",
    ))

    fig.add_vline(x=50, line_dash="dash", line_color="#bbb", line_width=1)
    fig.add_hline(y=50, line_dash="dash", line_color="#bbb", line_width=1)
    fig.add_annotation(x=98, y=97, text=f"<b>{labmap['TR']}</b>", showarrow=False,
                       font=dict(size=11, color="#555"), xanchor="right")
    fig.add_annotation(x=2,  y=97, text=f"<b>{labmap['TL']}</b>", showarrow=False,
                       font=dict(size=11, color="#555"), xanchor="left")
    fig.add_annotation(x=98, y=3,  text=f"<b>{labmap['BR']}</b>", showarrow=False,
                       font=dict(size=11, color="#555"), xanchor="right")
    fig.add_annotation(x=2,  y=3,  text=f"<b>{labmap['BL']}</b>", showarrow=False,
                       font=dict(size=11, color="#555"), xanchor="left")

    fig.update_layout(
        title=(f"<b>Archetypes within role {role}:  {x_theme} × {y_theme}</b>  "
               f"<span style='font-size:12px;color:#888'>"
               f"(n={len(sub)}, min {min_minutes} min; size = minutes)</span>"),
        xaxis=dict(title=f"{x_theme} index (percentile within role)",
                   range=[-2, 102], gridcolor="#eee", zeroline=False),
        yaxis=dict(title=f"{y_theme} index (percentile within role)",
                   range=[-2, 102], gridcolor="#eee", zeroline=False),
        height=720, width=1050,
        plot_bgcolor="white",
        margin=dict(t=80, b=60, l=70, r=40),
    )
    fig.show()
    _render_static(fig)
