import AsyncStorage from '@react-native-async-storage/async-storage';
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import type { Permit } from './api';

interface Settings {
  permit: Permit;
  ada: boolean;
  setPermit: (p: Permit) => void;
  setAda: (v: boolean) => void;
}

const KEY = 'whereupark.settings.v1';
const SettingsContext = createContext<Settings | null>(null);

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [permit, setPermit] = useState<Permit>('yellow');
  const [ada, setAda] = useState(false);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    AsyncStorage.getItem(KEY)
      .then((raw) => {
        if (!raw) return;
        const saved = JSON.parse(raw) as Partial<{ permit: Permit; ada: boolean }>;
        if (saved.permit) setPermit(saved.permit);
        if (typeof saved.ada === 'boolean') setAda(saved.ada);
      })
      .catch(() => {})
      .finally(() => setLoaded(true));
  }, []);

  useEffect(() => {
    if (loaded) AsyncStorage.setItem(KEY, JSON.stringify({ permit, ada })).catch(() => {});
  }, [permit, ada, loaded]);

  const value = useMemo(() => ({ permit, ada, setPermit, setAda }), [permit, ada]);
  if (!loaded) return null;
  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>;
}

export function useSettings(): Settings {
  const ctx = useContext(SettingsContext);
  if (!ctx) throw new Error('useSettings must be used inside SettingsProvider');
  return ctx;
}

export const PERMIT_LABELS: Record<Permit, string> = {
  red: 'Red permit',
  yellow: 'Yellow permit',
  visitor: 'Visitor / no permit',
};
