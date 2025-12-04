import React, { useState, useEffect } from 'react'
import { Product } from '../types'

const CATEGORIES: { id: number; name: string }[] = [
  {id:38,name:'Karty Pokémon'},{id:39,name:'151'},{id:40,name:'Licytacja'},{id:41,name:'Zestawy'},{id:42,name:'Temporal Forces'},{id:43,name:'Obsidian Flames'},{id:44,name:'Journey Together'},{id:48,name:'Stellar Crown'},{id:49,name:'Twilight Masquerade'},{id:51,name:'Prismatic Evolutions'},{id:53,name:'Destined Rivals'},{id:55,name:'Scarlet & Violet'},{id:56,name:'Paldea Evolved'},{id:57,name:'Paradox Rift'},{id:58,name:'Surging Sparks'},{id:60,name:'Shrouded Fable'},{id:65,name:'Paldean Fates'},{id:66,name:'Evolutions'},{id:70,name:'White Flare'},{id:71,name:'Black Bolt'},{id:72,name:'Scarlet & Violet'},{id:74,name:'XY'},{id:75,name:'Sun & Moon'},{id:80,name:'SVP Black Star Promos'},{id:89,name:'BREAKpoint'},{id:90,name:'Sword & Shield'},{id:91,name:'Vivid Voltage'},{id:92,name:'Pokémon GO'},{id:93,name:'Rebel Clash'},{id:94,name:'Lost Origin'},{id:95,name:'Shining Fates'},{id:96,name:'Chilling Reign'},{id:97,name:'SWSH Black Star Promos'},{id:98,name:'BREAKthrough'},{id:99,name:'Crown Zenith'},{id:100,name:'Astral Radiance'},{id:101,name:'Roaring Skies'},{id:102,name:'Primal Clash'},{id:103,name:'Brilliant Stars'},{id:104,name:'Evolving Skies'},{id:105,name:'Fusion Strike'},{id:106,name:'Celebrations'},{id:107,name:'Silver Tempest'},{id:108,name:'Darkness Ablaze'},{id:109,name:'Generations'},{id:110,name:'Ancient Origins'},{id:111,name:'Steam Siege'}
]

type Props = {
  product: Product
  onClose: () => void
  onUpdate: (product: Product) => Promise<void>
  apiBase: string
}

export default function ProductEditSlider({ product, onClose, onUpdate, apiBase }: Props) {
  const [formData, setFormData] = useState<Product>(product)
  const [open, setOpen] = useState(false)
  const [isUpdating, setIsUpdating] = useState(false)
  const [isEditMode, setIsEditMode] = useState(false)
  const [locations, setLocations] = useState<any[] | null>(null);
  const [isLoadingLocations, setIsLoadingLocations] = useState(false);
  const [locationsError, setLocationsError] = useState<string | null>(null);

  useEffect(() => {
    setFormData(product)
    setIsEditMode(false) // Reset to details view when product changes
    const timer = setTimeout(() => setOpen(true), 50);
    return () => clearTimeout(timer);
  }, [product])

  useEffect(() => {
    if (product.shoper_id) {
      const fetchLocations = async () => {
        setIsLoadingLocations(true);
        setLocationsError(null);
        try {
          // Use /api directly to avoid any issues with apiBase propagation
          const response = await fetch(`/api/products/${product.shoper_id}/locations`);
          if (!response.ok) {
            throw new Error(`Failed to fetch locations: ${response.status}`);
          }
          // Check if response is JSON
          const contentType = response.headers.get("content-type");
          if (!contentType || !contentType.includes("application/json")) {
             const text = await response.text();
             console.error("Received non-JSON response:", text.substring(0, 200));
             throw new Error("Received invalid response from server (not JSON)");
          }
          const data = await response.json();
          setLocations(data);
        } catch (error: any) {
          setLocationsError(error.message);
        } finally {
          setIsLoadingLocations(false);
        }
      };
      fetchLocations();
    } else {
      setLocations(null);
    }
  }, [product.shoper_id]); // Removed apiBase from dependency array as we hardcoded /api

  const handleClose = () => {
    setOpen(false);
    const timer = setTimeout(onClose, 300);
    return () => clearTimeout(timer);
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target
    const parsedValue = name === 'price' ? parseFloat(value) : (name === 'stock' || name === 'category_id' ? parseInt(value, 10) : value);
    setFormData(prev => ({ ...prev, [name]: parsedValue }))
  }

  const handleUpdate = async () => {
    setIsUpdating(true);
    try {
      await onUpdate(formData);
      handleClose();
    } catch (error) {
      console.error('Error updating product:', error);
      alert(`Błąd podczas aktualizacji produktu: ${error.message}`);
    } finally {
      setIsUpdating(false);
    }
  }

  const getNumberFromCode = (code: string) => {
    if (!code) return 'N/A';
    const parts = code.split('-');
    return parts[parts.length - 1] || 'N/A';
  };

  const parseWarehouseCode = (code: string) => {
    const match = code.match(/K(P|\d+)-R(\d+)-P(\d+)/);
    if (!match) return null;
    return {
      karton: match[1] === 'P' ? 'Premium' : match[1],
      rzad: match[2],
      pozycja: match[3],
    };
  };

  return (
    <div className={`fixed inset-0 z-40 ${open ? 'pointer-events-auto' : 'pointer-events-none'}`}>
      <div className={`absolute inset-0 bg-black/50 transition-opacity ${open ? 'opacity-100' : 'opacity-0'}`} onClick={handleClose} />
      <div className={`absolute right-0 top-0 h-full w-full sm:w-[520px] bg-[#111418] border-l border-white/10 shadow-xl transition-transform duration-300 ${open ? 'translate-x-0' : 'translate-x-full'} flex flex-col`}>
        <div className="flex items-center justify-between p-4 border-b border-white/10 flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className="text-white font-semibold">{isEditMode ? `Edytuj: ${product.name}` : `Szczegóły karty`}</div>
          </div>
          <button className="text-white/80 hover:text-white" onClick={handleClose}><span className="material-symbols-outlined">close</span></button>
        </div>
        <div className="p-4 pb-8 overflow-y-auto flex-grow">
          {product.image && (
            <div className="mb-4 flex justify-center">
              <img src={product.image} alt={product.name} className="w-48 h-auto object-contain rounded-lg border border-white/10" />
            </div>
          )}

          {isEditMode ? (
            <form className="space-y-4">
              {/* Form fields from your existing code */}
              <div>
                <label htmlFor="name" className="block text-sm font-medium text-gray-300">Nazwa</label>
                <input type="text" name="name" id="name" value={formData.name} onChange={handleChange} className="mt-1 block w-full rounded-md border-gray-700 shadow-sm bg-[#1D2632] text-white focus:border-primary focus:ring-primary sm:text-sm" />
              </div>
              <div>
                <label htmlFor="code" className="block text-sm font-medium text-gray-300">Kod</label>
                <input type="text" name="code" id="code" value={formData.code} onChange={handleChange} className="mt-1 block w-full rounded-md border-gray-700 shadow-sm bg-[#1D2632] text-white focus:border-primary focus:ring-primary sm:text-sm" />
              </div>
              <div>
                <label htmlFor="price" className="block text-sm font-medium text-gray-300">Cena</label>
                <input type="number" name="price" id="price" value={formData.price ?? ''} onChange={handleChange} className="mt-1 block w-full rounded-md border-gray-700 shadow-sm bg-[#1D2632] text-white focus:border-primary focus:ring-primary sm:text-sm" />
              </div>
              <div>
                <label htmlFor="stock" className="block text-sm font-medium text-gray-300">Stan</label>
                <input type="number" name="stock" id="stock" value={formData.stock ?? ''} onChange={handleChange} className="mt-1 block w-full rounded-md border-gray-700 shadow-sm bg-[#1D2632] text-white focus:border-primary focus:ring-primary sm:text-sm" />
              </div>
              <div>
                <label htmlFor="category_id" className="block text-sm font-medium text-gray-300">Kategoria</label>
                <select id="category_id" name="category_id" value={formData.category_id ?? ''} onChange={handleChange} className="mt-1 block w-full rounded-md border-gray-700 shadow-sm bg-[#1D2632] text-white focus:border-primary focus:ring-primary sm:text-sm">
                  <option value="">Wybierz kategorię</option>
                  {CATEGORIES.map(c => (<option key={c.id} value={c.id}>{c.name}</option>))}
                </select>
              </div>
            </form>
          ) : (
            <div className="space-y-4 text-white">
              <div>
                <h3 className="text-lg font-bold">{product.name}</h3>
              </div>
              <div className="border-t border-white/10 pt-4">
                <dl className="space-y-2">
                  <div className="flex justify-between">
                    <dt className="text-sm font-medium text-gray-400">Numer</dt>
                    <dd className="text-sm">{getNumberFromCode(product.code)}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-sm font-medium text-gray-400">Cena</dt>
                    <dd className="text-sm">{product.price ?? '-'} PLN</dd>
                  </div>
                   <div className="flex justify-between">
                    <dt className="text-sm font-medium text-gray-400">Stan</dt>
                    <dd className="text-sm">{product.stock ?? '-'}</dd>
                  </div>
                </dl>
              </div>

              <div className="border-t border-white/10 pt-4 mt-4">
                <h4 className="text-sm font-medium text-gray-300 mb-2 flex items-center gap-2">
                  <span className="material-symbols-outlined text-lg text-cyan-400">inventory_2</span>
                  Miejsca magazynowe
                </h4>
                {isLoadingLocations && <p className="text-sm text-gray-500">Ładowanie...</p>}
                {locationsError && <p className="text-sm text-red-400">Błąd: {locationsError}</p>}
                {locations && locations.length > 0 ? (
                  <div className="grid grid-cols-1 gap-4">
                    {locations.map((loc, index) => {
                      const parsed = parseWarehouseCode(loc.warehouse_code);
                      return (
                        <div key={index} className="bg-gray-800/50 border border-gray-700/50 p-4 rounded-xl flex flex-col items-center justify-center text-center shadow-lg">
                          {/* KARTON */}
                          <div className="mb-4">
                            <div className="text-xs text-gray-500 uppercase tracking-widest mb-1 font-semibold">Karton</div>
                            <div className="text-4xl font-bold text-white tracking-tight">{parsed?.karton || '-'}</div>
                          </div>
                          
                          {/* RZĄD & POZYCJA row */}
                          <div className="flex w-full justify-center gap-8 border-t border-white/10 pt-4">
                            <div>
                              <div className="text-xs text-gray-500 uppercase tracking-widest mb-1 font-semibold">Rząd</div>
                              <div className="text-2xl font-bold text-cyan-400">{parsed?.rzad || '-'}</div>
                            </div>
                            <div>
                              <div className="text-xs text-gray-500 uppercase tracking-widest mb-1 font-semibold">Pozycja</div>
                              <div className="text-2xl font-bold text-cyan-400">{parsed?.pozycja || '-'}</div>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  !isLoadingLocations && !locationsError && (
                    <div className="p-3 rounded-lg bg-gray-800/50 border border-yellow-600/50 text-center">
                      <p className="font-bold text-yellow-400">Karton Premium</p>
                      <p className="text-xs text-gray-500 mt-1">Brak przypisanej lokalizacji</p>
                    </div>
                  )
                )}
              </div>
            </div>
          )}
        </div>
        <div className="flex items-center justify-end p-4 border-t border-white/10 space-x-4">
          {isEditMode ? (
            <>
              <button type="button" onClick={() => setIsEditMode(false)} className="rounded-md py-2 px-4 text-sm font-medium text-gray-300 hover:bg-gray-700">
                Anuluj
              </button>
              <button type="button" onClick={handleUpdate} disabled={isUpdating} className="flex justify-center rounded-md border border-transparent bg-primary py-2 px-4 text-sm font-medium text-white shadow-sm hover:bg-primary-dark focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 disabled:opacity-50">
                {isUpdating ? 'Zapisywanie...' : 'Zapisz zmiany'}
              </button>
            </>
          ) : (
            <button type="button" onClick={() => setIsEditMode(true)} className="flex justify-center rounded-md border border-transparent bg-primary py-2 px-4 text-sm font-medium text-white shadow-sm hover:bg-primary-dark focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2">
              Edytuj
            </button>
          )}
        </div>
      </div>
    </div>
  )
}