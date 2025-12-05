import React from 'react'

type Item = { key: string; label: string; icon: string; color: string }

type Props = {
  active: string
  onChange: (key: string) => void
}

const items: Item[] = [
  { key: 'scan', label: 'Skanowanie', icon: 'qr_code_scanner', color: 'cyan' },
  { key: 'inventory', label: 'Magazyn', icon: 'inventory_2', color: 'purple' },
  { key: 'warehouse', label: 'Wizualizacja', icon: 'warehouse', color: 'amber' },
  { key: 'reports', label: 'Statystyki', icon: 'analytics', color: 'purple' },
  { key: 'pricing', label: 'Wycena', icon: 'sell', color: 'emerald' },
  { key: 'bidding', label: 'Licytacje', icon: 'gavel', color: 'amber' },
  { key: 'app_dashboard', label: 'Collector', icon: 'collections_bookmark', color: 'rose' },
  { key: 'orders', label: 'Zamówienia', icon: 'receipt_long', color: 'blue' },
]

// Color mappings for gradients and text
const colorStyles: Record<string, { gradient: string; text: string; glow: string }> = {
  cyan: {
    gradient: 'from-cyan-500/20 to-blue-600/20',
    text: 'text-cyan-400',
    glow: 'shadow-cyan-500/20',
  },
  purple: {
    gradient: 'from-purple-500/20 to-pink-600/20',
    text: 'text-purple-400',
    glow: 'shadow-purple-500/20',
  },
  emerald: {
    gradient: 'from-emerald-500/20 to-teal-600/20',
    text: 'text-emerald-400',
    glow: 'shadow-emerald-500/20',
  },
  amber: {
    gradient: 'from-amber-500/20 to-orange-600/20',
    text: 'text-amber-400',
    glow: 'shadow-amber-500/20',
  },
  blue: {
    gradient: 'from-blue-500/20 to-indigo-600/20',
    text: 'text-blue-400',
    glow: 'shadow-blue-500/20',
  },
  rose: {
    gradient: 'from-rose-500/20 to-pink-600/20',
    text: 'text-rose-400',
    glow: 'shadow-rose-500/20',
  },
}

export default function Sidebar({ active, onChange }: Props) {
  return (
    <aside className="hidden md:flex flex-col w-64 bg-[#0f172a] min-h-screen border-r border-gray-800/50">
      {/* Logo */}
      <div className="flex items-center justify-center h-16 border-b border-gray-800/50">
        <img src="/biale-male.png" alt="Logo" className="h-8 object-contain" />
      </div>

      {/* Navigation */}
      <div className="flex flex-col flex-1 p-3">
        <nav className="flex flex-col gap-1">
          {/* Dashboard / Panel */}
          <button
            onClick={() => onChange('dashboard')}
            className={`group relative flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-200 ${
              active === 'dashboard'
                ? 'bg-gradient-to-r from-cyan-500/20 to-blue-600/20 border border-cyan-500/30 shadow-lg shadow-cyan-500/10'
                : 'hover:bg-white/5 border border-transparent'
            }`}
          >
            <div className={`w-8 h-8 flex items-center justify-center rounded-lg transition-all duration-200 ${
              active === 'dashboard'
                ? 'bg-gradient-to-br from-cyan-500/30 to-blue-600/30'
                : 'bg-gray-800/50 group-hover:bg-gradient-to-br group-hover:from-cyan-500/20 group-hover:to-blue-600/20'
            }`}>
              <span className={`material-symbols-outlined text-lg transition-colors ${
                active === 'dashboard' ? 'text-cyan-400' : 'text-gray-400 group-hover:text-cyan-400'
              }`} style={active === 'dashboard' ? { fontVariationSettings: "'FILL' 1" } : undefined}>
                home
              </span>
            </div>
            <span className={`font-display text-sm transition-colors ${
              active === 'dashboard' ? 'text-white' : 'text-gray-400 group-hover:text-white'
            }`}>
              Panel
            </span>
          </button>

          {/* Menu items */}
          {items.map(it => {
            const colors = colorStyles[it.color] || colorStyles.cyan
            const isActive = active === it.key

            return (
              <button
                key={it.key}
                onClick={() => onChange(it.key)}
                className={`group relative flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-200 ${
                  isActive
                    ? `bg-gradient-to-r ${colors.gradient} border border-${it.color}-500/30 shadow-lg ${colors.glow}`
                    : 'hover:bg-white/5 border border-transparent'
                }`}
              >
                <div className={`w-8 h-8 flex items-center justify-center rounded-lg transition-all duration-200 ${
                  isActive
                    ? `bg-gradient-to-br ${colors.gradient}`
                    : `bg-gray-800/50 group-hover:bg-gradient-to-br group-hover:${colors.gradient}`
                }`}>
                  <span
                    className={`material-symbols-outlined text-lg transition-colors ${
                      isActive ? colors.text : `text-gray-400 group-hover:${colors.text}`
                    }`}
                    style={isActive ? { fontVariationSettings: "'FILL' 1" } : undefined}
                  >
                    {it.icon}
                  </span>
                </div>
                <span className={`font-display text-sm transition-colors ${
                  isActive ? 'text-white' : 'text-gray-400 group-hover:text-white'
                }`}>
                  {it.label}
                </span>

                {/* Active indicator line */}
                {isActive && (
                  <div className={`absolute right-0 top-1/2 -translate-y-1/2 w-1 h-6 rounded-l-full bg-gradient-to-b ${colors.gradient.replace('/20', '/60')}`} />
                )}
              </button>
            )
          })}
        </nav>
      </div>

      {/* Settings at bottom */}
      <div className="p-3 border-t border-gray-800/50">
        <button
          onClick={() => onChange('settings')}
          className={`group w-full flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-200 ${
            active === 'settings'
              ? 'bg-gradient-to-r from-gray-500/20 to-slate-600/20 border border-gray-500/30'
              : 'hover:bg-white/5 border border-transparent'
          }`}
        >
          <div className={`w-8 h-8 flex items-center justify-center rounded-lg transition-all duration-200 ${
            active === 'settings'
              ? 'bg-gradient-to-br from-gray-500/30 to-slate-600/30'
              : 'bg-gray-800/50 group-hover:bg-gray-700/50'
          }`}>
            <span className={`material-symbols-outlined text-lg transition-colors ${
              active === 'settings' ? 'text-gray-300' : 'text-gray-500 group-hover:text-gray-300'
            }`} style={active === 'settings' ? { fontVariationSettings: "'FILL' 1" } : undefined}>
              settings
            </span>
          </div>
          <span className={`font-display text-sm transition-colors ${
            active === 'settings' ? 'text-white' : 'text-gray-400 group-hover:text-white'
          }`}>
            Ustawienia
          </span>
        </button>
      </div>
    </aside>
  )
}
