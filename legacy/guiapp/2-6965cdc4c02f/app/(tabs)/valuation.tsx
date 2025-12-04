
import React, { useState } from "react";
import { ScrollView, StyleSheet, View, Text, Pressable, Platform, TextInput } from "react-native";
import { Stack } from "expo-router";
import { IconSymbol } from "@/components/IconSymbol";
import { colors } from "@/styles/commonStyles";

export default function ValuationScreen() {
  const [cardName, setCardName] = useState("");
  const [selectedCondition, setSelectedCondition] = useState("Near Mint");

  const conditions = ["Mint", "Near Mint", "Excellent", "Good", "Played"];

  // Mock valuation data
  const valuationResults = cardName.length > 0 ? [
    { condition: "Mint", price: 450, trend: "+5%" },
    { condition: "Near Mint", price: 380, trend: "+3%" },
    { condition: "Excellent", price: 320, trend: "+2%" },
    { condition: "Good", price: 250, trend: "0%" },
    { condition: "Played", price: 180, trend: "-2%" },
  ] : [];

  return (
    <>
      <Stack.Screen
        options={{
          title: "Card Valuation",
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
            Card Valuation
          </Text>
          <Text style={[styles.subtitle, { color: colors.textSecondary }]}>
            Get real-time pricing for your trading cards
          </Text>
        </View>

        <View style={[styles.searchCard, { backgroundColor: colors.card }]}>
          <Text style={[styles.label, { color: colors.text }]}>
            Card Name
          </Text>
          <TextInput
            style={[styles.input, { color: colors.text, borderColor: colors.textSecondary }]}
            placeholder="Enter card name..."
            placeholderTextColor={colors.textSecondary}
            value={cardName}
            onChangeText={setCardName}
          />

          <Text style={[styles.label, { color: colors.text }]}>
            Condition
          </Text>
          <View style={styles.conditionButtons}>
            {conditions.map((condition) => (
              <Pressable
                key={condition}
                style={[
                  styles.conditionButton,
                  selectedCondition === condition && { backgroundColor: colors.primary },
                  selectedCondition !== condition && { backgroundColor: colors.card, borderWidth: 1, borderColor: colors.textSecondary },
                ]}
                onPress={() => setSelectedCondition(condition)}
              >
                <Text
                  style={[
                    styles.conditionText,
                    selectedCondition === condition && { color: '#ffffff' },
                    selectedCondition !== condition && { color: colors.text },
                  ]}
                >
                  {condition}
                </Text>
              </Pressable>
            ))}
          </View>
        </View>

        {valuationResults.length > 0 && (
          <View style={[styles.resultsCard, { backgroundColor: colors.card }]}>
            <View style={styles.resultsHeader}>
              <IconSymbol name="dollarsign.circle.fill" size={32} color={colors.accent} />
              <Text style={[styles.resultsTitle, { color: colors.text }]}>
                Valuation Results
              </Text>
            </View>

            {valuationResults.map((result, index) => (
              <View key={index} style={styles.resultRow}>
                <View style={styles.resultInfo}>
                  <Text style={[styles.resultCondition, { color: colors.text }]}>
                    {result.condition}
                  </Text>
                  <Text style={[styles.resultTrend, { color: result.trend.startsWith('+') ? colors.accent : colors.secondary }]}>
                    {result.trend}
                  </Text>
                </View>
                <Text style={[styles.resultPrice, { color: colors.accent }]}>
                  ${result.price}
                </Text>
              </View>
            ))}

            <View style={styles.marketInfo}>
              <IconSymbol name="info.circle.fill" size={20} color={colors.primary} />
              <Text style={[styles.marketText, { color: colors.textSecondary }]}>
                Prices based on recent market data
              </Text>
            </View>
          </View>
        )}

        {cardName.length === 0 && (
          <View style={[styles.emptyState, { backgroundColor: colors.card }]}>
            <IconSymbol name="dollarsign.circle.fill" size={64} color={colors.textSecondary} />
            <Text style={[styles.emptyText, { color: colors.textSecondary }]}>
              Enter a card name to see valuations
            </Text>
          </View>
        )}
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
  searchCard: {
    padding: 20,
    borderRadius: 12,
    marginBottom: 16,
    boxShadow: '0px 2px 8px rgba(0, 0, 0, 0.1)',
    elevation: 3,
  },
  label: {
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 8,
  },
  input: {
    borderWidth: 1,
    borderRadius: 8,
    padding: 12,
    fontSize: 16,
    marginBottom: 20,
  },
  conditionButtons: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  conditionButton: {
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 8,
  },
  conditionText: {
    fontSize: 14,
    fontWeight: '600',
  },
  resultsCard: {
    padding: 20,
    borderRadius: 12,
    boxShadow: '0px 2px 8px rgba(0, 0, 0, 0.1)',
    elevation: 3,
  },
  resultsHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 20,
  },
  resultsTitle: {
    fontSize: 20,
    fontWeight: '700',
    marginLeft: 12,
  },
  resultRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
  },
  resultInfo: {
    flex: 1,
  },
  resultCondition: {
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 4,
  },
  resultTrend: {
    fontSize: 13,
    fontWeight: '500',
  },
  resultPrice: {
    fontSize: 20,
    fontWeight: '700',
  },
  marketInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 16,
    padding: 12,
    backgroundColor: '#007bff10',
    borderRadius: 8,
  },
  marketText: {
    fontSize: 13,
    marginLeft: 8,
  },
  emptyState: {
    padding: 40,
    borderRadius: 12,
    alignItems: 'center',
    boxShadow: '0px 2px 6px rgba(0, 0, 0, 0.08)',
    elevation: 2,
  },
  emptyText: {
    fontSize: 16,
    marginTop: 16,
    textAlign: 'center',
  },
});
