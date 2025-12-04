import React, { useState, useEffect } from 'react';

type Props = {
  onSessionStarted: (session: { session_id: number; starting_warehouse_code: string | null }) => void;
  apiBase: string;
};

export default function StartSessionView({ onSessionStarted, apiBase }: Props) {
  const [box, setBox] = useState('');
  const [row, setRow] = useState('');
  const [pos, setPos] = useState('');
  
  const [code, setCode] = useState('');
  const [validation, setValidation] = useState<{ status: string; message?: string; next_available?: string } | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [debouncedCode, setDebouncedCode] = useState(code);

  // Combine box, row, pos into a single code string
  useEffect(() => {
    if (box && row && pos) {
      const paddedPos = pos.padStart(4, '0');
      const boxPart = box.toUpperCase() === 'P' ? 'P' : (box ? `${box}`: '');
      setCode(`K${boxPart}-R${row}-P${paddedPos}`);
    } else {
      setCode('');
    }
  }, [box, row, pos]);


  useEffect(() => {
    const handler = setTimeout(() => {
      // Only set the debounced code if all parts are present, or if all are empty
      if ((box && row && pos) || (!box && !row && !pos)) {
        setDebouncedCode(code);
      } else {
        // If the code is partial, don't trigger validation
        setDebouncedCode('');
        setValidation(null);
      }
    }, 500);

    return () => {
      clearTimeout(handler);
    };
  }, [code, box, row, pos]);

  useEffect(() => {
    if (debouncedCode) {
      validateCode(debouncedCode);
    } else {
      setValidation(null);
    }
  }, [debouncedCode, apiBase]);

  const validateCode = async (codeToValidate: string) => {
    try {
      const res = await fetch(`${apiBase}/inventory/check_code`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: codeToValidate }),
      });
      const data = await res.json();
      if (res.ok) {
        setValidation({ status: 'available' });
      } else {
        setValidation({ status: data.status || 'error', message: data.message, next_available: data.next_available });
      }
    } catch (e) {
      setValidation({ status: 'error', message: 'Network error' });
    }
  };

  const handleStartSession = async () => {
    setIsLoading(true);
    try {
      // Use the combined code state for starting the session
      const res = await fetch(`${apiBase}/sessions/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ starting_warehouse_code: code || null }),
      });
      const sessionData = await res.json();
      if (res.ok) {
        onSessionStarted(sessionData);
      } else {
        setValidation({ status: 'error', message: sessionData.error || 'Failed to start session.' });
      }
    } catch (e) {
      setValidation({ status: 'error', message: 'Network error.' });
    } finally {
      setIsLoading(false);
    }
  };

  const handleFetchNextCode = async () => {
    try {
      const res = await fetch(`${apiBase}/inventory/next_code`);
      const data = await res.json();
      if (res.ok && data.code) {
        // Parse K<box>-R<row>-P<pos>
        const match = data.code.match(/K(P|\d+)-R(\d+)-P(\d+)/);
        if (match) {
          setBox(match[1]);
          setRow(match[2]);
          setPos(match[3]);
        }
      }
    } catch (e) {
      // ignore
    }
  }

  // A code is valid if it's empty OR if it's filled and the backend says it's available.
  const isCodeValidForStart = !code || validation?.status === 'available';


  return (
    <div className="flex flex-col items-center justify-center min-h-[80vh] p-4">
      {/* Main Card with Glow Effect */}
      <div className="relative w-full max-w-md">
        {/* Glow background */}
        <div className="absolute -inset-1 bg-gradient-to-r from-cyan-500/20 via-blue-500/20 to-purple-500/20 rounded-2xl blur-xl opacity-75"></div>
        
        {/* Card Content */}
        <div className="relative w-full p-6 space-y-6 bg-[#0f172a] border border-gray-700/50 rounded-2xl shadow-2xl backdrop-blur-sm">
          
          {/* Header with Icon */}
          <div className="flex flex-col items-center text-center">
            <div className="relative mb-4">
              {/* Icon glow */}
              <div className="absolute inset-0 bg-cyan-500/30 rounded-full blur-xl"></div>
              <div className="relative w-20 h-20 flex items-center justify-center bg-gradient-to-br from-cyan-500/20 to-blue-600/20 rounded-full border border-cyan-500/30">
                <span className="material-symbols-outlined text-4xl text-cyan-400">inventory_2</span>
              </div>
            </div>
            <h2 className="text-2xl font-bold text-white tracking-wide">Rozpocznij Sesję</h2>
            <p className="text-sm text-gray-400 mt-2 max-w-xs">
              Ustaw lokalizację startową dla numeracji magazynowej
            </p>
          </div>

          {/* Divider */}
          <div className="h-px bg-gradient-to-r from-transparent via-gray-600 to-transparent"></div>

          {/* Location Input Section */}
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <label className="text-sm font-medium text-gray-300 flex items-center gap-2">
                <span className="material-symbols-outlined text-lg text-cyan-400">location_on</span>
                Lokalizacja
              </label>
              <button 
                onClick={handleFetchNextCode} 
                className="flex items-center gap-1 text-xs text-cyan-400 hover:text-cyan-300 font-medium transition-colors"
              >
                <span className="material-symbols-outlined text-sm">auto_awesome</span>
                Następna wolna
              </button>
            </div>

            {/* Input Grid */}
            <div className="grid grid-cols-3 gap-3">
              {/* Box Input */}
              <div className="space-y-1">
                <label className="text-xs text-gray-500 uppercase tracking-wider">Karton</label>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-cyan-400 font-bold text-sm">K</span>
                  <input
                    type="text"
                    value={box}
                    onChange={(e) => setBox(e.target.value.toUpperCase())}
                    placeholder="1-10 lub P"
                    maxLength={3}
                    className="w-full pl-8 pr-3 py-3 text-white placeholder-gray-600 bg-gray-800/50 border border-gray-600/50 rounded-lg shadow-inner focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500/50 transition-all text-center font-mono text-lg"
                  />
                </div>
              </div>

              {/* Row Input */}
              <div className="space-y-1">
                <label className="text-xs text-gray-500 uppercase tracking-wider">Rząd</label>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-cyan-400 font-bold text-sm">R</span>
                  <input
                    type="number"
                    value={row}
                    onChange={(e) => setRow(e.target.value)}
                    placeholder="4"
                    min="1"
                    max="9"
                    className="w-full pl-8 pr-3 py-3 text-white placeholder-gray-600 bg-gray-800/50 border border-gray-600/50 rounded-lg shadow-inner focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500/50 transition-all text-center font-mono text-lg [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                  />
                </div>
              </div>

              {/* Position Input */}
              <div className="space-y-1">
                <label className="text-xs text-gray-500 uppercase tracking-wider">Pozycja</label>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-cyan-400 font-bold text-sm">P</span>
                  <input
                    type="number"
                    value={pos}
                    onChange={(e) => setPos(e.target.value)}
                    placeholder="0001"
                    min="1"
                    className="w-full pl-8 pr-3 py-3 text-white placeholder-gray-600 bg-gray-800/50 border border-gray-600/50 rounded-lg shadow-inner focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500/50 transition-all text-center font-mono text-lg [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                  />
                </div>
              </div>
            </div>

            {/* Premium Box Hint */}
            <div className="flex items-center justify-center gap-2 text-xs text-gray-400">
              <span className="material-symbols-outlined text-sm text-yellow-400">info</span>
              <span>Dla kartonu premium wpisz <span className="font-mono font-bold text-yellow-400">P</span> w polu Karton</span>
            </div>

            {/* Generated Code Display */}
            {code && (
              <div className="flex items-center justify-center gap-2 py-3 px-4 bg-gray-800/30 rounded-lg border border-gray-700/50">
                <span className="material-symbols-outlined text-gray-500">tag</span>
                <span className="font-mono text-lg text-white tracking-wider">{code}</span>
              </div>
            )}
            
            {/* Validation Messages */}
            <div className="h-6 flex items-center justify-center">
              {validation && (
                <div className="flex items-center gap-2 text-sm">
                  {validation.status === 'available' && (
                    <>
                      <span className="material-symbols-outlined text-green-400 text-lg">check_circle</span>
                      <span className="text-green-400">Lokalizacja dostępna</span>
                    </>
                  )}
                  {validation.status === 'taken' && (
                    <>
                      <span className="material-symbols-outlined text-amber-400 text-lg">warning</span>
                      <span className="text-amber-400">
                        Zajęta. Następna: <span className="font-mono font-bold">{validation.next_available}</span>
                      </span>
                    </>
                  )}
                  {validation.status === 'invalid_format' && (
                    <>
                      <span className="material-symbols-outlined text-red-400 text-lg">error</span>
                      <span className="text-red-400">{validation.message || 'Nieprawidłowy format'}</span>
                    </>
                  )}
                  {validation.status === 'error' && (
                    <>
                      <span className="material-symbols-outlined text-red-400 text-lg">error</span>
                      <span className="text-red-400">{validation.message || 'Wystąpił błąd'}</span>
                    </>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Divider */}
          <div className="h-px bg-gradient-to-r from-transparent via-gray-600 to-transparent"></div>

          {/* Action Button */}
          <button
            onClick={handleStartSession}
            disabled={!isCodeValidForStart || isLoading}
            className="relative w-full group"
          >
            {/* Button glow on hover */}
            <div className="absolute -inset-0.5 bg-gradient-to-r from-cyan-500 to-blue-500 rounded-xl blur opacity-30 group-hover:opacity-60 transition duration-300 group-disabled:opacity-0"></div>
            
            <div className={`relative flex items-center justify-center gap-3 w-full px-6 py-4 font-bold text-white rounded-xl transition-all duration-300
              ${isCodeValidForStart && !isLoading 
                ? 'bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 shadow-lg shadow-cyan-500/25' 
                : 'bg-gray-700 cursor-not-allowed'}`}
            >
              {isLoading ? (
                <>
                  <span className="spinner"></span>
                  <span>Rozpoczynam...</span>
                </>
              ) : (
                <>
                  <span className="material-symbols-outlined">play_arrow</span>
                  <span>Rozpocznij Skanowanie</span>
                </>
              )}
            </div>
          </button>

          {/* Skip option */}
          <p className="text-center text-xs text-gray-500">
            Pozostaw puste, aby uzyc automatycznej numeracji
          </p>
        </div>
      </div>
    </div>
  );
}
