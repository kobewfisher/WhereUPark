import { useMemo } from 'react';
import { Pressable, ScrollView, StyleSheet, Switch, Text, View } from 'react-native';
import { API_URL, type Permit } from '../../api';
import { Card, makeScreenStyles } from '../../components';
import { PERMIT_LABELS, useSettings } from '../../settings';
import { useColors } from '../../theme';

const PERMITS: Permit[] = ['red', 'yellow', 'visitor'];
const PERMIT_HINT: Record<Permit, string> = {
  red: 'Red permit spaces',
  yellow: 'Yellow permit spaces',
  visitor: 'Visitor spaces any time. Yellow spaces too 5 PM–7 AM on weekdays and all weekend',
};

export default function SettingsScreen() {
  const c = useColors();
  const s = useMemo(() => makeScreenStyles(c), [c]);
  const { permit, setPermit, ada, setAda } = useSettings();

  return (
    <ScrollView style={s.screen} contentContainerStyle={s.content}>
      <Card title="Your parking permit">
        {PERMITS.map((p, i) => {
          const selected = p === permit;
          return (
            <Pressable key={p} onPress={() => setPermit(p)} accessibilityRole="radio" accessibilityState={{ selected }}
              style={[st.option, i > 0 && { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: c.border }]}>
              <View style={[st.radio, { borderColor: selected ? c.accent : c.border }]}>
                {selected && <View style={[st.radioDot, { backgroundColor: c.accent }]} />}
              </View>
              <View style={{ flex: 1 }}>
                <Text style={{ color: c.text, fontSize: 16, fontWeight: '600' }}>{PERMIT_LABELS[p]}</Text>
                <Text style={{ color: c.muted, fontSize: 13, marginTop: 2 }}>{PERMIT_HINT[p]}</Text>
              </View>
            </Pressable>
          );
        })}
      </Card>
      <Card>
        <View style={st.switchRow}>
          <View style={{ flex: 1 }}>
            <Text style={{ color: c.text, fontSize: 16, fontWeight: '600' }}>ADA placard</Text>
            <Text style={{ color: c.muted, fontSize: 13, marginTop: 2 }}>Include accessible spaces</Text>
          </View>
          <Switch value={ada} onValueChange={setAda} trackColor={{ true: c.accent, false: c.track }} />
        </View>
      </Card>
      <Text style={[s.caption, { paddingHorizontal: 4, lineHeight: 18 }]}>
        Server: {API_URL}
      </Text>
    </ScrollView>
  );
}

const st = StyleSheet.create({
  option: { flexDirection: 'row', alignItems: 'center', paddingVertical: 12, gap: 12 },
  radio: { width: 22, height: 22, borderRadius: 11, borderWidth: 2, alignItems: 'center', justifyContent: 'center' },
  radioDot: { width: 10, height: 10, borderRadius: 5 },
  switchRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
});
