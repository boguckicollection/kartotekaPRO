import csv
import json
import os
import re
from collections.abc import Iterable, Mapping
from datetime import date, timedelta
from numbers import Number
from typing import Any, Optional, Tuple
from tkinter import filedialog, messagebox, TclError
import unicodedata

import logging

from webdav_client import WebDAVClient
INVENTORY_CSV = os.getenv(
    "INVENTORY_CSV", os.getenv("WAREHOUSE_CSV", "magazyn.csv")
)
WAREHOUSE_CSV = os.getenv("WAREHOUSE_CSV", INVENTORY_CSV)
STORE_EXPORT_CSV = os.getenv("STORE_EXPORT_CSV", "store_export.csv")
STORE_CACHE_JSON = os.getenv("STORE_CACHE_JSON", "store_cache.json")

# Track last modification time and cached statistics for the warehouse CSV
WAREHOUSE_CSV_MTIME: Optional[float] = None
_inventory_stats_cache: Optional[Tuple[int, float, int, float]] = None
_inventory_stats_path: Optional[str] = None

# column order for exported CSV files
STORE_FIELDNAMES = [
    "product_code",
    "name",
    "producer_code",
    "category",
    "producer",
    "short_description",
    "description",
    "price",
    "currency",
    "availability",
    "unit",
    "delivery",
    "stock",
    "active",
    "seo_title",
    "vat",
    "images 1",
    "ean",
    "type",
    "producer_id",
    "group_id",
    "tax_id",
    "category_id",
    "unit_id",
    "code",
    "pkwiu",
    "dimensions",
    "tags",
    "collections",
    "additional_codes",
    "virtual",
]

# include a ``sold`` flag so individual cards can be marked as sold and track
# when cards were added to the warehouse
WAREHOUSE_FIELDNAMES = [
    "name",
    "number",
    "set",
    "warehouse_code",
    "price",
    "image",
    "variant",
    "sold",
    "added_at",
]


logger = logging.getLogger(__name__)


DEFAULT_AVAILABILITY_VALUE = "1"
DEFAULT_AVAILABILITY_ID: Optional[int] = None


def _coerce_optional_int(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        if raw.isdigit():
            try:
                return int(raw)
            except ValueError:
                return None
        try:
            return int(float(raw))
        except ValueError:
            return None
    return None


def set_default_availability(value: Any) -> None:
    """Update the fallback availability value used when exporting rows."""

    global DEFAULT_AVAILABILITY_VALUE, DEFAULT_AVAILABILITY_ID

    label: Optional[str] = None
    identifier: Optional[int] = None

    if isinstance(value, Mapping):
        label_keys = (
            "available_label",
            "label",
            "name",
            "title",
            "value",
            "text",
            "code",
        )
        for key in label_keys:
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                label = candidate.strip()
                break

        id_keys = (
            "available_id",
            "availability_id",
            "id",
            "value",
            "default",
        )
        for key in id_keys:
            identifier = _coerce_optional_int(value.get(key))
            if identifier is not None:
                break
    elif isinstance(value, (list, tuple)):
        if value:
            first = value[0]
            if isinstance(first, str) and first.strip():
                label = first.strip()
            elif first is not None and label is None:
                label = str(first).strip()
        if len(value) > 1:
            identifier = _coerce_optional_int(value[1])
    elif isinstance(value, str):
        label = value.strip()
    elif value is not None:
        label = str(value).strip()

    cleaned = label or (str(identifier) if identifier is not None else "")

    if cleaned:
        DEFAULT_AVAILABILITY_VALUE = cleaned
        if identifier is not None:
            DEFAULT_AVAILABILITY_ID = identifier
        elif cleaned.isdigit():
            try:
                DEFAULT_AVAILABILITY_ID = int(cleaned)
            except ValueError:
                DEFAULT_AVAILABILITY_ID = None
        else:
            DEFAULT_AVAILABILITY_ID = None


def get_default_availability_id() -> Optional[int]:
    """Return the numeric identifier of the default availability when known."""

    return DEFAULT_AVAILABILITY_ID


def get_default_availability() -> str:
    """Return the currently configured fallback availability value."""

    return DEFAULT_AVAILABILITY_VALUE


def get_warehouse_inventory():
    """Wczytuje całą zawartość pliku magazyn.csv."""
    try:
        with open(WAREHOUSE_CSV, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f, delimiter=";")
            return list(reader)
    except FileNotFoundError:
        logger.error(f"Plik magazynu {WAREHOUSE_CSV} nie został znaleziony.")
        return []
    except Exception as e:
        logger.error(f"Błąd odczytu pliku {WAREHOUSE_CSV}: {e}")
        return []

def _ensure_warehouse_csv_exists(path: str = WAREHOUSE_CSV) -> None:
    """Create an empty warehouse CSV with headers when missing."""

    if not path:
        return

    directory = os.path.dirname(path)
    try:
        if directory and not os.path.isdir(directory):
            os.makedirs(directory, exist_ok=True)
        if os.path.exists(path):
            return
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(WAREHOUSE_FIELDNAMES)
    except OSError as exc:  # pragma: no cover - best effort logging
        logger.warning("Unable to initialise warehouse CSV at %s: %s", path, exc)


_ensure_warehouse_csv_exists()


def load_store_cache(path: str = STORE_CACHE_JSON) -> dict[str, dict[str, str]]:
    """Return cached product data stored as JSON."""

    try:
        with open(path, encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}

    items: Iterable[Mapping[str, Any]]
    if isinstance(payload, Mapping):
        items = [value for value in payload.values() if isinstance(value, Mapping)]
    elif isinstance(payload, list):
        items = [value for value in payload if isinstance(value, Mapping)]
    else:
        return {}

    data: dict[str, dict[str, str]] = {}
    for item in items:
        product_code = str(item.get("product_code") or item.get("code") or "").strip()
        if not product_code:
            continue
        serialised = {
            key: "" if value is None else str(value)
            for key, value in item.items()
        }
        data[product_code] = serialised
    return data


def save_store_cache(
    rows: Iterable[Mapping[str, Any]], path: str = STORE_CACHE_JSON
) -> None:
    """Persist ``rows`` to :data:`STORE_CACHE_JSON`."""

    serialisable: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        serialisable.append(
            {
                key: "" if value is None else str(value)
                for key, value in row.items()
            }
        )

    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    with open(path, "w", encoding="utf-8") as fh:
        json.dump(serialisable, fh, ensure_ascii=False, indent=2)


def normalize_store_cache_row(
    product_code: str, row: Mapping[str, Any] | None
) -> dict[str, str]:
    """Normalise ``row`` for use in the local product cache."""

    code = str(product_code or "").strip()
    data: dict[str, str] = {"product_code": code, "code": code}
    if not row:
        return data

    for key, value in row.items():
        key_text = str(key or "").strip()
        if not key_text:
            continue
        if isinstance(value, str):
            data[key_text] = value
        elif value is None:
            data[key_text] = ""
        elif isinstance(value, Number):
            data[key_text] = str(value)
        else:
            data[key_text] = str(value)
    if "product_code" not in data:
        data["product_code"] = code
    if "code" not in data:
        data["code"] = code
    return data


def _coerce_scalar(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if isinstance(value, Number):
        return str(value)
    return None


def _extract_from_translations(translations: Any) -> Optional[str]:
    if not isinstance(translations, Mapping):
        return None
    preferred_locales = ["pl_PL", "pl", "en_GB", "en_US", "en"]
    for locale in preferred_locales:
        entry = translations.get(locale)
        if isinstance(entry, Mapping):
            for key in ("name", "title"):
                value = entry.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
    for entry in translations.values():
        if not isinstance(entry, Mapping):
            continue
        for key in ("name", "title"):
            value = entry.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _extract_product_name(product: Mapping[str, Any]) -> Optional[str]:
    name = product.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    return _extract_from_translations(product.get("translations"))


def _extract_product_price(product: Mapping[str, Any]) -> Optional[str]:
    price_fields = [
        "price",
        "price_brutto",
        "price_gross",
        "price_net",
        "price_value",
        "priceValue",
    ]
    for field in price_fields:
        value = product.get(field)
        coerced = _coerce_scalar(value)
        if coerced is not None:
            return coerced
        if isinstance(value, Mapping):
            for sub_key in ("gross", "brutto", "net", "value", "amount", "price"):
                coerced = _coerce_scalar(value.get(sub_key))
                if coerced is not None:
                    return coerced
    return None


def _extract_product_category(product: Mapping[str, Any]) -> Optional[str]:
    direct = product.get("category") or product.get("category_full_name")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    categories = product.get("categories")
    if isinstance(categories, list):
        collected: list[str] = []
        for entry in categories:
            if isinstance(entry, Mapping):
                for key in ("path", "name", "title", "label"):
                    value = entry.get(key)
                    if isinstance(value, str) and value.strip():
                        collected.append(value.strip())
                        break
            elif isinstance(entry, str) and entry.strip():
                collected.append(entry.strip())
        if collected:
            if len(collected) == 1:
                return collected[0]
            return " > ".join(collected)
    return None


def _extract_product_stock(product: Mapping[str, Any]) -> Optional[str]:
    stock_fields = ["stock", "qty", "quantity", "stock_qty"]
    for field in stock_fields:
        value = product.get(field)
        coerced = _coerce_scalar(value)
        if coerced is not None:
            return coerced
        if isinstance(value, Mapping):
            coerced = _coerce_scalar(value.get("stock"))
            if coerced is not None:
                return coerced
    return None


def _extract_product_image(product: Mapping[str, Any]) -> Optional[str]:
    for key in ("images 1", "image", "image_url", "main_image", "image1"):
        value = product.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    images = product.get("images")
    if isinstance(images, list):
        for entry in images:
            if isinstance(entry, Mapping):
                for key in ("url", "src", "image", "path"):
                    value = entry.get(key)
                    if isinstance(value, str) and value.strip():
                        return value.strip()
            elif isinstance(entry, str) and entry.strip():
                return entry.strip()
    return None


def normalise_api_product(
    product: Mapping[str, Any]
) -> Optional[tuple[str, dict[str, str]]]:
    """Transform a Shoper API product payload into a cache-friendly row."""

    if not isinstance(product, Mapping):
        return None

    code = str(product.get("product_code") or product.get("code") or "").strip()
    if not code:
        return None

    row: dict[str, Any] = {"product_code": code, "code": code}
    product_id = product.get("product_id") or product.get("id")
    if product_id is not None and product_id != "":
        row["product_id"] = str(product_id)
    name = _extract_product_name(product)
    if name:
        row["name"] = name
    price = _extract_product_price(product)
    if price is not None:
        row["price"] = price
    category = _extract_product_category(product)
    if category:
        row["category"] = category
    stock = _extract_product_stock(product)
    if stock is not None:
        row["stock"] = stock
    producer_code = _coerce_scalar(
        product.get("producer_code")
        or product.get("symbol")
        or product.get("sku")
        or product.get("ean")
    )
    if producer_code is not None:
        row["producer_code"] = producer_code
    warehouse_code = _coerce_scalar(product.get("warehouse_code") or product.get("warehouse"))
    if warehouse_code is not None:
        row["warehouse_code"] = warehouse_code
    description = _coerce_scalar(
        product.get("description")
        or product.get("long_description")
        or product.get("full_description")
    )
    if description is not None:
        row["description"] = description
    short_description = _coerce_scalar(
        product.get("short_description") or product.get("intro")
    )
    if short_description is not None:
        row["short_description"] = short_description
    image = _extract_product_image(product)
    if image:
        row["images 1"] = image

    normalised = normalize_store_cache_row(code, row)
    return code, normalised


def iter_api_products(response: Mapping[str, Any] | None) -> Iterable[Mapping[str, Any]]:
    """Yield product payloads from a Shoper API response."""

    if not isinstance(response, Mapping):
        return []

    items: list[Any] = []
    for key in ("list", "items", "products", "data"):
        value = response.get(key)
        if isinstance(value, list):
            items = value
            break
    else:
        single = response.get("product")
        if isinstance(single, Mapping):
            items = [single]

    def _iterator() -> Iterable[Mapping[str, Any]]:
        for item in items:
            if isinstance(item, Mapping):
                yield item

    return _iterator()


def api_pagination(response: Mapping[str, Any] | None) -> tuple[int | None, int | None]:
    """Extract current and total pages from an API response."""

    if not isinstance(response, Mapping):
        return (None, None)

    current = None
    total = None
    for key in ("page", "current_page", "currentPage"):
        value = response.get(key)
        if value is None:
            continue
        try:
            current = int(value)
            break
        except (TypeError, ValueError):
            continue
    for key in ("pages", "total_pages", "totalPages"):
        value = response.get(key)
        if value is None:
            continue
        try:
            total = int(value)
            break
        except (TypeError, ValueError):
            continue
    return current, total


def product_image_url(row: Mapping[str, Any] | None) -> Optional[str]:
    """Return best-effort image URL from cached product ``row``."""

    if not isinstance(row, Mapping):
        return None

    for key in ("images 1", "image", "image_url", "main_image", "image1"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    images = row.get("images")
    if isinstance(images, list):
        for entry in images:
            if isinstance(entry, Mapping):
                for key in ("url", "src", "image", "path"):
                    value = entry.get(key)
                    if isinstance(value, str) and value.strip():
                        return value.strip()
            elif isinstance(entry, str) and entry.strip():
                return entry.strip()
    return None


def _sanitize_number(value: str) -> str:
    """Return ``value`` without leading zeros.

    Parameters
    ----------
    value:
        Raw number string.

    Returns
    -------
    str
        Normalised number or ``"0"`` if the result is empty.
    """

    return value.strip().lstrip("0") or "0"


VARIANT_CODE_TO_NAME = {"C": "common", "H": "holo", "R": "reverse"}
VARIANT_SUFFIXES = {name: code for code, name in VARIANT_CODE_TO_NAME.items()}


def try_normalize_variant_code(value: Any) -> Optional[str]:
    """Return the variant code (``C``, ``H`` or ``R``) when recognised."""

    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        normalized = unicodedata.normalize("NFKD", stripped)
        ascii_variant = "".join(ch for ch in normalized if not unicodedata.combining(ch)) or stripped
        upper = ascii_variant.upper()
        if upper in VARIANT_CODE_TO_NAME:
            return upper
        lower = ascii_variant.lower()
        if lower in VARIANT_SUFFIXES:
            return VARIANT_SUFFIXES[lower]
    return None


def normalize_variant_code(value: Any, *, default: str = "C") -> str:
    """Return a variant code, falling back to ``default`` when unknown."""

    return try_normalize_variant_code(value) or default


def variant_code_to_name(code: str, *, default: str = "common") -> str:
    """Return the textual name for ``code``."""

    return VARIANT_CODE_TO_NAME.get(code, default)


def infer_variant_code(data: Mapping[str, Any] | None) -> str:
    """Infer variant code from ``data`` supporting legacy structures."""

    if not data:
        return "C"
    for key in ("card_type", "variant", "typ"):
        code = try_normalize_variant_code(data.get(key))
        if code:
            return code
    types = data.get("types") if isinstance(data, Mapping) else None
    if isinstance(types, Mapping):
        if types.get("Holo") or types.get("holo"):
            return "H"
        if types.get("Reverse") or types.get("reverse"):
            return "R"
    return "C"


def build_product_code(
    set_name: str,
    number: str,
    variant: str | None = None,
    ball_suffix: str | None = None,
) -> str:
    """Return a product code based on set abbreviation and card number."""
    from .ui import get_set_abbr  # local import to avoid circular dependency

    abbr = get_set_abbr(set_name)
    if not abbr:
        sanitized = re.sub(r"[^A-Za-z0-9]", "", set_name).upper()
        abbr = sanitized[:3]
    num = _sanitize_number(str(number))
    variant_code = normalize_variant_code(variant)
    ball = (ball_suffix or "").strip().upper()
    if ball not in {"P", "M"}:
        ball = ""
    return f"PKM-{abbr}-{num}{variant_code}{ball}"


def infer_product_code(data: Mapping[str, Any] | None) -> str:
    """Return a product code derived from ``data`` when available."""

    if not data:
        return ""

    for key in ("product_code", "code", "producer_code"):
        value = str(data.get(key) or "").strip()
        if value:
            return value

    set_name = data.get("set") or data.get("set_name") or ""
    number = data.get("number") or data.get("numer") or ""
    variant = data.get("variant") or data.get("card_type")
    ball = data.get("ball") or data.get("ball_suffix")
    if not set_name or not number:
        return ""

    try:
        return build_product_code(set_name, number, variant, ball)
    except Exception:
        return ""


def decrement_store_stock(product_counts: Mapping[str, int]):
    """Legacy helper kept for backwards compatibility."""

    raise RuntimeError(
        "CSV-based stock management has been replaced with direct Shoper API "
        "integration. Use ShoperClient.update_product_stock instead."
    )


def mark_warehouse_codes_as_sold(codes, *, path: str | None = None) -> int:
    """Legacy helper kept for backwards compatibility."""

    raise RuntimeError(
        "Warehouse CSV updates are no longer supported. Use the Shoper API "
        "via ShoperClient.mark_products_sold instead."
    )


def find_duplicates(
    name: str, number: str, set_name: str, variant: str | None = None
):
    """Return rows from ``WAREHOUSE_CSV`` matching the given card details.

    Parameters
    ----------
    name, number, set_name:
        Card attributes to match against ``WAREHOUSE_CSV`` entries.
    variant:
        Optional card variant. When ``None`` or falsy any variant matches.

    Returns
    -------
    list[dict[str, str]]
        List of matching rows including warehouse codes.
    """

    from .ui import normalize  # local import to avoid circular dependency

    matches = []
    number = _sanitize_number(str(number))
    name_norm = normalize(name)
    set_norm = normalize(set_name)
    requested_code = try_normalize_variant_code(variant)

    if not os.path.exists(WAREHOUSE_CSV):
        return matches

    try:
        with open(WAREHOUSE_CSV, encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                row_number = _sanitize_number(str(row.get("number", "")))
                row_name = normalize(row.get("name") or "")
                row_set = normalize(row.get("set") or "")
                row_variant_code = infer_variant_code(row)
                if (
                    row_name == name_norm
                    and row_number == number
                    and row_set == set_norm
                    and (requested_code is None or row_variant_code == requested_code)
                ):
                    matches.append(row)
    except OSError:
        pass

    return matches


def get_row_by_code(code: str, path: str = WAREHOUSE_CSV) -> Optional[dict[str, str]]:
    """Return the first row in ``path`` matching ``code``.

    Parameters
    ----------
    code:
        Warehouse code identifying a card.
    path:
        Optional path to the warehouse CSV. Defaults to :data:`WAREHOUSE_CSV`.

    Returns
    -------
    dict | None
        Matching row or ``None`` when the code is not found or the file is
        inaccessible.
    """

    code = (code or "").strip()
    if not code:
        return None
    try:
        with open(path, encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                codes = [c.strip() for c in str(row.get("warehouse_code") or "").split(";") if c.strip()]
                if code in codes:
                    return row
    except OSError:
        return None
    return None


def get_inventory_stats(path: str = WAREHOUSE_CSV, force: bool = False):
    """Return statistics for both unsold and sold items in the warehouse CSV.

    Parameters
    ----------
    path:
        Optional path to the warehouse CSV. Defaults to ``WAREHOUSE_CSV``.

    Returns
    -------
    tuple[int, float, int, float]
        ``(count_unsold, total_unsold, count_sold, total_sold)`` where each
        count is the number of rows and each total is the sum of the ``price``
        column for items in the respective category.
    """

    count_unsold = 0
    total_unsold = 0.0
    count_sold = 0
    total_sold = 0.0

    global WAREHOUSE_CSV_MTIME, _inventory_stats_cache, _inventory_stats_path

    # Determine current modification time if the file exists
    try:
        current_mtime = os.path.getmtime(path)
    except OSError:
        current_mtime = None

    cache_valid = (
        not force
        and _inventory_stats_cache is not None
        and _inventory_stats_path == path
        and WAREHOUSE_CSV_MTIME == current_mtime
    )

    if cache_valid:
        return _inventory_stats_cache

    if not os.path.exists(path):
        _inventory_stats_cache = (
            count_unsold,
            total_unsold,
            count_sold,
            total_sold,
        )
        _inventory_stats_path = path
        WAREHOUSE_CSV_MTIME = current_mtime
        return _inventory_stats_cache

    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            sold_flag = str(row.get("sold") or "").lower() in {"1", "true", "yes"}
            price_raw = str(row.get("price") or "0").replace(",", ".")
            try:
                price = float(price_raw)
            except ValueError:
                continue

            if sold_flag:
                count_sold += 1
                total_sold += price
            else:
                count_unsold += 1
                total_unsold += price

    _inventory_stats_cache = (
        count_unsold,
        total_unsold,
        count_sold,
        total_sold,
    )
    _inventory_stats_path = path
    WAREHOUSE_CSV_MTIME = current_mtime
    return _inventory_stats_cache


def get_daily_additions(days: int = 7) -> dict[str, int]:
    """Return counts of cards added per day for the last ``days`` days."""
    end = date.today()
    start = end - timedelta(days=days - 1)
    counts = {
        (start + timedelta(days=i)).isoformat(): 0 for i in range(days)
    }
    if not os.path.exists(WAREHOUSE_CSV):
        return counts

    with open(WAREHOUSE_CSV, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            added_raw = (row.get("added_at") or "").split("T", 1)[0]
            try:
                added_date = date.fromisoformat(added_raw)
            except ValueError:
                continue
            if start <= added_date <= end:
                counts[added_date.isoformat()] += 1
    return counts


def format_store_row(row):
    """Return a row formatted for the store CSV."""

    def _serialise(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, bool):
            return "1" if value else ""
        if isinstance(value, (list, dict)):
            try:
                return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            except TypeError:
                return json.dumps(
                    [str(v) for v in value], ensure_ascii=False, separators=(",", ":")
                )
        return str(value)

    formatted_name = row["nazwa"]

    return {
        "product_code": row["product_code"],
        "name": formatted_name,
        "producer_code": row.get("producer_code") or row.get("numer", ""),
        "category": row["category"],
        "producer": row["producer"],
        "short_description": row["short_description"],
        "description": row["description"],
        "price": row["cena"],
        "currency": row.get("currency", "PLN"),
        "availability": row.get("availability", DEFAULT_AVAILABILITY_VALUE),
        "unit": row.get("unit", "szt."),
        "delivery": "3 dni",
        "stock": row.get("stock", 1),
        "active": row.get("active", 1),
        "seo_title": row.get("seo_title", ""),
        "vat": row.get("vat", "23%"),
        "images 1": row.get("image1", row.get("images", "")),
        "ean": _serialise(row.get("ean")),
        "type": _serialise(row.get("type")),
        "producer_id": _serialise(row.get("producer_id")),
        "group_id": _serialise(row.get("group_id")),
        "tax_id": _serialise(row.get("tax_id")),
        "category_id": _serialise(row.get("category_id")),
        "unit_id": _serialise(row.get("unit_id")),
        "code": _serialise(row.get("code")),
        "pkwiu": _serialise(row.get("pkwiu")),
        "dimensions": _serialise(row.get("dimensions")),
        "tags": _serialise(row.get("tags")),
        "collections": _serialise(row.get("collections")),
        "additional_codes": _serialise(row.get("additional_codes")),
        "virtual": _serialise(row.get("virtual")),
    }


def format_warehouse_row(row):
    """Return a row formatted for the warehouse CSV."""
    variant_code = infer_variant_code(row)
    variant = variant_code_to_name(variant_code)
    return {
        "name": row.get("nazwa", ""),
        "number": row.get("numer", ""),
        "set": row.get("set", ""),
        "warehouse_code": row.get("warehouse_code", ""),
        "price": row.get("cena") or row.get("price", ""),
        "image": row.get("image1", row.get("images", "")),
        "variant": variant,
        "sold": row.get("sold", ""),
        "added_at": row.get("added_at") or date.today().isoformat(),
    }


def _iter_session_rows(app: Any) -> Iterable[Mapping[str, Any]]:
    """Yield mapping-like rows collected during the current session."""

    entries = getattr(app, "session_entries", None)
    if isinstance(entries, list) and any(isinstance(row, Mapping) for row in entries):
        for row in entries:
            if isinstance(row, Mapping):
                yield row
        return

    for row in getattr(app, "output_data", []):
        if isinstance(row, Mapping):
            yield row


def load_csv_data(app):
    """Load a CSV file and merge duplicate rows."""
    file_path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
    if not file_path:
        return

    with open(file_path, encoding="utf-8") as f:
        sample = f.read(2048)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=";,")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(f, dialect=dialect)

        def norm_header(name: str) -> str:
            normalized = name.strip().lower()
            if normalized == "images 1":
                return "image1"
            return normalized

        fieldnames = [norm_header(fn) for fn in reader.fieldnames or []]
        rows = []
        for raw_row in reader:
            row = {(norm_header(k) if k else k): v for k, v in raw_row.items()}
            if "warehouse_code" not in row and re.match(r"k\d+r\d+p\d+", str(row.get("product_code", "")).lower()):
                row["warehouse_code"] = row["product_code"]
                row["product_code"] = ""
                if "warehouse_code" not in fieldnames:
                    fieldnames.append("warehouse_code")
            rows.append(row)

    combined = {}
    qty_field = None
    qty_variants = {"stock", "ilość", "ilosc", "quantity", "qty"}

    for row in rows:
        img_val = row.get("image1") or row.get("images", "")
        row["image1"] = img_val
        row["images"] = img_val

        key = (
            f"{row.get('nazwa', '').strip()}|{row.get('numer', '').strip()}|{row.get('set', '').strip()}"
        )
        if qty_field is None:
            for variant in qty_variants:
                if variant in row:
                    qty_field = variant
                    break
        qty = 1
        if qty_field:
            try:
                qty = int(row.get(qty_field, 0))
            except ValueError:
                qty = 1

        warehouse = str(row.get("warehouse_code", "")).strip()

        if key in combined:
            combined[key]["qty"] += qty
            if warehouse:
                combined[key]["warehouses"].add(warehouse)
        else:
            new_row = row.copy()
            new_row["qty"] = qty
            new_row["warehouses"] = set()
            if warehouse:
                new_row["warehouses"].add(warehouse)
            combined[key] = new_row

    for row in combined.values():
        if not row.get("product_code"):
            number = row.get("numer") or row.get("number") or ""
            row["product_code"] = build_product_code(
                row.get("set", ""),
                number,
                infer_variant_code(row),
                ball_suffix=row.get("ball_type"),
            )

    if qty_field is None:
        qty_field = "ilość"
        if qty_field not in fieldnames:
            fieldnames.append(qty_field)

    if "image1" in fieldnames:
        fieldnames[fieldnames.index("image1")] = "images 1"

    save_path = filedialog.asksaveasfilename(
        defaultextension=".csv", filetypes=[("CSV files", "*.csv")]
    )
    if not save_path:
        return

    with open(save_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        for row in combined.values():
            row_out = row.copy()
            row_out[qty_field] = row_out.pop("qty")
            row_out["warehouse_code"] = ";".join(sorted(row_out.pop("warehouses", [])))
            row_out["images 1"] = row_out.get("image1", row_out.get("images", ""))
            if qty_field != "stock":
                row_out.pop("stock", None)
            if qty_field != "ilość":
                row_out.pop("ilość", None)
            writer.writerow({k: row_out.get(k, "") for k in fieldnames})

    messagebox.showinfo("Sukces", "Plik CSV został scalony i zapisany.")


def export_csv(app, path: str = STORE_EXPORT_CSV) -> list[dict[str, str]]:
    """Return prepared store rows without writing them to disk."""

    combined: dict[str, dict[str, Any]] = {}

    store_data = getattr(app, "store_data", None)
    if isinstance(store_data, dict) and store_data:
        for product_code, row in store_data.items():
            if not isinstance(row, Mapping):
                continue
            row_copy = dict(row)
            try:
                row_copy["stock"] = int(row_copy.get("stock") or 0)
            except (TypeError, ValueError):
                try:
                    row_copy["stock"] = int(str(row_copy.get("stock") or 0))
                except (TypeError, ValueError):
                    row_copy["stock"] = 0
            combined[str(product_code).strip()] = row_copy
    elif os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                product_code = str(row.get("product_code") or "").strip()
                if not product_code:
                    continue
                try:
                    row["stock"] = int(row.get("stock") or 0)
                except (TypeError, ValueError):
                    row["stock"] = 0
                combined[product_code] = row

    session_rows = list(_iter_session_rows(app))

    session_override_fields = {"price", "currency", "vat", "cena"}

    for raw in session_rows:
        try:
            row = dict(raw)
        except Exception:
            continue

        product_code = str(row.get("product_code") or row.get("code") or "").strip()
        if not product_code:
            number = row.get("numer") or row.get("number") or ""
            product_code = build_product_code(
                row.get("set") or row.get("set_code") or "",
                number,
                infer_variant_code(row),
                ball_suffix=row.get("ball_type"),
            )
            if product_code:
                row["product_code"] = product_code

        if not product_code:
            continue

        if product_code in combined:
            existing = combined[product_code]
            try:
                stock_value = int(existing.get("stock", 0))
            except (TypeError, ValueError):
                stock_value = 0
            existing["stock"] = stock_value + 1
            formatted_row = format_store_row(row)
            if "cena" not in formatted_row and "cena" in row:
                formatted_row["cena"] = row["cena"]
            for key, value in formatted_row.items():
                if key in session_override_fields:
                    existing[key] = value
                    continue
                if key in existing and existing[key]:
                    continue
                existing[key] = value
        else:
            row_copy = row.copy()
            row_copy["stock"] = 1
            combined[product_code] = format_store_row(row_copy)

    prepared_rows: list[dict[str, str]] = []
    for row in combined.values():
        output = {key: ("" if value is None else str(value)) for key, value in row.items()}
        try:
            stock_value = int(output.get("stock", 0))
        except (TypeError, ValueError):
            stock_value = 0
        output["stock"] = str(stock_value)
        prepared_rows.append(output)

    return prepared_rows


def write_store_csv(rows: Iterable[Mapping[str, Any]], path: str) -> None:
    """Write ``rows`` in store CSV format to ``path``."""

    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    with open(path, mode="w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=STORE_FIELDNAMES, delimiter=";")
        writer.writeheader()
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            writer.writerow({key: str(row.get(key, "")) for key in STORE_FIELDNAMES})


def append_warehouse_csv(
    app, path: str = WAREHOUSE_CSV, exported_rows: Iterable[Mapping[str, Any]] | None = None
):
    """Append all collected rows to the warehouse CSV."""
    fieldnames = WAREHOUSE_FIELDNAMES

    file_exists = os.path.exists(path)
    product_codes: set[str] = set()
    if exported_rows is not None:
        for row in exported_rows:
            if not isinstance(row, Mapping):
                continue
            code = str(row.get("product_code") or row.get("code") or "").strip()
            if code:
                product_codes.add(code)

    session_rows = list(_iter_session_rows(app))

    with open(path, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        if not file_exists:
            writer.writeheader()
        for row in session_rows:
            if not isinstance(row, Mapping):
                continue
            if product_codes:
                code = str(row.get("product_code") or "").strip()
                if not code or code not in product_codes:
                    continue
            writer.writerow(format_warehouse_row(row))

    # Recompute and cache inventory statistics to include newly written rows
    get_inventory_stats(path, force=True)

    if hasattr(app, "update_inventory_stats"):
        try:
            app.update_inventory_stats(force=True)
        except TclError:
            pass


def send_csv_to_shoper(app, file_path: str):
    """Send a CSV file using the Shoper API or WebDAV fallback."""
    from tkinter import messagebox  # ensure patched instance is used
    try:
        if getattr(app, "shoper_client", None):
            result = app.shoper_client.import_csv(file_path)
            errors = result.get("errors") or []
            warnings = result.get("warnings") or []
            status = (result.get("status") or "").lower()
            if errors or warnings or status not in {"completed", "finished", "done", "success"}:
                issues = "\n".join(map(str, errors + warnings)) or f"Status: {status or 'nieznany'}"
                messagebox.showerror("Błąd", f"Import zakończony z problemami:\n{issues}")
            else:
                messagebox.showinfo("Sukces", f"Import zakończony: {status}")
        else:
            with WebDAVClient(
                getattr(app, "WEBDAV_URL", None),
                getattr(app, "WEBDAV_USER", None),
                getattr(app, "WEBDAV_PASSWORD", None),
            ) as client:
                client.upload_file(file_path)
            messagebox.showinfo("Sukces", "Plik CSV został wysłany.")
    except Exception as exc:  # pragma: no cover - network failure
        messagebox.showerror("Błąd", f"Nie udało się wysłać pliku: {exc}")

