"""Lightweight local SQLite cache for products and warehouse locations.

This module persists a minimal subset of product data so the application can
browse inventory quickly and work offline. It is intentionally simple and
focused on the magazyn use‑case.
"""

from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from typing import Iterable, Mapping, Optional


@dataclass(frozen=True)
class DBItem:
    code: str
    name: str
    price: str
    image: str
    active: int
    quantity: int
    warehouse_codes: tuple[str, ...]
    updated_at: str


class LocalInventoryDB:
    """Simple SQLite wrapper for the local inventory cache.

    Schema:
      - products(id, code UNIQUE, name, price, image, active, updated_at)
      - levels(product_id, location_code, quantity, PRIMARY KEY(product_id, location_code))
      - sync_state(key PRIMARY KEY, value)
    """

    def __init__(self, path: str = "inventory.sqlite") -> None:
        self.path = path
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._ensure_schema()

    # ------------------------------------------------------------------
    # schema
    # ------------------------------------------------------------------
    def _ensure_schema(self) -> None:
        with self._lock:
            cur = self.conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT UNIQUE,
                    name TEXT,
                    price TEXT,
                    image TEXT,
                    active INTEGER,
                    updated_at TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS levels (
                    product_id INTEGER,
                    location_code TEXT,
                    quantity INTEGER,
                    PRIMARY KEY(product_id, location_code)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS sync_state (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS stats_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT DEFAULT (datetime('now')),
                    data TEXT
                )
                """
            )
            # indexes for fast lookups
            cur.execute("CREATE INDEX IF NOT EXISTS idx_products_code ON products(code)")
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_levels_code ON levels(location_code)"
            )
            self.conn.commit()

    # ------------------------------------------------------------------
    # sync state
    # ------------------------------------------------------------------
    def get_state(self, key: str) -> Optional[str]:
        with self._lock:
            cur = self.conn.cursor()
            cur.execute("SELECT value FROM sync_state WHERE key=?", (key,))
            row = cur.fetchone()
            return str(row[0]) if row else None

    def set_state(self, key: str, value: str) -> None:
        with self._lock:
            cur = self.conn.cursor()
            cur.execute(
                "INSERT INTO sync_state(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )
            self.conn.commit()

    # ------------------------------------------------------------------
    # upsert helpers
    # ------------------------------------------------------------------
    def upsert_item(self, item: Mapping[str, object]) -> None:
        """Insert or update a product and its locations.

        Expected keys in ``item``:
          - code, name, price, image, active (int 0/1), updated_at (str)
          - warehouse_codes (Iterable[str]) and quantity (int)
        """

        code = str(item.get("code") or "").strip()
        if not code:
            return
        name = str(item.get("name") or "").strip()
        price = str(item.get("price") or "").strip()
        image = str(item.get("image") or "").strip()
        active = 1 if int(item.get("active") or 1) else 0
        updated_at = str(item.get("updated_at") or "").strip()
        try:
            quantity = int(item.get("quantity") or 0)
        except Exception:
            quantity = 0
        codes: list[str] = []
        raw_codes = item.get("warehouse_codes")
        if isinstance(raw_codes, Iterable):
            for c in raw_codes:
                c_str = str(c or "").strip()
                if c_str:
                    codes.append(c_str)

        with self._lock:
            cur = self.conn.cursor()
            cur.execute(
                "INSERT INTO products(code, name, price, image, active, updated_at) "
                "VALUES(?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(code) DO UPDATE SET name=excluded.name, price=excluded.price, image=excluded.image, active=excluded.active, updated_at=excluded.updated_at",
                (code, name, price, image, active, updated_at),
            )
            # fetch row id
            cur.execute("SELECT id FROM products WHERE code=?", (code,))
            row = cur.fetchone()
            if row is None:
                self.conn.commit()
                return
            pid = int(row[0])
            # replace levels for the product
            cur.execute("DELETE FROM levels WHERE product_id=?", (pid,))
            if codes:
                for loc in codes:
                    cur.execute(
                        "INSERT OR REPLACE INTO levels(product_id, location_code, quantity) VALUES(?, ?, ?)",
                        (pid, loc, 1),
                    )
            else:
                # keep a synthetic aggregate level when locations are unknown
                cur.execute(
                    "INSERT OR REPLACE INTO levels(product_id, location_code, quantity) VALUES(?, '', ?)",
                    (pid, max(quantity, 1) or 1),
                )
            self.conn.commit()

    # ------------------------------------------------------------------
    # querying
    # ------------------------------------------------------------------
    def get_items(self) -> list[DBItem]:
        with self._lock:
            cur = self.conn.cursor()
            cur.execute(
                "SELECT p.id, p.code, p.name, p.price, p.image, p.active, p.updated_at "
                "FROM products p ORDER BY p.name COLLATE NOCASE"
            )
            products = cur.fetchall()
            if not products:
                return []
            ids = [int(r[0]) for r in products]
            placeholders = ",".join(["?"] * len(ids))
            cur.execute(
                f"SELECT product_id, location_code, quantity FROM levels WHERE product_id IN ({placeholders})",
                ids,
            )
            levels_map: dict[int, list[tuple[str, int]]] = {}
            for row in cur.fetchall():
                pid = int(row[0])
                levels_map.setdefault(pid, []).append((str(row[1] or ""), int(row[2] or 0)))

            result: list[DBItem] = []
            for row in products:
                pid = int(row[0])
                code = str(row[1] or "")
                name = str(row[2] or "")
                price = str(row[3] or "")
                image = str(row[4] or "")
                active = int(row[5] or 0)
                updated_at = str(row[6] or "")
                levels = levels_map.get(pid, [])
                codes = tuple(lc for lc, _q in levels if lc)
                quantity = sum(q for _lc, q in levels) or max(1, len(codes))
                result.append(
                    DBItem(
                        code=code,
                        name=name,
                        price=price,
                        image=image,
                        active=active,
                        quantity=quantity,
                        warehouse_codes=codes,
                        updated_at=updated_at,
                    )
                )
            return result

    # ------------------------------------------------------------------
    # stats snapshots
    # ------------------------------------------------------------------
    def save_stats_snapshot(self, data_json: str) -> None:
        with self._lock:
            cur = self.conn.cursor()
            cur.execute(
                "INSERT INTO stats_snapshots(data) VALUES(?)",
                (data_json,),
            )
            self.conn.commit()

    def get_latest_stats(self) -> Optional[str]:
        with self._lock:
            cur = self.conn.cursor()
            cur.execute(
                "SELECT data FROM stats_snapshots ORDER BY id DESC LIMIT 1"
            )
            row = cur.fetchone()
            return str(row[0]) if row else None
