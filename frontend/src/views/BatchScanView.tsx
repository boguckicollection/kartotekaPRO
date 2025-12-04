import React, { useState, useCallback, useEffect, useRef } from 'react';

// Helper for finish mapping (same as Scan.tsx)
const FINISH_MAP: Record<string, string> = {
  '184': 'normal',  // Normal
  '149': 'holo',    // Holo
  '150': 'reverse', // Reverse Holo
  '151': 'holo',    // Full Art (treat as holo pricing)
  '155': 'normal',  // PokéBall Pattern
  '156': 'holo',    // MasterBall Pattern
  '157': 'holo',    // Gold (premium)
  '158': 'holo',    // Rainbow (premium)
};

type BatchItem = {
  id: number;
  filename: string;
  status: 'pending' | 'processing' | 'success' | 'failed';
  image_url?: string;
  
  // Detected
  detected_name?: string;
  detected_set?: string;
  detected_number?: string;
  
  // Matched
  matched_name?: string;
  matched_set?: string;
  matched_number?: string;
  matched_image?: string;
  match_score?: number;
  matched_provider_id?: string;
  
  // Pricing
  price_eur?: number;
  price_pln?: number;
  price_pln_final?: number;
  variants?: any[]; // Pricing variants
  
  // Attributes (option IDs)
  attr_language?: string;
  attr_condition?: string;
  attr_finish?: string;
  attr_rarity?: string;
  attr_energy?: string;
  attr_card_type?: string;
  
  // Duplicates
  duplicate_of_scan_id?: number;
  duplicate_distance?: number;
  
  // Warehouse
  warehouse_code?: string;
  
  // Images
  use_tcggo_image?: boolean;
  additional_images?: string[]; // URLs to additional uploaded images
  
  // Meta
  fields_complete?: number;
  fields_total?: number;
  error_message?: string;
  cardmarket_url?: string;
  publish_status?: string;
  candidates?: any[];
};

type BatchStatus = {
  batch_id: number;
  status: 'pending' | 'processing' | 'completed';
  total_items: number;
  processed_items: number;
  successful_items: number;
  failed_items: number;
  current_filename?: string;
  progress_percent: number;
};

type Props = {
  apiBase: string;
  onBack: () => void;
  session?: {id: number, starting_warehouse_code?: string | null} | null;
};

export default function BatchScanView({ apiBase, onBack, session }: Props) {
  const [batchId, setBatchId] = useState<number | null>(null);
  const [status, setStatus] = useState<BatchStatus | null>(null);
  const [items, setItems] = useState<BatchItem[]>([]);
  const [selectedItem, setSelectedItem] = useState<BatchItem | null>(null);
  
  // Global data
  const [shoperAttributes, setShoperAttributes] = useState<any[]>([]);
  const [shoperCategories, setShoperCategories] = useState<any[]>([]);
  
  const [isUploading, setIsUploading] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isPublishing, setIsPublishing] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [additionalImagesToUpload, setAdditionalImagesToUpload] = useState<File[]>([]);
  
  const fileInputRef = useRef<HTMLInputElement>(null);
  const processingRef = useRef(false);
  const drawerRef = useRef<HTMLDivElement>(null);

  // Load attributes on mount
  useEffect(() => {
    const loadData = async () => {
      try {
        const [attrRes, catRes] = await Promise.all([
          fetch(`${apiBase}/shoper/attributes`),
          fetch(`${apiBase}/shoper/categories`)
        ]);
        const attrs = await attrRes.json();
        const cats = await catRes.json();
        setShoperAttributes(attrs.items || []);
        setShoperCategories(cats.items || []);
      } catch (e) {
        console.error("Failed to load shoper data", e);
      }
    };
    loadData();
  }, [apiBase]);

  useEffect(() => {
    if (toast) {
      const t = setTimeout(() => setToast(null), 3000);
      return () => clearTimeout(t);
    }
  }, [toast]);

  // Keyboard navigation in edit drawer
  useEffect(() => {
    if (!selectedItem) return;
    
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
        e.preventDefault();
        
        const currentIndex = items.findIndex(it => it.id === selectedItem.id);
        let nextIndex = -1;
        
        if (e.key === 'ArrowLeft' && currentIndex > 0) {
          nextIndex = currentIndex - 1;
        } else if (e.key === 'ArrowRight' && currentIndex < items.length - 1) {
          nextIndex = currentIndex + 1;
        }
        
        if (nextIndex !== -1) {
          // Save current changes before navigating
          updateItem(selectedItem.id, {
            matched_name: selectedItem.matched_name,
            matched_set: selectedItem.matched_set,
            matched_number: selectedItem.matched_number,
            matched_image: selectedItem.matched_image,
            matched_provider_id: selectedItem.matched_provider_id,
            price_pln_final: selectedItem.price_pln_final,
            warehouse_code: selectedItem.warehouse_code,
            attr_language: selectedItem.attr_language,
            attr_condition: selectedItem.attr_condition,
            attr_finish: selectedItem.attr_finish,
            attr_rarity: selectedItem.attr_rarity,
            attr_energy: selectedItem.attr_energy,
            attr_card_type: selectedItem.attr_card_type,
          });
          
          // Navigate to next item
          setSelectedItem(items[nextIndex]);
          setAdditionalImagesToUpload([]); // Clear additional images when navigating
        }
      }
    };
    
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [selectedItem, items]);

  // Handle attribute change with price logic
  const handleItemAttributeChange = (item: BatchItem, attrId: string, value: string) => {
    const updates: Partial<BatchItem> = {};
    
    // Map generic attrId to specific field
    if (attrId === '64') updates.attr_language = value;
    if (attrId === '66') updates.attr_condition = value;
    if (attrId === '65') updates.attr_finish = value;
    if (attrId === '38') updates.attr_rarity = value;
    if (attrId === '63') updates.attr_energy = value;
    if (attrId === '39') updates.attr_card_type = value;
    
    // Price logic for Finish (65)
    if (attrId === '65' && item.variants) {
      const finishType = FINISH_MAP[value] || 'normal';
      let targetLabel = 'Normal';
      if (finishType === 'holo') targetLabel = 'Holo';
      if (finishType === 'reverse') targetLabel = 'Reverse Holo';
      
      const variant = item.variants.find((v: any) => v.label === targetLabel);
      // Fallback to Normal if specific variant not found
      const normalVariant = item.variants.find((v: any) => v.label === 'Normal');
      
      const bestVariant = variant || normalVariant;
      
      if (bestVariant && bestVariant.price_pln_final) {
        updates.price_pln_final = bestVariant.price_pln_final;
      }
    }
    
    return updates;
  };

  // Handle candidate selection
  const handleCandidateSelect = (item: BatchItem, candidate: any) => {
    return {
      matched_name: candidate.name,
      matched_set: candidate.set,
      matched_number: candidate.number,
      matched_image: candidate.image,
      matched_provider_id: candidate.id,
      match_score: candidate.score,
    };
  };

  // Handle file upload
  const handleUpload = async (files: FileList | File[]) => {
    const imageFiles = Array.from(files).filter(f => f.type.startsWith('image/'));
    if (imageFiles.length === 0) {
      setToast('Wybierz pliki graficzne (JPG, PNG)');
      return;
    }

    setIsUploading(true);
    try {
      const fd = new FormData();
      imageFiles.forEach(file => fd.append('files', file));
      
      // Add session info if available
      if (session?.id) {
        fd.append('session_id', session.id.toString());
      }
      if (session?.starting_warehouse_code) {
        fd.append('starting_warehouse_code', session.starting_warehouse_code);
      }

      const res = await fetch(`${apiBase}/batch/start`, {
        method: 'POST',
        body: fd,
      });
      const data = await res.json();
      
      if (res.ok) {
        setBatchId(data.batch_id);
        setStatus({
          batch_id: data.batch_id,
          status: 'pending',
          total_items: data.total_items,
          processed_items: 0,
          successful_items: 0,
          failed_items: 0,
          progress_percent: 0,
        });
        // Initial items with temporary ID
        setItems(data.items.map((it: any, idx: number) => ({
          id: idx,
          filename: it.filename,
          status: it.status || 'pending',
        })));
        setToast(`Wgrano ${imageFiles.length} plikow`);
        
        // Fetch full items list from backend to get real IDs
        try {
          const itemsRes = await fetch(`${apiBase}/batch/${data.batch_id}/items`);
          const itemsData = await itemsRes.json();
          if (itemsRes.ok && itemsData.items) {
            setItems(itemsData.items);
          }
        } catch (e) {
          console.error('Failed to fetch items after upload:', e);
        }
      } else {
        setToast(data.error || 'Blad wgrywania');
      }
    } catch (e) {
      setToast('Blad sieci');
    } finally {
      setIsUploading(false);
    }
  };

  // Start processing
  const startProcessing = async () => {
    if (!batchId || processingRef.current) return;
    processingRef.current = true;
    setIsProcessing(true);

    while (processingRef.current) {
      try {
        const res = await fetch(`${apiBase}/batch/${batchId}/analyze-next`, {
          method: 'POST',
        });
        const data = await res.json();

        if (data.status === 'completed') {
          // All done
          processingRef.current = false;
          setIsProcessing(false);
          await refreshItems();
          await refreshStatus();
          setToast('Analiza zakonczona!');
          break;
        }

        if (data.status === 'processed' && data.item) {
          // Update item in list
          setItems(prev => prev.map(it => 
            it.filename === data.item.filename ? { ...it, ...data.item } : it
          ));
          // Update progress
          if (data.progress) {
            setStatus(prev => prev ? {
              ...prev,
              processed_items: data.progress.processed,
              progress_percent: data.progress.percent,
              current_filename: data.item.filename,
            } : null);
          }
        }
      } catch (e) {
        console.error('Processing error:', e);
        processingRef.current = false;
        setIsProcessing(false);
        setToast('Blad podczas analizy');
        break;
      }
    }
  };

  const stopProcessing = () => {
    processingRef.current = false;
    setIsProcessing(false);
  };

  const refreshItems = async () => {
    if (!batchId) return;
    try {
      const res = await fetch(`${apiBase}/batch/${batchId}/items`);
      const data = await res.json();
      if (res.ok) {
        setItems(data.items || []);
      }
    } catch (e) {
      console.error('Failed to refresh items:', e);
    }
  };

  const refreshStatus = async () => {
    if (!batchId) return;
    try {
      const res = await fetch(`${apiBase}/batch/${batchId}/status`);
      const data = await res.json();
      if (res.ok) {
        setStatus(data);
      }
    } catch (e) {
      console.error('Failed to refresh status:', e);
    }
  };

  // Update single item
  const updateItem = async (itemId: number, updates: Partial<BatchItem>, additionalFiles?: File[]) => {
    if (!batchId) return;
    try {
      // If there are additional images to upload, use FormData
      if (additionalFiles && additionalFiles.length > 0) {
        const formData = new FormData();
        
        // Add all updates as JSON
        formData.append('updates', JSON.stringify(updates));
        
        // Add additional image files
        additionalFiles.forEach((file, index) => {
          formData.append('additional_images', file);
        });
        
        const res = await fetch(`${apiBase}/batch/${batchId}/items/${itemId}`, {
          method: 'PATCH',
          body: formData,
        });
        const data = await res.json();
        if (res.ok) {
          setItems(prev => prev.map(it => it.id === itemId ? { ...it, ...updates } : it));
          setAdditionalImagesToUpload([]); // Clear uploaded files
          setToast('Zapisano zmiany i zdjęcia');
          // Refresh item to get new image URLs
          await refreshItems();
        }
      } else {
        // Standard JSON update
        const res = await fetch(`${apiBase}/batch/${batchId}/items/${itemId}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(updates),
        });
        const data = await res.json();
        if (res.ok) {
          setItems(prev => prev.map(it => it.id === itemId ? { ...it, ...updates } : it));
          setToast('Zapisano zmiany');
        }
      }
    } catch (e) {
      setToast('Blad zapisu');
    }
  };

  // Publish all
  const publishAll = async () => {
    if (!batchId) return;
    setIsPublishing(true);
    try {
      const res = await fetch(`${apiBase}/batch/${batchId}/publish`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      const data = await res.json();
      if (res.ok) {
        setToast(`Opublikowano: ${data.published_count}, Bledy: ${data.failed_count}`);
        await refreshItems();
      } else {
        setToast(data.error || 'Blad publikacji');
      }
    } catch (e) {
      setToast('Blad sieci');
    } finally {
      setIsPublishing(false);
    }
  };

  // Drag & drop handlers
  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleUpload(e.dataTransfer.files);
    }
  }, []);

  const successItems = items.filter(it => it.status === 'success');
  const readyToPublish = successItems.filter(it => !it.publish_status);

  return (
    <div className="min-h-screen bg-[#0a0f1a] text-white p-4 md:p-6">
      {/* Header */}
      <div className="flex items-center gap-4 mb-6">
        <button
          onClick={onBack}
          className="flex items-center gap-2 px-3 py-2 text-gray-400 hover:text-white transition-colors"
        >
          <span className="material-symbols-outlined">arrow_back</span>
          Wstecz
        </button>
        <h1 className="text-2xl font-bold bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">
          Skanowanie Katalogowe
        </h1>
      </div>

      {/* Upload Zone - show if no batch */}
      {!batchId && (
        <div
          className={`relative border-2 border-dashed rounded-2xl p-12 text-center transition-all cursor-pointer
            ${dragActive 
              ? 'border-cyan-400 bg-cyan-500/10' 
              : 'border-gray-600 hover:border-gray-500 bg-gray-800/30'}`}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
        >
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept="image/*"
            className="hidden"
            onChange={(e) => e.target.files && handleUpload(e.target.files)}
          />
          
          {isUploading ? (
            <div className="flex flex-col items-center gap-4">
              <div className="w-12 h-12 border-4 border-cyan-400 border-t-transparent rounded-full animate-spin"></div>
              <p className="text-gray-400">Wgrywanie plikow...</p>
            </div>
          ) : (
            <>
              <div className="w-20 h-20 mx-auto mb-4 flex items-center justify-center bg-gradient-to-br from-cyan-500/20 to-blue-600/20 rounded-full border border-cyan-500/30">
                <span className="material-symbols-outlined text-4xl text-cyan-400">cloud_upload</span>
              </div>
              <h3 className="text-xl font-semibold mb-2">Przeciagnij pliki lub kliknij</h3>
              <p className="text-gray-400 text-sm">Obslugiwane formaty: JPG, PNG, WebP</p>
              <p className="text-gray-500 text-xs mt-2">Mozesz wybrac caly folder ze zdjeciami kart</p>
            </>
          )}
        </div>
      )}

      {/* Batch Processing View */}
      {batchId && status && (
        <div className="space-y-6">
          {/* Progress Card */}
          <div className="bg-[#0f172a] border border-gray-700/50 rounded-xl p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-lg font-semibold">Postep analizy</h3>
                <p className="text-sm text-gray-400">
                  {status.processed_items} / {status.total_items} przetworzonych
                </p>
              </div>
              <div className="flex gap-3">
                {!isProcessing && status.processed_items < status.total_items && (
                  <button
                    onClick={startProcessing}
                    className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-cyan-600 to-blue-600 rounded-lg font-medium hover:from-cyan-500 hover:to-blue-500 transition-all"
                  >
                    <span className="material-symbols-outlined">play_arrow</span>
                    Rozpocznij analize
                  </button>
                )}
                {isProcessing && (
                  <button
                    onClick={stopProcessing}
                    className="flex items-center gap-2 px-4 py-2 bg-red-600 rounded-lg font-medium hover:bg-red-500 transition-all"
                  >
                    <span className="material-symbols-outlined">stop</span>
                    Zatrzymaj
                  </button>
                )}
              </div>
            </div>

            {/* Progress Bar */}
            <div className="relative h-3 bg-gray-700 rounded-full overflow-hidden">
              <div
                className="absolute inset-y-0 left-0 bg-gradient-to-r from-cyan-500 to-blue-500 rounded-full transition-all duration-300"
                style={{ width: `${status.progress_percent}%` }}
              />
            </div>
            
            {/* Stats */}
            <div className="flex gap-6 mt-4 text-sm">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 bg-green-500 rounded-full"></span>
                <span>Sukces: {status.successful_items}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 bg-red-500 rounded-full"></span>
                <span>Bledy: {status.failed_items}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 bg-gray-500 rounded-full"></span>
                <span>Oczekuje: {status.total_items - status.processed_items}</span>
              </div>
            </div>

            {/* Current file */}
            {isProcessing && status.current_filename && (
              <div className="mt-3 flex items-center gap-2 text-sm text-cyan-400">
                <div className="w-4 h-4 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin"></div>
                <span>Analizuje: {status.current_filename}</span>
              </div>
            )}
          </div>

          {/* Publish Button */}
          {readyToPublish.length > 0 && !isProcessing && (
            <div className="bg-[#0f172a] border border-gray-700/50 rounded-xl p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">Gotowe do publikacji: {readyToPublish.length}</p>
                  <p className="text-sm text-gray-400">Wszystkie pomyslnie przeanalizowane karty</p>
                </div>
                <button
                  onClick={publishAll}
                  disabled={isPublishing}
                  className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-green-600 to-emerald-600 rounded-lg font-medium hover:from-green-500 hover:to-emerald-500 transition-all disabled:opacity-50"
                >
                  {isPublishing ? (
                    <>
                      <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                      Publikuje...
                    </>
                  ) : (
                    <>
                      <span className="material-symbols-outlined">publish</span>
                      Opublikuj wszystkie
                    </>
                  )}
                </button>
              </div>
            </div>
          )}

          {/* Items List */}
          <div className="space-y-2">
            {items.map((item, index) => (
              <div
                key={`${item.filename}-${index}`}
                onClick={() => setSelectedItem(item)}
                className={`relative overflow-hidden flex items-center gap-4 p-3 bg-[#0f172a] border rounded-xl cursor-pointer transition-all hover:bg-gray-800/50
                  ${item.status === 'success' ? 'border-green-500/50' : ''}
                  ${item.status === 'failed' ? 'border-red-500/50' : ''}
                  ${item.status === 'processing' ? 'border-cyan-500/50 bg-gradient-to-r from-cyan-900/20 to-blue-900/20 animate-pulse' : ''}
                  ${item.status === 'pending' ? 'border-gray-700/50' : ''}
                  ${item.publish_status === 'published' ? 'ring-2 ring-green-400' : ''}`}
              >
                {/* Thumbnail Stack */}
                <div className="flex gap-2">
                  {/* Original Scan */}
                  <div className="w-16 h-20 flex-shrink-0 bg-gray-800 rounded-lg overflow-hidden relative flex items-center justify-center">
                    {item.image_url ? (
                      <img
                        src={`${apiBase}${item.image_url}`}
                        alt="Scan"
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <span className="material-symbols-outlined text-xl text-gray-600">image</span>
                    )}
                    <span className="absolute bottom-0 inset-x-0 bg-black/60 text-[8px] text-center py-0.5 font-bold text-gray-300">SKAN</span>
                  </div>
                  
                  {/* Match */}
                  <div className="w-16 h-20 flex-shrink-0 bg-gray-800 rounded-lg overflow-hidden relative flex items-center justify-center border-l border-gray-700/50 pl-2">
                    {item.matched_image ? (
                      <img
                        src={item.matched_image}
                        alt="Match"
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <span className="material-symbols-outlined text-xl text-gray-600">search</span>
                    )}
                    <span className="absolute bottom-0 inset-x-0 bg-black/60 text-[8px] text-center py-0.5 font-bold text-cyan-400">BAZA</span>
                  </div>
                </div>

                {/* Info */}
                <div className="flex-grow min-w-0 z-10">
                  <p className="text-sm font-medium text-white truncate">
                    {item.matched_name || item.filename}
                  </p>
                  <div className="flex items-center gap-2 mt-1">
                    {item.matched_set && (
                      <span className="text-xs text-gray-400">{item.matched_set}</span>
                    )}
                    {item.matched_number && (
                      <span className="text-xs text-cyan-400">#{item.matched_number}</span>
                    )}
                  </div>
                  {item.price_pln_final && (
                    <p className="text-xs text-green-400 mt-1">{item.price_pln_final.toFixed(2)} PLN</p>
                  )}
                  {item.error_message && (
                    <p className="text-xs text-red-400 mt-1 truncate">{item.error_message}</p>
                  )}
                  {item.duplicate_of_scan_id && (
                    <div className="inline-flex items-center gap-1 px-2 py-0.5 bg-amber-500/20 text-amber-400 rounded text-[10px] mt-1">
                      <span className="material-symbols-outlined text-[12px]">content_copy</span>
                      Duplikat
                    </div>
                  )}
                </div>

                {/* Progress / Status */}
                <div className="flex-shrink-0 flex items-center gap-3 z-10">
                  {item.fields_complete !== undefined && (
                    <div className="text-center hidden sm:block">
                      <div className="w-20 h-1.5 bg-gray-700 rounded-full overflow-hidden">
                        <div
                          className={`h-full ${item.fields_complete === item.fields_total ? 'bg-green-500' : 'bg-cyan-500'}`}
                          style={{ width: `${(item.fields_complete / (item.fields_total || 7)) * 100}%` }}
                        />
                      </div>
                      <span className="text-[10px] text-gray-500">
                        {item.fields_complete}/{item.fields_total || 7}
                      </span>
                    </div>
                  )}

                  {/* Status Badge */}
                  <div className="flex-shrink-0">
                    {item.status === 'processing' && (
                      <div className="w-8 h-8 bg-cyan-500 rounded-full flex items-center justify-center">
                        <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                      </div>
                    )}
                    {item.status === 'success' && !item.publish_status && (
                      <div className="w-8 h-8 bg-green-500 rounded-full flex items-center justify-center">
                        <span className="material-symbols-outlined text-white text-lg">check</span>
                      </div>
                    )}
                    {item.status === 'failed' && (
                      <div className="w-8 h-8 bg-red-500 rounded-full flex items-center justify-center">
                        <span className="material-symbols-outlined text-white text-lg">close</span>
                      </div>
                    )}
                    {item.status === 'pending' && (
                      <div className="w-8 h-8 bg-gray-600 rounded-full flex items-center justify-center">
                        <span className="material-symbols-outlined text-gray-400 text-lg">hourglass_empty</span>
                      </div>
                    )}
                    {item.publish_status === 'published' && (
                      <div className="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center">
                        <span className="material-symbols-outlined text-white text-lg">cloud_done</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Edit Drawer */}
      {selectedItem && (
        <div className="fixed inset-0 z-50 flex justify-end">
          <div className="absolute inset-0 bg-black/50" onClick={() => setSelectedItem(null)} />
          <div ref={drawerRef} className="relative w-full max-w-2xl bg-[#0f172a] border-l border-gray-700 overflow-y-auto shadow-2xl">
            <div className="sticky top-0 bg-[#0f172a] border-b border-gray-700 p-4 flex items-center justify-between z-10">
              <div className="flex items-center gap-4">
                <h3 className="text-lg font-semibold">Edytuj karte</h3>
                <div className="flex items-center gap-2 text-sm text-gray-400">
                  <kbd className="px-2 py-1 bg-gray-800 border border-gray-600 rounded text-xs">←</kbd>
                  <kbd className="px-2 py-1 bg-gray-800 border border-gray-600 rounded text-xs">→</kbd>
                  <span>Nawigacja</span>
                  <span className="ml-2 text-cyan-400">
                    {items.findIndex(it => it.id === selectedItem.id) + 1} / {items.length}
                  </span>
                </div>
              </div>
              <button
                onClick={() => setSelectedItem(null)}
                className="p-2 hover:bg-gray-700 rounded-lg"
              >
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>

            <div className="p-4 space-y-6">
              {/* Image Comparison (Two Images) */}
              <div className="grid grid-cols-2 gap-4">
                {/* Scan */}
                <div className="space-y-1">
                  <div className="aspect-[3/4] bg-gray-800 rounded-lg overflow-hidden relative group border border-gray-600">
                    {selectedItem.image_url ? (
                      <img
                        src={`${apiBase}${selectedItem.image_url}`}
                        alt="Scan"
                        className="w-full h-full object-contain"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-gray-600">Brak skanu</div>
                    )}
                    <span className="absolute top-2 left-2 px-2 py-1 bg-black/70 rounded text-xs font-bold text-gray-300">TWOJE ZDJĘCIE</span>
                  </div>
                </div>

                {/* Matched */}
                <div className="space-y-1">
                  <div className="aspect-[3/4] bg-gray-800 rounded-lg overflow-hidden relative group border border-cyan-500/50">
                    {selectedItem.matched_image ? (
                      <img
                        src={selectedItem.matched_image}
                        alt="Matched"
                        className="w-full h-full object-contain"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-gray-600">Brak dopasowania</div>
                    )}
                    <span className="absolute top-2 right-2 px-2 py-1 bg-cyan-600/90 rounded text-xs font-bold text-white">BAZA DANYCH</span>
                    {selectedItem.duplicate_of_scan_id && (
                      <div className="absolute bottom-2 right-2 px-3 py-1 bg-amber-500 text-black font-bold rounded-lg shadow-lg text-sm">
                        DUPLIKAT
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Status Info */}
              <div className={`px-3 py-2 rounded-lg text-sm font-medium text-center
                ${selectedItem.status === 'success' ? 'bg-green-500/20 text-green-400' : ''}
                ${selectedItem.status === 'failed' ? 'bg-red-500/20 text-red-400' : ''}
                ${selectedItem.status === 'pending' ? 'bg-gray-500/20 text-gray-400' : ''}
                ${selectedItem.status === 'processing' ? 'bg-cyan-500/20 text-cyan-400' : ''}`}
              >
                {selectedItem.status === 'success' && 'Przeanalizowano pomyslnie'}
                {selectedItem.status === 'failed' && `Blad: ${selectedItem.error_message || 'Nieznany'}`}
                {selectedItem.status === 'pending' && 'Oczekuje na analize'}
                {selectedItem.status === 'processing' && 'Analizowanie...'}
              </div>


              {/* Form Fields */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Left Column - Basic */}
                <div className="space-y-3">
                  <h4 className="text-sm font-bold text-gray-400 uppercase tracking-wider border-b border-gray-700 pb-1">Dane podstawowe</h4>
                  <div>
                    <label className="text-xs text-gray-400">Nazwa karty</label>
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={selectedItem.matched_name || selectedItem.detected_name || ''}
                        onChange={(e) => setSelectedItem({ ...selectedItem, matched_name: e.target.value })}
                        className="flex-1 mt-1 px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-cyan-500"
                      />
                      <button
                        onClick={() => {
                          const cardNumber = (selectedItem.matched_number || selectedItem.detected_number || '').split('/')[0];
                          const searchString = `${selectedItem.matched_name || selectedItem.detected_name || ''} ${cardNumber}`.trim();
                          if (searchString) {
                            window.open(`https://www.cardmarket.com/en/Pokemon/Products/Search?category=-1&searchString=${encodeURIComponent(searchString)}&searchMode=v1`, '_blank');
                          }
                        }}
                        disabled={!selectedItem.matched_name && !selectedItem.detected_name}
                        className="mt-1 h-10 w-10 flex items-center justify-center rounded-lg bg-blue-600 hover:bg-blue-500 text-white transition-all disabled:opacity-50 disabled:cursor-not-allowed relative group"
                        title="Szukaj na CardMarket"
                      >
                        <span className="material-symbols-outlined text-xl">storefront</span>
                        <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 hidden w-auto p-2 text-xs text-white whitespace-nowrap bg-gray-800 rounded-md group-hover:block z-50">
                          Szukaj na CardMarket
                        </span>
                      </button>
                    </div>
                  </div>

                  <div>
                    <label className="text-xs text-gray-400">Set</label>
                    <input
                      type="text"
                      value={selectedItem.matched_set || selectedItem.detected_set || ''}
                      onChange={(e) => setSelectedItem({ ...selectedItem, matched_set: e.target.value })}
                      className="w-full mt-1 px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-cyan-500"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-xs text-gray-400">Numer</label>
                      <input
                        type="text"
                        value={selectedItem.matched_number || selectedItem.detected_number || ''}
                        onChange={(e) => setSelectedItem({ ...selectedItem, matched_number: e.target.value })}
                        className="w-full mt-1 px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-cyan-500"
                      />
                    </div>
                    <div>
                      <label className="text-xs text-gray-400">Kod magazynowy</label>
                      <input
                        type="text"
                        value={selectedItem.warehouse_code || ''}
                        onChange={(e) => setSelectedItem({ ...selectedItem, warehouse_code: e.target.value })}
                        className="w-full mt-1 px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-cyan-500"
                      />
                    </div>
                  </div>
                </div>

                {/* Right Column - Attributes & Price */}
                <div className="space-y-3">
                  <h4 className="text-sm font-bold text-gray-400 uppercase tracking-wider border-b border-gray-700 pb-1">Atrybuty i Cena</h4>
                  
                  {shoperAttributes.map(attr => {
                    // Map attribute to item field
                    let val = '';
                    if (attr.attribute_id === '64') val = selectedItem.attr_language || '142';
                    if (attr.attribute_id === '66') val = selectedItem.attr_condition || '176';
                    if (attr.attribute_id === '65') val = selectedItem.attr_finish || '184';
                    if (attr.attribute_id === '38') val = selectedItem.attr_rarity || '';
                    if (attr.attribute_id === '63') val = selectedItem.attr_energy || '';
                    if (attr.attribute_id === '39') val = selectedItem.attr_card_type || '';

                    return (
                      <div key={attr.attribute_id}>
                        <label className="text-xs text-gray-400">{attr.name}</label>
                        <select
                          value={val}
                          onChange={(e) => {
                            const updates = handleItemAttributeChange(selectedItem, attr.attribute_id, e.target.value);
                            setSelectedItem({ ...selectedItem, ...updates });
                          }}
                          className="w-full mt-1 px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-cyan-500"
                        >
                          <option value="">- Wybierz -</option>
                          {attr.options.map((opt: any) => (
                            <option key={opt.option_id} value={opt.option_id}>{opt.value}</option>
                          ))}
                        </select>
                      </div>
                    );
                  })}

                  <div className="grid grid-cols-2 gap-3 pt-2">
                    <div>
                      <label className="text-xs text-gray-400">Cena PLN</label>
                      <div className="relative">
                        <input
                          type="number"
                          step="0.01"
                          value={selectedItem.price_pln_final || ''}
                          onChange={(e) => setSelectedItem({ ...selectedItem, price_pln_final: parseFloat(e.target.value) || undefined })}
                          className="w-full mt-1 pl-3 pr-10 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-cyan-500"
                        />
                        <button className="absolute inset-y-0 right-0 px-2 text-gray-400 hover:text-white">
                          <span className="material-symbols-outlined text-base">refresh</span>
                        </button>
                      </div>
                    </div>
                    <div>
                      <label className="text-xs text-gray-400">Bazowa EUR</label>
                      <div className="relative">
                        <input
                          type="number"
                          step="0.01"
                          value={selectedItem.price_eur || ''}
                          readOnly
                          className="w-full mt-1 pl-3 pr-10 py-2 bg-gray-900 border border-gray-700 rounded-lg text-gray-400 cursor-not-allowed"
                        />
                        {selectedItem.cardmarket_url && (
                          <a href={selectedItem.cardmarket_url} target="_blank" rel="noopener noreferrer" className="absolute inset-y-0 right-0 px-2 flex items-center text-gray-400 hover:text-white">
                            <span className="material-symbols-outlined text-base">open_in_new</span>
                          </a>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Candidates */}
              {selectedItem.candidates && selectedItem.candidates.length > 0 && (
                <div className="space-y-3 pt-4 border-t border-gray-700">
                  <h4 className="text-sm font-bold text-gray-400 uppercase tracking-wider">Inne dopasowania (kliknij aby zmienić)</h4>
                  <div className="flex gap-3 overflow-x-auto pb-4">
                    {selectedItem.candidates.map((cand) => (
                      <div 
                        key={cand.id}
                        onClick={() => {
                          const updates = handleCandidateSelect(selectedItem, cand);
                          setSelectedItem({ ...selectedItem, ...updates });
                        }}
                        className={`flex-shrink-0 w-28 cursor-pointer border rounded-lg overflow-hidden transition-all hover:scale-105
                          ${selectedItem.matched_provider_id === cand.id ? 'border-cyan-500 ring-2 ring-cyan-500/20' : 'border-gray-700 opacity-60 hover:opacity-100'}`}
                      >
                        <div className="aspect-[3/4] bg-gray-800 relative">
                          <img src={cand.image} alt={cand.name} className="w-full h-full object-cover" />
                          {selectedItem.matched_provider_id === cand.id && (
                            <div className="absolute inset-0 bg-cyan-500/20 flex items-center justify-center">
                              <span className="material-symbols-outlined text-white text-3xl drop-shadow-lg">check_circle</span>
                            </div>
                          )}
                        </div>
                        <div className="p-2 bg-[#0f172a] text-[10px] border-t border-gray-700">
                          <p className="truncate text-white font-bold">{cand.name}</p>
                          <p className="text-gray-500 truncate">{cand.set} #{cand.number}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Image Selection UI */}
              <div className="space-y-3 pt-4 border-t border-gray-700">
                <h4 className="text-sm font-bold text-gray-400 uppercase tracking-wider">Wybór grafiki głównej</h4>
                <div className="flex justify-center items-start gap-3 p-3 bg-gray-800/30 rounded-lg">
                  {/* Option 1: TCGGO Image */}
                  {selectedItem.matched_image && (
                    <div 
                      className={`flex flex-col items-center gap-2 cursor-pointer p-2 rounded-md transition-all ${selectedItem.use_tcggo_image !== false ? 'bg-cyan-500/30 ring-2 ring-cyan-500' : 'hover:bg-gray-700'}`}
                      onClick={() => setSelectedItem({ ...selectedItem, use_tcggo_image: true })}
                    >
                      <img src={selectedItem.matched_image} className="w-20 h-auto rounded border border-gray-600" alt="TCGGO" />
                      <span className="text-xs text-white font-medium">Grafika z API</span>
                      {selectedItem.use_tcggo_image !== false && (
                        <span className="material-symbols-outlined text-cyan-400 text-sm">check_circle</span>
                      )}
                    </div>
                  )}

                  {/* Option 2: User's Scan */}
                  {selectedItem.image_url && (
                    <div 
                      className={`flex flex-col items-center gap-2 cursor-pointer p-2 rounded-md transition-all ${selectedItem.use_tcggo_image === false ? 'bg-cyan-500/30 ring-2 ring-cyan-500' : 'hover:bg-gray-700'}`}
                      onClick={() => setSelectedItem({ ...selectedItem, use_tcggo_image: false })}
                    >
                      <img src={`${apiBase}${selectedItem.image_url}`} className="w-20 h-auto rounded border border-gray-600" alt="Skan" />
                      <span className="text-xs text-white font-medium">Twój skan</span>
                      {selectedItem.use_tcggo_image === false && (
                        <span className="material-symbols-outlined text-cyan-400 text-sm">check_circle</span>
                      )}
                    </div>
                  )}
                </div>
              </div>

              {/* Additional Images Upload */}
              <div className="space-y-3 pt-4 border-t border-gray-700">
                <h4 className="text-sm font-bold text-gray-400 uppercase tracking-wider">Dodatkowe zdjęcia (stan karty)</h4>
                <div className="flex flex-col gap-2 p-3 bg-gray-800/30 rounded-lg">
                  <label className="cursor-pointer flex items-center justify-center p-4 border-2 border-dashed border-gray-600 rounded-lg hover:bg-gray-700 transition-colors">
                    <span className="material-symbols-outlined text-cyan-400 mr-2">add_a_photo</span>
                    <span className="text-white text-sm">Dodaj zdjęcia</span>
                    <input 
                      type="file" 
                      accept="image/*" 
                      multiple 
                      className="hidden" 
                      onChange={(e) => {
                        if (e.target.files) {
                          setAdditionalImagesToUpload(prev => [...prev, ...Array.from(e.target.files!)]);
                        }
                      }} 
                    />
                  </label>
                  
                  {/* Display existing additional images from server */}
                  {selectedItem.additional_images && selectedItem.additional_images.length > 0 && (
                    <div className="grid grid-cols-3 gap-2 mt-2">
                      {selectedItem.additional_images.map((imgUrl, index) => (
                        <div key={index} className="relative">
                          <img src={`${apiBase}${imgUrl}`} alt={`Dodatkowe ${index + 1}`} className="w-full h-auto rounded border border-gray-600" />
                          <span className="absolute top-1 left-1 bg-black/70 text-white text-[10px] px-1 rounded">Zapisane</span>
                        </div>
                      ))}
                    </div>
                  )}
                  
                  {/* Display newly selected images to upload */}
                  {additionalImagesToUpload.length > 0 && (
                    <div className="grid grid-cols-3 gap-2 mt-2">
                      {additionalImagesToUpload.map((file, index) => (
                        <div key={index} className="relative">
                          <img src={URL.createObjectURL(file)} alt={`Nowe ${index + 1}`} className="w-full h-auto rounded border border-cyan-500" />
                          <button 
                            className="absolute top-0 right-0 bg-red-600 text-white rounded-full p-0.5 w-5 h-5 flex items-center justify-center text-xs"
                            onClick={() => setAdditionalImagesToUpload(prev => prev.filter((_, i) => i !== index))}
                          >
                            ×
                          </button>
                          <span className="absolute bottom-1 left-1 bg-cyan-600/90 text-white text-[10px] px-1 rounded">Nowe</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
              {/* Match Score */}
              {selectedItem.match_score !== undefined && (
                <div className="flex items-center gap-2 text-sm pt-2 justify-center">
                  <span className="text-gray-400">Dopasowanie automatyczne:</span>
                  <span className={`font-bold ${selectedItem.match_score > 0.7 ? 'text-green-400' : selectedItem.match_score > 0.4 ? 'text-yellow-400' : 'text-red-400'}`}>
                    {Math.round(selectedItem.match_score * 100)}%
                  </span>
                </div>
              )}

              {/* Save Button */}
              <button
                onClick={() => {
                  updateItem(selectedItem.id, {
                    matched_name: selectedItem.matched_name,
                    matched_set: selectedItem.matched_set,
                    matched_number: selectedItem.matched_number,
                    matched_image: selectedItem.matched_image,
                    matched_provider_id: selectedItem.matched_provider_id,
                    price_pln_final: selectedItem.price_pln_final,
                    warehouse_code: selectedItem.warehouse_code,
                    attr_language: selectedItem.attr_language,
                    attr_condition: selectedItem.attr_condition,
                    attr_finish: selectedItem.attr_finish,
                    attr_rarity: selectedItem.attr_rarity,
                    attr_energy: selectedItem.attr_energy,
                    attr_card_type: selectedItem.attr_card_type,
                    use_tcggo_image: selectedItem.use_tcggo_image,
                  }, additionalImagesToUpload.length > 0 ? additionalImagesToUpload : undefined);
                  setSelectedItem(null);
                }}
                className="w-full py-4 bg-gradient-to-r from-cyan-600 to-blue-600 rounded-lg font-bold hover:from-cyan-500 hover:to-blue-500 transition-all shadow-lg shadow-cyan-500/20 text-lg"
              >
                Zapisz zmiany
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Toast */}
      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg shadow-lg z-50">
          {toast}
        </div>
      )}
    </div>
  );
}
