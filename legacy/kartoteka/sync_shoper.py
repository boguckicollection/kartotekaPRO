"""Synchronisation helpers between Shoper API and the local inventory DB."""

from __future__ import annotations

from typing import Optional
import os
import hashlib
import mimetypes
from urllib.parse import urlparse

import requests

from .local_db import LocalInventoryDB
from .inventory_service import WarehouseInventoryService


def sync_products(
    client,
    db: Optional[LocalInventoryDB] = None,
    *,
    per_page: int = 100,
    verbose: bool = True,
    progress: Optional[callable] = None,
) -> int:
    """Fetch products from Shoper and store them in the local DB.

    Returns number of processed products. Stores the most recent update token
    in ``sync_state['last_products_token']`` when available.
    """

    if db is None:
        db = LocalInventoryDB()

    svc = WarehouseInventoryService(client=client)
    image_cache_dir = os.getenv("IMAGE_CACHE_DIR", ".cache/images").strip() or ".cache/images"

    def _resolve_image_url(value: str) -> str:
        if not value:
            return value
        try:
            p = urlparse(value)
            if p.scheme in ("http", "https"):
                return value
        except Exception:
            pass
        base = os.getenv("BASE_IMAGE_URL", "").strip().rstrip("/")
        if not base:
            return value
        path = value.lstrip("/")
        return f"{base}/{path}"

    def _image_cache_path(url: str) -> str:
        os.makedirs(image_cache_dir, exist_ok=True)
        parsed = urlparse(url)
        ext = os.path.splitext(parsed.path)[1]
        if not ext:
            guessed = mimetypes.guess_extension(mimetypes.guess_type(url)[0] or "image/jpeg") or ".jpg"
            ext = guessed
        name = hashlib.sha1(url.encode("utf-8", errors="ignore")).hexdigest() + ext
        return os.path.join(image_cache_dir, name)

    def _download_to_cache(url: str) -> Optional[str]:
        if not url:
            return None
        local_path = _image_cache_path(url)
        try:
            if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
                return local_path
        except OSError:
            pass
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            with open(local_path, "wb") as fh:
                fh.write(resp.content)
            return local_path
        except Exception:
            return None
    count = 0
    page = 1
    total_items = None
    max_token = ""
    last_token = db.get_state("last_products_token") or ""
    # progress output helper
    def _log(msg: str) -> None:
        if verbose:
            print(f"[SYNC] {msg}")
    while True:
        _log(f"Pobieram stronę {page}…")
        response = client.get_inventory(page=page, per_page=per_page)
        # Report total pages if available
        try:
            from .inventory_service import WarehouseInventoryService as _Svc

            svc = _Svc(client=client)
            total_pages = svc._extract_total_pages(response)
        except Exception:
            total_pages = None
        products = svc._extract_product_list(response)
        # Determine total number of items if available; fallback to pages*per_page
        if total_items is None:
            try:
                ti = svc._extract_total_items(response)
                if isinstance(ti, int) and ti > 0:
                    total_items = ti
            except Exception:
                pass
        if total_items is None and total_pages:
            try:
                total_items = int(total_pages) * int(per_page)
            except Exception:
                total_items = None
        if not products:
            break
        have_new = False
        if progress and total_pages:
            try:
                progress({
                    "phase": "page",
                    "page": page,
                    "pages": total_pages,
                    "processed": count,
                    "per_page": per_page,
                    "total_items": total_items,
                })
            except Exception:
                pass
        for product in products:
            item = svc._normalise_api_product(product)
            if item is None:
                continue
            token = svc._extract_update_token(product) or ""
            if token and token > max_token:
                max_token = token
            # stop early when we reached already-known token set
            if last_token and token and token <= last_token:
                continue
            have_new = True
            codes = [loc.code for loc in item.locations if loc.code]
            # Attempt to download product image to disk cache
            image_url = _resolve_image_url(item.image or "") if getattr(item, "image", None) else ""
            local_image = _download_to_cache(image_url) if image_url else None
            # Derive an 'active' flag – treat zero quantity as not active in local view
            active = 0 if item.sold else 1
            code = item.number or str(product.get("code") or product.get("product_code") or "").strip()
            if not code:
                # last resort: skip items without a stable code
                continue
            db.upsert_item(
                {
                    "code": code,
                    "name": item.name,
                    "price": item.price,
                    "image": local_image or item.image,
                    "active": active,
                    "quantity": item.quantity,
                    "warehouse_codes": codes,
                    "updated_at": token,
                }
            )
            count += 1
        _log(f"Strona {page}: zapisano {count} pozycji łącznie")
        if progress and total_pages:
            try:
                progress({
                    "phase": "page_done",
                    "page": page,
                    "pages": total_pages,
                    "processed": count,
                    "per_page": per_page,
                    "total_items": total_items,
                })
            except Exception:
                pass
        # If nothing new on this page and last_token present, we can stop
        if last_token and not have_new:
            _log("Brak nowych pozycji – przerywam sync na podstawie tokenu")
            break
        # advance
        current_page = svc._extract_current_page(response)
        total_pages = svc._extract_total_pages(response)
        if current_page >= total_pages:
            break
        page = current_page + 1

    if max_token:
        db.set_state("last_products_token", max_token)
    if progress:
        try:
            progress({"phase": "done", "processed": count})
        except Exception:
            pass
    return count
