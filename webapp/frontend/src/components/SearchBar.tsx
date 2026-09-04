interface SearchBarProps {
  searchTerm: string;
  setSearchTerm: (value: string) => void;
}

export default function SearchBar({ searchTerm, setSearchTerm }: SearchBarProps) {
  return (
    <div className="relative h-full">
      <label htmlFor="player-search" className="sr-only">Search player by name</label>
      <input
        id="player-search"
        type="search"
        value={searchTerm}
        onChange={(e) => setSearchTerm(e.target.value)}
        placeholder="Search player by name…"
        autoComplete="off"
        className="input w-full h-full pl-11 pr-10"
        aria-label="Search player by name"
      />
      <svg
        aria-hidden
        className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 pointer-events-none text-[var(--text-dim)]"
        xmlns="http://www.w3.org/2000/svg"
        fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}
      >
        <circle cx="11" cy="11" r="8" /><path d="M21 21l-4.35-4.35" />
      </svg>
      {searchTerm && (
        <button
          onClick={() => setSearchTerm('')}
          aria-label="Clear search"
          className="absolute right-3 top-1/2 -translate-y-1/2 w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold transition-colors bg-[var(--surface2)] text-[var(--text-muted)] hover:text-[var(--text)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
        >
          ✕
        </button>
      )}
    </div>
  );
}