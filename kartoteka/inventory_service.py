"""Inventory service providing warehouse data from Shoper API or fallbacks."""
from __future__ import annotations

import json
import csv
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Optional

from . import csv_utils
from .storage_config import BOX_COLUMNS

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WarehouseLocation:
    """Normalized location information for a single card."""

    code: str
    box: Optional[int]
    column: Optional[int]
    position: Optional[int]


@dataclass(frozen=True)
class InventoryItem:
    """Normalized representation of a warehouse card."""

    name: str
    number: str
    set: str
    variant: str
    sold: bool
    price: str
    image: str
    added_at: str
    quantity: int
    locations: tuple[WarehouseLocation, ...]
    warehouse_code: str
    source: str
    raw: Mapping[str, Any]


@dataclass(frozen=True)
class InventorySnapshot:
    """Container returned by :class:`WarehouseInventoryService`."""

    items: tuple[InventoryItem, ...]
    column_occupancy: Mapping[tuple[int, int], int]
    version: Any
    source: str


class WarehouseInventoryService:
    """Provide warehouse inventory data using the best available source."""

    def __init__(self, client: Any | None = None, csv_path: str | None = None):
        from shoper_client import ShoperClient  # late import to avoid cycles

        self._client: ShoperClient | None
        if isinstance(client, ShoperClient):
            self._client = client
        else:
            self._client = None
            if client is None:
                try:
                    self._client = ShoperClient()
                except Exception as exc:  # pragma: no cover - environment specific
                    logger.info("Falling back to CSV warehouse data: %s", exc)
            else:  # pragma: no cover - unexpected injection
                self._client = None
        self._csv_path = csv_path or getattr(csv_utils, "WAREHOUSE_CSV", "magazyn.csv")
        self._snapshot: InventorySnapshot | None = None
        self._csv_mtime: float | None = None
        self._api_version: Any = None

    @classmethod
    def create_default(cls) -> "WarehouseInventoryService":
        return cls()

    # Public API -----------------------------------------------------------------

    def get_version(self) -> Any:
        """Return change token for the current inventory snapshot."""

        snapshot = self.get_snapshot()
        return snapshot.version if snapshot else None

    def get_snapshot(self) -> InventorySnapshot:
        """Return cached inventory snapshot, fetching if necessary."""

        if self._client:
            if self._snapshot is None or self._snapshot.source != "api":
                self._snapshot = self._fetch_from_api()
            return self._snapshot
        return self._fetch_from_csv()

    def fetch_snapshot(self) -> InventorySnapshot:
        """Force refresh of the snapshot from the underlying source."""

        if self._client:
            self._snapshot = self._fetch_from_api(force=True)
        else:
            self._snapshot = self._fetch_from_csv(force=True)
        return self._snapshot

    # Internal helpers -----------------------------------------------------------

    def _fetch_from_csv(self, force: bool = False) -> InventorySnapshot:
        csv_path = self._csv_path
        try:
            mtime = os.path.getmtime(csv_path)
        except OSError:
            mtime = None
        if (
            not force
            and self._snapshot is not None
            and self._snapshot.source == "csv"
            and self._csv_mtime == mtime
        ):
            return self._snapshot

        items: list[InventoryItem] = []
        try:
            with open(csv_path, encoding="utf-8") as fh:
                reader = csv.DictReader(fh, delimiter=";")
                for row in reader:
                    normalised = self._normalise_csv_row(row)
                    if normalised is not None:
                        items.append(normalised)
        except FileNotFoundError:
            logger.info("Warehouse CSV %s not found", csv_path)
        except Exception as exc:  # pragma: no cover - logged for diagnostics
            logger.warning("Failed to read warehouse CSV %s: %s", csv_path, exc)

        column_occ = self._compute_column_occupancy(items)
        snapshot = InventorySnapshot(
            items=tuple(items),
            column_occupancy=column_occ,
            version=mtime,
            source="csv",
        )
        self._snapshot = snapshot
        self._csv_mtime = mtime
        return snapshot

    def _fetch_from_api(self, force: bool = False) -> InventorySnapshot:
        client = self._client
        if client is None:
            return self._fetch_from_csv(force=force)

        items: list[InventoryItem] = []
        version_tokens: list[str] = []
        page = 1
        per_page = 100
        while True:
            response = client.get_inventory(page=page, per_page=per_page)
            products = self._extract_product_list(response)
            if not products:
                break
            for product in products:
                normalised = self._normalise_api_product(product)
                if normalised is not None:
                    items.append(normalised)
                token = self._extract_update_token(product)
                if token:
                    version_tokens.append(token)
            total_pages = self._extract_total_pages(response)
            current_page = self._extract_current_page(response)
            if current_page >= total_pages:
                break
            page = current_page + 1

        if not items:
            logger.info("Shoper API returned empty inventory; falling back to CSV")
            return self._fetch_from_csv(force=force)

        column_occ = self._compute_column_occupancy(items)
        if version_tokens:
            version = max(version_tokens)
        else:
            version = time.time()
        self._api_version = version
        snapshot = InventorySnapshot(
            items=tuple(items),
            column_occupancy=column_occ,
            version=version,
            source="api",
        )
        self._snapshot = snapshot
        return snapshot

    # Normalisation helpers ------------------------------------------------------

    @staticmethod
    def _parse_locations(value: Any) -> list[WarehouseLocation]:
        locations: list[WarehouseLocation] = []
        codes: Iterable[str]
        if value is None:
            codes = []
        elif isinstance(value, str):
            codes = [c.strip() for c in value.split(";") if c.strip()]
        elif isinstance(value, Iterable):
            codes = []
            for entry in value:
                if isinstance(entry, Mapping):
                    code = str(entry.get("code") or entry.get("warehouse_code") or "").strip()
                    if code:
                        codes.append(code)
                else:
                    code = str(entry).strip()
                    if code:
                        codes.append(code)
        else:
            codes = []

        pattern = re.compile(r"K(\d+)R(\d+)P(\d+)")
        for code in codes:
            match = pattern.fullmatch(code)
            if match:
                box, column, pos = map(int, match.groups())
                locations.append(
                    WarehouseLocation(code=code, box=box, column=column, position=pos)
                )
            else:
                locations.append(WarehouseLocation(code=code, box=None, column=None, position=None))
        return locations

    def _normalise_csv_row(self, row: Mapping[str, Any]) -> InventoryItem | None:
        name = str(row.get("name") or "").strip()
        if not name:
            logger.debug("Skipping CSV row without name: %s", row)
            return None
        number = str(row.get("number") or "").strip()
        set_name = str(row.get("set") or "").strip()
        variant = str(row.get("variant") or "common").strip() or "common"
        sold_flag = str(row.get("sold") or "").strip().lower()
        sold = sold_flag in {"1", "true", "yes"}
        price = str(row.get("price") or "").strip()
        image = str(row.get("image") or "").strip()
        added_at = str(row.get("added_at") or "").strip()
        codes_value = row.get("warehouse_code")
        locations = self._parse_locations(codes_value)
        quantity = max(len(locations), 1)
        warehouse_code = ";".join(loc.code for loc in locations if loc.code)
        return InventoryItem(
            name=name,
            number=number,
            set=set_name,
            variant=variant,
            sold=sold,
            price=price,
            image=image,
            added_at=added_at,
            quantity=quantity,
            locations=tuple(locations),
            warehouse_code=warehouse_code,
            source="csv",
            raw=dict(row),
        )

    def _normalise_api_product(self, product: Mapping[str, Any]) -> InventoryItem | None:
        name = self._first_non_empty(
            product.get("name"),
            product.get("product_name"),
            product.get("title"),
            self._resolve_translation(product, "name"),
        )
        if not name:
            return None
        number = self._first_non_empty(
            product.get("number"),
            product.get("sku"),
            product.get("code"),
            product.get("producer_code"),
        )
        set_name = self._first_non_empty(
            product.get("set"),
            product.get("category"),
            product.get("category_name"),
        )
        variant = self._first_non_empty(
            product.get("variant"),
            product.get("card_variant"),
            product.get("attributes", {}).get("variant") if isinstance(product.get("attributes"), Mapping) else None,
        ) or "common"
        sold_value = product.get("sold")
        if isinstance(sold_value, str):
            sold = sold_value.strip().lower() in {"1", "true", "yes"}
        elif isinstance(sold_value, (int, float)):
            sold = bool(sold_value)
        else:
            stock = product.get("stock")
            sold = False
            if isinstance(stock, Mapping):
                quantity_val = stock.get("quantity") or stock.get("value")
                try:
                    sold = float(quantity_val or 0) <= 0
                except (TypeError, ValueError):
                    sold = False
            elif isinstance(stock, (int, float)):
                sold = float(stock) <= 0
        price = self._first_non_empty(
            product.get("price"),
            product.get("price_gross"),
            product.get("price_net"),
        )
        price_str = str(price or "").strip()
        added_at = self._first_non_empty(
            product.get("added_at"),
            product.get("created_at"),
            product.get("date_add"),
            product.get("date"),
        )
        image = self._extract_primary_image(product)
        location_value = self._first_non_empty(
            product.get("warehouse_code"),
            product.get("warehouse_codes"),
            product.get("locations"),
            product.get("stock"),
        )
        locations = self._parse_locations(location_value)
        if not locations:
            stock = product.get("stock")
            if isinstance(stock, Mapping):
                maybe_codes = stock.get("warehouses") or stock.get("locations")
                locations = self._parse_locations(maybe_codes)
        quantity = 0
        if isinstance(product.get("stock"), Mapping):
            quantity = product.get("stock", {}).get("quantity") or 0
        elif isinstance(product.get("stock"), (int, float)):
            quantity = int(product.get("stock") or 0)
        if not quantity:
            quantity = len(locations) or 1
        warehouse_code = ";".join(loc.code for loc in locations if loc.code)
        return InventoryItem(
            name=str(name),
            number=str(number or ""),
            set=str(set_name or ""),
            variant=str(variant or "common"),
            sold=bool(sold),
            price=price_str,
            image=str(image or ""),
            added_at=str(added_at or ""),
            quantity=int(quantity),
            locations=tuple(locations),
            warehouse_code=warehouse_code,
            source="api",
            raw=dict(product),
        )

    @staticmethod
    def _compute_column_occupancy(items: Iterable[InventoryItem]) -> dict[tuple[int, int], int]:
        occupancy: dict[tuple[int, int], int] = {}
        for item in items:
            if item.sold:
                continue
            for loc in item.locations:
                if loc.box is None or loc.column is None:
                    continue
                key = (loc.box, loc.column)
                occupancy[key] = occupancy.get(key, 0) + 1
        # ensure keys exist for known boxes so UI renders consistently
        for box, columns in BOX_COLUMNS.items():
            for column in range(1, columns + 1):
                occupancy.setdefault((box, column), 0)
        return occupancy

    @staticmethod
    def _first_non_empty(*values: Any) -> Any:
        for value in values:
            if isinstance(value, str):
                text = value.strip()
                if text:
                    return text
            elif value is not None:
                return value
        return ""

    @staticmethod
    def _resolve_translation(product: Mapping[str, Any], field: str) -> Any:
        translations = product.get("translations")
        if isinstance(translations, Mapping):
            for lang in ("pl_PL", "pl", "en_GB", "en_US", "en"):
                payload = translations.get(lang)
                if isinstance(payload, Mapping) and payload.get(field):
                    return payload[field]
        return None

    @staticmethod
    def _extract_primary_image(product: Mapping[str, Any]) -> str:
        images = product.get("images")
        if isinstance(images, list) and images:
            first = images[0]
            if isinstance(first, Mapping):
                for key in ("url", "path", "image", "src"):
                    if first.get(key):
                        return str(first[key])
            return str(first)
        if isinstance(product.get("main_image"), Mapping):
            main_image = product.get("main_image")
            for key in ("url", "path", "image", "src"):
                if main_image.get(key):
                    return str(main_image[key])
        return str(product.get("main_image") or product.get("image") or "")

    @staticmethod
    def _extract_product_list(response: Any) -> list[Mapping[str, Any]]:
        if isinstance(response, Mapping):
            for key in ("list", "items", "products"):
                value = response.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, Mapping)]
        if isinstance(response, list):
            return [item for item in response if isinstance(item, Mapping)]
        return []

    @staticmethod
    def _extract_total_pages(response: Any) -> int:
        if isinstance(response, Mapping):
            for key in ("pages", "pageCount", "pages_count", "total_pages"):
                value = response.get(key)
                try:
                    return max(1, int(value))
                except (TypeError, ValueError):
                    continue
        return 1

    @staticmethod
    def _extract_current_page(response: Any) -> int:
        if isinstance(response, Mapping):
            for key in ("page", "current_page"):
                value = response.get(key)
                try:
                    return max(1, int(value))
                except (TypeError, ValueError):
                    continue
        return 1

    def _extract_update_token(self, product: Mapping[str, Any]) -> str:
        for key in ("updated_at", "modified", "modified_at", "date_mod", "date_update"):
            value = product.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""


__all__ = [
    "InventoryItem",
    "InventorySnapshot",
    "WarehouseInventoryService",
    "WarehouseLocation",
]
