import React, { useState } from 'react'
import ProductEditSlider from '../components/ProductEditSlider'
import { Product } from '../types'

type Props = {
  items: Product[]
  page: number
  limit: number
  hasNext: boolean
  sort: string
  order: string
  onSearch: (query: string, sort: string, order: string, page: number, limit: number, categoryId?: number)=>void
  onSync: ()=>void
  onUpdate: (product: Product) => Promise<void>
  isSyncing: boolean
  q: string | undefined
  categoryId: number | undefined
}

const CATEGORIES: { id: number; name: string }[] = [
  {id:38,name:'Karty Pokémon'},{id:39,name:'151'},{id:40,name:'Licytacja'},{id:41,name:'Zestawy'},{id:42,name:'Temporal Forces'},{id:43,name:'Obsidian Flames'},{id:44,name:'Journey Together'},{id:48,name:'Stellar Crown'},{id:49,name:'Twilight Masquerade'},{id:51,name:'Prismatic Evolutions'},{id:53,name:'Destined Rivals'},{id:55,name:'Scarlet & Violet'},{id:56,name:'Paldea Evolved'},{id:57,name:'Paradox Rift'},{id:58,name:'Surging Sparks'},{id:60,name:'Shrouded Fable'},{id:65,name:'Paldean Fates'},{id:66,name:'Evolutions'},{id:70,name:'White Flare'},{id:71,name:'Black Bolt'},{id:72,name:'Scarlet & Violet'},{id:74,name:'XY'},{id:75,name:'Sun & Moon'},{id:80,name:'SVP Black Star Promos'},{id:89,name:'BREAKpoint'},{id:90,name:'Sword & Shield'},{id:91,name:'Vivid Voltage'},{id:92,name:'Pokémon GO'},{id:93,name:'Rebel Clash'},{id:94,name:'Lost Origin'},{id:95,name:'Shining Fates'},{id:96,name:'Chilling Reign'},{id:97,name:'SWSH Black Star Promos'},{id:98,name:'BREAKthrough'},{id:99,name:'Crown Zenith'},{id:100,name:'Astral Radiance'},{id:101,name:'Roaring Skies'},{id:102,name:'Primal Clash'},{id:103,name:'Brilliant Stars'},{id:104,name:'Evolving Skies'},{id:105,name:'Fusion Strike'},{id:106,name:'Celebrations'},{id:107,name:'Silver Tempest'},{id:108,name:'Darkness Ablaze'},{id:109,name:'Generations'},{id:110,name:'Ancient Origins'},{id:111,name:'Steam Siege'}
]

export default function InventoryView({ items, page, limit, hasNext, sort, order, onSearch, onSync, onUpdate, isSyncing, q, categoryId }: Props){
  const [localLimit, setLocalLimit] = useState<number>(limit)
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null)
  const [isSliderOpen, setIsSliderOpen] = useState(false)
  const [hoveredImage, setHoveredImage] = useState<{ src: string; x: number; y: number; showBelow?: boolean } | null>(null)

  const handleMouseEnter = (e: React.MouseEvent<HTMLTableCellElement>, image: string | null | undefined) => {
    if (!image) return
    const rect = e.currentTarget.getBoundingClientRect()
    const viewportHeight = window.innerHeight
    
    // Sprawdź czy element jest w górnej połowie ekranu
    const isInTopHalf = rect.top < viewportHeight / 2
    
    setHoveredImage({
      src: image,
      x: rect.left + rect.width / 2,
      y: isInTopHalf ? rect.bottom : rect.top, // Użyj bottom jeśli góra, top jeśli dół
      showBelow: isInTopHalf, // Flaga dla CSS
    })
  }

  const handleMouseLeave = () => {
    setHoveredImage(null)
  }

  const handleProductClick = (product: Product) => {
    setSelectedProduct(product)
    setIsSliderOpen(true)
  }

  const handleCloseSlider = () => {
    setIsSliderOpen(false)
    setSelectedProduct(null)
  }

  return (
    <div className="font-display">
      {hoveredImage && (
        <div
          className="fixed z-50 p-2 bg-gray-900/95 backdrop-blur-sm border border-cyan-500 rounded-lg shadow-2xl pointer-events-none transition-all duration-300 ease-out animate-fade-in"
          style={{
            left: hoveredImage.x,
            top: hoveredImage.y,
            transform: hoveredImage.showBelow 
              ? 'translate(-50%, 10px)'  // Pokaż poniżej z marginesem
              : 'translate(-50%, calc(-100% - 10px))', // Pokaż powyżej z marginesem
            maxHeight: '80vh', // Ogranicz wysokość do 80% viewportu
            overflow: 'hidden',
            animation: 'fadeInScale 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
          }}
        >
          <img 
            src={hoveredImage.src} 
            alt="Podgląd" 
            className="w-64 h-auto rounded"
            style={{ maxHeight: '75vh', objectFit: 'contain' }}
          />
        </div>
      )}
      
      {/* Keyframes for fade-in animation */}
      <style>{`
        @keyframes fadeInScale {
          from {
            opacity: 0;
            transform: translate(-50%, ${hoveredImage?.showBelow ? '20px' : 'calc(-100% - 20px)'}) scale(0.95);
          }
          to {
            opacity: 1;
            transform: translate(-50%, ${hoveredImage?.showBelow ? '10px' : 'calc(-100% - 10px)'}) scale(1);
          }
        }
      `}</style>
      <header className="flex items-center justify-between whitespace-nowrap border-b border-gray-800 px-2 md:px-6 py-3">
        <div className="flex items-center gap-3 text-white">
          <span className="material-symbols-outlined text-primary">visibility</span>
          <h2 className="text-lg font-bold">Magazyn</h2>
        </div>
      </header>
      <main className="p-4 md:p-6">
        <div className="flex flex-wrap gap-3 mb-4">
          <input value={q || ''} onChange={e=>onSearch(e.target.value, sort, order, 1, localLimit, categoryId)} placeholder="Szukaj" className="flex-1 min-w-[220px] rounded-md border border-gray-700 bg-[#101922] text-white px-3 py-2" />
          <select value={categoryId ?? ''} onChange={e=>onSearch(q, sort, order, 1, localLimit, e.target.value ? Number(e.target.value) : undefined)} className="rounded-md border border-gray-700 bg-[#101922] text-white px-3 py-2">
            <option value="">Wszystkie kategorie</option>
            {CATEGORIES.map(c => (<option key={c.id} value={c.id}>{c.name}</option>))}
          </select>
          <select value={localLimit} onChange={e=>{ const v=Number(e.target.value); setLocalLimit(v); onSearch(q, sort, order, 1, v, categoryId) }} className="rounded-md border border-gray-700 bg-[#101922] text-white px-3 py-2">
            <option value={25}>25</option>
            <option value={50}>50</option>
            <option value={100}>100</option>
            <option value={250}>250</option>
          </select>
          <button onClick={()=>onSearch(q, sort, order, 1, localLimit, categoryId)} className="rounded-lg h-10 px-4 bg-primary text-white text-sm font-bold">Szukaj</button>
                    <button onClick={onSync} disabled={isSyncing} className="rounded-lg h-10 px-4 bg-[#283039] text-white text-sm font-bold flex items-center justify-center disabled:opacity-50">
            {isSyncing ? (
              <>
                <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Synchronizowanie...
              </>
            ) : (
              'Sync z Shoper'
            )}
          </button>
        </div>
        {/* DESKTOP: Tabela */}
        <div className="hidden md:block overflow-auto rounded-xl border border-white/10">
          <table className="w-full min-w-[680px] table-auto">
            <thead>
              <tr className="bg-[#111827] text-gray-200">
                <Th label="Miniatura" />
                <Th label="Nazwa" sortable current={sort} field="name" order={order} onSort={(f)=>onSearch(q, f, sort===f && order==='asc'?'desc':'asc', 1, localLimit, categoryId)} />
                <Th label="Kod" sortable current={sort} field="code" order={order} onSort={(f)=>onSearch(q, f, sort===f && order==='asc'?'desc':'asc', 1, localLimit, categoryId)} />
                <Th label="Kategoria" />
                <Th label="Cena" sortable current={sort} field="price" order={order} onSort={(f)=>onSearch(q, f, sort===f && order==='asc'?'desc':'asc', 1, localLimit, categoryId)} />
                <Th label="Stan" sortable current={sort} field="stock" order={order} onSort={(f)=>onSearch(q, f, sort===f && order==='asc'?'desc':'asc', 1, localLimit, categoryId)} />
                <Th label="Link" />
              </tr>
            </thead>
            <tbody>
              {items.map(p => (
                <tr key={p.id} className="border-t border-white/10 cursor-pointer hover:bg-white/5" onClick={() => handleProductClick(p)}>
                  <td 
                    className="p-2"
                    onMouseEnter={(e) => handleMouseEnter(e, p.image)}
                    onMouseLeave={handleMouseLeave}
                  >
                    {p.image ? (
                      <div className="w-12 h-12 rounded overflow-hidden border border-white/10">
                        <img src={p.image} alt={p.name} className="w-full h-full object-cover object-top" />
                      </div>
                    ) : (
                      <div className="w-12 h-12 border border-white/10 rounded flex items-center justify-center text-gray-500 text-xs">brak</div>
                    )}
                  </td>
                  <td className="p-2 text-white">{p.name || '—'}</td>
                  <td className="p-2 text-gray-300">{p.code || ''}</td>
                  <td className="p-2 text-gray-400 text-sm">{p.category_name || (p.category_id ? `Kategoria ${p.category_id}` : '')}</td>
                  <td className="p-2 text-gray-200">{p.price ?? '-'} PLN</td>
                  <td className="p-2 text-gray-200">{p.stock ?? '-'}</td>
                  <td className="p-2">{p.permalink && <a href={p.permalink} className="text-primary" target="_blank" rel="noreferrer">Permalink</a>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* MOBILE: Lista kart */}
        <div className="md:hidden space-y-3">
            {items.map(p => (
                <div key={p.id} className="bg-gray-800/50 rounded-lg p-3 border border-gray-700 flex gap-3 items-start" onClick={() => handleProductClick(p)}>
                    {/* Obrazek */}
                    <div className="w-16 h-20 flex-shrink-0 bg-black/50 rounded overflow-hidden border border-gray-600">
                        {p.image ? (
                            <img src={p.image} alt={p.name} className="w-full h-full object-cover" />
                        ) : (
                            <div className="w-full h-full flex items-center justify-center text-gray-500 text-xs">brak</div>
                        )}
                    </div>
                    
                    {/* Detale */}
                    <div className="flex-grow min-w-0">
                        <h4 className="font-bold text-sm text-white truncate">{p.name}</h4>
                        <p className="text-xs text-gray-400 mt-1">{p.category_name || 'Brak kategorii'}</p>
                        <div className="flex items-center justify-between mt-2">
                            <span className="text-base font-bold text-primary">{p.price ?? '0.00'} PLN</span>
                            <span className="text-xs px-2 py-1 bg-gray-700 rounded text-gray-300">Stan: {p.stock ?? '0'}</span>
                        </div>
                    </div>
                </div>
            ))}
        </div>

        <div className="flex items-center justify-between mt-4">
          <div className="text-gray-400 text-sm">Strona {page} • {items.length} pozycji • Na stronę: {localLimit}</div>
          <div className="flex gap-2">
            <button className="rounded-lg h-9 px-3 bg-[#283039] text-white text-sm font-bold disabled:opacity-50" disabled={page<=1} onClick={()=>onSearch(q, sort, order, page-1, localLimit, categoryId)}>Poprzednia</button>
            <button className="rounded-lg h-9 px-3 bg-primary text-white text-sm font-bold disabled:opacity-50" disabled={!hasNext} onClick={()=>onSearch(q, sort, order, page+1, localLimit, categoryId)}>Następna</button>
          </div>
        </div>
      </main>
      {isSliderOpen && selectedProduct && (
        <ProductEditSlider 
          key={selectedProduct.id}
          product={selectedProduct} 
          onClose={handleCloseSlider} 
          onUpdate={onUpdate}
        />
      )}
    </div>
  )
}

function Th({ label, sortable=false, field, current, order, onSort }:{ label:string; sortable?:boolean; field?:string; current?:string; order?:string; onSort?:(f:string)=>void }){
  const active = sortable && field && current===field
  return (
    <th className="text-left px-2 py-2 select-none">
      {!sortable ? (
        <span>{label}</span>
      ) : (
        <button className={`inline-flex items-center gap-1 ${active?'text-primary':'text-gray-200'}`} onClick={()=>field && onSort && onSort(field)}>
          <span>{label}</span>
          {active && <span className="material-symbols-outlined text-sm align-middle">{order==='asc'?'arrow_upward':'arrow_downward'}</span>}
        </button>
      )}
    </th>
  )
}