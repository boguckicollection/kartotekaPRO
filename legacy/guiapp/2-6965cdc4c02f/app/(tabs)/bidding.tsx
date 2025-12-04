
import React from "react";
import { ScrollView, StyleSheet, View, Text, Pressable, Platform } from "react-native";
import { Stack } from "expo-router";
import { IconSymbol } from "@/components/IconSymbol";
import { colors } from "@/styles/commonStyles";

export default function BiddingScreen() {
  // Mock bidding data
  const activeBids = [
    {
      id: 1,
      cardName: "Charizard VMAX",
      currentBid: 420,
      yourBid: 400,
      timeLeft: "2h 15m",
      status: "outbid",
    },
    {
      id: 2,
      cardName: "Pikachu V",
      currentBid: 85,
      yourBid: 85,
      timeLeft: "5h 42m",
      status: "winning",
    },
    {
      id: 3,
      cardName: "Umbreon VMAX",
      currentBid: 510,
      yourBid: 510,
      timeLeft: "1d 3h",
      status: "winning",
    },
  ];

  const getStatusColor = (status: string) => {
    return status === "winning" ? colors.accent : colors.highlight;
  };

  const getStatusIcon = (status: string) => {
    return status === "winning" ? "checkmark.circle.fill" : "exclamationmark.circle.fill";
  };

  return (
    <>
      <Stack.Screen
        options={{
          title: "Bidding",
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
            Bidding & Auctions
          </Text>
          <Text style={[styles.subtitle, { color: colors.textSecondary }]}>
            Manage your active bids and auctions
          </Text>
        </View>

        <View style={[styles.summaryCard, { backgroundColor: colors.card }]}>
          <View style={styles.summaryItem}>
            <Text style={[styles.summaryValue, { color: colors.primary }]}>
              {activeBids.length}
            </Text>
            <Text style={[styles.summaryLabel, { color: colors.textSecondary }]}>
              Active Bids
            </Text>
          </View>
          <View style={styles.summaryItem}>
            <Text style={[styles.summaryValue, { color: colors.accent }]}>
              {activeBids.filter(b => b.status === "winning").length}
            </Text>
            <Text style={[styles.summaryLabel, { color: colors.textSecondary }]}>
              Winning
            </Text>
          </View>
          <View style={styles.summaryItem}>
            <Text style={[styles.summaryValue, { color: colors.highlight }]}>
              {activeBids.filter(b => b.status === "outbid").length}
            </Text>
            <Text style={[styles.summaryLabel, { color: colors.textSecondary }]}>
              Outbid
            </Text>
          </View>
        </View>

        <Text style={[styles.sectionTitle, { color: colors.text }]}>
          Active Bids
        </Text>

        {activeBids.map((bid) => (
          <View key={bid.id} style={[styles.bidCard, { backgroundColor: colors.card }]}>
            <View style={styles.bidHeader}>
              <View style={styles.bidInfo}>
                <Text style={[styles.cardName, { color: colors.text }]}>
                  {bid.cardName}
                </Text>
                <View style={styles.timeContainer}>
                  <IconSymbol name="clock.fill" size={14} color={colors.textSecondary} />
                  <Text style={[styles.timeText, { color: colors.textSecondary }]}>
                    {bid.timeLeft}
                  </Text>
                </View>
              </View>
              <View style={[styles.statusBadge, { backgroundColor: getStatusColor(bid.status) + '20' }]}>
                <IconSymbol 
                  name={getStatusIcon(bid.status) as any} 
                  size={16} 
                  color={getStatusColor(bid.status)} 
                />
                <Text style={[styles.statusText, { color: getStatusColor(bid.status) }]}>
                  {bid.status === "winning" ? "Winning" : "Outbid"}
                </Text>
              </View>
            </View>

            <View style={styles.bidDetails}>
              <View style={styles.bidDetailItem}>
                <Text style={[styles.bidLabel, { color: colors.textSecondary }]}>
                  Your Bid
                </Text>
                <Text style={[styles.bidValue, { color: colors.text }]}>
                  ${bid.yourBid}
                </Text>
              </View>
              <View style={styles.bidDetailItem}>
                <Text style={[styles.bidLabel, { color: colors.textSecondary }]}>
                  Current Bid
                </Text>
                <Text style={[styles.bidValue, { color: colors.accent }]}>
                  ${bid.currentBid}
                </Text>
              </View>
            </View>

            <Pressable
              style={[styles.actionButton, { backgroundColor: colors.primary }]}
              onPress={() => console.log("Increase bid for", bid.cardName)}
            >
              <Text style={styles.actionButtonText}>
                {bid.status === "outbid" ? "Increase Bid" : "View Details"}
              </Text>
            </Pressable>
          </View>
        ))}
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
  summaryCard: {
    flexDirection: 'row',
    padding: 20,
    borderRadius: 12,
    marginBottom: 24,
    boxShadow: '0px 2px 8px rgba(0, 0, 0, 0.1)',
    elevation: 3,
  },
  summaryItem: {
    flex: 1,
    alignItems: 'center',
  },
  summaryValue: {
    fontSize: 28,
    fontWeight: '700',
    marginBottom: 4,
  },
  summaryLabel: {
    fontSize: 13,
  },
  sectionTitle: {
    fontSize: 20,
    fontWeight: '700',
    marginBottom: 16,
  },
  bidCard: {
    padding: 16,
    borderRadius: 12,
    marginBottom: 12,
    boxShadow: '0px 2px 6px rgba(0, 0, 0, 0.08)',
    elevation: 2,
  },
  bidHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 16,
  },
  bidInfo: {
    flex: 1,
  },
  cardName: {
    fontSize: 18,
    fontWeight: '600',
    marginBottom: 8,
  },
  timeContainer: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  timeText: {
    fontSize: 13,
    marginLeft: 4,
  },
  statusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 12,
  },
  statusText: {
    fontSize: 13,
    fontWeight: '600',
    marginLeft: 4,
  },
  bidDetails: {
    flexDirection: 'row',
    marginBottom: 16,
  },
  bidDetailItem: {
    flex: 1,
  },
  bidLabel: {
    fontSize: 13,
    marginBottom: 4,
  },
  bidValue: {
    fontSize: 18,
    fontWeight: '700',
  },
  actionButton: {
    padding: 12,
    borderRadius: 8,
    alignItems: 'center',
  },
  actionButtonText: {
    color: '#ffffff',
    fontSize: 15,
    fontWeight: '600',
  },
});
