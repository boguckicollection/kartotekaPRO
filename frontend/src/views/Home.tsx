import React, { useEffect, useMemo } from 'react'

type Props = { 
  stats: any;
  orders?: any[];
  onNav: (key: string)=>void;
  onRefresh: ()=>void;
  onOpenOrder?: (order: any)=>void;
}

const welcomeMessages = [
  "Gotowy na podbój rynku kart? Działaj, Boguś!",
  "Każda zeskanowana karta to krok do sukcesu! Naprzód, Boguś!",
  "Twoja kolekcja czeka na wycenę i sprzedaż. Pokaż im, Boguś!",
  "Nowe zamówienia same się nie zrealizują. Do dzieła, Boguś!",
  "Zróbmy dziś coś wielkiego! Czas na skanowanie, Boguś!",
  "Twoje karty to Twój skarb. Dbaj o nie i sprzedawaj z zyskiem, Boguś!",
  "Dzień dobry, Boguś! Czas na kolejne rekordy sprzedaży!",
  "Wyceniaj, skanuj, sprzedawaj! Jesteś najlepszy, Boguś!",
];

// Stat card configuration with colors
const statConfig: Record<string, { icon: string; color: string; glowColor: string }> = {
  total_scans: { icon: 'qr_code_scanner', color: 'from-cyan-500/20 to-blue-600/20', glowColor: 'cyan-500' },
  scans_ready: { icon: 'publish', color: 'from-amber-500/20 to-orange-600/20', glowColor: 'amber-500' },
  scans_published: { icon: 'cloud_done', color: 'from-green-500/20 to-emerald-600/20', glowColor: 'green-500' },
  total_products: { icon: 'inventory_2', color: 'from-purple-500/20 to-pink-600/20', glowColor: 'purple-500' },
  sold_value: { icon: 'account_balance_wallet', color: 'from-emerald-500/20 to-teal-600/20', glowColor: 'emerald-500' },
  sold_count: { icon: 'shopping_cart', color: 'from-blue-500/20 to-indigo-600/20', glowColor: 'blue-500' },
  users: { icon: 'group', color: 'from-rose-500/20 to-pink-600/20', glowColor: 'rose-500' },
  total_inventory_value: { icon: 'savings', color: 'from-emerald-500/20 to-green-600/20', glowColor: 'emerald-500' },
  total_inventory_cost: { icon: 'payments', color: 'from-red-500/20 to-orange-600/20', glowColor: 'red-500' },
  potential_profit: { icon: 'trending_up', color: 'from-green-400/20 to-emerald-500/20', glowColor: 'green-400' },
};

export default function Home({ stats, orders, onNav, onRefresh, onOpenOrder }: Props){
  const welcomeMessage = useMemo(() => {
    const randomIndex = Math.floor(Math.random() * welcomeMessages.length);
    return welcomeMessages[randomIndex];
  }, []);

  useEffect(()=>{
    document.documentElement.classList.add('dark')
    return ()=>{ /* keep dark */ }
  }, [])

  const statItems = useMemo(() => [
    { key: 'total_scans', label: 'Skanów łącznie', value: stats?.total_scans },
    { key: 'scans_ready', label: 'Gotowe do publikacji', value: stats?.scans_ready },
    { key: 'scans_published', label: 'Opublikowane', value: stats?.scans_published },
    { key: 'total_inventory_value', label: 'Wartość zapasów', value: stats?.total_inventory_value != null ? stats.total_inventory_value.toLocaleString('pl-PL', {style: 'currency', currency: 'PLN', minimumFractionDigits: 2}) : '-' },
    { key: 'total_inventory_cost', label: 'Koszt zakupu', value: stats?.total_inventory_cost != null ? stats.total_inventory_cost.toLocaleString('pl-PL', {style: 'currency', currency: 'PLN', minimumFractionDigits: 2}) : '-' },
    { key: 'potential_profit', label: 'Potencjalny zysk', value: stats?.potential_profit != null ? stats.potential_profit.toLocaleString('pl-PL', {style: 'currency', currency: 'PLN', minimumFractionDigits: 2}) : '-' },
    { key: 'sold_value', label: 'Sprzedane (wartość)', value: stats?.sold_value_pln != null ? stats.sold_value_pln.toLocaleString('pl-PL', {style: 'currency', currency: 'PLN', minimumFractionDigits: 2}) : '-', nav: 'reports' },
    { key: 'sold_count', label: 'Sprzedane (sztuki)', value: stats?.sold_count, nav: 'reports' },
  ], [stats]);

  // Calculate alerts
  const lowStockCount = useMemo(() => {
    // This will need to come from API - for now we'll add it when we have the data
    return 0; // Placeholder
  }, []);

  const needsPriceUpdate = useMemo(() => {
    // This will need to come from API - for now we'll add it when we have the data
    return 0; // Placeholder
  }, []);

  return (
    <div className="max-w-7xl mx-auto font-display pb-24">
      {/* Header */}
      <header className="mb-8">
        <div className="flex items-center gap-4 mb-2">
          <div className="w-12 h-12 flex items-center justify-center bg-gradient-to-br from-cyan-500/20 to-blue-600/20 rounded-full border border-cyan-500/30">
            <span className="material-symbols-outlined text-2xl text-cyan-400">waving_hand</span>
          </div>
          <div>
            <h1 className="text-white text-2xl font-bold">Witaj, Boguś!</h1>
            <p className="text-gray-400 text-sm">{welcomeMessage}</p>
          </div>
        </div>
      </header>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 md:gap-4">
        {statItems.map(item => {
          const config = statConfig[item.key] || statConfig.total_scans;
          return (
            <div 
              key={item.key} 
              className={`relative group ${item.nav ? 'cursor-pointer' : ''}`}
              onClick={() => item.nav && onNav(item.nav)}
            >
              {/* Glow effect on hover */}
              {item.nav && (
                <div className={`absolute -inset-0.5 bg-gradient-to-r ${config.color} rounded-xl blur opacity-0 group-hover:opacity-75 transition duration-300`}></div>
              )}
              
              <div className={`relative h-24 flex items-center rounded-xl p-4 bg-[#0f172a] border border-gray-700/50 transition-all duration-300 ${item.nav ? 'hover:border-gray-600 group-hover:shadow-lg' : ''}`}>
                {/* Icon */}
                <div className={`flex-shrink-0 w-12 h-12 flex items-center justify-center bg-gradient-to-br ${config.color} rounded-lg border border-gray-700/50 mr-4`}>
                  <span className="material-symbols-outlined text-2xl text-white/80">{config.icon}</span>
                </div>
                
                <div className="flex-grow">
                  {/* Label */}
                  <p className="text-xs text-gray-400 leading-tight">{item.label}</p>
                  {/* Value */}
                  <p className="text-xl font-bold text-white">{item.value ?? '-'}</p>
                </div>
                
                {/* Click indicator */}
                {item.nav && (
                  <span className="absolute top-2 right-2 material-symbols-outlined text-xs text-gray-600 group-hover:text-cyan-400 transition-colors">open_in_new</span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Alerts & Notifications */}
      {(lowStockCount > 0 || needsPriceUpdate > 0 || (stats?.scans_ready && stats.scans_ready > 0)) && (
        <div className="mt-8">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2 mb-4">
            <span className="material-symbols-outlined text-amber-400">notifications</span>
            Powiadomienia
          </h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {/* Niski stan magazynu */}
            {lowStockCount > 0 && (
              <div 
                className="group relative cursor-pointer"
                onClick={() => onNav('inventory')}
              >
                <div className="absolute -inset-0.5 bg-gradient-to-r from-amber-500/20 to-orange-600/20 rounded-xl blur opacity-75 group-hover:opacity-100 transition duration-300"></div>
                <div className="relative p-4 bg-[#0f172a] border border-amber-500/30 rounded-xl hover:border-amber-500/50 transition-all">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 flex items-center justify-center bg-amber-500/20 rounded-lg">
                      <span className="material-symbols-outlined text-2xl text-amber-400">inventory</span>
                    </div>
                    <div className="flex-1">
                      <p className="text-white font-medium">Niski stan magazynu</p>
                      <p className="text-gray-400 text-sm">{lowStockCount} produktów &lt; 100 sztuk</p>
                    </div>
                  </div>
                </div>
              </div>
            )}
            
            {/* Gotowe do publikacji */}
            {stats?.scans_ready && stats.scans_ready > 0 && (
              <div 
                className="group relative cursor-pointer"
                onClick={() => onNav('scan')}
              >
                <div className="absolute -inset-0.5 bg-gradient-to-r from-cyan-500/20 to-blue-600/20 rounded-xl blur opacity-75 group-hover:opacity-100 transition duration-300"></div>
                <div className="relative p-4 bg-[#0f172a] border border-cyan-500/30 rounded-xl hover:border-cyan-500/50 transition-all">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 flex items-center justify-center bg-cyan-500/20 rounded-lg">
                      <span className="material-symbols-outlined text-2xl text-cyan-400">pending_actions</span>
                    </div>
                    <div className="flex-1">
                      <p className="text-white font-medium">Gotowe do publikacji</p>
                      <p className="text-gray-400 text-sm">{stats.scans_ready} skanów czeka</p>
                    </div>
                  </div>
                </div>
              </div>
            )}
            
            {/* Aktualizacja cen */}
            {needsPriceUpdate > 0 && (
              <div 
                className="group relative cursor-pointer"
                onClick={() => onNav('pricing')}
              >
                <div className="absolute -inset-0.5 bg-gradient-to-r from-purple-500/20 to-pink-600/20 rounded-xl blur opacity-75 group-hover:opacity-100 transition duration-300"></div>
                <div className="relative p-4 bg-[#0f172a] border border-purple-500/30 rounded-xl hover:border-purple-500/50 transition-all">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 flex items-center justify-center bg-purple-500/20 rounded-lg">
                      <span className="material-symbols-outlined text-2xl text-purple-400">update</span>
                    </div>
                    <div className="flex-1">
                      <p className="text-white font-medium">Aktualizacja cen</p>
                      <p className="text-gray-400 text-sm">{needsPriceUpdate} produktów wymaga aktualizacji</p>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Recent Scans */}
      {stats?.recent_scans?.length ? (
        <div className="mt-8">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
              <span className="material-symbols-outlined text-green-400">cloud_done</span>
              Ostatnio opublikowane
            </h2>
            <button 
              onClick={onRefresh}
              className="flex items-center gap-1 text-xs text-gray-400 hover:text-cyan-400 transition-colors"
            >
              <span className="material-symbols-outlined text-sm">refresh</span>
              Odśwież
            </button>
          </div>
          
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
            {stats.recent_scans.map((r:any)=> (
              <div 
                key={r.id} 
                className="relative group"
              >
                <div className="absolute -inset-0.5 bg-gradient-to-r from-cyan-500/20 to-blue-500/20 rounded-xl blur opacity-0 group-hover:opacity-75 transition duration-300"></div>
                
                <div className="relative flex gap-3 p-3 bg-[#0f172a] border border-gray-700/50 rounded-xl hover:border-gray-600 transition-all">
                  {/* Thumbnail */}
                  <div className="flex-shrink-0 w-16 h-22 rounded-lg overflow-hidden bg-gray-800 border border-gray-700/50">
                    {r.image ? (
                      <img 
                        src={r.image} 
                        alt={r.name || 'Skan'} 
                        className="w-full h-full object-cover"
                        onError={(e) => {
                          (e.target as HTMLImageElement).style.display = 'none';
                          (e.target as HTMLImageElement).nextElementSibling?.classList.remove('hidden');
                        }}
                      />
                    ) : null}
                    <div className={`w-full h-full flex items-center justify-center ${r.image ? 'hidden' : ''}`}>
                      <span className="material-symbols-outlined text-2xl text-gray-600">image</span>
                    </div>
                  </div>
                  
                  {/* Info */}
                  <div className="flex-1 min-w-0">
                    <p className="text-white font-medium text-sm truncate">{r.name || 'Nieznana karta'}</p>
                    <p className="text-gray-400 text-xs truncate">{r.set || '-'}</p>
                    {r.number && <p className="text-gray-500 text-xs">#{r.number}</p>}
                    
                    <div className="flex items-center gap-2 mt-1.5">
                      {r.price_pln_final ? (
                        <span className="text-xs font-medium text-green-400">{r.price_pln_final.toFixed(2)} zł</span>
                      ) : (
                        <span className="text-xs text-gray-500">Brak ceny</span>
                      )}
                      
                      {r.permalink ? (
                        <a 
                          href={r.permalink} 
                          target="_blank" 
                          rel="noopener noreferrer"
                          className="flex items-center gap-0.5 text-xs text-cyan-400 hover:text-cyan-300 transition-colors"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <span className="material-symbols-outlined text-xs">storefront</span>
                        </a>
                      ) : (
                        <span className="material-symbols-outlined text-xs text-green-400">cloud_done</span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      ): (
        <div className="mt-8 p-8 bg-[#0f172a] border border-gray-700/50 rounded-xl text-center">
          <span className="material-symbols-outlined text-4xl text-gray-600 mb-2">cloud_upload</span>
          <p className="text-gray-400">Brak opublikowanych kart</p>
          <p className="text-gray-500 text-sm mt-1">Opublikuj karty, aby zobaczyć je tutaj</p>
        </div>
      )}

      {/* Recent Orders - Last 5 */}
      {orders && orders.length > 0 && (
        <div className="mt-8">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
              <span className="material-symbols-outlined text-blue-400">receipt_long</span>
              Ostatnie zamówienia
            </h2>
            <button 
              onClick={() => onNav('orders')}
              className="text-sm text-cyan-400 hover:text-cyan-300 transition-colors flex items-center gap-1"
            >
              Zobacz wszystkie
              <span className="material-symbols-outlined text-sm">arrow_forward</span>
            </button>
          </div>
          
          <div className="grid gap-3 grid-cols-2 sm:grid-cols-3 lg:grid-cols-5">
            {[...orders].sort((a:any, b:any) => Number(b.id) - Number(a.id)).slice(0, 5).map((order: any) => {
              const statusId = order?.status?.id;
              const userName = order?.user?.firstname && order?.user?.lastname 
                ? `${order.user.firstname} ${order.user.lastname}`
                : order?.user?.email?.split('@')[0] || 'Gość';
              
              // Status configuration
              let statusColor = '#6B7280';
              let statusIcon = 'label';
              let statusBg = 'bg-gray-700/50';
              
              if (statusId === '1' || statusId === 1) {
                statusColor = '#3B82F6';
                statusIcon = 'new_releases';
                statusBg = 'bg-blue-500/20';
              } else if (statusId === '2' || statusId === 2) {
                statusColor = '#F59E0B';
                statusIcon = 'hourglass_empty';
                statusBg = 'bg-amber-500/20';
              } else if (statusId === '7' || statusId === 7) {
                statusColor = '#10B981';
                statusIcon = 'local_shipping';
                statusBg = 'bg-green-500/20';
              }
              
              return (
                <div
                  key={order.id}
                  onClick={() => onOpenOrder && onOpenOrder(order)}
                  className="group relative cursor-pointer rounded-xl p-4 bg-[#0f172a] border border-gray-700/50 hover:border-gray-600 transition-all duration-200 hover:scale-[1.02] aspect-square flex flex-col justify-between shadow-lg hover:shadow-xl"
                >
                  {/* Top: Status Icon & ID */}
                  <div className="flex justify-between items-start">
                     <div 
                        className={`w-10 h-10 flex items-center justify-center rounded-xl ${statusBg}`}
                      >
                        <span className="material-symbols-outlined text-xl" style={{ color: statusColor }}>
                          {statusIcon}
                        </span>
                      </div>
                      <span className="text-white font-bold text-lg">#{order.id}</span>
                  </div>

                  {/* Middle: Buyer */}
                  <div className="text-left mt-2">
                      <p className="text-gray-500 text-[10px] uppercase tracking-wider">Kupujący</p>
                      <p className="text-white font-medium truncate text-sm">{userName}</p>
                  </div>

                  {/* Bottom: Stats */}
                  <div className="flex justify-between items-end border-t border-gray-700/50 pt-3 mt-auto">
                    <div className="text-left">
                        <p className="text-gray-500 text-[10px]">Sztuk</p>
                        <p className="text-white font-bold">{order.items_count || 0}</p>
                    </div>
                    <div className="text-right">
                        <p className="text-gray-500 text-[10px]">Kwota</p>
                        <p className="text-cyan-400 font-bold">{order.total ? `${Number(String(order.total).replace(',', '.')).toFixed(2)} zł` : '-'}</p>
                    </div>
                  </div>
                  
                  {/* Hover indicator */}
                  <div className="absolute inset-0 rounded-xl border-2 border-cyan-500/0 group-hover:border-cyan-500/50 transition-all pointer-events-none"></div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* New Orders Panel */}
      {orders && orders.length > 0 && (() => {
        const newOrders = orders.filter((o) => {
          const statusId = o?.status?.id;
          return statusId === '1' || statusId === 1 || statusId === '2' || statusId === 2;
        });
        
        if (newOrders.length === 0) return null;
        
        return (
          <section className="mt-8">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                <span className="material-symbols-outlined text-purple-400">notification_important</span>
                Nowe zamówienia
                <span className="text-sm font-normal text-gray-400">
                  ({newOrders.length})
                </span>
              </h2>
              <button 
                onClick={() => onNav('orders')}
                className="text-sm text-cyan-400 hover:text-cyan-300 transition-colors flex items-center gap-1"
              >
                Zobacz wszystkie
                <span className="material-symbols-outlined text-sm">arrow_forward</span>
              </button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {newOrders.slice(0, 6).map((order: any) => {
              const statusId = order?.status?.id;
              const isNew = statusId === '1' || statusId === 1 || statusId === '2' || statusId === 2;
              const statusName = order?.status?.name || 'Nieznany status';
              const userName = order?.user?.firstname && order?.user?.lastname 
                ? `${order.user.firstname} ${order.user.lastname}`
                : order?.user?.email?.split('@')[0] || 'Gość';
              
              let statusColor = '#6B7280';
              let statusIcon = 'label';
              
              if (statusId === '1' || statusId === 1) {
                statusColor = '#3498DB';
                statusIcon = 'new_releases';
              } else if (statusId === '2' || statusId === 2) {
                statusColor = '#9B59B6';
                statusIcon = 'notification_important';
              } else if (statusId === '7' || statusId === 7) {
                statusColor = '#2ECC71';
                statusIcon = 'local_shipping';
              }
              
              return (
                <div
                  key={order.id}
                  onClick={() => onOpenOrder && onOpenOrder(order)}
                  className={`group relative cursor-pointer rounded-lg p-4 transition-all duration-200 hover:scale-[1.02] ${
                    isNew
                      ? 'bg-gradient-to-br from-[#1f2937] to-[#2d1f3a] border-2 border-purple-500/60 hover:border-purple-400 hover:shadow-lg hover:shadow-purple-500/20'
                      : 'bg-[#0f172a] border border-gray-700/50 hover:border-gray-600'
                  }`}
                >
                  {isNew && (
                    <div className="absolute -top-2 -right-2 w-6 h-6 bg-purple-500 rounded-full flex items-center justify-center animate-pulse">
                      <span className="material-symbols-outlined text-white text-xs">priority_high</span>
                    </div>
                  )}
                  
                  <div className="flex items-start gap-3 mb-3">
                    <div 
                      className="w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0"
                      style={{ background: statusColor + '33' }}
                    >
                      <span className="material-symbols-outlined text-sm" style={{ color: statusColor }}>
                        {statusIcon}
                      </span>
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-white font-semibold text-sm">#{order.id}</span>
                        <span className="text-gray-400 text-xs">·</span>
                        <span className="text-gray-400 text-xs truncate">{userName}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span 
                          className="px-2 py-0.5 rounded text-xs font-medium"
                          style={{ background: statusColor + '22', color: statusColor }}
                        >
                          {statusName}
                        </span>
                      </div>
                    </div>
                  </div>
                  
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-400 flex items-center gap-1">
                      <span className="material-symbols-outlined text-xs">shopping_cart</span>
                      {order.items_count || 0} szt.
                    </span>
                    <span className="text-cyan-400 font-bold">
                      {order.total ? `${Number(String(order.total).replace(',', '.')).toFixed(2)} zł` : '-'}
                    </span>
                  </div>
                  
                  <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
                    <span className="material-symbols-outlined text-xs text-gray-400">open_in_new</span>
                  </div>
                </div>
              );
              })}
            </div>
          </section>
        );
      })()}
    </div>
  )
}
