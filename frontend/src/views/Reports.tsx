import React, { useEffect, useMemo, useState } from 'react'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js'
import { Line, Doughnut } from 'react-chartjs-2'

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler
)

type SeriesPoint = { date: string; count: number }
type CategoryItem = { id: number | null; name: string | null; count: number }
type ProductRow = { id: number; code?: string | null; name?: string | null; stock?: number | null; price?: number | null; permalink?: string | null; image?: string | null }

type ReportsData = {
  metrics: {
    total_products: number
    inventory_units: number
    inventory_value_pln: number
    total_scans: number
    scans_ready: number
    scans_published: number
    sold_value_pln?: number
    sold_count?: number
    users_count?: number
  }
  products_per_day: SeriesPoint[]
  scans_per_day: SeriesPoint[]
  top_categories: CategoryItem[]
  low_stock: ProductRow[]
  top_value: Array<ProductRow & { value: number }>
}

type TopCustomer = {
  email: string
  name: string
  orders_count: number
  total_spent: number
}

// Stat card configuration with colors
const statConfig: Record<string, { icon: string; color: string; gradient: string }> = {
  total_products: { icon: 'inventory_2', color: 'text-purple-400', gradient: 'from-purple-500/20 to-pink-600/20' },
  inventory_units: { icon: 'warehouse', color: 'text-blue-400', gradient: 'from-blue-500/20 to-indigo-600/20' },
  inventory_value: { icon: 'payments', color: 'text-emerald-400', gradient: 'from-emerald-500/20 to-teal-600/20' },
  sold_value: { icon: 'account_balance_wallet', color: 'text-green-400', gradient: 'from-green-500/20 to-emerald-600/20' },
  sold_count: { icon: 'shopping_cart', color: 'text-amber-400', gradient: 'from-amber-500/20 to-orange-600/20' },
  users_count: { icon: 'group', color: 'text-rose-400', gradient: 'from-rose-500/20 to-pink-600/20' },
  total_scans: { icon: 'qr_code_scanner', color: 'text-cyan-400', gradient: 'from-cyan-500/20 to-blue-600/20' },
  scans_ready: { icon: 'pending_actions', color: 'text-yellow-400', gradient: 'from-yellow-500/20 to-amber-600/20' },
  scans_published: { icon: 'cloud_done', color: 'text-green-400', gradient: 'from-green-500/20 to-emerald-600/20' },
}

// Chart colors
const chartColors = {
  cyan: { line: '#22d3ee', fill: 'rgba(34, 211, 238, 0.1)', border: 'rgba(34, 211, 238, 0.3)' },
  green: { line: '#22c55e', fill: 'rgba(34, 197, 94, 0.1)', border: 'rgba(34, 197, 94, 0.3)' },
  purple: { line: '#a855f7', fill: 'rgba(168, 85, 247, 0.1)', border: 'rgba(168, 85, 247, 0.3)' },
  doughnut: [
    'rgba(34, 211, 238, 0.8)',   // cyan
    'rgba(168, 85, 247, 0.8)',   // purple
    'rgba(34, 197, 94, 0.8)',    // green
    'rgba(251, 191, 36, 0.8)',   // amber
    'rgba(244, 63, 94, 0.8)',    // rose
    'rgba(59, 130, 246, 0.8)',   // blue
    'rgba(236, 72, 153, 0.8)',   // pink
    'rgba(20, 184, 166, 0.8)',   // teal
  ],
}

const Num = ({ v, suffix = '' }: { v: number; suffix?: string }) => (
  <span>{v.toLocaleString('pl-PL')}{suffix}</span>
)

export default function Reports() {
  const [data, setData] = useState<ReportsData | null>(null)
  const [loading, setLoading] = useState(false)
  const [panel, setPanel] = useState<'users' | 'sold' | 'customers' | null>(null)
  const [users, setUsers] = useState<any[] | null>(null)
  const [topCustomers, setTopCustomers] = useState<TopCustomer[]>([])
  const [soldAggregated, setSoldAggregated] = useState<Array<{ key: string; name: string; code?: string | null; qty: number; total?: number | null; image?: string | null }>>([])
  const [timeRange, setTimeRange] = useState<7 | 30 | 90>(30)
  const [showProfit, setShowProfit] = useState<boolean>(false) // false = revenue, true = profit

  const apiBase = useMemo(() => {
    const env = (import.meta as any).env?.VITE_API_BASE_URL as string | undefined
    if (env) return env
    try {
      const loc = window.location
      if (loc.protocol === 'https:') return '/api'
      const url = new URL(loc.href)
      const port = url.port === '5173' ? '8000' : url.port
      return `${url.protocol}//${url.hostname}:${port || '8000'}`
    } catch {
      return 'http://localhost:8000'
    }
  }, [])

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      try {
        const res = await fetch(`${apiBase}/reports?range_days=${timeRange}`)
        const d = await res.json()
        setData(d)
      } catch {
        // noop
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [apiBase, timeRange])

  // Support deep-linking from Home
  useEffect(() => {
    const toOpen = (window as any).__OPEN_REPORTS_PANEL as 'users' | 'sold' | undefined
    if (toOpen === 'users') { setPanel('users'); loadUsers() }
    if (toOpen === 'sold') { setPanel('sold'); loadSold() }
    try { delete (window as any).__OPEN_REPORTS_PANEL } catch {}
  }, [])

  const loadUsers = async () => {
    try {
      const r = await fetch(`${apiBase}/users`)
      const d = await r.json()
      setUsers(Array.isArray(d) ? d : [])
    } catch {}
  }

  const loadSold = async () => {
    try {
      const r = await fetch(`${apiBase}/orders?detailed=1`)
      const orders = await r.json()
      const acc = new Map<string, { key: string; name: string; code?: string | null; qty: number; total?: number | null; image?: string | null }>()
      const customerAcc = new Map<string, TopCustomer>()

      if (Array.isArray(orders)) {
        for (const o of orders) {
          // Aggregate items
          const items = Array.isArray(o.items) ? o.items : []
          for (const it of items) {
            const name = it?.name || '-'
            const code = it?.code || null
            const qty = Number(it?.quantity || 0)
            const price = it?.price != null ? Number(it.price) : null
            const key = (code || name) as string
            const prev: any = acc.get(key) || { key, name, code, qty: 0, total: 0, image: it?.image || null }
            prev.qty += isNaN(qty) ? 0 : qty
            if (price != null) prev.total = (prev.total || 0) + (isNaN(qty) ? 0 : qty) * price
            if (!prev.image && it?.image) prev.image = it.image
            acc.set(key, prev)
          }

          // Aggregate customers
          const buyer = o.buyer || {}
          const email = buyer.email || o.email || ''
          if (email) {
            const customerName = [buyer.firstname, buyer.lastname].filter(Boolean).join(' ') || email.split('@')[0]
            const orderTotal = Number(String(o.total || 0).replace(',', '.')) || 0
            const prev = customerAcc.get(email) || { email, name: customerName, orders_count: 0, total_spent: 0 }
            prev.orders_count += 1
            prev.total_spent += orderTotal
            customerAcc.set(email, prev)
          }
        }
      }

      const list = Array.from(acc.values()).sort((a, b) => (b.total || 0) - (a.total || 0))
      setSoldAggregated(list)

      const customers = Array.from(customerAcc.values()).sort((a, b) => b.total_spent - a.total_spent)
      setTopCustomers(customers)
    } catch {}
  }

  // Chart data for products per day
  const productsChartData = useMemo(() => {
    const points = data?.products_per_day || []
    return {
      labels: points.map(p => {
        const d = new Date(p.date)
        return `${d.getDate()}.${d.getMonth() + 1}`
      }),
      datasets: [{
        label: 'Produkty',
        data: points.map(p => p.count),
        borderColor: chartColors.cyan.line,
        backgroundColor: chartColors.cyan.fill,
        fill: true,
        tension: 0.4,
        pointRadius: 0,
        pointHoverRadius: 4,
      }],
    }
  }, [data?.products_per_day])

  // Chart data for scans per day
  const scansChartData = useMemo(() => {
    const points = data?.scans_per_day || []
    return {
      labels: points.map(p => {
        const d = new Date(p.date)
        return `${d.getDate()}.${d.getMonth() + 1}`
      }),
      datasets: [{
        label: 'Skany',
        data: points.map(p => p.count),
        borderColor: chartColors.green.line,
        backgroundColor: chartColors.green.fill,
        fill: true,
        tension: 0.4,
        pointRadius: 0,
        pointHoverRadius: 4,
      }],
    }
  }, [data?.scans_per_day])

  // Chart data for top categories (Doughnut)
  const categoriesChartData = useMemo(() => {
    const categories = data?.top_categories?.slice(0, 8) || []
    return {
      labels: categories.map(c => c.name || `Kategoria #${c.id}` || 'Inne'),
      datasets: [{
        data: categories.map(c => c.count),
        backgroundColor: chartColors.doughnut,
        borderColor: 'rgba(15, 23, 42, 1)',
        borderWidth: 2,
      }],
    }
  }, [data?.top_categories])

  // Chart data for sales over time (multi-axis: revenue/profit + quantity)
  const salesChartData = useMemo(() => {
    const points = data?.sales_per_day || []
    return {
      labels: points.map(p => {
        const d = new Date(p.date)
        return `${d.getDate()}.${d.getMonth() + 1}`
      }),
      datasets: [
        {
          label: showProfit ? 'Zysk (zł)' : 'Przychód (zł)',
          data: points.map(p => showProfit ? (p.profit || 0) : (p.revenue || 0)),
          borderColor: chartColors.green.line,
          backgroundColor: chartColors.green.fill,
          yAxisID: 'y-money',
          tension: 0.4,
          pointRadius: 0,
          pointHoverRadius: 4,
          fill: true,
        },
        {
          label: 'Ilość kart',
          data: points.map(p => p.quantity || 0),
          borderColor: chartColors.purple.line,
          backgroundColor: chartColors.purple.fill,
          yAxisID: 'y-quantity',
          tension: 0.4,
          pointRadius: 0,
          pointHoverRadius: 4,
          fill: true,
        }
      ]
    }
  }, [data?.sales_per_day, showProfit])



  const lineChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: 'rgba(15, 23, 42, 0.9)',
        titleColor: '#fff',
        bodyColor: '#94a3b8',
        borderColor: 'rgba(71, 85, 105, 0.5)',
        borderWidth: 1,
        padding: 12,
        cornerRadius: 8,
      },
    },
    scales: {
      x: {
        grid: { color: 'rgba(71, 85, 105, 0.2)', drawBorder: false },
        ticks: { color: '#64748b', font: { size: 10 } },
      },
      y: {
        grid: { color: 'rgba(71, 85, 105, 0.2)', drawBorder: false },
        ticks: { color: '#64748b', font: { size: 10 } },
        beginAtZero: true,
      },
    },
  }

  const doughnutOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'right' as const,
        labels: { color: '#94a3b8', font: { size: 11 }, padding: 12, boxWidth: 12 },
      },
      tooltip: {
        backgroundColor: 'rgba(15, 23, 42, 0.9)',
        titleColor: '#fff',
        bodyColor: '#94a3b8',
        borderColor: 'rgba(71, 85, 105, 0.5)',
        borderWidth: 1,
        padding: 12,
        cornerRadius: 8,
      },
    },
    cutout: '60%',
  }

  const salesChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      mode: 'index' as const,
      intersect: false,
    },
    plugins: {
      legend: {
        display: true,
        position: 'top' as const,
        labels: { color: '#94a3b8', font: { size: 11 }, padding: 12, boxWidth: 12 },
      },
      tooltip: {
        backgroundColor: 'rgba(15, 23, 42, 0.9)',
        titleColor: '#fff',
        bodyColor: '#94a3b8',
        borderColor: 'rgba(71, 85, 105, 0.5)',
        borderWidth: 1,
        padding: 12,
        cornerRadius: 8,
      },
    },
    scales: {
      x: {
        grid: { color: 'rgba(71, 85, 105, 0.2)', drawBorder: false },
        ticks: { color: '#64748b', font: { size: 10 } },
      },
      'y-money': {
        type: 'linear' as const,
        position: 'left' as const,
        grid: { color: 'rgba(71, 85, 105, 0.2)', drawBorder: false },
        ticks: { 
          color: '#22c55e',
          font: { size: 10 },
          callback: function(value: any) {
            return value.toFixed(0) + ' zł'
          }
        },
        title: { 
          display: true, 
          text: showProfit ? 'Zysk (PLN)' : 'Przychód (PLN)',
          color: '#22c55e',
          font: { size: 11 }
        }
      },
      'y-quantity': {
        type: 'linear' as const,
        position: 'right' as const,
        grid: { display: false },
        ticks: { 
          color: '#a855f7',
          font: { size: 10 },
          callback: function(value: any) {
            return value + ' szt.'
          }
        },
        title: { 
          display: true, 
          text: 'Ilość kart',
          color: '#a855f7',
          font: { size: 11 }
        }
      }
    }
  }



  const statItems = useMemo(() => [
    { key: 'total_products', label: 'Produkty w sklepie', value: data?.metrics.total_products },
    { key: 'inventory_units', label: 'Sztuki w magazynie', value: data?.metrics.inventory_units },
    { key: 'inventory_value', label: 'Wartość magazynu', value: data?.metrics.inventory_value_pln, suffix: ' zł', round: true },
    { key: 'sold_value', label: 'Sprzedane (wartość)', value: data?.metrics.sold_value_pln, suffix: ' zł', round: true, clickable: true, panel: 'sold' as const },
    { key: 'sold_count', label: 'Sprzedane (sztuki)', value: data?.metrics.sold_count, clickable: true, panel: 'sold' as const },
    { key: 'users_count', label: 'Użytkownicy', value: data?.metrics.users_count, clickable: true, panel: 'users' as const },
    { key: 'total_scans', label: 'Skanów łącznie', value: data?.metrics.total_scans },
    { key: 'scans_ready', label: 'Gotowe do publikacji', value: data?.metrics.scans_ready },
    { key: 'scans_published', label: 'Opublikowane', value: data?.metrics.scans_published },
  ], [data])

  if (loading && !data) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="flex items-center gap-3 text-gray-400">
          <span className="material-symbols-outlined animate-spin">progress_activity</span>
          <span>Ładowanie statystyk...</span>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto font-display pb-24">
      {/* Header */}
      <header className="mb-8">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 flex items-center justify-center bg-gradient-to-br from-purple-500/20 to-pink-600/20 rounded-full border border-purple-500/30">
              <span className="material-symbols-outlined text-2xl text-purple-400">analytics</span>
            </div>
            <div>
              <h1 className="text-white text-2xl font-bold">Statystyki</h1>
              <p className="text-gray-400 text-sm">Raporty i analityka Twojego sklepu</p>
            </div>
          </div>

          {/* Time range selector */}
          <div className="flex items-center gap-2 bg-[#0f172a] rounded-lg border border-gray-700/50 p-1">
            {([7, 30, 90] as const).map(days => (
              <button
                key={days}
                onClick={() => setTimeRange(days)}
                className={`px-3 py-1.5 text-sm font-medium rounded-md transition-all ${
                  timeRange === days
                    ? 'bg-gradient-to-r from-cyan-500/20 to-blue-600/20 text-cyan-400 border border-cyan-500/30'
                    : 'text-gray-400 hover:text-white'
                }`}
              >
                {days} dni
              </button>
            ))}
          </div>
        </div>
      </header>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-3 gap-3 md:gap-4 mb-8">
        {statItems.map(item => {
          const config = statConfig[item.key] || statConfig.total_products
          const isClickable = item.clickable
          return (
            <div
              key={item.key}
              className={`relative group ${isClickable ? 'cursor-pointer' : ''}`}
              onClick={() => {
                if (item.panel === 'users') { setPanel('users'); loadUsers() }
                if (item.panel === 'sold') { setPanel('sold'); loadSold() }
              }}
            >
              {/* Glow effect */}
              {isClickable && (
                <div className={`absolute -inset-0.5 bg-gradient-to-r ${config.gradient} rounded-xl blur opacity-0 group-hover:opacity-75 transition duration-300`} />
              )}

              <div className={`relative h-24 flex items-center rounded-xl p-4 bg-[#0f172a] border border-gray-700/50 transition-all duration-300 ${isClickable ? 'hover:border-gray-600 group-hover:shadow-lg' : ''}`}>
                {/* Icon */}
                <div className={`flex-shrink-0 w-12 h-12 flex items-center justify-center bg-gradient-to-br ${config.gradient} rounded-lg border border-gray-700/50 mr-4`}>
                  <span className={`material-symbols-outlined text-2xl ${config.color}`}>{config.icon}</span>
                </div>

                <div className="flex-grow min-w-0">
                  <p className="text-xs text-gray-400 leading-tight truncate">{item.label}</p>
                  <p className="text-xl font-bold text-white">
                    {item.value != null ? (
                      <Num v={item.round ? Math.round(item.value) : item.value} suffix={item.suffix} />
                    ) : '-'}
                  </p>
                </div>

                {isClickable && (
                  <span className="absolute top-2 right-2 material-symbols-outlined text-xs text-gray-600 group-hover:text-cyan-400 transition-colors">open_in_new</span>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {/* Sales Chart - Full Width */}
      <div className="mb-4">
        <div className="bg-[#0f172a] rounded-xl p-5 border border-gray-700/50">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 flex items-center justify-center bg-gradient-to-br from-green-500/20 to-emerald-600/20 rounded-lg">
                <span className="material-symbols-outlined text-lg text-green-400">monitoring</span>
              </div>
              <h3 className="text-white font-semibold">Sprzedaż w czasie</h3>
            </div>
            
            {/* Toggle: Revenue / Profit */}
            <button 
              onClick={() => setShowProfit(!showProfit)}
              className="px-3 py-1.5 text-sm font-medium rounded-lg border transition-all flex items-center gap-2 bg-gray-800/50 border-gray-600 hover:border-cyan-500/50 text-white"
            >
              <span className="material-symbols-outlined text-sm">
                {showProfit ? 'trending_up' : 'attach_money'}
              </span>
              {showProfit ? 'Zysk' : 'Przychód'}
            </button>
          </div>
          <div className="h-64">
            {data?.sales_per_day?.length ? (
              <Line data={salesChartData} options={salesChartOptions} />
            ) : (
              <div className="h-full flex items-center justify-center text-gray-500">Brak danych o sprzedaży</div>
            )}
          </div>
        </div>
      </div>

      {/* Charts Row 1: Line Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        {/* Products per day */}
        <div className="bg-[#0f172a] rounded-xl p-5 border border-gray-700/50">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-8 h-8 flex items-center justify-center bg-gradient-to-br from-cyan-500/20 to-blue-600/20 rounded-lg">
              <span className="material-symbols-outlined text-lg text-cyan-400">trending_up</span>
            </div>
            <h3 className="text-white font-semibold">Aktualizacje produktów</h3>
          </div>
          <div className="h-48">
            {data?.products_per_day?.length ? (
              <Line data={productsChartData} options={lineChartOptions} />
            ) : (
              <div className="h-full flex items-center justify-center text-gray-500">Brak danych</div>
            )}
          </div>
        </div>

        {/* Scans per day */}
        <div className="bg-[#0f172a] rounded-xl p-5 border border-gray-700/50">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-8 h-8 flex items-center justify-center bg-gradient-to-br from-green-500/20 to-emerald-600/20 rounded-lg">
              <span className="material-symbols-outlined text-lg text-green-400">qr_code_scanner</span>
            </div>
            <h3 className="text-white font-semibold">Skany w czasie</h3>
          </div>
          <div className="h-48">
            {data?.scans_per_day?.length ? (
              <Line data={scansChartData} options={lineChartOptions} />
            ) : (
              <div className="h-full flex items-center justify-center text-gray-500">Brak danych</div>
            )}
          </div>
        </div>
      </div>

      {/* Charts Row 2: Doughnut & Bar */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        {/* Top Categories - Doughnut */}
        <div className="bg-[#0f172a] rounded-xl p-5 border border-gray-700/50">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-8 h-8 flex items-center justify-center bg-gradient-to-br from-purple-500/20 to-pink-600/20 rounded-lg">
              <span className="material-symbols-outlined text-lg text-purple-400">category</span>
            </div>
            <h3 className="text-white font-semibold">Top kategorie</h3>
          </div>
          <div className="h-64">
            {data?.top_categories?.length ? (
              <Doughnut data={categoriesChartData} options={doughnutOptions} />
            ) : (
              <div className="h-full flex items-center justify-center text-gray-500">Brak danych</div>
            )}
          </div>
        </div>

        {/* Top Value Products - List with thumbnails */}
        <div className="bg-[#0f172a] rounded-xl p-5 border border-gray-700/50">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-8 h-8 flex items-center justify-center bg-gradient-to-br from-amber-500/20 to-orange-600/20 rounded-lg">
              <span className="material-symbols-outlined text-lg text-amber-400">diamond</span>
            </div>
            <h3 className="text-white font-semibold">Najbardziej wartościowe pozycje</h3>
          </div>
          <div className="h-64 overflow-y-auto pr-1 space-y-2">
            {data?.top_value?.length ? (
              data.top_value.slice(0, 8).map((product, idx) => (
                <div
                  key={product.id}
                  className="flex items-center gap-3 p-2 bg-[#1e293b] rounded-lg border border-gray-700/30 hover:border-gray-600/50 transition-colors"
                >
                  {/* Rank */}
                  <div className={`flex-shrink-0 w-6 h-6 flex items-center justify-center rounded text-xs font-bold ${
                    idx === 0 ? 'bg-amber-500/20 text-amber-400' :
                    idx === 1 ? 'bg-gray-400/20 text-gray-300' :
                    idx === 2 ? 'bg-orange-600/20 text-orange-400' :
                    'bg-gray-700/50 text-gray-500'
                  }`}>
                    {idx + 1}
                  </div>

                  {/* Thumbnail */}
                  {product.image ? (
                    <img
                      src={product.image}
                      alt=""
                      className="w-10 h-14 object-cover rounded border border-gray-700/50 flex-shrink-0"
                    />
                  ) : (
                    <div className="w-10 h-14 flex items-center justify-center bg-gray-800 rounded border border-gray-700/50 flex-shrink-0">
                      <span className="material-symbols-outlined text-gray-600 text-sm">image</span>
                    </div>
                  )}

                  {/* Info */}
                  <div className="flex-grow min-w-0">
                    <p className="text-white text-sm font-medium truncate">{product.name || product.code || `#${product.id}`}</p>
                    <p className="text-gray-500 text-xs truncate">{product.code}</p>
                  </div>

                  {/* Stock */}
                  <div className="flex-shrink-0 text-center px-2">
                    <p className="text-gray-400 text-xs">szt.</p>
                    <p className="text-white text-sm font-medium">{product.stock}</p>
                  </div>

                  {/* Value */}
                  <div className="flex-shrink-0 text-right min-w-[80px]">
                    <p className="text-green-400 font-semibold text-sm">{Math.round(product.value).toLocaleString('pl-PL')} zł</p>
                    <p className="text-gray-500 text-xs">{product.price?.toFixed(2)} zł/szt</p>
                  </div>
                </div>
              ))
            ) : (
              <div className="h-full flex items-center justify-center text-gray-500">Brak danych</div>
            )}
          </div>
        </div>
      </div>

      {/* Top Customers Card */}
      <div className="bg-[#0f172a] rounded-xl p-5 border border-gray-700/50">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 flex items-center justify-center bg-gradient-to-br from-rose-500/20 to-pink-600/20 rounded-lg">
              <span className="material-symbols-outlined text-lg text-rose-400">loyalty</span>
            </div>
            <h3 className="text-white font-semibold">Top klienci</h3>
          </div>
          <button
            onClick={() => { setPanel('customers'); loadSold() }}
            className="flex items-center gap-1 text-xs text-gray-400 hover:text-cyan-400 transition-colors"
          >
            <span>Zobacz wszystkich</span>
            <span className="material-symbols-outlined text-sm">chevron_right</span>
          </button>
        </div>

        {topCustomers.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {topCustomers.slice(0, 6).map((customer, idx) => (
              <div
                key={customer.email}
                className="flex items-center gap-3 p-3 bg-[#1e293b] rounded-lg border border-gray-700/30"
              >
                {/* Rank badge */}
                <div className={`flex-shrink-0 w-8 h-8 flex items-center justify-center rounded-full font-bold text-sm ${
                  idx === 0 ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30' :
                  idx === 1 ? 'bg-gray-400/20 text-gray-300 border border-gray-400/30' :
                  idx === 2 ? 'bg-orange-600/20 text-orange-400 border border-orange-500/30' :
                  'bg-gray-700/50 text-gray-500 border border-gray-600/30'
                }`}>
                  {idx + 1}
                </div>

                <div className="flex-grow min-w-0">
                  <p className="text-white font-medium text-sm truncate">{customer.name}</p>
                  <p className="text-gray-500 text-xs truncate">{customer.email}</p>
                </div>

                <div className="flex-shrink-0 text-right">
                  <p className="text-green-400 font-semibold text-sm">{Math.round(customer.total_spent).toLocaleString('pl-PL')} zł</p>
                  <p className="text-gray-500 text-xs">{customer.orders_count} zam.</p>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-8 text-gray-500">
            <span className="material-symbols-outlined text-3xl mb-2">person_off</span>
            <p>Brak danych o klientach</p>
            <button
              onClick={loadSold}
              className="mt-2 text-cyan-400 hover:text-cyan-300 text-sm"
            >
              Załaduj dane
            </button>
          </div>
        )}
      </div>

      {/* Right drawer for users/sold/customers */}
      <div className={`fixed inset-0 z-40 ${panel ? 'pointer-events-auto' : 'pointer-events-none'}`}>
        <div className={`absolute inset-0 bg-black/60 backdrop-blur-sm transition-opacity ${panel ? 'opacity-100' : 'opacity-0'}`} onClick={() => setPanel(null)} />
        <div className={`absolute right-0 top-0 h-full w-full sm:w-[640px] bg-[#0f172a] border-l border-gray-700/50 shadow-2xl transition-transform duration-300 ${panel ? 'translate-x-0' : 'translate-x-full'} flex flex-col`}>
          {/* Panel Header */}
          <div className="flex items-center justify-between p-4 border-b border-gray-700/50 flex-shrink-0">
            <div className="flex items-center gap-3">
              <div className={`w-8 h-8 flex items-center justify-center rounded-lg ${
                panel === 'users' ? 'bg-gradient-to-br from-rose-500/20 to-pink-600/20' :
                panel === 'customers' ? 'bg-gradient-to-br from-amber-500/20 to-orange-600/20' :
                'bg-gradient-to-br from-green-500/20 to-emerald-600/20'
              }`}>
                <span className={`material-symbols-outlined text-lg ${
                  panel === 'users' ? 'text-rose-400' :
                  panel === 'customers' ? 'text-amber-400' :
                  'text-green-400'
                }`}>
                  {panel === 'users' ? 'group' : panel === 'customers' ? 'loyalty' : 'shopping_bag'}
                </span>
              </div>
              <div className="text-white font-semibold">
                {panel === 'users' ? 'Użytkownicy' : panel === 'customers' ? 'Top klienci' : 'Sprzedane karty'}
              </div>
            </div>
            <button
              className="w-8 h-8 flex items-center justify-center rounded-lg text-gray-400 hover:text-white hover:bg-white/10 transition-colors"
              onClick={() => setPanel(null)}
            >
              <span className="material-symbols-outlined">close</span>
            </button>
          </div>

          {/* Panel Content */}
          <div className="p-4 overflow-y-auto flex-grow">
            {/* Users Panel */}
            {panel === 'users' && (
              <div className="space-y-2">
                {(users || []).map((u: any, i: number) => (
                  <div key={i} className="flex items-center gap-3 p-3 bg-[#1e293b] rounded-lg border border-gray-700/30">
                    <div className="w-10 h-10 flex items-center justify-center bg-gradient-to-br from-rose-500/20 to-pink-600/20 rounded-full">
                      <span className="material-symbols-outlined text-rose-400">person</span>
                    </div>
                    <div className="flex-grow min-w-0">
                      <p className="text-white font-medium truncate">{u.email || '-'}</p>
                      <p className="text-gray-500 text-xs">
                        {u.date_add ? `Dołączył: ${new Date(u.date_add).toLocaleDateString('pl-PL')}` : ''}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      {u.has_orders && (
                        <span className="px-2 py-1 text-xs bg-green-500/20 text-green-400 rounded-full">Kupujący</span>
                      )}
                      {u.active ? (
                        <span className="px-2 py-1 text-xs bg-cyan-500/20 text-cyan-400 rounded-full">Aktywny</span>
                      ) : (
                        <span className="px-2 py-1 text-xs bg-gray-500/20 text-gray-400 rounded-full">Nieaktywny</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Sold Items Panel */}
            {panel === 'sold' && (
              <div className="space-y-2">
                {soldAggregated.map((it: any, i) => (
                  <div key={i} className="flex items-center gap-3 p-3 bg-[#1e293b] rounded-lg border border-gray-700/30">
                    {it.image ? (
                      <img src={it.image} alt="" className="w-12 h-12 object-cover rounded-lg border border-gray-700/50" />
                    ) : (
                      <div className="w-12 h-12 flex items-center justify-center bg-gray-800 rounded-lg border border-gray-700/50">
                        <span className="material-symbols-outlined text-gray-600">image</span>
                      </div>
                    )}
                    <div className="flex-grow min-w-0">
                      <p className="text-white font-medium truncate">{it.name}</p>
                      <p className="text-gray-500 text-xs truncate">{it.code || '-'}</p>
                    </div>
                    <div className="flex-shrink-0 text-right">
                      <p className="text-green-400 font-semibold">{it.total != null ? `${Math.round(it.total).toLocaleString('pl-PL')} zł` : '-'}</p>
                      <p className="text-gray-500 text-xs">{it.qty} szt.</p>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Top Customers Panel */}
            {panel === 'customers' && (
              <div className="space-y-2">
                {topCustomers.map((customer, idx) => (
                  <div key={customer.email} className="flex items-center gap-3 p-3 bg-[#1e293b] rounded-lg border border-gray-700/30">
                    {/* Rank */}
                    <div className={`flex-shrink-0 w-10 h-10 flex items-center justify-center rounded-full font-bold ${
                      idx === 0 ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30' :
                      idx === 1 ? 'bg-gray-400/20 text-gray-300 border border-gray-400/30' :
                      idx === 2 ? 'bg-orange-600/20 text-orange-400 border border-orange-500/30' :
                      'bg-gray-700/50 text-gray-500 border border-gray-600/30'
                    }`}>
                      #{idx + 1}
                    </div>

                    <div className="flex-grow min-w-0">
                      <p className="text-white font-medium truncate">{customer.name}</p>
                      <p className="text-gray-500 text-xs truncate">{customer.email}</p>
                    </div>

                    <div className="flex-shrink-0 text-right">
                      <p className="text-green-400 font-semibold">{Math.round(customer.total_spent).toLocaleString('pl-PL')} zł</p>
                      <p className="text-gray-500 text-xs">{customer.orders_count} zamówień</p>
                    </div>

                    {/* Medal for top 3 */}
                    {idx < 3 && (
                      <div className="flex-shrink-0">
                        <span className={`material-symbols-outlined text-2xl ${
                          idx === 0 ? 'text-amber-400' :
                          idx === 1 ? 'text-gray-300' :
                          'text-orange-400'
                        }`}>
                          {idx === 0 ? 'emoji_events' : 'military_tech'}
                        </span>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
