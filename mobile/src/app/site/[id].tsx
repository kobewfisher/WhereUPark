import { Stack, useLocalSearchParams } from 'expo-router';
import { useMemo } from 'react';
import { RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { api } from '../../api';
import {
  Card, ForecastChart, Loading, OccupancyBar, PlaceholderBanner, SourceBadge, TypeBreakdown, makeScreenStyles,
} from '../../components';
import { useSettings } from '../../settings';
import { formatTime, fullnessColor, useColors } from '../../theme';
import { useFetch } from '../../useFetch';

export default function SiteScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const c = useColors();
  const s = useMemo(() => makeScreenStyles(c), [c]);
  const { permit, ada } = useSettings();
  const { data, error, refreshing, refresh, retry } = useFetch(
    async () => {
      const [site, forecast] = await Promise.all([api.site(id, permit, ada), api.forecast(id, permit, ada, 12, 30)]);
      return { site, forecast };
    },
    [id, permit, ada],
    60_000,
  );

  if (!data) return <Loading error={error} onRetry={retry} />;
  const { site, forecast } = data;
  const sum = site.summary;
  const pct = sum.eligible_percent_full ?? sum.percent_full;
  const best = forecast.points.reduce((a, b) => ((b.summary.eligible_open ?? 0) > (a.summary.eligible_open ?? 0) ? b : a));
  const firstRoomy = forecast.points.find((p) => (p.summary.eligible_open ?? 0) >= 10);

  return (
    <ScrollView style={s.screen} contentContainerStyle={s.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor={c.accent} />}>
      <Stack.Screen options={{ title: site.name }} />
      {(site.counts_are_placeholder || site.source !== 'live') && <PlaceholderBanner />}

      <Card>
        <View style={st.rowBetween}>
          <Text style={{ color: c.muted, fontSize: 13 }}>Right now · {formatTime(site.as_of)}</Text>
          <SourceBadge source={site.source} />
        </View>
        <View style={[st.rowBetween, { marginTop: 12, alignItems: 'flex-end' }]}>
          <View>
            <Text style={[st.huge, { color: fullnessColor(c, pct) }]}>{sum.eligible_open}</Text>
            <Text style={{ color: c.muted }}>spaces open for you</Text>
          </View>
          <View style={{ alignItems: 'flex-end' }}>
            <Text style={[st.pct, { color: c.text }]}>{sum.percent_full}%</Text>
            <Text style={{ color: c.muted }}>{sum.open} of {sum.capacity} open overall</Text>
          </View>
        </View>
        <View style={{ marginTop: 14 }}>
          <OccupancyBar byType={site.by_type} height={12} />
        </View>
      </Card>

      <Card title="By spot type">
        <TypeBreakdown byType={site.by_type} eligible={sum.eligible_types ?? []} />
      </Card>

      <Card title="Next 12 hours">
        <ForecastChart points={forecast.points} />
        <View style={{ marginTop: 14, gap: 4 }}>
          <Text style={{ color: c.text, fontSize: 14 }}>
            Most room for you: <Text style={{ fontWeight: '700' }}>{formatTime(best.ts)}</Text> ({best.summary.eligible_open} open)
          </Text>
          {firstRoomy && firstRoomy !== forecast.points[0] && (sum.eligible_open ?? 0) < 10 && (
            <Text style={{ color: c.text, fontSize: 14 }}>
              10+ open spaces expected by <Text style={{ fontWeight: '700' }}>{formatTime(firstRoomy.ts)}</Text>
            </Text>
          )}
          <Text style={{ color: c.muted, fontSize: 12, marginTop: 4 }}>
            {forecast.basis === 'baseline' ? 'Based on placeholder baseline' : 'Forecast model'} · early forecasts improve as real data comes in
          </Text>
        </View>
      </Card>

      <Card title="About this site">
        <Text style={{ color: c.text, lineHeight: 21 }}>
          {site.kind === 'lot' ? 'Surface lot' : `${site.levels}-level garage`} · {site.capacity} spaces{'\n'}
          Data: {site.data_source === 'east_end_sensors' ? 'in-garage spot sensors' : 'Parklio cameras'}
          {site.counts_are_placeholder ? '\nSpace counts are estimates pending the site audit.' : ''}
        </Text>
      </Card>
    </ScrollView>
  );
}

const st = StyleSheet.create({
  rowBetween: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  huge: { fontSize: 44, fontWeight: '800', fontVariant: ['tabular-nums'] },
  pct: { fontSize: 24, fontWeight: '700', fontVariant: ['tabular-nums'] },
});
