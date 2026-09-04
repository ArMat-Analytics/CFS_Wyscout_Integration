import { useState, useEffect } from 'react';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

// ── Types ─────────────────────────────────────────────────────────────────────

export interface OffBallRow {
  player: string;
  team: string;
  primary_role: string;
  macro_role: string;
  minutes_played: number;

  // Headline
  urs_pct_within_role: number;

  // Radar axes (percentiles)
  potential_pct_within_role: number;
  xepv_mean_pct_within_role: number;
  latency_pct_within_role: number;

  // Raw stats
  urs_per90: number;
  off_ball_potential_per90: number;
  capitalization_rate: number;
  xepv_mean: number;
  
  // Extra metrics
  urs_sum: number;
  off_ball_potential_sum: number;
  off_ball_captured_sum: number;
  n_confident_candidates: number;
  n_received: number;
  receiver_conf_rate: number;
  n_confident_per90: number;
  latency_rate: number;
}

// ── Hook: single player ───────────────────────────────────────────────────────

export function usePlayerOffBallMovement(playerId: string | undefined) {
  const [data, setData] = useState<OffBallRow | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!playerId) { setLoading(false); return; }
    setLoading(true);
    setError(false);
    fetch(`${API_BASE_URL}/players/${playerId}/off-ball`)
      .then(r => { if (!r.ok) throw new Error(r.statusText); return r.json(); })
      .then((d: OffBallRow) => { setData(d); setLoading(false); })
      .catch(() => { setError(true); setLoading(false); });
  }, [playerId]);

  return { data, loading, error };
}
