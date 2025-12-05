import React, { useState, useEffect } from 'react'

type DashboardStats = {
  total_users: number
  total_collections: number
  online_users: number
  shop_clicks: number
  total_cards: number
  total_products: number
  average_card_price: number
  last_sync: string | null
  system_status: 'healthy' | 'warning' | 'error'
  most_popular_card: {
    name: string
    set_code: string
    number: string
    count: number
  } | null
  most_valuable_card: {
    name: string
    set_code: string
    number: string
    price: number
    image: string
  } | null
  top_cards: Array<{
    name: string
    set_code: string
    number: string
    price: number
    image: string
    count: number
  }> | null
}

type Props = {
  apiBase: string
}

export default function AppDashboard({ apiBase }: Props) {
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // URL for the Mobile App Backend
  // Dynamically determine host based on current window location
  const hostname = window.location.hostname;
  const APP_API_URL = `http://${hostname}:8001`;

  const resolveImageUrl = (path: string) => {
    if (!path) return '';
    if (path.startsWith('http')) return path;
    return `${APP_API_URL}${path}`;
  }

  useEffect(() => {
    loadStats()
  }, [])

  const loadStats = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${APP_API_URL}/users/stats/dashboard`)
      if (!res.ok) throw new Error('Failed to fetch app stats')
      const data = await res.json()
      setStats(data)
    } catch (err: any) {
      console.error(err)
      setError("Nie udało się połączyć z aplikacją mobilną (port 8001). Sprawdź czy serwer działa.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="font-display p-4 md:p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-3 text-white">
          <span className="material-symbols-outlined text-amber-400 text-3xl">collections_bookmark</span>
          <div>
            <h2 className="text-2xl font-bold">Collector App</h2>
            <p className="text-gray-400 text-sm">Zarządzanie kolekcją Pokemon TCG</p>
          </div>
        </div>
        <button 
          onClick={loadStats}
          className="p-2 hover:bg-white/5 rounded-lg text-gray-400 hover:text-white transition-colors"
        >
          <span className="material-symbols-outlined">refresh</span>
        </button>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/20 text-red-400 px-4 py-3 rounded-xl mb-6">
          {error}
        </div>
      )}

       {loading && !stats ? (
        <div className="text-center py-12 text-gray-500">Ładowanie danych z aplikacji...</div>
       ) : stats ? (
         <div className="space-y-6">
           {/* Top Stats Row */}
           <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
             <StatCard 
               icon="group" 
               label="Użytkownicy" 
               value={stats.total_users} 
               color="blue" 
             />
             <StatCard 
               icon="collections_bookmark" 
               label="Kolekcje" 
               value={stats.total_collections} 
               color="purple" 
             />
             <StatCard 
               icon="shopping_bag" 
               label="Karty w bazie" 
               value={stats.total_cards} 
               color="emerald" 
             />
             <StatCard 
               icon="inventory_2" 
               label="Produkty" 
               value={stats.total_products} 
               color="amber" 
             />
           </div>

           {/* Second Row - Additional Metrics */}
           <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
             <StatCard 
               icon="attach_money" 
               label="Średnia Cena" 
               value={`${stats.average_card_price.toFixed(2)} PLN`}
               color="cyan"
               numeric={false}
             />
             <StatCard 
               icon="sync" 
               label="Ostatnia Sync" 
               value={stats.last_sync ? new Date(stats.last_sync).toLocaleTimeString('pl-PL').split(':').slice(0,2).join(':') : 'N/A'}
               color="indigo"
               numeric={false}
             />
             <StatCard 
               icon="favorite" 
               label="Popularne" 
               value={stats.most_popular_card?.count || 0}
               color="pink"
             />
             <StatCard 
               icon="diamond" 
               label="Status" 
               value={stats.system_status === 'healthy' ? '✓ OK' : stats.system_status === 'warning' ? '⚠ Warning' : '✗ Error'}
               color={stats.system_status === 'healthy' ? 'emerald' : stats.system_status === 'warning' ? 'amber' : 'red'}
               numeric={false}
             />
           </div>

           <div className="grid md:grid-cols-2 gap-6">
             {/* Most Popular Card */}
             <div className="bg-[#1e293b] rounded-2xl p-6 border border-gray-800/50 hover:border-pink-500/30 transition-colors">
               <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                 <span className="material-symbols-outlined text-pink-400">favorite</span>
                 Najczęściej Dodawana
               </h3>
               {stats.most_popular_card ? (
                 <div className="flex gap-4 items-center">
                   <div className="bg-gray-800 h-24 w-16 rounded flex items-center justify-center text-gray-600">
                     IMG
                   </div>
                   <div>
                     <div className="text-xl font-bold text-white">{stats.most_popular_card.name}</div>
                     <div className="text-gray-400 text-sm">
                       {stats.most_popular_card.set_code} #{stats.most_popular_card.number}
                     </div>
                     <div className="mt-2 inline-block bg-pink-500/20 text-pink-300 px-2 py-1 rounded text-xs font-bold">
                       🔥 {stats.most_popular_card.count} razy
                     </div>
                   </div>
                 </div>
               ) : (
                 <div className="text-gray-500">Brak danych</div>
               )}
             </div>

             {/* Most Valuable Card */}
             <div className="bg-[#1e293b] rounded-2xl p-6 border border-gray-800/50 hover:border-emerald-500/30 transition-colors">
               <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                 <span className="material-symbols-outlined text-emerald-400">diamond</span>
                 Najdroższa Karta
               </h3>
               {stats.most_valuable_card ? (
                 <div className="flex gap-4 items-center">
                   {stats.most_valuable_card.image ? (
                     <img 
                       src={resolveImageUrl(stats.most_valuable_card.image)} 
                       alt={stats.most_valuable_card.name}
                       className="h-24 w-auto rounded object-contain"
                     />
                   ) : (
                     <div className="bg-gray-800 h-24 w-16 rounded flex items-center justify-center text-gray-600">
                       IMG
                     </div>
                   )}
                   <div>
                     <div className="text-xl font-bold text-white">{stats.most_valuable_card.name}</div>
                     <div className="text-gray-400 text-sm">
                       {stats.most_valuable_card.set_code} #{stats.most_valuable_card.number}
                     </div>
                     <div className="mt-2 text-2xl font-mono text-emerald-400 font-bold">
                       💰 {stats.most_valuable_card.price} PLN
                     </div>
                   </div>
                 </div>
               ) : (
                 <div className="text-gray-500">Brak danych</div>
               )}
             </div>
           </div>

           {/* Top 5 Cards Table */}
           {stats.top_cards && stats.top_cards.length > 0 && (
             <div className="bg-[#1e293b] rounded-2xl p-6 border border-gray-800/50">
               <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                 <span className="material-symbols-outlined text-blue-400">trending_up</span>
                 Top 5 Karty
               </h3>
               <div className="overflow-x-auto">
                 <table className="w-full text-sm">
                   <thead>
                     <tr className="border-b border-gray-700">
                       <th className="text-left py-2 px-3 text-gray-400">Karta</th>
                       <th className="text-right py-2 px-3 text-gray-400">Cena</th>
                       <th className="text-right py-2 px-3 text-gray-400">Dodań</th>
                     </tr>
                   </thead>
                   <tbody>
                     {stats.top_cards.map((card, idx) => (
                       <tr key={idx} className="border-b border-gray-800 hover:bg-gray-800/30 transition-colors">
                         <td className="py-3 px-3">
                           <div className="font-bold text-white">{card.name}</div>
                           <div className="text-xs text-gray-400">{card.set_code} #{card.number}</div>
                         </td>
                         <td className="py-3 px-3 text-right text-emerald-400 font-bold">{card.price} PLN</td>
                         <td className="py-3 px-3 text-right text-pink-400 font-bold">{card.count}</td>
                       </tr>
                     ))}
                   </tbody>
                 </table>
               </div>
             </div>
           )}
        </div>
      ) : null}
    </div>
  )
}

function StatCard({ icon, label, value, color, subtext, numeric = true }: any) {
  const colors: any = {
    blue: 'text-blue-400 bg-blue-500/10 border-blue-500/20',
    emerald: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
    purple: 'text-purple-400 bg-purple-500/10 border-purple-500/20',
    amber: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
    cyan: 'text-cyan-400 bg-cyan-500/10 border-cyan-500/20',
    indigo: 'text-indigo-400 bg-indigo-500/10 border-indigo-500/20',
    pink: 'text-pink-400 bg-pink-500/10 border-pink-500/20',
    red: 'text-red-400 bg-red-500/10 border-red-500/20',
  }
  
  const colorMap: any = {
    blue: 'text-blue-400',
    emerald: 'text-emerald-400',
    purple: 'text-purple-400',
    amber: 'text-amber-400',
    cyan: 'text-cyan-400',
    indigo: 'text-indigo-400',
    pink: 'text-pink-400',
    red: 'text-red-400',
  }
  
  return (
    <div className={`rounded-xl p-4 border ${colors[color] || colors.blue} hover:scale-105 transition-transform cursor-pointer`}>
      <div className="flex items-start justify-between mb-2">
        <span className={`material-symbols-outlined text-2xl ${colorMap[color] || colorMap.blue}`}>
          {icon}
        </span>
      </div>
      <div className={`${numeric ? 'text-3xl' : 'text-lg'} font-bold text-white mb-1`}>{value}</div>
      <div className="text-xs text-gray-400">{label}</div>
      {subtext && <div className="text-[10px] text-gray-500 mt-1">{subtext}</div>}
    </div>
  )
}
