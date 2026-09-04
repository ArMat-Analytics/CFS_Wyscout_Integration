const LIMITATIONS = [
  // — The data is a snapshot, not a film —
  {
    title: 'A single instant, not a film',
    body: 'Each metric reads the pitch at the moment the pass is played, not the movement before it or the ball trajectory after. It describes the geometry of the decision, not how it unfolds. Speed at reception, acceleration, distance covered and pressing intensity over time cannot be measured, and a player standing in a dangerous zone scores the same as one sprinting into it at that instant.',
  },
  {
    title: 'Pressure read from distance alone',
    body: 'A frame shows where defenders are, not their physical state: a defender 2 m away may be jogging or sprinting in to tackle, and the snapshot cannot tell them apart. Pressure here approximates threat from distance only.',
  },
  // — The frame sees little, and names no one —
  {
    title: 'Partial player coverage',
    body: 'A 360 frame usually shows 8 to 12 of the 22 players, those near the ball. Players far from the action are often missing, so anything measured far from the ball is less reliable.',
  },
  {
    title: 'Anonymous opponents and teammates',
    body: 'Only the player on the ball is named; everyone else carries just a team tag. The model cannot weight opposition by quality, so beating a top defender counts the same as beating a weak one, and a pass into a dangerous zone is valued by the zone, not by who would receive it.',
  },
  // — What the model leaves out —
  {
    title: 'No game state',
    body: 'Decisions are graded on value alone. Score, time left, match importance and manager instructions are ignored, so a deliberately safe choice late in a game reads as conservative rather than smart.',
  },
  {
    title: 'Not every visible option is a real choice',
    body: 'Decision Quality grades a pass against the teammates the player could reach in that frame. It treats every reachable option as part of the decision, but football is messier: some visible options are easy to reach yet tactically pointless, and the metric still counts them as choices the player beat. Options that are hard or impossible to complete are already down-weighted, since each one is scored by how likely the pass is to arrive, so the main gap is tactical: the model sees who was reachable, not whether passing there made sense. Read the score as how well the player ranked his pick among the available options, not as an absolute verdict on the pass.',
  },
  {
    title: 'Built on base models, shared across hypotheses',
    body: 'The indices sit on top of an EPV model (adapted from Friends of Tracking) and a custom pass-completion model (built for H2 and reused by H3). Any error in these base models carries through into the metrics above them. And because H2 and H3 read H1\'s player pool, roles and EPV from the same files, a bias in those shared foundations would show up in all three at once rather than as a disagreement between them.',
  },
  // — Sample and validation —
  {
    title: 'Single tournament, small samples',
    body: 'All data come from Euro 2024 alone, so patterns may not carry over to club football or other competitions. Players need at least 135 minutes (about 1.5 matches) to be included, and per-role pools are small: a low-sample player has a noisy ranking that can also nudge the players around him. The sample size is always shown so low-sample profiles can be discounted.',
  },
  {
    title: 'Some things have no ground truth',
    body: 'H2 compares the chosen pass against the alternatives the player could have played. Those alternatives were never actually played, so there is no real outcome to check them against; the index limits this by only needing the options ordered roughly right. H3 has a similar gap: the off-ball identities are reconstructed by estimating each anonymous teammate\'s position and matching it to their recent on-ball events. That is validated against StatsBomb\'s actual pass recipient and is accurate on the high-confidence assignments it keeps, but it remains an estimate, not a certainty.',
  },
  {
    title: 'Off-ball score depends on teammates too',
    body: 'The Uncapitalized Run Score counts an off-ball run only when teammates do not serve it, so part of the score reflects how well his teammates see and execute the pass, not the player alone: a good mover surrounded by weaker passers can post a high score because his runs keep going unused. This is by design, not an error. The score splits into Off-Ball Potential — the value he exposes, which is player-only — and Latency, the share left unserved, where teammates enter; the two are nearly independent, so read Potential for the cleanest individual signal and the headline as off-ball value in his current team context. Read this way it complements Decision Quality: one grades him as the passer, the other shows how often his own off-ball offers go unused.',
  },
  {
    title: 'Team bias reduced, not removed',
    body: 'Grading players by the value of what they do rather than the volume, and then ranking them within their role, removes most of the team bias that distorts raw stats. What it cannot remove is exposure: a player in a possession-dominant side still appears in more freeze frames, and gets more chances to add value, than an equal player in a pressed side.',
  },
];

const HYPOTHESES = [
  {
    title: 'Space Control & Value',
    body: 'It is posited that a player\'s quality is measurable by their spatial influence on the pitch. The methodology will explore the use of Convex Hulls to quantify defensive territorial control and evaluate an attacker\'s ability to penetrate it. Utilizing Expected Possession Value (EPV), the objective is to identify "Line Breakers", who are players capable of executing passes that bypass defensive structures and significantly elevate the probability of scoring.',
  },
  {
    title: 'Decision Quality',
    body: 'Aggregate pass completion rates lack analytical value when devoid of contextual factors. This phase will analyze "Passing under Pressure" by measuring the proximity of defending players. The aim is to assess decision-making efficacy: specifically, whether the player selected the optimal passing lane relative to immediate defensive danger. This differentiation facilitates the separation of players who default to conservative actions from those who exhibit tactical astuteness under high cognitive load.',
  },
  {
    title: 'Off-Ball Movement',
    body: 'The vast majority of a player\'s on-pitch activity occurs out of possession. This investigation seeks to identify players executing high-value attacking runs that are ultimately not capitalized upon by teammates. Analyzing 360-degree spatial frames enables the detection of players who consistently occupy and attack dangerous areas, thereby quantifying a latent dimension of offensive contribution regardless of ball reception.',
  },
];

export default function Home() {
  return (
    <div className="w-full pb-20 min-h-screen">

      {/* ── Hero ────────────────────────────────────────────────────────────── */}
      <div className="border-b border-[var(--border)] px-6 pt-10 pb-8 bg-[var(--surface)]">
        <div className="max-w-[1200px] mx-auto">
          <h1 className="font-display font-black text-5xl sm:text-6xl leading-none tracking-tight text-[var(--text)]">
            Contextual<br />Football Scouting
          </h1>
          {/* Main title description */}
          <p className="mt-3 text-base text-[var(--text-muted)] mb-6">
            A new paradigm for football scouting: quantifying player value through context-aware analytics, advanced spatial data, and contextual decision quality. Discover the difference between individual talent and systemic advantage.
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
              The primary objective of this project is to shift the analytical paradigm from descriptive to explanatory observations. By incorporating the geometric and spatial context provided by 360-degree data, we evaluate elements often obscured by standard statistics, such as optimal spatial positioning and the quality of a player's decisions relative to the defensive pressure around them. This methodology allows us to determine whether elite performance is a function of individual talent or systemic advantage, providing the optimal approach for uncovering undervalued talent currently operating within less prominent clubs.
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
              We are <a href="https://www.linkedin.com/in/matteo-vezzoli83" target="_blank" rel="noreferrer" className="inline-flex items-center gap-0.5 font-semibold text-[var(--text)] hover:text-[var(--accent)] transition-colors">Matteo Vezzoli<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg></a> and <a href="https://www.linkedin.com/in/armando-mio" target="_blank" rel="noreferrer" className="inline-flex items-center gap-0.5 font-semibold text-[var(--text)] hover:text-[var(--accent)] transition-colors">Armando Mio<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg></a>, and we present this project as the culmination of our academic journey at the <a href="https://barcainnovationhub.fcbarcelona.com/" target="_blank" rel="noreferrer" className="inline-flex items-center gap-0.5 font-semibold text-[var(--text)] hover:text-[var(--accent)] transition-colors">Barça Innovation Hub<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg></a>. Motivated by a rigorous interest in data science applied to football, our work focuses on uncovering the latent variables of a match that frequently escape standard statistical frameworks.
              <br /><br />
              For more information, you can view our <a href="https://github.com/ArMat-Analytics/Contextual-Football-Scouting" target="_blank" rel="noreferrer" className="inline-flex items-center gap-0.5 font-semibold text-[var(--text)] hover:text-[var(--accent)] transition-colors">GitHub repository<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg></a>.
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
            {HYPOTHESES.map((item, i) => (
              <li key={i} className="flex gap-5 sm:gap-8 py-5 items-baseline">
                {/* Number */}
                <span
                  className="font-mono text-[15px] font-bold text-[var(--accent)] shrink-0 w-6 text-right select-none"
                  aria-hidden
                >
                  H{i + 1}
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
              All metrics on this site come from StatsBomb 360 freeze-frame data combined with predictive models. This is what they can, and cannot, describe.
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