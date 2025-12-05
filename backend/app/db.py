from __future__ import annotations

from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, ForeignKey, DateTime, Text, event
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.engine import Engine

from .settings import settings


connect_args = {}
if settings.database_url.startswith("sqlite"):
    # Allow usage across threads and increase lock wait timeout
    connect_args = {"check_same_thread": False, "timeout": 15}

engine: Engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    future=True,
    pool_pre_ping=True,
)

if settings.database_url.startswith("sqlite"):
    # Apply SQLite pragmas for better concurrency
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):  # type: ignore
        try:
            cursor = dbapi_connection.cursor()
            # Use DELETE mode instead of WAL to avoid permission issues
            cursor.execute("PRAGMA journal_mode=DELETE")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()
        except Exception:
            pass
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)
Base = declarative_base()


class Scan(Base):
    __tablename__ = "scans"
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    filename = Column(String(255), nullable=True)
    stored_path = Column(Text, nullable=True)
    stored_path_back = Column(Text, nullable=True)
    message = Column(Text, nullable=True)

    detected_name = Column(String(255), nullable=True)
    detected_set = Column(String(255), nullable=True)
    detected_set_code = Column(String(64), nullable=True)
    detected_number = Column(String(64), nullable=True)
    detected_language = Column(String(64), nullable=True)
    detected_variant = Column(String(64), nullable=True)
    detected_condition = Column(String(64), nullable=True)
    detected_rarity = Column(String(64), nullable=True)
    detected_energy = Column(String(64), nullable=True)
    detected_payload = Column(Text, nullable=True)

    # Product publishing preferences
    use_tcggo_image = Column(Boolean, default=True, nullable=True)  # True = TCGGO, False = local scan
    additional_images = Column(Text, nullable=True)  # JSON array of file paths
    warehouse_code = Column(String(64), nullable=True, index=True)  # K1K1P001 format

    selected_candidate_id = Column(Integer, ForeignKey("scan_candidates.id"), nullable=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=True, index=True)
    catalog_id = Column(Integer, ForeignKey("card_catalog.id"), nullable=True, index=True)  # Link to CardCatalog
    publish_status = Column(String(32), nullable=True)  # pending, published, failed
    published_shoper_id = Column(Integer, nullable=True)
    published_at = Column(DateTime, nullable=True)

    # Pricing fields
    cardmarket_currency = Column(String(8), nullable=True)
    cardmarket_7d_average = Column(Float, nullable=True)
    price_pln = Column(Float, nullable=True)
    price_pln_final = Column(Float, nullable=True)
    purchase_price = Column(Float, nullable=True)
    graded_psa10 = Column(Float, nullable=True)
    graded_currency = Column(String(8), nullable=True)

    candidates = relationship(
        "ScanCandidate",
        back_populates="scan",
        foreign_keys=lambda: [ScanCandidate.scan_id],
        primaryjoin=lambda: Scan.id == ScanCandidate.scan_id,
        cascade="all, delete-orphan",
    )
    selected_candidate = relationship(
        "ScanCandidate",
        foreign_keys=[selected_candidate_id],
        post_update=True,
        uselist=False,
    )


class ScanCandidate(Base):
    __tablename__ = "scan_candidates"
    id = Column(Integer, primary_key=True, index=True)
    scan_id = Column(Integer, ForeignKey("scans.id", ondelete="CASCADE"), nullable=False, index=True)
    provider_id = Column(String(128), nullable=False)
    name = Column(String(255), nullable=False)
    set = Column(String(255), nullable=True)
    set_code = Column(String(64), nullable=True)
    number = Column(String(64), nullable=True)
    rarity = Column(String(128), nullable=True)
    image = Column(Text, nullable=True)
    score = Column(Float, nullable=False, default=0.0)
    chosen = Column(Boolean, default=False, nullable=False)

    scan = relationship(
        "Scan",
        back_populates="candidates",
        foreign_keys=[scan_id],
        primaryjoin=lambda: Scan.id == ScanCandidate.scan_id,
    )


class Session(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    status = Column(String(32), default="open", nullable=False)
    starting_warehouse_code = Column(String(64), nullable=True)


class InventoryItem(Base):
    __tablename__ = "inventory"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=True)
    number = Column(String(64), nullable=True)
    set = Column(String(255), nullable=True)
    warehouse_code = Column(String(64), nullable=True, index=True)
    price = Column(Float, nullable=True)
    purchase_price = Column(Float, nullable=True)
    image = Column(Text, nullable=True)
    variant = Column(String(64), nullable=True)
    sold = Column(Integer, nullable=True)
    added_at = Column(String(32), nullable=True)


class CardCatalog(Base):
    """
    Catalog of unique cards - each card type exists once here.
    Contains reference data and cached prices from TCGGO/Cardmarket.
    """
    __tablename__ = "card_catalog"
    id = Column(Integer, primary_key=True)
    
    # Unique identifier from provider (e.g., "base1-4" from TCGGO)
    provider_id = Column(String(128), unique=True, index=True, nullable=False)
    
    # Card identification
    name = Column(String(255), nullable=False)
    set_name = Column(String(255), nullable=True)
    set_code = Column(String(64), index=True, nullable=True)
    number = Column(String(64), nullable=True)
    rarity = Column(String(128), nullable=True)
    energy = Column(String(64), nullable=True)  # Card energy type (Fire, Water, etc.)
    
    # Reference image from provider
    image_url = Column(Text, nullable=True)
    
    # Cached prices in EUR from Cardmarket/TCGGO
    price_normal_eur = Column(Float, nullable=True)
    price_holo_eur = Column(Float, nullable=True)
    price_reverse_eur = Column(Float, nullable=True)
    prices_updated_at = Column(DateTime, nullable=True)
    
    # Full API payload (JSON) for future use
    api_payload = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class Fingerprint(Base):
    """
    Visual fingerprints for duplicate detection based on image similarity.
    """
    __tablename__ = "fingerprints"
    id = Column(Integer, primary_key=True)
    scan_id = Column(Integer, ForeignKey("scans.id", ondelete="CASCADE"), index=True, nullable=False)
    catalog_id = Column(Integer, ForeignKey("card_catalog.id"), index=True, nullable=True)  # Link to catalog entry
    phash = Column(Text, nullable=False)
    dhash = Column(Text, nullable=False)
    tile_phash = Column(Text, nullable=False)
    orb = Column(Text, nullable=True)
    meta = Column(Text, nullable=True)


class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    shoper_id = Column(Integer, unique=True, index=True, nullable=False)
    code = Column(String(128), nullable=True)
    name = Column(String(255), nullable=True)
    price = Column(Float, nullable=True)
    purchase_price = Column(Float, nullable=True)
    stock = Column(Integer, nullable=True)
    image = Column(Text, nullable=True)
    updated_at = Column(DateTime, nullable=True)
    catalog_id = Column(Integer, ForeignKey("card_catalog.id"), nullable=True, index=True)  # Link to CardCatalog
    finish = Column(String(32), nullable=True)  # normal, holo, reverse - for price updates
    price_locked = Column(Boolean, default=False, nullable=True)  # If True, don't auto-update price
    tcggo_id = Column(String(128), nullable=True)
    fingerprint_hash = Column(Text, nullable=True)
    last_price_update = Column(DateTime, nullable=True)
    # Extra metadata from Shoper
    category_id = Column(Integer, nullable=True)
    categories = Column(Text, nullable=True)  # JSON or comma-separated
    producer_id = Column(Integer, nullable=True)
    tax_id = Column(Integer, nullable=True)
    permalink = Column(Text, nullable=True)
    main_image_gfx_id = Column(String(64), nullable=True)
    main_image_extension = Column(String(16), nullable=True)
    main_image_unic_name = Column(String(64), nullable=True)

class PriceHistory(Base):
    __tablename__ = "price_history"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    price = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    product = relationship("Product")


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"
    id = Column(Integer, primary_key=True, index=True)
    subscription_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class BatchScan(Base):
    """
    Batch scan session for processing multiple card images at once.
    """
    __tablename__ = "batch_scans"
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    status = Column(String(32), default="pending", nullable=False)  # pending, processing, completed, failed
    total_items = Column(Integer, default=0, nullable=False)
    processed_items = Column(Integer, default=0, nullable=False)
    successful_items = Column(Integer, default=0, nullable=False)
    failed_items = Column(Integer, default=0, nullable=False)
    current_filename = Column(String(255), nullable=True)
    error_message = Column(Text, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Session integration for warehouse codes
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=True, index=True)
    starting_warehouse_code = Column(String(64), nullable=True)
    
    items = relationship("BatchScanItem", back_populates="batch", cascade="all, delete-orphan")


class BatchScanItem(Base):
    """
    Individual item in a batch scan - represents one card image.
    Contains all fields needed for full card analysis like single scan.
    """
    __tablename__ = "batch_scan_items"
    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("batch_scans.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Original file info
    filename = Column(String(255), nullable=False)
    stored_path = Column(Text, nullable=True)
    
    # Processing status
    status = Column(String(32), default="pending", nullable=False)  # pending, processing, success, failed, skipped
    error_message = Column(Text, nullable=True)
    processed_at = Column(DateTime, nullable=True)
    
    # Detected card info (from Vision/OCR)
    detected_name = Column(String(255), nullable=True)
    detected_set = Column(String(255), nullable=True)
    detected_set_code = Column(String(64), nullable=True)
    detected_number = Column(String(64), nullable=True)
    detected_language = Column(String(64), nullable=True)
    detected_variant = Column(String(64), nullable=True)
    detected_condition = Column(String(64), nullable=True)
    detected_rarity = Column(String(128), nullable=True)
    detected_energy = Column(String(64), nullable=True)
    
    # Matched card from TCGGO/provider
    matched_provider_id = Column(String(128), nullable=True)
    matched_name = Column(String(255), nullable=True)
    matched_set = Column(String(255), nullable=True)
    matched_set_code = Column(String(64), nullable=True)
    matched_number = Column(String(64), nullable=True)
    matched_rarity = Column(String(128), nullable=True)
    matched_image = Column(Text, nullable=True)
    match_score = Column(Float, nullable=True)
    
    # All candidates from search (JSON array)
    candidates_json = Column(Text, nullable=True)
    
    # Pricing (full pricing data)
    price_eur = Column(Float, nullable=True)
    price_pln = Column(Float, nullable=True)
    price_pln_final = Column(Float, nullable=True)
    purchase_price = Column(Float, nullable=True)
    # Variant prices (JSON: {"normal": {"eur": 1.5, "pln": 7.5}, "holo": {...}, "reverse": {...}})
    variants_json = Column(Text, nullable=True)
    
    # Duplicate detection
    duplicate_of_scan_id = Column(Integer, nullable=True)
    duplicate_distance = Column(Integer, nullable=True)
    catalog_id = Column(Integer, nullable=True)
    
    # Shoper attributes (mapped option IDs)
    attr_language = Column(String(16), nullable=True)  # option_id for language
    attr_condition = Column(String(16), nullable=True)  # option_id for condition
    attr_finish = Column(String(16), nullable=True)  # option_id for finish/variant
    attr_rarity = Column(String(16), nullable=True)  # option_id for rarity
    attr_energy = Column(String(16), nullable=True)  # option_id for energy
    attr_card_type = Column(String(16), nullable=True)  # option_id for card type
    
    # Image selection
    use_tcggo_image = Column(Boolean, default=True, nullable=True)
    additional_images_json = Column(Text, nullable=True)  # JSON array of stored image paths
    
    # Completeness tracking (JSON with field status)
    fields_status = Column(Text, nullable=True)  # JSON: {"name": true, "set": true, "number": false, ...}
    fields_complete = Column(Integer, default=0, nullable=True)
    fields_total = Column(Integer, default=7, nullable=True)
    
    # Publishing
    publish_status = Column(String(32), nullable=True)  # pending, published, failed
    published_shoper_id = Column(Integer, nullable=True)
    warehouse_code = Column(String(64), nullable=True)
    cardmarket_url = Column(Text, nullable=True)
    
    batch = relationship("BatchScan", back_populates="items")


class FurgonetkaToken(Base):
    """
    OAuth tokens for Furgonetka API integration.
    Stores access and refresh tokens with expiration tracking.
    """
    __tablename__ = "furgonetka_tokens"
    id = Column(Integer, primary_key=True)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=False)
    expires_at = Column(Float, nullable=False)  # Unix timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class FurgonetkaShipment(Base):
    """
    Tracking table for shipments created via Furgonetka API.
    Links Shoper orders to Furgonetka packages and stores label information.
    """
    __tablename__ = "furgonetka_shipments"
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Links to system
    order_id = Column(Integer, nullable=False, index=True)  # Shoper order ID
    shoper_order_number = Column(String(64), nullable=True)  # Display format: #12345
    
    # Furgonetka data
    package_id = Column(String(128), nullable=True, unique=True, index=True)  # From API response
    tracking_number = Column(String(128), nullable=True)
    carrier_service = Column(String(32), nullable=True)  # inpost, dpd, dhl, orlen, etc.
    
    # Status tracking
    status = Column(String(32), default="pending", nullable=False)  # pending, created, label_downloaded, error
    error_message = Column(Text, nullable=True)
    
    # Label storage
    label_format = Column(String(10), default="pdf", nullable=True)  # pdf, zpl
    label_url = Column(Text, nullable=True)  # URL from Furgonetka API
    label_path = Column(Text, nullable=True)  # Local cached copy (optional)
    label_downloaded_at = Column(DateTime, nullable=True)
    
    # Request/Response payloads (for debugging and audit)
    request_payload = Column(Text, nullable=True)  # JSON
    response_payload = Column(Text, nullable=True)  # JSON


# ========== AUCTIONS & BIDS (Integration with Kartoteka App) ==========

class KartotekaUser(Base):
    """
    Cache table for users from Kartoteka App (port 8001).
    Used for auction bids and winner tracking.
    Synced from kartoteka.db via API.
    """
    __tablename__ = "kartoteka_users"
    id = Column(Integer, primary_key=True, index=True)
    kartoteka_user_id = Column(Integer, unique=True, nullable=False, index=True)  # ID from kartoteka.db
    username = Column(String(255), nullable=False, index=True)
    email = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    synced_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Auction(Base):
    """
    Auction for Pokemon cards or sealed products.
    Managed from admin panel, visible in Kartoteka App.
    """
    __tablename__ = "auctions"
    id = Column(Integer, primary_key=True, index=True)
    
    # Link to existing product in shop (if already in Shoper)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True, index=True)
    
    # Or link to catalog entry
    catalog_id = Column(Integer, ForeignKey("card_catalog.id"), nullable=True, index=True)
    
    # Auction details
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    image_url = Column(Text, nullable=True)
    
    # Pricing
    start_price = Column(Float, nullable=False)
    current_price = Column(Float, nullable=False)
    min_increment = Column(Float, default=1.0, nullable=False)
    buyout_price = Column(Float, nullable=True)  # Optional instant buy price
    
    # Timing
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime, nullable=False, index=True)
    
    # Status: draft, active, ended, cancelled, sold
    status = Column(String(32), default="draft", nullable=False, index=True)
    
    # Winner (from Kartoteka App users)
    winner_kartoteka_user_id = Column(Integer, nullable=True)
    
    # Shoper integration
    auto_publish_to_shoper = Column(Boolean, default=False, nullable=False)
    published_shoper_id = Column(Integer, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    
    # Relationships
    product = relationship("Product", foreign_keys=[product_id])
    catalog = relationship("CardCatalog", foreign_keys=[catalog_id])
    bids = relationship("AuctionBid", back_populates="auction", cascade="all, delete-orphan")
    messages = relationship("AuctionMessage", back_populates="auction", cascade="all, delete-orphan")


class AuctionBid(Base):
    """
    Bid placed on an auction by a Kartoteka App user.
    """
    __tablename__ = "auction_bids"
    id = Column(Integer, primary_key=True, index=True)
    
    auction_id = Column(Integer, ForeignKey("auctions.id", ondelete="CASCADE"), nullable=False, index=True)
    kartoteka_user_id = Column(Integer, nullable=False, index=True)  # ID from kartoteka.db
    
    amount = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # User info snapshot (for display if Kartoteka App is offline)
    username = Column(String(255), nullable=True)
    
    # Relationships
    auction = relationship("Auction", back_populates="bids")


class AuctionMessage(Base):
    """
    Chat message in an auction room.
    """
    __tablename__ = "auction_messages"
    id = Column(Integer, primary_key=True, index=True)
    
    auction_id = Column(Integer, ForeignKey("auctions.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Message sender
    kartoteka_user_id = Column(Integer, nullable=True) # If None, it's a system/admin message
    username = Column(String(255), nullable=False)
    
    message = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    auction = relationship("Auction", back_populates="messages")


def init_db():
    Base.metadata.create_all(bind=engine)
    # Best-effort lightweight migration for SQLite
    if not settings.database_url.startswith("sqlite"):
        return

    # Define the full desired schema
    schema = {
        "scans": [
            ("cardmarket_currency", "VARCHAR(8)"),
            ("cardmarket_7d_average", "FLOAT"),
            ("price_pln", "FLOAT"),
            ("price_pln_final", "FLOAT"),
            ("purchase_price", "FLOAT"),
            ("graded_psa10", "FLOAT"),
            ("graded_currency", "VARCHAR(8)"),
            ("session_id", "INTEGER"),
            ("publish_status", "VARCHAR(32)"),
            ("published_shoper_id", "INTEGER"),
            ("published_at", "DATETIME"),
            ("detected_rarity", "VARCHAR(64)"),
            ("detected_energy", "VARCHAR(64)"),
            ("detected_payload", "TEXT"),
            ("stored_path_back", "TEXT"),
            ("use_tcggo_image", "INTEGER DEFAULT 1"),
            ("additional_images", "TEXT"),
            ("warehouse_code", "VARCHAR(64)"),
            ("catalog_id", "INTEGER"),
        ],
        "sessions": [
            ("starting_warehouse_code", "VARCHAR(64)"),
        ],
        "products": [
            ("category_id", "INTEGER"),
            ("categories", "TEXT"),
            ("producer_id", "INTEGER"),
            ("tax_id", "INTEGER"),
            ("permalink", "TEXT"),
            ("main_image_gfx_id", "VARCHAR(64)"),
            ("main_image_extension", "VARCHAR(16)"),
            ("main_image_unic_name", "VARCHAR(64)"),
            ("tcggo_id", "VARCHAR(128)"),
            ("fingerprint_hash", "TEXT"),
            ("last_price_update", "DATETIME"),
            ("catalog_id", "INTEGER"),
            ("finish", "VARCHAR(32)"),
            ("price_locked", "INTEGER DEFAULT 0"),
            ("purchase_price", "FLOAT"),
        ],
        "scan_candidates": [
            ("rarity", "VARCHAR(128)"),
        ],
        "fingerprints": [
            ("catalog_id", "INTEGER"),
        ],
        "batch_scans": [
            ("successful_items", "INTEGER DEFAULT 0"),
            ("failed_items", "INTEGER DEFAULT 0"),
            ("current_filename", "VARCHAR(255)"),
            ("error_message", "TEXT"),
            ("completed_at", "DATETIME"),
            ("session_id", "INTEGER"),
            ("starting_warehouse_code", "VARCHAR(64)"),
        ],
        "batch_scan_items": [
            ("detected_rarity", "VARCHAR(128)"),
            ("matched_rarity", "VARCHAR(128)"),
            ("detected_energy", "VARCHAR(64)"),
            ("attr_rarity", "VARCHAR(16)"),
            ("attr_energy", "VARCHAR(16)"),
            ("attr_card_type", "VARCHAR(16)"),
            ("use_tcggo_image", "INTEGER DEFAULT 1"),
            ("additional_images_json", "TEXT"),
            ("cardmarket_url", "TEXT"),
            ("purchase_price", "FLOAT"),
        ],
        "inventory": [
            ("purchase_price", "FLOAT"),
        ],
        "auctions": [
            ("product_id", "INTEGER"),
            ("catalog_id", "INTEGER"),
            ("buyout_price", "FLOAT"),
            ("auto_publish_to_shoper", "INTEGER DEFAULT 0"),
            ("published_shoper_id", "INTEGER"),
            ("ended_at", "DATETIME"),
        ],
    }

    with engine.begin() as conn:
        for table_name, columns in schema.items():
            try:
                # Check if table exists
                res = conn.exec_driver_sql(f"PRAGMA table_info('{table_name}')").fetchall()
                existing_columns = {row[1] for row in res}
                
                for col_name, col_type in columns:
                    if col_name not in existing_columns:
                        print(f"Adding column '{col_name}' to table '{table_name}'...")
                        conn.exec_driver_sql(f'ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}')
            except Exception as e:
                print(f"Could not migrate table {table_name}: {e}")
