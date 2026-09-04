import { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { getFlagUrl, ALL_STATS, CAT_ACCENT, type PlayerStats, formatMarketValue, getMarketTrendArrow } from '../utils';
import { usePlayerSpaceControl } from '../hooks/useSpaceControl';
import SpaceControlSection, { type StatViewMode } from '../components/SpaceControlSection';
import { usePlayerDecisionQuality } from '../hooks/useDecisionQuality';
import DecisionQualitySection from '../components/DecisionQualitySection';
import { usePlayerOffBallMovement } from '../hooks/useOffBallMovement';
import OffBallSection from '../components/OffBallSection';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

function StatCard({ label, value, category, statKey }: { label: string; value: unknown; category: string; statKey: string }) {
  const accent = CAT_ACCENT[category] ?? '#64748b';
  let display = String(value ?? '—');
  if (value != null) {
    if (typeof value === 'string' && /^-?\d+,\d+$/.test(value)) {
      display = value.replace(',', '.');
    }
    if (label === 'xG' || statKey === 'xg_total' || statKey === 'xg' || label === 'Pass %' || statKey === 'pass_completion_pct') {
      const num = typeof value === 'string' ? parseFloat(value.replace(',', '.')) : Number(value);
      if (!isNaN(num)) display = num.toFixed(2);
    }
  }
  return (
    <div className="relative flex flex-col p-4 bg-[var(--surface2)] border border-[var(--border)] rounded-[12px] overflow-hidden">
      <div className="absolute top-0 left-0 bottom-0 w-[3px]" style={{ background: accent }} />
      <div className="pl-2 flex flex-col gap-1">
        <span className="font-mono text-[9px] tracking-[0.12em] uppercase font-bold" style={{ color: accent }}>{category}</span>
        <span className="font-display font-black text-2xl leading-none text-[var(--text)]">{display}</span>
        <span className="text-[11px] font-semibold text-[var(--text-muted)] leading-tight">{label}</span>
      </div>
    </div>
  );
}


function ProfileSkeleton() {
  return (
    <div className="max-w-[1200px] mx-auto px-6 pt-10 pb-16 space-y-8" aria-busy="true">
      <div className="card p-8">
        <div className="flex gap-6">
          <div className="skeleton w-24 h-24 rounded-2xl flex-shrink-0" />
          <div className="flex-1 space-y-3">
            <div className="skeleton h-8 rounded w-64" />
            <div className="skeleton h-4 rounded w-40" />
            <div className="flex gap-3">
              {[80, 70, 90, 80].map((w, i) => <div key={i} className="skeleton h-12 rounded-xl" style={{ width: w }} />)}
            </div>
          </div>
        </div>
      </div>
      <div className="flex flex-col gap-3 items-center w-full">
        <div className="flex justify-center flex-wrap xl:flex-nowrap gap-3 w-full">
          {Array.from({ length: 5 }).map((_, i) => <div key={`sk1-${i}`} className="skeleton h-24 w-[45%] sm:w-[30%] md:w-[18%] lg:w-[140px] xl:w-[150px] flex-shrink-0 rounded-xl" />)}
        </div>
        <div className="flex justify-center flex-wrap xl:flex-nowrap gap-3 w-full">
          {Array.from({ length: 4 }).map((_, i) => <div key={`sk2-${i}`} className="skeleton h-24 w-[45%] sm:w-[30%] md:w-[18%] lg:w-[140px] xl:w-[150px] flex-shrink-0 rounded-xl" />)}
        </div>
      </div>
    </div>
  );
}

export default function PlayerProfile() {
  const { playerId } = useParams<{ playerId: string }>();
  const navigate = useNavigate();

  const [stats, setStats] = useState<PlayerStats | null>(null);
  const [loadingStats, setLoadingStats] = useState(true);
  const [statMode, setStatMode] = useState<StatViewMode>('raw');
  const [dqMode, setDqMode] = useState<StatViewMode>('raw');
  const [obMode, setObMode] = useState<StatViewMode>('raw');

  const { data: scData, loading: scLoading } = usePlayerSpaceControl(playerId);
  const { data: dqData, loading: dqLoading } = usePlayerDecisionQuality(playerId);
  const { data: obData, loading: obLoading } = usePlayerOffBallMovement(playerId);

  useEffect(() => {
    if (!playerId) return;
    setLoadingStats(true);
    fetch(`${API_BASE_URL}/players/${playerId}/stats`)
      .then(r => r.json())
      .then((d: PlayerStats) => { setStats(d); setLoadingStats(false); })
      .catch(() => setLoadingStats(false));
  }, [playerId]);

  const handleFindSimilar = () => {
    if (!stats) return;
    navigate(`/similar?${new URLSearchParams({
      playerId: playerId!,
      playerName: stats.player_name,
      playerTeam: stats.source_team_name ?? '',
      macroRole: scData?.indices?.macro_role ?? '',
      primaryRole: stats.primary_role ?? '',
    })}`);
  };

  if (loadingStats) return <ProfileSkeleton />;

  if (!stats) {
    return (
      <div className="flex-1 flex items-center justify-center py-40 text-center">
        <div>
          <p className="text-5xl mb-4" aria-hidden>⚠️</p>
          <p className="font-display font-bold text-xl text-[var(--text)]">Player not found</p>
          <Link to="/" className="mt-6 inline-block text-sm font-semibold text-[var(--text-muted)] hover:text-[var(--accent)] transition-colors">
            ← Back to Home
          </Link>
        </div>
      </div>
    );
  }

  const flagUrl = getFlagUrl(stats.source_team_name);
  const minutesPlayed = scData?.indices?.minutes_played ?? stats.minutes_played;
  const passesAnalysed = (scData?.aggregated as any)?.passes_analysed as number | null | undefined;

  return (
    <div className="w-full pb-16 min-h-screen bg-[var(--bg)]">

      {/* Breadcrumb */}
      <nav aria-label="Breadcrumb" className="max-w-[1200px] mx-auto px-6 pt-8 mb-6">
        <ol className="flex items-center gap-2 text-sm text-[var(--text-muted)]">
          <li><Link to="/" className="hover:text-[var(--accent)] transition-colors font-semibold">Home</Link></li>
          <li aria-hidden>/</li>
          <li className="font-semibold text-[var(--text)]" aria-current="page">{stats.player_name}</li>
        </ol>
      </nav>

      {/* Unified Hero & Stats Section */}
      <div className="max-w-[1200px] mx-auto px-6 mb-12">
        <div className="card p-0 overflow-hidden shadow-sm fade-up">
          
          {/* Header / Identity Area */}
          <div className="relative p-8 md:p-10 bg-[var(--surface2)] border-b border-[var(--border)] overflow-hidden">
            <div className="absolute top-0 right-0 w-[500px] h-[500px] pointer-events-none opacity-40 mix-blend-multiply" style={{ background: 'radial-gradient(circle at top right, rgba(37,99,235,0.15) 0%, transparent 60%)' }} />
            
            <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-8">
              <div className="flex items-center gap-6 sm:gap-8">
                <div>
                  <h1 className="font-display font-black text-4xl sm:text-5xl leading-tight tracking-tight text-[var(--text)] mb-3">
                    {stats.player_name}
                  </h1>
                  <div className="flex flex-wrap gap-2 mb-3">
                    <p className="flex items-center gap-2.5 text-base font-semibold text-[var(--text-muted)]">
                      {flagUrl && <img src={flagUrl} alt="" className="w-7 h-5 object-cover rounded-[3px] shadow-sm" aria-hidden />}
                      {stats.source_team_name}
                    </p>
                    {scData?.indices?.macro_role && (
                      <span className="tag bg-[var(--surface)] border border-[var(--border)] text-[var(--text)] font-bold shadow-sm">
                        {scData.indices.macro_role}
                      </span>
                    )}
                    {stats.primary_role && (
                      <span className="tag bg-[var(--surface)] border border-[var(--border)] text-[var(--accent)] font-bold shadow-sm">
                        {stats.primary_role.replace(/_/g, ' ')}
                      </span>
                    )}
                    {stats.preferred_foot && (
                      <span className="tag bg-[var(--surface)] border border-[var(--border)] text-[var(--text-muted)] font-bold shadow-sm">
                        {stats.preferred_foot === 'both' ? 'Both Feet' : `${stats.preferred_foot.charAt(0).toUpperCase() + stats.preferred_foot.slice(1)} Foot`}
                      </span>
                    )}
                    {stats.age != null && (
                      <span className="tag bg-[var(--surface)] border border-[var(--border)] text-[var(--text-muted)] font-bold shadow-sm">
                        Age: {stats.age}
                      </span>
                    )}
                    {stats.market_value_before_euros && (
                      <span className="tag bg-[var(--surface)] border border-[var(--border)] text-[var(--text-muted)] font-semibold shadow-sm flex items-center gap-1">
                        Pre-Euro: <strong className="text-[var(--text)]">{formatMarketValue(stats.market_value_before_euros)}</strong>
                        {stats.market_value_after_euros ? (
                          <>
                            <span className="ml-1">(Post:</span>
                            <strong className="text-[var(--text)]">{formatMarketValue(stats.market_value_after_euros)}</strong>
                            {(() => {
                              const arrow = getMarketTrendArrow(stats.market_value_before_euros, stats.market_value_after_euros);
                              if (!arrow) return null;
                              const color = arrow === '▲' ? 'var(--win)' : 'var(--lose)';
                              return <span className="ml-0.5 font-bold" style={{ color }}>{arrow}</span>;
                            })()}
                            <span>)</span>
                          </>
                        ) : (
                          <span className="ml-1">(Post: —)</span>
                        )}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              <div className="shrink-0">
                <button onClick={handleFindSimilar} className="btn btn-primary w-full md:w-auto px-6 py-3 shadow-md hover:shadow-lg transition-all" aria-label="Find a player similar to this one">
                  <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" aria-hidden fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                    <circle cx="11" cy="11" r="8" /><path d="M21 21l-4.35-4.35" />
                  </svg>
                  Find Similar Player
                </button>
              </div>
            </div>
          </div>

          {/* Info & Stats Area */}
          <div className="flex flex-col xl:flex-row bg-[var(--surface)]">
            {/* Left Column: Player Info */}
            <div className="xl:w-[320px] p-8 border-b xl:border-b-0 xl:border-r border-[var(--border)]" style={{ background: 'rgba(var(--surface2-rgb, 248, 250, 252), 0.5)' }}>
              <p className="font-mono text-[10px] tracking-[0.14em] uppercase text-[var(--text-dim)] mb-6 font-bold">Player Info</p>
              <div className="grid grid-cols-2 xl:grid-cols-1 gap-3" role="list">
                {([
                  { label: 'Minutes',         value: minutesPlayed != null ? `${minutesPlayed}'` : null },
                  { label: 'Passes Analysed', value: passesAnalysed },
                ] as { label: string; value: string | number | null | undefined }[])
                  .filter(d => d.value != null && d.value !== '')
                  .map((d, i) => (
                    <div key={d.label} role="listitem" className={`fade-up delay-${Math.min(i + 1, 5)}`}>
                      <StatCard label={d.label} value={d.value} category="General" statKey={d.label.toLowerCase()} />
                    </div>
                ))}
              </div>
            </div>

            {/* Right Column: Traditional Stats */}
            <div className="flex-1 p-8">
              <p className="font-mono text-[10px] tracking-[0.14em] uppercase text-[var(--text-dim)] mb-6 font-bold">Traditional Stats</p>
              <div className="flex flex-col gap-3 items-center w-full" role="list" aria-label="Player statistics">
                {/* Top Row: 5 Attacking stats */}
                <div className="flex justify-center flex-wrap xl:flex-nowrap gap-3 w-full">
                  {ALL_STATS.slice(0, 5).map((stat, i) => (
                    <div key={stat.key} role="listitem" className={`fade-up delay-${Math.min(i + 1, 5)} w-[45%] sm:w-[30%] md:w-[18%] lg:w-[140px] xl:w-[150px] flex-shrink-0`}>
                      <StatCard label={stat.label} value={(stats as unknown as Record<string, unknown>)[stat.key]} category={stat.category} statKey={stat.key} />
                    </div>
                  ))}
                </div>
                {/* Bottom Row: 4 other stats */}
                <div className="flex justify-center flex-wrap xl:flex-nowrap gap-3 w-full">
                  {ALL_STATS.slice(5).map((stat, i) => (
                    <div key={stat.key} role="listitem" className={`fade-up delay-${Math.min(i + 6, 5)} w-[45%] sm:w-[30%] md:w-[18%] lg:w-[140px] xl:w-[150px] flex-shrink-0`}>
                      <StatCard label={stat.label} value={(stats as unknown as Record<string, unknown>)[stat.key]} category={stat.category} statKey={stat.key} />
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

        </div>
      </div>

      {/* Space Control section */}
      {scLoading ? (
        <div className="max-w-[1200px] mx-auto px-6 mb-12">
          <div className="card p-8 text-center">
            <p className="font-mono text-xs text-[var(--text-dim)]">Loading Space Control data…</p>
          </div>
        </div>
      ) : scData?.indices ? (
        <SpaceControlSection
          playerName={stats.player_name}
          teamName={stats.source_team_name}
          indexRow={scData.indices}
          aggRow={scData.aggregated}
          mode={statMode}
          onModeChange={setStatMode}
        />
      ) : (
        <div className="max-w-[1200px] mx-auto px-6 mb-12">
          <div className="card p-6">
            <p className="font-mono text-xs text-[var(--text-dim)]">
              No Space Control data available for this player.
            </p>
          </div>
        </div>
      )}

      {/* Decision Quality section */}
      {dqLoading ? (
        <div className="max-w-[1200px] mx-auto px-6 mb-12">
          <div className="card p-8 text-center">
            <p className="font-mono text-xs text-[var(--text-dim)]">Loading Decision Quality data…</p>
          </div>
        </div>
      ) : dqData ? (
        <DecisionQualitySection
          playerName={stats.player_name}
          teamName={stats.source_team_name}
          row={dqData}
          mode={dqMode}
          onModeChange={setDqMode}
        />
      ) : (
        <div className="max-w-[1200px] mx-auto px-6 mb-12">
          <div className="card p-6">
            <p className="font-mono text-xs text-[var(--text-dim)]">
              No Decision Quality data available for this player.
            </p>
          </div>
        </div>
      )}


      {/* Off-Ball Movement Section */}
      {obLoading ? (
        <div className="max-w-[1200px] mx-auto px-6 mb-12">
          <div className="card p-8 text-center">
            <p className="font-mono text-xs text-[var(--text-dim)]">Loading Off-Ball Movement data…</p>
          </div>
        </div>
      ) : obData ? (
        <OffBallSection
          playerName={stats.player_name}
          row={obData}
          mode={obMode}
          onModeChange={setObMode}
        />
      ) : (
        <div className="max-w-[1200px] mx-auto px-6 mb-12">
          <div className="card p-6">
            <p className="font-mono text-xs text-[var(--text-dim)]">
              No Off-Ball Movement data available for this player.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
