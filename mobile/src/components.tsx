import { useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View, type LayoutChangeEvent } from 'react-native';
import Svg, { Line, Path, Rect, Text as SvgText } from 'react-native-svg';
import type { ForecastPoint, SiteStatus, Source, SpotType, TypeCount } from './api';
import {
  fullnessColor, formatTime, SPOT_COLORS, SPOT_LABELS, SPOT_ORDER, useColors, type Colors,
} from './theme';

type ByType = Partial<Record<SpotType, TypeCount>>;

const SOURCE_LABEL: Record<Source, string> = {
  live: 'Live',
  simulated: 'Simulated',
  mixed: 'Partly live',
  forecast: 'Forecast',
  baseline: 'Baseline',
};

export function SourceBadge({ source }: { source: Source }) {
  const c = useColors();
  const live = source === 'live';
  return (
    <View style={[styles.badge, { borderColor: live ? c.good : c.border }]}>
      <View style={[styles.badgeDot, { backgroundColor: live ? c.good : c.muted }]} />
      <Text style={[styles.badgeText, { color: live ? c.good : c.muted }]}>{SOURCE_LABEL[source]}</Text>
    </View>
  );
}

/** Stacked bar: each spot type's share of capacity, solid for occupied, faint for open. */
export function OccupancyBar({ byType, height = 10 }: { byType: ByType; height?: number }) {
  const c = useColors();
  const total = SPOT_ORDER.reduce((n, t) => n + (byType[t]?.capacity ?? 0), 0) || 1;
  return (
    <View style={[styles.bar, { height, backgroundColor: c.track }]}>
      {SPOT_ORDER.filter((t) => byType[t]).map((t) => {
        const v = byType[t]!;
        return (
          <View key={t} style={{ flex: v.capacity / total, flexDirection: 'row' }}>
            <View style={{ flex: v.occupied || 0.0001, backgroundColor: SPOT_COLORS[t] }} />
            <View style={{ flex: v.open || 0.0001, backgroundColor: SPOT_COLORS[t], opacity: 0.22 }} />
          </View>
        );
      })}
    </View>
  );
}

export function TypeBreakdown({ byType, eligible }: { byType: ByType; eligible: SpotType[] }) {
  const c = useColors();
  return (
    <View style={{ gap: 12 }}>
      {SPOT_ORDER.filter((t) => byType[t]).map((t) => {
        const v = byType[t]!;
        const mine = eligible.includes(t);
        return (
          <View key={t} style={{ opacity: mine ? 1 : 0.55 }}>
            <View style={styles.rowBetween}>
              <View style={styles.row}>
                <View style={[styles.swatch, { backgroundColor: SPOT_COLORS[t] }]} />
                <Text style={[styles.typeLabel, { color: c.text }]}>{SPOT_LABELS[t]}</Text>
                {mine && <Text style={[styles.tag, { color: c.accent, borderColor: c.accent }]}>You</Text>}
              </View>
              <Text style={[styles.typeCount, { color: c.text }]}>
                <Text style={{ fontWeight: '700' }}>{v.open}</Text>
                <Text style={{ color: c.muted }}> open / {v.capacity}</Text>
              </Text>
            </View>
            <View style={[styles.bar, { height: 6, marginTop: 6, backgroundColor: c.track }]}>
              <View style={{ flex: v.occupied || 0.0001, backgroundColor: SPOT_COLORS[t] }} />
              <View style={{ flex: v.open || 0.0001 }} />
            </View>
          </View>
        );
      })}
    </View>
  );
}

/** Line chart of % full over the forecast horizon (eligible spaces if available, else total). */
export function ForecastChart({ points }: { points: ForecastPoint[] }) {
  const c = useColors();
  const [width, setWidth] = useState(0);
  const height = 170;
  const pad = { l: 34, r: 8, t: 10, b: 24 };
  const onLayout = (e: LayoutChangeEvent) => setWidth(e.nativeEvent.layout.width);
  const vals = points.map((p) => p.summary.eligible_percent_full ?? p.summary.percent_full);
  const totals = points.map((p) => p.summary.percent_full);

  const w = Math.max(width - pad.l - pad.r, 1);
  const h = height - pad.t - pad.b;
  const x = (i: number) => pad.l + (points.length > 1 ? (i / (points.length - 1)) * w : 0);
  const y = (v: number) => pad.t + (1 - v / 100) * h;
  const path = (arr: number[]) => arr.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ');
  const labelEvery = Math.max(1, Math.round(points.length / 4));

  return (
    <View onLayout={onLayout}>
      {width > 0 && (
        <Svg width={width} height={height}>
          {[0, 50, 100].map((g) => (
            <Line key={g} x1={pad.l} x2={pad.l + w} y1={y(g)} y2={y(g)} stroke={c.border} strokeWidth={1} />
          ))}
          {[0, 50, 100].map((g) => (
            <SvgText key={`l${g}`} x={pad.l - 6} y={y(g) + 4} fontSize={10} fill={c.muted} textAnchor="end">
              {`${g}%`}
            </SvgText>
          ))}
          <Rect x={pad.l} y={y(100)} width={w} height={y(95) - y(100)} fill={c.bad} opacity={0.08} />
          <Path d={path(totals)} stroke={c.muted} strokeWidth={1.5} strokeDasharray="4 4" fill="none" />
          <Path d={path(vals)} stroke={c.accent} strokeWidth={2.5} fill="none" />
          {points.map((p, i) =>
            i % labelEvery === 0 ? (
              <SvgText key={p.ts} x={x(i)} y={height - 6} fontSize={10} fill={c.muted} textAnchor="middle">
                {formatTime(p.ts).replace(':00', '')}
              </SvgText>
            ) : null,
          )}
        </Svg>
      )}
      <View style={[styles.row, { gap: 16, marginTop: 4 }]}>
        <Legend color={c.accent} label="Spaces you can use" />
        <Legend color={c.muted} label="Whole site" dashed />
      </View>
    </View>
  );
}

function Legend({ color, label, dashed }: { color: string; label: string; dashed?: boolean }) {
  const c = useColors();
  return (
    <View style={styles.row}>
      <View style={{ width: 16, height: 0, borderTopWidth: 2, borderColor: color, borderStyle: dashed ? 'dashed' : 'solid', marginRight: 6 }} />
      <Text style={{ fontSize: 12, color: c.muted }}>{label}</Text>
    </View>
  );
}

export function SiteCard({ site, onPress }: { site: SiteStatus; onPress: () => void }) {
  const c = useColors();
  const s = site.summary;
  const pct = s.eligible_percent_full ?? s.percent_full;
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={`${site.name}, ${s.eligible_open} spaces open for you, ${s.percent_full}% full overall`}
      style={({ pressed }) => [styles.card, { backgroundColor: c.card, borderColor: c.border, opacity: pressed ? 0.85 : 1 }]}
    >
      <View style={styles.rowBetween}>
        <View style={{ flex: 1 }}>
          <Text style={[styles.cardTitle, { color: c.text }]}>{site.name}</Text>
          <Text style={{ color: c.muted, fontSize: 13, marginTop: 2 }}>
            {site.kind === 'lot' ? 'Surface lot' : `${site.levels}-level garage`} · {site.capacity} spaces
          </Text>
        </View>
        <SourceBadge source={site.source} />
      </View>
      <View style={[styles.rowBetween, { marginTop: 14, alignItems: 'flex-end' }]}>
        <View>
          <Text style={[styles.bigNumber, { color: fullnessColor(c, pct) }]}>{s.eligible_open}</Text>
          <Text style={{ color: c.muted, fontSize: 12 }}>open for you</Text>
        </View>
        <View style={{ alignItems: 'flex-end' }}>
          <Text style={[styles.pct, { color: c.text }]}>{Math.round(s.percent_full)}%</Text>
          <Text style={{ color: c.muted, fontSize: 12 }}>full overall</Text>
        </View>
      </View>
      <View style={{ marginTop: 12 }}>
        <OccupancyBar byType={site.by_type} />
      </View>
    </Pressable>
  );
}

export function Card({ children, title }: { children: React.ReactNode; title?: string }) {
  const c = useColors();
  return (
    <View style={[styles.card, { backgroundColor: c.card, borderColor: c.border }]}>
      {title && <Text style={[styles.sectionTitle, { color: c.muted }]}>{title}</Text>}
      {children}
    </View>
  );
}

export function PlaceholderBanner() {
  const c = useColors();
  return (
    <View style={[styles.banner, { backgroundColor: c.bannerBg }]}>
      <Text style={{ color: c.bannerText, fontSize: 13, lineHeight: 18 }}>
        Preview data. Counts and occupancy are placeholder estimates until cameras and site audits
        are complete.
      </Text>
    </View>
  );
}

export function Loading({ error, onRetry }: { error?: string | null; onRetry?: () => void }) {
  const c = useColors();
  return (
    <View style={styles.center}>
      {error ? (
        <>
          <Text style={{ color: c.text, fontSize: 16, fontWeight: '600' }}>Can't reach WhereUPark</Text>
          <Text style={{ color: c.muted, marginTop: 6, textAlign: 'center' }}>{error}</Text>
          {onRetry && (
            <Pressable onPress={onRetry} style={[styles.button, { backgroundColor: c.accent }]}>
              <Text style={{ color: '#fff', fontWeight: '600' }}>Try again</Text>
            </Pressable>
          )}
        </>
      ) : (
        <ActivityIndicator color={c.accent} />
      )}
    </View>
  );
}

export function Chip({ label, selected, onPress }: { label: string; selected: boolean; onPress: () => void }) {
  const c = useColors();
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityState={{ selected }}
      style={[styles.chip, { borderColor: selected ? c.accent : c.border, backgroundColor: selected ? c.accent : c.card }]}
    >
      <Text style={{ color: selected ? '#fff' : c.text, fontWeight: '600', fontSize: 13 }}>{label}</Text>
    </Pressable>
  );
}

export const makeScreenStyles = (c: Colors) =>
  StyleSheet.create({
    screen: { flex: 1, backgroundColor: c.bg },
    content: { padding: 16, gap: 12, paddingBottom: 32 },
    caption: { color: c.muted, fontSize: 13 },
  });

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center' },
  rowBetween: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  bar: { flexDirection: 'row', borderRadius: 999, overflow: 'hidden' },
  card: { borderRadius: 16, borderWidth: StyleSheet.hairlineWidth, padding: 16 },
  cardTitle: { fontSize: 17, fontWeight: '700' },
  bigNumber: { fontSize: 34, fontWeight: '800', fontVariant: ['tabular-nums'] },
  pct: { fontSize: 20, fontWeight: '700', fontVariant: ['tabular-nums'] },
  sectionTitle: { fontSize: 12, fontWeight: '700', letterSpacing: 0.6, textTransform: 'uppercase', marginBottom: 12 },
  swatch: { width: 10, height: 10, borderRadius: 3, marginRight: 8 },
  typeLabel: { fontSize: 15, fontWeight: '600' },
  typeCount: { fontSize: 14, fontVariant: ['tabular-nums'] },
  tag: { fontSize: 11, fontWeight: '700', borderWidth: 1, borderRadius: 6, paddingHorizontal: 5, marginLeft: 8, overflow: 'hidden' },
  badge: { flexDirection: 'row', alignItems: 'center', borderWidth: 1, borderRadius: 999, paddingHorizontal: 8, paddingVertical: 3 },
  badgeDot: { width: 6, height: 6, borderRadius: 3, marginRight: 5 },
  badgeText: { fontSize: 11, fontWeight: '600' },
  banner: { borderRadius: 12, padding: 12 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24 },
  button: { marginTop: 16, paddingHorizontal: 20, paddingVertical: 10, borderRadius: 10 },
  chip: { borderWidth: 1, borderRadius: 999, paddingHorizontal: 14, paddingVertical: 8 },
});
