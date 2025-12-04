from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, Dict

from .db import SessionLocal, InventoryItem, init_db


HEADERS = [
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


def read_csv(path: str) -> Iterable[Dict[str, str]]:
    p = Path(path)
    with p.open("r", encoding="utf-8", newline="") as fh:
        sample = fh.read(4096)
        fh.seek(0)
        # delimiter ; or ,
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=";,")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(fh, dialect=dialect)
        for row in reader:
            yield row


def parse_float(v: str | None):
    if v is None:
        return None
    try:
        s = str(v).replace(",", ".").strip()
        return float(s)
    except Exception:
        return None


def run(path: str) -> dict:
    init_db()
    db = SessionLocal()
    created = 0
    updated = 0
    try:
        for row in read_csv(path):
            data = {k: (row.get(k) or "").strip() for k in HEADERS}
            price = parse_float(data.get("price"))
            sold = None
            try:
                sold = int((data.get("sold") or "").strip() or 0)
            except Exception:
                sold = None
            # UPSERT by warehouse_code + number + set + name combo
            key_wc = data.get("warehouse_code") or None
            q = db.query(InventoryItem)
            if key_wc:
                q = q.filter(InventoryItem.warehouse_code == key_wc)
            else:
                q = q.filter(
                    InventoryItem.name == data.get("name"),
                    InventoryItem.number == data.get("number"),
                    InventoryItem.set == data.get("set"),
                )
            item = q.first()
            if not item:
                item = InventoryItem()
                created += 1
                db.add(item)
            else:
                updated += 1

            item.name = data.get("name") or None
            item.number = data.get("number") or None
            item.set = data.get("set") or None
            item.warehouse_code = key_wc
            item.price = price
            item.image = data.get("image") or None
            item.variant = data.get("variant") or None
            item.sold = sold
            item.added_at = data.get("added_at") or None
        db.commit()
        return {"created": created, "updated": updated}
    finally:
        db.close()


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Import magazyn.csv into Inventory table")
    ap.add_argument("--csv", default="/app/storage/magazyn.csv", help="CSV path")
    args = ap.parse_args()
    res = run(args.csv)
    print(f"Imported: {res}")

