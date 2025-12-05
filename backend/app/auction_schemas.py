"""Pydantic schemas for Auction API endpoints."""

from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ========== Auction Schemas ==========

class AuctionBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="Auction title")
    description: Optional[str] = Field(None, description="Auction description")
    image_url: Optional[str] = Field(None, description="Image URL")
    start_price: float = Field(..., gt=0, description="Starting price in PLN")
    min_increment: float = Field(1.0, gt=0, description="Minimum bid increment")
    buyout_price: Optional[float] = Field(None, gt=0, description="Instant buyout price")
    start_time: datetime = Field(..., description="Auction start time (UTC)")
    end_time: datetime = Field(..., description="Auction end time (UTC)")
    auto_publish_to_shoper: bool = Field(False, description="Auto-publish to Shoper after auction ends")


class AuctionCreate(AuctionBase):
    """Schema for creating a new auction (admin only)."""
    product_id: Optional[int] = Field(None, description="Existing product ID (if already in shop)")
    catalog_id: Optional[int] = Field(None, description="Card catalog ID")
    status: str = Field("draft", description="Initial status: draft, active")


class AuctionUpdate(BaseModel):
    """Schema for updating auction (admin only)."""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    image_url: Optional[str] = None
    start_price: Optional[float] = Field(None, gt=0)
    min_increment: Optional[float] = Field(None, gt=0)
    buyout_price: Optional[float] = Field(None, gt=0)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: Optional[str] = Field(None, description="draft, active, ended, cancelled")
    auto_publish_to_shoper: Optional[bool] = None


class BidCreate(BaseModel):
    """Schema for placing a bid."""
    amount: float = Field(..., gt=0, description="Bid amount in PLN")
    kartoteka_user_id: int = Field(..., description="User ID from Kartoteka App")
    username: Optional[str] = Field(None, description="Username for display")


class BidRead(BaseModel):
    """Schema for bid response."""
    id: int
    auction_id: int
    kartoteka_user_id: int
    username: Optional[str]
    amount: float
    timestamp: datetime

    class Config:
        from_attributes = True


class AuctionRead(AuctionBase):
    """Schema for auction response."""
    id: int
    product_id: Optional[int]
    catalog_id: Optional[int]
    current_price: float
    status: str
    winner_kartoteka_user_id: Optional[int]
    published_shoper_id: Optional[int]
    created_at: datetime
    updated_at: datetime
    ended_at: Optional[datetime]
    
    # Additional computed fields
    bid_count: Optional[int] = Field(None, description="Total number of bids")
    time_remaining: Optional[int] = Field(None, description="Seconds until auction ends")
    is_active: Optional[bool] = Field(None, description="Is auction currently active")
    
    class Config:
        from_attributes = True


class AuctionDetail(AuctionRead):
    """Detailed auction with bids."""
    bids: List[BidRead] = []
    messages: List[MessageRead] = []
    product_name: Optional[str] = None
    card_name: Optional[str] = None
    # Card details for info popup
    card_set: Optional[str] = None
    card_number: Optional[str] = None
    card_price_market: Optional[float] = None
    card_price_psa: Optional[float] = None


class AuctionList(BaseModel):
    """Paginated list of auctions."""
    items: List[AuctionRead]
    total: int
    page: int
    per_page: int
    has_next: bool
    has_prev: bool


class AuctionStats(BaseModel):
    """Statistics for auction dashboard."""
    total_auctions: int
    active_auctions: int
    ended_auctions: int
    total_bids: int
    total_value: float  # Sum of all final prices
    avg_bids_per_auction: float


# ========== Kartoteka User Sync ==========

class KartotekaUserSync(BaseModel):
    """Schema for syncing user from Kartoteka App."""
    kartoteka_user_id: int
    username: str
    email: Optional[str] = None
    is_active: bool = True


class KartotekaUserRead(BaseModel):
    """Schema for reading Kartoteka User (with auction stats)."""
    id: int
    kartoteka_user_id: int
    username: str
    is_active: bool
    synced_at: datetime
    
    # Stats
    total_bids: int = 0
    won_auctions: int = 0
    total_spent: float = 0.0
    
    class Config:
        from_attributes = True


# ========== Message Schemas ==========

class MessageCreate(BaseModel):
    """Schema for sending a chat message."""
    message: str = Field(..., min_length=1, max_length=1000)
    kartoteka_user_id: Optional[int] = None # If None, sent as system/admin
    username: str


class MessageRead(BaseModel):
    """Schema for reading a chat message."""
    id: int
    auction_id: int
    kartoteka_user_id: Optional[int]
    username: str
    message: str
    timestamp: datetime

    class Config:
        from_attributes = True
