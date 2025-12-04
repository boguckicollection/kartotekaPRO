from __future__ import annotations

from typing import Any, Dict, Optional, Tuple, List

from .settings import settings


def _norm(s: Optional[str]) -> str:
    return (str(s or "").strip().lower())


def _pick_cardmarket_variant(cm: Dict[str, Any], preferred: Optional[str]) -> Tuple[Optional[float], str]:
    v = _norm(preferred)
    keys: List[str] = []

    if "reverse" in v:
        keys = ["reverseHoloAvg7", "reverseHolo7", "reverseHolo7d", "reverse_holo_7d_average", "reverseHoloTrend"]
    elif any(k in v for k in ["holo", "foil"]):
        keys = ["holofoilAvg7", "holofoil7", "holofoil7d", "holo_7d_average", "holofoilTrend"]
    elif v == "": # Explicitly check for normal to avoid matching holo/reverse
        keys = ["avg7", "7d_average", "avg7d", "seven_day_average", "trendPrice"]

    for k in keys:
        if cm.get(k) is not None:
            try:
                return float(cm.get(k)), k
            except Exception:
                continue
    return None, ""


def _pick_tcgplayer_variant(tcg: Dict[str, Any], preferred: Optional[str]) -> Tuple[Optional[float], str]:
    v = _norm(preferred)
    prices = tcg.get("prices") or {}
    # map pools
    if "reverse" in v:
        node = prices.get("reverseHolofoil") or {}
        val = node.get("market") or node.get("mid")
        return (float(val), "reverseHolofoil.market") if val is not None else (None, "")
    if any(k in v for k in ["holo", "foil"]) and "reverse" not in v:
        node = prices.get("holofoil") or {}
        val = node.get("market") or node.get("mid")
        return (float(val), "holofoil.market") if val is not None else (None, "")
    node = prices.get("normal") or {}
    val = node.get("market") or node.get("mid")
    return (float(val), "normal.market") if val is not None else (None, "")


def extract_prices_from_payload(payload: Dict[str, Any], preferred_variant: Optional[str] = None) -> Dict[str, Any]:
    prices = payload.get("prices") or {}
    # Cardmarket style
    cardmarket = prices.get("cardmarket") or payload.get("cardmarket") or {}
    # TCGplayer style
    tcg = payload.get("tcgplayer") or {}
    graded = payload.get("graded") or {}
    psa = graded.get("psa") or {}

    cm_val, cm_key = _pick_cardmarket_variant(cardmarket, preferred_variant)
    currency = cardmarket.get("currency") or "EUR"
    tcg_val, tcg_key = _pick_tcgplayer_variant(tcg, preferred_variant)

    # Prefer Cardmarket, fallback TCGplayer (converted from USD to EUR? skipping for now)
    seven_day = cm_val if cm_val is not None else tcg_val

    return {
        "cardmarket_currency": currency,
        "cardmarket_7d_average": seven_day,
        "source_key": cm_key or tcg_key,
        "graded_psa10": psa.get("psa10"),
        "graded_currency": graded.get("currency") or currency,
        "cardmarket_prices": cardmarket,  # Return all CM prices
    }


def compute_price_pln(cardmarket_avg_eur: Optional[float]) -> Dict[str, Optional[float]]:
    if not cardmarket_avg_eur:
        return {"price_pln": None, "price_pln_final": None}
    try:
        rate = float(settings.eur_pln_rate)
        base = float(cardmarket_avg_eur) * rate
        final = base * float(settings.price_multiplier)
        # Round to 2 decimals
        return {
            "price_pln": round(base, 2),
            "price_pln_final": round(final, 2),
        }
    except Exception:
        return {"price_pln": None, "price_pln_final": None}


def list_variant_prices(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    prices = payload.get("prices") or {}
    cardmarket = prices.get("cardmarket") or payload.get("cardmarket") or {}
    out: List[Dict[str, Any]] = []

    def _emit(label: str, val: Optional[float], source: str, estimated: bool = False):
        if val is None:
            return
        comp = compute_price_pln(val)
        out.append({
            "label": label,
            "base_eur": val,
            "price_pln": comp.get("price_pln"),
            "price_pln_final": comp.get("price_pln_final"),
            "source_key": source,
            "estimated": estimated,
        })

    # Get all variant prices, which can be None
    rev_price, rev_key = _pick_cardmarket_variant(cardmarket, "reverse holo")
    holo_price, holo_key = _pick_cardmarket_variant(cardmarket, "holo")
    norm_price, norm_key = _pick_cardmarket_variant(cardmarket, "")

    # Emit Normal price first
    if norm_price is not None:
        _emit("Normal", norm_price, norm_key or "cardmarket.normal")

    # Emit Holo, with estimation if needed
    if norm_price is not None:
        if holo_price is not None:
            _emit("Holo", holo_price, holo_key or "cardmarket.holofoil")
        else:
            _emit("Holo", norm_price * 3.0, norm_key or "cardmarket.holofoil", estimated=True)

    # Emit Reverse Holo, with estimation if needed
    if norm_price is not None:
        if rev_price is not None:
            _emit("Reverse Holo", rev_price, rev_key or "cardmarket.reverseHolo")
        else:
            _emit("Reverse Holo", norm_price * 2.0, norm_key or "cardmarket.reverseHolo", estimated=True)

    # Deduplicate by label keeping first occurrence
    seen = set()
    uniq: List[Dict[str, Any]] = []
    for it in out:
        if it["label"] in seen:
            continue
        seen.add(it["label"])
        uniq.append(it)
    return uniq
