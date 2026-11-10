import { router } from 'expo-router';
import { useMemo, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { api } from '../../api';
import { Card, Chip, Loading, makeScreenStyles } from '../../components';
import { PERMIT_LABELS, useSettings } from '../../settings';
import { CAMPUS_TZ, fullnessColor, useColors } from '../../theme';
import { useFetch } from '../../useFetch';

function campusNow() {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat('en-CA', {
      timeZone: CAMPUS_TZ, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', hourCycle: 'h23',
    }).formatToParts(new Date()).map((p) => [p.type, p.value]),
  );
  return { y: +parts.year, m: +parts.month, d: +parts.day, h: +parts.hour };
}

const pad = (n: number) => String(n).padStart(2, '0');
const HOURS = Array.from({ length: 17 }, (_, i) => i + 6); // 6 AM .. 10 PM
const hourLabel = (h: number) => `${h % 12 || 12} ${h < 12 ? 'AM' : 'PM'}`;

export default function PlanScreen() {
  const c = useColors();
  const s = useMemo(() => makeScreenStyles(c), [c]);
  const { permit, ada } = useSettings();
  const now = useMemo(campusNow, []);
  const days = useMemo(
    () => Array.from({ length: 7 }, (_, i) => {
      const dt = new Date(Date.UTC(now.y, now.m - 1, now.d + i, 12));
      return {
        key: `${dt.getUTCFullYear()}-${pad(dt.getUTCMonth() + 1)}-${pad(dt.getUTCDate())}`,
        label: i === 0 ? 'Today' : i === 1 ? 'Tomorrow' : dt.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', timeZone: 'UTC' }),
      };
    }),
    [now],
  );
  const [day, setDay] = useState(days[0].key);
  const [hour, setHour] = useState(Math.min(Math.max(now.h + 1, 6), 22));
  const at = `${day}T${pad(hour)}:00:00`; // campus local time; the API interprets it as America/Chicago
  const { data, error, retry } = useFetch(() => api.recommendations(permit, ada, at), [permit, ada, at]);

  return (
    <ScrollView style={s.screen} contentContainerStyle={s.content}>
      <Text style={s.caption}>When are you arriving? Showing spaces for {PERMIT_LABELS[permit].toLowerCase()}.</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={st.chips}>
        {days.map((d) => <Chip key={d.key} label={d.label} selected={d.key === day} onPress={() => setDay(d.key)} />)}
      </ScrollView>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={st.chips}>
        {HOURS.map((h) => <Chip key={h} label={hourLabel(h)} selected={h === hour} onPress={() => setHour(h)} />)}
      </ScrollView>

      {!data ? (
        <View style={{ height: 200 }}><Loading error={error} onRetry={retry} /></View>
      ) : (
        <Card title={`Expected at ${hourLabel(hour)}${data.free_hours && permit === 'visitor' ? ' · yellow spaces open to visitors' : ''}`}>
          {data.sites.map((r, i) => {
            const pct = r.summary.eligible_percent_full ?? r.summary.percent_full;
            return (
              <Pressable key={r.site_id} onPress={() => router.push({ pathname: '/site/[id]', params: { id: r.site_id } })}
                style={[st.rankRow, i > 0 && { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: c.border }]}>
                <Text style={[st.rank, { color: c.muted }]}>{i + 1}</Text>
                <View style={{ flex: 1 }}>
                  <Text style={{ color: c.text, fontSize: 16, fontWeight: '600' }}>{r.name}</Text>
                  <Text style={{ color: c.muted, fontSize: 12 }}>{Math.round(r.summary.percent_full)}% full overall</Text>
                </View>
                <View style={{ alignItems: 'flex-end' }}>
                  <Text style={{ color: fullnessColor(c, pct), fontSize: 20, fontWeight: '800' }}>{r.summary.eligible_open}</Text>
                  <Text style={{ color: c.muted, fontSize: 11 }}>open for you</Text>
                </View>
              </Pressable>
            );
          })}
        </Card>
      )}
    </ScrollView>
  );
}

const st = StyleSheet.create({
  chips: { gap: 8, paddingVertical: 2 },
  rankRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 12, gap: 12 },
  rank: { width: 18, fontSize: 15, fontWeight: '700', textAlign: 'center' },
});
