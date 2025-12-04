
import React from "react";
import { ScrollView, StyleSheet, View, Text, Platform } from "react-native";
import { Stack } from "expo-router";
import { IconSymbol } from "@/components/IconSymbol";
import { colors } from "@/styles/commonStyles";

export default function StatisticsScreen() {
  // Mock statistics data
  const stats = {
    overview: {
      totalCards: 15234,
      totalValue: 487650,
      cardsSold: 3421,
      soldValue: 125890,
      avgCardValue: 32,
      topCard: "Charizard VMAX",
    },
    monthly: {
      sales: 42,
      revenue: 8450,
      newCards: 156,
      growth: 12.5,
    },
    topSets: [
      { name: "Evolving Skies", cards: 234, value: 45600 },
      { name: "Darkness Ablaze", cards: 189, value: 38900 },
      { name: "Vivid Voltage", cards: 167, value: 28700 },
    ],
  };

  return (
    <>
      <Stack.Screen
        options={{
          title: "Statistics",
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
        <View style={styles.header}>
          <Text style={[styles.title, { color: colors.text }]}>
            Statistics & Analytics
          </Text>
          <Text style={[styles.subtitle, { color: colors.textSecondary }]}>
            Detailed insights into your store performance
          </Text>
        </View>

        {/* Overview Section */}
        <View style={[styles.section, { backgroundColor: colors.card }]}>
          <Text style={[styles.sectionTitle, { color: colors.text }]}>
            Overview
          </Text>
          <View style={styles.statsGrid}>
            <View style={styles.statItem}>
              <Text style={[styles.statValue, { color: colors.primary }]}>
                {stats.overview.totalCards.toLocaleString()}
              </Text>
              <Text style={[styles.statLabel, { color: colors.textSecondary }]}>
                Total Cards
              </Text>
            </View>
            <View style={styles.statItem}>
              <Text style={[styles.statValue, { color: colors.accent }]}>
                ${stats.overview.totalValue.toLocaleString()}
              </Text>
              <Text style={[styles.statLabel, { color: colors.textSecondary }]}>
                Total Value
              </Text>
            </View>
            <View style={styles.statItem}>
              <Text style={[styles.statValue, { color: colors.highlight }]}>
                {stats.overview.cardsSold.toLocaleString()}
              </Text>
              <Text style={[styles.statLabel, { color: colors.textSecondary }]}>
                Cards Sold
              </Text>
            </View>
            <View style={styles.statItem}>
              <Text style={[styles.statValue, { color: colors.accent }]}>
                ${stats.overview.soldValue.toLocaleString()}
              </Text>
              <Text style={[styles.statLabel, { color: colors.textSecondary }]}>
                Sales Value
              </Text>
            </View>
          </View>
        </View>

        {/* Monthly Performance */}
        <View style={[styles.section, { backgroundColor: colors.card }]}>
          <Text style={[styles.sectionTitle, { color: colors.text }]}>
            This Month
          </Text>
          <View style={styles.monthlyGrid}>
            <View style={styles.monthlyItem}>
              <IconSymbol name="cart.fill" size={24} color={colors.primary} />
              <Text style={[styles.monthlyValue, { color: colors.text }]}>
                {stats.monthly.sales}
              </Text>
              <Text style={[styles.monthlyLabel, { color: colors.textSecondary }]}>
                Sales
              </Text>
            </View>
            <View style={styles.monthlyItem}>
              <IconSymbol name="dollarsign.circle.fill" size={24} color={colors.accent} />
              <Text style={[styles.monthlyValue, { color: colors.text }]}>
                ${stats.monthly.revenue.toLocaleString()}
              </Text>
              <Text style={[styles.monthlyLabel, { color: colors.textSecondary }]}>
                Revenue
              </Text>
            </View>
            <View style={styles.monthlyItem}>
              <IconSymbol name="plus.circle.fill" size={24} color={colors.highlight} />
              <Text style={[styles.monthlyValue, { color: colors.text }]}>
                {stats.monthly.newCards}
              </Text>
              <Text style={[styles.monthlyLabel, { color: colors.textSecondary }]}>
                New Cards
              </Text>
            </View>
            <View style={styles.monthlyItem}>
              <IconSymbol name="arrow.up.circle.fill" size={24} color={colors.accent} />
              <Text style={[styles.monthlyValue, { color: colors.text }]}>
                +{stats.monthly.growth}%
              </Text>
              <Text style={[styles.monthlyLabel, { color: colors.textSecondary }]}>
                Growth
              </Text>
            </View>
          </View>
        </View>

        {/* Top Sets */}
        <View style={[styles.section, { backgroundColor: colors.card }]}>
          <Text style={[styles.sectionTitle, { color: colors.text }]}>
            Top Sets
          </Text>
          {stats.topSets.map((set, index) => (
            <View key={index} style={styles.setItem}>
              <View style={styles.setRank}>
                <Text style={[styles.rankText, { color: colors.primary }]}>
                  #{index + 1}
                </Text>
              </View>
              <View style={styles.setInfo}>
                <Text style={[styles.setName, { color: colors.text }]}>
                  {set.name}
                </Text>
                <Text style={[styles.setDetails, { color: colors.textSecondary }]}>
                  {set.cards} cards • ${set.value.toLocaleString()}
                </Text>
              </View>
            </View>
          ))}
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
    padding: 16,
  },
  scrollContentWithTabBar: {
    paddingBottom: 100,
  },
  header: {
    marginBottom: 24,
  },
  title: {
    fontSize: 24,
    fontWeight: '700',
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 16,
  },
  section: {
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
  statsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginHorizontal: -8,
  },
  statItem: {
    width: '50%',
    padding: 8,
    alignItems: 'center',
  },
  statValue: {
    fontSize: 24,
    fontWeight: '700',
    marginBottom: 4,
  },
  statLabel: {
    fontSize: 13,
    textAlign: 'center',
  },
  monthlyGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginHorizontal: -8,
  },
  monthlyItem: {
    width: '50%',
    padding: 8,
    alignItems: 'center',
  },
  monthlyValue: {
    fontSize: 20,
    fontWeight: '700',
    marginTop: 8,
    marginBottom: 4,
  },
  monthlyLabel: {
    fontSize: 13,
  },
  setItem: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
  },
  setRank: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#007bff20',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  rankText: {
    fontSize: 16,
    fontWeight: '700',
  },
  setInfo: {
    flex: 1,
  },
  setName: {
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 4,
  },
  setDetails: {
    fontSize: 13,
  },
});
