"""
FastAPI endpoints for Furgonetka shipping integration.

These endpoints handle:
- OAuth 2.0 authorization flow
- Shipment creation and management
- Label download (PDF/ZPL)
- Shipment listing and status tracking
"""

from __future__ import annotations

import json
import time
from typing import Optional

from fastapi import APIRouter, Body, Query
from fastapi.responses import JSONResponse, StreamingResponse
import httpx

from .settings import settings
from .db import SessionLocal, FurgonetkaShipment, FurgonetkaToken
from .furgonetka_client import FurgonetkaClient
from .furgonetka_mapper import map_shoper_order_to_furgonetka, validate_sender_config
from .shoper import ShoperClient


# Create router for Furgonetka endpoints
router = APIRouter(prefix="/furgonetka", tags=["Furgonetka Shipping"])


@router.get("/oauth/authorize")
async def furgonetka_oauth_start():
    """
    Step 1 of OAuth flow: Generate authorization URL.
    
    Returns a URL that the user must visit to authorize the application.
    After authorization, they will be redirected back to the callback endpoint.
    """
    if not settings.furgonetka_client_id or not settings.furgonetka_client_secret:
        return JSONResponse({
            "error": "Furgonetka not configured",
            "detail": "Please set FURGONETKA_CLIENT_ID and FURGONETKA_CLIENT_SECRET in .env"
        }, status_code=400)
    
    client = FurgonetkaClient()
    auth_url = client.get_authorization_url()
    
    return {
        "authorization_url": auth_url,
        "instructions": "Please visit the URL above to authorize this application with Furgonetka."
    }


@router.get("/oauth/callback")
async def furgonetka_oauth_callback(code: str):
    """
    Step 2 of OAuth flow: Handle authorization callback.
    
    This endpoint is called by Furgonetka after user authorization.
    It exchanges the authorization code for access and refresh tokens.
    
    Query Parameters:
        code: Authorization code from Furgonetka
    """
    if not code:
        return JSONResponse({
            "error": "Missing authorization code"
        }, status_code=400)
    
    try:
        client = FurgonetkaClient()
        token_data = await client.exchange_code_for_tokens(code)
        
        return {
            "message": "✅ Authorization successful! You can now create shipments.",
            "expires_in": token_data.get("expires_in", 2592000),
            "expires_in_days": int(token_data.get("expires_in", 2592000) / 86400),
            "sandbox_mode": settings.furgonetka_sandbox_mode
        }
    
    except httpx.HTTPStatusError as e:
        error_detail = e.response.text if e.response else str(e)
        return JSONResponse({
            "error": "Token exchange failed",
            "detail": error_detail,
            "status_code": e.response.status_code if e.response else 500
        }, status_code=400)
    except Exception as e:
        return JSONResponse({
            "error": "Internal error",
            "detail": str(e)
        }, status_code=500)


@router.post("/shipments")
async def create_furgonetka_shipment(
    order_id: int = Body(..., embed=True, description="Shoper order ID")
):
    """
    Create a Furgonetka shipment for a Shoper order.
    
    This endpoint:
    1. Fetches order details from Shoper
    2. Transforms data to Furgonetka format
    3. Validates shipment data
    4. Creates shipment in Furgonetka
    5. Stores shipment reference in database
    
    Request Body:
        {
            "order_id": 12345
        }
    
    Returns:
        {
            "message": "Shipment created successfully",
            "shipment_id": 1,
            "package_id": "PKG123456",
            "tracking_number": "ABC123",
            "label_url": "/furgonetka/shipments/1/label"
        }
    """
    # Check configuration
    if not settings.shoper_base_url or not settings.shoper_access_token:
        return JSONResponse({
            "error": "Shoper API not configured",
            "detail": "Please set SHOPER_BASE_URL and SHOPER_ACCESS_TOKEN"
        }, status_code=400)
    
    if not settings.furgonetka_client_id or not settings.furgonetka_client_secret:
        return JSONResponse({
            "error": "Furgonetka API not configured",
            "detail": "Please set FURGONETKA_CLIENT_ID and FURGONETKA_CLIENT_SECRET"
        }, status_code=400)
    
    # Validate sender configuration
    try:
        validate_sender_config()
    except ValueError as e:
        return JSONResponse({
            "error": "Sender configuration incomplete",
            "detail": str(e)
        }, status_code=400)
    
    db = SessionLocal()
    try:
        # 1. Check if shipment already exists for this order
        existing = db.query(FurgonetkaShipment).filter(
            FurgonetkaShipment.order_id == order_id
        ).first()
        
        if existing and existing.package_id:
            return JSONResponse({
                "error": "Shipment already exists for this order",
                "shipment_id": existing.id,
                "package_id": existing.package_id,
                "status": existing.status,
                "created_at": existing.created_at.isoformat() if existing.created_at else None
            }, status_code=409)
        
        # 2. Fetch order from Shoper
        shoper_client = ShoperClient(settings.shoper_base_url, settings.shoper_access_token)
        order = await shoper_client.fetch_order_detail(order_id)
        
        if not order:
            return JSONResponse({
                "error": "Order not found in Shoper",
                "order_id": order_id
            }, status_code=404)
        
        # 3. Transform to Furgonetka format
        try:
            payload = map_shoper_order_to_furgonetka(order)
        except ValueError as e:
            return JSONResponse({
                "error": "Data mapping failed",
                "detail": str(e),
                "hint": "Check FURGONETKA_SERVICE_MAP configuration"
            }, status_code=400)
        except Exception as e:
            return JSONResponse({
                "error": "Unexpected mapping error",
                "detail": str(e)
            }, status_code=500)
        
        # 4. Validate with Furgonetka API (optional but recommended)
        furgon_client = FurgonetkaClient()
        validation = await furgon_client.validate_shipment(payload)
        
        if validation.get("errors"):
            return JSONResponse({
                "error": "Shipment validation failed",
                "validation_errors": validation["errors"],
                "hint": "Please fix the errors and try again"
            }, status_code=422)
        
        # 5. Create shipment
        response = await furgon_client.create_shipment(payload)
        
        # 6. Save to database
        shipment = FurgonetkaShipment(
            order_id=order_id,
            shoper_order_number=f"#{order_id}",
            package_id=response.get("package_id") or response.get("id"),
            tracking_number=response.get("tracking_number") or response.get("waybill"),
            carrier_service=payload["package"]["service"],
            status="created",
            request_payload=json.dumps(payload),
            response_payload=json.dumps(response),
            label_url=response.get("label_url") or response.get("documents", {}).get("label")
        )
        db.add(shipment)
        db.commit()
        db.refresh(shipment)
        
        return {
            "message": "✅ Shipment created successfully!",
            "shipment_id": shipment.id,
            "package_id": shipment.package_id,
            "tracking_number": shipment.tracking_number,
            "carrier": shipment.carrier_service,
            "label_url": f"/api/furgonetka/shipments/{shipment.id}/label",
            "created_at": shipment.created_at.isoformat()
        }
    
    except httpx.HTTPStatusError as e:
        error_detail = e.response.text if e.response else str(e)
        error_json = None
        try:
            error_json = e.response.json() if e.response else None
        except:
            pass
        
        return JSONResponse({
            "error": "Furgonetka API error",
            "status_code": e.response.status_code if e.response else 500,
            "detail": error_detail,
            "errors": error_json.get("errors") if error_json else None
        }, status_code=e.response.status_code if e.response else 500)
    
    except RuntimeError as e:
        # OAuth token issues
        return JSONResponse({
            "error": "Authorization error",
            "detail": str(e),
            "hint": "Please re-authorize via /furgonetka/oauth/authorize"
        }, status_code=401)
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({
            "error": "Internal server error",
            "detail": str(e)
        }, status_code=500)
    
    finally:
        db.close()


@router.get("/shipments/{shipment_id}/label")
async def get_furgonetka_label(
    shipment_id: int,
    format: str = Query("pdf", regex="^(pdf|zpl)$", description="Label format: pdf or zpl")
):
    """
    Download shipment label in PDF or ZPL format.
    
    Path Parameters:
        shipment_id: Shipment ID from database
    
    Query Parameters:
        format: Label format - "pdf" (default) or "zpl"
    
    Returns:
        PDF or ZPL file as downloadable attachment
    """
    db = SessionLocal()
    try:
        shipment = db.get(FurgonetkaShipment, shipment_id)
        
        if not shipment:
            return JSONResponse({
                "error": "Shipment not found",
                "shipment_id": shipment_id
            }, status_code=404)
        
        if not shipment.package_id:
            return JSONResponse({
                "error": "Shipment has no package ID",
                "detail": "This shipment may not have been created successfully"
            }, status_code=400)
        
        # Download label from Furgonetka
        furgon_client = FurgonetkaClient()
        label_bytes = await furgon_client.get_label(shipment.package_id, format=format)
        
        # Update shipment status
        shipment.status = "label_downloaded"
        shipment.label_format = format
        shipment.label_downloaded_at = db.query(FurgonetkaShipment).filter(
            FurgonetkaShipment.id == shipment_id
        ).first().created_at  # Use current time
        db.commit()
        
        # Return as downloadable file
        content_type = "application/pdf" if format == "pdf" else "text/plain"
        filename = f"etykieta_#{shipment.order_id}_{shipment.package_id}.{format}"
        
        return StreamingResponse(
            iter([label_bytes]),
            media_type=content_type,
            headers={
                "Content-Disposition": f'inline; filename="{filename}"',
                "Content-Length": str(len(label_bytes))
            }
        )
    
    except httpx.HTTPStatusError as e:
        error_detail = e.response.text if e.response else str(e)
        return JSONResponse({
            "error": "Failed to download label",
            "status_code": e.response.status_code if e.response else 500,
            "detail": error_detail
        }, status_code=e.response.status_code if e.response else 500)
    
    except RuntimeError as e:
        return JSONResponse({
            "error": "Authorization error",
            "detail": str(e),
            "hint": "Please re-authorize via /furgonetka/oauth/authorize"
        }, status_code=401)
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({
            "error": "Internal server error",
            "detail": str(e)
        }, status_code=500)
    
    finally:
        db.close()


@router.get("/shipments")
async def list_furgonetka_shipments(
    order_id: Optional[int] = Query(None, description="Filter by Shoper order ID"),
    limit: int = Query(50, ge=1, le=100, description="Number of results")
):
    """
    List all shipments with optional filtering.
    
    Query Parameters:
        order_id: Filter by specific Shoper order ID (optional)
        limit: Maximum number of results (default: 50, max: 100)
    
    Returns:
        List of shipments with details
    """
    db = SessionLocal()
    try:
        query = db.query(FurgonetkaShipment)
        
        if order_id:
            query = query.filter(FurgonetkaShipment.order_id == order_id)
        
        shipments = query.order_by(
            FurgonetkaShipment.created_at.desc()
        ).limit(limit).all()
        
        return [
            {
                "id": s.id,
                "order_id": s.order_id,
                "order_number": s.shoper_order_number,
                "package_id": s.package_id,
                "tracking_number": s.tracking_number,
                "carrier": s.carrier_service,
                "status": s.status,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "label_url": f"/api/furgonetka/shipments/{s.id}/label" if s.package_id else None,
                "label_format": s.label_format
            }
            for s in shipments
        ]
    
    finally:
        db.close()



@router.get("/shipments/sync/{order_id}")
async def sync_shipment_from_furgonetka(order_id: int):
    """
    Sync shipment data from Furgonetka for given Shoper order.
    
    This endpoint:
    1. Searches for package in Furgonetka by order reference
    2. If found, saves to local database
    3. Returns status (ready, pending, not_found)
    
    Use case: Background polling when loading orders list
    """
    db = SessionLocal()
    try:
        # 1. Check if already synced
        existing = db.query(FurgonetkaShipment).filter(
            FurgonetkaShipment.order_id == order_id
        ).first()
        
        if existing and existing.package_id:
            return {
                "status": "ready",
                "shipment_id": existing.id,
                "package_id": existing.package_id,
                "synced_at": existing.created_at.isoformat() if existing.created_at else None
            }
        
        # 2. Search in Furgonetka
        client = FurgonetkaClient()
        package = await client.find_package_by_reference(f"#{order_id}")
        
        if not package:
            # Przesyłka jeszcze nie została zaimportowana przez Furgonetka
            return {
                "status": "pending_import",
                "message": "Oczekiwanie na import przez Furgonetka (5-15 min)",
                "order_id": order_id
            }
        
        # 3. Save to database
        if existing:
            # Update existing record
            existing.package_id = package.get("id") or package.get("package_id")
            existing.tracking_number = package.get("tracking_number")
            existing.carrier_service = package.get("service")
            existing.status = "synced"
            existing.response_payload = json.dumps(package)
            shipment = existing
        else:
            # Create new record
            shipment = FurgonetkaShipment(
                order_id=order_id,
                shoper_order_number=f"#{order_id}",
                package_id=package.get("id") or package.get("package_id"),
                tracking_number=package.get("tracking_number"),
                carrier_service=package.get("service"),
                status="synced",
                response_payload=json.dumps(package)
            )
            db.add(shipment)
        
        db.commit()
        db.refresh(shipment)
        
        return {
            "status": "ready",
            "shipment_id": shipment.id,
            "package_id": shipment.package_id,
            "tracking_number": shipment.tracking_number,
            "carrier": shipment.carrier_service,
            "label_url": f"/api/furgonetka/shipments/{shipment.id}/label"
        }
    
    except RuntimeError as e:
        return JSONResponse({
            "status": "error",
            "error": "Authorization error",
            "detail": str(e)
        }, status_code=401)
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({
            "status": "error",
            "error": str(e)
        }, status_code=500)
    
    finally:
        db.close()


@router.post("/shipments/sync/batch")
async def sync_multiple_shipments(
    order_ids: list[int] = Body(..., description="List of Shoper order IDs")
):
    """
    Sync multiple shipments in batch.
    
    Used when loading orders list - syncs all new orders at once.
    """
    results = []
    
    for order_id in order_ids[:50]:  # Limit to 50 to avoid timeout
        try:
            result = await sync_shipment_from_furgonetka(order_id)
            # Extract JSON from JSONResponse if needed
            if isinstance(result, JSONResponse):
                # If error response, treat as error status
                import json as _json
                result = _json.loads(result.body.decode())
            results.append({
                "order_id": order_id,
                **result
            })
        except Exception as e:
            results.append({
                "order_id": order_id,
                "status": "error",
                "error": str(e)
            })
    
    # Summary
    summary = {
        "total": len(results),
        "ready": sum(1 for r in results if r.get("status") == "ready"),
        "pending": sum(1 for r in results if r.get("status") == "pending_import"),
        "errors": sum(1 for r in results if r.get("status") == "error")
    }
    
    return {
        "summary": summary,
        "results": results
    }


@router.get("/status")
async def furgonetka_status():
    """
    Check Furgonetka integration status.
    
    Returns configuration status and token validity.
    """
    db = SessionLocal()
    try:
        # Check configuration
        config_ok = all([
            settings.furgonetka_client_id,
            settings.furgonetka_client_secret,
            settings.furgonetka_sender_name,
            settings.furgonetka_sender_street,
            settings.furgonetka_sender_city
        ])
        
        # Check token
        token_row = db.query(FurgonetkaToken).first()
        token_ok = False
        token_expires_in = None
        
        if token_row:
            token_ok = time.time() < token_row.expires_at
            token_expires_in = int(token_row.expires_at - time.time())
        
        # Check service mapping
        service_map_ok = bool(settings.furgonetka_service_map)
        
        return {
            "configured": config_ok,
            "authorized": token_ok,
            "token_expires_in_seconds": token_expires_in if token_ok else None,
            "token_expires_in_days": int(token_expires_in / 86400) if token_expires_in else None,
            "service_mapping_configured": service_map_ok,
            "sandbox_mode": settings.furgonetka_sandbox_mode,
            "api_url": settings.furgonetka_base_url,
            "ready": config_ok and token_ok and service_map_ok
        }
    
    finally:
        db.close()
