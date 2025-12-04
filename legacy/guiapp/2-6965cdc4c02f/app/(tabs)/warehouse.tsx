
import React, { useState } from "react";
import { ScrollView, StyleSheet, View, Text, Pressable, Platform, TextInput, Image, Dimensions } from "react-native";
import { Stack } from "expo-router";
import { IconSymbol } from "@/components/IconSymbol";
import { colors } from "@/styles/commonStyles";

const { width } = Dimensions.get('window');
const CARD_WIDTH = (width - 48) / 2; // 2 columns with padding

export default function WarehouseScreen() {
  const [searchQuery, setSearchQuery] = useState("");
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');

  // Mock warehouse data with card images
  const warehouseCards = [
    {
      id: 1,
      name: "Charizard VMAX",
      set: "Darkness Ablaze",
      quantity: 3,
      condition: "Near Mint",
      location: "A-12",
      value: 450,
      image: "https://images.unsplash.com/photo-1613771404721-1f92d799e49f?w=400&h=560&fit=crop",
    },
    {
      id: 2,
      name: "Pikachu V",
      set: "Vivid Voltage",
      quantity: 8,
      condition: "Mint",
      location: "B-05",
      value: 85,
      image: "https://images.unsplash.com/photo-1606503153255-59d5c23f2925?w=400&h=560&fit=crop",
    },
    {
      id: 3,
      name: "Mewtwo GX",
      set: "Shining Legends",
      quantity: 5,
      condition: "Near Mint",
      location: "A-18",
      value: 120,
      image: "https://images.unsplash.com/photo-1611339555312-e607c8352fd7?w=400&h=560&fit=crop",
    },
    {
      id: 4,
      name: "Rayquaza VMAX",
      set: "Evolving Skies",
      quantity: 2,
      condition: "Mint",
      location: "C-03",
      value: 380,
      image: "https://images.unsplash.com/photo-1621259182978-fbf93132d53d?w=400&h=560&fit=crop",
    },
    {
      id: 5,
      name: "Umbreon VMAX",
      set: "Evolving Skies",
      quantity: 1,
      condition: "Near Mint",
      location: "C-07",
      value: 520,
      image: "https://images.unsplash.com/photo-1542779283-429940ce8336?w=400&h=560&fit=crop",
    },
    {
      id: 6,
      name: "Lugia V",
      set: "Silver Tempest",
      quantity: 4,
      condition: "Mint",
      location: "B-12",
      value: 210,
      image: "https://images.unsplash.com/photo-1606503153255-59d5c23f2925?w=400&h=560&fit=crop&sat=-100",
    },
    {
      id: 7,
      name: "Giratina VSTAR",
      set: "Lost Origin",
      quantity: 6,
      condition: "Near Mint",
      location: "C-15",
      value: 165,
      image: "https://images.unsplash.com/photo-1613771404721-1f92d799e49f?w=400&h=560&fit=crop&hue=180",
    },
    {
      id: 8,
      name: "Mew VMAX",
      set: "Fusion Strike",
      quantity: 7,
      condition: "Mint",
      location: "A-22",
      value: 195,
      image: "https://images.unsplash.com/photo-1611339555312-e607c8352fd7?w=400&h=560&fit=crop&hue=270",
    },
  ];

  const filteredCards = warehouseCards.filter(card =>
    card.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    card.set.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const totalQuantity = filteredCards.reduce((sum, card) => sum + card.quantity, 0);
  const totalValue = filteredCards.reduce((sum, card) => sum + (card.value * card.quantity), 0);

  return (
    <>
      <Stack.Screen
        options={{
          title: "Warehouse",
          headerShown: Platform.OS === 'ios',
        }}
      />
      <View style={[styles.container, { backgroundColor: colors.background }]}>
        <View style={styles.header}>
          <View style={styles.headerTop}>
            <View>
              <Text style={[styles.title, { color: colors.text }]}>
                Warehouse
              </Text>
              <Text style={[styles.subtitle, { color: colors.textSecondary }]}>
                {filteredCards.length} unique cards • {totalQuantity} total
              </Text>
            </View>
            <Pressable
              style={[styles.viewToggle, { backgroundColor: colors.card }]}
              onPress={() => setViewMode(viewMode === 'grid' ? 'list' : 'grid')}
            >
              <IconSymbol 
                name={viewMode === 'grid' ? 'list.bullet' : 'square.grid.2x2'} 
                size={22} 
                color={colors.accent} 
              />
            </Pressable>
          </View>

          <View style={[styles.statsRow]}>
            <View style={[styles.statCard, { backgroundColor: colors.card }]}>
              <IconSymbol name="cube.box.fill" size={20} color={colors.accent} />
              <Text style={[styles.statValue, { color: colors.text }]}>{totalQuantity}</Text>
              <Text style={[styles.statLabel, { color: colors.textSecondary }]}>Cards</Text>
            </View>
            <View style={[styles.statCard, { backgroundColor: colors.card }]}>
              <IconSymbol name="dollarsign.circle.fill" size={20} color={colors.accent} />
              <Text style={[styles.statValue, { color: colors.text }]}>${totalValue.toLocaleString()}</Text>
              <Text style={[styles.statLabel, { color: colors.textSecondary }]}>Value</Text>
            </View>
          </View>
        </View>

        <View style={[styles.searchContainer, { backgroundColor: colors.card }]}>
          <IconSymbol name="magnifyingglass" size={20} color={colors.textSecondary} />
          <TextInput
            style={[styles.searchInput, { color: colors.text }]}
            placeholder="Search cards..."
            placeholderTextColor={colors.textSecondary}
            value={searchQuery}
            onChangeText={setSearchQuery}
          />
          {searchQuery.length > 0 && (
            <Pressable onPress={() => setSearchQuery('')}>
              <IconSymbol name="xmark.circle.fill" size={20} color={colors.textSecondary} />
            </Pressable>
          )}
        </View>

        <ScrollView 
          style={styles.scrollView}
          contentContainerStyle={[
            styles.scrollContent,
            Platform.OS !== 'ios' && styles.scrollContentWithTabBar
          ]}
          showsVerticalScrollIndicator={false}
        >
          {viewMode === 'grid' ? (
            <View style={styles.gridContainer}>
              {filteredCards.map((card) => (
                <Pressable 
                  key={card.id} 
                  style={[styles.gridCard, { backgroundColor: colors.card }]}
                  onPress={() => console.log('Card pressed:', card.name)}
                >
                  <View style={styles.cardImageContainer}>
                    <Image 
                      source={{ uri: card.image }} 
                      style={styles.cardImage}
                      resizeMode="cover"
                    />
                    <View style={[styles.quantityBadge, { backgroundColor: colors.accent }]}>
                      <Text style={styles.quantityText}>×{card.quantity}</Text>
                    </View>
                  </View>
                  <View style={styles.gridCardInfo}>
                    <Text style={[styles.gridCardName, { color: colors.text }]} numberOfLines={1}>
                      {card.name}
                    </Text>
                    <Text style={[styles.gridCardSet, { color: colors.textSecondary }]} numberOfLines={1}>
                      {card.set}
                    </Text>
                    <View style={styles.gridCardFooter}>
                      <View style={styles.gridCardDetail}>
                        <IconSymbol name="location.fill" size={12} color={colors.textSecondary} />
                        <Text style={[styles.gridCardDetailText, { color: colors.textSecondary }]}>
                          {card.location}
                        </Text>
                      </View>
                      <Text style={[styles.gridCardValue, { color: colors.accent }]}>
                        ${card.value}
                      </Text>
                    </View>
                  </View>
                </Pressable>
              ))}
            </View>
          ) : (
            <View>
              {filteredCards.map((card) => (
                <Pressable 
                  key={card.id} 
                  style={[styles.listCard, { backgroundColor: colors.card }]}
                  onPress={() => console.log('Card pressed:', card.name)}
                >
                  <Image 
                    source={{ uri: card.image }} 
                    style={styles.listCardImage}
                    resizeMode="cover"
                  />
                  <View style={styles.listCardContent}>
                    <View style={styles.listCardHeader}>
                      <View style={styles.listCardInfo}>
                        <Text style={[styles.listCardName, { color: colors.text }]} numberOfLines={1}>
                          {card.name}
                        </Text>
                        <Text style={[styles.listCardSet, { color: colors.textSecondary }]} numberOfLines={1}>
                          {card.set}
                        </Text>
                      </View>
                      <View style={[styles.listQuantityBadge, { backgroundColor: colors.accent + '20' }]}>
                        <Text style={[styles.listQuantityText, { color: colors.accent }]}>
                          ×{card.quantity}
                        </Text>
                      </View>
                    </View>

                    <View style={styles.listCardDetails}>
                      <View style={styles.listDetailItem}>
                        <IconSymbol name="location.fill" size={14} color={colors.textSecondary} />
                        <Text style={[styles.listDetailText, { color: colors.textSecondary }]}>
                          {card.location}
                        </Text>
                      </View>

                      <View style={styles.listDetailItem}>
                        <IconSymbol name="star.fill" size={14} color={colors.textSecondary} />
                        <Text style={[styles.listDetailText, { color: colors.textSecondary }]}>
                          {card.condition}
                        </Text>
                      </View>

                      <View style={styles.listDetailItem}>
                        <IconSymbol name="dollarsign.circle.fill" size={14} color={colors.accent} />
                        <Text style={[styles.listValueText, { color: colors.accent }]}>
                          ${card.value}
                        </Text>
                      </View>
                    </View>
                  </View>
                </Pressable>
              ))}
            </View>
          )}
        </ScrollView>
      </View>
    </>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 16,
  },
  header: {
    marginBottom: 16,
  },
  headerTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 12,
  },
  title: {
    fontSize: 28,
    fontWeight: '700',
    marginBottom: 4,
  },
  subtitle: {
    fontSize: 14,
  },
  viewToggle: {
    width: 44,
    height: 44,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    boxShadow: '0px 2px 4px rgba(0, 0, 0, 0.08)',
    elevation: 2,
  },
  statsRow: {
    flexDirection: 'row',
    gap: 12,
  },
  statCard: {
    flex: 1,
    padding: 12,
    borderRadius: 12,
    alignItems: 'center',
    boxShadow: '0px 2px 4px rgba(0, 0, 0, 0.08)',
    elevation: 2,
  },
  statValue: {
    fontSize: 20,
    fontWeight: '700',
    marginTop: 4,
  },
  statLabel: {
    fontSize: 12,
    marginTop: 2,
  },
  searchContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
    borderRadius: 12,
    marginBottom: 16,
    boxShadow: '0px 2px 4px rgba(0, 0, 0, 0.08)',
    elevation: 2,
  },
  searchInput: {
    flex: 1,
    marginLeft: 8,
    fontSize: 16,
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    paddingBottom: 16,
  },
  scrollContentWithTabBar: {
    paddingBottom: 100,
  },
  
  // Grid View Styles
  gridContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
  },
  gridCard: {
    width: CARD_WIDTH,
    borderRadius: 12,
    overflow: 'hidden',
    boxShadow: '0px 2px 6px rgba(0, 0, 0, 0.1)',
    elevation: 3,
  },
  cardImageContainer: {
    position: 'relative',
    width: '100%',
    aspectRatio: 0.714, // Standard trading card ratio (2.5" x 3.5")
  },
  cardImage: {
    width: '100%',
    height: '100%',
  },
  quantityBadge: {
    position: 'absolute',
    top: 8,
    right: 8,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 16,
    boxShadow: '0px 2px 4px rgba(0, 0, 0, 0.2)',
    elevation: 4,
  },
  quantityText: {
    color: '#ffffff',
    fontSize: 14,
    fontWeight: '700',
  },
  gridCardInfo: {
    padding: 12,
  },
  gridCardName: {
    fontSize: 15,
    fontWeight: '600',
    marginBottom: 2,
  },
  gridCardSet: {
    fontSize: 12,
    marginBottom: 8,
  },
  gridCardFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  gridCardDetail: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  gridCardDetailText: {
    fontSize: 11,
  },
  gridCardValue: {
    fontSize: 14,
    fontWeight: '700',
  },

  // List View Styles
  listCard: {
    flexDirection: 'row',
    borderRadius: 12,
    marginBottom: 12,
    overflow: 'hidden',
    boxShadow: '0px 2px 6px rgba(0, 0, 0, 0.08)',
    elevation: 2,
  },
  listCardImage: {
    width: 80,
    height: 112,
  },
  listCardContent: {
    flex: 1,
    padding: 12,
    justifyContent: 'space-between',
  },
  listCardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 8,
  },
  listCardInfo: {
    flex: 1,
    marginRight: 8,
  },
  listCardName: {
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 2,
  },
  listCardSet: {
    fontSize: 13,
  },
  listQuantityBadge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  listQuantityText: {
    fontSize: 13,
    fontWeight: '700',
  },
  listCardDetails: {
    flexDirection: 'row',
    gap: 12,
  },
  listDetailItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  listDetailText: {
    fontSize: 12,
  },
  listValueText: {
    fontSize: 13,
    fontWeight: '600',
  },
});
