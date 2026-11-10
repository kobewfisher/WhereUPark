import { Tabs } from 'expo-router/js-tabs';
import type { ColorValue } from 'react-native';
import Svg, { Circle, Path, Rect } from 'react-native-svg';
import { useColors } from '../../theme';

type IconProps = { color: ColorValue; size: number };

const NowIcon = ({ color, size }: IconProps) => (
  <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={2}>
    <Rect x={3} y={3} width={18} height={18} rx={4} />
    <Path d="M9 17V7h4a3 3 0 0 1 0 6H9" strokeLinecap="round" strokeLinejoin="round" />
  </Svg>
);
const PlanIcon = ({ color, size }: IconProps) => (
  <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={2}>
    <Circle cx={12} cy={12} r={9} />
    <Path d="M12 7v5l3 2" strokeLinecap="round" />
  </Svg>
);
const SettingsIcon = ({ color, size }: IconProps) => (
  <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={2}>
    <Path d="M4 7h10M18 7h2M4 17h2M10 17h10" strokeLinecap="round" />
    <Circle cx={16} cy={7} r={2} />
    <Circle cx={8} cy={17} r={2} />
  </Svg>
);

export default function TabsLayout() {
  const c = useColors();
  return (
    <Tabs
      screenOptions={{
        tabBarActiveTintColor: c.accent,
        tabBarInactiveTintColor: c.muted,
        tabBarStyle: { backgroundColor: c.card, borderTopColor: c.border },
        headerStyle: { backgroundColor: c.card },
        headerTintColor: c.text,
      }}
    >
      <Tabs.Screen name="index" options={{ title: 'Park now', tabBarIcon: NowIcon }} />
      <Tabs.Screen name="plan" options={{ title: 'Plan ahead', tabBarIcon: PlanIcon }} />
      <Tabs.Screen name="settings" options={{ title: 'My permit', tabBarIcon: SettingsIcon }} />
    </Tabs>
  );
}
