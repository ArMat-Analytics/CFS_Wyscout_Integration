import { useState, useEffect } from 'react';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

// ── Types ─────────────────────────────────────────────────────────────────────

export interface SpaceControlIndex {
  player: string; team: string; primary_role: string; macro_role: string;
  minutes_played: number; coverage_pct: number;
  player_id?: number;
  idx__PROGRESSION: number; idx__DANGEROUSNESS: number;
  idx__RECEPTION: number; idx__GRAVITY: number;
  pct__lb_geom_per90: number; pct__lb_quality_per90: number;
  pct__lb_epv_per90: number; pct__successful_hull_penetrations_per90: number;
  pct__defenders_bypassed_mean: number; pct__epv_added_per90: number;
  pct__epv_penetration_per90: number; pct__epv_inside_circ_per90: number;
  pct__between_lines_pct: number; pct__successful_hull_exits_per90: number;
  pct__pressure_resistance_pct: number; pct__gravity_proximity_pct: number;
  pct__gravity_hull_pct: number; pct__gravity_abs_m: number;
  similarity_score?: number | null;
  age?: number | null;
  market_value_before_euros?: string | null;
  market_value_after_euros?: string | null;
  preferred_foot?: string | null;
}

export interface SpaceControlAggregated {
  player: string; team: string; primary_role: string; macro_role: string;
  minutes_played: number; passes_total: number; passes_op: number; passes_analysed: number;
  coverage_pct: number; lb_geom: number; lb_quality: number; lb_epv: number;
  hull_penetration_n: number; defenders_bypassed_mean: number;
  successful_hull_penetrations_n: number;
  lb_geom_per90: number; lb_quality_per90: number; lb_epv_per90: number;
  successful_hull_penetrations_per90: number;
  lb_geom_pct: number; lb_quality_pct: number; lb_epv_pct: number; hull_penetration_pct: number;
  penetration_completion_pct: number;
  epv_added_sum: number; epv_added_mean: number; epv_penetration_sum: number;
  epv_penetration_mean: number; epv_inside_circ_sum: number; epv_inside_circ_mean: number;
  epv_exit_sum: number; epv_outside_circ_sum: number; epv_exit_mean: number; epv_outside_circ_mean: number;
  penetration_n: number; inside_circ_n: number;
  epv_added_per90: number; epv_penetration_per90: number; epv_inside_circ_per90: number;
  epv_exit_per90: number; epv_outside_circ_per90: number;
  penetration_per90: number; inside_circ_per90: number; exit_per90: number; outside_circ_per90: number;
  between_lines_n: number; hull_exit_n: number; pressure_resistance_n: number;
  between_lines_per90: number; successful_hull_exits_per90: number;
  between_lines_pct: number; hull_exit_pct: number; pressure_resistance_pct: number;
  gravity_n: number; gravity_directional_n: number; gravity_directional_m: number;
  gravity_proximity_pct: number; gravity_hull_pct: number; gravity_composite_pct: number;
}

export interface SpaceControlPayload {
  indices: SpaceControlIndex | null;
  aggregated: SpaceControlAggregated | null;
}

// ── Hook: single player ───────────────────────────────────────────────────────

export function usePlayerSpaceControl(playerId: string | undefined) {
  const [data, setData] = useState<SpaceControlPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!playerId) { setLoading(false); return; }
    setLoading(true);
    setError(false);
    fetch(`${API_BASE_URL}/players/${playerId}/space-control`)
      .then(r => { if (!r.ok) throw new Error(r.statusText); return r.json(); })
      .then((d: SpaceControlPayload) => { setData(d); setLoading(false); })
      .catch(() => { setError(true); setLoading(false); });
  }, [playerId]);

  return { data, loading, error };
}

// ── Hook: similar players ─────────────────────────────────────────────────────

export function useSimilarPlayers(
  macroRole: string | undefined,
  excludePlayer: string | undefined,
) {
  const [players, setPlayers] = useState<SpaceControlIndex[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!macroRole) {
      setLoading(false);
      setError('no_macro_role');
      return;
    }

    setLoading(true);
    setError(null);

    const params = new URLSearchParams({ macro_role: macroRole });
    if (excludePlayer) params.set('exclude_player', excludePlayer);

    const controller = new AbortController();

    let timedOut = false;
    const timeout = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, 15_000);

    fetch(`${API_BASE_URL}/space-control/similar?${params}`, { signal: controller.signal })
      .then(r => {
        if (!r.ok) {
          return r.json().then((body: any) => {
            throw new Error(body?.hint ?? `HTTP ${r.status}: ${body?.error ?? r.statusText}`);
          });
        }
        return r.json();
      })
      .then((d: SpaceControlIndex[]) => {
        clearTimeout(timeout);
        setPlayers(Array.isArray(d) ? d : []);
        setLoading(false);
      })
      .catch((err: Error) => {
        clearTimeout(timeout);
        if (err.name === 'AbortError') {
          if (timedOut) {
            setError('timeout');
            setLoading(false);
          }
          return;
        }
        setError(err.message ?? 'fetch_error');
        setLoading(false);
      });

    return () => {
      clearTimeout(timeout);
      controller.abort();
    };
  }, [macroRole, excludePlayer]);

  return { players, loading, error };
}