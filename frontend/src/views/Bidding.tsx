import React, { useState } from 'react'

type Auction = {
  name: string
  number: string
  price: number
  step: number
  leader?: string
  timeLeft?: number
  image?: string
}

type Props = {
  initial?: Auction | null
  queue?: { name: string; number: string }[]
}

export default function BiddingView({ initial = null, queue: q = [] }: Props) {
  const [auction, setAuction] = useState<Auction | null>(initial)
  const [queue, setQueue] = useState(q)
  const [form, setForm] = useState({ name: '', number: '', start: 10, step: 1 })

  return (
    <div className="font-display">
      <header className="flex items-center justify-between whitespace-nowrap border-b border-gray-800 px-2 md:px-6 py-3">
        <div className="flex items-center gap-3 text-white">
          <span className="material-symbols-outlined text-primary">gavel</span>
          <h2 className="text-lg font-bold">Licytacje</h2>
        </div>
        <div className="flex gap-2">
          <button className="rounded-lg h-10 px-4 bg-primary text-white text-sm font-bold" onClick={() => {/* TODO: persist queue */}}>Zapisz kolejkę</button>
        </div>
      </header>

      <main className="p-4 md:p-6 grid gap-6 lg:grid-cols-3">
        <section className="rounded-xl p-4 bg-[#1f2937] border border-white/10 lg:col-span-2">
          <h3 className="text-white font-semibold mb-3">Aktualna aukcja</h3>
          {!auction ? (
            <div className="text-gray-400">Brak aktywnej aukcji</div>
          ) : (
            <div className="grid gap-4 md:grid-cols-[180px_1fr]">
              <div>
                {auction.image ? (
                  <img src={auction.image} alt={auction.name} className="w-[180px] h-[240px] object-cover rounded" />
                ) : (
                  <div className="w-[180px] h-[240px] border border-white/10 rounded flex items-center justify-center text-gray-500">Brak obrazu</div>
                )}
              </div>
              <div className="grid gap-2">
                <div className="text-white text-xl font-bold">{auction.name} ({auction.number})</div>
                <div className="text-gray-300">Cena: <span className="text-white font-bold">{auction.price.toFixed(2)} PLN</span></div>
                <div className="text-gray-300">Prowadzi: <span className="text-white">{auction.leader || '—'}</span></div>
                <div className="text-gray-300">Kwota przebicia: <span className="text-white">{auction.step.toFixed(2)} PLN</span></div>
                <div className="text-gray-300">Pozostało: <span className="text-white">{auction.timeLeft ?? 0}s</span></div>
                <div className="flex gap-2 mt-2">
                  <button className="rounded-lg h-10 px-4 bg-[#283039] text-white text-sm font-bold" onClick={() => setAuction(a => a ? { ...a, price: a.price + a.step } : a)}>Przebij +</button>
                  <button className="rounded-lg h-10 px-4 bg-primary text-white text-sm font-bold" onClick={() => setAuction(a => a ? { ...a, leader: 'YOU' } : a)}>Ustaw prowadzącego</button>
                  <button className="rounded-lg h-10 px-4 bg-red-600 text-white text-sm font-bold" onClick={() => setAuction(null)}>Zakończ</button>
                </div>
              </div>
            </div>
          )}
        </section>

        <section className="rounded-xl p-4 bg-[#1f2937] border border-white/10">
          <h3 className="text-white font-semibold mb-3">Kolejka aukcji</h3>
          <div className="grid gap-2 mb-4">
            {queue.length === 0 && <div className="text-gray-400">Kolejka jest pusta</div>}
            {queue.map((x, i) => (
              <div key={`${x.name}-${x.number}-${i}`} className="flex items-center justify-between rounded-lg border border-white/10 px-3 py-2">
                <div className="text-white">{x.name} ({x.number})</div>
                <div className="flex gap-2">
                  <button className="text-sm text-primary" onClick={() => setAuction({ name: x.name, number: x.number, price: form.start, step: form.step })}>Start</button>
                  <button className="text-sm text-red-400" onClick={() => setQueue(q => q.filter((_, idx) => idx !== i))}>Usuń</button>
                </div>
              </div>
            ))}
          </div>
          <div className="grid gap-2">
            <div className="grid grid-cols-2 gap-2">
              <input placeholder="Nazwa karty" className="rounded-md border border-gray-700 bg-[#101922] text-white px-3 py-2" value={form.name} onChange={e=>setForm(f=>({...f, name:e.target.value}))} />
              <input placeholder="Numer" className="rounded-md border border-gray-700 bg-[#101922] text-white px-3 py-2" value={form.number} onChange={e=>setForm(f=>({...f, number:e.target.value}))} />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <input type="number" step="0.01" placeholder="Start [PLN]" className="rounded-md border border-gray-700 bg-[#101922] text-white px-3 py-2" value={form.start} onChange={e=>setForm(f=>({...f, start: Number(e.target.value)}))} />
              <input type="number" step="0.01" placeholder="Przebicie [PLN]" className="rounded-md border border-gray-700 bg-[#101922] text-white px-3 py-2" value={form.step} onChange={e=>setForm(f=>({...f, step: Number(e.target.value)}))} />
            </div>
            <div className="flex gap-2">
              <button className="rounded-lg h-10 px-4 bg-primary text-white text-sm font-bold" onClick={() => { if (!form.name || !form.number) return; setQueue(q => [...q, { name: form.name, number: form.number }]) }}>Dodaj do kolejki</button>
              <button className="rounded-lg h-10 px-4 bg-[#283039] text-white text-sm font-bold" onClick={() => setQueue([])}>Wyczyść</button>
            </div>
          </div>
        </section>
      </main>
    </div>
  )
}

