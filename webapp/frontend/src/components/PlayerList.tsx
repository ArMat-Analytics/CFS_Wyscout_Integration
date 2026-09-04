import { useEffect, useState, useId } from 'react';
import { Link } from 'react-router-dom';
import type { FilterState } from './Filters';
import { getFlagUrl } from '../utils';
import { useDebounce } from '../hooks/useDebounce';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

interface Player {
  player_id: number;
  player_name: string;
  primary_role?: string;
  market_value_before_euros?: string;
  market_value_after_euros?: string;
  val_pre_num?: number;
  val_post_num?: number;
  age?: number;
  source_team_name?: string;
  preferred_foot?: string;
}

interface PlayerListProps {
  searchTerm: string;
  selectedTeams: string[];
  filters: FilterState;
}

type SortCol =
  | 'player_name' | 'primary_role' | 'age'
  | 'source_team_name' | 'preferred_foot'
  | 'market_value_before_euros' | 'market_value_after_euros' | 'val_diff';

const COLS: { key: SortCol; label: string; align?: string }[] = [
  { key: 'player_name',               label: 'Player' },
  { key: 'primary_role',              label: 'Role' },
  { key: 'age',                       label: 'Age',         align: 'center' },
  { key: 'source_team_name',          label: 'Nation',      align: 'center' },
  { key: 'preferred_foot',            label: 'Foot',        align: 'center' },
  { key: 'market_value_before_euros', label: 'Pre €',       align: 'right'  },
  { key: 'market_value_after_euros',  label: 'Post €',      align: 'right'  },
  { key: 'val_diff',                  label: 'Δ Value',     align: 'right'  },
];

const SKELETON_ROWS = 12;
const RETIRED_PLAYERS = new Set(['toni kroos', 'pepe']);

function isRetiredPlayer(name?: string) {
  return RETIRED_PLAYERS.has((name || '').trim().toLowerCase());
}

function SkeletonRow() {
  return (
    <tr aria-hidden="true">
      {COLS.map((c) => (
        <td key={c.key} className="px-4 py-3">
          <div className="skeleton h-4 rounded" style={{ width: c.key === 'player_name' ? '140px' : '64px' }} />
        </td>
      ))}
    </tr>
  );
}

function SortIcon({ active, dir }: { active: boolean; dir: 'asc' | 'desc' }) {
  if (!active) return <svg className="w-3 h-3 inline ml-1 opacity-30" aria-hidden viewBox="0 0 12 12" fill="currentColor"><path d="M6 2l3 4H3zM6 10L3 6h6z"/></svg>;
  return dir === 'asc'
    ? <svg className="w-3 h-3 inline ml-1 text-[var(--accent)]" aria-hidden viewBox="0 0 12 12" fill="currentColor"><path d="M6 2l3 4H3z"/></svg>
    : <svg className="w-3 h-3 inline ml-1 text-[var(--accent)]" aria-hidden viewBox="0 0 12 12" fill="currentColor"><path d="M6 10L3 6h6z"/></svg>;
}

function FootBadge({ foot }: { foot?: string }) {
  if (!foot) return <span className="text-[var(--text-dim)]">—</span>;
  const map: Record<string, string> = { right: 'R', left: 'L', both: 'B' };
  const colors: Record<string, string> = { right: '#2563eb', left: '#d97706', both: '#16a34a' };
  return (
    <span className="inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-mono font-bold"
      style={{ background: `${colors[foot] ?? '#000'}11`, color: colors[foot] ?? 'var(--text)' }}>
      {map[foot] ?? foot[0].toUpperCase()}
    </span>
  );
}

function DeltaBadge({ pre, post }: { pre?: number; post?: number }) {
  if (pre == null || post == null || pre === 0) return <span className="text-[var(--text-dim)] font-mono text-[11px]">—</span>;
  const diff = post - pre;
  const pct  = ((diff / pre) * 100).toFixed(0);
  const abs  = Math.abs(diff);
  const fmt  = abs >= 1_000_000 ? `${(diff / 1_000_000).toFixed(1)}M` : abs >= 1000 ? `${(diff / 1000).toFixed(0)}K` : String(diff);
  const color = diff > 0 ? 'var(--win)' : diff < 0 ? 'var(--lose)' : 'var(--text-dim)';
  return (
    <span className="font-mono text-[11px] font-bold" style={{ color }}>
      {diff > 0 ? '+' : ''}{fmt}
      <span className="text-[9px] opacity-75 ml-[3px]">({diff > 0 ? '+' : ''}{pct}%)</span>
    </span>
  );
}

export default function PlayerList({ searchTerm, selectedTeams, filters }: PlayerListProps) {
  const [players, setPlayers] = useState<Player[]>([]);
  const [loading, setLoading] = useState(false);
  const [sortCol, setSortCol] = useState<SortCol>('player_name');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');
  const captionId = useId();
  const debouncedSearch = useDebounce(searchTerm, 300);

  useEffect(() => {
    setLoading(true);
    // val_diff sort is client-side only; send player_name to backend
    const backendSort = sortCol === 'val_diff' ? 'player_name' : sortCol;
    const params = new URLSearchParams({ search: debouncedSearch, sort_by: backendSort, sort_order: sortOrder });
    selectedTeams.forEach(t => params.append('teams', t));
    if (filters.ageMin)   params.append('age_min',     filters.ageMin);
    if (filters.ageMax)   params.append('age_max',     filters.ageMax);
    if (filters.macroRole) params.append('macro_role', filters.macroRole);
    if (filters.role)     params.append('role',        filters.role);
    if (filters.foot)     params.append('foot',        filters.foot);
    if (filters.vPreMin)  params.append('val_pre_min', filters.vPreMin);
    if (filters.vPreMax)  params.append('val_pre_max', filters.vPreMax);
    if (filters.vPostMin) params.append('val_post_min',filters.vPostMin);
    if (filters.vPostMax) params.append('val_post_max',filters.vPostMax);
    if (filters.vDiffMin) params.append('val_diff_min',filters.vDiffMin);
    if (filters.vDiffMax) params.append('val_diff_max',filters.vDiffMax);

    fetch(`${API_BASE_URL}/players/?${params}`)
      .then(r => r.json())
      .then(d => {
        let rows: Player[] = Array.isArray(d) ? d : [];
        rows = Array.from(new Map(rows.map((row) => [row.player_id, row])).values());
        // Client-side sort for Δ Value
        if (sortCol === 'val_diff') {
          rows = [...rows].sort((a, b) => {
            const da = (a.val_post_num ?? 0) - (a.val_pre_num ?? 0);
            const db2 = (b.val_post_num ?? 0) - (b.val_pre_num ?? 0);
            return sortOrder === 'asc' ? da - db2 : db2 - da;
          });
        }
        setPlayers(rows);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [debouncedSearch, sortCol, sortOrder, selectedTeams, filters]);

  const handleSort = (col: SortCol) => {
    if (sortCol === col) setSortOrder(o => o === 'asc' ? 'desc' : 'asc');
    else { setSortCol(col); setSortOrder('desc'); }
  };

  return (
    <section className="rounded-2xl overflow-hidden border border-[var(--border)] bg-[var(--surface)] shadow-[var(--shadow)]" aria-label="Player database">
      <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--border)]">
        <h2 className="font-display font-extrabold text-lg tracking-tight text-[var(--text)]">Player Database</h2>
        <span className="tag font-mono bg-[var(--accent-dim)] text-[var(--accent)]" aria-live="polite" aria-atomic="true">
          {loading ? '…' : `${players.length} players`}
        </span>
      </div>

      <div className="overflow-auto" style={{ maxHeight: '640px' }}>
        <table className="w-full border-collapse text-sm whitespace-nowrap" aria-labelledby={captionId} aria-busy={loading}>
          <caption id={captionId} className="sr-only">Sortable player statistics. {players.length} players shown.</caption>
          <thead className="sticky top-0 z-10 bg-[var(--surface)]">
            <tr className="border-b border-[var(--border)]">
              {COLS.map(col => (
                <th key={col.key} scope="col"
                  className={`px-4 py-3 font-mono text-[10px] tracking-widest uppercase cursor-pointer select-none transition-colors hover:bg-[var(--surface2)] ${col.align === 'center' ? 'text-center' : col.align === 'right' ? 'text-right' : 'text-left'} ${sortCol === col.key ? 'text-[var(--accent)]' : 'text-[var(--text-dim)]'}`}
                  onClick={() => handleSort(col.key)}
                  aria-sort={sortCol === col.key ? (sortOrder === 'asc' ? 'ascending' : 'descending') : 'none'}
                  tabIndex={0} onKeyDown={e => e.key === 'Enter' && handleSort(col.key)}
                >
                  {col.label}<SortIcon active={sortCol === col.key} dir={sortOrder} />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading
              ? Array.from({ length: SKELETON_ROWS }).map((_, i) => <SkeletonRow key={i} />)
              : players.map((player, idx) => {
                  const flagUrl = getFlagUrl(player.source_team_name);
                  const retired = isRetiredPlayer(player.player_name);
                  return (
                    <tr key={player.player_id}
                      className="border-b border-[var(--border)] transition-colors hover:bg-[var(--surface2)] fade-up"
                      style={{ animationDelay: `${Math.min(idx * 18, 300)}ms` }}
                    >
                      <td className="px-4 py-3 font-semibold text-[var(--text)]">
                        {player.player_id
                          ? <Link to={`/player/${player.player_id}`} className="hover:text-[var(--accent)] transition-colors focus-visible:outline-none focus-visible:underline">{player.player_name || '—'}</Link>
                          : player.player_name || '—'
                        }
                      </td>
                      <td className="px-4 py-3 capitalize text-xs text-[var(--text-muted)]">{player.primary_role?.replace(/_/g, ' ') || '—'}</td>
                      <td className="px-4 py-3 text-center font-mono text-[var(--text-muted)]">{player.age || '—'}</td>
                      <td className="px-4 py-3 text-center">
                        <span className="inline-flex items-center justify-center gap-2 font-semibold text-xs text-[var(--text)]">
                          {flagUrl
                            ? <img src={flagUrl} alt="" className="w-5 h-3.5 object-cover rounded-sm shadow-sm" aria-hidden />
                            : <span className="font-mono text-[10px] bg-[var(--surface2)] px-1.5 py-0.5 rounded text-[var(--text-muted)]" aria-hidden>{player.source_team_name?.substring(0,3).toUpperCase()}</span>
                          }
                          <span>{player.source_team_name || '—'}</span>
                        </span>
                      </td>
                      <td className="px-4 py-3 text-center"><FootBadge foot={player.preferred_foot} /></td>
                      <td className="px-4 py-3 text-right font-mono text-xs text-[var(--text-muted)]">{player.market_value_before_euros || '—'}</td>
                      <td className="px-4 py-3 text-right font-mono text-xs font-bold text-[var(--accent)]">
                        {retired ? 'RETIRED' : (player.market_value_after_euros || '—')}
                      </td>
                      <td className="px-4 py-3 text-right">
                        {retired
                          ? <span className="text-[var(--text-dim)] font-mono text-[11px] font-bold">RETIRED</span>
                          : <DeltaBadge pre={player.val_pre_num} post={player.val_post_num} />
                        }
                      </td>
                    </tr>
                  );
                })
            }
          </tbody>
        </table>

        {!loading && players.length === 0 && (
          <div className="py-20 text-center text-[var(--text-dim)]">
            <p className="font-display font-bold text-xl mb-1">No players found</p>
            <p className="text-sm">Try adjusting your search or filters.</p>
          </div>
        )}
      </div>
    </section>
  );
}