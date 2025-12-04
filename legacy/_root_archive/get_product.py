import argparse
import json
import os
from typing import Any, Dict, Iterable, Mapping, Optional

from dotenv import load_dotenv

from shoper_client import ShoperClient


def _first_product(payload: Any) -> Optional[Dict[str, Any]]:
    """Extract the first product-like mapping from an API response."""
    def _iter_items(obj: Any) -> Iterable[Mapping[str, Any]]:
        if isinstance(obj, Mapping):
            # common containers
            for key in ("list", "items", "data", "results", "products"):
                container = obj.get(key)
                if isinstance(container, list):
                    for entry in container:
                        if isinstance(entry, Mapping):
                            yield entry
                elif isinstance(container, Mapping):
                    yield from _iter_items(container)
            # flat product
            if any(k in obj for k in ("product_id", "id", "code")):
                yield obj
        elif isinstance(obj, list):
            for entry in obj:
                if isinstance(entry, Mapping):
                    yield entry

    for entry in _iter_items(payload):
        return dict(entry)
    return None


def _print_candidates(resp: Any) -> None:
    try:
        items = []
        if isinstance(resp, dict):
            items = resp.get("list") or resp.get("items") or []
        if not isinstance(items, list):
            return
        print("\nPodobne wyniki:")
        for it in items[:20]:
            if not isinstance(it, dict):
                continue
            pid = it.get("product_id") or it.get("id")
            code = it.get("code") or it.get("product_code")
            name = it.get("name") or (it.get("translations") or {}).get("pl_PL", {}).get("name") if isinstance(it.get("translations"), dict) else None
            print(f" - ID: {pid} | CODE: {code} | NAME: {name}")
    except Exception:
        pass


def fetch_by_code(client: ShoperClient, code: str) -> Dict[str, Any]:
    # Use convenience key; client normalises it to filters[code]
    resp = client.search_products(filters={"code": code}, page=1, per_page=10)
    # Pick exact code match to avoid unrelated results
    code_norm = code.strip().lower()
    candidate = None
    if isinstance(resp, dict):
        items = resp.get("list") or resp.get("items") or []
        if isinstance(items, list):
            for it in items:
                if not isinstance(it, dict):
                    continue
                code_val = (it.get("code") or it.get("product_code") or "").strip().lower()
                if code_val == code_norm:
                    candidate = dict(it)
                    break
    product = _first_product(resp)
    if candidate:
        product = candidate
    if not product:
        # Fuzzy search by 'search' to show nearest candidates
        fuzzy = client.search_products(filters={"search": code}, page=1, per_page=20)
        _print_candidates(fuzzy)
        raise SystemExit(f"Nie znaleziono produktu o kodzie: {code}")
    return product


def fetch_by_id(client: ShoperClient, pid: str) -> Dict[str, Any]:
    # Try to fetch a single product; if the API doesn't expose a direct show endpoint,
    # fall back to a search on id filters
    try:
        resp = client.get(f"products/{pid}")
        if isinstance(resp, Mapping) and resp:
            return dict(resp)
    except Exception:
        pass
    # fallback search
    resp = client.search_products(filters={"id": pid}, page=1, per_page=1)
    product = _first_product(resp)
    if not product:
        raise SystemExit(f"Nie znaleziono produktu o ID: {pid}")
    return product


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pobierz pełne dane istniejącego produktu z Shoper API"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--code", help="Kod produktu (product_code)")
    group.add_argument("--id", help="ID produktu w Shoper")
    parser.add_argument(
        "--out",
        help="Zapisz wynik do pliku JSON (opcjonalnie)",
    )
    args = parser.parse_args()

    load_dotenv()

    client = ShoperClient(
        base_url=os.getenv("SHOPER_API_URL"),
        token=os.getenv("SHOPER_API_TOKEN"),
        client_id=os.getenv("SHOPER_CLIENT_ID"),
    )

    if args.code:
        product = fetch_by_code(client, args.code.strip())
    else:
        product = fetch_by_id(client, args.id.strip())

    # Pretty print to terminal
    print(json.dumps(product, ensure_ascii=False, indent=2, default=str))

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(product, fh, ensure_ascii=False, indent=2)
        print(f"\nZapisano do pliku: {args.out}")


if __name__ == "__main__":
    main()
