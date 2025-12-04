from __future__ import annotations

from typing import List, Optional
import json
import os
import httpx
from rapidfuzz import fuzz

from .schemas import Candidate, DetectedData
from .settings import settings


class CardProvider:
    async def search(self, detected: DetectedData) -> List[Candidate]:  # pragma: no cover
        raise NotImplementedError
    async def details(self, card_id: str) -> dict:  # pragma: no cover
        """Fetch detailed info (including prices) for a given provider-specific card id."""
        raise NotImplementedError


class PokemonTCGProvider(CardProvider):
    """Basic integration with pokemontcg.io v2 as a working fallback provider.

    This is used until a specific TCGGO API is configured.
    """

    base_url = "https://api.pokemontcg.io/v2"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.tcggo_api_key

    async def search(self, detected: DetectedData) -> List[Candidate]:
        if not detected.name:
            return []

        # Build query with optional filters
        query_parts = [f"name:{detected.name}"]
        if detected.number:
            # Handle number variants (e.g. SV029 vs SV29)
            import re
            num = str(detected.number).strip()
            variants = [f'"{num}"'] # Quote to handle potential spaces or special chars safely
            
            # Variant 1: Strip leading zeros from numeric part (SV029 -> SV29)
            # Match prefix (letters) + zeros + digits
            m = re.match(r"^([A-Za-z]*)(0+)([1-9][0-9]*)$", num)
            if m:
                # Keep prefix + digits (e.g. SV + 29)
                v1 = m.group(1) + m.group(3)
                if v1 != num:
                    variants.append(f'"{v1}"')
            
            # Construct OR query for number
            if len(variants) > 1:
                query_parts.append("(" + " OR ".join([f"number:{v}" for v in variants]) + ")")
            else:
                query_parts.append(f"number:{num}")
                
        q = " ".join(query_parts)

        headers = {}
        if self.api_key:
            headers["X-Api-Key"] = self.api_key

        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{self.base_url}/cards", params={"q": q, "pageSize": 20}, headers=headers)
            r.raise_for_status()
            data = r.json()

        cards = data.get("data", [])
        results: List[Candidate] = []
        for c in cards:
            name = c.get("name")
            set_info = c.get("set", {})
            set_name = set_info.get("name")
            set_code = set_info.get("id")
            number = c.get("number")
            images = c.get("images", {})
            image_url = images.get("small") or images.get("large")

            # Score basic similarity
            score = 0.0
            if detected.name and name:
                score = fuzz.token_set_ratio(detected.name, name) / 100.0
            # Boost for exact number
            if detected.number and number and str(detected.number) == str(number):
                score += 0.15
            # Boost for set name/code hints
            if detected.set and set_name and detected.set.lower() in set_name.lower():
                score += 0.1
            if detected.set_code and set_code and str(detected.set_code).lower() == str(set_code).lower():
                score += 0.1
            score = max(0.0, min(1.0, score))

            results.append(
                Candidate(
                    id=c.get("id"),
                    name=name,
                    set=set_name,
                    set_code=set_code,
                    number=number,
                    rarity=c.get("rarity"),
                    image=image_url,
                    score=score,
                )
            )

        # Sort by number exact match first, then score; keep top 12
        def _key(cand: Candidate):
            exact = 1 if (detected.number and cand.number and str(detected.number) == str(cand.number)) else 0
            return (exact, cand.score)
        results.sort(key=_key, reverse=True)
        return results[:12]  # Increased from 8 to 12 for better coverage

    async def details(self, card_id: str) -> dict:
        # Public details endpoint
        headers = {}
        if self.api_key:
            headers["X-Api-Key"] = self.api_key
        async with httpx.AsyncClient(timeout=12) as client:
            r = await client.get(f"{self.base_url}/cards/{card_id}", headers=headers)
            r.raise_for_status()
            data = r.json()
        # Normalize a bit
        return data.get("data") or data


class RapidAPITCGGOProvider(CardProvider):
    """RapidAPI provider for tcggopro / pokemon-tcg-api.

    Config via settings: rapidapi_key, rapidapi_host, tcggo_base_url, tcggo_search_path.
    """
    
    _set_abbr_map = None

    def _load_set_map(self):
        if self.__class__._set_abbr_map is not None:
            return

        mapping = {}
        try:
            # Check likely locations
            # 1. Current working directory
            # 2. Relative to this file (backend/app/../../tcg_sets.json)
            possible_paths = [
                "/app/tcg_sets.json",
                "tcg_sets.json",
                os.path.join(os.path.dirname(__file__), "../../tcg_sets.json"),
            ]
            
            found_path = None
            for p in possible_paths:
                if os.path.exists(p):
                    found_path = p
                    break
            
            if found_path:
                with open(found_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for group_sets in data.values():
                        for s in group_sets:
                            if "name" in s and "abbr" in s:
                                mapping[s["name"]] = s["abbr"]
                # print(f"DEBUG: Loaded {len(mapping)} set abbreviations from {found_path}")
            else:
                print(f"ERROR: tcg_sets.json not found for TCGGO provider. Checked paths: {possible_paths}")
        except Exception as e:
            print(f"ERROR: Failed to load tcg_sets.json: {e}")
        
        self.__class__._set_abbr_map = mapping

    def __init__(self):
        self._load_set_map()
        self.key = settings.rapidapi_key
        self.host = settings.rapidapi_host

        def _normalize_base(u: str | None) -> str:
            if not u:
                return ""
            s = str(u).strip()
            if not (s.startswith("http://") or s.startswith("https://")):
                s = "https://" + s.lstrip("/")
            return s.rstrip("/")

        def _normalize_path(p: str | None) -> str:
            if not p:
                return ""
            s = str(p).strip()
            if not s.startswith("/"):
                s = "/" + s
            return s

        self.base_url = _normalize_base(settings.tcggo_base_url)
        self.search_path = _normalize_path(settings.tcggo_search_path)
        self.search_search_path = _normalize_path(settings.tcggo_search_search_path)

    async def search(self, detected: DetectedData) -> List[Candidate]:
        if not detected.name:
            return []

        headers = {
            "x-rapidapi-key": self.key or "",
            "x-rapidapi-host": self.host,
        }

        # Prepare set information
        search_set = detected.set
        # 1. Handle "null" string
        if search_set and str(search_set).strip().lower() in ("null", "none"):
            search_set = None

        if search_set and self._set_abbr_map and search_set in self._set_abbr_map:
            abbr = self._set_abbr_map[search_set]
            print(f"DEBUG: Normalized set '{search_set}' to '{abbr}'")
            search_set = abbr

        # Define search tiers
        attempts = []
        
        # Helper to generate number variants
        num_variants = []
        if detected.number:
            import re
            n_orig = str(detected.number).strip()
            num_variants.append(n_orig)
            
            # Variant: Remove leading zeros (SV029 -> SV29)
            m = re.match(r"^([A-Za-z]*)(0+)([1-9][0-9]*)$", n_orig)
            short_num = None
            if m:
                short_num = m.group(1) + m.group(3)
                if short_num != n_orig:
                    num_variants.append(short_num)
            
            # Variant: Prefix with Set Code (User req: SV092 -> SHFSV092)
            if search_set:
                # Try {SetCode}{OriginalNumber} -> SHFSV092
                num_variants.append(f"{search_set}{n_orig}")
                # Try {SetCode}{ShortNumber} -> SHFSV29
                if short_num:
                    num_variants.append(f"{search_set}{short_num}")
        
        # Attempt 1: Specific (Name + Number + EPISODE:Set)
        if search_set:
            if num_variants:
                for nv in num_variants:
                    parts = [str(detected.name).strip(), nv, f"EPISODE:{str(search_set).strip()}"]
                    attempts.append((f"Attempt 1 (Specific: {nv})", " ".join(parts)))
            else:
                parts = [str(detected.name).strip(), f"EPISODE:{str(search_set).strip()}"]
                attempts.append(("Attempt 1 (Specific: No Num)", " ".join(parts)))

        # Attempt 2: Name + Number (without Set)
        if num_variants:
            for nv in num_variants:
                parts = [str(detected.name).strip(), nv]
                attempts.append((f"Attempt 2 (Name + {nv})", " ".join(parts)))

        # Attempt 3: Broad (Name only)
        attempts.append(("Attempt 3 (Broad)", str(detected.name).strip()))

        all_cards = []
        
        async with httpx.AsyncClient(timeout=12) as client:
            for label, query in attempts:
                if not query:
                    continue
                    
                print(f"DEBUG: Search {label}: '{query}'")
                try:
                    r = await client.get(
                        f"{self.base_url}{self.search_search_path}",
                        params={"search": query, "sort": settings.tcggo_sort},
                        headers=headers,
                    )
                    r.raise_for_status()
                    payload = r.json()
                except Exception as e:
                    print(f"DEBUG: Search {label} failed: {e}")
                    continue

                # Extract cards
                current_cards = []
                if isinstance(payload, list):
                    current_cards = payload
                elif isinstance(payload, dict):
                    current_cards = payload.get("data") or payload.get("cards") or payload.get("results") or []
                
                if current_cards:
                    print(f"DEBUG: Search {label} returned {len(current_cards)} results")
                    all_cards.extend(current_cards)
                    # If we found results with name+number (Attempt 1 or 2), stop searching
                    if detected.number and label in ["Attempt 1 (Specific)", "Attempt 2 (Name + Number)"]:
                        print(f"DEBUG: Stopping search - found results with name+number")
                        break
                else:
                    print(f"DEBUG: Search {label} returned 0 results")
        
        # Deduplicate by card ID (some attempts might return same cards)
        seen_ids = set()
        cards = []
        for card in all_cards:
            card_id = card.get("id")
            if card_id and card_id not in seen_ids:
                seen_ids.add(card_id)
                cards.append(card)
            elif not card_id:
                cards.append(card)  # Keep cards without ID

        results: List[Candidate] = []
        for c in cards or []:
            if not isinstance(c, dict):
                # Sometimes RapidAPI returns a list of IDs or strings; skip safely
                continue
            name = c.get("name")
            set_info = c.get("set") or {}
            set_name = set_info.get("name") or c.get("setName")
            set_code = set_info.get("id") or set_info.get("code") or c.get("setCode")
            number = c.get("number")
            images = c.get("images") or {}
            image_url = images.get("small") or images.get("large") or c.get("imageUrl") or c.get("image")

            # Score basic similarity
            score = 0.0
            if detected.name and name:
                score = fuzz.token_set_ratio(detected.name, name) / 100.0
            
            # Boost for exact number match
            if detected.number and number and str(detected.number) == str(number):
                score += 0.3  # Increased boost for number match
            
            # Boost for set name hints
            if detected.set and set_name:
                # Check for partial match (e.g. "Scarlet & Violet" in "Scarlet & Violet - Paldea Evolved")
                if detected.set.lower() in set_name.lower() or set_name.lower() in detected.set.lower():
                    score += 0.2
            
            # Boost for set code hints (Strong signal)
            if detected.set_code and set_code and str(detected.set_code).lower() == str(set_code).lower():
                score += 0.3

            # Penalize if number exists in detected but doesn't match candidate
            if detected.number and number and str(detected.number) != str(number):
                score -= 0.2

            score = max(0.0, min(1.0, score))

            # PENALTY: If we only matched by name (no number, no set hints confirmed), cap the score.
            # This prevents "Pikachu" from auto-selecting the first result (usually latest promo)
            # when we actually have no idea which Pikachu it is.
            is_name_only_match = (
                (not detected.number or str(detected.number) != str(number)) and 
                (not detected.set or not set_name or detected.set.lower() not in set_name.lower()) and
                (not detected.set_code or not set_code or str(detected.set_code).lower() != str(set_code).lower())
            )
            
            if is_name_only_match:
                # Cap at 0.45 so it's below the typical 0.5/0.6 auto-match threshold
                score = min(score, 0.45)
            
            score = max(0.0, min(1.0, score))

            cid = c.get("id") or c.get("tcgid") or c.get("slug") or name or "unknown"
            results.append(
                Candidate(
                    id=str(cid),
                    name=name or "",
                    set=set_name,
                    set_code=set_code,
                    number=number,
                    rarity=c.get("rarity"),
                    image=image_url,
                    score=score,
                )
            )

        # CRITICAL FILTER: If we detected a card number, ONLY show cards with exact number match
        # This prevents showing wrong cards (e.g. Pikachu #25 when we scanned Pikachu #123)
        # Also handles promo card numbers (SWSH092, SV092, etc.)
        if detected.number:
            def normalize_card_number(num):
                """Normalize card numbers for flexible matching.
                
                Handles cases like:
                - SWSH092 vs 092 (promo cards)
                - SV092 vs 92 (prefix variants)
                - 006 vs 6 (leading zeros)
                """
                if not num:
                    return None, None
                s = str(num).upper().strip()
                # Extract prefix (SWSH, SV, TG, GG, PR, SM, etc.)
                prefix = ''
                for p in ['SWSH', 'SV', 'TG', 'GG', 'PR', 'SM', 'XY', 'BW']:
                    if s.startswith(p):
                        prefix = p
                        s = s[len(p):]
                        break
                # Extract numeric part
                digits = ''.join(filter(str.isdigit, s))
                return prefix, digits
            
            detected_prefix, detected_digits = normalize_card_number(detected.number)
            exact_matches = []
            
            for c in results:
                c_prefix, c_digits = normalize_card_number(c.number)
                
                # Exact match (same prefix and digits)
                if detected_prefix == c_prefix and detected_digits == c_digits:
                    exact_matches.append(c)
                # Partial match (same digits, different or missing prefix)
                elif detected_digits and c_digits and detected_digits == c_digits:
                    # Accept if either has a promo prefix
                    if detected_prefix or c_prefix:
                        exact_matches.append(c)
            
            if exact_matches:
                print(f"DEBUG: Filtered to {len(exact_matches)} cards with number match: {detected.number} (digits: {detected_digits}, prefix: {detected_prefix or 'none'})")
                results = exact_matches
            else:
                print(f"WARNING: No exact number matches found for number {detected.number}, showing all {len(results)} results")
        
        # Prefer exact number match first, then score
        def _key(c: Candidate):
            exact = 1 if (detected.number and c.number and str(detected.number) == str(c.number)) else 0
            return (exact, c.score)
        results.sort(key=_key, reverse=True)
        return results[:12]  # Increased from 8 to 12 for better coverage

    async def details(self, card_id: str) -> dict:
        headers = {
            "x-rapidapi-key": self.key or "",
            "x-rapidapi-host": self.host,
        }
        async with httpx.AsyncClient(timeout=12) as client:
            r = await client.get(f"{self.base_url}{self.search_path}/{card_id}", headers=headers)
            r.raise_for_status()
            payload = r.json()
        # Accept direct or wrapped payloads
        return payload.get("data") or payload.get("card") or payload


def get_provider() -> CardProvider:
    # Prefer RapidAPI provider if key is set
    if settings.rapidapi_key:
        return RapidAPITCGGOProvider()
    return PokemonTCGProvider()
