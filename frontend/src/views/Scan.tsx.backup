import React, { useEffect, useMemo, useState, useRef } from 'react'
import Toast from '../components/Toast';
import SlideOutPanel from '../components/SlideOutPanel';

type Candidate = { id: string; name: string; score: number; set?: string|null; number?: string|null; image?: string|null }

type Props = {
  session: {id: number} | null;
  preview: string | null
  loading: boolean
  analyzing?: boolean
  status?: string
  ripple?: boolean
  result: { detected: { name: string|null; set: string|null; number: string|null; language: string|null; variant: string|null; condition: string|null; rarity: string|null; energy: string|null; price_pln_final?: number | null; variants?: any[]; }; candidates: Candidate[]; message: string; overlay?: { x:number;y:number;w:number;h:number } | null; quality?: number|null; confidence_label?: string|null } | null
  selected: string | null
  onPick: (id: string)=>void
  onFile: (e: React.ChangeEvent<HTMLInputElement>)=>void
  onFolderChange?: (e: React.ChangeEvent<HTMLInputElement>)=>void
  onCsvUpload?: (e: React.ChangeEvent<HTMLInputElement>)=>void
  onStartSession?: () => void
  onSubmit: ()=>void
  onConfirm: (data: any, imageInfo: { primary: { source: string; url: string | null; file?: File | null; }; additional: File[]; }) => void;
  rightExtras?: React.ReactNode
  showFileInputs?: boolean
  torchSupported?: boolean
  torchOn?: boolean
  onToggleTorch?: ()=>void
  tapFocusSupported?: boolean
  onTapToFocus?: (x:number, y:number)=>void
  lowLight?: boolean
  qualityCommitMin?: number
  qualityLive?: number | null
  onEndSession?: ()=>void
  onForceCommit?: ()=>void
  videoRef?: React.Ref<HTMLVideoElement>
  initStatus?: string
  zoomCaps?: {min: number, max: number, step: number} | null
  setZoom?: (zoom: number) => void
  onBatchScan?: ()=>void
}

export default function ScanView({ session, preview, loading, analyzing, status, ripple, result, selected, onPick, onFile, onFolderChange, onCsvUpload, onStartSession, onSubmit, onConfirm, rightExtras, showFileInputs = true, torchSupported=false, torchOn=false, onToggleTorch, tapFocusSupported=false, onTapToFocus, lowLight=false, qualityCommitMin=0.55, qualityLive=null, onEndSession, onForceCommit, videoRef, initStatus, zoomCaps, setZoom, onBatchScan }: Props){
  const isAndroid = useMemo(()=>/Android/i.test(navigator.userAgent||''), [])
  const [focusPt, setFocusPt] = useState<{x:number;y:number}|null>(null)
  const [showAll, setShowAll] = useState(false)
  const [banner, setBanner] = useState<{ key:'lowLight'|'quality'; ts:number } | null>(null)
  const [scanResult, setScanResult] = useState<any | null>(null);
  const [toast, setToast] = useState<{message: string, type: string} | null>(null);
  const [formData, setFormData] = useState<any>({});
  const [shoperAttributes, setShoperAttributes] = useState<any[] | null>(null);
  const [shoperCategories, setShoperCategories] = useState<any[] | null>(null);
  const [manualPrice, setManualPrice] = useState<number | null>(null);
  const [scanMode, setScanMode] = useState<'choice' | 'image' | 'csv'>('choice');
  const [scanSubMode, setScanSubMode] = useState<'single' | 'folder' | null>(null);

  const [showAllCandidates, setShowAllCandidates] = useState(false);
  const [isFetchingDetails, setIsFetchingDetails] = useState(false);
  const [selectedPrimaryImage, setSelectedPrimaryImage] = useState<{source: 'tcggo' | 'scan' | 'upload', url: string | null, file?: File | null}>({source: 'tcggo', url: null});
  const [additionalImages, setAdditionalImages] = useState<File[]>([]);
  const [candidatesPanelOpen, setCandidatesPanelOpen] = useState(false);
  const [manualPriceEdit, setManualPriceEdit] = useState(false);

  const handleCandidateSelect = async (candidate: Candidate) => {
    // 1. Immediately update UI for responsiveness
    setScanResult((prev: any) => ({
        ...prev,
        candidates: [candidate, ...prev.candidates.filter((c: Candidate) => c.id !== candidate.id)]
    }));

    // 2. Fetch full details in the background
    setIsFetchingDetails(true);
    try {
      const res = await fetch('/api/scan/candidate_details', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ candidate_id: candidate.id })
      });
      if (!res.ok) {
        throw new Error('Failed to fetch candidate details');
      }
      const enrichedData = await res.json();

      // 3. Merge new data with existing form data (preserve user edits)
      const newFormData = { 
        ...formData, // Keep existing values
        ...enrichedData, // Override with new data from API
        // Ensure critical fields are preserved even if API returns null/undefined
        name: enrichedData.name || formData.name || candidate.name,
        number: enrichedData.number || formData.number || candidate.number,
        set: enrichedData.set || formData.set || candidate.set,
        set_code: enrichedData.set_code || formData.set_code,
      };

      // Re-apply defaults for all attributes if not present
      if (!newFormData['64']) { // Język (Language)
        newFormData['64'] = '142'; // Angielski (English)
      }
      if (!newFormData['66']) { // Jakość (Quality)
        newFormData['66'] = '176'; // Near Mint
      }
      if (!newFormData['65']) { // Wykończenie (Finish)
        newFormData['65'] = '184'; // Normal
      }
      if (!newFormData['39']) { // Typ karty (Card Type)
        newFormData['39'] = '182'; // Nie dotyczy (N/A)
      }

      setFormData(newFormData);
      setManualPriceEdit(false); // Reset flag when selecting new candidate
      
      // Update the primary image to the newly selected candidate's image
      if (enrichedData.image) {
        setSelectedPrimaryImage({ source: 'tcggo', url: enrichedData.image });
      }

      // Update scanResult.detected to keep it in sync (preserve variants!)
      setScanResult((prev: any) => ({
        ...prev,
        detected: {
          ...prev.detected,
          ...newFormData,
          // Preserve variants if they exist in enrichedData or previous state
          variants: enrichedData.variants || prev.detected?.variants || []
        }
      }));

    } catch (e) {
      console.error("Failed to fetch details for selected candidate", e);
      setToast({ message: 'Nie udało się pobrać szczegółów karty.', type: 'error' });
    } finally {
      setIsFetchingDetails(false);
    }
  };


  const productCode = useMemo(() => {
    // Prioritize the set_code from the scan result itself, as it's the most accurate.
    const setAbbr = formData.set_code || '';
    const finishAttr = shoperAttributes?.find(a => a.attribute_id === '65');
    const finishOption = finishAttr?.options.find(o => o.option_id === formData['65']);
    const finishSuffix = finishOption ? `-${finishOption.value.substring(0, 1)}` : '';
    return `POKE-${setAbbr}-${formData.number || ''}${finishSuffix}`;
  }, [formData, shoperAttributes]);

  const finishBadge = useMemo(() => {
    const selectedFinishId = formData['65']; // The 'Finish' attribute
    switch (String(selectedFinishId)) {
        case '149': // Holo
            return { letter: 'H', label: 'Holo', color: 'bg-purple-600' };
        case '150': // Reverse Holo
            return { letter: 'R', label: 'Reverse Holo', color: 'bg-blue-600' };
        case '151': // Full Art
            return { letter: 'F', label: 'Full Art', color: 'bg-pink-600' };
        case '155': // PokéBall Pattern
            return { letter: 'P', label: 'PokéBall', color: 'bg-red-600' };
        case '156': // MasterBall Pattern
            return { letter: 'M', label: 'MasterBall', color: 'bg-purple-800' };
        case '157': // Gold
            return { letter: 'G', label: 'Gold', color: 'bg-yellow-500' };
        case '158': // Rainbow
            return { letter: '🌈', label: 'Rainbow', color: 'bg-gradient-to-r from-red-500 via-yellow-500 to-blue-500' };
        case '184': // Normal - no badge needed
        default:
            return null;
    }
  }, [formData['65']]);

  // Handle attribute change with special logic for Finish (recalculate price)
  const handleAttributeChange = async (attrId: string, value: string) => {
    // Update form data immediately
    setFormData((prev: any) => ({...prev, [attrId]: value}));
    
    // Special handling for Finish attribute (ID 65) - recalculate price
    if (attrId === '65' && scanResult?.scan_id && !manualPriceEdit) {
      // Map option ID to finish type
      const finishMap: Record<string, string> = {
        '184': 'normal',  // Normal
        '149': 'holo',    // Holo
        '150': 'reverse', // Reverse Holo
        '151': 'holo',    // Full Art (treat as holo pricing)
        '155': 'normal',  // PokéBall Pattern
        '156': 'holo',    // MasterBall Pattern
        '157': 'holo',    // Gold (premium)
        '158': 'holo',    // Rainbow (premium)
      };
      const finish = finishMap[value] || 'normal';
      
      try {
        const res = await fetch('/api/pricing/recalculate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ 
            scan_id: scanResult.scan_id,
            finish: finish 
          })
        });
        
        if (res.ok) {
          const priceData = await res.json();
          if (priceData.price_pln_final !== null) {
            setFormData((prev: any) => ({
              ...prev, 
              price_pln_final: priceData.price_pln_final,
              price_pln: priceData.price_pln,
              base_eur: priceData.base_eur,
            }));
            
            // Show toast if price was estimated
            if (priceData.estimated) {
              setToast({ message: `Cena została oszacowana (brak danych dla ${finish})`, type: 'info' });
            }
          }
        }
      } catch (e) {
        console.error("Failed to recalculate price", e);
      }
    }
  };

  useEffect(() => {
    const fetchShoperData = async () => {
      try {
        const [attributesRes, categoriesRes] = await Promise.all([
          fetch('/api/shoper/attributes'),
          fetch('/api/shoper/categories'),
        ]);
        const attributesData = await attributesRes.json();
        const categoriesData = await categoriesRes.json();
        setShoperAttributes(attributesData.items || []);
        setShoperCategories(categoriesData.items || []);
      } catch (e) {
        console.error("Failed to fetch shoper data", e);
      }
    };
    fetchShoperData();
  }, []);

  useEffect(() => {
    if (!result) {
      setScanResult(null);
      setFormData({});
      setManualPriceEdit(false);
      return;
    }

    setScanResult(result);
    setManualPriceEdit(false); // Reset flag on new scan

    if (result.duplicate_of) {
      setToast({ message: `Wykryto duplikat. Możesz opublikować, aby zaktualizować stan magazynowy.`, type: 'success' });
      const fetchOriginalScan = async () => {
        try {
          const res = await fetch(`/api/scans/${result.duplicate_of}`);
          const originalScan = await res.json();
          // Preserve scan_id from current scan result for publishing
          const mergedResult = { 
            ...originalScan, 
            scan_id: result.scan_id, // Keep NEW scan's ID for publishing
            duplicate_of: result.duplicate_of, 
            duplicate_distance: result.duplicate_distance 
          };
          
          if (mergedResult.detected) {
            const newFormData: any = { ...mergedResult.detected };

            // 1. Restore Price
            if (mergedResult.pricing?.price_pln_final) {
              newFormData.price_pln_final = mergedResult.pricing.price_pln_final;
            }

            // Attributes are now included in the detected payload, so no need to map them again.
            
            // Set default values for Language and Condition if not mapped
            if (!newFormData['64']) { // Język (Language)
              newFormData['64'] = '142'; // Angielski (English)
            }
            if (!newFormData['66']) { // Jakość (Quality)
              newFormData['66'] = '176'; // Near Mint
            }

            setFormData(newFormData);
          }
          setScanResult(mergedResult);

        } catch (e) {
          console.error("Failed to fetch original scan", e);
        }
      };
      fetchOriginalScan();
    } else if (result.detected) { // Handle new scans (not duplicates)
      const newFormData: any = { ...result.detected };

      // Set default values for attributes if not already set
      if (!newFormData['64']) { // 64 is Język (Language)
        newFormData['64'] = '142'; // 142 is Angielski (English)
      }
      if (!newFormData['66']) { // 66 is Jakość (Quality)
        newFormData['66'] = '176'; // 176 is Near Mint
      }
      if (!newFormData['65']) { // 65 is Wykończenie (Finish)
        newFormData['65'] = '184'; // 184 is Normal
      }
      if (!newFormData['39']) { // 39 is Typ karty (Card Type)
        newFormData['39'] = '182'; // 182 is Nie dotyczy (N/A)
      }
      
      // Set price directly from detected data if available
      if (result.detected.price_pln_final) {
        newFormData.price_pln_final = result.detected.price_pln_final;
      } else {
        // Fallback to normal variant price if direct price is not available
        const normalVariant = result.detected.variants?.find((v:any) => v.label === 'Normal');
        if (normalVariant) {
          newFormData.price_pln_final = normalVariant.price_pln_final;
        }
      }

      // Map attributes from detected data
      const mapAttributes = async () => {
        try {
          const attrRes = await fetch('/api/shoper/map_attributes', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(result.detected),
          });
          const attrMapping = await attrRes.json();
          if (attrMapping.attributes) {
            Object.assign(newFormData, attrMapping.attributes);
          }
        } catch (e) {
          console.error("Failed to map attributes", e);
        }
        setFormData(newFormData);
      }

      mapAttributes();
    }
  }, [result]);

  // Reset manual price edit flag when finish changes (user wants auto-pricing)
  useEffect(() => {
    setManualPriceEdit(false);
  }, [formData['65']]);

  useEffect(() => {
    // Don't auto-update price if user manually edited it
    if (manualPriceEdit) return;

    const finishAttrId = '65';
    const selectedFinishId = formData[finishAttrId];
    // If there are no variants to check against, do nothing.
    if (!scanResult?.detected?.variants || !Array.isArray(scanResult.detected.variants)) return;

    const variants = scanResult.detected.variants;
    let newPrice = null;

    // Determine which variant label we are looking for based on the dropdown selection.
    let targetVariantLabel = 'Normal'; // Default to 'Normal'
    switch (String(selectedFinishId)) {
      case '149': // Holo
        targetVariantLabel = 'Holo';
        break;
      case '150': // Reverse Holo
        targetVariantLabel = 'Reverse Holo';
        break;
    }

    // Find the price for the target variant.
    const targetVariant = variants.find(v => v.label === targetVariantLabel);
    if (targetVariant && typeof targetVariant.price_pln_final === 'number') {
      newPrice = targetVariant.price_pln_final;
    } else {
      // If the specific variant isn't found, fall back to the 'Normal' price
      // without applying any multipliers.
      const normalVariant = variants.find(v => v.label === 'Normal');
      if (normalVariant && typeof normalVariant.price_pln_final === 'number') {
        newPrice = normalVariant.price_pln_final;
      }
    }

    // Only update state if the price has actually changed to prevent infinite loops.
    if (newPrice !== null && newPrice !== formData.price_pln_final) {
      setFormData(prev => ({ ...prev, price_pln_final: newPrice }));
    }
  }, [formData['65'], scanResult, formData.price_pln_final, manualPriceEdit]);

  useEffect(() => {
    // Set the primary image, preferring TCGGO's and falling back to the user's scan
    if (scanResult?.candidates?.[0]?.image) {
      setSelectedPrimaryImage({ source: 'tcggo', url: scanResult.candidates[0].image });
    } else if (preview) {
      setSelectedPrimaryImage({ source: 'scan', url: preview });
    }
  }, [scanResult, preview]);


  const lastShownRef = useRef({ lowLightAt: 0, qualityAt: 0 })
  const timerRef = useRef({ id: 0 as number|undefined })

  // Ephemeral banner logic: show for a few seconds, with cooldown to avoid flicker
  useEffect(()=>{
    const now = Date.now()
    if (isAndroid && lowLight){
      if (now - (lastShownRef.current.lowLightAt||0) > 7000){
        setBanner({ key:'lowLight', ts: now })
        lastShownRef.current.lowLightAt = now
        if (timerRef.current.id) window.clearTimeout(timerRef.current.id)
        timerRef.current.id = window.setTimeout(()=> setBanner(null), 4500)
      }
      return
    }
    const q = typeof qualityLive==='number' ? qualityLive : null
    if (isAndroid && q!=null && q < (qualityCommitMin||0.55)){
      if (now - (lastShownRef.current.qualityAt||0) > 6000){
        setBanner({ key:'quality', ts: now })
        lastShownRef.current.qualityAt = now
        if (timerRef.current.id) window.clearTimeout(timerRef.current.id)
        timerRef.current.id = window.setTimeout(()=> setBanner(null), 3800)
      }
    }
  }, [isAndroid, lowLight, qualityLive, qualityCommitMin])

  const handleFetchPrice = async () => {
    try {
      const res = await fetch('/api/pricing/variants', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: formData.name, number: formData.number, set: formData.set })
      });
      const data = await res.json();
      
      // Update variants in scanResult for automatic price switching
      setScanResult((prev: any) => ({
        ...prev,
        detected: {
          ...prev.detected,
          variants: data.variants || []
        }
      }));

      const normalVariant = data.variants?.find((v: any) => v.label === 'Normal');
      if (normalVariant) {
        setManualPriceEdit(false); // Reset flag so automatic switching works
        setFormData(prev => ({...prev, price_pln_final: normalVariant.price_pln_final}));
      }
    } catch (e) {
      console.error("Failed to fetch price", e);
    }
  };

  const handleCalculatePrice = async () => {
    if (manualPrice === null) return;
    try {
      const res = await fetch('/api/pricing/convert', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ eur: manualPrice })
      });
      const data = await res.json();
      setManualPriceEdit(false); // Reset flag so automatic switching works
      setFormData(prev => ({...prev, price_pln_final: data.price_pln_final}));
    } catch (e) {
      console.error("Failed to calculate price", e);
    }
  };

  // Canvas overlay rendering (real-time) - NEW!
  const overlayCanvasRef = useRef<HTMLCanvasElement>(null);
  
  useEffect(() => {
    if (!overlayCanvasRef.current || !videoRef) return;
    
    const canvas = overlayCanvasRef.current;
    const video = (videoRef as any).current;
    if (!video) return;
    
    let rafId: number;
    
    const drawOverlay = () => {
      const ctx = canvas.getContext('2d');
      if (!ctx) return;
      
      // Match canvas size to video
      if (video.videoWidth && video.videoHeight) {
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
      }
      
      // Clear canvas
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      
      // Draw overlay box if available
      if (result?.overlay) {
        const { x, y, w, h } = result.overlay;
        const quality = qualityLive || 0;
        
        // Color based on quality
        const color = quality > 0.7 ? '#00ff00' : 
                      quality > 0.55 ? '#ffff00' : '#ff0000';
        
        ctx.strokeStyle = color;
        ctx.lineWidth = 4;
        ctx.shadowBlur = 15;
        ctx.shadowColor = color;
        
        // Draw main box
        const boxX = x * canvas.width;
        const boxY = y * canvas.height;
        const boxW = w * canvas.width;
        const boxH = h * canvas.height;
        
        ctx.strokeRect(boxX, boxY, boxW, boxH);
        
        // Draw corner brackets for visual effect
        const cornerLen = 25;
        ctx.lineWidth = 6;
        ctx.lineCap = 'round';
        
        // Top-left
        ctx.beginPath();
        ctx.moveTo(boxX, boxY + cornerLen);
        ctx.lineTo(boxX, boxY);
        ctx.lineTo(boxX + cornerLen, boxY);
        ctx.stroke();
        
        // Top-right
        ctx.beginPath();
        ctx.moveTo(boxX + boxW - cornerLen, boxY);
        ctx.lineTo(boxX + boxW, boxY);
        ctx.lineTo(boxX + boxW, boxY + cornerLen);
        ctx.stroke();
        
        // Bottom-left
        ctx.beginPath();
        ctx.moveTo(boxX, boxY + boxH - cornerLen);
        ctx.lineTo(boxX, boxY + boxH);
        ctx.lineTo(boxX + cornerLen, boxY + boxH);
        ctx.stroke();
        
        // Bottom-right
        ctx.beginPath();
        ctx.moveTo(boxX + boxW - cornerLen, boxY + boxH);
        ctx.lineTo(boxX + boxW, boxY + boxH);
        ctx.lineTo(boxX + boxW, boxY + boxH - cornerLen);
        ctx.stroke();
      }
      
      rafId = requestAnimationFrame(drawOverlay);
    };
    
    rafId = requestAnimationFrame(drawOverlay);
    
    return () => {
      if (rafId) cancelAnimationFrame(rafId);
    };
  }, [result, qualityLive, videoRef]);

return (
    <div className="font-display">
      <header className="flex items-center justify-between whitespace-nowrap border-b border-gray-800 px-2 md:px-6 py-3">
        <div className="flex items-center gap-3 text-white">
          <span className="material-symbols-outlined text-primary">qr_code_scanner</span>
          <h2 className="text-lg font-bold">Skanowanie kart</h2>
          <span className="text-xs bg-green-500/20 text-green-400 px-2 py-1 rounded-full border border-green-500/30">v2.0 HD</span>
        </div>
        <div className="flex gap-2">
          {isAndroid && onEndSession && (
            <button onClick={onEndSession} className="btn text-sm">Zakończ sesję</button>
          )}
        </div>
      </header>

      <main className="p-4 md:p-6">
        {toast && <Toast message={toast.message} onClose={() => setToast(null)} />}
        {scanMode === 'choice' && (
          <div className="flex flex-col items-center justify-center min-h-[60vh] p-4">
            {/* Header */}
            <div className="text-center mb-10">
              <div className="inline-flex items-center justify-center w-16 h-16 mb-4 bg-gradient-to-br from-cyan-500/20 to-blue-600/20 rounded-full border border-cyan-500/30">
                <span className="material-symbols-outlined text-3xl text-cyan-400">qr_code_scanner</span>
              </div>
              <h3 className="text-2xl font-bold text-white mb-2">Wybierz metodę skanowania</h3>
              <p className="text-gray-400 text-sm">Jak chcesz wprowadzić karty do systemu?</p>
            </div>
            
            {/* Cards */}
            <div className="flex flex-wrap justify-center gap-6">
              {/* Skanuj z komputera */}
              <div className="relative group">
                <div className="absolute -inset-1 bg-gradient-to-r from-cyan-500/30 to-blue-500/30 rounded-2xl blur-lg opacity-0 group-hover:opacity-100 transition duration-500"></div>
                <button 
                  onClick={() => setScanMode('image')} 
                  className="relative flex flex-col items-center justify-center w-52 h-56 p-6 bg-[#0f172a] border border-gray-700/50 rounded-2xl shadow-xl hover:border-cyan-500/50 transition-all duration-300 group-hover:shadow-cyan-500/10"
                >
                  <div className="relative mb-4">
                    <div className="absolute inset-0 bg-cyan-500/20 rounded-full blur-xl opacity-50 group-hover:opacity-100 transition-opacity"></div>
                    <div className="relative w-20 h-20 flex items-center justify-center bg-gradient-to-br from-cyan-500/10 to-blue-600/10 rounded-full border border-cyan-500/30">
                      <span className="material-symbols-outlined text-4xl text-cyan-400">image_search</span>
                    </div>
                  </div>
                  <span className="text-lg font-bold text-white mb-1">Skanuj z komputera</span>
                  <span className="text-xs text-gray-400 text-center px-2">Prześlij pliki graficzne kart</span>
                </button>
              </div>

              {/* Importuj z CSV */}
              <div className="relative group">
                <div className="absolute -inset-1 bg-gradient-to-r from-green-500/30 to-emerald-500/30 rounded-2xl blur-lg opacity-0 group-hover:opacity-100 transition duration-500"></div>
                <button 
                  onClick={() => setScanMode('csv')} 
                  className="relative flex flex-col items-center justify-center w-52 h-56 p-6 bg-[#0f172a] border border-gray-700/50 rounded-2xl shadow-xl hover:border-green-500/50 transition-all duration-300 group-hover:shadow-green-500/10"
                >
                  <div className="relative mb-4">
                    <div className="absolute inset-0 bg-green-500/20 rounded-full blur-xl opacity-50 group-hover:opacity-100 transition-opacity"></div>
                    <div className="relative w-20 h-20 flex items-center justify-center bg-gradient-to-br from-green-500/10 to-emerald-600/10 rounded-full border border-green-500/30">
                      <span className="material-symbols-outlined text-4xl text-green-400">cloud_upload</span>
                    </div>
                  </div>
                  <span className="text-lg font-bold text-white mb-1">Importuj z CSV</span>
                  <span className="text-xs text-gray-400 text-center px-2">Załaduj dane kart z pliku</span>
                </button>
              </div>
            </div>
          </div>
        )}

        {scanMode === 'image' && !scanSubMode && (
          <div className="flex flex-col items-center justify-center min-h-[60vh] p-4 relative">
            {/* Back button */}
            <button 
              onClick={() => setScanMode('choice')} 
              className="absolute top-4 left-4 flex items-center gap-2 px-3 py-2 text-gray-400 hover:text-cyan-400 bg-gray-800/50 hover:bg-gray-800 rounded-lg border border-gray-700/50 hover:border-cyan-500/30 transition-all duration-300"
            >
              <span className="material-symbols-outlined text-lg">arrow_back</span>
              <span className="text-sm">Wstecz</span>
            </button>

            {/* Header */}
            <div className="text-center mb-10">
              <div className="inline-flex items-center justify-center w-16 h-16 mb-4 bg-gradient-to-br from-cyan-500/20 to-blue-600/20 rounded-full border border-cyan-500/30">
                <span className="material-symbols-outlined text-3xl text-cyan-400">computer</span>
              </div>
              <h3 className="text-2xl font-bold text-white mb-2">Wybierz tryb skanowania</h3>
              <p className="text-gray-400 text-sm">Prześlij pojedynczy plik lub cały folder</p>
            </div>
            
            {/* Cards */}
            <div className="flex flex-wrap justify-center gap-6">
              {/* Pojedynczy plik */}
              <div className="relative group">
                <div className="absolute -inset-1 bg-gradient-to-r from-cyan-500/30 to-blue-500/30 rounded-2xl blur-lg opacity-0 group-hover:opacity-100 transition duration-500"></div>
                <button 
                  onClick={() => setScanSubMode('single')} 
                  className="relative flex flex-col items-center justify-center w-52 h-56 p-6 bg-[#0f172a] border border-gray-700/50 rounded-2xl shadow-xl hover:border-cyan-500/50 transition-all duration-300 group-hover:shadow-cyan-500/10"
                >
                  <div className="relative mb-4">
                    <div className="absolute inset-0 bg-cyan-500/20 rounded-full blur-xl opacity-50 group-hover:opacity-100 transition-opacity"></div>
                    <div className="relative w-20 h-20 flex items-center justify-center bg-gradient-to-br from-cyan-500/10 to-blue-600/10 rounded-full border border-cyan-500/30">
                      <span className="material-symbols-outlined text-4xl text-cyan-400">image</span>
                    </div>
                  </div>
                  <span className="text-lg font-bold text-white mb-1">Pojedynczy plik</span>
                  <span className="text-xs text-gray-400 text-center px-2">Prześlij jeden obraz karty</span>
                </button>
              </div>

              {/* Cały folder - Batch Scan */}
              <div className="relative group">
                <div className="absolute -inset-1 bg-gradient-to-r from-purple-500/30 to-pink-500/30 rounded-2xl blur-lg opacity-0 group-hover:opacity-100 transition duration-500"></div>
                <button 
                  onClick={() => onBatchScan?.()} 
                  className="relative flex flex-col items-center justify-center w-52 h-56 p-6 bg-[#0f172a] border border-gray-700/50 rounded-2xl shadow-xl hover:border-purple-500/50 transition-all duration-300 group-hover:shadow-purple-500/10"
                >
                  <div className="relative mb-4">
                    <div className="absolute inset-0 bg-purple-500/20 rounded-full blur-xl opacity-50 group-hover:opacity-100 transition-opacity"></div>
                    <div className="relative w-20 h-20 flex items-center justify-center bg-gradient-to-br from-purple-500/10 to-pink-600/10 rounded-full border border-purple-500/30">
                      <span className="material-symbols-outlined text-4xl text-purple-400">folder_open</span>
                    </div>
                  </div>
                  <span className="text-lg font-bold text-white mb-1">Cały katalog</span>
                  <span className="text-xs text-gray-400 text-center px-2">Prześlij wiele kart naraz</span>
                </button>
              </div>
            </div>
          </div>
        )}

        {scanMode === 'image' && scanSubMode && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="lg:col-span-1 flex flex-col items-center gap-3">
              {isAndroid ? (
                <div 
                  className="fixed inset-0 z-50 bg-black md:relative md:w-full md:aspect-[63/88] md:rounded-lg md:overflow-hidden"
                  onClick={(e) => {
                    // Tap to resume if paused
                    if (result && scanResult) {
                      // User tapped - could be to resume or interact
                      // Don't interfere with button clicks
                      const target = e.target as HTMLElement;
                      if (!target.closest('button')) {
                        // Tapped on video area - show hint to use confirm button
                      }
                    }
                  }}
                >
                  {/* Video feed */}
                  <video ref={videoRef} autoPlay playsInline muted className="absolute inset-0 w-full h-full object-cover"></video>
                  
                  {/* Canvas overlay */}
                  <canvas ref={overlayCanvasRef} className="absolute inset-0 w-full h-full pointer-events-none"></canvas>
                  
                  {/* Scanning indicator - modern ripple effect */}
                  {analyzing && (
                    <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 pointer-events-none">
                      <div className="relative w-16 h-16">
                        {/* Pulsing rings */}
                        <div className="absolute inset-0 rounded-full bg-primary/20 animate-ping"></div>
                        <div className="absolute inset-2 rounded-full bg-primary/30 animate-pulse"></div>
                        {/* Center icon */}
                        <div className="absolute inset-0 flex items-center justify-center">
                          <span className="material-symbols-outlined text-primary text-4xl animate-pulse">qr_code_scanner</span>
                        </div>
                      </div>
                    </div>
                  )}
                  
                  {/* Top status bar - glassmorphism */}
                  {status && (
                    <div className="absolute top-0 left-0 right-0 bg-gradient-to-b from-black/70 via-black/50 to-transparent backdrop-blur-md">
                      <div className="p-4">
                        <div className="flex items-center justify-center gap-2">
                          <span className="material-symbols-outlined text-primary text-sm animate-pulse">visibility</span>
                          <span className="text-white font-semibold text-sm">{status}</span>
                        </div>
                        {qualityLive && (
                          <div className="mt-2">
                            {/* Quality progress bar */}
                            <div className="w-full bg-gray-800/50 rounded-full h-1.5 overflow-hidden">
                              <div 
                                className={`h-full rounded-full transition-all duration-300 ${
                                  qualityLive > 0.7 ? 'bg-green-500' : 
                                  qualityLive > 0.55 ? 'bg-yellow-500' : 'bg-red-500'
                                }`}
                                style={{ width: `${(qualityLive * 100).toFixed(0)}%` }}
                              ></div>
                            </div>
                            <p className="text-center text-xs text-gray-300 mt-1">
                              Jakość: {(qualityLive * 100).toFixed(0)}%
                            </p>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                  
                  {initStatus && <div className="absolute inset-0 flex items-center justify-center bg-black bg-opacity-75 text-white text-lg">{initStatus}</div>}
                  
                  {/* Bottom card preview - Modern card design */}
                  {scanResult && scanResult.candidates && scanResult.candidates.length > 0 && (
                    <div className="absolute bottom-32 left-4 right-4 animate-slide-up">
                      <div className="bg-white/10 backdrop-blur-2xl rounded-3xl border border-white/30 shadow-2xl overflow-hidden">
                        <div className="bg-gradient-to-br from-primary/20 to-blue-600/20 p-4">
                          <div className="flex items-center gap-4">
                            {/* Card thumbnail with glow */}
                            {scanResult.candidates[0]?.image && (
                              <div className="flex-shrink-0 relative">
                                <div className="absolute inset-0 bg-primary/30 rounded-xl blur-xl"></div>
                                <img 
                                  src={scanResult.candidates[0].image} 
                                  alt={scanResult.detected?.name || 'Card'}
                                  className="relative w-20 h-auto rounded-xl shadow-2xl border-2 border-white/40"
                                />
                              </div>
                            )}
                            
                            {/* Card info */}
                            <div className="flex-grow min-w-0">
                              <div className="flex items-start gap-2 mb-1">
                                <span className="material-symbols-outlined text-green-400 text-sm">check_circle</span>
                                <h3 className="text-white font-bold text-base leading-tight flex-grow">
                                  {scanResult.detected?.name || scanResult.candidates[0]?.name || 'Unknown'}
                                </h3>
                              </div>
                              <p className="text-gray-200 text-xs">
                                {scanResult.detected?.set || scanResult.candidates[0]?.set || 'Unknown Set'}
                                {(scanResult.detected?.number || scanResult.candidates[0]?.number) && (
                                  <span className="text-primary font-bold ml-1">
                                    • #{scanResult.detected?.number || scanResult.candidates[0]?.number}
                                  </span>
                                )}
                              </p>
                              {scanResult.detected?.price_pln_final && (
                                <div className="mt-2 flex items-baseline gap-1">
                                  <span className="text-white text-2xl font-black">
                                    {scanResult.detected.price_pln_final.toFixed(2)}
                                  </span>
                                  <span className="text-gray-300 text-sm font-medium">PLN</span>
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Controls bar - modern floating design */}
                  <div className="absolute bottom-0 left-0 right-0 pb-safe">
                    {/* Glassmorphic control panel */}
                    <div className="bg-gradient-to-t from-black/90 via-black/70 to-transparent backdrop-blur-xl pt-8 pb-6">
                      <div className="flex justify-around items-center px-6">
                        {/* Left - Torch */}
                        <div className="flex-shrink-0">
                          {torchSupported && onToggleTorch ? (
                            <button
                              onClick={onToggleTorch}
                              className={`p-4 rounded-2xl transition-all duration-300 ${
                                torchOn 
                                  ? 'bg-yellow-500 shadow-lg shadow-yellow-500/50' 
                                  : 'bg-white/10 backdrop-blur-md border border-white/20 hover:bg-white/20'
                              }`}
                              title="Latarka"
                            >
                              <span className="material-symbols-outlined text-2xl text-white">
                                {torchOn ? 'flashlight_on' : 'flashlight_off'}
                              </span>
                            </button>
                          ) : (
                            <div className="w-14"></div>
                          )}
                        </div>
                        
                        {/* Center - Capture button */}
                        <div className="flex-shrink-0 -mt-12">
                          {onForceCommit && (
                            <div className="relative">
                              {/* Outer glow ring */}
                              <div className="absolute inset-0 rounded-full bg-primary/30 blur-xl animate-pulse"></div>
                              {/* Button */}
                              <button
                                onClick={onForceCommit}
                                disabled={analyzing}
                                className="relative w-20 h-20 rounded-full bg-gradient-to-br from-primary to-blue-600 text-white shadow-2xl transition-all duration-300 hover:scale-110 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed border-4 border-white/40"
                                title="Zrób zdjęcie"
                              >
                                <span className="material-symbols-outlined text-4xl">photo_camera</span>
                              </button>
                            </div>
                          )}
                        </div>
                        
                        {/* Right - Placeholder for symmetry */}
                        <div className="flex-shrink-0 w-14"></div>
                      </div>
                    </div>
                  </div>
                  
                  {/* Zoom slider - modern glassmorphic design */}
                  {zoomCaps && setZoom && (
                    <div className="absolute top-safe-top left-4 right-4 mt-20">
                      <div className="bg-white/10 backdrop-blur-xl rounded-2xl px-5 py-4 border border-white/20 shadow-2xl">
                        <div className="flex items-center gap-4">
                          <div className="flex-shrink-0 w-8 h-8 rounded-full bg-white/10 flex items-center justify-center">
                            <span className="material-symbols-outlined text-white text-lg">zoom_out</span>
                          </div>
                          <input
                            type="range"
                            min={zoomCaps.min}
                            max={zoomCaps.max}
                            step={zoomCaps.step}
                            defaultValue={1}
                            onChange={(e) => setZoom(parseFloat(e.target.value))}
                            className="flex-grow h-2 bg-white/20 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-5 [&::-webkit-slider-thumb]:h-5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-primary [&::-webkit-slider-thumb]:shadow-lg [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-white [&::-moz-range-thumb]:w-5 [&::-moz-range-thumb]:h-5 [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:bg-primary [&::-moz-range-thumb]:border-2 [&::-moz-range-thumb]:border-white [&::-moz-range-thumb]:shadow-lg"
                          />
                          <div className="flex-shrink-0 w-8 h-8 rounded-full bg-white/10 flex items-center justify-center">
                            <span className="material-symbols-outlined text-white text-lg">zoom_in</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  {tapFocusSupported && onTapToFocus && focusPt && (
                    <div
                      className="absolute border-2 border-blue-500 rounded-full animate-ping"
                      style={{
                        left: `${focusPt.x * 100}%`,
                        top: `${focusPt.y * 100}%`,
                        width: '20px',
                        height: '20px',
                        transform: 'translate(-50%, -50%)',
                      }}
                    ></div>
                  )}

                </div>
              ) : (
                <>
                  <div className="grid grid-cols-2 gap-4 w-full">
                      <div>
                          <label className="text-xs text-gray-400 block text-center mb-1">Twój skan</label>
                          <div 
                              className="scan-preview-container"
                              onMouseEnter={(e) => {
                                  const magnifier = e.currentTarget.querySelector('.magnifier') as HTMLDivElement;
                                  if (magnifier) magnifier.style.display = 'block';
                              }}
                              onMouseLeave={(e) => {
                                  const magnifier = e.currentTarget.querySelector('.magnifier') as HTMLDivElement;
                                  if (magnifier) magnifier.style.display = 'none';
                              }}
                              onMouseMove={(e) => {
                                  const target = e.currentTarget;
                                  const img = target.querySelector('img');
                                  const magnifier = target.querySelector('.magnifier') as HTMLDivElement;
                                  if (!img || !magnifier) return;

                                  const rect = target.getBoundingClientRect();
                                  const x = e.clientX - rect.left;
                                  const y = e.clientY - rect.top;

                                  const magnifierSize = 150;
                                  const zoom = 2;

                                  const bgX = -x * zoom + magnifierSize / 2;
                                  const bgY = -y * zoom + magnifierSize / 2;

                                  magnifier.style.left = `${x - magnifierSize / 2}px`;
                                  magnifier.style.top = `${y - magnifierSize / 2}px`;
                                  magnifier.style.backgroundImage = `url(${img.src})`;
                                  magnifier.style.backgroundPosition = `${bgX}px ${bgY}px`;
                                  magnifier.style.backgroundSize = `${rect.width * zoom}px ${rect.height * zoom}px`;
                              }}
                          >
                              {preview ? (
                                  <>
                                      <img src={preview} alt="podgląd" className="scan-preview-image"/>
                                      <div className="magnifier"></div>
                                  </>
                              ) : (
                                  <div className="w-full h-full flex items-center justify-center text-gray-500">Brak obrazu</div>
                              )}
                              {loading && <div className="scan-line" />}
                          </div>
                      </div>
                      <div>
                          <label className="text-xs text-gray-400 block text-center mb-1">Grafika do sklepu</label>
                          <div className="relative w-full aspect-[63/88] bg-gray-800 rounded-lg flex items-center justify-center overflow-hidden">
                          {selectedPrimaryImage.url ? (
                              <>
                                  <img src={selectedPrimaryImage.url} alt="Grafika do sklepu" className="w-full h-full object-contain"/>
                                  {finishBadge && (
                                    <div className={`absolute top-2 right-2 ${finishBadge.color} text-white font-bold rounded-full w-8 h-8 flex items-center justify-center text-sm shadow-lg border-2 border-white`}>
                                      {finishBadge.letter}
                                    </div>
                                  )}
                              </>
                          ) : (
                              <span className="text-gray-500 text-sm">Wybierz lub wgraj obraz</span>
                          )}
                          </div>
                      </div>
                  </div>

                  {/* --- Image Selection UI --- */}
                  <div className="mt-4 w-full">
                    <h3 className="text-base font-bold text-white mb-2">Wybór grafiki głównej</h3>
                    <div className="flex justify-around items-start gap-2 p-2 bg-gray-800 rounded-lg">
                      
                      {/* Option 1: TCGGO Image */}
                      {scanResult?.candidates?.[0]?.image && (
                        <div 
                          className={`flex flex-col items-center gap-2 cursor-pointer p-2 rounded-md ${selectedPrimaryImage.source === 'tcggo' ? 'bg-primary/30' : ''}`}
                          onClick={() => setSelectedPrimaryImage({ source: 'tcggo', url: scanResult.candidates[0].image })}
                        >
                          <img src={scanResult.candidates[0].image} className="w-16 h-auto rounded" />
                          <span className="text-xs text-white">TCGGO</span>
                        </div>
                      )}

                      {/* Option 2: User's Scan */}
                      {preview && (
                        <div 
                          className={`flex flex-col items-center gap-2 cursor-pointer p-2 rounded-md ${selectedPrimaryImage.source === 'scan' ? 'bg-primary/30' : ''}`}
                          onClick={() => setSelectedPrimaryImage({ source: 'scan', url: preview })}
                        >
                          <img src={preview} className="w-16 h-auto rounded" />
                          <span className="text-xs text-white">Twój skan</span>
                        </div>
                      )}

                      {/* Option 3: Custom Upload */}
                      <label className={`flex flex-col items-center gap-2 cursor-pointer p-2 rounded-md ${selectedPrimaryImage.source === 'upload' ? 'bg-primary/30' : ''}`}>
                        <div className="w-16 h-[88px] bg-gray-700 rounded flex items-center justify-center">
                          <span className="material-symbols-outlined text-white">add_photo_alternate</span>
                        </div>
                        <span className="text-xs text-white">Wgraj własne</span>
                        <input type="file" accept="image/*" className="hidden" onChange={(e) => {
                          if (e.target.files?.[0]) {
                            const file = e.target.files[0];
                            const url = URL.createObjectURL(file);
                            setSelectedPrimaryImage({ source: 'upload', url: url, file: file });
                          }
                        }} />
                      </label>
                    </div>
                  </div>

                  {/* --- Additional Images UI --- */}
                  <div className="mt-4 w-full">
                    <h3 className="text-base font-bold text-white mb-2">Dodatkowe zdjęcia (stan karty)</h3>
                    <div className="flex flex-col gap-2 p-2 bg-gray-800 rounded-lg">
                      <label className="cursor-pointer flex items-center justify-center p-4 border-2 border-dashed border-gray-600 rounded-lg hover:bg-gray-700">
                        <span className="material-symbols-outlined text-primary mr-2">add_a_photo</span>
                        <span className="text-white">Dodaj zdjęcia</span>
                        <input type="file" accept="image/*" multiple className="hidden" onChange={(e) => {
                          if (e.target.files) {
                            setAdditionalImages(prev => [...prev, ...Array.from(e.target.files)]);
                          }
                        }} />
                      </label>
                      {additionalImages.length > 0 && (
                        <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-2 mt-2">
                          {additionalImages.map((file, index) => (
                            <div key={index} className="relative">
                              <img src={URL.createObjectURL(file)} alt={`Dodatkowe zdj. ${index + 1}`} className="w-full h-auto rounded" />
                              <button 
                                className="absolute top-0 right-0 bg-red-600 text-white rounded-full p-0.5 w-5 h-5 flex items-center justify-center text-xs"
                                onClick={() => setAdditionalImages(prev => prev.filter((_, i) => i !== index))}
                              >
                                &times;
                              </button>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>

                  {scanResult?.candidates && scanResult.candidates.length > 1 && (
                    <div className="mt-4 w-full">
                      <div className="flex items-center justify-between mb-2">
                        <h3 className="text-lg font-bold text-white">Wybierz właściwą kartę:</h3>
                        <button 
                          onClick={() => setCandidatesPanelOpen(true)}
                          className="text-primary text-sm font-semibold hover:text-blue-400 transition-colors flex items-center gap-1"
                        >
                          <span className="material-symbols-outlined text-sm">open_in_new</span>
                          Zobacz wszystkie ({scanResult.candidates.length})
                        </button>
                      </div>
                      <div className="flex flex-col gap-2"> 
                        {scanResult.candidates.slice(0, 3).map((candidate: Candidate) => (
                          <div
                            key={candidate.id}
                            className="bg-gray-800 p-3 rounded-lg flex items-center gap-3 cursor-pointer hover:bg-gray-700 transition-colors border border-gray-700 hover:border-primary"
                            onClick={() => handleCandidateSelect(candidate)}
                          >
                            <img src={candidate.image || ''} alt={candidate.name} className="w-16 h-auto rounded-md shadow-md" />
                            <div className="text-sm flex-grow">
                              <p className="font-bold text-white text-base mb-1">
                                {candidate.name || 'Brak nazwy'}
                              </p>
                              <div className="flex flex-wrap gap-2 text-xs">
                                {candidate.set && (
                                  <span className="font-semibold text-gray-300">{candidate.set}</span>
                                )}
                                {candidate.number && (
                                  <span className="text-primary font-bold">#{candidate.number}</span>
                                )}
                                {!candidate.set && !candidate.number && (
                                  <span className="text-gray-500 italic">Brak dodatkowych informacji</span>
                                )}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {showFileInputs && scanSubMode === 'single' && (
                    <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4 w-full">
                        <label htmlFor="file-upload" className="cursor-pointer flex flex-col items-center justify-center p-6 bg-gray-800 rounded-lg shadow-lg hover:bg-gray-700 transition-colors duration-200 text-center">
                            <span className="material-symbols-outlined text-4xl text-primary mb-2">image</span>
                            <span className="text-md font-bold text-white">Wgraj plik</span>
                            <span className="text-xs text-gray-400 mt-1">Pojedynczy obraz karty</span>
                            <input id="file-upload" type="file" accept="image/*" capture="environment" onChange={onFile} className="hidden" />
                        </label>
                    </div>
                  )}
                  {showFileInputs && scanSubMode === 'folder' && (
                    <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4 w-full">
                        <label htmlFor="folder-upload" className="cursor-pointer flex flex-col items-center justify-center p-6 bg-gray-800 rounded-lg shadow-lg hover:bg-gray-700 transition-colors duration-200 text-center">
                            <span className="material-symbols-outlined text-4xl text-primary mb-2">folder_open</span>
                            <span className="text-md font-bold text-white">Wgraj folder</span>
                            <span className="text-xs text-gray-400 mt-1">Cały folder ze skanami</span>
                            <input id="folder-upload" type="file" webkitdirectory="" mozdirectory="" directory="" onChange={onFolderChange} className="hidden" />
                        </label>
                    </div>
                  )}
                  {showFileInputs && (
                  <div className="mt-3">
                    <button onClick={onSubmit} disabled={loading} className="rounded-lg h-10 px-4 bg-primary text-white text-sm font-bold disabled:opacity-60">{loading && <span className="spinner" />} {loading ? 'Skanuję…' : 'Wyślij do analizy'}</button>
                  </div>
                  )}
                </>
              )}
            </div>

            <div className="lg:col-span-1">
              {scanResult && !isAndroid && (
                <div className="flex flex-col gap-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="col-span-2 flex items-end gap-2">
                      <div className="flex-grow">
                        <label className="text-xs text-gray-400">Nazwa</label>
                        <input type="text" value={formData.name || ''} onChange={(e) => setFormData({...formData, name: e.target.value})} className="w-full p-2 rounded bg-gray-700 text-white" />
                      </div>
                      <button 
                        onClick={() => {
                          const cardNumber = formData.number ? formData.number.split('/')[0] : '';
                          const searchString = `${formData.name || ''} ${cardNumber}`.trim();
                          if (searchString) {
                            window.open(`https://www.cardmarket.com/en/Pokemon/Products/Search?category=-1&searchString=${encodeURIComponent(searchString)}&searchMode=v1`, '_blank');
                          }
                        }}
                        className="h-10 w-10 flex items-center justify-center rounded-lg bg-blue-600 text-white text-sm font-bold relative group"
                        disabled={!formData.name && !formData.number}
                      >
                        <span className="material-symbols-outlined">storefront</span>
                        <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 hidden w-auto p-2 text-xs text-white whitespace-nowrap bg-gray-800 rounded-md group-hover:block">Szukaj na Cardmarket</span>
                      </button>
                    </div>
                    <div>
                      <label className="text-xs text-gray-400">Numer</label>
                      <input type="text" value={formData.number || ''} onChange={(e) => setFormData({...formData, number: e.target.value})} className="w-full p-2 rounded bg-gray-700 text-white" />
                    </div>
                    <div>
                      <label className="text-xs text-gray-400">Zestaw</label>
                      <select
                        className="w-full p-2 rounded bg-gray-700 text-white"
                        value={formData.set_id || ''}
                        onChange={(e) => {
                          const selectedCategoryId = e.target.value;
                          const selectedCategory = shoperCategories?.find(c => String(c.category_id) === selectedCategoryId);
                          setFormData({
                            ...formData,
                            set_id: selectedCategoryId,
                            set: selectedCategory ? selectedCategory.name : ''
                          });
                        }}
                      >
                        <option value="">-- Wybierz zestaw --</option>
                        {shoperCategories?.sort((a, b) => a.name.localeCompare(b.name)).map((cat: any) => (
                          <option key={cat.category_id} value={cat.category_id}>
                            {cat.name}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-2 items-end">
                    <div>
                      <label className="text-xs text-gray-400">Cena (PLN)</label>
                      <input 
                        type="number" 
                        step="0.01" 
                        value={formData.price_pln_final || ''} 
                        onChange={(e) => {
                          setManualPriceEdit(true);
                          setFormData({...formData, price_pln_final: parseFloat(e.target.value)});
                        }} 
                        className="w-full p-2 rounded bg-gray-700 text-white" 
                      />
                    </div>
                    <button onClick={handleFetchPrice} className="w-full h-10 rounded-lg bg-primary text-white text-sm font-bold">Pobierz z CM</button>
                  </div>

                  <div className="grid grid-cols-2 gap-2 items-end">
                    <div>
                      <label className="text-xs text-gray-400">Cena manualna (EUR)</label>
                      <input type="number" step="0.01" onChange={(e) => setManualPrice(parseFloat(e.target.value))} className="w-full p-2 rounded bg-gray-700 text-white" />
                    </div>
                    <button onClick={handleCalculatePrice} className="w-full h-10 rounded-lg bg-primary text-white text-sm font-bold">Przelicz</button>
                  </div>

                                    <div className="flex flex-col gap-4 mt-4">
                                      <h3 className="text-lg font-bold text-white col-span-2">Atrybuty Shoper</h3>
                                      <div className="grid grid-cols-2 gap-4">
                                        {shoperAttributes && shoperAttributes.map((attr: any) => (
                                          <div key={attr.attribute_id}>
                                            <label className="text-xs text-gray-400">{attr.name}</label>
                                            <select 
                                              className="w-full p-2 rounded bg-gray-700 text-white"
                                              value={formData[attr.attribute_id] || ''}
                                              onChange={(e) => handleAttributeChange(attr.attribute_id, e.target.value)}
                                            >
                                              <option value="">-</option>
                                              {attr.options.map((opt: any) => (
                                                <option key={opt.option_id} value={opt.option_id}>{opt.value}</option>
                                              ))}
                                            </select>
                                          </div>
                                        ))}
                                      </div>
                                    </div>
                  <div className="mt-4">
                    <label className="text-xs text-gray-400">Kod produktu</label>
                    <input type="text" value={productCode} readOnly className="w-full p-2 rounded bg-gray-800 text-gray-400" />
                  </div>

                  <div className="mt-4 p-3 rounded-lg bg-gray-800 border border-gray-700">
                    <label className="text-xs text-gray-400 block mb-1">Lokalizacja Magazynowa</label>
                    {scanResult?.warehouse_code ? (
                      <p className="text-lg font-bold text-green-400">{scanResult.warehouse_code}</p>
                    ) : (
                      <p className="text-lg font-bold text-yellow-400">karton premium</p>
                    )}
                  </div>

                  <div className="mt-4 flex justify-end gap-2">
                    {scanSubMode === 'single' && (
                        <button onClick={async () => {
                            if (!scanResult?.scan_id) return;
                            try {
                                const data = new FormData();

                                // Helper to resolve attribute option_id to text value
                                const resolveAttribute = (attrId: string, optionId: string): string | null => {
                                  const attr = shoperAttributes?.find(a => a.attribute_id === attrId);
                                  if (!attr) return null;
                                  const option = attr.options.find((o: any) => o.option_id === optionId);
                                  return option ? option.value : null;
                                };

                                // Build detected object with BOTH plain fields AND attribute mappings
                                const detectedPayload = {
                                  // Plain fields for confirm_candidate
                                  name: formData.name,
                                  number: formData.number,
                                  set: formData.set,
                                  set_id: formData.set_id,
                                  set_code: formData.set_code,
                                  price_pln_final: formData.price_pln_final,
                                  
                                  // Resolve attribute values to plain text for confirm_candidate
                                  energy: formData['63'] ? resolveAttribute('63', formData['63']) : null,
                                  rarity: formData['38'] ? resolveAttribute('38', formData['38']) : null,
                                  language: formData['64'] ? resolveAttribute('64', formData['64']) : null,
                                  condition: formData['66'] ? resolveAttribute('66', formData['66']) : null,
                                  variant: formData['65'] ? resolveAttribute('65', formData['65']) : null,
                                  
                                  // Keep attribute IDs for Shoper publication
                                  '38': formData['38'], // Rarity
                                  '63': formData['63'], // Energy
                                  '64': formData['64'], // Language
                                  '65': formData['65'], // Finish
                                  '66': formData['66'], // Condition
                                };

                                // 1. Append main form data as a JSON string
                                data.append('data', JSON.stringify({
                                    scan_id: scanResult.scan_id,
                                    candidate_id: scanResult.candidates[0].id,
                                    detected: detectedPayload
                                }));

                                // 2. Append primary image
                                data.append('primary_image_source', selectedPrimaryImage.source);
                                if (selectedPrimaryImage.source === 'upload' && selectedPrimaryImage.file) {
                                    data.append('primary_image', selectedPrimaryImage.file);
                                } else if (selectedPrimaryImage.url) {
                                    // For 'tcggo' or 'scan', send the URL/data URL
                                    data.append('primary_image_url', selectedPrimaryImage.url);
                                }

                                // 3. Append additional images
                                additionalImages.forEach((file, index) => {
                                    data.append(`additional_image_${index}`, file);
                                });

                                const res = await fetch(`/api/scans/${scanResult.scan_id}/publish`, { 
                                    method: 'POST',
                                    body: data // FormData object
                                });
                                const responseData = await res.json();
                                if (res.ok) {
                                    // Handle success for both new products and duplicate updates
                                    if (responseData.message && responseData.message.includes("Updated existing product")) {
                                        setToast({ message: responseData.message, type: 'success' });
                                    } else {
                                        const productId = responseData.json?.product_id || responseData.shoper_id || responseData.id;
                                        setToast({ message: `Opublikowano produkt: ${productId}`, type: 'success' });
                                    }
                                    setScanResult(null);
                                    setAdditionalImages([]);
                                } else {
                                    const errorText = responseData.details?.text || responseData.error || 'Błąd podczas publikowania';
                                    setToast({ message: errorText, type: 'error' });
                                }
                            } catch (e) {
                                console.error("Failed to publish scan", e);
                                setToast({ message: 'Błąd podczas publikowania', type: 'error' });
                            }
                        }} disabled={!formData.name || !formData.number || !formData.set} className="rounded-lg h-10 px-4 bg-primary text-white text-sm font-bold disabled:opacity-60">Publikuj</button>
                    )}
                    {scanSubMode === 'folder' && (
                        <>
                            <button onClick={() => onConfirm(formData, { primary: selectedPrimaryImage, additional: additionalImages })} disabled={!formData.name || !formData.number || !formData.set} className="rounded-lg h-10 px-4 bg-primary text-white text-sm font-bold disabled:opacity-60">Zapisz i dalej</button>
                            <button onClick={async () => {
                              if (!session) return;
                              try {
                                const res = await fetch(`/api/sessions/${session.id}/publish`, { method: 'POST' });
                                const data = await res.json();
                                setToast({ message: `Opublikowano: ${data.published}`, type: 'success' });
                              } catch (e) {
                                console.error("Failed to publish session", e);
                                setToast({ message: 'Błąd podczas publikowania sesji', type: 'error' });
                              }
                            }} className="rounded-lg h-10 px-4 bg-green-600 text-white text-sm font-bold">Zakończ i zapisz</button>
                        </>
                    )}
                  </div>


                </div>
              )}
            </div>
          </div>
        )}
        {scanMode === 'csv' && (
          <div className="text-center">
            <h3 className="text-xl font-bold text-white mb-4">Importuj z pliku CSV</h3>
            <div className="flex justify-center">
              <input type="file" accept=".csv" onChange={onCsvUpload} className="block w-full max-w-md text-sm text-gray-300 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-primary file:text-white hover:file:bg-primary/90" />
            </div>
          </div>
        )}
      </main>

      {/* Slide-out panel for full candidates list */}
      <SlideOutPanel isOpen={candidatesPanelOpen} onClose={() => setCandidatesPanelOpen(false)}>
        <div className="flex flex-col h-full">
          <div className="flex items-center justify-between mb-4 pb-3 border-b border-gray-700">
            <h2 className="text-xl font-bold text-white">Wszystkie kandydaci ({scanResult?.candidates?.length || 0})</h2>
            <button 
              onClick={() => setCandidatesPanelOpen(false)}
              className="text-gray-400 hover:text-white transition-colors"
            >
              <span className="material-symbols-outlined">close</span>
            </button>
          </div>
          
          <div className="flex-grow overflow-y-auto space-y-3">
            {scanResult?.candidates?.map((candidate: Candidate, index: number) => (
              <div
                key={candidate.id}
                className="bg-gray-900 p-3 rounded-lg cursor-pointer hover:bg-gray-800 transition-colors border border-gray-700 hover:border-primary"
                onClick={() => {
                  handleCandidateSelect(candidate);
                  setCandidatesPanelOpen(false);
                }}
              >
                <div className="flex items-start gap-3">
                  <div className="flex-shrink-0">
                    {candidate.image ? (
                      <img 
                        src={candidate.image} 
                        alt={candidate.name} 
                        className="w-20 h-auto rounded-md shadow-lg"
                      />
                    ) : (
                      <div className="w-20 h-28 bg-gray-700 rounded-md flex items-center justify-center">
                        <span className="material-symbols-outlined text-gray-500">image_not_supported</span>
                      </div>
                    )}
                  </div>
                  
                  <div className="flex-grow min-w-0">
                    <div className="flex items-start justify-between gap-2 mb-1">
                      <p className="font-bold text-white text-sm leading-tight">
                        {candidate.name}
                      </p>
                      <span className="text-xs text-gray-500 flex-shrink-0">#{index + 1}</span>
                    </div>
                    
                    <div className="space-y-1">
                      {candidate.set && (
                        <p className="text-xs text-gray-400">
                          <span className="text-gray-500">Zestaw:</span>{' '}
                          <span className="font-semibold text-gray-300">{candidate.set}</span>
                        </p>
                      )}
                      
                      {candidate.number && (
                        <p className="text-xs text-gray-400">
                          <span className="text-gray-500">Numer:</span>{' '}
                          <span className="font-semibold text-primary">{candidate.number}</span>
                        </p>
                      )}
                      
                      <div className="flex items-center gap-2 mt-2">
                        <div className="flex-grow bg-gray-800 rounded-full h-1.5">
                          <div 
                            className="bg-primary h-1.5 rounded-full transition-all"
                            style={{ width: `${(candidate.score || 0) * 100}%` }}
                          ></div>
                        </div>
                        <span className="text-xs text-gray-500 flex-shrink-0">
                          {((candidate.score || 0) * 100).toFixed(0)}%
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </SlideOutPanel>
    </div>
  );
}
