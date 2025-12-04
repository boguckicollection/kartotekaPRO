import React, { useState, useEffect, useRef } from 'react';
import { useLivePricingScan } from '../hooks/useLivePricingScan';

const useIsMobile = () => {
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);

  useEffect(() => {
    const handleResize = () => {
      setIsMobile(window.innerWidth < 768);
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return isMobile;
};

const ManualEntryView = ({ onBack }: { onBack: () => void }) => {
  const [name, setName] = useState('');
  const [number, setNumber] = useState('');
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedVariant, setSelectedVariant] = useState<any>(null);
  const [collectionResults, setCollectionResults] = useState<any[]>([]);

    const handleCollectionUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        setLoading(true);
        setError('');
        setCollectionResults([]);
        setResult(null);

        try {
            // Convert to base64
            const reader = new FileReader();
            reader.readAsDataURL(file);
            reader.onload = async () => {
                const base64Image = reader.result as string;
                
                try {
                    const res = await fetch(`/api/pricing/analyze_collection`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ image: base64Image })
                    });
                    
                    if (!res.ok) {
                        const err = await res.json();
                        throw new Error(err.error || 'Collection analysis failed');
                    }
                    
                    const data = await res.json();
                    setCollectionResults(data.results || []);
                    
                    if (data.results && data.results.length === 0) {
                        setError('Nie znaleziono żadnych kart na zdjęciu.');
                    }
                } catch (err: any) {
                    setError(err.message || 'Wystąpił błąd podczas analizy zdjęcia.');
                } finally {
                    setLoading(false);
                }
            };
            reader.onerror = () => {
                setError('Błąd odczytu pliku.');
                setLoading(false);
            };
        } catch (err) {
            setError('Nieoczekiwany błąd.');
            setLoading(false);
        }
    };

    const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    setSelectedVariant(null);

    try {
      const response = await fetch(`/api/pricing/manual_search`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'ngrok-skip-browser-warning': 'true',
        },
        body: JSON.stringify({ name, number }),
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.error || 'Nie znaleziono karty');
      }

      const data = await response.json();
      setResult(data);
      if (data.pricing.variants && data.pricing.variants.length > 0) {
        const normalVariant = data.pricing.variants.find((v: any) => v.label === 'Normal') || data.pricing.variants[0];
        setSelectedVariant(normalVariant);
      }
    } catch (err: any) {
      setError(err.message || 'Wystąpił błąd');
    } finally {
      setLoading(false);
    }
  };

  const getOverlayClass = () => {
    const rarity = result?.card?.rarity?.toLowerCase() || '';
    const variant = selectedVariant?.label?.toLowerCase() || '';

    if (rarity.includes('rainbow')) return 'rainbow-overlay';
    if (rarity.includes('gold') || rarity.includes('hyper')) return 'gold-overlay';
    if (rarity.includes('amazing')) return 'amazing-rare-overlay';
    if (rarity.includes('shiny')) return 'shiny-overlay';
    if (rarity.includes('illustration') || rarity.includes('full art')) return 'full-art-overlay';
    if (rarity.includes('double rare')) return 'double-rare-overlay';
    if (variant.includes('holo') && !variant.includes('reverse')) return 'holo-overlay';
    if (variant.includes('reverse')) return 'reverse-holo-overlay';
    return '';
  };

  const getFinishBadge = (label: string) => {
    const l = label.toLowerCase();
    if (l.includes('holo') && !l.includes('reverse')) return { letter: 'H', label: 'Holo', color: 'bg-purple-600' };
    if (l.includes('reverse')) return { letter: 'R', label: 'Reverse', color: 'bg-blue-600' };
    if (l.includes('normal')) return null;
    return { letter: '?', label: label, color: 'bg-gray-600' };
  };

  return (
    <div className="flex flex-col lg:grid lg:grid-cols-3 gap-6">
      <div className="lg:col-span-1 order-1">
        <button onClick={onBack} className="flex items-center gap-2 text-gray-400 hover:text-white mb-4 lg:mb-6 transition-colors">
            <span className="material-symbols-outlined">arrow_back</span> 
            <span>Powrót</span>
        </button>
        
        <div className="bg-gray-800/50 backdrop-blur-xl rounded-2xl p-4 lg:p-6 shadow-lg border border-gray-700/50">
            <h3 className="text-lg lg:text-xl font-bold mb-4 flex items-center gap-2">
                <span className="material-symbols-outlined text-primary">search</span>
                Szukaj karty
            </h3>
            <form onSubmit={handleSubmit} className="flex flex-col gap-3 lg:gap-4">
            <div>
                <label className="text-xs text-gray-400 ml-1 mb-1 block">Nazwa karty</label>
                <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="np. Charizard"
                    className="w-full p-3 rounded-lg bg-gray-900 border border-gray-700 focus:border-primary focus:outline-none transition-colors text-white text-sm lg:text-base"
                />
            </div>
            <div>
                <label className="text-xs text-gray-400 ml-1 mb-1 block">Numer karty (opcjonalny)</label>
                <input
                    type="text"
                    value={number}
                    onChange={(e) => setNumber(e.target.value)}
                    placeholder="np. 4/102"
                    className="w-full p-3 rounded-lg bg-gray-900 border border-gray-700 focus:border-primary focus:outline-none transition-colors text-white text-sm lg:text-base"
                />
            </div>
            <button 
                type="submit" 
                disabled={loading || !name} 
                className="mt-2 p-3 rounded-lg bg-gradient-to-r from-primary to-blue-600 text-white font-bold shadow-lg shadow-primary/20 disabled:opacity-50 disabled:shadow-none hover:brightness-110 transition-all text-sm lg:text-base"
            >
                {loading ? (
                    <span className="flex items-center justify-center gap-2">
                        <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
                        Szukanie...
                    </span>
                ) : 'Wyceń kartę'}
            </button>
            
            <div className="relative flex items-center gap-2 my-2">
                <div className="h-px bg-gray-700 flex-grow"></div>
                <span className="text-xs text-gray-500 font-medium uppercase">LUB</span>
                <div className="h-px bg-gray-700 flex-grow"></div>
            </div>
            
            <label className="cursor-pointer group relative overflow-hidden p-3 rounded-lg bg-gray-900 border border-gray-700 hover:border-primary transition-colors text-center block">
                <input 
                    type="file" 
                    accept="image/*" 
                    className="hidden" 
                    onChange={handleCollectionUpload}
                    disabled={loading}
                />
                <span className="flex items-center justify-center gap-2 text-gray-400 group-hover:text-white transition-colors text-sm lg:text-base font-medium">
                    <span className="material-symbols-outlined">add_photo_alternate</span>
                    Załaduj zdjęcie kolekcji (Beta)
                </span>
                {loading && (
                    <div className="absolute inset-0 bg-black/60 flex items-center justify-center backdrop-blur-sm">
                        <span className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
                    </div>
                )}
            </label>
            </form>
        </div>
      </div>
      
      <div className="lg:col-span-2 order-2">
        {loading && (
            <div className="h-full flex flex-col items-center justify-center text-gray-400">
                <span className="material-symbols-outlined text-4xl mb-2 animate-bounce">search</span>
                <p>Przeszukuję bazę kart...</p>
            </div>
        )}
        
        {error && (
            <div className="bg-red-500/10 border border-red-500/20 text-red-400 p-4 rounded-xl flex items-center gap-3">
                <span className="material-symbols-outlined">error</span>
                {error}
            </div>
        )}

        {result && (
          <div className="bg-gray-800/50 backdrop-blur-xl rounded-2xl p-4 lg:p-6 shadow-xl border border-gray-700/50 relative overflow-hidden">
            {/* Background Glow */}
            <div className="absolute top-0 right-0 w-64 h-64 bg-primary/5 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2 pointer-events-none"></div>

            <div className="flex flex-col md:flex-row gap-4 lg:gap-8 relative z-10">
                {/* Card Image */}
                <div className="flex-shrink-0 mx-auto md:mx-0">
                    <div className={`relative w-48 md:w-64 h-auto rounded-xl overflow-hidden shadow-2xl transition-transform duration-300 hover:scale-105 group`}>
                    {result.card.image ? (
                        <img src={result.card.image} alt={result.card.name} className="w-full h-full object-cover" />
                    ) : (
                        <div className="w-48 md:w-64 h-60 md:h-80 bg-gray-700 flex items-center justify-center text-gray-500 flex-col gap-2">
                            <span className="material-symbols-outlined text-3xl md:text-4xl">image_not_supported</span>
                            <span className="text-sm">Brak obrazka</span>
                        </div>
                    )}
                    <div className={`absolute inset-0 ${getOverlayClass()} opacity-40 group-hover:opacity-60 transition-opacity`}></div>
                    
                    {/* Rarity Badge on Image */}
                    {result.card.rarity && (
                        <div className="absolute bottom-2 left-2 right-2 bg-black/70 backdrop-blur-sm text-white text-xs py-1 px-2 rounded text-center border border-white/10">
                            {result.card.rarity}
                        </div>
                    )}
                    </div>
                </div>

                {/* Card Details */}
                <div className="flex-grow flex flex-col">
                    <div>
                        <div className="flex items-start justify-between gap-2 lg:gap-4">
                            <div>
                                <h2 className="text-xl lg:text-3xl font-black text-white mb-1">{result.card.name}</h2>
                                <p className="text-gray-400 text-sm lg:text-lg flex items-center gap-2 flex-wrap">
                                    <span className="text-primary font-bold">{result.card.set}</span>
                                    <span>#{result.card.number}</span>
                                </p>
                            </div>
                            <div className="text-right hidden md:block">
                                <span className="inline-block px-2 lg:px-3 py-1 bg-gray-900 rounded-lg text-xs text-gray-500 border border-gray-700">
                                    ID: {result.card.id}
                                </span>
                            </div>
                        </div>
                    </div>

                    {/* Variants */}
                    {result.pricing.variants && result.pricing.variants.length > 0 && (
                        <div className="mt-4 lg:mt-6">
                            <label className="text-xs text-gray-500 uppercase tracking-wider font-bold mb-2 lg:mb-3 block">Warianty</label>
                            <div className="flex flex-wrap gap-2">
                                {result.pricing.variants.map((variant: any) => {
                                    const badge = getFinishBadge(variant.label);
                                    const isSelected = selectedVariant?.label === variant.label;
                                    return (
                                        <button 
                                            key={variant.label} 
                                            onClick={() => setSelectedVariant(variant)} 
                                            className={`
                                                relative px-3 lg:px-4 py-1.5 lg:py-2 rounded-xl text-xs lg:text-sm font-bold transition-all border
                                                ${isSelected 
                                                    ? 'bg-primary text-white border-primary shadow-lg shadow-primary/25 scale-105' 
                                                    : 'bg-gray-900 text-gray-400 border-gray-700 hover:border-gray-500 hover:text-gray-200'
                                                }
                                            `}
                                        >
                                            <div className="flex items-center gap-1.5 lg:gap-2">
                                                {badge && (
                                                    <span className={`w-1.5 lg:w-2 h-1.5 lg:h-2 rounded-full ${badge.color}`}></span>
                                                )}
                                                {variant.label}
                                            </div>
                                        </button>
                                    );
                                })}
                            </div>
                        </div>
                    )}

                    {/* Pricing Grid */}
                    <div className="mt-4 lg:mt-6 grid grid-cols-2 gap-3 lg:gap-4">
                        <div className="bg-gray-900/50 p-3 lg:p-4 rounded-xl border border-gray-700/50 relative overflow-hidden group">
                            <div className="absolute top-0 right-0 p-2 lg:p-3 opacity-10 group-hover:opacity-20 transition-opacity">
                                <span className="material-symbols-outlined text-3xl lg:text-4xl">payments</span>
                            </div>
                            <p className="text-gray-400 text-xs uppercase tracking-wider font-bold mb-1">Cena rynkowa</p>
                            <p className="text-2xl lg:text-3xl font-black text-white">
                                {(selectedVariant?.price_pln_final || result.pricing.price_pln_final)?.toFixed(2)} <span className="text-sm lg:text-lg text-gray-500 font-normal">PLN</span>
                            </p>
                            {selectedVariant?.estimated && (
                                <p className="text-yellow-500 text-xs flex items-center gap-1 mt-1">
                                    <span className="material-symbols-outlined text-xs">warning</span>
                                    Szacunkowa
                                </p>
                            )}
                        </div>
                        <div className="bg-gray-900/50 p-3 lg:p-4 rounded-xl border border-gray-700/50 relative overflow-hidden group">
                            <div className="absolute top-0 right-0 p-2 lg:p-3 opacity-10 group-hover:opacity-20 transition-opacity">
                                <span className="material-symbols-outlined text-3xl lg:text-4xl">shopping_cart</span>
                            </div>
                            <p className="text-gray-400 text-xs uppercase tracking-wider font-bold mb-1">Cena skupu (80%)</p>
                            <p className="text-2xl lg:text-3xl font-black text-green-400">
                                {((selectedVariant?.price_pln_final * 0.8) || (result.pricing.purchase_price_pln))?.toFixed(2)} <span className="text-sm lg:text-lg text-green-500/50 font-normal">PLN</span>
                            </p>
                        </div>
                    </div>

                    {/* Additional Prices */}
                    <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-6">
                        {result.pricing.cardmarket && (
                            <div>
                                <h5 className="font-bold text-sm text-gray-300 mb-3 flex items-center gap-2">
                                    <span className="material-symbols-outlined text-blue-400">storefront</span>
                                    Cardmarket
                                </h5>
                                <div className="bg-gray-900 rounded-lg p-3 space-y-2 text-sm border border-gray-700">
                                    {result.pricing.cardmarket['7d_average'] && (
                                        <div className="flex justify-between items-center">
                                            <span className="text-gray-500">Średnia 7 dni</span>
                                            <span className="font-mono text-white">{result.pricing.cardmarket['7d_average'].pln_final?.toFixed(2)} PLN</span>
                                        </div>
                                    )}
                                    {result.pricing.cardmarket['30d_average'] && (
                                        <div className="flex justify-between items-center pt-2 border-t border-gray-800">
                                            <span className="text-gray-500">Średnia 30 dni</span>
                                            <span className="font-mono text-white">{result.pricing.cardmarket['30d_average'].pln_final?.toFixed(2)} PLN</span>
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}
                        
                        {result.pricing.graded && (
                            <div>
                                <h5 className="font-bold text-sm text-gray-300 mb-3 flex items-center gap-2">
                                    <span className="material-symbols-outlined text-purple-400">workspace_premium</span>
                                    Grading
                                </h5>
                                <div className="bg-gray-900 rounded-lg p-3 space-y-2 text-sm border border-gray-700">
                                    {result.pricing.graded.psa?.psa10 && (
                                        <div className="flex justify-between items-center">
                                            <span className="text-gray-500">PSA 10</span>
                                            <span className="font-mono text-white">{result.pricing.graded.psa.psa10.pln_final?.toFixed(2)} PLN</span>
                                        </div>
                                    )}
                                    {result.pricing.graded.psa?.psa9 && (
                                        <div className="flex justify-between items-center">
                                            <span className="text-gray-500">PSA 9</span>
                                            <span className="font-mono text-white">{result.pricing.graded.psa.psa9.pln_final?.toFixed(2)} PLN</span>
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

const LiveScanView = ({ onBack }: { onBack: () => void }) => {
  const [result, setResult] = useState<any>(null);
  const [selectedVariant, setSelectedVariant] = useState<any>(null);
  const [showZoom, setShowZoom] = useState(false);
  const [showCandidates, setShowCandidates] = useState(false);
  const [flash, setFlash] = useState(false);
  const successAudioRef = useRef<HTMLAudioElement>(null);
  const failAudioRef = useRef<HTMLAudioElement>(null);
  const shutterAudioRef = useRef<HTMLAudioElement>(null);
  const isMobile = useIsMobile();

  // Audio warm-up for mobile
  useEffect(() => {
      const unlockAudio = () => {
          [successAudioRef.current, failAudioRef.current, shutterAudioRef.current].forEach(audio => {
              if (audio) {
                  audio.play().catch(() => {}).then(() => {
                      audio.pause();
                      audio.currentTime = 0;
                  });
              }
          });
          document.removeEventListener('click', unlockAudio);
          document.removeEventListener('touchstart', unlockAudio);
      };
      
      document.addEventListener('click', unlockAudio);
      document.addEventListener('touchstart', unlockAudio);
      
      return () => {
          document.removeEventListener('click', unlockAudio);
          document.removeEventListener('touchstart', unlockAudio);
      };
  }, []);

  const { 
    analyzing, 
    status, 
    initStatus, 
    videoRef, 
    canvasRef, 
    setZoom, 
    zoomCaps, 
    toggleTorch, 
    torchSupported, 
    torchOn, 
    captureImage 
  } = useLivePricingScan({
    enabled: true,
    apiBase: '/api',
    onResult: (data) => {
      setFlash(true);
      setTimeout(() => setFlash(false), 300);
      setResult(data);
      setShowCandidates(false);
      if (data.pricing.variants && data.pricing.variants.length > 0) {
        const normalVariant = data.pricing.variants.find((v: any) => v.label === 'Normal') || data.pricing.variants[0];
        setSelectedVariant(normalVariant);
      }
    },
    onScan: () => {
      // Callback triggered on each scan frame (viewfinder loop)
    },
    onSound: (sound) => {
        const playSafe = async (audio: HTMLAudioElement) => {
            try {
                audio.currentTime = 0;
                await audio.play();
            } catch (e) {
                console.warn('Audio play failed', e);
            }
        };

        if (sound === 'success' && successAudioRef.current) {
            playSafe(successAudioRef.current);
        } else if (sound === 'fail' && failAudioRef.current) {
            playSafe(failAudioRef.current);
        } else if (sound === 'shutter' && shutterAudioRef.current) {
            playSafe(shutterAudioRef.current);
        }
    }
  });

  const getOverlayClass = () => {
    const rarity = result?.card?.rarity?.toLowerCase() || '';
    const variant = selectedVariant?.label?.toLowerCase() || '';

    if (rarity.includes('rainbow')) return 'rainbow-overlay';
    if (rarity.includes('gold') || rarity.includes('hyper')) return 'gold-overlay';
    if (rarity.includes('amazing')) return 'amazing-rare-overlay';
    if (rarity.includes('shiny')) return 'shiny-overlay';
    if (rarity.includes('illustration') || rarity.includes('full art')) return 'full-art-overlay';
    if (rarity.includes('double rare')) return 'double-rare-overlay';
    if (variant.includes('holo') && !variant.includes('reverse')) return 'holo-overlay';
    if (variant.includes('reverse')) return 'reverse-holo-overlay';
    return '';
  };

  const getFinishBadge = (label: string) => {
    const l = label.toLowerCase();
    if (l.includes('holo') && !l.includes('reverse')) return { letter: 'H', label: 'Holo', color: 'bg-purple-600' };
    if (l.includes('reverse')) return { letter: 'R', label: 'Reverse', color: 'bg-blue-600' };
    if (l.includes('normal')) return null;
    return { letter: '?', label: label, color: 'bg-gray-600' };
  };

  const selectCandidate = async (candidate: any) => {
      // Simple manual fetch to get details for alternative candidate
      try {
          const res = await fetch('/api/pricing/manual_search', {
              method: 'POST',
              headers: { 
                  'Content-Type': 'application/json',
                  'ngrok-skip-browser-warning': 'true'
              },
              body: JSON.stringify({ name: candidate.name, number: candidate.number })
          });
          
          if (res.ok) {
              const data = await res.json();
              setResult(data);
              setShowCandidates(false); // Zamknij listę po wyborze
              if (data.pricing.variants && data.pricing.variants.length > 0) {
                  const normalVariant = data.pricing.variants.find((v: any) => v.label === 'Normal') || data.pricing.variants[0];
                  setSelectedVariant(normalVariant);
              }
          }
      } catch (e) {
          console.error("Failed to select candidate", e);
      }
  };

  return (
    <div className={isMobile ? "fixed inset-0 z-50 bg-black" : "flex flex-col h-full"}>
      {/* Mobile: Fullscreen view */}
      {isMobile ? (
        <>
          {/* Video feed - fullscreen */}
          <video ref={videoRef} autoPlay playsInline muted className="absolute inset-0 w-full h-full object-cover"></video>
          <canvas ref={canvasRef} className="absolute inset-0 w-full h-full pointer-events-none"></canvas>
          
          {/* Flash Effect */}
          {flash && (
            <div className="absolute inset-0 bg-white z-50 animate-out fade-out duration-300 pointer-events-none"></div>
          )}
          
          {/* Subtelny efekt skanowania - minimalistyczny */}
          {!result && !analyzing && (
             <>
               {/* Scan line - animowana linia skanująca */}
               <div className="absolute inset-0 pointer-events-none overflow-hidden">
                 <div className="absolute w-full h-0.5 bg-gradient-to-r from-transparent via-primary/80 to-transparent 
                                 shadow-[0_0_20px_rgba(59,130,246,0.5)] 
                                 animate-[scan-down_2s_ease-in-out_infinite]">
                 </div>
               </div>
               
               {/* Corner guides - większe i bardziej widoczne */}
               <div className="absolute inset-0 pointer-events-none flex items-center justify-center p-4">
                 <div className="relative w-[90vw] max-w-sm h-[70vh] max-h-[600px]">
                   {/* 4 narożne kreski - większe i bardziej widoczne */}
                   <div className="absolute top-0 left-0 w-12 h-12 border-t-4 border-l-4 border-primary/70 animate-pulse"></div>
                   <div className="absolute top-0 right-0 w-12 h-12 border-t-4 border-r-4 border-primary/70 animate-pulse"></div>
                   <div className="absolute bottom-0 left-0 w-12 h-12 border-b-4 border-l-4 border-primary/70 animate-pulse"></div>
                   <div className="absolute bottom-0 right-0 w-12 h-12 border-b-4 border-r-4 border-primary/70 animate-pulse"></div>
                 </div>
               </div>
             </>
          )}

          {/* Scanning indicator with logo and blurred background */}
          {analyzing && (
            <>
              {/* Blurred background overlay */}
              <div className="absolute inset-0 bg-black/30 backdrop-blur-md z-19 pointer-events-none"></div>
              
              {/* Logo animation */}
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 pointer-events-none z-20">
                <div className="relative w-32 h-32">
                  <div className="absolute inset-0 rounded-full bg-primary/20 animate-ping"></div>
                  <div className="absolute inset-2 rounded-full bg-primary/30 animate-pulse"></div>
                  <div className="absolute inset-0 flex items-center justify-center p-6">
                    <img 
                      src="/logo-white.png" 
                      alt="Analyzing" 
                      className="w-full h-full object-contain animate-pulse drop-shadow-[0_0_10px_rgba(59,130,246,0.5)]"
                    />
                  </div>
                </div>
                <p className="text-white text-sm font-medium text-center mt-4 bg-black/50 backdrop-blur-sm px-4 py-2 rounded-full">
                  Analizuję kartę...
                </p>
              </div>
            </>
          )}
          
          {/* Top status bar - enhanced glassmorphism */}
          <div className="absolute top-0 left-0 right-0 
                        bg-gradient-to-b from-black/80 via-black/40 to-transparent 
                        backdrop-blur-md backdrop-saturate-150
                        pt-safe-top pb-6 px-4 flex items-center justify-between z-10">
             <button onClick={onBack} className="p-2 bg-black/20 backdrop-blur-md rounded-full text-white border border-white/10">
                <span className="material-symbols-outlined">arrow_back</span>
             </button>
             
             <div className="px-4 py-1 bg-black/40 backdrop-blur-md rounded-full border border-white/10">
                <span className="text-white text-sm font-medium flex items-center gap-2">
                   {status === 'Gotowy' ? <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span> : null}
                   {status}
                </span>
             </div>

             <div className="flex gap-2">
               {torchSupported && (
                 <button 
                   onClick={toggleTorch} 
                   className={`p-2 rounded-full border border-white/10 transition-all ${torchOn ? 'bg-yellow-500 text-white' : 'bg-black/20 backdrop-blur-md text-white'}`}
                 >
                    <span className="material-symbols-outlined">{torchOn ? 'flashlight_on' : 'flashlight_off'}</span>
                 </button>
               )}
             </div>
          </div>
          
          {/* Zoom Control (Hidden by default) */}
          {showZoom && zoomCaps && setZoom && (
            <div className="absolute top-24 right-4 bottom-32 w-12 flex flex-col items-center justify-center z-10 animate-fade-in">
               <div className="bg-black/40 backdrop-blur-md rounded-full py-4 px-2 border border-white/10 h-64 flex flex-col items-center">
                  <span className="material-symbols-outlined text-white text-xs mb-2">add</span>
                  <input
                    type="range"
                    orient="vertical"
                    min={zoomCaps.min}
                    max={zoomCaps.max}
                    step={zoomCaps.step}
                    defaultValue={1}
                    onChange={(e) => setZoom(parseFloat(e.target.value))}
                    className="h-full w-2 bg-white/20 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-6 [&::-webkit-slider-thumb]:h-6 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-white [&::-webkit-slider-thumb]:shadow-lg"
                    style={{ writingMode: 'bt-lr', WebkitAppearance: 'slider-vertical' } as any}
                  />
                  <span className="material-symbols-outlined text-white text-xs mt-2">remove</span>
               </div>
            </div>
          )}

          {/* Result card - Fixed positioning with max-height constraint */}
          {result && (
            <div className="fixed bottom-32 left-4 right-4 z-40 animate-slide-up 
                          bg-gradient-to-b from-gray-900/95 via-gray-800/95 to-gray-900/95 
                          backdrop-blur-xl
                          rounded-2xl border border-white/20 
                          shadow-2xl
                          p-4 pb-4 overflow-hidden overflow-y-auto max-h-[60vh]">
               <button 
                 onClick={() => { setResult(null); setShowCandidates(false); }} 
                 className="absolute top-3 right-3 p-2 text-gray-400 hover:text-white z-50 bg-black/50 rounded-full"
               >
                 <span className="material-symbols-outlined text-xl">close</span>
               </button>

                <div className="flex gap-4">
                    {result.card.image && (
                      <div className="flex-shrink-0 relative w-24 h-32">
                        <img 
                          src={result.card.image} 
                          alt={result.card.name}
                          className="w-full h-full object-cover rounded-lg shadow-lg border-2 border-white/30"
                        />
                      </div>
                    )}
                    
                    <div className="flex-grow min-w-0 pt-1 pr-10">
                      <h3 className="text-white font-bold text-base leading-tight truncate mb-1">
                        {result.card.name}
                      </h3>
                      
                      {/* Badge'y dla set + number - BARDZIEJ WIDOCZNE */}
                      <div className="flex flex-wrap gap-2 mb-3">
                        <span className="text-xs px-3 py-1 bg-primary/30 text-primary rounded-full border-2 border-primary/50 font-bold shadow-sm">
                          {result.card.set}
                        </span>
                        <span className="text-xs px-3 py-1 bg-blue-500/30 text-blue-200 rounded-full border-2 border-blue-500/50 font-bold shadow-sm">
                          #{result.card.number}
                        </span>
                      </div>
                      
                      {/* CENA - WIĘKSZA I BARDZIEJ WIDOCZNA */}
                      <div className="bg-gradient-to-br from-primary/20 to-blue-600/20 rounded-xl p-3 border border-primary/30">
                        <p className="text-gray-300 text-xs mb-1 uppercase tracking-wide">Cena rynkowa</p>
                        <div className="flex items-baseline gap-2">
                          {(() => {
                              const p = selectedVariant?.price_pln_final || result.pricing.price_pln_final;
                              if (p != null) {
                                  return (
                                      <>
                                          <span className="text-white text-3xl font-black">{p.toFixed(2)}</span>
                                          <span className="text-gray-300 text-sm font-medium">PLN</span>
                                      </>
                                  );
                              }
                              return <span className="text-gray-500 text-base italic">Brak wyceny</span>;
                          })()}
                        </div>
                        {selectedVariant?.estimated && (
                          <p className="text-yellow-400 text-xs flex items-center gap-1 mt-1">
                            <span className="material-symbols-outlined text-xs">info</span>
                            Szacunkowa
                          </p>
                        )}
                      </div>
                    </div>
                </div>
                
                {/* Variants chips */}
                {result.pricing.variants && result.pricing.variants.length > 0 && (
                <div className="mt-4 flex gap-2 overflow-x-auto pb-2 no-scrollbar">
                    {result.pricing.variants.map((variant: any) => {
                    const isSelected = selectedVariant?.label === variant.label;
                    return (
                        <button 
                        key={variant.label} 
                        onClick={() => setSelectedVariant(variant)} 
                        className={`flex-shrink-0 px-3 py-1.5 rounded-full text-xs font-bold transition-all border ${
                            isSelected 
                            ? 'bg-white text-black border-white' 
                            : 'bg-white/10 text-white border-white/20'
                        }`}
                        >
                        {variant.label}
                        </button>
                    );
                    })}
                </div>
                )}

                {/* Additional Prices Grid (Cardmarket & Grading) */}
                <div className="mt-4 grid grid-cols-2 gap-3">
                    {/* Cardmarket */}
                    {result.pricing.cardmarket && (
                        <div className="bg-black/40 rounded-xl p-3 border border-white/10">
                            <h5 className="font-bold text-[10px] text-gray-400 mb-2 flex items-center gap-1 uppercase tracking-wide">
                                <span className="material-symbols-outlined text-blue-400 text-sm">storefront</span>
                                Cardmarket
                            </h5>
                            <div className="space-y-1">
                                {result.pricing.cardmarket['7d_average'] && (
                                    <div className="flex justify-between items-center text-xs">
                                        <span className="text-gray-500">7 dni</span>
                                        <span className="font-mono text-white font-bold">{result.pricing.cardmarket['7d_average'].pln_final?.toFixed(2)} zł</span>
                                    </div>
                                )}
                                {result.pricing.cardmarket['30d_average'] && (
                                    <div className="flex justify-between items-center text-xs pt-1 border-t border-white/5">
                                        <span className="text-gray-500">30 dni</span>
                                        <span className="font-mono text-white font-bold">{result.pricing.cardmarket['30d_average'].pln_final?.toFixed(2)} zł</span>
                                    </div>
                                )}
                            </div>
                        </div>
                    )}
                    
                    {/* Grading */}
                    {result.pricing.graded && result.pricing.graded.psa && (
                        <div className="bg-black/40 rounded-xl p-3 border border-white/10">
                            <h5 className="font-bold text-[10px] text-gray-400 mb-2 flex items-center gap-1 uppercase tracking-wide">
                                <span className="material-symbols-outlined text-purple-400 text-sm">workspace_premium</span>
                                Grading
                            </h5>
                            <div className="space-y-1">
                                {result.pricing.graded.psa.psa10 && (
                                    <div className="flex justify-between items-center text-xs">
                                        <span className="text-gray-500 font-bold">PSA 10</span>
                                        <span className="font-mono text-white font-bold">{result.pricing.graded.psa.psa10.pln_final?.toFixed(2)} zł</span>
                                    </div>
                                )}
                                {result.pricing.graded.psa.psa9 && (
                                    <div className="flex justify-between items-center text-xs pt-1 border-t border-white/5">
                                        <span className="text-gray-500">PSA 9</span>
                                        <span className="font-mono text-white font-bold">{result.pricing.graded.psa.psa9.pln_final?.toFixed(2)} zł</span>
                                    </div>
                                )}
                            </div>
                        </div>
                    )}
                </div>

                {/* Alternative Candidates - POPRAWIONA WERSJA */}
                {result.candidates && result.candidates.length > 1 && (
                    <div className="mt-4 pt-4 border-t border-white/10">
                        <button 
                            onClick={() => setShowCandidates(!showCandidates)}
                            className="flex items-center justify-between w-full text-left py-2 px-1 active:bg-white/5 rounded-lg transition-colors"
                        >
                            <span className="text-xs text-primary font-bold uppercase tracking-wide">
                                Inne wyniki ({result.candidates.length - 1})
                            </span>
                            <span className="material-symbols-outlined text-gray-400 text-lg">
                                {showCandidates ? 'expand_less' : 'expand_more'}
                            </span>
                        </button>
                        
                        {showCandidates && (
                            <div className="max-h-72 overflow-y-auto pb-2 mt-2 animate-fade-in space-y-2 pr-1">
                                {result.candidates.map((cand: any) => {
                                    if (cand.id === result.card.id) return null; // Skip current
                                    return (
                                        <button 
                                            key={cand.id}
                                            onClick={() => selectCandidate(cand)}
                                            className="w-full flex items-center gap-3 p-2 rounded-xl bg-white/5 border border-white/10 hover:border-primary hover:bg-white/10 transition-all group active:scale-[0.98]"
                                        >
                                            {/* Miniaturka - z lepszym fallbackiem */}
                                            <div className="flex-shrink-0 w-16 h-22 relative rounded-md overflow-hidden border border-white/10 bg-gradient-to-br from-gray-800 to-gray-900 group-hover:border-primary/50 transition-colors">
                                                {cand.image ? (
                                                    <img 
                                                      src={cand.image} 
                                                      className="w-full h-full object-cover" 
                                                      alt={cand.name}
                                                      onError={(e) => {
                                                        // Fallback gdy obrazek się nie załaduje
                                                        (e.target as HTMLImageElement).style.display = 'none';
                                                        const parent = (e.target as HTMLImageElement).parentElement;
                                                        if (parent) {
                                                          parent.innerHTML = '<div class="w-full h-full flex flex-col items-center justify-center gap-1 p-2"><span class="material-symbols-outlined text-gray-600 text-lg">image_not_supported</span><span class="text-gray-600 text-[8px] text-center leading-tight">' + cand.name.substring(0, 12) + '</span></div>';
                                                        }
                                                      }}
                                                    />
                                                ) : (
                                                    <div className="w-full h-full flex flex-col items-center justify-center gap-1 p-2">
                                                        <span className="material-symbols-outlined text-gray-600 text-lg">image_not_supported</span>
                                                        <span className="text-gray-600 text-[8px] text-center leading-tight">{cand.name.substring(0, 12)}</span>
                                                    </div>
                                                )}
                                            </div>
                                            
                                            {/* Info */}
                                            <div className="flex-grow min-w-0 text-left">
                                                <p className="text-white font-bold text-sm truncate leading-tight">{cand.name}</p>
                                                <p className="text-gray-400 text-xs truncate mt-0.5">
                                                    {cand.set} {cand.number && <span className="text-primary font-bold">• #{cand.number}</span>}
                                                </p>
                                                {/* Placeholder dla ceny - będzie pobrana po kliknięciu */}
                                                <p className="text-gray-500 text-[10px] italic mt-1 flex items-center gap-1">
                                                    <span className="material-symbols-outlined text-xs">touch_app</span>
                                                    Kliknij dla wyceny
                                                </p>
                                            </div>
                                            
                                            {/* Chevron */}
                                            <div className="flex-shrink-0">
                                                <span className="material-symbols-outlined text-gray-400 group-hover:text-primary transition-colors">
                                                    chevron_right
                                                </span>
                                            </div>
                                        </button>
                                    );
                                })}
                            </div>
                        )}
                    </div>
                )}
            </div>
          )}
          
          {/* Bottom controls - Lifted above TabBar with full gradient background */}
          {!result && (
            <div className="absolute bottom-0 left-0 right-0 pb-[calc(env(safe-area-inset-bottom)+5rem)] pt-12 px-6 bg-gradient-to-t from-black via-black/80 to-transparent z-20 flex justify-between items-center">
               {/* Zoom Toggle */}
               {zoomCaps ? (
                   <button 
                     onClick={() => setShowZoom(!showZoom)}
                     className={`w-12 h-12 rounded-full flex items-center justify-center backdrop-blur-md border ${showZoom ? 'bg-white text-black border-white' : 'bg-black/30 text-white border-white/20'}`}
                   >
                      <span className="text-xs font-bold">1.0x</span>
                   </button>
               ) : <div className="w-12"></div>}

               {/* SHUTTER BUTTON */}
               <button 
                 onClick={captureImage}
                 disabled={analyzing}
                 className="w-20 h-20 rounded-full border-4 border-white flex items-center justify-center relative group active:scale-95 transition-transform"
               >
                  <div className="w-16 h-16 rounded-full bg-white group-active:bg-gray-200 transition-colors"></div>
               </button>

               {/* Placeholder / Gallery (future) */}
               <div className="w-12 h-12 rounded-full bg-black/30 backdrop-blur-md border border-white/20"></div>
            </div>
          )}
        </>
      ) : (
        /* Desktop view - keep original layout */
        <>
          <div className="flex items-center justify-between mb-4">
            <button onClick={onBack} className="text-primary flex items-center gap-2">
                <span className="material-symbols-outlined">arrow_back</span> Powrót
            </button>
            <h3 className="text-xl font-bold">Skanowanie na żywo</h3>
            <div className="w-8"></div>
          </div>

          <div className="flex-grow flex flex-col items-center">
            <div className="w-full max-w-sm aspect-[63/88] bg-gray-900 rounded-2xl overflow-hidden relative shadow-2xl border border-gray-800">
              <video ref={videoRef} autoPlay playsInline muted className="absolute inset-0 w-full h-full object-cover"></video>
              <canvas ref={canvasRef} className="absolute inset-0 w-full h-full pointer-events-none"></canvas>
              
              {analyzing && (
                <div className="absolute top-4 right-4">
                  <span className="flex h-3 w-3 relative">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-3 w-3 bg-primary"></span>
                  </span>
                </div>
              )}
              
              <div className="absolute top-4 left-4 right-12 text-center">
                <div className="text-white font-bold text-shadow">{status}</div>
                <div className="text-xs text-gray-300 text-shadow">{initStatus}</div>
              </div>
              
              {zoomCaps && (
                <div className="absolute bottom-4 left-4 right-4 flex items-center gap-2 bg-black/50 backdrop-blur-md p-2 rounded-full">
                  <span className="material-symbols-outlined text-sm text-white">zoom_out</span>
                  <input 
                    type="range" 
                    min={zoomCaps.min} 
                    max={zoomCaps.max} 
                    step={zoomCaps.step} 
                    defaultValue={1}
                    onChange={(e) => setZoom(parseFloat(e.target.value))} 
                    className="w-full h-2 bg-gray-600 rounded-lg appearance-none cursor-pointer"
                  />
                  <span className="material-symbols-outlined text-sm text-white">zoom_in</span>
                </div>
              )}
            </div>

        {collectionResults.length > 0 && (
            <div className="space-y-4">
                <h3 className="text-xl font-bold text-white flex items-center gap-2">
                    <span className="material-symbols-outlined text-green-400">photo_library</span>
                    Wyniki analizy kolekcji ({collectionResults.length})
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {collectionResults.map((item) => (
                        <div key={item.id} className="bg-gray-800/80 rounded-xl p-3 border border-gray-700 flex gap-3 items-start">
                            {/* Crop Image */}
                            <div className="w-20 h-28 flex-shrink-0 bg-black/50 rounded-lg overflow-hidden border border-gray-600">
                                <img src={item.crop_image} alt="Crop" className="w-full h-full object-contain" />
                            </div>
                            
                            {/* Details */}
                            <div className="flex-grow min-w-0">
                                {item.card ? (
                                    <>
                                        <h4 className="font-bold text-sm text-white truncate">{item.card.name}</h4>
                                        <div className="flex gap-2 my-1">
                                            <span className="text-[10px] px-1.5 py-0.5 bg-primary/20 text-primary rounded border border-primary/30">
                                                {item.card.set}
                                            </span>
                                            <span className="text-[10px] px-1.5 py-0.5 bg-blue-500/20 text-blue-300 rounded border border-blue-500/30">
                                                #{item.card.number}
                                            </span>
                                        </div>
                                        {item.pricing ? (
                                            <div className="mt-2">
                                                <p className="text-xs text-gray-400">Cena rynkowa:</p>
                                                <p className="text-lg font-bold text-green-400">
                                                    {item.pricing.price_pln_final?.toFixed(2)} PLN
                                                </p>
                                            </div>
                                        ) : (
                                            <p className="text-xs text-gray-500 mt-2 italic">Brak wyceny</p>
                                        )}
                                    </>
                                ) : (
                                    <div className="h-full flex flex-col justify-center">
                                        <p className="text-sm text-red-400 font-medium">Nie rozpoznano karty</p>
                                        <p className="text-xs text-gray-500 mt-1">
                                            Odczytano: {item.detected.name || '?'} {item.detected.number ? '#' + item.detected.number : ''}
                                        </p>
                                    </div>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        )}

        {result && (
              <div className="w-full max-w-md mt-4">
                <div className="bg-gradient-to-b from-gray-800/50 via-gray-900/45 to-gray-800/50 
                              backdrop-blur-2xl backdrop-saturate-150
                              rounded-2xl p-5 
                              shadow-[0_8px_32px_0_rgba(0,0,0,0.3)]
                              border border-gray-700/50
                              before:absolute before:inset-0 before:rounded-2xl 
                              before:bg-gradient-to-b before:from-white/5 before:to-transparent before:pointer-events-none
                              relative overflow-hidden">
                  <div className="flex gap-4">
                    <div className="relative w-24 h-32 flex-shrink-0 rounded-lg overflow-hidden shadow-lg border-2 border-white/20">
                      {result.card.image ? (
                        <img src={result.card.image} alt={result.card.name} className="w-full h-full object-cover" />
                      ) : (
                        <div className="w-full h-full bg-gray-700 flex items-center justify-center text-xs text-gray-500 flex-col gap-1">
                          <span className="material-symbols-outlined text-2xl">image_not_supported</span>
                          <span>Brak foto</span>
                        </div>
                      )}
                      <div className={`absolute inset-0 ${getOverlayClass()} opacity-40`}></div>
                    </div>
                    <div className="flex-grow min-w-0">
                      <h4 className="text-lg font-bold truncate text-white mb-1">{result.card.name}</h4>
                      
                      {/* Badge'y dla set + number - desktop */}
                      <div className="flex flex-wrap gap-2 mb-3">
                        <span className="text-sm px-3 py-1 bg-primary/30 text-primary rounded-full border-2 border-primary/50 font-bold shadow-sm">
                          {result.card.set}
                        </span>
                        <span className="text-sm px-3 py-1 bg-blue-500/30 text-blue-200 rounded-full border-2 border-blue-500/50 font-bold shadow-sm">
                          #{result.card.number}
                        </span>
                      </div>
                      
                      {/* Desktop price box */}
                      <div className="bg-gradient-to-br from-primary/20 to-blue-600/20 rounded-xl p-3 border border-primary/30">
                        <p className="text-gray-300 text-xs mb-1 uppercase tracking-wide">Cena rynkowa</p>
                        <div className="flex items-baseline gap-2">
                          <span className="text-2xl font-black text-white">
                            {(selectedVariant?.price_pln_final || result.pricing.price_pln_final)?.toFixed(2) || 'N/A'}
                          </span>
                          <span className="text-sm text-gray-300 font-medium">PLN</span>
                        </div>
                        {selectedVariant?.estimated && (
                          <p className="text-yellow-400 text-xs flex items-center gap-1 mt-1">
                            <span className="material-symbols-outlined text-xs">info</span>
                            Szacunkowa
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                  
                  {result.pricing.variants && result.pricing.variants.length > 0 && (
                    <div className="mt-4 pt-4 border-t border-gray-700/50">
                      <p className="text-xs text-gray-400 uppercase tracking-wide mb-2">Warianty</p>
                      <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
                        {result.pricing.variants.map((variant: any) => {
                          const badge = getFinishBadge(variant.label);
                          const isSelected = selectedVariant?.label === variant.label;
                          return (
                            <button 
                              key={variant.label} 
                              onClick={() => setSelectedVariant(variant)} 
                              className={`flex-shrink-0 px-3 py-1.5 rounded-full text-xs font-bold transition-all border flex items-center gap-1.5 ${
                                isSelected ? 'bg-primary text-white border-primary shadow-lg shadow-primary/25' : 'bg-gray-900 text-gray-400 border-gray-700 hover:border-gray-500'
                              }`}
                            >
                              {badge && <span className={`w-1.5 h-1.5 rounded-full ${badge.color}`}></span>}
                              {variant.label}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  )}
                  
                  {/* Alternative candidates for desktop */}
                  {result.candidates && result.candidates.length > 1 && (
                    <div className="mt-4 pt-4 border-t border-gray-700/50">
                      <button 
                        onClick={() => setShowCandidates(!showCandidates)}
                        className="flex items-center justify-between w-full text-left py-2 px-1 hover:bg-white/5 rounded-lg transition-colors"
                      >
                        <span className="text-xs text-primary font-bold uppercase tracking-wide">
                          Inne wyniki ({result.candidates.length - 1})
                        </span>
                        <span className="material-symbols-outlined text-gray-400 text-lg">
                          {showCandidates ? 'expand_less' : 'expand_more'}
                        </span>
                      </button>
                      
                      {showCandidates && (
                        <div className="max-h-64 overflow-y-auto mt-2 space-y-2 pr-1">
                          {result.candidates.map((cand: any) => {
                            if (cand.id === result.card.id) return null;
                            return (
                              <button 
                                key={cand.id}
                                onClick={() => selectCandidate(cand)}
                                className="w-full flex items-center gap-3 p-2 rounded-lg bg-gray-900/50 border border-gray-700 hover:border-primary hover:bg-gray-900 transition-all group"
                              >
                                <div className="flex-shrink-0 w-12 h-16 relative rounded-md overflow-hidden border border-white/10 bg-gradient-to-br from-gray-800 to-gray-900">
                                  {cand.image ? (
                                    <img 
                                      src={cand.image} 
                                      className="w-full h-full object-cover" 
                                      alt={cand.name}
                                      onError={(e) => {
                                        (e.target as HTMLImageElement).style.display = 'none';
                                        const parent = (e.target as HTMLImageElement).parentElement;
                                        if (parent) {
                                          parent.innerHTML = '<div class="w-full h-full flex items-center justify-center"><span class="material-symbols-outlined text-gray-600 text-sm">image_not_supported</span></div>';
                                        }
                                      }}
                                    />
                                  ) : (
                                    <div className="w-full h-full flex items-center justify-center">
                                      <span className="material-symbols-outlined text-gray-600 text-sm">image_not_supported</span>
                                    </div>
                                  )}
                                </div>
                                
                                <div className="flex-grow min-w-0 text-left">
                                  <p className="text-white font-semibold text-xs truncate">{cand.name}</p>
                                  <p className="text-gray-400 text-xs truncate">
                                    {cand.set} {cand.number && <span className="text-primary">• #{cand.number}</span>}
                                  </p>
                                </div>
                                
                                <span className="material-symbols-outlined text-gray-400 group-hover:text-primary transition-colors text-sm">
                                  chevron_right
                                </span>
                              </button>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </>
      )}

      <audio ref={successAudioRef} src="/done.mp3" preload="auto" />
      <audio ref={failAudioRef} src="/beep.mp3" preload="auto" />
      <audio ref={shutterAudioRef} src="/capture.mp3" preload="auto" />
    </div>
  );
};

const CsvUploadView = ({ onBack }: { onBack: () => void }) => (
  <div className="flex flex-col items-center justify-center min-h-[50vh]">
    <div className="text-center max-w-md p-8 bg-gray-800 rounded-2xl border border-gray-700/50 shadow-2xl">
      <div className="inline-flex items-center justify-center w-20 h-20 mb-6 bg-gray-700/50 rounded-full">
        <span className="material-symbols-outlined text-5xl text-gray-500">construction</span>
      </div>
      <h3 className="text-2xl font-bold text-white mb-2">Funkcja w budowie</h3>
      <p className="text-gray-400 mb-6">Moduł importu CSV jest obecnie w trakcie przygotowania. Zajrzyj tu ponownie wkrótce!</p>
      <button 
        onClick={onBack} 
        className="px-6 py-2 rounded-lg bg-gray-700 hover:bg-gray-600 text-white font-bold transition-colors"
      >
        Wróć do wyboru
      </button>
    </div>
  </div>
);

type View = 'SELECT' | 'MANUAL' | 'SCAN' | 'CSV';

export default function PricingView() {
  const [currentView, setCurrentView] = useState<View>('SELECT');
  const isMobile = useIsMobile();

  const renderContent = () => {
    switch (currentView) {
      case 'MANUAL':
        return <ManualEntryView onBack={() => setCurrentView('SELECT')} />;
      case 'SCAN':
        return <LiveScanView onBack={() => setCurrentView('SELECT')} />;
      case 'CSV':
        return <CsvUploadView onBack={() => setCurrentView('SELECT')} />;
      case 'SELECT':
      default:
        return (
          <div className="flex flex-col items-center justify-center min-h-[60vh] p-4">
            <div className="text-center mb-10">
              <div className="inline-flex items-center justify-center w-16 h-16 mb-4 bg-gradient-to-br from-yellow-500/20 to-orange-600/20 rounded-full border border-yellow-500/30">
                <span className="material-symbols-outlined text-3xl text-yellow-400">sell</span>
              </div>
              <h3 className="text-2xl font-bold text-white mb-2">Wycena kart</h3>
              <p className="text-gray-400 text-sm">Sprawdź wartość swoich kart jedną z metod</p>
            </div>

            <div className={`flex ${isMobile ? 'flex-col' : 'flex-wrap justify-center'} gap-4 ${isMobile ? 'w-full max-w-sm mx-auto' : ''}`}>
              {/* Wpisz ręcznie */}
              <div className="relative group">
                <div className="absolute -inset-1 bg-gradient-to-r from-yellow-500/30 to-orange-500/30 rounded-2xl blur-lg opacity-0 group-hover:opacity-100 transition duration-500"></div>
                <button 
                  onClick={() => setCurrentView('MANUAL')} 
                  className={`relative flex ${isMobile ? 'flex-row' : 'flex-col'} items-center ${isMobile ? 'justify-start' : 'justify-center'} ${isMobile ? 'w-full h-28' : 'w-52 h-56'} ${isMobile ? 'p-5' : 'p-6'} bg-[#0f172a] border border-gray-700/50 rounded-2xl shadow-xl hover:border-yellow-500/50 transition-all duration-300 group-hover:shadow-yellow-500/10`}
                >
                  <div className={`relative ${isMobile ? 'mr-4' : 'mb-4'}`}>
                    <div className="absolute inset-0 bg-yellow-500/20 rounded-full blur-xl opacity-50 group-hover:opacity-100 transition-opacity"></div>
                    <div className={`relative ${isMobile ? 'w-14 h-14' : 'w-20 h-20'} flex items-center justify-center bg-gradient-to-br from-yellow-500/10 to-orange-600/10 rounded-full border border-yellow-500/30`}>
                      <span className={`material-symbols-outlined ${isMobile ? 'text-3xl' : 'text-4xl'} text-yellow-400`}>keyboard</span>
                    </div>
                  </div>
                  <div className={`${isMobile ? 'text-left' : 'text-center'}`}>
                    <span className={`${isMobile ? 'text-base' : 'text-lg'} font-bold text-white block mb-1`}>Wpisz ręcznie</span>
                    <span className={`text-xs text-gray-400 ${isMobile ? 'block' : 'px-2'}`}>Wyszukaj po nazwie i numerze</span>
                  </div>
                </button>
              </div>

              {/* Skanowanie na żywo (Mobile) */}
              {isMobile && (
                <div className="relative group">
                  <div className="absolute -inset-1 bg-gradient-to-r from-blue-500/30 to-cyan-500/30 rounded-2xl blur-lg opacity-0 group-hover:opacity-100 transition duration-500"></div>
                  <button 
                    onClick={() => setCurrentView('SCAN')} 
                    className="relative flex flex-row items-center justify-start w-full h-28 p-5 bg-[#0f172a] border border-gray-700/50 rounded-2xl shadow-xl hover:border-blue-500/50 transition-all duration-300 group-hover:shadow-blue-500/10"
                  >
                    <div className="relative mr-4">
                      <div className="absolute inset-0 bg-blue-500/20 rounded-full blur-xl opacity-50 group-hover:opacity-100 transition-opacity"></div>
                      <div className="relative w-14 h-14 flex items-center justify-center bg-gradient-to-br from-blue-500/10 to-cyan-600/10 rounded-full border border-blue-500/30">
                        <span className="material-symbols-outlined text-3xl text-blue-400">photo_camera</span>
                      </div>
                    </div>
                    <div className="text-left">
                      <span className="text-base font-bold text-white block mb-1">Skanuj kamerą</span>
                      <span className="text-xs text-gray-400">Szybka wycena kamerą telefonu</span>
                    </div>
                  </button>
                </div>
              )}

              {/* CSV (Desktop) */}
              {!isMobile && (
                <div className="relative group">
                  <div className="absolute -inset-1 bg-gradient-to-r from-green-500/30 to-emerald-500/30 rounded-2xl blur-lg opacity-0 group-hover:opacity-100 transition duration-500"></div>
                  <button 
                    onClick={() => setCurrentView('CSV')} 
                    className="relative flex flex-col items-center justify-center w-52 h-56 p-6 bg-[#0f172a] border border-gray-700/50 rounded-2xl shadow-xl hover:border-green-500/50 transition-all duration-300 group-hover:shadow-green-500/10"
                  >
                    <div className="relative mb-4">
                      <div className="absolute inset-0 bg-green-500/20 rounded-full blur-xl opacity-50 group-hover:opacity-100 transition-opacity"></div>
                      <div className="relative w-20 h-20 flex items-center justify-center bg-gradient-to-br from-green-500/10 to-emerald-600/10 rounded-full border border-green-500/30">
                        <span className="material-symbols-outlined text-4xl text-green-400">table_view</span>
                      </div>
                    </div>
                    <span className="text-lg font-bold text-white mb-1">Import CSV</span>
                    <span className="text-xs text-gray-400 text-center px-2">Wyceń wiele kart naraz</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        );
    }
  };

  return (
    <div className="font-display text-white">
      <header className="flex items-center justify-between whitespace-nowrap border-b border-gray-800 px-2 md:px-6 py-3">
        <div className="flex items-center gap-3">
          <span className="material-symbols-outlined text-primary">sell</span>
          <h2 className="text-lg font-bold">Wycena</h2>
          <span className="text-xs bg-green-500/20 text-green-400 px-2 py-1 rounded-full border border-green-500/30">v2.0 HD</span>
        </div>
      </header>
      <main className="p-4 md:p-6">
        {renderContent()}
      </main>
    </div>
  );
}
