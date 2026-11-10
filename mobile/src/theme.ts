import { useColorScheme } from 'react-native';
import type { SpotType } from './api';

export const SPOT_COLORS: Record<SpotType, string> = {
  red: '#D64545',
  yellow: '#E0A814',
  visitor: '#3B82C4',
  ada: '#7B5EA7',
  other: '#8A8F98',
};

export const SPOT_LABELS: Record<SpotType, string> = {
  red: 'Red permit',
  yellow: 'Yellow permit',
  visitor: 'Visitor',
  ada: 'ADA',
  other: 'Unclassified',
};

export const SPOT_ORDER: SpotType[] = ['red', 'yellow', 'visitor', 'ada', 'other'];

const light = {
  bg: '#F4F5F7',
  card: '#FFFFFF',
  text: '#16181D',
  muted: '#5F6672',
  border: '#E1E4E8',
  track: '#E9ECEF',
  accent: '#A51417', // WashU red
  good: '#1E8E4E',
  warn: '#C77700',
  bad: '#C62828',
  bannerBg: '#FFF4E0',
  bannerText: '#7A4B00',
};

const dark: typeof light = {
  bg: '#0F1115',
  card: '#1A1D23',
  text: '#F2F3F5',
  muted: '#9AA1AD',
  border: '#2A2F37',
  track: '#2A2F37',
  accent: '#E5484D',
  good: '#3DD68C',
  warn: '#F5A524',
  bad: '#FF6B6B',
  bannerBg: '#3A2A10',
  bannerText: '#FFD9A0',
};

export type Colors = typeof light;

export function useColors(): Colors {
  return useColorScheme() === 'dark' ? dark : light;
}

/** Colour for a "% full" value: green when there is room, amber when tight, red when full. */
export function fullnessColor(c: Colors, percentFull: number): string {
  if (percentFull >= 95) return c.bad;
  if (percentFull >= 85) return c.warn;
  return c.good;
}

export const CAMPUS_TZ = 'America/Chicago';

export function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    timeZone: CAMPUS_TZ,
  });
}
