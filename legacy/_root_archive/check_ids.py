import os
import json
import argparse
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from dotenv import load_dotenv
from shoper_client import ShoperClient

# Wczytaj konfigurację z pliku .env
load_dotenv()


def _coerce_id(entry: Mapping[str, Any], preferred: Iterable[str]) -> Optional[str]:
    for key in preferred:
        if key in entry and entry.get(key) not in (None, ""):
            return str(entry.get(key))
    # fallback: first key ending with _id or plain id
    for key, value in entry.items():
        if value in (None, ""):
            continue
        k = str(key).lower()
        if k.endswith("_id") or k == "id":
            return str(value)
    return None


def _coerce_name(entry: Mapping[str, Any]) -> str:
    # Prefer top-level name
    name = entry.get("name")
    if isinstance(name, str) and name.strip():
        return name
    # Look into translations-like structures
    translations = entry.get("translations")
    if isinstance(translations, Mapping):
        for lang_data in translations.values():
            if isinstance(lang_data, Mapping):
                n = lang_data.get("name")
                if isinstance(n, str) and n.strip():
                    return n
    # Try common alternatives
    for key in ("label", "title", "value"):
        v = entry.get(key)
        if isinstance(v, str) and v.strip():
            return v
    # As a last resort stringified entry id
    return "Brak nazwy"


def _extract_attribute_values(attr: Mapping[str, Any]) -> List[Tuple[Any, str]]:
    values_source = (
        attr.get("dictionary")
        or attr.get("values")
        or attr.get("options")
        or []
    )
    items: List[Tuple[Any, str]] = []
    iterable: Iterable[Any]
    if isinstance(values_source, Mapping):
        iterable = values_source.items()
    else:
        iterable = values_source
    for value in iterable:
        key: Any
        label: Any
        if isinstance(value, tuple) and len(value) == 2:
            key, label = value
        elif isinstance(value, Mapping):
            key = (
                value.get("value_id")
                or value.get("id")
                or value.get("value")
                or value.get("key")
            )
            label = (
                value.get("name")
                or value.get("label")
                or value.get("value")
                or value.get("text")
                or value.get("title")
            )
        else:
            key = value
            label = value
        if key is None:
            continue
        label_text = label if isinstance(label, str) else str(label)
        items.append((key, label_text))
    return items


def print_section(
    title: str,
    items: List[Mapping[str, Any]],
    id_field: str,
    *,
    extra: Optional[Iterable[Tuple[str, str]]] = None,
    show_all_attr_values: bool = False,
) -> None:
    """Pomocnicza funkcja do ładnego drukowania danych."""
    print("-" * 60)
    print(f" {title.upper()} ")
    print("-" * 60)
    if not items:
        print("Nie znaleziono danych dla tej sekcji.")
        return

    for item in items:
        if not isinstance(item, Mapping):
            continue
        item_id = item.get(id_field)
        if item_id in (None, ""):
            # Best-effort fallback
            item_id = _coerce_id(item, (id_field,)) or "?"

        name = _coerce_name(item)

        line = f"  ID: {str(item_id):<10} | Nazwa: {name}"
        # Optional extras
        if extra:
            extras: List[str] = []
            for label, key in extra:
                value = item
                for part in key.split('.'):
                    if isinstance(value, Mapping):
                        value = value.get(part)
                    else:
                        value = None
                        break
                if value not in (None, ""):
                    extras.append(f"{label}: {value}")
            if extras:
                line += " | " + ", ".join(extras)
        print(line)
        # If this is attributes section, also display group and dictionary values
        if id_field == "attribute_id":
            group_id = item.get("attribute_group_id") or (item.get("group") or {}).get("id")
            group_name = item.get("group_name") or (item.get("group") or {}).get("name")
            if group_id or group_name:
                print(f"     Grupa: {group_name or ''} (ID: {group_id or ''})")
            values = _extract_attribute_values(item)
            if values:
                if show_all_attr_values:
                    text = ", ".join(f"{v_id}:{v_label}" for v_id, v_label in values)
                    print(f"     Wartości: {text}")
                else:
                    preview = ", ".join(f"{v_id}:{v_label}" for v_id, v_label in values[:10])
                    suffix = " …" if len(values) > 10 else ""
                    print(f"     Wartości: {preview}{suffix}")
    print("\n")


def _fetch_all(client: ShoperClient, endpoint: str, *, limit: int = 250) -> List[Dict[str, Any]]:
    """Pobierz wszystkie elementy z paginacją (page/limit)."""
    page = 1
    all_items: List[Dict[str, Any]] = []
    while True:
        try:
            resp = client.get(endpoint, params={"page": page, "limit": limit})
        except Exception as e:
            print(f"BŁĄD: Nie udało się pobrać '{endpoint}': {e}")
            break
        if not isinstance(resp, Mapping):
            break
        items = resp.get("list") or resp.get("items") or []
        if not isinstance(items, list) or not items:
            break
        all_items.extend([i for i in items if isinstance(i, dict)])
        current = int(resp.get("page", page))
        pages = int(resp.get("pages", page))
        if current >= pages:
            break
        page += 1
    return all_items


def _normalise_languages(raw: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for e in raw:
        lang = e.get("language") if isinstance(e.get("language"), dict) else None
        code = (
            e.get("locale")
            or e.get("language_code")
            or e.get("code")
            or (lang.get("locale") if lang else None)
            or (lang.get("language_code") if lang else None)
            or (lang.get("code") if lang else None)
        )
        lid = (
            e.get("lang_id")
            or e.get("language_id")
            or e.get("id")
            or (lang.get("lang_id") if lang else None)
            or (lang.get("language_id") if lang else None)
            or (lang.get("id") if lang else None)
        )
        currency_id = e.get("currency_id") or (lang.get("currency_id") if lang else None)
        active = e.get("active") if e.get("active") is not None else (lang.get("active") if lang else None)
        order = e.get("order") if e.get("order") is not None else (lang.get("order") if lang else None)
        symbol = e.get("symbol") or (lang.get("symbol") if lang else None)
        # heuristics for default
        is_default = bool(
            e.get("default")
            or e.get("is_default")
            or e.get("main")
            or (lang.get("default") if lang else None)
            or (lang.get("is_default") if lang else None)
            or (lang.get("main") if lang else None)
        )
        if code and lid is not None:
            try:
                lid_int = int(lid)
            except Exception:
                continue
            out.append({
                "lang_id": lid_int,
                "language_id": lid_int,
                "locale": code,
                "language_code": code,
                "currency_id": currency_id,
                "active": bool(active) if active is not None else None,
                "order": order,
                "symbol": symbol,
                "is_default": is_default,
            })
    return out


def check_shoper_data(show_all_attr_values: bool = False, show_full_languages: bool = False) -> None:
    """Pobierz i wyświetl komplet ID i podstawowe dane konfiguracyjne produktów."""
    try:
        client = ShoperClient()
        print("Pomyślnie połączono z API Shoper.\n")
    except Exception as e:
        print(f"BŁĄD: Nie można połączyć się z API Shoper. Sprawdź plik .env. Szczegóły: {e}")
        return

    try:
        print("Pobieranie danych... To może chwilę potrwać.\n")
        categories = _fetch_all(client, "categories")
        producers = _fetch_all(client, "producers")
        taxes = _fetch_all(client, "taxes")
        units = _fetch_all(client, "units")
        availabilities = _fetch_all(client, "availabilities")
        attributes = _fetch_all(client, "attributes")
        languages_raw = _fetch_all(client, "languages")
        languages = _normalise_languages(languages_raw) if languages_raw else []
        # 'groups' może być niedostępne w niektórych sklepach — próbujemy opcjonalnie
        try:
            groups = _fetch_all(client, "groups")
        except Exception:
            groups = []

        # Wyświetlanie — ID + nazwy
        print_section("kategorie", categories, "category_id")
        print_section("producenci", producers, "producer_id")
        print_section("stawki podatkowe", taxes, "tax_id")
        print_section("jednostki miary", units, "unit_id")
        print_section("dostępności", availabilities, "availability_id")
        print_section("atrybuty", attributes, "attribute_id", show_all_attr_values=show_all_attr_values)
        print("-" * 60)
        print(" JĘZYKI ")
        print("-" * 60)
        if languages:
            for lang in languages:
                base = (
                    f"  ID: {lang.get('lang_id', ''):<4} | lang_id: {lang.get('lang_id', ''):<4}"
                    f" | language_id: {lang.get('language_id', ''):<4} | locale: {lang.get('locale', '')}"
                    f" | language_code: {lang.get('language_code', '')}"
                )
                if show_full_languages:
                    extra = (
                        f" | default: {lang.get('is_default', False)} | active: {lang.get('active', '')}"
                        f" | currency_id: {lang.get('currency_id', '')} | order: {lang.get('order', '')}"
                    )
                else:
                    extra = ""
                print(base + extra)
            print("\n  Przykładowy wpis translations, jaki aplikacja może wysłać:")
            # Pokaż preview na podstawie pierwszego języka
            first = languages[0]
            print(
                "  translations: [ { "
                f"'language_id': {first.get('language_id')}, 'lang_id': {first.get('lang_id')}, "
                f"'language_code': '{first.get('language_code')}', 'locale': '{first.get('locale')}', 'name': '…' "
                "} ]\n"
            )
        else:
            print("Nie znaleziono danych dla tej sekcji.\n")
        if groups:
            print_section("grupy produktów", groups, "group_id")

        # Zapis pełnego zrzutu JSON do pliku dla analizy
        dump = {
            "categories": categories,
            "producers": producers,
            "taxes": taxes,
            "units": units,
            "availabilities": availabilities,
            "attributes": attributes,
            "languages": languages,
            "groups": groups,
        }
        with open("ids_dump.json", "w", encoding="utf-8") as fh:
            json.dump(dump, fh, ensure_ascii=False, indent=2)
        print("Pełne dane zapisano do pliku: ids_dump.json")

    except Exception as e:
        print(f"BŁĄD: Wystąpił problem podczas pobierania danych z API: {e}")
        print("Sprawdź, czy Twój klucz API ma uprawnienia do odczytu (GET) dla tych zasobów.")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Wyświetl i zapisz ID zasobów Shoper.")
    parser.add_argument(
        "--full-attributes",
        action="store_true",
        help="Wyświetl wszystkie wartości słownikowe atrybutów (nie tylko podgląd).",
    )
    parser.add_argument(
        "--full-languages",
        action="store_true",
        help="Wyświetl pełne informacje o językach (locale, currency_id, active, order).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    check_shoper_data(
        show_all_attr_values=args.full_attributes,
        show_full_languages=args.full_languages,
    )
