const LIMITATIONS = [
  // — Nature of the data —
  {
    title: 'Aggregated seasonal metrics, not frame-by-frame tracking',
    body: 'All metrics are derived from Wyscout seasonal aggregated match data (wyscout_sample.csv), rather than optical tracking coordinates or physical trajectory tracking. They capture seasonal execution volume, efficiency rates, and creative actions rather than instantaneous pitch geometry.',
  },
  {
    title: 'Statistical proxies for tactical constructs',
    body: 'The four Space Control dimensions (H1) and Decision Quality (H2) are modeled via statistical proxy mappings. For example, Dangerousness is proxied through Expected Goals and Expected Assists per 90, and Decision Quality through pass accuracy, duel success %, and incisive action volumes. These serve as robust directional indicators rather than physical measurements of defensive displacement or alternative teammate sets.',
  },
  {
    title: 'Gravity as an inferential proxy',
    body: 'In tracking data, gravity physically measures defender displacement towards a ball carrier. In aggregated seasonal data, it is approximated by fouls suffered/90 and offensive duels/90 under the rationale that drawing duels commands extra defensive attention, but it remains an inference rather than a coordinate-level centroid shift.',
  },
  // — Scope and sample —
  {
    title: 'Sample context & 300-minute floor',
    body: 'All data come from a curated Wyscout seasonal sample dataset. To ensure statistical reliability across per-90 rates, eligible outfield players are filtered with a threshold of at least 300 minutes played (yielding 1,059 players).',
  },
  {
    title: 'Macro-role benchmarking',
    body: 'Percentile rankings benchmark each player strictly within their macro-role (CB, FB, MID, CAM, WIDE, FW). While this prevents cross-positional distortions, hybrid or fluid tactical roles (e.g. inverted full-backs or roaming wingers) are evaluated against their primary registered positional bucket.',
  },
  {
    title: 'Team bias reduced, not completely eliminated',
    body: 'Normalizing by 90 minutes and evaluating percentiles within macro-roles substantially reduces volume bias from dominant possession sides. However, tactical context still matters: players in sides that dominate territorial possession naturally record higher volumes in advanced zones than those in deep defensive setups.',
  },
  {
    title: 'Single valuation snapshot for style matchmaking',
    body: 'Market values in the dataset represent a single seasonal valuation snapshot. Player similarity (H4) identifies stylistic twins and market-value arbitrage based on this snapshot, without tracking subsequent transfer market value fluctuations.',
  },
  {
    title: 'Absence of game state & match circumstances',
    body: 'Seasonal totals aggregate all phases of play equally. The data does not isolate specific match scores, game state, tactical manager instructions, or minutes played when defending a lead versus chasing a deficit.',
  },
];

const HYPOTHESES = [
  {
    id: 'H1',
    title: 'Space Control & Value (H1)',
    body: 'Quantifies a player\'s ability to dominate territory and break lines through Progression, Dangerousness, Reception, and Gravity, establishing spatial influence within macro roles.',
  },
  {
    id: 'H2',
    title: 'Decision Quality (H2)',
    body: 'Evaluates decision-making efficacy by combining technical accuracy, duel robustness, and high-value risk reading under cognitive load, separating conservative passers from decisive playmakers.',
  },
  {
    id: 'H4',
    title: 'Player Similarity (H4)',
    body: 'Constructs an 8-axis stylistic DNA combining Space Control and Decision Quality dimensions, enabling within-role nearest-neighbour look-alike discovery and market-value arbitrage.',
  },
];

export default function Home() {
  return (
    <div className="w-full pb-20 min-h-screen">

      {/* ── Hero ────────────────────────────────────────────────────────────── */}
      <div className="border-b border-[var(--border)] px-6 pt-10 pb-8 bg-[var(--surface)]">
        <div className="max-w-[1200px] mx-auto">
          {/* Fork badge */}
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-[var(--accent)]/40 bg-[var(--accent)]/10 text-xs font-mono font-medium text-[var(--accent)] mb-4">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <line x1="6" y1="3" x2="6" y2="15" />
              <circle cx="18" cy="6" r="3" />
              <circle cx="6" cy="18" r="3" />
              <path d="M18 9a9 9 0 0 1-9 9" />
            </svg>
            <span>
              Fork of{' '}
              <a
                href="https://github.com/ArMat-Analytics/Contextual-Football-Scouting"
                target="_blank"
                rel="noreferrer"
                className="underline font-semibold hover:text-[var(--text)] transition-colors"
              >
                Contextual Football Scouting
              </a>
            </span>
          </div>

          <h1 className="font-display font-black text-5xl sm:text-6xl leading-none tracking-tight text-[var(--text)]">
            Contextual<br />Football Scouting
            <span className="block text-2xl sm:text-3xl font-semibold text-[var(--accent)] mt-2">
              Wyscout Integration
            </span>
          </h1>

          {/* Main title description */}
          <p className="mt-4 text-base sm:text-lg text-[var(--text-muted)] mb-6 leading-relaxed">
            This project is a dedicated <strong>fork</strong> of{' '}
            <a
              href="https://github.com/ArMat-Analytics/Contextual-Football-Scouting"
              target="_blank"
              rel="noreferrer"
              className="font-semibold text-[var(--text)] hover:text-[var(--accent)] underline transition-colors"
            >
              Contextual Football Scouting
            </a>
            . It integrates the contextual scouting methodology with <strong>Wyscout seasonal aggregated data (<code className="text-xs bg-[var(--surface2)] px-1.5 py-0.5 rounded font-mono">data/wyscout_sample.csv</code>)</strong>, translating spatial influence and decision quality into statistical proxies processed <strong>100% in-memory</strong>.
          </p>

          {/* Separator line */}
          <div className="w-full h-px bg-[var(--border)] mb-8" />
          <div className="w-full">
            {/* Analytical Challenge */}
            <div className="flex items-start gap-3 mt-2 mb-1">
              <span className="mt-1">
                {/* Target SVG */}
                <svg width="22" height="22" fill="none" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" stroke="var(--accent)" strokeWidth="2"/><circle cx="12" cy="12" r="4" stroke="var(--accent)" strokeWidth="2"/><circle cx="12" cy="12" r="1.5" fill="var(--accent)"/></svg>
              </span>
              <h2 className="font-display font-bold text-[20px] text-[var(--text)] m-0">The Analytical Challenge</h2>
            </div>
            <p className="text-[16px] text-[var(--text-muted)] mb-5">
              Within the modern transfer market, one of the most significant challenges is the phenomenon of "Team Bias". Clubs frequently overvalue players based on superficial statistical outputs that are often a byproduct of a dominant team structure rather than an accurate reflection of exceptional individual talent. It remains highly difficult to objectively evaluate an athlete without the compounding influence of their respective team's tactical system.
            </p>
            {/* Our Objective */}
            <div className="flex items-start gap-3 mt-6 mb-1">
              <span className="mt-1">
                {/* Compass SVG */}
                <svg width="22" height="22" fill="none" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" stroke="var(--accent)" strokeWidth="2"/><polygon points="12,7 15,17 12,15 9,17" fill="var(--accent)"/></svg>
              </span>
              <h2 className="font-display font-bold text-[20px] text-[var(--text)] m-0">Our Objective</h2>
            </div>
            <p className="text-[16px] text-[var(--text-muted)] mb-5">
              The primary objective of this project is to shift the analytical paradigm from descriptive to explanatory observations. By mapping the contextual and spatial principles of the original framework onto Wyscout seasonal metrics, we evaluate player performance relative to role-specific benchmarks and defensive actions. This methodology allows scouts to uncover undervalued talent operating across different tactical setups.
            </p>
            {/* Who We Are */}
            <div className="flex items-start gap-3 mt-6 mb-1">
              <span className="mt-1">
                {/* Users SVG */}
                <svg width="22" height="22" fill="none" viewBox="0 0 24 24"><circle cx="8" cy="10" r="3" stroke="var(--accent)" strokeWidth="2"/><circle cx="16" cy="10" r="3" stroke="var(--accent)" strokeWidth="2"/><path d="M2 20c0-2.5 3-4.5 6-4.5s6 2 6 4.5" stroke="var(--accent)" strokeWidth="2"/><path d="M14 20c0-1.5 2-2.5 4-2.5s4 1 4 2.5" stroke="var(--accent)" strokeWidth="2"/></svg>
              </span>
              <h2 className="font-display font-bold text-[20px] text-[var(--text)] m-0">Who We Are</h2>
            </div>
            <p className="text-[16px] text-[var(--text-muted)] leading-relaxed">
              We are <a href="https://www.linkedin.com/in/matteo-vezzoli83" target="_blank" rel="noreferrer" className="inline-flex items-center gap-0.5 font-semibold text-[var(--text)] hover:text-[var(--accent)] transition-colors">Matteo Vezzoli<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg></a> and <a href="https://www.linkedin.com/in/armando-mio" target="_blank" rel="noreferrer" className="inline-flex items-center gap-0.5 font-semibold text-[var(--text)] hover:text-[var(--accent)] transition-colors">Armando Mio<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg></a>, and we present this project as the culmination of our academic journey at the <a href="https://barcainnovationhub.fcbarcelona.com/" target="_blank" rel="noreferrer" className="inline-flex items-center gap-0.5 font-semibold text-[var(--text)] hover:text-[var(--accent)] transition-colors">Barça Innovation Hub<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg></a>.
              <br /><br />
              For the full theoretical framing, research paper, and upstream methodology, visit the main <a href="https://github.com/ArMat-Analytics/Contextual-Football-Scouting" target="_blank" rel="noreferrer" className="inline-flex items-center gap-0.5 font-semibold text-[var(--text)] hover:text-[var(--accent)] transition-colors">Contextual Football Scouting repository<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg></a>, or inspect this integration fork at <a href="https://github.com/ArMat-Analytics/CFS_Wyscout_Integration" target="_blank" rel="noreferrer" className="inline-flex items-center gap-0.5 font-semibold text-[var(--text)] hover:text-[var(--accent)] transition-colors">CFS_Wyscout_Integration<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg></a>.
            </p>
          </div>
        </div>
      </div>

      {/* ── Project Hypotheses ──────────────────────────────────────────────── */}
      <div className="px-6 pt-14 pb-4 bg-[var(--surface2)] border-b border-[var(--border)]">
        <div className="max-w-[1200px] mx-auto">
          {/* Section header */}
          <div className="mb-10 pb-6 border-b border-[var(--border)]">
            <h2
              className="font-display font-black tracking-tight mb-3 text-[var(--text)]"
              style={{ fontSize: 'clamp(24px, 4vw, 36px)' }}
            >
              Project Hypotheses
            </h2>
            <p className="text-[15px] leading-relaxed text-[var(--text-muted)]">
              This project is built upon three core hypotheses that aim to quantify the contextual value of player actions on the pitch.
            </p>
          </div>

          {/* Hypotheses list */}
          <ol className="flex flex-col divide-y divide-[var(--border)]" aria-label="Project Hypotheses">
            {HYPOTHESES.map((item) => (
              <li key={item.id} className="flex gap-5 sm:gap-8 py-5 items-baseline">
                {/* Number */}
                <span
                  className="font-mono text-[15px] font-bold text-[var(--accent)] shrink-0 w-6 text-right select-none"
                  aria-hidden
                >
                  {item.id}
                </span>
                {/* Content */}
                <p className="text-[14px] text-[var(--text-muted)] leading-[1.7] m-0">
                  <strong className="font-semibold text-[var(--text)] mr-2">{item.title}.</strong>
                  {item.body}
                </p>
              </li>
            ))}
          </ol>
        </div>
      </div>

      {/* ── Data scope & limitations ────────────────────────────────────────── */}
      <div className="px-6 pt-14 pb-4">
        <div className="max-w-[1200px] mx-auto">

          {/* Section header */}
          <div className="mb-10 pb-6 border-b border-[var(--border)]">
            <h2
              className="font-display font-black tracking-tight mb-3 text-[var(--text)]"
              style={{ fontSize: 'clamp(24px, 4vw, 36px)' }}
            >
              Data scope and limitations
            </h2>
            <p className="text-[15px] leading-relaxed text-[var(--text-muted)]">
              All metrics on this platform are computed from Wyscout seasonal aggregated data (<code className="text-xs bg-[var(--surface2)] px-1.5 py-0.5 rounded font-mono">wyscout_sample.csv</code>) using statistical proxy mappings and within-role percentile rankings.
            </p>
          </div>

          {/* Limitations list */}
          <ol className="flex flex-col divide-y divide-[var(--border)]" aria-label="Limitations">
            {LIMITATIONS.map((item, i) => (
              <li key={i} className="flex gap-5 sm:gap-8 py-5 items-baseline">
                {/* Number */}
                <span
                  className="font-mono text-[15px] font-bold text-[var(--accent)] shrink-0 w-6 text-right select-none"
                  aria-hidden
                >
                  {String(i + 1).padStart(2, '0')}
                </span>
                {/* Content */}
                <p className="text-[14px] text-[var(--text-muted)] leading-[1.7] m-0">
                  <strong className="font-semibold text-[var(--text)] mr-2">{item.title}.</strong>
                  {item.body}
                </p>
              </li>
            ))}
          </ol>

        </div>
      </div>

    </div>
  );
}