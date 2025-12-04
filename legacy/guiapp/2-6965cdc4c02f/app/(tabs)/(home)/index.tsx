
import React from "react";
import { Stack } from "expo-router";
import { ScrollView, Pressable, StyleSheet, View, Text, Platform } from "react-native";
import { IconSymbol } from "@/components/IconSymbol";
import { useTheme } from "@react-navigation/native";
import { useRouter } from "expo-router";
import { colors, commonStyles } from "@/styles/commonStyles";

export default function HomeScreen() {
  const theme = useTheme();
  const router = useRouter();

  // Mock statistics data
  const statistics = {
    totalCards: 15234,
    totalValue: 487650,
    cardsSold: 3421,
    soldValue: 125890,
  };

  // Navigation modules
  const modules = [
    {
      title: "Card Scan",
      description: "Scan and analyze trading cards",
      route: "/(tabs)/card-scan",
      icon: "camera.fill",
      color: colors.primary,
    },
    {
      title: "Warehouse",
      description: "View and manage inventory",
      route: "/(tabs)/warehouse",
      icon: "shippingbox.fill",
      color: colors.accent,
    },
    {
      title: "Statistics",
      description: "View detailed analytics",
      route: "/(tabs)/statistics",
      icon: "chart.bar.fill",
      color: colors.highlight,
    },
    {
      title: "Valuation",
      description: "Card pricing and valuation",
      route: "/(tabs)/valuation",
      icon: "dollarsign.circle.fill",
      color: colors.primary,
    },
    {
      title: "Bidding",
      description: "Manage bids and auctions",
      route: "/(tabs)/bidding",
      icon: "hammer.fill",
      color: colors.secondary,
    },
    {
      title: "Orders",
      description: "Order management and tracking",
      route: "/(tabs)/orders",
      icon: "list.bullet.clipboard.fill",
      color: colors.accent,
    },
  ];

  const formatCurrency = (value: number) => {
    return `$${value.toLocaleString()}`;
  };

  const formatNumber = (value: number) => {
    return value.toLocaleString();
  };

  return (
    <>
      {Platform.OS === 'ios' && (
        <Stack.Screen
          options={{
            title: "TCG Store CRM",
            headerLargeTitle: true,
          }}
        />
      )}
      <ScrollView 
        style={[styles.container, { backgroundColor: colors.background }]}
        contentContainerStyle={[
          styles.scrollContent,
          Platform.OS !== 'ios' && styles.scrollContentWithTabBar
        ]}
        showsVerticalScrollIndicator={false}
      >
        {/* Header */}
        <View style={styles.header}>
          <Text style={[styles.headerTitle, { color: colors.text }]}>
            TCG Store CRM
          </Text>
          <Text style={[styles.headerSubtitle, { color: colors.textSecondary }]}>
            Dashboard Overview
          </Text>
        </View>

        {/* Statistics Cards */}
        <View style={styles.statsContainer}>
          <View style={[styles.statCard, { backgroundColor: colors.card }]}>
            <View style={[styles.statIconContainer, { backgroundColor: colors.primary + '20' }]}>
              <IconSymbol name="square.stack.3d.up.fill" size={24} color={colors.primary} />
            </View>
            <Text style={[styles.statValue, { color: colors.text }]}>
              {formatNumber(statistics.totalCards)}
            </Text>
            <Text style={[styles.statLabel, { color: colors.textSecondary }]}>
              Cards in Store
            </Text>
          </View>

          <View style={[styles.statCard, { backgroundColor: colors.card }]}>
            <View style={[styles.statIconContainer, { backgroundColor: colors.accent + '20' }]}>
              <IconSymbol name="dollarsign.circle.fill" size={24} color={colors.accent} />
            </View>
            <Text style={[styles.statValue, { color: colors.text }]}>
              {formatCurrency(statistics.totalValue)}
            </Text>
            <Text style={[styles.statLabel, { color: colors.textSecondary }]}>
              Total Value
            </Text>
          </View>

          <View style={[styles.statCard, { backgroundColor: colors.card }]}>
            <View style={[styles.statIconContainer, { backgroundColor: colors.highlight + '20' }]}>
              <IconSymbol name="cart.fill" size={24} color={colors.highlight} />
            </View>
            <Text style={[styles.statValue, { color: colors.text }]}>
              {formatNumber(statistics.cardsSold)}
            </Text>
            <Text style={[styles.statLabel, { color: colors.textSecondary }]}>
              Cards Sold
            </Text>
          </View>

          <View style={[styles.statCard, { backgroundColor: colors.card }]}>
            <View style={[styles.statIconContainer, { backgroundColor: colors.accent + '20' }]}>
              <IconSymbol name="banknote.fill" size={24} color={colors.accent} />
            </View>
            <Text style={[styles.statValue, { color: colors.text }]}>
              {formatCurrency(statistics.soldValue)}
            </Text>
            <Text style={[styles.statLabel, { color: colors.textSecondary }]}>
              Sales Value
            </Text>
          </View>
        </View>

        {/* Modules Section */}
        <View style={styles.modulesSection}>
          <Text style={[styles.sectionTitle, { color: colors.text }]}>
            Modules
          </Text>
          <View style={styles.modulesGrid}>
            {modules.map((module, index) => (
              <Pressable
                key={index}
                style={[styles.moduleCard, { backgroundColor: colors.card }]}
                onPress={() => router.push(module.route as any)}
              >
                <View style={[styles.moduleIcon, { backgroundColor: module.color + '20' }]}>
                  <IconSymbol name={module.icon as any} size={28} color={module.color} />
                </View>
                <Text style={[styles.moduleTitle, { color: colors.text }]}>
                  {module.title}
                </Text>
                <Text style={[styles.moduleDescription, { color: colors.textSecondary }]}>
                  {module.description}
                </Text>
              </Pressable>
            ))}
          </View>
        </View>
      </ScrollView>
    </>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  scrollContent: {
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 16,
  },
  scrollContentWithTabBar: {
    paddingBottom: 100,
  },
  header: {
    marginBottom: 24,
  },
  headerTitle: {
    fontSize: 28,
    fontWeight: '700',
    marginBottom: 4,
  },
  headerSubtitle: {
    fontSize: 16,
  },
  statsContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginHorizontal: -6,
    marginBottom: 24,
  },
  statCard: {
    width: '48%',
    margin: '1%',
    padding: 16,
    borderRadius: 12,
    boxShadow: '0px 2px 6px rgba(0, 0, 0, 0.08)',
    elevation: 2,
    alignItems: 'center',
  },
  statIconContainer: {
    width: 48,
    height: 48,
    borderRadius: 24,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 12,
  },
  statValue: {
    fontSize: 22,
    fontWeight: '700',
    marginBottom: 4,
  },
  statLabel: {
    fontSize: 13,
    textAlign: 'center',
  },
  modulesSection: {
    marginBottom: 16,
  },
  sectionTitle: {
    fontSize: 20,
    fontWeight: '700',
    marginBottom: 16,
  },
  modulesGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginHorizontal: -6,
  },
  moduleCard: {
    width: '48%',
    margin: '1%',
    padding: 16,
    borderRadius: 12,
    boxShadow: '0px 2px 6px rgba(0, 0, 0, 0.08)',
    elevation: 2,
    alignItems: 'center',
  },
  moduleIcon: {
    width: 56,
    height: 56,
    borderRadius: 28,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 12,
  },
  moduleTitle: {
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 4,
    textAlign: 'center',
  },
  moduleDescription: {
    fontSize: 12,
    textAlign: 'center',
    lineHeight: 16,
  },
});
