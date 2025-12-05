import React, { useState, useEffect } from 'react'

type Auction = {
  id: number
  title: string
  description?: string
  current_price: number
  start_price: number
  min_increment: number
  buyout_price?: number
  status: 'draft' | 'active' | 'ended' | 'cancelled'
  end_time: string
  start_time: string
  winner_kartoteka_user_id?: number
  image_url?: string
  bids?: any[]
  bid_count?: number
  time_remaining?: number
}

type Props = {
  apiBase: string
}

type ViewMode = 'menu' | 'create' | 'list'

export default function BiddingView({ apiBase }: Props) {
  const [viewMode, setViewMode] = useState<ViewMode>('menu')
  const [auctions, setAuctions] = useState<Auction[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [refreshKey, setRefreshKey] = useState(0)
  
  // Create Form State
  const [searchName, setSearchName] = useState('')
  const [searchNumber, setSearchNumber] = useState('')
  const [isSearching, setIsSearching] = useState(false)
  
  const [newTitle, setNewTitle] = useState('')
  const [newPrice, setNewPrice] = useState(10)
  const [newIncrement, setNewIncrement] = useState(5)
  
  // Card Details (Auto-filled)
  const [cardName, setCardName] = useState('')
  const [cardNumber, setCardNumber] = useState('')
  const [cardSet, setCardSet] = useState('')
  const [marketPrice, setMarketPrice] = useState<number | undefined>(undefined)
  const [mainImageUrl, setMainImageUrl] = useState('')
  
  // Duration
  const [durationDays, setDurationDays] = useState(7)
  const [durationHours, setDurationHours] = useState(0)
  const [durationMinutes, setDurationMinutes] = useState(0)

  // Images
  const [additionalImages, setAdditionalImages] = useState<string[]>([])
  const [uploadingImage, setUploadingImage] = useState(false)

  // List View State
  const [listTab, setListTab] = useState<'active' | 'history'>('active')

  useEffect(() => {
    if (viewMode === 'list') {
      loadAuctions()
    }
  }, [viewMode, refreshKey, listTab])

  const loadAuctions = async () => {
    setLoading(true)
    try {
      // Filter by status based on tab
      const statusFilter = listTab === 'active' ? 'active' : ''
      const url = statusFilter 
        ? `${apiBase}/auctions/?status=active&limit=100` 
        : `${apiBase}/auctions/?limit=100` // Fetch all for history, sort locally
        
      const res = await fetch(url)
      if (!res.ok) throw new Error('Failed to fetch auctions')
      const data = await res.json()
      
      let items = data.items || []
      
      // Client-side filtering for History tab (ended/cancelled)
      if (listTab === 'history') {
        items = items.filter((a: Auction) => a.status === 'ended' || a.status === 'cancelled')
      }

      setAuctions(items)
    } catch (err: any) {
      console.error(err)
      setError("Błąd pobierania aukcji")
    } finally {
      setLoading(false)
    }
  }

  const handleCardSearch = async () => {
    if (!searchName) return
    setIsSearching(true)
    setError(null)
    
    try {
        const response = await fetch(`${apiBase}/pricing/manual_search`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: searchName, number: searchNumber }),
        });

        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.error || 'Nie znaleziono karty');
        }

        const data = await response.json();
        const card = data.card;
        
        if (card) {
            setCardName(card.name || '')
            setCardNumber(card.number || '')
            // Backend returns 'set' for set name/code
            const setVal = card.set || card.set_code || ''
            setCardSet(setVal)
            // Backend returns 'image' for image url
            setMainImageUrl(card.image || card.image_url || card.image_small || '')
            
            // Pricing is in data.pricing
            if (data.pricing && data.pricing.price_pln_final) {
                setMarketPrice(data.pricing.price_pln_final)
            }
            
            // Use local variables to set title immediately
            const t_name = card.name || '';
            const t_num = card.number ? `#${card.number}` : '';
            setNewTitle(`${t_name} ${setVal} ${t_num}`.trim())
        }
    } catch (err: any) {
        setError(err.message)
    } finally {
        setIsSearching(false)
    }
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files || files.length === 0) return

    setUploadingImage(true)
    try {
        const formData = new FormData()
        // Upload one by one or bulk depending on backend. We made single file endpoint.
        // Let's upload sequentially.
        const newUrls: string[] = []
        
        for (let i = 0; i < files.length; i++) {
            const fd = new FormData()
            fd.append('file', files[i])
            
            const res = await fetch(`${apiBase}/auctions/upload`, {
                method: 'POST',
                body: fd
            })
            
            if (res.ok) {
                const data = await res.json()
                newUrls.push(data.url)
            }
        }
        
        setAdditionalImages([...additionalImages, ...newUrls])
    } catch (err) {
        setError("Błąd wgrywania plików")
    } finally {
        setUploadingImage(false)
        // Reset input
        e.target.value = ''
    }
  }

  const handleCreateAuction = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    try {
      const startTime = new Date()
      const totalMinutes = (durationDays * 24 * 60) + (durationHours * 60) + durationMinutes
      if (totalMinutes <= 0) throw new Error("Czas trwania musi być większy niż 0")
      
      const endTime = new Date(startTime.getTime() + totalMinutes * 60000)

      // Build structured description from card data
      const description = `
**Szczegóły Karty**
- Nazwa: ${cardName}
- Numer: ${cardNumber}
- Set: ${cardSet}
- Cena Rynkowa: ${marketPrice ? marketPrice + ' PLN' : 'Nie podano'}

**Dodatkowe Skany**
${additionalImages.map(url => `![Skan](${url})`).join('\n')}
      `.trim()

      const payload = {
        title: newTitle,
        description: description,
        image_url: mainImageUrl,
        start_price: newPrice,
        min_increment: newIncrement,
        buyout_price: null,
        start_time: startTime.toISOString(),
        end_time: endTime.toISOString(),
        status: 'active'
      }

      const res = await fetch(`${apiBase}/auctions/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Failed to create auction')
      }

      // Reset and go to list
      resetForm()
      setViewMode('list')
      setListTab('active')
      setRefreshKey(k => k + 1)
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const resetForm = () => {
      setNewTitle('')
      setNewPrice(10)
      setCardName('')
      setCardNumber('')
      setCardSet('')
      setMarketPrice(undefined)
      setMainImageUrl('')
      setAdditionalImages([])
      setSearchName('')
      setSearchNumber('')
  }

  const handleCancelAuction = async (id: number) => {
    if (!confirm('Czy na pewno chcesz anulować tę aukcję?')) return
    try {
      const res = await fetch(`${apiBase}/auctions/${id}/cancel`, { method: 'POST' })
      if (!res.ok) throw new Error('Failed to cancel')
      setRefreshKey(k => k + 1)
    } catch (err: any) {
      alert(err.message)
    }
  }

  const formatTimeLeft = (endTimeStr: string) => {
    const end = new Date(endTimeStr).getTime()
    const now = new Date().getTime()
    const diff = end - now
    
    if (diff <= 0) return "Zakończona"
    
    const minutes = Math.floor(diff / 60000)
    const seconds = Math.floor((diff % 60000) / 1000)
    
    if (minutes > 60) {
       const hours = Math.floor(minutes / 60)
       return `${hours}h ${minutes % 60}m`
    }
    return `${minutes}m ${seconds}s`
  }

  // --- RENDERERS ---

  const renderMenu = () => (
    <div className="grid md:grid-cols-2 gap-6 mt-8 max-w-4xl mx-auto">
        <button 
            onClick={() => setViewMode('create')}
            className="group relative bg-slate-900 hover:bg-slate-800 p-8 rounded-2xl border border-slate-800 hover:border-slate-700 transition-all shadow-xl hover:shadow-2xl flex flex-col items-center justify-center text-center gap-4 h-64"
        >
            <div className="w-20 h-20 bg-emerald-500/10 rounded-full flex items-center justify-center group-hover:scale-110 transition-transform border border-emerald-500/20">
                <span className="material-symbols-outlined text-5xl text-emerald-400">add_circle</span>
            </div>
            <div>
                <h3 className="text-2xl font-bold text-white mb-2">Nowa Licytacja</h3>
                <p className="text-slate-400 text-sm max-w-xs mx-auto">Utwórz nową aukcję, wyszukaj kartę z API i dodaj własne skany.</p>
            </div>
        </button>

        <button 
            onClick={() => setViewMode('list')}
            className="group relative bg-slate-900 hover:bg-slate-800 p-8 rounded-2xl border border-slate-800 hover:border-slate-700 transition-all shadow-xl hover:shadow-2xl flex flex-col items-center justify-center text-center gap-4 h-64"
        >
            <div className="w-20 h-20 bg-blue-500/10 rounded-full flex items-center justify-center group-hover:scale-110 transition-transform border border-blue-500/20">
                <span className="material-symbols-outlined text-5xl text-blue-400">list_alt</span>
            </div>
            <div>
                <h3 className="text-2xl font-bold text-white mb-2">Przeglądaj Aukcje</h3>
                <p className="text-slate-400 text-sm max-w-xs mx-auto">Zarządzaj aktywnymi licytacjami oraz przeglądaj historię zakończonych.</p>
            </div>
        </button>
    </div>
  )

  const renderCreate = () => (
    <div className="max-w-5xl mx-auto">
        <button onClick={() => setViewMode('menu')} className="mb-6 flex items-center text-slate-400 hover:text-white transition-colors text-sm font-medium">
            <span className="material-symbols-outlined mr-2">arrow_back</span> Wróć do menu
        </button>

        <div className="bg-slate-900 rounded-2xl p-6 md:p-8 border border-slate-800 shadow-xl">
            <h2 className="text-2xl font-bold text-white mb-8 flex items-center gap-3">
                <div className="p-2 bg-indigo-500/10 rounded-lg border border-indigo-500/20">
                    <span className="material-symbols-outlined text-indigo-400">gavel</span>
                </div>
                Nowa Licytacja
            </h2>

            {/* 1. Search Section */}
            <div className="bg-slate-950/50 p-6 rounded-xl border border-slate-800/50 mb-8">
                <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-4 flex items-center gap-2">
                    <span className="w-5 h-5 rounded-full bg-slate-800 flex items-center justify-center text-[10px] text-white">1</span>
                    Znajdź Kartę
                </h3>
                <div className="flex gap-3">
                    <div className="flex-1 relative">
                        <input 
                            type="text" 
                            value={searchName}
                            onChange={e => setSearchName(e.target.value)}
                            placeholder="Nazwa karty (np. Charizard)"
                            className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-10 pr-4 py-2.5 text-white focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 focus:outline-none transition-all placeholder:text-slate-600"
                        />
                        <span className="material-symbols-outlined absolute left-3 top-2.5 text-slate-600 text-[20px]">search</span>
                    </div>
                    <input 
                        type="text" 
                        value={searchNumber}
                        onChange={e => setSearchNumber(e.target.value)}
                        placeholder="Numer (opc.)"
                        className="w-32 bg-slate-950 border border-slate-800 rounded-lg px-4 py-2.5 text-white focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 focus:outline-none transition-all placeholder:text-slate-600"
                    />
                    <button 
                        onClick={handleCardSearch}
                        disabled={isSearching || !searchName}
                        className="bg-indigo-600 hover:bg-indigo-500 text-white px-6 rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                    >
                        {isSearching ? <span className="animate-spin material-symbols-outlined text-sm">progress_activity</span> : 'Szukaj'}
                    </button>
                </div>
                {error && <div className="text-red-400 text-sm mt-3 flex items-center gap-2 bg-red-500/10 p-3 rounded-lg border border-red-500/20"><span className="material-symbols-outlined text-sm">error</span> {error}</div>}
            </div>

            <form onSubmit={handleCreateAuction}>
                <div className="grid md:grid-cols-2 gap-8">
                    {/* Left Col: Image */}
                    <div>
                        <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-4 flex items-center gap-2">
                            <span className="w-5 h-5 rounded-full bg-slate-800 flex items-center justify-center text-[10px] text-white">2</span>
                            Grafika Główna
                        </h3>
                        <div className="aspect-[3/4] bg-slate-950 rounded-xl border-2 border-dashed border-slate-800 flex items-center justify-center overflow-hidden relative group hover:border-slate-700 transition-colors">
                            {mainImageUrl ? (
                                <img src={mainImageUrl} alt="Main" className="w-full h-full object-contain p-4" />
                            ) : (
                                <div className="text-center text-slate-600">
                                    <span className="material-symbols-outlined text-4xl block mb-2 opacity-50">image</span>
                                    <span className="text-sm">Brak grafiki</span>
                                </div>
                            )}
                        </div>
                        <div className="mt-4">
                            <label className="text-xs text-slate-500 mb-1.5 block">URL Obrazka</label>
                            <input 
                                type="text"
                                value={mainImageUrl}
                                onChange={e => setMainImageUrl(e.target.value)}
                                placeholder="https://..."
                                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-300 focus:border-indigo-500 focus:outline-none transition-colors"
                            />
                        </div>
                    </div>

                    {/* Right Col: Details */}
                    <div className="space-y-8">
                        {/* Details */}
                        <div>
                            <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-4 flex items-center gap-2">
                                <span className="w-5 h-5 rounded-full bg-slate-800 flex items-center justify-center text-[10px] text-white">3</span>
                                Szczegóły Aukcji
                            </h3>
                            <div className="space-y-4">
                                <div>
                                    <label className="text-xs text-slate-400 mb-1.5 block font-medium">Tytuł Aukcji</label>
                                    <input 
                                        type="text" 
                                        value={newTitle}
                                        onChange={e => setNewTitle(e.target.value)}
                                        placeholder="np. Charizard Base Set Holo #4"
                                        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-3 text-white font-bold text-lg focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 focus:outline-none transition-all placeholder:text-slate-700 placeholder:font-normal"
                                        required
                                    />
                                </div>
                                <div className="grid grid-cols-2 gap-4">
                                    <div>
                                        <label className="text-xs text-slate-500 mb-1.5 block">Nazwa Karty</label>
                                        <input 
                                            type="text" value={cardName} onChange={e => setCardName(e.target.value)}
                                            placeholder="Nazwa" className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-300 text-sm focus:border-indigo-500 focus:outline-none"
                                        />
                                    </div>
                                    <div>
                                        <label className="text-xs text-slate-500 mb-1.5 block">Numer</label>
                                        <input 
                                            type="text" value={cardNumber} onChange={e => setCardNumber(e.target.value)}
                                            placeholder="Numer" className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-300 text-sm focus:border-indigo-500 focus:outline-none"
                                        />
                                    </div>
                                </div>
                                <div className="grid grid-cols-2 gap-4">
                                    <div>
                                        <label className="text-xs text-slate-500 mb-1.5 block">Set / Dodatek</label>
                                        <input 
                                            type="text" value={cardSet} onChange={e => setCardSet(e.target.value)}
                                            placeholder="Set" className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-300 text-sm focus:border-indigo-500 focus:outline-none"
                                        />
                                    </div>
                                    <div>
                                        <label className="text-xs text-slate-500 mb-1.5 block">Szacowana Wartość (PLN)</label>
                                        <input 
                                            type="number" value={marketPrice || ''} onChange={e => setMarketPrice(parseFloat(e.target.value) || undefined)}
                                            placeholder="0.00" className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-300 text-sm focus:border-indigo-500 focus:outline-none"
                                        />
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Settings */}
                        <div>
                            <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-4 flex items-center gap-2">
                                <span className="w-5 h-5 rounded-full bg-slate-800 flex items-center justify-center text-[10px] text-white">4</span>
                                Parametry
                            </h3>
                            <div className="bg-slate-950/50 p-5 rounded-xl border border-slate-800/50 space-y-5">
                                <div className="grid grid-cols-2 gap-5">
                                    <div>
                                        <label className="text-[10px] text-slate-500 uppercase font-bold mb-1.5 block">Cena Startowa</label>
                                        <div className="relative">
                                            <input type="number" value={newPrice} onChange={e => setNewPrice(Number(e.target.value))} className="w-full bg-slate-900 border border-slate-700 rounded-lg pl-3 pr-8 py-2 text-white font-mono" />
                                            <span className="absolute right-3 top-2 text-slate-500 text-xs">PLN</span>
                                        </div>
                                    </div>
                                    <div>
                                        <label className="text-[10px] text-slate-500 uppercase font-bold mb-1.5 block">Min. Przebicie</label>
                                        <div className="relative">
                                            <input type="number" value={newIncrement} onChange={e => setNewIncrement(Number(e.target.value))} className="w-full bg-slate-900 border border-slate-700 rounded-lg pl-3 pr-8 py-2 text-white font-mono" />
                                            <span className="absolute right-3 top-2 text-slate-500 text-xs">PLN</span>
                                        </div>
                                    </div>
                                </div>
                                <div>
                                    <label className="text-[10px] text-slate-500 uppercase font-bold mb-1.5 block">Czas Trwania</label>
                                    <div className="grid grid-cols-3 gap-3">
                                        <div className="relative">
                                            <input type="number" value={durationDays} onChange={e => setDurationDays(Number(e.target.value))} className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2 py-2 text-white text-center" />
                                            <span className="text-[10px] text-slate-500 absolute right-2 top-2.5">dni</span>
                                        </div>
                                        <div className="relative">
                                            <input type="number" value={durationHours} onChange={e => setDurationHours(Number(e.target.value))} className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2 py-2 text-white text-center" />
                                            <span className="text-[10px] text-slate-500 absolute right-2 top-2.5">h</span>
                                        </div>
                                        <div className="relative">
                                            <input type="number" value={durationMinutes} onChange={e => setDurationMinutes(Number(e.target.value))} className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2 py-2 text-white text-center" />
                                            <span className="text-[10px] text-slate-500 absolute right-2 top-2.5">m</span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Additional Files */}
                        <div>
                            <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-4 flex items-center gap-2">
                                <span className="w-5 h-5 rounded-full bg-slate-800 flex items-center justify-center text-[10px] text-white">5</span>
                                Dodatkowe Skany
                            </h3>
                            <div className="bg-slate-950 p-6 rounded-xl border border-dashed border-slate-800 hover:border-slate-600 transition-colors relative cursor-pointer group">
                                <input 
                                    type="file" 
                                    multiple 
                                    accept="image/*"
                                    onChange={handleFileUpload}
                                    className="absolute inset-0 opacity-0 cursor-pointer z-10"
                                    disabled={uploadingImage}
                                />
                                <div className="text-center text-slate-500 group-hover:text-slate-400 transition-colors">
                                    {uploadingImage ? (
                                        <div className="flex flex-col items-center">
                                            <span className="animate-spin material-symbols-outlined text-3xl mb-2 text-indigo-500">progress_activity</span>
                                            <span>Wgrywanie...</span>
                                        </div>
                                    ) : (
                                        <div className="flex flex-col items-center gap-2">
                                            <div className="p-3 bg-slate-900 rounded-full border border-slate-800 group-hover:border-slate-700 group-hover:bg-slate-800 transition-all">
                                                <span className="material-symbols-outlined text-2xl">upload_file</span>
                                            </div>
                                            <div>
                                                <span className="text-sm font-medium text-slate-300">Kliknij lub upuść pliki tutaj</span>
                                                <p className="text-xs mt-1">PNG, JPG do 5MB</p>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </div>
                            {additionalImages.length > 0 && (
                                <div className="flex flex-wrap gap-3 mt-4">
                                    {additionalImages.map((url, i) => (
                                        <div key={i} className="relative w-20 h-20 bg-slate-950 rounded-lg border border-slate-800 overflow-hidden group">
                                            <img src={url} className="w-full h-full object-cover" />
                                            <button 
                                                type="button"
                                                onClick={() => setAdditionalImages(additionalImages.filter((_, idx) => idx !== i))}
                                                className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 flex items-center justify-center text-white transition-opacity"
                                            >
                                                <span className="material-symbols-outlined text-lg">close</span>
                                            </button>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>

                        <button 
                            type="submit" 
                            disabled={loading || uploadingImage}
                            className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-800 disabled:text-slate-500 text-white font-bold py-4 rounded-xl transition-all shadow-lg shadow-indigo-900/20 active:scale-[0.98] mt-4 flex items-center justify-center gap-2"
                        >
                            {loading ? <span className="animate-spin material-symbols-outlined">progress_activity</span> : <span className="material-symbols-outlined">rocket_launch</span>}
                            {loading ? 'Przetwarzanie...' : 'Uruchom Aukcję'}
                        </button>
                    </div>
                </div>
            </form>
        </div>
    </div>
  )

  const renderList = () => (
    <div className="max-w-6xl mx-auto">
        <div className="flex items-center justify-between mb-6">
            <button onClick={() => setViewMode('menu')} className="flex items-center text-slate-400 hover:text-white transition-colors text-sm font-medium">
                <span className="material-symbols-outlined mr-2">arrow_back</span> Menu
            </button>
            <div className="flex bg-slate-900 p-1 rounded-lg border border-slate-800">
                <button 
                    onClick={() => setListTab('active')}
                    className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all ${listTab === 'active' ? 'bg-slate-800 text-white shadow-sm border border-slate-700' : 'text-slate-500 hover:text-slate-300'}`}
                >
                    Aktywne
                </button>
                <button 
                    onClick={() => setListTab('history')}
                    className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all ${listTab === 'history' ? 'bg-slate-800 text-white shadow-sm border border-slate-700' : 'text-slate-500 hover:text-slate-300'}`}
                >
                    Historia
                </button>
            </div>
        </div>

        {loading ? (
            <div className="text-center py-12 text-slate-500 flex flex-col items-center">
                <span className="material-symbols-outlined animate-spin mb-2">progress_activity</span>
                Ładowanie...
            </div>
        ) : auctions.length === 0 ? (
            <div className="text-center py-12 text-slate-500 bg-slate-900 rounded-2xl border border-slate-800 flex flex-col items-center">
                <span className="material-symbols-outlined text-4xl mb-2 opacity-50">inbox</span>
                Brak aukcji w tej kategorii.
            </div>
        ) : (
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
                {auctions.map(auction => (
                    <div key={auction.id} className="bg-slate-900 rounded-xl border border-slate-800 overflow-hidden hover:border-slate-700 transition-all hover:shadow-lg group">
                        <div className="h-48 bg-slate-950 relative flex items-center justify-center p-4">
                            {auction.image_url ? (
                                <img src={auction.image_url} alt={auction.title} className="w-full h-full object-contain" />
                            ) : (
                                <div className="text-slate-700 flex flex-col items-center">
                                    <span className="material-symbols-outlined text-4xl mb-1">image</span>
                                    <span className="text-xs">Brak podglądu</span>
                                </div>
                            )}
                            <div className="absolute top-3 right-3 bg-black/60 backdrop-blur-sm text-white text-xs font-mono px-2 py-1 rounded border border-white/10">
                                #{auction.id}
                            </div>
                        </div>
                        <div className="p-5">
                            <h3 className="font-bold text-white mb-4 truncate text-lg" title={auction.title}>{auction.title}</h3>
                            <div className="flex justify-between items-end border-t border-slate-800 pt-4">
                                <div>
                                    <div className="text-[10px] uppercase font-bold text-slate-500 mb-0.5">Cena</div>
                                    <div className="text-xl font-bold text-emerald-400 font-mono">{auction.current_price} <span className="text-sm">PLN</span></div>
                                </div>
                                <div className="text-right">
                                    <div className="text-[10px] uppercase font-bold text-slate-500 mb-0.5">{listTab === 'active' ? 'Koniec za' : 'Zakończono'}</div>
                                    <div className="text-sm font-medium text-amber-400 font-mono">
                                        {listTab === 'active' ? formatTimeLeft(auction.end_time) : new Date(auction.end_time).toLocaleDateString()}
                                    </div>
                                </div>
                            </div>
                            
                            {listTab === 'active' && (
                                <button 
                                    onClick={() => handleCancelAuction(auction.id)}
                                    className="w-full mt-5 bg-red-500/10 hover:bg-red-500/20 text-red-400 py-2.5 rounded-lg text-sm font-medium transition-colors border border-red-500/20 flex items-center justify-center gap-2 group-hover:bg-red-500/20"
                                >
                                    <span className="material-symbols-outlined text-base">cancel</span>
                                    Anuluj Aukcję
                                </button>
                            )}
                        </div>
                    </div>
                ))}
            </div>
        )}
    </div>
  )

  return (
    <div className="font-display p-4 md:p-6">
      {/* Header only shown in menu mode or handled inside views */}
      {viewMode === 'menu' && (
          <div className="text-center mb-8">
            <h2 className="text-3xl font-bold text-white mb-2">Panel Licytacji</h2>
            <p className="text-gray-400">Zarządzaj swoimi aukcjami</p>
          </div>
      )}

      {viewMode === 'menu' && renderMenu()}
      {viewMode === 'create' && renderCreate()}
      {viewMode === 'list' && renderList()}
    </div>
  )
}
