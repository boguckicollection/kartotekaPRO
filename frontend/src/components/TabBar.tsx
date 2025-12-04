import React from 'react'

type Tab = { key: string; label?: string; icon?: string }

type Props = {
  tabs: Tab[]
  active: string
  onChange: (k: string) => void
}

const defaultIcon = (key: string): string => {
  switch (key) {
    case 'dashboard': return 'home'
    case 'scan': return 'qr_code_scanner'
    case 'inventory': return 'visibility'
    case 'orders': return 'receipt_long'
    case 'pricing': return 'sell'
    default: return 'widgets'
  }
}

export default function TabBar({tabs, active, onChange}: Props){
  return (
    <div className="fixed bottom-0 left-0 right-0 h-20 bg-gray-900/80 backdrop-blur-lg border-t border-gray-700/50 z-50 pb-safe">
      <div className="flex justify-around items-center h-full">
        {tabs.map(t => {
          const isActive = active === t.key;
          return (
            <button
              key={t.key}
              className={`flex flex-col items-center justify-center w-full h-full text-gray-400 transition-colors duration-300 relative group ${isActive ? 'text-primary' : 'hover:text-white'}`}
              onClick={()=>onChange(t.key)}
              aria-label={t.label || t.key}
              title={t.label || t.key}
            >
              <div className={`absolute top-0 w-12 h-1 rounded-b-full bg-primary transition-all duration-300 ${isActive ? 'opacity-100 scale-x-100' : 'opacity-0 scale-x-0'}`}></div>
              
              <div className={`relative flex items-center justify-center w-16 h-8 rounded-full transition-all duration-300 ${isActive ? 'bg-primary/20' : 'group-hover:bg-gray-700/50'}`}>
                <span className="material-symbols-outlined text-2xl">{t.icon || defaultIcon(t.key)}</span>
              </div>
              
              <span className="text-[10px] font-bold mt-1 transition-opacity duration-200">{t.label}</span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
