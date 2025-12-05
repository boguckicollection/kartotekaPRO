"""FastAPI routes for Auction management."""

from __future__ import annotations
from fastapi import APIRouter, HTTPException, Depends, Query, WebSocket, UploadFile, File
from sqlalchemy.orm import Session as DBSession
from sqlalchemy import desc, and_, or_, func
from datetime import datetime, timedelta
from typing import List, Optional
import logging
import shutil
import os
import uuid
from pathlib import Path

from .db import SessionLocal, Auction, AuctionBid, KartotekaUser, Product, CardCatalog
from .auction_schemas import (
    AuctionCreate, AuctionUpdate, AuctionRead, AuctionDetail, 
    AuctionList, BidCreate, BidRead, AuctionStats, KartotekaUserSync,
    KartotekaUserRead
)
from .websocket import manager
from .settings import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auctions", tags=["Auctions"])


# ========== Dependencies ==========

def get_db():
    """Database session dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ========== WebSocket Endpoint ==========

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except Exception:
        manager.disconnect(websocket)


# ========== Helper Functions ==========

def calculate_auction_fields(auction: Auction) -> dict:
    """Calculate computed fields for auction response."""
    now = datetime.utcnow()
    
    # Time remaining in seconds
    time_remaining = None
    if auction.end_time > now:
        time_remaining = int((auction.end_time - now).total_seconds())
    
    # Is auction active
    is_active = (
        auction.status == "active" and
        auction.start_time <= now <= auction.end_time
    )
    
    return {
        "time_remaining": time_remaining,
        "is_active": is_active,
    }


def sync_kartoteka_user(db: DBSession, kartoteka_user_id: int, username: str = None) -> KartotekaUser:
    """Sync or create Kartoteka App user in local cache."""
    user = db.query(KartotekaUser).filter(
        KartotekaUser.kartoteka_user_id == kartoteka_user_id
    ).first()
    
    if not user:
        user = KartotekaUser(
            kartoteka_user_id=kartoteka_user_id,
            username=username or f"User_{kartoteka_user_id}",
            is_active=True,
            synced_at=datetime.utcnow()
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info(f"Created cached user for kartoteka_user_id={kartoteka_user_id}")
    elif username and user.username != username:
        # Update username if changed
        user.username = username
        user.synced_at = datetime.utcnow()
        db.commit()
    
    return user


# ========== Auction CRUD Endpoints ==========

@router.post("/", response_model=AuctionRead, status_code=201)
def create_auction(
    auction_data: AuctionCreate,
    db: DBSession = Depends(get_db)
):
    """
    Create a new auction (Admin only).
    
    - **title**: Auction title
    - **start_price**: Starting price in PLN
    - **end_time**: When auction ends (UTC)
    - **product_id** or **catalog_id**: Link to existing product/card
    """
    # Validate time range
    if auction_data.end_time <= auction_data.start_time:
        raise HTTPException(status_code=400, detail="end_time must be after start_time")
    
    if auction_data.end_time <= datetime.utcnow():
        raise HTTPException(status_code=400, detail="end_time must be in the future")
    
    # Validate product or catalog exists
    if auction_data.product_id:
        product = db.query(Product).filter(Product.id == auction_data.product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
    
    if auction_data.catalog_id:
        catalog = db.query(CardCatalog).filter(CardCatalog.id == auction_data.catalog_id).first()
        if not catalog:
            raise HTTPException(status_code=404, detail="Card catalog entry not found")
    
    # Create auction
    auction = Auction(
        product_id=auction_data.product_id,
        catalog_id=auction_data.catalog_id,
        title=auction_data.title,
        description=auction_data.description,
        image_url=auction_data.image_url,
        start_price=auction_data.start_price,
        current_price=auction_data.start_price,  # Initial = start price
        min_increment=auction_data.min_increment,
        buyout_price=auction_data.buyout_price,
        start_time=auction_data.start_time,
        end_time=auction_data.end_time,
        status=auction_data.status,
        auto_publish_to_shoper=auction_data.auto_publish_to_shoper,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    db.add(auction)
    db.commit()
    db.refresh(auction)
    
    logger.info(f"Created auction #{auction.id}: {auction.title}")
    
    # Add computed fields
    response_data = AuctionRead.from_orm(auction)
    computed = calculate_auction_fields(auction)
    response_data.time_remaining = computed["time_remaining"]
    response_data.is_active = computed["is_active"]
    response_data.bid_count = 0
    
    return response_data


@router.get("/", response_model=AuctionList)
def list_auctions(
    status: Optional[str] = Query(None, description="Filter by status: draft, active, ended, cancelled"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    db: DBSession = Depends(get_db)
):
    """
    Get list of auctions with pagination.
    
    - **status**: Filter by status (optional)
    - **page**: Page number (default: 1)
    - **per_page**: Items per page (default: 20, max: 100)
    """
    query = db.query(Auction)
    
    # Filter by status
    if status:
        query = query.filter(Auction.status == status)
    
    # Order by end_time (soonest first for active, newest first for others)
    if status == "active":
        query = query.order_by(Auction.end_time.asc())
    else:
        query = query.order_by(desc(Auction.created_at))
    
    # Get total count
    total = query.count()
    
    # Pagination
    offset = (page - 1) * per_page
    auctions = query.offset(offset).limit(per_page).all()
    
    # Add computed fields and bid counts
    items = []
    for auction in auctions:
        bid_count = db.query(func.count(AuctionBid.id)).filter(
            AuctionBid.auction_id == auction.id
        ).scalar()
        
        auction_data = AuctionRead.from_orm(auction)
        computed = calculate_auction_fields(auction)
        auction_data.time_remaining = computed["time_remaining"]
        auction_data.is_active = computed["is_active"]
        auction_data.bid_count = bid_count
        
        items.append(auction_data)
    
    return AuctionList(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        has_next=(page * per_page) < total,
        has_prev=page > 1
    )


@router.get("/{auction_id}", response_model=AuctionDetail)
def get_auction(
    auction_id: int,
    db: DBSession = Depends(get_db)
):
    """Get auction details with all bids."""
    auction = db.query(Auction).filter(Auction.id == auction_id).first()
    
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")
    
    # Get all bids
    bids = db.query(AuctionBid).filter(
        AuctionBid.auction_id == auction_id
    ).order_by(desc(AuctionBid.timestamp)).all()
    
    # Get product/card name
    product_name = None
    card_name = None
    
    if auction.product_id:
        product = db.query(Product).filter(Product.id == auction.product_id).first()
        if product:
            product_name = product.name
    
    if auction.catalog_id:
        card = db.query(CardCatalog).filter(CardCatalog.id == auction.catalog_id).first()
        if card:
            card_name = card.name
    
    # Build response
    auction_data = AuctionDetail.from_orm(auction)
    auction_data.bids = [BidRead.from_orm(bid) for bid in bids]
    auction_data.product_name = product_name
    auction_data.card_name = card_name
    
    computed = calculate_auction_fields(auction)
    auction_data.time_remaining = computed["time_remaining"]
    auction_data.is_active = computed["is_active"]
    auction_data.bid_count = len(bids)
    
    return auction_data


@router.put("/{auction_id}", response_model=AuctionRead)
def update_auction(
    auction_id: int,
    auction_data: AuctionUpdate,
    db: DBSession = Depends(get_db)
):
    """Update auction details (Admin only)."""
    auction = db.query(Auction).filter(Auction.id == auction_id).first()
    
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")
    
    # Cannot update ended/cancelled auctions
    if auction.status in ["ended", "cancelled"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot update {auction.status} auction"
        )
    
    # Update fields
    update_data = auction_data.dict(exclude_unset=True)
    
    # Validate time changes
    if "end_time" in update_data or "start_time" in update_data:
        new_start = update_data.get("start_time", auction.start_time)
        new_end = update_data.get("end_time", auction.end_time)
        
        if new_end <= new_start:
            raise HTTPException(status_code=400, detail="end_time must be after start_time")
    
    for key, value in update_data.items():
        setattr(auction, key, value)
    
    auction.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(auction)
    
    logger.info(f"Updated auction #{auction_id}")
    
    # Build response
    response_data = AuctionRead.from_orm(auction)
    computed = calculate_auction_fields(auction)
    response_data.time_remaining = computed["time_remaining"]
    response_data.is_active = computed["is_active"]
    
    bid_count = db.query(func.count(AuctionBid.id)).filter(
        AuctionBid.auction_id == auction.id
    ).scalar()
    response_data.bid_count = bid_count
    
    return response_data


@router.delete("/{auction_id}", status_code=204)
def delete_auction(
    auction_id: int,
    db: DBSession = Depends(get_db)
):
    """Delete auction (Admin only). Only draft auctions can be deleted."""
    auction = db.query(Auction).filter(Auction.id == auction_id).first()
    
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")
    
    # Only allow deleting draft auctions
    if auction.status != "draft":
        raise HTTPException(
            status_code=400,
            detail="Only draft auctions can be deleted. Cancel instead."
        )
    
    db.delete(auction)
    db.commit()
    
    logger.info(f"Deleted auction #{auction_id}")
    return None


@router.post("/{auction_id}/cancel", response_model=AuctionRead)
def cancel_auction(
    auction_id: int,
    db: DBSession = Depends(get_db)
):
    """Cancel an active auction (Admin only)."""
    auction = db.query(Auction).filter(Auction.id == auction_id).first()
    
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")
    
    if auction.status in ["ended", "cancelled"]:
        raise HTTPException(
            status_code=400,
            detail=f"Auction is already {auction.status}"
        )
    
    auction.status = "cancelled"
    auction.updated_at = datetime.utcnow()
    auction.ended_at = datetime.utcnow()
    
    db.commit()
    db.refresh(auction)
    
    logger.info(f"Cancelled auction #{auction_id}")
    
    # Build response
    response_data = AuctionRead.from_orm(auction)
    computed = calculate_auction_fields(auction)
    response_data.time_remaining = computed["time_remaining"]
    response_data.is_active = computed["is_active"]
    
    bid_count = db.query(func.count(AuctionBid.id)).filter(
        AuctionBid.auction_id == auction.id
    ).scalar()
    response_data.bid_count = bid_count
    
    return response_data


# ========== Bidding Endpoints ==========

@router.post("/{auction_id}/bids", response_model=BidRead, status_code=201)
async def place_bid(
    auction_id: int,
    bid_data: BidCreate,
    db: DBSession = Depends(get_db)
):
    """
    Place a bid on an auction (Kartoteka App users).
    
    - **amount**: Bid amount in PLN
    - **kartoteka_user_id**: User ID from Kartoteka App
    - **username**: Username for display (optional)
    """
    auction = db.query(Auction).filter(Auction.id == auction_id).first()
    
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")
    
    # Validate auction is active
    now = datetime.utcnow()
    
    if auction.status != "active":
        raise HTTPException(status_code=400, detail=f"Auction is {auction.status}")
    
    if now < auction.start_time:
        raise HTTPException(status_code=400, detail="Auction has not started yet")
    
    if now > auction.end_time:
        raise HTTPException(status_code=400, detail="Auction has ended")
    
    # Check buyout price
    if auction.buyout_price and bid_data.amount >= auction.buyout_price:
        # Instant buyout
        bid = AuctionBid(
            auction_id=auction_id,
            kartoteka_user_id=bid_data.kartoteka_user_id,
            username=bid_data.username,
            amount=bid_data.amount,
            timestamp=datetime.utcnow()
        )
        db.add(bid)
        
        # End auction immediately
        auction.status = "ended"
        auction.current_price = bid_data.amount
        auction.winner_kartoteka_user_id = bid_data.kartoteka_user_id
        auction.ended_at = datetime.utcnow()
        auction.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(bid)
        
        logger.info(f"Auction #{auction_id} won by buyout: {bid_data.amount} PLN")
        
        # Broadcast WebSocket update
        await manager.broadcast({
            "type": "auction_ended",
            "auction_id": auction_id,
            "winner_id": bid_data.kartoteka_user_id,
            "price": bid_data.amount,
            "reason": "buyout"
        })
        
        return BidRead.from_orm(bid)
    
    # Validate bid amount
    min_bid = auction.current_price + auction.min_increment
    
    if bid_data.amount < min_bid:
        raise HTTPException(
            status_code=400,
            detail=f"Bid must be at least {min_bid:.2f} PLN (current price + min increment)"
        )
    
    # Create bid
    bid = AuctionBid(
        auction_id=auction_id,
        kartoteka_user_id=bid_data.kartoteka_user_id,
        username=bid_data.username,
        amount=bid_data.amount,
        timestamp=datetime.utcnow()
    )
    
    db.add(bid)
    
    # Update auction current price
    auction.current_price = bid_data.amount
    auction.updated_at = datetime.utcnow()
    
    # Sync user to cache
    sync_kartoteka_user(db, bid_data.kartoteka_user_id, bid_data.username)
    
    db.commit()
    db.refresh(bid)
    
    logger.info(f"New bid on auction #{auction_id}: {bid_data.amount} PLN by user {bid_data.kartoteka_user_id}")
    
    # Broadcast WebSocket update
    await manager.broadcast({
        "type": "new_bid",
        "auction_id": auction_id,
        "amount": bid_data.amount,
        "user_id": bid_data.kartoteka_user_id,
        "username": bid_data.username
    })
    
    return BidRead.from_orm(bid)


@router.get("/{auction_id}/bids", response_model=List[BidRead])
def get_auction_bids(
    auction_id: int,
    db: DBSession = Depends(get_db)
):
    """Get all bids for an auction, ordered by timestamp (newest first)."""
    auction = db.query(Auction).filter(Auction.id == auction_id).first()
    
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")
    
    bids = db.query(AuctionBid).filter(
        AuctionBid.auction_id == auction_id
    ).order_by(desc(AuctionBid.timestamp)).all()
    
    return [BidRead.from_orm(bid) for bid in bids]


# ========== Statistics ==========

@router.post("/upload", response_model=dict, status_code=201)
async def upload_auction_image(file: UploadFile = File(...)):
    """Upload an image for an auction."""
    try:
        # Create upload directory if not exists
        upload_dir = Path(settings.upload_dir) / "auctions"
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate unique filename
        file_ext = file.filename.split(".")[-1] if "." in file.filename else "jpg"
        filename = f"{uuid.uuid4()}.{file_ext}"
        file_path = upload_dir / filename
        
        # Save file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Return URL
        return {"url": f"/uploads/auctions/{filename}"}
    except Exception as e:
        logger.error(f"Failed to upload auction image: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload image")


@router.get("/stats/overview", response_model=AuctionStats)
def get_auction_stats(db: DBSession = Depends(get_db)):
    """Get auction statistics for admin dashboard."""
    total_auctions = db.query(func.count(Auction.id)).scalar()
    
    active_auctions = db.query(func.count(Auction.id)).filter(
        Auction.status == "active"
    ).scalar()
    
    ended_auctions = db.query(func.count(Auction.id)).filter(
        Auction.status == "ended"
    ).scalar()
    
    total_bids = db.query(func.count(AuctionBid.id)).scalar()
    
    # Total value of ended auctions
    total_value = db.query(func.sum(Auction.current_price)).filter(
        Auction.status == "ended"
    ).scalar() or 0.0
    
    # Average bids per auction
    avg_bids = total_bids / total_auctions if total_auctions > 0 else 0.0
    
    return AuctionStats(
        total_auctions=total_auctions,
        active_auctions=active_auctions,
        ended_auctions=ended_auctions,
        total_bids=total_bids,
        total_value=float(total_value),
        avg_bids_per_auction=avg_bids
    )


# ========== User Sync Endpoint ==========

@router.post("/sync-user", response_model=dict, status_code=201)
def sync_user(
    user_data: KartotekaUserSync,
    db: DBSession = Depends(get_db)
):
    """Sync a Kartoteka App user to local cache (called by Kartoteka App)."""
    user = sync_kartoteka_user(
        db,
        user_data.kartoteka_user_id,
        user_data.username
    )
    
    return {
        "status": "ok",
        "user_id": user.id,
        "kartoteka_user_id": user.kartoteka_user_id,
        "username": user.username
    }


# ========== User List Endpoint ==========

@router.get("/users", response_model=List[KartotekaUserRead])
def list_users(db: DBSession = Depends(get_db)):
    """
    Get list of cached Kartoteka App users with auction statistics.
    """
    users = db.query(KartotekaUser).order_by(desc(KartotekaUser.synced_at)).all()
    
    result = []
    for user in users:
        # Calculate stats
        total_bids = db.query(func.count(AuctionBid.id)).filter(
            AuctionBid.kartoteka_user_id == user.kartoteka_user_id
        ).scalar()
        
        won_auctions = db.query(func.count(Auction.id)).filter(
            Auction.winner_kartoteka_user_id == user.kartoteka_user_id,
            Auction.status == "ended"
        ).scalar()
        
        # Sum of final prices for won auctions
        total_spent = db.query(func.sum(Auction.current_price)).filter(
            Auction.winner_kartoteka_user_id == user.kartoteka_user_id,
            Auction.status == "ended"
        ).scalar() or 0.0
        
        user_data = KartotekaUserRead.from_orm(user)
        user_data.total_bids = total_bids
        user_data.won_auctions = won_auctions
        user_data.total_spent = float(total_spent)
        
        result.append(user_data)
        
    return result
