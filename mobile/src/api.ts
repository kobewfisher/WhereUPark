import Constants from 'expo-constants';

/**
 * Backend base URL. Override per environment with EXPO_PUBLIC_API_URL.
 *  - iOS simulator / web:  http://localhost:8000
 *  - Android emulator:     http://10.0.2.2:8000
 *  - Physical device:      http://<your computer's LAN IP>:8000
 */
export const API_URL: string =
  process.env.EXPO_PUBLIC_API_URL ??
  (Constants.expoConfig?.extra as { apiUrl?: string } | undefined)?.apiUrl ??
  'http://localhost:8000';

export type SpotType = 'red' | 'yellow' | 'visitor' | 'ada' | 'other';
export type Permit = 'red' | 'yellow' | 'visitor';
export type Source = 'live' | 'simulated' | 'mixed' | 'forecast' | 'baseline';

export interface TypeCount {
  capacity: number;
  occupied: number;
  open: number;
  source?: 'live' | 'simulated';
}

export interface Summary {
  capacity: number;
  occupied: number;
  open: number;
  percent_full: number;
  eligible_types?: SpotType[];
  eligible_open?: number;
  eligible_percent_full?: number | null;
}

export interface SiteStatus {
  id: string;
  name: string;
  kind: 'garage' | 'lot';
  levels: number;
  capacity: number;
  counts: Partial<Record<SpotType, number>>;
  data_source: string;
  counts_are_placeholder: boolean;
  as_of: string;
  source: Source;
  by_type: Partial<Record<SpotType, TypeCount>>;
  summary: Summary;
}

export interface ForecastPoint {
  ts: string;
  by_type: Partial<Record<SpotType, TypeCount>>;
  summary: Summary;
}

export interface Forecast {
  site_id: string;
  basis: string;
  step_minutes: number;
  points: ForecastPoint[];
}

export interface Recommendations {
  at: string;
  permit: Permit;
  ada_placard: boolean;
  free_hours: boolean;
  sites: { site_id: string; name: string; source: Source; summary: Summary }[];
}

async function get<T>(path: string, params: Record<string, string | number | boolean | undefined>) {
  const qs = Object.entries(params)
    .filter(([, v]) => v !== undefined)
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
    .join('&');
  const res = await fetch(`${API_URL}${path}${qs ? `?${qs}` : ''}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return (await res.json()) as T;
}

export const api = {
  sites: (permit: Permit, ada: boolean) =>
    get<{ as_of: string; sites: SiteStatus[] }>('/sites', { permit, ada }),
  site: (id: string, permit: Permit, ada: boolean) =>
    get<SiteStatus>(`/sites/${id}`, { permit, ada }),
  forecast: (id: string, permit: Permit, ada: boolean, hours = 12, step = 30) =>
    get<Forecast>(`/sites/${id}/forecast`, { permit, ada, hours, step }),
  recommendations: (permit: Permit, ada: boolean, at: string) =>
    get<Recommendations>('/recommendations', { permit, ada, at }),
};
