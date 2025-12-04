from pydantic import BaseModel, Field
from typing import Optional, List, Dict


class DetectedData(BaseModel):
    name: Optional[str] = None
    set: Optional[str] = None
    set_id: Optional[str] = None
    set_code: Optional[str] = None
    number: Optional[str] = None
    language: Optional[str] = None
    variant: Optional[str] = None
    condition: Optional[str] = None
    rarity: Optional[str] = None
    energy: Optional[str] = None
    price_pln_final: Optional[float] = None
    warehouse_code: Optional[str] = None
    variants: Optional[list] = None

    class Config:
        extra = "allow"


class Candidate(BaseModel):
    id: str
    name: str
    set: Optional[str] = None
    set_code: Optional[str] = None
    number: Optional[str] = None
    rarity: Optional[str] = None
    image: Optional[str] = None
    score: float = Field(ge=0, le=1)
    chosen: Optional[bool] = None

class OverlayRect(BaseModel):
    """Normalized rectangle within the frame (0..1)."""
    x: float
    y: float
    w: float
    h: float


class ScanResponse(BaseModel):
    scan_id: int | None = None
    detected: DetectedData
    candidates: List[Candidate]
    message: Optional[str] = None
    stored_path: Optional[str] = None
    image_url: Optional[str] = None
    duplicate_of: Optional[int] = None
    duplicate_distance: Optional[int] = None
    overlay: Optional[OverlayRect] = None
    quality: Optional[float] = None  # 0..1
    confidence: Optional[float] = None  # 0..1
    confidence_label: Optional[str] = None  # GOOD / FAIR / POOR
    warehouse_code: Optional[str] = None


class ProbeResponse(BaseModel):
    status: str  # 'card' | 'no_card'
    overlay: Optional[OverlayRect] = None
    quality: Optional[float] = None


class ConfirmRequest(BaseModel):
    scan_id: int
    candidate_id: str
    detected: Optional[dict] = None
    warehouse_code: Optional[str] = None


class ConfirmResponse(BaseModel):
    status: str
    scan_id: int
    candidate_id: str
    note: Optional[str] = None
    pricing: Optional[dict] = None


class ScanHistoryItem(BaseModel):
    id: int
    created_at: str
    detected_name: Optional[str]
    detected_set: Optional[str]
    detected_number: Optional[str]
    selected: Optional[Candidate] = None


class ScanDetailResponse(BaseModel):
    id: int
    created_at: str
    message: Optional[str]
    detected: DetectedData
    candidates: List[Candidate]
    selected_candidate_id: Optional[int] = None
    pricing: Optional[dict] = None
    image_url: Optional[str] = None
    back_image_url: Optional[str] = None
    warehouse_code: Optional[str] = None


class CreateProductRequest(BaseModel):
    attributes: Dict[str, str] = Field(default_factory=dict)
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    create_category_if_missing: Optional[bool] = None
    price_pln_final: Optional[float] = None
    name_override: Optional[str] = None
    number_override: Optional[str] = None
    candidate_id: Optional[str] = None

class ProductUpdateRequest(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    price: Optional[float] = None
    stock: Optional[int] = None
    category_id: Optional[int] = None

