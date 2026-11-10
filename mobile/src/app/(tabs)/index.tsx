import { router } from 'expo-router';
import { useMemo } from 'react';
import { RefreshControl, ScrollView, Text } from 'react-native';
import { api } from '../../api';
import { Loading, PlaceholderBanner, SiteCard, makeScreenStyles } from '../../components';
import { PERMIT_LABELS, useSettings } from '../../settings';
import { formatTime, useColors } from '../../theme';
import { useFetch } from '../../useFetch';

export default function NowScreen() {
  const c = useColors();
  const s = useMemo(() => makeScreenStyles(c), [c]);
  const { permit, ada } = useSettings();
  const { data, error, refreshing, refresh, retry } = useFetch(() => api.sites(permit, ada), [permit, ada], 60_000);

  if (!data) return <Loading error={error} onRetry={retry} />;
  const sites = [...data.sites].sort((a, b) => (b.summary.eligible_open ?? 0) - (a.summary.eligible_open ?? 0));
  const anyPlaceholder = sites.some((x) => x.counts_are_placeholder || x.source !== 'live');

  return (
    <ScrollView style={s.screen} contentContainerStyle={s.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor={c.accent} />}>
      <Text style={s.caption}>
        {PERMIT_LABELS[permit]}{ada ? ' + ADA placard' : ''} · updated {formatTime(data.as_of)} · best options first
      </Text>
      {anyPlaceholder && <PlaceholderBanner />}
      {sites.map((site) => (
        <SiteCard key={site.id} site={site} onPress={() => router.push({ pathname: '/site/[id]', params: { id: site.id } })} />
      ))}
    </ScrollView>
  );
}
