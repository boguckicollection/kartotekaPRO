
import React from "react";
import { SafeAreaView } from "react-native-safe-area-context";
import { View, Text, StyleSheet, ScrollView, Platform, Pressable } from "react-native";
import { Stack } from "expo-router";
import { IconSymbol } from "@/components/IconSymbol";
import { colors } from "@/styles/commonStyles";

export default function ProfileScreen() {
  const profileData = {
    name: "Store Manager",
    email: "manager@tcgstore.com",
    role: "Administrator",
    storeInfo: {
      name: "TCG Trading Cards",
      location: "New York, NY",
      established: "2020",
    },
  };

  const menuItems = [
    { icon: "gear", label: "Settings", color: colors.primary },
    { icon: "bell.fill", label: "Notifications", color: colors.highlight },
    { icon: "person.2.fill", label: "Team Management", color: colors.accent },
    { icon: "chart.line.uptrend.xyaxis", label: "Reports", color: colors.primary },
    { icon: "questionmark.circle.fill", label: "Help & Support", color: colors.secondary },
  ];

  return (
    <>
      <Stack.Screen
        options={{
          title: "Profile",
          headerShown: Platform.OS === 'ios',
        }}
      />
      <ScrollView 
        style={[styles.container, { backgroundColor: colors.background }]}
        contentContainerStyle={[
          styles.scrollContent,
          Platform.OS !== 'ios' && styles.scrollContentWithTabBar
        ]}
      >
        <View style={[styles.profileCard, { backgroundColor: colors.card }]}>
          <View style={[styles.avatar, { backgroundColor: colors.primary + '20' }]}>
            <IconSymbol name="person.fill" size={48} color={colors.primary} />
          </View>
          <Text style={[styles.name, { color: colors.text }]}>
            {profileData.name}
          </Text>
          <Text style={[styles.email, { color: colors.textSecondary }]}>
            {profileData.email}
          </Text>
          <View style={[styles.roleBadge, { backgroundColor: colors.accent + '20' }]}>
            <Text style={[styles.roleText, { color: colors.accent }]}>
              {profileData.role}
            </Text>
          </View>
        </View>

        <View style={[styles.storeCard, { backgroundColor: colors.card }]}>
          <Text style={[styles.sectionTitle, { color: colors.text }]}>
            Store Information
          </Text>
          <View style={styles.infoRow}>
            <IconSymbol name="building.2.fill" size={20} color={colors.textSecondary} />
            <Text style={[styles.infoText, { color: colors.text }]}>
              {profileData.storeInfo.name}
            </Text>
          </View>
          <View style={styles.infoRow}>
            <IconSymbol name="location.fill" size={20} color={colors.textSecondary} />
            <Text style={[styles.infoText, { color: colors.text }]}>
              {profileData.storeInfo.location}
            </Text>
          </View>
          <View style={styles.infoRow}>
            <IconSymbol name="calendar" size={20} color={colors.textSecondary} />
            <Text style={[styles.infoText, { color: colors.text }]}>
              Established {profileData.storeInfo.established}
            </Text>
          </View>
        </View>

        <View style={styles.menuSection}>
          {menuItems.map((item, index) => (
            <Pressable
              key={index}
              style={[styles.menuItem, { backgroundColor: colors.card }]}
              onPress={() => console.log("Navigate to", item.label)}
            >
              <View style={[styles.menuIcon, { backgroundColor: item.color + '20' }]}>
                <IconSymbol name={item.icon as any} size={24} color={item.color} />
              </View>
              <Text style={[styles.menuLabel, { color: colors.text }]}>
                {item.label}
              </Text>
              <IconSymbol name="chevron.right" size={20} color={colors.textSecondary} />
            </Pressable>
          ))}
        </View>

        <Pressable
          style={[styles.logoutButton, { backgroundColor: colors.card, borderColor: '#dc3545' }]}
          onPress={() => console.log("Logout")}
        >
          <IconSymbol name="arrow.right.square.fill" size={20} color="#dc3545" />
          <Text style={[styles.logoutText, { color: '#dc3545' }]}>
            Logout
          </Text>
        </Pressable>
      </ScrollView>
    </>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  scrollContent: {
    padding: 16,
  },
  scrollContentWithTabBar: {
    paddingBottom: 100,
  },
  profileCard: {
    padding: 24,
    borderRadius: 12,
    alignItems: 'center',
    marginBottom: 16,
    boxShadow: '0px 2px 8px rgba(0, 0, 0, 0.1)',
    elevation: 3,
  },
  avatar: {
    width: 96,
    height: 96,
    borderRadius: 48,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 16,
  },
  name: {
    fontSize: 24,
    fontWeight: '700',
    marginBottom: 4,
  },
  email: {
    fontSize: 14,
    marginBottom: 12,
  },
  roleBadge: {
    paddingHorizontal: 16,
    paddingVertical: 6,
    borderRadius: 12,
  },
  roleText: {
    fontSize: 13,
    fontWeight: '600',
  },
  storeCard: {
    padding: 20,
    borderRadius: 12,
    marginBottom: 16,
    boxShadow: '0px 2px 8px rgba(0, 0, 0, 0.1)',
    elevation: 3,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '700',
    marginBottom: 16,
  },
  infoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
  },
  infoText: {
    fontSize: 15,
    marginLeft: 12,
  },
  menuSection: {
    marginBottom: 16,
  },
  menuItem: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    borderRadius: 12,
    marginBottom: 8,
    boxShadow: '0px 2px 6px rgba(0, 0, 0, 0.08)',
    elevation: 2,
  },
  menuIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  menuLabel: {
    flex: 1,
    fontSize: 16,
    fontWeight: '500',
  },
  logoutButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 16,
    borderRadius: 12,
    borderWidth: 2,
    boxShadow: '0px 2px 6px rgba(0, 0, 0, 0.08)',
    elevation: 2,
  },
  logoutText: {
    fontSize: 16,
    fontWeight: '600',
    marginLeft: 8,
  },
});
