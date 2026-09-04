import { useState } from 'react';
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  ResponsiveContainer, Legend, Tooltip,
} from 'recharts';
import type { SpaceControlIndex, SpaceControlAggregated } from '../hooks/useSpaceControl';
import { TOOLTIP_DESCRIPTIONS } from '../data/tooltip';

// ── Stat view mode ────────────────────────────────────────────────────────────

export type StatViewMode = 'raw' | 'per90' | 'percentages';

const MODES: { key: StatViewMode; label: string }[] = [
  { key: 'raw',         label: 'Raw' },
  { key: 'per90',       label: 'Per 90' },
  { key: 'percentages', label: 'Percentages' },
];

export function StatViewToggle({
  mode, onChange,
}: { mode: StatViewMode; onChange: (m: StatViewMode) => void }) {
  return (
    <div
      role="tablist"
      aria-label="Statistic view mode"
      className="flex w-full sm:w-auto sm:inline-flex gap-1 bg-[var(--surface2)] rounded-xl p-1"
    >
      {MODES.map(m => (
        <button
          key={m.key}
          role="tab"
          aria-selected={mode === m.key}
          onClick={() => onChange(m.key)}
          className={`flex-1 sm:flex-none px-4 py-1.5 rounded-lg text-[11px] font-bold font-display tracking-wide border-none cursor-pointer transition-all ${
            mode === m.key
              ? 'bg-[var(--accent)] text-white'
              : 'bg-transparent text-[var(--text-muted)] hover:text-[var(--text)]'
          }`}
        >
          {m.label}
        </button>
      ))}
    </div>
  );
}

// ── Radar config ──────────────────────────────────────────────────────────────

const RADAR_DEFS = [
  {
    key: 'PROGRESSION' as const, label: 'Progression',
    idxKey: 'idx__PROGRESSION' as keyof SpaceControlIndex, color: '#16a34a',
    axes: [
      { dataKey: 'pct__lb_geom_per90'                      as keyof SpaceControlIndex, label: 'LB Geom /90' },
      { dataKey: 'pct__lb_quality_per90'                   as keyof SpaceControlIndex, label: 'LB Quality /90' },
      { dataKey: 'pct__lb_epv_per90'                       as keyof SpaceControlIndex, label: 'LB EPV /90' },
      { dataKey: 'pct__successful_hull_penetrations_per90' as keyof SpaceControlIndex, label: 'Hull Penetr. /90' },
      { dataKey: 'pct__defenders_bypassed_mean'            as keyof SpaceControlIndex, label: 'Def. Bypassed Avg' },
    ],
  },
  {
    key: 'DANGEROUSNESS' as const, label: 'Dangerousness',
    idxKey: 'idx__DANGEROUSNESS' as keyof SpaceControlIndex, color: '#dc2626',
    axes: [
      { dataKey: 'pct__epv_penetration_per90' as keyof SpaceControlIndex, label: 'EPV Penetr. /90' },
      { dataKey: 'pct__epv_inside_circ_per90' as keyof SpaceControlIndex, label: 'EPV In-Circ /90' },
      { dataKey: 'pct__epv_exit_per90'        as keyof SpaceControlIndex, label: 'EPV Exit /90' },
      { dataKey: 'pct__epv_outside_circ_per90' as keyof SpaceControlIndex, label: 'EPV Out-Circ /90' },
    ],
  },
  {
    key: 'RECEPTION' as const, label: 'Reception',
    idxKey: 'idx__RECEPTION' as keyof SpaceControlIndex, color: '#2563eb',
    axes: [
      { dataKey: 'pct__between_lines_pct'           as keyof SpaceControlIndex, label: 'Between Lines %' },
      { dataKey: 'pct__successful_hull_exits_per90'  as keyof SpaceControlIndex, label: 'Hull Exits /90' },
      { dataKey: 'pct__pressure_resistance_pct'     as keyof SpaceControlIndex, label: 'Press. Resist %' },
    ],
  },
  {
    key: 'GRAVITY' as const, label: 'Gravity',
    idxKey: 'idx__GRAVITY' as keyof SpaceControlIndex, color: '#d97706',
    axes: [
      { dataKey: 'pct__gravity_proximity_pct' as keyof SpaceControlIndex, label: 'Space Attraction %' },
      { dataKey: 'pct__gravity_hull_pct'      as keyof SpaceControlIndex, label: 'Gravity Hull %' },
      { dataKey: 'pct__gravity_abs_m'         as keyof SpaceControlIndex, label: 'Def. Pull |m|' },
    ],
  },
] as const;

// ── Mother stats ──────────────────────────────────────────────────────────────

type StatDef = { col: keyof SpaceControlAggregated; label: string };
type MotherBlock = { raw: StatDef[]; per90: StatDef[]; percentages: StatDef[] };

const MOTHER_STATS: Record<'PROGRESSION' | 'DANGEROUSNESS' | 'RECEPTION' | 'GRAVITY', MotherBlock> = {
  PROGRESSION: {
    raw: [
      { col: 'lb_geom', label: 'LB Geom' },
      { col: 'lb_quality', label: 'LB Quality' },
      { col: 'lb_epv', label: 'High Value Pass' },
      { col: 'defenders_bypassed_mean', label: 'Def. Bypassed (avg)' },
      { col: 'penetration_n', label: 'Penetration Attempts (n)' },
      { col: 'successful_hull_penetrations_n', label: 'Successful Penetrations (n)' },
    ],
    per90: [
      { col: 'lb_geom_per90', label: 'LB Geom /90' },
      { col: 'lb_quality_per90', label: 'LB Quality /90' },
      { col: 'lb_epv_per90', label: 'LB EPV /90' },
      { col: 'penetration_per90', label: 'Penetration Attempts /90' },
      { col: 'successful_hull_penetrations_per90', label: 'Successful Penetrations /90' },
    ],
    percentages: [
      { col: 'lb_geom_pct', label: 'LB Geom %' },
      { col: 'lb_quality_pct', label: 'LB Quality %' },
      { col: 'lb_epv_pct', label: 'LB EPV %' },
      { col: 'penetration_completion_pct', label: 'Penetration Completion %' },
    ],
  },
  DANGEROUSNESS: {
    raw: [
      { col: 'epv_penetration_sum', label: 'EPV Penetr. (sum)' },
      { col: 'epv_inside_circ_sum',  label: 'EPV In-Circ (sum)' },
      { col: 'epv_exit_sum',         label: 'EPV Exit (sum)' },
      { col: 'epv_outside_circ_sum', label: 'EPV Out-Circ (sum)' },
    ],
    per90: [
      { col: 'epv_added_per90',        label: 'EPV Added /90' },
      { col: 'epv_penetration_per90',  label: 'EPV Penetr. /90' },
      { col: 'epv_inside_circ_per90',  label: 'EPV In-Circ /90' },
      { col: 'epv_exit_per90',         label: 'EPV Exit /90' },
      { col: 'epv_outside_circ_per90', label: 'EPV Out-Circ /90' },
    ],
    percentages: [],
  },
  RECEPTION: {
    raw: [
      { col: 'between_lines_n',       label: 'Block Receipts (n)' },
      { col: 'pressure_resistance_n', label: 'Press. Resist (n)' },
      { col: 'inside_circ_n',         label: 'In-Circ (n)' },
    ],
    per90: [
      { col: 'between_lines_per90',          label: 'Between Lines /90' },
      { col: 'successful_hull_exits_per90',  label: 'Hull Exits /90' },
      { col: 'inside_circ_per90',            label: 'In-Circ /90' },
    ],
    percentages: [
      { col: 'between_lines_pct',       label: 'Between Lines %' },
      { col: 'hull_exit_pct',           label: 'Hull Exits %' },
      { col: 'pressure_resistance_pct', label: 'Press. Resist %' },
    ],
  },
  GRAVITY: {
    raw: [
      { col: 'gravity_directional_m', label: 'Def. Pull (m)' },
    ],
    per90: [],
    percentages: [
      { col: 'gravity_proximity_pct', label: 'Space Attraction %' },
      { col: 'gravity_hull_pct',      label: 'Gravity Hull %' },
    ],
  },
};

// ── Radar custom tooltip ──────────────────────────────────────────────────────

function RadarTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const statLabel = payload[0]?.payload?.stat ?? payload[0]?.name ?? 'Metric';
  return (
    <div className="bg-[var(--surface)] border border-[var(--border)] rounded-[10px] px-3.5 py-2.5 text-xs shadow-lg">
      <p className="font-bold text-[var(--text)] mb-1.5">{statLabel}</p>
      {payload.map((item: any) => (
        <p key={item.name} className="font-mono mt-0.5" style={{ color: item.color }}>
          <span className="text-[var(--text-muted)] mr-1">{payload.length > 1 ? `${item.name} Percentile:` : 'Percentile:'}</span>
          <strong>{typeof item.value === 'number' ? item.value.toFixed(1) : '—'}</strong>
        </p>
      ))}
    </div>
  );
}

// ── Number formatter ──────────────────────────────────────────────────────────

function fmt(v: unknown): string {
  if (v == null) return '—';
  if (typeof v === 'string' && /^-?\d+,\d+$/.test(v)) {
    v = parseFloat(v.replace(',', '.'));
  }
  if (typeof v === 'number') return Math.abs(v) < 10 ? v.toFixed(2) : v.toFixed(1);
  return String(v);
}

// ── Mother stat row with "?" tooltip (core stats only) ───────────────────────

function MotherStatRow({
  label,
  value,
  color,
  showExperimental,
}: {
  label: string;
  value: string;
  color: string;
  showExperimental?: boolean;
}) {
  const [hovered, setHovered] = useState(false);
  const description = TOOLTIP_DESCRIPTIONS[label] ?? 'No description available.';

  return (
    <div className="relative flex justify-between items-center gap-2">
      {/* Left side: label + badges */}
      <div className="flex items-center gap-2 min-w-0">
        <span className="text-xs font-semibold text-[var(--text-muted)]">
          {label}
        </span>

        {showExperimental && (
          <span
            className="text-[9px] font-bold uppercase tracking-wide shrink-0 px-1.5 py-0.5 rounded"
            style={{ color, backgroundColor: `${color}15` }}
          >
            Experimental
          </span>
        )}

        {/* "?" button */}
        <button
          aria-label={`Description for ${label}`}
          onMouseEnter={() => setHovered(true)}
          onMouseLeave={() => setHovered(false)}
          className="shrink-0 w-[15px] h-[15px] rounded-full text-[8px] font-bold font-display cursor-help flex items-center justify-center transition-all p-0 leading-none border"
          style={{
            borderColor: hovered ? 'rgba(0,0,0,0.3)' : 'rgba(0,0,0,0.12)',
            background: hovered ? 'rgba(0,0,0,0.06)' : 'rgba(0,0,0,0.02)',
            color: hovered ? 'rgba(0,0,0,0.6)' : 'rgba(0,0,0,0.35)',
          }}
        >
          ?
        </button>

        {/* Tooltip — shown on hover */}
        {hovered && (
          <div
            role="tooltip"
            className="absolute bottom-[calc(100%+8px)] left-0 max-w-[240px] bg-[var(--surface)] rounded-[10px] px-3.5 py-2.5 z-[60] pointer-events-none"
            style={{ border: `1px solid ${color}33`, borderLeft: `3px solid ${color}`, boxShadow: 'var(--shadow-lg)' }}
          >
            <p className="font-display text-[10px] font-bold mb-1.5 tracking-wide" style={{ color }}>
              {label}
            </p>
            <p className="text-[11px] text-[var(--text-muted)] leading-[1.55]">
              {description}
            </p>
          </div>
        )}
      </div>

      {/* Right side: formatted value */}
      <span className="font-mono font-bold text-[13px] shrink-0" style={{ color }}>
        {value}
      </span>
    </div>
  );
}

// ── Simple static radar axis tick (no hover) ──────────────────────────────────

function SimpleRadarTick({
  x = 0, y = 0, cx = 0, cy = 0,
  payload,
}: {
  x?: number; y?: number; cx?: number; cy?: number;
  payload?: { value: string };
}) {
  if (!payload) return null;

  const dx = x - cx;
  const dy = y - cy;
  const length = Math.sqrt(dx * dx + dy * dy) || 1;
  const offset = 34; // push outward
  const nx = x + (dx / length) * offset;
  const ny = y + (dy / length) * offset;

  return (
    <text
      x={nx} y={ny}
      textAnchor="middle"
      dominantBaseline="middle"
      fill="var(--text-muted)"
      fontSize={12}
      fontFamily="Inter, sans-serif"
      fontWeight={600}
    >
      {payload.value}
    </text>
  );
}

// ── Index label with "?" tooltip beside it ────────────────────────────────────

function IndexLabelWithTooltip({ def }: { def: typeof RADAR_DEFS[number] }) {
  const [hovered, setHovered] = useState(false);

  const isGravity = def.key === 'GRAVITY';
  const baseDesc  = TOOLTIP_DESCRIPTIONS[def.label] ?? `${def.label} index — percentile rank within macro-role (0–100).`;
  const expDesc   = TOOLTIP_DESCRIPTIONS['Experimental'];

  return (
    <div className="flex flex-col gap-1">
      {/* Label row: text + "?" */}
      <div className="flex items-center gap-1.5">
        <span
          className="font-display text-[10px] tracking-[0.12em] uppercase font-bold"
          style={{ color: def.color }}
        >
          {def.label}
        </span>

        <div className="relative">
          <button
            aria-label={`Description for ${def.label} index`}
            onMouseEnter={() => setHovered(true)}
            onMouseLeave={() => setHovered(false)}
            style={{
              width: 14, height: 14, borderRadius: '50%',
              border: `1px solid ${hovered ? def.color : 'rgba(0,0,0,0.15)'}`,
              background: hovered ? `${def.color}18` : 'rgba(0,0,0,0.03)',
              color: hovered ? def.color : 'rgba(0,0,0,0.35)',
              fontSize: 8, fontWeight: 700, fontFamily: 'Inter, sans-serif',
              cursor: 'help', display: 'flex', alignItems: 'center', justifyContent: 'center',
              transition: 'all 0.12s', padding: 0, lineHeight: 1, flexShrink: 0,
            }}
          >
            ?
          </button>

          {hovered && (
            <div
              role="tooltip"
              style={{
                position: 'absolute', top: 'calc(100% + 6px)', left: 0,
                minWidth: 220, maxWidth: 280, zIndex: 60,
                background: 'var(--surface2)',
                border: `1px solid ${def.color}44`,
                borderLeft: `3px solid ${def.color}`,
                borderRadius: 10, padding: '12px 14px',
                pointerEvents: 'none',
                boxShadow: '0 8px 24px rgba(0,0,0,0.18)',
              }}
            >
              {/* Index name */}
              <p style={{
                fontFamily: 'Inter, sans-serif', fontSize: 10,
                fontWeight: 700, color: def.color, marginBottom: 6, letterSpacing: '0.04em',
              }}>
                {def.label}
              </p>

              {/* Base description */}
              <p style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.6, margin: 0 }}>
                {baseDesc}
              </p>

              {/* Gravity only: Experimental badge + description */}
              {isGravity && (
                <>
                  <div style={{ marginTop: 10, marginBottom: 6 }}>
                    <span style={{
                      display: 'inline-flex', alignItems: 'center', gap: 4,
                      fontSize: 9, fontWeight: 700, textTransform: 'uppercase',
                      letterSpacing: '0.06em',
                      color: def.color, background: `${def.color}20`,
                      padding: '3px 8px', borderRadius: 5,
                    }}>
                      Experimental
                    </span>
                  </div>
                  <p style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.6, margin: 0 }}>
                    {expDesc}
                  </p>
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Single radar card ─────────────────────────────────────────────────────────

function RadarCard({
  def, indexRow, aggRow, mode, playerName,
}: {
  def: typeof RADAR_DEFS[number];
  indexRow: SpaceControlIndex;
  aggRow: SpaceControlAggregated | null | undefined;
  mode: StatViewMode;
  playerName: string;
}) {
  const idxValue = indexRow[def.idxKey] as number | undefined;
  const lastName = playerName.trim().split(' ').pop() || playerName;

  const radarData = def.axes.map(ax => ({
    stat: ax.label,
    value: (indexRow[ax.dataKey] as number) ?? 0,
  }));

  const block    = MOTHER_STATS[def.key];
  const statList = block[mode] as StatDef[];

  const renderTick = (props: any) => <SimpleRadarTick {...props} />;

  // Informative messages for empty mother-stat panels
  let emptyMessage =
    mode === 'per90'
      ? `${def.label} has no per-90 statistics in the spec`
      : `${def.label} has no percentage statistics in the spec`;

  if (def.key === 'DANGEROUSNESS' && mode === 'percentages') {
    emptyMessage =
      'The Dangerousness index does not include percentage statistics because it is based on EPV (Expected Pass Value) and absolute penetration volumes. Being a probabilistic measure that calculates the net offensive "weight" generated by a player, it is evaluated exclusively in absolute values (Raw) or scaled to playing time (Per 90).';
  } else if (def.key === 'GRAVITY' && mode === 'per90') {
    emptyMessage =
      "Gravity statistics are not calculated 'Per 90' because they measure the reaction and spatial deformation of the opposing defense (in meters or percentage deviations). Since it represents an average effect calculated every time the player has the ball, it reflects a constant 'magnetic pull' rather than a cumulative volume of actions over time.";
  }

  return (
    <div
      className="relative bg-[var(--surface)] border border-[var(--border)] rounded-[var(--radius-lg)] p-6 shadow-[var(--shadow)]"
      style={{ borderTop: `3px solid ${def.color}` }}
    >
      {/* Header: label with "?" on left, index value on right */}
      <div className="flex justify-between items-start mb-2">
        <IndexLabelWithTooltip def={def} />
        <div className="text-right">
          <div className="font-display text-[9px] tracking-[0.1em] uppercase text-[var(--text-dim)]">Index</div>
          <div className="font-display font-black text-[26px] leading-none" style={{ color: def.color }}>
            {idxValue != null ? idxValue.toFixed(1) : '—'}
          </div>
        </div>
      </div>

      {/* Radar — static axis labels */}
      <ResponsiveContainer width="100%" height={440}>
        <RadarChart data={radarData} margin={{ top: 28, right: 50, bottom: 40, left: 50 }}>
          <PolarGrid stroke="rgba(0,0,0,0.08)" />
          <PolarAngleAxis dataKey="stat" tick={renderTick} />
          <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
          <Tooltip content={<RadarTooltip />} />
          <Radar
            name={lastName}
            dataKey="value"
            stroke={def.color} fill={def.color} fillOpacity={0.15} strokeWidth={2}
            dot={{ fill: def.color, r: 3, strokeWidth: 0 }}
            activeDot={{ r: 5, fill: def.color, stroke: '#fff', strokeWidth: 1.5 }}
          />
          <Legend
            formatter={() => <span className="text-[var(--text-muted)] text-[11px]">Percentile rank (0–100)</span>}
            wrapperStyle={{ position: 'relative', top: 20 }}
          />
        </RadarChart>
      </ResponsiveContainer>

      {/* Mother stats card */}
      <div className="mt-4 bg-[var(--surface2)] rounded-xl p-4">
        <p className="font-display text-[9px] tracking-[0.1em] uppercase text-[var(--text-dim)] mb-3">
          Core stats
        </p>

        {statList.length === 0 ? (
          <div className="bg-[var(--bg)] p-3 rounded-md border border-[var(--border)]">
            <p className="text-[11px] text-[var(--text-muted)] leading-[1.5]">
              {emptyMessage}
            </p>
          </div>
        ) : aggRow == null ? (
          <p className="text-[11px] text-[var(--text-dim)]">Aggregated data not available</p>
        ) : (
          <div className="flex flex-col gap-2">
            {statList.map(s => (
              <MotherStatRow
                key={s.col}
                label={s.label}
                value={fmt(aggRow[s.col])}
                color={def.color}
                showExperimental={def.key === 'GRAVITY'}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Exported section ──────────────────────────────────────────────────────────

export default function SpaceControlSection({
  playerName, indexRow, aggRow, mode, onModeChange,
}: {
  playerName: string;
  teamName?: string;
  indexRow: SpaceControlIndex;
  aggRow: SpaceControlAggregated | null | undefined;
  mode: StatViewMode;
  onModeChange: (m: StatViewMode) => void;
}) {
  return (
    <section className="max-w-[1200px] mx-auto px-6 pb-12">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <div>
          <h2 className="font-display font-black text-xl text-[var(--text)] mb-1">
            Space Control &amp; Value
          </h2>
          <p className="text-xs text-[var(--text-muted)]">
            Selected player metrics — {playerName}
          </p>
        </div>
        <StatViewToggle mode={mode} onChange={onModeChange} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {RADAR_DEFS.map(def => (
          <RadarCard
            key={def.key}
            def={def}
            indexRow={indexRow}
            aggRow={aggRow}
            mode={mode}
            playerName={playerName}
          />
        ))}
      </div>
    </section>
  );
}