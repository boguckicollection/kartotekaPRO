"""
Data mapper for transforming Shoper orders to Furgonetka API payloads.

This module handles the complex task of mapping Polish e-commerce order data
to the Furgonetka shipping API format, including:
- Address normalization (postcodes, phone numbers)
- Parcel locker ID extraction (InPost, Orlen, etc.)
- Service code mapping
- Package dimension estimation
- COD (Cash on Delivery) detection
"""

from __future__ import annotations

import json
import re
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from .settings import settings


def map_shoper_order_to_furgonetka(order: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform Shoper order data to Furgonetka API payload.
    
    Args:
        order: Full order dict from Shoper API (with delivery_address, user, products, etc.)
    
    Returns:
        Complete Furgonetka API payload ready for POST /packages
    
    Raises:
        ValueError: If required data is missing or service mapping is not configured
    
    Example:
        >>> order = await shoper_client.fetch_order_detail(12345)
        >>> payload = map_shoper_order_to_furgonetka(order)
        >>> response = await furgonetka_client.create_shipment(payload)
    """
    
    # 1. Extract receiver data
    delivery = order.get("delivery_address") or {}
    user = order.get("user") or {}
    
    # Determine if recipient is a company
    is_company = bool(delivery.get("company"))
    
    receiver = {
        "type": "company" if is_company else "private",
        "name": _get_receiver_name(delivery, user),
        "street": delivery.get("street", ""),
        "city": delivery.get("city", ""),
        "postcode": _normalize_postcode(delivery.get("postcode", "")),
        "phone": _normalize_phone(delivery.get("phone", "") or user.get("phone", "")),
        "email": delivery.get("email", "") or user.get("email", "")
    }
    
    if is_company:
        receiver["company"] = delivery.get("company")
    
    # 2. Determine carrier service
    delivery_method = order.get("delivery", {}) or order.get("delivery_method", {})
    delivery_method_id = str(delivery_method.get("id", ""))
    
    service_code = _get_service_code(delivery_method_id)
    
    # 3. Extract Parcel Locker/PUDO ID (if applicable)
    parcel_locker_id = _extract_parcel_locker_id(order, service_code)
    
    if parcel_locker_id:
        # For PUDO deliveries, recipient address is the locker location
        receiver["point"] = parcel_locker_id
        # Clear street/city/postcode as they're not needed for PUDO
        receiver["street"] = ""
        receiver["city"] = ""
        receiver["postcode"] = ""
    
    # 4. Calculate package dimensions
    items = order.get("products") or order.get("items") or order.get("order_products") or []
    parcels = _estimate_parcels(items)
    
    # 5. Detect payment method and services
    payment_method = order.get("payment", {}) or order.get("payment_method", {})
    is_cod = _is_cash_on_delivery(payment_method)
    
    services = {}
    
    if is_cod:
        total = float(order.get("sum", 0) or order.get("total", 0) or order.get("total_gross", 0))
        services["cod"] = {
            "amount": round(total, 2),
            "currency": "PLN"
        }
    
    # Always add insurance for shipment protection
    total_value = float(order.get("sum", 0) or order.get("total", 0) or order.get("total_gross", 0))
    if total_value > 0:
        services["insurance"] = {"amount": round(total_value, 2)}
    
    # 6. Build final payload
    payload = {
        "package": {
            "type": "package",
            "service": service_code,
            "user_reference_number": f"Zamówienie #{order.get('id') or order.get('order_id')}",
            "ref": f"#{order.get('id') or order.get('order_id')}",
            "send_date": _get_next_business_day(),
            "receiver": receiver,
            "sender": {
                "name": settings.furgonetka_sender_name,
                "street": settings.furgonetka_sender_street,
                "city": settings.furgonetka_sender_city,
                "postcode": settings.furgonetka_sender_postcode,
                "phone": settings.furgonetka_sender_phone,
                "email": settings.furgonetka_sender_email
            },
            "parcels": parcels,
            "services": services,
            "pickup": {"type": "courier"}  # or "dropoff" if you take packages to post office
        }
    }
    
    return payload


def _get_receiver_name(delivery: Dict[str, Any], user: Dict[str, Any]) -> str:
    """
    Extract receiver name from delivery address or user data.
    
    Args:
        delivery: delivery_address object
        user: user object
    
    Returns:
        Full name (firstname + lastname) or email username as fallback
    """
    firstname = delivery.get("firstname", "") or user.get("firstname", "")
    lastname = delivery.get("lastname", "") or user.get("lastname", "")
    
    name = f"{firstname} {lastname}".strip()
    
    if not name:
        # Fallback to email username
        email = delivery.get("email", "") or user.get("email", "")
        if email and "@" in email:
            name = email.split("@")[0]
        else:
            name = "Klient"  # Ultimate fallback
    
    return name


def _normalize_postcode(postcode: str) -> str:
    """
    Format Polish postcode to XX-XXX format required by Furgonetka API.
    
    Args:
        postcode: Raw postcode (may be "00123", "00-123", "00 123", etc.)
    
    Returns:
        Formatted postcode in XX-XXX format
    
    Examples:
        >>> _normalize_postcode("00123")
        "00-123"
        >>> _normalize_postcode("00-123")
        "00-123"
        >>> _normalize_postcode("invalid")
        "invalid"
    """
    # Remove all non-digit characters
    cleaned = re.sub(r'[^\d]', '', postcode)
    
    # If exactly 5 digits, format as XX-XXX
    if len(cleaned) == 5:
        return f"{cleaned[:2]}-{cleaned[2:]}"
    
    # Return as-is if not valid (API will reject it with 422)
    return postcode


def _normalize_phone(phone: str) -> str:
    """
    Normalize Polish phone number by removing international prefix and formatting.
    
    Args:
        phone: Raw phone number ("+48 501 502 503", "48501502503", "501-502-503", etc.)
    
    Returns:
        9-digit phone number without spaces or hyphens
    
    Examples:
        >>> _normalize_phone("+48 501 502 503")
        "501502503"
        >>> _normalize_phone("48501502503")
        "501502503"
    """
    # Remove all non-digit characters
    cleaned = re.sub(r'[^\d]', '', phone)
    
    # Remove international prefix if present
    if cleaned.startswith('48') and len(cleaned) == 11:
        cleaned = cleaned[2:]
    
    return cleaned


def _get_service_code(delivery_method_id: str) -> str:
    """
    Map Shoper delivery method ID to Furgonetka service code.
    
    Args:
        delivery_method_id: Delivery method ID from Shoper
    
    Returns:
        Furgonetka service code (e.g., "inpost", "dpd", "dhl")
    
    Raises:
        ValueError: If service mapping is not configured or ID not found
    """
    if not settings.furgonetka_service_map:
        raise ValueError(
            "FURGONETKA_SERVICE_MAP not configured. "
            "Please set it in .env as JSON: {\"15\": \"inpost\", \"16\": \"dpd_pickup\", ...}"
        )
    
    try:
        service_map = json.loads(settings.furgonetka_service_map)
    except json.JSONDecodeError:
        raise ValueError(f"Invalid FURGONETKA_SERVICE_MAP JSON: {settings.furgonetka_service_map}")
    
    service_code = service_map.get(str(delivery_method_id))
    
    if not service_code:
        raise ValueError(
            f"Unknown delivery method ID: {delivery_method_id}. "
            f"Available mappings: {list(service_map.keys())}"
        )
    
    return service_code


def _extract_parcel_locker_id(order: Dict[str, Any], service_code: str) -> Optional[str]:
    """
    Extract Paczkomat/PUDO ID from order data.
    
    This is the most complex part of the mapping. Shoper stores parcel locker IDs
    in different places depending on the integration and configuration:
    - delivery_address.additional_info
    - order.comment (customer comment)
    - delivery_method.parcel_locker_id (custom field)
    - order.notes (admin notes)
    
    Args:
        order: Full Shoper order dict
        service_code: Furgonetka service code to determine ID format
    
    Returns:
        Parcel locker ID (e.g., "WAW22A", "106088") or None if not applicable/found
    
    Note:
        You MUST test this with a real Shoper order to see where the ID is stored!
        The regex patterns below are generic and may need adjustment.
    """
    
    # Only relevant for PUDO services
    if service_code not in ["inpost", "orlen", "dpd_pickup", "poczta_pickup", "dhl_pickup"]:
        return None
    
    # Collect all text fields where ID might be hiding
    search_fields = []
    
    delivery = order.get("delivery_address") or {}
    search_fields.append(delivery.get("additional_info", ""))
    search_fields.append(delivery.get("address2", ""))  # Some Shoper configs use address2
    search_fields.append(order.get("comment", ""))
    search_fields.append(order.get("notes", ""))
    search_fields.append(order.get("admin_comments", ""))
    
    # Also check if there's a direct field (some plugins add this)
    direct_id = order.get("parcel_locker_id") or order.get("paczkomat_id") or order.get("point_id")
    if direct_id:
        return str(direct_id)
    
    # Try to extract ID based on service type
    combined_text = " ".join(str(f) for f in search_fields if f)
    
    if service_code == "inpost":
        # InPost Paczkomat pattern: 3 letters + 2 digits + 1 letter (e.g., WAW22A, KRA01N)
        match = re.search(r'\b([A-Z]{3}\d{2}[A-Z])\b', combined_text)
        if match:
            return match.group(1)
    
    elif service_code == "orlen":
        # Orlen Paczka pattern: 6 digits (e.g., 106088)
        match = re.search(r'\b(\d{6})\b', combined_text)
        if match:
            return match.group(1)
    
    elif service_code in ["dpd_pickup", "poczta_pickup"]:
        # DPD Pickup / Poczta Polska: Often alphanumeric with prefix
        # DPD example: PL11033
        match = re.search(r'\b(PL\d{5})\b', combined_text)
        if match:
            return match.group(1)
        
        # Poczta Polska: Usually numeric PNI
        match = re.search(r'\b(PNI\d{4,6})\b', combined_text)
        if match:
            return match.group(1)
    
    # If we reach here, we couldn't find the ID
    # This is not necessarily an error - maybe it's a regular courier delivery
    return None


def _estimate_parcels(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Estimate parcel dimensions based on order items.
    
    For Pokemon cards, most orders fit in a small package.
    This is a simplified estimation - you may want to refine based on your packaging logic.
    
    Args:
        items: List of order items/products
    
    Returns:
        List of parcel dicts with dimensions (cm) and weight (kg)
    
    Note:
        Furgonetka validates dimensions against carrier limits!
        - InPost Paczkomat: max 41x38x64 cm, 25 kg
        - DPD: max 100x60x60 cm, 31.5 kg
    """
    # Calculate total quantity
    total_qty = 0
    for item in items:
        qty = item.get("quantity") or item.get("qty") or item.get("count") or 1
        try:
            total_qty += int(qty)
        except (ValueError, TypeError):
            total_qty += 1
    
    # Simple logic: 1 parcel for most orders, split if > 100 cards
    # Adjust these dimensions based on your actual packaging
    
    if total_qty <= 100:
        # Single small parcel
        return [{
            "width": 20,   # cm
            "height": 15,  # cm
            "length": 10,  # cm
            "weight": 0.5  # kg
        }]
    elif total_qty <= 300:
        # Medium parcel or 2 small parcels
        return [{
            "width": 30,
            "height": 20,
            "length": 15,
            "weight": 1.5
        }]
    else:
        # Large order - split into multiple parcels
        return [
            {"width": 30, "height": 20, "length": 15, "weight": 1.5},
            {"width": 30, "height": 20, "length": 15, "weight": 1.5}
        ]


def _is_cash_on_delivery(payment_method: Dict[str, Any]) -> bool:
    """
    Detect if payment method is Cash on Delivery (COD).
    
    Args:
        payment_method: Payment method object from order
    
    Returns:
        True if this is a COD order
    
    Note:
        Detection is based on payment method name containing "pobranie" or "cod".
        Adjust if your Shoper uses different naming.
    """
    method_name = payment_method.get("name", "") or payment_method.get("type", "")
    method_name_lower = str(method_name).lower()
    
    # Common Polish names for COD
    cod_keywords = ["pobranie", "pobraniem", "cod", "za pobraniem", "przy odbiorze"]
    
    for keyword in cod_keywords:
        if keyword in method_name_lower:
            return True
    
    return False


def _get_next_business_day() -> str:
    """
    Get next business day (skip Sundays) in YYYY-MM-DD format.
    
    Furgonetka requires send_date to be a future date.
    We default to tomorrow, unless tomorrow is Sunday.
    
    Returns:
        Date string in YYYY-MM-DD format
    
    Note:
        This doesn't account for Polish holidays. For production,
        you may want to integrate with a holiday calendar API.
    """
    tomorrow = datetime.now() + timedelta(days=1)
    
    # Skip Sunday (weekday 6)
    while tomorrow.weekday() == 6:
        tomorrow += timedelta(days=1)
    
    return tomorrow.strftime("%Y-%m-%d")


def validate_sender_config() -> bool:
    """
    Check if sender configuration is complete.
    
    Returns:
        True if all required sender fields are configured
    
    Raises:
        ValueError: If critical sender fields are missing
    """
    required_fields = {
        "name": settings.furgonetka_sender_name,
        "street": settings.furgonetka_sender_street,
        "city": settings.furgonetka_sender_city,
        "postcode": settings.furgonetka_sender_postcode,
        "phone": settings.furgonetka_sender_phone,
        "email": settings.furgonetka_sender_email
    }
    
    missing = [field for field, value in required_fields.items() if not value]
    
    if missing:
        raise ValueError(
            f"Furgonetka sender configuration incomplete. Missing fields: {', '.join(missing)}. "
            f"Please set FURGONETKA_SENDER_* environment variables."
        )
    
    return True
