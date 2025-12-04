from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import unicodedata


def _norm(s: Any) -> str:
    if s is None:
        return ""
    text = str(s)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.strip().lower()


def _extract_options(attr_item: dict) -> List[Tuple[str, str]]:
    # Accept shapes: options: [ { option_id, value } ], values/dictionary: { id: name } or list
    options: List[Tuple[str, str]] = []
    src = (
        attr_item.get("options")
        or attr_item.get("values")
        or attr_item.get("dictionary")
        or []
    )
    if isinstance(src, dict):
        for k, v in src.items():
            options.append((str(k), str(v)))
    elif isinstance(src, list):
        for it in src:
            if not isinstance(it, dict):
                continue
            oid = it.get("option_id") or it.get("id") or it.get("value_id")
            val = it.get("value") or it.get("name") or it.get("label")
            if oid is None or val is None:
                continue
            options.append((str(oid), str(val)))
    return options


def _index_attributes(items: List[dict]) -> Dict[str, dict]:
    out: Dict[str, dict] = {}
    for it in items or []:
        if not isinstance(it, dict):
            continue
        name = it.get("name") or it.get("attribute_name")
        if not isinstance(name, str) or not name.strip():
            continue
        key = _norm(name)
        if not key:
            continue
        out[key] = {
            "id": str(it.get("attribute_id") or it.get("id") or ""),
            "name": name,
            "options": _extract_options(it),
            "raw": it,
        }
    return out


def simplify_attributes(items: List[dict]) -> List[dict]:
    """Normalize Shoper attribute entries to a consistent shape.

    Output items each have keys: attribute_id (str), name (str), options: list[{ option_id, value }]
    """
    out: List[dict] = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        attr_id = it.get("attribute_id") or it.get("id")
        name = it.get("name") or it.get("attribute_name")
        if attr_id is None or not isinstance(name, str):
            continue
        opts = _extract_options(it)
        norm_opts = [ { "option_id": str(oid), "value": val } for (oid, val) in opts ]
        out.append({
            "attribute_id": str(attr_id),
            "name": name,
            "options": norm_opts,
        })
    return out


def simplify_categories(items: List[dict]) -> List[dict]:
    """Normalize category entries to a consistent shape { category_id, name }."""
    out: List[dict] = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        cid = it.get("category_id") or it.get("id")
        name = it.get("name") or it.get("category") or it.get("title")
        if cid is None or not isinstance(name, str):
            continue
        out.append({"category_id": int(cid), "name": name})
    return out


def _best_option_id(options: List[Tuple[str, str]], candidates: List[str]) -> Optional[str]:
    """Find best option value text by matching candidates against option names.
    
    Returns the OPTION TEXT (e.g., "Near Mint"), NOT the option_id!
    This is required by Shoper API - it expects text values, not numeric IDs.
    
    options: list of (option_id, option_value_text) tuples
    candidates: list of candidate strings to match
    """
    if not options:
        return None
    # Normalize options once - map normalized text to original text value
    opt_norm = [(_norm(val), val) for oid, val in options]
    cands = [_norm(c) for c in candidates if c]
    for c in cands:
        # exact match
        for oname, oval in opt_norm:
            if oname == c:
                return oval  # Return option TEXT value!
        # contains match (fallback)
        for oname, oval in opt_norm:
            if c and c in oname:
                return oval  # Return option TEXT value
    return None


def _best_option_numeric_id(options: List[Tuple[str, str]], candidates: List[str]) -> Optional[str]:
    """Find best option ID by matching candidates against option names.
    
    Returns the OPTION ID (e.g., "176" for Near Mint), NOT the text!
    This is used for frontend form population.
    
    options: list of (option_id, option_value_text) tuples
    candidates: list of candidate strings to match
    """
    if not options:
        return None
    # Normalize options once - map normalized text to (option_id, original_text)
    opt_norm = [(_norm(val), oid, val) for oid, val in options]
    cands = [_norm(c) for c in candidates if c]
    for c in cands:
        # exact match
        for oname, oid, oval in opt_norm:
            if oname == c:
                return oid  # Return option ID!
        # contains match (fallback)
        for oname, oid, oval in opt_norm:
            if c and c in oname:
                return oid  # Return option ID
    return None


def _language_candidates(value: Optional[str]) -> List[str]:
    v = _norm(value)
    if not v:
        return []
    # Recognize codes and common names
    aliases = {
        "pl": ["polski", "polish", "pl", "pl_pl"],
        "en": ["angielski", "english", "en", "en_us", "en_gb"],
        "de": ["niemiecki", "german", "de", "de_de"],
        "fr": ["francuski", "french", "fr", "fr_fr"],
        "es": ["hiszpanski", "spanish", "es", "es_es"],
        "it": ["wloski", "italian", "it", "it_it"],
        "ja": ["japonski", "japanese", "ja", "jp", "jp_jp"],
    }
    for code, names in aliases.items():
        if v == code or v in names:
            return names + [code]
    return [v]


def _finish_candidates(value: Optional[str]) -> List[str]:
    v = _norm(value)
    if not v:
        return []
    cands = [v]
    # Handle Shiny cards (yellow border detection from Vision API)
    if "shiny" in v:
        cands.append("shiny")
        # Shiny can be combined with other finishes (e.g., "VMAX Shiny")
        # Extract base finish if present
        for finish_type in ["vmax", "vstar", "ex", "gx", "v"]:
            if finish_type in v:
                cands.append(finish_type)
    if "reverse" in v:
        cands.append("reverse holo")
    if "holo" in v or "foil" in v:
        cands.append("holo")
    if "full art" in v or ("full" in v and "art" in v):
        cands.append("full art")
    if "gold" in v:
        cands.append("gold")
    if "rainbow" in v:
        cands.append("rainbow")
    if "pokeball" in v or "pok\xe9ball" in v:
        cands.append("pokeball pattern")
    if "masterball" in v:
        cands.append("masterball pattern")
    return cands


def _condition_candidates(value: Optional[str]) -> List[str]:
    v = _norm(value)
    if not v:
        return []
    cands = [v]
    # Map common abbreviations/synonyms
    repl = {
        "nm": "near mint",
        "ex": "excellent",
        "lp": "light played",
        "pl": "played",
        "gd": "good",
    }
    if v in repl:
        cands.append(repl[v])
    if "exellent" in v:  # cope with misspelling
        cands.append("excellent")
    return cands


def _energy_candidates(value: Optional[str]) -> List[str]:
    v = _norm(value)
    if not v:
        return []
    cands = [v]
    synonyms = {
        "electric": "lightning",
        "elektryczna": "lightning",
        "steel": "metal",
        "ciemna": "darkness",
        "walka": "fighting",
        "psychiczna": "psychic",
        "zielona": "grass",
        "trawa": "grass",
        "woda": "water",
        "ogien": "fire",
        "ogniowa": "fire",
        "normal": "colorless",
    }
    for k, val in synonyms.items():
        if k in v:
            cands.append(val)
    return cands


def _rarity_candidates(value: Optional[str]) -> List[str]:
    """Generate candidate strings for rarity matching.
    
    Handles variations like 'Double Rare' -> ['double rare', 'rare'],
    'Special Illustration Rare' -> ['special illustration rare', 'illustration rare'],
    'ACE SPEC' and 'Shiny' special rarities.
    """
    v = _norm(value)
    if not v:
        return []
    cands = [v]
    
    # Handle compound rarities
    # TCGGO returns: Common, Uncommon, Rare, Double Rare, Illustration Rare, 
    # Special Illustration Rare, Hyper Rare, Ultra Rare, Shiny, Promo, ACE SPEC
    
    # Handle ACE SPEC (pink star rarity symbol)
    if "ace" in v and "spec" in v:
        cands.extend(["ace spec", "ace-spec", "acespec", "ace_spec"])
    
    # Handle Shiny as rarity (can be standalone or combined)
    if "shiny" in v:
        cands.append("shiny")
        # Also try without "shiny" if it's combined (e.g., "Shiny Rare" -> also try "Rare")
        base = v.replace("shiny", "").strip()
        if base:
            cands.append(base)
    
    # If it contains 'rare', also try just 'rare' as fallback
    if "rare" in v and v != "rare":
        cands.append("rare")
    
    # Handle 'Special Illustration Rare' -> 'Secial Illustration Rare' (typo in Shoper)
    if "special illustration rare" in v:
        cands.append("secial illustration rare")  # Note typo in Shoper
        
    return cands


def map_detected_to_shoper_attributes(
    detected: dict,
    shoper_attribute_items: List[dict],
    *,
    prefer_attribute_names: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """Return mapping { attribute_id: option_text } for relevant fields.
    
    IMPORTANT: Values are OPTION TEXT (e.g., "Near Mint"), NOT option IDs!
    Shoper API expects text values, not numeric option_id values.
    Format for Shoper API: {"group_id": {"attribute_id": "option_text"}}
    Example from actual Shoper product: {"11": {"38": "Double Rare"}}

    prefer_attribute_names: optional map to override which attribute name to use
    for a given logical key, e.g. { 'language': 'Język', 'finish': 'Wykończenie' }.
    """
    idx = _index_attributes(shoper_attribute_items)
    # Attribute keys we try to map (logical -> attribute display name candidates)
    attribute_targets: Dict[str, List[str]] = {
        "language": [
            (prefer_attribute_names or {}).get("language", "Język"),
            "Jezyk",
            "Language",
        ],
        "finish": [
            (prefer_attribute_names or {}).get("finish", "Wykończenie"),
            "Wykonczenie",
            "Finish",
        ],
        "condition": [
            (prefer_attribute_names or {}).get("condition", "Jakość"),
            "Jakosc",
            "Condition",
            "Stan",
            "Quality",
        ],
        "rarity": [
            (prefer_attribute_names or {}).get("rarity", "Rzadkość"),
            "Rzadkosc",
            "Rarity",
        ],
        "energy": [
            (prefer_attribute_names or {}).get("energy", "Energia"),
            "Energy",
        ],
        "type": [
            (prefer_attribute_names or {}).get("type", "Rodzaj"),
            "Typ",
            "Type",
            "Typ Karty",
        ],
    }

    # Resolve attribute_id and option_id
    result: Dict[str, str] = {}

    # Helper to pick attribute meta by any of the aliases
    def _find_attr(aliases: List[str]) -> Optional[dict]:
        for name in aliases:
            key = _norm(name)
            meta = idx.get(key)
            if meta:
                return meta
        return None

    # Language
    lang_val = detected.get("language")
    meta = _find_attr(attribute_targets["language"])
    if meta and lang_val:
        oid = _best_option_id(meta["options"], _language_candidates(lang_val))
        if oid:
            result[str(meta["id"])] = str(oid)
        else:
            print(f"WARNING: No option found for language '{lang_val}' in attribute '{meta['name']}'")
    elif lang_val:
        print(f"WARNING: Attribute for language not found in Shoper (tried names: {attribute_targets['language']}).")

    # Finish (from variant)
    # Default to "Normal" if no special finish detected
    meta = _find_attr(attribute_targets["finish"])
    if meta:
        fin_val = detected.get("variant") or detected.get("finish")
        if fin_val and _norm(fin_val) != "normal":
            candidates = _finish_candidates(fin_val)
            oid = _best_option_id(meta["options"], candidates)
            if oid:
                result[str(meta["id"])] = str(oid)
        else:
            # Default to "Normal" option
            oid = _best_option_id(meta["options"], ["normal"])
            if oid:
                result[str(meta["id"])] = str(oid)

    # Condition
    cond_val = detected.get("condition")
    meta = _find_attr(attribute_targets["condition"])
    if meta and cond_val:
        oid = _best_option_id(meta["options"], _condition_candidates(cond_val))
        if oid:
            result[str(meta["id"])] = str(oid)

    # Rarity
    rar_val = detected.get("rarity")
    meta = _find_attr(attribute_targets["rarity"])
    if meta and rar_val:
        oid = _best_option_id(meta["options"], _rarity_candidates(rar_val))
        if oid:
            result[str(meta["id"])] = str(oid)
        else:
            print(f"WARNING: No option found for rarity '{rar_val}' in attribute '{meta['name']}'")

    # Energy
    eng_val = detected.get("energy")
    meta = _find_attr(attribute_targets["energy"])
    if meta:
        candidates = _energy_candidates(eng_val) if eng_val else ["Nie dotyczy"]
        print(f"DEBUG: Mapping Energy. Value: '{eng_val}'. Candidates: {candidates}")
        oid = _best_option_id(meta["options"], candidates)
        print(f"DEBUG: Mapping Energy. Chosen option text: '{oid}'")
        if oid:
            result[str(meta["id"])] = str(oid)
        else:
            print(f"WARNING: No option found for energy '{eng_val}' in attribute '{meta['name']}'")
    elif eng_val:
        print(f"WARNING: Attribute for energy not found in Shoper (tried names: {attribute_targets['energy']}).")

    # Type/Rodzaj
    type_val = detected.get("type") or detected.get("rodzaj")
    meta = _find_attr(attribute_targets["type"])
    if meta:
        candidates = [_norm(type_val)] if type_val else []
        # Also check variant for Type mapping
        variant_val = detected.get("variant")
        if variant_val:
             candidates.append(_norm(variant_val))
        
        if not candidates:
            candidates = ["nie dotyczy", "n/a"]
            
        print(f"DEBUG: Mapping Type. Value: '{type_val}/{variant_val}'. Candidates: {candidates}")
        oid = _best_option_id(meta["options"], candidates)
        
        # If still no match, try forcing "nie dotyczy"
        if not oid:
            oid = _best_option_id(meta["options"], ["nie dotyczy", "n/a"])

        print(f"DEBUG: Mapping Type. Chosen option text: '{oid}'")
        if oid:
            result[str(meta["id"])] = str(oid)


    return result


def map_detected_to_form_ids(
    detected: dict,
    shoper_attribute_items: List[dict],
    *,
    prefer_attribute_names: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """Return mapping { attribute_id: option_id } for form population.
    
    Unlike map_detected_to_shoper_attributes which returns option TEXT,
    this function returns option IDs for populating frontend select dropdowns.
    Format: {"38": "115"} (attribute_id -> option_id)
    """
    idx = _index_attributes(shoper_attribute_items)
    attribute_targets: Dict[str, List[str]] = {
        "language": [
            (prefer_attribute_names or {}).get("language", "Język"),
            "Jezyk",
            "Language",
        ],
        "finish": [
            (prefer_attribute_names or {}).get("finish", "Wykończenie"),
            "Wykonczenie",
            "Finish",
        ],
        "condition": [
            (prefer_attribute_names or {}).get("condition", "Jakość"),
            "Jakosc",
            "Condition",
            "Stan",
            "Quality",
        ],
        "rarity": [
            (prefer_attribute_names or {}).get("rarity", "Rzadkość"),
            "Rzadkosc",
            "Rarity",
        ],
        "energy": [
            (prefer_attribute_names or {}).get("energy", "Energia"),
            "Energy",
        ],
        "type": [
            (prefer_attribute_names or {}).get("type", "Typ karty"),
            "Rodzaj",
            "Typ",
            "Type",
        ],
    }

    result: Dict[str, str] = {}

    def _find_attr(aliases: List[str]) -> Optional[dict]:
        for name in aliases:
            key = _norm(name)
            meta = idx.get(key)
            if meta:
                return meta
        return None

    # Language
    lang_val = detected.get("language")
    meta = _find_attr(attribute_targets["language"])
    if meta and lang_val:
        oid = _best_option_numeric_id(meta["options"], _language_candidates(lang_val))
        if oid:
            result[str(meta["id"])] = str(oid)

    # Finish (from variant)
    # Default to "Normal" if no special finish detected
    meta = _find_attr(attribute_targets["finish"])
    if meta:
        fin_val = detected.get("variant") or detected.get("finish")
        if fin_val and _norm(fin_val) != "normal":
            candidates = _finish_candidates(fin_val)
            oid = _best_option_numeric_id(meta["options"], candidates)
            if oid:
                result[str(meta["id"])] = str(oid)
        else:
            # Default to "Normal" option
            oid = _best_option_numeric_id(meta["options"], ["normal"])
            if oid:
                result[str(meta["id"])] = str(oid)

    # Condition
    cond_val = detected.get("condition")
    meta = _find_attr(attribute_targets["condition"])
    if meta and cond_val:
        oid = _best_option_numeric_id(meta["options"], _condition_candidates(cond_val))
        if oid:
            result[str(meta["id"])] = str(oid)

    # Rarity
    rar_val = detected.get("rarity")
    meta = _find_attr(attribute_targets["rarity"])
    if meta and rar_val:
        oid = _best_option_numeric_id(meta["options"], _rarity_candidates(rar_val))
        if oid:
            result[str(meta["id"])] = str(oid)

    # Energy
    eng_val = detected.get("energy")
    meta = _find_attr(attribute_targets["energy"])
    if meta:
        candidates = _energy_candidates(eng_val) if eng_val else ["Nie dotyczy"]
        oid = _best_option_numeric_id(meta["options"], candidates)
        if oid:
            result[str(meta["id"])] = str(oid)

    # Type (Card Type) - map specific card variants (EX, V, VMAX, VSTAR, GX, Supporter, Item, etc.)
    # Use 'variant' field from Vision API which now detects these special types
    variant_val = detected.get("variant")
    type_val = detected.get("type")
    
    meta = _find_attr(attribute_targets["type"])
    if meta:
        found_id = None
        # 1. Try specific variant mapping
        if variant_val:
            normalized_variant = _norm(variant_val)
            # Map common variants to card type options
            # EX, V, VMAX, VSTAR, GX, ex, Supporter, Item, Stadium, Tool, ACE SPEC, etc.
            if normalized_variant not in ["normal", "regular", ""]:
                candidates = [normalized_variant, variant_val]
                found_id = _best_option_numeric_id(meta["options"], candidates)
        
        # 2. If not found via variant, try type field
        if not found_id and type_val:
             found_id = _best_option_numeric_id(meta["options"], [_norm(type_val)])

        # 3. If still not found, default to "Nie dotyczy"
        if not found_id:
             # Try finding "Nie dotyczy" dynamically, fallback to 182 if not found but options exist
             found_id = _best_option_numeric_id(meta["options"], ["nie dotyczy", "n/a"])
             if not found_id:
                 # Fallback to hardcoded 182 if user insisted on ID 182 and we can't find it by name
                 # But verification is better. Let's check if 182 exists in options
                 for oid, _ in meta["options"]:
                     if str(oid) == "182":
                         found_id = "182"
                         break
        
        if found_id:
            result[str(meta["id"])] = str(found_id)

    return result
