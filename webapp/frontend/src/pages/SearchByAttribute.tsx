import { useEffect, useId, useState } from 'react';
import { Link } from 'react-router-dom';
import { getFlagUrl } from '../utils';
import { useDebounce } from '../hooks/useDebounce';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

// ── Constants ─────────────────────────────────────────────────────────────────

const MACRO_ROLES = ['CB', 'FB', 'MID', 'CAM', 'WIDE', 'FW'] as const;

const PRIMARY_ROLES = [
  'Center Back', 'Left Center Back', 'Right Center Back',
  'Left Back', 'Right Back', 'Left Wing Back', 'Right Wing Back',
  'Center Defensive Midfield', 'Left Defensive Midfield', 'Right Defensive Midfield',
  'Left Center Midfield', 'Right Center Midfield', 'Left Midfield', 'Right Midfield',
  'Center Attacking Midfield', 'Left Attacking Midfield', 'Right Attacking Midfield',
  'Left Wing', 'Right Wing',
  'Center Forward', 'Left Center Forward', 'Right Center Forward',
] as const;

// macro_role → primary_roles that belong to it (for progressive filtering)
const ROLE_TO_MACRO: Record<string, string> = {
  'Center Back': 'CB', 'Left Center Back': 'CB', 'Right Center Back': 'CB',
  'Left Back': 'FB', 'Right Back': 'FB', 'Left Wing Back': 'FB', 'Right Wing Back': 'FB',
  'Center Defensive Midfield': 'MID', 'Left Defensive Midfield': 'MID', 'Right Defensive Midfield': 'MID',
  'Left Center Midfield': 'MID', 'Right Center Midfield': 'MID', 'Left Midfield': 'MID', 'Right Midfield': 'MID',
  'Center Attacking Midfield': 'CAM', 'Left Attacking Midfield': 'CAM', 'Right Attacking Midfield': 'CAM',
  'Left Wing': 'WIDE', 'Right Wing': 'WIDE',
  'Center Forward': 'FW', 'Left Center Forward': 'FW', 'Right Center Forward': 'FW',
};

const MACRO_COLOR: Record<string, string> = {
  CB: '#2563eb', FB: '#16a34a', MID: '#d97706',
  CAM: '#ea580c', WIDE: '#dc2626', FW: '#7c3aed',
};

const INDICES = [
  { key: 'idx__PROGRESSION',   label: 'Progression',      color: '#16a34a', short: 'PROG' },
  { key: 'idx__DANGEROUSNESS', label: 'Dangerousness',    color: '#dc2626', short: 'DNGR' },
  { key: 'idx__RECEPTION',     label: 'Reception',        color: '#2563eb', short: 'RECEP' },
  { key: 'idx__GRAVITY',       label: 'Gravity',          color: '#d97706', short: 'GRAV' },
  { key: 'DQ_index',           label: 'Decision Quality', color: '#7c3aed', short: 'DQ' },
  { key: 'urs_pct_within_role',label: 'Uncapitalized Run Score', color: '#db2777', short: 'URS' },
] as const;

const TABLE_ABBREVIATION_LABELS: Record<string, string> = {
  PROG: 'Progression',
  DNGR: 'Dangerousness',
  RECEP: 'Reception',
  GRAV: 'Gravity',
  DQ: 'Decision Quality',
  URS: 'Uncapitalized Run Score',
  AVG: 'Average',
  MIN: 'Minutes played',
};

type IndexKey = typeof INDICES[number]['key'];
type SortKey  = IndexKey | 'avg' | 'minutes_played' | 'nation' | 'player';

// ── Types ─────────────────────────────────────────────────────────────────────

interface IndexRange { min: string; max: string; }

interface Filters {
  macroRole: string;
  role: string;
  nation: string;
  ranges: Record<IndexKey, IndexRange>;
}

interface PlayerRow {
  player: string;
  nation: string;
  player_id?: number;
  team: string;
  primary_role: string;
  macro_role: string;
  minutes_played: number;
  idx__PROGRESSION: number;
  idx__DANGEROUSNESS: number;
  idx__RECEPTION: number;
  idx__GRAVITY: number;
  DQ_index: number | null;
  urs_pct_within_role: number | null;
}

// ── Shared UI ─────────────────────────────────────────────────────────────────

function SortIcon({ active, dir }: { active: boolean; dir: 'asc' | 'desc' }) {
  if (!active) return <svg className="w-3 h-3 inline ml-1 opacity-30" aria-hidden viewBox="0 0 12 12" fill="currentColor"><path d="M6 2l3 4H3zM6 10L3 6h6z"/></svg>;
  return dir === 'asc'
    ? <svg className="w-3 h-3 inline ml-1" aria-hidden viewBox="0 0 12 12" fill="currentColor" style={{ color: 'inherit' }}><path d="M6 2l3 4H3z"/></svg>
    : <svg className="w-3 h-3 inline ml-1" aria-hidden viewBox="0 0 12 12" fill="currentColor" style={{ color: 'inherit' }}><path d="M6 10L3 6h6z"/></svg>;
}

function RangeFilter({
  label,
  color,
  range,
  onChange,
}: {
  label: string;
  color: string;
  range: IndexRange;
  onChange: (r: IndexRange) => void;
}) {
  const minId = useId();
  const maxId = useId();

  const minVal = range.min === '' ? 0   : Number(range.min);
  const maxVal = range.max === '' ? 100 : Number(range.max);

  // Progress bar percentage
  const leftPct  = minVal;
  const widthPct = maxVal - minVal;

  return (
    <div
      className="bg-[var(--surface2)] border border-[var(--border)] rounded-[var(--radius)] p-4"
      style={{ borderLeft: `3px solid ${color}` }}
    >
      {/* Label + current range */}
      <div className="flex justify-between items-center mb-3">
        <span className="font-mono text-[10px] tracking-[0.12em] uppercase font-bold" style={{ color }}>
          {label}
        </span>
        <span className="font-mono text-[11px] font-bold text-[var(--text-muted)]">
          {range.min === '' ? '0' : range.min} – {range.max === '' ? '100' : range.max}
        </span>
      </div>

      {/* Visual track */}
      <div className="relative h-1 bg-[var(--surface)] rounded-sm mb-3">
        <div
          className="absolute h-full rounded-sm opacity-70"
          style={{ left: `${leftPct}%`, width: `${widthPct}%`, background: color }}
        />
      </div>

      {/* Number inputs */}
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label htmlFor={minId} className="block text-[10px] font-mono text-[var(--text-dim)] mb-1">MIN</label>
          <input
            id={minId}
            type="number"
            min={0}
            max={100}
            step={1}
            value={range.min}
            placeholder="0"
            onChange={e => {
              let val = e.target.value;
              if (val !== '') {
                const num = parseInt(val, 10);
                if (num > 100) val = '100';
                if (num < 0)   val = '0';
              }
              onChange({ ...range, min: val });
            }}
            className="input py-1.5 px-2.5 text-[13px] font-mono"
          />
        </div>
        <div>
          <label htmlFor={maxId} className="block text-[10px] font-mono text-[var(--text-dim)] mb-1">MAX</label>
          <input
            id={maxId}
            type="number"
            min={0}
            max={100}
            step={1}
            value={range.max}
            placeholder="100"
            onChange={e => {
              let val = e.target.value;
              if (val !== '') {
                const num = parseInt(val, 10);
                if (num > 100) val = '100';
                if (num < 0)   val = '0';
              }
              onChange({ ...range, max: val });
            }}
            className="input py-1.5 px-2.5 text-[13px] font-mono"
          />
        </div>
      </div>
    </div>
  );
}

// ── Index badge ───────────────────────────────────────────────────────────────

function IndexBadge({ label, value, color }: { label: string; value: number | null; color: string }) {
  const fullLabel = TABLE_ABBREVIATION_LABELS[label] ?? label;
  return (
    <div className="flex flex-col items-center min-w-[48px]">
      <span className="font-mono font-black text-base leading-none" style={{ color }}>
        {value != null ? value.toFixed(0) : '—'}
      </span>
      <span
        className="font-mono text-[8px] tracking-[0.1em] uppercase text-[var(--text-dim)] mt-0.5"
        title={fullLabel}
        aria-label={fullLabel}
      >
        {label}
      </span>
    </div>
  );
}

// ── Player result row ─────────────────────────────────────────────────────────

function PlayerResultRow({ player, rank }: { player: PlayerRow; rank: number }) {
  const nationName = player.nation || player.team;
  const flagUrl    = getFlagUrl(nationName);
  const macro      = player.macro_role;
  const macroColor = MACRO_COLOR[macro] ?? 'var(--text-muted)';

  const avg = (
    ((player.idx__PROGRESSION   ?? 0) +
     (player.idx__DANGEROUSNESS ?? 0) +
     (player.idx__RECEPTION     ?? 0) +
     (player.idx__GRAVITY       ?? 0)) / 4
  );

  return (
    <div
      className="card fade-up p-4 sm:p-5 cursor-default"
      role="listitem"
    >
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">

        {/* Player info */}
        <div className="flex items-center gap-3 sm:gap-4 flex-1 min-w-0">
          <span className="font-mono font-bold text-[13px] min-w-[24px] text-right text-[var(--text-dim)]">
            {rank}
          </span>

          {/* Flag */}
          {flagUrl
            ? <img src={flagUrl} alt={nationName} title={nationName} aria-label={nationName} className="w-7 h-5 object-cover rounded-sm shrink-0" />
            : <span className="w-7 shrink-0 font-mono text-[9px] text-[var(--text-dim)]" title={nationName} aria-label={nationName}>{nationName.substring(0, 3).toUpperCase()}</span>
          }

          {/* Name + role */}
          <div className="flex-1 min-w-0">
            {player.player_id ? (
              <Link
                to={`/player/${player.player_id}`}
                className="block no-underline hover:text-[var(--accent)] transition-colors focus-visible:outline-none focus-visible:underline"
              >
                <p className="font-display font-black text-lg text-inherit leading-none mb-0.5">
                  {player.player}
                </p>
              </Link>
            ) : (
              <p className="font-display font-black text-lg text-[var(--text)] leading-none mb-0.5">
                {player.player}
              </p>
            )}
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="font-display text-[10px] font-bold tracking-wide uppercase text-[var(--text-muted)]">{player.primary_role}</span>
              <span className="tag text-[9px]" style={{ background: `${macroColor}12`, color: macroColor, border: `1px solid ${macroColor}30` }}>
                {macro}
              </span>
            </div>
          </div>

          {/* Minutes (Mobile) */}
          <div className="lg:hidden flex flex-col items-end">
            <span className="font-mono font-black text-[13px] leading-none text-[var(--text)]">{player.minutes_played}'</span>
            <span className="font-mono text-[8px] tracking-[0.1em] uppercase text-[var(--text-dim)] mt-0.5">MIN</span>
          </div>
        </div>

        {/* Bottom: Indices and Statistics (go below on mobile, right on desktop) */}
        <div className="flex items-center justify-center lg:justify-end gap-3 pt-3 lg:pt-0 border-t lg:border-t-0 border-[var(--border)]">
          <div className="flex items-center justify-center gap-2 sm:gap-4 flex-wrap">
            {INDICES.map(idx => (
              <IndexBadge
                key={idx.key}
                label={idx.short}
                value={(player as any)[idx.key] as number | null}
                color={idx.color}
              />
            ))}

            {/* Average score */}
            <div
              className="flex flex-col items-center bg-[var(--surface2)] rounded-lg py-1.5 px-2.5 min-w-[52px]"
              title="Average"
              aria-label="Average"
            >
              <span className="font-mono font-black text-lg leading-none text-[var(--text)]">
                {avg.toFixed(0)}
              </span>
              <span className="font-mono text-[8px] tracking-[0.1em] uppercase text-[var(--text-dim)] mt-0.5" title="Average" aria-label="Average">AVG</span>
            </div>
          </div>

          {/* Minutes (Desktop) */}
          <div className="hidden lg:flex flex-col items-center min-w-[48px]">
            <span className="font-mono font-black text-[15px] leading-none text-[var(--text)]" title="Minutes played" aria-label="Minutes played">
              {player.minutes_played}'
            </span>
            <span className="font-mono text-[8px] tracking-[0.1em] uppercase text-[var(--text-dim)] mt-0.5" title="Minutes played" aria-label="Minutes played">
              MIN
            </span>
          </div>
        </div>

      </div>
    </div>
  );
}

// ── Active filter pills ───────────────────────────────────────────────────────

function ActiveFilterPills({ filters, onClear }: { filters: Filters; onClear: () => void }) {
  const pills: string[] = [];
  if (filters.macroRole) pills.push(`Macro: ${filters.macroRole}`);
  if (filters.role) pills.push(`Role: ${filters.role}`);
  if (filters.nation) pills.push(`Nation: ${filters.nation}`);
  INDICES.forEach(idx => {
    const r = filters.ranges[idx.key];
    if (r.min !== '' || r.max !== '') {
      pills.push(`${idx.label}: ${r.min || '0'}–${r.max || '100'}`);
    }
  });
  if (pills.length === 0) return null;
  return (
    <div className="flex flex-wrap items-center gap-2 mb-4">
      <span className="font-mono text-[10px] text-[var(--text-dim)] uppercase tracking-[0.1em]">Active filters:</span>
      {pills.map(p => (
        <span key={p} className="tag bg-[var(--accent-dim)] text-[var(--accent)] border border-[rgba(37,99,235,0.2)]">{p}</span>
      ))}
      <button onClick={onClear} className="btn btn-ghost text-[11px] py-0.5 px-3">Clear all</button>
    </div>
  );
}

// ── Empty state ───────────────────────────────────────────────────────────────

function EmptyState() {
  return (
    <div className="text-center py-16 px-6">
      <p className="text-[40px] mb-3">🔍</p>
      <p className="font-display font-bold text-xl text-[var(--text)] mb-2">No players match your filters</p>
      <p className="text-sm text-[var(--text-muted)]">Try widening the index ranges or clearing the role filter</p>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

const DEFAULT_RANGES: Record<IndexKey, IndexRange> = {
  idx__PROGRESSION:   { min: '', max: '' },
  idx__DANGEROUSNESS: { min: '', max: '' },
  idx__RECEPTION:     { min: '', max: '' },
  idx__GRAVITY:       { min: '', max: '' },
  DQ_index:           { min: '', max: '' },
  urs_pct_within_role:{ min: '', max: '' },
};

export default function SearchByAttribute() {
  const [filters, setFilters]           = useState<Filters>({ macroRole: '', role: '', nation: '', ranges: DEFAULT_RANGES });
  const [allPlayers, setAllPlayers]     = useState<PlayerRow[]>([]);
  const [loading, setLoading]           = useState(true);
  const [searched, setSearched]         = useState(false);
  const [sortKey, setSortKey]           = useState<SortKey>('player');
  const [sortOrder, setSortOrder]       = useState<'asc' | 'desc'>('asc');
  const [mobileFiltersOpen, setMobile]  = useState(false);

  const macroRoleId = useId();
  const roleId      = useId();

  // Roles available given selected macro_role
  const availableRoles = filters.macroRole
    ? PRIMARY_ROLES.filter(r => ROLE_TO_MACRO[r] === filters.macroRole)
    : PRIMARY_ROLES;

  // Load all players on mount
  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const data: PlayerRow[] = await fetch(`${API_BASE_URL}/space-control/search`).then(r => r.json());
        setAllPlayers(data.map(player => ({
          ...player,
          nation: player.team,
        })));
      } catch {
        setAllPlayers([]);
      } finally {
        setLoading(false);
        setSearched(true);
      }
    })();
  }, []);

  const clearFilters = () => setFilters({ macroRole: '', role: '', nation: '', ranges: DEFAULT_RANGES });

  // Debounce filters so rapid typing in range inputs doesn't cause per-keystroke re-filtering
  const debouncedFilters = useDebounce(filters, 300);

  // Client-side filtering (since we fetch all players at once, we can do it here)
  const filtered = allPlayers.filter(player => {
    const f = debouncedFilters;
    
    // Filter by macro role and primary role
    if (f.macroRole && player.macro_role !== f.macroRole) return false;
    if (f.role && player.primary_role !== f.role) return false;
    if (f.nation && player.nation !== f.nation) return false;

    // Numerical filters: check if player indices fall within selected ranges
    for (const idx of INDICES) {
      const raw = (player as any)[idx.key] as number | null | undefined;
      // DQ_index and urs_pct_within_role may be null — skip when the range is at default (no filter set)
      if ((idx.key === 'DQ_index' || idx.key === 'urs_pct_within_role') && raw == null) continue;
      const val = raw == null ? 0 : Math.round(Number(raw));
      const r   = f.ranges[idx.key];
      const min = r.min === '' ? 0   : Number(r.min);
      const max = r.max === '' ? 100 : Number(r.max);
      if (val < min || val > max) return false;
    }

    return true;
  });

  const sorted = [...filtered].sort((a, b) => {
    if (sortKey === 'player' || sortKey === 'nation') {
      const valA = String((a as any)[sortKey] ?? '');
      const valB = String((b as any)[sortKey] ?? '');
      const compare = valA.localeCompare(valB, undefined, { sensitivity: 'base' });
      return sortOrder === 'asc' ? compare : -compare;
    }

    let valA = 0, valB = 0;
    if (sortKey === 'avg') {
      valA = ((a.idx__PROGRESSION ?? 0) + (a.idx__DANGEROUSNESS ?? 0) + (a.idx__RECEPTION ?? 0) + (a.idx__GRAVITY ?? 0)) / 4;
      valB = ((b.idx__PROGRESSION ?? 0) + (b.idx__DANGEROUSNESS ?? 0) + (b.idx__RECEPTION ?? 0) + (b.idx__GRAVITY ?? 0)) / 4;
    } else {
      valA = ((a as any)[sortKey] ?? 0) as number;
      valB = ((b as any)[sortKey] ?? 0) as number;
    }
    return sortOrder === 'asc' ? valA - valB : valB - valA;
  });

  const handleSort = (key: SortKey) => {
    const defaultOrder = key === 'player' || key === 'nation' ? 'asc' : 'desc';
    if (sortKey === key) setSortOrder(p => p === 'asc' ? 'desc' : 'asc');
    else { setSortKey(key); setSortOrder(defaultOrder); }
  };

  return (
    <div className="w-full pb-16 min-h-screen bg-[var(--bg)]">
      {/* Page header */}
      <div className="border-b border-[var(--border)] px-6 pt-10 pb-8 bg-[var(--surface)]">
        <div className="max-w-[1200px] mx-auto">
          {/* Breadcrumb */}
          <nav aria-label="Breadcrumb" className="mb-4">
            <ol className="flex items-center gap-2 text-sm text-[var(--text-muted)]">
              <li><Link to="/" className="hover:text-[var(--accent)] transition-colors font-semibold">Home</Link></li>
              <li aria-hidden>/</li>
              <li className="font-semibold text-[var(--text)]" aria-current="page">Search by Attribute</li>
            </ol>
          </nav>
          <h1 className="font-display font-black text-5xl sm:text-6xl leading-none tracking-tight text-[var(--text)]">
            Search by Attribute
          </h1>
          <p className="mt-3 text-base text-[var(--text-muted)]">
            Filter all the players by macro role, tactical role, and contextual space control index ranges.
            Rankings are sorted alphabetically by player name by default.
          </p>
        </div>
      </div>

      <div className="max-w-[1200px] mx-auto px-6 pt-8">
        <div className="flex flex-col lg:grid lg:grid-cols-[300px_1fr] gap-8 items-start">

          {/* Hamburger Trigger Button for Mobile */}
          <div className="lg:hidden w-full mb-2">
            <button
              onClick={() => setMobile(true)}
              className="w-full flex items-center justify-center gap-2 p-3 rounded-[var(--radius)] font-bold transition-colors bg-[var(--surface2)] border border-[var(--border)] text-[var(--text)]"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
              </svg>
              Filter by Attributes
            </button>
          </div>

          {/* Left panel: filters - Drawer overlay (Mobile), static (Desktop) */}
          <aside 
            className={`
              ${mobileFiltersOpen ? 'fixed inset-0 z-50 bg-[var(--bg)] overflow-y-auto p-4 sm:p-6 block' : 'hidden'} 
              lg:block lg:static lg:p-0 lg:bg-transparent lg:w-full
            `}
            aria-label="Search filters"
          >
            <div className="card p-6 relative">
              
              {/* Close Button X for Mobile */}
              <button
                onClick={() => setMobile(false)}
                className="lg:hidden absolute top-4 right-4 text-xl font-bold p-2 text-[var(--text-muted)] bg-transparent border-none cursor-pointer"
                aria-label="Close filters"
              >✕</button>

              <h2 className="font-display font-black text-xl text-[var(--text)] mb-5">Filters</h2>

              {/* Macro role */}
              <div className="mb-5">
                <label htmlFor={macroRoleId} className="block font-mono text-[10px] tracking-[0.12em] uppercase text-[var(--text-dim)] mb-2">
                  Macro Role
                </label>
                {/* Pill buttons for macro role */}
                <div className="flex flex-wrap gap-1.5">
                  <button
                    onClick={() => setFilters(f => ({ ...f, macroRole: '', role: '' }))}
                    className="tag cursor-pointer border-none py-[5px] px-3"
                    style={{ background: filters.macroRole === '' ? 'var(--accent)' : 'var(--surface2)', color: filters.macroRole === '' ? '#fff' : 'var(--text-muted)' }}
                  >All</button>
                  {MACRO_ROLES.map(m => {
                    const active = filters.macroRole === m;
                    const col = MACRO_COLOR[m];
                    return (
                      <button
                        key={m}
                        onClick={() => setFilters(f => ({ ...f, macroRole: active ? '' : m, role: '' }))}
                        className="tag cursor-pointer"
                        style={{ border: `1px solid ${active ? col : 'var(--border)'}`, background: active ? `${col}15` : 'var(--surface2)', color: active ? col : 'var(--text-muted)' }}
                      >{m}</button>
                    );
                  })}
                </div>
              </div>

              {/* Primary role */}
              <div className="mb-6">
                <label htmlFor={roleId} className="block font-mono text-[10px] tracking-[0.12em] uppercase text-[var(--text-dim)] mb-2">
                  Primary Role
                </label>
                <select
                  id={roleId}
                  value={filters.role}
                  onChange={e => setFilters(f => ({ ...f, role: e.target.value }))}
                  className="input text-[13px]"
                >
                  <option value="">All roles</option>
                  {availableRoles.map(r => <option key={r} value={r}>{r}</option>)}
                </select>
              </div>

              {/* Nation */}
              <div className="mb-6">
                <label className="block font-mono text-[10px] tracking-[0.12em] uppercase text-[var(--text-dim)] mb-2">
                  Nation
                </label>
                <select
                  value={filters.nation}
                  onChange={e => setFilters(f => ({ ...f, nation: e.target.value }))}
                  className="input text-[13px]"
                >
                  <option value="">All nations</option>
                  {Array.from(new Set(allPlayers.map(p => p.nation))).sort().map(n => <option key={n} value={n}>{n}</option>)}
                </select>
              </div>

              {/* Divider */}
              <div className="h-px bg-[var(--border)] mb-5" />

              {/* Index ranges */}
              <p className="font-mono text-[10px] tracking-[0.12em] uppercase text-[var(--text-dim)] mb-3">
                Index Ranges (0–100)
              </p>
              <div className="flex flex-col gap-3 mb-6">
                {INDICES.map(idx => (
                  <RangeFilter
                    key={idx.key}
                    label={idx.label}
                    color={idx.color}
                    range={filters.ranges[idx.key]}
                    onChange={r => setFilters(f => ({ ...f, ranges: { ...f.ranges, [idx.key]: r } }))}
                  />
                ))}
              </div>

              <button onClick={clearFilters} className="btn btn-ghost w-full justify-center mt-2">
                Reset Filters
              </button>
              <button
                onClick={() => setMobile(false)}
                className="btn btn-primary lg:hidden w-full mt-4 flex items-center justify-center font-bold py-3"
              >Apply Filters</button>
            </div>
          </aside>

          {/* Results */}
          <section aria-label="Search results" className="w-full">
            <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
              <div>
                <span className="font-display font-black text-[22px] text-[var(--text)] mr-2.5">
                  {loading ? '…' : sorted.length} players
                </span>
                {searched && !loading && (
                  <span className="font-mono text-[11px] text-[var(--text-dim)]">found</span>
                )}
              </div>
            </div>

            <ActiveFilterPills filters={filters} onClear={clearFilters} />

            {/* Clickable Header sorting ticks (hidden on Mobile) */}
            {sorted.length > 0 && (
              <div
                className="hidden lg:grid items-center gap-4 py-2 px-5 mb-1.5"
                style={{ gridTemplateColumns: '28px 48px 1fr repeat(7, 52px) 48px' }}
              >
                <span />
                <button
                  onClick={() => handleSort('nation')}
                  className={`bg-transparent border-none cursor-pointer p-0 font-mono text-[9px] tracking-[0.1em] uppercase text-center flex items-center justify-center transition-colors ${sortKey === 'nation' ? 'text-[var(--text)]' : 'text-[var(--text-dim)]'}`}
                  title="Nation"
                  aria-label="Sort by nation"
                >
                  NAT <SortIcon active={sortKey === 'nation'} dir={sortOrder} />
                </button>
                <button
                  onClick={() => handleSort('player')}
                  className={`bg-transparent border-none cursor-pointer p-0 font-mono text-[9px] tracking-[0.1em] uppercase text-center flex items-center justify-center transition-colors ${sortKey === 'player' ? 'text-[var(--text)]' : 'text-[var(--text-dim)]'}`}
                  title="Player name"
                  aria-label="Sort by player name"
                >
                  Player name <SortIcon active={sortKey === 'player'} dir={sortOrder} />
                </button>
                {INDICES.map(idx => (
                  <button
                    key={idx.key}
                    onClick={() => handleSort(idx.key)}
                    className="bg-transparent border-none cursor-pointer p-0 font-mono text-[9px] tracking-[0.1em] uppercase text-center flex items-center justify-center transition-colors"
                    style={{ color: sortKey === idx.key ? idx.color : 'var(--text-dim)' }}
                    title={idx.label}
                    aria-label={`Sort by ${idx.label}`}
                  >
                    {idx.short} <SortIcon active={sortKey === idx.key} dir={sortOrder} />
                  </button>
                ))}
                <button
                  onClick={() => handleSort('avg')}
                  className={`bg-transparent border-none cursor-pointer p-0 font-mono text-[9px] tracking-[0.1em] uppercase text-center flex items-center justify-center transition-colors ${sortKey === 'avg' ? 'text-[var(--text)]' : 'text-[var(--text-dim)]'}`}
                  title="Average"
                  aria-label="Sort by average"
                >
                  AVG <SortIcon active={sortKey === 'avg'} dir={sortOrder} />
                </button>
                <button
                  onClick={() => handleSort('minutes_played')}
                  className={`bg-transparent border-none cursor-pointer p-0 font-mono text-[9px] tracking-[0.1em] uppercase text-center flex items-center justify-center transition-colors ${sortKey === 'minutes_played' ? 'text-[var(--text)]' : 'text-[var(--text-dim)]'}`}
                  title="Minutes played"
                  aria-label="Sort by minutes played"
                >
                  MIN <SortIcon active={sortKey === 'minutes_played'} dir={sortOrder} />
                </button>
              </div>
            )}

            {/* Results list */}
            {loading ? (
              <div className="flex flex-col gap-2.5">
                {Array.from({ length: 8 }).map((_, i) => (
                  <div key={i} className="skeleton h-[72px] rounded-[20px]" />
                ))}
              </div>
            ) : sorted.length === 0 && searched ? (
              <div className="card"><EmptyState /></div>
            ) : (
              <div className="flex flex-col gap-2" role="list" aria-label="Player results">
                {sorted.map((player, i) => (
                  <PlayerResultRow key={`${player.player}-${player.team}`} player={player} rank={i + 1} />
                ))}
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}