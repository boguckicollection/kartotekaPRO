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

const ProgressBar: React.FC<{ value: number }> = ({ value }) => {
  const percentage = Math.round(value * 100);
  let colorClass = 'bg-green-500';
  if (percentage > 75) {
    colorClass = 'bg-yellow-500';
  }
  if (percentage > 90) {
    colorClass = 'bg-red-500';
  }

  return (
    <div className="w-full bg-gray-700 rounded-full h-4">
      <div
        className={`h-4 rounded-full ${colorClass} transition-all duration-500`}
        style={{ width: `${percentage}%` }}
      ></div>
    </div>
  );
};

const StorageView: React.FC<{ apiBase: string }> = ({ apiBase }) => {
  const [summary, setSummary] = useState<StorageSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSummary = async () => {
    setIsLoading(true);
    try {
      const res = await fetch(`${apiBase}/inventory/storage_summary`);
      if (!res.ok) {
        throw new Error('Failed to fetch storage summary');
      }
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
    return <div className="text-center text-white">Loading storage summary...</div>;
  }

  if (error) {
    return <div className="text-center text-red-500">Error: {error}</div>;
  }

  if (!summary) {
    return <div className="text-center text-white">No storage summary available.</div>;
  }
  
  const sortedBoxes = Object.entries(summary.boxes).sort(([keyA], [keyB]) => {
    const numA = parseInt(keyA.replace('K','').replace('P', '100'));
    const numB = parseInt(keyB.replace('K','').replace('P', '100'));
    return numA - numB;
  });


  return (
    <div className="p-4 md:p-6 text-white">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Podsumowanie Magazynu</h1>
        <button onClick={fetchSummary} className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-md hover:bg-indigo-700">
          Odśwież
        </button>
      </div>

      {/* Overall Summary */}
      <div className="p-4 bg-gray-800 rounded-lg mb-6">
        <h2 className="text-xl font-semibold mb-3">Całkowite zapełnienie</h2>
        <div className="grid grid-cols-3 gap-4 text-center">
          <div>
            <div className="text-3xl font-bold">{summary.total_used}</div>
            <div className="text-sm text-gray-400">Zajęte</div>
          </div>
          <div>
            <div className="text-3xl font-bold">{summary.total_free}</div>
            <div className="text-sm text-gray-400">Wolne</div>
          </div>
          <div>
            <div className="text-3xl font-bold">{summary.total_capacity}</div>
            <div className="text-sm text-gray-400">Pojemność</div>
          </div>
        </div>
        <div className="mt-4">
          <ProgressBar value={summary.total_occupancy} />
          <div className="text-center text-sm mt-1">{`${(summary.total_occupancy * 100).toFixed(2)}%`}</div>
        </div>
      </div>

      {/* Boxes Breakdown */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {sortedBoxes.map(([boxKey, box]) => (
          <div key={boxKey} className="p-4 bg-gray-800 rounded-lg">
            <h3 className="text-lg font-bold mb-3">{`Karton ${boxKey.replace('K','').replace('P', 'PREMIUM')}`}</h3>
            <div className="flex justify-between items-center mb-2 text-sm">
              <span>{`${box.used} / ${box.capacity}`}</span>
              <span>{`${(box.occupancy * 100).toFixed(1)}%`}</span>
            </div>
            <ProgressBar value={box.occupancy} />

            <div className="mt-4 space-y-2">
              {Object.entries(box.rows).map(([rowKey, row]) => (
                <div key={rowKey}>
                  <h4 className="text-sm font-semibold text-gray-400">{`Rząd ${rowKey}`}</h4>
                  <div className="flex justify-between items-center text-xs">
                    <span>{`${row.used} / ${row.capacity}`}</span>
                    <span>{`${(row.occupancy * 100).toFixed(1)}%`}</span>
                  </div>
                  <ProgressBar value={row.occupancy} />
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default StorageView;
