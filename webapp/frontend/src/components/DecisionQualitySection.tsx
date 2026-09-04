import { useState } from 'react';
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  ResponsiveContainer, Legend, Tooltip,
} from 'recharts';
import type { DecisionQualityRow } from '../hooks/useDecisionQuality';
import { TOOLTIP_DESCRIPTIONS } from '../data/tooltip';
import { StatViewToggle, type StatViewMode } from './SpaceControlSection';

// ── Constants ─────────────────────────────────────────────────────────────────

const DQ_COLOR = '#7c3aed';

// ── Radar axes ────────────────────────────────────────────────────────────────

const RADAR_AXES: { dataKey: keyof DecisionQualityRow; label: string }[] = [
  { dataKey: 'pct__accuracy', label: 'Picks the best %' },
  { dataKey: 'pct__worst_choice', label: 'Avoids the worst %' },
  { dataKey: 'pct__elite_per90', label: 'Elite reads / 90' },
  { dataKey: 'pct__poor_per90', label: 'Avoids poor / 90' },
];

// ── Core stat definitions per tab ─────────────────────────────────────────────

type StatDef = { col: keyof DecisionQualityRow; label: string };

const CORE_STATS: Record<StatViewMode, StatDef[]> = {
  raw: [
    { col: 'score', label: 'Score' },
    { col: 'avg_miss_cost', label: 'Avg miss cost' },
    { col: 'value_impact', label: 'Value Impact' },
  ],
  per90: [
    { col: 'elite_per90', label: 'Elite reads / 90' },
    { col: 'poor_per90', label: 'Poor reads / 90' },
  ],
  percentages: [
    { col: 'accuracy_pct', label: 'Picks the best %' },
    { col: 'worst_choice_pct', label: 'Worst choice %' },
  ],
};

// ── Custom radar tooltip ──────────────────────────────────────────────────────

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
  if (typeof v === 'number') return v.toFixed(2);
  return String(v);
}

// ── Stat row with inline "?" tooltip ─────────────────────────────────────────

function StatRow({ label, value }: { label: string; value: string }) {
  const [hovered, setHovered] = useState(false);
  const description = TOOLTIP_DESCRIPTIONS[label] ?? 'No description available.';

  return (
    <div className="relative flex justify-between items-center gap-2">
      <div className="flex items-center gap-2 min-w-0">
        <span className="text-xs font-semibold text-[var(--text-muted)]">
          {label}
        </span>
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
        {hovered && (
          <div
            role="tooltip"
            className="absolute bottom-[calc(100%+8px)] left-0 max-w-[240px] bg-[var(--surface)] rounded-[10px] px-3.5 py-2.5 z-[60] pointer-events-none"
            style={{ border: `1px solid ${DQ_COLOR}33`, borderLeft: `3px solid ${DQ_COLOR}`, boxShadow: 'var(--shadow-lg)' }}
          >
            <p className="font-display text-[10px] font-bold mb-1.5 tracking-wide" style={{ color: DQ_COLOR }}>
              {label}
            </p>
            <p className="text-[11px] text-[var(--text-muted)] leading-[1.55]">
              {description}
            </p>
          </div>
        )}
      </div>
      <span className="font-mono text-[13px] font-bold shrink-0" style={{ color: DQ_COLOR }}>
        {value}
      </span>
    </div>
  );
}

// ── Simple static radar axis tick (no hover) ──────────────────────────────────

function SimpleRadarTick({ x = 0, y = 0, cx = 0, cy = 0, payload }: any) {
  if (!payload) return null;

  const dx = x - cx;
  const dy = y - cy;
  const length = Math.sqrt(dx * dx + dy * dy) || 1;
  const offset = 34; // push outward
  const nx = x + (dx / length) * offset;
  const ny = y + (dy / length) * offset;

  return (
    <text
      x={nx}
      y={ny}
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

// ── Main exported component ───────────────────────────────────────────────────

export interface DQCardProps {
  playerName: string;
  teamName?: string;
  row: DecisionQualityRow;
  mode: StatViewMode;
  onModeChange: (m: StatViewMode) => void;
}

export default function DecisionQualitySection({
  playerName, row, mode, onModeChange,
}: DQCardProps) {
  const lastName = playerName.split(' ').at(-1) ?? playerName;
  const [hoveredTitle, setHoveredTitle] = useState(false);

  // Build radar data
  const radarData = RADAR_AXES.map(ax => ({
    stat: ax.label,
    value: (row[ax.dataKey] as number) ?? 0,
  }));

  const statList = CORE_STATS[mode];

  const renderTick = (props: any) => <SimpleRadarTick {...props} />;

  return (
    <section className="max-w-[1200px] mx-auto px-6 pb-12">

      {/* Section header */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <div>
          <h2 className="font-display font-black text-xl text-[var(--text)] mb-1">
            Decision Quality
          </h2>
          <p className="text-xs text-[var(--text-muted)]">
            Selected player metrics — {playerName}
          </p>
        </div>
        <StatViewToggle mode={mode} onChange={onModeChange} />
      </div>

      {/* Single card — sits in first cell of the 2-col grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div
          className="bg-[var(--surface)] border border-[var(--border)] rounded-[var(--radius-lg)] p-6 shadow-[var(--shadow)]"
          style={{ borderTop: `3px solid ${DQ_COLOR}` }}
        >
          {/* Card header: label+tooltip left (matches SpaceControl IndexLabelWithTooltip), index right */}
          <div className="flex justify-between items-start mb-2">
            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-1.5">
                <span className="font-display text-[10px] tracking-[0.12em] uppercase font-bold" style={{ color: DQ_COLOR }}>
                  Decision Quality
                </span>

                <div className="relative">
                  <button
                    aria-label="Description for Decision Quality"
                    onMouseEnter={() => setHoveredTitle(true)}
                    onMouseLeave={() => setHoveredTitle(false)}
                    style={{
                      width: 14, height: 14, borderRadius: '50%',
                      border: `1px solid ${hoveredTitle ? DQ_COLOR : 'rgba(0,0,0,0.15)'}`,
                      background: hoveredTitle ? `${DQ_COLOR}18` : 'rgba(0,0,0,0.03)',
                      color: hoveredTitle ? DQ_COLOR : 'rgba(0,0,0,0.35)',
                      fontSize: 8, fontWeight: 700, fontFamily: 'Inter, sans-serif',
                      cursor: 'help', display: 'flex', alignItems: 'center', justifyContent: 'center',
                      transition: 'all 0.12s', padding: 0, lineHeight: 1, flexShrink: 0,
                    }}
                  >
                    ?
                  </button>

                  {hoveredTitle && (
                    <div
                      role="tooltip"
                      style={{
                        position: 'absolute', top: 'calc(100% + 6px)', left: 0,
                        minWidth: 220, maxWidth: 280, zIndex: 60,
                        background: 'var(--surface2)',
                        border: `1px solid ${DQ_COLOR}44`,
                        borderLeft: `3px solid ${DQ_COLOR}`,
                        borderRadius: 10, padding: '12px 14px',
                        pointerEvents: 'none',
                        boxShadow: '0 8px 24px rgba(0,0,0,0.18)',
                      }}
                    >
                      <p style={{ fontFamily: 'Inter, sans-serif', fontSize: 10, fontWeight: 700, color: DQ_COLOR, marginBottom: 6, letterSpacing: '0.04em' }}>
                        Decision Quality
                      </p>
                      <p style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.6, margin: 0 }}>
                        {TOOLTIP_DESCRIPTIONS['Decision Quality'] ?? 'No description available.'}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </div>
            <div className="text-right">
              <div className="font-display text-[9px] tracking-[0.1em] uppercase text-[var(--text-dim)]">Index</div>
              <div className="font-display font-black text-[26px] leading-none" style={{ color: DQ_COLOR }}>
                {row.DQ_index != null ? row.DQ_index.toFixed(1) : '—'}
              </div>
            </div>
          </div>

          {/* Radar — percentile axes 0–100 */}
          <ResponsiveContainer width="100%" height={440}>
            <RadarChart data={radarData} margin={{ top: 28, right: 50, bottom: 40, left: 50 }}>
              <PolarGrid stroke="rgba(0,0,0,0.08)" />
              <PolarAngleAxis dataKey="stat" tick={renderTick} />
              <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
              <Tooltip content={<RadarTooltip />} />
              <Radar
                name={lastName}
                dataKey="value"
                stroke={DQ_COLOR} fill={DQ_COLOR} fillOpacity={0.15} strokeWidth={2}
                dot={{ fill: DQ_COLOR, r: 3, strokeWidth: 0 }}
                activeDot={{ r: 5, fill: DQ_COLOR, stroke: '#fff', strokeWidth: 1.5 }}
              />
              <Legend
                formatter={() => <span className="text-[var(--text-muted)] text-[11px]">Percentile rank (0–100)</span>}
                wrapperStyle={{ position: 'relative', top: 20 }}
              />
            </RadarChart>
          </ResponsiveContainer>

          {/* Core stats card — tooltips on "?" only */}
          <div className="mt-4 bg-[var(--surface2)] rounded-xl p-4">
            <p className="font-display text-[9px] tracking-[0.1em] uppercase text-[var(--text-dim)] mb-3">
              Core stats
            </p>
            {statList.length === 0 ? (
              <div className="bg-[var(--bg)] p-3 rounded-md border border-[var(--border)]">
                <p className="text-[11px] text-[var(--text-muted)] leading-[1.5]">
                  No {mode} statistics in this tab.
                </p>
              </div>
            ) : (
              <div className="flex flex-col gap-2">
                {statList.map(s => {
                  const raw = row[s.col];
                  const val = (s.col === 'value_impact' || s.col === 'avg_miss_cost') && typeof raw === 'number'
                    ? raw * 100
                    : raw;
                  return <StatRow key={s.col} label={s.label} value={fmt(val)} />;
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

// ── Dual stat row (source vs compare) ────────────────────────────────────────

const C_SOURCE = '#0891b2';
const C_COMPARE = '#df4d14';

function DualStatRow({
  label,
  srcVal,
  cmpVal,
}: {
  label: string;
  srcVal: unknown;
  cmpVal: unknown;
}) {
  const [hovered, setHovered] = useState(false);
  const description = TOOLTIP_DESCRIPTIONS[label] ?? 'No description available.';

  const sourceValue = fmt(srcVal);
  const compareValue = fmt(cmpVal);

  return (
    <div className="relative grid gap-2 items-center" style={{ gridTemplateColumns: '1fr auto auto' }}>
      {/* Label + ? tooltip */}
      <div className="flex items-center gap-1.5 min-w-0">
        <span className="text-[11px] font-semibold text-[var(--text-muted)]">
          {label}
        </span>
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
        >?</button>
        {hovered && (
          <div role="tooltip" className="absolute bottom-[calc(100%+8px)] left-0 max-w-[240px] bg-[var(--surface)] rounded-[10px] px-3.5 py-2.5 z-[60] pointer-events-none"
            style={{ border: `1px solid ${DQ_COLOR}33`, borderLeft: `3px solid ${DQ_COLOR}`, boxShadow: 'var(--shadow-lg)' }}
          >
            <p className="font-display text-[10px] font-bold mb-1.5 tracking-wide" style={{ color: DQ_COLOR }}>
              {label}
            </p>
            <p className="text-[11px] text-[var(--text-muted)] leading-[1.55]">
              {description}
            </p>
          </div>
        )}
      </div>

      {/* Source value */}
      <span className="font-mono text-xs font-bold text-right min-w-[52px]" style={{ color: '#000' }}>
        {sourceValue}
      </span>

      <span
        className="font-mono text-xs font-bold text-right min-w-[52px]"
        style={{ color: '#000' }}
      >
        {compareValue}
      </span>
    </div>
  );
}

// ── DQ radar card for SimilarPlayers ─────────────────────────────────────────

export function DQCompareRadar({
  sourceRow,
  compareRow,
  sourceName,
  compareName,
  mode = 'raw',
}: {
  sourceRow: DecisionQualityRow;
  compareRow: DecisionQualityRow;
  sourceName: string;
  compareName: string;
  mode?: StatViewMode;
}) {
  const [hoveredTitle, setHoveredTitle] = useState(false);

  const sName = sourceName.trim().split(' ').pop() ?? sourceName;
  const cName = compareName.trim().split(' ').pop() ?? compareName;

  const radarData = RADAR_AXES.map(ax => ({
    stat: ax.label,
    [sName]: (sourceRow[ax.dataKey] as number) ?? 0,
    [cName]: (compareRow[ax.dataKey] as number) ?? 0,
  }));

  const statList = CORE_STATS[mode];

  return (
    <div
      className="bg-[var(--surface)] border border-[var(--border)] rounded-[var(--radius-lg)] p-6 shadow-[var(--shadow)]"
      style={{ borderTop: `3px solid ${DQ_COLOR}` }}
    >

      {/* Header: label left, indices right */}
      <div className="flex justify-between items-start mb-2">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-1.5">
            <span className="font-display text-[10px] tracking-[0.12em] uppercase font-bold" style={{ color: DQ_COLOR }}>
              Decision Quality
            </span>

            <div className="relative">
              <button
                aria-label="Description for Decision Quality"
                onMouseEnter={() => setHoveredTitle(true)}
                onMouseLeave={() => setHoveredTitle(false)}
                style={{
                  width: 14, height: 14, borderRadius: '50%',
                  border: `1px solid ${hoveredTitle ? DQ_COLOR : 'rgba(0,0,0,0.15)'}`,
                  background: hoveredTitle ? `${DQ_COLOR}18` : 'rgba(0,0,0,0.03)',
                  color: hoveredTitle ? DQ_COLOR : 'rgba(0,0,0,0.35)',
                  fontSize: 8, fontWeight: 700, fontFamily: 'Inter, sans-serif',
                  cursor: 'help', display: 'flex', alignItems: 'center', justifyContent: 'center',
                  transition: 'all 0.12s', padding: 0, lineHeight: 1, flexShrink: 0,
                }}
              >
                ?
              </button>

              {hoveredTitle && (
                <div
                  role="tooltip"
                  style={{
                    position: 'absolute', top: 'calc(100% + 6px)', left: 0,
                    minWidth: 220, maxWidth: 280, zIndex: 60,
                    background: 'var(--surface2)',
                    border: `1px solid ${DQ_COLOR}44`,
                    borderLeft: `3px solid ${DQ_COLOR}`,
                    borderRadius: 10, padding: '12px 14px',
                    pointerEvents: 'none',
                    boxShadow: '0 8px 24px rgba(0,0,0,0.18)',
                  }}
                >
                  <p style={{ fontFamily: 'Inter, sans-serif', fontSize: 10, fontWeight: 700, color: DQ_COLOR, marginBottom: 6, letterSpacing: '0.04em' }}>
                    Decision Quality
                  </p>
                  <p style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.6, margin: 0 }}>
                    {TOOLTIP_DESCRIPTIONS['Decision Quality'] ?? 'No description available.'}
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
        <div className="flex gap-3 items-baseline">
          <div className="text-right">
            <div className="font-mono text-[9px] tracking-[0.1em] uppercase text-[var(--text-dim)]">Index</div>
            <div className="font-mono text-lg font-black leading-none">
              <span style={{ color: C_SOURCE }}>{sourceRow.DQ_index?.toFixed(1) ?? '—'}</span>
              <span className="text-[var(--text-dim)] text-xs mx-1">vs</span>
              <span style={{ color: C_COMPARE }}>{compareRow.DQ_index?.toFixed(1) ?? '—'}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Dual radar — static axis labels */}
      <ResponsiveContainer width="100%" height={440}>
        <RadarChart data={radarData} margin={{ top: 28, right: 50, bottom: 40, left: 50 }}>
          <PolarGrid stroke="rgba(0,0,0,0.06)" />
          <PolarAngleAxis dataKey="stat" tick={<SimpleRadarTick />} />
          <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
          <Tooltip content={<RadarTooltip />} />
          <Radar name={sName} dataKey={sName}
            stroke={C_SOURCE} fill={C_SOURCE} fillOpacity={0.12} strokeWidth={2}
            dot={{ fill: C_SOURCE, r: 3, strokeWidth: 0 }}
            activeDot={{ r: 5, fill: C_SOURCE, stroke: '#fff', strokeWidth: 1.5 }}
          />
          <Radar name={cName} dataKey={cName}
            stroke={C_COMPARE} fill={C_COMPARE} fillOpacity={0.12} strokeWidth={2}
            dot={{ fill: C_COMPARE, r: 3, strokeWidth: 0 }}
            activeDot={{ r: 5, fill: C_COMPARE, stroke: '#fff', strokeWidth: 1.5 }}
          />
          <Legend
            formatter={(v: string) => (
              <span className="text-[10px] font-display" style={{ color: v === sName ? C_SOURCE : C_COMPARE }}>{v}</span>
            )}
            wrapperStyle={{ position: 'relative', top: 20 }}
          />
        </RadarChart>
      </ResponsiveContainer>

      {/* Core stats comparison */}
      <div className="mt-4 bg-[var(--surface2)] rounded-xl p-4">

        {/* Column headers */}
        <div className="grid gap-2 pb-1 mb-1 border-b border-[var(--border)]" style={{ gridTemplateColumns: '1fr auto auto' }}>
          <span className="font-display text-[9px] text-[var(--text-dim)] uppercase" style={{ fontFamily: 'Inter, sans-serif' }}>Core Stats</span>
          <span className="font-display text-[9px] uppercase text-right min-w-[52px]" style={{ color: C_SOURCE, fontFamily: 'Inter, sans-serif' }}>{sName}</span>
          <span className="font-display text-[9px] uppercase text-right min-w-[52px]" style={{ color: C_COMPARE, fontFamily: 'Inter, sans-serif' }}>{cName}</span>
        </div>

        {statList.length === 0 ? (
          <p className="text-[11px] text-[var(--text-muted)]">No {mode} stats for Decision Quality.</p>
        ) : (
          <div className="flex flex-col gap-1.5">
            {statList.map(s => {
              const scale = (s.col === 'value_impact' || s.col === 'avg_miss_cost') ? 100 : 1;
              const sv = sourceRow[s.col];
              const cv = compareRow[s.col];
              return (
                <DualStatRow
                  key={s.col}
                  label={s.label}
                  srcVal={typeof sv === 'number' ? sv * scale : sv}
                  cmpVal={typeof cv === 'number' ? cv * scale : cv}
                />
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}