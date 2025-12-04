import base64
from typing import Optional

from .settings import settings


def _read_b64(path: str) -> str:
    with open(path, 'rb') as f:
        return base64.b64encode(f.read()).decode('ascii')


def _normalize_card_number(number_str: str | None) -> str | None:
    """Extract just the card number, removing total count after slash."""
    if not number_str:
        return None
    
    num = str(number_str).strip()
    
    # If contains slash, take only the part before it
    if '/' in num:
        num = num.split('/')[0].strip()
    
    return num if num else None


def _call_openai_vision(b64: str) -> dict:
    """Helper to call OpenAI Vision with a base64 image string."""
    from openai import OpenAI
    import json

    client = OpenAI(api_key=settings.openai_api_key)

    # Optimization: Resize image if too large before sending to OpenAI
    try:
        from PIL import Image
        import io
        
        # Decode
        img_data = base64.b64decode(b64)
        img = Image.open(io.BytesIO(img_data))
        
        # Resize if needed (max 1000px long edge)
        max_dim = 1000
        if max(img.size) > max_dim:
            ratio = max_dim / max(img.size)
            new_size = (int(img.width * ratio), int(img.height * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
            
            # Re-encode to JPEG
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            b64 = base64.b64encode(buf.getvalue()).decode('ascii')
    except Exception as e:
        print(f"Image resize optimization failed: {e}")
        # Continue with original b64 if resize fails

    prompt = (
        "You are an expert OCR system for Pokémon Trading Card Game cards. "
        "Analyze the card using the EXACT layout structure below. Read text fields precisely from their designated locations.\n\n"
        
        "═══════════════════════════════════════════════════════════════\n"
        "CARD STRUCTURE (Field Positions):\n"
        "═══════════════════════════════════════════════════════════════\n\n"
        
        "📍 **TOP LEFT CORNER:**\n"
        "   • Card Name: Large bold text (e.g., 'Charizard')\n"
        "   • Mechanic Tag: Look for 'EX', 'ex', 'V', 'VMAX', 'VSTAR', 'GX' as part of or next to the name\n"
        "   • Stage: Small text below name (e.g., 'Basic Pokémon V', 'Stage 2', 'Evolves from Charmeleon')\n\n"
        
        "📍 **TOP RIGHT CORNER:**\n"
        "   • HP: Format '230 HP' or 'HP 230'\n"
        "   • Type Icon: Small icon next to HP (Grass/Fire/Water/Lightning/Psychic/Fighting/Darkness/Metal/Fairy/Dragon/Colorless)\n\n"
        
        "📍 **BOTTOM SECTION (below portrait):**\n"
        "   • Attacks: 1-3 sections, each with:\n"
        "     - Energy cost icons (left side)\n"
        "     - Attack name (bold text)\n"
        "     - Damage value (right side, e.g., '150')\n"
        "   • Ability/VSTAR Power: Special colored bar with 'Ability' or 'VSTAR Power' label\n\n"
        
        "📍 **BOTTOM AREA (near card edge):**\n"
        "   • Weakness/Resistance/Retreat: Three sections with type icons and modifiers\n"
        "   • Rule Box: Rectangle with text about Prize cards (e.g., 'takes 2 Prize cards')\n\n"
        
        "📍 **BOTTOM LEFT/RIGHT (collector info):**\n"
        "   • **Collector Number**: Format 'XXX/YYY' (e.g., '045/198' or 'SWSH092')\n"
        "     ⚠️ DISTINCTION: \n"
        "       - Promo Number (e.g. 'SWSH092') is ONE CONTINUOUS STRING (no spaces).\n"
        "       - Set Code (e.g. 'TWM') is SEPARATED from number (e.g. '045/198   TWM').\n"
        "     ⚠️ CRITICAL: For promo cards with YELLOW BOX, return FULL prefix: 'SWSH092', 'SV092', 'SWSH023'\n"
        "     ⚠️ Do NOT strip prefix! Return exactly as printed.\n"
        "   • **Rarity Symbol** (next to number):\n"
        "     ● Black circle = 'Common'\n"
        "     ◆ Black diamond = 'Uncommon'\n"
        "     ★ Black star = 'Rare'\n"
        "     ★★ Two black stars = 'Double Rare'\n"
        "     ★★ Two silver stars = 'Ultra Rare'\n"
        "     ★ One gold star = 'Illustration Rare'\n"
        "     ★★ Two gold stars = 'Special Illustration Rare'\n"
        "     ★★★ Three gold stars = 'Hyper Rare'\n"
        "     ★ PINK/MAGENTA star = 'ACE SPEC' (NOT Rare!)\n"
        "     ★ with 'PROMO' text = 'Promo'\n"
        "   • Set Symbol: Small graphic icon (describe shape/color)\n\n"
        
        "═══════════════════════════════════════════════════════════════\n"
        "SPECIAL MECHANICS IDENTIFICATION:\n"
        "═══════════════════════════════════════════════════════════════\n\n"
        
        "🔷 **EX / ex Cards:**\n"
        "   • Name contains 'EX' (old) or 'ex' (Scarlet & Violet)\n"
        "   • Rule Box: 'opponent takes 2 Prize cards'\n"
        "   • High HP for stage\n\n"
        
        "🔷 **V Cards:**\n"
        "   • Name contains 'V' (single letter)\n"
        "   • Stage: 'Basic Pokémon V' OR 'Pokémon V'\n"
        "   • Rule Box: 'opponent takes 2 Prize cards'\n\n"
        
        "🔷 **VMAX Cards:**\n"
        "   • Name contains 'VMAX'\n"
        "   • Stage: 'Pokémon VMAX' + 'Evolves from [Name] V'\n"
        "   • Rule Box: 'opponent takes 3 Prize cards' (NOT 2!)\n"
        "   • Gigantic/oversized Pokémon artwork\n\n"
        
        "🔷 **VSTAR Cards:**\n"
        "   • Name contains 'VSTAR'\n"
        "   • Stage: 'Pokémon VSTAR' + 'Evolves from [Name] V'\n"
        "   • Rule Box: 'opponent takes 2 Prize cards' (NOT 3!)\n"
        "   • Has 'VSTAR Power' section (special colored bar)\n"
        "   • White/pearl border with gold accents\n\n"
        
        "🔷 **GX Cards:**\n"
        "   • Name contains 'GX'\n"
        "   • Stage: 'Pokémon-GX'\n"
        "   • Rule Box: 'opponent takes 2 Prize cards'\n"
        "   • Has 'GX attack' section (special move with GX icon)\n"
        "   • Text: 'You can't use more than 1 GX attack in a game'\n\n"
        
        "🔷 **Shiny/Special Variants:**\n"
        "   • Yellow/Gold border around ENTIRE card image = add 'Shiny' to variant\n"
        "   • Rainbow texture = 'Rainbow Rare'\n"
        "   • Full Art (no yellow border, just extends to edges) = 'Full Art'\n\n"
        
        "═══════════════════════════════════════════════════════════════\n"
        "ENERGY TYPE ICONS:\n"
        "═══════════════════════════════════════════════════════════════\n"
        "🍃 Grass (leaf), 🔥 Fire (flame), 💧 Water (droplet), ⚡ Lightning (bolt),\n"
        "👁️ Psychic (eye), 👊 Fighting (fist), 🌙 Darkness (crescent moon),\n"
        "⚙️ Metal (gear - dark gray/silver), 🧚 Fairy (pink star - older sets),\n"
        "🐉 Dragon (dual-color background), ⭐ Colorless (white star)\n\n"
        
        "⚠️ CRITICAL: 'Metal' is DARK gray with metallic texture. 'Colorless' is LIGHT/WHITE.\n\n"
        
        "═══════════════════════════════════════════════════════════════\n"
        "OUTPUT FORMAT:\n"
        "═══════════════════════════════════════════════════════════════\n"
        "Return ONLY valid JSON with these exact keys:\n"
        "{\n"
        "  \"name\": string (Pokemon name only, e.g., 'Charizard'),\n"
        "  \"number\": string (FULL number with prefix if present, e.g., 'SWSH092' or '045'),\n"
        "  \"set\": string (set symbol description or set name if recognizable),\n"
        "  \"rarity\": string (use exact terms: 'Common', 'Uncommon', 'Rare', 'Double Rare', 'Ultra Rare', 'Illustration Rare', 'Special Illustration Rare', 'Hyper Rare', 'ACE SPEC', 'Promo'),\n"
        "  \"energy\": string (type from icon: 'Grass', 'Fire', 'Water', 'Lightning', 'Psychic', 'Fighting', 'Darkness', 'Metal', 'Fairy', 'Dragon', 'Colorless'),\n"
        "  \"card_type\": string ('Pokemon', 'Trainer', or 'Energy'),\n"
        "  \"variant\": string or null (mechanic: 'EX', 'ex', 'V', 'VMAX', 'VSTAR', 'GX', 'Shiny', 'Full Art', 'Rainbow Rare', 'Supporter', 'Item', 'Stadium', 'Tool', 'ACE SPEC' for trainers)\n"
        "}\n\n"
        
        "═══════════════════════════════════════════════════════════════\n"
        "RULES:\n"
        "═══════════════════════════════════════════════════════════════\n"
        "1. ❌ NO GUESSING: If text is unclear, return null. Better null than wrong.\n"
        "2. ❌ NO DEFAULT VALUES: Do not assume 'Pikachu' or any default name.\n"
        "3. ✅ READ EXACTLY: Extract text character-by-character from designated positions.\n"
        "4. ✅ PRESERVE PREFIXES: 'SWSH092' must stay 'SWSH092', NOT '92'.\n"
        "5. ✅ DISTINGUISH SYMBOLS: Pink star ≠ Black star. Two stars ≠ One star.\n"
        "6. ✅ CHECK PRIZE COUNT: VMAX takes 3 prizes, VSTAR/V/GX/EX take 2 prizes.\n"
        "7. ✅ JSON ONLY: Respond with valid JSON. No explanations, no markdown.\n\n"
        
        "Analyze the card now."
    )

    chat = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                ],
            }
        ],
        temperature=0.2,
    )

    text = chat.choices[0].message.content or "{}"
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        text = text[start : end + 1]
    data = json.loads(text)

    def _scalar(v):
        if v is None: return None
        if isinstance(v, (list, tuple)):
            for item in v:
                if item is None: continue
                s = str(item).strip()
                if s: return s
            return None
        s = str(v).strip()
        return s or None

    # Extract variant from Vision API if available
    detected_variant = _scalar(data.get('variant'))
    
    return {
        'name': _scalar(data.get('name')),
        'set': _scalar(data.get('set')),
        'number': _normalize_card_number(_scalar(data.get('number'))),
        'rarity': _scalar(data.get('rarity')),
        'energy': _scalar(data.get('energy')),
        'card_type': _scalar(data.get('card_type')),
        'variant': detected_variant,  # Now can be detected from Vision
        'set_code': None,
        'language': None,
        'condition': None,
    }


def extract_fields_with_openai_bytes(image_bytes: bytes) -> dict:
    """Extract fields from card using raw image bytes."""
    if not settings.openai_api_key:
        return {
            'name': None, 'set': None, 'set_code': None, 'number': None,
            'language': None, 'variant': None, 'condition': None, 'rarity': None, 'energy': None
        }

    try:
        import base64
        b64 = base64.b64encode(image_bytes).decode('ascii')
        return _call_openai_vision(b64)
    except Exception as e:
        print(f"OpenAI Vision (bytes) failed: {e}")
        return {
            'name': None, 'set': None, 'set_code': None, 'number': None,
            'language': None, 'variant': None, 'condition': None, 'rarity': None, 'energy': None
        }


def extract_fields_with_openai(image_path: str) -> dict:
    """Extract fields from card using file path."""
    if not settings.openai_api_key:
        from pathlib import Path
        stem = Path(image_path).stem.replace('_', ' ').strip()
        return {
            'name': stem or None, 'set': None, 'set_code': None, 'number': None,
            'language': None, 'variant': None, 'condition': None, 'rarity': None, 'energy': None
        }

    try:
        b64 = _read_b64(image_path)
        return _call_openai_vision(b64)
    except Exception as e:
        print(f"OpenAI Vision (file) failed: {e}")
        # Fallback
        from pathlib import Path
        stem = Path(image_path).stem.replace('_', ' ').strip()
        return {
            'name': stem or None, 'set': None, 'set_code': None, 'number': None,
            'language': None, 'variant': None, 'condition': None, 'rarity': None, 'energy': None
        }
