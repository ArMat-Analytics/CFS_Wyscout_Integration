import { useState, useId } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import { getFlagUrl, formatMarketValue, getMarketTrendArrow } from '../utils';
import {
  useSimilarPlayers, usePlayerSpaceControl,
  type SpaceControlIndex, type SpaceControlAggregated,
} from '../hooks/useSpaceControl';
import { StatViewToggle, type StatViewMode } from '../components/SpaceControlSection';
import { TOOLTIP_DESCRIPTIONS } from '../data/tooltip';
import { usePlayerDecisionQuality } from '../hooks/useDecisionQuality';
import { DQCompareRadar } from '../components/DecisionQualitySection';
import { usePlayerOffBallMovement } from '../hooks/useOffBallMovement';
import { OBCompareRadar } from '../components/OffBallSection';

// ── Palette ───────────────────────────────────────────────────────────────────

const C_SOURCE = '#0891b2';
const C_SIMILAR = '#df4d14';

// ── Radar dimension definitions ───────────────────────────────────────────────

const RADAR_DEFS = [
  {
    key: 'PROGRESSION', label: 'Progression', color: '#16a34a',
    axes: [
      { k: 'pct__lb_geom_per90' as keyof SpaceControlIndex, label: 'LB Geom /90' },
      { k: 'pct__lb_quality_per90' as keyof SpaceControlIndex, label: 'LB Quality /90' },
      { k: 'pct__lb_epv_per90' as keyof SpaceControlIndex, label: 'LB EPV /90' },
      { k: 'pct__successful_hull_penetrations_per90' as keyof SpaceControlIndex, label: 'Hull Penetr. /90' },
      { k: 'pct__defenders_bypassed_mean' as keyof SpaceControlIndex, label: 'Def. Bypassed Avg' },
    ],
  },
  {
    key: 'DANGEROUSNESS', label: 'Dangerousness', color: '#dc2626',
    axes: [
      { k: 'pct__epv_penetration_per90' as keyof SpaceControlIndex, label: 'EPV Penetr. /90' },
      { k: 'pct__epv_inside_circ_per90' as keyof SpaceControlIndex, label: 'EPV In-Circ /90' },
      { k: 'pct__epv_exit_per90' as keyof SpaceControlIndex, label: 'EPV Exit /90' },
      { k: 'pct__epv_outside_circ_per90' as keyof SpaceControlIndex, label: 'EPV Out-Circ /90' },
    ],
  },
  {
    key: 'RECEPTION', label: 'Reception', color: '#2563eb',
    axes: [
      { k: 'pct__between_lines_pct' as keyof SpaceControlIndex, label: 'Between Lines %' },
      { k: 'pct__successful_hull_exits_per90' as keyof SpaceControlIndex, label: 'Hull Exits /90' },
      { k: 'pct__pressure_resistance_pct' as keyof SpaceControlIndex, label: 'Press. Resist %' },
    ],
  },
  {
    key: 'GRAVITY', label: 'Gravity', color: '#d97706',
    axes: [
      { k: 'pct__gravity_proximity_pct' as keyof SpaceControlIndex, label: 'Space Attraction %' },
      { k: 'pct__gravity_hull_pct' as keyof SpaceControlIndex, label: 'Gravity Hull %' },
      { k: 'pct__gravity_abs_m' as keyof SpaceControlIndex, label: 'Def. Pull |m|' },
    ],
  },
] as const;

// ── Mother stat definitions per dimension × mode ──────────────────────────────

type StatDef = { col: keyof SpaceControlAggregated; label: string };

const MOTHER: Record<string, Record<StatViewMode, StatDef[]>> = {
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
      { col: 'epv_inside_circ_sum', label: 'EPV In-Circ (sum)' },
      { col: 'epv_exit_sum', label: 'EPV Exit (sum)' },
      { col: 'epv_outside_circ_sum', label: 'EPV Out-Circ (sum)' },
    ],
    per90: [
      { col: 'epv_added_per90', label: 'EPV Added /90' },
      { col: 'epv_penetration_per90', label: 'EPV Penetr. /90' },
      { col: 'epv_inside_circ_per90', label: 'EPV In-Circ /90' },
      { col: 'epv_exit_per90', label: 'EPV Exit /90' },
      { col: 'epv_outside_circ_per90', label: 'EPV Out-Circ /90' },
    ],
    percentages: [],
  },
  RECEPTION: {
    raw: [
      { col: 'between_lines_n', label: 'Block Receipts (n)' },
      { col: 'pressure_resistance_n', label: 'Press. Resist (n)' },
      { col: 'inside_circ_n', label: 'In-Circ (n)' },
    ],
    per90: [
      { col: 'between_lines_per90', label: 'Between Lines /90' },
      { col: 'successful_hull_exits_per90', label: 'Hull Exits /90' },
      { col: 'inside_circ_per90', label: 'In-Circ /90' },
    ],
    percentages: [
      { col: 'between_lines_pct', label: 'Between Lines %' },
      { col: 'hull_exit_pct', label: 'Hull Exits %' },
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
      { col: 'gravity_hull_pct', label: 'Gravity Hull %' },
    ],
  },
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(v: unknown): string {
  if (v == null) return '—';
  if (typeof v === 'string' && /^-?\d+,\d+$/.test(v)) {
    v = parseFloat(v.replace(',', '.'));
  }
  if (typeof v === 'number') return Math.abs(v) < 10 ? v.toFixed(2) : v.toFixed(1);
  return String(v);
}

function ScoreBadge({ score }: { score?: number | null }) {
  if (score == null) return (
    <span className="font-mono font-bold text-[11px] py-0.5 px-2.5 rounded-full bg-[var(--surface2)] text-[var(--text-dim)]">
      N/A
    </span>
  );
  return (
    <span className="font-mono font-bold text-[11px] py-0.5 px-2.5 rounded-full bg-[var(--accent-dim)] text-[var(--accent)]">
      {score.toFixed(1)}% Sim
    </span>
  );
}

function ScoreBar({ score }: { score?: number | null }) {
  if (score == null) return <div className="w-full h-[3px] rounded-full bg-[var(--surface2)]" />;
  return (
    <div className="w-full h-[3px] rounded-full bg-[var(--surface2)] overflow-hidden">
      <div className="h-full bg-[var(--accent)]" style={{ width: `${score}%` }} />
    </div>
  );
}

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

// ── Custom PolarAngleAxis tick ─────────────────────────────────────────────────

interface CustomRadarTickProps {
  x?: number;
  y?: number;
  cx?: number;
  cy?: number;
  payload?: { value: string };
}

function CustomRadarTick({
  x = 0, y = 0, cx = 0, cy = 0,
  payload,
}: CustomRadarTickProps) {
  if (!payload) return null;

  const label = payload.value;

  const halfW = label.length * 3.5;

  const dx = x - cx;
  const dy = y - cy;
  const length = Math.sqrt(dx * dx + dy * dy) || 1;
  const offset = 34; // push outward
  const nx = x + (dx / length) * offset;
  const ny = y + (dy / length) * offset;

  return (
    <g>
      <rect
        x={nx - halfW}
        y={ny - 8}
        width={halfW * 2}
        height={16}
        fill="transparent"
      />
      <text
        x={nx}
        y={ny}
        textAnchor="middle"
        dominantBaseline="middle"
        fill="var(--text-muted)"
        fontSize={12}
        fontFamily="Inter, sans-serif"
        fontWeight={600}
        style={{ pointerEvents: 'none' }}
      >
        {label}
      </text>
    </g>
  );
}

// ── Dual mother stat row ──────────────────────────────────────────────────────

function DualMotherStatRow({
  label,
  sourceValue,
  similarValue,
  color,
  showExperimental,
}: {
  label: string;
  sourceValue: string;
  similarValue: string;
  color: string;
  showExperimental?: boolean;
}) {
  const [hovered, setHovered] = useState(false);
  const description = TOOLTIP_DESCRIPTIONS[label] ?? 'No description available.';

  return (
    <div className="relative grid gap-2 items-center" style={{ gridTemplateColumns: '1fr auto auto' }}>
      {/* Left cell: label + badges + "?" button + tooltip */}
      <div className="flex items-center gap-1.5 min-w-0">
        <span className="text-[11px] font-semibold text-[var(--text-muted)]">
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
            className="absolute bottom-[calc(100%+8px)] left-0 w-[240px] bg-[var(--surface)] rounded-[10px] px-3.5 py-2.5 z-[60] pointer-events-none"
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

      {/* Source value */}
      <span className="font-mono text-xs font-bold text-right min-w-[52px]" style={{ color: '#000' }}>
        {sourceValue}
      </span>

      {/* Similar value */}
      <span
        className="font-mono text-xs font-bold text-right min-w-[52px]"
        style={{ color: '#000' }}
      >
        {similarValue}
      </span>
    </div>
  );
}

// ── Overlapping dual radar card ───────────────────────────────────────────────

function DualRadarCard({
  def, sourceIdx, similarIdx, sourceAgg, similarAgg,
  sourceName, similarName, mode,
}: {
  def: typeof RADAR_DEFS[number];
  sourceIdx: SpaceControlIndex;
  similarIdx: SpaceControlIndex;
  sourceAgg: SpaceControlAggregated | null | undefined;
  similarAgg: SpaceControlAggregated | null | undefined;
  sourceName: string;
  similarName: string;
  mode: StatViewMode;
}) {
  const sName = sourceName.trim().split(' ').pop() || sourceName;
  const mName = similarName.trim().split(' ').pop() || similarName;
  const [hoveredTitle, setHoveredTitle] = useState(false);
  const isGravity = def.key === 'GRAVITY';
  const expDesc = TOOLTIP_DESCRIPTIONS['Experimental'];

  const radarData = def.axes.map(ax => ({
    stat: ax.label,
    [sName]: (sourceIdx[ax.k] as number) ?? 0,
    [mName]: (similarIdx[ax.k] as number) ?? 0,
  }));

  const statList = MOTHER[def.key]?.[mode] ?? [];

  const renderTick = (props: any) => <CustomRadarTick {...props} />;

  let emptyMessage =
    mode === 'per90'
      ? `No /90 stats for ${def.label}`
      : `No percentage stats for ${def.label}`;

  if (def.key === 'DANGEROUSNESS' && mode === 'percentages') {
    emptyMessage =
      "The Dangerousness index does not include percentage statistics because it is based on EPV (Expected Pass Value) and absolute penetration volumes. Being a probabilistic measure that calculates the net offensive 'weight' generated by a player, it is evaluated exclusively in absolute values (Raw) or scaled to playing time (Per 90).";
  } else if (def.key === 'GRAVITY' && mode === 'per90') {
    emptyMessage =
      "Gravity statistics are not calculated 'Per 90' because they measure the reaction and spatial deformation of the opposing defense (in meters or percentage deviations). Since it represents an average effect calculated every time the player has the ball, it reflects a constant 'magnetic pull' rather than a cumulative volume of actions over time.";
  }

  return (
    <div
      className="relative bg-[var(--surface)] border border-[var(--border)] rounded-[var(--radius-lg)] p-6 shadow-[var(--shadow)]"
      style={{ borderTop: `3px solid ${def.color}` }}
    >
      {/* Header: label left, index vs right — mirrors SpaceControl RadarCard */}
      <div className="flex justify-between items-start mb-2">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-1.5">
            <span className="font-display text-[10px] tracking-[0.12em] uppercase font-bold" style={{ color: def.color }}>
              {def.label}
            </span>

            <button
              aria-label={`Description for ${def.label}`}
              onMouseEnter={() => setHoveredTitle(true)}
              onMouseLeave={() => setHoveredTitle(false)}
              className="shrink-0 w-[15px] h-[15px] rounded-full text-[8px] font-bold font-display cursor-help flex items-center justify-center transition-all p-0 leading-none border"
              style={{
                borderColor: hoveredTitle ? 'rgba(0,0,0,0.3)' : 'rgba(0,0,0,0.12)',
                background: hoveredTitle ? 'rgba(0,0,0,0.06)' : 'rgba(0,0,0,0.02)',
                color: hoveredTitle ? 'rgba(0,0,0,0.6)' : 'rgba(0,0,0,0.35)',
              }}
            >
              ?
            </button>

            {hoveredTitle && (
              <div
                role="tooltip"
                className="absolute bottom-[calc(100%+8px)] left-0 w-[240px] bg-[var(--surface)] rounded-[10px] px-3.5 py-2.5 z-[60] pointer-events-none"
                style={{ border: `1px solid ${def.color}33`, borderLeft: `3px solid ${def.color}`, boxShadow: 'var(--shadow-lg)' }}
              >
                <p className="font-display text-[10px] font-bold mb-1.5 tracking-wide" style={{ color: def.color }}>
                  {def.label}
                </p>
                <p className="text-[11px] text-[var(--text-muted)] leading-[1.55]">
                  {TOOLTIP_DESCRIPTIONS[def.label] ?? `${def.label} index — percentile rank within macro-role (0–100).`}
                </p>
                {isGravity && (
                  <>
                    <div className="mt-2 mb-1">
                      <span className="inline-flex items-center gap-1 rounded px-2 py-0.75 text-[9px] font-bold uppercase tracking-wide" style={{ color: def.color, backgroundColor: `${def.color}15` }}>
                        Experimental
                      </span>
                    </div>
                    <p className="text-[11px] text-[var(--text-muted)] leading-[1.55]">
                      {expDesc}
                    </p>
                  </>
                )}
              </div>
            )}
          </div>
        </div>

        {(['idx__PROGRESSION', 'idx__DANGEROUSNESS', 'idx__RECEPTION', 'idx__GRAVITY'] as (keyof SpaceControlIndex)[])
          .filter(k => k === `idx__${def.key}`)
          .map(k => (
            <div key={String(k)} className="text-right">
              <div className="font-display text-[9px] tracking-[0.1em] uppercase text-[var(--text-dim)]">Index</div>
              <div className="font-mono text-lg font-black leading-none">
                <span style={{ color: C_SOURCE }}>{fmt(sourceIdx[k])}</span>
                <span className="text-[var(--text-dim)] text-xs mx-1">vs</span>
                <span style={{ color: C_SIMILAR }}>{fmt(similarIdx[k])}</span>
              </div>
            </div>
          ))
        }
      </div>

      <ResponsiveContainer width="100%" height={440}>
        <RadarChart data={radarData} margin={{ top: 28, right: 50, bottom: 40, left: 50 }}>
          <PolarGrid stroke="rgba(0,0,0,0.08)" />
          <PolarAngleAxis dataKey="stat" tick={renderTick} />
          <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
          <Tooltip content={<RadarTooltip />} />
          <Radar name={sName} dataKey={sName} stroke={C_SOURCE} fill={C_SOURCE} fillOpacity={0.15} strokeWidth={2}
            dot={{ fill: C_SOURCE, r: 3, strokeWidth: 0 }}
            activeDot={{ r: 5, fill: C_SOURCE, stroke: '#fff', strokeWidth: 1.5 }}
          />
          <Radar name={mName} dataKey={mName} stroke={C_SIMILAR} fill={C_SIMILAR} fillOpacity={0.15} strokeWidth={2}
            dot={{ fill: C_SIMILAR, r: 3, strokeWidth: 0 }}
            activeDot={{ r: 5, fill: C_SIMILAR, stroke: '#fff', strokeWidth: 1.5 }}
          />
          <Legend
            formatter={(v: string) => (
              <span className="text-[10px] font-display" style={{ color: v === sName ? C_SOURCE : C_SIMILAR }}>{v}</span>
            )}
            wrapperStyle={{ position: 'relative', top: 20 }}
          />
        </RadarChart>
      </ResponsiveContainer>

      {/* Mother stats comparison */}
      <div className="mt-4 bg-[var(--surface2)] rounded-xl p-4">

        {statList.length === 0 ? (
          <div className="bg-[var(--bg)] p-3 rounded-md border border-[var(--border)]">
            <p className="text-[11px] text-[var(--text-muted)] leading-[1.5]">
              {emptyMessage}
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-1.5">
            {/* Column headers */}
            <div className="grid gap-2 pb-1 mb-1 border-b border-[var(--border)]" style={{ gridTemplateColumns: '1fr auto auto' }}>
              <span className="font-display text-[9px] text-[var(--text-dim)] uppercase">Core Stats</span>
              <span className="font-display text-[9px] uppercase text-right min-w-[52px]" style={{ color: C_SOURCE }}>{sName}</span>
              <span className="font-display text-[9px] uppercase text-right min-w-[52px]" style={{ color: C_SIMILAR }}>{mName}</span>
            </div>

            {statList.map(s => {
              const sv = sourceAgg ? (sourceAgg[s.col] as number) : null;
              const mv = similarAgg ? (similarAgg[s.col] as number) : null;
              return (
                <DualMotherStatRow
                  key={s.col}
                  label={s.label}
                  sourceValue={fmt(sv)}
                  similarValue={fmt(mv)}
                  color={def.color}
                  showExperimental={def.key === 'GRAVITY'}
                />
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Market Value parsing & rendering helpers ─────────────────────────────────

export function parseMarketValue(val: string | null | undefined): number | null {
  if (!val) return null;
  const clean = val.replace(/[^0-9.,km]/gi, '').replace(',', '.');
  let factor = 1;
  if (clean.toLowerCase().includes('m')) {
    factor = 1000000;
  } else if (clean.toLowerCase().includes('k')) {
    factor = 1000;
  }
  const num = parseFloat(clean.replace(/[km]/gi, ''));
  return isNaN(num) ? null : num * factor;
}

function renderMarketValue(pre: string | null | undefined, post: string | null | undefined) {
  if (!pre) return null;
  const preNum = parseMarketValue(pre);
  const postNum = parseMarketValue(post);
  let arrow = null;
  let arrowColor = '';

  if (preNum && postNum) {
    if (postNum > preNum) {
      arrow = '▲';
      arrowColor = 'text-green-600 font-bold ml-1';
    } else if (postNum < preNum) {
      arrow = '▼';
      arrowColor = 'text-red-600 font-bold ml-1';
    }
  }

  return (
    <span className="px-2.5 py-1 rounded border border-[var(--border)] bg-[var(--surface)] shadow-sm text-xs font-semibold text-[var(--text-muted)] flex flex-wrap items-center gap-1">
      <span>Pre-Euro: <strong className="text-[var(--text)]">{pre}</strong></span>
      {post && (
        <span className="text-[11px] text-[var(--text-dim)] flex items-center">
          (Post: {post}
          {arrow && <span className={arrowColor}>{arrow}</span>})
        </span>
      )}
    </span>
  );
}

function renderPriceDelta(sourcePreStr: string | null | undefined, comparePreStr: string | null | undefined) {
  const sVal = parseMarketValue(sourcePreStr);
  const cVal = parseMarketValue(comparePreStr);
  if (!sVal || !cVal) return null;
  const diff = cVal - sVal;
  if (diff === 0) return null;

  const formattedDiff = formatDiffValue(diff);
  const isCheaper = diff < 0;
  const colorClass = isCheaper
    ? 'text-green-700 bg-green-50/50 border-green-200'
    : 'text-red-700 bg-red-50/50 border-red-200';

  return (
    <span className={`px-2.5 py-1 rounded border text-xs font-semibold ${colorClass}`}>
      {isCheaper ? 'Cheaper:' : 'More expensive:'} {formattedDiff}
    </span>
  );
}

function formatDiffValue(diff: number): string {
  const abs = Math.abs(diff);
  if (abs >= 1000000) {
    return `€${(abs / 1000000).toFixed(1)}m`;
  }
  if (abs >= 1000) {
    return `€${(abs / 1000).toFixed(0)}k`;
  }
  return `€${abs}`;
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function SimilarPlayers() {
  const [searchParams] = useSearchParams();
  const playerName = searchParams.get('playerName') || 'Player';
  const playerId = searchParams.get('playerId');
  const macroRole = searchParams.get('macroRole') || '';

  const dropdownId = useId();
  const [selectedIdx, setSelectedIdx] = useState(0);
  const [statMode, setStatMode] = useState<StatViewMode>('raw');
  const [dqMode, setDqMode] = useState<StatViewMode>('raw');
  const [obMode, setObMode] = useState<StatViewMode>('raw');

  const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

  // Fetch similar players list
  const { players: similarList, loading, error } = useSimilarPlayers(
    macroRole || undefined,
    playerName,
  );

  // Fetch source player's SC data via playerId
  const { data: sourceScData, loading: sourceScLoading } = usePlayerSpaceControl(
    playerId ?? undefined,
  );
  const { data: sourceDQ } = usePlayerDecisionQuality(playerId ?? undefined);
  const { data: sourceOB } = usePlayerOffBallMovement(playerId ?? undefined);

  const selectedPlayer = similarList[selectedIdx] ?? null;
  const { data: compareDQ } = usePlayerDecisionQuality(
    selectedPlayer?.player_id != null ? String(selectedPlayer.player_id) : undefined,
  );
  const { data: compareOB } = usePlayerOffBallMovement(
    selectedPlayer?.player_id != null ? String(selectedPlayer.player_id) : undefined,
  );
  const sourceIdx = sourceScData?.indices ?? null;
  const sourceAgg = sourceScData?.aggregated ?? null;

  const sourcePassesAnalysed = (sourceAgg as any)?.passes_analysed as number | null | undefined;

  // Fetch selected similar player's aggregated data
  const [similarAgg, setSimilarAgg] = useState<SpaceControlAggregated | null>(null);
  const [loadingAgg, setLoadingAgg] = useState(false);

  const fetchAgg = async (player: string, team: string) => {
    setLoadingAgg(true);
    try {
      const params = new URLSearchParams({ player, team });
      const res = await fetch(`${API_BASE_URL}/space-control/aggregated?${params}`);
      if (res.ok) {
        const data = await res.json();
        setSimilarAgg(data ?? null);
      } else {
        setSimilarAgg(null);
      }
    } catch {
      setSimilarAgg(null);
    } finally {
      setLoadingAgg(false);
    }
  };

  // Effect: fetch aggregated when selected player changes
  const [prevSelected, setPrevSelected] = useState<string | null>(null);
  if (selectedPlayer && `${selectedPlayer.player}__${selectedPlayer.team}` !== prevSelected) {
    setPrevSelected(`${selectedPlayer.player}__${selectedPlayer.team}`);
    fetchAgg(selectedPlayer.player, selectedPlayer.team);
  }

  // ── Loading / error screens ───────────────────────────────────────────────

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center py-40">
        <div className="text-center">
          <div className="w-8 h-8 border-[3px] border-[var(--accent)] border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="font-mono text-xs text-[var(--text-dim)]">Loading similar players…</p>
        </div>
      </div>
    );
  }

  if (error === 'timeout') {
    return (
      <div className="flex-1 flex items-center justify-center py-40 text-center px-6">
        <div>
          <p className="text-[40px] mb-3">⏱</p>
          <p className="font-display font-bold text-xl mb-2 text-[var(--text)]">Request Timeout</p>
          <p className="text-sm mb-6 text-[var(--text-muted)]">The backend did not respond within 15 seconds. Make sure the server is running.</p>
          <Link to={playerId ? `/player/${playerId}` : '/'} className="btn btn-primary">← Back to Profile</Link>
        </div>
      </div>
    );
  }

  if (error && error !== 'no_macro_role') {
    return (
      <div className="flex-1 flex items-center justify-center py-40 text-center px-6">
        <div>
          <p className="text-[40px] mb-3">⚠️</p>
          <p className="font-display font-bold text-xl mb-2 text-[var(--text)]">Connection Error</p>
          <p className="text-sm mb-2 text-[var(--text-muted)]">Unable to reach the backend.</p>
          <p className="font-mono text-xs mb-6 text-[var(--text-dim)]">{error}</p>
          <Link to={playerId ? `/player/${playerId}` : '/'} className="btn btn-primary">← Back to Profile</Link>
        </div>
      </div>
    );
  }

  const chartsReady = sourceIdx && selectedPlayer && !sourceScLoading;

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
              {playerId && (
                <>
                  <li><Link to={`/player/${playerId}`} className="hover:text-[var(--accent)] transition-colors font-semibold">{playerName}</Link></li>
                  <li aria-hidden>/</li>
                </>
              )}
              <li className="font-semibold text-[var(--text)]" aria-current="page">Similar Players</li>
            </ol>
          </nav>

          <h1 className="font-display font-black text-5xl sm:text-6xl leading-none tracking-tight text-[var(--text)]">
            Similar Players
          </h1>
        </div>
      </div>

      {similarList.length > 0 && (
        <div className="max-w-[1200px] mx-auto px-6 pt-8">

          {/* Symmetric comparison header */}
          <div className="card p-0 mb-8 overflow-hidden shadow-sm">
            <div className="relative grid grid-cols-1 lg:grid-cols-2 divide-y lg:divide-y-0 lg:divide-x divide-[var(--border)]">

              {/* Left — Source Player */}
              <div className="relative flex flex-col p-6 md:p-8 bg-[var(--surface2)] overflow-hidden">
                <div className="absolute top-0 right-0 w-[500px] h-[500px] pointer-events-none opacity-40 mix-blend-multiply" style={{ background: `radial-gradient(circle at top right, ${C_SOURCE}15 0%, transparent 60%)` }} />

                <div className="relative z-10 flex flex-col h-full">
                  {/* Header row */}
                  <div className="flex items-center justify-between mb-6 h-10">
                    <span className="px-3 py-1.5 rounded-md text-[10px] font-display font-bold uppercase tracking-wider bg-[var(--surface)] border border-[var(--border)] shadow-sm" style={{ color: C_SOURCE }}>
                      Source Player
                    </span>
                  </div>

                  {/* Avatar & Name */}
                  <div className="flex items-center gap-5 mb-6">
                    <div>
                      <h1 className="font-display font-black text-2xl sm:text-3xl leading-tight tracking-tight text-[var(--text)] mb-2">
                        {playerName}
                      </h1>
                      <div className="flex flex-wrap gap-2 items-center">
                        {searchParams.get('playerTeam') && (
                          <span className="px-2.5 py-1 rounded border border-[var(--border)] bg-[var(--surface)] shadow-sm text-xs font-bold text-[var(--text-muted)] flex items-center gap-2">
                            {getFlagUrl(searchParams.get('playerTeam')!) && <img src={getFlagUrl(searchParams.get('playerTeam')!)!} alt="" className="w-4 h-3 object-cover rounded-[2px]" aria-hidden />}
                            {searchParams.get('playerTeam')}
                          </span>
                        )}
                        {macroRole && (
                          <span className="px-2.5 py-1 rounded border border-[var(--border)] bg-[var(--surface)] shadow-sm text-xs font-bold text-[var(--text)]">
                            {macroRole}
                          </span>
                        )}
                        {searchParams.get('primaryRole') && (
                          <span className="px-2.5 py-1 rounded border border-[var(--border)] bg-[var(--surface)] shadow-sm text-xs font-bold text-[var(--text)]">
                            {searchParams.get('primaryRole')!.replace(/_/g, ' ')}
                          </span>
                        )}
                        {sourceIdx?.preferred_foot && (
                          <span className="px-2.5 py-1 rounded border border-[var(--border)] bg-[var(--surface)] shadow-sm text-xs font-bold text-[var(--text-muted)]">
                            {sourceIdx.preferred_foot === 'both' ? 'Both Feet' : `${sourceIdx.preferred_foot.charAt(0).toUpperCase() + sourceIdx.preferred_foot.slice(1)} Foot`}
                          </span>
                        )}
                        {sourceIdx?.age != null && (
                          <span className="px-2.5 py-1 rounded border border-[var(--border)] bg-[var(--surface)] shadow-sm text-xs font-bold text-[var(--text-muted)]">
                            Age: {sourceIdx.age}
                          </span>
                        )}
                        {renderMarketValue(sourceIdx?.market_value_before_euros, sourceIdx?.market_value_after_euros)}
                      </div>
                    </div>
                  </div>

                  {/* Meta stats */}
                  <div className="grid grid-cols-2 gap-3 mt-auto mb-0">
                    <div className="flex flex-col gap-1 p-3 bg-[var(--surface)] rounded-[12px] border border-[var(--border)] shadow-sm">
                      <span className="font-mono text-[9px] tracking-[0.12em] uppercase text-[var(--text-dim)]">Minutes played</span>
                      <span className="font-display font-black text-xl text-[var(--text)]">
                        {sourceIdx?.minutes_played != null ? `${sourceIdx.minutes_played}'` : '—'}
                      </span>
                    </div>
                    <div className="flex flex-col gap-1 p-3 bg-[var(--surface)] rounded-[12px] border border-[var(--border)] shadow-sm">
                      <span className="font-mono text-[9px] tracking-[0.12em] uppercase text-[var(--text-dim)]">Passes</span>
                      <span className="font-display font-black text-xl text-[var(--text)]">
                        {sourcePassesAnalysed != null ? sourcePassesAnalysed : '—'}
                      </span>
                    </div>
                  </div>

                  <div className="pt-4">
                    {playerId ? (
                      <Link
                        to={`/player/${playerId}`}
                        className="btn btn-primary w-full justify-center rounded-xl py-3"
                      >
                        View full profile →
                      </Link>
                    ) : (
                      <div className="h-[46px]"></div>
                    )}
                  </div>
                </div>
              </div>

              {/* Mobile Similarity Row (between source and comparison players) */}
              {selectedPlayer && selectedPlayer.similarity_score != null && (
                <div className="lg:hidden flex items-center justify-center py-3.5 bg-[var(--surface)] text-sm">
                  <span className="font-display font-bold text-[var(--text-muted)] mr-2">Stylistic Similarity</span>
                  <span className="font-display font-black text-[var(--accent)] px-2.5 py-1 rounded-full bg-[var(--accent-dim)] border border-[rgba(37,99,235,0.15)] leading-none text-xs">
                    {selectedPlayer.similarity_score.toFixed(1)}%
                  </span>
                </div>
              )}

              {/* Right — Comparison Player */}
              <div className="relative flex flex-col p-6 md:p-8 bg-[var(--surface2)] overflow-hidden">
                <div className="absolute top-0 right-0 w-[500px] h-[500px] pointer-events-none opacity-40 mix-blend-multiply" style={{ background: `radial-gradient(circle at top right, ${C_SIMILAR}15 0%, transparent 60%)` }} />

                <div className="relative z-10 flex flex-col h-full">
                  {/* Header row with dropdown */}
                  <div className="flex items-center justify-between lg:justify-end mb-6 h-10 gap-4">
                    <span className="px-3 py-1.5 rounded-md text-[10px] font-display font-bold uppercase tracking-wider bg-[var(--surface)] border border-[var(--border)] shadow-sm" style={{ color: C_SIMILAR }}>
                      Compare With
                    </span>
                    <div className="relative flex-1 max-w-[280px] lg:hidden">
                      <select
                        id={dropdownId}
                        value={selectedIdx}
                        onChange={e => setSelectedIdx(Number(e.target.value))}
                        className="w-full appearance-none bg-[var(--surface)] border border-[var(--border)] shadow-sm font-semibold text-sm h-10 px-4 pr-10 rounded-lg cursor-pointer focus:outline-none focus:border-[var(--accent)] transition-colors"
                      >
                        {similarList.map((p, i) => {
                          const simStr = p.similarity_score != null ? `${p.similarity_score.toFixed(1)}%` : 'N/A';
                          return (
                            <option key={`${p.player}-${p.team}`} value={i}>
                              {simStr} | {p.player}
                            </option>
                          );
                        })}
                      </select>
                      <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-dim)] pointer-events-none">▾</span>
                    </div>
                  </div>

                  {selectedPlayer ? (
                    <>
                      {/* Avatar & Name */}
                      <div className="flex items-center justify-start lg:justify-end mb-6 w-full">
                        <div className="text-left lg:text-right flex flex-col items-start lg:items-end w-full">
                          <h1 className="font-display font-black text-2xl sm:text-3xl leading-tight tracking-tight text-[var(--text)] mb-2 text-left lg:text-right">
                            {selectedPlayer.player}
                          </h1>
                          <div className="flex flex-wrap justify-start lg:justify-end gap-2 items-center">
                            {selectedPlayer.team && (
                              <span className="px-2.5 py-1 rounded border border-[var(--border)] bg-[var(--surface)] shadow-sm text-xs font-bold text-[var(--text-muted)] flex items-center gap-2">
                                {getFlagUrl(selectedPlayer.team) && <img src={getFlagUrl(selectedPlayer.team)!} alt="" className="w-4 h-3 object-cover rounded-[2px]" aria-hidden />}
                                {selectedPlayer.team}
                              </span>
                            )}
                            {macroRole && (
                              <span className="px-2.5 py-1 rounded border border-[var(--border)] bg-[var(--surface)] shadow-sm text-xs font-bold text-[var(--text)]">
                                {macroRole}
                              </span>
                            )}
                            {selectedPlayer.primary_role && (
                              <span className="px-2.5 py-1 rounded border border-[var(--border)] bg-[var(--surface)] shadow-sm text-xs font-bold text-[var(--text)]">
                                {selectedPlayer.primary_role.replace(/_/g, ' ')}
                              </span>
                            )}
                            {selectedPlayer.preferred_foot && (
                              <span className="px-2.5 py-1 rounded border border-[var(--border)] bg-[var(--surface)] shadow-sm text-xs font-bold text-[var(--text-muted)]">
                                {selectedPlayer.preferred_foot === 'both' ? 'Both Feet' : `${selectedPlayer.preferred_foot.charAt(0).toUpperCase() + selectedPlayer.preferred_foot.slice(1)} Foot`}
                              </span>
                            )}
                            {selectedPlayer.age != null && (
                              <span className="px-2.5 py-1 rounded border border-[var(--border)] bg-[var(--surface)] shadow-sm text-xs font-bold text-[var(--text-muted)]">
                                Age: {selectedPlayer.age}
                              </span>
                            )}
                            {renderMarketValue(selectedPlayer.market_value_before_euros, selectedPlayer.market_value_after_euros)}
                            {renderPriceDelta(sourceIdx?.market_value_before_euros, selectedPlayer.market_value_before_euros)}
                          </div>
                        </div>
                      </div>

                      {/* Meta stats */}
                      <div className="grid grid-cols-2 gap-3 mt-auto mb-0">
                        <div className="flex flex-col gap-1 p-3 bg-[var(--surface)] rounded-[12px] border border-[var(--border)] shadow-sm">
                          <span className="font-mono text-[9px] tracking-[0.12em] uppercase text-[var(--text-dim)]">Minutes played</span>
                          <span className="font-display font-black text-xl text-[var(--text)]">
                            {selectedPlayer.minutes_played != null ? `${selectedPlayer.minutes_played}'` : '—'}
                          </span>
                        </div>
                        <div className="flex flex-col gap-1 p-3 bg-[var(--surface)] rounded-[12px] border border-[var(--border)] shadow-sm">
                          <span className="font-mono text-[9px] tracking-[0.12em] uppercase text-[var(--text-dim)]">Passes</span>
                          <span className="font-display font-black text-xl text-[var(--text)]">
                            {(similarAgg as any)?.passes_analysed != null ? (similarAgg as any).passes_analysed : '—'}
                          </span>
                        </div>
                      </div>

                      <div className="pt-4">
                        <Link
                          to={`/player/${selectedPlayer.player_id}`}
                          className="btn btn-primary w-full justify-center rounded-xl py-3"
                        >
                          View full profile →
                        </Link>
                      </div>
                    </>
                  ) : (
                    <div className="flex-1 flex items-center justify-center text-sm font-mono text-[var(--text-dim)]">
                      Select a player to compare
                    </div>
                  )}
                </div>
              </div>

              {/* Centered Dropdown (Desktop only) */}
              <div className="hidden lg:block absolute top-[32px] left-1/2 -translate-x-1/2 z-30 w-[280px]">
                <div className="relative">
                  <select
                    id={`${dropdownId}-centered`}
                    value={selectedIdx}
                    onChange={e => setSelectedIdx(Number(e.target.value))}
                    className="w-full appearance-none bg-[var(--surface)] border border-[var(--border2)] shadow-md font-semibold text-sm h-10 px-4 pr-10 rounded-lg cursor-pointer focus:outline-none focus:border-[var(--accent)] transition-colors"
                  >
                    {similarList.map((p, i) => {
                      const simStr = p.similarity_score != null ? `${p.similarity_score.toFixed(1)}%` : 'N/A';
                      return (
                        <option key={`${p.player}-${p.team}-centered`} value={i}>
                          {simStr} | {p.player}
                        </option>
                      );
                    })}
                  </select>
                  <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-dim)] pointer-events-none">▾</span>
                </div>
              </div>

              {/* Centered Similarity Badge (Desktop only) */}
              {selectedPlayer && selectedPlayer.similarity_score != null && (
                <div className="hidden lg:block absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-20 pointer-events-none">
                  <div
                    className="flex flex-col items-center justify-center w-16 h-16 rounded-full bg-[var(--surface)] border border-[var(--border2)]"
                    style={{
                      boxShadow: '0 0 0 6px var(--surface2), 0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1), 0 0 12px var(--accent-dim)',
                    }}
                  >
                    <span className="font-display font-black text-base text-[var(--accent)] leading-none">
                      {selectedPlayer.similarity_score.toFixed(1)}%
                    </span>
                  </div>
                </div>
              )}

            </div>
          </div>

          {/* 4 dual radar cards + DQ card — split into two panels */}
          {chartsReady && selectedPlayer ? (
            loadingAgg ? (
              <div className="text-center py-8">
                <div className="w-6 h-6 border-2 border-t-transparent rounded-full animate-spin mx-auto" style={{ borderColor: C_SIMILAR, borderTopColor: 'transparent' }} />
              </div>
            ) : (
              <>
                {/* Space & Control panel (first four radars) */}
                <section className="max-w-[1200px] mx-auto px-0 pb-6">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
                    <div>
                      <h2 className="font-display font-black text-xl text-[var(--text)] mb-1">Space Control &amp; Value</h2>
                      <p className="text-xs text-[var(--text-muted)]">Selected players metrics — {playerName} · {selectedPlayer.player}</p>
                    </div>
                    <StatViewToggle mode={statMode} onChange={setStatMode} />
                  </div>

                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                    {RADAR_DEFS.map(def => (
                      <DualRadarCard
                        key={def.key}
                        def={def}
                        sourceIdx={sourceIdx}
                        similarIdx={selectedPlayer}
                        sourceAgg={sourceAgg}
                        similarAgg={similarAgg}
                        sourceName={playerName}
                        similarName={selectedPlayer.player}
                        mode={statMode}
                      />
                    ))}
                  </div>
                </section>

                {/* Decision Quality panel (single DQ radar) */}
                <section className="max-w-[1200px] mx-auto px-0 pb-12 mt-8">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
                    <div>
                      <h2 className="font-display font-black text-xl text-[var(--text)] mb-1">Decision Quality</h2>
                      <p className="text-xs text-[var(--text-muted)]">Selected players metrics — {playerName} · {selectedPlayer.player}</p>
                    </div>
                    <StatViewToggle mode={dqMode} onChange={setDqMode} />
                  </div>

                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                    {sourceDQ && compareDQ ? (
                      <DQCompareRadar
                        sourceRow={sourceDQ}
                        compareRow={compareDQ}
                        sourceName={playerName}
                        compareName={selectedPlayer?.player ?? 'Comparison player'}
                        mode={dqMode}
                      />
                    ) : (
                      <div className="col-span-2 text-sm text-[var(--text-muted)]">Decision Quality data not available for one of the players.</div>
                    )}
                  </div>
                </section>

                {/* Off-Ball Movement panel (single OB radar) */}
                <section className="max-w-[1200px] mx-auto px-0 pb-12 mt-8">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
                    <div>
                      <h2 className="font-display font-black text-xl text-[var(--text)] mb-1">Off-Ball Movement</h2>
                      <p className="text-xs text-[var(--text-muted)]">Selected players metrics — {playerName.trim().split(' ').pop()} · {selectedPlayer.player.trim().split(' ').pop()}</p>
                    </div>
                    <StatViewToggle mode={obMode} onChange={setObMode} />
                  </div>

                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                    {sourceOB && compareOB ? (
                      <OBCompareRadar
                        sourceRow={sourceOB}
                        compareRow={compareOB}
                        sourceName={playerName}
                        compareName={selectedPlayer?.player ?? 'Comparison player'}
                        mode={obMode}
                      />
                    ) : (
                      <div className="col-span-2 text-sm text-[var(--text-muted)]">Off-Ball Movement data not available for one of the players.</div>
                    )}
                  </div>
                </section>
              </>
            )
          ) : sourceScLoading ? (
            <div className="text-center py-8">
              <p className="font-mono text-xs text-[var(--text-dim)]">Loading source player's space control profile…</p>
            </div>
          ) : (
            <div className="rounded-xl px-4 py-3 border bg-[var(--surface2)] border-[var(--border)]">
              <p className="text-xs font-mono text-[var(--text-dim)]">
                The source player's space control profile is not available. Make sure the SC tables have been imported.
              </p>
            </div>
          )}


          {/* Full similar players list */}
          <h2 className="font-display font-black text-2xl mb-4 text-[var(--text)]">
            All {macroRole} players ({similarList.length})
          </h2>
          <div className="space-y-3" role="list">
            {similarList.map((player, idx) => {
              const isSelected = idx === selectedIdx;
              const flagUrl = getFlagUrl(player.team);
              return (
                <div
                  key={`${player.player}-${player.team}`}
                  role="listitem"
                  className="card p-4 sm:p-5 flex flex-col sm:flex-row items-start sm:items-center gap-4 transition-all cursor-pointer"
                  style={isSelected ? { borderColor: 'var(--accent)', boxShadow: '0 0 0 1px var(--accent)' } : undefined}
                  onClick={() => setSelectedIdx(idx)}
                  tabIndex={0}
                  onKeyDown={e => e.key === 'Enter' && setSelectedIdx(idx)}
                  aria-selected={isSelected}
                >
                  <span className={`font-mono font-bold text-xl w-8 text-center ${idx < 3 ? 'text-[var(--accent)]' : 'text-[var(--text-dim)]'}`} aria-hidden>
                    {idx + 1}
                  </span>
                  {flagUrl
                    ? <img src={flagUrl} alt="" className="w-8 h-6 object-cover rounded shadow-sm shrink-0" aria-hidden />
                    : <span className="text-xs font-mono font-bold rounded shrink-0 bg-[var(--surface2)] px-2 py-1 text-[var(--text-muted)]" aria-hidden>{player.team?.substring(0, 3).toUpperCase()}</span>
                  }
                  <div className="flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2 mb-1">
                      <span className="font-display font-black text-xl" style={{ color: isSelected ? 'var(--accent)' : 'var(--text)' }}>{player.player}</span>
                      <ScoreBadge score={player.similarity_score} />
                    </div>
                    <p className="text-xs flex flex-wrap items-center gap-x-2 gap-y-1 text-[var(--text-muted)]">
                      <span>{player.team}</span><span aria-hidden>·</span>
                      <span>{player.primary_role}</span><span aria-hidden>·</span>
                      {player.age != null && (
                        <>
                          <span>Age: {player.age}</span><span aria-hidden>·</span>
                        </>
                      )}
                      <span>{player.minutes_played}' played</span>
                      {player.market_value_before_euros && (
                        <>
                          <span aria-hidden>·</span>
                          <span>
                            Pre-Euro: {formatMarketValue(player.market_value_before_euros)}
                            {player.market_value_after_euros ? (
                              <>
                                {' '}(Post: {formatMarketValue(player.market_value_after_euros)}
                                {(() => {
                                  const arrow = getMarketTrendArrow(player.market_value_before_euros, player.market_value_after_euros);
                                  if (!arrow) return null;
                                  const color = arrow === '▲' ? 'var(--win)' : 'var(--lose)';
                                  return <span className="ml-1 font-bold" style={{ color }}>{arrow}</span>;
                                })()}
                                )
                              </>
                            ) : (
                              ' (Post: —)'
                            )}
                          </span>
                        </>
                      )}
                    </p>
                    <div className="mt-2"><ScoreBar score={player.similarity_score} /></div>
                  </div>
                  <button
                    className={`btn text-xs px-3 py-1.5 shrink-0 w-[110px] justify-center ${isSelected ? 'bg-[var(--accent-dim)] text-[var(--accent)] border-[var(--accent)]' : 'bg-[var(--surface2)] text-[var(--text-muted)] border-[var(--border)]'}`}
                    style={isSelected ? { borderColor: 'var(--accent)' } : undefined}
                    onClick={e => { e.stopPropagation(); setSelectedIdx(idx); }}
                    aria-pressed={isSelected}
                  >
                    {isSelected ? '✓ Comparing' : 'Compare'}
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {!loading && similarList.length === 0 && macroRole && !error && (
        <div className="max-w-[1200px] mx-auto px-6 pt-8">
          <div className="card p-8 text-center">
            <p className="text-3xl mb-3">🔍</p>
            <p className="font-display font-bold text-lg text-[var(--text)]">
              No other {macroRole} players found in the dataset
            </p>
          </div>
        </div>
      )}
    </div>
  );
}