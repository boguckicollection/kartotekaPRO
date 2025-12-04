import { useMemo, useState, useEffect } from 'react'
import { Product } from './types'
import TabBar from './components/TabBar'
import Sidebar from './components/Sidebar'
import Home from './views/Home'
import ReportsView from './views/Reports'
import InventoryView from './views/Inventory'
import OrdersView from './views/Orders'
import PricingView from './views/Pricing'
import ScanView from './views/Scan'
import StartSessionView from './views/StartSessionView'
import StorageView from './views/StorageView'
import WarehouseVisualView from './views/WarehouseVisualView'
import BatchScanView from './views/BatchScanView'

export default function App() {
  const [stats, setStats] = useState<any | null>(null)
  const [products, setProducts] = useState<any[] | null>(null)
  const [invPage, setInvPage] = useState(1)
  const [invLimit, setInvLimit] = useState(50)
  const [invTotal, setInvTotal] = useState(0)
  const [invSort, setInvSort] = useState('updated_at')
  const [invOrder, setInvOrder] = useState('desc')
  const [invQ, setInvQ] = useState<string | undefined>(undefined)
  const [invCategoryId, setInvCategoryId] = useState<number | undefined>(undefined)
  const [orders, setOrders] = useState<any[] | null>(null)
  const [pricingItems, setPricingItems] = useState<any[] | null>(null)
  const [tab, setTab] = useState<'dashboard'|'reports'|'inventory'|'orders'|'pricing'|'scan'|'storage'|'warehouse'>('dashboard')
  const [toast, setToast] = useState<string | null>(null)
  const [scanResult, setScanResult] = useState<any | null>(null)
  const [scanPreview, setScanPreview] = useState<string | null>(null)
  const [scanLoading, setScanLoading] = useState<boolean>(false)
  const [isSyncing, setIsSyncing] = useState<boolean>(false)
  const [isSliderOpen, setIsSliderOpen] = useState(false)
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null)
  const [scanSession, setScanSession] = useState<{id: number, starting_warehouse_code?: string | null} | null>(null)
  const [folderFiles, setFolderFiles] = useState<File[]>([])
  const [currentFileIndex, setCurrentFileIndex] = useState<number>(0)
  const [showSessionStart, setShowSessionStart] = useState(true);
  const [showBatchScan, setShowBatchScan] = useState(false);
  const [lastOrderId, setLastOrderId] = useState<number | null>(null);

  const isAndroid = useMemo(()=>/Android/i.test(navigator.userAgent||''), [])

  const apiBase = useMemo(() => {
    // Always use the Vite proxy in development.
    // The VITE_API_BASE_URL is for building for production.
    return (import.meta as any).env?.VITE_API_BASE_URL || '/api';
  }, [])

  useEffect(()=>{ if(!toast) return; const t = setTimeout(()=> setToast(null), 2500); return ()=> clearTimeout(t) }, [toast])

  const urlBase64ToUint8Array = (base64String: string) => {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding).replace(/\-/g, '+').replace(/_/g, '/')
    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);
    for (let i = 0; i < rawData.length; ++i) {
      outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
  };

  useEffect(()=>{
    if (isAndroid && 'serviceWorker' in navigator && 'PushManager' in window) {
      const registerServiceWorkerAndSubscribe = async () => {
        try {
          const swRegistration = await navigator.serviceWorker.register('/sw.js');
          let subscription = await swRegistration.pushManager.getSubscription();

          if (subscription === null) {
            // VAPID public key - replace with your actual key
            const vapidPublicKey = 'BIPulh12xJ6cGo8iO0t2bA8_3-cAYCg3w_D3fPS2GBl1tS2kYjJzVzGjD_3-cAYCg3w_D3fPS2GBl1tS2kYjJzVzGj';
            const convertedVapidKey = urlBase64ToUint8Array(vapidPublicKey);

            subscription = await swRegistration.pushManager.subscribe({
              userVisibleOnly: true,
              applicationServerKey: convertedVapidKey,
            });
          }

          await fetch(`${apiBase}/notifications/subscribe`, {
            method: 'POST',
            body: JSON.stringify(subscription),
            headers: {
              'Content-Type': 'application/json',
            },
          });
        } catch (error) {
          console.error('Service Worker Error', error);
        }
      };

      Notification.requestPermission().then(permission => {
        if (permission === 'granted') {
          registerServiceWorkerAndSubscribe();
        }
      });
    }
  }, [isAndroid, apiBase]);

  const loadStats = async (silent: boolean = false) => { 
    try { 
      const r = await fetch(`${apiBase}/stats`); 
      setStats(await r.json());
      // Load recent orders for dashboard - need detailed=1 for items
      const ordersRes = await fetch(`${apiBase}/orders?limit=20&detailed=1`);
      const ordersData = await ordersRes.json();
      
      // Check for new orders (only if we have previous data and not silent initial load)
      if (!silent && lastOrderId !== null && Array.isArray(ordersData) && ordersData.length > 0) {
        const latestOrderId = Math.max(...ordersData.map((o: any) => Number(o.id) || 0));
        if (latestOrderId > lastOrderId) {
          // Find new orders with status 1 or 2
          const newOrders = ordersData.filter((o: any) => {
            const orderId = Number(o.id) || 0;
            const statusId = o?.status?.id;
            const isNew = statusId === '1' || statusId === 1 || statusId === '2' || statusId === 2;
            return orderId > lastOrderId && isNew;
          });
          
          if (newOrders.length > 0) {
            const orderText = newOrders.length === 1 ? 'zamówienie' : newOrders.length < 5 ? 'zamówienia' : 'zamówień';
            setToast(`🔔 Nowe ${orderText}! (${newOrders.length})`);
          }
          setLastOrderId(latestOrderId);
        }
      } else if (lastOrderId === null && Array.isArray(ordersData) && ordersData.length > 0) {
        // Initial load - just set the latest ID without notification
        const latestOrderId = Math.max(...ordersData.map((o: any) => Number(o.id) || 0));
        setLastOrderId(latestOrderId);
      }
      
      setOrders(ordersData);
    } catch {} 
  }
  const loadProducts = async (q?: string, page?: number, sort?: string, order?: string, limit?: number, categoryId?: number) => {
    const p = new URLSearchParams()
    if (q) p.set('q', q)
    if (page) p.set('page', String(page))
    if (sort) p.set('sort', sort)
    if (order) p.set('order', order)
    if (limit) p.set('limit', String(limit))
    if (categoryId) p.set('category_id', String(categoryId))
    try {
      const r = await fetch(`${apiBase}/products?${p.toString()}`);
      const d = await r.json();
      setProducts(Array.isArray(d)? d : d.items||[])
      setInvTotal(d.total_count || 0)
    } catch {}
  }
  const loadOrders = async () => { try { const r = await fetch(`${apiBase}/orders?detailed=1`); setOrders(await r.json()) } catch {} }
  const loadPricing = async () => { try { const r = await fetch(`${apiBase}/scans?limit=50`); const items = await r.json(); const details = await Promise.all((items||[]).slice(0,10).map((x:any)=> fetch(`${apiBase}/scans/${x.id}`).then(m=>m.json()).catch(()=>null))); setPricingItems(details.filter(Boolean)) } catch {} }

  const handleUpdateProduct = async (product: Product) => {
    try {
      const response = await fetch(`${apiBase}/products/${product.shoper_id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(product),
      });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to update product');
      }
      setToast('Produkt zaktualizowany!');
      loadProducts();
    } catch (error) {
      console.error('Error updating product:', error);
      throw error;
    }
  };

  const handleProductClick = (product: Product) => {
    setSelectedProduct(product)
    setIsSliderOpen(true)
  }

  const handleCloseSlider = () => {
    setIsSliderOpen(false)
    setSelectedProduct(null)
  }

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setScanPreview(URL.createObjectURL(file))
    setScanLoading(true)
    try {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('session_id', scanSession ? String(scanSession.id) : '');
      fd.append('starting_warehouse_code', scanSession?.starting_warehouse_code || '');

      const res = await fetch(`${apiBase}/scan`, { method: 'POST', body: fd })
      const data = await res.json()
      if (res.ok) {
        setScanResult(data)
      } else {
        setToast(data.error || 'Scan failed')
      }
    } catch (err) {
      setToast('Network error during scan')
    } finally {
      setScanLoading(false)
    }
  }

  const handleFolderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files) {
      const imageFiles = Array.from(files).filter(file => file.type.startsWith('image/'));
      setFolderFiles(imageFiles);
      setCurrentFileIndex(0);
    }
  };

  const scanFile = async (file: File) => {
    setScanPreview(URL.createObjectURL(file));
    setScanLoading(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('session_id', scanSession ? String(scanSession.id) : '');
      fd.append('starting_warehouse_code', scanSession?.starting_warehouse_code || '');
      
      const res = await fetch(`${apiBase}/scan`, { method: 'POST', body: fd });
      const data = await res.json();
      if (res.ok) {
        setScanResult(data);
      } else {
        setToast(data.error || 'Scan failed');
      }
    } catch (err) {
      setToast('Network error during scan');
    } finally {
      setScanLoading(false);
    }
  };

  
  useEffect(() => {
    if (folderFiles.length > 0 && currentFileIndex < folderFiles.length) {
      scanFile(folderFiles[currentFileIndex]);
    }
  }, [currentFileIndex, folderFiles]);


  const handleConfirmScan = async (
    formData: any, 
    imageInfo: { 
      primary: { source: string; url: string | null; file?: File | null; }; 
      additional: File[]; 
    }
  ) => {
    if (!scanResult?.scan_id || !scanResult.candidates || scanResult.candidates.length === 0) return;
    
    try {
      const data = new FormData();

      // 1. Append main form data as a JSON string
      data.append('data', JSON.stringify({
          scan_id: scanResult.scan_id,
          candidate_id: scanResult.candidates[0].id,
          detected: formData
      }));

      // 2. Append primary image
      data.append('primary_image_source', imageInfo.primary.source);
      if (imageInfo.primary.source === 'upload' && imageInfo.primary.file) {
          data.append('primary_image', imageInfo.primary.file);
      } else if (imageInfo.primary.url) {
          data.append('primary_image_url', imageInfo.primary.url);
      }

      // 3. Append additional images
      imageInfo.additional.forEach((file, index) => {
          data.append(`additional_image_${index}`, file);
      });

      const res = await fetch(`${apiBase}/scans/${scanResult.scan_id}/publish`, { 
          method: 'POST',
          body: data
      });

      const responseData = await res.json();
      if (res.ok) {
          setToast(`Opublikowano: ${responseData.shoper_id}`);
          // Reset for next scan
          setScanResult(null);
          setScanPreview(null);

          // If there are more files in the folder, scan the next one
          if (folderFiles.length > 0 && currentFileIndex < folderFiles.length - 1) {
            const nextIndex = currentFileIndex + 1;
            setCurrentFileIndex(nextIndex);
          } else {
            setFolderFiles([]);
            setCurrentFileIndex(0);
            // Optionally, show a session summary or completion message
            setToast('Skanowanie folderu zakończone!');
          }
      } else {
          const errorText = responseData.details?.text || responseData.error || 'Błąd podczas publikowania';
          setToast(errorText);
      }
    } catch (err) {
        console.error("Failed to publish scan in folder mode", err);
        setToast('Błąd sieci podczas publikowania');
    }
  };

  const startSession = async (starting_warehouse_code: string | null) => {
    try {
      const res = await fetch(`${apiBase}/sessions/start`, { 
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ starting_warehouse_code })
      });
      const data = await res.json();
      if (res.ok) {
        setScanSession(data);
        setShowSessionStart(false); // Hide the start view
      } else {
        throw new Error(data.error || 'Failed to start session');
      }
    } catch (err: any) {
      setToast(err.message || 'Failed to start session');
    }
  };

  const handleCsvUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setScanLoading(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await fetch(`${apiBase}/import/inventory_csv`, { method: 'POST', body: fd });
      const data = await res.json();
      if (res.ok) {
        setToast(`Imported: ${data.created} created, ${data.updated} updated`);
      } else {
        setToast(data.error || 'CSV import failed');
      }
    } catch (err) {
      setToast('Network error during CSV import');
    } finally {
      setScanLoading(false);
    }
  };

    useEffect(() => {

      if (tab === 'inventory') {

        loadProducts(invQ, invPage, invSort, invOrder, invLimit, invCategoryId);

      } else if (tab === 'dashboard') {

        loadStats(true); // Silent initial load

      } else if (tab === 'pricing' && !pricingItems) {

        loadPricing();

      } else if (tab === 'orders' && !orders) {

        loadOrders();

      }

    }, [tab, invPage, invLimit, invSort, invOrder, invQ, invCategoryId, apiBase]);

  // Periodic check for new orders on dashboard (every 2 minutes)
  useEffect(() => {
    if (tab !== 'dashboard') return;
    
    const interval = setInterval(() => {
      loadStats(false); // Not silent - will show notifications
    }, 120000); // 2 minutes
    
    return () => clearInterval(interval);
  }, [tab]);

  const renderContent = () => {
    if (tab === 'scan') {
      if (showBatchScan) {
        return <BatchScanView 
          apiBase={apiBase} 
          session={scanSession}
          onBack={() => {
            setShowBatchScan(false);
            setShowSessionStart(false);
          }} 
        />;
      }
      if (showSessionStart) {
        return <StartSessionView apiBase={apiBase} onSessionStarted={(sessionData) => {
          setScanSession(sessionData);
          setShowSessionStart(false);
        }} />; 
      }
      return (
        <ScanView
          session={scanSession}
          preview={scanPreview}
          loading={scanLoading}
          result={scanResult}
          selected={scanResult?.candidates?.[0]?.id || null}
          onFile={handleFileChange}
          onConfirm={handleConfirmScan}
          onFolderChange={handleFolderChange}
          onCsvUpload={handleCsvUpload}
          onStartSession={() => {}} // This button is now in StartSessionView
          onBatchScan={() => setShowBatchScan(true)}
          onPick={(id) => {
            if (scanResult) {
              const updatedResult = { ...scanResult, candidates: scanResult.candidates.map(c => ({...c, chosen: c.id === id})) };
              setScanResult(updatedResult);
            }
          }}
          onSubmit={() => {
            // This might be used for folder uploads later
          }}
        />
      );
    }
    if (tab==='dashboard') return <Home stats={stats} orders={orders||[]} onNav={(k)=> setTab(k as any)} onRefresh={loadStats} onOpenOrder={(o)=>{ setSelected(o); setTab('orders'); setIsSliderOpen(true); }} />;
    if (tab==='reports') return <ReportsView />;
    if (tab==='warehouse') return <WarehouseVisualView apiBase={apiBase} />;
    if (tab==='inventory') return <InventoryView
      items={(products||[])}
      page={invPage}
      limit={invLimit}
      hasNext={(invPage * invLimit) < invTotal}
      sort={invSort}
      order={invOrder}
      q={invQ}
      categoryId={invCategoryId}
      onSearch={(q,sort,order,page,limit,categoryId)=>{ setInvQ(q); setInvCategoryId(categoryId); setInvPage(page); setInvLimit(limit); setInvSort(sort); setInvOrder(order); loadProducts(q, page, sort, order, limit, categoryId) }}
      onSync={async ()=>{
        setIsSyncing(true);
        try {
          const response = await fetch(`${apiBase}/sync/shoper`, {method:'POST'});
          const result = await response.json();
          if (response.ok) {
            setToast(`Synchronizacja zakończona: Pobranych: ${result.fetched}, Utworzonych: ${result.created}, Zaktualizowanych: ${result.updated}`);
          } else {
            setToast(`Błąd synchronizacji: ${result.error || response.statusText}`);
          }
        } catch (error: any) {
          setToast(`Błąd sieci podczas synchronizacji: ${error.message}`);
        }
        loadProducts(invQ, invPage, invSort, invOrder, invLimit, invCategoryId);
        setIsSyncing(false);
      }}
      onUpdate={handleUpdateProduct}
      isSyncing={isSyncing}
      onProductClick={handleProductClick}
    />;
    if (tab==='orders') return <OrdersView items={(orders||[])} apiBase={apiBase} />;
    if (tab==='pricing') return <PricingView items={(pricingItems||[])} onRefresh={loadPricing} />;
    return null;
  }

  return (
    <div className="font-display">
      <div className="flex">
        <Sidebar active={tab} onChange={(k)=>{ setTab(k as any); if (k === 'scan') { setShowSessionStart(true); setShowBatchScan(false); } }} />
        <main className="relative flex-1 p-4 md:p-8 global-app-background">
          {isAndroid && (
            <img 
              src="/białe-male.png" 
              alt="Logo" 
              style={{
                position: 'absolute', 
                top: '16px', 
                right: '16px', 
                height: '28px', 
                zIndex: 10,
                filter: 'drop-shadow(0 1px 2px rgba(0,0,0,0.5))'
              }} 
            />
          )}
          {renderContent()}
          {toast && <div style={{ position: 'fixed', left: '50%', transform: 'translateX(-50%)', bottom: 18, background: '#111', color: '#fff', borderRadius: 10, border: '1px solid #333', padding: '10px 14px' }}>{toast}</div>}
        </main>
      </div>

      {isSliderOpen && selectedProduct && (
        <ProductEditSlider 
          key={selectedProduct.id}
          product={selectedProduct} 
          onClose={handleCloseSlider} 
          onUpdate={handleUpdateProduct}
          apiBase={apiBase}
        />
      )}

      {/* Mobile bottom navigation (Android only) */}
      <div className="md:hidden" style={{ display: isAndroid ? 'block' : 'none' }}>
        <TabBar
          tabs={[
            { key: 'dashboard', icon: 'monitoring', label: 'Statystyki' },
            { key: 'scan', icon: 'qr_code_scanner', label: 'Skanuj' },
            { key: 'pricing', icon: 'photo_camera', label: 'Wyceń' },
            { key: 'inventory', icon: 'inventory_2', label: 'Magazyn' },
            { key: 'warehouse', icon: 'warehouse', label: 'Lokalizacje'},
            { key: 'orders', icon: 'receipt_long', label: 'Zamówienia'}
          ]}
          active={tab}
          onChange={(k)=>{ setTab(k as any); if(k==='dashboard') loadStats(true); if(k==='inventory') loadProducts(); if(k==='pricing' && !pricingItems) loadPricing(); if(k === 'scan') { setShowSessionStart(true); setShowBatchScan(false); } }}
        />
      </div>
    </div>
  )
}
