import { useState, useEffect, useRef } from 'react';
import { useDebounce } from '../hooks/useDebounce';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

export interface FilterState {
  ageMin: string; ageMax: string;
  macroRole: string;
  role: string; foot: string;
  vPreMin: string; vPreMax: string;
  vPostMin: string; vPostMax: string;
  vDiffMin: string; vDiffMax: string;
}

interface FiltersProps {
  filters: FilterState;
  setFilters: (f: FilterState) => void;
}

const MACRO_ROLES = ['CB', 'FB', 'MID', 'CAM', 'WIDE', 'FW'];

const ROLE_TO_MACRO: Record<string, string> = {
  'Center Back': 'CB', 'Left Center Back': 'CB', 'Right Center Back': 'CB',
  'Left Back': 'FB', 'Right Back': 'FB', 'Left Wing Back': 'FB', 'Right Wing Back': 'FB',
  'Center Defensive Midfield': 'MID', 'Left Defensive Midfield': 'MID', 'Right Defensive Midfield': 'MID',
  'Left Center Midfield': 'MID', 'Right Center Midfield': 'MID', 'Left Midfield': 'MID', 'Right Midfield': 'MID',
  'Center Attacking Midfield': 'CAM', 'Left Attacking Midfield': 'CAM', 'Right Attacking Midfield': 'CAM',
  'Left Wing': 'WIDE', 'Right Wing': 'WIDE',
  'Center Forward': 'FW', 'Left Center Forward': 'FW', 'Right Center Forward': 'FW',
};

export default function Filters({ filters, setFilters }: FiltersProps) {
  const [isOpen, setIsOpen]           = useState(false);
  const [allRoles, setRoles]          = useState<string[]>([]);
  const panelRef                      = useRef<HTMLDivElement>(null);
  const btnRef                        = useRef<HTMLButtonElement>(null);

  // Internal draft state for immediate input responsiveness
  const [draft, setDraft] = useState<FilterState>(filters);
  const debouncedDraft = useDebounce(draft, 300);

  // Sync debounced draft → parent
  const setFiltersRef = useRef(setFilters);
  setFiltersRef.current = setFilters;
  useEffect(() => {
    setFiltersRef.current(debouncedDraft);
  }, [debouncedDraft]);

  // Sync parent → draft when parent resets filters (e.g. "Clear All")
  const prevFiltersRef = useRef(filters);
  useEffect(() => {
    // Only sync if parent changed from outside (not from our own debounce)
    if (JSON.stringify(filters) !== JSON.stringify(prevFiltersRef.current)) {
      prevFiltersRef.current = filters;
      setDraft(filters);
    }
  }, [filters]);
  useEffect(() => { prevFiltersRef.current = debouncedDraft; }, [debouncedDraft]);

  useEffect(() => {
    fetch(`${API_BASE_URL}/roles/`)
      .then(r => r.json())
      .then(d => setRoles(d))
      .catch(() => {});
  }, []);

  const availableRoles = draft.macroRole
    ? allRoles.filter(role => ROLE_TO_MACRO[role] === draft.macroRole)
    : allRoles;

  useEffect(() => {
    if (draft.role && !availableRoles.includes(draft.role)) {
      setDraft(d => ({ ...d, role: '' }));
    }
  }, [availableRoles, draft.role]);

  // Close on outside click
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: MouseEvent) => {
      if (
        panelRef.current && !panelRef.current.contains(e.target as Node) &&
        btnRef.current   && !btnRef.current.contains(e.target as Node)
      ) setIsOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [isOpen]);

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') setIsOpen(false); };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setDraft(d => ({ ...d, [e.target.name]: e.target.value }));
  };

  const reset = () => {
    const empty: FilterState = { ageMin:'', ageMax:'', macroRole:'', role:'', foot:'', vPreMin:'', vPreMax:'', vPostMin:'', vPostMax:'', vDiffMin:'', vDiffMax:'' };
    setDraft(empty);
    setFilters(empty);
  };

  const active = Object.values(filters).some(v => v !== '');
  const activeCount = Object.values(filters).filter(v => v !== '').length;

  return (
    <div className="relative">
      <button
        ref={btnRef}
        onClick={() => setIsOpen(o => !o)}
        aria-expanded={isOpen}
        aria-controls="filters-panel"
        aria-label={`Advanced filters${active ? ` (${activeCount} active)` : ''}`}
        className={`btn btn-ghost h-full whitespace-nowrap ${active ? 'border-[var(--accent)] text-[var(--accent)]' : ''}`}
      >
        <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 4h18M7 8h10M11 12h2M13 16h-2" />
        </svg>
        {active ? `Filters (${activeCount})` : 'Filters'}
      </button>

      {isOpen && (
        <div
          id="filters-panel"
          ref={panelRef}
          role="dialog"
          aria-label="Advanced filters"
          className="absolute right-0 top-full mt-2 w-[480px] max-sm:w-[calc(100vw-3rem)] z-50 p-6 max-h-[80vh] overflow-y-auto bg-[var(--surface)] border border-[var(--border2)] rounded-[var(--radius-lg)] shadow-xl"
        >
          <div className="flex justify-between items-center mb-8 border-b border-[var(--border)] pb-4">
            <h2 className="font-display font-extrabold text-2xl tracking-tight text-[var(--text)]">
              Advanced Filters
            </h2>
            <button
              onClick={() => setIsOpen(false)}
              aria-label="Close filters panel"
              className="w-8 h-8 rounded-full flex items-center justify-center text-sm transition-colors hover:text-[var(--text)] bg-[var(--surface2)] text-[var(--text-muted)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
            >
              ✕
            </button>
          </div>

          <div className="space-y-6">
            <fieldset className="border border-[var(--border2)] p-4 rounded-xl">
              <legend className="text-xs font-mono font-bold tracking-widest uppercase px-2 text-[var(--accent)]">
                General Attributes
              </legend>
              <div className="grid grid-cols-2 gap-4 mt-2">
                <div>
                  <label htmlFor="ageMin" className="block text-xs font-semibold mb-1 text-[var(--text-muted)]">Min Age</label>
                  <input id="ageMin" type="number" name="ageMin" value={draft.ageMin} onChange={handleChange} placeholder="e.g. 18" className="input" min={15} max={50} />
                </div>
                <div>
                  <label htmlFor="ageMax" className="block text-xs font-semibold mb-1 text-[var(--text-muted)]">Max Age</label>
                  <input id="ageMax" type="number" name="ageMax" value={draft.ageMax} onChange={handleChange} placeholder="e.g. 35" className="input" min={15} max={50} />
                </div>
                <div>
                  <label htmlFor="macroRole" className="block text-xs font-semibold mb-1 text-[var(--text-muted)]">Macro Role</label>
                  <select id="macroRole" name="macroRole" value={draft.macroRole} onChange={handleChange} className="input">
                    <option value="">All Macro Roles</option>
                    {MACRO_ROLES.map(r => (
                      <option key={r} value={r}>{r}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label htmlFor="role" className="block text-xs font-semibold mb-1 text-[var(--text-muted)]">Role</label>
                  <select id="role" name="role" value={draft.role} onChange={handleChange} className="input">
                    <option value="">All Roles</option>
                    {availableRoles.map(r => (
                      <option key={r} value={r}>{r.replace(/_/g, ' ')}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label htmlFor="foot" className="block text-xs font-semibold mb-1 text-[var(--text-muted)]">Preferred Foot</label>
                  <select id="foot" name="foot" value={draft.foot} onChange={handleChange} className="input">
                    <option value="">Any Foot</option>
                    <option value="right">Right</option>
                    <option value="left">Left</option>
                    <option value="both">Both</option>
                  </select>
                </div>
              </div>
            </fieldset>

            <fieldset className="border border-[var(--border2)] p-4 rounded-xl">
              <legend className="text-xs font-mono font-bold tracking-widest uppercase px-2 text-[var(--blue)]">
                Market Value (€)
              </legend>
              <div className="space-y-4 mt-2">
                {[
                  { label: 'Value BEFORE Euro 2024', minKey: 'vPreMin', maxKey: 'vPreMax' },
                  { label: 'Value AFTER Euro 2024',  minKey: 'vPostMin', maxKey: 'vPostMax' },
                  { label: 'Value Difference',       minKey: 'vDiffMin', maxKey: 'vDiffMax' },
                ].map(({ label, minKey, maxKey }) => (
                  <div key={minKey} className="grid grid-cols-2 gap-4">
                    <div>
                      <label htmlFor={minKey} className="block text-[10px] font-semibold mb-1 text-[var(--text-muted)]">Min {label}</label>
                      <input id={minKey} type="number" name={minKey} value={(draft as any)[minKey]} onChange={handleChange} placeholder="Min €" className="input" />
                    </div>
                    <div>
                      <label htmlFor={maxKey} className="block text-[10px] font-semibold mb-1 text-[var(--text-muted)]">Max {label}</label>
                      <input id={maxKey} type="number" name={maxKey} value={(draft as any)[maxKey]} onChange={handleChange} placeholder="Max €" className="input" />
                    </div>
                  </div>
                ))}
              </div>
            </fieldset>
          </div>

          <div className="mt-8">
            <button onClick={reset} className="btn btn-ghost w-full justify-center" aria-label="Clear all filters">
              Clear All Filters
            </button>
          </div>
        </div>
      )}
    </div>
  );
}