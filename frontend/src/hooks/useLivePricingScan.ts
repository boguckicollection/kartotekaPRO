import { useCallback, useEffect, useRef, useState } from 'react';

type LivePricingScanOptions = {
  enabled: boolean;
  apiBase: string;
  onResult: (data: any) => void;
  onScan: () => void;
  onSound: (sound: 'success' | 'fail') => void;
  intervalMs?: number;
};

export function useLivePricingScan({ enabled, apiBase, onResult, onScan, onSound, intervalMs = 500 }: LivePricingScanOptions) {
  const [analyzing, setAnalyzing] = useState(false);
  const [status, setStatus] = useState('Gotowy');
  const [initStatus, setInitStatus] = useState('');
  const onResultRef = useRef(onResult);
  const [zoomCaps, setZoomCaps] = useState<{min: number, max: number, step: number} | null>(null);
  const [isStreamReady, setIsStreamReady] = useState(false);
  
  const [torchSupported, setTorchSupported] = useState(false);
  const [torchOn, setTorchOn] = useState(false);

  const [videoNode, setVideoNode] = useState<HTMLVideoElement | null>(null);
  const [canvasNode, setCanvasNode] = useState<HTMLCanvasElement | null>(null);
  
  const streamRef = useRef<MediaStream | null>(null);
  const trackRef = useRef<MediaStreamTrack | null>(null);
  const imageCaptureRef = useRef<any | null>(null);

  const videoRef = useCallback((node: HTMLVideoElement) => {
    if (node !== null) setVideoNode(node);
  }, []);

  const canvasRef = useCallback((node: HTMLCanvasElement) => {
    if (node !== null) setCanvasNode(node);
  }, []);

  useEffect(() => {
    onResultRef.current = onResult;
  }, [onResult]);

  // Zoom control
  const setZoom = useCallback(async (zoomValue: number) => {
    if (!trackRef.current) return;
    try {
        await (trackRef.current as any).applyConstraints({ advanced: [{ zoom: zoomValue }] });
    } catch (err) {
        console.error('Zoom failed', err);
    }
  }, []);

  // Torch control
  const toggleTorch = useCallback(async () => {
    if (!trackRef.current || !torchSupported) return;
    try {
      const newStatus = !torchOn;
      await (trackRef.current as any).applyConstraints({
        advanced: [{ torch: newStatus }]
      });
      setTorchOn(newStatus);
    } catch (err) {
      console.error('Torch toggle failed', err);
    }
  }, [torchOn, torchSupported]);

  // Manual Capture
  const captureImage = useCallback(async () => {
    if (!videoNode || !canvasNode || analyzing) return;
    
    setAnalyzing(true);
    setStatus('Przetwarzanie zdjęcia...');
    onSound('shutter'); // Shutter sound effect przy robieniu zdjęcia

    try {
      let blob: Blob | null = null;
      
      // Try ImageCapture for highest quality
      if (imageCaptureRef.current && imageCaptureRef.current.takePhoto) {
        try {
          blob = await imageCaptureRef.current.takePhoto();
        } catch (e) {
          console.warn('ImageCapture failed, falling back to canvas', e);
        }
      }

      let dataUrl = '';
      if (blob) {
         dataUrl = await new Promise<string>((resolve) => {
            const reader = new FileReader();
            reader.onloadend = () => resolve(reader.result as string);
            reader.readAsDataURL(blob!);
         });
      } else {
         // Fallback: Canvas snapshot
         const ctx = canvasNode.getContext('2d')!;
         canvasNode.width = videoNode.videoWidth;
         canvasNode.height = videoNode.videoHeight;
         ctx.drawImage(videoNode, 0, 0);
         dataUrl = canvasNode.toDataURL('image/jpeg', 0.95);
      }

      // Send to API
      const priceRes = await fetch(`${apiBase}/pricing/estimate_from_image`, {
          method: 'POST',
          headers: { 
              'Content-Type': 'application/json',
              'ngrok-skip-browser-warning': 'true'
          },
          body: JSON.stringify({ image: dataUrl }),
      });

      if (priceRes.ok) {
          const priceData = await priceRes.json();
          onResultRef.current(priceData);
          onSound('success'); // Sukces tylko gdy znaleziono wynik
          setStatus('Sukces!');
      } else if (priceRes.status === 404) {
          setStatus('Nie znaleziono karty w bazie');
          onSound('fail');
      } else {
          const errData = await priceRes.json();
          setStatus(errData.error || 'Nie rozpoznano karty');
          onSound('fail'); // Fail gdy nie znaleziono
      }

    } catch (err) {
      console.error('Capture error', err);
      setStatus('Błąd zapisu');
      onSound('fail');
    } finally {
      setAnalyzing(false);
    }
  }, [videoNode, canvasNode, analyzing, apiBase, onSound]);

  useEffect(() => {
    if (!enabled || !videoNode || !canvasNode) return;

    const isSecure = (window.isSecureContext === true) || ['localhost','127.0.0.1'].includes(location.hostname);
    
    if (!isSecure){ 
      setInitStatus('Kamera wymaga połączenia HTTPS (nie działa po HTTP/Tailscale bez certyfikatu).');
      return;
    }

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia){
        setInitStatus('Brak wsparcia kamery w tej przeglądarce');
        return;
    }

    let aborted = false;

    const start = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ 
          video: { 
            facingMode: 'environment',
            // Prefer 4K or Full HD for better OCR
            width: { ideal: 3840, min: 1920 },
            height: { ideal: 2160, min: 1080 }
          }
        });
        
        if (aborted) return;
        
        streamRef.current = stream;
        videoNode.srcObject = stream;
        await videoNode.play();

        const track = stream.getVideoTracks()[0];
        trackRef.current = track;
        
        // Capabilities check
        const caps: any = (track as any).getCapabilities ? (track as any).getCapabilities() : {};
        
        if (caps.zoom) {
            setZoomCaps({min: caps.zoom.min, max: caps.zoom.max, step: caps.zoom.step});
        }
        
        if (caps.torch) {
            setTorchSupported(true);
        }

        // Init ImageCapture
        try {
            const IC = (window as any).ImageCapture;
            if (IC) imageCaptureRef.current = new IC(track);
        } catch {}

        canvasNode.width = videoNode.videoWidth;
        canvasNode.height = videoNode.videoHeight;
        setIsStreamReady(true);
        setInitStatus('');
      } catch (err) {
        setInitStatus('Błąd kamery. Sprawdź uprawnienia.');
      }
    };

    start();

    return () => {
      aborted = true;
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(t => t.stop());
      }
    };
  }, [enabled, videoNode, canvasNode]);

  // Lightweight loop just for viewfinder overlay (optional)
  useEffect(() => {
      if (!isStreamReady || !videoNode || !canvasNode) return;
      let aborted = false;

      const loop = async () => {
          if (aborted) return;
          if (analyzing) { setTimeout(loop, 500); return; } // Pause loop when analyzing
          
          try {
             // Just draw frame for "live" feel, maybe do light probe later if needed
             // For now we rely on manual capture for best performance
             onScan(); 
          } catch {}
          
          setTimeout(loop, 200);
      };
      
      loop();
      return () => { aborted = true; }
  }, [isStreamReady, videoNode, canvasNode, analyzing, onScan]);

  return { analyzing, status, initStatus, videoRef, canvasRef, setZoom, zoomCaps, toggleTorch, torchSupported, torchOn, captureImage };
}
