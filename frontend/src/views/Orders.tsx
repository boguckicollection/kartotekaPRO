import React, { useState, useRef, useEffect, useCallback } from 'react';
import { ThermalReceipt } from '../components/ThermalReceipt';

type Props = { 
  items?: any[];
  apiBase?: string;
}

// Skeleton Loading Component
function OrderSkeleton() {
  return (
    <div className="rounded-lg p-3 bg-[#1f2937] border border-white/10 animate-pulse">
      <div className="flex justify-between items-start mb-2">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-full bg-gray-700"></div>
          <div>
            <div className="h-4 w-20 bg-gray-700 rounded mb-1"></div>
            <div className="h-3 w-24 bg-gray-800 rounded"></div>
          </div>
        </div>
        <div className="h-5 w-16 bg-gray-700 rounded"></div>
      </div>
      <div className="flex justify-between items-center pt-2 border-t border-white/5">
        <div className="h-3 w-16 bg-gray-800 rounded"></div>
        <div className="h-4 w-20 bg-gray-700 rounded"></div>
      </div>
    </div>
  );
}

// Loading Spinner Component
function LoadingSpinner() {
  return (
    <div className="flex items-center justify-center gap-2 text-gray-400">
      <div className="w-5 h-5 border-2 border-primary border-t-transparent rounded-full animate-spin"></div>
      <span className="text-sm">Ładowanie...</span>
    </div>
  );
}

export default function OrdersView({ items: initialItems, apiBase }: Props) {
  const [orders, setOrders] = useState<any[]>([]);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const [hasMore, setHasMore] = useState(true);
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<any | null>(null);
  const [statuses, setStatuses] = useState<any[]>([]);
  const [changingStatus, setChangingStatus] = useState(false);
  const receiptRef = useRef<HTMLDivElement>(null);
  const observerTarget = useRef<HTMLDivElement>(null);
  const hasInitialized = useRef(false);

  // Helper to fetch Furgonetka statuses
  const fetchFurgonetkaStatuses = useCallback(async (ordersToUpdate: any[]) => {
    if (!apiBase || !ordersToUpdate.length) return;

    try {
      // Fetch statuses in parallel
      const updatedOrders = await Promise.all(
        ordersToUpdate.map(async (order) => {
          try {
            const res = await fetch(`${apiBase}/furgonetka/shipments/sync/${order.id}`);
            if (res.ok) {
              const data = await res.json();
              return {
                ...order,
                furgonetka_status: data.status,
                shipment_id: data.shipment_id,
                package_id: data.package_id,
                label_url: data.label_url
              };
            }
          } catch (e) {
            console.error(`Failed to sync Furgonetka for order ${order.id}`, e);
          }
          return order;
        })
      );

      // Update state with new info
      setOrders(prev => {
        const orderMap = new Map(prev.map(o => [o.id, o]));
        updatedOrders.forEach(o => orderMap.set(o.id, o));
        // Return sorted values
        return Array.from(orderMap.values()).sort((a: any, b: any) => (b.id || 0) - (a.id || 0));
      });
    } catch (err) {
      console.error('Failed to fetch Furgonetka statuses', err);
    }
  }, [apiBase]);

  const handlePrint = () => {
    const receiptElement = receiptRef.current;
    if (!receiptElement) return;

    const printWindow = window.open('', '_blank', 'width=227,height=302');
    if (!printWindow) {
      alert('Proszę zezwolić na wyskakujące okienka dla tej strony');
      return;
    }

    printWindow.document.write(`
      <!DOCTYPE html>
      <html>
        <head>
          <title>Paragon #${selected?.id || ''}</title>
          <style>
            @page {
              size: 60mm 80mm;
              margin: 0;
            }
            @media print {
              html, body {
                width: 60mm;
                height: 80mm;
                margin: 0;
                padding: 0;
                -webkit-print-color-adjust: exact;
                print-color-adjust: exact;
              }
            }
            * {
              box-sizing: border-box;
            }
            body {
              margin: 0;
              padding: 0;
              font-family: Consolas, Monaco, "Courier New", monospace;
              font-size: 9pt;
              line-height: 1.3;
              background: white;
              color: black;
            }
          </style>
        </head>
        <body>
          ${receiptElement.innerHTML}
        </body>
      </html>
    `);
    printWindow.document.close();

    printWindow.onload = function() {
      setTimeout(() => {
        printWindow.focus();
        printWindow.print();
        printWindow.close();
      }, 100);
    };
  };

  // Load statuses from API
  const loadStatuses = useCallback(async () => {
    if (!apiBase) return;
    try {
      const res = await fetch(`${apiBase}/orders/statuses`);
      if (!res.ok) {
        console.error('Failed to load statuses:', res.status);
        setStatuses([]);
        return;
      }
      const data = await res.json();
      setStatuses(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error('Failed to load statuses', err);
      setStatuses([]);
    }
  }, [apiBase]);

  // Load orders from API
  const loadOrders = useCallback(async (pageNum: number = 1, append: boolean = false) => {
    if (!apiBase || loading) return;
    
    setLoading(true);
    try {
      const res = await fetch(`${apiBase}/orders?page=${pageNum}&limit=20&detailed=1`);
      const newOrders = await res.json();
      
      if (newOrders.length < 20) {
        setHasMore(false);
      }
      
      // Sort by ID descending (newest first)
      const sortedOrders = newOrders.sort((a: any, b: any) => (b.id || 0) - (a.id || 0));
      
      if (append) {
        setOrders(prev => [...prev, ...sortedOrders]);
      } else {
        setOrders(sortedOrders);
      }
      
      // Fetch Furgonetka statuses in background
      fetchFurgonetkaStatuses(sortedOrders);
      
      setPage(pageNum + 1);
    } catch (err) {
      console.error('Failed to load orders', err);
    } finally {
      setLoading(false);
      setInitialLoading(false);
    }
  }, [apiBase, loading]);

  // Change order status
  const handleStatusChange = async (newStatusId: number) => {
    if (!apiBase || !selected) return;
    
    setChangingStatus(true);
    try {
      const res = await fetch(`${apiBase}/orders/${selected.id}/status`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status_id: newStatusId })
      });
      
      if (res.ok) {
        // Update local state
        const newStatus = statuses.find(s => s.id === newStatusId);
        const updatedOrder = {
          ...selected,
          status: {
            id: newStatusId,
            type: newStatus?.type,
            name: newStatus?.name,
            color: newStatus?.color
          }
        };
        setSelected(updatedOrder);
        
        // Update in orders list
        setOrders(prev => prev.map(o => 
          o.id === selected.id ? updatedOrder : o
        ));
      } else {
        alert('Nie udało się zmienić statusu');
      }
    } catch (err) {
      console.error('Failed to update status', err);
      alert('Błąd podczas zmiany statusu');
    } finally {
      setChangingStatus(false);
    }
  };

  // Initial load - use initialItems if provided, otherwise fetch from API
  useEffect(() => {
    if (hasInitialized.current) return;
    hasInitialized.current = true;

    if (initialItems && initialItems.length > 0) {
      // Sort initial items by ID descending
      const sortedItems = [...initialItems].sort((a: any, b: any) => (b.id || 0) - (a.id || 0));
      setOrders(sortedItems);
      fetchFurgonetkaStatuses(sortedItems);
      setInitialLoading(false);
      setHasMore(initialItems.length >= 20);
    } else if (apiBase) {
      loadOrders(1, false);
    }
    
    // Load statuses
    if (apiBase) {
      loadStatuses();
    }
  }, []);

  // Intersection Observer for infinite scroll
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMore && !loading && !initialLoading) {
          loadOrders(page, true);
        }
      },
      { threshold: 0.5 }
    );
    
    if (observerTarget.current) {
      observer.observe(observerTarget.current);
    }
    
    return () => {
      if (observerTarget.current) {
        observer.unobserve(observerTarget.current);
      }
    };
  }, [loadOrders, hasMore, loading, page, initialLoading]);

  const onOpen = async (o: any) => {
    setSelected(o);
    setOpen(true);
    
    // Fetch detailed order data if we don't have items yet
    if (apiBase && (!o.items || o.items.length === 0)) {
      try {
        const res = await fetch(`${apiBase}/orders/${o.id}`);
        if (res.ok) {
          const detailed = await res.json();
          setSelected(detailed);
          // Update in the orders list too
          setOrders(prev => prev.map(ord => ord.id === detailed.id ? detailed : ord));
        }
      } catch (err) {
        console.error('Failed to fetch order details:', err);
      }
    }
  };

  const onClose = () => {
    setOpen(false);
    setTimeout(() => {
      setSelected(null);
    }, 250);
  };

  const statusLabel = (o: any) => {
    if (o?.status?.name) return o.status.name;
    const t = o?.status?.type;
    if (t === 1) return 'Nowe';
    if (t === 2) return 'W realizacji';
    if (t === 3) return 'Zakończone';
    if (t === 4) return 'Anulowane';
    return '—';
  };

  const statusColor = (o: any) => {
    const statusId = o?.status?.id;
    
    // Specific status ID mappings (more precise than type)
    if (statusId === '1' || statusId === 1) return '#3498DB'; // złożone - niebieski
    if (statusId === '2' || statusId === 2) return '#9B59B6'; // przyjęte do realizacji - fioletowy
    if (statusId === '3' || statusId === 3) return '#F39C12'; // oczekiwanie na dostawę - pomarańczowy
    if (statusId === '4' || statusId === 4) return '#E67E22'; // w trakcie kompletowania - ciemny pomarańczowy
    if (statusId === '5' || statusId === 5) return '#E74C3C'; // oczekiwanie na płatność - czerwony
    if (statusId === '6' || statusId === 6) return '#1ABC9C'; // gotowe do wysłania - turkusowy
    if (statusId === '7' || statusId === 7) return '#2ECC71'; // przesyłka wysłana - zielony
    if (statusId === '8' || statusId === 8) return '#95A5A6'; // anulowane - szary
    if (statusId === '9' || statusId === 9) return '#7F8C8D'; // odrzucone - ciemny szary
    if (statusId === '11' || statusId === 11) return '#34495E'; // zwrócone - grafitowy
    
    // Fallback to type-based colors
    const t = o?.status?.type;
    if (t === 1) return '#3498DB'; // nowe
    if (t === 2) return '#F39C12'; // w realizacji
    if (t === 3) return '#2ECC71'; // zakończone
    if (t === 4) return '#95A5A6'; // anulowane
    
    return '#6B7280';
  };

  const statusIcon = (o: any) => {
    const statusId = o?.status?.id;
    
    // Specific icons for key statuses
    if (statusId === '1' || statusId === 1) return 'new_releases'; // złożone
    if (statusId === '2' || statusId === 2) return 'notification_important'; // przyjęte do realizacji - ważne!
    if (statusId === '3' || statusId === 3) return 'local_shipping'; // oczekiwanie na dostawę
    if (statusId === '4' || statusId === 4) return 'inventory_2'; // w trakcie kompletowania
    if (statusId === '5' || statusId === 5) return 'payments'; // oczekiwanie na płatność
    if (statusId === '6' || statusId === 6) return 'outbox'; // gotowe do wysłania
    if (statusId === '7' || statusId === 7) return 'local_shipping'; // przesyłka wysłana
    if (statusId === '8' || statusId === 8) return 'cancel'; // anulowane
    if (statusId === '9' || statusId === 9) return 'block'; // odrzucone
    if (statusId === '11' || statusId === 11) return 'keyboard_return'; // zwrócone
    
    // Fallback to type-based icons
    const t = o?.status?.type;
    if (t === 1) return 'new_releases';
    if (t === 2) return 'schedule';
    if (t === 3) return 'check_circle';
    if (t === 4) return 'cancel';
    
    return 'label';
  };
  
  const isNewOrder = (o: any) => {
    const statusId = o?.status?.id;
    // Status 1 (złożone) i 2 (przyjęte do realizacji) to nowe zamówienia
    return statusId === '1' || statusId === 1 || statusId === '2' || statusId === 2;
  };

  const getUserName = (o: any) => {
    const user = o?.user;
    if (!user) return null;
    
    const firstname = user.firstname || '';
    const lastname = user.lastname || '';
    const email = user.email || '';
    
    if (firstname || lastname) {
      return `${firstname} ${lastname}`.trim();
    }
    if (email) {
      return email.split('@')[0];
    }
    return null;
  };

  return (
    <div className="font-display">
      <header className="flex items-center justify-between whitespace-nowrap border-b border-gray-800 px-2 md:px-6 py-3">
        <div className="flex items-center gap-3 text-white">
          <span className="material-symbols-outlined text-primary">receipt_long</span>
          <h2 className="text-lg font-bold">Zamówienia</h2>
          {orders.length > 0 && (
            <span className="text-sm text-gray-400">({orders.length})</span>
          )}
        </div>
      </header>

      <main className="p-4 md:p-6">
        {initialLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
            {Array(8).fill(0).map((_, i) => <OrderSkeleton key={i} />)}
          </div>
        ) : !orders.length ? (
          <div className="rounded-xl p-8 bg-[#1f2937] border border-white/10 text-center max-w-md mx-auto">
            <span className="material-symbols-outlined text-6xl text-gray-600 mb-3 block">receipt_long</span>
            <p className="text-gray-400">Brak zamówień.</p>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
              {orders.map((o: any, i: number) => {
                const userName = getUserName(o);
                const isNew = isNewOrder(o);
                return (
                  <div 
                    key={`${o.id}-${i}`} 
                    className={`rounded-lg p-3 text-white cursor-pointer transition-all duration-200 hover:shadow-md hover:scale-[1.02] ${
                      isNew 
                        ? 'bg-gradient-to-br from-[#1f2937] to-[#2d1f3a] border-2 border-primary/60 hover:border-primary hover:shadow-primary/20' 
                        : 'bg-[#1f2937] border border-white/10 hover:bg-white/5 hover:border-primary/40'
                    }`}
                    onClick={() => onOpen(o)}
                  >
                    <div className="flex justify-between items-start mb-2">
                      <div className="flex items-center gap-2 flex-1 min-w-0">
                        <div 
                          className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0"
                          style={{ background: statusColor(o) + '22' }}
                        >
                          <span className="material-symbols-outlined text-xs" style={{ color: statusColor(o) }}>
                            {statusIcon(o)}
                          </span>
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <div className="font-semibold text-sm">#{o.id}</div>
                            {userName && (
                              <div className="text-gray-400 text-xs truncate">· {userName}</div>
                            )}
                          </div>
                          <div className="text-gray-400 text-xs">
                            {o.date ? new Date(o.date).toLocaleDateString('pl-PL', { 
                              day: '2-digit', 
                              month: 'short'
                            }) : '-'}
                          </div>
                        </div>
                      </div>
                      
                      <span 
                        className="px-2 py-0.5 rounded text-xs font-medium whitespace-nowrap flex-shrink-0" 
                        style={{ background: statusColor(o) + '22', color: statusColor(o) }}
                      >
                        {statusLabel(o)}
                      </span>
                    </div>
                    
                    <div className="flex justify-between items-center pt-2 border-t border-white/5">
                      <div className="text-gray-400 text-xs flex items-center gap-1">
                        <span className="material-symbols-outlined text-xs">shopping_cart</span>
                        {o.items_count ?? 0} szt.
                      </div>
                      <div className="text-primary font-bold text-sm">
                        {o.total != null ? `${Number(String(o.total).replace(',', '.')).toFixed(2)} zł` : '-'}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Infinite scroll trigger + loading indicator */}
            <div ref={observerTarget} className="h-16 flex items-center justify-center mt-4">
              {loading && <LoadingSpinner />}
              {!hasMore && orders.length > 0 && (
                <p className="text-gray-500 text-sm">Brak więcej zamówień</p>
              )}
            </div>
          </>
        )}
      </main>

      {/* Right drawer - Szczegóły zamówienia */}
      <div className={`fixed inset-0 z-50 ${open ? 'pointer-events-auto' : 'pointer-events-none'}`}>
        <div 
          className={`absolute inset-0 bg-black/70 backdrop-blur-sm transition-opacity duration-300 ${open ? 'opacity-100' : 'opacity-0'}`} 
          onClick={onClose} 
        />
        <div className={`absolute right-0 top-0 h-full w-full md:w-[600px] bg-[#0f172a] border-l border-gray-700/50 shadow-2xl transition-transform duration-300 ${open ? 'translate-x-0' : 'translate-x-full'} flex flex-col`}>
          <div className="flex items-center justify-between p-4 border-b border-gray-700/50 flex-shrink-0 bg-gradient-to-r from-gray-900/50 to-gray-800/50">
            <div className="flex items-center gap-3 flex-1 min-w-0">
              <div 
                className="w-10 h-10 rounded-full flex items-center justify-center"
                style={{ background: selected ? statusColor(selected) + '33' : '#6B728033' }}
              >
                <span className="material-symbols-outlined text-lg" style={{ color: selected ? statusColor(selected) : '#6B7280' }}>
                  {selected ? statusIcon(selected) : 'receipt'}
                </span>
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-white font-bold text-lg">#{selected?.id || ''}</div>
                {selected && getUserName(selected) && (
                  <div className="text-gray-400 text-sm">{getUserName(selected)}</div>
                )}
              </div>
            </div>
            <button 
              className="text-gray-400 hover:text-white transition-colors ml-2" 
              onClick={onClose}
            >
              <span className="material-symbols-outlined">close</span>
            </button>
          </div>
          
          <div className="p-4 overflow-y-auto flex-grow bg-[#0a0f1a]">
            {!selected ? null : (
              <div className="grid gap-3">
                {/* Status Change */}
                <div className="rounded-lg p-4 bg-gradient-to-br from-gray-900/50 to-gray-800/50 border border-gray-700/50">
                  <div className="text-white font-semibold mb-3 flex items-center gap-2">
                    <span className="material-symbols-outlined text-lg text-cyan-400">swap_horiz</span>
                    Status zamówienia
                  </div>
                  <select 
                    className="w-full px-3 py-2.5 rounded-lg bg-[#0f172a] border border-gray-600/50 text-white text-sm focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500/50 transition-all disabled:opacity-50"
                    value={selected.status?.id || ''}
                    onChange={(e) => handleStatusChange(Number(e.target.value))}
                    disabled={changingStatus}
                  >
                    {statuses.length === 0 ? (
                      <option>Ładowanie...</option>
                    ) : (
                      statuses.map(st => (
                        <option key={st.id} value={st.id}>
                          {st.name}
                        </option>
                      ))
                    )}
                  </select>
                  {changingStatus && (
                    <div className="mt-2 text-cyan-400 text-xs flex items-center gap-2">
                      <div className="w-3 h-3 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin"></div>
                      Zapisywanie...
                    </div>
                  )}
                </div>

                {/* Buyer Info */}
                {selected.buyer && (
                  <div className="rounded-lg p-4 bg-gradient-to-br from-gray-900/50 to-gray-800/50 border border-gray-700/50">
                    <div className="text-white font-semibold mb-3 flex items-center gap-2">
                      <span className="material-symbols-outlined text-lg text-cyan-400">person</span>
                      Kupujący
                    </div>
                    <div className="space-y-1.5 text-sm">
                      {(selected.buyer.firstname || selected.buyer.lastname) && (
                        <div className="text-gray-200">
                          {selected.buyer.firstname || ''} {selected.buyer.lastname || ''}
                        </div>
                      )}
                      {selected.buyer.email && (
                        <div className="text-gray-400 flex items-center gap-2">
                          <span className="material-symbols-outlined text-xs">email</span>
                          {selected.buyer.email}
                        </div>
                      )}
                      {selected.buyer.phone && (
                        <div className="text-gray-400 flex items-center gap-2">
                          <span className="material-symbols-outlined text-xs">phone</span>
                          {selected.buyer.phone}
                        </div>
                      )}
                      {(selected.buyer.street1 || selected.buyer.city) && (
                        <div className="text-gray-400 flex items-center gap-2 pt-1">
                          <span className="material-symbols-outlined text-xs">location_on</span>
                          <span>{[selected.buyer.street1, selected.buyer.postcode, selected.buyer.city, selected.buyer.country].filter(Boolean).join(', ')}</span>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Order Items */}
                <div className="rounded-lg p-4 bg-gradient-to-br from-gray-900/50 to-gray-800/50 border border-gray-700/50">
                  <div className="text-white font-semibold mb-3 flex items-center gap-2">
                    <span className="material-symbols-outlined text-lg text-cyan-400">shopping_bag</span>
                    Pozycje ({selected.items?.length || 0})
                  </div>
                  <div className="grid gap-2">
                    {(selected.items && selected.items.length > 0) ? (
                      selected.items.map((it: any, idx: number) => (
                        <div key={idx} className="flex items-center gap-3 p-2 rounded bg-black/30 hover:bg-black/40 transition-colors">
                          {it.image ? (
                            <img src={it.image} alt={it.name || ''} className="w-12 h-12 object-cover rounded border border-white/20" />
                          ) : (
                            <div className="w-12 h-12 rounded bg-white/5 flex items-center justify-center border border-white/10">
                              <span className="material-symbols-outlined text-gray-600 text-sm">image</span>
                            </div>
                          )}
                          <div className="flex-1 min-w-0">
                            <div className="text-white text-sm truncate">{it.name || '-'}</div>
                            {it.code && <div className="text-gray-500 text-xs">{it.code}</div>}
                          </div>
                          <div className="text-gray-400 text-sm whitespace-nowrap">×{it.quantity ?? 1}</div>
                          <div className="text-white text-sm font-medium whitespace-nowrap min-w-[70px] text-right">
                            {it.price != null ? `${Number(it.price).toFixed(2)} zł` : '-'}
                          </div>
                        </div>
                      ))
                    ) : (
                      <div className="text-gray-500 text-sm text-center py-4">Brak produktów</div>
                    )}
                  </div>
                </div>

                {/* Shipping / Furgonetka */}
                <div className="rounded-lg p-4 bg-gradient-to-br from-gray-900/50 to-gray-800/50 border border-gray-700/50">
                  <div className="text-white font-semibold mb-3 flex items-center gap-2">
                    <span className="material-symbols-outlined text-lg text-cyan-400">local_shipping</span>
                    Wysyłka (Furgonetka)
                  </div>
                  
                  <div className="flex flex-col gap-3">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-gray-400">Status:</span>
                      
                      {selected.furgonetka_status === 'ready' || selected.furgonetka_status === 'synced' ? (
                        <span className="text-green-400 flex items-center gap-1">
                          <span className="material-symbols-outlined text-sm">check_circle</span>
                          Gotowe do druku
                        </span>
                      ) : selected.furgonetka_status === 'pending_import' ? (
                        <span className="text-yellow-400 flex items-center gap-1">
                          <span className="material-symbols-outlined text-sm">hourglass_empty</span>
                          Oczekiwanie na import
                        </span>
                      ) : (
                        <span className="text-gray-500">Nie zsynchronizowano</span>
                      )}
                    </div>

                    {/* Actions */}
                    <div className="flex gap-2 mt-1">
                      {selected.shipment_id ? (
                        <button
                          onClick={() => window.open(`${apiBase}/furgonetka/shipments/${selected.shipment_id}/label`, '_blank')}
                          className="flex-1 bg-green-600/20 hover:bg-green-600/30 text-green-400 border border-green-600/50 rounded px-3 py-1.5 text-sm flex items-center justify-center gap-2 transition-colors"
                        >
                          <span className="material-symbols-outlined text-sm">print</span>
                          Etykieta
                        </button>
                      ) : (
                        <button
                          onClick={() => fetchFurgonetkaStatuses([selected])}
                          className="flex-1 bg-gray-700/50 hover:bg-gray-700 text-gray-300 border border-gray-600 rounded px-3 py-1.5 text-sm flex items-center justify-center gap-2 transition-colors"
                        >
                          <span className="material-symbols-outlined text-sm">sync</span>
                          Sprawdź status
                        </button>
                      )}
                    </div>
                    
                    {selected.package_id && (
                      <div className="text-xs text-gray-500 text-center font-mono">
                        PKG: {selected.package_id}
                      </div>
                    )}
                  </div>
                </div>

                {/* Order Metadata */}
                <div className="rounded-lg p-4 bg-gradient-to-br from-gray-900/50 to-gray-800/50 border border-gray-700/50">
                  <div className="text-white font-semibold mb-3 flex items-center gap-2">
                    <span className="material-symbols-outlined text-lg text-cyan-400">info</span>
                    Informacje
                  </div>
                  <div className="grid gap-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-gray-400">Data złożenia:</span>
                      <span className="text-gray-200">
                        {selected.date ? new Date(selected.date).toLocaleString('pl-PL') : '-'}
                      </span>
                    </div>
                    {selected.delivery_date && (
                      <div className="flex justify-between">
                        <span className="text-gray-400">Data wysyłki:</span>
                        <span className="text-gray-200">
                          {new Date(selected.delivery_date).toLocaleString('pl-PL')}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
          
          {/* Footer total */}
          <div className="p-4 border-t border-gray-700/50 bg-gradient-to-r from-gray-900/80 to-gray-800/80">
            <div className="flex items-center justify-between mb-3">
              <button
                onClick={handlePrint}
                className="flex items-center gap-2 px-4 py-2.5 text-sm font-medium text-cyan-400 bg-cyan-500/10 rounded-lg border border-cyan-500/30 hover:bg-cyan-500/20 hover:border-cyan-400 transition-all hover:shadow-lg hover:shadow-cyan-500/20"
              >
                <span className="material-symbols-outlined text-lg">print</span>
                Drukuj paragon
              </button>
              <div className="text-right">
                <div className="text-gray-400 text-xs uppercase tracking-wide mb-1">Wartość zamówienia</div>
                <div className="text-cyan-400 font-bold text-2xl">
                  {selected?.total != null ? `${Number(String(selected.total).replace(',', '.')).toFixed(2)} zł` : '-'}
                </div>
              </div>
            </div>
            
            {/* Margin calculation */}
            {(() => {
              const items = selected?.products || selected?.items || selected?.orders_products || selected?.order_products || [];
              let totalCost = 0;
              let totalRevenue = selected?.total != null ? Number(String(selected.total).replace(',', '.')) : 0;
              
              // Calculate total purchase cost from order items
              // Note: This requires purchase_price to be included in order items from backend
              // For now, we'll show a placeholder or fetch from products table
              const hasValidCost = items.some((item: any) => item.purchase_price != null);
              
              if (hasValidCost) {
                items.forEach((item: any) => {
                  const qty = Number(item?.quantity || item?.qty || item?.count || 0);
                  const purchasePrice = Number(item?.purchase_price || 0);
                  totalCost += qty * purchasePrice;
                });
                
                const margin = totalRevenue - totalCost;
                const marginPercent = totalRevenue > 0 ? (margin / totalRevenue) * 100 : 0;
                
                return (
                  <div className="grid grid-cols-3 gap-3 pt-3 border-t border-gray-700/30">
                    <div className="text-center p-2 bg-gray-800/50 rounded-lg">
                      <div className="text-gray-400 text-xs mb-1">Koszt zakupu</div>
                      <div className="text-red-400 font-semibold text-sm">
                        {totalCost.toFixed(2)} zł
                      </div>
                    </div>
                    <div className="text-center p-2 bg-gray-800/50 rounded-lg">
                      <div className="text-gray-400 text-xs mb-1">Marża</div>
                      <div className="text-green-400 font-semibold text-sm">
                        {margin.toFixed(2)} zł
                      </div>
                    </div>
                    <div className="text-center p-2 bg-gray-800/50 rounded-lg">
                      <div className="text-gray-400 text-xs mb-1">Marża %</div>
                      <div className="text-emerald-400 font-semibold text-sm">
                        {marginPercent.toFixed(1)}%
                      </div>
                    </div>
                  </div>
                );
              }
              
              return null;
            })()}
          </div>
        </div>
      </div>

      {/* Hidden receipt for printing */}
      <div className="hidden">
        {selected && <ThermalReceipt ref={receiptRef} order={selected} />}
      </div>
    </div>
  );
}
