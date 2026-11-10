import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { SettingsProvider } from '../settings';
import { useColors } from '../theme';

export default function RootLayout() {
  const c = useColors();
  return (
    <SettingsProvider>
      <StatusBar style="auto" />
      <Stack
        screenOptions={{
          headerStyle: { backgroundColor: c.card },
          headerTintColor: c.text,
          contentStyle: { backgroundColor: c.bg },
        }}
      >
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen name="site/[id]" options={{ title: '' }} />
      </Stack>
    </SettingsProvider>
  );
}
