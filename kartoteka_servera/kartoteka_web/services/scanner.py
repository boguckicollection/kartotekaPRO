import io
import os
import base64
import datetime as dt
from typing import List, Optional, Tuple
from PIL import Image
import imagehash
import httpx
from sqlmodel import Session, select
from ..models import CardImageHash, CardRecord

def compute_phash(image_bytes: bytes) -> str:
    """Compute perceptual hash of an image."""
    try:
        image = Image.open(io.BytesIO(image_bytes))
        # Convert to RGB just in case
        if image.mode != 'RGB':
            image = image.convert('RGB')
        # Use perceptual hash (pHash) which is robust to scaling/rotation
        h = imagehash.phash(image)
        return str(h)
    except Exception as e:
        print(f"Error computing phash: {e}")
        raise ValueError("Invalid image data")

async def google_ocr(image_bytes: bytes) -> str | None:
    """
    Extract text from image using Google Cloud Vision API.
    Requires GOOGLE_VISION_API_KEY in environment variables.
    """
    api_key = os.getenv("GOOGLE_VISION_API_KEY")
    if not api_key:
        print("Warning: GOOGLE_VISION_API_KEY not set. Skipping Google OCR.")
        return None

    url = f"https://vision.googleapis.com/v1/images:annotate?key={api_key}"
    
    # Encode image to base64
    content_b64 = base64.b64encode(image_bytes).decode("utf-8")
    
    payload = {
        "requests": [
            {
                "image": {"content": content_b64},
                "features": [{"type": "TEXT_DETECTION", "maxResults": 1}]
            }
        ]
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=10.0)
            
        if response.status_code != 200:
            print(f"Google Vision API error: {response.status_code} - {response.text}")
            return None
            
        data = response.json()
        responses = data.get("responses", [])
        if not responses:
            return None
            
        text_annotations = responses[0].get("textAnnotations", [])
        if text_annotations:
            # The first annotation is the entire text
            return text_annotations[0].get("description", "").strip()
            
    except Exception as e:
        print(f"Google OCR failed: {e}")
        
    return None

def find_similar_card(session: Session, image_bytes: bytes, threshold: int = 12) -> Optional[CardRecord]:
    """
    Find a card visually similar to the uploaded image using pHash.
    threshold: Max hamming distance (0-64). 10-12 is usually a good balance.
    """
    try:
        target_hash_hex = compute_phash(image_bytes)
        target_hash = imagehash.hex_to_hash(target_hash_hex)
    except ValueError:
        return None
    
    # Fetch all hashes (optimized: usually we'd filter, but pHash requires bitwise comparison)
    known_hashes = session.exec(select(CardImageHash)).all()
    
    best_match = None
    min_dist = 65  # Max possible distance is 64
    
    for record in known_hashes:
        try:
            db_hash = imagehash.hex_to_hash(record.phash)
            dist = target_hash - db_hash
            
            if dist < min_dist:
                min_dist = dist
                best_match = record
        except Exception:
            continue
            
    if best_match and min_dist <= threshold:
        return session.get(CardRecord, best_match.card_record_id)
        
    return None

def register_card_image(session: Session, card_id: int, image_bytes: bytes):
    """Register a known image for a card to build the visual database."""
    try:
        phash = compute_phash(image_bytes)
        
        # Check duplicates
        existing = session.exec(select(CardImageHash).where(CardImageHash.phash == phash)).first()
        if not existing:
            db_entry = CardImageHash(phash=phash, card_record_id=card_id)
            session.add(db_entry)
            session.commit()
            print(f"Registered new visual fingerprint for card {card_id}: {phash}")
    except Exception as e:
        print(f"Failed to register card image: {e}")
