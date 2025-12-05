import React, { useState, useEffect } from 'react'

type KartotekaUser = {
  id: number
  kartoteka_user_id: number
  username: string
  is_active: boolean
  synced_at: string
  total_bids: number
  won_auctions: number
  total_spent: number
}

type Props = {
  apiBase: string
}

export default function UsersView({ apiBase }: Props) {
  const [users, setUsers] = useState<KartotekaUser[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadUsers()
  }, [apiBase])

  const loadUsers = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${apiBase}/auctions/users`)
      if (!res.ok) throw new Error('Failed to fetch users')
      const data = await res.json()
      setUsers(data)
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="font-display p-4 md:p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-3 text-white">
          <span className="material-symbols-outlined text-blue-400 text-3xl">group</span>
          <div>
            <h2 className="text-2xl font-bold">Użytkownicy Aplikacji</h2>
            <p className="text-gray-400 text-sm">Lista licytujących użytkowników Kartoteka App</p>
          </div>
        </div>
        <button 
          onClick={loadUsers}
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

      <div className="bg-[#1e293b] rounded-2xl border border-gray-800/50 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="bg-[#0f172a] text-gray-400 border-b border-gray-800">
                <th className="px-6 py-4 font-medium">User ID</th>
                <th className="px-6 py-4 font-medium">Nazwa Użytkownika</th>
                <th className="px-6 py-4 font-medium text-center">Liczba Ofert</th>
                <th className="px-6 py-4 font-medium text-center">Wygrane Aukcje</th>
                <th className="px-6 py-4 font-medium text-right">Suma Wydatków</th>
                <th className="px-6 py-4 font-medium text-right">Ostatnia Aktywność</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/50">
              {loading ? (
                <tr>
                  <td colSpan={6} className="px-6 py-8 text-center text-gray-500">
                    Ładowanie danych...
                  </td>
                </tr>
              ) : users.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-8 text-center text-gray-500">
                    Brak użytkowników. Użytkownicy pojawią się po złożeniu pierwszej oferty.
                  </td>
                </tr>
              ) : (
                users.map(user => (
                  <tr key={user.id} className="hover:bg-white/5 transition-colors">
                    <td className="px-6 py-4 text-gray-500">#{user.kartoteka_user_id}</td>
                    <td className="px-6 py-4">
                      <div className="font-bold text-white">{user.username}</div>
                      <div className="text-xs text-gray-500">ID lokalne: {user.id}</div>
                    </td>
                    <td className="px-6 py-4 text-center text-gray-300">
                      {user.total_bids}
                    </td>
                    <td className="px-6 py-4 text-center">
                      {user.won_auctions > 0 ? (
                        <span className="bg-emerald-500/20 text-emerald-400 px-2 py-1 rounded text-xs font-bold">
                          {user.won_auctions}
                        </span>
                      ) : (
                        <span className="text-gray-600">-</span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-right font-mono text-emerald-400 font-bold">
                      {user.total_spent.toFixed(2)} PLN
                    </td>
                    <td className="px-6 py-4 text-right text-gray-500 text-xs">
                      {new Date(user.synced_at).toLocaleString()}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
