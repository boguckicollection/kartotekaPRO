"""Card scanner service with OpenAI Vision and pHash visual search."""

import io
import os
import base64
import datetime as dt
from typing import Optional, TYPE_CHECKING
from pydantic import BaseModel
from PIL import Image
import imagehash
from sqlmodel import Session, select

if TYPE_CHECKING:
    from ..models import CardRecord


class CardImageHash(BaseModel):
    """
    Pydantic model for visual search compatibility.
    Represents cached card data for pHash functionality.
    In the future, add a dedicated phash column to CardRecord.
    """
    id: Optional[int] = None
    phash: Optional[str] = None
    name: str
    set_code: Optional[str] = None
    image_small: Optional[str] = None


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


async def openai_vision_ocr(image_bytes: bytes) -> str | None:
    """
    Extract text from image using OpenAI Vision API.
    Integrated with existing backend/app/vision.py implementation.
    """
    try:
        # Convert to base64
        content_b64 = base64.b64encode(image_bytes).decode("utf-8")
        
        # Import OpenAI client
        from openai import OpenAI
        
        # Get API key from environment
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("Warning: OPENAI_API_KEY not set. Skipping OpenAI OCR.")
            return None
        
        client = OpenAI(api_key=api_key)
        
        # Optimize image size before sending
        img = Image.open(io.BytesIO(image_bytes))
        max_dim = 1000
        if max(img.size) > max_dim:
            ratio = max_dim / max(img.size)
            new_size = (int(img.width * ratio), int(img.height * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
            
            # Re-encode to JPEG
            buf = io.BytesIO()
            img.convert('RGB').save(buf, format='JPEG', quality=85)
            content_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        
        # Call OpenAI Vision API
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Extract the Pokemon card name and number from this image. Return only the card name."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{content_b64}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=100
        )
        
        # Extract text from response
        text = response.choices[0].message.content
        return text.strip() if text else None
        
    except Exception as e:
        print(f"OpenAI Vision OCR failed: {e}")
        return None


def find_similar_card(session: Session, image_bytes: bytes, threshold: int = 12) -> Optional[dict]:
    """
    Find a card visually similar to the uploaded image using pHash.
    threshold: Max hamming distance (0-64). 10-12 is usually a good balance.
    
    Note: This requires pHash data to be stored in database.
    For now, returns None until phash column is added to CardRecord.
    """
    # TODO: Add phash column to CardRecord model
    # For now, return None (feature disabled)
    print("Warning: pHash visual search not yet implemented. Add 'phash' column to CardRecord.")
    return None
    
    # Future implementation:
    # try:
    #     target_hash_hex = compute_phash(image_bytes)
    #     target_hash = imagehash.hex_to_hash(target_hash_hex)
    # except ValueError:
    #     return None
    #
    # # Fetch all cards with phash data
    # known_cards = session.exec(
    #     select(CardRecord).where(CardRecord.phash.isnot(None))
    # ).all()
    #
    # best_match = None
    # min_dist = 65
    #
    # for card in known_cards:
    #     try:
    #         db_hash = imagehash.hex_to_hash(card.phash)
    #         dist = target_hash - db_hash
    #         if dist < min_dist:
    #             min_dist = dist
    #             best_match = card
    #     except Exception:
    #         continue
    #
    # if best_match and min_dist <= threshold:
    #     return best_match
    #
    # return None


def register_card_image(session: Session, card_id: int, image_bytes: bytes):
    """
    Register a known image for a card to build the visual database.
    
    Note: Requires phash column in CardRecord.
    For now, this is a no-op until database is updated.
    """
    print(f"Warning: register_card_image not yet implemented. Add 'phash' column to CardRecord.")
    # TODO: Implement after adding phash column
    pass
    
    # Future implementation:
    # try:
    #     phash = compute_phash(image_bytes)
    #     card = session.get(CardRecord, card_id)
    #     if card:
    #         card.phash = phash
    #         session.add(card)
    #         session.commit()
    #         print(f"Registered visual fingerprint for card {card_id}: {phash}")
    # except Exception as e:
    #     print(f"Failed to register card image: {e}")
