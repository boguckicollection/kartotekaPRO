
import React, { useState } from "react";
import { ScrollView, StyleSheet, View, Text, Pressable, Platform } from "react-native";
import { Stack } from "expo-router";
import { IconSymbol } from "@/components/IconSymbol";
import { colors } from "@/styles/commonStyles";

export default function OrdersScreen() {
  const [selectedTab, setSelectedTab] = useState<"pending" | "completed">("pending");

  // Mock orders data
  const orders = {
    pending: [
      {
        id: "ORD-001",
        customer: "John Smith",
        items: 3,
        total: 245,
        date: "2024-01-15",
        status: "processing",
      },
      {
        id: "ORD-002",
        customer: "Sarah Johnson",
        items: 1,
        total: 450,
        date: "2024-01-15",
        status: "pending",
      },
      {
        id: "ORD-003",
        customer: "Mike Davis",
        items: 5,
        total: 680,
        date: "2024-01-14",
        status: "processing",
      },
    ],
    completed: [
      {
        id: "ORD-004",
        customer: "Emily Brown",
        items: 2,
        total: 320,
        date: "2024-01-13",
        status: "completed",
      },
      {
        id: "ORD-005",
        customer: "David Wilson",
        items: 4,
        total: 890,
        date: "2024-01-12",
        status: "completed",
      },
    ],
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "pending":
        return colors.highlight;
      case "processing":
        return colors.primary;
      case "completed":
        return colors.accent;
      default:
        return colors.secondary;
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "pending":
        return "clock.fill";
      case "processing":
        return "arrow.clockwise.circle.fill";
      case "completed":
        return "checkmark.circle.fill";
      default:
        return "circle.fill";
    }
  };

  const currentOrders = selectedTab === "pending" ? orders.pending : orders.completed;

  return (
    <>
      <Stack.Screen
        options={{
          title: "Orders",
          headerShown: Platform.OS === 'ios',
        }}
      />
      <View style={[styles.container, { backgroundColor: colors.background }]}>
        <View style={styles.header}>
          <Text style={[styles.title, { color: colors.text }]}>
            Order Management
          </Text>
          <Text style={[styles.subtitle, { color: colors.textSecondary }]}>
            Track and manage customer orders
          </Text>
        </View>

        <View style={[styles.tabContainer, { backgroundColor: colors.card }]}>
          <Pressable
            style={[
              styles.tab,
              selectedTab === "pending" && { backgroundColor: colors.primary },
            ]}
            onPress={() => setSelectedTab("pending")}
          >
            <Text
              style={[
                styles.tabText,
                selectedTab === "pending" ? { color: '#ffffff' } : { color: colors.text },
              ]}
            >
              Pending ({orders.pending.length})
            </Text>
          </Pressable>
          <Pressable
            style={[
              styles.tab,
              selectedTab === "completed" && { backgroundColor: colors.primary },
            ]}
            onPress={() => setSelectedTab("completed")}
          >
            <Text
              style={[
                styles.tabText,
                selectedTab === "completed" ? { color: '#ffffff' } : { color: colors.text },
              ]}
            >
              Completed ({orders.completed.length})
            </Text>
          </Pressable>
        </View>

        <ScrollView 
          style={styles.scrollView}
          contentContainerStyle={[
            styles.scrollContent,
            Platform.OS !== 'ios' && styles.scrollContentWithTabBar
          ]}
          showsVerticalScrollIndicator={false}
        >
          {currentOrders.map((order) => (
            <View key={order.id} style={[styles.orderCard, { backgroundColor: colors.card }]}>
              <View style={styles.orderHeader}>
                <View style={styles.orderInfo}>
                  <Text style={[styles.orderId, { color: colors.text }]}>
                    {order.id}
                  </Text>
                  <Text style={[styles.customerName, { color: colors.textSecondary }]}>
                    {order.customer}
                  </Text>
                </View>
                <View style={[styles.statusBadge, { backgroundColor: getStatusColor(order.status) + '20' }]}>
                  <IconSymbol 
                    name={getStatusIcon(order.status) as any} 
                    size={14} 
                    color={getStatusColor(order.status)} 
                  />
                  <Text style={[styles.statusText, { color: getStatusColor(order.status) }]}>
                    {order.status.charAt(0).toUpperCase() + order.status.slice(1)}
                  </Text>
                </View>
              </View>

              <View style={styles.orderDetails}>
                <View style={styles.detailRow}>
                  <View style={styles.detailItem}>
                    <IconSymbol name="calendar" size={16} color={colors.textSecondary} />
                    <Text style={[styles.detailText, { color: colors.textSecondary }]}>
                      {order.date}
                    </Text>
                  </View>
                  <View style={styles.detailItem}>
                    <IconSymbol name="square.stack.3d.up.fill" size={16} color={colors.textSecondary} />
                    <Text style={[styles.detailText, { color: colors.textSecondary }]}>
                      {order.items} items
                    </Text>
                  </View>
                </View>
                <View style={styles.totalRow}>
                  <Text style={[styles.totalLabel, { color: colors.textSecondary }]}>
                    Total:
                  </Text>
                  <Text style={[styles.totalValue, { color: colors.accent }]}>
                    ${order.total}
                  </Text>
                </View>
              </View>

              <Pressable
                style={[styles.actionButton, { backgroundColor: colors.primary }]}
                onPress={() => console.log("View order", order.id)}
              >
                <Text style={styles.actionButtonText}>View Details</Text>
              </Pressable>
            </View>
          ))}
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
  title: {
    fontSize: 24,
    fontWeight: '700',
    marginBottom: 4,
  },
  subtitle: {
    fontSize: 16,
  },
  tabContainer: {
    flexDirection: 'row',
    padding: 4,
    borderRadius: 8,
    marginBottom: 16,
    boxShadow: '0px 2px 4px rgba(0, 0, 0, 0.08)',
    elevation: 2,
  },
  tab: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: 6,
    alignItems: 'center',
  },
  tabText: {
    fontSize: 14,
    fontWeight: '600',
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
  orderCard: {
    padding: 16,
    borderRadius: 12,
    marginBottom: 12,
    boxShadow: '0px 2px 6px rgba(0, 0, 0, 0.08)',
    elevation: 2,
  },
  orderHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 16,
  },
  orderInfo: {
    flex: 1,
  },
  orderId: {
    fontSize: 18,
    fontWeight: '700',
    marginBottom: 4,
  },
  customerName: {
    fontSize: 14,
  },
  statusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 12,
  },
  statusText: {
    fontSize: 12,
    fontWeight: '600',
    marginLeft: 4,
  },
  orderDetails: {
    marginBottom: 16,
  },
  detailRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 12,
  },
  detailItem: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  detailText: {
    fontSize: 13,
    marginLeft: 6,
  },
  totalRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: '#e0e0e0',
  },
  totalLabel: {
    fontSize: 14,
    fontWeight: '500',
  },
  totalValue: {
    fontSize: 20,
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
