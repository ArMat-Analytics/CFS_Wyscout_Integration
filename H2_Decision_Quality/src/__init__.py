"""Contextual Decision Quality (H2) — Euro 2024.

Currently focused on the xPass model: P(complete | features) for any
(sender, target, freeze frame) candidate. Three model families share the
same CV / OOF / diagnostics pipeline so they can be compared head-to-head:
L2 logistic, class-balanced logistic, and gradient-boosted trees. The
production model is the calibrated GBM (sigmoid + clip [0.05, 0.99]).

Modules:
    config   — paths and thresholds (re-exports H1 constants)
    corpus   — assemble the H2 working corpus from H1's hull_events_lb.csv
    features — 12 logical features per candidate pass (curated, audited)
    xpass    — multi-model training, calibration, comparison, plots
    xepv     — bilinear EPV lookup + xEPV per candidate pass
    viz      — pitch plotting helpers for example passes
"""
