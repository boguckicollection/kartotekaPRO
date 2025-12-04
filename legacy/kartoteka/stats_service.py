"""Service computing warehouse statistics from Shoper API and caching them.

Exposed helpers:
  - compute_stats(client) -> dict
  - compute_and_store(client, db) -> dict
  - get_cached_or_compute(client) -> dict
"""

from __future__ import annotations

import json
import os
import datetime as _dt
from typing import Dict, Any, Iterable

from .inventory_service import WarehouseInventoryService
from .local_db import LocalInventoryDB


def _today() -> _dt.date:
    return _dt.date.today()


def compute_stats(client) -> Dict[str, Any]:
    """Return statistics aggregated from Shoper products/orders.

    Current metrics:
      - unsold_count, unsold_total (sumy po ilości i cenie: price * quantity)
      - sold_count, sold_total (na podstawie zamówień w wybranych statusach)
      - added_count_total, added_value_total (po ilości)
      - daily_additions (ostatnie 7 dni): { YYYY-MM-DD: count }
    """
    svc = WarehouseInventoryService(client=client)

    # Aggregate over products inventory
    unsold_count = 0  # suma ilości w magazynie
    unsold_total = 0.0  # suma wartości w magazynie (price * quantity)
    sold_count = 0
    sold_total = 0.0
    added_count_total = 0
    added_value_total = 0.0
    daily_additions: Dict[str, int] = {}

    page = 1
    per_page = 200
    start_7 = _today() - _dt.timedelta(days=6)

    while True:
        response = client.get_inventory(page=page, per_page=per_page)
        products = svc._extract_product_list(response)
        if not products:
            break
        for p in products:
            item = svc._normalise_api_product(p)
            if item is None:
                continue
            price = 0.0
            try:
                price = float(str(item.price).replace(",", ".")) if item.price else 0.0
            except Exception:
                price = 0.0
            qty = 0
            try:
                qty = int(item.quantity or 0)
            except Exception:
                qty = 0

            # Skladujemy wartość magazynu wg ilości
            if qty > 0 and not item.sold:
                unsold_count += qty
                unsold_total += price * qty

            # Addition date
            date_text = str(item.added_at or "").split("T", 1)[0]
            try:
                added_date = _dt.date.fromisoformat(date_text) if date_text else None
            except ValueError:
                added_date = None
            if added_date is not None:
                added_count_total += max(1, qty) if qty else 1
                added_value_total += price * (max(1, qty) if qty else 1)
                if added_date >= start_7:
                    key = added_date.isoformat()
                    daily_additions[key] = daily_additions.get(key, 0) + 1

        current_page = svc._extract_current_page(response)
        total_pages = svc._extract_total_pages(response)
        if current_page >= total_pages:
            break
        page = current_page + 1

    # Ensure last 7 days keys exist
    cur = start_7
    while cur <= _today():
        daily_additions.setdefault(cur.isoformat(), 0)
        cur += _dt.timedelta(days=1)

    # Sales from orders -------------------------------------------------
    sold_stats = _compute_sales_from_orders(client)

    return {
        "unsold_count": int(unsold_count),
        "unsold_total": float(round(unsold_total, 2)),
        "sold_count": int(sold_stats.get("count", 0)),
        "sold_total": float(round(float(sold_stats.get("total", 0.0)), 2)),
        "added_count_total": int(added_count_total),
        "added_value_total": float(round(added_value_total, 2)),
        "daily_additions": dict(sorted(daily_additions.items())),
        "ts": _dt.datetime.now().isoformat(timespec="seconds"),
    }


def _compute_sales_from_orders(client) -> Dict[str, Any]:
    """Aggregate sold items/value from orders.

    Statusy traktowane jako sprzedaż można nadpisać przez env
    SHOPER_SOLD_STATUSES (lista rozdzielana przecinkami), domyślnie:
        paid,completed,finished,shipped
    """
    # Names (status type) and numeric IDs can be provided via env.
    # If IDs are provided, try them first as they are unambiguous.
    status_names: list[str] = []
    status_ids: list[str] = []
    try:
        raw_names = os.getenv("SHOPER_SOLD_STATUSES", "paid,completed,finished,shipped")
        status_names = [s.strip() for s in raw_names.replace(";", ",").split(",") if s.strip()]
    except Exception:
        status_names = ["paid", "completed", "finished", "shipped"]
    try:
        raw_ids = os.getenv("SHOPER_SOLD_STATUS_IDS", "")
        status_ids = [s.strip() for s in raw_ids.replace(";", ",").split(",") if s.strip()]
    except Exception:
        status_ids = []

    count = 0
    total = 0.0
    page = 1
    per_page = 50
    def _sum_from(filters: dict) -> tuple[int, float]:
        _count, _total = 0, 0.0
        p = 1
        while True:
            resp = client.list_orders(filters, page=p, per_page=per_page, include_products=True)
            if not isinstance(resp, dict) or not resp.get("list"):
                break
            for order in resp.get("list", []) or []:
                for line in (order.get("products") or []):
                    try:
                        qty = int(float(str(line.get("quantity") or 0)))
                    except Exception:
                        qty = 0
                    try:
                        price = float(str(line.get("price_gross") or line.get("price") or 0).replace(",", "."))
                    except Exception:
                        price = 0.0
                    _count += qty
                    _total += price * qty
            p += 1
            if p > 1000:
                break
        return _count, _total

    try:
        # Try by IDs first if provided
        if status_ids:
            c, t = _sum_from({"status_id[in]": ",".join(status_ids)})
            count += c
            total += t
        else:
            # Fallback to names/types
            c, t = _sum_from({"status": ",".join(status_names)})
            count += c
            total += t
        # If nothing found, try the other form as a fallback
        if count == 0 and status_ids:
            c, t = _sum_from({"status": ",".join(status_names)})
            count += c
            total += t
        elif count == 0 and not status_ids:
            # maybe IDs are configured elsewhere
            alt_ids = os.getenv("SHOPER_SOLD_STATUS_IDS_ALT", "")
            if alt_ids:
                c, t = _sum_from({"status_id[in]": alt_ids})
                count += c
                total += t
    except Exception:
        return {"count": 0, "total": 0.0}
    return {"count": count, "total": total}


def compute_and_store(client, db: LocalInventoryDB | None = None) -> Dict[str, Any]:
    if db is None:
        db = LocalInventoryDB()
    data = compute_stats(client)
    try:
        db.save_stats_snapshot(json.dumps(data, ensure_ascii=False))
    except Exception:
        pass
    return data


def get_cached_or_compute(client, db: LocalInventoryDB | None = None) -> Dict[str, Any]:
    if db is None:
        db = LocalInventoryDB()
    try:
        raw = db.get_latest_stats()
        if raw:
            return json.loads(raw)
    except Exception:
        pass
    # By default fetch stats on start; allow disabling via env
    fetch_on_start = str(os.getenv("STATS_FETCH_ON_START", "1")).strip().lower() in {"1", "true", "yes", "on"}
    if not fetch_on_start:
        return {}
    return compute_and_store(client, db)
