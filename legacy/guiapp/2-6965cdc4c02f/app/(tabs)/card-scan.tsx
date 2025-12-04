
import React, { useState } from "react";
import { ScrollView, StyleSheet, View, Text, Pressable, Platform, Alert } from "react-native";
import { Stack } from "expo-router";
import { IconSymbol } from "@/components/IconSymbol";
import { colors } from "@/styles/commonStyles";
import * as ImagePicker from 'expo-image-picker';

export default function CardScanScreen() {
  const [scannedCard, setScannedCard] = useState<any>(null);

  const handleScanCard = async () => {
    try {
      const permissionResult = await ImagePicker.requestCameraPermissionsAsync();
      
      if (permissionResult.granted === false) {
        Alert.alert("Permission Required", "Camera permission is required to scan cards.");
        return;
      }

      const result = await ImagePicker.launchCameraAsync({
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
        allowsEditing: true,
        aspect: [3, 4],
        quality: 1,
      });

      if (!result.canceled) {
        // Mock card analysis result
        setScannedCard({
          name: "Charizard VMAX",
          set: "Darkness Ablaze",
          number: "020/189",
          rarity: "Ultra Rare",
          condition: "Near Mint",
          estimatedValue: 450,
          image: result.assets[0].uri,
        });
      }
    } catch (error) {
      console.log("Error scanning card:", error);
      Alert.alert("Error", "Failed to scan card. Please try again.");
    }
  };

  const handleUploadImage = async () => {
    try {
      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
        allowsEditing: true,
        aspect: [3, 4],
        quality: 1,
      });

      if (!result.canceled) {
        // Mock card analysis result
        setScannedCard({
          name: "Pikachu V",
          set: "Vivid Voltage",
          number: "043/185",
          rarity: "Rare Holo V",
          condition: "Mint",
          estimatedValue: 85,
          image: result.assets[0].uri,
        });
      }
    } catch (error) {
      console.log("Error uploading image:", error);
      Alert.alert("Error", "Failed to upload image. Please try again.");
    }
  };

  return (
    <>
      <Stack.Screen
        options={{
          title: "Card Scan Analysis",
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
            Card Scan Analysis
          </Text>
          <Text style={[styles.subtitle, { color: colors.textSecondary }]}>
            Scan or upload a card image for instant analysis
          </Text>
        </View>

        <View style={styles.actionButtons}>
          <Pressable
            style={[styles.actionButton, { backgroundColor: colors.primary }]}
            onPress={handleScanCard}
          >
            <IconSymbol name="camera.fill" size={32} color="#ffffff" />
            <Text style={styles.actionButtonText}>Scan Card</Text>
          </Pressable>

          <Pressable
            style={[styles.actionButton, { backgroundColor: colors.accent }]}
            onPress={handleUploadImage}
          >
            <IconSymbol name="photo.fill" size={32} color="#ffffff" />
            <Text style={styles.actionButtonText}>Upload Image</Text>
          </Pressable>
        </View>

        {scannedCard && (
          <View style={[styles.resultCard, { backgroundColor: colors.card }]}>
            <View style={styles.resultHeader}>
              <IconSymbol name="checkmark.circle.fill" size={32} color={colors.accent} />
              <Text style={[styles.resultTitle, { color: colors.text }]}>
                Card Identified
              </Text>
            </View>

            <View style={styles.resultDetails}>
              <View style={styles.detailRow}>
                <Text style={[styles.detailLabel, { color: colors.textSecondary }]}>
                  Name:
                </Text>
                <Text style={[styles.detailValue, { color: colors.text }]}>
                  {scannedCard.name}
                </Text>
              </View>

              <View style={styles.detailRow}>
                <Text style={[styles.detailLabel, { color: colors.textSecondary }]}>
                  Set:
                </Text>
                <Text style={[styles.detailValue, { color: colors.text }]}>
                  {scannedCard.set}
                </Text>
              </View>

              <View style={styles.detailRow}>
                <Text style={[styles.detailLabel, { color: colors.textSecondary }]}>
                  Number:
                </Text>
                <Text style={[styles.detailValue, { color: colors.text }]}>
                  {scannedCard.number}
                </Text>
              </View>

              <View style={styles.detailRow}>
                <Text style={[styles.detailLabel, { color: colors.textSecondary }]}>
                  Rarity:
                </Text>
                <Text style={[styles.detailValue, { color: colors.text }]}>
                  {scannedCard.rarity}
                </Text>
              </View>

              <View style={styles.detailRow}>
                <Text style={[styles.detailLabel, { color: colors.textSecondary }]}>
                  Condition:
                </Text>
                <Text style={[styles.detailValue, { color: colors.text }]}>
                  {scannedCard.condition}
                </Text>
              </View>

              <View style={[styles.detailRow, styles.valueRow]}>
                <Text style={[styles.detailLabel, { color: colors.textSecondary }]}>
                  Estimated Value:
                </Text>
                <Text style={[styles.valueText, { color: colors.accent }]}>
                  ${scannedCard.estimatedValue}
                </Text>
              </View>
            </View>

            <Pressable
              style={[styles.addButton, { backgroundColor: colors.primary }]}
              onPress={() => Alert.alert("Success", "Card added to warehouse!")}
            >
              <Text style={styles.addButtonText}>Add to Warehouse</Text>
            </Pressable>
          </View>
        )}

        {!scannedCard && (
          <View style={[styles.emptyState, { backgroundColor: colors.card }]}>
            <IconSymbol name="camera.fill" size={64} color={colors.textSecondary} />
            <Text style={[styles.emptyText, { color: colors.textSecondary }]}>
              No card scanned yet
            </Text>
            <Text style={[styles.emptySubtext, { color: colors.textSecondary }]}>
              Use the buttons above to scan or upload a card image
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
  actionButtons: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 24,
  },
  actionButton: {
    flex: 1,
    padding: 24,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    boxShadow: '0px 2px 6px rgba(0, 0, 0, 0.1)',
    elevation: 3,
  },
  actionButtonText: {
    color: '#ffffff',
    fontSize: 16,
    fontWeight: '600',
    marginTop: 8,
  },
  resultCard: {
    padding: 20,
    borderRadius: 12,
    boxShadow: '0px 2px 8px rgba(0, 0, 0, 0.1)',
    elevation: 3,
  },
  resultHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 20,
  },
  resultTitle: {
    fontSize: 20,
    fontWeight: '700',
    marginLeft: 12,
  },
  resultDetails: {
    marginBottom: 20,
  },
  detailRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
  },
  detailLabel: {
    fontSize: 14,
    fontWeight: '500',
  },
  detailValue: {
    fontSize: 14,
    fontWeight: '600',
  },
  valueRow: {
    borderBottomWidth: 0,
    marginTop: 8,
  },
  valueText: {
    fontSize: 20,
    fontWeight: '700',
  },
  addButton: {
    padding: 16,
    borderRadius: 8,
    alignItems: 'center',
  },
  addButtonText: {
    color: '#ffffff',
    fontSize: 16,
    fontWeight: '600',
  },
  emptyState: {
    padding: 40,
    borderRadius: 12,
    alignItems: 'center',
    boxShadow: '0px 2px 6px rgba(0, 0, 0, 0.08)',
    elevation: 2,
  },
  emptyText: {
    fontSize: 18,
    fontWeight: '600',
    marginTop: 16,
  },
  emptySubtext: {
    fontSize: 14,
    marginTop: 8,
    textAlign: 'center',
  },
});
