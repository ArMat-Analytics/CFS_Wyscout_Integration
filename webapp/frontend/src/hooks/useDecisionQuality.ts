import { useState, useEffect } from 'react';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

// ── Types ─────────────────────────────────────────────────────────────────────

export interface DecisionQualityRow {
  player: string;
  team: string;
  primary_role: string;
  macro_role: string;
  minutes_played: number;
  n_decisions: number;

  // Headline + companion
  DQ_index: number;
  value_impact: number;

  // Radar axes — percentile within-role 0–100, already mirrored where needed
  pct__accuracy: number;
  pct__worst_choice: number;
  pct__elite_per90: number;
  pct__poor_per90: number;

  // Core stats — Raw
  score: number;
  avg_miss_cost: number;

  // Core stats — Per 90
  elite_per90: number;
  poor_per90: number;

  // Core stats — Percentages
  accuracy_pct: number;
  worst_choice_pct: number;

  // Optional (similarity comparison)
  similarity_score?: number | null;
}

// ── Hook: single player ───────────────────────────────────────────────────────

export function usePlayerDecisionQuality(playerId: string | undefined) {
  const [data, setData] = useState<DecisionQualityRow | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!playerId) { setLoading(false); return; }
    setLoading(true);
    setError(false);
    fetch(`${API_BASE_URL}/players/${playerId}/decision-quality`)
      .then(r => { if (!r.ok) throw new Error(r.statusText); return r.json(); })
      .then((d: DecisionQualityRow) => { setData(d); setLoading(false); })
      .catch(() => { setError(true); setLoading(false); });
  }, [playerId]);

  return { data, loading, error };
}

// ── Hook: similar players (DQ) ────────────────────────────────────────────────

export function useSimilarDQ(
  macroRole: string | undefined,
  excludePlayer: string | undefined,
) {
  const [players, setPlayers] = useState<DecisionQualityRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!macroRole) { setLoading(false); setError('no_macro_role'); return; }
    setLoading(true);
    setError(null);
    const params = new URLSearchParams({ macro_role: macroRole });
    if (excludePlayer) params.set('exclude_player', excludePlayer);
    fetch(`${API_BASE_URL}/decision-quality/similar?${params}`)
      .then(r => { if (!r.ok) throw new Error(r.statusText); return r.json(); })
      .then((d: DecisionQualityRow[]) => {
        setPlayers(Array.isArray(d) ? d : []);
        setLoading(false);
      })
      .catch((err: Error) => {
        setError(err.message ?? 'fetch_error');
        setLoading(false);
      });
  }, [macroRole, excludePlayer]);

  return { players, loading, error };
}
