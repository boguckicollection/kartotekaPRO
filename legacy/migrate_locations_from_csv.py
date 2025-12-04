"""One-off migration: assign warehouse locations from magazyn.csv to local DB.

Usage:
  python migrate_locations_from_csv.py [--csv path]

Assumes you have already synced products from Shoper into the local DB
(`inventory.sqlite`). The script will:
  - read warehouse codes from the CSV (column: warehouse_code)
  - resolve product code (prefer 'product_code', fallback to 'code')
  - update the local DB levels for matched products
  - print a short summary (updated, missing codes, unmatched rows)

It does NOT push any data to Shoper; locations are internal to Kartoteka.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
from typing import Iterable

from kartoteka.local_db import LocalInventoryDB
from kartoteka import csv_utils


def _iter_codes(value: str | None) -> list[str]:
    if not value:
        return []
    raw = [c.strip() for c in str(value).split(";") if c.strip()]
    # keep only valid K..R..P.. codes
    pat = re.compile(r"^K(\d+)R(\d+)P(\d+)$")
    return [c for c in raw if pat.match(c)]


def _read_csv(path: str) -> list[dict]:
    # Try via csv_utils (respects env overrides)
    if os.path.abspath(path) == os.path.abspath(csv_utils.WAREHOUSE_CSV):
        return csv_utils.get_warehouse_inventory()
    # Fallback lightweight reader
    with open(path, encoding="utf-8", newline="") as fh:
        sample = fh.read(2048)
        fh.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=";,")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(fh, dialect=dialect)
        return list(reader)


def main() -> None:
    ap = argparse.ArgumentParser(description="Assign warehouse codes from CSV to local DB")
    ap.add_argument("--csv", default=csv_utils.WAREHOUSE_CSV, help="Path to magazyn.csv")
    args = ap.parse_args()

    rows = _read_csv(args.csv)
    if not rows:
        print(f"No rows found in {args.csv}")
        return

    db = LocalInventoryDB()

    updated = 0
    skipped_no_code = 0
    unmatched = 0

    for row in rows:
        # resolve product code
        code = str(row.get("product_code") or row.get("code") or "").strip()
        if not code:
            skipped_no_code += 1
            continue
        codes = _iter_codes(row.get("warehouse_code") or row.get("kod_magazynowy") or row.get("warehouse codes"))
        if not codes:
            continue
        # Upsert/update product levels in DB; do not alter other fields
        db.upsert_item(
            {
                "code": code,
                # keep minimal fields to avoid clobbering:
                "name": str(row.get("name") or row.get("nazwa") or row.get("nazwa_karty") or "").strip(),
                "price": str(row.get("price") or row.get("cena") or "").strip(),
                "image": str(row.get("images 1") or row.get("image") or "").strip(),
                "active": 1,
                "quantity": max(1, len(codes)),
                "warehouse_codes": codes,
                "updated_at": "",
            }
        )
        updated += 1

    print(
        "Migration finished:\n"
        f" - Updated entries: {updated}\n"
        f" - Rows without product_code: {skipped_no_code}\n"
        f" - Unmatched (by code, not applicable with upsert): {unmatched}\n"
        f"Local DB: {db.path}"
    )


if __name__ == "__main__":
    main()

