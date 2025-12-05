import os
from typing import List, Optional
from fastapi import APIRouter, Depends, File, UploadFile, Form, HTTPException
from sqlalchemy import func
from sqlmodel import Session, select
from ..database import get_session
from ..services import scanner, tcg_api
from ..models import CardRecord
from ..schemas import CardSearchResult
from .cards import _payload_to_search_schema

router = APIRouter(prefix="/api/scanner", tags=["scanner"])

RAPIDAPI_KEY = (
    os.getenv("KARTOTEKA_RAPIDAPI_KEY")
    or os.getenv("POKEMONTCG_RAPIDAPI_KEY")
    or os.getenv("RAPIDAPI_KEY")
)
RAPIDAPI_HOST = (
    os.getenv("KARTOTEKA_RAPIDAPI_HOST")
    or os.getenv("POKEMONTCG_RAPIDAPI_HOST")
    or os.getenv("RAPIDAPI_HOST")
)

@router.post("/scan")
async def scan_card(
    file: UploadFile = File(...),
    ocr_text: Optional[str] = Form(None),
    session: Session = Depends(get_session)
):
    """
    Process uploaded card image:
    1. Try Google Cloud Vision OCR -> Global TCG API Search.
    2. Try visual search (pHash) against local DB.
    3. Fallback to client-side OCR text -> Global TCG API Search.
    """
    contents = await file.read()
    
    # 1. Google Vision OCR (Highest Priority)
    google_text = await scanner.google_ocr(contents)
    if google_text:
        query = google_text.strip()
        # Search global API to get prices and rich data
        records, _, _ = tcg_api.search_cards(
            name=query,
            limit=5,
            per_page=5,
            rapidapi_key=RAPIDAPI_KEY,
            rapidapi_host=RAPIDAPI_HOST
        )
        
        if records:
            items = [
                _payload_to_search_schema(r) for r in records if isinstance(r, dict)
            ]
            return {
                "match_type": "google_ocr",
                "results": items,
                "raw_text": google_text
            }
    
    # 2. Visual Search (pHash)
    visual_match = scanner.find_similar_card(session, contents)
    if visual_match:
        result = CardSearchResult(
            name=visual_match.name,
            number=visual_match.number,
            set_name=visual_match.set_name,
            set_code=visual_match.set_code,
            image_small=visual_match.image_small,
            price=visual_match.price,
            rarity=visual_match.rarity
        )
        return {
            "match_type": "visual",
            "results": [result]
        }

    # 3. Text Search (Client-side Fallback)
    if ocr_text and len(ocr_text.strip()) > 2:
        query = ocr_text.strip()
        records, _, _ = tcg_api.search_cards(
            name=query,
            limit=5,
            per_page=5,
            rapidapi_key=RAPIDAPI_KEY,
            rapidapi_host=RAPIDAPI_HOST
        )
            
        if records:
            items = [
                _payload_to_search_schema(r) for r in records if isinstance(r, dict)
            ]
            return {
                "match_type": "text",
                "results": items
            }

    return {"match_type": "none", "results": []}


@router.post("/learn")
async def learn_card(
    card_id: int = Form(...),
    file: UploadFile = File(...),
    session: Session = Depends(get_session)
):
    """
    Save pHash for a known card to improve future visual search.
    Called when user confirms a match or selects a card manually after taking a photo.
    """
    contents = await file.read()
    scanner.register_card_image(session, card_id, contents)
    return {"status": "learned"}
