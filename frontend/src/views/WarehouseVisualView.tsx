import React, { useEffect, useState } from 'react';

interface StorageSummary {
  total_used: number;
  total_capacity: number;
  total_free: number;
  total_occupancy: number;
  boxes: {
    [key: string]: BoxSummary;
  };
}

interface BoxSummary {
  used: number;
  capacity: number;
  free: number;
  occupancy: number;
  rows: {
    [key: string]: RowSummary;
  };
}

interface RowSummary {
  used: number;
  capacity: number;
  free: number;
  occupancy: number;
}

interface BoxDetailData {
  box_key: string;
  total_cards: number;
  total_value: number;
  sets: { [setName: string]: number };
  rows: {
    [rowNum: string]: {
      cards: number;
      value: number;
      codes: string[];
    }
  };
}

interface VerticalRowBarProps {
  rowNum: string;
  used: number;
  capacity: number;
  occupancy: number;
  index: number;
}

const VerticalRowBar: React.FC<VerticalRowBarProps> = ({ rowNum, used, capacity, occupancy, index }) => {
  const getColor = (occ: number) => {
    if (occ >= 0.9) return { bg: 'bg-red-500', from: 'rgba(239, 68, 68, 1)', to: 'rgba(220, 38, 38, 0.8)' };
    if (occ >= 0.75) return { bg: 'bg-orange-500', from: 'rgba(249, 115, 22, 1)', to: 'rgba(234, 88, 12, 0.8)' };
    if (occ >= 0.5) return { bg: 'bg-yellow-500', from: 'rgba(234, 179, 8, 1)', to: 'rgba(202, 138, 4, 0.8)' };
    return { bg: 'bg-green-500', from: 'rgba(34, 197, 94, 1)', to: 'rgba(22, 163, 74, 0.8)' };
  };

  const color = getColor(occupancy);
  const height = capacity === 500 ? 64 : 128; // Premium vs Standard

  return (
    <div 
      className="flex flex-col items-center gap-2 animate-fade-in"
      style={{ animationDelay: `${index * 100}ms` }}
    >
      {/* Label rzędu */}
      <div className="text-xs font-medium text-gray-400">R{rowNum}</div>
      
      {/* PIONOWY pasek */}
      <div 
        className="relative w-10 bg-gray-800/50 rounded-lg overflow-hidden border border-gray-700/50 backdrop-blur-sm group"
        style={{ height: `${height}px` }}
      >
        {/* Wypełnienie od DOŁU z animacją */}
        <div 
          className="absolute bottom-0 left-0 right-0 transition-all duration-1000 ease-out animate-fill-from-bottom"
          style={{ 
            height: `${occupancy * 100}%`,
            background: `linear-gradient(to top, ${color.from}, ${color.to})`,
            boxShadow: occupancy > 0 ? `0 0 10px ${color.from}` : 'none'
          }}
        />
        
        {/* Grid lines (podziałki) */}
        <div className="absolute inset-0 flex flex-col justify-between pointer-events-none">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="border-t border-gray-700/30" />
          ))}
        </div>

        {/* Tooltip hover */}
        <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity bg-black/70 backdrop-blur-sm">
          <div className="text-white text-xs font-bold text-center">
            <div>{used}</div>
            <div className="text-gray-400">/</div>
            <div>{capacity}</div>
          </div>
        </div>
      </div>
      
      {/* Liczba kart pod paskiem */}
      <div className="text-xs font-bold text-white">{used}</div>
    </div>
  );
};

interface BoxCardProps {
  boxKey: string;
  boxData: BoxSummary;
  index: number;
  onClick: () => void;
}

const BoxCard: React.FC<BoxCardProps> = ({ boxKey, boxData, index, onClick }) => {
  const isPremium = boxKey === 'KP';
  const displayName = isPremium ? 'PREMIUM' : boxKey.replace('K', '');
  const occupancyPercent = (boxData.occupancy * 100).toFixed(1);
  
  const sortedRows = Object.entries(boxData.rows).sort(([a], [b]) => parseInt(a) - parseInt(b));

  return (
    <div 
      className={`relative box-card p-4 rounded-2xl border-2 transition-all duration-300 cursor-pointer animate-fade-in ${
        isPremium 
          ? 'border-yellow-400 bg-gradient-to-br from-yellow-900/20 to-gray-900 hover:shadow-premium' 
          : 'border-gray-700 bg-gradient-to-br from-gray-800 to-gray-900 hover:border-cyan-500'
      }`}
      style={{ 
        animationDelay: `${index * 150}ms`,
        boxShadow: isPremium ? '0 8px 32px rgba(251, 191, 36, 0.15)' : '0 8px 24px rgba(0,0,0,0.4)'
      }}
      onClick={onClick}
    >
      {/* Korona dla Premium */}
      {isPremium && (
        <div className="absolute -top-3 -right-3 text-3xl filter drop-shadow-lg animate-bounce-slow">
          👑
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className={`text-lg font-bold ${isPremium ? 'text-yellow-400' : 'text-white'}`}>
          {isPremium ? '✨ PREMIUM' : `KARTON ${displayName}`}
        </h3>
        <span className={`text-sm font-semibold px-2 py-1 rounded-full ${
          boxData.occupancy >= 0.9 ? 'bg-red-500/20 text-red-400' :
          boxData.occupancy >= 0.75 ? 'bg-orange-500/20 text-orange-400' :
          boxData.occupancy >= 0.5 ? 'bg-yellow-500/20 text-yellow-400' :
          'bg-green-500/20 text-green-400'
        }`}>
          {occupancyPercent}%
        </span>
      </div>

      {/* Rzędy PIONOWE */}
      <div className="flex flex-wrap justify-center gap-3 mb-4">
        {sortedRows.map(([rowNum, row], idx) => (
          <VerticalRowBar
            key={rowNum}
            rowNum={rowNum}
            used={row.used}
            capacity={row.capacity}
            occupancy={row.occupancy}
            index={idx}
          />
        ))}
      </div>

      {/* Footer */}
      <div className="text-center pt-3 border-t border-gray-700/50">
        <div className="text-sm text-gray-400">
          <span className="font-bold text-white">{boxData.used}</span>
          <span className="mx-1">/</span>
          <span>{boxData.capacity}</span>
          <span className="ml-1">kart</span>
        </div>
      </div>

      {/* Hover effect */}
      <div className="absolute inset-0 rounded-2xl bg-gradient-to-br from-cyan-500/0 to-blue-500/0 opacity-0 group-hover:opacity-10 transition-opacity pointer-events-none" />
    </div>
  );
};

interface BoxDetailModalProps {
  boxKey: string;
  onClose: () => void;
  apiBase: string;
}

const BoxDetailModal: React.FC<BoxDetailModalProps> = ({ boxKey, onClose, apiBase }) => {
  const [data, setData] = useState<BoxDetailData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchDetails = async () => {
      try {
        const res = await fetch(`${apiBase}/inventory/box_details/${boxKey}`);
        if (res.ok) {
          setData(await res.json());
        }
      } catch (err) {
        console.error('Failed to fetch box details', err);
      } finally {
        setLoading(false);
      }
    };
    fetchDetails();
  }, [boxKey, apiBase]);

  const isPremium = boxKey === 'KP';
  const displayName = isPremium ? 'PREMIUM' : `KARTON ${boxKey.replace('K', '')}`;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in" onClick={onClose}>
      <div 
        className="bg-gradient-to-br from-gray-900 to-gray-800 rounded-2xl border-2 border-gray-700 max-w-4xl w-full max-h-[90vh] overflow-y-auto shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className={`sticky top-0 z-10 p-6 border-b backdrop-blur-sm ${
          isPremium 
            ? 'bg-gradient-to-r from-yellow-900/30 to-orange-900/30 border-yellow-700/30' 
            : 'bg-gray-900/90 border-gray-700'
        }`}>
          <div className="flex items-center justify-between">
            <h2 className={`text-2xl font-bold ${isPremium ? 'text-yellow-400' : 'text-white'}`}>
              {isPremium && '👑 '}{displayName}
            </h2>
            <button 
              onClick={onClose}
              className="text-gray-400 hover:text-white transition-colors"
            >
              <span className="material-symbols-outlined text-3xl">close</span>
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="p-6">
          {loading ? (
            <div className="text-center py-12 text-gray-400">
              <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-cyan-500 mb-4"></div>
              <p>Ładowanie szczegółów...</p>
            </div>
          ) : data ? (
            <div className="space-y-6">
              {/* Statystyki */}
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-700/50">
                  <div className="text-sm text-gray-400 mb-1">Liczba kart</div>
                  <div className="text-3xl font-bold text-white">{data.total_cards}</div>
                </div>
                <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-700/50">
                  <div className="text-sm text-gray-400 mb-1">Wartość</div>
                  <div className="text-3xl font-bold text-green-400">
                    {data.total_value.toLocaleString('pl-PL', {style: 'currency', currency: 'PLN'})}
                  </div>
                </div>
              </div>

              {/* Wykres setów - placeholder na chart.js */}
              <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-700/50">
                <h3 className="text-lg font-semibold text-white mb-3">Rozkład setów</h3>
                <div className="text-sm text-gray-400">
                  {Object.keys(data.sets).length > 0 ? (
                    <ul className="space-y-2">
                      {Object.entries(data.sets).map(([setName, count]) => (
                        <li key={setName} className="flex justify-between">
                          <span>{setName}</span>
                          <span className="font-bold text-white">{count} kart</span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-center py-4">Brak kart w tym kartonie</p>
                  )}
                </div>
              </div>

              {/* Szczegóły rzędów */}
              <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-700/50">
                <h3 className="text-lg font-semibold text-white mb-3">Szczegóły rzędów</h3>
                <div className="space-y-3">
                  {Object.entries(data.rows).map(([rowNum, rowData]) => (
                    <div key={rowNum} className="bg-gray-900/50 rounded p-3">
                      <div className="flex justify-between items-center mb-2">
                        <span className="text-sm font-semibold text-cyan-400">Rząd {rowNum}</span>
                        <span className="text-sm text-gray-400">{rowData.cards} kart</span>
                      </div>
                      {rowData.cards > 0 && (
                        <div className="text-xs text-gray-500 space-y-1">
                          <div>Wartość: {rowData.value.toFixed(2)} zł</div>
                          <div className="truncate">Kody: {rowData.codes.slice(0, 3).join(', ')}{rowData.codes.length > 3 && '...'}</div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="text-center py-12 text-gray-400">
              Brak danych dla tego kartonu
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

const WarehouseVisualView: React.FC<{ apiBase: string }> = ({ apiBase }) => {
  const [summary, setSummary] = useState<StorageSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedBox, setSelectedBox] = useState<string | null>(null);

  const fetchSummary = async () => {
    setIsLoading(true);
    try {
      const res = await fetch(`${apiBase}/inventory/storage_summary`);
      if (!res.ok) throw new Error('Failed to fetch storage summary');
      const data = await res.json();
      setSummary(data);
    } catch (err: any) {
      setError(err.message || 'An unknown error occurred');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchSummary();
  }, [apiBase]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-16 w-16 border-b-2 border-cyan-500 mb-4"></div>
          <p className="text-white text-lg">Ładowanie magazynu...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center text-red-500">
          <span className="material-symbols-outlined text-6xl mb-4">error</span>
          <p>Błąd: {error}</p>
        </div>
      </div>
    );
  }

  if (!summary) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-gray-400">Brak danych magazynu</p>
      </div>
    );
  }

  // Sortowanie: K1-K10, potem KP (Premium)
  const sortedBoxes = Object.entries(summary.boxes).sort(([keyA], [keyB]) => {
    if (keyA === 'KP') return 1;
    if (keyB === 'KP') return -1;
    const numA = parseInt(keyA.replace('K', ''));
    const numB = parseInt(keyB.replace('K', ''));
    return numA - numB;
  });

  const occupancyPercent = (summary.total_occupancy * 100).toFixed(2);

  return (
    <div className="p-2 sm:p-4 md:p-6 max-w-7xl mx-auto pb-24">
      {/* Header */}
      <div className="flex items-center justify-between mb-6 animate-fade-in">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 flex items-center justify-center bg-gradient-to-br from-cyan-500/20 to-blue-600/20 rounded-xl border border-cyan-500/30">
            <span className="material-symbols-outlined text-3xl text-cyan-400">warehouse</span>
          </div>
           <div>
            <h1 className="text-xl sm:text-2xl md:text-3xl font-bold text-white">Wizualizacja Magazynu</h1>
            <p className="text-xs sm:text-sm text-gray-400">Podgląd kartonów z zapełnieniem w czasie rzeczywistym</p>
          </div>
        </div>
        <button 
          onClick={fetchSummary} 
          className="px-4 py-2 text-sm font-medium text-white bg-gradient-to-r from-cyan-600 to-blue-600 rounded-lg hover:from-cyan-700 hover:to-blue-700 transition-all shadow-lg hover:shadow-cyan-500/50"
        >
          <span className="material-symbols-outlined text-lg">refresh</span>
        </button>
      </div>

      {/* Overall Summary */}
      <div className="bg-gradient-to-br from-gray-800 to-gray-900 rounded-2xl p-6 mb-8 border border-gray-700 shadow-2xl animate-fade-in" style={{ animationDelay: '100ms' }}>
        <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
          <span className="material-symbols-outlined text-cyan-400">analytics</span>
          Całkowite zapełnienie
        </h2>
        <div className="grid grid-cols-3 gap-4 sm:gap-6 text-center mb-4">
          <div>
            <div className="text-2xl sm:text-4xl font-bold text-green-400">{summary.total_used}</div>
            <div className="text-xs sm:text-sm text-gray-400 mt-1">Zajęte</div>
          </div>
          <div>
            <div className="text-2xl sm:text-4xl font-bold text-cyan-400">{summary.total_free}</div>
            <div className="text-xs sm:text-sm text-gray-400 mt-1">Wolne</div>
          </div>
          <div>
            <div className="text-2xl sm:text-4xl font-bold text-white">{summary.total_capacity}</div>
            <div className="text-xs sm:text-sm text-gray-400 mt-1">Pojemność</div>
          </div>
        </div>
        <div className="relative w-full h-6 bg-gray-700/50 rounded-full overflow-hidden backdrop-blur-sm">
          <div 
            className="absolute left-0 top-0 h-full bg-gradient-to-r from-green-500 to-emerald-600 transition-all duration-1000 ease-out"
            style={{ width: `${occupancyPercent}%` }}
          />
        </div>
        <div className="text-center text-sm mt-2 font-semibold text-gray-300">{occupancyPercent}% zapełnione</div>
      </div>

      {/* Boxes Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 sm:gap-6">
        {sortedBoxes.map(([boxKey, box], idx) => (
          <BoxCard
            key={boxKey}
            boxKey={boxKey}
            boxData={box}
            index={idx}
            onClick={() => setSelectedBox(boxKey)}
          />
        ))}
      </div>

      {/* Detail Modal */}
      {selectedBox && (
        <BoxDetailModal
          boxKey={selectedBox}
          onClose={() => setSelectedBox(null)}
          apiBase={apiBase}
        />
      )}

      {/* CSS Animations */}
      <style>{`
        @keyframes fade-in {
          from {
            opacity: 0;
            transform: translateY(10px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        @keyframes fill-from-bottom {
          from {
            height: 0%;
            opacity: 0;
          }
          to {
            opacity: 1;
          }
        }

        @keyframes bounce-slow {
          0%, 100% {
            transform: translateY(0);
          }
          50% {
            transform: translateY(-5px);
          }
        }

        .animate-fade-in {
          animation: fade-in 0.5s ease-out forwards;
          opacity: 0;
        }

        .animate-fill-from-bottom {
          animation: fill-from-bottom 1.2s cubic-bezier(0.4, 0, 0.2, 1);
        }

        .animate-bounce-slow {
          animation: bounce-slow 3s ease-in-out infinite;
        }

        .hover\\:shadow-premium:hover {
          box-shadow: 0 0 40px rgba(251, 191, 36, 0.4);
        }

        .box-card:hover {
          transform: translateY(-4px);
        }
      `}</style>
    </div>
  );
};

export default WarehouseVisualView;
