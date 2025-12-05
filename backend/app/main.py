import traceback
from fastapi import FastAPI, UploadFile, File, Query, Body, Form, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import shutil
import time
from datetime import datetime, timedelta
import httpx
import json
import os
from typing import Any, Optional, List

from .settings import settings
from .schemas import ScanResponse, DetectedData, Candidate, ConfirmRequest, ConfirmResponse, ScanHistoryItem, ScanDetailResponse, CreateProductRequest, ProbeResponse, ProductUpdateRequest
from pydantic import BaseModel

from .vision import extract_fields_with_openai
from .analysis.pipeline import analyze_card, detect_card_roi, detect_card_roi_bytes, extract_name_number_from_bytes, warp_card_from_bytes, assess_quality
from .analysis.fingerprint import compute_fingerprint, pack_ndarray, unpack_ndarray, hamming_distance
from .providers import get_provider, PokemonTCGProvider
import httpx
from .pricing import extract_prices_from_payload, compute_price_pln, list_variant_prices
from .db import init_db, SessionLocal, Scan, ScanCandidate, Product, Fingerprint, Session, CardCatalog, InventoryItem, BatchScanItem
from sqlalchemy import func
from .db import Session as ScanSession
from .shoper import ShoperClient, upsert_products, publish_scan_to_shoper, build_shoper_payload, _category_name_from_id, get_shoper_categories, _get_related_products_from_category, build_product_attributes_payload
from rapidfuzz import fuzz
from .attributes import map_detected_to_shoper_attributes, simplify_attributes, simplify_categories
from .db import PushSubscription
from .warehouse import get_storage_summary, get_next_free_location, NoFreeLocationError, location_to_index, parse_warehouse_code, get_used_indices, get_next_free_location_for_batch
from pywebpush import webpush, WebPushException
import asyncio
import re
# Import auction routes
from .auction_routes import router as auction_router


def _get_or_create_catalog_entry(
    db,
    provider_id: str,
    name: str,
    set_name: str | None = None,
    set_code: str | None = None,
    number: str | None = None,
    rarity: str | None = None,
    energy: str | None = None,
    image_url: str | None = None,
    price_normal_eur: float | None = None,
    price_holo_eur: float | None = None,
    price_reverse_eur: float | None = None,
    api_payload: dict | None = None,
) -> CardCatalog:
    """
    Find existing CardCatalog entry by provider_id, or create a new one.
    Returns the catalog entry (existing or newly created).
    """
    existing = db.query(CardCatalog).filter(CardCatalog.provider_id == provider_id).first()
    if existing:
        # Update with latest data if provided
        if name:
            existing.name = name
        if set_name:
            existing.set_name = set_name
        if set_code:
            existing.set_code = set_code
        if number:
            existing.number = number
        if rarity:
            existing.rarity = rarity
        if energy:
            existing.energy = energy
        if image_url:
            existing.image_url = image_url
        if price_normal_eur is not None:
            existing.price_normal_eur = price_normal_eur
        if price_holo_eur is not None:
            existing.price_holo_eur = price_holo_eur
        if price_reverse_eur is not None:
            existing.price_reverse_eur = price_reverse_eur
        if api_payload:
            existing.api_payload = json.dumps(api_payload)
        existing.prices_updated_at = datetime.utcnow()
        db.commit()
        return existing
    
    # Create new entry
    new_entry = CardCatalog(
        provider_id=provider_id,
        name=name,
        set_name=set_name,
        set_code=set_code,
        number=number,
        rarity=rarity,
        energy=energy,
        image_url=image_url,
        price_normal_eur=price_normal_eur,
        price_holo_eur=price_holo_eur,
        price_reverse_eur=price_reverse_eur,
        api_payload=json.dumps(api_payload) if api_payload else None,
        prices_updated_at=datetime.utcnow(),
    )
    db.add(new_entry)
    db.commit()
    db.refresh(new_entry)
    return new_entry


def _extract_prices_for_catalog(details: dict) -> dict:
    """Extract price variants from TCGGO API response for CardCatalog."""
    prices = details.get("prices") or {}
    cardmarket = prices.get("cardmarket") or details.get("cardmarket") or {}
    
    # Normal price
    normal = None
    for k in ["avg7", "7d_average", "avg7d", "trendPrice"]:
        if cardmarket.get(k) is not None:
            normal = float(cardmarket.get(k))
            break
    
    # Holo price
    holo = None
    for k in ["holofoilAvg7", "holofoil7", "holofoil7d", "holofoilTrend"]:
        if cardmarket.get(k) is not None:
            holo = float(cardmarket.get(k))
            break
    
    # Reverse Holo price
    reverse = None
    for k in ["reverseHoloAvg7", "reverseHolo7", "reverseHolo7d", "reverseHoloTrend"]:
        if cardmarket.get(k) is not None:
            reverse = float(cardmarket.get(k))
            break
    
    return {
        "price_normal_eur": normal,
        "price_holo_eur": holo,
        "price_reverse_eur": reverse,
    }


def _calculate_purchase_cost(rarity: str | None, price_pln: float | None) -> float:
    """
    Calculate the purchase cost based on rarity and current market price.
    Common/Uncommon/Rare -> Fixed cost (e.g. 0.10 PLN)
    Premium -> Percentage of market price (e.g. 80%)
    """
    if not rarity:
        return settings.min_price_common
    
    # Check for premium rarities
    is_premium = False
    for p in settings.premium_rarities:
        if p.lower() in rarity.lower():
            is_premium = True
            break
            
    if is_premium and price_pln is not None:
        return round(price_pln * settings.min_price_premium_percent, 2)
    
    # Standard rarities
    r = rarity.lower()
    if "uncommon" in r:
        return settings.min_price_uncommon
    if "rare" in r and not is_premium:
        return settings.min_price_rare
        
    # Default fallback (Common)
    return settings.min_price_common


def _calculate_price_from_catalog(catalog: CardCatalog, finish: str = "normal") -> dict:
    """
    Calculate PLN price based on finish type and CardCatalog prices.
    Applies dynamic minimum price logic based on rarity/cost.
    """
    finish_lower = (finish or "normal").lower()
    base_eur = None
    estimated = False
    
    if "reverse" in finish_lower:
        base_eur = catalog.price_reverse_eur
        if base_eur is None and catalog.price_normal_eur:
            base_eur = catalog.price_normal_eur * settings.reverse_holo_price_multiplier
            estimated = True
    elif "holo" in finish_lower:
        base_eur = catalog.price_holo_eur
        if base_eur is None and catalog.price_normal_eur:
            base_eur = catalog.price_normal_eur * settings.holo_price_multiplier
            estimated = True
    else:  # normal
        base_eur = catalog.price_normal_eur
    
    if base_eur is None:
        return {"base_eur": None, "price_pln": None, "price_pln_final": None, "estimated": False, "purchase_price": None}
    
    # 1. Calculate Market Price in PLN
    price_pln = base_eur * settings.eur_pln_rate
    
    # 2. Calculate Purchase Cost (what we paid/would pay)
    purchase_price = _calculate_purchase_cost(catalog.rarity, price_pln)
    
    # 3. Calculate Sell Price based on Multiplier
    calculated_sell_price = price_pln * settings.price_multiplier
    
    # 4. Determine Minimum Sell Price logic
    # Logic: Sell Price cannot be lower than Purchase Cost
    # For premium cards, purchase cost is 80% of market, so min sell price is 80% of market
    min_sell_price = purchase_price
    
    # 5. Final Price
    price_pln_final = max(calculated_sell_price, min_sell_price)
    
    # Ensure absolute minimum fallback (e.g. 0.10)
    if price_pln_final < settings.min_price_common:
        price_pln_final = settings.min_price_common
    
    return {
        "base_eur": round(base_eur, 2),
        "price_pln": round(price_pln, 2),
        "price_pln_final": round(price_pln_final, 2),
        "purchase_price": round(purchase_price, 2),
        "estimated": estimated,
        "min_applied": price_pln_final == min_sell_price,
    }


def _product_image_url(row: Product) -> str | None:
    try:
        if getattr(row, "image", None):
            return row.image
        base = getattr(settings, "shoper_image_base", None)
        if base:
            uni = getattr(row, "main_image_unic_name", None)
            ext = getattr(row, "main_image_extension", None)
            if uni and ext:
                return f"{base.rstrip('/')}/{uni}.{ext}"
            gfx = getattr(row, "main_image_gfx_id", None)
            if gfx and ext:
                return f"{base.rstrip('/')}/{gfx}.{ext}"
    except Exception:
        pass
    return None





app = FastAPI(title=settings.app_name)

@app.post("/shoper/create-category-tree", status_code=200)
def create_shoper_category_tree_sync():
    """
    Tworzy drzewo kategorii w Shoperze na podstawie tcg_sets.json.
    Operacja jest synchroniczna - odpowiedź nadejdzie po zakończeniu.
    """
    print("Endpoint /shoper/create-category-tree called. Starting sync.")
    try:
        from . import shoper_sync
        result = shoper_sync.sync_shoper_categories()
        print("Sync finished.")
        if "error" in result:
             return JSONResponse(status_code=400, content=result)
        return {"message": "Category tree creation process finished.", "result": result}
    except Exception as e:
        print("CRITICAL ERROR in /shoper/create-category-tree endpoint:")
        print(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"error": "Internal Server Error", "detail": str(e), "traceback": traceback.format_exc()},
        )

origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Register auction router
app.include_router(auction_router)
# Serve uploaded files (for detail view)
try:
    app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")
except Exception:
    pass

# Register Furgonetka API router
try:
    from .furgonetka_endpoints import router as furgonetka_router
    app.include_router(furgonetka_router)
    print("✅ Furgonetka API endpoints registered")
except Exception as e:
    print(f"⚠️  Furgonetka endpoints not available: {e}")


@app.post("/inventory/check_code")
async def check_warehouse_code(body: dict = Body(default={})):
    """
    Checks if a warehouse code is valid and available.
    If taken, suggests the next available code.
    """
    code = body.get("code")
    if not code:
        return JSONResponse({"error": "Code is required"}, status_code=400)

    db = SessionLocal()
    try:
        # 1. Validate format
        code_index = location_to_index(code)
        if code_index is None:
            return JSONResponse({"status": "invalid_format", "message": "Nieprawidłowy format kodu. Użyj K<numer>-R<rząd>-P<pozycja>."}, status_code=422)

        # 2. Check if taken (only published scans count)
        used_indices = get_used_indices(db, only_published=True)
        if code_index in used_indices:
            try:
                next_code = get_next_free_location(db, starting_code=code)
                return JSONResponse({"status": "taken", "next_available": next_code}, status_code=409)
            except NoFreeLocationError:
                return JSONResponse({"status": "taken", "next_available": None}, status_code=409)
        else:
            return {"status": "available"}
    finally:
        db.close()

@app.get("/inventory/next_code")
async def get_next_warehouse_code_endpoint():
    """Suggests the next available warehouse code starting from the beginning."""
    db = SessionLocal()
    try:
        next_code = get_next_free_location(db)
        return {"code": next_code}
    except NoFreeLocationError:
        return JSONResponse({"error": "No free locations available"}, status_code=503)
    finally:
        db.close()

@app.get("/inventory/storage_summary")
async def get_storage_summary_endpoint():
    """Returns a detailed summary of warehouse occupancy."""
    db = SessionLocal()
    try:
        summary = get_storage_summary(db)
        return summary
    finally:
        db.close()


@app.get("/inventory/box_details/{box_key}")
async def get_box_details(box_key: str):
    """Returns detailed information about a specific box: cards count, value, sets breakdown, row details."""
    db = SessionLocal()
    try:
        from collections import defaultdict
        
        # Parse box_key (e.g., "K1", "KP")
        box_num = 100 if box_key == 'KP' else int(box_key.replace('K', ''))
        
        # Get all warehouse codes for this box
        # Query scans + inventory items + batch items
        all_codes = []
        
        # From Scans (published only)
        scan_codes = db.query(Scan.warehouse_code, Scan.detected_name, Scan.detected_set, Scan.price_pln_final).filter(
            Scan.warehouse_code.isnot(None),
            Scan.publish_status == 'published'
        ).all()
        
        # From InventoryItems
        inv_codes = db.query(InventoryItem.warehouse_code, InventoryItem.name, InventoryItem.set, InventoryItem.price).filter(
            InventoryItem.warehouse_code.isnot(None)
        ).all()
        
        # From BatchScanItems (published only)
        batch_codes = db.query(BatchScanItem.warehouse_code, BatchScanItem.matched_name, BatchScanItem.matched_set, BatchScanItem.price_pln_final).filter(
            BatchScanItem.warehouse_code.isnot(None),
            BatchScanItem.publish_status == 'published'
        ).all()
        
        # Combine all codes
        from .warehouse import parse_warehouse_code, PREMIUM_BOX_NUMBER
        
        cards_data = []
        for code, name, set_name, price in scan_codes + inv_codes + batch_codes:
            parsed = parse_warehouse_code(code)
            if not parsed:
                continue
            
            # Check if this code belongs to the requested box
            karton = parsed['karton']
            if (box_key == 'KP' and karton == 'PREMIUM') or (box_key != 'KP' and karton == int(box_key.replace('K', ''))):
                cards_data.append({
                    'code': code,
                    'name': name or 'Unknown',
                    'set': set_name or 'Unknown',
                    'price': price or 0.0,
                    'row': parsed['row']
                })
        
        # SPECIAL: For Premium box (KP), add products from shop without warehouse codes
        # These are cards added outside the scanning system (legacy/manual entries)
        if box_key == 'KP':
            # Get all Products that don't have a warehouse_code assigned via scans
            # We'll treat these as being in Premium Row 1
            products_without_location = db.query(Product.shoper_id, Product.name, Product.price, Product.stock).filter(
                Product.stock > 0  # Only in-stock products
            ).all()
            
            # Filter out products that already have a scan/location
            scan_product_ids = {s.published_shoper_id for s in db.query(Scan.published_shoper_id).filter(Scan.published_shoper_id.isnot(None)).all()}
            
            premium_row1_products = []
            for prod in products_without_location:
                if prod.shoper_id not in scan_product_ids:
                    premium_row1_products.append({
                        'code': f'KP-R1-VIRT{prod.shoper_id:04d}',  # Virtual code
                        'name': prod.name or 'Unknown',
                        'set': 'Legacy/Shop',
                        'price': prod.price or 0.0,
                        'row': 1  # Always Row 1 for Premium
                    })
            
            # Add virtual products to cards_data
            cards_data.extend(premium_row1_products)
        
        # Aggregate data
        total_cards = len(cards_data)
        total_value = sum(c['price'] for c in cards_data)
        
        # Sets breakdown
        sets_count = defaultdict(int)
        for card in cards_data:
            sets_count[card['set']] += 1
        
        # Rows breakdown
        rows_data = defaultdict(lambda: {'cards': 0, 'value': 0.0, 'codes': []})
        for card in cards_data:
            row = str(card['row'])
            rows_data[row]['cards'] += 1
            rows_data[row]['value'] += card['price']
            rows_data[row]['codes'].append(card['code'])
        
        # Convert defaultdict to regular dict
        rows_data = {k: dict(v) for k, v in rows_data.items()}
        
        return {
            "box_key": box_key,
            "total_cards": total_cards,
            "total_value": round(total_value, 2),
            "sets": dict(sets_count),
            "rows": rows_data
        }
    finally:
        db.close()


@app.get("/health")
def health():
    return {"status": "ok", "ts": int(time.time())}



@app.get("/config")
def config():
    """Return runtime configuration relevant for frontend hints.
    Values are read from settings/env so the UI can match backend gates.
    """
    return {
        "min_quality_probe_warn": float(getattr(settings, "min_quality_probe_warn", 0.45)),
        "min_quality_commit": float(getattr(settings, "min_quality_commit", 0.55)),
    }


@app.get("/ids_dump")
def get_ids_dump():
    # Best-effort: try to read ids_dump.json from several locations; if missing, synthesize from Shoper API
    candidates = [
        Path(__file__).parent.parent.parent / "ids_dump.json",  # project root if mounted
        Path(__file__).parent.parent / "ids_dump.json",         # backend folder
        Path.cwd() / "ids_dump.json",
    ]
    for p in candidates:
        try:
            if p.exists():
                with p.open("r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            continue
    # Also allow loading from env: IDS_DUMP_PATH or IDS_DUMP_JSON
    try:
        import os
        p_env = os.getenv("IDS_DUMP_PATH")
        if p_env:
            pf = Path(p_env)
            if pf.exists():
                with pf.open("r", encoding="utf-8") as f:
                    return json.load(f)
        j_env = os.getenv("IDS_DUMP_JSON")
        if j_env:
            return json.loads(j_env)
    except Exception:
        pass
    # Final fallback: empty structure to avoid 500
    return {"attributes": [], "categories": []}

class FrameScanRequest(BaseModel):
    image: str
    session_id: int | None = None
    starting_warehouse_code: str | None = None


@app.post("/scan/probe", response_model=ProbeResponse)
async def scan_probe(payload: FrameScanRequest):
    import base64, re
    data = payload.image or ""
    m = re.match(r"^data:image/[^;]+;base64,(.*)$", data)
    b64 = m.group(1) if m else data
    try:
        raw = base64.b64decode(b64)
    except Exception:
        return JSONResponse({"error": "invalid image payload"}, status_code=400)
    warped = warp_card_from_bytes(raw)
    if warped is None:
        return ProbeResponse(status="no_card", overlay=None, quality=None)
    card_img, roi = warped
    q = assess_quality(card_img)
    qual = float(q.get("quality_score") or 0.0)
    # Keep status 'card' for compatibility; front uses quality for guidance
    return ProbeResponse(status="card", overlay={"x": float(roi[0]), "y": float(roi[1]), "w": float(roi[2]), "h": float(roi[3])}, quality=qual)


@app.post("/scan/commit", response_model=ScanResponse)
async def scan_commit(payload: FrameScanRequest):
    import base64, re
    data = payload.image or ""
    m = re.match(r"^data:image/[^;]+;base64,(.*)$", data)
    b64 = m.group(1) if m else data
    try:
        raw = base64.b64decode(b64)
    except Exception:
        return JSONResponse({"error": "invalid image payload"}, status_code=400)

    warped = warp_card_from_bytes(raw)
    if warped is None:
        return JSONResponse({"error": "no_card"}, status_code=400)
    card_img, roi = warped
    q = assess_quality(card_img)
    quality = float(q.get("quality_score") or 0.0)
    if quality < float(settings.min_quality_commit):
        return JSONResponse({"error": "low_quality", "quality": quality, "min_quality": float(settings.min_quality_commit)}, status_code=422)
    quick, _ = extract_name_number_from_bytes(raw)

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    target = upload_dir / f"frame_{int(time.time()*1000)}.jpg"
    try:
        target.write_bytes(raw)
    except Exception:
        return JSONResponse({"error": "failed to write frame"}, status_code=500)

    db = SessionLocal()
    try:
        # Determine the starting code. Priority:
        # 1. Code passed directly to the endpoint.
        # 2. Code from the session.
        # 3. None (find first available).
        starting_code = payload.starting_warehouse_code
        if payload.session_id and not starting_code:
            session = db.get(Session, payload.session_id)
            if session and session.starting_warehouse_code:
                starting_code = session.starting_warehouse_code

        # Calculate suggested warehouse code (NOT saved to database yet)
        # Will be assigned only upon successful publication
        suggested_warehouse_code = None
        try:
            suggested_warehouse_code = get_next_free_location(db, starting_code=starting_code)
        except NoFreeLocationError:
            # Non-fatal: user can still scan and publish will assign a code
            print("WARNING: No free storage locations available, will assign at publish time")

        fused: dict[str, Any] = {}
        for k in ("name","number","total"):
            v = quick.get(k)
            if v:
                fused[k] = v
        detected = DetectedData(**fused)

        # Search provider
        provider = get_provider()
        try:
            candidates = await provider.search(detected)
        except httpx.HTTPStatusError:
            try:
                fb = PokemonTCGProvider()
                candidates = await fb.search(detected)
            except Exception:
                candidates = []
        except httpx.RequestError:
            try:
                fb = PokemonTCGProvider()
                candidates = await fb.search(detected)
            except Exception:
                candidates = []

        scan = Scan(
            filename=target.name,
            stored_path=str(target),
            stored_path_back=None,
            message="roi+ocr + provider",
            session_id=payload.session_id,
            warehouse_code=None,  # NOT assigned yet - will be set at publish time
        )
        db.add(scan)
        db.flush()
        scan.detected_name = detected.name
        scan.detected_set = detected.set
        scan.detected_set_code = detected.set_code
        scan.detected_number = detected.number
        scan.detected_language = detected.language
        scan.detected_variant = detected.variant
        scan.detected_condition = detected.condition
        scan.detected_rarity = detected.rarity
        scan.detected_energy = detected.energy
        db.add(scan)
        db.flush()
        for c in candidates:
            db.add(ScanCandidate(
                scan_id=scan.id,
                provider_id=c.id,
                name=c.name,
                set=c.set,
                set_code=c.set_code,
                number=c.number,
                rarity=c.rarity,
                image=c.image,
                score=c.score,
            ))
        db.commit()
        image_url = f"/uploads/{target.name}"
        # Final confidence: blend quality and best candidate score
        best_score = 0.0
        try:
            if candidates:
                best_score = float(max((c.score for c in candidates), default=0.0))
        except Exception:
            best_score = 0.0
        quality = quality
        confidence = max(0.0, min(1.0, 0.5*quality + 0.5*best_score))
        label = "GOOD" if confidence >= 0.8 else ("FAIR" if confidence >= 0.6 else "POOR")
        return ScanResponse(
            scan_id=scan.id,
            detected=detected,
            candidates=candidates,
            message=scan.message,
            stored_path=scan.stored_path,
            image_url=image_url,
            duplicate_of=None,
            duplicate_distance=None,
            overlay={"x": float(roi[0]), "y": float(roi[1]), "w": float(roi[2]), "h": float(roi[3])},
            quality=quality,
            confidence=confidence,
            confidence_label=label,
            warehouse_code=suggested_warehouse_code,  # Return as suggested, not saved to DB
        )
    finally:
        db.close()

@app.post("/scan/frame", response_model=ScanResponse)
async def scan_frame(payload: FrameScanRequest):
    import base64, re
    # Decode data URL or raw base64
    data = payload.image or ""
    m = re.match(r"^data:image/[^;]+;base64,(.*)$", data)
    b64 = m.group(1) if m else data
    try:
        raw = base64.b64decode(b64)
    except Exception:
        return JSONResponse({"error": "invalid image payload"}, status_code=400)

    # Phase 1: fast ROI + region OCR (no disk, no providers)
    quick, roi = extract_name_number_from_bytes(raw)
    if roi is None:
        return ScanResponse(
            scan_id=None,
            detected=DetectedData(),
            candidates=[],
            message="no_card",
            stored_path=None,
            image_url=None,
            duplicate_of=None,
            duplicate_distance=None,
            overlay=None,
        )

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    target = upload_dir / f"frame_{int(time.time()*1000)}.jpg"
    try:
        target.write_bytes(raw)
    except Exception:
        return JSONResponse({"error": "failed to write frame"}, status_code=500)

    db = SessionLocal()
    try:
        scan = Scan(
            filename=target.name,
            stored_path=str(target),
            stored_path_back=None,
            message="frame",
            session_id=payload.session_id,
        )
        db.add(scan)
        db.flush()

        # Build detected from quick OCR first (skip heavy Vision here)
        fused: dict[str, Any] = {}
        for k in ("name","number","total"):
            v = quick.get(k)
            if v:
                fused[k] = v
        detected = DetectedData(**fused)

        # Short-circuit: if we have neither name nor number, return lightweight result (no DB commit)
        if not (detected.name or detected.number):
            return ScanResponse(
                scan_id=None,
                detected=DetectedData(),
                candidates=[],
                message="no_text",
                stored_path=str(target),
                image_url=f"/uploads/{target.name}",
                duplicate_of=None,
                duplicate_distance=None,
                overlay={"x": float(roi[0]), "y": float(roi[1]), "w": float(roi[2]), "h": float(roi[3])},
            )

        provider = get_provider()
        try:
            candidates = await provider.search(detected)
        except httpx.HTTPStatusError:
            try:
                fb = PokemonTCGProvider()
                candidates = await fb.search(detected)
            except Exception:
                candidates = []
        except httpx.RequestError:
            try:
                fb = PokemonTCGProvider()
                candidates = await fb.search(detected)
            except Exception:
                candidates = []
        scan.message = "roi+ocr + provider"
        scan.detected_name = detected.name
        scan.detected_set = detected.set
        scan.detected_set_code = detected.set_code
        scan.detected_number = detected.number
        scan.detected_language = detected.language
        scan.detected_variant = detected.variant
        scan.detected_condition = detected.condition
        scan.detected_rarity = detected.rarity
        scan.detected_energy = detected.energy
        db.add(scan)
        db.flush()
        for c in candidates:
            cm = ScanCandidate(
                scan_id=scan.id,
                provider_id=c.id,
                name=c.name,
                set=c.set,
                set_code=c.set_code,
                number=c.number,
                rarity=c.rarity,
                image=c.image,
                score=c.score,
            )
            db.add(cm)
        db.commit()

        image_url = f"/uploads/{target.name}"
        return ScanResponse(
            scan_id=scan.id,
            detected=detected,
            candidates=candidates,
            message=scan.message,
            stored_path=scan.stored_path,
            image_url=image_url,
            duplicate_of=None,
            duplicate_distance=None,
            overlay={"x": float(roi[0]), "y": float(roi[1]), "w": float(roi[2]), "h": float(roi[3])},
        )
    finally:
        db.close()


class StartSessionRequest(BaseModel):
    starting_warehouse_code: str | None = None




@app.get("/sessions/recent")
def recent_sessions(limit: int = 10):
    """Return recent scan sessions with counts and last activity."""
    db = SessionLocal()
    try:
        rows = (
            db.query(Scan.session_id, func.count(Scan.id).label("count"), func.max(Scan.created_at).label("last_at"))
            .filter(Scan.session_id.isnot(None))
            .group_by(Scan.session_id)
            .order_by(func.max(Scan.created_at).desc())
            .limit(max(1, min(limit, 50)))
            .all()
        )
        out = []
        for sid, cnt, last_at in rows:
            try:
                out.append({"session_id": int(sid), "count": int(cnt), "last_at": last_at.isoformat()})
            except Exception:
                continue
        return out
    finally:
        db.close()


# Ensure DB tables exist at startup and optionally sync products
try:
    init_db()
except Exception:
    pass

async def _auto_update_prices_task():
    """
    Background task that periodically updates prices from TCGGO API
    and syncs them to Shoper if enabled.
    """
    if not getattr(settings, 'price_auto_update_enabled', False):
        print("Price auto-update is disabled")
        return
    
    interval_hours = getattr(settings, 'price_update_interval_hours', 24)
    interval_seconds = interval_hours * 3600
    
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            print(f"Starting scheduled price update...")
            
            db = SessionLocal()
            try:
                # Get all catalog entries that need updating
                entries = db.query(CardCatalog).limit(500).all()
                
                if not entries:
                    print("No catalog entries to update")
                    continue
                
                provider = get_provider()
                updated_count = 0
                
                for entry in entries:
                    try:
                        details = await provider.details(entry.provider_id)
                        prices_data = _extract_prices_for_catalog(details)
                        
                        changed = False
                        if prices_data.get("price_normal_eur") is not None and prices_data["price_normal_eur"] != entry.price_normal_eur:
                            entry.price_normal_eur = prices_data["price_normal_eur"]
                            changed = True
                        if prices_data.get("price_holo_eur") is not None and prices_data["price_holo_eur"] != entry.price_holo_eur:
                            entry.price_holo_eur = prices_data["price_holo_eur"]
                            changed = True
                        if prices_data.get("price_reverse_eur") is not None and prices_data["price_reverse_eur"] != entry.price_reverse_eur:
                            entry.price_reverse_eur = prices_data["price_reverse_eur"]
                            changed = True
                        
                        if changed:
                            entry.prices_updated_at = datetime.utcnow()
                            updated_count += 1
                        
                        # Small delay to avoid rate limiting
                        await asyncio.sleep(0.5)
                        
                    except Exception as e:
                        print(f"Failed to update catalog entry {entry.id}: {e}")
                        continue
                
                db.commit()
                print(f"Price update completed: {updated_count}/{len(entries)} entries updated")
                
                # TODO: Sync updated prices to Shoper products
                # This would iterate over Product entries linked to updated CardCatalog entries
                # and call Shoper API to update prices
                
            finally:
                db.close()
                
        except Exception as e:
            print(f"Price auto-update task error: {e}")
            await asyncio.sleep(60)  # Wait a minute before retrying


def _migrate_purchase_prices():
    """
    Automatically calculates and sets purchase_price for all products that don't have it.
    Runs once at startup to ensure all products have a purchase cost.
    """
    db = SessionLocal()
    try:
        products_without_price = db.query(Product).filter(Product.purchase_price.is_(None)).all()
        
        if not products_without_price:
            print("✅ All products already have purchase_price set")
            return
        
        print(f"🔄 Migrating purchase_price for {len(products_without_price)} products...")
        updated = 0
        
        for product in products_without_price:
            try:
                price = float(product.price or 0.0)
                rarity = None
                
                # Try to get rarity from linked CardCatalog
                if product.catalog_id:
                    catalog_entry = db.get(CardCatalog, product.catalog_id)
                    if catalog_entry:
                        rarity = catalog_entry.rarity
                
                # Calculate purchase price using existing logic
                purchase_price = _calculate_purchase_cost(rarity, price)
                product.purchase_price = purchase_price
                updated += 1
            except Exception as e:
                print(f"⚠️  Failed to calculate purchase_price for product {product.id}: {e}")
                continue
        
        db.commit()
        print(f"✅ Successfully migrated purchase_price for {updated} products")
    except Exception as e:
        print(f"❌ Purchase price migration failed: {e}")
    finally:
        db.close()


@app.on_event("startup")
async def _on_startup():
    if settings.shoper_auto_sync_on_startup:
        await _sync_products_if_needed(force=True)
    asyncio.create_task(check_for_new_orders())
    
    # Start price auto-update background task
    if getattr(settings, 'price_auto_update_enabled', False):
        asyncio.create_task(_auto_update_prices_task())
    
    # Start auction scheduler background task
    try:
        from .auction_scheduler import auction_scheduler_task
        asyncio.create_task(auction_scheduler_task())
    except Exception as e:
        print(f"❌ Failed to start auction scheduler: {e}")
    
    # Migrate purchase_price for existing products
    _migrate_purchase_prices()


@app.post("/notifications/subscribe")
async def subscribe(subscription: dict):
    db = SessionLocal()
    try:
        sub_json = json.dumps(subscription)
        existing = db.query(PushSubscription).filter(PushSubscription.subscription_json == sub_json).first()
        if not existing:
            db_sub = PushSubscription(subscription_json=sub_json)
            db.add(db_sub)
            db.commit()
        return {"status": "ok"}
    finally:
        db.close()


async def send_web_push(subscription_info: dict, payload: dict):
    try:
        webpush(
            subscription_info=subscription_info,
            data=json.dumps(payload),
            vapid_private_key=settings.vapid_private_key,
            vapid_claims={"sub": "mailto:admin@example.com"} # Replace with your email
        )
    except WebPushException as ex:
        print(f"Web push failed: {ex}")


async def _match_shoper_category(set_to_match: str) -> dict | None:
    """
    Finds the best Shoper category for a given set name using fuzzy matching.
    Uses the local ids_dump.json as the source of truth for categories.
    """
    if not set_to_match:
        return None

    try:
        # Path relative from main.py to the /app dir where ids_dump.json is located
        dump_path = Path(__file__).parent.parent / "ids_dump.json"
        if not dump_path.exists():
            return None

        with open(dump_path, "r", encoding="utf-8") as f:
            all_categories_data = json.load(f)
        
        all_categories = all_categories_data.get('categories', [])

        if not all_categories:
            return None

        best_match = None
        highest_score = 0
        MATCH_THRESHOLD = 85

        normalized_set_to_match = set_to_match.lower()

        for cat_data in all_categories:
            try:
                cat_name = cat_data['translations']['pl_PL']['name']
                cat_id = cat_data['category_id']
                is_root = cat_data.get('root') == '1'
            except KeyError:
                continue

            if not cat_name or is_root:
                continue

            normalized_cat_name = cat_name.lower()
            score = 0
            if normalized_set_to_match in normalized_cat_name:
                score = 100 + fuzz.token_set_ratio(set_to_match, cat_name)
            else:
                score = fuzz.token_set_ratio(set_to_match, cat_name)

            if score > highest_score:
                highest_score = score
                best_match = {'id': cat_id, 'name': cat_name}

        if best_match and highest_score >= MATCH_THRESHOLD:
            category_id = best_match.get('id')
            if category_id is not None:
                return {
                    'set_id': str(category_id),
                    'set': best_match.get('name')
                }

        return None
    except Exception as e:
        return None


async def check_for_new_orders():
    """
    Background task that checks for new orders every 60 seconds.
    Uses persistent file storage to track last processed order ID.
    Only fetches NEW orders since last check (FAST!).
    """
    # Load last processed order ID from file (persistent across restarts)
    last_order_id = read_last_order_id()
    print(f"📋 Order monitoring started. Last processed order ID: {last_order_id}")

    while True:
        await asyncio.sleep(60)  # Check every 60 seconds
        try:
            if not settings.shoper_base_url or not settings.shoper_access_token:
                continue

            client = ShoperClient(settings.shoper_base_url, settings.shoper_access_token)
            
            # OPTIMIZED: Fetch only NEW orders since last check
            # This is MUCH faster than fetching all orders!
            new_orders = await client.fetch_orders_since(
                since_id=last_order_id,
                limit=50  # Max 50 new orders per check
            )

            if new_orders:
                # Find the highest order ID
                max_order_id = last_order_id
                for order in new_orders:
                    order_id = order.get("order_id") or order.get("id")
                    try:
                        order_id_int = int(order_id)
                        if order_id_int > max_order_id:
                            max_order_id = order_id_int
                    except (ValueError, TypeError):
                        continue
                
                # Filter only "new" status orders (1 or 2)
                truly_new_orders = []
                for order in new_orders:
                    status = order.get("status") or {}
                    status_id = status.get("status_id") or status.get("id")
                    try:
                        # Only notify for status 1 (złożone) or 2 (przyjęte do realizacji)
                        if str(status_id) in ["1", "2"] or int(status_id) in [1, 2]:
                            truly_new_orders.append(order)
                    except (ValueError, TypeError):
                        pass
                
                if truly_new_orders:
                    count = len(truly_new_orders)
                    print(f"🔔 {count} new order(s) detected: {[o.get('id') for o in truly_new_orders]}")
                    
                    # For each new order, fetch FULL details for rich notifications
                    for order in truly_new_orders:
                        order_id = order.get("order_id") or order.get("id")
                        
                        # Fetch full order details (with items, buyer info)
                        try:
                            detailed_order = await client.fetch_order_detail(order_id)
                            if detailed_order:
                                # Normalize to same format as list_orders endpoint
                                # We need buyer info and items for rich notification
                                normalized = await get_order_details(order_id)
                                
                                # Send Web Push (browser)
                                db = SessionLocal()
                                try:
                                    subscriptions = db.query(PushSubscription).all()
                                    if subscriptions:
                                        payload = {
                                            "title": "🔔 Nowe zamówienie!",
                                            "body": f"Zamówienie #{order_id} - {normalized.get('items_count', 0)} kart za {normalized.get('total', 0)} zł"
                                        }
                                        for sub in subscriptions:
                                            try:
                                                await send_web_push(json.loads(sub.subscription_json), payload)
                                            except Exception as push_err:
                                                print(f"Failed to send web push: {push_err}")
                                finally:
                                    db.close()
                                
                                # Send ntfy notification with FULL details
                                await send_rich_order_notification(normalized)
                        except Exception as detail_err:
                            print(f"⚠️  Could not fetch details for order #{order_id}: {detail_err}")
                else:
                    print(f"ℹ️  Found {len(new_orders)} new order(s), but none with status 1 or 2")
                
                # Update last processed order ID (persistent)
                if max_order_id > last_order_id:
                    last_order_id = max_order_id
                    write_last_order_id(last_order_id)
                    print(f"✅ Updated last_order_id to {last_order_id}")
                    
        except Exception as e:
            print(f"❌ Error checking for new orders: {e}")
            import traceback
            traceback.print_exc()


# File-based persistence for last order ID
LAST_ORDER_ID_FILE = Path(settings.upload_dir).parent / "last_order_id.txt"

def read_last_order_id() -> int:
    """Read last processed order ID from file."""
    try:
        if LAST_ORDER_ID_FILE.exists():
            content = LAST_ORDER_ID_FILE.read_text().strip()
            return int(content) if content else 0
    except Exception as e:
        print(f"Warning: Could not read last_order_id from file: {e}")
    return 0

def write_last_order_id(order_id: int) -> None:
    """Write last processed order ID to file."""
    try:
        LAST_ORDER_ID_FILE.parent.mkdir(parents=True, exist_ok=True)
        LAST_ORDER_ID_FILE.write_text(str(order_id))
    except Exception as e:
        print(f"Error: Could not write last_order_id to file: {e}")


async def send_rich_order_notification(order: dict) -> None:
    """
    Send detailed order notification via ntfy with full customer data.
    ONLY use with self-hosted ntfy server (GDPR compliant)!
    
    Notification includes:
    - Customer name, email, phone
    - Order value and item count
    - Top 3 most expensive cards
    - Status info with emoji
    - Clickable actions (view order, accept order)
    """
    if not settings.ntfy_enabled:
        return
    
    try:
        # Extract order data
        order_id = order.get("id")
        items_count = order.get("items_count", 0)
        total = float(order.get("total", 0))
        
        # Customer info
        buyer = order.get("buyer", {})
        user = order.get("user", {})
        customer_name = f"{buyer.get('firstname', '')} {buyer.get('lastname', '')}".strip()
        if not customer_name:
            customer_name = user.get("email", "Klient").split("@")[0]
        
        email = buyer.get("email") or user.get("email", "")
        phone = buyer.get("phone", "")
        
        # Top 3 most expensive items
        items = order.get("items", [])
        top_items = sorted(
            items, 
            key=lambda x: float(x.get("price", 0)) * int(x.get("quantity", 1)), 
            reverse=True
        )[:3]
        
        top_cards_text = "\n".join([
            f"• {item.get('name', 'Unknown')} ({item.get('quantity', 1)}x) - {float(item.get('price', 0)) * int(item.get('quantity', 1)):.2f} zł"
            for item in top_items
        ]) if top_items else "Brak szczegółów"
        
        # Status info
        status = order.get("status", {})
        status_name = status.get("name", "Nieznany")
        status_id = status.get("id")
        status_icon = "🆕" if str(status_id) == "1" else "📦"
        
        # Build rich notification message
        message = f"""📊 Szczegóły zamówienia:

👤 Klient: {customer_name}
📧 Email: {email}
{"📱 Tel: " + phone if phone else "📱 Tel: brak"}
📍 Status: {status_name}

💳 Wartość: {total:.2f} zł
📦 Ilość kart: {items_count}

🏆 Najdroższe karty:
{top_cards_text}

⏰ Data: {order.get('date', 'brak')}
"""
        
        # Prepare ntfy headers
        headers = {
            "Content-Type": "text/plain; charset=utf-8",
            "Title": f"{status_icon} Zamówienie #{order_id} - {customer_name}",
            "Priority": settings.ntfy_priority,
            "Tags": "rotating_light,money_with_wings,shopping_cart",
            "Click": f"{settings.app_base_url}/#/orders?open={order_id}",
            "Actions": f"view, Zobacz szczegóły, {settings.app_base_url}/#/orders?open={order_id}; http, Przyjmij zamówienie, {settings.app_base_url}/api/orders/{order_id}/status, method=PUT, body={{\"status_id\": 2}}"
        }
        
        if settings.ntfy_auth_token:
            headers["Authorization"] = f"Bearer {settings.ntfy_auth_token}"
        
        # Send via ntfy
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{settings.ntfy_url}/{settings.ntfy_topic}",
                headers=headers,
                content=message.encode("utf-8")
            )
            
            if response.status_code == 200:
                print(f"📱 Sent ntfy notification for order #{order_id}")
            else:
                print(f"⚠️  ntfy notification failed: {response.status_code} - {response.text}")
                
    except Exception as e:
        print(f"❌ Error sending ntfy notification: {e}")
        import traceback
        traceback.print_exc()

# In-memory timestamp of last product sync
_last_products_sync_ts: float | None = None
_products_sync_in_progress: bool = False
_sales_cache: dict | None = None
_taxonomy_cache: dict[str, dict] = {}
_orders_cache: dict | None = None
_orders_cache_ts: float | None = None

async def _get_sales_metrics():
    global _sales_cache
    now = time.time()
    ttl = max(1, int(getattr(settings, 'sales_metrics_ttl_minutes', 5))) * 60
    if _sales_cache and (now - _sales_cache.get('ts', 0) < ttl):
        return _sales_cache.get('data')
    sold_count = 0
    sold_value_pln = 0.0
    users_count = None
    try:
        if settings.shoper_base_url and settings.shoper_access_token:
            client = ShoperClient(settings.shoper_base_url, settings.shoper_access_token)
            orders = await client.fetch_all_orders(limit=200)
            for o in orders:
                c = o.get("total_products")
                if c is None:
                    products = (
                        o.get("products")
                        or o.get("items")
                        or o.get("orders_products")
                        or o.get("order_products")
                        or []
                    )
                    if isinstance(products, dict):
                        products = products.get("items") or products.get("list") or []
                    # Avoid fetching per-order products here for speed
                    try:
                        c = sum(int(p.get("quantity") or p.get("qty") or p.get("count") or 0) for p in (products or []) if isinstance(p, dict))
                    except Exception:
                        c = 0
                try:
                    sold_count += int(c or 0)
                except Exception:
                    pass
                try:
                    val = o.get("sum") or o.get("total_gross") or o.get("total") or o.get("amount")
                    if val is not None:
                        sold_value_pln += float(str(val).replace(",", "."))
                except Exception:
                    pass
            users = await client.fetch_all_users(limit=200)
            users_count = len(users)
    except Exception:
        pass
    data = {"sold_count": sold_count, "sold_value_pln": sold_value_pln, "users_count": users_count}
    _sales_cache = {"ts": now, "data": data}
    return data

def _tax_cache_get(key: str):
    now = time.time()
    entry = _taxonomy_cache.get(key)
    if not entry:
        return None
    ttl = max(1, int(getattr(settings, 'shoper_taxonomy_ttl_minutes', 60))) * 60
    if now - entry.get('ts', 0) > ttl:
        return None
    return entry.get('data')

def _tax_cache_set(key: str, data):
    _taxonomy_cache[key] = { 'ts': time.time(), 'data': data }

async def _sync_products_if_needed(force: bool = False):
    global _last_products_sync_ts, _products_sync_in_progress
    if _products_sync_in_progress:
        return
    if not settings.shoper_base_url or not settings.shoper_access_token:
        return
    import time as _t
    now = _t.time()
    if not force and _last_products_sync_ts is not None:
        ttl = max(1, int(settings.shoper_sync_ttl_minutes)) * 60
        if now - _last_products_sync_ts < ttl:
            return
    _products_sync_in_progress = True
    try:
        client = ShoperClient(settings.shoper_base_url, settings.shoper_access_token)
        # Spróbuj pobrać więcej na stronę, aby szybciej zapełnić magazyn
        items = await client.fetch_all_products(limit=250)
        upsert_products(items)
        _last_products_sync_ts = now
    except Exception:
        pass
    finally:
        _products_sync_in_progress = False


@app.post("/pricing/estimate")
async def pricing_estimate(body: dict = Body(default={})):
    name = (body or {}).get('name')
    number = (body or {}).get('number')
    set_name = (body or {}).get('set')
    set_code = (body or {}).get('set_code')
    if not name and not number:
        return JSONResponse({"error": "name or number required"}, status_code=400)
    provider = get_provider()
    det = DetectedData(name=name, number=str(number) if number is not None else None, set=set_name, set_code=set_code)
    try:
        cands = await provider.search(det)
    except Exception as e:
        return JSONResponse({"error": f"search failed: {e}"}, status_code=500)
    if not cands:
        return {"pricing": None, "note": "no candidates"}
    # Prefer exact number match if provided
    num_text = str(number or "").strip()
    if num_text:
        cands.sort(key=lambda c: (1 if (c.number and str(c.number)==num_text) else 0, c.score), reverse=True)
    # Allow explicit candidate selection
    cand_id = body.get('candidate_id') or (cands[0].id if cands else None)
    cid = cand_id
    try:
        details = await provider.details(cid)
        preferred_variant = body.get('variant') or body.get('finish')
        extracted = extract_prices_from_payload(details, preferred_variant=preferred_variant)
        cm_avg = extracted.get("cardmarket_7d_average")
        computed = compute_price_pln(cm_avg)
        pricing_payload = {
            "cardmarket_currency": extracted.get("cardmarket_currency"),
            "cardmarket_7d_average": cm_avg,
            "eur_pln_rate": float(settings.eur_pln_rate),
            "multiplier": float(settings.price_multiplier),
            "price_pln": computed.get("price_pln"),
            "price_pln_final": computed.get("price_pln_final"),
            "source_key": extracted.get("source_key"),
        }
        return {"pricing": pricing_payload, "provider_id": cid}
    except Exception as e:
        return JSONResponse({"error": f"details failed: {e}"}, status_code=500)


@app.post("/pricing/convert")
async def pricing_convert(body: dict = Body(default={})):  # { eur: number }
    try:
        eur = float((body or {}).get('eur'))
    except Exception:
        return JSONResponse({"error": "eur required"}, status_code=400)
    base = eur * float(settings.eur_pln_rate)
    final = base * float(settings.price_multiplier)
    return { "price_pln": round(base,2), "price_pln_final": round(final,2), "eur_pln_rate": float(settings.eur_pln_rate), "multiplier": float(settings.price_multiplier) }


@app.post("/pricing/variants")
async def pricing_variants(body: dict = Body(default={})):  # Return possible variant prices for best match
    from .pricing import list_variant_prices
    name = (body or {}).get('name')
    number = (body or {}).get('number')
    set_name = (body or {}).get('set')
    set_code = (body or {}).get('set_code')
    if not name and not number:
        return JSONResponse({"error": "name or number required"}, status_code=400)
    provider = get_provider()
    det = DetectedData(name=name, number=str(number) if number is not None else None, set=set_name, set_code=set_code)
    try:
        cands = await provider.search(det)
    except Exception as e:
        return JSONResponse({"error": f"search failed: {e}"}, status_code=500)
    if not cands:
        return {"candidates": [], "variants": []}
    # Allow explicit candidate selection
    cand_id = body.get('candidate_id') or (cands[0].id if cands else None)
    cid = cand_id
    try:
        details = await provider.details(cid)
        variants = list_variant_prices(details)
        # Emit normalized candidate list
        out_cands = [
            {"id": c.id, "name": c.name, "set": c.set, "number": c.number, "image": c.image, "score": c.score}
            for c in cands
        ]
        return {"provider_id": cid, "candidates": out_cands, "variants": variants}
    except Exception as e:
        return JSONResponse({"error": f"details failed: {e}"}, status_code=500)

@app.post("/pricing/manual_search")
async def manual_search(body: dict = Body(default={})):
    name = (body or {}).get('name')
    number = (body or {}).get('number')
    if not name and not number:
        return JSONResponse({"error": "name or number required"}, status_code=400)

    provider = get_provider()
    det = DetectedData(name=name, number=str(number) if number is not None else None)
    try:
        cands = await provider.search(det)
        
        # Broad search to find alternatives (same name, different sets)
        if len(cands) < 10 and name:
            try:
                broad_det = DetectedData(name=name, number=None)
                broad_cands = await provider.search(broad_det)
                
                # Merge maintaining order but avoiding duplicates
                seen_ids = {c.id for c in cands}
                for bc in broad_cands:
                    if bc.id not in seen_ids:
                        cands.append(bc)
                        seen_ids.add(bc.id)
            except Exception:
                pass # Ignore broad search errors
                
    except Exception as e:
        return JSONResponse({"error": f"search failed: {e}"}, status_code=500)

    if not cands:
        return JSONResponse({"error": "not_found"}, status_code=404)

    best_cand = cands[0]

    try:
        details = await provider.details(best_cand.id)
        extracted = extract_prices_from_payload(details, preferred_variant=None)
        cm_avg = extracted.get("cardmarket_7d_average")
        computed = compute_price_pln(cm_avg)

        # Calculate purchase price (80% of cardmarket price)
        purchase_price_pln = None
        if computed.get("price_pln"):
            purchase_price_pln = round(computed["price_pln"] * 0.8, 2)

        variants = list_variant_prices(details)

        # Construct a clean pricing object with all conversions
        final_pricing = {
            "price_pln_final": computed.get("price_pln_final"),
            "purchase_price_pln": purchase_price_pln,
            "source": extracted.get("source_key"),
            "variants": variants,
            "cardmarket": {},
            "graded": {},
        }

        cm_prices = extracted.get("cardmarket_prices", {})
        if cm_prices:
            for key in ['avg1', 'avg7', 'avg30', '7d_average', '30d_average']:
                if cm_prices.get(key):
                    computed_avg = compute_price_pln(cm_prices.get(key))
                    final_pricing["cardmarket"][key] = {
                        "eur": cm_prices.get(key),
                        "pln_final": computed_avg.get("price_pln_final")
                    }

        graded_prices = cm_prices.get("graded", {})
        if graded_prices:
            for service, grades in graded_prices.items():
                if not isinstance(grades, dict): continue
                final_pricing["graded"][service] = {}
                for grade, price in grades.items():
                    if isinstance(price, (int, float)):
                        computed_graded = compute_price_pln(price)
                        final_pricing["graded"][service][grade] = {
                            "eur": price,
                            "pln_final": computed_graded.get("price_pln_final")
                        }

        # Prepare list of alternative candidates with fallbacks
        candidates_list = []
        for c in cands:
            # Ensure all fields are populated from the candidate object
            candidates_list.append({
                "id": c.id,
                "name": c.name or "Unknown Card",
                "set": c.set or "Unknown Set",
                "number": c.number or "?",
                "image": c.image or None  # Frontend will handle missing images
            })

        return {
            "card": {
                "id": best_cand.id,
                "name": best_cand.name,
                "number": best_cand.number or details.get("number") or details.get("collection_number"),
                "set": best_cand.set,
                "set_code": best_cand.set_code or details.get("set_code"),
                "image": details.get("image"),
                "rarity": details.get("rarity"),
            },
            "pricing": final_pricing,
            "candidates": candidates_list,
            "raw_details": details,
        }
    except Exception as e:
        return JSONResponse({"error": f"details failed: {e}"}, status_code=500)


class PricingImageRequest(BaseModel):
    image: str

@app.post("/pricing/estimate_from_image")
async def estimate_from_image(body: PricingImageRequest):
    """
    Analyzes an image of a card, extracts name/number, and returns pricing information
    without saving any data to the database. A lightweight version for live pricing.
    """
    db = SessionLocal()
    try:
        import base64
        from .analysis.pipeline import detect_card_roi_bytes, warp_card_from_bytes, extract_name_number_from_bytes
        from .vision import extract_fields_with_openai_bytes

        # 1. Decode image from base64
        try:
            image_bytes = base64.b64decode(body.image.split(',')[1])
        except Exception as e:
            return JSONResponse({"error": f"Nieprawidłowy format obrazu (base64): {e}"}, status_code=400)

        # 2. Try Local OCR Pipeline first
        name, number = None, None
        
        # Try finding ROI and OCR
        try:
            detected_tuple = extract_name_number_from_bytes(image_bytes)
            detected_data = detected_tuple[0]
            print(f"DEBUG: Local OCR raw result: {detected_data}")
            name = detected_data.get("name")
            number = detected_data.get("number")
        except Exception as e:
            print(f"Local OCR failed: {e}")

        # 3. Fallback to OpenAI Vision if local OCR failed
        if not name or not number:
            print("Local OCR insufficient, trying OpenAI Vision...")
            openai_data = extract_fields_with_openai_bytes(image_bytes)
            print(f"DEBUG: OpenAI Vision result: {openai_data}")
            
            if openai_data.get("name"):
                name = openai_data.get("name")
            if openai_data.get("number"):
                number = openai_data.get("number")

        print(f"DEBUG: Final extraction result - Name: '{name}', Number: '{number}'")

        if not name and not number:
            return JSONResponse({"error": "Nie udało się odczytać nazwy ani numeru z karty (OCR + AI failed)"}, status_code=404)

        # 4. Call the existing manual_search logic to get pricing
        return await manual_search(body={"name": name, "number": number})

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error in estimate_from_image: {e}")
        return JSONResponse({"error": f"Internal Server Error: {str(e)}"}, status_code=500)
    finally:
        db.close()


@app.post("/pricing/analyze_collection")
async def analyze_collection(body: PricingImageRequest):
    """
    Analyzes an image containing MULTIPLE cards.
    Returns a list of detected cards with their estimated pricing.
    """
    db = SessionLocal()
    try:
        import base64
        from .analysis.pipeline import detect_multiple_cards_roi_bytes, extract_name_number_from_bytes
        
        # 1. Decode image
        try:
            image_bytes = base64.b64decode(body.image.split(',')[1])
        except Exception as e:
            return JSONResponse({"error": f"Invalid base64 image: {e}"}, status_code=400)

        # 2. Detect multiple ROIs
        crops = detect_multiple_cards_roi_bytes(image_bytes)
        if not crops:
            return JSONResponse({"error": "Nie wykryto żadnych kart na zdjęciu"}, status_code=404)

        results = []
        
        # 3. Process each crop
        for i, (roi, crop_bytes) in enumerate(crops):
            try:
                # Try Local OCR first
                detected_tuple = extract_name_number_from_bytes(crop_bytes)
                detected_data = detected_tuple[0]
                name = detected_data.get("name")
                number = detected_data.get("number")
                
                # If local OCR fails, maybe try OpenAI (optional - skipping for speed/cost in batch mode for now)
                # To enable OpenAI for collection, uncomment below (WARNING: slow and costly for many cards)
                # if not name or not number:
                #     from .vision import extract_fields_with_openai_bytes
                #     openai_data = extract_fields_with_openai_bytes(crop_bytes)
                #     name = openai_data.get("name") or name
                #     number = openai_data.get("number") or number

                if name or number:
                    # Get pricing
                    search_res = await manual_search(body={"name": name, "number": number})
                    
                    pricing_data = None
                    card_data = None
                    
                    if isinstance(search_res, dict):
                        pricing_data = search_res.get("pricing")
                        card_data = search_res.get("card")
                    elif isinstance(search_res, JSONResponse):
                        # Handle error response from manual_search gracefully
                        pass

                    # Encode crop to base64 for frontend display
                    crop_b64 = "data:image/jpeg;base64," + base64.b64encode(crop_bytes).decode('ascii')

                    results.append({
                        "id": i,
                        "crop_image": crop_b64,
                        "detected": {"name": name, "number": number},
                        "card": card_data,
                        "pricing": pricing_data,
                        "roi": roi # (x, y, w, h) normalized
                    })
            except Exception as e:
                print(f"Error processing crop {i}: {e}")
                continue

        return {"results": results, "count": len(results)}

    except Exception as e:
        print(f"Error in analyze_collection: {e}")
        return JSONResponse({"error": f"Collection analysis failed: {str(e)}"}, status_code=500)
    finally:
        db.close()


@app.get("/shoper/attributes")
async def shoper_attributes():
    if not settings.shoper_base_url or not settings.shoper_access_token:
        return JSONResponse({"error": "Configure SHOPER_BASE_URL and SHOPER_ACCESS_TOKEN"}, status_code=400)
    cached = _tax_cache_get('attributes')
    if cached is not None:
        return cached
    client = ShoperClient(settings.shoper_base_url, settings.shoper_access_token)
    data = await client.fetch_attributes()
    items = data.get('items') if isinstance(data, dict) else []
    simple = simplify_attributes(items if isinstance(items, list) else [])
    out = { 'items': simple }
    _tax_cache_set('attributes', out)
    return out


@app.get("/shoper/categories")
async def shoper_categories():
    if not settings.shoper_base_url or not settings.shoper_access_token:
        return JSONResponse({"error": "Configure SHOPER_BASE_URL and SHOPER_ACCESS_TOKEN"}, status_code=400)
    cached = _tax_cache_get('categories')
    if cached is not None:
        return cached
    client = ShoperClient(settings.shoper_base_url, settings.shoper_access_token)
    data = await client.fetch_categories()
    items = data.get('items') if isinstance(data, dict) else (data if isinstance(data, list) else [])
    simple = simplify_categories(items if isinstance(items, list) else [])
    # Fallback to ids_dump.json if API returns nothing
    if not simple:
        try:
            dump_path = Path(__file__).parent.parent / "ids_dump.json"
            if dump_path.exists():
                import json as _json
                raw = _json.loads(dump_path.read_text(encoding='utf-8'))
                cats = raw.get('categories') if isinstance(raw, dict) else []
                if isinstance(cats, list):
                    simple = simplify_categories(cats)
        except Exception:
            pass
    # Final hardcoded fallback
    if not simple:
        simple = _CATEGORIES_FALLBACK
    # Extend with sets from tcg_sets.json that are not on the store yet
    try:
        p = Path(__file__).parent.parent.parent / "storage" / "legacy" / "tcg_sets.json"
        if p.exists():
            import json as _json
            sets_data = _json.loads(p.read_text(encoding='utf-8'))
            existing = { (c.get('name') or '').lower() for c in simple }
            
            items_iter = []
            if isinstance(sets_data, dict):
                for era, sets in sets_data.items():
                    if isinstance(sets, list):
                        items_iter.extend(sets)
            
            for it in items_iter:
                nm = (it.get('name') or it.get('set') or '').strip()
                if not nm or nm.lower() in existing:
                    continue
                simple.append({"category_id": None, "name": nm, "code": it.get('code'), "virtual": True})
    except Exception as e:
        print(f"Error extending categories with tcg_sets.json: {e}")
    out = { 'items': simple }
    _tax_cache_set('categories', out)
    return out





@app.get("/shoper/languages")
async def shoper_languages():
    if not settings.shoper_base_url or not settings.shoper_access_token:
        return JSONResponse({"error": "Configure SHOPER_BASE_URL and SHOPER_ACCESS_TOKEN"}, status_code=400)
    cached = _tax_cache_get('languages')
    if cached is not None:
        return cached
    client = ShoperClient(settings.shoper_base_url, settings.shoper_access_token)
    data = await client.fetch_languages()
    _tax_cache_set('languages', data)
    return data


@app.get("/shoper/product/{product_id}")
async def get_shoper_product(product_id: int):
    if not settings.shoper_base_url or not settings.shoper_access_token:
        return JSONResponse({"error": "Configure SHOPER_BASE_URL and SHOPER_ACCESS_TOKEN"}, status_code=400)
    client = ShoperClient(settings.shoper_base_url, settings.shoper_access_token)
    product = await client.get_product(product_id)
    if not product:
        return JSONResponse({"error": "Product not found"}, status_code=404)
    return product





async def _find_best_category_match_internal(name: str, threshold: int = 85) -> dict | None:
    """
    Internal helper to find the best Shoper category for a given set name.
    """
    if not name:
        return None

    # This function uses the existing taxonomy cache, so it's efficient.
    categories_response = await shoper_categories()
    
    all_categories = []
    # The response can be a dict with 'items' or a direct list from fallback
    if isinstance(categories_response, dict) and "items" in categories_response:
        all_categories = categories_response["items"]
    elif isinstance(categories_response, list):
        all_categories = categories_response
    
    if not all_categories:
        return None

    from rapidfuzz import process, fuzz

    # Create a dictionary mapping name to the full category object
    choices = {cat["name"]: cat for cat in all_categories if cat.get("name")}
    
    # Find the best match
    result = process.extractOne(name, choices.keys(), scorer=fuzz.token_set_ratio)
    
    if result:
        best_match_name, score, _ = result
        if score >= threshold:
            return choices[best_match_name]

    return None





@app.get("/shoper/availability")
async def shoper_availability():
    if not settings.shoper_base_url or not settings.shoper_access_token:
        return JSONResponse({"error": "Configure SHOPER_BASE_URL and SHOPER_ACCESS_TOKEN"}, status_code=400)
    cached = _tax_cache_get('availability')
    if cached is not None:
        return cached
    client = ShoperClient(settings.shoper_base_url, settings.shoper_access_token)
    data = await client.fetch_availability()
    _tax_cache_set('availability', data)
    return data


@app.post("/scan", response_model=ScanResponse)
async def scan_image(
    file: UploadFile = File(...),
    session_id_str: Optional[str] = Form(default=None),
    file_back: UploadFile | None = File(default=None),
    starting_warehouse_code: str | None = Form(default=None),
):
    # Manually parse session_id from string to handle empty strings from form data
    session_id: int | None = None
    if session_id_str and session_id_str.isdigit():
        session_id = int(session_id_str)
        
    # Ensure upload dir exists
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Persist the uploaded file(s) (for audit/retry); in future add TTL/cleanup
    sanitized_filename = os.path.basename(file.filename)
    target = upload_dir / f"{int(time.time()*1000)}_{sanitized_filename}"
    with target.open("wb") as out:
        shutil.copyfileobj(file.file, out)
    target_back = None
    if file_back is not None:
        target_back = upload_dir / f"{int(time.time()*1000)}_back_{file_back.filename}"
        with target_back.open("wb") as out2:
            shutil.copyfileobj(file_back.file, out2)

    # Persist scan early (basic data)
    db = SessionLocal()
    try:
        # Determine the starting code. Priority:
        # 1. Code passed directly to the endpoint.
        # 2. Code from the session.
        # 3. None (find first available).
        starting_code = starting_warehouse_code
        if session_id and not starting_code:
            session = db.get(Session, session_id)
            if session and session.starting_warehouse_code:
                starting_code = session.starting_warehouse_code

        # Calculate suggested warehouse code (NOT saved to database yet)
        # Will be assigned only upon successful publication
        suggested_warehouse_code = None
        try:
            suggested_warehouse_code = get_next_free_location(db, starting_code=starting_code)
        except NoFreeLocationError:
            # Non-fatal: user can still scan and publish will assign a code
            print("WARNING: No free storage locations available, will assign at publish time")

        scan = Scan(
            filename=file.filename,
            stored_path=str(target),
            stored_path_back=(str(target_back) if target_back is not None else None),
            message="pending",
            session_id=session_id,
            warehouse_code=None,  # NOT assigned yet - will be set at publish time
        )
        db.add(scan)
        db.flush()

        # Compute fingerprint first and detect duplicates
        duplicate_hit_id: int | None = None
        duplicate_distance: int | None = None
        try:
            from PIL import Image as _PILImage
            with _PILImage.open(target) as _im:
                fp = compute_fingerprint(_im, use_orb=True)
            fprow = Fingerprint(
                scan_id=scan.id,
                phash=pack_ndarray(fp["phash"]),
                dhash=pack_ndarray(fp["dhash"]),
                tile_phash=pack_ndarray(fp["tile_phash"]),
                orb=pack_ndarray(fp.get("orb")),
                meta=None,
            )
            db.add(fprow)
            db.commit()

            # Optional: compute fingerprint for back image as well and store as an extra row
            if target_back is not None:
                try:
                    with _PILImage.open(target_back) as _im2:
                        fp2 = compute_fingerprint(_im2, use_orb=True)
                    fprow2 = Fingerprint(
                        scan_id=scan.id,
                        phash=pack_ndarray(fp2["phash"]),
                        dhash=pack_ndarray(fp2["dhash"]),
                        tile_phash=pack_ndarray(fp2["tile_phash"]),
                        orb=pack_ndarray(fp2.get("orb")),
                        meta=None,
                    )
                    db.add(fprow2)
                    db.commit()
                except Exception:
                    pass

            # Duplicate search (only if enabled)
            if settings.duplicate_check_enabled:
                src_phash = fp["phash"]
                src_dhash = fp["dhash"]
                src_tile = fp["tile_phash"]
                rows = db.query(Fingerprint).filter(Fingerprint.scan_id != scan.id).all()
                best_dist = None
                best_id = None
                for r in rows:
                    try:
                        ph = unpack_ndarray(r.phash)
                        dh = unpack_ndarray(r.dhash)
                        tl = unpack_ndarray(r.tile_phash)
                    except Exception:
                        continue
                    score = 0
                    score += hamming_distance(src_phash, ph)
                    score += hamming_distance(src_dhash, dh)
                    if getattr(settings, 'duplicate_use_tiles', True):
                        try:
                            for a, b in zip(src_tile, tl):
                                score += hamming_distance(a, b)
                        except Exception:
                            score += 999
                    if best_dist is None or score < best_dist:
                        best_dist = score
                        best_id = r.scan_id
                thr = max(1, int(getattr(settings, 'duplicate_distance_threshold', 80)))
                if best_dist is not None and best_dist <= thr and best_id is not None:
                    duplicate_hit_id = int(best_id)
                    duplicate_distance = int(best_dist)
        except Exception:
            pass

        # Public URL for image (served under /uploads)
        try:
            image_url = f"/uploads/{target.name}"
        except Exception:
            image_url = None

        # Early exit on duplicate to avoid Vision/provider
        if duplicate_hit_id is not None:
            # Get catalog_id from the original scan's fingerprint
            orig_fp = db.query(Fingerprint).filter(Fingerprint.scan_id == duplicate_hit_id).first()
            catalog_entry = None
            if orig_fp and orig_fp.catalog_id:
                catalog_entry = db.get(CardCatalog, orig_fp.catalog_id)
            
            # Fallback: get original scan for candidates and legacy data
            try:
                orig = db.get(Scan, duplicate_hit_id)
            except Exception:
                orig = None
            
            if catalog_entry:
                # Use data from CardCatalog (preferred)
                # Build full detected data with all variants
                detected_data = {
                    "name": catalog_entry.name,
                    "set": catalog_entry.set_name,
                    "set_code": catalog_entry.set_code,
                    "number": catalog_entry.number,
                    "rarity": catalog_entry.rarity,
                    "energy": catalog_entry.energy,
                    "suggested_warehouse_code": suggested_warehouse_code,
                }
                
                # Calculate all price variants from catalog
                variants = []
                for finish_type in ["normal", "holo", "reverse"]:
                    price_info = _calculate_price_from_catalog(catalog_entry, finish_type)
                    if price_info.get("price_pln_final"):
                        variants.append({
                            "label": finish_type.replace("normal", "Normal").replace("holo", "Holo").replace("reverse", "Reverse Holo"),
                            "finish": finish_type,
                            "base_eur": price_info.get("base_eur"),
                            "price_pln": price_info.get("price_pln"),
                            "price_pln_final": price_info.get("price_pln_final"),
                            "estimated": price_info.get("estimated", False),
                        })
                
                detected_data["variants"] = variants
                
                # Set default price (normal finish)
                default_price_info = _calculate_price_from_catalog(catalog_entry, "normal")
                detected_data["price_pln_final"] = default_price_info.get("price_pln_final")
                
                # Try to match set to Shoper category
                try:
                    matched_category = await _match_shoper_category(catalog_entry.set_name)
                    if matched_category:
                        detected_data["set_id"] = matched_category.get("set_id")
                except Exception:
                    pass
                
                # Map attributes to Shoper option IDs
                try:
                    if settings.shoper_base_url and settings.shoper_access_token:
                        from .attributes import map_detected_to_form_ids
                        client = ShoperClient(settings.shoper_base_url, settings.shoper_access_token)
                        tax = await client.fetch_attributes()
                        items = tax.get("items") if isinstance(tax, dict) else []
                        if items:
                            # Get original scan data for language/condition/variant if available
                            detected_attrs = {
                                "rarity": catalog_entry.rarity,
                                "energy": catalog_entry.energy,
                                "language": orig.detected_language if orig else None,
                                "variant": orig.detected_variant if orig else None,
                                "condition": orig.detected_condition if orig else None,
                            }
                            mapped_attributes = map_detected_to_form_ids(detected_attrs, items)
                            detected_data.update(mapped_attributes)
                            
                            # Set defaults if not mapped
                            if not detected_data.get('64'):  # Language
                                detected_data['64'] = '142'  # English
                            if not detected_data.get('66'):  # Quality/Condition
                                detected_data['66'] = '176'  # Near Mint
                            if not detected_data.get('65'):  # Finish
                                detected_data['65'] = '184'  # Normal
                            if not detected_data.get('39'):  # Card Type
                                detected_data['39'] = '182'  # Nie dotyczy (N/A)
                except Exception as e:
                    print(f"WARNING: Failed to map attributes for duplicate: {e}")
                
                detected = DetectedData(**detected_data)
                
                # Link scan to catalog
                scan.catalog_id = catalog_entry.id
                scan.detected_name = catalog_entry.name
                scan.detected_set = catalog_entry.set_name
                scan.detected_set_code = catalog_entry.set_code
                scan.detected_number = catalog_entry.number
                scan.detected_rarity = catalog_entry.rarity
                scan.detected_energy = catalog_entry.energy
                scan.price_pln = default_price_info.get("price_pln")
                scan.price_pln_final = default_price_info.get("price_pln_final")
                
                # Save full detected_data (including Shoper attributes) to detected_payload
                scan.detected_payload = json.dumps(detected_data)
                
                # Update fingerprint with catalog_id
                if fprow:
                    fprow.catalog_id = catalog_entry.id
                
                # Copy candidates from original scan
                response_candidates = []
                if orig:
                    orig_candidates_db = db.query(ScanCandidate).filter(ScanCandidate.scan_id == orig.id).all()
                    for c_orig in orig_candidates_db:
                        new_cand = ScanCandidate(
                            scan_id=scan.id,
                            provider_id=c_orig.provider_id,
                            name=c_orig.name,
                            set=c_orig.set,
                            set_code=c_orig.set_code,
                            number=c_orig.number,
                            rarity=c_orig.rarity,
                            image=c_orig.image,
                            score=c_orig.score,
                            chosen=c_orig.chosen,
                        )
                        db.add(new_cand)
                        response_candidates.append(Candidate(
                            id=new_cand.provider_id,
                            name=new_cand.name,
                            set=new_cand.set,
                            set_code=new_cand.set_code,
                            number=new_cand.number,
                            image=new_cand.image,
                            score=new_cand.score,
                        ))

                scan.message = f"duplicate_of:{duplicate_hit_id} distance:{duplicate_distance} catalog:{catalog_entry.id}"
                db.commit()
                return ScanResponse(
                    scan_id=scan.id,
                    detected=detected,
                    candidates=response_candidates,
                    message=scan.message,
                    stored_path=scan.stored_path,
                    image_url=image_url,
                    duplicate_of=duplicate_hit_id,
                    duplicate_distance=duplicate_distance,
                    warehouse_code=suggested_warehouse_code,
                )
            elif orig:
                # Fallback: use original scan data (legacy behavior)
                # Try to get provider details to calculate variants
                detected_data = {
                    "name": orig.detected_name,
                    "set": orig.detected_set,
                    "set_code": orig.detected_set_code,
                    "number": orig.detected_number,
                    "language": orig.detected_language,
                    "variant": orig.detected_variant,
                    "condition": orig.detected_condition,
                    "rarity": orig.detected_rarity,
                    "energy": orig.detected_energy,
                    "warehouse_code": suggested_warehouse_code,
                }
                
                # Try to enrich with pricing from provider if we have candidates
                orig_candidates_db = db.query(ScanCandidate).filter(ScanCandidate.scan_id == orig.id).all()
                if orig_candidates_db:
                    try:
                        provider = get_provider()
                        # Get details from best candidate
                        best_candidate = orig_candidates_db[0]
                        details = await provider.details(best_candidate.provider_id)
                        
                        # Calculate price variants
                        variants = list_variant_prices(details)
                        detected_data["variants"] = variants
                        
                        # Set default price
                        if variants:
                            detected_data["price_pln_final"] = variants[0].get("price_pln_final")
                        
                        # Try to match set to Shoper category
                        try:
                            matched_category = await _match_shoper_category(orig.detected_set)
                            if matched_category:
                                detected_data["set_id"] = matched_category.get("set_id")
                        except Exception:
                            pass
                        
                        # Map attributes to Shoper option IDs
                        try:
                            if settings.shoper_base_url and settings.shoper_access_token:
                                from .attributes import map_detected_to_form_ids
                                client = ShoperClient(settings.shoper_base_url, settings.shoper_access_token)
                                tax = await client.fetch_attributes()
                                items = tax.get("items") if isinstance(tax, dict) else []
                                if items:
                                    detected_attrs = {
                                        "rarity": orig.detected_rarity,
                                        "energy": orig.detected_energy,
                                        "language": orig.detected_language,
                                        "variant": orig.detected_variant,
                                        "condition": orig.detected_condition,
                                    }
                                    mapped_attributes = map_detected_to_form_ids(detected_attrs, items)
                                    detected_data.update(mapped_attributes)
                                    
                                    # Set defaults if not mapped
                                    if not detected_data.get('64'):  # Language
                                        detected_data['64'] = '142'  # English
                                    if not detected_data.get('66'):  # Quality/Condition
                                        detected_data['66'] = '176'  # Near Mint
                                    if not detected_data.get('65'):  # Finish
                                        detected_data['65'] = '184'  # Normal
                        except Exception as e:
                            print(f"WARNING: Failed to map attributes for legacy duplicate: {e}")
                    except Exception as e:
                        print(f"WARNING: Failed to enrich legacy duplicate with provider data: {e}")
                
                detected = DetectedData(**detected_data)
                
                # Save full detected_data (including Shoper attributes) to detected_payload
                scan.detected_payload = json.dumps(detected_data)
                
                # Copy candidates from original scan
                response_candidates = []
                for c_orig in orig_candidates_db:
                    new_cand = ScanCandidate(
                        scan_id=scan.id,
                        provider_id=c_orig.provider_id,
                        name=c_orig.name,
                        set=c_orig.set,
                        set_code=c_orig.set_code,
                        number=c_orig.number,
                        rarity=c_orig.rarity,
                        image=c_orig.image,
                        score=c_orig.score,
                        chosen=c_orig.chosen,
                    )
                    db.add(new_cand)
                    response_candidates.append(Candidate(
                        id=new_cand.provider_id,
                        name=new_cand.name,
                        set=new_cand.set,
                        set_code=new_cand.set_code,
                        number=new_cand.number,
                        image=new_cand.image,
                        score=new_cand.score,
                    ))

                scan.message = f"duplicate_of:{duplicate_hit_id} distance:{duplicate_distance}"
                db.commit()
                return ScanResponse(
                    scan_id=scan.id,
                    detected=detected,
                    candidates=response_candidates,
                    message=scan.message,
                    stored_path=scan.stored_path,
                    image_url=image_url,
                    duplicate_of=duplicate_hit_id,
                    duplicate_distance=duplicate_distance,
                    warehouse_code=suggested_warehouse_code,
                )
            else:
                scan.message = f"duplicate_detected distance:{duplicate_distance}"
                db.commit()
                return ScanResponse(
                    scan_id=scan.id,
                    detected=DetectedData(),
                    candidates=[],
                    message=scan.message,
                    stored_path=scan.stored_path,
                    image_url=image_url,
                    duplicate_of=None,
                    duplicate_distance=duplicate_distance,
                    warehouse_code=suggested_warehouse_code,
                )

        # No duplicate: proceed with Vision + provider
        # Analyze front and optionally back; fuse with preference to front
        detected_front = analyze_card(str(target))
        roi = detect_card_roi(str(target))
        detected_back = None
        if target_back is not None:
            try:
                detected_back = analyze_card(str(target_back))
            except Exception:
                detected_back = None
        fused: dict = dict(detected_front or {})
        def _fill(key: str):
            if not fused.get(key) and isinstance(detected_back, dict):
                val = detected_back.get(key)
                if val:
                    fused[key] = val
        for k in ("name","set","set_code","number","language","variant","condition","rarity","energy","total"):
            _fill(k)
        # Ensure scalar string types for pydantic (sometimes model returns lists)
        def _scalarize(v):
            if v is None:
                return None
            if isinstance(v, (list, tuple)):
                for item in v:
                    if item is None:
                        continue
                    s = str(item).strip()
                    if s:
                        return s
                return None
            return str(v).strip() or None
        for key in ["name","set","set_code","number","language","variant","condition","rarity","energy","total"]:
            if key in fused:
                fused[key] = _scalarize(fused.get(key))
        
        fused['warehouse_code'] = suggested_warehouse_code
        detected = DetectedData(**fused)

        provider = get_provider()
        candidates = await provider.search(detected)

        # If we have candidates, get full details for the best ones to enrich the response
        if candidates:
            try:
                # Enrich top N candidates with better images and details
                for i, cand in enumerate(candidates[:5]): # Limit to top 5 to avoid too many API calls
                    details = await provider.details(cand.id)
                    if i == 0: # For the best candidate, also enrich the main 'fused' object
                        price_variants = list_variant_prices(details)
                        primary_price_pln_final = None
                        for label_priority in ['Normal', 'Holo', 'Reverse Holo']:
                            variant_info = next((p for p in price_variants if p.get('label') == label_priority), None)
                            if variant_info and variant_info.get('price_pln_final') is not None:
                                primary_price_pln_final = variant_info.get('price_pln_final')
                                break
                        fused['price_pln_final'] = primary_price_pln_final
                        fused['variants'] = price_variants

                        detailed_set_name = details.get("episode", {}).get("name")
                        detailed_set_code = details.get("episode", {}).get("code")

                        fused['set'] = detailed_set_name or fused.get('set') or cand.set
                        fused['set_code'] = detailed_set_code or fused.get('set_code') or cand.set_code
                        fused['rarity'] = details.get("rarity") or fused.get('rarity')

                    # Update candidate's image from details
                    detailed_image = details.get("image")
                    if not detailed_image and isinstance(details.get("images"), dict):
                        detailed_image = details["images"].get("large") or details["images"].get("small")
                    if detailed_image:
                        cand.image = detailed_image

                # Match Set to Shoper Category ID
                matched_category = await _match_shoper_category(fused.get('set'))
                if matched_category:
                    fused.update(matched_category)

                print("FUSED:", fused)

                # Try to map attributes, but don't fail the request if this part fails
                try:
                    # Extract energy from 'types' field (TCGGO API returns list)
                    energy_from_api = details.get("energy")
                    if not energy_from_api:
                        types = details.get('types')
                        if isinstance(types, list) and types:
                            energy_from_api = types[0]
                        elif isinstance(types, str):
                            energy_from_api = types
                    
                    # Use energy from API if available, fallback to Vision detection
                    final_energy = energy_from_api or fused.get('energy')
                    fused['energy'] = final_energy
                    
                    detected_attrs = {
                        "rarity": details.get("rarity"),
                        "variant": detected.variant,
                        "condition": detected.condition,
                        "energy": final_energy,
                        "type": details.get("supertype"),
                    }
                    client = ShoperClient(settings.shoper_base_url, settings.shoper_access_token)
                    tax = await client.fetch_attributes()
                    items = tax.get("items") if isinstance(tax, dict) else []
                    if items:
                        mapped_attributes = map_detected_to_shoper_attributes(detected_attrs, items)
                        fused.update(mapped_attributes)
                except Exception:
                    pass # Log this failure in a real app

            except Exception as e:
                scan.message = f"OpenAI Vision + provider search (details/pricing failed: {e})"
        else:
            scan.message = "OpenAI Vision (no provider candidates)"

        # Re-create DetectedData with the fused data
        detected = DetectedData(**fused)

        # Save to CardCatalog (for future duplicate detection and price updates)
        catalog_entry = None
        if candidates and len(candidates) > 0:
            best_candidate = candidates[0]
            try:
                # Extract prices for catalog
                prices_data = _extract_prices_for_catalog(details) if 'details' in dir() else {}
                
                catalog_entry = _get_or_create_catalog_entry(
                    db=db,
                    provider_id=best_candidate.id,
                    name=best_candidate.name or detected.name,
                    set_name=fused.get('set') or best_candidate.set,
                    set_code=fused.get('set_code') or best_candidate.set_code,
                    number=best_candidate.number or detected.number,
                    rarity=fused.get('rarity') or best_candidate.rarity,
                    energy=fused.get('energy'),
                    image_url=best_candidate.image,
                    price_normal_eur=prices_data.get('price_normal_eur'),
                    price_holo_eur=prices_data.get('price_holo_eur'),
                    price_reverse_eur=prices_data.get('price_reverse_eur'),
                    api_payload=details if 'details' in dir() else None,
                )
                
                # Link scan to catalog
                scan.catalog_id = catalog_entry.id
                
                # Update fingerprint with catalog_id
                if fprow:
                    fprow.catalog_id = catalog_entry.id
                    
            except Exception as e:
                print(f"WARNING: Failed to save to CardCatalog: {e}")

        # Update scan with detected and store candidates
        scan.message = scan.message or "OpenAI Vision + provider search"
        scan.detected_name = detected.name
        scan.detected_set = detected.set
        scan.detected_set_code = detected.set_code
        scan.detected_number = detected.number

        for c in candidates:
            cm = ScanCandidate(
                scan_id=scan.id,
                provider_id=c.id,
                name=c.name,
                set=c.set,
                set_code=c.set_code,
                number=c.number,
                rarity=c.rarity,
                image=c.image,
                score=c.score,
            )
            db.add(cm)
        db.commit()

        return ScanResponse(
            scan_id=scan.id,
            detected=detected,
            candidates=candidates,
            message=scan.message,
            stored_path=scan.stored_path,
            image_url=image_url,
            duplicate_of=None,
            duplicate_distance=None,
            warehouse_code=suggested_warehouse_code,
            overlay=(
                None if roi is None else {
                    "x": float(roi[0]),
                    "y": float(roi[1]),
                    "w": float(roi[2]),
                    "h": float(roi[3]),
                }
            ),
        )
    finally:
        db.close()


@app.post("/scan/candidate_details")
async def get_candidate_details(body: dict = Body(default={})):
    candidate_id = body.get('candidate_id')
    if not candidate_id:
        return JSONResponse({"error": "candidate_id is required"}, status_code=400)

    provider = get_provider()
    fused = {}

    try:
        details = await provider.details(candidate_id)
        
        # Basic info from details
        fused['name'] = details.get('name')
        fused['number'] = details.get('number')
        fused['rarity'] = details.get('rarity')
        fused['set'] = details.get("episode", {}).get("name")
        fused['set_code'] = details.get("episode", {}).get("code")
        fused['language'] = details.get('language')
        fused['variant'] = details.get('variant')
        fused['condition'] = details.get('condition')
        
        # Energy: TCGGO API returns 'types' as list, we take the first one
        energy = details.get('energy')
        if not energy:
            types = details.get('types')
            if isinstance(types, list) and types:
                energy = types[0]
            elif isinstance(types, str):
                energy = types
        fused['energy'] = energy

        # Pricing
        price_variants = list_variant_prices(details)
        primary_price_pln_final = None
        for label_priority in ['Normal', 'Holo', 'Reverse Holo']:
            variant_info = next((p for p in price_variants if p.get('label') == label_priority), None)
            if variant_info and variant_info.get('price_pln_final') is not None:
                primary_price_pln_final = variant_info.get('price_pln_final')
                break
        fused['price_pln_final'] = primary_price_pln_final
        fused['variants'] = price_variants

        # Set Matching
        matched_category = await _match_shoper_category(fused.get('set'))
        if matched_category:
            fused.update(matched_category)

        # Attribute Mapping for form population (option IDs, not text)
        try:
            from .attributes import map_detected_to_form_ids
            
            detected_attrs = {
                "rarity": details.get("rarity"),
                "energy": details.get("energy"),
                "language": details.get("language"),
                "variant": details.get("variant"),
                "condition": details.get("condition"),
            }
            client = ShoperClient(settings.shoper_base_url, settings.shoper_access_token)
            tax = await client.fetch_attributes()
            items = tax.get("items") if isinstance(tax, dict) else []
            if items:
                form_ids = map_detected_to_form_ids(detected_attrs, items)
                fused.update(form_ids)
                
                # Force default card type "Nie dotyczy" if not mapped
                if not fused.get('39'):
                    fused['39'] = '182'
        except Exception as e:
            print(f"ERROR during attribute mapping in candidate_details: {e}")

        return fused

    except Exception as e:
        return JSONResponse({"error": f"Failed to get candidate details: {e}"}, status_code=500)


@app.post("/pricing/recalculate")
async def recalculate_price(body: dict = Body(default={})):
    """
    Recalculate price based on finish type (normal, holo, reverse).
    Uses CardCatalog for cached prices.
    
    Body:
        - catalog_id: int (optional) - ID from CardCatalog
        - scan_id: int (optional) - Scan ID to look up catalog_id
        - finish: str - "normal", "holo", or "reverse"
    
    Returns price information for the selected finish.
    """
    catalog_id = body.get("catalog_id")
    scan_id = body.get("scan_id")
    finish = body.get("finish", "normal")
    
    db = SessionLocal()
    try:
        catalog_entry = None
        
        # Get catalog entry by ID or via scan
        if catalog_id:
            catalog_entry = db.get(CardCatalog, catalog_id)
        elif scan_id:
            scan = db.get(Scan, scan_id)
            if scan and scan.catalog_id:
                catalog_entry = db.get(CardCatalog, scan.catalog_id)
        
        if not catalog_entry:
            return JSONResponse({"error": "Card not found in catalog"}, status_code=404)
        
        # Calculate price for the selected finish
        price_info = _calculate_price_from_catalog(catalog_entry, finish)
        
        return {
            "catalog_id": catalog_entry.id,
            "provider_id": catalog_entry.provider_id,
            "name": catalog_entry.name,
            "finish": finish,
            "base_eur": price_info.get("base_eur"),
            "price_pln": price_info.get("price_pln"),
            "price_pln_final": price_info.get("price_pln_final"),
            "estimated": price_info.get("estimated", False),
            "prices": {
                "normal_eur": catalog_entry.price_normal_eur,
                "holo_eur": catalog_entry.price_holo_eur,
                "reverse_eur": catalog_entry.price_reverse_eur,
            }
        }
    finally:
        db.close()


@app.get("/catalog/{catalog_id}")
async def get_catalog_entry(catalog_id: int):
    """Get a single CardCatalog entry by ID."""
    db = SessionLocal()
    try:
        entry = db.get(CardCatalog, catalog_id)
        if not entry:
            return JSONResponse({"error": "Catalog entry not found"}, status_code=404)
        
        return {
            "id": entry.id,
            "provider_id": entry.provider_id,
            "name": entry.name,
            "set_name": entry.set_name,
            "set_code": entry.set_code,
            "number": entry.number,
            "rarity": entry.rarity,
            "energy": entry.energy,
            "image_url": entry.image_url,
            "prices": {
                "normal_eur": entry.price_normal_eur,
                "holo_eur": entry.price_holo_eur,
                "reverse_eur": entry.price_reverse_eur,
            },
            "prices_updated_at": entry.prices_updated_at.isoformat() if entry.prices_updated_at else None,
            "created_at": entry.created_at.isoformat() if entry.created_at else None,
        }
    finally:
        db.close()


@app.post("/catalog/refresh-prices")
async def refresh_catalog_prices(body: dict = Body(default={})):
    """
    Refresh prices for cards in CardCatalog from TCGGO API.
    
    Body:
        - catalog_ids: list[int] (optional) - specific IDs to refresh
        - all: bool (optional) - refresh all catalog entries
        - limit: int (optional) - max entries to refresh (default 100)
    """
    catalog_ids = body.get("catalog_ids", [])
    refresh_all = body.get("all", False)
    limit = min(body.get("limit", 100), 500)  # Cap at 500
    
    db = SessionLocal()
    try:
        if catalog_ids:
            entries = db.query(CardCatalog).filter(CardCatalog.id.in_(catalog_ids)).all()
        elif refresh_all:
            entries = db.query(CardCatalog).limit(limit).all()
        else:
            return JSONResponse({"error": "Specify catalog_ids or all=true"}, status_code=400)
        
        provider = get_provider()
        updated = 0
        errors = []
        
        for entry in entries:
            try:
                details = await provider.details(entry.provider_id)
                prices_data = _extract_prices_for_catalog(details)
                
                if prices_data.get("price_normal_eur") is not None:
                    entry.price_normal_eur = prices_data["price_normal_eur"]
                if prices_data.get("price_holo_eur") is not None:
                    entry.price_holo_eur = prices_data["price_holo_eur"]
                if prices_data.get("price_reverse_eur") is not None:
                    entry.price_reverse_eur = prices_data["price_reverse_eur"]
                
                entry.prices_updated_at = datetime.utcnow()
                entry.api_payload = json.dumps(details)
                updated += 1
            except Exception as e:
                errors.append({"catalog_id": entry.id, "error": str(e)})
        
        db.commit()
        
        return {
            "updated": updated,
            "total": len(entries),
            "errors": errors[:10],  # Limit error list
        }
    finally:
        db.close()


@app.post("/confirm", response_model=ConfirmResponse)
async def confirm_candidate(payload: ConfirmRequest):
    db = SessionLocal()
    try:
        scan = db.get(Scan, payload.scan_id)
        if not scan:
            return JSONResponse({"error": "scan not found"}, status_code=404)
        # find candidate for this scan
        cand = db.query(ScanCandidate).filter(ScanCandidate.scan_id == scan.id, ScanCandidate.provider_id == payload.candidate_id).first()
        if not cand:
            return JSONResponse({"error": "candidate not found for this scan"}, status_code=404)

        # unchoose all, choose this
        db.query(ScanCandidate).filter(ScanCandidate.scan_id == scan.id).update({ScanCandidate.chosen: False})
        cand.chosen = True
        scan.selected_candidate_id = cand.id

        # Update scan with form data if provided
        if payload.detected:
            # Store the whole detected payload as JSON for complete data restoration
            scan.detected_payload = json.dumps(payload.detected)

            scan.detected_name = payload.detected.get('name')
            scan.detected_number = payload.detected.get('number')
            scan.detected_set = payload.detected.get('set')
            
            # Update additional detected fields from form
            if 'energy' in payload.detected:
                scan.detected_energy = payload.detected.get('energy')
            if 'rarity' in payload.detected:
                scan.detected_rarity = payload.detected.get('rarity')
            if 'condition' in payload.detected:
                scan.detected_condition = payload.detected.get('condition')
            if 'language' in payload.detected:
                scan.detected_language = payload.detected.get('language')

            # Resolve variant ID to name
            variant_id = payload.detected.get('65') # 65 is the attribute ID for 'Finish'
            if variant_id:
                try:
                    attrs_response = await shoper_attributes()
                    attrs = attrs_response.get('items', [])
                    finish_attr = next((attr for attr in attrs if attr['attribute_id'] == '65'), None)
                    if finish_attr:
                        option = next((opt for opt in finish_attr['options'] if opt['option_id'] == variant_id), None)
                        if option:
                            scan.detected_variant = option['value']
                except Exception as e:
                    print(f"Error resolving variant: {e}") # Or log it properly

        # Update warehouse code if provided
        if payload.warehouse_code:
            parsed = parse_warehouse_code(payload.warehouse_code)
            if parsed:
                scan.warehouse_code = payload.warehouse_code.upper()
                print(f"INFO: Set warehouse_code={scan.warehouse_code} for scan {scan.id}")
            else:
                print(f"WARNING: Invalid warehouse_code format: {payload.warehouse_code}")

        # Fetch details/prices and compute PLN
        provider = get_provider()
        details = await provider.details(cand.provider_id)
        preferred_variant = payload.detected.get('variant') if payload.detected else (scan.detected_variant or None)
        extracted = extract_prices_from_payload(details, preferred_variant=preferred_variant)
        cm_avg = extracted.get("cardmarket_7d_average")
        computed = compute_price_pln(cm_avg)

        # Persist pricing
        scan.cardmarket_currency = extracted.get("cardmarket_currency")
        scan.cardmarket_7d_average = cm_avg
        scan.price_pln = computed.get("price_pln")
        scan.price_pln_final = computed.get("price_pln_final")
        scan.graded_psa10 = extracted.get("graded_psa10")
        scan.graded_currency = extracted.get("graded_currency")

        # Calculate purchase_price based on RARITY (not variant/finish)
        # Common, Uncommon, Rare → 0.10 PLN
        # Premium rarities (Double Rare, Promo, Illustration Rare, etc.) → 80% of market price
        rarity = scan.detected_rarity or ''
        rarity_lower = rarity.lower()
        
        # Check if it's a premium rarity
        is_premium_rarity = any(keyword in rarity_lower for keyword in [
            'double rare', 'promo', 'illustration rare', 'special illustration rare',
            'ultra rare', 'hyper rare', 'ace spec', 'shiny'
        ])
        
        if is_premium_rarity and scan.price_pln_final:
            # Premium: 80% of market price
            scan.purchase_price = round(scan.price_pln_final * settings.min_price_premium_percent, 2)
            print(f"INFO: Premium rarity '{rarity}' -> purchase_price = 80% of {scan.price_pln_final} = {scan.purchase_price} PLN")
        else:
            # Standard: fixed 0.10 PLN
            scan.purchase_price = settings.min_price_common
            print(f"INFO: Standard rarity '{rarity}' -> purchase_price = {scan.purchase_price} PLN")

        # ALWAYS prefer price from frontend if provided (user may have manually edited)
        if payload.detected and 'price_pln_final' in payload.detected:
             try:
                  price_from_frontend = payload.detected['price_pln_final']
                  if price_from_frontend is not None and price_from_frontend != '':
                      price_override = float(price_from_frontend)
                      if price_override > 0:  # Only override if positive
                          scan.price_pln_final = price_override
                          print(f"DEBUG: Using price from frontend: {price_override} PLN")
                          # Recalculate purchase_price if price changed
                          if is_premium_rarity:
                              scan.purchase_price = round(price_override * settings.min_price_premium_percent, 2)
                              print(f"DEBUG: Recalculated purchase_price = {scan.purchase_price} PLN")
             except (ValueError, TypeError) as e:
                 print(f"WARNING: Invalid price_pln_final from frontend: {payload.detected.get('price_pln_final')} - {e}")
                 pass # keep calculated price
        db.commit()

        pricing_payload = {
            "cardmarket_currency": scan.cardmarket_currency,
            "cardmarket_7d_average": scan.cardmarket_7d_average,
            "eur_pln_rate": float(settings.eur_pln_rate),
            "multiplier": float(settings.price_multiplier),
            "price_pln": scan.price_pln,
            "price_pln_final": scan.price_pln_final,
            "graded_psa10": scan.graded_psa10,
            "graded_currency": scan.graded_currency,
        }

        return ConfirmResponse(status="ok", scan_id=scan.id, candidate_id=payload.candidate_id, note="Selection stored", pricing=pricing_payload)
    finally:
        db.close()


@app.get("/scans", response_model=list[ScanHistoryItem])
def list_scans(limit: int = 20, session_id: int | None = None):
    db = SessionLocal()
    try:
        q = db.query(Scan)
        if session_id is not None:
            try:
                q = q.filter(Scan.session_id == int(session_id))
            except Exception:
                pass
        rows = q.order_by(Scan.id.desc()).limit(max(1, min(limit, 200))).all()
        items: list[ScanHistoryItem] = []
        for s in rows:
            selected = None
            if s.selected_candidate_id:
                c = db.get(ScanCandidate, s.selected_candidate_id)
                if c:
                    selected = Candidate(
                        id=c.provider_id,
                        name=c.name,
                        set=c.set,
                        set_code=c.set_code,
                        number=c.number,
                        image=c.image,
                        score=c.score,
                    )
            items.append(
                ScanHistoryItem(
                    id=s.id,
                    created_at=s.created_at.isoformat(),
                    detected_name=s.detected_name,
                    detected_set=s.detected_set,
                    detected_number=s.detected_number,
                    selected=selected,
                )
            )
        return items
    finally:
        db.close()





@app.get("/products")
async def list_products(limit: int = 50, page: int = 1, category_id: int | None = None, q: str | None = None, sort: str | None = None, order: str = "asc"):
    db = SessionLocal()
    try:
        # Auto-sync on first load or after TTL expiry
        await _sync_products_if_needed(force=False)

        # Fetch categories for name mapping from ids_dump.json
        cat_map = {}
        try:
            # Correctly reference the ids_dump.json at the project root
            dump_path = Path(__file__).parent.parent.parent / "ids_dump.json"
            if not dump_path.exists():
                # Fallback to the one in the app directory if it exists
                dump_path = Path(__file__).parent.parent / "ids_dump.json"

            with open(dump_path, "r", encoding="utf-8") as f:
                all_categories_data = json.load(f)
            
            all_categories = all_categories_data.get('categories', [])
            
            cat_map = {
                int(c.get("category_id")):
                (c.get("translations", {}).get("pl_PL", {}).get("name") or c.get("name"))
                for c in all_categories
                if c.get("category_id") and c.get("translations", {}).get("pl_PL")
            }
        except (FileNotFoundError, json.JSONDecodeError, Exception) as e:
            print(f"Error loading categories from ids_dump.json: {e}")
            pass

        query = db.query(Product)
        if category_id is not None:
            query = query.filter(Product.category_id == category_id)
        if q:
            like = f"%{q}%"
            query = query.filter(Product.name.ilike(like))

        # Get total count after filters
        total_count = query.count()

        sort_map = {
            "name": Product.name,
            "price": Product.price,
            "stock": Product.stock,
            "updated_at": Product.updated_at,
        }
        col = sort_map.get((sort or "").lower(), Product.updated_at)
        if (order or "").lower() == "desc":
            query = query.order_by(col.desc().nullslast())
        else:
            query = query.order_by(col.asc().nullslast())
        
        safe_limit = max(1, min(limit, 500))
        safe_page = max(1, page)
        
        rows = query.offset((safe_page - 1) * safe_limit).limit(safe_limit).all()
        items = [
            {
                "id": r.id,
                "shoper_id": r.shoper_id,
                "code": r.code,
                "name": r.name,
                "price": r.price,
                "stock": r.stock,
                "image": _product_image_url(r),
                "category_id": r.category_id,
                "category_name": cat_map.get(r.category_id),
                "permalink": r.permalink,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in rows
        ]
        return {"items": items, "total_count": total_count, "page": safe_page, "limit": safe_limit}
    finally:
        db.close()
        
@app.get("/products/{shoper_id}/locations")
async def get_product_locations(shoper_id: int):
    """
    Returns a list of warehouse locations for a given Shoper product ID.
    Each location is parsed into carton, row, and position.
    """
    db = SessionLocal()
    try:
        # Find all scans linked to this shoper_id
        scans = db.query(Scan).filter(Scan.published_shoper_id == shoper_id).all()
        
        locations = []
        for scan in scans:
            if scan.warehouse_code:
                # Handle multiple codes separated by semicolons (if applicable)
                for code in scan.warehouse_code.split(';'):
                    parsed_location = parse_warehouse_code(code.strip())
                    if parsed_location:
                        locations.append({
                            "code": code.strip(),
                            "karton": parsed_location["karton"],
                            "row": parsed_location["row"],
                            "position": parsed_location["position"]
                        })
        
        return locations
    finally:
        db.close()
        
@app.patch("/products/{product_id}/purchase_price")
async def update_purchase_price(product_id: int, body: dict = Body(...)):
    """
    Updates the purchase price for a product in the local database.
    Body: {"purchase_price": 12.50}
    """
    db = SessionLocal()
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            return JSONResponse({"error": "Product not found"}, status_code=404)
        
        try:
            new_price = float(body.get("purchase_price", 0))
        except (ValueError, TypeError):
            return JSONResponse({"error": "Invalid purchase_price value"}, status_code=400)
        
        product.purchase_price = new_price
        db.commit()
        
        return {"success": True, "product_id": product_id, "purchase_price": new_price}
    finally:
        db.close()


@app.put("/products/{shoper_id}")
async def update_product(shoper_id: int, product_update: ProductUpdateRequest):
    if not settings.shoper_base_url or not settings.shoper_access_token:
        return JSONResponse(
            {"error": "Configure SHOPER_BASE_URL and SHOPER_ACCESS_TOKEN"},
            status_code=400,
        )

    
    client = ShoperClient(settings.shoper_base_url, settings.shoper_access_token)
    
    # Convert Pydantic model to a dictionary, excluding unset values
    updates = product_update.dict(exclude_unset=True)

    result = await client.update_product(shoper_id, updates)

    if result.get("ok"):
        # Optionally, update the local database if needed
        db = SessionLocal()
        try:
            product_in_db = db.query(Product).filter(Product.shoper_id == shoper_id).first()
            if product_in_db:
                for field, value in updates.items():
                    # Map schema fields to DB model fields if necessary
                    if field == "name":
                        product_in_db.name = value
                    elif field == "code":
                        product_in_db.code = value
                    elif field == "price":
                        product_in_db.price = value
                    elif field == "stock":
                        product_in_db.stock = value
                    elif field == "category_id":
                        product_in_db.category_id = value
                product_in_db.updated_at = datetime.utcnow()
                db.commit()
        finally:
            db.close()
        
        return {"status": "ok", "shoper_id": shoper_id, "updated_fields": updates}
    else:
        return JSONResponse(
            {"error": "Failed to update product in Shoper", "details": result},
            status_code=result.get("status_code", 500),
        )
        
        
        @app.post("/scans/{scan_id}/create_product")
        async def create_product_in_shoper(scan_id: int, request: CreateProductRequest):
            if not settings.shoper_base_url or not settings.shoper_access_token:
                return JSONResponse(
                    {"error": "Configure SHOPER_BASE_URL and SHOPER_ACCESS_TOKEN"},
                    status_code=400,
                )

    db = SessionLocal()
    try:
        scan = db.get(Scan, scan_id)
        if not scan:
            return JSONResponse({"error": "Scan not found"}, status_code=404)

        candidate = None
        # If candidate not selected yet, try request.candidate_id or best-scored
        if not scan.selected_candidate_id:
            if request.candidate_id:
                candidate = (
                    db.query(ScanCandidate)
                    .filter(ScanCandidate.scan_id == scan.id, ScanCandidate.provider_id == request.candidate_id)
                    .first()
                )
                if candidate:
                    db.query(ScanCandidate).filter(ScanCandidate.scan_id == scan.id).update({ScanCandidate.chosen: False})
                    candidate.chosen = True
                    scan.selected_candidate_id = candidate.id
                    db.commit()
            if not candidate:
                # pick best score
                best = (
                    db.query(ScanCandidate)
                    .filter(ScanCandidate.scan_id == scan.id)
                    .order_by(ScanCandidate.score.desc())
                    .first()
                )
                if best:
                    db.query(ScanCandidate).filter(ScanCandidate.scan_id == scan.id).update({ScanCandidate.chosen: False})
                    best.chosen = True
                    scan.selected_candidate_id = best.id
                    db.commit()
                    candidate = best
        else:
            candidate = db.get(ScanCandidate, scan.selected_candidate_id)

        # Candidate may be None — we can still create a generic product from detected fields

        # Build attributes: use provided, otherwise try to auto-map from detected using Shopera taxonomy
        attributes_payload = request.attributes or {}
        if not attributes_payload:
            try:
                client = ShoperClient(settings.shoper_base_url, settings.shoper_access_token)
                tax = await client.fetch_attributes()
                items = tax.get("items") if isinstance(tax, dict) else []
                # Fallback to ids_dump.json when API yields nothing
                if not items:
                    try:
                        import json
                        from pathlib import Path
                        for p in [
                            Path(__file__).parent.parent.parent / "ids_dump.json",
                            Path(__file__).parent.parent / "ids_dump.json",
                            Path.cwd() / "ids_dump.json",
                        ]:
                            if p.exists():
                                data = json.loads(p.read_text(encoding="utf-8"))
                                items = data.get("attributes") or []
                                if items:
                                    break
                    except Exception:
                        items = []
                detected = {
                    "language": scan.detected_language,
                    "variant": scan.detected_variant,
                    "condition": scan.detected_condition,
                    "rarity": scan.detected_rarity,
                    "energy": scan.detected_energy,
                }
                attributes_payload = map_detected_to_shoper_attributes(detected, items)
            except Exception:
                attributes_payload = {}

        # Build product payload WITH attributes for atomic creation
        client = ShoperClient(settings.shoper_base_url, settings.shoper_access_token)
        # NEW FLOW: Upload image first to get gfx_id, then create product.
        gfx_id = None
        if scan.stored_path:
            try:
                gfx_id = await client.upload_gfx(scan.stored_path)
            except Exception:
                gfx_id = None # Proceed without image if upload fails

        payload = await build_shoper_payload(client, scan, candidate, gfx_id=gfx_id)
        # Apply overrides: category and price
        if request.category_id is not None:
            try:
                payload["category_id"] = int(request.category_id)
                payload["categories"] = [int(request.category_id)]
            except Exception:
                pass
        elif request.category_name:
            # Try find or create category by name
            try:
                client_lookup = ShoperClient(settings.shoper_base_url, settings.shoper_access_token)
                cats = await client_lookup.fetch_categories()
                items = cats.get('items') if isinstance(cats, dict) else (cats if isinstance(cats, list) else [])
                found_id = None
                for it in items or []:
                    try:
                        nm = (it.get('name') or it.get('category') or '').strip().lower()
                        cid = it.get('category_id') or it.get('id')
                        if nm and nm == str(request.category_name).strip().lower() and cid is not None:
                            found_id = int(cid)
                            break
                    except Exception:
                        continue
                if not found_id and request.create_category_if_missing:
                    found_id = await client_lookup.create_category(str(request.category_name).strip())
                if found_id:
                    payload['category_id'] = int(found_id)
                    payload['categories'] = [int(found_id)]
            except Exception:
                pass
        if request.price_pln_final is not None:
            try:
                price_text = f"{float(request.price_pln_final):.2f}"
                if isinstance(payload.get("stock"), dict):
                    payload["stock"]["price"] = price_text
                else:
                    payload.setdefault("stock", {})
                    payload["stock"]["price"] = price_text
            except Exception:
                pass
        if request.name_override:
            try:
                lang = settings.default_language_code
                if isinstance(payload.get("translations"), dict) and lang in payload["translations"]:
                    payload["translations"][lang]["name"] = request.name_override.strip()
            except Exception:
                pass
        if request.number_override:
            try:
                number_txt = str(request.number_override).strip()
                # Update code and stock.code by replacing trailing segment
                code_old = payload.get("code") or ""
                import re
                if code_old:
                    m = re.match(r"^(.*-)([^-]*)$", code_old)
                    if m:
                        code_new = f"{m.group(1)}{number_txt}"
                    else:
                        code_new = f"{code_old}-{number_txt}"
                    payload["code"] = code_new
                    if isinstance(payload.get("stock"), dict):
                        payload["stock"]["code"] = code_new
                # Also update display name to reflect new number
                lang = settings.default_language_code
                if isinstance(payload.get("translations"), dict) and lang in payload["translations"]:
                    base_name = (payload["translations"][lang].get("name") or "").strip()
                    # Rebuild name from scan/candidate sources for correctness
                    nm = candidate.name or scan.detected_name or "Karta"
                    st = candidate.set or scan.detected_set or ""
                    payload["translations"][lang]["name"] = f"{nm} {number_txt} {st}".strip()
            except Exception:
                pass

        # Recompute set code in product code, preferring the actual set over era/category
        try:
            from .shoper import _category_name_from_id, _set_code_from_name as _setcode
            preferred_set_name = (scan.detected_set or (candidate.set if candidate else None))
            set_code = _setcode(preferred_set_name) if preferred_set_name else None
            if not set_code:
                cat_id = payload.get("category_id")
                if cat_id:
                    client_for_cat = ShoperClient(settings.shoper_base_url, settings.shoper_access_token)
                    cat_name = await _category_name_from_id(client_for_cat, int(cat_id))
                    if cat_name:
                        set_code = _setcode(cat_name)
            if set_code:
                # Update PKM-SETCODE-NUMBER if set_code resolvable
                num_part = None
                try:
                    cur = payload.get("code") or ""
                    import re
                    m = re.match(r"^([A-Z]+)-([A-Z0-9]+)-(.+)$", cur)
                    if m:
                        num_part = m.group(3)
                except Exception:
                    num_part = None
                new_code = f"{settings.code_prefix}-{set_code}-{num_part or (scan.detected_number or (candidate.number if candidate else ''))}".strip("-")
                payload["code"] = new_code
                if isinstance(payload.get("stock"), dict):
                    payload["stock"]["code"] = new_code
        except Exception:
            pass

        # Create product in Shoper
        headers = {
            "Authorization": f"Bearer {client.token}",
            "Accept": "application/json",
        }
        url = f"{client.base_url}{settings.shoper_products_path}"
        async with httpx.AsyncClient(timeout=30) as http:
            r = await http.post(url, json=payload, headers=headers)
            try:
                r.raise_for_status()
                # Mark scan as published
                scan.publish_status = "published"
                uploads = []
                attr_results = []
                try:
                    resp_json = r.json()
                    sid = int(resp_json.get("product_id") or resp_json.get("id") or 0)
                    scan.published_shoper_id = sid or None

                    # STEP 2: If product was created and there are attributes, add them via PUT
                    if sid and attributes_payload:
                        print(f"INFO: Adding attributes to product {sid} via PUT request")
                        update_result = await client.update_product(sid, {"attributes": attributes_payload})
                        if update_result.get("ok"):
                            print(f"SUCCESS: Attributes successfully added to product {sid}")
                            attr_results.append(update_result)
                        else:
                            print(f"WARNING: Failed to add attributes to product {sid}: {update_result.get('text', 'Unknown error')}")

                except Exception as e:
                    print(f"ERROR processing product creation response or updating attributes: {e}")
                    pass
                db.commit()
                # Images are handled by a separate endpoint after this.
                return {"ok": True, "json": r.json(), "payload": payload, "uploads": uploads, "attributes_applied": attr_results}
            except Exception:
                return {
                    "error": True,
                    "status_code": r.status_code,
                    "text": r.text,
                    "payload": payload,
                }
    finally:
        db.close()


@app.post("/shoper/map_attributes")
async def map_attributes_endpoint(scan_id: int | None = None, detected: dict | None = Body(default=None)):
    """Return suggested { attribute_id: option_id } based on detected data and Shoper taxonomy.

    Accepts either a scan_id (loads detected_* from DB) or a 'detected' dict body
    with keys like language, variant/finish, condition, rarity, energy.
    
    Returns option IDs (not text) for frontend form population.
    """
    if not settings.shoper_base_url or not settings.shoper_access_token:
        return JSONResponse({"error": "Configure SHOPER_BASE_URL and SHOPER_ACCESS_TOKEN"}, status_code=400)
    src = detected or {}
    if scan_id is not None and not detected:
        db = SessionLocal()
        try:
            s = db.get(Scan, int(scan_id))
            if not s:
                return JSONResponse({"error": "scan not found"}, status_code=404)
            src = {
                "language": s.detected_language,
                "variant": s.detected_variant,
                "condition": s.detected_condition,
                "rarity": s.detected_rarity,
                "energy": s.detected_energy,
            }
        finally:
            db.close()
    client = ShoperClient(settings.shoper_base_url, settings.shoper_access_token)
    tax = await client.fetch_attributes()
    items = tax.get("items") if isinstance(tax, dict) else []
    # Use map_detected_to_form_ids for numeric option IDs (for frontend)
    from .attributes import map_detected_to_form_ids
    out = map_detected_to_form_ids(src or {}, items)
    return {"attributes": out}


@app.get("/shoper/map_set_symbol")
async def map_set_symbol_endpoint(symbol: str = Query(..., description="Set symbol (ptcgoCode) like TWM, PAL, OBF")):
    """Map a set symbol (ptcgoCode) to Shoper category_id.
    
    Example: GET /shoper/map_set_symbol?symbol=TWM returns {"symbol": "TWM", "category_id": "49"}
    """
    from .set_mapping import get_category_id_for_set_symbol
    
    category_id = get_category_id_for_set_symbol(symbol)
    if category_id:
        return {"symbol": symbol.upper(), "category_id": category_id}
    else:
        return JSONResponse(
            {"error": f"No category mapping found for set symbol: {symbol}"},
            status_code=404
        )


@app.get("/scans/{scan_id}", response_model=ScanDetailResponse)
async def scan_detail(scan_id: int):
    db = SessionLocal()
    try:
        s = db.get(Scan, scan_id)
        if not s:
            return JSONResponse({"error": "scan not found"}, status_code=404)
        # Fetch all candidates
        cands = db.query(ScanCandidate).filter(ScanCandidate.scan_id == s.id).order_by(ScanCandidate.score.desc()).all()
        candidates: list[Candidate] = []
        selected_provider_id: str | None = None
        for c in cands:
            candidates.append(
                Candidate(
                    id=c.provider_id,
                    name=c.name,
                    set=c.set,
                    set_code=c.set_code,
                    number=c.number,
                    image=c.image,
                    score=c.score,
                )
            )
        
        # Build detected data with enriched information
        # First try to load from detected_payload (includes Shoper attributes)
        detected_data = {}
        if s.detected_payload:
            try:
                detected_data = json.loads(s.detected_payload)
            except Exception:
                pass
        
        # Fallback to individual fields if payload is not available
        if not detected_data:
            detected_data = {
                "name": s.detected_name,
                "set": s.detected_set,
                "set_code": s.detected_set_code,
                "number": s.detected_number,
                "language": s.detected_language,
                "variant": s.detected_variant,
                "condition": s.detected_condition,
                "rarity": s.detected_rarity,
                "energy": s.detected_energy,
                "warehouse_code": s.warehouse_code,
            }
        
        # If scan has catalog_id, enrich with variants and mapped attributes
        if s.catalog_id:
            try:
                catalog_entry = db.get(CardCatalog, s.catalog_id)
                if catalog_entry:
                    # Calculate all price variants
                    variants = []
                    for finish_type in ["normal", "holo", "reverse"]:
                        price_info = _calculate_price_from_catalog(catalog_entry, finish_type)
                        if price_info.get("price_pln_final"):
                            variants.append({
                                "label": finish_type.replace("normal", "Normal").replace("holo", "Holo").replace("reverse", "Reverse Holo"),
                                "finish": finish_type,
                                "base_eur": price_info.get("base_eur"),
                                "price_pln": price_info.get("price_pln"),
                                "price_pln_final": price_info.get("price_pln_final"),
                                "estimated": price_info.get("estimated", False),
                            })
                    detected_data["variants"] = variants
                    
                    # Set default price if not already set
                    if not s.price_pln_final and variants:
                        detected_data["price_pln_final"] = variants[0]["price_pln_final"]
                    else:
                        detected_data["price_pln_final"] = s.price_pln_final
                    
                    # Try to match set to Shoper category
                    try:
                        matched_category = await _match_shoper_category(catalog_entry.set_name)
                        if matched_category:
                            detected_data["set_id"] = matched_category.get("set_id")
                    except Exception:
                        pass
                    
                    # Map attributes to Shoper option IDs
                    try:
                        if settings.shoper_base_url and settings.shoper_access_token:
                            from .attributes import map_detected_to_form_ids
                            client = ShoperClient(settings.shoper_base_url, settings.shoper_access_token)
                            tax = await client.fetch_attributes()
                            items = tax.get("items") if isinstance(tax, dict) else []
                            if items:
                                detected_attrs = {
                                    "rarity": s.detected_rarity or catalog_entry.rarity,
                                    "energy": s.detected_energy or catalog_entry.energy,
                                    "language": s.detected_language,
                                    "variant": s.detected_variant,
                                    "condition": s.detected_condition,
                                }
                                mapped_attributes = map_detected_to_form_ids(detected_attrs, items)
                                detected_data.update(mapped_attributes)
                                
                                # Set defaults if not mapped
                                if not detected_data.get('64'):  # Language
                                    detected_data['64'] = '142'  # English
                                if not detected_data.get('66'):  # Quality/Condition
                                    detected_data['66'] = '176'  # Near Mint
                                if not detected_data.get('65'):  # Finish
                                    detected_data['65'] = '184'  # Normal
                    except Exception as e:
                        print(f"WARNING: Failed to map attributes in scan_detail: {e}")
            except Exception as e:
                print(f"WARNING: Failed to enrich scan with catalog data: {e}")
        else:
            # No catalog, use basic price from scan
            detected_data["price_pln_final"] = s.price_pln_final
        
        return ScanDetailResponse(
            id=s.id,
            created_at=s.created_at.isoformat(),
            message=s.message,
            detected=DetectedData(**detected_data),
            candidates=candidates,
            selected_candidate_id=s.selected_candidate_id,
            pricing={
                "cardmarket_currency": s.cardmarket_currency,
                "cardmarket_7d_average": s.cardmarket_7d_average,
                "price_pln": s.price_pln,
                "price_pln_final": s.price_pln_final,
                "graded_psa10": s.graded_psa10,
                "graded_currency": s.graded_currency,
            } if s.cardmarket_currency else None,
            image_url=f"/uploads/{s.filename}" if s.filename else None,
            back_image_url=f"/uploads/{Path(s.stored_path_back).name}" if s.stored_path_back else None,
            warehouse_code=s.warehouse_code,
        )
    finally:
        db.close()


@app.post("/sync/shoper")
async def sync_shoper(limit: int = 100):
    if not settings.shoper_base_url or not settings.shoper_access_token:
        return JSONResponse({"error": "Configure SHOPER_BASE_URL and SHOPER_ACCESS_TOKEN"}, status_code=400)
    client = ShoperClient(settings.shoper_base_url, settings.shoper_access_token)
    items = await client.fetch_all_products(limit=limit)
    res = upsert_products(items)
    # Update last sync marker
    import time as _t
    global _last_products_sync_ts
    _last_products_sync_ts = _t.time()
    return {"status": "ok", "fetched": len(items), **res}


@app.get("/scans/{scan_id}/duplicates")
def find_duplicates(scan_id: int, limit: int = 5):
    db = SessionLocal()
    try:
        src = db.query(Fingerprint).filter(Fingerprint.scan_id == scan_id).first()
        if not src:
            return []
        src_phash = unpack_ndarray(src.phash)
        src_dhash = unpack_ndarray(src.dhash)
        src_tile = unpack_ndarray(src.tile_phash)
        rows = db.query(Fingerprint).filter(Fingerprint.scan_id != scan_id).all()
        scored = []
        for r in rows:
            try:
                ph = unpack_ndarray(r.phash)
                dh = unpack_ndarray(r.dhash)
                tl = unpack_ndarray(r.tile_phash)
            except Exception:
                continue
            score = 0
            score += hamming_distance(src_phash, ph)
            score += hamming_distance(src_dhash, dh)
            # sum tile distances (zip shape)
            try:
                for a, b in zip(src_tile, tl):
                    score += hamming_distance(a, b)
            except Exception:
                score += 999
            scored.append({"scan_id": r.scan_id, "distance": score})
        scored.sort(key=lambda x: x["distance"])
        return scored[: max(1, min(limit, 20))]
    finally:
        db.close()


@app.post("/sessions/start")
def start_session():
    db = SessionLocal()
    try:
        s = ScanSession(status="open")
        db.add(s)
        db.flush()
        db.commit()
        return {"session_id": s.id}
    finally:
        db.close()


@app.get("/sessions/{session_id}/summary")
def session_summary(session_id: int):
    db = SessionLocal()
    try:
        scans = db.query(Scan).filter(Scan.session_id == session_id).all()
        total = len(scans)
        ready = sum(1 for s in scans if s.selected_candidate_id)
        sum_price = sum((s.price_pln_final or 0.0) for s in scans if s.selected_candidate_id)
        return {"session_id": session_id, "total_scans": total, "ready_to_publish": ready, "sum_price_pln_final": round(sum_price, 2)}
    finally:
        db.close()


from fastapi import Form, Request

@app.post("/scans/{scan_id}/publish")
async def publish_single_scan(
    request: Request,
    scan_id: int,
    data: str = Form(...),
):
    print(f"DEBUG: publish_single_scan called with scan_id={scan_id}")
    print(f"DEBUG: data parameter received: {data[:100] if data else 'NONE'}")
    
    db = SessionLocal()
    temp_dir = None
    try:
        # 1. Parse form data and confirm candidate
        form_data = json.loads(data)
        payload = ConfirmRequest(**form_data)
        print(f"DEBUG: Parsed form_data: {form_data}")
        
        confirm_response = await confirm_candidate(payload)
        if isinstance(confirm_response, JSONResponse):
            return confirm_response

        # 2. Get scan and candidate from DB
        scan = db.get(Scan, scan_id)
        if not scan or not scan.selected_candidate_id:
            return JSONResponse({"error": "Scan not confirmed or candidate not selected"}, status_code=400)
        cand = db.get(ScanCandidate, scan.selected_candidate_id)
        if not cand:
            return JSONResponse({"error": "Candidate not found"}, status_code=404)

        # 2.5. Assign warehouse code if not already assigned
        # This is the definitive moment when the warehouse code is committed
        if not scan.warehouse_code:
            # Try to get code from form data (user might have edited it)
            proposed_code = form_data.get('warehouse_code')
            starting_code = None
            
            if proposed_code:
                # Validate proposed code
                parsed = parse_warehouse_code(proposed_code)
                if parsed:
                    starting_code = proposed_code
            
            # If no valid code from form, try to get from session
            if not starting_code and scan.session_id:
                session = db.get(Session, scan.session_id)
                if session and session.starting_warehouse_code:
                    starting_code = session.starting_warehouse_code
            
            # Assign the next available code
            try:
                scan.warehouse_code = get_next_free_location(db, starting_code=starting_code)
                print(f"INFO: Assigned warehouse code {scan.warehouse_code} to scan {scan_id}")
            except NoFreeLocationError:
                return JSONResponse({"error": "No free storage locations available"}, status_code=503)

        # 3. Handle image uploads
        form = await request.form()
        primary_image_source = form.get("primary_image_source")
        
        primary_image_path_or_url = None
        additional_image_paths = []
        
        upload_dir = Path(settings.upload_dir)
        temp_dir = upload_dir / f"temp_{scan_id}_{int(time.time())}"
        temp_dir.mkdir(parents=True, exist_ok=True)

        if primary_image_source == 'upload':
            primary_image_file = form.get("primary_image")
            if isinstance(primary_image_file, UploadFile):
                path = temp_dir / primary_image_file.filename
                with open(path, "wb") as buffer:
                    shutil.copyfileobj(primary_image_file.file, buffer)
                primary_image_path_or_url = path
        elif primary_image_source == 'tcggo':
            primary_image_path_or_url = form.get("primary_image_url")
        elif primary_image_source == 'scan':
            # Use the stored scan path from database instead of blob URL
            if scan.stored_path and Path(scan.stored_path).is_file():
                primary_image_path_or_url = scan.stored_path
                print(f"DEBUG: Using scan.stored_path for primary image: {scan.stored_path}")
            else:
                print(f"WARNING: Scan stored_path not found or invalid: {scan.stored_path}")

        # Process additional images
        for key in form.keys():
            if key.startswith("additional_image_"):
                img_file = form.get(key)
                if isinstance(img_file, UploadFile):
                    path = temp_dir / img_file.filename
                    with open(path, "wb") as buffer:
                        shutil.copyfileobj(img_file.file, buffer)
                    additional_image_paths.append(path)

        # 4. Fuzzy match set name for category
        set_id = payload.detected.get('set_id') if payload.detected else None
        # Convert set_id to int if it's a string
        if set_id is not None:
            try:
                set_id = int(set_id)
            except (ValueError, TypeError):
                set_id = None
        if not set_id:
            set_name = payload.detected.get('set') if payload.detected else None
            print(f"DEBUG: set_id not found in payload. Attempting to match by set_name: '{set_name}'")
            if set_name:
                match = await _find_best_category_match_internal(set_name)
                if match and match.get('id'):
                    set_id = match.get('id')
                    print(f"DEBUG: Matched set_name '{set_name}' to category_id (set_id): {set_id}")
                else:
                    print(f"DEBUG: No category match found for set_name: '{set_name}'")

        # 5. Fetch related products from same category (set)
        client = ShoperClient(settings.shoper_base_url, settings.shoper_access_token)
        related_product_ids = []
        print(f"DEBUG: Final set_id before fetching related products: {set_id}")
        if set_id:
            related_product_ids = await _get_related_products_from_category(client, set_id, limit=10)
        
        # 6. Publish to Shoper with images and related products
        print(f"INFO: Publishing scan {scan_id} to Shoper...")
        result = await publish_scan_to_shoper(
            client,
            scan,
            cand,
            set_id=set_id,
            primary_image=primary_image_path_or_url,
            additional_images=additional_image_paths,
            related_ids=related_product_ids if related_product_ids else None
        )

        print(f"INFO: Shoper publish result: {json.dumps(result, indent=2, default=str)}")

        # 6. Update scan status in DB
        if result.get("ok") or result.get("dry_run"):
            scan.publish_status = "published" if not settings.publish_dry_run else "dry_run"
            shoper_id = None
            try:
                resp = result.get("json") or {}
                shoper_id = int(resp.get("product_id") or resp.get("id") or 0)
                if shoper_id:
                    scan.published_shoper_id = shoper_id
                    print(f"SUCCESS: Product published to Shoper with ID: {shoper_id}")
                    
                    # Update local Product with purchase_price from scan
                    if scan.purchase_price is not None and scan.purchase_price > 0:
                        product = db.query(Product).filter(Product.shoper_id == shoper_id).first()
                        if product:
                            product.purchase_price = scan.purchase_price
                            print(f"INFO: Updated Product {shoper_id} with purchase_price={scan.purchase_price}")
                        else:
                            # Create local Product record if not exists
                            new_product = Product(
                                shoper_id=shoper_id,
                                purchase_price=scan.purchase_price,
                                code=scan.warehouse_code,
                                name=scan.detected_name,
                                price=scan.price_pln_final,
                                stock=1,
                                updated_at=datetime.utcnow()
                            )
                            db.add(new_product)
                            db.flush()
                            print(f"INFO: Created local Product {shoper_id} with purchase_price={scan.purchase_price}")
            except Exception as e:
                print(f"WARNING: Could not extract product ID from response: {e}")
            # Attribute mapping logic can remain here or be moved if needed
        else:
            # Extract error details for better error message
            error_msg = "Publication failed"
            if result.get("error"):
                status_code = result.get("status_code", "unknown")
                error_text = result.get("text", "No error details")
                try:
                    # Try to parse error_text as JSON for cleaner display
                    error_json = json.loads(error_text)
                    error_desc = error_json.get("error_description", error_text)
                except:
                    error_desc = error_text
                error_msg = f"Publication failed (HTTP {status_code}): {error_desc}"
            print(f"ERROR: {error_msg}")
            scan.publish_status = "failed"
        db.commit()
        return result

    finally:
        if temp_dir and temp_dir.exists():
            shutil.rmtree(temp_dir)
        db.close()


@app.post("/sessions/{session_id}/publish")
async def publish_session(session_id: int):
    if not settings.shoper_base_url or not settings.shoper_access_token:
        return JSONResponse({"error": "Configure SHOPER_BASE_URL and SHOPER_ACCESS_TOKEN"}, status_code=400)
    client = ShoperClient(settings.shoper_base_url, settings.shoper_access_token)
    db = SessionLocal()
    published = 0
    failed = 0
    try:
        scans = db.query(Scan).filter(Scan.session_id == session_id, Scan.selected_candidate_id.isnot(None)).all()
        for s in scans:
            cand = db.get(ScanCandidate, s.selected_candidate_id)
            if not cand:
                continue

            # Determine primary image source (default to TCGGO if not set)
            primary_image = None
            use_tcggo = s.use_tcggo_image if s.use_tcggo_image is not None else True
            if use_tcggo:
                # Use TCGGO image (from candidate) - will be downloaded automatically
                primary_image = None  # Function will use candidate.image
            else:
                # Use local scan image
                if s.stored_path and Path(s.stored_path).is_file():
                    primary_image = s.stored_path

            # Parse additional images from JSON
            additional_images = None
            if s.additional_images:
                try:
                    import json
                    additional_paths = json.loads(s.additional_images)
                    if isinstance(additional_paths, list):
                        # Filter to existing files
                        additional_images = [p for p in additional_paths if Path(p).is_file()]
                except Exception:
                    pass

            r = await publish_scan_to_shoper(client, s, cand, primary_image=primary_image, additional_images=additional_images)
            if r.get("ok") or r.get("dry_run"):
                s.publish_status = "published" if not settings.publish_dry_run else "dry_run"
                # record id if possible
                try:
                    resp = r.get("json") or {}
                    sid = int(resp.get("product_id") or resp.get("id") or 0)
                    s.published_shoper_id = sid or None
                    
                    # Update local Product with purchase_price from scan
                    if sid and s.purchase_price is not None and s.purchase_price > 0:
                        product = db.query(Product).filter(Product.shoper_id == sid).first()
                        if product:
                            product.purchase_price = s.purchase_price
                            print(f"INFO: Updated Product {sid} with purchase_price={s.purchase_price}")
                        else:
                            # Create local Product record if not exists
                            new_product = Product(
                                shoper_id=sid,
                                purchase_price=s.purchase_price,
                                code=s.warehouse_code,
                                name=s.detected_name,
                                price=s.price_pln_final,
                                stock=1,
                                updated_at=datetime.utcnow()
                            )
                            db.add(new_product)
                            db.flush()
                            print(f"INFO: Created local Product {sid} with purchase_price={s.purchase_price}")
                except Exception as e:
                    print(f"WARNING: Could not update product purchase_price: {e}")
                published += 1
            else:
                s.publish_status = "failed"
                failed += 1
        db.commit()
        return {"session_id": session_id, "published": published, "failed": failed, "dry_run": settings.publish_dry_run}
    finally:
        db.close()


@app.get("/scans/{scan_id}/duplicates")
def find_duplicates(scan_id: int, limit: int = 5):
    db = SessionLocal()
    try:
        src = db.query(Fingerprint).filter(Fingerprint.scan_id == scan_id).first()
        if not src:
            return []
        src_phash = unpack_ndarray(src.phash)
        src_dhash = unpack_ndarray(src.dhash)
        src_tile = unpack_ndarray(src.tile_phash)
        rows = db.query(Fingerprint).filter(Fingerprint.scan_id != scan_id).all()
        scored = []
        for r in rows:
            try:
                ph = unpack_ndarray(r.phash)
                dh = unpack_ndarray(r.dhash)
                tl = unpack_ndarray(r.tile_phash)
            except Exception:
                continue
            score = 0
            score += hamming_distance(src_phash, ph)
            score += hamming_distance(src_dhash, dh)
            try:
                for a, b in zip(src_tile, tl):
                    score += hamming_distance(a, b)
            except Exception:
                score += 999
            scored.append({"scan_id": r.scan_id, "distance": score})
        scored.sort(key=lambda x: x["distance"])
        return scored[: max(1, min(limit, 20))]
    finally:
        db.close()


@app.patch("/scans/{scan_id}/image-settings")
async def update_scan_image_settings(scan_id: int, use_tcggo_image: bool | None = None, additional_images: list[str] | None = None):
    """Update image source preference and additional images for a scan."""
    db = SessionLocal()
    try:
        scan = db.get(Scan, scan_id)
        if not scan:
            return JSONResponse({"error": "Scan not found"}, status_code=404)

        if use_tcggo_image is not None:
            scan.use_tcggo_image = use_tcggo_image

        if additional_images is not None:
            import json
            # Validate paths exist
            valid_paths = [p for p in additional_images if Path(p).is_file()]
            scan.additional_images = json.dumps(valid_paths) if valid_paths else None

        db.commit()
        return {
            "scan_id": scan_id,
            "use_tcggo_image": scan.use_tcggo_image,
            "additional_images": json.loads(scan.additional_images) if scan.additional_images else []
        }
    finally:
        db.close()


@app.post("/scans/{scan_id}/upload-additional-image")
async def upload_additional_image(scan_id: int, file: UploadFile = File(...)):
    """Upload an additional image for a scan (e.g., back, detail shots)."""
    db = SessionLocal()
    try:
        scan = db.get(Scan, scan_id)
        if not scan:
            return JSONResponse({"error": "Scan not found"}, status_code=404)

        # Save uploaded file
        upload_dir = Path(settings.upload_dir)
        upload_dir.mkdir(parents=True, exist_ok=True)

        ext = Path(file.filename).suffix if file.filename else ".jpg"
        filename = f"scan_{scan_id}_extra_{int(time.time()*1000)}{ext}"
        target = upload_dir / filename

        with target.open("wb") as out:
            shutil.copyfileobj(file.file, out)

        # Add to additional_images list
        import json
        current_images = []
        if scan.additional_images:
            try:
                current_images = json.loads(scan.additional_images)
            except Exception:
                pass

        current_images.append(str(target))
        scan.additional_images = json.dumps(current_images)
        db.commit()

        return {
            "scan_id": scan_id,
            "uploaded_path": str(target),
            "url": f"/uploads/{filename}",
            "all_additional_images": current_images
        }
    finally:
        db.close()


@app.patch("/scans/{scan_id}/warehouse-code")
async def update_scan_warehouse_code(scan_id: int, warehouse_code: str = Body(..., embed=True)):
    """Set warehouse code for a scan (e.g., K1K1P001)."""
    db = SessionLocal()
    try:
        scan = db.get(Scan, scan_id)
        if not scan:
            return JSONResponse({"error": "Scan not found"}, status_code=404)

        # Validate code format
        parsed = parse_warehouse_code(warehouse_code)
        if not parsed:
            return JSONResponse({
                "error": "Invalid warehouse code format. Expected: K{1-9}K{1-4}P{001-1000}",
                "example": "K1K1P001"
            }, status_code=400)

        scan.warehouse_code = warehouse_code.upper()
        db.commit()

        return {
            "scan_id": scan_id,
            "warehouse_code": scan.warehouse_code,
            "parsed": parsed
        }
    finally:
        db.close()


@app.get("/warehouse/last-code")
async def get_last_warehouse_code():
    """Get the most recently used warehouse code from all scans."""
    db = SessionLocal()
    try:
        # Find most recent scan with warehouse_code set
        scan = db.query(Scan).filter(
            Scan.warehouse_code.isnot(None),
            Scan.warehouse_code != ""
        ).order_by(Scan.created_at.desc()).first()

        if not scan or not scan.warehouse_code:
            return {"last_code": None, "next_code": "K1K1P001"}

        next_code = increment_warehouse_code(scan.warehouse_code)
        return {
            "last_code": scan.warehouse_code,
            "next_code": next_code,
            "scan_id": scan.id,
            "created_at": scan.created_at.isoformat() if scan.created_at else None
        }
    finally:
        db.close()


@app.post("/warehouse/increment")
async def increment_code(current_code: str = Body(..., embed=True)):
    """Calculate next warehouse code from current code.

    Example: K1K1P001 -> K1K1P002
    """
    next_code = increment_warehouse_code(current_code)
    if not next_code:
        return JSONResponse({
            "error": "Cannot increment code (end of warehouse or invalid format)",
            "current_code": current_code
        }, status_code=400)

    parsed_current = parse_warehouse_code(current_code)
    parsed_next = parse_warehouse_code(next_code)

    return {
        "current_code": current_code,
        "next_code": next_code,
        "current": parsed_current,
        "next": parsed_next
    }


@app.get("/warehouse/validate/{code}")
async def validate_warehouse_code(code: str):
    """Validate warehouse code format and return parsed components."""
    parsed = parse_warehouse_code(code)
    if not parsed:
        return JSONResponse({
            "valid": False,
            "error": "Invalid format. Expected: K{1-9}K{1-4}P{001-1000}",
            "example": "K1K1P001"
        }, status_code=400)

    return {
        "valid": True,
        "code": code.upper(),
        "karton": parsed["karton"],
        "kolumna": parsed["kolumna"],
        "pozycja": parsed["pozycja"],
        "formatted": format_warehouse_code(parsed["karton"], parsed["kolumna"], parsed["pozycja"])
    }


@app.get("/debug/shoper-product/{product_id}")
async def debug_get_shoper_product(product_id: int):
    """Debug endpoint to fetch and inspect a product structure from Shoper."""
    if not settings.shoper_base_url or not settings.shoper_access_token:
        return JSONResponse({"error": "Configure SHOPER_BASE_URL and SHOPER_ACCESS_TOKEN"}, status_code=400)

    client = ShoperClient(settings.shoper_base_url, settings.shoper_access_token)
    product = await client.get_product(product_id)

    if product:
        return {"product_id": product_id, "data": product}
    else:
        return JSONResponse({"error": f"Product {product_id} not found"}, status_code=404)


@app.get("/sessions/{session_id}/publish/preview")
def publish_preview(session_id: int):
    db = SessionLocal()
    try:
        scans = db.query(Scan).filter(Scan.session_id == session_id, Scan.selected_candidate_id.isnot(None)).all()
        payloads: list[dict] = []
        for s in scans:
            cand = db.get(ScanCandidate, s.selected_candidate_id)
            if not cand:
                continue
            payload = build_shoper_payload(s, cand)
            payloads.append({"scan_id": s.id, "payload": payload})
        return {"session_id": session_id, "count": len(payloads), "payloads": payloads}
    finally:
        db.close()


@app.post("/import/inventory_csv")
async def import_inventory_csv(file: UploadFile = File(...)):
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    target = upload_dir / f"inventory_{int(time.time()*1000)}.csv"
    with target.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    from . import import_inventory
    result = import_inventory.run(str(target))
    return result

 


@app.get("/orders")
async def list_orders(
    limit: int = 20, 
    page: int | None = None, 
    detailed: bool = Query(default=False),
    auto_sync_furgonetka: bool = Query(default=True, description="Sync with Furgonetka in background")
):
    """Fetch orders with caching and pagination support.
    
    Args:
        limit: Number of orders per page (default: 20, max: 250)
        page: Page number (optional, defaults to fetch all)
        detailed: Include full order details (items, buyer info)
        auto_sync_furgonetka: Trigger background sync with Furgonetka
    
    Returns:
        List of normalized order objects
    """
    global _orders_cache, _orders_cache_ts
    
    if not settings.shoper_base_url or not settings.shoper_access_token:
        return []
    
    # Cache key based on parameters
    cache_key = f"orders_{limit}_{page}_{detailed}"
    now = time.time()
    
    # Different TTL for detailed vs simple requests
    # Detailed requests are slower so cache longer, but refresh more often to get new order details
    ttl = 120 if detailed else 300  # 2 min for detailed, 5 min for simple
    
    # Check cache for both detailed and simple requests
    if _orders_cache is not None and _orders_cache_ts is not None:
        if now - _orders_cache_ts < ttl and cache_key in _orders_cache:
            return _orders_cache[cache_key]
    
    client = ShoperClient(settings.shoper_base_url, settings.shoper_access_token)
    if page is not None:
        meta = await client.fetch_orders_page(page=max(1, int(page or 1)), limit=max(1, min(int(limit or 20), 250)))
        items = meta.get("items") or []
    else:
        # OPTIMIZED: Use fetch_recent_orders instead of fetch_all_orders
        # This fetches only ONE page, respecting the limit!
        items = await client.fetch_recent_orders(limit=max(1, min(int(limit or 20), 250)))
    # Normalize a compact shape for UI
    out = []
    # Optional product cache and DB session for enrichment
    prod_cache_by_code: dict[str, tuple[str|None, str|None, float|None]] = {}
    prod_cache_by_id: dict[int, tuple[str|None, str|None, float|None]] = {}
    db = SessionLocal() if detailed else None
    for o in items:
        oid = o.get("order_id") or o.get("id") or o.get("orderId")
        ts = o.get("date") or o.get("created_at") or o.get("add_date") or o.get("createdAt")
        total = (o.get("sum") or o.get("total_gross") or o.get("total") or o.get("amount") or 0)
        # prefer explicit total_products field when present
        items_count = o.get("total_products")
        if items_count is None:
            products = o.get("products") or o.get("items") or o.get("orders_products") or []
            if isinstance(products, dict):
                products = products.get("items") or products.get("list") or []
            try:
                items_count = sum(int(p.get("quantity") or p.get("qty") or p.get("count") or 0) for p in (products or []) if isinstance(p, dict))
            except Exception:
                items_count = None
        # Status info
        st = o.get("status") or {}
        st_name = None
        try:
            tr = st.get("translations")
            if isinstance(tr, dict):
                # Prefer configured language code
                lang = getattr(settings, "default_language_code", None) or "pl_PL"
                tr_lang = tr.get(lang)
                if isinstance(tr_lang, dict):
                    st_name = tr_lang.get("name")
                if not st_name:
                    # fallback: first entry
                    for _k, _v in tr.items():
                        if isinstance(_v, dict) and _v.get("name"):
                            st_name = _v.get("name")
                            break
        except Exception:
            pass
        st_type = (st.get("type") if isinstance(st, dict) else None) or o.get("status_type")
        st_id = (st.get("status_id") if isinstance(st, dict) else None) or o.get("status_id")
        st_color = (st.get("color") if isinstance(st, dict) else None)

        # Extract user info
        user_info = {}
        try:
            user = o.get("user")
            if isinstance(user, dict):
                user_info = {
                    "firstname": user.get("firstname"),
                    "lastname": user.get("lastname"),
                    "email": user.get("email") or o.get("email"),
                }
            elif o.get("email"):
                user_info = {"email": o.get("email")}
        except Exception:
            pass
        
        row = {
            "id": oid,
            "date": ts,
            "total": total,
            "items_count": items_count,
            "delivery_date": o.get("delivery_date"),
            "status": {"type": st_type, "id": st_id, "color": st_color, "name": st_name},
            "user": user_info,
        }
        if detailed:
            # Attach simplified items if present
            prods = (
                o.get("products")
                or o.get("orders_products")
                or o.get("order_products")
                or o.get("items")
                or []
            )
            if isinstance(prods, dict):
                prods = prods.get("items") or prods.get("list") or []
            # Fallback: fetch per-order products if empty
            if (not prods) and oid is not None:
                try:
                    prods = await client.fetch_order_products(oid)
                except Exception:
                    prods = []
            simp: list[dict] = []
            if isinstance(prods, list):
                def _emit(pobj: dict):
                    if not isinstance(pobj, dict):
                        return
                    name = pobj.get("name") or pobj.get("product_name") or pobj.get("title")
                    code = pobj.get("code") or pobj.get("sku") or pobj.get("product_code")
                    pid = pobj.get("product_id") or pobj.get("id")
                    qty = pobj.get("quantity") or pobj.get("qty") or pobj.get("count") or 0
                    price = pobj.get("price") or pobj.get("price_gross") or pobj.get("sum") or pobj.get("amount")
                    # concatenate options to name if present
                    try:
                        topts = pobj.get("text_options")
                        if isinstance(topts, list) and topts:
                            optstr = ", ".join([str(x.get("value")) for x in topts if isinstance(x, dict) and x.get("value")])
                            if optstr:
                                name = f"{name} ({optstr})"
                    except Exception:
                        pass
                    try:
                        qty = int(qty)
                    except Exception:
                        try:
                            qty = int(float(str(qty).replace(",", ".")))
                        except Exception:
                            qty = 0
                    try:
                        price = float(str(price).replace(",", ".")) if price is not None else None
                    except Exception:
                        price = None
                    # Enrich with image/permalink/purchase_price via local products when possible
                    image_url = None
                    permalink = None
                    purchase_price = None
                    try:
                        if code and code in prod_cache_by_code:
                            cached = prod_cache_by_code.get(code)
                            if cached and len(cached) == 3:
                                image_url, permalink, purchase_price = cached
                            else:
                                image_url, permalink = cached or (None, None)
                        elif isinstance(pid, int) and pid in prod_cache_by_id:
                            cached = prod_cache_by_id.get(pid)
                            if cached and len(cached) == 3:
                                image_url, permalink, purchase_price = cached
                            else:
                                image_url, permalink = cached or (None, None)
                        elif db is not None:
                            if code:
                                pr = db.query(Product).filter(Product.code == code).first()
                                if pr:
                                    image_url = _product_image_url(pr)
                                    permalink = pr.permalink
                                    purchase_price = float(pr.purchase_price) if pr.purchase_price else None
                                    prod_cache_by_code[code] = (image_url, permalink, purchase_price)
                            if (image_url is None) and isinstance(pid, int):
                                pr2 = db.query(Product).filter(Product.shoper_id == pid).first()
                                if pr2:
                                    image_url = _product_image_url(pr2)
                                    permalink = pr2.permalink
                                    purchase_price = float(pr2.purchase_price) if pr2.purchase_price else None
                                    prod_cache_by_id[pid] = (image_url, permalink, purchase_price)
                    except Exception:
                        pass
                    simp.append({
                        "name": name,
                        "code": code,
                        "product_id": pid,
                        "quantity": qty,
                        "price": price,
                        "image": image_url,
                        "permalink": permalink,
                        "purchase_price": purchase_price,
                    })

                for p in prods:
                    _emit(p)
                    # flatten children if any
                    try:
                        ch = p.get("children")
                        if isinstance(ch, list):
                            for c in ch:
                                _emit(c)
                    except Exception:
                        pass
            # Buyer basic info
            buyer = {"email": o.get("email")}
            try:
                b = o.get("billing_address") or {}
                d = o.get("delivery_address") or {}
                src = b or d or {}
                buyer.update({
                    "firstname": src.get("firstname"),
                    "lastname": src.get("lastname"),
                    "phone": src.get("phone"),
                    "city": src.get("city"),
                    "postcode": src.get("postcode"),
                    "street1": src.get("street1"),
                    "country": src.get("country") or src.get("country_code"),
                })
            except Exception:
                pass
            row["items"] = simp
            row["buyer"] = buyer
        out.append(row)
    if db is not None:
        try:
            db.close()
        except Exception:
            pass
    
    # Update cache (only for non-detailed to keep it fast)
    if not detailed:
        if _orders_cache is None:
            _orders_cache = {}
        _orders_cache[cache_key] = out
        _orders_cache_ts = now
    
    # Trigger background sync with Furgonetka
    if auto_sync_furgonetka and out:
        try:
            # Collect order IDs from the response
            order_ids = [o.get("id") for o in out if o.get("id")]
            if order_ids:
                asyncio.create_task(_background_sync_furgonetka(order_ids))
        except Exception as e:
            print(f"Failed to trigger Furgonetka sync: {e}")

    return out


@app.get("/orders/statuses")
async def get_order_statuses():
    """Fetch all available order statuses from Shoper API."""
    if not settings.shoper_base_url or not settings.shoper_access_token:
        return []
    client = ShoperClient(settings.shoper_base_url, settings.shoper_access_token)
    statuses = await client.fetch_order_statuses()
    
    # Normalize and translate statuses
    result = []
    for st in statuses:
        st_id = st.get("status_id") or st.get("id")
        st_type = st.get("type")
        st_color = st.get("color")
        
        # Extract translated name
        st_name = None
        try:
            tr = st.get("translations")
            if isinstance(tr, dict):
                lang = getattr(settings, "default_language_code", None) or "pl_PL"
                tr_lang = tr.get(lang)
                if isinstance(tr_lang, dict):
                    st_name = tr_lang.get("name")
                if not st_name:
                    # fallback: first entry
                    for _k, _v in tr.items():
                        if isinstance(_v, dict) and _v.get("name"):
                            st_name = _v.get("name")
                            break
        except Exception:
            pass
        
        if st_id is not None:
            result.append({
                "id": st_id,
                "type": st_type,
                "name": st_name or f"Status {st_id}",
                "color": st_color
            })
    
    return result


@app.get("/orders/{order_id}")
async def get_order_details(order_id: int):
    """Fetch detailed information for a specific order."""
    if not settings.shoper_base_url or not settings.shoper_access_token:
        return JSONResponse({"error": "Shoper configuration missing"}, status_code=400)
    
    client = ShoperClient(settings.shoper_base_url, settings.shoper_access_token)
    try:
        # Fetch single order with all details
        order_data = await client.fetch_order_detail(order_id)
        if not order_data:
            return JSONResponse({"error": "Order not found"}, status_code=404)
        
        # Normalize using the same logic as list_orders
        # Process as a list with one item to reuse normalization
        db = SessionLocal()
        prod_cache_by_code: dict[str, tuple[str|None, str|None]] = {}
        prod_cache_by_id: dict[int, tuple[str|None, str|None]] = {}
        
        try:
            o = order_data
            oid = o.get("order_id") or o.get("id") or o.get("orderId")
            ts = o.get("date") or o.get("created_at") or o.get("add_date") or o.get("createdAt")
            total = (o.get("sum") or o.get("total_gross") or o.get("total") or o.get("amount") or 0)
            
            # Extract items count
            items_count = o.get("total_products")
            if items_count is None:
                products = o.get("products") or o.get("items") or o.get("orders_products") or []
                if isinstance(products, dict):
                    products = products.get("items") or products.get("list") or []
                try:
                    items_count = sum(int(p.get("quantity") or p.get("qty") or p.get("count") or 0) for p in (products or []) if isinstance(p, dict))
                except Exception:
                    items_count = None
            
            # Status info
            st = o.get("status") or {}
            st_name = None
            try:
                tr = st.get("translations")
                if isinstance(tr, dict):
                    lang = getattr(settings, "default_language_code", None) or "pl_PL"
                    tr_lang = tr.get(lang)
                    if isinstance(tr_lang, dict):
                        st_name = tr_lang.get("name")
                    if not st_name:
                        for _k, _v in tr.items():
                            if isinstance(_v, dict) and _v.get("name"):
                                st_name = _v.get("name")
                                break
            except Exception:
                pass
            st_type = (st.get("type") if isinstance(st, dict) else None) or o.get("status_type")
            st_id = (st.get("status_id") if isinstance(st, dict) else None) or o.get("status_id")
            st_color = (st.get("color") if isinstance(st, dict) else None)
            
            # Extract user info
            user_info = {}
            try:
                user = o.get("user")
                if isinstance(user, dict):
                    user_info = {
                        "firstname": user.get("firstname"),
                        "lastname": user.get("lastname"),
                        "email": user.get("email") or o.get("email"),
                    }
                elif o.get("email"):
                    user_info = {"email": o.get("email")}
            except Exception:
                pass
            
            # Build basic row
            row = {
                "id": oid,
                "date": ts,
                "total": total,
                "items_count": items_count,
                "delivery_date": o.get("delivery_date"),
                "status": {"type": st_type, "id": st_id, "color": st_color, "name": st_name},
                "user": user_info,
            }
            
            # Attach detailed items
            prods = (
                o.get("products")
                or o.get("orders_products")
                or o.get("order_products")
                or o.get("items")
                or []
            )
            if isinstance(prods, dict):
                prods = prods.get("items") or prods.get("list") or []
            
            # Fallback: fetch per-order products if empty
            if (not prods) and oid is not None:
                try:
                    prods = await client.fetch_order_products(oid)
                except Exception:
                    prods = []
            
            simp: list[dict] = []
            if isinstance(prods, list):
                def _emit(pobj: dict):
                    if not isinstance(pobj, dict):
                        return
                    name = pobj.get("name") or pobj.get("product_name") or pobj.get("title")
                    code = pobj.get("code") or pobj.get("sku") or pobj.get("product_code")
                    pid = pobj.get("product_id") or pobj.get("id")
                    qty = pobj.get("quantity") or pobj.get("qty") or pobj.get("count") or 0
                    price = pobj.get("price") or pobj.get("price_gross") or pobj.get("sum") or pobj.get("amount")
                    
                    # Concatenate options to name if present
                    try:
                        topts = pobj.get("text_options")
                        if isinstance(topts, list) and topts:
                            optstr = ", ".join([str(x.get("value")) for x in topts if isinstance(x, dict) and x.get("value")])
                            if optstr:
                                name = f"{name} ({optstr})"
                    except Exception:
                        pass
                    
                    try:
                        qty = int(qty)
                    except Exception:
                        try:
                            qty = int(float(str(qty).replace(",", ".")))
                        except Exception:
                            qty = 0
                    try:
                        price = float(str(price).replace(",", ".")) if price is not None else None
                    except Exception:
                        price = None
                    
                    # Enrich with image/permalink via local products when possible
                    image_url = None
                    permalink = None
                    try:
                        if code and code in prod_cache_by_code:
                            image_url, permalink = prod_cache_by_code.get(code) or (None, None)
                        elif isinstance(pid, int) and pid in prod_cache_by_id:
                            image_url, permalink = prod_cache_by_id.get(pid) or (None, None)
                        elif db is not None:
                            if code:
                                pr = db.query(Product).filter(Product.code == code).first()
                                if pr:
                                    image_url = _product_image_url(pr)
                                    permalink = pr.permalink
                                    prod_cache_by_code[code] = (image_url, permalink)
                            if (image_url is None) and isinstance(pid, int):
                                pr2 = db.query(Product).filter(Product.shoper_id == pid).first()
                                if pr2:
                                    image_url = _product_image_url(pr2)
                                    permalink = pr2.permalink
                                    prod_cache_by_id[pid] = (image_url, permalink)
                    except Exception:
                        pass
                    
                    simp.append({
                        "name": name,
                        "code": code,
                        "product_id": pid,
                        "quantity": qty,
                        "price": price,
                        "image": image_url,
                        "permalink": permalink,
                    })
                
                for p in prods:
                    _emit(p)
                    # flatten children if any
                    try:
                        ch = p.get("children")
                        if isinstance(ch, list):
                            for c in ch:
                                _emit(c)
                    except Exception:
                        pass
            
            # Buyer basic info
            buyer = {"email": o.get("email")}
            try:
                b = o.get("billing_address") or {}
                d = o.get("delivery_address") or {}
                src = b or d or {}
                buyer.update({
                    "firstname": src.get("firstname"),
                    "lastname": src.get("lastname"),
                    "phone": src.get("phone"),
                    "city": src.get("city"),
                    "postcode": src.get("postcode"),
                    "street1": src.get("street1"),
                    "country": src.get("country") or src.get("country_code"),
                })
            except Exception:
                pass
            
            row["items"] = simp
            row["buyer"] = buyer
            
            return row
        finally:
            if db is not None:
                try:
                    db.close()
                except Exception:
                    pass
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.put("/orders/{order_id}/status")
async def update_order_status(order_id: int, payload: dict):
    """Update order status."""
    if not settings.shoper_base_url or not settings.shoper_access_token:
        return JSONResponse({"error": "Shoper not configured"}, status_code=400)
    
    status_id = payload.get("status_id")
    if not status_id:
        return JSONResponse({"error": "status_id required"}, status_code=400)
    
    client = ShoperClient(settings.shoper_base_url, settings.shoper_access_token)
    result = await client.update_order_status(order_id, status_id)
    
    if result.get("error"):
        return JSONResponse(result, status_code=result.get("status_code", 500))
    
    # Invalidate orders cache
    global _orders_cache, _orders_cache_ts
    _orders_cache = None
    _orders_cache_ts = None
    
    return result


@app.get("/users")
async def list_users(limit: int = 200, page: int | None = None):
    if not settings.shoper_base_url or not settings.shoper_access_token:
        return []
    client = ShoperClient(settings.shoper_base_url, settings.shoper_access_token)
    if page is not None:
        meta = await client.fetch_users_page(page=max(1, int(page or 1)), limit=max(1, min(int(limit or 200), 250)))
        items = meta.get("items") or []
    else:
        items = await client.fetch_all_users(limit=max(1, min(int(limit or 200), 250)))
    # Fetch orders to annotate whether user purchased anything
    orders_user_ids = set()
    try:
        orders = await client.fetch_all_orders(limit=200)
        for o in orders or []:
            uid = o.get("user_id")
            if uid is not None:
                orders_user_ids.add(uid)
    except Exception:
        pass
    out = []
    for u in items:
        out.append({
            "user_id": u.get("user_id") or u.get("id"),
            "login": u.get("login"),  # kept for compatibility, UI may hide it
            "date_add": u.get("date_add") or u.get("created_at"),
            "lastvisit": u.get("lastvisit") or u.get("last_login"),
            "firstname": u.get("firstname"),  # kept
            "lastname": u.get("lastname"),    # kept
            "email": u.get("email"),
            "active": u.get("active"),
            "newsletter": u.get("newsletter"),
            "has_orders": (u.get("user_id") or u.get("id")) in orders_user_ids,
        })
    return out


@app.get("/stats")
async def stats():
    db = SessionLocal()
    try:
        total_scans = db.query(func.count(Scan.id)).scalar() or 0
        scans_ready = db.query(func.count(Scan.id)).filter(Scan.selected_candidate_id.isnot(None)).scalar() or 0
        scans_published = db.query(func.count(Scan.id)).filter(Scan.publish_status == "published").scalar() or 0
        total_products = db.query(func.count(Product.id)).scalar() or 0
        
        # Recent activity: Combined Scans and BatchScanItems (published)
        # Fetch top 10 from each to ensure we get the true top 10 combined
        
        # 1. Recent Scans
        scan_rows = db.query(Scan).filter(Scan.publish_status == "published").order_by(Scan.id.desc()).limit(10).all()
        
        # 2. Recent Batch Items
        batch_rows = db.query(BatchScanItem).filter(BatchScanItem.publish_status == "published").order_by(BatchScanItem.processed_at.desc()).limit(10).all()
        
        combined_recent = []
        
        # Process Scans
        for s in scan_rows:
            image_url = None
            if s.selected_candidate_id:
                cand = db.get(ScanCandidate, s.selected_candidate_id)
                if cand:
                    image_url = cand.image
            if not image_url:
                first_cand = db.query(ScanCandidate).filter(ScanCandidate.scan_id == s.id).first()
                if first_cand:
                    image_url = first_cand.image
            if not image_url and s.stored_path:
                image_url = f"/uploads/{Path(s.stored_path).name}"
            
            permalink = None
            if s.published_shoper_id:
                product = db.query(Product).filter(Product.shoper_id == s.published_shoper_id).first()
                if product:
                    permalink = product.permalink
            
            combined_recent.append({
                "type": "scan",
                "id": s.id,
                "date": s.created_at,
                "created_at": s.created_at.isoformat(),
                "name": s.detected_name,
                "set": s.detected_set,
                "number": s.detected_number,
                "priced": bool(s.price_pln_final is not None),
                "image": image_url,
                "price_pln_final": s.price_pln_final,
                "permalink": permalink,
            })
            
        # Process Batch Items
        for b in batch_rows:
            image_url = None
            if b.matched_image:
                image_url = b.matched_image
            elif b.stored_path:
                image_url = f"/uploads/{Path(b.stored_path).name}"
                
            permalink = None
            if b.published_shoper_id:
                product = db.query(Product).filter(Product.shoper_id == b.published_shoper_id).first()
                if product:
                    permalink = product.permalink
            
            # Use processed_at or fallback to now if missing
            date_val = b.processed_at or datetime.utcnow()
            
            combined_recent.append({
                "type": "batch_item",
                "id": b.id,
                "date": date_val,
                "created_at": date_val.isoformat(),
                "name": b.matched_name or b.detected_name,
                "set": b.matched_set or b.detected_set,
                "number": b.matched_number or b.detected_number,
                "priced": bool(b.price_pln_final is not None),
                "image": image_url,
                "price_pln_final": b.price_pln_final,
                "permalink": permalink,
            })
            
        # Sort by date descending and take top 10
        combined_recent.sort(key=lambda x: x["date"], reverse=True)
        recent = combined_recent[:10]
        
        # Remove raw date object before returning
        for r in recent:
            r.pop("date", None)

        # Augment with external API metrics if configured
        metrics = await _get_sales_metrics()

        sold_value_pln = metrics.get("sold_value_pln", 0.0)
        sold_count = metrics.get("sold_count", 0)
        users_count = metrics.get("users_count")

        # Inventory stats (from all products in shop)
        # Calculate total cost and value (price × stock)
        total_inventory_cost = 0.0
        total_inventory_value = 0.0
        products_counted = 0
        products_without_purchase_price = 0
        
        products_in_stock = db.query(Product).filter(Product.stock > 0).all()
        for product in products_in_stock:
            stock = int(product.stock or 0)
            price = float(product.price or 0.0)
            purchase_price = float(product.purchase_price or 0.0)
            
            # If purchase_price is not set, calculate it dynamically
            if not purchase_price and price:
                products_without_purchase_price += 1
                # Use rarity from linked catalog or estimate from price
                rarity = None
                if product.catalog_id:
                    catalog_entry = db.get(CardCatalog, product.catalog_id)
                    if catalog_entry:
                        rarity = catalog_entry.rarity
                purchase_price = _calculate_purchase_cost(rarity, price)
            
            if purchase_price > 0:
                products_counted += 1
            
            total_inventory_cost += stock * purchase_price
            total_inventory_value += stock * price
        
        # Debug logging
        if products_without_purchase_price > 0:
            print(f"⚠️  {products_without_purchase_price} products calculated purchase_price dynamically")
        print(f"📊 Inventory: {products_counted} products, cost={total_inventory_cost:.2f}, value={total_inventory_value:.2f}")
        
        potential_profit = total_inventory_value - total_inventory_cost

        return {
            "total_scans": total_scans,
            "scans_ready": scans_ready,
            "scans_published": scans_published,
            "total_products": total_products,
            "recent_scans": recent,
            "sold_value_pln": sold_value_pln,
            "sold_count": sold_count,
            "users_count": users_count,
            "total_inventory_cost": round(total_inventory_cost, 2),
            "total_inventory_value": round(total_inventory_value, 2),
            "potential_profit": round(potential_profit, 2),
        }
    finally:
        db.close()


@app.get("/reports")
async def reports(range_days: int | None = None, low_stock_threshold: int = 1, top_n: int = 10):
    db = SessionLocal()
    try:
        # Metrics
        total_products = db.query(func.count(Product.id)).scalar() or 0
        total_scans = db.query(func.count(Scan.id)).scalar() or 0
        scans_ready = db.query(func.count(Scan.id)).filter(Scan.selected_candidate_id.isnot(None)).scalar() or 0
        scans_published = db.query(func.count(Scan.id)).filter(Scan.publish_status == "published").scalar() or 0

        # Inventory numbers
        rows_inv = db.query(Product.stock, Product.price).all()
        inv_units = 0
        inv_value = 0.0
        for st, pr in rows_inv:
            s = int(st or 0)
            p = float(pr or 0.0)
            inv_units += s
            inv_value += s * p

        # Build date keys
        # Build daily key series (if range specified use that many days, else 30 for charts only)
        if range_days is not None:
            try:
                days = max(1, min(365, int(range_days)))
            except Exception:
                days = 30
        else:
            days = 30
        today = datetime.utcnow().date()
        start = today - timedelta(days=days - 1)
        keys = [(start + timedelta(days=i)).isoformat() for i in range(days)]

        # Products per day (by updated_at)
        prod_rows = db.query(Product.updated_at).filter(Product.updated_at.isnot(None)).all()
        prod_map: dict[str, int] = {k: 0 for k in keys}
        for (dt,) in prod_rows:
            try:
                d = (dt.date() if hasattr(dt, 'date') else dt).isoformat()
                if d in prod_map:
                    prod_map[d] += 1
            except Exception:
                continue
        products_per_day = [{"date": k, "count": prod_map[k]} for k in keys]

        # Scans per day (by created_at)
        scan_rows = db.query(Scan.created_at).all()
        scan_map: dict[str, int] = {k: 0 for k in keys}
        for (dt,) in scan_rows:
            try:
                d = (dt.date() if hasattr(dt, 'date') else dt).isoformat()
                if d in scan_map:
                    scan_map[d] += 1
            except Exception:
                continue
        scans_per_day = [{"date": k, "count": scan_map[k]} for k in keys]

        # Category breakdown (top N)
        # Start with fallback categories
        _CATEGORY_NAMES = {c["category_id"]: c["name"] for c in _CATEGORIES_FALLBACK}
        # Try to get fresh data from Shoper API
        if settings.shoper_base_url and settings.shoper_access_token:
            try:
                client = ShoperClient(settings.shoper_base_url, settings.shoper_access_token)
                all_categories = await get_shoper_categories(client)
                for c in all_categories:
                    cid = c.get("category_id") or c.get("id")
                    if cid:
                        name = c.get("translations", {}).get("pl_PL", {}).get("name") or c.get("name")
                        if name:
                            _CATEGORY_NAMES[int(cid)] = name
            except Exception:
                pass  # Keep fallback names

        cats = (
            db.query(Product.category_id, func.count(Product.id))
            .group_by(Product.category_id)
            .order_by(func.count(Product.id).desc())
            .limit(max(1, min(50, int(top_n))))
            .all()
        )
        top_categories = [
            {"id": cid, "name": _CATEGORY_NAMES.get(cid), "count": int(c)} for cid, c in cats
        ]

        # Low stock items (<= threshold)
        try:
            thr = max(0, int(low_stock_threshold))
        except Exception:
            thr = 1
        low_stock_rows = (
            db.query(Product)
            .filter(Product.stock.isnot(None))
            .filter(Product.stock <= thr)
            .order_by(Product.stock.asc().nullsfirst(), Product.updated_at.desc().nullslast())
            .limit(20)
            .all()
        )
        low_stock = [
            {
                "id": r.id,
                "code": r.code,
                "name": r.name,
                "stock": r.stock,
                "price": r.price,
                "permalink": r.permalink,
            }
            for r in low_stock_rows
        ]

        # Top value products (price * stock)
        rows_all = db.query(Product).all()
        enriched = []
        for r in rows_all:
            s = int(r.stock or 0)
            p = float(r.price or 0.0)
            enriched.append({
                "id": r.id,
                "code": r.code,
                "name": r.name,
                "stock": s,
                "price": p,
                "permalink": r.permalink,
                "image": _product_image_url(r),
                "value": s * p,
            })
        top_value = sorted(enriched, key=lambda x: x["value"], reverse=True)[: max(1, min(50, int(top_n)))]

        # External API metrics — reuse cached sales/users (fast and spójne z Panelem)
        metrics = await _get_sales_metrics()
        sold_value_pln = metrics.get("sold_value_pln", 0.0)
        sold_count = metrics.get("sold_count", 0)
        users_count = metrics.get("users_count")
        
        # Sales over time (revenue, quantity, cost, profit per day)
        sales_per_day = []
        if settings.shoper_base_url and settings.shoper_access_token:
            try:
                client = ShoperClient(settings.shoper_base_url, settings.shoper_access_token)
                orders = await client.fetch_all_orders(limit=500)
                
                # Initialize sales map with all dates in range
                sales_map: dict[str, dict[str, float | int]] = {
                    k: {"revenue": 0.0, "quantity": 0, "cost": 0.0, "profit": 0.0} 
                    for k in keys
                }
                
                for order in orders:
                    try:
                        # Parse order date
                        order_date_str = order.get("date") or order.get("date_add")
                        if not order_date_str:
                            continue
                        
                        # Handle different date formats
                        if isinstance(order_date_str, str):
                            try:
                                order_date = datetime.fromisoformat(order_date_str.replace('Z', '+00:00')).date()
                            except:
                                try:
                                    order_date = datetime.strptime(order_date_str.split(' ')[0], '%Y-%m-%d').date()
                                except:
                                    continue
                        else:
                            order_date = order_date_str.date()
                        
                        order_date_key = order_date.isoformat()
                        
                        if order_date_key not in sales_map:
                            continue
                        
                        # Revenue
                        total = order.get("sum") or order.get("total_gross") or order.get("total") or order.get("amount") or 0
                        try:
                            revenue = float(str(total).replace(",", "."))
                            sales_map[order_date_key]["revenue"] += revenue
                        except:
                            pass
                        
                        # Quantity and cost - try multiple approaches
                        items = order.get("products") or order.get("items") or order.get("orders_products") or order.get("order_products") or []
                        if isinstance(items, dict):
                            items = items.get("items") or items.get("list") or []
                        
                        # If no items found in order, try fetching them separately
                        if not items:
                            order_id = order.get("order_id") or order.get("id")
                            if order_id:
                                try:
                                    items = await client.fetch_order_products(int(order_id))
                                except:
                                    items = []
                        
                        for item in items:
                            if not isinstance(item, dict):
                                continue
                            
                            qty = int(item.get("quantity") or item.get("qty") or item.get("count") or 0)
                            sales_map[order_date_key]["quantity"] += qty
                            
                            # Try to get purchase cost from Product
                            product_code = item.get("code")
                            if product_code and qty > 0:
                                product = db.query(Product).filter(Product.code == product_code).first()
                                if product and product.purchase_price:
                                    sales_map[order_date_key]["cost"] += qty * float(product.purchase_price)
                    except Exception as e:
                        print(f"Error processing order for sales_per_day: {e}")
                        continue
                
                # Calculate profit for each day after all orders processed
                for k, v in sales_map.items():
                    v["profit"] = v["revenue"] - v["cost"]
                
                # Convert to list
                sales_per_day = [
                    {
                        "date": k,
                        "revenue": round(v["revenue"], 2),
                        "quantity": int(v["quantity"]),
                        "cost": round(v["cost"], 2),
                        "profit": round(v["profit"], 2),
                    }
                    for k, v in sales_map.items()
                ]
                
                # Debug: Log summary
                total_qty = sum(v["quantity"] for v in sales_map.values())
                total_rev = sum(v["revenue"] for v in sales_map.values())
                total_cost = sum(v["cost"] for v in sales_map.values())
                print(f"📊 Sales data: {len(orders)} orders, {total_qty} cards sold, {total_rev:.2f} PLN revenue, {total_cost:.2f} PLN cost")
                if total_qty == 0:
                    print(f"⚠️ WARNING: No card quantities found in {len(orders)} orders!")
                    # Sample first order to debug structure
                    if orders:
                        print(f"🔍 Sample order keys: {list(orders[0].keys())}")
                        items_test = orders[0].get("products") or orders[0].get("items") or []
                        print(f"🔍 Sample order products type: {type(items_test)}, length: {len(items_test) if isinstance(items_test, (list, dict)) else 'N/A'}")
            except Exception as e:
                print(f"❌ Error fetching sales_per_day: {e}")
                import traceback
                traceback.print_exc()
                sales_per_day = []

        return {
            "metrics": {
                "total_products": total_products,
                "inventory_units": inv_units,
                "inventory_value_pln": inv_value,
                "total_scans": total_scans,
                "scans_ready": scans_ready,
                "scans_published": scans_published,
                "sold_value_pln": sold_value_pln,
                "sold_count": sold_count,
                "users_count": users_count,
            },
            "products_per_day": products_per_day,
            "scans_per_day": scans_per_day,
            "sales_per_day": sales_per_day,
            "top_categories": top_categories,
            "low_stock": low_stock,
            "top_value": top_value,
        }
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════════════════════
# BATCH SCAN ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/batch/start")
async def batch_start(
    files: List[UploadFile] = File(...),
    session_id: Optional[str] = Form(default=None),
    starting_warehouse_code: Optional[str] = Form(default=None),
):
    """
    Start a new batch scan session by uploading multiple images.
    Accepts session_id for warehouse code tracking.
    Returns batch_id and list of queued items.
    """
    from .db import BatchScan, BatchScanItem, Session
    
    db = SessionLocal()
    try:
        # Parse session_id
        sess_id: int | None = None
        if session_id and session_id.isdigit():
            sess_id = int(session_id)
        
        # Get starting code from session if not provided
        starting_code = starting_warehouse_code
        if sess_id and not starting_code:
            session = db.get(Session, sess_id)
            if session and session.starting_warehouse_code:
                starting_code = session.starting_warehouse_code
        
        # Create batch session
        batch = BatchScan(
            status="pending",
            total_items=len(files),
            processed_items=0,
            successful_items=0,
            failed_items=0,
            session_id=sess_id,
            starting_warehouse_code=starting_code,
        )
        db.add(batch)
        db.commit()
        db.refresh(batch)
        
        items_created = []
        for file in files:
            # Save file to disk
            filename = file.filename or f"batch_{batch.id}_{len(items_created)}.jpg"
            safe_filename = filename.replace("/", "_").replace("\\", "_")
            stored_path = Path(settings.upload_dir) / f"batch_{batch.id}_{safe_filename}"
            
            content = await file.read()
            stored_path.write_bytes(content)
            
            # Create batch item
            item = BatchScanItem(
                batch_id=batch.id,
                filename=safe_filename,
                stored_path=str(stored_path),
                status="pending",
            )
            db.add(item)
            items_created.append({
                "filename": safe_filename,
                "status": "pending",
            })
        
        db.commit()
        
        return {
            "batch_id": batch.id,
            "session_id": sess_id,
            "starting_warehouse_code": starting_code,
            "total_items": len(items_created),
            "items": items_created,
            "status": "pending",
        }
    finally:
        db.close()


@app.get("/batch/{batch_id}/status")
async def batch_status(batch_id: int):
    """
    Get current status of batch scan processing.
    """
    from .db import BatchScan, BatchScanItem
    
    db = SessionLocal()
    try:
        batch = db.get(BatchScan, batch_id)
        if not batch:
            return JSONResponse({"error": "Batch not found"}, status_code=404)
        
        return {
            "batch_id": batch.id,
            "status": batch.status,
            "total_items": batch.total_items,
            "processed_items": batch.processed_items,
            "successful_items": batch.successful_items,
            "failed_items": batch.failed_items,
            "current_filename": batch.current_filename,
            "progress_percent": round((batch.processed_items / max(1, batch.total_items)) * 100, 1),
            "created_at": batch.created_at.isoformat() if batch.created_at else None,
            "completed_at": batch.completed_at.isoformat() if batch.completed_at else None,
        }
    finally:
        db.close()


@app.post("/batch/{batch_id}/analyze-next")
async def batch_analyze_next(batch_id: int):
    """
    Analyze the next pending item in the batch using FULL scan logic:
    - OpenAI Vision analysis
    - TCGGO provider search and details
    - Cardmarket pricing with variants
    - Fingerprint duplicate detection
    - Shoper attribute mapping
    - Warehouse code assignment
    """
    from .db import BatchScan, BatchScanItem, Session, Fingerprint, CardCatalog
    import json as json_module
    
    db = SessionLocal()
    try:
        batch = db.get(BatchScan, batch_id)
        if not batch:
            return JSONResponse({"error": "Batch not found"}, status_code=404)
        
        # Find next pending item
        next_item = db.query(BatchScanItem).filter(
            BatchScanItem.batch_id == batch_id,
            BatchScanItem.status == "pending"
        ).first()
        
        if not next_item:
            # All items processed
            batch.status = "completed"
            batch.completed_at = datetime.utcnow()
            db.commit()
            return {
                "status": "completed",
                "batch_id": batch_id,
                "message": "All items processed",
            }
        
        # Update batch status
        batch.status = "processing"
        batch.current_filename = next_item.filename
        next_item.status = "processing"
        db.commit()
        
        try:
            image_path = Path(next_item.stored_path)
            if not image_path.exists():
                raise FileNotFoundError(f"Image not found: {next_item.stored_path}")
            
            # === STEP 1: Assign warehouse code ===
            starting_code = batch.starting_warehouse_code
            if batch.session_id and not starting_code:
                session = db.get(Session, batch.session_id)
                if session and session.starting_warehouse_code:
                    starting_code = session.starting_warehouse_code
            
            try:
                warehouse_code = get_next_free_location_for_batch(db, batch_id=batch.id, starting_code=starting_code)
                next_item.warehouse_code = warehouse_code
            except Exception as e:
                print(f"WARNING: Could not assign warehouse code: {e}")
                warehouse_code = None
            
            # === STEP 2: Fingerprint & Duplicate Detection ===
            duplicate_hit_id = None
            duplicate_distance = None
            try:
                from PIL import Image as _PILImage
                with _PILImage.open(image_path) as _im:
                    fp = compute_fingerprint(_im, use_orb=True)
                
                # Check for duplicates
                if settings.duplicate_check_enabled:
                    src_phash = fp["phash"]
                    src_dhash = fp["dhash"]
                    src_tile = fp["tile_phash"]
                    rows = db.query(Fingerprint).all()
                    best_dist = None
                    best_id = None
                    for r in rows:
                        try:
                            ph = unpack_ndarray(r.phash)
                            dh = unpack_ndarray(r.dhash)
                            tl = unpack_ndarray(r.tile_phash)
                        except Exception:
                            continue
                        score = 0
                        score += hamming_distance(src_phash, ph)
                        score += hamming_distance(src_dhash, dh)
                        if getattr(settings, 'duplicate_use_tiles', True):
                            try:
                                for a, b in zip(src_tile, tl):
                                    score += hamming_distance(a, b)
                            except Exception:
                                score += 999
                        if best_dist is None or score < best_dist:
                            best_dist = score
                            best_id = r.scan_id
                    thr = max(1, int(getattr(settings, 'duplicate_distance_threshold', 80)))
                    if best_dist is not None and best_dist <= thr and best_id is not None:
                        duplicate_hit_id = int(best_id)
                        duplicate_distance = int(best_dist)
                        next_item.duplicate_of_scan_id = duplicate_hit_id
                        next_item.duplicate_distance = duplicate_distance
            except Exception as e:
                print(f"Fingerprint error: {e}")
            
            # === STEP 3: Vision Analysis (OpenAI) ===
            detected_data = analyze_card(str(image_path))
            
            next_item.detected_name = detected_data.get("name")
            next_item.detected_set = detected_data.get("set")
            next_item.detected_set_code = detected_data.get("set_code")
            next_item.detected_number = detected_data.get("number")
            next_item.detected_language = detected_data.get("language")
            next_item.detected_variant = detected_data.get("variant")
            next_item.detected_condition = detected_data.get("condition")
            next_item.detected_rarity = detected_data.get("rarity")
            next_item.detected_energy = detected_data.get("energy")
            
            # === STEP 4: Provider Search ===
            provider = get_provider()
            detected_schema = DetectedData(**detected_data)
            candidates = await provider.search(detected_schema)
            
            candidates_list = []
            best_candidate = None
            details = None
            
            if candidates:
                for i, cand in enumerate(candidates[:5]):
                    cand_dict = {
                        "id": cand.id,
                        "name": cand.name,
                        "set": cand.set,
                        "set_code": cand.set_code,
                        "number": cand.number,
                        "rarity": cand.rarity,
                        "image": cand.image,
                        "score": cand.score,
                    }
                    
                    # Get details for top candidate
                    if i == 0:
                        best_candidate = cand
                        try:
                            details = await provider.details(cand.id)
                            
                            # Update image from details
                            detailed_image = details.get("image")
                            if not detailed_image and isinstance(details.get("images"), dict):
                                detailed_image = details["images"].get("large") or details["images"].get("small")
                            if detailed_image:
                                cand_dict["image"] = detailed_image
                                
                        except Exception as e:
                            print(f"Details fetch error: {e}")
                            # details stays None, but we still have best_candidate
                    
                    candidates_list.append(cand_dict)
            
            next_item.candidates_json = json_module.dumps(candidates_list)
            
            # === STEP 5: Apply best match data ===
            if best_candidate:
                next_item.matched_provider_id = best_candidate.id
                next_item.matched_name = best_candidate.name
                next_item.matched_set = best_candidate.set
                next_item.matched_set_code = best_candidate.set_code
                next_item.matched_number = best_candidate.number
                next_item.matched_rarity = best_candidate.rarity
                next_item.matched_image = candidates_list[0].get("image") if candidates_list else best_candidate.image
                
                # Calculate robust match score with penalties
                base_score = best_candidate.score
                penalty = 0.0
                
                # Penalty for missing price (implies obscure card)
                prices = best_candidate.cardmarket if hasattr(best_candidate, 'cardmarket') else {}
                has_price = bool(prices)
                if not has_price:
                    penalty += 0.15
                
                # Penalty for missing rarity
                if not next_item.matched_rarity and not next_item.detected_rarity:
                    penalty += 0.10
                    
                next_item.match_score = max(0.0, base_score - penalty)
                
                # Update from details
                if details:
                    next_item.matched_set = details.get("episode", {}).get("name") or next_item.matched_set
                    next_item.matched_set_code = details.get("episode", {}).get("code") or next_item.matched_set_code
                    next_item.matched_rarity = details.get("rarity") or next_item.matched_rarity
                    
                    # Extract energy from types list
                    types = details.get('types')
                    if isinstance(types, list) and types:
                        next_item.detected_energy = types[0]
                    elif isinstance(types, str):
                        next_item.detected_energy = types
                    
                    # Extract Cardmarket URL
                    cardmarket_data = details.get("cardmarket", {})
                    if cardmarket_data and isinstance(cardmarket_data, dict):
                        next_item.cardmarket_url = cardmarket_data.get("url")
            
            # === STEP 6: Pricing with Variants ===
            variants_data = []
            if details:
                try:
                    price_variants = list_variant_prices(details)
                    variants_data = price_variants
                    
                    # Find primary price
                    primary_price_pln_final = None
                    primary_price_eur = None
                    for label_priority in ['Normal', 'Holo', 'Reverse Holo']:
                        variant_info = next((p for p in price_variants if p.get('label') == label_priority), None)
                        if variant_info:
                            if variant_info.get('price_pln_final') is not None:
                                primary_price_pln_final = variant_info.get('price_pln_final')
                            if variant_info.get('eur') is not None:
                                primary_price_eur = variant_info.get('eur')
                            break
                    
                    next_item.price_pln_final = primary_price_pln_final
                    next_item.price_eur = primary_price_eur
                    if primary_price_eur and not primary_price_pln_final:
                        next_item.price_pln = round(primary_price_eur * settings.eur_pln_rate, 2)
                        next_item.price_pln_final = round(primary_price_eur * settings.eur_pln_rate * settings.price_multiplier, 2)
                        
                except Exception as e:
                    print(f"Pricing error: {e}")
            
            next_item.variants_json = json_module.dumps(variants_data)
            
            # === STEP 7: Shoper Attribute Mapping ===
            try:
                # Filter out generic 'Pokémon' supertype to prevent mapping to 'Pokemon EX' or similar
                # We want standard Pokemon to default to 'Nie dotyczy' (182)
                raw_type = details.get("supertype") if details else None
                if raw_type and str(raw_type).lower() in ['pokémon', 'pokemon']:
                    raw_type = None

                detected_attrs = {
                    "rarity": next_item.matched_rarity or next_item.detected_rarity,
                    "variant": next_item.detected_variant,
                    "condition": next_item.detected_condition,
                    "energy": next_item.detected_energy,
                    "language": next_item.detected_language,
                    "type": raw_type,
                }
                
                if settings.shoper_base_url and settings.shoper_access_token:
                    client = ShoperClient(settings.shoper_base_url, settings.shoper_access_token)
                    tax = await client.fetch_attributes()
                    items = tax.get("items") if isinstance(tax, dict) else []
                    if items:
                        # USE FORM IDs mapping!
                        from .attributes import map_detected_to_form_ids
                        mapped = map_detected_to_form_ids(detected_attrs, items)
                        
                        next_item.attr_language = mapped.get('64')  # Language
                        next_item.attr_condition = mapped.get('66')  # Condition  
                        next_item.attr_finish = mapped.get('65')  # Finish
                        next_item.attr_rarity = mapped.get('38')  # Rarity
                        next_item.attr_energy = mapped.get('63')  # Energy
                        next_item.attr_card_type = mapped.get('39')  # Card Type
            except Exception as e:
                print(f"Attribute mapping error: {e}")
            
            # Set defaults if not mapped
            if not next_item.attr_language:
                next_item.attr_language = '142'  # English
            if not next_item.attr_condition:
                next_item.attr_condition = '176'  # Near Mint
            if not next_item.attr_finish:
                next_item.attr_finish = '184'  # Normal
            if not next_item.attr_card_type:
                next_item.attr_card_type = '182'  # Nie dotyczy (N/A)
            
            # === STEP 8: Calculate completeness ===
            fields = {
                "name": bool(next_item.matched_name or next_item.detected_name),
                "set": bool(next_item.matched_set or next_item.detected_set),
                "number": bool(next_item.matched_number or next_item.detected_number),
                "image": bool(next_item.matched_image),
                "price": bool(next_item.price_pln_final or next_item.price_eur),
                "rarity": bool(next_item.matched_rarity or next_item.detected_rarity),
                "energy": bool(next_item.detected_energy),
            }
            next_item.fields_status = json_module.dumps(fields)
            next_item.fields_complete = sum(1 for v in fields.values() if v)
            next_item.fields_total = len(fields)
            
            next_item.status = "success"
            next_item.processed_at = datetime.utcnow()
            batch.processed_items += 1
            batch.successful_items += 1
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            next_item.status = "failed"
            next_item.error_message = str(e)
            next_item.processed_at = datetime.utcnow()
            batch.processed_items += 1
            batch.failed_items += 1
        
        db.commit()
        db.refresh(next_item)
        
        # Build response
        variants = []
        if next_item.variants_json:
            try:
                variants = json_module.loads(next_item.variants_json)
            except:
                pass
        
        candidates_response = []
        if next_item.candidates_json:
            try:
                candidates_response = json_module.loads(next_item.candidates_json)
            except:
                pass
        
        return {
            "status": "processed",
            "batch_id": batch_id,
            "item": {
                "id": next_item.id,
                "filename": next_item.filename,
                "status": next_item.status,
                "image_url": f"/uploads/{Path(next_item.stored_path).name}" if next_item.stored_path else None,
                # Detected
                "detected_name": next_item.detected_name,
                "detected_set": next_item.detected_set,
                "detected_number": next_item.detected_number,
                "detected_rarity": next_item.detected_rarity,
                "detected_energy": next_item.detected_energy,
                "detected_language": next_item.detected_language,
                "detected_variant": next_item.detected_variant,
                "detected_condition": next_item.detected_condition,
                # Matched
                "matched_provider_id": next_item.matched_provider_id,
                "matched_name": next_item.matched_name,
                "matched_set": next_item.matched_set,
                "matched_set_code": next_item.matched_set_code,
                "matched_number": next_item.matched_number,
                "matched_rarity": next_item.matched_rarity,
                "matched_image": next_item.matched_image,
                "match_score": next_item.match_score,
                # Pricing
                "price_eur": next_item.price_eur,
                "price_pln": next_item.price_pln,
                "price_pln_final": next_item.price_pln_final,
                "variants": variants,
                # Duplicates
                "duplicate_of_scan_id": next_item.duplicate_of_scan_id,
                "duplicate_distance": next_item.duplicate_distance,
                # Attributes
                "attr_language": next_item.attr_language,
                "attr_condition": next_item.attr_condition,
                "attr_finish": next_item.attr_finish,
                "attr_rarity": next_item.attr_rarity,
                "attr_energy": next_item.attr_energy,
                # Warehouse
                "warehouse_code": next_item.warehouse_code,
                # Candidates
                "candidates": candidates_response,
                # Completeness
                "fields_complete": next_item.fields_complete,
                "fields_total": next_item.fields_total,
                "error_message": next_item.error_message,
            },
            "progress": {
                "processed": batch.processed_items,
                "total": batch.total_items,
                "percent": round((batch.processed_items / max(1, batch.total_items)) * 100, 1),
            },
        }
    finally:
        db.close()


@app.get("/batch/{batch_id}/items")
async def batch_items(batch_id: int):
    """
    Get all items in a batch with their current status.
    """
    from .db import BatchScan, BatchScanItem
    import json as json_module
    
    db = SessionLocal()
    try:
        batch = db.get(BatchScan, batch_id)
        if not batch:
            return JSONResponse({"error": "Batch not found"}, status_code=404)
        
        items = db.query(BatchScanItem).filter(BatchScanItem.batch_id == batch_id).all()
        
        result = []
        for item in items:
            result.append({
                "id": item.id,
                "filename": item.filename,
                "status": item.status,
                "stored_path": item.stored_path,
                "image_url": f"/uploads/{Path(item.stored_path).name}" if item.stored_path else None,
                "detected_name": item.detected_name,
                "detected_set": item.detected_set,
                "detected_number": item.detected_number,
                "detected_variant": item.detected_variant,
                "detected_condition": item.detected_condition,
                "detected_rarity": item.detected_rarity,
                "detected_energy": item.detected_energy,
                "detected_language": item.detected_language,
                "matched_provider_id": item.matched_provider_id,
                "matched_name": item.matched_name,
                "matched_set": item.matched_set,
                "matched_number": item.matched_number,
                "matched_image": item.matched_image,
                "match_score": item.match_score,
                "price_eur": item.price_eur,
                "price_pln": item.price_pln,
                "price_pln_final": item.price_pln_final,
                "attr_language": item.attr_language,
                "attr_condition": item.attr_condition,
                "attr_finish": item.attr_finish,
                "attr_rarity": item.attr_rarity,
                "attr_energy": item.attr_energy,
                "attr_card_type": item.attr_card_type,
                "use_tcggo_image": item.use_tcggo_image if item.use_tcggo_image is not None else True,
                "additional_images": json_module.loads(item.additional_images_json) if item.additional_images_json else [],
                "candidates": json_module.loads(item.candidates_json) if item.candidates_json else [],
                "variants": json_module.loads(item.variants_json) if item.variants_json else None,
                "duplicate_of_scan_id": item.duplicate_of_scan_id,
                "duplicate_distance": item.duplicate_distance,
                "fields_complete": item.fields_complete,
                "fields_total": item.fields_total,
                "fields_status": json_module.loads(item.fields_status) if item.fields_status else None,
                "error_message": item.error_message,
                "publish_status": item.publish_status,
                "warehouse_code": item.warehouse_code,
            })
        
        return {
            "batch_id": batch_id,
            "status": batch.status,
            "total_items": batch.total_items,
            "processed_items": batch.processed_items,
            "items": result,
        }
    finally:
        db.close()


@app.patch("/batch/{batch_id}/items/{item_id}")
async def batch_update_item(
    batch_id: int, 
    item_id: int, 
    request: Request,
    additional_images: List[UploadFile] = File(default=[])
):
    """
    Update a single item in the batch (for manual corrections).
    Supports both JSON and FormData (for additional images upload).
    """
    from .db import BatchScan, BatchScanItem
    import json as json_module
    
    db = SessionLocal()
    try:
        item = db.query(BatchScanItem).filter(
            BatchScanItem.batch_id == batch_id,
            BatchScanItem.id == item_id
        ).first()
        
        if not item:
            return JSONResponse({"error": "Item not found"}, status_code=404)
        
        # Try to parse as JSON first, fallback to form data
        data = {}
        content_type = request.headers.get("content-type", "")
        
        if "multipart/form-data" in content_type:
            # FormData with files
            form = await request.form()
            if "updates" in form:
                data = json_module.loads(form["updates"])
        else:
            # Standard JSON
            data = await request.json()
        
        # Update allowed fields
        updatable = [
            "detected_name", "detected_set", "detected_number",
            "detected_variant", "detected_condition", "detected_language",
            "matched_provider_id", "matched_name", "matched_set", "matched_number", "matched_image",
            "price_eur", "price_pln", "price_pln_final", "warehouse_code",
            "attr_language", "attr_condition", "attr_finish", "attr_rarity", "attr_energy", "attr_card_type",
            "matched_rarity", "detected_rarity", "detected_energy", "use_tcggo_image"
        ]
        
        for field in updatable:
            if field in data:
                setattr(item, field, data[field])
        
        # Handle additional images upload
        if additional_images:
            existing_images = []
            if item.additional_images_json:
                try:
                    existing_images = json_module.loads(item.additional_images_json)
                except:
                    existing_images = []
            
            upload_dir = Path(settings.upload_dir)
            upload_dir.mkdir(parents=True, exist_ok=True)
            
            for img_file in additional_images:
                if img_file.filename:
                    # Generate unique filename
                    safe_name = img_file.filename.replace("/", "_").replace("\\", "_")
                    stored_name = f"batch_{batch_id}_item_{item_id}_{safe_name}"
                    stored_path = upload_dir / stored_name
                    
                    # Save file
                    content = await img_file.read()
                    stored_path.write_bytes(content)
                    
                    # Add to list (store relative path for serving)
                    existing_images.append(f"/uploads/{stored_name}")
            
            item.additional_images_json = json_module.dumps(existing_images)
        
        # Recalculate completeness
        fields = {
            "name": bool(item.matched_name or item.detected_name),
            "set": bool(item.matched_set or item.detected_set),
            "number": bool(item.matched_number or item.detected_number),
            "image": bool(item.matched_image),
            "price": bool(item.price_pln_final or item.price_eur),
            "rarity": bool(item.matched_rarity or item.detected_rarity),
            "energy": bool(item.detected_energy),
        }
        item.fields_status = json_module.dumps(fields)
        item.fields_complete = sum(1 for v in fields.values() if v)
        item.fields_total = len(fields)
        
        db.commit()
        db.refresh(item)
        
        return {
            "status": "updated",
            "item": {
                "id": item.id,
                "filename": item.filename,
                "fields_complete": item.fields_complete,
                "fields_total": item.fields_total,
            }
        }
    finally:
        db.close()


@app.post("/batch/{batch_id}/publish")
async def batch_publish(batch_id: int, request: Request):
    """
    Publish all successful items in the batch to Shoper.
    Can optionally specify item_ids to publish only selected items.
    """
    from .db import BatchScan, BatchScanItem
    
    db = SessionLocal()
    try:
        batch = db.get(BatchScan, batch_id)
        if not batch:
            return JSONResponse({"error": "Batch not found"}, status_code=404)
        
        data = {}
        try:
            data = await request.json()
        except Exception:
            pass
        
        item_ids = data.get("item_ids")  # Optional: publish only selected
        
        # Get items to publish
        query = db.query(BatchScanItem).filter(
            BatchScanItem.batch_id == batch_id,
            BatchScanItem.status == "success",
            BatchScanItem.publish_status.is_(None)
        )
        if item_ids:
            query = query.filter(BatchScanItem.id.in_(item_ids))
        
        items = query.all()
        
        if not items:
            return {"status": "no_items", "message": "No items to publish"}
        
        # Check Shoper credentials
        if not settings.shoper_base_url or not settings.shoper_access_token:
            return JSONResponse({"error": "Shoper not configured"}, status_code=400)
        
        published = []
        failed = []
        
        client = ShoperClient(settings.shoper_base_url, settings.shoper_access_token)
        
        # Prepare headers for direct API calls
        headers = {
            "Authorization": f"Bearer {client.token}",
            "Accept": "application/json",
        }
        products_url = f"{client.base_url}{settings.shoper_products_path}"
        
        async with httpx.AsyncClient(timeout=30) as http:
            for item in items:
                try:
                    # Create temporary objects for builders
                    temp_scan = Scan(
                        detected_name=item.detected_name,
                        detected_set=item.detected_set,
                        detected_number=item.detected_number,
                        detected_language=item.detected_language,
                        detected_variant=item.detected_variant,
                        detected_condition=item.detected_condition,
                        detected_rarity=item.detected_rarity,
                        detected_energy=item.detected_energy,
                        price_pln_final=item.price_pln_final,
                        price_pln=item.price_pln,
                        stored_path=item.stored_path,
                    )
                    
                    temp_candidate = None
                    if item.matched_provider_id:
                        temp_candidate = ScanCandidate(
                            provider_id=item.matched_provider_id,
                            name=item.matched_name,
                            set=item.matched_set,
                            number=item.matched_number,
                            rarity=item.matched_rarity,
                            image=item.matched_image,
                        )

                    # 1. Build attributes payload
                    attributes_payload = await build_product_attributes_payload(client, temp_scan, temp_candidate)
                    
                    # 2. Build product payload
                    payload = await build_shoper_payload(client, temp_scan, temp_candidate)
                    
                    if settings.publish_dry_run:
                        item.publish_status = "published"
                        item.published_shoper_id = 0
                        published.append({"id": item.id, "filename": item.filename, "shoper_id": 0, "dry_run": True})
                        continue
                    
                    # 3. Publish product
                    r = await http.post(products_url, json=payload, headers=headers)
                    
                    if r.status_code in (200, 201):
                        response_json = r.json()
                        product_id = None
                        if isinstance(response_json, dict):
                            product_id = response_json.get("product_id") or response_json.get("id")
                        elif isinstance(response_json, (int, str)):
                            try:
                                product_id = int(response_json)
                            except (ValueError, TypeError):
                                pass
                        
                        if product_id:
                            item.publish_status = "published"
                            item.published_shoper_id = product_id
                            published.append({"id": item.id, "filename": item.filename, "shoper_id": product_id})
                            
                            # 4. Set attributes
                            if attributes_payload:
                                await client.set_product_attributes(product_id, attributes_payload)
                                
                            # 5. Upload primary image (based on user choice)
                            image_to_upload = None
                            use_tcggo = item.use_tcggo_image if item.use_tcggo_image is not None else True
                            
                            if use_tcggo and item.matched_image and item.matched_image.startswith("http"):
                                # User chose TCGGO/API image
                                image_to_upload = item.matched_image
                            elif not use_tcggo and item.stored_path and Path(item.stored_path).is_file():
                                # User chose their scan
                                image_to_upload = item.stored_path
                            elif item.matched_image and item.matched_image.startswith("http"):
                                # Fallback to TCGGO if scan not available
                                image_to_upload = item.matched_image
                            elif item.stored_path and Path(item.stored_path).is_file():
                                # Fallback to scan if TCGGO not available
                                image_to_upload = item.stored_path
                                
                            if image_to_upload:
                                try:
                                    await client.upload_product_image(product_id, str(image_to_upload), main=True)
                                except Exception as img_e:
                                    print(f"WARNING: Primary image upload exception for item {item.id}: {img_e}")
                            
                            # 5b. Upload additional images
                            if item.additional_images_json:
                                try:
                                    import json as json_module2
                                    additional_imgs = json_module2.loads(item.additional_images_json)
                                    for img_path in additional_imgs:
                                        # img_path is like "/uploads/filename.jpg"
                                        full_path = Path(settings.upload_dir) / Path(img_path).name
                                        if full_path.is_file():
                                            try:
                                                await client.upload_product_image(product_id, str(full_path), main=False)
                                            except Exception as add_img_e:
                                                print(f"WARNING: Additional image upload failed for {img_path}: {add_img_e}")
                                except Exception as e:
                                    print(f"WARNING: Failed to process additional images for item {item.id}: {e}")
                            
                            # 6. Set Related Products
                            try:
                                # Determine set_id from payload (category_id)
                                category_id = payload.get("category_id")
                                if not category_id and "categories" in payload and payload["categories"]:
                                    category_id = payload["categories"][0]
                                
                                if category_id:
                                    # Use existing helper to get related products from same category
                                    related_ids = await _get_related_products_from_category(client, int(category_id), limit=10)
                                    if related_ids:
                                        # Use update_product to set related products (ShoperClient doesn't have set_product_related)
                                        await client.update_product(product_id, {"related": related_ids})
                            except Exception as rel_e:
                                print(f"WARNING: Failed to set related products for item {item.id}: {rel_e}")

                        else:
                            raise Exception("No product_id in response")
                    else:
                        error_text = r.text[:200] if r.text else "Unknown error"
                        raise Exception(f"HTTP {r.status_code}: {error_text}")
                        
                except Exception as e:
                    item.publish_status = "failed"
                    item.error_message = str(e)
                    failed.append({"id": item.id, "filename": item.filename, "error": str(e)})
        
        db.commit()
        
        return {
            "status": "completed",
            "published_count": len(published),
            "failed_count": len(failed),
            "published": published,
            "failed": failed,
        }
    finally:
        db.close()


_CATEGORIES_FALLBACK = [
    {"category_id": 38, "name": "Karty Pokémon"},
    {"category_id": 39, "name": "151"},
    {"category_id": 40, "name": "Licytacja"},
    {"category_id": 41, "name": "Zestawy"},
    {"category_id": 42, "name": "Temporal Forces"},
    {"category_id": 43, "name": "Obsidian Flames"},
    {"category_id": 44, "name": "Journey Together"},
    {"category_id": 48, "name": "Stellar Crown"},
    {"category_id": 49, "name": "Twilight Masquerade"},
    {"category_id": 51, "name": "Prismatic Evolutions"},
    {"category_id": 53, "name": "Destined Rivals"},
    {"category_id": 55, "name": "Scarlet & Violet"},
    {"category_id": 56, "name": "Paldea Evolved"},
    {"category_id": 57, "name": "Paradox Rift"},
    {"category_id": 58, "name": "Surging Sparks"},
    {"category_id": 60, "name": "Shrouded Fable"},
    {"category_id": 65, "name": "Paldean Fates"},
    {"category_id": 66, "name": "Evolutions"},
    {"category_id": 70, "name": "White Flare"},
    {"category_id": 71, "name": "Black Bolt"},
    {"category_id": 72, "name": "Scarlet & Violet"},
    {"category_id": 74, "name": "XY"},
    {"category_id": 75, "name": "Sun & Moon"},
    {"category_id": 80, "name": "SVP Black Star Promos"},
    {"category_id": 89, "name": "BREAKpoint"},
    {"category_id": 90, "name": "Sword & Shield"},
    {"category_id": 91, "name": "Vivid Voltage"},
    {"category_id": 92, "name": "Pokémon GO"},
    {"category_id": 93, "name": "Rebel Clash"},
    {"category_id": 94, "name": "Lost Origin"},
    {"category_id": 95, "name": "Shining Fates"},
    {"category_id": 96, "name": "Chilling Reign"},
    {"category_id": 97, "name": "SWSH Black Star Promos"},
    {"category_id": 98, "name": "BREAKthrough"},
    {"category_id": 99, "name": "Crown Zenith"},
    {"category_id": 100, "name": "Astral Radiance"},
    {"category_id": 101, "name": "Roaring Skies"},
    {"category_id": 102, "name": "Primal Clash"},
    {"category_id": 103, "name": "Brilliant Stars"},
    {"category_id": 104, "name": "Evolving Skies"},
    {"category_id": 105, "name": "Fusion Strike"},
    {"category_id": 106, "name": "Celebrations"},
    {"category_id": 107, "name": "Silver Tempest"},
    {"category_id": 108, "name": "Darkness Ablaze"},
    {"category_id": 109, "name": "Generations"},
    {"category_id": 110, "name": "Ancient Origins"},
    {"category_id": 111, "name": "Steam Siege"},
]

@app.post("/admin/recalc_purchase_costs")
async def recalc_purchase_costs():
    """
    One-time migration to calculate purchase costs for all existing scans based on current logic.
    """
    db = SessionLocal()
    try:
        scans = db.query(Scan).all()
        count = 0
        updated = 0
        
        for s in scans:
            count += 1
            
            # 1. Get rarity
            rarity = s.detected_rarity
            
            # Try to fallback to catalog if linked
            if not rarity and s.catalog_id:
                cat = db.get(CardCatalog, s.catalog_id)
                if cat:
                    rarity = cat.rarity
            
            # 2. Get price_pln (market value without multiplier)
            price_pln = s.price_pln
            
            # If price_pln missing but catalog exists, recalculate
            if not price_pln and s.catalog_id:
                cat = db.get(CardCatalog, s.catalog_id)
                if cat and cat.price_normal_eur:
                    price_pln = cat.price_normal_eur * settings.eur_pln_rate
            
            # Calculate
            cost = _calculate_purchase_cost(rarity, price_pln)
            s.purchase_price = cost
            updated += 1
            
        db.commit()
        return {"status": "ok", "total_scans": count, "updated_scans": updated}
    finally:
        db.close()

@app.post("/admin/recalc_product_costs")
async def recalc_product_costs():
    """
    One-time migration to calculate purchase costs for all existing products.
    For old products (premium cards): purchase_price = 80% of current price.
    """
    db = SessionLocal()
    try:
        products = db.query(Product).all()
        count = 0
        updated = 0
        
        for p in products:
            count += 1
            
            # Skip if already has purchase_price
            if p.purchase_price is not None and p.purchase_price > 0:
                continue
            
            # Calculate: 80% of current price (old cards are premium)
            if p.price and p.price > 0:
                p.purchase_price = round(p.price * 0.80, 2)
                updated += 1
            
        db.commit()
        return {"status": "ok", "total_products": count, "updated_products": updated}
    finally:
        db.close()


async def _background_sync_furgonetka(order_ids: List[int]):
    """Background task to sync Furgonetka shipments."""
    try:
        # Import locally to avoid circular imports
        from .furgonetka_endpoints import sync_shipment_from_furgonetka
        
        # Process in chunks to avoid overwhelming API
        chunk_size = 5
        for i in range(0, len(order_ids), chunk_size):
            chunk = order_ids[i:i + chunk_size]
            for order_id in chunk:
                try:
                    await sync_shipment_from_furgonetka(order_id)
                except Exception as e:
                    print(f"Background sync failed for order {order_id}: {e}")
            
            # Small delay between chunks
            if i + chunk_size < len(order_ids):
                await asyncio.sleep(1)
                
    except Exception as e:
        print(f"Background sync error: {e}")

