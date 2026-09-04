# H1 — Space Control and Value

Part of **[Contextual Football Scouting](../README.md)** (Vezzoli & Mio, 2026). For the full framing of the four hypotheses see [`docs/Project_Proposal.pdf`](../docs/Project_Proposal.pdf).

Implementation of **Hypothesis 1**: a player's quality is measurable through their spatial influence on the pitch, not their volume. We measure influence on three layers. The **shape** of the opposing block (convex hulls of the visible defenders), the **threat** added with each ball progression (Expected Possession Value), and the **pull** a player exerts on the defenders around them (gravity).

Built on **StatsBomb 360 open data** for UEFA Euro 2024 (`competition_id=55`, `season_id=282`, 51 matches, 272 players after the minutes filter).

## The four indices

Three of the four (PROGRESSION, RECEPTION, GRAVITY) are **stylistic composites**: their headline is the mean of within-role percentile ranks of their mother variables. The fourth (DANGEROUSNESS) is a **magnitude**: a single within-role percentile of `EPV Added /90`, with the four EPV by-geom_type components used only for the radar profile. The distinction matters because EPV creation is by construction additive (the four components *sum* to `EPV Added /90`), while progression style, reception style and gravity style are not.

Within-role percentiles are the heart of the approach in every case: a centre-back ranked 90th on PROGRESSION is among the best 10% of *centre-backs* at progressing the ball, not the best 10% of the whole tournament.

Quick glossary: **convex hull** = polygon enclosing the visible opponents in the 360 frame; **line-breaker** = successful pass that bypasses ≥ 3 opponents inside a 5 m corridor along the pass line; **EPV** = probability of scoring in the next actions given the ball location.

### PROGRESSION, the volume of forward play

How often, and how cleanly, a player moves the ball through opponent lines. Mother variables (5):

`LB Geom /90` + `LB Quality /90` + `LB EPV /90` + `Hull Penetr. /90` + `Def. Bypassed Avg`

The first three count line-breakers under three lenses (geometric corridor, EPV threshold, the intersection of the two). `Hull Penetr. /90` is the volume of successful passes that *enter* the opposing block. `Def. Bypassed Avg` is the mean number of opponents removed from play per progressive pass. A player can score high here in two ways: by being a high-volume metronome (Kroos, Modrić) or by being a vertical specialist on lower volume (Alexander-Arnold).

### DANGEROUSNESS, the magnitude of EPV creation

The total expected possession value a player generates per 90 minutes. Unlike the other three, DANGEROUSNESS is **not** a stylistic composite. The headline is the **within-role percentile of `EPV Added /90`** alone, a direct magnitude. The radar that decomposes it shows the **four additive EPV by-geom_type per-90 components** (they sum to `EPV Added /90`, by construction):

`EPV Penetr. /90` + `EPV In-Circ /90` + `EPV Exit /90` + `EPV Out-Circ /90`

`EPV Penetr. /90` is the value added on passes that *enter* the opposing block. `EPV In-Circ /90` is the value circulated *inside* the block. `EPV Exit /90` is the value of clean ball-exits from inside the block back out. `EPV Out-Circ /90` is the value circulated outside the block. Reading the four together explains *where* a player's EPV comes from: a centre-back will produce value mostly through `Out-Circ` and `Penetr.`, a between-the-lines CAM mostly through `In-Circ` and `Exit`, a winger drifting inside through `Penetr.` and `In-Circ`. The single magnitude (`EPV Added /90`) keeps the headline honest, the four sub-components keep the profile interpretable.

### RECEPTION, between-the-lines play and tight-space technique

How often the player receives the ball *inside* the opposing block, and how often they survive when pressed. Mother variables (3):

`Between Lines %` + `Hull Exits /90` + `Press. Resist %`

`Between Lines %` is the share of touches taken inside the opponent convex hull. `Hull Exits /90` is the per-90 volume of clean ball-exits from inside the block. `Press. Resist %` is the completion rate when ≥ 2 opponents are within 2.5 m at the moment of release. This index is where Pedri, Wirtz and a cluster of ball-playing CBs (Calafiori, Matvienko, Krejčí) show up, because the signal is about *where you stand*, not how many touches you take.

### GRAVITY, the spatial pull on the defense

How much the opposing defenders move *because of you*. Mother variables (3):

`Space Attraction %` + `Gravity Hull %` + `Def. Pull |m|`

The first two summarise how often defenders sit in the player's neighbourhood relative to a leave-one-out baseline (the same `(match, zone)` baseline computed *without* that player's events). `Def. Pull |m|` is the absolute displacement, in meters, of the opposing defensive centroid toward the player. Gravity is the only index where Cronbach's α is negative, on purpose: a forward who pulls the centre-back wide and a winger who pins both full-backs inside are doing two *different* things, both legitimately "gravitational". The composite measures the union, not a single coherent skill.

## Pipeline

```
StatsBomb events + 360 frames
        │
        ▼
  Player totals          ──►  Euro2024_Player_Totals_Distances_Roles.xlsx
        │
        ▼
  Hull Metrics           ──►  hull_events_raw.csv
                              hull_zone_baselines.csv
                              hull_metrics_aggregated.csv
        │
        ▼
  Directional Gravity         (extends hull_metrics_aggregated.csv)
        │
        ▼
  EPV Pipeline           ──►  hull_events_with_epv.csv  (open play only)
        │
        ▼
  Line Breaker           ──►  hull_events_lb.csv
        │
        ▼
  Player Aggregation     ──►  player_space_control_aggregated.csv
        │
        ▼
  Indices + Dashboard    ──►  player_space_control_indices.csv
        │                     (single radar + head-to-head radar + leaderboard + archetype scatter)
        ▼
  Validation                  Cronbach's α + H1 evidence + scouting discoveries
```

## Website graphic: the family radar

The single-player card renders **four small radars side by side**, one per index. PROGRESSION, RECEPTION and GRAVITY each show the within-role percentiles of their mother variables (5, 3 and 3 axes respectively). DANGEROUSNESS shows its four additive EPV by-geom_type components (Penetr., In-Circ, Exit, Out-Circ): the polygon's area scales with the magnitude headline, the four directions tell you *where* the EPV is coming from. All axes are oriented so outside is better.

The two-player comparison page overlays two polygons per radar (same macro-role only, the picker prevents cross-role duels upstream). Reading the shapes is direct. A balanced PROGRESSION polygon is a balanced progressor (Kroos on MIDs). A DANGEROUSNESS polygon stretched on Penetr. + In-Circ with a thin Out-Circ is a final-third finisher; a polygon stretched on Out-Circ with thin Penetr. is a deep distributor whose EPV comes from build-up volume, not penetration. A RECEPTION spike with low PROGRESSION is a between-the-lines receiver who does not progress the ball himself (a classic 10 in a possession side).

## Key findings

A scout-first read of the Euro 2024 leaderboards on the four indices, with the minutes floor at 135' (≈ 1.5 matches). The interesting names show up not at the very top of "volume" stats but inside their own role pool, where the within-role percentile lives.

### PROGRESSION

- **Trent Alexander-Arnold** (England, MID, n=135') tops the index at 95th, on the smallest sample of the leaders. He played a hybrid inverted role at Euro 2024 and the metric reads exactly that: high LB EPV volume and high `Def. Bypassed Avg`, even on short minutes.
- **Toni Kroos** (Germany, MID) at 93rd on 485 minutes is the metronome answer. Highest sample of any midfield leader on this index.
- **Luka Modrić** (Croatia, MID) at 94th and **Mateo Kovačić** (Croatia, MID) at 92nd, both at the top of the role pool, the Croatian double pivot reads as a progression duo where the naive view tends to credit only Modrić.
- **Alessandro Bastoni** (Italy, CB) and **Joachim Andersen** (Denmark, CB) at 94th and 92nd among CBs, two ball-playing centre-backs whose `LB EPV /90` is comparable to that of central midfielders.
- **Bruno Fernandes** (Portugal, MID, n=379) at 90th, top of the MID pool on the line-breaking volume axes (`LB Geom /90` and `LB Quality /90` both above the 98th percentile). The index sits at 90th and not higher only because `Hull Penetr. /90` is more modest for him: he breaks lines often, but a smaller share of those passes actually land *inside* the opposing block.

### DANGEROUSNESS

This is the index where the contextual approach moves the leaderboard *most*. The headline is the within-role percentile of EPV Added /90, the naive proxy is `passes /90`. The two disagree by more than 20 percentile points on **54%** of the pool, the largest disagreement of all four indices. The reading is direct: ball volume is a very poor predictor of *value created*.

- **Arda Güler** (Turkey, FW, n=369), **Bruno Fernandes** (Portugal, MID, n=379), **Antonio Rüdiger** (Germany, CB, n=488) and **Joachim Andersen** (Denmark, CB) all sit at 98–100 inside their role. Rüdiger and Andersen sitting at the top of the CB pool on EPV /90 *and* in the top tier on raw passing volume is the kind of read the naive view *partially* surfaces, but the radar profile (Out-Circ at 100, Penetr. at 84) clarifies that they are not just high-volume distributors, they are also actively penetrating from the back.
- **Tomáš Souček** (Czech Rep, MID, +80 Δ), **Heorhii Tsitaishvili** (Ukraine, FB, +75 Δ) and **Ivan Perišić** (Croatia, FB, +74 Δ) are role-level discoveries with the largest naive-to-contextual shifts in the pool. Souček in particular is the headline of this group: 3rd percentile by `passes /90` among MIDs, 83rd by EPV /90. A player whose passing volume is genuinely low but whose every involvement moves the value needle (his radar peaks on Exit at 100, In-Circ at 72: the box-arriving CDM who breaks out of pressed phases).
- A counter-intuitive read here is **Phil Foden** (England, WIDE), 11th percentile on DANGEROUSNESS (bottom of the WIDE role pool). Foden is the cleanest single illustration of the volume-versus-value gap in the whole index: he sits at the 89th percentile of WIDE players on `passes /90`, but at the 11th on `EPV Added /90`. He is heavily involved in possession, his involvement just adds little expected value in the Euro 2024 sample.

The radar (the four EPV by-geom_type sub-components) reads as a profile under the headline. Rüdiger's EPV is concentrated on Out-Circ and Penetr. (the centre-back fingerprint, value built in the build-up *and* into the block). Güler peaks on Penetr. and Out-Circ at the same time (the receiver-finisher who also gets EPV from his deep starts when drifting back to receive).

### RECEPTION

- **Pedri** (Spain, CAM, n=185') at 98th. The clearest "between-the-lines" CAM of the tournament, with the highest `Between Lines %` of any CAM and very strong `Press. Resist %`.
- **Florian Wirtz** (Germany, WIDE) at 90th, the highest of the WIDE pool. Wide attackers normally score low here because they receive on the touchline, Wirtz is the exception because he comes inside.
- **Riccardo Calafiori** (Italy, CB), **Mykola Matvienko** (Ukraine, CB), **Ladislav Krejčí** (Czech Rep, CB), **Willi Orban** (Hungary, CB), **Nacho Fernández** (Spain, CB), a cluster of ball-playing centre-backs at 88–93 inside the CB pool. CBs typically take very few touches inside the opposing block in raw terms (the role median `Between Lines %` is about 4%, against 52% for CAMs), so the within-role pool surfaces the *ball-playing* CBs cleanly: a CB at 90th here is genuinely the kind who steps into the half-space to receive, not just the median back-line passer.
- **Breel Embolo** (Switzerland, FW) at 89th, a centre-forward whose between-the-lines reception rate beats most CAMs. Reads as the modern "drop nine" profile.

### GRAVITY

GRAVITY does not depend on how much a player touches the ball, it depends on how the opposing defenders react to them. Because of that the top is dominated by players from smaller national teams: a side built around one attacking reference produces a clear gravitational signal on that player.

- **Jan Mlakar** (Slovenia, WIDE) at 95th, the leader of the index. He sits at the 100th percentile of WIDE players on the proximity component: when Mlakar is on the ball the nearest defenders close in more tightly than the leave-one-out baseline expects, and the defensive centroid shifts toward him.
- **Giorgi Kochorashvili** (Georgia, MID) at 93rd, **Lukáš Provod** (Czech Rep, MID) at 92nd, **Salih Özcan** (Turkey, MID) at 92nd. Three midfielders from sides that funnel possession through one central player, so the defending team sets up to mark that player and the gravity signal picks it up.
- **David Strelec** (Slovakia, FW) at 92nd, the only FW in the top of the index. He has the largest directional pull of this group: the opposing defensive centroid shifts about 12 m toward him on average, the highest signed displacement of the six players here.
- **Kenan Yildiz** (Turkey, WIDE) at 84th, a more recognisable name in this group.

A separate finding sits in the famous-names column. **Joshua Kimmich** (Germany, FB) at 83rd PROGRESSION, 96th DANGEROUSNESS, 72nd RECEPTION, 57th GRAVITY. A profile that confirms the public reading on the offensive side but suggests his gravitational pull is mid-pool inside the FB role.

### Contextual vs naive, the headline H1 test

**Internal validity (Cronbach's α, averaged over the 6 roles)**

| Index | Mean α | Reading |
|---|---:|---|
| PROGRESSION | **0.77** | tight construct, the 5 variables measure the same dimension |
| DANGEROUSNESS | **0.32** | diagnostic only, the four radar axes are *additive* EPV components of `EPV Added /90`, not a reflective composite. The headline is a single percentile, α is reported just to read the sub-profile |
| RECEPTION | **0.41** | composite, high on CB and CAM, low on FW (small sample) |
| GRAVITY | **−0.03** | **multi-directional** construct, the three variables capture different phenomena (expected, not a flaw) |

The four composites are **weakly correlated with each other** (|r| ≤ 0.56 across the full pool, target < 0.6), so no redundancy.

**Core H1 test: contextual vs naive (within-role, n = 272)**

| Index | Naive proxy | Spearman ρ | mean \|Δ\| | % \|Δ\| > 20 |
|---|---|---:|---:|---:|
| PROGRESSION | passes /90 | 0.47 | 21.7 | 47% |
| DANGEROUSNESS | passes /90 | **0.28** | **27.8** | **54%** |
| RECEPTION | between-lines % | 0.75 | 14.9 | 29% |
| GRAVITY | gravity proximity % | 0.60 | 18.5 | 39% |

Reading: **DANGEROUSNESS** is where the gap hits hardest. More than one player in two shifts by more than 20 percentile points moving from the naive ranking (ball volume) to the contextual one (EPV magnitude). The DANGEROUSNESS proxy is `passes /90` and not `EPV /90` by design: the index headline is itself the within-role percentile of `EPV /90`, so comparing it to `EPV /90` would be tautological. The honest naive baseline is "do the high-EPV players just play more passes?", and the answer here is a clear no.

A second illustration of the same gap, on PROGRESSION. For MIDs, the naive top-15 by `passes /90` and the contextual top-15 by PROGRESSION overlap on only 10/15: **five new names** enter (Trent Alexander-Arnold, Mateo Kovačić, Robert Andrich, Fabián Ruiz, Youri Tielemans) and as many drop out (Brozović, Hjulmand, Cristante, Veerman, Rodri).

A note on the naive proxies. PROGRESSION and DANGEROUSNESS are tested against pure volume (`passes /90`), an external stat that is *not* part of the index. RECEPTION and GRAVITY are tested against one of their own raw mother variables (`between-lines %` and `gravity proximity %`): here the question is not "volume vs context" but "does the single most intuitive component reproduce the full index, or do the other components re-order it?". For GRAVITY the answer is partial, ρ = 0.60, the proximity signal alone agrees with the full index on the broad strokes but the hull and directional-pull components still move 39% of the pool by more than 20 percentile points.

### Players the contextual view finds

![Scouting discoveries](docs/figures/scouting_discoveries.png)

The chart shows, per index, the players whose contextual percentile is dramatically higher than their naive percentile. Read it role by role, not across the whole pitch.

### Players the naive view overrates

![Naive overrating](docs/figures/naive_overrating.png)

The mirror chart. Players whose naive ranking sits well above their contextual one, one panel per index. On PROGRESSION and DANGEROUSNESS these are typically high-volume passers whose ball circulation inflates the naive view without matching line-breaking or EPV output. Read it role by role, not across the whole pitch.

## Folder structure

```
H1_Space_Control_and_Value/
├── README.md
├── requirements.txt
├── .gitignore
│
├── notebooks/
│   └── H1-Space_Control_and_Value.ipynb       # thin notebook: imports from src/ and shows results
│
├── docs/figures/                               # images used by this README
│
├── data/                                       # pipeline inputs and outputs
│   ├── EPV_grid.csv                            # input: EPV grid (Friends-of-Tracking-Data)
│   ├── Euro2024_Player_Totals_Distances_Roles.{csv,xlsx}
│   ├── hull_events_*.csv                       # intermediates (gitignored)
│   ├── hull_metrics_aggregated.csv
│   ├── hull_zone_baselines.csv
│   ├── player_space_control_aggregated.csv
│   ├── player_space_control_indices.csv        # final output (4 indices + 16 percentiles)
│   └── cache/                                   # StatsBomb 360-frame cache (gitignored)
│
└── src/
    ├── config.py                # paths, thresholds, role maps
    ├── geometry.py              # geometric helpers (hull, distance, corridor)
    ├── player_totals.py         # → totals .xlsx
    ├── hull_metrics.py          # → hull_metrics_aggregated.csv
    ├── directional_gravity.py   # extends hull_metrics_aggregated.csv
    ├── epv_pipeline.py          # → hull_events_with_epv.csv
    ├── line_breaker.py          # → hull_events_lb.csv
    ├── aggregation.py           # → player_space_control_aggregated.csv
    ├── indices.py               # 4 composites + within-role percentiles
    ├── dashboard.py             # 4 prototype views (single radar / h2h radar / leaderboard / archetypes)
    └── validation.py            # Cronbach's α + H1 evidence + final export
```

## Quick start

```bash
git clone https://github.com/ArMat-Analytics/Contextual-Football-Scouting
cd Contextual-Football-Scouting/H1_Space_Control_and_Value
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

jupyter notebook notebooks/H1-Space_Control_and_Value.ipynb
```

The notebook runs the pipeline in order, one section per stage. To run a single stage from the CLI:

```bash
python -m src.player_totals
python -m src.hull_metrics
python -m src.directional_gravity
python -m src.epv_pipeline
python -m src.line_breaker
python -m src.aggregation
```

The aggregated CSVs (`hull_metrics_aggregated.csv`, `hull_zone_baselines.csv`, `player_space_control_aggregated.csv`, `player_space_control_indices.csv`) are committed for the *analysis-only* path: you can jump straight to the index design / validation / dashboard cells without re-running the heavy pipelines. The `hull_events_*.csv` event tables are gitignored and regenerable from the stages above.

## Conventions

- **Coordinates**: pitch in meters (105 × 68, UEFA standard). StatsBomb yard coordinates are converted via `X_SCALE = 105/120`, `Y_SCALE = 68/80`.
- **Open play**: the EPV step filters out corners, free kicks, throw-ins and kick-offs. Downstream rates use the open-play subset (`passes_op`).
- **Leave-one-out gravity**: each player's gravity is measured against a baseline that **excludes** their own passes.
- **Within-role percentiles**: every axis of every index is the player's percentile rank inside their macro-role (CB / FB / MID / CAM / WIDE / FW).
- **Min minutes**: the index pool is filtered at 135' (= 1.5 matches). Every table and leaderboard in this README is read on that 272-player pool.

---

*Matteo Vezzoli & Armando Mio — 2026*
