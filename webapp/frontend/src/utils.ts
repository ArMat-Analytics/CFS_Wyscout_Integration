// ── Flag URL Helper ────────────────────────────────────────────────────────
// Maps national team names to ISO codes and fetches the SVG flag from flagcdn.

const NAME_TO_CODE: Record<string, string> = {
  // Group A
  'Germany': 'de', 'Scotland': 'gb-sct', 'Hungary': 'hu', 'Switzerland': 'ch',
  // Group B
  'Spain': 'es', 'Croatia': 'hr', 'Italy': 'it', 'Albania': 'al',
  // Group C
  'Slovenia': 'si', 'Denmark': 'dk', 'Serbia': 'rs', 'England': 'gb-eng',
  // Group D
  'Poland': 'pl', 'Netherlands': 'nl', 'Austria': 'at', 'France': 'fr',
  // Group E
  'Belgium': 'be', 'Slovakia': 'sk', 'Romania': 'ro', 'Ukraine': 'ua',
  // Group F
  'Turkey': 'tr', 'Türkiye': 'tr', 'Turkiye': 'tr', 'Georgia': 'ge', 'Portugal': 'pt', 'Czech Republic': 'cz',
  // Extras / alternate names
  'Czechia': 'cz', 'Czech': 'cz',
  'United Kingdom': 'gb', 'Great Britain': 'gb',
  'Russia': 'ru', 'Sweden': 'se', 'Norway': 'no', 'Finland': 'fi',
  'Iceland': 'is', 'Wales': 'gb-wls', 'Ireland': 'ie', 'Northern Ireland': 'gb-nir',
  'Greece': 'gr', 'Israel': 'il', 'Kosovo': 'xk',
  'North Macedonia': 'mk', 'Bosnia': 'ba', 'Montenegro': 'me',
  'Luxembourg': 'lu', 'Moldova': 'md', 'Armenia': 'am', 'Azerbaijan': 'az',
  'Kazakhstan': 'kz', 'Belarus': 'by', 'Estonia': 'ee', 'Latvia': 'lv',
  'Lithuania': 'lt', 'Malta': 'mt', 'Cyprus': 'cy', 'Andorra': 'ad',
  'San Marino': 'sm', 'Liechtenstein': 'li', 'Faroe Islands': 'fo',
  'Gibraltar': 'gi',
};

/** Returns the FlagCDN SVG URL for a given national team name. */
export function getFlagUrl(teamName?: string | null): string | null {
  if (!teamName) return null;
  const code = NAME_TO_CODE[teamName];
  if (!code) return null;
  return `https://flagcdn.com/${code}.svg`;
}

// ── Shared stat definitions ──────────────────────────────────────────────────
export const ALL_STATS = [
  /*{ key: 'minutes_played',      label: 'Minutes',          category: 'General',   unit: '' },*/
  { key: 'goals',               label: 'Goals',            category: 'Attacking', unit: '' },
  { key: 'xg_total',            label: 'xG',               category: 'Attacking', unit: '' },
  { key: 'assists',             label: 'Assists',          category: 'Attacking', unit: '' },
  { key: 'key_passes',          label: 'Key Passes',       category: 'Attacking', unit: '' },
  { key: 'dribbles_successful', label: 'Dribbles',         category: 'Attacking', unit: '' },
  { key: 'pass_completion_pct', label: 'Pass %',           category: 'Passing',   unit: '%' },
  { key: 'total_touches',       label: 'Touches',          category: 'Passing',   unit: '' },
  { key: 'ball_recoveries',     label: 'Recoveries',       category: 'Defending', unit: '' },
  { key: 'interceptions',       label: 'Interceptions',    category: 'Defending', unit: '' },
  /*{ key: 'aerials_won',         label: 'Aerials Won',      category: 'Defending', unit: '' },*/
] as const;

export type StatKey = typeof ALL_STATS[number]['key'];

export const CATEGORIES = ['General', 'Attacking', 'Passing', 'Defending'] as const;

export const CAT_ACCENT: Record<string, string> = {
  General:   '#d97706',
  Attacking: '#dc2626',
  Passing:   '#2563eb',
  Defending: '#16a34a',
};

// ── Player data types ────────────────────────────────────────────────────────
export interface PlayerStats {
  player_id: number;
  player_name: string;
  source_team_name?: string;
  primary_role?: string;
  age?: number;
  preferred_foot?: string;
  market_value_before_euros?: string;
  market_value_after_euros?: string;
  minutes_played?: number;
  goals?: number;
  xg_total?: number;
  assists?: number;
  key_passes?: number;
  pass_completion_pct?: number;
  total_touches?: number;
  dribbles_successful?: number;
  ball_recoveries?: number;
  interceptions?: number;
  aerials_won?: number;
}

/** Formats a market value string to be clean, e.g. €12.00M instead of €12,00M */
export function formatMarketValue(val?: string | null): string {
  if (!val) return '—';
  let cleaned = val.trim().replace(',', '.');
  if (!cleaned.startsWith('€')) {
    cleaned = cleaned.replace(/^[^\d]+/, '');
    cleaned = '€' + cleaned;
  }
  return cleaned;
}

/** Parses a market value string like €12.00M or €400.00K to a numeric value */
export function parseMarketValueToNum(val?: string | null): number {
  if (!val) return 0;
  const cleaned = val.replace(/[^0-9,.]/g, '').replace(',', '.');
  const num = parseFloat(cleaned);
  if (isNaN(num)) return 0;
  if (val.toLowerCase().includes('m')) {
    return num * 1000000;
  } else if (val.toLowerCase().includes('k')) {
    return num * 1000;
  }
  return num;
}

/** Returns ▲ or ▼ depending on whether the post-euro value is higher or lower than pre-euro */
export function getMarketTrendArrow(before?: string | null, after?: string | null): string {
  if (!before || !after) return '';
  const numBefore = parseMarketValueToNum(before);
  const numAfter = parseMarketValueToNum(after);
  if (numAfter > numBefore) return '▲';
  if (numAfter < numBefore) return '▼';
  return '';
}