
import React from 'react';
import { Platform } from 'react-native';
import { NativeTabs, Icon, Label } from 'expo-router/unstable-native-tabs';
import { Stack } from 'expo-router';
import FloatingTabBar, { TabBarItem } from '@/components/FloatingTabBar';
import { colors } from '@/styles/commonStyles';

export default function TabLayout() {
  // Define the tabs configuration
  const tabs: TabBarItem[] = [
    {
      name: '(home)',
      route: '/(tabs)/(home)/',
      icon: 'house.fill',
      label: 'Home',
    },
    {
      name: 'warehouse',
      route: '/(tabs)/warehouse',
      icon: 'shippingbox.fill',
      label: 'Warehouse',
    },
    {
      name: 'statistics',
      route: '/(tabs)/statistics',
      icon: 'chart.bar.fill',
      label: 'Stats',
    },
    {
      name: 'profile',
      route: '/(tabs)/profile',
      icon: 'person.fill',
      label: 'Profile',
    },
  ];

  // Use NativeTabs for iOS, custom FloatingTabBar for Android and Web
  if (Platform.OS === 'ios') {
    return (
      <NativeTabs>
        <NativeTabs.Trigger name="(home)">
          <Icon sf="house.fill" drawable="ic_home" />
          <Label>Home</Label>
        </NativeTabs.Trigger>
        <NativeTabs.Trigger name="card-scan">
          <Icon sf="camera.fill" drawable="ic_camera" />
          <Label>Scan</Label>
        </NativeTabs.Trigger>
        <NativeTabs.Trigger name="warehouse">
          <Icon sf="shippingbox.fill" drawable="ic_warehouse" />
          <Label>Warehouse</Label>
        </NativeTabs.Trigger>
        <NativeTabs.Trigger name="statistics">
          <Icon sf="chart.bar.fill" drawable="ic_stats" />
          <Label>Stats</Label>
        </NativeTabs.Trigger>
        <NativeTabs.Trigger name="profile">
          <Icon sf="person.fill" drawable="ic_profile" />
          <Label>Profile</Label>
        </NativeTabs.Trigger>
      </NativeTabs>
    );
  }

  // For Android and Web, use Stack navigation with custom floating tab bar
  return (
    <>
      <Stack
        screenOptions={{
          headerShown: false,
          animation: 'none',
        }}
      >
        <Stack.Screen name="(home)" />
        <Stack.Screen name="card-scan" />
        <Stack.Screen name="warehouse" />
        <Stack.Screen name="statistics" />
        <Stack.Screen name="valuation" />
        <Stack.Screen name="bidding" />
        <Stack.Screen name="orders" />
        <Stack.Screen name="profile" />
      </Stack>
      <FloatingTabBar tabs={tabs} />
    </>
  );
}
