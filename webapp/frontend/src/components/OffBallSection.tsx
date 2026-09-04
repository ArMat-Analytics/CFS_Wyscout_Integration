import { useState } from 'react';
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer, Tooltip, Legend } from 'recharts';
import { type OffBallRow } from '../hooks/useOffBallMovement';

import { TOOLTIP_DESCRIPTIONS } from '../data/tooltip';
import { StatViewToggle, type StatViewMode } from './SpaceControlSection';

const OB_COLOR = '#9cc507';
const C_SOURCE = '#0891b2';
const C_COMPARE = '#df4d14';

// ── Custom Tick ───────────────────────────────────────────────────────────────

function SimpleRadarTick(props: any) {
  const { payload, x, y, cx, cy } = props;
  const dx = x - cx;
  const dy = y - cy;
  const dist = Math.sqrt(dx * dx + dy * dy);
  const offset = 34;
  const nx = dist === 0 ? x : x + (dx / dist) * offset;
  const ny = dist === 0 ? y : y + (dy / dist) * offset;
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

// ── Custom Tooltip ────────────────────────────────────────────────────────────

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

// ── Core Stats Mapping ────────────────────────────────────────────────────────

type StatDef = { col: keyof OffBallRow; label: string };

const CORE_STATS: Record<StatViewMode, StatDef[]> = {
  raw: [
    { col: 'xepv_mean', label: 'xEPV mean' },
  ],
  per90: [
    { col: 'urs_per90', label: 'URS /90' },
    { col: 'off_ball_potential_per90', label: 'Off-Ball Potential /90' },
  ],
  percentages: [
    { col: 'capitalization_rate', label: 'Capitalisation rate' },
  ],
};


// ── Component: Single Player ──────────────────────────────────────────────────

interface OffBallSectionProps {
  playerName: string;
  row: OffBallRow;
  mode: StatViewMode;
  onModeChange: (m: StatViewMode) => void;
}

export default function OffBallSection({ playerName, row, mode, onModeChange }: OffBallSectionProps) {
  const [hoveredTitle, setHoveredTitle] = useState(false);
  const radarData = [
    { stat: 'Off-Ball Potential /90', value: row.potential_pct_within_role ?? 0 },
    { stat: 'xEPV mean', value: row.xepv_mean_pct_within_role ?? 0 },
    { stat: 'Latency (1 − Cap.)', value: row.latency_pct_within_role ?? 0 },
  ];

  return (
    <section className="max-w-[1200px] mx-auto px-6 pb-12 mt-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
        <div>
          <h2 className="font-display font-black text-xl text-[var(--text)] mb-1">Off-Ball Movement</h2>
          <p className="text-xs text-[var(--text-muted)]">Selected player metrics — {playerName}</p>
        </div>
        <StatViewToggle mode={mode} onChange={onModeChange} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        
        {/* Radar Card */}
        <div className="relative bg-[var(--surface)] border border-[var(--border)] rounded-[var(--radius-lg)] p-6 shadow-[var(--shadow)]" style={{ borderTop: `3px solid ${OB_COLOR}` }}>
          
          <div className="flex justify-between items-start mb-2">
            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-1.5">
                <span className="font-display text-[10px] tracking-[0.12em] uppercase font-bold" style={{ color: OB_COLOR }}>Uncapitalized Run Score</span>
                <div className="relative">
                  <button
                    aria-label="Description for Uncapitalized Run Score"
                    onMouseEnter={() => setHoveredTitle(true)}
                    onMouseLeave={() => setHoveredTitle(false)}
                    style={{
                      width: 14, height: 14, borderRadius: '50%',
                      border: `1px solid ${hoveredTitle ? OB_COLOR : 'rgba(0,0,0,0.15)'}`,
                      background: hoveredTitle ? `${OB_COLOR}18` : 'rgba(0,0,0,0.03)',
                      color: hoveredTitle ? OB_COLOR : 'rgba(0,0,0,0.35)',
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
                        border: `1px solid ${OB_COLOR}44`,
                        borderLeft: `3px solid ${OB_COLOR}`,
                        borderRadius: 10, padding: '12px 14px',
                        pointerEvents: 'none',
                        boxShadow: '0 8px 24px rgba(0,0,0,0.18)',
                      }}
                    >
                      <p style={{ fontFamily: 'Inter, sans-serif', fontSize: 10, fontWeight: 700, color: OB_COLOR, marginBottom: 6, letterSpacing: '0.04em' }}>
                        Uncapitalized Run Score
                      </p>
                      <p style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.6, margin: 0 }}>
                        {TOOLTIP_DESCRIPTIONS['Uncapitalized Run Score'] || 'Quality of decisions relative to available space and pressure.'}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </div>
            
            <div className="text-right">
              <div className="font-display text-[9px] tracking-[0.1em] uppercase text-[var(--text-dim)]">INDEX</div>
              <div className="font-display font-black text-[26px] leading-none" style={{ color: OB_COLOR }}>
                {row.urs_pct_within_role?.toFixed(1) ?? '—'}
              </div>
            </div>
          </div>

          <div style={{ width: '100%', height: 440 }}>
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart data={radarData} margin={{ top: 28, right: 50, bottom: 40, left: 50 }}>
                <PolarGrid stroke="rgba(0,0,0,0.08)" />
                <PolarAngleAxis dataKey="stat" tick={<SimpleRadarTick />} />
                <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
                <Radar
                  name={playerName}
                  dataKey="value"
                  stroke={OB_COLOR}
                  fill={OB_COLOR}
                  fillOpacity={0.12}
                  strokeWidth={2}
                  dot={{ r: 3, strokeWidth: 0, fill: OB_COLOR }}
                />
                <Tooltip content={<RadarTooltip />} />
                <Legend
                  formatter={() => <span className="text-[var(--text-muted)] text-[11px]">Percentile rank (0–100)</span>}
                  wrapperStyle={{ position: 'relative', top: 20 }}
                />
              </RadarChart>
            </ResponsiveContainer>
          </div>

          {/* Core stats panel */}
          <div className="mt-4 bg-[var(--surface2)] rounded-xl p-4">
             <p className="font-display text-[9px] tracking-[0.1em] uppercase text-[var(--text-dim)] mb-3">Core stats</p>
            {CORE_STATS[mode].length === 0 ? (
              <div className="bg-[var(--bg)] p-3 rounded-md border border-[var(--border)]">
                <p className="text-[11px] text-[var(--text-muted)] leading-[1.5]">
                  No metrics available for this view.
                </p>
              </div>
            ) : (
              <div className="flex flex-col gap-2">
                {CORE_STATS[mode].map(s => {
                  let val = row[s.col];
                  if (s.col === 'capitalization_rate' && typeof val === 'number') val *= 100;
                  return <StatRow key={s.col} label={s.label} val={val} color={OB_COLOR} />;
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

// ── Component: Comparison Radar ───────────────────────────────────────────────

interface OBCompareRadarProps {
  sourceRow: OffBallRow;
  compareRow: OffBallRow;
  sourceName: string;
  compareName: string;
  mode: StatViewMode;
}

export function OBCompareRadar({ sourceRow, compareRow, sourceName, compareName, mode }: OBCompareRadarProps) {
  const [hoveredTitle, setHoveredTitle] = useState(false);
  const sName = sourceName.trim().split(' ').pop() ?? sourceName;
  const cName = compareName.trim().split(' ').pop() ?? compareName;

  const radarData = [
    { stat: 'Off-Ball Potential /90', s: sourceRow.potential_pct_within_role ?? 0, c: compareRow.potential_pct_within_role ?? 0 },
    { stat: 'xEPV mean', s: sourceRow.xepv_mean_pct_within_role ?? 0, c: compareRow.xepv_mean_pct_within_role ?? 0 },
    { stat: 'Latency (1 − Cap.)', s: sourceRow.latency_pct_within_role ?? 0, c: compareRow.latency_pct_within_role ?? 0 },
  ];

  return (
    <div className="relative bg-[var(--surface)] border border-[var(--border)] rounded-[var(--radius-lg)] p-6 shadow-[var(--shadow)]" style={{ borderTop: `3px solid ${OB_COLOR}` }}>
      <div className="flex justify-between items-start mb-2">
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-1.5">
              <span className="font-display text-[10px] tracking-[0.12em] uppercase font-bold" style={{ color: OB_COLOR }}>Uncapitalized Run Score</span>
                <div className="relative">
                  <button
                    aria-label="Description for Uncapitalized Run Score"
                    onMouseEnter={() => setHoveredTitle(true)}
                    onMouseLeave={() => setHoveredTitle(false)}
                    style={{
                      width: 14, height: 14, borderRadius: '50%',
                      border: `1px solid ${hoveredTitle ? OB_COLOR : 'rgba(0,0,0,0.15)'}`,
                      background: hoveredTitle ? `${OB_COLOR}18` : 'rgba(0,0,0,0.03)',
                      color: hoveredTitle ? OB_COLOR : 'rgba(0,0,0,0.35)',
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
                        border: `1px solid ${OB_COLOR}44`,
                        borderLeft: `3px solid ${OB_COLOR}`,
                        borderRadius: 10, padding: '12px 14px',
                        pointerEvents: 'none',
                        boxShadow: '0 8px 24px rgba(0,0,0,0.18)',
                      }}
                    >
                      <p style={{ fontFamily: 'Inter, sans-serif', fontSize: 10, fontWeight: 700, color: OB_COLOR, marginBottom: 6, letterSpacing: '0.04em' }}>
                        Uncapitalized Run Score
                      </p>
                      <p style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.6, margin: 0 }}>
                        {TOOLTIP_DESCRIPTIONS['Uncapitalized Run Score'] || 'Quality of decisions relative to available space and pressure.'}
                      </p>
                    </div>
                  )}
                </div>
            </div>
          </div>
          
          <div className="text-right">
            <div className="font-display text-[9px] tracking-[0.1em] uppercase text-[var(--text-dim)]">Index</div>
            <div className="font-mono text-lg font-black leading-none">
              <span style={{ color: C_SOURCE }}>{sourceRow.urs_pct_within_role?.toFixed(1) ?? '—'}</span>
              <span className="text-[var(--text-dim)] text-xs mx-1">vs</span>
              <span style={{ color: C_COMPARE }}>{compareRow.urs_pct_within_role?.toFixed(1) ?? '—'}</span>
            </div>
          </div>
        </div>

        <div style={{ width: '100%', height: 440 }}>
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart data={radarData} margin={{ top: 28, right: 50, bottom: 40, left: 50 }}>
              <PolarGrid stroke="rgba(0,0,0,0.06)" />
              <PolarAngleAxis dataKey="stat" tick={<SimpleRadarTick />} />
              <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
              <Radar
                name={sName}
                dataKey="s"
                stroke={C_SOURCE}
                fill={C_SOURCE}
                fillOpacity={0.12}
                strokeWidth={2}
                dot={{ r: 3, strokeWidth: 0, fill: C_SOURCE }}
                activeDot={{ r: 5, fill: C_SOURCE, stroke: '#fff', strokeWidth: 1.5 }}
              />
              <Radar
                name={cName}
                dataKey="c"
                stroke={C_COMPARE}
                fill={C_COMPARE}
                fillOpacity={0.12}
                strokeWidth={2}
                dot={{ r: 3, strokeWidth: 0, fill: C_COMPARE }}
                activeDot={{ r: 5, fill: C_COMPARE, stroke: '#fff', strokeWidth: 1.5 }}
              />
              <Tooltip content={<RadarTooltip />} />
              <Legend
                formatter={(v: string) => (
                  <span className="text-[10px] font-display" style={{ color: v === sName ? C_SOURCE : C_COMPARE }}>{v}</span>
                )}
                wrapperStyle={{ position: 'relative', top: 20 }}
              />
            </RadarChart>
          </ResponsiveContainer>
        </div>

        <div className="mt-4 bg-[var(--surface2)] rounded-xl p-4">
          <div className="grid gap-2 pb-1 mb-1 border-b border-[var(--border)]" style={{ gridTemplateColumns: '1fr auto auto' }}>
            <span className="font-display text-[9px] text-[var(--text-dim)] uppercase">Core Stats</span>
            <span className="font-display text-[9px] uppercase text-right min-w-[52px]" style={{ color: C_SOURCE }}>{sName}</span>
            <span className="font-display text-[9px] uppercase text-right min-w-[52px]" style={{ color: C_COMPARE }}>{cName}</span>
          </div>
          {CORE_STATS[mode].length === 0 ? (
            <div className="bg-[var(--bg)] p-3 rounded-md border border-[var(--border)]">
              <p className="text-[11px] text-[var(--text-muted)] leading-[1.5]">
                No metrics available for this view.
              </p>
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              {CORE_STATS[mode].map(s => {
                let vS = sourceRow[s.col];
                let vC = compareRow[s.col];
                if (s.col === 'capitalization_rate') {
                  if (typeof vS === 'number') vS *= 100;
                  if (typeof vC === 'number') vC *= 100;
                }
                return <DualStatRow key={s.col} label={s.label} valS={vS} valC={vC} />;
              })}
            </div>
          )}
        </div>
      </div>
  );
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function StatRow({ label, val, color }: { label: string; val: string | number | null | undefined; color: string }) {
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
      <span className="font-mono font-bold text-[13px] shrink-0" style={{ color }}>
        {val != null ? Number(val).toFixed(2) : '—'}
      </span>
    </div>
  );
}

function DualStatRow({ label, valS, valC }: { label: string; valS: string | number | null | undefined; valC: string | number | null | undefined }) {
  const [hovered, setHovered] = useState(false);
  const description = TOOLTIP_DESCRIPTIONS[label] ?? 'No description available.';

  return (
    <div className="relative grid gap-2 items-center" style={{ gridTemplateColumns: '1fr auto auto' }}>
      <div className="flex items-center gap-2 min-w-0">
        <span className="text-xs font-semibold text-[var(--text-muted)] truncate">
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
            style={{ border: `1px solid ${OB_COLOR}33`, borderLeft: `3px solid ${OB_COLOR}`, boxShadow: 'var(--shadow-lg)' }}
          >
            <p className="font-display text-[10px] font-bold mb-1.5 tracking-wide" style={{ color: OB_COLOR }}>
              {label}
            </p>
            <p className="text-[11px] text-[var(--text-muted)] leading-[1.55]">
              {description}
            </p>
          </div>
        )}
      </div>
      <span className="font-mono text-[13px] font-bold text-right min-w-[52px]" style={{ color: 'var(--text)' }}>
        {valS != null ? Number(valS).toFixed(2) : '—'}
      </span>
      <span className="font-mono text-[13px] font-bold text-right min-w-[52px]" style={{ color: 'var(--text)' }}>
        {valC != null ? Number(valC).toFixed(2) : '—'}
      </span>
    </div>
  );
}
