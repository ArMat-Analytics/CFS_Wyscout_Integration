import { useEffect, useState } from 'react';
import { getFlagUrl } from '../utils';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

interface Team { team_id: number; team_name: string; logo_url?: string; }
interface TeamListProps {
  selectedTeams: string[];
  setSelectedTeams: (teams: string[]) => void;
}

export default function TeamList({ selectedTeams, setSelectedTeams }: TeamListProps) {
  const [teams, setTeams] = useState<Team[]>([]);

  useEffect(() => {
    fetch(`${API_BASE_URL}/teams/`)
      .then(r => r.json())
      .then(d => setTeams(d))
      .catch(() => {});
  }, []);

  const toggleTeam = (name: string) => {
    if (!name) return;
    setSelectedTeams(
      selectedTeams.includes(name)
        ? selectedTeams.filter(t => t !== name)
        : [...selectedTeams, name]
    );
  };

  return (
    <section
      className="w-full mb-6"
      aria-label="Filter by national team"
    >
      <div className="max-w-[1200px] mx-auto px-6">
        <div className="mb-4 pb-2 border-b border-[var(--border)]">
          <p className="font-mono text-[10px] tracking-widest uppercase text-[var(--text-dim)]">
            Filter by National Team
          </p>
        </div>

        <ul
          className="flex flex-wrap items-center gap-x-2 gap-y-2"
          role="list"
          aria-label="National teams"
        >
          {teams.map((team, idx) => {
            const name     = team?.team_name || 'N/A';
            const selected = selectedTeams.includes(name);
            const flagUrl  = getFlagUrl(name);

            return (
              <li key={`team-${team.team_id ?? idx}`} role="listitem">
                <button
                  onClick={() => toggleTeam(name)}
                  aria-pressed={selected}
                  aria-label={name}
                  title={name}
                  className="flex items-center justify-center transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] rounded-full cursor-pointer"
                  style={{ opacity: selected ? 1 : 0.5 }}
                >
                  <div
                    className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-mono font-bold overflow-hidden shrink-0 transition-all bg-[var(--surface2)]"
                    style={{
                      border: selected ? '2px solid var(--accent)' : '2px solid transparent',
                      boxShadow: selected ? '0 4px 12px rgba(37,99,235,0.25)' : 'none',
                    }}
                  >
                    {flagUrl ? (
                      <img src={flagUrl} alt={name} className="w-full h-full object-cover" />
                    ) : team.logo_url ? (
                      <img src={team.logo_url} alt={name} className="w-6 h-6 object-contain" />
                    ) : (
                      <span className={selected ? 'text-[var(--text)]' : 'text-[var(--text-muted)]'}>
                        {name.substring(0,2).toUpperCase()}
                      </span>
                    )}
                  </div>
                </button>
              </li>
            );
          })}
          {selectedTeams.length > 0 && (
            <li role="listitem" className="ml-auto">
              <button
                onClick={() => setSelectedTeams([])}
                className="btn btn-ghost text-xs py-1.5 px-3 text-[var(--red)] h-8 rounded-full"
                aria-label="Clear all team filters"
              >
                Clear ({selectedTeams.length})
              </button>
            </li>
          )}
        </ul>
      </div>
    </section>
  );
}