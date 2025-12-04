import React from 'react';

interface RowData {
  row: number;
  count: number;
  occupancy: number;
}

interface CartonData {
  carton: number;
  rows: RowData[];
}

interface StorageSummary {
  summary: CartonData[];
  total_items: number;
}

interface StorageViewProps {
  onBack: () => void;
}

const StorageView: React.FC<StorageViewProps> = ({ onBack }) => {
  const [data, setData] = React.useState<StorageSummary | null>(null);
  const [isLoading, setIsLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    const fetchData = async () => {
      try {
        setIsLoading(true);
        const response = await fetch('/api/inventory/storage_summary');
        if (!response.ok) {
          throw new Error('Network response was not ok');
        }
        const result = await response.json();
        setData(result);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, []);

  const getOccupancyColor = (occupancy: number) => {
    if (occupancy >= 0.9) return 'bg-red-600';
    if (occupancy >= 0.7) return 'bg-yellow-500';
    return 'bg-green-600';
  };

  return (
    <div className="p-4 md:p-6 bg-gray-900 text-white min-h-screen">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl md:text-3xl font-bold text-gray-100">Wizualizacja Magazynu</h1>
        <button
          onClick={onBack}
          className="bg-gray-700 hover:bg-gray-600 text-white font-bold py-2 px-4 rounded-lg transition-colors"
        >
          &larr; Powrót
        </button>
      </div>

      {isLoading && (
        <div className="flex justify-center items-center h-64">
            <div className="spinner-lg"></div>
        </div>
      )}
      {error && <p className="text-center text-red-500 text-lg">Wystąpił błąd: {error}</p>}
      
      {data && (
        <>
          <div className="mb-8 text-center bg-gray-800/50 p-4 rounded-lg shadow-lg">
            <h2 className="text-xl font-semibold text-gray-300">Podsumowanie</h2>
            <p className="text-lg">
              Całkowita liczba kart w magazynie: 
              <span className="font-bold text-primary ml-2">{data.total_items.toLocaleString('pl-PL')}</span>
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5 gap-6">
            {data.summary.map((carton) => (
              <div key={carton.carton} className="bg-gray-800 rounded-lg shadow-xl p-4 flex flex-col">
                <h3 className="text-xl font-bold mb-4 text-center text-gray-200">Karton #{carton.carton}</h3>
                <div className="flex justify-around items-end flex-grow h-72 min-h-[18rem] pt-4 gap-x-2 md:gap-x-4">
                  {carton.rows.map((row) => (
                    <div key={row.row} className="flex flex-col items-center w-12 group relative">
                      <div className="w-full h-full bg-gray-700/50 rounded-lg overflow-hidden flex flex-col justify-end shadow-inner">
                        <div
                          className={`transition-all duration-700 ease-out ${getOccupancyColor(row.occupancy)}`}
                          style={{ height: `${row.occupancy * 100}%` }}
                        ></div>
                      </div>
                      <span className="mt-2 text-sm font-bold text-gray-300">{row.row}</span>
                      {/* Tooltip */}
                      <div className="absolute bottom-full mb-3 w-max px-3 py-1.5 bg-gray-900 border border-gray-700 text-white text-xs rounded-md opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none shadow-lg">
                        Zapełnienie: {row.count} / {row.capacity} ({Math.round(row.occupancy * 100)}%)
                        <svg className="absolute text-gray-900 h-2 w-full left-0 top-full" x="0px" y="0px" viewBox="0 0 255 255">
                          <polygon className="fill-current" points="0,0 127.5,127.5 255,0"/>
                        </svg>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
};

export default StorageView;
