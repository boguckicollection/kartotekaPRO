from __future__ import annotations

from datetime import datetime
from typing import Dict, Any, List, Optional
import json
import httpx
from sqlalchemy import desc

from .settings import settings
from pathlib import Path
import unicodedata
from sqlalchemy import desc

from .db import Product, SessionLocal, Scan, ScanCandidate
from .settings import settings


_shoper_categories_cache: List[Dict[str, Any]] | None = None


async def get_shoper_categories(client: ShoperClient) -> List[Dict[str, Any]]:
    """Fetches categories from Shoper API and caches them in memory."""
    global _shoper_categories_cache
    if _shoper_categories_cache is None:
        data = await client.fetch_categories()
        _shoper_categories_cache = data.get("items") or []
    return _shoper_categories_cache or []


class ShoperClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.token = token

    async def fetch_all_categories(self) -> List[Dict[str, Any]]:
        """Fetch all categories handling pagination (async)."""
        results: List[Dict[str, Any]] = []
        page = 1
        while True:
            url = f"{self.base_url}/categories"
            params = {"page": page, "limit": 50}
            headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}
            
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    r = await client.get(url, params=params, headers=headers)
                    if r.status_code != 200:
                        break
                    data = r.json()
                    
                items = []
                if isinstance(data, dict):
                    items = data.get("list") or data.get("items") or []
                    pages = int(data.get("pages") or 1)
                elif isinstance(data, list):
                    items = data
                    pages = 1
                else:
                    pages = 1
                    
                if not items:
                    break
                    
                results.extend(items)
                
                if page >= pages:
                    break
                page += 1
            except Exception:
                break
        return results

    async def create_category_async(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create a category (async)."""
        url = f"{self.base_url}/categories"
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(url, json=payload, headers=headers)
            r.raise_for_status()
            return r.json()

    async def delete_category_async(self, category_id: int) -> bool:
        """Delete a category (async)."""
        url = f"{self.base_url}/categories/{category_id}"
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.delete(url, headers=headers)
            return r.status_code in (200, 204)

    async def fetch_products_page(self, page: int = 1, limit: int = 50) -> Dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}
        url = f"{self.base_url}{settings.shoper_products_path}"
        params = {"page": page, "limit": limit}
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(url, params=params, headers=headers)
            r.raise_for_status()
            data = r.json()
        # Accept shapes: {list: [...]}, {items: [...]}, or top-level list
        if isinstance(data, dict):
            items = data.get("list") or data.get("items") or data.get("data") or []
            try:
                page_meta = int(data.get("page") or page)
            except Exception:
                page_meta = page
            pages_meta = data.get("pages")
            try:
                pages_meta = int(pages_meta) if pages_meta is not None else None
            except Exception:
                pages_meta = None
        elif isinstance(data, list):
            items = data
            page_meta = page
            pages_meta = None
        else:
            items = []
            page_meta = page
            pages_meta = None
        return {"items": items, "page": page_meta, "pages": pages_meta}

    async def fetch_all_products(self, limit: int = 100) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        page = 1
        while True:
            meta = await self.fetch_products_page(page=page, limit=limit)
            items = meta.get("items") or []
            if not items:
                break
            results.extend(items)
            pages = meta.get("pages")
            if isinstance(pages, int) and pages > 0:
                if page >= pages:
                    break
            else:
                # Fallback termination when API doesn't expose total pages
                if len(items) < limit:
                    break
            page += 1
        return results

    async def _get_json(self, url: str, params: Dict[str, Any] | None = None) -> Any:
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(url, params=params or {}, headers=headers)
            r.raise_for_status()
            return r.json()

    async def _get_collection(self, paths: list[str], params: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """Try multiple API paths and normalize to { items: [...], raw: <response> }.

        Accepts common Shoper shapes: {list: [...]}, {items: [...]}, {data: [...]}, or top-level list.
        Returns empty "items" when all attempts fail.
        """
        for p in paths:
            try:
                url = f"{self.base_url}{p}"
                data = await self._get_json(url, params=params)
                items = []
                if isinstance(data, dict):
                    items = data.get("list") or data.get("items") or data.get("data") or []
                elif isinstance(data, list):
                    items = data
                if isinstance(items, list):
                    return {"items": items, "raw": data}
            except Exception:
                continue
        return {"items": [], "raw": None}

    async def fetch_attributes(self) -> Dict[str, Any]:
        """Fetch attributes list (with options) using several known endpoints."""
        paths = [
            settings.shoper_attributes_path,
            "/attributes/list",
            "/product-attributes",
        ]
        return await self._get_collection(paths)

    async def fetch_categories(self) -> Dict[str, Any]:
        """Fetch categories; try plain, list and tree endpoints."""
        paths = [
            settings.shoper_categories_path,
            "/categories/list",
            "/categories-tree",
        ]
        return await self._get_collection(paths)

    async def fetch_languages(self) -> Dict[str, Any]:
        paths = [
            settings.shoper_languages_path,
            "/languages/list",
        ]
        return await self._get_collection(paths)

    async def create_category(self, name: str, parent_id: Optional[int] = None) -> Optional[int]:
        """Create a category; returns its id on success or None.

        Tries common endpoints with minimal payload.
        """
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}
        url = f"{self.base_url}/categories"
        payload: Dict[str, Any] = {"name": name, "active": "1"}
        if parent_id is not None:
            payload["parent_id"] = int(parent_id)
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                r = await client.post(url, json=payload, headers=headers)
                r.raise_for_status()
                data = r.json()
                cid = data.get("category_id") or data.get("id")
                return int(cid) if cid is not None else None
        except Exception:
            return None

    async def fetch_availability(self) -> Dict[str, Any]:
        """Fetch availability list; common paths differ by install."""
        paths = [
            settings.shoper_availability_path,
            "/availabilities",
            "/availability/list",
        ]
        return await self._get_collection(paths)

    async def upload_gfx(self, file_path: str) -> str | None:
        """Uploads an image from a local path to the Shoper GFX endpoint and returns the gfx_id.

        Tries multiple endpoint variants:
        1. /gfx (if base_url already contains /webapi/rest)
        2. /webapi2/gfx
        3. /webapi/rest/gfx
        """
        import base64
        import os

        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}

        # Determine possible URLs - always try multiple endpoints
        possible_urls = []

        # Extract base domain without /webapi/rest suffix
        if "/webapi/rest" in self.base_url:
            base_domain = self.base_url.split("/webapi/rest")[0]
        else:
            base_domain = self.base_url.rstrip("/")

        # Try all possible endpoints in order of preference
        possible_urls.append(f"{base_domain}/webapi2/gfx")      # Newest API (preferred)
        possible_urls.append(f"{base_domain}/webapi/rest/gfx")  # Standard API

        # If base_url already includes /webapi/rest, also try simple /gfx
        if "/webapi/rest" in self.base_url:
            possible_urls.append(f"{self.base_url}/gfx")

        print(f"DEBUG: upload_gfx called with file_path={file_path}")
        print(f"DEBUG: Will try these endpoints in order: {possible_urls}")

        try:
            if not os.path.exists(file_path):
                print(f"ERROR: File does not exist: {file_path}")
                return None

            file_size = os.path.getsize(file_path)
            print(f"DEBUG: File exists, size={file_size} bytes")

            with open(file_path, "rb") as f:
                content_bytes = f.read()

            content_b64 = base64.b64encode(content_bytes).decode("utf-8")
            filename = os.path.basename(file_path)

            payload = {
                "gfx": {
                    "file": filename,
                    "content": content_b64
                }
            }

            # Try each endpoint until one succeeds
            last_error = None
            for url in possible_urls:
                try:
                    print(f"DEBUG: Trying endpoint: {url}, filename={filename}, base64_length={len(content_b64)}")
                    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as http:
                        r = await http.post(url, json=payload, headers=headers)
                        print(f"DEBUG: Response status: {r.status_code}")

                        if r.status_code == 200 or r.status_code == 201:
                            data = r.json()
                            print(f"DEBUG: Success! Response body: {data}")
                            gfx_id = data.get("gfx_id") or data.get("id")
                            if gfx_id:
                                print(f"SUCCESS: Image uploaded via {url}, gfx_id={gfx_id}")
                                return str(gfx_id)
                            else:
                                print(f"WARNING: No gfx_id in response: {data}")
                        else:
                            # Non-2xx response, log and try next endpoint
                            error_body = r.text if hasattr(r, 'text') else str(r.content)
                            print(f"DEBUG: Endpoint {url} failed with {r.status_code}: {error_body}")
                            last_error = f"{r.status_code}: {error_body}"
                except Exception as e:
                    print(f"DEBUG: Endpoint {url} failed with exception: {e}")
                    last_error = str(e)
                    continue

            # All endpoints failed
            print(f"ERROR: All GFX upload endpoints failed. Last error: {last_error}")
            return None

        except Exception as e:
            print(f"ERROR in upload_gfx (outer): {e}")
            return None

    async def upload_product_image(self, product_id: int, file_path: str, *, main: bool | None = None) -> Dict[str, Any]:
        """Upload image to product using Shoper API.

        Follows Shoper API best practices:
        1. If file_path is a URL: send JSON with {"product_id": X, "url": "...", "main": true}
        2. If file_path is local: encode as Base64 and send JSON {"product_id": X, "data": "base64...", "main": true}
        
        Tries two endpoints in order:
        - POST {base}/webapi2/product-images (newer API)
        - POST {base}/webapi/rest/product-images (standard API)
        """
        import base64
        import os
        
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}
        
        # Possible endpoints to try (modern first)
        endpoints = [
            f"{self.base_url.rstrip('/')}/webapi2/product-images" if "/webapi" in self.base_url else None,
            f"{self.base_url}/product-images",
        ]
        endpoints = [e for e in endpoints if e]  # Remove None entries
        
        # Prepare payload
        payload: Dict[str, Any] = {"product_id": int(product_id)}
        if main is not None:
            payload["main"] = bool(main)
        
        # Check if file_path is a URL
        if isinstance(file_path, str) and (file_path.startswith('http://') or file_path.startswith('https://')):
            # Method 1: Upload via URL
            payload["url"] = file_path
            print(f"DEBUG: upload_product_image - using URL method with: {file_path}")
        else:
            # Method 2: Upload via Base64
            try:
                if not os.path.exists(file_path):
                    return {"error": True, "message": f"File not found: {file_path}"}
                
                with open(file_path, "rb") as fh:
                    file_content = fh.read()
                    file_b64 = base64.b64encode(file_content).decode("utf-8")
                
                # Shoper API uses "content" field for base64 encoded image
                payload["content"] = file_b64
                print(f"DEBUG: upload_product_image - using Base64 method, size={len(file_content)} bytes")
            except Exception as e:
                return {"error": True, "message": f"Failed to read file: {str(e)}"}
        
        # Try each endpoint
        last_error = None
        for url in endpoints:
            try:
                print(f"DEBUG: Trying endpoint: {url}")
                async with httpx.AsyncClient(timeout=60) as http:
                    r = await http.post(url, json=payload, headers=headers)
                    
                    if r.status_code in (200, 201):
                        data = r.json()
                        print(f"SUCCESS: Image uploaded via {url}")
                        return {"ok": True, "json": data}
                    else:
                        error_body = r.text
                        print(f"DEBUG: Endpoint {url} failed with {r.status_code}: {error_body}")
                        last_error = f"{r.status_code}: {error_body}"
            except Exception as e:
                print(f"DEBUG: Endpoint {url} failed with exception: {e}")
                last_error = str(e)
                continue
        
        # All endpoints failed
        return {"error": True, "message": f"All image upload endpoints failed. Last error: {last_error}"}

    async def update_product(self, shoper_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Updates an existing product in Shoper."""
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}
        url = f"{self.base_url}{settings.shoper_products_path}/{shoper_id}"

        payload: Dict[str, Any] = {}

        # Handle translations (name)
        if "name" in updates:
            payload.setdefault("translations", {})[settings.default_language_code] = {"name": updates["name"]}
        
        # Handle stock updates (price, stock)
        stock_updates = {}
        if "price" in updates:
            stock_updates["price"] = f"{updates['price']:.2f}"
        if "stock" in updates:
            stock_updates["stock"] = str(updates["stock"])
        if stock_updates:
            payload["stock"] = stock_updates

        # Handle category_id
        if "category_id" in updates:
            payload["category_id"] = updates["category_id"]
        
        # Handle code
        if "code" in updates:
            payload["code"] = updates["code"]

        if "related" in updates:
            payload["related"] = updates["related"]


        # NOTE: Attributes are handled via separate PUT request with proper format
        # Remove attributes from this update to avoid format conflicts
        # They must be sent in a separate call using set_product_attributes()

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.put(url, json=payload, headers=headers)
                r.raise_for_status()
                return {"ok": True, "json": r.json()}
        except httpx.HTTPStatusError as e:
            return {"error": True, "status_code": e.response.status_code, "text": e.response.text, "payload": payload, "exception": str(e)}
        except Exception as e:
            return {"error": True, "message": str(e), "payload": payload}

    async def set_product_attributes(self, product_id: int, attributes: Dict[str, Dict[str, str]]) -> Dict[str, Any]:
        """Set product attributes by updating the product via PUT /products/{id}.
        
        This implementation now FLATTENS the attribute structure, as the API seems to
        expect a flat { "attribute_id": "value" } dictionary, despite documentation
        suggesting a nested structure. This is to fix the "Attribute X does not exist" error.
        """
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}
        
        # Flatten the nested attributes dictionary into a single-level dict.
        # from: {"group_id": {"attribute_id": "value"}}
        # to:   {"attribute_id": "value", ...}
        flat_attributes = {}
        for group_id, group_attrs in attributes.items():
            for attr_id, value in group_attrs.items():
                flat_attributes[str(attr_id)] = str(value)

        # Build the final payload with the flattened attributes object.
        payload: Dict[str, Any] = {
            "attributes": flat_attributes
        }
        
        # Use standard product update endpoint
        url = f"{self.base_url}{settings.shoper_products_path}/{product_id}"
        
        print(f"DEBUG: set_product_attributes called with FLATTENED payload: {payload}")
        print(f"DEBUG: Updating product via PUT {url}")
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.put(url, json=payload, headers=headers)
                
                if r.status_code in (200, 201, 204):
                    print(f"SUCCESS: Attributes set via PUT {url}")
                    try:
                        return {"ok": True, "json": r.json() if r.status_code != 204 else {}}
                    except:
                        return {"ok": True, "json": {}}
                else:
                    error_body = r.text
                    print(f"ERROR: PUT {url} failed with {r.status_code}: {error_body}")
                    return {"error": True, "status_code": r.status_code, "message": error_body}
        except Exception as e:
            print(f"ERROR: PUT {url} failed with exception: {e}")
            return {"error": True, "message": str(e)}

    async def fetch_order_detail(self, order_id: Any) -> Dict[str, Any] | None:
        """Fetch a single order; request embedded products/addresses when available.

        Many Shoper installations support a "with" query param that embeds
        related resources to avoid N+1 calls. If unsupported, the API simply
        ignores unknown params, so it is safe to include.
        """
        try:
            url = f"{self.base_url}{settings.shoper_orders_path}/{order_id}"
            params = {"with": "products,delivery_address,billing_address,status,user"}
            data = await self._get_json(url, params=params)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return None

    async def fetch_order_products(self, order_id: Any) -> List[Dict[str, Any]]:
        """Return all products for an order, handling common API variants + pagination.

        Order products may be exposed via:
        - embedded on order detail when using "with=products"
        - a dedicated collection under ``/order-products`` (preferred, paginated)
        - occasionally ``/orders-products`` (legacy/alias)
        - or ``/orders/{id}/products`` in some setups
        """
        # 1) Try embedded products on order detail
        try:
            detail = await self.fetch_order_detail(order_id)
            if isinstance(detail, dict):
                items = (
                    detail.get("products")
                    or detail.get("orders_products")
                    or detail.get("order_products")
                )
                if isinstance(items, dict):
                    items = items.get("items") or items.get("list")
                if isinstance(items, list) and items:
                    return items
        except Exception:
            pass

        # Helper to iterate paginated collection using JSON-encoded filters
        async def _collect_from_collection(path: str) -> list[dict]:
            acc: list[dict] = []
            page = 1
            while True:
                try:
                    params = {"filters": json.dumps({"order_id": order_id}), "page": page, "limit": 50}
                    data = await self._get_json(path, params=params)
                except Exception:
                    break
                if isinstance(data, dict):
                    items = data.get("list") or data.get("items") or data.get("data") or []
                    if not items:
                        break
                    if isinstance(items, list):
                        acc.extend(items)
                    try:
                        cur = int(data.get("page") or page)
                        pages_val = data.get("pages")
                        pages = int(pages_val) if pages_val is not None else None
                    except Exception:
                        cur = page
                        pages = None
                    if pages is not None:
                        if cur >= pages:
                            break
                    else:
                        if len(items) < 50:
                            break
                    page += 1
                elif isinstance(data, list):
                    # Unpaginated list
                    acc.extend(data)
                    break
                else:
                    break
            return acc

        # 2) Preferred: /order-products (paginated)
        items = await _collect_from_collection(f"{self.base_url}/order-products")
        if items:
            return items

        # 3) Alias: /orders-products (paginated)
        items = await _collect_from_collection(f"{self.base_url}/orders-products")
        if items:
            return items

        # 4) Fallback: nested resource /orders/{id}/products (may be unpaginated)
        try:
            data = await self._get_json(f"{self.base_url}{settings.shoper_orders_path}/{order_id}/products")
            if isinstance(data, dict):
                items = data.get("list") or data.get("items") or data.get("data") or []
                if isinstance(items, list) and items:
                    return items
            if isinstance(data, list) and data:
                return data
        except Exception:
            pass

        return []

    async def fetch_orders_page(self, page: int = 1, limit: int = 50) -> Dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}
        url = f"{self.base_url}{settings.shoper_orders_path}"
        # Request products and buyer data embedded
        params = {"page": page, "limit": limit, "with": "products,buyer"}
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(url, params=params, headers=headers)
            r.raise_for_status()
            data = r.json()
        # Normalize shapes
        if isinstance(data, dict):
            items = data.get("list") or data.get("items") or data.get("data") or []
            try:
                page_meta = int(data.get("page") or page)
            except Exception:
                page_meta = page
            pages_meta = data.get("pages")
            try:
                pages_meta = int(pages_meta) if pages_meta is not None else None
            except Exception:
                pages_meta = None
        elif isinstance(data, list):
            items = data
            page_meta = page
            pages_meta = None
        else:
            items = []
            page_meta = page
            pages_meta = None
        return {"items": items, "page": page_meta, "pages": pages_meta}

    async def fetch_all_orders(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        DEPRECATED: This method fetches ALL orders across all pages, ignoring the limit parameter.
        Use fetch_recent_orders() instead for limited results.
        
        For backward compatibility, this still works but can be slow.
        """
        results: List[Dict[str, Any]] = []
        page = 1
        while True:
            meta = await self.fetch_orders_page(page=page, limit=limit)
            items = meta.get("items") or []
            if not items:
                break
            results.extend(items)
            pages = meta.get("pages")
            if isinstance(pages, int) and pages > 0:
                if page >= pages:
                    break
            else:
                if len(items) < limit:
                    break
            page += 1
        return results

    async def fetch_recent_orders(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Fetch only the most recent orders (single page).
        This is FAST and respects the limit parameter.
        
        Args:
            limit: Maximum number of orders to return (default: 20, max: 250)
        
        Returns:
            List of order dictionaries, sorted by date descending
        """
        meta = await self.fetch_orders_page(page=1, limit=min(limit, 250))
        return meta.get("items") or []

    async def fetch_orders_since(self, since_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Fetch orders with ID greater than since_id.
        This is VERY FAST - single API call with server-side filtering.
        
        Args:
            since_id: Fetch orders with order_id > this value
            limit: Maximum number of orders to return
        
        Returns:
            List of new orders, sorted by ID descending
        """
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}
        url = f"{self.base_url}{settings.shoper_orders_path}"
        
        # Shoper API supports filtering by order_id
        params = {
            "limit": min(limit, 250),
            "order": "DESC",  # Newest first
            "sort": "order_id"
        }
        
        # Try to use filters if Shoper API supports it
        # Format: filters[order_id][from]=123
        # If not supported, we'll filter client-side
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # First try with server-side filtering
                filter_params = {**params, f"filters[order_id][from]": since_id + 1}
                r = await client.get(url, params=filter_params, headers=headers)
                
                if r.status_code == 200:
                    data = r.json()
                    if isinstance(data, dict):
                        items = data.get("list") or data.get("items") or data.get("data") or []
                    elif isinstance(data, list):
                        items = data
                    else:
                        items = []
                    return items
                
                # If filtering not supported, fall back to fetching first page and filtering client-side
                r = await client.get(url, params=params, headers=headers)
                r.raise_for_status()
                data = r.json()
                
                if isinstance(data, dict):
                    items = data.get("list") or data.get("items") or data.get("data") or []
                elif isinstance(data, list):
                    items = data
                else:
                    items = []
                
                # Client-side filter: only orders with ID > since_id
                filtered = []
                for order in items:
                    order_id = order.get("order_id") or order.get("id")
                    try:
                        if int(order_id) > since_id:
                            filtered.append(order)
                    except (ValueError, TypeError):
                        continue
                
                return filtered
                
        except Exception as e:
            print(f"Error fetching orders since {since_id}: {e}")
            return []

    async def fetch_users_page(self, page: int = 1, limit: int = 100) -> Dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}
        url = f"{self.base_url}{settings.shoper_users_path}"
        params = {"page": page, "limit": limit}
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(url, params=params, headers=headers)
            r.raise_for_status()
            data = r.json()
        if isinstance(data, dict):
            items = data.get("list") or data.get("items") or data.get("data") or []
            try:
                page_meta = int(data.get("page") or page)
            except Exception:
                page_meta = page
            pages_meta = data.get("pages")
            try:
                pages_meta = int(pages_meta) if pages_meta is not None else None
            except Exception:
                pages_meta = None
        elif isinstance(data, list):
            items = data
            page_meta = page
            pages_meta = None
        else:
            items = []
            page_meta = page
            pages_meta = None
        return {"items": items, "page": page_meta, "pages": pages_meta}

    async def get_product(self, product_id: int) -> Dict[str, Any] | None:
        """Fetch a single product by its ID, requesting related data."""
        try:
            url = f"{self.base_url}{settings.shoper_products_path}/{product_id}"
            # The 'with' parameter is a common pattern in Shoper to embed related
            # resources like translations, images, attributes, and stock information
            # in a single API call, which is more efficient than making multiple requests.
            params = {"with": "translations,images,attributes,stock,related"}
            data = await self._get_json(url, params=params)
            if isinstance(data, dict):
                return data
        except Exception:
            # If the request fails for any reason (e.g., product not found, API error),
            # return None to indicate that the product could not be retrieved.
            pass
        return None

    async def fetch_all_users(self, limit: int = 200) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        page = 1
        while True:
            meta = await self.fetch_users_page(page=page, limit=limit)
            items = meta.get("items") or []
            if not items:
                break
            results.extend(items)
            pages = meta.get("pages")
            if isinstance(pages, int) and pages > 0:
                if page >= pages:
                    break
            else:
                if len(items) < limit:
                    break
            page += 1
        return results

    async def validate_product_ids(self, product_ids: list[int]) -> list[int]:
        """Given a list of product IDs, return a sub-list of those that exist in Shoper."""
        if not product_ids:
            return []
        
        url = f"{self.base_url}{settings.shoper_products_path}"
        filters = {"product_id": {"in": product_ids}}
        params = {"filters": json.dumps(filters), "limit": str(len(product_ids))}
        headers = {"Authorization": f"Bearer {self.token}"}
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.get(url, params=params, headers=headers)
                r.raise_for_status()
                data = r.json()
                items = data.get("items") or data.get("list") or []
                existing_ids = {int(item["product_id"]) for item in items if "product_id" in item}
                return [pid for pid in product_ids if pid in existing_ids]
        except Exception as e:
            print(f"WARNING: Failed to validate product IDs: {e}")
            return product_ids

    async def fetch_order_statuses(self) -> List[Dict[str, Any]]:
        """Fetch all available order statuses from Shoper API.
        
        According to Shoper API documentation, statuses are available at /statuses endpoint.
        Resource structure includes: status_id, active, default, color, type, translations.
        """
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}
        
        # Try multiple possible endpoints for statuses
        possible_paths = ["/statuses", "/order-statuses", "/orders/statuses"]
        
        for path in possible_paths:
            try:
                url = f"{self.base_url}{path}"
                print(f"DEBUG: Trying to fetch statuses from {path}")
                
                async with httpx.AsyncClient(timeout=30) as client:
                    r = await client.get(url, headers=headers)
                    
                    if r.status_code == 200:
                        data = r.json()
                        
                        # Normalize response shape
                        if isinstance(data, dict):
                            items = data.get("list") or data.get("items") or []
                        elif isinstance(data, list):
                            items = data
                        else:
                            items = []
                        
                        if items:
                            print(f"SUCCESS: Fetched {len(items)} statuses from {path}")
                            return items
                    
            except Exception as e:
                print(f"DEBUG: Failed to fetch from {path}: {e}")
                continue
        
        # If all endpoints failed, try extracting from orders
        print("INFO: All direct endpoints failed, extracting statuses from orders")
        try:
            orders = await self.fetch_all_orders(limit=50)
            print(f"DEBUG: Fetched {len(orders)} orders for status extraction")
            
            # Extract unique statuses
            statuses_map: Dict[int, Dict[str, Any]] = {}
            
            for order in orders:
                status = order.get("status")
                if isinstance(status, dict):
                    status_id = status.get("status_id")
                    if status_id is not None and status_id not in statuses_map:
                        statuses_map[status_id] = {
                            "status_id": status_id,
                            "type": status.get("type"),
                            "color": status.get("color"),
                            "translations": status.get("translations"),
                            "default": status.get("default"),
                            "active": status.get("active"),
                            "order": status.get("order", 0)
                        }
            
            statuses_list = list(statuses_map.values())
            statuses_list.sort(key=lambda x: x.get("order", 0))
            
            if statuses_list:
                print(f"SUCCESS: Extracted {len(statuses_list)} unique statuses from orders")
                return statuses_list
                
        except Exception as e:
            print(f"WARNING: Failed to extract statuses from orders: {e}")
        
        # Final fallback: return common default statuses
        print("INFO: Returning default fallback statuses")
        return [
            {"status_id": 1, "type": 1, "color": "#3498DB", "translations": {"pl_PL": {"name": "Nowe"}}},
            {"status_id": 2, "type": 2, "color": "#F39C12", "translations": {"pl_PL": {"name": "W realizacji"}}},
            {"status_id": 3, "type": 3, "color": "#2ECC71", "translations": {"pl_PL": {"name": "Zakończone"}}},
            {"status_id": 4, "type": 4, "color": "#E74C3C", "translations": {"pl_PL": {"name": "Anulowane"}}}
        ]

    async def update_order_status(self, order_id: int, status_id: int) -> Dict[str, Any]:
        """Update order status in Shoper."""
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        url = f"{self.base_url}{settings.shoper_orders_path}/{order_id}"
        payload = {"status_id": status_id}
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.put(url, json=payload, headers=headers)
                if r.status_code in (200, 201, 204):
                    return {"ok": True, "order_id": order_id, "status_id": status_id}
                else:
                    error_body = r.text
                    return {"error": True, "status_code": r.status_code, "message": error_body}
        except Exception as e:
            return {"error": True, "exception": str(e)}


def _parse_float(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        return float(str(v).replace(",", "."))
    except Exception:
        return None


def _parse_int(v: Any) -> Optional[int]:
    try:
        if v is None or str(v).strip() == "":
            return None
        return int(v)
    except Exception:
        return None


def _extract_primary_image(item: Dict[str, Any]) -> Optional[str]:
    # Try common shapes
    img = item.get("main_image") or item.get("image") or item.get("images 1")
    if isinstance(img, dict):
        return img.get("url") or img.get("src")
    if isinstance(img, str):
        return img
    images = item.get("images")
    if isinstance(images, list) and images:
        i0 = images[0]
        if isinstance(i0, dict):
            return i0.get("url") or i0.get("src")
        if isinstance(i0, str):
            return i0
    return None


def _absolute_url(u: Optional[str]) -> Optional[str]:
    if not u:
        return u
    try:
        s = str(u)
        if s.startswith("http://") or s.startswith("https://"):
            return s
        # If only a bare filename was provided, prefer image base
        img_base = settings.shoper_image_base or ""
        if img_base and not s.startswith("/") and "://" not in s:
            return f"{img_base.rstrip('/')}/{s.lstrip('/')}"
        base = settings.shoper_base_url or ""
        if base:
            from urllib.parse import urlsplit
            sp = urlsplit(base)
            origin = f"{sp.scheme}://{sp.netloc}"
            if s.startswith("/"):
                return origin + s
            return origin + "/" + s
    except Exception:
        pass
    return u


def _extract_image_meta(item: Dict[str, Any]) -> Dict[str, Any]:
    meta: Dict[str, Any] = {"gfx_id": None, "extension": None, "unic_name": None, "url": None}
    main = item.get("main_image")
    if isinstance(main, dict):
        gfx_id = main.get("gfx_id")
        extension = main.get("extension")
        if gfx_id and extension:
            # Construct the URL based on the new, correct pattern
            path = f"/userdata/public/gfx/{gfx_id}.{extension}"
            meta["url"] = _absolute_url(path)
        
        # Still store the other meta fields for completeness
        meta["gfx_id"] = str(gfx_id) if gfx_id is not None else None
        meta["extension"] = extension if isinstance(extension, str) else None
        name_field = main.get("name") or main.get("unic_name")
        meta["unic_name"] = str(name_field) if name_field is not None else None

    # Fallback to the old extractor just in case, but the new logic should be primary
    if not meta["url"]:
        meta["url"] = _absolute_url(_extract_primary_image(item))
    return meta

def upsert_products(items: List[Dict[str, Any]]) -> Dict[str, int]:
    db = SessionLocal()
    created = 0
    updated = 0
    try:
        for it in items:
            shoper_id = _parse_int(it.get("product_id") or it.get("id") or it.get("productId"))
            if not shoper_id:
                continue
            code = (it.get("code") or it.get("sku") or "").strip() or None
            # Name: prefer pl_PL translation
            name = None
            tr = it.get("translations") or {}
            pl = tr.get("pl_PL") if isinstance(tr, dict) else None
            if isinstance(pl, dict):
                name = (pl.get("name") or "").strip() or None
            if not name:
                name = (it.get("name") or it.get("product") or "").strip() or None
            # Price/stock from nested stock
            stock_obj = it.get("stock") or {}
            price = _parse_float(stock_obj.get("price") or stock_obj.get("comp_price") or it.get("price") or it.get("price_gross"))
            stock = _parse_int(stock_obj.get("stock") or it.get("stock") or it.get("quantity"))
            # Image meta
            imeta = _extract_image_meta(it)
            image = imeta.get("url")
            # Categories/producer/tax
            categories = it.get("categories") if isinstance(it.get("categories"), list) else []
            cat_id = None
            if categories:
                try:
                    cat_id = int(categories[0])
                except Exception:
                    cat_id = None
            producer_id = _parse_int(it.get("producer_id"))
            tax_id = _parse_int(it.get("tax_id"))
            permalink = None
            if isinstance(pl, dict):
                permalink = pl.get("permalink")
            
            # New fields for duplicate recognition and price tracking
            tcggo_id = it.get("tcggo_id") # Assuming this comes from the Shoper API response or is passed in 'it'
            fingerprint_hash = it.get("fingerprint_hash") # Assuming this comes from the Shoper API response or is passed in 'it'

            row = db.query(Product).filter(Product.shoper_id == shoper_id).first()
            if not row:
                row = Product(shoper_id=shoper_id)
                db.add(row)
                created += 1
                # Flush to get the row.id for the foreign key in PriceHistory
                db.flush()
                db.refresh(row)
            else:
                updated += 1
            row.code = code
            row.name = name
            row.price = price
            row.stock = stock
            row.image = image
            row.updated_at = datetime.utcnow()
            row.category_id = cat_id
            try:
                import json
                row.categories = json.dumps(categories)
            except Exception:
                row.categories = None
            row.producer_id = producer_id
            row.tax_id = tax_id
            row.permalink = permalink
            row.main_image_gfx_id = imeta.get("gfx_id")
            row.main_image_extension = imeta.get("extension")
            row.main_image_unic_name = imeta.get("unic_name")
            row.tcggo_id = tcggo_id # Update new field
            row.fingerprint_hash = fingerprint_hash # Update new field

            # Price tracking
            if price is not None and (row.price is None or row.price != price):
                price_history_entry = PriceHistory(
                    product_id=row.id,
                    price=price,
                    timestamp=datetime.utcnow()
                )
                db.add(price_history_entry)
                row.last_price_update = datetime.utcnow() # Update new field

        db.commit()
        return {"created": created, "updated": updated}
    finally:
        db.close()


def _slugify(s: str) -> str:
    import re
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "item"


async def _category_from_set(client: ShoperClient, set_name: str | None) -> int | None:
    import json
    import unicodedata
    if not set_name:
        return None
    # Env override
    if settings.set_category_map_json:
        try:
            m = json.loads(settings.set_category_map_json)
            if isinstance(m, dict):
                for k, v in m.items():
                    if k.lower() == set_name.lower():
                        try:
                            return int(v)
                        except Exception:
                            return None
        except Exception:
            pass

    cats = await get_shoper_categories(client)

    def _norm(s: str) -> str:
        t = unicodedata.normalize("NFKD", s)
        t = "".join(ch for ch in t if not unicodedata.combining(ch))
        return t.strip().lower()

    target = _norm(set_name)
    if not cats:
        return None

    # exact (case/diacritics-insensitive)
    for c in cats:
        try:
            translations = c.get("translations", {})
            pl_trans = translations.get("pl_PL", {})
            nm = pl_trans.get("name") or c.get("name") or c.get("category")
            cid = c.get("category_id") or c.get("id")
            if isinstance(nm, str) and cid is not None and _norm(nm) == target:
                return int(cid)
        except Exception:
            continue
    # contains as weak fallback (avoid false positives)
    for c in cats:
        try:
            translations = c.get("translations", {})
            pl_trans = translations.get("pl_PL", {})
            nm = pl_trans.get("name") or c.get("name") or c.get("category")
            cid = c.get("category_id") or c.get("id")
            if isinstance(nm, str) and cid is not None and target and target in _norm(nm):
                return int(cid)
        except Exception:
            continue
    return None


async def _category_name_from_id(client: ShoperClient, category_id: int | None) -> str | None:
    if not category_id:
        return None
    
    cats = await get_shoper_categories(client)
    if not cats:
        return None

    for c in cats:
        try:
            cid = c.get("category_id") or c.get("id")
            if cid is not None and int(cid) == int(category_id):
                translations = c.get("translations", {})
                pl_trans = translations.get("pl_PL", {})
                return pl_trans.get("name") or c.get("name") or c.get("category")
        except (TypeError, ValueError, AttributeError):
            continue
    return None


def _set_code_from_name(name: str | None) -> str | None:
    if not name:
        return None
    # Env override
    try:
        if settings.set_code_map_json:
            m = json.loads(settings.set_code_map_json)
            if isinstance(m, dict):
                for k, v in m.items():
                    if k.lower() == name.lower():
                        try:
                            return str(v).upper()
                        except Exception:
                            pass
    except Exception:
        pass
    builtin = {
        "Destined Rivals": "DR",
        "Scarlet & Violet": "SV",
        "Paldean Fates": "PAF",
        "Temporal Forces": "TEF",
        "Surging Sparks": "SS",
        "Shrouded Fable": "SF",
        "Stellar Crown": "SC",
        "Twilight Masquerade": "TM",
        "Journey Together": "JT",
        "Obsidian Flames": "OF",
        "Prismatic Evolutions": "PE",
    }
    if name in builtin:
        return builtin[name]
    # Fallback: initials up to 3 letters
    try:
        txt = unicodedata.normalize("NFKD", name)
        txt = "".join(ch for ch in txt if not unicodedata.combining(ch))
        parts = [p for p in txt.replace("&", " ").split() if p]
        code = "".join(p[0] for p in parts)[:3].upper()
        return code or None
    except Exception:
        return None


def _get_attribute_group_from_fallback(attribute_id: str) -> str | None:
    """Load attribute_group_id from ids_dump.json fallback file.
    
    Returns: attribute_group_id as string, or None if not found.
    """
    try:
        import json
        from pathlib import Path
        dump_path = Path(__file__).parent.parent / "ids_dump.json"
        if not dump_path.exists():
            return None
        with open(dump_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        attrs = data.get("attributes", [])
        for attr in attrs:
            attr_id = str(attr.get("attribute_id", ""))
            if attr_id == attribute_id:
                group_id = attr.get("attribute_group_id")
                if group_id:
                    return str(group_id)
        return None
    except Exception as e:
        print(f"WARNING: Failed to load attribute_group_id from ids_dump.json: {e}")
        return None


def _get_category_attribute_groups(category_id: int) -> list[str]:
    """Get list of attribute group IDs assigned to a category.
    
    Returns: List of group_id strings (e.g., ["11", "12", "13", "14"])
    """
    try:
        import json
        from pathlib import Path
        dump_path = Path(__file__).parent.parent / "ids_dump.json"
        if not dump_path.exists():
            return []
        with open(dump_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        cats = data.get("categories", [])
        for cat in cats:
            cat_id = cat.get("category_id")
            if str(cat_id) == str(category_id):
                trans = cat.get("translations", {}).get("pl_PL", {})
                groups = trans.get("attribute_groups", [])
                return [str(g) for g in groups]
        return []
    except Exception as e:
        print(f"WARNING: Failed to load category attribute groups from ids_dump.json: {e}")
        return []


async def build_product_attributes_payload(client: ShoperClient, scan: Scan, candidate: Optional[ScanCandidate]) -> Dict[str, Dict[str, str]]:
    """Build Shoper attributes payload as nested object grouped by attribute_group_id.

    Returns: Dict like {"11": {"38": "Rare", "66": "Near Mint"}} with OPTION TEXT values!
    Shoper API expects text values, not numeric option IDs.
    Example from actual Shoper product: {"11": {"38": "Double Rare"}}
    """
    from .attributes import map_detected_to_shoper_attributes, simplify_attributes

    # Fetch and simplify available Shoper attributes
    try:
        attr_response = await client.fetch_attributes()
        shoper_attrs_raw = attr_response.get("items", [])
        shoper_attrs_simple = simplify_attributes(shoper_attrs_raw)
    except Exception as e:
        print(f"WARNING: Failed to fetch Shoper attributes: {e}")
        return {}

    if not shoper_attrs_simple:
        return {}

    # Build detected data dict from scan and candidate
    detected = {
        "language": scan.detected_language or "en",  # Default to English for Pokemon cards
        "variant": scan.detected_variant,
        "finish": scan.detected_variant,
        "condition": scan.detected_condition or "NM",
        "rarity": candidate.rarity if candidate and hasattr(candidate, 'rarity') else scan.detected_rarity,
        "energy": candidate.energy if candidate and hasattr(candidate, 'energy') else scan.detected_energy,
        "type": candidate.card_type if candidate and hasattr(candidate, 'card_type') else None,
    }

    print(f"DEBUG: Detected attributes data: {detected}")

    # Get mapping: { attribute_id_str: option_id_str }
    attr_id_mapping = map_detected_to_shoper_attributes(detected, shoper_attrs_raw)

    print(f"DEBUG: Raw mapping from attributes.py: {attr_id_mapping}")

    # Build index of attribute_id -> attribute_group_id
    # Fallback to ids_dump.json if API doesn't provide attribute_group_id
    attr_to_group = {}
    for attr_item in shoper_attrs_raw:
        attr_id = str(attr_item.get("attribute_id") or attr_item.get("id") or "")
        group_id = str(attr_item.get("attribute_group_id") or attr_item.get("group_id") or "")
        if attr_id:
            # If group_id is missing or "0", try to load from ids_dump.json fallback
            if not group_id or group_id == "0":
                fallback_group = _get_attribute_group_from_fallback(attr_id)
                if fallback_group:
                    group_id = fallback_group
                    print(f"DEBUG: Loaded group_id={group_id} for attribute_id={attr_id} from ids_dump.json fallback")
            attr_to_group[attr_id] = group_id if group_id else "0"

    # Convert to nested format grouped by attribute_group_id
    # Format: { "group_id": { "attribute_id": "option_id" } }
    attributes_payload: Dict[str, Dict[str, str]] = {}

    for attr_id_str, option_id_str in attr_id_mapping.items():
        group_id = attr_to_group.get(attr_id_str, "0")

        if group_id not in attributes_payload:
            attributes_payload[group_id] = {}

        # Values must be strings!
        attributes_payload[group_id][attr_id_str] = option_id_str

    print(f"INFO: Final attributes payload (nested object with group_id): {attributes_payload}")
    return attributes_payload


async def build_shoper_payload(client: ShoperClient, scan: Scan, candidate: Optional[ScanCandidate], set_id: int | None = None, gfx_id: str | None = None, related_ids: list[int] | None = None) -> Dict[str, Any]:
    """Build Shoper product payload for given scan + chosen candidate.
    
    NOTE: Attributes SHOULD NOT be included in the POST payload during product creation.
    They will be added in a separate PUT request after the product is created.
    
    Fetches full card details from provider to enrich descriptions with artist info and other metadata.
    """
    # Fetch full card details from provider for enriched descriptions
    card_details = None
    artist_name = None
    rarity_full = None
    hp = None
    supertype = None
    
    if candidate and candidate.provider_id:
        try:
            from .providers import get_provider
            provider = get_provider()
            card_details = await provider.details(candidate.provider_id)
            if card_details:
                artist_info = card_details.get("artist") or {}
                artist_name = artist_info.get("name")
                rarity_full = card_details.get("rarity")
                hp = card_details.get("hp")
                supertype = card_details.get("supertype")
                print(f"INFO: Enriched card details - Artist: {artist_name}, Rarity: {rarity_full}, HP: {hp}")
        except Exception as e:
            print(f"WARNING: Could not fetch card details for descriptions: {e}")
    # Build code like PKM-SETCODE-NUMBER when possible
    # Prefer deriving SETCODE from set/category name rather than provider set_code
    set_name_for_code = (scan.detected_set or ((candidate.set) if candidate else None))
    set_code = _set_code_from_name(set_name_for_code)
    number_for_code = (scan.detected_number or (candidate.number if candidate else None) or "").split("/")[0].strip()

    code_parts = [settings.code_prefix]
    if set_code:
        code_parts.append(_slugify(set_code).upper())
    if number_for_code:
        code_parts.append(number_for_code)

    # Add condition and variant to make code unique
    condition = scan.detected_condition or "NM"  # Default to Near Mint
    variant = scan.detected_variant or "NORMAL"  # Default to Normal

    # Normalize condition (e.g., "Near Mint" -> "NM", "Light Play" -> "LP")
    condition_map = {
        "near mint": "NM",
        "nm": "NM",
        "lightly played": "LP",
        "light play": "LP",
        "lp": "LP",
        "moderately played": "MP",
        "mp": "MP",
        "heavily played": "HP",
        "hp": "HP",
        "damaged": "DMG",
        "dmg": "DMG",
    }
    condition_code = condition_map.get(condition.lower(), condition.upper()[:3])

    # Normalize variant (e.g., "Reverse Holo" -> "REV")
    variant_map = {
        "normal": "NORM",
        "holo": "HOLO",
        "reverse holo": "REV",
        "reverse": "REV",
        "full art": "FA",
        "rainbow rare": "RR",
        "secret rare": "SR",
        "gold": "GOLD",
        "amazing rare": "AR",
    }
    variant_code = variant_map.get(variant.lower(), _slugify(variant).upper()[:4])

    code_parts.append(condition_code)
    code_parts.append(variant_code)

    # Join parts, ensuring no trailing dash if number is missing
    code = "-".join(p for p in code_parts if p) # Filter out empty parts

    # Price: from pricing field
    price = scan.price_pln_final or scan.price_pln or 0.0
    if price <= 0:
        price = 0.01  # Shoper API may reject price <= 0
    stock_qty = 1
    category_id = set_id if set_id is not None else await _category_from_set(client, scan.detected_set)

    # Image URL: prefer provider (TCGGO) image; fallback to template/base
    image_url = None
    cand_img = (candidate.image if candidate else None) or None
    if isinstance(cand_img, str) and cand_img.strip():
        image_url = cand_img.strip()
    elif settings.shoper_image_base:
        try:
            from pathlib import Path
            stored = getattr(scan, "stored_path", None)
            if isinstance(stored, str) and stored:
                bn = Path(stored).name
                if bn:
                    image_url = f"{settings.shoper_image_base.rstrip('/')}/{bn}"
        except Exception:
            image_url = None
        if not image_url:
            fname = settings.image_name_template.format(
                name=_slugify((scan.detected_name or (candidate.name if candidate else None)) or "card"),
                number=(candidate.number if candidate else None) or (scan.detected_number or ""),
                set=_slugify((scan.detected_set or (candidate.set if candidate else None)) or ""),
            )
            image_url = f"{settings.shoper_image_base.rstrip('/')}/{fname}"

    # Translations pl_PL
    nm = (candidate.name if candidate else None) or scan.detected_name or 'Karta'
    num = number_for_code
    st = (candidate.set if candidate else None) or (scan.detected_set or '')
    name = nm.strip() # Use only the card name as requested

    # Append variant to name if it exists and is not 'normal'
    variant = getattr(scan, 'detected_variant', None)
    if variant and variant.lower() != 'normal':
        name = f"{name} ({variant})"
    cond = getattr(scan, 'detected_condition', None) or ''
    
    # Map finish attribute to readable name
    finish_names = {
        "149": "Holo",
        "150": "Reverse Holo",
        "151": "Full Art",
        "155": "PokéBall Pattern",
        "156": "MasterBall Pattern",
        "157": "Gold",
        "158": "Rainbow",
        "184": "Normal"
    }
    finish_id = str(getattr(scan, 'detected_variant', '') or '184')
    finish_name = finish_names.get(finish_id, "Normal")
    
    # Enhanced SHORT description with SEO keywords
    short_desc_parts = [
        f"<ul style=\"margin:0 0 0.7em 1.2em; padding:0; font-size:1.14em;\">",
        f"<li><strong>{nm}</strong> - oryginalna karta Pokémon TCG</li>",
        f"<li style=\"margin-top:0.3em;\">Zestaw: <strong>{st}</strong></li>",
        f"<li style=\"margin-top:0.3em;\">Numer karty: <strong>#{num}</strong></li>",
    ]
    if finish_name and finish_name != "Normal":
        short_desc_parts.append(f"<li style=\"margin-top:0.3em;\">Wykończenie: <strong>{finish_name}</strong></li>")
    if rarity_full:
        short_desc_parts.append(f"<li style=\"margin-top:0.3em;\">Rzadkość: <strong>{rarity_full}</strong></li>")
    short_desc_parts.append(f"<li style=\"margin-top:0.3em;\">Stan: <strong>{cond or 'Near Mint (NM)'}</strong></li>")
    short_desc_parts.append("</ul>")
    short_desc = "".join(short_desc_parts)
    
    # Enhanced LONG description with artist, specs, and SEO content
    long_desc_parts = [
        f"<div style=\"font-size:1.10em;line-height:1.7;\">",
        f"<h2 style=\"margin:0 0 0.6em 0;font-size:1.4em;\">{nm} #{num} - {st}</h2>",
        f"<p style=\"margin-bottom:1em;\">Oryginalna karta <strong>Pokémon Trading Card Game</strong> w doskonałym stanie. "
        f"Idealna dla kolekcjonerów i graczy poszukujących wysokiej jakości kart do swojej kolekcji lub talii.</p>",
        "<h3 style=\"margin:1.2em 0 0.5em 0;font-size:1.2em;\">Specyfikacja karty:</h3>",
        "<ul style=\"margin:0 0 1em 1.5em;\">",
        f"<li><strong>Nazwa:</strong> {nm}</li>",
        f"<li><strong>Zestaw:</strong> {st}</li>",
        f"<li><strong>Numer karty:</strong> #{num}</li>",
    ]
    if finish_name and finish_name != "Normal":
        long_desc_parts.append(f"<li><strong>Wykończenie:</strong> {finish_name}</li>")
    if rarity_full:
        long_desc_parts.append(f"<li><strong>Rzadkość:</strong> {rarity_full}</li>")
    if hp:
        long_desc_parts.append(f"<li><strong>HP:</strong> {hp}</li>")
    if supertype:
        long_desc_parts.append(f"<li><strong>Typ:</strong> {supertype}</li>")
    if artist_name:
        long_desc_parts.append(f"<li><strong>Ilustrator:</strong> {artist_name}</li>")
    long_desc_parts.append(f"<li><strong>Stan karty:</strong> {cond or 'Near Mint (NM)'}</li>")
    long_desc_parts.append("</ul>")
    
    # Add artist appreciation paragraph if available
    if artist_name:
        long_desc_parts.extend([
            f"<p style=\"margin:1em 0;\">Grafika na tej karcie została stworzona przez utalentowanego artystę <strong>{artist_name}</strong>, "
            f"znanego z pięknych ilustracji w świecie Pokémon TCG. Każda karta to małe dzieło sztuki, które zasługuje na miejsce w Twojej kolekcji.</p>"
        ])
    
    # SEO and why buy section
    long_desc_parts.extend([
        "<h3 style=\"margin:1.5em 0 0.5em 0;font-size:1.2em;\">Dlaczego warto kupić w Kartoteka.shop?</h3>",
        "<ul style=\"margin:0 0 1em 1.5em;\">",
        "<li><strong>100% oryginalne karty</strong> - gwarancja autentyczności</li>",
        "<li><strong>Bezpieczna wysyłka</strong> - profesjonalne opakowanie chroniące kartę</li>",
        "<li><strong>Weryfikowany stan</strong> - szczegółowe zdjęcia i opis</li>",
        "<li><strong>Szybka realizacja</strong> - wysyłka w ciągu 3 dni roboczych</li>",
        "<li><strong>Profesjonalna obsługa</strong> - pomoc w doborze kart</li>",
        "</ul>",
        f"<p style=\"margin:1.5em 0 0 0;\">Szukasz konkretnej karty Pokémon? Karta <strong>{nm}</strong> z zestawu <strong>{st}</strong> "
        f"to doskonały wybór dla każdego kolekcjonera. Sprawdź naszą pełną ofertę kart Pokemon TCG!</p>",
        "</div>"
    ])
    long_desc = "".join(long_desc_parts)
    
    seo_title = f"{nm} #{num} {st} - Karta Pokemon TCG | Kartoteka.shop".strip()

    # Build payload - start with minimal required fields
    payload: Dict[str, Any] = {
        "category_id": int(category_id) if category_id is not None else 38,
        "unit_id": int(settings.default_unit_id),
        "currency_id": 1,
        "translations": {
            settings.default_language_code: {
                "name": name,
                "active": True,
                "description": long_desc,
                "short_description": short_desc,
                "seo_title": seo_title,
                "seo_description": f"{nm} #{num} z zestawu {st}. Oryginalna karta Pokemon TCG w stanie {cond or 'NM'}. Bezpieczna wysyłka, 100% autentyczność. Kup teraz!",
            }
        },
        "stock": {
            "price": float(f"{price:.2f}"),
            "stock": float(stock_qty),
            "availability_id": int(settings.default_availability_id),
            "delivery_id": int(settings.default_delivery_id),
        },
        "options": [],  # Array of option IDs - empty for products without variants
    }
    
    # Add optional fields only if they have values
    if code:
        payload["code"] = code
    if num:
        payload["additional_producer"] = str(num)
    if int(settings.default_tax_id) > 0:
        payload["tax_id"] = int(settings.default_tax_id)
    if int(settings.default_producer_id) > 0:
        payload["producer_id"] = int(settings.default_producer_id)

    # Add gfx_id to stock if image was uploaded
    if gfx_id:
        payload["stock"]["gfx_id"] = int(gfx_id)

    if related_ids:
        payload["related"] = related_ids

    return payload


async def _get_related_products_from_category(client: ShoperClient, category_id: int, limit: int = 10) -> list[int]:
    """Fetch product IDs from the same category using local DB and validate with Shoper API."""
    db = SessionLocal()
    try:
        print(f"DEBUG: Fetching related product candidates from category {category_id} using local DB...")
        products = (
            db.query(Product.shoper_id)
            .filter(Product.category_id == category_id)
            .order_by(desc(Product.shoper_id))
            .limit(limit * 2)  # Fetch more to have a buffer for validation
            .all()
        )
        candidate_ids = [p.shoper_id for p in products if p.shoper_id is not None]

        if not candidate_ids:
            print(f"INFO: No related product candidates found in local DB for category {category_id}")
            return []

        print(f"DEBUG: Validating existence of {len(candidate_ids)} product IDs with Shoper API...")
        existing_ids = await client.validate_product_ids(candidate_ids)
        
        final_ids = existing_ids[:limit]
        print(f"INFO: Found {len(final_ids)} valid related products in category {category_id}")
        return final_ids

    except Exception as e:
        print(f"ERROR: Failed to get related products: {e}")
        return []
    finally:
        db.close()


async def _find_and_update_product_by_code(client: ShoperClient, code: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Find product by code and update its stock quantity.
    
    Used when a product with the same code already exists in Shoper.
    Increments quantity by 1 instead of creating a duplicate.
    """
    try:
        # Search for product by code
        print(f"DEBUG: Searching for product with code '{code}'...")
        headers = {"Authorization": f"Bearer {client.token}", "Accept": "application/json"}
        url = f"{client.base_url}{settings.shoper_products_path}"
        params = {"code": code}
        
        async with httpx.AsyncClient(timeout=30) as http:
            r = await http.get(url, params=params, headers=headers)
            if r.status_code != 200:
                print(f"DEBUG: Failed to search for product by code: {r.status_code}")
                return {"error": True, "message": f"Failed to search for product"}
            
            search_result = r.json()
            items = search_result.get("items") or search_result.get("list") or []
            
            if not items:
                print(f"DEBUG: No product found with code '{code}'")
                return {"error": True, "message": f"No product found with code '{code}'"}
            
            # Get first match
            existing_product = items[0]
            product_id = existing_product.get("product_id") or existing_product.get("id")
            
            if not product_id:
                return {"error": True, "message": "Could not extract product_id"}
            
            print(f"INFO: Found existing product ID {product_id}, updating stock...")
            
            # Get current stock
            current_stock_obj = existing_product.get("stock") or {}
            current_stock_qty = float(current_stock_obj.get("stock") or 1)
            
            # Increment by 1
            new_stock_qty = current_stock_qty + 1.0
            
            # Update product stock
            update_payload = {
                "stock": {
                    "stock": new_stock_qty,
                    # Keep price the same as original
                    "price": float(current_stock_obj.get("price") or payload.get("stock", {}).get("price") or 0.01),
                }
            }
            
            r_update = await http.put(
                f"{client.base_url}{settings.shoper_products_path}/{product_id}",
                json=update_payload,
                headers=headers
            )
            
            if r_update.status_code not in (200, 201, 204):
                print(f"DEBUG: Failed to update product stock: {r_update.status_code} - {r_update.text}")
                return {"error": True, "message": f"Failed to update product stock"}
            
            print(f"SUCCESS: Updated product {product_id} stock from {current_stock_qty} to {new_stock_qty}")
            return {
                "ok": True,
                "json": {"product_id": int(product_id), "stock": new_stock_qty},
                "message": f"Updated existing product - stock increased to {new_stock_qty}",
                "payload": update_payload
            }
    
    except Exception as e:
        print(f"ERROR: Exception in _find_and_update_product_by_code: {e}")
        return {"error": True, "message": str(e)}


async def publish_scan_to_shoper(
    client: ShoperClient,
    scan: Scan,
    candidate: ScanCandidate,
    set_id: int | None = None,
    primary_image: str | Path | None = None,
    additional_images: list[str | Path] | None = None,
    related_ids: list[int] | None = None
) -> Dict[str, Any]:
    """
    Builds payload, creates a product in Shoper, and uploads primary and additional images.
    This now follows the recommended two-step process:
    1. POST product with minimal data.
    2. PUT attributes to the newly created product.
    """
    import tempfile
    import os

    temp_image_path = None

    # Determine the image source
    image_to_upload = primary_image
    print(f"DEBUG: primary_image={primary_image}")
    print(f"DEBUG: candidate.image={getattr(candidate, 'image', None)}")
    print(f"DEBUG: scan.stored_path={getattr(scan, 'stored_path', None)}")

    # Reject blob URLs - they're frontend-only and can't be used on backend
    if image_to_upload and isinstance(image_to_upload, str) and image_to_upload.startswith('blob:'):
        print(f"WARNING: Ignoring blob URL (frontend-only): {image_to_upload}")
        image_to_upload = None

    # If no primary_image provided, use candidate.image (TCGGO URL)
    if not image_to_upload and candidate.image:
        image_to_upload = candidate.image
        print(f"DEBUG: Using candidate.image (TCGGO URL): {image_to_upload}")

    # If no image_to_upload and scan has stored_path, use that
    if not image_to_upload and scan.stored_path and Path(scan.stored_path).is_file():
        image_to_upload = scan.stored_path
        print(f"DEBUG: Using scan.stored_path (local file): {image_to_upload}")

    print(f"INFO: Final image_to_upload={image_to_upload}")

    # Download image if it's a URL
    if image_to_upload and isinstance(image_to_upload, str) and image_to_upload.startswith('http'):
        print(f"INFO: Downloading image from URL: {image_to_upload}")
        try:
            async with httpx.AsyncClient(timeout=30) as http:
                r = await http.get(image_to_upload)
                r.raise_for_status()
                # Create temp file with appropriate extension
                ext = '.jpg'
                if 'content-type' in r.headers:
                    ct = r.headers['content-type'].lower()
                    if 'png' in ct:
                        ext = '.png'
                # Save to temp file
                with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                    tmp.write(r.content)
                    temp_image_path = tmp.name
                    image_to_upload = temp_image_path
                print(f"SUCCESS: Downloaded image to temp file: {temp_image_path} ({len(r.content)} bytes)")
        except Exception as e:
            print(f"ERROR: Failed to download image from {image_to_upload}: {e}")
            image_to_upload = None

    # Build attributes payload separately.
    attributes_payload = await build_product_attributes_payload(client, scan, candidate)
    if attributes_payload:
        print(f"INFO: Attributes payload prepared for separate PUT request: {attributes_payload}")

    # Build the main product payload WITHOUT attributes.
    payload = await build_shoper_payload(client, scan, candidate, set_id=set_id, gfx_id=None, related_ids=related_ids)

    # Log the complete payload (truncate for readability)
    import json
    payload_str = json.dumps(payload, indent=2, default=str, ensure_ascii=False)
    if len(payload_str) > 3000:
        payload_str = payload_str[:3000] + "\n... (truncated)"
    print(f"INFO: Product creation payload:\n{payload_str}")

    # Send create product request
    headers = {
        "Authorization": f"Bearer {client.token}",
        "Accept": "application/json",
    }
    url = f"{client.base_url}{settings.shoper_products_path}"

    async with httpx.AsyncClient(timeout=30) as http:
        if settings.publish_dry_run:
            return {"dry_run": True, "payload": payload}
        
        # Log payload size for debugging
        import json as json_module
        payload_json_str = json_module.dumps(payload, default=str, ensure_ascii=False)
        payload_size = len(payload_json_str)
        print(f"DEBUG: POST {url} with {payload_size} bytes")
        
        # Use json= parameter which handles serialization AND sets Content-Type automatically
        r = await http.post(url, json=payload, headers=headers)

        # NEW: Handle invalid 'related' ID error and retry
        if r.status_code == 400:
            try:
                error_data = r.json()
                error_desc = error_data.get("error_description", "").lower()
                if "related" in error_desc and ("nie znaleziono" in error_desc or "not found" in error_desc):
                    print(f"WARNING: Invalid 'related' ID detected. Retrying without related products. Error: {error_desc}")
                    payload.pop("related", None) # Remove the problematic field
                    r = await http.post(url, json=payload, headers=headers) # Retry the request
            except Exception as e:
                print(f"DEBUG: Could not handle potential 'related' field error: {e}")
        
        # Handle "code already exists" error - update existing product instead
        if r.status_code == 400:
            try:
                error_response = r.json()
                error_desc = error_response.get("error_description", "").lower()
                # Check if error is about duplicate code
                if "już istnieje" in error_desc or "already exists" in error_desc or "code" in error_desc.lower():
                    code = payload.get("code")
                    if code:
                        print(f"INFO: Product with code '{code}' already exists. Attempting to update quantity...")
                        # Try to find and update existing product by code
                        update_result = await _find_and_update_product_by_code(client, code, payload)
                        if update_result.get("ok"):
                            print(f"SUCCESS: Updated existing product with code '{code}'")
                            return update_result
            except Exception as e:
                print(f"DEBUG: Error handling duplicate code: {e}")
        
        try:
            r.raise_for_status()
            response_json = r.json()

            # Parse product_id from various response formats
            product_id = None
            if isinstance(response_json, dict):
                product_id = response_json.get("product_id") or response_json.get("id")
            elif isinstance(response_json, (int, str)):
                try:
                    product_id = int(response_json)
                except (ValueError, TypeError):
                    pass

            print(f"INFO: Extracted product_id={product_id} from response type={type(response_json).__name__}")

            # DEBUG: Verify related products
            if product_id:
                print(f"DEBUG: Verifying related products for created product {product_id}...")
                created_product_data = await client.get_product(product_id)
                if created_product_data:
                    related_products_from_get = created_product_data.get("related")
                    print(f"DEBUG: Product {product_id} verification - related products from GET: {related_products_from_get}")
                else:
                    print(f"WARNING: Could not fetch product {product_id} for verification.")

            # STEP 2: Set attributes in a separate PUT request if product was created
            if product_id and attributes_payload:
                # Re-introduce filtering logic before setting attributes
                category_id_for_filter = payload.get("category_id")
                filtered_attributes = attributes_payload
                if category_id_for_filter:
                    allowed_groups = _get_category_attribute_groups(int(category_id_for_filter))
                    if allowed_groups:
                        filtered_attributes = {
                            group_id: attrs 
                            for group_id, attrs in attributes_payload.items() 
                            if group_id in allowed_groups
                        }
                        if filtered_attributes != attributes_payload:
                            removed_groups = set(attributes_payload.keys()) - set(filtered_attributes.keys())
                            print(f"INFO: Filtered out attribute groups {removed_groups} (not assigned to category {category_id_for_filter})")
                    else:
                        print(f"WARNING: Could not determine allowed attribute groups for category {category_id_for_filter}, sending all attributes.")

                if not filtered_attributes:
                    print("INFO: No valid attributes to set for this product's category.")
                else:
                    print(f"INFO: Product {product_id} created. Now setting filtered attributes...")
                    attr_result = await client.set_product_attributes(product_id, filtered_attributes)
                    if attr_result.get("ok"):
                        print(f"SUCCESS: Attributes set for product {product_id}.")
                    else:
                        # Log the error but don't fail the whole process
                        print(f"WARNING: Failed to set attributes for product {product_id}. Reason: {attr_result.get('message', 'Unknown error')}")

            # Set related products in a separate PUT request
            if product_id and related_ids:
                print(f"INFO: Setting related products for product {product_id}...")
                update_result = await client.update_product(product_id, {"related": related_ids})
                if update_result.get("ok"):
                    print(f"SUCCESS: Related products set for product {product_id}.")
                else:
                    print(f"WARNING: Failed to set related products for product {product_id}. Reason: {update_result.get('text', 'Unknown error')}")

            # Upload main image AFTER product creation (via product-images endpoint)
            if product_id and image_to_upload:
                print(f"INFO: Uploading main product image: {image_to_upload}")
                try:
                    img_result = await client.upload_product_image(product_id, str(image_to_upload), main=True)
                    if img_result.get("ok"):
                        print(f"SUCCESS: Main image uploaded to product {product_id}")
                    else:
                        error_msg = img_result.get("message", "Unknown error")
                        print(f"WARNING: Failed to upload main image to product {product_id}: {error_msg}")
                except Exception as e:
                    print(f"ERROR: Exception while uploading main image: {e}")

            # If product created and there are additional images, upload them
            if product_id and additional_images:
                for img_path in additional_images:
                    if isinstance(img_path, (str, Path)) and Path(img_path).is_file():
                        try:
                            await client.upload_product_image(product_id, str(img_path), main=False)
                        except Exception as e:
                            print(f"ERROR: Failed to upload additional image {img_path} for product {product_id}: {e}")

            # Normalize response to always include product_id in json
            normalized_response = response_json if isinstance(response_json, dict) else {}
            if product_id and "product_id" not in normalized_response:
                normalized_response["product_id"] = product_id

            return {"ok": True, "json": normalized_response, "payload": payload}
        except Exception as e:
            return {"error": True, "status_code": r.status_code, "text": r.text, "payload": payload, "exception": str(e)}