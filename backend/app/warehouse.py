"""
Warehouse and storage location management.

This module adapts the logic from the legacy `kartoteka.storage` and
`kartoteka.storage_config` modules to work with the FastAPI backend
and SQLAlchemy database.
"""
import re
from pathlib import Path

from sqlalchemy.orm import Session
from sqlalchemy import or_

from . import db as models
from .settings import settings

# --- Configuration (from storage_config.py) ---

BOX_COUNT = 10
STANDARD_BOX_COLUMNS = 4
BOX_COLUMN_CAPACITY = 1000
STANDARD_BOX_CAPACITY = STANDARD_BOX_COLUMNS * BOX_COLUMN_CAPACITY

PREMIUM_BOX_NUMBER = 100
PREMIUM_BOX_ROWS = 3
PREMIUM_ROW_CAPACITY = 500
PREMIUM_BOX_CAPACITY = PREMIUM_BOX_ROWS * PREMIUM_ROW_CAPACITY

BOX_CAPACITY: dict[int, int] = {
    **{b: STANDARD_BOX_CAPACITY for b in range(1, BOX_COUNT + 1)},
    PREMIUM_BOX_NUMBER: PREMIUM_BOX_CAPACITY,
}

BOX_STRUCTURE: dict[int, dict[str, int]] = {
    **{b: {"rows": STANDARD_BOX_COLUMNS, "row_capacity": BOX_COLUMN_CAPACITY} for b in range(1, BOX_COUNT + 1)},
    PREMIUM_BOX_NUMBER: {"rows": PREMIUM_BOX_ROWS, "row_capacity": PREMIUM_ROW_CAPACITY},
}

_box_order = list(range(1, BOX_COUNT + 1)) + [
    b for b in sorted(BOX_CAPACITY) if b > BOX_COUNT
]
BOX_OFFSETS: dict[int, int] = {}
_offset = 0
for b in _box_order:
    BOX_OFFSETS[b] = _offset
    _offset += BOX_CAPACITY[b]
del _box_order, _offset

LAST_LOCATION_FILE = Path(settings.upload_dir).parent / "last_location.txt"

class NoFreeLocationError(Exception):
    """Raised when all storage locations are occupied."""

# --- Core Logic (adapted from storage.py) ---

def max_capacity() -> int:
    """Return total number of available storage slots."""
    return sum(BOX_CAPACITY.values())

def location_to_index(code: str) -> int | None:
    """Convert warehouse_code to its sequential index."""
    code = code.upper().strip()
    match = re.match(r"K(P|\d+)-R(\d+)-P(\d+)", code)
    if not match:
        return None

    box_str, row_str, pos_str = match.groups()
    
    box = PREMIUM_BOX_NUMBER if box_str == 'P' else int(box_str)
    row = int(row_str)
    pos = int(pos_str)

    offset = BOX_OFFSETS.get(box)
    if offset is None:
        return None

    structure = BOX_STRUCTURE.get(box)
    if not structure:
        return None

    if not (1 <= row <= structure["rows"]):
        return None
    if not (1 <= pos <= structure["row_capacity"]):
        return None

    return offset + (row - 1) * structure["row_capacity"] + (pos - 1)

def generate_location(idx: int) -> str:
    """Return a warehouse code for a sequential slot index."""
    total = max_capacity()
    if not (0 <= idx < total):
        raise ValueError("Index out of range for known storage boxes")

    original_idx = idx
    for box_num, box_offset in BOX_OFFSETS.items():
        if idx < box_offset + BOX_CAPACITY[box_num]:
            local_idx = idx - box_offset
            structure = BOX_STRUCTURE[box_num]
            row_capacity = structure["row_capacity"]
            
            row = local_idx // row_capacity + 1
            pos = local_idx % row_capacity + 1
            
            box_str = 'P' if box_num == PREMIUM_BOX_NUMBER else str(box_num)
            
            return f"K{box_str}-R{row}-P{pos:04d}"

    raise ValueError(f"Could not generate location for index {original_idx}")


def parse_warehouse_code(code: str) -> dict | None:
    """
    Parses a warehouse code (e.g., "K1-R1-P001") into its components.
    Returns a dict with "karton", "row", "position" or None if invalid.
    """
    code = code.upper().strip()
    match = re.match(r"K(P|\d+)-R(\d+)-P(\d+)", code)
    if not match:
        return None

    box_str, row_str, pos_str = match.groups()
    
    # Map 'P' to PREMIUM_BOX_NUMBER for internal logic, but return 'PREMIUM' string for display
    karton_display = 'PREMIUM' if box_str == 'P' else int(box_str)
    karton_internal = PREMIUM_BOX_NUMBER if box_str == 'P' else int(box_str)

    row = int(row_str)
    position = int(pos_str)

    # Basic validation using BOX_STRUCTURE for max rows and row_capacity
    box_structure_entry = BOX_STRUCTURE.get(karton_internal)
    if not box_structure_entry:
        return None # Invalid carton number

    if not (1 <= row <= box_structure_entry["rows"]):
        return None
    if not (1 <= position <= box_structure_entry["row_capacity"]):
        return None
        
    return {
        "karton": karton_display,
        "row": row,
        "position": position
    }


def get_used_indices(db: Session, only_published: bool = True) -> set[int]:
    """Queries the database for all used warehouse codes and returns them as a set of indices.
    
    Args:
        only_published: If True, only count published scans to avoid reserving codes for unpublished items.
    """
    used_indices = set()
    
    def _process_query(query):
        for (code,) in query:
            if not code:
                continue
            for single_code in code.split(';'):
                if not single_code:
                    continue
                index = location_to_index(single_code)
                if index is not None:
                    used_indices.add(index)

    # Check Scans - only published ones to avoid reserving codes for abandoned scans
    scan_query = db.query(models.Scan.warehouse_code).filter(models.Scan.warehouse_code.isnot(None))
    if only_published:
        scan_query = scan_query.filter(models.Scan.publish_status == 'published')
    _process_query(scan_query.all())
    
    # Check Inventory Items - always count these as they represent actual stock
    _process_query(db.query(models.InventoryItem.warehouse_code).filter(models.InventoryItem.warehouse_code.isnot(None)).all())
    
    # Check Batch Scan Items - only published ones
    batch_query = db.query(models.BatchScanItem.warehouse_code).filter(models.BatchScanItem.warehouse_code.isnot(None))
    if only_published:
        # Check if published OR if we have a shoper ID (which implies publication)
        batch_query = batch_query.filter(or_(
            models.BatchScanItem.publish_status == 'published',
            models.BatchScanItem.published_shoper_id.isnot(None)
        ))
    _process_query(batch_query.all())
    
    return used_indices

def get_next_free_location(db: Session, starting_code: str | None = None, only_published: bool = True) -> str:
    """Finds the next available warehouse location code."""
    used_indices = get_used_indices(db, only_published=only_published)
    
    start_idx = 0
    if starting_code:
        parsed_idx = location_to_index(starting_code)
        if parsed_idx is not None:
            start_idx = parsed_idx
    
    # Find the first unused index from the starting point
    idx = start_idx
    while idx in used_indices:
        idx += 1
        
    if idx >= max_capacity():
        # If no free slot from starting point, search from the beginning
        for i in range(max_capacity()):
            if i not in used_indices:
                idx = i
                break
        else:
            raise NoFreeLocationError("No free storage locations available.")

    return generate_location(idx)

# --- Monitoring ---

def get_storage_summary(db: Session) -> dict:
    """Provides a summary of warehouse occupancy."""
    from . import db as models
    
    used_indices = get_used_indices(db)
    total_capacity = max_capacity()
    used_count = len(used_indices)
    
    # Count products from shop without scans (for Premium Row 1)
    products_without_scans_count = 0
    try:
        products_count = db.query(models.Product).filter(models.Product.stock > 0).count()
        scans_with_products = db.query(models.Scan.published_shoper_id).filter(
            models.Scan.published_shoper_id.isnot(None)
        ).distinct().count()
        products_without_scans_count = max(0, products_count - scans_with_products)
    except:
        pass
    
    # Add virtual products to used count
    total_used_with_virtual = used_count + products_without_scans_count
    free_count = total_capacity - total_used_with_virtual
    
    occupancy_by_box = {}
    for box_num, structure in BOX_STRUCTURE.items():
        box_str = 'P' if box_num == PREMIUM_BOX_NUMBER else str(box_num)
        offset = BOX_OFFSETS[box_num]
        capacity = BOX_CAPACITY[box_num]
        box_indices = {i for i in used_indices if offset <= i < offset + capacity}
        
        rows = {}
        for r in range(1, structure["rows"] + 1):
            row_capacity = structure["row_capacity"]
            row_offset = offset + (r - 1) * row_capacity
            row_indices = {i for i in box_indices if row_offset <= i < row_offset + row_capacity}
            
            row_used = len(row_indices)
            
            # SPECIAL: For Premium Box (KP), Row 1 includes shop products without scans
            if box_num == PREMIUM_BOX_NUMBER and r == 1:
                row_used += products_without_scans_count
            
            rows[r] = {
                "used": row_used,
                "capacity": row_capacity,
                "free": row_capacity - row_used,
                "occupancy": row_used / row_capacity if row_capacity > 0 else 0,
            }
        
        # Calculate box totals
        box_used = len(box_indices)
        if box_num == PREMIUM_BOX_NUMBER:
            box_used += products_without_scans_count
        
        occupancy_by_box[f"K{box_str}"] = {
            "used": box_used,
            "capacity": capacity,
            "free": capacity - box_used,
            "occupancy": box_used / capacity if capacity > 0 else 0,
            "rows": rows,
        }
        
    return {
        "total_used": total_used_with_virtual,
        "total_capacity": total_capacity,
        "total_free": free_count,
        "total_occupancy": total_used_with_virtual / total_capacity if total_capacity > 0 else 0,
        "boxes": occupancy_by_box,
    }


def get_next_free_location_for_batch(db: Session, batch_id: int, starting_code: str | None = None) -> str:
    """
    Finds next free location, considering:
    1. Permanently published items (Scan, Inventory, BatchScanItem with published status)
    2. Items reserved by the CURRENT batch (even if not published yet)
    Ignores unpublished items from OTHER batches (allows reusing abandoned codes).
    """
    # 1. Get base used indices (only published items from Scans, Inventory, Batches)
    used_indices = get_used_indices(db, only_published=True)
    
    # 2. Add indices from the CURRENT batch (pending/processing/success) to avoid self-collision
    # We query all items in this batch that have a code assigned
    batch_items = db.query(models.BatchScanItem.warehouse_code).filter(
        models.BatchScanItem.batch_id == batch_id,
        models.BatchScanItem.warehouse_code.isnot(None)
    ).all()
    
    for (code,) in batch_items:
        if not code:
            continue
        # Split in case of multiple codes (though rare for batch items)
        for single_code in code.split(';'):
            idx = location_to_index(single_code)
            if idx is not None:
                used_indices.add(idx)
            
    # 3. Find next free slot
    start_idx = 0
    if starting_code:
        parsed_idx = location_to_index(starting_code)
        if parsed_idx is not None:
            start_idx = parsed_idx
    
    idx = start_idx
    while idx in used_indices:
        idx += 1
        
    if idx >= max_capacity():
        # Fallback: search from beginning if we ran out of space from starting point
        for i in range(max_capacity()):
            if i not in used_indices:
                idx = i
                break
        else:
            raise NoFreeLocationError("No free storage locations available.")

    return generate_location(idx)
