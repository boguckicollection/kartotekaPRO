from __future__ import annotations

import re
from typing import Optional, Dict, Tuple
from PIL import Image
import pytesseract

from ..vision import extract_fields_with_openai
from ..settings import settings
from rapidfuzz import fuzz, process
from functools import lru_cache
from .set_symbol import identify_set_by_symbol
import numpy as np
import cv2


def _ocr_number_total(text: str) -> tuple[Optional[str], Optional[str]]:
    # Look for patterns like 123/198 or 12/99
    m = re.search(r"(\d{1,3})\s*/\s*(\d{1,3})", text)
    if m:
        return m.group(1), m.group(2)
    # Or a single number
    m2 = re.search(r"\b(\d{1,3})\b", text)
    if m2:
        return m2.group(1), None
    return None, None


def ocr_extract(image_path: str) -> Dict[str, Optional[str]]:
    try:
        img = Image.open(image_path)
    except Exception:
        return {"name": None, "number": None, "total": None, "set": None, "set_code": None}
    try:
        text = pytesseract.image_to_string(img)
    except Exception:
        text = ""
    number, total = _ocr_number_total(text)
    return {"name": None, "number": number, "total": total, "set": None, "set_code": None}


def analyze_card(image_path: str) -> Dict[str, Optional[str]]:
    """Combined extraction using OpenAI Vision, Symbol Matching, and OCR fallback.

    Returns a dict with keys: name, number, total, set, set_code, language, variant, condition
    """
    # Step 1: Primary analysis with OpenAI Vision
    data = extract_fields_with_openai(image_path)

    # Step 2: If set is missing, use local symbol matching as a specialist
    if not data.get("set"):
        try:
            match = identify_set_by_symbol(image_path)
            if match:
                set_code, set_name = match
                print(f"DEBUG: Symbol matcher overrode set. Found: {set_name} ({set_code})")
                data["set"] = set_name
                data["set_code"] = set_code
        except Exception as e:
            print(f"DEBUG: Symbol matcher failed: {e}")

    # Step 3: If number is missing (common with Vision hallucinations), use local OCR as a specialist
    if not data.get("number"):
        try:
            ocr_data = ocr_extract(image_path)
            if ocr_data.get("number"):
                print(f"DEBUG: OCR overrode number. Found: {ocr_data.get('number')}")
                data["number"] = ocr_data.get("number")
                if ocr_data.get("total"):
                    data["total"] = ocr_data.get("total")
        except Exception as e:
            print(f"DEBUG: OCR fallback failed: {e}")
            
    return data


def detect_card_roi(image_path: str) -> Optional[Tuple[float, float, float, float]]:
    """Return a normalized (x,y,w,h) of the main card region in the image.

    Best-effort using OpenCV: grayscale -> blur -> Canny -> contours -> pick the largest
    4-point poly (or largest contour) and return its bounding rect normalized to image size.
    """
    try:
        img = cv2.imread(image_path)
        if img is None:
            return None
        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(gray, 50, 150)
        cnts, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cnts:
            return None
        # Prefer large, approximately rectangular contours
        best = None
        best_area = 0
        for c in cnts:
            area = cv2.contourArea(c)
            if area < (w * h * 0.05):
                continue
            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.02 * peri, True)
            if len(approx) == 4 and area > best_area:
                best = approx
                best_area = area
        if best is None:
            # fallback: largest contour
            c = max(cnts, key=cv2.contourArea)
            x, y, ww, hh = cv2.boundingRect(c)
        else:
            x, y, ww, hh = cv2.boundingRect(best)
        # Normalize and clamp
        nx = float(max(0, x) / max(1, w))
        ny = float(max(0, y) / max(1, h))
        nw = float(min(w, x + ww) - x) / max(1, w)
        nh = float(min(h, y + hh) - y) / max(1, h)
        # sanity bounds
        nx = max(0.0, min(1.0, nx)); ny = max(0.0, min(1.0, ny))
        nw = max(0.0, min(1.0, nw)); nh = max(0.0, min(1.0, nh))
        if nw <= 0 or nh <= 0:
            return None
        return (nx, ny, nw, nh)
    except Exception:
        return None


def detect_card_roi_bytes(raw: bytes) -> Optional[Tuple[float, float, float, float]]:
    """Same as detect_card_roi, but takes raw image bytes and avoids filesystem IO."""
    try:
        arr = np.frombuffer(raw, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return None
        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(gray, 50, 150)
        cnts, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cnts:
            return None
        best = None
        best_area = 0
        for c in cnts:
            area = cv2.contourArea(c)
            if area < (w * h * 0.05):
                continue
            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.02 * peri, True)
            if len(approx) == 4 and area > best_area:
                best = approx
                best_area = area
        if best is None:
            c = max(cnts, key=cv2.contourArea)
            x, y, ww, hh = cv2.boundingRect(c)
        else:
            x, y, ww, hh = cv2.boundingRect(best)
        nx = float(max(0, x) / max(1, w))
        ny = float(max(0, y) / max(1, h))
        nw = float(min(w, x + ww) - x) / max(1, w)
        nh = float(min(h, y + hh) - y) / max(1, h)
        nx = max(0.0, min(1.0, nx)); ny = max(0.0, min(1.0, ny))
        nw = max(0.0, min(1.0, nw)); nh = max(0.0, min(1.0, nh))
        if nw <= 0 or nh <= 0:
            return None
        return (nx, ny, nw, nh)
    except Exception:
        return None


def _ocr_text(img: np.ndarray, *, digits_only: bool = False) -> str:
    import pytesseract as _t
    try:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    except Exception:
        gray = img
    # Upscale for better OCR
    try:
        h, w = gray.shape[:2]
        scale = 1.6 if max(h, w) < 600 else 1.2
        if scale > 1.0:
            gray = cv2.resize(gray, (int(w*scale), int(h*scale)), interpolation=cv2.INTER_CUBIC)
    except Exception:
        pass
    # Denoise + local contrast
    try:
        gray = cv2.bilateralFilter(gray, d=7, sigmaColor=75, sigmaSpace=75)
    except Exception:
        pass
    try:
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        gray = clahe.apply(gray)
    except Exception:
        pass
    # Try binarization variants
    variants = []
    try:
        th1 = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 9)
        variants.append(th1)
        th2 = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 9)
        variants.append(th2)
    except Exception:
        variants.append(gray)

    # Try multiple OCR configs
    base = "--oem 1"
    configs = []
    if digits_only:
        configs = [
            base + " --psm 7 -c tessedit_char_whitelist=0123456789/",
            base + " --psm 6 -c tessedit_char_whitelist=0123456789/",
        ]
    else:
        configs = [
            base + " --psm 6",
            base + " --psm 7",
        ]

    def _score(s: str) -> int:
        s = (s or "").strip()
        return sum(ch.isalnum() for ch in s)

    best_txt = ""
    best_score = -1
    for v in variants:
        for cfg in configs:
            try:
                txt = _t.image_to_string(v, config=cfg)
            except Exception:
                txt = ""
            sc = _score(txt)
            if sc > best_score:
                best_score = sc
                best_txt = txt
    return (best_txt or "").strip()


def _parse_number(text: str) -> Tuple[Optional[str], Optional[str]]:
    import re as _re
    t = text or ""
    m = _re.search(r"(\d{1,3})\s*/\s*(\d{1,3})", t)
    if m:
        return m.group(1), m.group(2)
    m2 = _re.search(r"\b(\d{1,3})\b", t)
    if m2:
        return m2.group(1), None
    return None, None


def extract_name_number_from_bytes(raw: bytes) -> Tuple[Dict[str, Optional[str]], Optional[Tuple[float, float, float, float]]]:
    """Detect card ROI and OCR name (top-left) and number (bottom-left/right).

    Returns: ({ name, number, total }, roi) where roi is (x,y,w,h) normalized, or ( {}, None )
    """
    roi = detect_card_roi_bytes(raw)
    if roi is None:
        return {"name": None, "number": None, "total": None}, None
    # Decode full image
    try:
        arr = np.frombuffer(raw, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return {"name": None, "number": None, "total": None}, roi
    except Exception:
        return {"name": None, "number": None, "total": None}, roi

    H, W = img.shape[:2]
    x = int(max(0, roi[0]) * W)
    y = int(max(0, roi[1]) * H)
    w = int(max(0, roi[2]) * W)
    h = int(max(0, roi[3]) * H)
    x2 = min(W, x + w)
    y2 = min(H, y + h)
    if x2 <= x or y2 <= y:
        return {"name": None, "number": None, "total": None}, roi
    card = img[y:y2, x:x2].copy()

    ch, cw = card.shape[:2]
    # Heurystyczne regiony: nazwa w górnym-lewym rogu; numer w dole — lewym i prawym
    name_roi = card[0:int(0.26*ch), 0:int(0.82*cw)]  # top ~26%, wider area for long names
    num_left_roi = card[int(0.74*ch):ch, 0:int(0.48*cw)]   # bottom ~26%, left
    num_right_roi = card[int(0.74*ch):ch, int(0.52*cw):cw] # bottom right
    num_center_roi = card[int(0.74*ch):ch, int(0.30*cw):int(0.70*cw)] # bottom center (fallback)

    name_text = _ocr_text(name_roi, digits_only=False)
    num_text_l = _ocr_text(num_left_roi, digits_only=True)
    num_text_r = _ocr_text(num_right_roi, digits_only=True)
    num_text_c = _ocr_text(num_center_roi, digits_only=True)

    number, total = _parse_number(num_text_l)
    if not number:
        number, total = _parse_number(num_text_r)
    if not number:
        number, total = _parse_number(num_text_c)
    if not number:
        # as a last resort, OCR entire bottom strip
        bottom = card[int(0.70*ch):ch, :]
        num_text_b = _ocr_text(bottom, digits_only=True)
        number, total = _parse_number(num_text_b)

    # Postprocess name z filtrem słownika Pokemon
    def _candidate_from_text(txt: str) -> Optional[str]:
        import re as _re
        tokens = _re.findall(r"[A-Za-zÀ-ÿ'\-]{3,}", txt)
        if not tokens:
            return None
        return " ".join(tokens[:3])

    @lru_cache(maxsize=1)
    def _pokemon_names() -> list[str]:
        # Spróbuj ścieżkę z env, potem kilka lokalizacji; jeśli brak pełnej listy, pobierz z PokeAPI
        from pathlib import Path
        import os
        import json as _json
        candidates = []
        if settings.pokemon_names_path:
            candidates.append(Path(settings.pokemon_names_path))
        candidates += [
            Path("storage/pokemon_names.txt"),
            Path(__file__).parent / "data" / "pokemon_names.txt",
            Path.cwd() / "pokemon_names.txt",
        ]
        # 1) Lokalny plik (preferowany)
        for p in candidates:
            try:
                if p.exists():
                    names = [line.strip() for line in p.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip()]
                    # jeśli lista jest sensownie duża (>= 300), użyj jej
                    if len(names) >= 300:
                        return names
            except Exception:
                continue
        # 2) PokeAPI fallback (pełna lista) — zapis do storage/pokemon_names.txt
        try:
            import httpx as _httpx
            url = os.getenv("POKEMON_NAMES_URL", "https://pokeapi.co/api/v2/pokemon?limit=2000")
            r = _httpx.get(url, timeout=10.0)
            if r.status_code == 200:
                js = r.json()
                results = js.get("results") if isinstance(js, dict) else None
                names_raw = [it.get("name") for it in (results or []) if isinstance(it, dict) and it.get("name")]
                def _norm(n: str) -> str:
                    n = n.replace("-", " ").strip()
                    # kapitalizacja bazowa; specjalne przypadki poprawi fuzzy
                    return n.title()
                names = sorted({_norm(n) for n in names_raw})
                if len(names) >= 300:
                    outp = Path("storage/pokemon_names.txt")
                    try:
                        outp.parent.mkdir(parents=True, exist_ok=True)
                        outp.write_text("\n".join(names), encoding="utf-8")
                    except Exception:
                        pass
                    return list(names)
        except Exception:
            pass
        # 3) Minimalny fallback – krótsza lista
        return [
            "Bulbasaur","Ivysaur","Venusaur","Charmander","Charmeleon","Charizard","Squirtle","Wartortle","Blastoise",
            "Caterpie","Metapod","Butterfree","Weedle","Kakuna","Beedrill","Pidgey","Pidgeotto","Pidgeot","Rattata","Raticate",
            "Pikachu","Raichu","Eevee","Vaporeon","Jolteon","Flareon","Snorlax","Mew","Mewtwo","Dragonite","Gyarados",
            "Gastly","Haunter","Gengar","Onix","Lapras","Scyther","Magmar","Electabuzz","Jynx","Ditto","Mr Mime","Beldum","Metang","Metagross"
        ]

    cand = _candidate_from_text(name_text)
    name: Optional[str] = None
    if cand:
        # Dopasowanie słownikowe (token_set_ratio); akceptuj, jeśli score sensowny
        names = _pokemon_names()
        try:
            match = process.extractOne(cand, names, scorer=fuzz.token_set_ratio)
            if match and match[1] >= 80:
                name = match[0]
            else:
                # delikatny fallback – popraw pisownię i kapitalizację
                name = cand.title()
        except Exception:
            name = cand.title()
    else:
        name = None

    return {"name": name, "number": number, "total": total}, roi


def _find_quad(img: np.ndarray) -> Optional[np.ndarray]:
    try:
        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(gray, 50, 150)
        cnts, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cnts:
            return None
        # Pick the largest reasonable contour
        cnts = sorted(cnts, key=cv2.contourArea, reverse=True)
        for c in cnts:
            area = cv2.contourArea(c)
            if area < (w*h*0.05):
                continue
            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.02*peri, True)
            if len(approx) == 4:
                pts = approx.reshape(4,2).astype(np.float32)
                # order points (tl,tr,br,bl)
                s = pts.sum(axis=1)
                diff = np.diff(pts, axis=1).reshape(-1)
                tl = pts[np.argmin(s)]
                br = pts[np.argmax(s)]
                tr = pts[np.argmin(diff)]
                bl = pts[np.argmax(diff)]
                return np.array([tl,tr,br,bl], dtype=np.float32)
        return None
    except Exception:
        return None


def warp_card_from_bytes(raw: bytes, out_size: Tuple[int,int] = (840, 1176)) -> Optional[Tuple[np.ndarray, Tuple[float,float,float,float]]]:
    """Return (warped_card_image, roi) if a quadrilateral is found; else None.
    ROI returned as normalized bounding rect for overlay convenience.
    """
    arr = np.frombuffer(raw, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return None
    quad = _find_quad(img)
    if quad is None:
        return None
    W,H = out_size
    dst = np.array([[0,0],[W-1,0],[W-1,H-1],[0,H-1]], dtype=np.float32)
    M = cv2.getPerspectiveTransform(quad, dst)
    warped = cv2.warpPerspective(img, M, (W,H))
    # build roi from bounding rect of quad (normalized)
    x = float(max(0.0, quad[:,0].min())/img.shape[1])
    y = float(max(0.0, quad[:,1].min())/img.shape[0])
    w = float((quad[:,0].max()-quad[:,0].min())/img.shape[1])
    h = float((quad[:,1].max()-quad[:,1].min())/img.shape[0])
    return warped, (x,y,w,h)



def detect_multiple_cards_roi_bytes(raw: bytes) -> list[Tuple[Tuple[float, float, float, float], bytes]]:
    """Detect multiple card ROIs in an image.
    
    Returns a list of tuples: ((x,y,w,h) normalized, cropped_image_bytes)
    """
    try:
        arr = np.frombuffer(raw, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return []
        
        # 1. Preprocessing for low quality images
        h, w = img.shape[:2]
        processed = img.copy()
        
        # Upscale if too small (width < 1000px)
        if w < 1000:
            scale = 1000 / w
            processed = cv2.resize(processed, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        
        gray = cv2.cvtColor(processed, cv2.COLOR_BGR2GRAY)
        
        # CLAHE (Contrast Limited Adaptive Histogram Equalization) - crucial for bad lighting
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        gray = clahe.apply(gray)
        
        # Denoise
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Edge detection with broader thresholds
        edges = cv2.Canny(gray, 30, 200)
        
        # Dilate to connect broken edges
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5,5))
        dilated = cv2.dilate(edges, kernel, iterations=2)
        
        # Find contours
        cnts, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        results = []
        ph, pw = processed.shape[:2] # Dimensions of processed image
        
        for c in cnts:
            # Filter by area (at least 0.5% of image to avoid noise, but catch smaller cards in collection)
            area = cv2.contourArea(c)
            if area < (pw * ph * 0.005):
                continue
                
            x, y, cw, ch = cv2.boundingRect(c)
            
            # Filter by aspect ratio (Pokemon cards are ~0.71 or 1.4)
            aspect = float(cw) / ch
            # Allow wider range for slightly tilted cards
            if aspect < 0.5 or aspect > 2.2:
                continue
                
            # Filter by absolute size
            if cw < 50 or ch < 50:
                continue

            # Check solidity (card should be somewhat solid rectangle)
            hull = cv2.convexHull(c)
            hull_area = cv2.contourArea(hull)
            if hull_area > 0:
                solidity = float(area)/hull_area
                if solidity < 0.7: # Ignore weird shapes
                    continue

            # Map coordinates back to original image if upscaled
            orig_x = int(x * (w / pw))
            orig_y = int(y * (h / ph))
            orig_cw = int(cw * (w / pw))
            orig_ch = int(ch * (h / ph))
            
            # Ensure bounds
            orig_x = max(0, orig_x)
            orig_y = max(0, orig_y)
            orig_cw = min(w - orig_x, orig_cw)
            orig_ch = min(h - orig_y, orig_ch)

            # Crop from ORIGINAL image
            crop = img[orig_y:orig_y+orig_ch, orig_x:orig_x+orig_cw]
            success, encoded = cv2.imencode('.jpg', crop)
            if not success:
                continue
                
            # Normalize ROI relative to original dimensions
            nx = float(orig_x) / w
            ny = float(orig_y) / h
            nw = float(orig_cw) / w
            nh = float(orig_ch) / h
            
            results.append(((nx, ny, nw, nh), encoded.tobytes()))
            
        # Deduplicate overlapping rectangles (non-max suppression style)
        # Sort by area descending
        results.sort(key=lambda r: r[0][2] * r[0][3], reverse=True)
        final_results = []
        
        for r in results:
            roi1 = r[0]
            overlap = False
            for fr in final_results:
                roi2 = fr[0]
                # Calculate Intersection over Union (IoU) or Intersection over Area1
                x_left = max(roi1[0], roi2[0])
                y_top = max(roi1[1], roi2[1])
                x_right = min(roi1[0] + roi1[2], roi2[0] + roi2[2])
                y_bottom = min(roi1[1] + roi1[3], roi2[1] + roi2[3])
                
                if x_right > x_left and y_bottom > y_top:
                    intersection_area = (x_right - x_left) * (y_bottom - y_top)
                    area1 = roi1[2] * roi1[3]
                    # If huge overlap (>50% of smaller rect), treat as duplicate
                    if intersection_area > 0.5 * area1:
                        overlap = True
                        break
            if not overlap:
                final_results.append(r)

        # Final Sort: top-to-bottom, then left-to-right for display
        # Use a tolerance for Y to group rows
        final_results.sort(key=lambda r: (int(r[0][1] * 10), r[0][0]))
        
        return final_results
    except Exception as e:
        print(f"Multi-card detection failed: {e}")
        return []


def assess_quality(image_bgr: np.ndarray) -> Dict[str, float]:
    """Return simple quality metrics and overall score in 0..1.
    - sharpness via variance of Laplacian
    - brightness via mean luma
    - glare via proportion of near-white pixels
    """
    try:
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    except Exception:
        gray = image_bgr
    # Sharpness
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    sharp_var = float(lap.var())
    # Brightness
    brightness = float(gray.mean()) / 255.0
    # Glare
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    v = hsv[:,:,2]
    glare_ratio = float((v > 245).sum()) / float(v.size)
    # Normalize sharpness to 0..1 using logistic-ish mapping around ~150
    sharp_norm = max(0.0, min(1.0, (sharp_var/200.0)))
    # Penalize glare; ideal brightness ~0.55..0.85
    glare_pen = max(0.0, 1.0 - min(1.0, glare_ratio*5.0))
    bright_pen = 1.0 - min(abs(brightness-0.7)/0.7, 1.0)
    # Combine
    quality = max(0.0, min(1.0, 0.5*sharp_norm + 0.3*bright_pen + 0.2*glare_pen))
    return {
        "quality_score": quality,
        "sharpness_var": sharp_var,
        "brightness": brightness,
        "glare_ratio": glare_ratio,
    }
