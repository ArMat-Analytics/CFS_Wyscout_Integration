import { useState } from 'react';
import { Link } from 'react-router-dom';
import { GLOSSARY_SECTIONS, type GlossaryCategory } from '../data/glossary';

// ── Category filter pill ──────────────────────────────────────────────────────

type FilterKey = GlossaryCategory | 'ALL' | 'COMMON_PREMISES';

const FILTER_OPTIONS: { key: FilterKey; label: string }[] = [
  { key: 'ALL',             label: 'All' },
  { key: 'COMMON_PREMISES', label: 'Common premises' },
  { key: 'PROGRESSION',     label: 'Progression' },
  { key: 'DANGEROUSNESS',   label: 'Dangerousness' },
  { key: 'RECEPTION',       label: 'Reception' },
  { key: 'GRAVITY',         label: 'Gravity' },
  { key: 'DECISION_QUALITY',label: 'Decision Quality' },
  { key: 'OFF_BALL_MOVEMENT',label: 'Off-Ball Movement' },
];

const CATEGORY_COLORS: Record<string, string> = {
  COMMON_PREMISES: '#0d9488',
  PROGRESSION:  '#16a34a',
  DANGEROUSNESS:'#dc2626',
  RECEPTION:    '#2563eb',
  GRAVITY:      '#d97706',
  DECISION_QUALITY: '#7c3aed',
  OFF_BALL_MOVEMENT: '#9cc507',
};

// ── Entry card ────────────────────────────────────────────────────────────────

function EntryCard({ label, description, color }: { label: string; description: string; color: string }) {
  return (
    <div
      className="card-inner p-4 flex flex-col gap-2 transition-all hover:scale-[1.01]"
      style={{ borderLeft: `3px solid ${color}` }}
    >
      <span
        className="font-mono text-xs font-bold tracking-wide text-[var(--text)]"
      >
        {label}
      </span>
      <p className="text-xs leading-relaxed text-[var(--text-muted)]">
        {description}
      </p>
    </div>
  );
}

// ── Section block ─────────────────────────────────────────────────────────────

function SectionBlock({
  title, color, intro, entries, category,
}: {
  title: string;
  color: string;
  intro: string;
  entries: { label: string; description: string }[];
  category: GlossaryCategory;
}) {
  return (
    <section
      id={`section-${category}`}
      aria-labelledby={`heading-${category}`}
      style={{ scrollMarginTop: '80px' }}
    >
      {/* Section header */}
      <div className="flex items-center gap-4 mb-5 pb-4 border-b border-[var(--border)]">
        {/* Colour swatch */}
        <span
          aria-hidden
          className="inline-block w-3 h-3 rounded-sm shrink-0"
          style={{ background: color }}
        />
        <h2
          id={`heading-${category}`}
          className="font-display font-black text-2xl tracking-tight text-[var(--text)]"
        >
          {title}
        </h2>
        {/* Variable count tag */}
      </div>

      {/* Intro paragraph */}
      <p className="text-sm leading-relaxed mb-6 text-[var(--text-muted)]">
        {intro}
      </p>

      {/* Entry grid */}
      <div
        className="grid gap-3"
        style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))' }}
      >
        {entries.map(entry => (
          <EntryCard
            key={entry.label}
            label={entry.label}
            description={entry.description}
            color={color}
          />
        ))}
      </div>
    </section>
  );
}

// ── Glossary page ─────────────────────────────────────────────────────────────

export default function Glossary() {
  const [activeFilter, setActiveFilter] = useState<FilterKey>('ALL');

  const visibleSections =
    activeFilter === 'ALL'
      ? GLOSSARY_SECTIONS
      : activeFilter === 'COMMON_PREMISES'
      ? []
      : GLOSSARY_SECTIONS.filter(s => s.category === activeFilter);

  return (
    <div className="w-full pb-20 min-h-screen">

      {/* ── Hero ──────────────────────────────────────────────────────────── */}
      <div className="border-b border-[var(--border)] px-6 pt-10 pb-8 bg-[var(--surface)]">
        <div className="max-w-[1200px] mx-auto">

          {/* Breadcrumb */}
          <nav aria-label="Breadcrumb" className="mb-4">
            <ol className="flex items-center gap-2 text-sm text-[var(--text-muted)]">
              <li>
                <Link to="/" className="hover:text-[var(--accent)] transition-colors font-semibold">
                  Home
                </Link>
              </li>
              <li aria-hidden>/</li>
              <li className="font-semibold text-[var(--text)]" aria-current="page">
                Glossary
              </li>
            </ol>
          </nav>

          <h1 className="font-display font-black text-5xl sm:text-6xl leading-none tracking-tight text-[var(--text)]">
            Glossary
          </h1>
          <p className="mt-3 text-base text-[var(--text-muted)]">
            Definitions of every metric on the platform. The variables are grouped by hypothesis: Space Control (H1), Decision Quality (H2) and Off-Ball Movement (H3). A few premises are shared by all three and are worth reading once before the individual cards below.
          </p>
        </div>
      </div>

      {/* ── Filter bar ─────────────────────────────────────────────── */}
      <div className="border-b border-[var(--border)] z-40 px-6 py-3 bg-white/92 backdrop-blur-xl">
        <div className="max-w-[1200px] mx-auto flex flex-wrap justify-center items-center gap-2">
          <span className="font-mono text-[10px] tracking-widest uppercase mr-2 hidden sm:inline text-[var(--text-dim)]">
            Filter
          </span>
          {FILTER_OPTIONS.map(opt => {
            const active = activeFilter === opt.key;
            const color  = opt.key === 'ALL' ? 'var(--accent)' : (CATEGORY_COLORS[opt.key] ?? 'var(--accent)');
            return (
              <button
                key={opt.key}
                onClick={() => setActiveFilter(opt.key)}
                aria-pressed={active}
                className="tag transition-all cursor-pointer"
                style={{
                  border: `1px solid ${active ? color : 'var(--border)'}`,
                  background: active ? `${color}11` : 'var(--surface)',
                  color: active ? color : 'var(--text-muted)',
                  fontWeight: active ? 700 : 600,
                }}
              >
                {opt.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* ── Main content ──────────────────────────────────────────────────── */}
      <div className="max-w-[1200px] mx-auto px-6 pt-10">
        
        {(activeFilter === 'ALL' || activeFilter === 'COMMON_PREMISES') && (
          <section className="mb-14">
            <div className="flex items-center gap-4 mb-5 pb-4 border-b border-[var(--border)]">
              <span
                aria-hidden
                className="inline-block w-3 h-3 rounded-sm shrink-0"
                style={{ background: CATEGORY_COLORS['COMMON_PREMISES'] }}
              />
              <h2 className="font-display font-black text-2xl tracking-tight text-[var(--text)]">
                Common premises
              </h2>
            </div>
            
            <div
              className="grid gap-3"
              style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))' }}
            >
              <EntryCard
                label="What the '360 freeze frame' is"
                description='For every open-play pass StatsBomb provides 360 data for, we know the (x, y) positions of the visible players at the instant the pass is released: who is behind the ball line, who is in front, where the opponents are. This is what lets us move from "total passes" to "passes in the context they were played in", and it is the shared foundation of all three hypotheses.'
                color={CATEGORY_COLORS['COMMON_PREMISES']}
              />
              <EntryCard
                label="Player pool"
                description="A player needs at least 135 minutes (about 1.5 matches) to be included: 272 players in total, one row per player. The same pool is used across H1, H2 and H3, so a profile is directly comparable from one hypothesis to the next. Below that threshold the numbers rest on too few events and become noisy."
                color={CATEGORY_COLORS['COMMON_PREMISES']}
              />
              <EntryCard
                label="Macro-roles"
                description="Every within-role percentile on the site is computed inside the player's macro-role: CB, FB, MID, CAM, WIDE, FW. A full-back at the 90th percentile is &quot;among the best full-backs&quot;, not &quot;among all players&quot;. A player's macro-role is the role he actually played most across the tournament, which can differ from his nominal position."
                color={CATEGORY_COLORS['COMMON_PREMISES']}
              />
              <EntryCard
                label="Open play only"
                description="All metrics look at open play only. Set pieces (corners, free kicks, throw-ins, kick-offs and goal kicks) are left out, because they are rehearsed situations that follow their own logic and would distort a measure built to read the flow of the game. What each hypothesis then counts underneath differs by design: H1 reads the passes a player attempts, H2 reads the passing decisions he faces, and H3 reads the off-ball positions he takes up while a teammate has the ball."
                color={CATEGORY_COLORS['COMMON_PREMISES']}
              />
            </div>
          </section>
        )}

        <div className="flex flex-col gap-14">
          {visibleSections.map(section => (
            <SectionBlock
              key={section.category}
              category={section.category}
              title={section.title}
              color={section.color}
              intro={section.intro}
              entries={section.entries}
            />
          ))}
        </div>

        {/* Empty state when a filter yields nothing (defensive) */}
        {visibleSections.length === 0 && activeFilter !== 'COMMON_PREMISES' && (
          <div className="py-24 text-center text-[var(--text-dim)]">
            <p className="font-display font-bold text-xl">No variables found.</p>
          </div>
        )}
      </div>
    </div>
  );
}
