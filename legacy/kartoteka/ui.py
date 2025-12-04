import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
import customtkinter as ctk
import tkinter.ttk as ttk
from PIL import Image, ImageTk, ImageFilter, ImageOps, ImageDraw, UnidentifiedImageError
import imagehash
import os
import csv
import json
import requests
import urllib3
import base64
import mimetypes
import re
import datetime
import time
import math
import asyncio
import platform
import shutil
import subprocess
import tempfile
from collections import Counter, defaultdict
from dotenv import load_dotenv, set_key
import unicodedata
from itertools import combinations
import html
import difflib
import sys
from collections.abc import Iterable, Mapping
from typing import Any, Optional, Awaitable, NamedTuple
from types import SimpleNamespace
from pydantic import BaseModel
import pytesseract
from pathlib import Path

if not hasattr(ctk, "CTkScrollableFrame"):
    class _FallbackScrollableFrame:  # pragma: no cover - simple stub for tests
        def __init__(self, *args, **kwargs):
            pass

    ctk.CTkScrollableFrame = _FallbackScrollableFrame  # type: ignore[attr-defined]

try:  # pragma: no cover - optional dependency
    import openai  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    openai = SimpleNamespace(
        OpenAI=lambda *a, **k: SimpleNamespace(),
        chat=SimpleNamespace(completions=SimpleNamespace(create=lambda *a, **k: None)),
        OpenAIError=Exception,
    )
else:  # pragma: no cover - optional dependency
    # accessing ``openai.chat`` on some versions can trigger network-heavy
    # initialization; provide a simple stub so tests can monkeypatch it
    if not hasattr(openai, "chat") or isinstance(openai.chat, property):
        openai.chat = SimpleNamespace(
            completions=SimpleNamespace(create=lambda *a, **k: None)
        )

from shoper_client import ShoperClient
from webdav_client import WebDAVClient
from . import csv_utils, storage, stats_utils
from .inventory_service import WarehouseInventoryService
import threading
from urllib.parse import urlencode, urlparse
import io
import array
import webbrowser
import logging
from gettext import gettext as _
from http.client import RemoteDisconnected


def _is_mock_object(obj: object) -> bool:
    """Return ``True`` if ``obj`` appears to originate from ``unittest.mock``."""

    module = getattr(type(obj), "__module__", "") or ""
    name = getattr(type(obj), "__name__", "") or ""
    return module.startswith(("unittest.mock", "mock")) or "mock" in name.lower()


def _create_bool_var(value: bool = False):
    try:
        return tk.BooleanVar(value=value)
    except (tk.TclError, RuntimeError):
        class _Var:
            def __init__(self, default: bool):
                self._value = bool(default)

            def get(self) -> bool:
                return self._value

            def set(self, new_value: bool) -> None:
                self._value = bool(new_value)

        return _Var(value)


def _create_string_var(value: str = ""):
    try:
        return tk.StringVar(value=value)
    except (tk.TclError, RuntimeError):
        class _Var:
            def __init__(self, default: str):
                self._value = str(default)

            def get(self) -> str:
                return self._value

            def set(self, new_value: Any) -> None:
                self._value = str(new_value)

        return _Var(value)


def _configure_widget(widget: Any, **kwargs: Any) -> None:
    configure = getattr(widget, "configure", None)
    if callable(configure):
        try:
            configure(**kwargs)
            return
        except Exception:
            pass
    for key, value in kwargs.items():
        try:
            setattr(widget, key, value)
        except Exception:
            pass


LANGUAGE_ATTRIBUTE_GROUP_ID = 14
LANGUAGE_DEFAULT_CODE = "ENG"
DEFAULT_TRANSLATION_LOCALE = "pl_PL"

# Commonly observed Shoper language identifiers. The API is queried when
# possible, but the fallback ensures unit tests – and offline usage – still
# produce valid payloads for the default locales we handle.
HARDCODED_SHOPER_LANGUAGE_IDS: Mapping[str, int] = {
    "pl_PL": 1,
    "pl": 1,
    "en_GB": 2,
    "en_US": 2,
    "en": 2,
}


def _normalize_locale_code(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("-", "_")
    if "_" in text:
        lang_part, country_part = text.split("_", 1)
        return f"{lang_part.lower()}_{country_part.upper()}"
    return text.lower()


def _normalize_language_label(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    upper = text.upper()
    direct = {
        "ENG": "ENG",
        "EN": "ENG",
        "ENGLISH": "ENG",
        "JP": "JP",
        "JPN": "JP",
        "JAP": "JP",
        "JAPANESE": "JP",
    }
    if upper in direct:
        return direct[upper]
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    lowered = ascii_text.lower()
    ascii_map = {
        "angielski": "ENG",
        "angielski (eng)": "ENG",
        "angielski (en)": "ENG",
        "ang": "ENG",
        "ang.": "ENG",
        "japonski": "JP",
        "japonski (jp)": "JP",
        "japonski (jpn)": "JP",
        "japonski (jap)": "JP",
    }
    if lowered in ascii_map:
        return ascii_map[lowered]
    if any(token in lowered for token in ("angiel", "english")):
        return "ENG"
    compact = lowered.replace(" ", "")
    if any(token in compact for token in ("jp", "jap", "jpn")):
        return "JP"
    if "japon" in lowered or "japan" in lowered:
        return "JP"


def _normalize_availability_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        text = value
    else:
        text = str(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.strip().lower()


def _looks_like_available_label(value: Any) -> bool:
    normalized = _normalize_availability_text(value)
    if not normalized:
        return False
    compact = normalized.replace(" ", "")
    negative_tokens = (
        "niedostep",
        "unavail",
        "brak",
        "outofstock",
        "preorder",
        "przedsprzedaz",
        "oczekiw",
        "soon",
        "wyprzedane",
        "sprzedane",
        "czasowo",
    )
    if any(token in compact for token in negative_tokens):
        return False
    positive_tokens = (
        "dostep",
        "avail",
        "instock",
        "magazyn",
        "stanie",
        "skladzie",
        "stock",
        "ilosc",
        "sredn",
    )
    return any(token in compact for token in positive_tokens)
    return None


def _score_availability_label(value: Any) -> float:
    """Return a priority score for Shoper availability labels."""

    normalized = _normalize_availability_text(value)
    if not normalized:
        return float("-inf")

    if not _looks_like_available_label(value):
        return float("-inf")

    score = 1.0
    compact = normalized.replace(" ", "")
    lowered_original = str(value).strip().lower() if value is not None else ""

    if "ilosc" in normalized or "ilosc" in compact or "ilość" in lowered_original:
        score += 1.0
    if "sredn" in normalized or "sredn" in compact or "średn" in lowered_original:
        score += 2.0
    if normalized == "srednia ilosc" or lowered_original == "średnia ilość":
        score += 3.0

    return score


def _iter_attribute_value_candidates(value: Any) -> Iterable[Any]:
    if isinstance(value, Mapping):
        for item in value.values():
            yield item
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            yield item
    else:
        yield value


def _get_attribute_control(app: Any, group_id: int, attribute_id: int) -> Optional[Mapping[str, Any]]:
    controls = getattr(app, "_attribute_controls", {})
    if isinstance(controls, Mapping):
        return controls.get((group_id, attribute_id))
    return None


def _decode_language_value(app: Any, attribute_id: Any, raw_value: Any) -> Optional[str]:
    try:
        attr_id = int(attribute_id)
    except (TypeError, ValueError):
        attr_id = attribute_id
    control = _get_attribute_control(app, LANGUAGE_ATTRIBUTE_GROUP_ID, attr_id)
    meta = control.get("meta") if isinstance(control, Mapping) else {}
    values_by_id = {}
    if isinstance(meta, Mapping):
        values_by_id = meta.get("values_by_id", {}) or {}
    value_to_label = control.get("value_to_label", {}) if isinstance(control, Mapping) else {}

    for candidate in _iter_attribute_value_candidates(raw_value):
        label = None
        if candidate in value_to_label:
            label = value_to_label.get(candidate)
        elif isinstance(candidate, str):
            stripped = candidate.strip()
            if stripped in value_to_label:
                label = value_to_label.get(stripped)
            elif stripped.isdigit():
                try:
                    numeric = int(stripped)
                except ValueError:
                    numeric = None
                if numeric is not None:
                    label = value_to_label.get(numeric) or values_by_id.get(numeric)
            if label is None and stripped in values_by_id:
                label = values_by_id.get(stripped)
        elif candidate in values_by_id:
            label = values_by_id.get(candidate)
        code = _normalize_language_label(label if label is not None else candidate)
        if code:
            return code
    return None


def _extract_language_code_from_attributes(app: Any) -> Optional[str]:
    values = getattr(app, "attribute_values", None)
    if not isinstance(values, Mapping):
        return None
    group_values = values.get(LANGUAGE_ATTRIBUTE_GROUP_ID)
    if not isinstance(group_values, Mapping):
        return None
    for attr_id, raw_value in group_values.items():
        code = _decode_language_value(app, attr_id, raw_value)
        if code:
            return code
    return None


def _get_current_language_code(app: Any) -> str:
    code = _extract_language_code_from_attributes(app)
    if code:
        return code
    lang_var = getattr(app, "lang_var", None)
    if lang_var is not None and hasattr(lang_var, "get"):
        try:
            fallback = lang_var.get()
        except Exception:
            fallback = None
        else:
            normalized = _normalize_language_label(fallback)
            if normalized:
                return normalized
    return LANGUAGE_DEFAULT_CODE


def _find_language_attribute_ids(app: Any) -> list[int]:
    controls = getattr(app, "_attribute_controls", {})
    if not isinstance(controls, Mapping):
        return []
    result: list[int] = []
    for (group_id, attr_id) in controls.keys():
        if group_id == LANGUAGE_ATTRIBUTE_GROUP_ID:
            try:
                result.append(int(attr_id))
            except (TypeError, ValueError):
                continue
    return result


def _find_language_dictionary_value(control: Optional[Mapping[str, Any]], code: str) -> Any:
    if not isinstance(control, Mapping):
        return None
    meta = control.get("meta")
    values = None
    if isinstance(meta, Mapping):
        values = meta.get("values")
    if not isinstance(values, Iterable):
        return None
    for item in values:
        if (
            isinstance(item, tuple)
            and len(item) == 2
            and _normalize_language_label(item[1]) == code
        ):
            return item[0]
    return None


def _apply_language_code_to_attribute(app: Any, code: str) -> None:
    attr_ids = _find_language_attribute_ids(app)
    if not attr_ids:
        return
    target_code = code or LANGUAGE_DEFAULT_CODE
    for attr_id in attr_ids:
        control = _get_attribute_control(app, LANGUAGE_ATTRIBUTE_GROUP_ID, attr_id)
        target_value = _find_language_dictionary_value(control, target_code)
        if target_value is None:
            target_value = target_code
        store = getattr(app, "_store_attribute_value", None)
        if callable(store):
            store(LANGUAGE_ATTRIBUTE_GROUP_ID, attr_id, target_value)
        else:
            values = getattr(app, "attribute_values", None)
            if not isinstance(values, dict):
                values = {}
                setattr(app, "attribute_values", values)
            group_map = values.setdefault(LANGUAGE_ATTRIBUTE_GROUP_ID, {})
            group_map[attr_id] = target_value
            try:
                app.update_set_options()
            except Exception:
                pass
        if isinstance(control, Mapping):
            widget_type = control.get("widget_type")
            var = control.get("variable")
            if widget_type == "select":
                value_to_label = control.get("value_to_label", {})
                label = value_to_label.get(target_value)
                if label is None and isinstance(target_value, str):
                    label = target_value
                if label is not None and var is not None:
                    try:
                        var.set(label)
                    except Exception:
                        pass
            elif widget_type == "text" and var is not None:
                try:
                    var.set(target_code)
                except Exception:
                    pass
        break


def _set_language_attribute_default(app: Any, code: str = LANGUAGE_DEFAULT_CODE) -> None:
    current = _extract_language_code_from_attributes(app)
    if current:
        return
    _apply_language_code_to_attribute(app, code)


class _AttributeEntryAdapter:
    """Expose attribute selections through ``self.entries``.

    ``save_current_data`` gathers values from every entry that provides a
    ``get`` method.  Attribute widgets store their selection inside
    ``self.attribute_values`` instead of a regular Tk variable, therefore
    ``self.entries`` keeps small adapter objects that forward ``get`` calls to
    the aggregated dictionary.
    """

    def __init__(self, app: "CardEditorApp", group_id: int, attribute_id: int):
        self.app = app
        self.group_id = int(group_id)
        self.attribute_id = int(attribute_id)

    def get(self):  # pragma: no cover - exercised indirectly via app logic
        group = getattr(self.app, "attribute_values", {})
        if not isinstance(group, Mapping):
            return None
        values = group.get(self.group_id, {})
        if not isinstance(values, Mapping):
            return None
        return values.get(self.attribute_id)

def _coerce_quantity(value: Any) -> int:
    if value is None:
        return 0
    try:
        if isinstance(value, str):
            cleaned = value.replace(" ", "").replace(",", ".")
            return max(0, int(float(cleaned)))
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _extract_numeric(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        match = re.findall(r"-?\d+[\.,]?\d*", text.replace(" ", ""))
        if not match:
            return None
        try:
            return float(match[-1].replace(",", "."))
        except ValueError:
            return None
    if isinstance(value, Mapping):
        for key in (
            "gross",
            "total_gross",
            "brutto",
            "value",
            "amount",
            "total",
            "with_tax",
            "to_pay",
        ):
            if key in value:
                result = _extract_numeric(value[key])
                if result is not None:
                    return result
        for subvalue in value.values():
            result = _extract_numeric(subvalue)
            if result is not None:
                return result
        return None
    if isinstance(value, (list, tuple, set)):
        for item in value:
            result = _extract_numeric(item)
            if result is not None:
                return result
    return None


def _format_order_total(order: Mapping[str, Any] | None) -> str:
    if not isinstance(order, Mapping):
        return ""

    currency = (
        str(
            order.get("currency")
            or order.get("order_currency")
            or order.get("summary", {}).get("currency")
            or "PLN"
        )
        .strip()
        .upper()
    )

    for key in ("sum", "summary", "total", "amount", "order_value", "payment"):
        if key in order:
            result = _extract_numeric(order[key])
            if result is not None:
                return f"{result:.2f} {currency or 'PLN'}"

    result = _extract_numeric(order)
    if result is None:
        return ""
    return f"{result:.2f} {currency or 'PLN'}"
try:  # pragma: no cover - optional dependency
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
except Exception:  # pragma: no cover - optional dependency
    Figure = None  # type: ignore[assignment]
    FigureCanvasTkAgg = None  # type: ignore[assignment]
try:
    from hash_db import HashDB, Candidate
except ImportError as exc:  # pragma: no cover - optional dependency
    logging.getLogger(__name__).info("HashDB import failed: %s", exc)
    HashDB = None  # type: ignore[assignment]
    Candidate = None  # type: ignore[assignment]
from fingerprint import compute_fingerprint
from tooltip import Tooltip
from .image_utils import load_rgba_image
from .storage_config import (
    BOX_CAPACITY as BOX_CAPACITY_MAP,
    BOX_COUNT,
    BOX_COLUMN_CAPACITY,
    BOX_COLUMNS,
    SPECIAL_BOX_CAPACITY,
    SPECIAL_BOX_NUMBER,
    STANDARD_BOX_CAPACITY,
    STANDARD_BOX_COLUMNS,
)

# Ensure tkinter dialog modules provide the expected functions even when tests
# replace them with simple stubs.  Missing attributes are replaced with no-op
# callables so that downstream monkeypatching can occur reliably.
for _name, _mod, _attrs in (
    ("tkinter.filedialog", filedialog, ["askdirectory", "askopenfilename", "asksaveasfilename"]),
    (
        "tkinter.messagebox",
        messagebox,
        ["showinfo", "showerror", "showwarning", "askyesno"],
    ),
    ("tkinter.simpledialog", simpledialog, ["askstring", "askinteger"]),
):
    for _attr in _attrs:
        if not hasattr(_mod, _attr):
            setattr(_mod, _attr, lambda *a, **k: None)
    sys.modules.setdefault(_name, _mod)

ENV_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_dotenv(ENV_FILE)

logger = logging.getLogger(__name__)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_IMAGE_URL = os.getenv("BASE_IMAGE_URL", "https://sklep839679.shoparena.pl/upload/images").rstrip("/")
SCANS_DIR = os.getenv("SCANS_DIR", "scans")

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
RAPIDAPI_HOST = os.getenv("RAPIDAPI_HOST")

SHOPER_API_URL = os.getenv("SHOPER_API_URL", "").strip()
SHOPER_API_TOKEN = os.getenv("SHOPER_API_TOKEN", "").strip()
SHOPER_CLIENT_ID = os.getenv("SHOPER_CLIENT_ID", "").strip()
WEBDAV_URL = os.getenv("WEBDAV_URL")
WEBDAV_USER = os.getenv("WEBDAV_USER")
WEBDAV_PASSWORD = os.getenv("WEBDAV_PASSWORD")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
USE_OPENAI_STUB = not OPENAI_API_KEY or os.getenv("OPENAI_TEST_MODE")
if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY
if USE_OPENAI_STUB:
    openai.OpenAI = lambda *a, **k: SimpleNamespace()

PRICE_DB_PATH = "card_prices.csv"
PRICE_MULTIPLIER = 1.23
HOLO_REVERSE_MULTIPLIER = 3.5
SET_LOGO_DIR = "set_logos"
HASH_DIFF_THRESHOLD = 20  # hash difference threshold for accepting matches
HASH_MATCH_THRESHOLD = 5  # maximum allowed fingerprint distance
HASH_SIZE = (32, 32)
PSA_ICON_URL = "https://www.pngkey.com/png/full/231-2310791_psa-grading-standards-professional-sports-authenticator.png"

CARD_TYPE_LABELS = {"C": "Common", "H": "Holo", "R": "Reverse"}
CARD_TYPE_DEFAULT = "C"

CARD_FINISH_ATTRIBUTE_GROUP_ID = 11


class CardFinishSelection(NamedTuple):
    code: str
    ball: Optional[str]
    label: Optional[str]
    value: Any | None = None


def _normalize_finish_label(text: Any) -> str:
    if text is None:
        return ""
    if isinstance(text, bytes):
        try:
            text = text.decode("utf-8", "ignore")
        except Exception:
            text = text.decode("latin-1", "ignore")
    normalized = unicodedata.normalize("NFKD", str(text))
    ascii_text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    lowered = ascii_text.lower()
    return re.sub(r"[^a-z0-9]+", "", lowered)


def _normalize_ball_suffix(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (list, tuple, set)):
        for item in value:
            normalized = _normalize_ball_suffix(item)
            if normalized:
                return normalized
        return None
    text = str(value).strip()
    if not text:
        return None
    upper = text.upper()
    if upper in {"P", "M"}:
        return upper
    normalized = _normalize_finish_label(text)
    if not normalized:
        return None
    if normalized.startswith("master") or "masterball" in normalized:
        return "M"
    if normalized.startswith("poke") or "pokeball" in normalized or "pokebal" in normalized:
        return "P"
    return None


def _deduce_finish_variant(normalized_label: str) -> tuple[str, Optional[str]]:
    if not normalized_label:
        return CARD_TYPE_DEFAULT, None
    ball = None
    if "masterball" in normalized_label or (
        normalized_label.startswith("master") and "ball" in normalized_label
    ):
        ball = "M"
    elif "pokeball" in normalized_label or (
        normalized_label.startswith("poke") and "ball" in normalized_label
    ):
        ball = "P"
    code = CARD_TYPE_DEFAULT
    if "reverse" in normalized_label or "mirror" in normalized_label:
        code = "R"
    elif any(token in normalized_label for token in ("holo", "foil", "blyszcz", "blysk")):
        code = "H"
    elif any(token in normalized_label for token in ("nonholo", "regular", "common", "zwykla", "normal")):
        code = "C"
    return code, ball


DEFAULT_CARD_FINISH_LABEL = CARD_TYPE_LABELS.get(
    CARD_TYPE_DEFAULT, CARD_TYPE_DEFAULT
)
DEFAULT_CARD_FINISH_SELECTION = CardFinishSelection(
    CARD_TYPE_DEFAULT, None, DEFAULT_CARD_FINISH_LABEL, None
)


def normalize_card_type_code(value: Any, *, default: str = CARD_TYPE_DEFAULT) -> str:
    return csv_utils.normalize_variant_code(value, default=default)


def infer_card_type_code(data: Mapping[str, Any] | None) -> str:
    return csv_utils.infer_variant_code(data)


def card_type_label(code: Any) -> str:
    normalized = normalize_card_type_code(code)
    return CARD_TYPE_LABELS.get(normalized, CARD_TYPE_LABELS[CARD_TYPE_DEFAULT])


def card_type_flags(code: Any) -> dict[str, bool]:
    normalized = normalize_card_type_code(code)
    return {
        "Reverse": normalized == "R",
        "Holo": normalized == "H",
    }


class OrdersListView(ctk.CTkScrollableFrame):
    """Scrollable list view tailored for displaying Shoper orders."""

    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", LIGHT_BG_COLOR)
        super().__init__(master, **kwargs)
        self._order_cards: list[tk.Widget] = []
        self._empty_label: ctk.CTkLabel | None = None
        self._title_font = ctk.CTkFont(size=16, weight="bold")
        self._meta_font = ctk.CTkFont(size=13)
        self._item_font = ctk.CTkFont(size=14)
        self._order_payloads: list[dict[str, Any]] = []
        self._on_select = None

    def _clear_placeholder(self) -> None:
        if self._empty_label is not None:
            self._empty_label.destroy()
            self._empty_label = None

    def set_order_handler(self, callback) -> None:
        """Register ``callback`` invoked when an order card is clicked."""

        self._on_select = callback

    def _handle_select(self, order: dict) -> None:
        if self._on_select is None:
            return
        try:
            self._on_select(order)
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Failed to handle order selection")

    def clear_orders(self) -> None:
        """Remove all rendered order cards from the view."""

        self._clear_placeholder()
        for card in self._order_cards:
            try:
                card.destroy()
            except Exception:
                logger.exception("Failed to destroy order card widget")
        self._order_cards.clear()
        self._order_payloads.clear()

    def render_orders(self, orders: list[dict[str, Any]]) -> None:
        """Render ``orders`` inside the scrollable frame."""

        self.clear_orders()
        if not orders:
            self._empty_label = ctk.CTkLabel(
                self,
                text="Brak zamówień do wyświetlenia",
                text_color=TEXT_COLOR,
                font=self._item_font,
            )
            self._empty_label.pack(pady=20)
            return

        for entry in orders:
            card = ctk.CTkFrame(self, fg_color=BG_COLOR, corner_radius=12)
            card.pack(fill="x", expand=True, padx=12, pady=8)
            self._order_cards.append(card)
            self._order_payloads.append(entry)
            payload = entry

            title = entry.get("title") or "Zamówienie"
            ctk.CTkLabel(
                card,
                text=title,
                text_color=TEXT_COLOR,
                font=self._title_font,
                anchor="w",
                justify="left",
            ).pack(anchor="w", padx=16, pady=(12, 4))

            meta_parts: list[str] = []
            status = entry.get("status")
            if isinstance(status, dict): # Pobieramy nazwę z obiektu status
                status_name = status.get('name')
                if status_name:
                    meta_parts.append(f"Status: {status_name}")
            elif status:
                meta_parts.append(f"Status: {status}")

            customer = entry.get("customer")
            if customer:
                meta_parts.append(f"Klient: {customer}")

            created = entry.get("created")
            if created:
                # Formatujemy datę do czytelniejszej postaci
                try:
                    date_obj = datetime.datetime.fromisoformat(created)
                    meta_parts.append(f"Data: {date_obj.strftime('%Y-%m-%d %H:%M')}")
                except (ValueError, TypeError):
                    meta_parts.append(f"Data: {created}")

            total_value = entry.get("total")
            if total_value:
                meta_parts.append(f"Wartość: {total_value}")

            quantity = entry.get("quantity")
            if quantity not in (None, ""):
                meta_parts.append(f"Liczba sztuk: {quantity}")

            if meta_parts:
                ctk.CTkLabel(
                    card,
                    text="  •  ".join(meta_parts),
                    text_color="#DDDDDD",
                    font=self._meta_font,
                    anchor="w",
                    justify="left",
                ).pack(anchor="w", padx=16, pady=(0, 10))

            def _bind_clicks(widget):
                bind = getattr(widget, "bind", None)
                if callable(bind):
                    bind("<Button-1>", lambda _e, data=payload: self._handle_select(data))
                children = getattr(widget, "winfo_children", None)
                if callable(children):
                    for child in children():
                        _bind_clicks(child)

            _bind_clicks(card)

# toggle automatic fingerprint lookup via environment variable
AUTO_HASH_LOOKUP = os.getenv("AUTO_HASH_LOOKUP", "1") not in {"0", "false", "False"}

# optional path to enable persistent fingerprint storage
HASH_DB_FILE = os.getenv("HASH_DB_FILE")

# minimum similarity ratio for fuzzy set code matching
SET_CODE_MATCH_CUTOFF = 0.8
try:
    SET_CODE_MATCH_CUTOFF = float(
        os.getenv("SET_CODE_MATCH_CUTOFF", SET_CODE_MATCH_CUTOFF)
    )
except ValueError:
    pass

_LOGO_HASHES: dict[str, tuple[imagehash.ImageHash, imagehash.ImageHash, imagehash.ImageHash]] = {}

# simple cache for downloaded remote images; values store the raw bytes (or
# ``None`` for failed downloads) along with the timestamp they were fetched.
# Entries older than ``_IMAGE_CACHE_TTL`` seconds are considered stale and will
# be refreshed on the next access.
_IMAGE_CACHE_TTL = 300  # seconds
_IMAGE_CACHE: dict[str, tuple[Optional[bytes], float]] = {}


def _coerce_image_bytes(data: object, *, _seen: Optional[set[int]] = None) -> Optional[bytes]:
    """Return ``data`` converted to raw bytes if possible.

    Several tests and code paths patch ``requests`` responses with lightweight
    stand-ins such as :class:`io.BytesIO`, ``memoryview`` or other buffer-like
    wrappers.  This helper normalises those objects so that ``_load_image`` can
    feed stable byte streams to :func:`load_rgba_image`.
    """

    if data is None:
        return None
    if isinstance(data, (bytes, bytearray)):
        return bytes(data)
    if isinstance(data, memoryview):
        return data.tobytes()
    if isinstance(data, array.array):
        try:
            return data.tobytes()
        except (TypeError, AttributeError):
            return None

    if _seen is None:
        _seen = set()
    obj_id = id(data)
    if obj_id in _seen:
        return None
    _seen.add(obj_id)

    if _is_mock_object(data):
        return None

    # ``io.BytesIO`` exposes ``getvalue``; some wrappers expose ``read`` or
    # ``getbuffer``.  Try the most common conversion hooks before falling back
    # to ``bytes()`` which may raise or yield textual representations.
    for attr in ("getbuffer", "tobytes"):
        func = getattr(data, attr, None)
        if callable(func):
            try:
                candidate = func()
            except TypeError:
                continue
            result = _coerce_image_bytes(candidate, _seen=_seen)
            if result is not None:
                return result

    for attr in ("getvalue", "read"):
        func = getattr(data, attr, None)
        if callable(func):
            try:
                candidate = func()
            except TypeError:
                try:
                    candidate = func(-1)
                except Exception:
                    continue
            result = _coerce_image_bytes(candidate, _seen=_seen)
            if result is not None:
                return result

    if isinstance(data, str):
        try:
            return data.encode("latin-1")
        except Exception:
            return None

    try:
        candidate = bytes(data)
    except Exception:
        return None
    return candidate


def _normalize_requests_exceptions() -> None:
    """Ensure :mod:`requests` exposes real exception classes.

    Some test suites substitute ``requests`` with :class:`unittest.mock.MagicMock`
    prior to reloading this module.  In that scenario the attributes under
    ``requests.exceptions`` become mocks as well which breaks retry logic that
    relies on ``isinstance`` checks.  Replace any missing or mocked exception
    types with lightweight stand-ins derived from :class:`Exception`.
    """

    exc_mod = getattr(requests, "exceptions", None)
    if exc_mod is None or _is_mock_object(exc_mod):
        exc_mod = SimpleNamespace()
        requests.exceptions = exc_mod  # type: ignore[assignment]

    fallback_bases: dict[str, type[BaseException]] = {
        "RequestException": Exception,
        "HTTPError": Exception,
        "SSLError": Exception,
        "ConnectionError": Exception,
    }

    for name, base in fallback_bases.items():
        candidate = getattr(exc_mod, name, None)
        if isinstance(candidate, type) and issubclass(candidate, BaseException):
            continue
        fallback = type(f"Requests{name}", (base,), {})
        setattr(exc_mod, name, fallback)

    # Ensure top-level aliases (``requests.RequestException`` etc.) exist.
    for attr, exc_name in (
        ("RequestException", "RequestException"),
        ("HTTPError", "HTTPError"),
        ("ConnectionError", "ConnectionError"),
    ):
        candidate = getattr(requests, attr, None)
        resolved = getattr(exc_mod, exc_name)
        if isinstance(candidate, type) and issubclass(candidate, BaseException):
            continue
        setattr(requests, attr, resolved)


_normalize_requests_exceptions()

# cache for resized thumbnails keyed by source path/URL
_THUMB_CACHE: dict[str, Image.Image] = {}

_REMOTE_IMAGE_HEADERS = {"User-Agent": "Mozilla/5.0"}


def _download_remote_image(url: str, *, verify: bool) -> bytes:
    """Return raw image bytes fetched from ``url``."""

    response = requests.get(
        url,
        timeout=5,
        headers=_REMOTE_IMAGE_HEADERS,
        verify=verify,
    )
    response.raise_for_status()
    return response.content

def _resolve_image_url(value: str) -> str:
    """Return absolute HTTP URL for image paths from API/WebDAV.

    - If ``value`` already starts with http/https, return as-is.
    - If it looks like a site-root or relative path (e.g. ``/upload/images/5/abc.jpg``
      or ``upload/images/5/abc.jpg``), prefix with ``BASE_IMAGE_URL``.
    - Otherwise return the original value.
    """
    if not value:
        return value
    try:
        p = urlparse(value)
        if p.scheme in ("http", "https"):
            return value
    except Exception:
        pass
    # Strip leading slashes to avoid '//' after join
    path = value.lstrip("/")
    base = BASE_IMAGE_URL
    if base:
        return f"{base}/{path}"
    return value


def draw_box_usage(canvas: "tk.Canvas", box_num: int, occupancy: dict[int, int]) -> float:
    """Draw per-column occupancy of a storage box on ``canvas``.

    Parameters
    ----------
    canvas:
        Target canvas to draw rectangles on.
    box_num:
        Identifier of the storage box.
    occupancy:
        Mapping of ``column -> used slots`` for ``box_num``.

    Returns
    -------
    float
        Overall percentage of used slots in the box.
    """

    box_w = BOX_THUMB_SIZE
    box_h = BOX_THUMB_SIZE
    columns = BOX_COLUMNS.get(box_num, STANDARD_BOX_COLUMNS)
    total_capacity = BOX_CAPACITY_MAP.get(
        box_num, columns * BOX_COLUMN_CAPACITY
    )
    col_capacity = total_capacity / columns if columns else BOX_COLUMN_CAPACITY

    # track rectangles for each column so we can update their coordinates/colors
    overlay_ids: dict[int, int] = getattr(canvas, "overlay_ids", {})
    if not isinstance(overlay_ids, dict):
        overlay_ids = {}
    canvas.overlay_ids = overlay_ids

    if box_num == SPECIAL_BOX_NUMBER:
        inner_w = BOX_THUMB_SIZE - 2 * BOX100_X_INSET
        inner_h = BOX_THUMB_SIZE - 2 * BOX100_Y_INSET
        col_w = inner_w / columns if columns else inner_w
    else:
        col_w = box_w / columns if columns else box_w
    total_used = 0
    for col in range(1, columns + 1):
        used = occupancy.get(col, 0)
        total_used += used
        value = used / col_capacity if col_capacity else 0
        if box_num == SPECIAL_BOX_NUMBER:
            fill_h = inner_h * value
            x0 = BOX100_X_INSET + (col - 1) * col_w
            x1 = x0 + col_w
            y1 = BOX_THUMB_SIZE - BOX100_Y_INSET - fill_h
            box_bottom = BOX_THUMB_SIZE - BOX100_Y_INSET
        else:
            fill_h = box_h * value
            y1 = box_h - fill_h
            x0 = (col - 1) * col_w
            x1 = col * col_w
            box_bottom = box_h
        color = _occupancy_color(value)

        rect_id = overlay_ids.get(col)
        if rect_id is None:
            rect_id = canvas.create_rectangle(x0, y1, x1, box_bottom, fill=color, outline="")
            overlay_ids[col] = rect_id
        else:
            canvas.coords(rect_id, x0, y1, x1, box_bottom)
            canvas.itemconfigure(rect_id, fill=color)

    occupied_percent = total_used / total_capacity * 100 if total_capacity else 0
    return occupied_percent


def _load_image(path: str) -> Optional[Image.Image]:
    """Load image from local path or URL with caching.

    Parameters
    ----------
    path:
        Local filesystem path or HTTP(S) URL.

    Returns
    -------
    Optional[Image.Image]
        Loaded PIL Image or ``None`` on failure.
    """

    if not path:
        return None

    if os.path.exists(path):
        img = load_rgba_image(path)
        if img is None:
            logger.warning("Failed to open image %s", path)
        return img

    parsed = urlparse(path)
    if parsed.scheme in ("http", "https"):
        cached = _IMAGE_CACHE.get(path)
        if cached is not None:
            data, ts = cached
            if time.time() - ts < _IMAGE_CACHE_TTL:
                if data is None:
                    return None
                img = load_rgba_image(io.BytesIO(data))
                if img is not None:
                    return img
                return None
            else:
                # expire stale entry
                _IMAGE_CACHE.pop(path, None)
        def _valid_exceptions(*candidates: object) -> tuple[type[BaseException], ...]:
            valid: list[type[BaseException]] = []
            for exc in candidates:
                if isinstance(exc, type) and issubclass(exc, BaseException):
                    valid.append(exc)
            return tuple(valid)

        download_errors = _valid_exceptions(
            getattr(requests.exceptions, "RequestException", Exception),
            getattr(urllib3.exceptions, "HTTPError", Exception),
            RemoteDisconnected,
        )
        retryable_errors = _valid_exceptions(
            getattr(requests.exceptions, "SSLError", Exception),
            getattr(requests.exceptions, "ConnectionError", Exception),
            getattr(urllib3.exceptions, "ProtocolError", Exception),
            getattr(urllib3.exceptions, "MaxRetryError", Exception),
            getattr(urllib3.exceptions, "NewConnectionError", Exception),
            RemoteDisconnected,
        )

        def _cache_failure() -> None:
            _IMAGE_CACHE[path] = (None, time.time() - _IMAGE_CACHE_TTL - 1)

        try:
            data = _download_remote_image(path, verify=True)
        except retryable_errors:
            try:
                data = _download_remote_image(path, verify=False)
            except download_errors as exc:
                logger.warning("Failed to download image %s: %s", path, exc)
                _cache_failure()
                return None
        except download_errors as exc:
            logger.warning("Failed to download image %s: %s", path, exc)
            _cache_failure()
            return None

        data_bytes = _coerce_image_bytes(data)
        if data_bytes is None:
            logger.warning("Unexpected image payload type %s for %s", type(data), path)
            _cache_failure()
            return None

        img = load_rgba_image(io.BytesIO(data_bytes))
        if img is not None:
            _IMAGE_CACHE[path] = (data_bytes, time.time())
            return img
        _cache_failure()
        return None

    return None


def _get_thumbnail(path: str, size: tuple[int, int]) -> Optional[Image.Image]:
    """Return a cached resized PIL image for ``path``.

    The image is loaded via :func:`_load_image` and resized using
    :py:meth:`PIL.Image.Image.thumbnail`. Subsequent calls with the same
    ``path`` reuse the stored thumbnail to avoid redundant disk or network
    operations.
    """

    if not path:
        return None
    cached = _THUMB_CACHE.get(path)
    if cached is not None:
        return cached
    img = _load_image(path)
    if img is None:
        return None
    img.thumbnail(size)
    _THUMB_CACHE[path] = img
    return img


def _create_image(img: Image.Image):
    """Return a CTkImage if available, otherwise a PhotoImage."""
    if hasattr(ctk, "CTkImage"):
        return ctk.CTkImage(light_image=img, size=img.size)
    return ImageTk.PhotoImage(img)


def _resize_to_width(img: Image.Image, width: int) -> Image.Image:
    """Return a copy of ``img`` scaled to the given ``width`` preserving aspect.

    The height is calculated from the original image ratio. If the source
    image is already smaller than ``width`` no upscaling is performed.
    """

    if width <= 0 or img.width == 0:
        return img
    if img.width == width:
        return img
    ratio = width / img.width
    height = max(1, int(img.height * ratio))
    return img.resize((width, height), Image.Resampling.LANCZOS)


def _preprocess_symbol(im: Image.Image) -> Image.Image:
    """Normalize symbol/logo image before hashing."""
    im = ImageOps.fit(im.convert("L"), HASH_SIZE, method=Image.Resampling.LANCZOS)
    im = im.filter(ImageFilter.MedianFilter(3))
    im = ImageOps.autocontrast(im)
    return im.convert("1")


def load_logo_hashes() -> bool:
    """Populate the global `_LOGO_HASHES` cache with preprocessed hashes.

    Returns
    -------
    bool
        ``True`` if at least one logo hash was loaded, ``False`` otherwise.
    """

    _LOGO_HASHES.clear()
    if not os.path.isdir(SET_LOGO_DIR):
        logger.warning(
            "Logo directory '%s' does not exist", SET_LOGO_DIR
        )
        return False
    for file in os.listdir(SET_LOGO_DIR):
        if not file.lower().endswith(".png"):
            continue
        code = os.path.splitext(file)[0]
        if ALLOWED_SET_CODES and code not in ALLOWED_SET_CODES:
            continue
        path = os.path.join(SET_LOGO_DIR, file)
        if not os.path.isfile(path):
            continue
        try:
            with Image.open(path) as im:
                im = im.convert("RGBA")
                im = _preprocess_symbol(im)
                _LOGO_HASHES[code] = (
                    imagehash.phash(im),
                    imagehash.dhash(im),
                    imagehash.average_hash(im),
                )
        except (OSError, UnidentifiedImageError) as exc:
            logger.warning("Failed to process logo %s: %s", path, exc)
            continue
    if not _LOGO_HASHES:
        logger.warning(
            "No logos loaded from '%s'; check SET_LOGO_DIR", SET_LOGO_DIR
        )
        return False
    return True

DEFAULT_LOGO_LIMIT = 20
try:
    DEFAULT_LOGO_LIMIT = int(os.getenv("SET_LOGO_LIMIT", DEFAULT_LOGO_LIMIT))
except ValueError:
    pass

# custom theme colors in grayscale
BG_COLOR = "#3A3A3A"
# lighter variant for subtle section backgrounds
LIGHT_BG_COLOR = "#4A4A4A"
FIELD_BG_COLOR = "#5A5A5A"  # even lighter for input fields
ACCENT_COLOR = "#666666"
HOVER_COLOR = "#525252"
TEXT_COLOR = "#FFFFFF"
BORDER_COLOR = "#444444"

# vivid colors for start menu buttons
SCAN_BUTTON_COLOR = "#2ECC71"  # green
PRICE_BUTTON_COLOR = "#3498DB"  # blue
SHOPER_BUTTON_COLOR = "#E67E22"  # orange
MAGAZYN_BUTTON_COLOR = "#9B59B6"  # purple
AUCTION_BUTTON_COLOR = "#E74C3C"  # red
STATS_BUTTON_COLOR = "#1ABC9C"  # teal

# shared colors for common actions
SAVE_BUTTON_COLOR = SCAN_BUTTON_COLOR
FETCH_BUTTON_COLOR = PRICE_BUTTON_COLOR
NAV_BUTTON_COLOR = ACCENT_COLOR

# color highlighting current price labels
CURRENT_PRICE_COLOR = "#FFD700"

# status colors for warehouse items; can be overridden via environment variables
OCCUPIED_COLOR = os.getenv("OCCUPIED_COLOR", "#4caf50")
FREE_COLOR = os.getenv("FREE_COLOR", "#ff9800")
SOLD_COLOR = os.getenv("SOLD_COLOR", "#888888")

# Layout constants to simplify future adjustments
BOX_THUMB_SIZE = 128  # square thumbnail size for warehouse boxes in pixels
BOX100_X_INSET = int(BOX_THUMB_SIZE * 175 / 600)
BOX100_Y_INSET = int(BOX_THUMB_SIZE * 50 / 600)
CARD_THUMB_SIZE = 160  # larger card thumbnails in the warehouse list
# Maximum allowed size for card thumbnails; used to cap dynamic calculations
MAX_CARD_THUMB_SIZE = 160
MAG_CARD_GAP = 3  # spacing between card frames in magazine view
GRID_COLUMNS = STANDARD_BOX_COLUMNS  # number of columns per storage box
WAREHOUSE_GRID_COLUMNS = 5  # number of columns in the warehouse grid
# BOX_COLUMN_CAPACITY, BOX_COUNT, SPECIAL_BOX_NUMBER and SPECIAL_BOX_CAPACITY
# are imported from :mod:`kartoteka.storage_config`.
BOX_CAPACITY = STANDARD_BOX_CAPACITY  # slots in a standard box
MAG_PAGE_SIZE = 20  # number of cards displayed per page in magazyn view


def _occupancy_color(value: float) -> str:
    """Return a color representing occupancy level."""
    if value < 0.5:
        return "#4caf50"  # green
    if value < 0.8:
        return "#ffeb3b"  # yellow
    return "#f44336"  # red



def normalize(text: str, keep_spaces: bool = False) -> str:
    """Normalize text for comparisons and API queries."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    for suffix in [
        " shiny",
        " promo",
    ]:
        text = text.replace(suffix, "")
    text = text.replace("-", "")
    if not keep_spaces:
        text = text.replace(" ", "")
    return text.strip()


def norm_header(name: str) -> str:
    """Return a normalized column name."""
    if name is None:
        return ""
    return name.strip().lower()


def sanitize_number(value: str) -> str:
    """Remove leading zeros from a number string.

    Returns
    -------
    str
        ``value`` without leading zeros or ``"0"`` if the result is
        empty.
    """

    return value.lstrip("0") or "0"




# Wczytanie danych setów
def reload_sets():
    """Load set definitions from the JSON files."""
    global tcg_sets_eng_by_era, tcg_sets_eng_map, tcg_sets_eng, tcg_sets_eng_code_map
    global tcg_sets_jp_by_era, tcg_sets_jp_map, tcg_sets_jp, tcg_sets_jp_code_map
    global tcg_sets_eng_abbr_map, tcg_sets_eng_abbr_name_map
    global tcg_sets_jp_abbr_map, tcg_sets_jp_abbr_name_map
    global tcg_sets_name_to_abbr, tcg_sets_jp_name_to_abbr
    global SET_TO_ERA

    tcg_sets_eng_code_map = globals().get("tcg_sets_eng_code_map", {})
    tcg_sets_jp_code_map = globals().get("tcg_sets_jp_code_map", {})
    tcg_sets_eng_abbr_map = globals().get("tcg_sets_eng_abbr_map", {})
    tcg_sets_eng_abbr_name_map = globals().get("tcg_sets_eng_abbr_name_map", {})
    tcg_sets_jp_abbr_map = globals().get("tcg_sets_jp_abbr_map", {})
    tcg_sets_jp_abbr_name_map = globals().get("tcg_sets_jp_abbr_name_map", {})
    tcg_sets_name_to_abbr = globals().get("tcg_sets_name_to_abbr", {})
    tcg_sets_jp_name_to_abbr = globals().get("tcg_sets_jp_name_to_abbr", {})
    SET_TO_ERA = {}

    try:
        with open("tcg_sets.json", encoding="utf-8") as f:
            tcg_sets_eng_by_era = json.load(f)
    except FileNotFoundError:
        tcg_sets_eng_by_era = {}
    tcg_sets_eng_map = {
        item["name"]: item["code"]
        for sets in tcg_sets_eng_by_era.values()
        for item in sets
    }
    tcg_sets_eng_code_map = {
        item["code"]: item["name"]
        for sets in tcg_sets_eng_by_era.values()
        for item in sets
    }
    tcg_sets_eng_abbr_map = {
        item["abbr"]: item["code"]
        for sets in tcg_sets_eng_by_era.values()
        for item in sets
        if "abbr" in item
    }
    tcg_sets_eng_abbr_name_map = {
        item["abbr"]: item["name"]
        for sets in tcg_sets_eng_by_era.values()
        for item in sets
        if "abbr" in item
    }
    tcg_sets_name_to_abbr = {
        item["name"]: item.get("abbr", "")
        for sets in tcg_sets_eng_by_era.values()
        for item in sets
    }
    tcg_sets_eng = [
        item["name"] for sets in tcg_sets_eng_by_era.values() for item in sets
    ]
    for era, sets in tcg_sets_eng_by_era.items():
        for item in sets:
            SET_TO_ERA[item["code"].lower()] = era
            SET_TO_ERA[item["name"].lower()] = era
            if "abbr" in item:
                SET_TO_ERA[item["abbr"].lower()] = era

    try:
        with open("tcg_sets_jp.json", encoding="utf-8") as f:
            tcg_sets_jp_by_era = json.load(f)
    except FileNotFoundError:
        tcg_sets_jp_by_era = {}
    tcg_sets_jp_map = {
        item["name"]: item["code"]
        for sets in tcg_sets_jp_by_era.values()
        for item in sets
    }
    tcg_sets_jp_code_map = {
        item["code"]: item["name"]
        for sets in tcg_sets_jp_by_era.values()
        for item in sets
    }
    tcg_sets_jp_abbr_map = {
        item["abbr"]: item["code"]
        for sets in tcg_sets_jp_by_era.values()
        for item in sets
        if "abbr" in item
    }
    tcg_sets_jp_abbr_name_map = {
        item["abbr"]: item["name"]
        for sets in tcg_sets_jp_by_era.values()
        for item in sets
        if "abbr" in item
    }
    tcg_sets_jp_name_to_abbr = {
        item["name"]: item.get("abbr", "")
        for sets in tcg_sets_jp_by_era.values()
        for item in sets
    }
    tcg_sets_jp = [
        item["name"] for sets in tcg_sets_jp_by_era.values() for item in sets
    ]
    for era, sets in tcg_sets_jp_by_era.items():
        for item in sets:
            SET_TO_ERA[item["code"].lower()] = era
            SET_TO_ERA[item["name"].lower()] = era
            if "abbr" in item:
                SET_TO_ERA[item["abbr"].lower()] = era


reload_sets()

# Allowed eras and set codes used for logo operations
ALLOWED_ERAS = {
    "Scarlet & Violet",
    "Sword & Shield",
    "Sun & Moon",
    "XY",
    "Black & White",
}

ALLOWED_SET_CODES: set[str] = set()


def refresh_logo_cache() -> bool:
    """Regenerate ``ALLOWED_SET_CODES`` and reload logo hashes.

    Returns
    -------
    bool
        ``True`` when logo hashes were loaded successfully.
    """

    global ALLOWED_SET_CODES
    ALLOWED_SET_CODES = {
        item["code"]
        for era, sets in tcg_sets_eng_by_era.items()
        if era in ALLOWED_ERAS
        for item in sets
    }
    success = load_logo_hashes()
    if not success:
        messagebox.showwarning(
            "Logotypy",
            f"Brak logotypów w katalogu '{SET_LOGO_DIR}' lub błędna ścieżka.",
        )
    return success


refresh_logo_cache()


def get_set_code(name: str) -> str:
    """Return the API code for a set name or abbreviation if available."""
    if not name:
        return ""
    search = name.strip()
    # remove trailing language or other short alphabetic suffixes like "EN", "JP"
    search = re.sub(r"[-_\s]+[a-z]{1,3}$", "", search, flags=re.IGNORECASE)
    search = search.strip().lower()
    for mapping in (
        tcg_sets_eng_map,
        tcg_sets_jp_map,
        tcg_sets_eng_abbr_map,
        tcg_sets_jp_abbr_map,
    ):
        for key, code in mapping.items():
            if key.lower() == search:
                return code
    return name


def get_set_name(code: str) -> str:
    """Return the display name for a set code or abbreviation if available."""
    if not code:
        return ""
    search = code.strip().lower()
    for mapping in (
        tcg_sets_eng_code_map,
        tcg_sets_jp_code_map,
        tcg_sets_eng_abbr_name_map,
        tcg_sets_jp_abbr_name_map,
    ):
        for key, name in mapping.items():
            if key.lower() == search:
                return name
    logger.warning(
        "Nie znaleziono nazwy dla setu '%s'. Weryfikacja ręczna wymagana.",
        code,
    )
    return code


def get_set_abbr(name: str) -> str:
    """Return the abbreviation for a set name if available.

    Parameters
    ----------
    name:
        Display name or abbreviation of the set.

    Returns
    -------
    str
        Matching abbreviation or an empty string when not found.
    """

    if not name:
        return ""
    search = name.strip()
    # remove trailing language or other short alphabetic suffixes like "EN", "JP"
    search = re.sub(r"[-_\s]+[a-z]{1,2}$", "", search, flags=re.IGNORECASE)
    lowered = search.lower()
    for mapping in (tcg_sets_name_to_abbr, tcg_sets_jp_name_to_abbr):
        for key, abbr in mapping.items():
            if key.lower() == lowered or (abbr and abbr.lower() == lowered):
                return abbr or ""
    return ""


def get_set_era(code_or_name: str) -> str:
    """Return the era name for a given set code or display name."""
    if not code_or_name:
        return ""
    search = code_or_name.strip()
    search = re.sub(r"[-_\s]+[a-z]{1,3}$", "", search, flags=re.IGNORECASE)
    search = search.strip().lower()
    return SET_TO_ERA.get(search, "")

def lookup_sets_from_api(name: str, number: str, total: Optional[str] = None):
    """Return possible set codes and names for the given card info.

    Parameters
    ----------
    name:
        Card name.
    number:
        Card number within the set.
    total:
        Optional total number of cards in the set (e.g. ``102`` for
        ``25/102``). When provided it is included in the API query.

    Returns
    -------
    list[tuple[str, str]]
        A list of ``(set_code, set_name)`` tuples sorted by relevance.
    """
    if not total:
        number_str = str(number)
        if "/" in number_str:
            num_part, tot_part = number_str.split("/", 1)
            first = lookup_sets_from_api(name, num_part, tot_part)
            second = lookup_sets_from_api(name, num_part, None)
            seen = set()
            merged = []
            for item in first + second:
                if item not in seen:
                    merged.append(item)
                    seen.add(item)
            return merged
    number = sanitize_number(str(number))
    if total is not None:
        total = sanitize_number(str(total))

    name_api = normalize(name, keep_spaces=True)
    params = {"name": name_api, "number": number}
    if total:
        params["total"] = total

    # log input data
    print(
        f"[lookup_sets_from_api] name={name!r}, number={number!r}, total={total!r}"
    )

    headers = {"User-Agent": "kartoteka/1.0"}
    url = "https://www.tcggo.com/api/cards/"
    if RAPIDAPI_KEY and RAPIDAPI_HOST:
        url = f"https://{RAPIDAPI_HOST}/cards/search"
        headers["X-RapidAPI-Key"] = RAPIDAPI_KEY
        headers["X-RapidAPI-Host"] = RAPIDAPI_HOST

    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        if response.status_code != 200:
            print(f"[ERROR] API error: {response.status_code}")
            return []
        data = response.json()
    except requests.Timeout:
        logger.warning("Request timed out")
        return []
    except requests.RequestException as e:  # pragma: no cover - network/JSON errors
        logger.warning("Fetching sets from TCGGO failed: %s", e)
        return []
    except ValueError as e:
        logger.warning("Invalid JSON from TCGGO: %s", e)
        return []

    if isinstance(data, dict):
        if "cards" in data:
            cards = data["cards"]
        elif "data" in data:
            cards = data["data"]
        else:
            cards = []
    else:
        cards = data

    name_norm = normalize(name)
    number_norm = sanitize_number(str(number).strip().lower())
    total_norm = sanitize_number(str(total).strip().lower()) if total else None

    scores = {}
    for card in cards:
        episode = card.get("episode") or {}
        set_name = episode.get("name")
        set_code = episode.get("code") or episode.get("slug")
        if not (set_name and set_code):
            continue

        card_name_norm = normalize(card.get("name", ""))
        card_number_norm = str(card.get("card_number", "")).strip().lower()
        card_total_norm = str(card.get("total_prints", "")).strip().lower()

        score = 0
        if name_norm:
            if card_name_norm == name_norm:
                score += 2
            elif name_norm in card_name_norm:
                score += 1
        if number_norm:
            if card_number_norm == number_norm:
                score += 2
            elif number_norm in card_number_norm:
                score += 1
        if total_norm and card_total_norm == total_norm:
            score += 1

        key = (set_code, set_name)
        scores[key] = scores.get(key, 0) + score

    sorted_sets = sorted(
        ((key, sc) for key, sc in scores.items() if sc > 0),
        key=lambda item: item[1],
        reverse=True,
    )

    result = [key for key, _ in sorted_sets]
    # log the results
    if result:
        details = ", ".join(f"{c} ({n})" for c, n in result)
    else:
        details = "none"
    print(
        f"[lookup_sets_from_api] found {len(result)} set(s): {details}"
    )

    return result
def choose_nearest_locations(order_list, output_data):
    """Assign the nearest warehouse codes to order items.

    The function modifies the provided ``order_list`` in place, attaching a
    ``warehouse_code`` to each product when possible.  When multiple codes are
    available for the same ``product_code`` the combination with the smallest
    total Manhattan distance is chosen.
    """

    pattern = re.compile(r"K(\d+)R(\d)P(\d+)")
    available = defaultdict(list)

    # Collect available locations grouped by product_code
    for row in output_data:
        if not row:
            continue
        prod = str(row.get("product_code", ""))
        codes = str(row.get("warehouse_code") or "").split(";")
        for code in codes:
            code = code.strip()
            m = pattern.match(code)
            if not m:
                continue
            box, col, pos = map(int, m.groups())
            available[prod].append(((box, col, pos), code))

    def manhattan(a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])

    def best_codes(options, qty):
        if qty <= 1:
            return [options[0][1]]

        best = None
        best_cost = None
        for combo in combinations(options, min(qty, len(options))):
            coords = [c[0] for c in combo]
            cost = 0
            for i in range(len(coords)):
                for j in range(i + 1, len(coords)):
                    cost += manhattan(coords[i], coords[j])
            if best_cost is None or cost < best_cost:
                best_cost = cost
                best = [c[1] for c in combo]
        return best or []

    for order in order_list:
        for item in order.get("products", []):
            prod = str(item.get("product_code") or item.get("code") or "")
            qty = int(item.get("quantity", 1))
            options = available.get(prod)
            if not options:
                continue
            options.sort(key=lambda x: x[1])
            chosen = best_codes(options, qty)
            # remove used ones
            remaining = [o for o in options if o[1] not in chosen]
            available[prod] = remaining
            if chosen:
                item["warehouse_code"] = ";".join(chosen)

    return order_list


def extract_cardmarket_price(card):
    """Return an approximate Cardmarket price for a card.

    The function prefers the arithmetic mean of ``30d_average`` and
    ``trendPrice`` when both metrics are present and greater than zero.  If
    only one of them is available the respective value is returned.  When
    neither metric is usable the function falls back to ``lowest_near_mint``.
    ``None`` is returned when no positive price can be determined.
    """

    prices = (card or {}).get("prices") or {}
    cardmarket = prices.get("cardmarket") or {}

    def _get_float(key: str) -> float:
        try:
            return float(cardmarket.get(key, 0) or 0)
        except (TypeError, ValueError):
            return 0.0

    avg_30d = _get_float("30d_average")
    trend = _get_float("trendPrice") or _get_float("trend_price")

    values = [v for v in (avg_30d, trend) if v > 0]
    if len(values) == 2:
        value = sum(values) / 2
        print(
            f"[DEBUG] Using mean of Cardmarket fields '30d_average' ({avg_30d}) and "
            f"'trendPrice' ({trend}) -> {value}"
        )
        return value
    if len(values) == 1:
        value = values[0]
        field = "30d_average" if avg_30d > 0 else "trendPrice"
        print(f"[DEBUG] Using Cardmarket field '{field}' with value {value}")
        return value

    lowest = _get_float("lowest_near_mint")
    if lowest > 0:
        print(
            f"[DEBUG] Using Cardmarket field 'lowest_near_mint' with value {lowest}"
        )
        return lowest

    return None


def translate_to_english(text: str) -> str:
    """Return an English translation of ``text`` using OpenAI."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return text

    try:
        openai.api_key = api_key
        resp = openai.chat.completions.create(
            model="gpt-5",
            messages=[{"role": "user", "content": f"Translate to English: {text}"}],
            max_tokens=50,
        )
        return resp.choices[0].message.content.strip()
    except openai.OpenAIError as exc:
        logger.warning("Translation failed: %s", exc)
        return text


def load_set_logo_uris(
    limit: Optional[int] = DEFAULT_LOGO_LIMIT,
    available_sets: Optional[Iterable[str]] = None,
) -> dict:
    """Return a mapping of set code to data URI for set logos.

    Parameters
    ----------
    limit:
        Maximum number of logos to load. ``None`` loads all available logos.
    available_sets:
        Optional iterable of set codes to include. When provided and ``limit``
        is ``None``, the limit defaults to the number of available sets.
    """
    if available_sets is not None:
        available_sets = set(available_sets)
        if limit is None:
            limit = len(available_sets)
    logos = {}
    if not os.path.isdir(SET_LOGO_DIR):
        return logos
    files = sorted(os.listdir(SET_LOGO_DIR))
    for file in files:
        path = os.path.join(SET_LOGO_DIR, file)
        if not os.path.isfile(path):
            continue
        if not file.lower().endswith((".png", ".jpg", ".jpeg", ".gif")):
            continue
        code = os.path.splitext(file)[0]
        if available_sets is not None and code not in available_sets:
            continue
        try:
            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
            mime, _ = mimetypes.guess_type(path)
            if not mime:
                mime = "image/png"
            logos[code] = f"data:{mime};base64,{b64}"
        except OSError as exc:
            logger.warning("Failed to load logo %s: %s", path, exc)
            continue
        if limit is not None and len(logos) >= limit:
            break
    return logos


def match_set_code(value: str) -> str:
    """Return a set code that matches available logo filenames.

    The function performs an exact match against filenames in ``SET_LOGO_DIR``.
    When no exact match is found, a fuzzy match is attempted.  An empty string
    is returned if no suitable match is identified or when the logo directory
    is missing.
    """

    if not value:
        return ""
    value = value.strip().lower()
    if not value or not os.path.isdir(SET_LOGO_DIR):
        return ""

    codes = {
        os.path.splitext(f)[0].lower()
        for f in os.listdir(SET_LOGO_DIR)
        if os.path.isfile(os.path.join(SET_LOGO_DIR, f))
    }

    if value in codes:
        return value

    match = difflib.get_close_matches(
        value, list(codes), n=1, cutoff=SET_CODE_MATCH_CUTOFF
    )
    if match:
        return match[0]
    return ""


def get_symbol_rects(w: int, h: int) -> list[tuple[int, int, int, int]]:
    """Return possible rectangles around expected set symbol locations.

    The set symbol is usually near the bottom-left corner of a card, but
    rotated or unusually formatted scans may place it in other corners.  This
    helper returns a list of candidate rectangles in the following order:
    bottom-left, bottom-right, top-left and top-right.  For very small images
    (e.g. stand-alone set logos) the entire image is returned to ensure
    matching still works in tests and for direct logo comparisons.
    """

    # Use the full image for tiny logos
    if w <= 100 and h <= 100:
        return [(0, 0, w, h)]

    rects = []
    upper = int(h * 0.75)
    lower = int(h * 0.25)
    right = int(w * 0.35)
    left = w - right

    # Bottom-left
    rects.append((0, upper, right, h))
    # Bottom-right
    rects.append((left, upper, w, h))
    # Top-left
    rects.append((0, 0, right, lower))
    # Top-right
    rects.append((left, 0, w, lower))

    return rects


def identify_set_by_hash(
    scan_path: str, rect: tuple[int, int, int, int]
) -> list[tuple[str, str, int]]:
    """Identify the card set by comparing image hashes of the set symbol.

    Parameters
    ----------
    scan_path:
        Path to the card scan image.
    rect:
        Bounding box ``(left, upper, right, lower)`` containing the set symbol
        within the scan.

    Returns
    -------
    list[tuple[str, str, int]]
        List of up to four tuples containing the best matching set codes,
        their full set names and hash differences, sorted in ascending order.
        When matching fails, an empty list is returned.
    """

    if not _LOGO_HASHES and not load_logo_hashes():
        return []

    try:
        with Image.open(scan_path) as im:
            crop = im.crop(rect)
            crop = _preprocess_symbol(crop)
            crop_hashes = (
                imagehash.phash(crop),
                imagehash.dhash(crop),
                imagehash.average_hash(crop),
            )
    except (OSError, UnidentifiedImageError) as exc:
        logger.warning("Failed to process scan %s: %s", scan_path, exc)
        return []

    results: list[tuple[str, int]] = []
    for code, hashes in _LOGO_HASHES.items():
        diff = sum(h - c for h, c in zip(hashes, crop_hashes))
        results.append((code, int(diff)))

    results.sort(key=lambda x: x[1])
    symbol_hash = str(crop_hashes[0])
    for best_code, diff in results[:4]:
        logger.debug("Hash %s -> %s (%s)", symbol_hash, best_code, diff)
    return [(code, get_set_name(code), diff) for code, diff in results[:4]]


def extract_set_code_ocr(
    scan_path: str,
    rect: tuple[int, int, int, int],
    debug: bool = False,
    h_pad: int = 0,
    v_pad: int = 0,
) -> list[str]:
    """Extract potential set codes from the scan using OCR.

    Parameters
    ----------
    scan_path:
        Path to the card scan image.
    rect:
        Bounding box ``(left, upper, right, lower)`` containing the expected
        location of the set code.
    debug:
        When ``True``, save intermediate crop to ``OCR`` directory for
        diagnostic purposes. Errors during saving are ignored.
    h_pad:
        Optional horizontal padding (in pixels) removed from both left and
        right sides of the cropped region.
    v_pad:
        Optional vertical padding (in pixels) removed from both the top and
        bottom of the cropped region *after* the initial bottom slice.

    Returns
    -------
    list[str]
        List of unique set code strings recognized from the image. When no codes
        are recognized the list is empty.
    """

    try:
        with Image.open(scan_path) as im:
            crop = im.crop(rect)
            h = crop.height
            # Focus on the bottom 20% of the region where the set code appears.
            top = int(h * 0.8)
            crop = crop.crop((0, top, crop.width, h))
            if h_pad or v_pad:
                left = min(max(h_pad, 0), crop.width // 2)
                upper = min(max(v_pad, 0), crop.height // 2)
                right = max(crop.width - left, left)
                lower = max(crop.height - upper, upper)
                crop = crop.crop((left, upper, right, lower))
        if debug:
            try:
                from pathlib import Path

                debug_dir = Path("OCR")
                debug_dir.mkdir(exist_ok=True)
                debug_file = debug_dir / f"{Path(scan_path).stem}_set_crop.png"
                crop.convert("RGB").save(debug_file)
            except OSError as exc:  # pragma: no cover - debug only
                logger.debug("Failed to save debug image for %s: %s", scan_path, exc)
        crop = crop.convert("L")
        crop = ImageOps.autocontrast(crop)
        crop = crop.resize((crop.width * 4, crop.height * 4))
        raw = pytesseract.image_to_string(
            crop,
            config="--psm 7 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ/-",
        )
    except (OSError, UnidentifiedImageError, pytesseract.TesseractError) as exc:
        logger.warning("Failed to OCR set code from %s: %s", scan_path, exc)
        return []

    candidates: set[str] = set()
    for token in re.split(r"\s+", raw.upper()):
        token = re.sub(r"[^A-Z0-9]", "", token).strip()
        if len(token) > 1 and not token.isdigit():
            candidates.add(token.lower())

    return list(candidates)


# ZMIANA: Model Pydantic prosi teraz również o `set_name`
class CardInfo(BaseModel):
    """Structured card data returned by the model."""
    name: str = ""
    number: str = ""
    set_name: str = ""
    set_format: str = ""
    era_name: str = ""


# ZMIANA: Funkcja prosi OpenAI o wszystkie dane naraz, w tym o zestaw
def extract_card_info_openai(path: str) -> tuple[str, str, str, str, str, str, str]:
    """Recognize card name, number, set, and its format using OpenAI Vision.

    Returns a tuple ``(name, number, total, era_name, set_name, set_code, set_format)``.
    The ``set_name`` value is normalised to the canonical display name whenever
    a matching ``set_code`` can be resolved. ``set_format`` is ``"text"`` or
    ``"symbol"`` depending on how the set was detected.
    """
    try:
        parsed = urlparse(path)
        if parsed.scheme in ("http", "https"):
            try:
                r = requests.get(path, timeout=10)
                r.raise_for_status()
                mime = r.headers.get("Content-Type") or mimetypes.guess_type(path)[0] or "image/jpeg"
                encoded = base64.b64encode(r.content).decode("utf-8")
            except requests.RequestException as e:
                logger.warning("extract_card_info_openai failed to fetch image: %s", e)
                return "", "", "", "", "", "", ""
        else:
            mime = mimetypes.guess_type(path)[0] or "image/jpeg"
            try:
                with open(path, "rb") as f:
                    encoded = base64.b64encode(f.read()).decode("utf-8")
            except OSError as e:
                logger.warning("extract_card_info_openai failed to read image: %s", e)
                return "", "", "", "", "", "", ""
        data_url = f"data:{mime};base64,{encoded}"

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return "", "", "", "", "", "", ""
        client = openai.OpenAI(api_key=api_key)

        PROMPT = (
            "You must return a JSON object with the Pokémon card's English name, "
            "card number in the form NNN/NNN, English set name, era name, and whether "
            "the set is written as text or shown as a symbol. Also include the card's rarity, finish, energy type, language and quality. The response must strictly "
            'match {"name":"", "number":"", "set_name":"", "era_name":"", "set_format":"", "rarity":"", "finish":"", "energy":"", "language":"", "quality":""}.'
        )

        try:
            resp = client.responses.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o"),
                response_format={"type": "json_object"},
                input=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": PROMPT},
                            {"type": "input_image", "image_url": data_url},
                        ],
                    }
                ],
                max_output_tokens=150,
            )
            raw = getattr(resp, "output_text", "")
            raw = raw.strip().strip("`")
            if raw.startswith("json"):
                raw = raw[len("json") :].lstrip()
            match = re.search(r"{.*}", raw, re.DOTALL)
            if match:
                raw = match.group(0)
            if not raw:
                logger.error(
                    "extract_card_info_openai got empty response from OpenAI: %r",
                    resp,
                )
                return "", "", "", "", "", "", ""
            try:
                data_dict = json.loads(raw)
            except json.JSONDecodeError:
                logger.error("OpenAI returned non-JSON: %r", raw)
                return "", "", "", "", "", "", ""
        except TypeError:
            resp = client.responses.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o"),
                input=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": PROMPT},
                            {"type": "input_image", "image_url": data_url},
                        ],
                    }
                ],
                max_output_tokens=150,
            )
            raw = getattr(resp, "output_text", "")
            raw = raw.strip().strip("`")
            if raw.startswith("json"):
                raw = raw[len("json") :].lstrip()
            match = re.search(r"{.*}", raw, re.DOTALL)
            if match:
                raw = match.group(0)
            if not raw:
                logger.error(
                    "extract_card_info_openai got empty response from OpenAI: %r",
                    resp,
                )
                return "", "", "", "", "", "", ""
            try:
                data_dict = json.loads(raw)
            except json.JSONDecodeError:
                logger.error("OpenAI returned non-JSON: %r", raw)
                return "", "", "", "", "", "", ""

        data = data_dict

        raw_number = data.get("number") or ""
        number, total = "", ""
        if isinstance(raw_number, str):
            m = re.search(r"(\d+)(?:\s*/\s*(\d+))?", raw_number)
            if m:
                number, total = m.group(1), m.group(2) or ""
            else:
                number = re.sub(r"\D+", "", raw_number)

        name = data.get("name") or ""
        set_name = data.get("set_name") or ""
        set_format = data.get("set_format") or ""
        set_code = ""
        if set_name:
            set_code = get_set_code(set_name)
            mapped = get_set_name(set_code)
            if mapped:
                set_name = mapped
        era_name = data.get("era_name") or ""
        rarity = data.get("rarity") or ""
        finish = data.get("finish") or ""
        energy = data.get("energy") or ""
        language = data.get("language") or ""
        quality = data.get("quality") or ""
        return name, number, total, era_name, set_name, set_code, set_format, rarity, finish, energy, language, quality
    except Exception as e:
        logger.warning("extract_card_info_openai failed: %s", e)
        return "", "", "", "", "", "", ""

# ZMIANA: Całkowicie nowa, hierarchiczna logika analizy obrazu
def analyze_card_image(
    path: str,
    translate_name: bool = False,
    debug: bool = False,
    preview_cb=None,
    preview_image=None,
):
    """Return card details recognized from an image.

    The processing order is:
    1. Local set-symbol hash lookup.
    2. OpenAI Vision for text recognition.
    3. OCR as a final fallback.
    """
    parsed = urlparse(path)
    local_path = path if parsed.scheme not in ("http", "https") else None
    orientation = 0
    rects: list[tuple[int, int, int, int]] = []
    rect: Optional[tuple[int, int, int, int]] = None
    rotated_path = None
    if local_path and os.path.exists(local_path):
        try:
            with Image.open(local_path) as im:
                exif_orientation = im.getexif().get(0x0112, 1)
                im = ImageOps.exif_transpose(im)
                w, h = im.size
                orientation = 90 if exif_orientation in (6, 8) else 0
                if exif_orientation != 1:
                    rotated_path = local_path + ".rot.jpg"
                    im.save(rotated_path)
                    local_path = rotated_path
                    path = rotated_path
                rects = get_symbol_rects(w, h)
                if rects:
                    rect = rects[0]
        except (OSError, UnidentifiedImageError) as exc:
            logger.warning("Failed to preprocess %s: %s", local_path, exc)
            rects = []
            rect = None

    name = number = total = set_name = ""
    set_code = ""
    set_format = ""
    era_name = ""

    try:
        # --- PRIORITY 1: Local hash lookup for the set symbol ---
        if local_path:
            print("[INFO] Step 1: Matching set symbol via hash...")
            try:
                if not rects:
                    rects = [(0, 0, 0, 0)]
                if rect is None and rects:
                    rect = rects[0]

                for candidate in rects:
                    if preview_cb and preview_image is not None:
                        try:
                            preview_cb(candidate, preview_image)
                        except Exception as exc:
                            logger.exception("preview callback failed")
                    potential = identify_set_by_hash(local_path, candidate)
                    if potential:
                        code, name_match, diff = potential[0]
                        if diff <= HASH_DIFF_THRESHOLD:
                            rect = candidate
                            set_code = code
                            set_name = name_match
                            print(
                                f"[SUCCESS] Local hash analysis found a match: {name_match}"
                            )
                            era_name = get_set_era(set_code) or get_set_era(set_name)
                            result = {
                                "name": name,
                                "number": number,
                                "total": total,
                                "set": set_name,
                                "set_code": set_code,
                                "orientation": orientation,
                                "set_format": set_format,
                                "era": era_name,
                            }
                            if debug and rect:
                                result["rect"] = rect
                            return result
            except (OSError, UnidentifiedImageError, ValueError) as e:
                logger.warning("Hash lookup failed: %s", e)

        # --- PRIORITY 2: OpenAI Vision ---
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            print("[INFO] Step 2: Analyzing with OpenAI Vision...")
            try:
                name, number, total, era_name, set_name, set_code, set_format = extract_card_info_openai(path)

                if translate_name and name and not name.isascii():
                    name = translate_to_english(name)

                if name and number and set_name:
                    print(
                        f"[SUCCESS] OpenAI found all data: {name}, {number}, {set_name}"
                    )
                    era = era_name or get_set_era(set_code) or get_set_era(set_name)
                    result = {
                        "name": name,
                        "number": number,
                        "total": total,
                        "set": set_name,
                        "set_code": set_code,
                        "orientation": orientation,
                        "set_format": set_format,
                        "era": era,
                    }
                    if debug and rect:
                        result["rect"] = rect
                    return result

                print(
                    "[INFO] OpenAI returned partial data. Proceeding to fallback methods."
                )

            except Exception as e:
                logger.warning("OpenAI analysis failed: %s", e)
                name = number = total = set_name = ""
                set_code = ""
        else:
            print("[WARN] No OpenAI API key. Skipping to OCR.")

        # --- PRIORITY 3: TCGGO API Lookup (if name and number are known) ---
        if name and number:
            print("[INFO] Step 3: Looking up sets via TCGGO API...")
            try:
                api_sets = lookup_sets_from_api(name, number, total or None)
                if len(api_sets) == 1:
                    set_code, api_set_name = api_sets[0]
                    print(
                        f"[SUCCESS] TCGGO API found a single match: {api_set_name}"
                    )
                    era = get_set_era(set_code) or get_set_era(api_set_name)
                    result = {
                        "name": name,
                        "number": number,
                        "total": total,
                        "set": api_set_name,
                        "set_code": set_code,
                        "orientation": orientation,
                        "set_format": set_format,
                        "era": era,
                    }
                    if debug and rect:
                        result["rect"] = rect
                    return result

                if len(api_sets) > 1:
                    set_code, selected_name = api_sets[0]
                    print(
                        "[INFO] TCGGO API found multiple matches. "
                        f"Selecting first result: {selected_name}"
                    )
                    era = get_set_era(set_code) or get_set_era(selected_name)
                    result = {
                        "name": name,
                        "number": number,
                        "total": total,
                        "set": selected_name,
                        "set_code": set_code,
                        "orientation": orientation,
                        "set_format": set_format,
                        "era": era,
                    }
                    if debug and rect:
                        result["rect"] = rect
                    return result

            except (requests.RequestException, ValueError) as e:
                logger.warning("TCGGO API lookup failed: %s", e)

        # --- PRIORITY 4: OCR fallback ---
        if local_path:
            print("[INFO] Step 4: Performing OCR fallback...")
            try:
                if not rects:
                    rects = [(0, 0, 0, 0)]
                if rect is None and rects:
                    rect = rects[0]

                for candidate in rects:
                    if preview_cb and preview_image is not None:
                        try:
                            preview_cb(candidate, preview_image)
                        except Exception as exc:
                            logger.exception("preview callback failed")
                    ocr_codes = extract_set_code_ocr(local_path, candidate, debug)
                    for code in ocr_codes:
                        name_lookup = get_set_name(code)
                        if name_lookup and name_lookup != code:
                            rect = candidate
                            set_code = code
                            set_name = name_lookup
                            print(f"[SUCCESS] OCR recognized set code: {name_lookup}")
                            era = get_set_era(set_code) or get_set_era(set_name)
                            result = {
                                "name": name,
                                "number": number,
                                "total": total,
                                "set": set_name,
                                "set_code": set_code,
                                "orientation": orientation,
                                "set_format": set_format,
                                "era": era,
                            }
                            if debug and rect:
                                result["rect"] = rect
                            return result
                        else:
                            print(f"[WARN] OCR produced unknown set code: {code}")
            except Exception:
                logger.exception("OCR analysis failed")

        # If all methods fail, return any partial data we might have
        print("[FAIL] All analysis methods failed to find a definitive set.")
        era = era_name or get_set_era(set_code) or get_set_era(set_name)
        result = {
            "name": name,
            "number": number,
            "total": total,
            "set": set_name,
            "set_code": set_code,
            "orientation": orientation,
            "set_format": set_format,
            "era": era,
        }
        if debug and rect:
            result["rect"] = rect
        return result
    finally:
        if rotated_path and os.path.exists(rotated_path):
            try:
                os.remove(rotated_path)
            except OSError:
                pass


class CardEditorApp:
    API_TIMEOUT = 30

    def __init__(self, root):
        self.root = root
        self.root.title("KARTOTEKA")
        # improve default font for all widgets
        self.root.configure(bg=BG_COLOR, fg_color=BG_COLOR)
        self.root.option_add("*Font", ("Segoe UI", 20))
        self.root.option_add("*Foreground", TEXT_COLOR)
        self.index = 0
        self.cards = []
        self.image_objects = []
        self.output_data = []
        self.session_entries: list[dict[str, Any] | None] = []
        self.card_counts = defaultdict(int)
        self.shoper_language_overrides = self._load_shoper_language_overrides()
        self.card_cache = {}
        self._default_availability_value: Optional[str] = None
        self._default_availability_id: Optional[int] = getattr(
            csv_utils, "get_default_availability_id", lambda: None
        )()
        initial_availability = csv_utils.get_default_availability()
        if isinstance(initial_availability, str):
            initial_availability = initial_availability.strip()
            if initial_availability:
                self._default_availability_value = initial_availability
        self.file_to_key = {}
        self.product_code_map = {}
        cache_data = csv_utils.load_store_cache()
        self.store_data = dict(cache_data) if isinstance(cache_data, dict) else {}
        if not self.store_data:
            fetched = self._load_store_products_from_api()
            if fetched:
                self.store_data.update(fetched)
                self._persist_store_cache()
        self.card_type_var = _create_string_var(CARD_TYPE_DEFAULT)
        self.card_type_display_var = _create_string_var(DEFAULT_CARD_FINISH_LABEL)
        self._finish_attribute_id: Optional[int] = None
        self._finish_value_to_variant: dict[Any, CardFinishSelection] = {}
        self._finish_variant_to_value: dict[tuple[str, str], Any] = {}
        self._finish_label_to_value: dict[str, Any] = {}
        self._finish_value_to_label: dict[Any, str] = {}
        self._pending_finish_selection: CardFinishSelection | None = None
        self.finish_var = _create_string_var()
        self.ball_var = _create_string_var()

        self.categories_map = {}
        self.attributes_map = {}
        self.attributes_by_name = {}

        self._latest_export_rows: list[dict[str, Any]] = []
        self._summary_warehouse_written = False
        try:
            if HashDB and HASH_DB_FILE:
                db_path = Path(HASH_DB_FILE)
                db_path.parent.mkdir(parents=True, exist_ok=True)
                db_path.touch(exist_ok=True)
                self.hash_db = HashDB(str(db_path))
            else:
                self.hash_db = None
        except Exception as exc:
            logger.warning("Failed to init hash DB: %s", exc)
            self.hash_db = None
        self.auto_lookup = AUTO_HASH_LOOKUP
        self.current_fingerprint = None
        self.selected_candidate_meta = None
        self.price_db = self.load_price_db()
        self.folder_name = ""
        self.folder_path = ""
        self.sets_file = "tcg_sets.json"
        self.progress_var = tk.StringVar(value="0/0 (0%)")
        self.start_box_var = tk.StringVar(value="1")
        self.start_col_var = tk.StringVar(value="1")
        self.start_pos_var = tk.StringVar(value="1")
        self.scan_folder_var = tk.StringVar()
        self.starting_idx = 0
        self.start_frame = None
        self.shoper_frame = None
        self.pricing_frame = None
        self.magazyn_frame = None
        self.location_frame = None
        self.auction_frame = None
        self.auction_preview_window = None
        self.auction_preview_tree = None
        self.auction_preview_next_var = None
        self.auction_preview_image_label = None
        selfself.auction_preview_photo = None
        self.auction_preview_name_var = tk.StringVar(value="")
        # Locally tracked warehouse codes considered "sold" for UI overlay.
        # This ensures the magazyn view can immediately reflect sold status
        # based on current orders and recent actions, even before API/cache sync.
        self._locally_sold_codes: set[str] = set()
        self.auction_preview_price_var = tk.StringVar(value="Cena: -")
        self.auction_preview_start_var = tk.StringVar(value="")
        self.auction_preview_time_var = tk.StringVar(value="30")
        self.auction_preview_step_var = tk.StringVar(value="")
        self.auction_preview_timer_var = tk.StringVar(value="0 s")
        self.auction_preview_leader_var = tk.StringVar(value="-")
        self.auction_preview_amount_var = tk.StringVar(value="-")

        self._load_id_maps()

    def _load_id_maps(self):
        try:
            with open("ids_dump.json", "r", encoding="utf-8") as f:
                ids_data = json.load(f)

            # Process categories (sets)
            self.categories_map = {
                cat["translations"]["pl_PL"]["name"]: cat["category_id"]
                for cat in ids_data.get("categories", [])
                if "pl_PL" in cat.get("translations", {})
            }

            # Process attributes
            self.attributes_map = {}
            self.attributes_by_name = {}
            for attr in ids_data.get("attributes", []):
                group_id = attr.get("attribute_group_id")
                attr_id = attr.get("attribute_id")
                if not group_id or not attr_id:
                    continue
                
                # Main map keyed by group_id
                self.attributes_map[group_id] = {
                    "name": attr["name"],
                    "attribute_id": attr_id, # Store the attribute_id
                    "options": {
                        opt["value"]: opt["option_id"]
                        for opt in attr.get("options", [])
                    },
                }
                # Reverse map for name -> group_id
                self.attributes_by_name[attr["name"]] = group_id

            logger.info("Successfully loaded ID maps from ids_dump.json")

        except FileNotFoundError:
            logger.error("ids_dump.json not found! Dropdowns will be empty.")
            messagebox.showerror("Błąd krytyczny", "Nie znaleziono pliku ids_dump.json! Pola wyboru będą puste.")
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse ids_dump.json: {e}")
            messagebox.showerror("Błąd krytyczny", f"Błąd podczas przetwarzania ids_dump.json: {e}")

        self._auction_preview_selected_index: Optional[int] = None
        self._auction_preview_updating = False
        self._auction_preview_trace_ids: list[tuple[tk.Variable, str]] = []
        self.auction_run_window = None
        self.bot = None
        self.mag_progressbars: dict[tuple[int, int], ctk.CTkProgressBar] = {}
        self.mag_percent_labels: dict[tuple[int, int], ctk.CTkLabel] = {}
        self.mag_labels: list[ctk.CTkLabel] = []
        self.inventory_service = WarehouseInventoryService.create_default()
        try:
            # Hook progress reporting from API->local DB sync
            self.inventory_service.progress_callback = self._inventory_sync_progress
        except Exception:
            pass
        self._mag_inventory_version: Any | None = None
        self._mag_snapshot = None
        self.log_widget = None
        self.cheat_frame = None
        self.set_logos = {}
        self.loading_frame = None
        self.loading_label = None
        self.price_pool_total = 0.0
        self.pool_total_label = None
        self.auction_queue = []
        self.in_scan = False
        self.attribute_values: dict[int, dict[int, Any]] = {}
        self._attribute_controls: dict[tuple[int, int], dict[str, Any]] = {}
        self._pending_attribute_payload: Optional[Mapping[int, Mapping[int, Any]]] = None
        self._attribute_editor_initialized = False
        self._attribute_cache: dict[str, Any] = {}
        self.current_image_path = ""
        self.current_analysis_thread = None
        self.current_location = ""
        self.summary_frame: ctk.CTkFrame | None = None
        # Status bar (persistent) and progress helpers
        try:
            self.status_var = _create_string_var("Gotowy")
        except Exception:
            self.status_var = _create_string_var("")
        try:
            self.status_bar = ctk.CTkFrame(self.root, fg_color="#262626")
            self.status_bar.pack(side="bottom", fill="x")
            self.status_label = ctk.CTkLabel(
                self.status_bar,
                textvariable=self.status_var,
                anchor="w",
                text_color="#BBBBBB",
            )
            self.status_label.pack(side="left", padx=10, pady=3)
            self.status_progress = ctk.CTkProgressBar(
                self.status_bar,
                width=180,
                fg_color="#2b2b2b",
                progress_color="#5c84ff",
            )
            self.status_progress.set(0)
            self.status_progress.pack(side="right", padx=10, pady=3)
            # Hide by default
            self.status_progress.pack_forget()
        except Exception:
            # Best-effort: status bar is optional
            self.status_bar = None
            self.status_label = None
            self.status_progress = None
        self._progress_total = None
        self._progress_done = 0
        self._progress_start_ts = 0.0

        # Order notifications: track known order IDs and start polling
        self._known_order_ids: set[str | int] = set()
        try:
            # Seed current orders silently, then start periodic notifications
            self.root.after(1500, self._seed_order_notifications)
            self.root.after(10000, self._start_order_notifications)
        except Exception:
            pass

        self.show_loading_screen()
        self.root.after(0, self.startup_tasks)

    # -----------------------
    # Status helpers
    # -----------------------
    def set_status(self, text: str, *, temporary: bool = False, ms: int = 2500) -> None:
        def _apply():
            try:
                self.status_var.set(str(text))
            except Exception:
                pass
            if temporary:
                try:
                    self.root.after(ms, lambda: self.status_var.set(""))
                except Exception:
                    pass
        try:
            self.root.after(0, _apply)
        except Exception:
            _apply()

    @staticmethod
    def _format_duration(seconds: float) -> str:
        try:
            seconds = max(0, int(seconds))
            m, s = divmod(seconds, 60)
            if m >= 60:
                h, m = divmod(m, 60)
                return f"{h}h {m}m {s}s"
            if m > 0:
                return f"{m}m {s}s"
            return f"{s}s"
        except Exception:
            return "--"

    def progress_begin(self, *, total: int | None = None) -> None:
        def _apply():
            try:
                if not self.status_progress:
                    return
                self.status_progress.pack(side="right", padx=10, pady=3)
                if total is None:
                    if hasattr(self.status_progress, "start"):
                        self.status_progress.start()
                    else:
                        self.status_progress.set(0.2)
                else:
                    if hasattr(self.status_progress, "stop"):
                        self.status_progress.stop()
                    self.status_progress.set(0)
                self._progress_total = total
                self._progress_done = 0
                self._progress_start_ts = time.time()
            except Exception:
                pass
        try:
            self.root.after(0, _apply)
        except Exception:
            _apply()

    def progress_update(self, done: int, total: int | None = None) -> None:
        def _apply():
            try:
                if not self.status_progress:
                    return
                if total is None:
                    total = getattr(self, "_progress_total", None)
                if total and total > 0:
                    val = max(0.0, min(1.0, done / float(total)))
                    if hasattr(self.status_progress, "stop"):
                        self.status_progress.stop()
                    self.status_progress.set(val)
                    # update ETA in status if current text refers to sync
                    elapsed = time.time() - (self._progress_start_ts or time.time())
                    remaining = (total - done) / (done / elapsed) if done > 0 else 0
                    eta_txt = self._format_duration(remaining)
                    try:
                        cur = self.status_var.get()
                    except Exception:
                        cur = ""
                    if cur:
                        if "ETA" in cur:
                            cur = cur.split(" ETA", 1)[0]
                        self.status_var.set(f"{cur} ETA {eta_txt}")
                self._progress_done = done
                self._progress_total = total
            except Exception:
                pass
        try:
            self.root.after(0, _apply)
        except Exception:
            _apply()

    def progress_end(self) -> None:
        def _apply():
            try:
                if not self.status_progress:
                    return
                if hasattr(self.status_progress, "stop"):
                    self.status_progress.stop()
                self.status_progress.set(0)
                self.status_progress.pack_forget()
            except Exception:
                pass
        try:
            self.root.after(0, _apply)
        except Exception:
            _apply()

    # -----------------------
    # Inventory sync progress handler
    # -----------------------
    def _inventory_sync_progress(self, event: Mapping[str, Any] | None) -> None:
        """Handle progress events from inventory sync and reflect in UI."""
        if not isinstance(event, Mapping):
            return
        phase = str(event.get("phase") or "").strip()
        # Prepare UI elements
        frame = getattr(self, "sync_frame", None)
        label_var = getattr(self, "sync_label_var", None)
        bar = getattr(self, "sync_progress", None)
        try:
            if frame and hasattr(frame, "pack"):
                frame.pack(fill="x", padx=10, pady=(0, 8))
        except Exception:
            pass
        if phase == "page":
            page = int(event.get("page") or 1)
            pages = int(event.get("pages") or 1)
            processed = int(event.get("processed") or 0)
            total_items = event.get("total_items")
            # Update bottom status bar with product-based progress when available
            if isinstance(total_items, int) and total_items > 0:
                msg = f"Pobieranie produktów: {processed}/{total_items} • strona {page}/{pages}"
            else:
                msg = f"Pobieranie produktów: strona {page}/{pages} • zapisano {processed}"
            try:
                self.set_status(msg)
            except Exception:
                pass
            try:
                if label_var:
                    label_var.set(msg)
                if bar and pages:
                    bar.set(max(0.0, min(1.0, (page - 1) / float(pages))))
                # Bottom status bar progress
                try:
                    if isinstance(total_items, int) and total_items > 0:
                        self.progress_begin(total=total_items)
                    else:
                        self.progress_begin(total=pages)
                except Exception:
                    pass
                try:
                    if isinstance(total_items, int) and total_items > 0:
                        self.progress_update(done=processed, total=total_items)
                    else:
                        self.progress_update(done=max(0, page - 1), total=pages)
                except Exception:
                    pass
            except Exception:
                pass
        elif phase == "page_done":
            page = int(event.get("page") or 1)
            pages = int(event.get("pages") or 1)
            processed = int(event.get("processed") or 0)
            total_items = event.get("total_items")
            msg = f"Zapisano {processed} pozycji (strona {page}/{pages})"
            try:
                # Reflect progress also in bottom status bar
                try:
                    self.set_status(msg)
                except Exception:
                    pass
                if label_var:
                    label_var.set(msg)
                if bar and pages:
                    bar.set(max(0.0, min(1.0, page / float(pages))))
                try:
                    if isinstance(total_items, int) and total_items > 0:
                        self.progress_update(done=processed, total=total_items)
                    else:
                        self.progress_update(done=page, total=pages)
                except Exception:
                    pass
            except Exception:
                pass
        elif phase == "done":
            processed = int(event.get("processed") or 0)
            try:
                if label_var:
                    label_var.set(f"Zakończono synchronizację. Zapisano {processed} pozycji.")
                # Show completion message in the bottom status bar (temporary)
                try:
                    self.set_status(f"Synchronizacja zakończona • zapisano {processed}", temporary=True, ms=6000)
                except Exception:
                    pass
                # Hide after a short delay
                if frame and hasattr(self.root, "after"):
                    self.root.after(2500, lambda: frame.pack_forget())
                try:
                    self.progress_end()
                except Exception:
                    pass
            except Exception:
                pass

    # -----------------------
    # Order notifications
    # -----------------------
    def _seed_order_notifications(self) -> None:
        """Populate the known orders set without showing notifications.

        Prevents showing existing orders as "new" on first poll.
        """
        try:
            client = getattr(self, "shoper_client", None) or self._get_product_client()
            if not client:
                return
            status_filters = {"status_id[in]": "1,2,3,4"}
            orders = client.list_orders(status_filters)
            raw = orders.get("list", orders)
            if isinstance(raw, Mapping):
                raw = raw.get("list", [])
            current = [o for o in raw or [] if o]
            for order in current:
                oid = order.get("order_id") or order.get("id")
                if oid is not None:
                    self._known_order_ids.add(oid)
            # Clear any visible banner
            note_var = getattr(self, "orders_notification_var", None)
            if note_var is not None:
                try:
                    note_var.set("")
                except Exception:
                    pass
        except Exception:
            logger.exception("Failed to seed order notifications")
    def _start_order_notifications(self) -> None:
        try:
            self._poll_orders_for_notifications()
        finally:
            try:
                # Repeat periodically
                self.root.after(60000, self._start_order_notifications)
            except Exception:
                pass

    def _poll_orders_for_notifications(self) -> None:
        try:
            client = getattr(self, "shoper_client", None) or self._get_product_client()
            if not client:
                return
            status_filters = {"status_id[in]": "1,2,3,4"}
            orders = client.list_orders(status_filters)
            orders_list_raw = orders.get("list", orders)
            if isinstance(orders_list_raw, Mapping):
                orders_list_raw = orders_list_raw.get("list", [])
            orders_list = [o for o in orders_list_raw if o]
            new_ids = []
            for order in orders_list:
                oid = order.get("order_id") or order.get("id")
                if oid is not None and oid not in self._known_order_ids:
                    new_ids.append(oid)
                    self._known_order_ids.add(oid)
            if new_ids:
                # Show a concise notification
                msg = (
                    f"Nowe zamówienia: {len(new_ids)} (np. #{new_ids[0]})"
                    if len(new_ids) > 1
                    else f"Nowe zamówienie #{new_ids[0]}"
                )
                try:
                    self.set_status(msg, temporary=True, ms=6000)
                    if hasattr(self.root, "bell"):
                        self.root.bell()
                    # Also surface the info on the welcome screen
                    note_var = getattr(self, "orders_notification_var", None)
                    if note_var is not None:
                        try:
                            note_var.set(msg)
                        except Exception:
                            pass
                except Exception:
                    pass
                # If orders list is visible, refresh it
                try:
                    if hasattr(self, "show_orders") and getattr(self, "orders_output", None):
                        self.show_orders(self.orders_output)
                except Exception:
                    pass
        except Exception:
            logger.exception("Failed to poll orders for notifications")

    def _compute_shoper_sales(self, start: datetime.date | None = None, end: datetime.date | None = None) -> tuple[int, float]:
        """Return (sold_count, sold_total_value) from Shoper orders.

        Applies optional date filter using common order date fields. Uses
        environment-driven status sets compatible with stats_service.
        """
        client = getattr(self, "shoper_client", None) or self._get_product_client()
        if not client:
            return 0, 0.0

        def _parse_date(val: Any) -> datetime.date | None:
            if not val:
                return None
            text = str(val).strip().split("T", 1)[0]
            try:
                return datetime.date.fromisoformat(text)
            except ValueError:
                return None

        # Build preferred filters for sold statuses
        try:
            names = os.getenv("SHOPER_SOLD_STATUSES", "paid,completed,finished,shipped")
            status_names = [s.strip() for s in names.replace(";", ",").split(",") if s.strip()]
        except Exception:
            status_names = ["paid", "completed", "finished", "shipped"]
        ids = [s.strip() for s in str(os.getenv("SHOPER_SOLD_STATUS_IDS", "")).replace(";", ",").split(",") if s.strip()]

        count = 0
        total = 0.0

        def _within(d: datetime.date | None) -> bool:
            if d is None:
                return True if (start is None and end is None) else False
            if start and d < start:
                return False
            if end and d > end:
                return False
            return True

        def _sum(filters: dict) -> tuple[int, float]:
            _c, _t = 0, 0.0
            page = 1
            per_page = 50
            while True:
                try:
                    resp = client.list_orders(filters, page=page, per_page=per_page, include_products=True)
                except Exception:
                    break
                raw_list = resp.get("list", resp)
                if isinstance(raw_list, Mapping):
                    raw_list = raw_list.get("list", [])
                orders = [o for o in raw_list or [] if o]
                if not orders:
                    break
                for order in orders:
                    d = (
                        _parse_date(order.get("order_date"))
                        or _parse_date(order.get("created_at"))
                        or _parse_date(order.get("date_add"))
                        or _parse_date(order.get("date"))
                    )
                    if not _within(d):
                        continue
                    for line in (order.get("products") or []):
                        try:
                            qty = int(float(str(line.get("quantity") or 0)))
                        except Exception:
                            qty = 0
                        try:
                            price = float(str(line.get("price_gross") or line.get("price") or 0).replace(",", "."))
                        except Exception:
                            price = 0.0
                        _c += qty
                        _t += price * qty
                page += 1
                if page > 1000:
                    break
            return _c, _t

        # Try with IDs first, then names
        if ids:
            c, t = _sum({"status_id[in]": ",".join(ids)})
            count += c
            total += t
        else:
            c, t = _sum({"status": ",".join(status_names)})
            count += c
            total += t
        if count == 0 and ids:
            c, t = _sum({"status": ",".join(status_names)})
            count += c
            total += t
        return count, total

    def setup_welcome_screen(self):
        """Display a simple welcome screen before loading scans."""
        w, h = 1920, 1080
        if all(
            hasattr(self.root, attr)
            for attr in ("geometry", "winfo_screenwidth", "winfo_screenheight")
        ):
            self.root.geometry(f"{w}x{h}")
            screen_w = self.root.winfo_screenwidth()
            screen_h = self.root.winfo_screenheight()
            x = (screen_w - w) // 2
            y = (screen_h - h) // 2
            self.root.geometry(f"{w}x{h}+{x}+{y}")

        # Allow resizing but provide a sensible minimum size
        self.root.minsize(1200, 800)
        self.start_frame = ctk.CTkFrame(
            self.root, fg_color=BG_COLOR, corner_radius=10
        )
        self.start_frame.pack(expand=True, fill="both")
        # Divide the start frame into a narrow menu on the left and a wider
        # main content area on the right.  Approximately one third of the
        # width is dedicated to the menu.
        self.start_frame.grid_columnconfigure(0, weight=1)
        self.start_frame.grid_columnconfigure(1, weight=2)

        menu_frame = ctk.CTkFrame(self.start_frame, fg_color=LIGHT_BG_COLOR)
        menu_frame.grid(row=0, column=0, sticky="nsew")
        if hasattr(menu_frame, "pack_propagate"):
            menu_frame.pack_propagate(False)

        main_frame = ctk.CTkFrame(self.start_frame, fg_color=BG_COLOR)
        main_frame.grid(row=0, column=1, sticky="nsew")

        logo_path = os.path.join(os.path.dirname(__file__), "banner22.png")
        if os.path.exists(logo_path):
            logo_img = load_rgba_image(logo_path)
            if logo_img:
                logo_img.thumbnail((200, 200))
                self.logo_photo = _create_image(logo_img)
                logo_label = ctk.CTkLabel(
                    menu_frame,
                    image=self.logo_photo,
                    text="",
                )
                logo_label.pack(pady=(10, 10))

        greeting = ctk.CTkLabel(
            main_frame,
            text="Witaj w aplikacji KARTOTEKA",
            text_color=TEXT_COLOR,
            font=("Segoe UI", 24, "bold"),
        )
        greeting.pack(pady=5, fill="x")

        desc = ctk.CTkLabel(
            main_frame,
            text=(
                "Aplikacja KARTOTEKA.SHOP pomaga przygotować skany do sprzedaży."
            ),
            wraplength=1400,
            justify="center",
            text_color=TEXT_COLOR,
            font=("Segoe UI", 18),
        )
        desc.pack(pady=5, fill="x")
        # Notification strip for new orders on the main screen
        try:
            self.orders_notification_var = tk.StringVar(value="")
            self.orders_notification_label = ctk.CTkLabel(
                main_frame,
                textvariable=self.orders_notification_var,
                text_color="#ffd166",
                font=("Segoe UI", 18, "bold"),
            )
            self.orders_notification_label.pack(pady=(0, 8), fill="x")
        except Exception:
            self.orders_notification_var = _create_string_var("")

        # Sync progress (API -> lokalna baza)
        try:
            self.sync_frame = ctk.CTkFrame(main_frame, fg_color=LIGHT_BG_COLOR)
            self.sync_frame.pack(fill="x", padx=10, pady=(0, 8))
            self.sync_label_var = _create_string_var("")
            self.sync_label = ctk.CTkLabel(
                self.sync_frame,
                textvariable=self.sync_label_var,
                text_color=TEXT_COLOR,
                font=("Segoe UI", 16),
                anchor="w",
            )
            self.sync_label.pack(side="left", padx=8, pady=6)
            self.sync_progress = ctk.CTkProgressBar(
                self.sync_frame, fg_color="#2b2b2b", progress_color="#5c84ff"
            )
            self.sync_progress.set(0)
            self.sync_progress.pack(side="right", padx=8, pady=6, fill="x", expand=True)
            # Hidden initially
            self.sync_frame.pack_forget()
        except Exception:
            self.sync_frame = None

        # Prefer Shoper-based statistics (with cache); fallback to CSV
        try:
            from .stats_service import get_cached_or_compute
            client = getattr(self, "shoper_client", None)
            if client is None:
                inv = getattr(self, "inventory_service", None) or WarehouseInventoryService.create_default()
                client = getattr(inv, "_client", None)
            api_stats = get_cached_or_compute(client) if client else None
        except Exception:
            api_stats = None
        if api_stats:
            unsold_count = int(api_stats.get("unsold_count", 0))
            unsold_total = float(api_stats.get("unsold_total", 0.0))
            sold_count = int(api_stats.get("sold_count", 0))
            sold_total = float(api_stats.get("sold_total", 0.0))
        else:
            unsold_count, unsold_total, sold_count, sold_total = csv_utils.get_inventory_stats()
        if unsold_count == 0 and sold_count == 0:
            messagebox.showinfo("Magazyn", "Brak kart w magazynie")
        # Module buttons stacked vertically in the menu
        scan_btn = self.create_button(
            menu_frame,
            text="\U0001f50d Skanuj",
            command=self.show_location_frame,
            fg_color=SCAN_BUTTON_COLOR,
            width=100,
        )
        scan_btn.pack(padx=10, pady=5, fill="x")
        self.create_button(
            menu_frame,
            text="\U0001f4b0 Wyceniaj",
            command=self.setup_pricing_ui,
            fg_color=PRICE_BUTTON_COLOR,
            width=100,
        ).pack(padx=10, pady=5, fill="x")
        self.create_button(
            menu_frame,
            text="\U0001f5c3\ufe0f Shoper",
            command=self.open_shoper_window,
            fg_color=SHOPER_BUTTON_COLOR,
            width=100,
        ).pack(padx=10, pady=5, fill="x")
        self.create_button(
            menu_frame,
            text="\U0001f4e6 Magazyn",
            command=self.show_magazyn_view,
            fg_color=MAGAZYN_BUTTON_COLOR,
            width=100,
        ).pack(padx=10, pady=5, fill="x")
        self.create_button(
            menu_frame,
            text="\U0001f528 Licytacje",
            command=self.open_auctions_window,
            fg_color=AUCTION_BUTTON_COLOR,
            width=100,
        ).pack(padx=10, pady=5, fill="x")

        self.create_button(
            menu_frame,
            text="\U0001F4C8 Statystyki",
            command=getattr(self, "open_statistics_window", lambda: None),
            fg_color=STATS_BUTTON_COLOR,
            width=100,
        ).pack(padx=10, pady=5, fill="x")

        ctk.CTkLabel(
            main_frame,
            text="Podgląd kartonów",
            text_color=TEXT_COLOR,
            font=("Segoe UI", 24, "bold"),
        ).pack(pady=(20, 0))

        box_frame = ctk.CTkFrame(main_frame, fg_color=LIGHT_BG_COLOR)
        box_frame.pack(anchor="center", padx=10, pady=10)

        CardEditorApp.build_home_box_preview(self, box_frame)
        # Refresh the initial box preview if possible.  The welcome screen does
        # not depend on the full warehouse window, therefore it prefers a
        # lightweight ``refresh_home_preview`` method but falls back to the
        # legacy ``refresh_magazyn`` if needed.
        if hasattr(self, "refresh_home_preview"):
            try:
                self.refresh_home_preview()
            except Exception:  # pragma: no cover - defensive logging
                logger.exception("Failed to refresh magazyn preview")
        elif hasattr(self, "refresh_magazyn"):
            try:
                self.refresh_magazyn()
            except Exception:  # pragma: no cover - defensive logging
                logger.exception("Failed to refresh magazyn preview")

        ctk.CTkLabel(
            main_frame,
            text="Statystyki",
            text_color=TEXT_COLOR,
            font=("Segoe UI", 24, "bold"),
        ).pack(pady=(20, 0))

        info_frame = ctk.CTkFrame(main_frame, fg_color=LIGHT_BG_COLOR)
        info_frame.pack(fill="x", padx=10, pady=(0, 40))

        self.inventory_count_label = ctk.CTkLabel(
            info_frame,
            text=f"📊 Łączna liczba kart: {unsold_count}",
            text_color=TEXT_COLOR,
            font=("Segoe UI", 24, "bold"),
            justify="left",
        )
        # Two-column summary: counts (left) and values (right)
        info_frame.pack_propagate(False)
        cols = ctk.CTkFrame(info_frame, fg_color=LIGHT_BG_COLOR)
        cols.pack(anchor="center", pady=(4, 0), fill="x")
        left_col = ctk.CTkFrame(cols, fg_color=LIGHT_BG_COLOR)
        right_col = ctk.CTkFrame(cols, fg_color=LIGHT_BG_COLOR)
        left_col.pack(side="left", padx=10)
        right_col.pack(side="left", padx=10)

        self.inventory_count_label.pack(in_=left_col, anchor="w")

        self.inventory_value_label = ctk.CTkLabel(
            info_frame,
            text=f"💰 Łączna wartość: {unsold_total:.2f} PLN",
            text_color="#FFD700",
            font=("Segoe UI", 24, "bold"),
            justify="left",
        )
        self.inventory_value_label.pack(in_=right_col, anchor="w")

        self.inventory_sold_count_label = ctk.CTkLabel(
            info_frame,
            text=f"Sprzedane karty: {sold_count}",
            text_color=TEXT_COLOR,
            font=("Segoe UI", 24, "bold"),
            justify="left",
        )
        self.inventory_sold_count_label.pack(in_=left_col, anchor="w", pady=(0, 5))

        self.inventory_sold_value_label = ctk.CTkLabel(
            right_col,
            text=f"Wartość sprzedanych: {sold_total:.2f} PLN",
            text_color=TEXT_COLOR,
            font=("Segoe UI", 24, "bold"),
            justify="left",
        )
        self.inventory_sold_value_label.pack(anchor="w")

        # Usunięto podgląd wykresu na ekranie startowym, pełne statystyki są
        # dostępne w widoku Statystyki.

        config_btn = self.create_button(
            menu_frame,
            text="\u2699\ufe0f Konfiguracja",
            command=self.open_config_dialog,
            fg_color="#404040",
            width=100,
        )
        config_btn.pack(side="bottom", pady=15, padx=10, fill="x", anchor="s")

        author = ctk.CTkLabel(
            menu_frame,
            text="Twórca: BOGUCKI 2025",
            wraplength=1400,
            justify="center",
            font=("Segoe UI", 14),
            text_color="#CCCCCC",
        )
        author.pack(side="bottom", pady=5)

    def update_inventory_stats(self, force: bool = False):
        """Refresh labels showing total item count and value in the UI.

        Parameters
        ----------
        force:
            When ``True`` statistics are recomputed even if cached values are
            available.

        Also refreshes the daily additions bar chart if matplotlib is available.
        """
        # Collect widgets that are available and still exist.  The start screen
        # may not yet be created which would leave these attributes undefined.
        widgets = []
        for attr in [
            "inventory_count_label",
            "inventory_sold_count_label",
            "inventory_sold_value_label",
            "mag_inventory_count_label",
            "inventory_value_label",
            "mag_inventory_value_label",
            "mag_sold_count_label",
            "mag_sold_value_label",
        ]:
            widget = getattr(self, attr, None)
            if widget and hasattr(widget, "winfo_exists"):
                try:
                    if widget.winfo_exists():
                        widgets.append((attr, widget))
                except tk.TclError:
                    pass

        # No labels found - nothing to update and avoids attribute errors.
        if not widgets:
            return

        # Prefer stats from Shoper (cached), fallback to CSV
        api_stats = None
        try:
            from .stats_service import get_cached_or_compute
            client = getattr(self, "shoper_client", None)
            if client is None:
                inv = getattr(self, "inventory_service", None) or WarehouseInventoryService.create_default()
                client = getattr(inv, "_client", None)
            api_stats = get_cached_or_compute(client) if client else None
        except Exception:
            api_stats = None
        if api_stats:
            unsold_count = int(api_stats.get("unsold_count", 0))
            unsold_total = float(api_stats.get("unsold_total", 0.0))
            sold_count = int(api_stats.get("sold_count", 0))
            sold_total = float(api_stats.get("sold_total", 0.0))
        else:
            unsold_count, unsold_total, sold_count, sold_total = csv_utils.get_inventory_stats(
                force=force
            )
        if unsold_count == 0 and sold_count == 0:
            messagebox.showinfo("Magazyn", "Brak kart w magazynie")
        unsold_count_text = f"📊 Łączna liczba kart: {unsold_count}"
        unsold_total_text = f"💰 Łączna wartość: {unsold_total:.2f} PLN"
        sold_count_text = f"Sprzedane karty: {sold_count}"
        sold_total_text = f"Wartość sprzedanych: {sold_total:.2f} PLN"
        for attr, widget in widgets:
            if "sold" in attr:
                text = sold_count_text if "count" in attr else sold_total_text
            else:
                text = unsold_count_text if "count" in attr else unsold_total_text
            try:
                widget.configure(text=text)
            except tk.TclError:
                pass

        # Podgląd wykresu został usunięty – aktualizujemy tylko etykiety.

    def placeholder_btn(self, text: str, master=None):
        if master is None:
            master = self.start_frame
        return self.create_button(
            master,
            text=text,
            command=lambda: messagebox.showinfo("Info", "Funkcja niezaimplementowana."),
        )

    def show_location_frame(self):
        """Display inputs for the starting scan location inside the main window."""
        # Hide any other active frames similar to other views
        if self.start_frame is not None:
            self.start_frame.destroy()
            self.start_frame = None
        if getattr(self, "pricing_frame", None):
            self.pricing_frame.destroy()
        if getattr(self, "location_frame", None):
            self.location_frame.destroy()
            self.location_frame = None
            self.pricing_frame = None
        if getattr(self, "shoper_frame", None):
            self.shoper_frame.destroy()
            self.shoper_frame = None
        if getattr(self, "magazyn_frame", None):
            self.magazyn_frame.destroy()
            self.magazyn_frame = None
            labels = getattr(self, "mag_card_image_labels", [])
            for i in range(len(labels)):
                labels[i] = None
        if getattr(self, "frame", None):
            self.frame.destroy()
            self.frame = None
        if getattr(self, "location_frame", None):
            self.location_frame.destroy()

        self.root.minsize(1200, 800)
        frame = ctk.CTkFrame(self.root)
        frame.pack(expand=True, fill="both", padx=10, pady=10)
        frame.grid_anchor("center")
        self.location_frame = frame

        start_row = 0
        logo_path = os.path.join(os.path.dirname(__file__), "banner22.png")
        if os.path.exists(logo_path):
            logo_img = load_rgba_image(logo_path)
            if logo_img:
                logo_img.thumbnail((200, 80))
                self.location_logo_photo = _create_image(logo_img)
                ctk.CTkLabel(
                    frame,
                    image=self.location_logo_photo,
                    text="",
                ).pack(pady=(0, 10))

        # show last used location to inform the user where scanning previously ended
        last_idx = storage.load_last_location()
        try:
            last_code = storage.generate_location(last_idx)
        except Exception:
            last_code = ""
        if last_code:
            ctk.CTkLabel(frame, text=storage.location_from_code(last_code)).pack(
                pady=(0, 10)
            )

        # prefill inputs with the next free location
        try:
            next_code = self.next_free_location()
            match = re.match(r"K(\d+)R(\d+)P(\d+)", next_code)
            if match:
                self.start_box_var.set(str(int(match.group(1))))
                self.start_col_var.set(str(int(match.group(2))))
                self.start_pos_var.set(str(int(match.group(3))))
        except Exception:
            pass

        form = tk.Frame(frame, bg=self.root.cget("background"))
        form.pack(pady=5)
        for idx, label in enumerate(["Karton", "Kolumna", "Pozycja"]):
            ctk.CTkLabel(form, text=label).grid(row=0, column=idx, padx=5, pady=2)
        ctk.CTkEntry(form, textvariable=self.start_box_var, width=120).grid(
            row=1, column=0, padx=5
        )
        ctk.CTkEntry(form, textvariable=self.start_col_var, width=120).grid(
            row=1, column=1, padx=5
        )
        ctk.CTkEntry(form, textvariable=self.start_pos_var, width=120).grid(
            row=1, column=2, padx=5
        )

        folder_frame = tk.Frame(frame, bg=self.root.cget("background"))
        folder_frame.pack(pady=5)
        ctk.CTkLabel(folder_frame, text="Folder").grid(row=0, column=0, padx=5, pady=2)
        ctk.CTkEntry(folder_frame, textvariable=self.scan_folder_var, width=300).grid(
            row=0, column=1, padx=5
        )
        self.create_button(
            folder_frame,
            text="Wybierz",
            command=self.select_scan_folder,
            fg_color=FETCH_BUTTON_COLOR,
        ).grid(row=0, column=2, padx=5)

        button_frame = ctk.CTkFrame(frame)
        button_frame.pack(pady=5)
        self.create_button(
            button_frame,
            text="Dalej",
            command=self.start_browse_scans,
            fg_color=NAV_BUTTON_COLOR,
        ).grid(row=0, column=0, padx=5, pady=5)
        self.create_button(
            button_frame,
            text="Powrót",
            command=self.back_to_welcome,
            fg_color=NAV_BUTTON_COLOR,
        ).grid(row=0, column=1, padx=5, pady=5)

    def select_scan_folder(self):
        """Open a dialog to choose the folder with scans."""
        folder = filedialog.askdirectory()
        if folder:
            self.scan_folder_var.set(folder)

    def create_button(self, master=None, **kwargs):
        if master is None:
            master = self.root
        fg_color = kwargs.pop("fg_color", ACCENT_COLOR)
        width = kwargs.pop("width", 140)
        height = kwargs.pop("height", 60)
        font = kwargs.pop("font", ("Segoe UI", 20, "bold"))
        return ctk.CTkButton(
            master,
            fg_color=fg_color,
            hover_color=HOVER_COLOR,
            corner_radius=10,
            width=width,
            height=height,
            font=font,
            **kwargs,
        )

    def open_shoper_window(self):
        if not self.shoper_client:
            messagebox.showerror("Błąd", "Brak konfiguracji Shoper API")
            return
        # Quick connection test to provide clearer error messages
        try:
            # use a known endpoint to verify the connection
            resp = self.shoper_client.get_inventory()
            if not resp:
                raise RuntimeError("404")
        except (requests.RequestException, RuntimeError) as exc:
            msg = str(exc)
            if "404" in msg:
                messagebox.showerror(
                    "Błąd",
                    "Nie znaleziono endpointu Shoper API ('products'). Czy adres zawiera '/webapi/rest'?",
                )
            else:
                messagebox.showerror(
                    "Błąd", f"Połączenie z Shoper API nie powiodło się: {msg}"
                )
            return
        if self.start_frame is not None:
            self.start_frame.destroy()
            self.start_frame = None
        if getattr(self, "shoper_frame", None):
            self.shoper_frame.destroy()
            self.shoper_frame = None
        if getattr(self, "location_frame", None):
            self.location_frame.destroy()
            self.location_frame = None
        if getattr(self, "statistics_frame", None):
            self.statistics_frame.destroy()
            self.statistics_frame = None
        # Ensure the window has a reasonable minimum size
        self.root.minsize(1200, 800)

        self.shoper_frame = tk.Frame(
            self.root, bg=self.root.cget("background")
        )
        self.shoper_frame.pack(expand=True, fill="both", padx=10, pady=10)
        self.shoper_frame.columnconfigure(0, weight=1)
        self.shoper_frame.rowconfigure(1, weight=1)

        logo_path = os.path.join(os.path.dirname(__file__), "banner22.png")
        if os.path.exists(logo_path):
            logo_img = load_rgba_image(logo_path)
            if logo_img:
                logo_img.thumbnail((200, 80))
                self.shoper_logo_photo = _create_image(logo_img)
                ctk.CTkLabel(
                    self.shoper_frame,
                    image=self.shoper_logo_photo,
                    text="",
                ).grid(row=0, column=0, pady=(0, 10))

        self.shoper_tabs = ctk.CTkTabview(self.shoper_frame)
        self.shoper_tabs.grid(row=1, column=0, sticky="nsew", pady=5)
        self.shoper_tabs.add("Zamówienia")
        orders_tab = self.shoper_tabs.tab("Zamówienia")

        orders_tab.columnconfigure(0, weight=1)
        orders_tab.rowconfigure(1, weight=1)

        ctk.CTkLabel(
            orders_tab,
            text="Lista zamówień",
            text_color=TEXT_COLOR,
            font=ctk.CTkFont(size=18, weight="bold"),
            anchor="w",
            justify="left",
        ).grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))

        orders_output = OrdersListView(orders_tab)
        orders_output.grid(row=1, column=0, sticky="nsew", padx=10, pady=(10, 5))
        self.orders_output = orders_output
        if hasattr(orders_output, "set_order_handler"):
            orders_output.set_order_handler(self.show_order_details)
        # Trigger an initial refresh so the list is populated immediately using
        # the same code path (and error handling) as the manual refresh button.
        if hasattr(self.root, "after_idle"):
            self.root.after_idle(lambda: self.show_orders(self.orders_output))
        else:
            self.show_orders(self.orders_output)

        buttons_frame = ctk.CTkFrame(orders_tab, fg_color=BG_COLOR, corner_radius=12)
        buttons_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(5, 10))
        buttons_frame.grid_columnconfigure((0, 1), weight=1, uniform="orders_buttons")

        self.create_button(
            buttons_frame,
            text="Odśwież zamówienia",
            command=self.show_orders,
            fg_color=FETCH_BUTTON_COLOR,
            width=220,
            height=55,
        ).grid(row=0, column=0, padx=10, pady=12, sticky="ew")

        self.create_button(
            buttons_frame,
            text="Potwierdź zamówienie",
            command=self.confirm_order,
            fg_color=SAVE_BUTTON_COLOR,
            width=220,
            height=55,
        ).grid(row=0, column=1, padx=10, pady=12, sticky="ew")

        self.create_button(
            self.shoper_frame,
            text="Powrót",
            command=self.back_to_welcome,
            fg_color=NAV_BUTTON_COLOR,
        ).grid(row=2, column=0, pady=5)

    def push_product(self, widget):
        """Send the currently selected card to Shoper."""
        try:
            card = None
            if getattr(self, "output_data", None):
                try:
                    self.save_current_data()
                except Exception as exc:
                    logger.exception("Failed to save current data")
                if 0 <= getattr(self, "index", 0) < len(self.output_data):
                    card = self.output_data[self.index]
                else:
                    card = next((r for r in self.output_data if r), None)
            if not card:
                messagebox.showerror("Błąd", "Brak danych karty do wysłania")
                return

            data = self._send_card_to_shoper(card)
            if isinstance(widget, tk.Text):
                widget.delete("1.0", tk.END)
                widget.insert(tk.END, json.dumps(data, indent=2, ensure_ascii=False))
            else:
                messagebox.showinfo(
                    "Wysłano",
                    json.dumps(data, indent=2, ensure_ascii=False),
                )
        except requests.RequestException as e:
            logger.exception("Failed to push product")
            messagebox.showerror("Błąd", str(e))

    def _send_card_to_shoper(self, card: Mapping[str, Any] | dict[str, Any]) -> dict:
        """Send ``card`` to the Shoper API and assign related attributes."""

        payload = self._build_shoper_payload(card)

        product_code: str = ""
        if isinstance(card, Mapping):
            raw_code = card.get("product_code")
            if isinstance(raw_code, str):
                product_code = raw_code.strip()
            elif raw_code is not None:
                product_code = str(raw_code).strip()
        if not product_code:
            raw_code = payload.get("product_code")
            if isinstance(raw_code, str):
                product_code = raw_code.strip()
            elif raw_code is not None:
                product_code = str(raw_code).strip()

        existing_product: Mapping[str, Any] | None = None
        if product_code:
            existing_product = self._get_store_product(product_code)

        existing_product_id: str | None = None
        if isinstance(existing_product, Mapping):
            for key in ("product_id", "id"):
                raw_id = existing_product.get(key)
                if raw_id in (None, ""):
                    continue
                text_id = str(raw_id).strip()
                if text_id:
                    existing_product_id = text_id
                    break

        if existing_product_id:
            if logger.isEnabledFor(logging.DEBUG):
                try:
                    payload_dump = json.dumps(payload, ensure_ascii=False, default=str)
                except TypeError:
                    payload_dump = str(payload)
                logger.debug(
                    "Updating Shoper product %s with payload: %s",
                    existing_product_id,
                    payload_dump,
                )
            response = self.shoper_client.update_product(existing_product_id, payload)
            if isinstance(response, Mapping):
                data = dict(response)
            else:
                data = {}
            data.setdefault("product_id", existing_product_id)
            data.setdefault("id", existing_product_id)
        else:
            if logger.isEnabledFor(logging.DEBUG):
                try:
                    payload_dump = json.dumps(payload, ensure_ascii=False, default=str)
                except TypeError:
                    payload_dump = str(payload)
                logger.debug(
                    "Creating Shoper product with payload: %s",
                    payload_dump,
                )
            data = self.shoper_client.add_product(payload)

        product_id = data.get("product_id") or data.get("id")
        # Best-effort: upload product image after create/update
        # Skip uploading images when URLs are already hosted in the store
        # Only allow explicit upload when SHOPER_FORCE_IMAGE_UPLOAD is truthy
        try:
            force_upload = str(os.getenv("SHOPER_FORCE_IMAGE_UPLOAD", "")).strip().lower() in {"1", "true", "yes", "on"}
            pid_text = str(product_id).strip() if product_id is not None else ""
            if pid_text and force_upload:
                image_value = None
                try:
                    image_value = card.get("image1") if isinstance(card, Mapping) else None
                except Exception:
                    image_value = None
                def _first_image(value) -> str | None:
                    if isinstance(value, str) and value.strip():
                        return value.strip()
                    if isinstance(value, (list, tuple, set)):
                        for item in value:
                            if isinstance(item, str) and item.strip():
                                return item.strip()
                    return None
                first_img = _first_image(image_value)
                if first_img and os.path.exists(first_img):
                    try:
                        self.shoper_client.upload_product_image(pid_text, first_img, is_main=True)
                    except Exception:
                        pass
        except Exception:
            pass
        try:
            attribute_map = card.get("attributes") if isinstance(card, Mapping) else {}
            cache: Mapping[str, Any] | dict[str, Any]
            try:
                cache = self._refresh_attribute_cache()
            except Exception as exc:  # pragma: no cover - defensive fallback
                logger.warning("Failed to refresh attribute cache: %s", exc)
                cache = getattr(self, "_attribute_cache", {}) or {}
            attr_defs = cache.get("attributes") if isinstance(cache, Mapping) else {}
            name_map = cache.get("by_name") if isinstance(cache, Mapping) else {}

            def _sort_key(item: tuple[Any, Any]) -> Any:
                key = item[0]
                try:
                    return int(key)
                except (TypeError, ValueError):
                    return str(key)

            seen_attribute_ids: set[int] = set()
            strict_attr = str(os.getenv("SHOPER_STRICT_ATTRIBUTES", "")).strip().lower() in {"1", "true", "yes", "on"}
            unresolved: list[str] = []
            if product_id and isinstance(attribute_map, Mapping):
                for _, attributes in sorted(attribute_map.items(), key=_sort_key):
                    if not isinstance(attributes, Mapping):
                        continue
                    for attr_key, raw_value in sorted(attributes.items(), key=_sort_key):
                        attr_id = self._resolve_attribute_id(attr_key, name_map)
                        if attr_id is None:
                            unresolved.append(f"{attr_key}: unknown attribute")
                            if strict_attr:
                                continue
                            else:
                                continue
                        attr_meta = (
                            attr_defs.get(attr_id) if isinstance(attr_defs, Mapping) else None
                        )
                        if not attr_meta:
                            logger.warning(
                                "Missing Shoper attribute definition for %s", attr_id
                            )
                            unresolved.append(f"{attr_key}: missing definition")
                            if strict_attr:
                                continue
                            else:
                                continue
                        values_payload = self._normalize_attribute_payload(
                            attr_meta, raw_value
                        )
                        if not values_payload:
                            unresolved.append(f"{attr_key}: no matching values")
                            if strict_attr:
                                continue
                            else:
                                continue
                        try:
                            logger.info(
                                "Assigning attribute %s values %s to product %s",
                                attr_id,
                                values_payload,
                                product_id,
                            )
                            self.shoper_client.add_product_attribute(
                                product_id, attr_id, values_payload
                            )
                            seen_attribute_ids.add(attr_id)
                        except Exception:
                            logger.exception(
                                "Failed to assign attribute %s to product %s",
                                attr_id,
                                product_id,
                            )
                if strict_attr and unresolved:
                    raise RuntimeError("Niepoprawne atrybuty (tryb ścisły): " + ", ".join(unresolved))

            card_type_code = normalize_card_type_code(
                card.get("card_type") if isinstance(card, Mapping) else None
            )
            attr_value = card_type_label(card_type_code)
            if product_id and attr_value:
                attr_id = self._resolve_attribute_id("Typ", name_map)
                if attr_id is not None and attr_id not in seen_attribute_ids:
                    attr_meta = (
                        attr_defs.get(attr_id)
                        if isinstance(attr_defs, Mapping)
                        else None
                    )
                    values_payload = self._normalize_attribute_payload(attr_meta, attr_value)
                    if values_payload:
                        try:
                            self.shoper_client.add_product_attribute(
                                product_id, attr_id, values_payload
                            )
                        except Exception:
                            logger.exception(
                                "Failed to set fallback attribute Typ for product %s",
                                product_id,
                            )
        except Exception:
            logger.exception("Failed to set product attributes")

        self._update_local_product_caches(card, payload)
        return data

    def _update_local_product_caches(
        self, card: Mapping[str, Any] | dict[str, Any], payload: Mapping[str, Any]
    ) -> None:
        """Keep local duplicate-detection caches in sync after an API import."""

        product_code: str = ""
        if isinstance(card, Mapping):
            raw_code = card.get("product_code")
            if isinstance(raw_code, str):
                product_code = raw_code.strip()
            elif raw_code is not None:
                product_code = str(raw_code).strip()
        if not product_code:
            raw_code = payload.get("product_code")
            if isinstance(raw_code, str):
                product_code = raw_code.strip()
            elif raw_code is not None:
                product_code = str(raw_code).strip()
        if not product_code:
            return

        try:
            card_snapshot: dict[str, Any]
            if isinstance(card, Mapping):
                card_snapshot = dict(card)
            else:
                card_snapshot = {"product_code": product_code}
        except Exception:
            card_snapshot = {"product_code": product_code}

        if isinstance(getattr(self, "product_code_map", None), dict):
            self.product_code_map[product_code] = card_snapshot
        else:  # pragma: no cover - fallback for unexpected state
            self.product_code_map = {product_code: card_snapshot}

        existing_row = self._get_store_product(product_code)
        row: dict[str, Any] = {}
        if isinstance(existing_row, Mapping):
            row.update(existing_row)
        row["product_code"] = product_code

        def _set_field(target_key: str, *source_keys: str) -> None:
            if row.get(target_key):
                return
            value: Any = None
            if isinstance(card, Mapping):
                for key in source_keys:
                    value = card.get(key)
                    if value not in (None, ""):
                        break
                    value = None
            if value in (None, ""):
                for key in source_keys:
                    value = payload.get(key)
                    if value not in (None, ""):
                        break
                    value = None
            if value in (None, ""):
                return
            row[target_key] = str(value)

        _set_field("name", "nazwa", "name")
        _set_field("price", "cena", "price")
        _set_field("set", "set")
        _set_field("number", "numer", "number")
        _set_field("variant", "variant")

        self._cache_store_product(product_code, row, persist=True)

    def _get_product_client(self) -> ShoperClient | None:
        client = getattr(self, "shoper_client", None)
        if client is not None:
            return client
        return self._create_shoper_client_for_cache()

    def _create_shoper_client_for_cache(self) -> ShoperClient | None:
        url = os.getenv("SHOPER_API_URL", "").strip()
        token = os.getenv("SHOPER_API_TOKEN", "").strip()
        client_id = os.getenv("SHOPER_CLIENT_ID", "").strip()
        if not url or not token:
            return None
        try:
            return ShoperClient(url, token, client_id or None)
        except Exception as exc:
            logger.warning("Failed to initialize ShoperClient for cache: %s", exc)
            return None

    def _fetch_inventory_page(
        self, client: ShoperClient, page: int, per_page: int
    ) -> Mapping[str, Any] | None:
        try:
            response = client.get_inventory(page=page, per_page=per_page)
            if response:
                return response
        except Exception as exc:
            logger.warning("Shoper get_inventory page %s failed: %s", page, exc)
        try:
            return client.search_products(page=page, per_page=per_page)
        except Exception as exc:
            logger.warning("Shoper search_products page %s failed: %s", page, exc)
            return None

    def _load_store_products_from_api(self) -> dict[str, dict[str, str]]:
        client = self._get_product_client()
        if client is None:
            return {}

        products: dict[str, dict[str, str]] = {}
        page = 1
        per_page = 100
        max_pages = 50

        while page <= max_pages:
            response = self._fetch_inventory_page(client, page, per_page)
            if not response:
                break

            new_items = 0
            for product in csv_utils.iter_api_products(response):
                normalised = csv_utils.normalise_api_product(product)
                if not normalised:
                    continue
                code, row = normalised
                products[code] = row
                new_items += 1

            current, total = csv_utils.api_pagination(response)
            if total is not None and current is not None and current >= total:
                break
            if new_items < per_page:
                break
            page = (current + 1) if current is not None else (page + 1)

        return products

    def _ensure_store_cache(self) -> None:
        store_data = getattr(self, "store_data", None)
        if isinstance(store_data, dict) and store_data:
            return

        fetched = self._load_store_products_from_api()
        if not fetched:
            return

        if not isinstance(store_data, dict):
            self.store_data = {}
            store_data = self.store_data

        store_data.update(fetched)
        self._persist_store_cache()

    def _fetch_product_from_api(self, product_code: str) -> dict[str, str] | None:
        client = self._get_product_client()
        if client is None:
            return None

        try:
            response = client.search_products(
                filters={"code": product_code}, page=1, per_page=1
            )
        except Exception as exc:
            logger.warning(
                "Failed to query Shoper for product %s: %s", product_code, exc
            )
            return None

        for product in csv_utils.iter_api_products(response):
            normalised = csv_utils.normalise_api_product(product)
            if not normalised:
                continue
            code, row = normalised
            if code.strip() == product_code:
                return row
        return None

    def _cache_store_product(
        self,
        product_code: str,
        row: Mapping[str, Any] | None,
        *,
        persist: bool,
    ) -> dict[str, str]:
        if not isinstance(self.store_data, dict):
            self.store_data = {}
        normalised = csv_utils.normalize_store_cache_row(
            product_code, row if isinstance(row, Mapping) else None
        )
        self.store_data[normalised.get("product_code", product_code)] = normalised
        if persist:
            self._persist_store_cache()
        return normalised

    def _persist_store_cache(self) -> None:
        store_data = getattr(self, "store_data", None)
        if not isinstance(store_data, dict):
            return
        try:
            csv_utils.save_store_cache(store_data.values())
        except Exception:
            logger.exception("Failed to persist store cache")

    def _get_store_product(self, product_code: str) -> Mapping[str, Any] | None:
        code = str(product_code or "").strip()
        if not code:
            return None

        store_data = getattr(self, "store_data", None)
        if not isinstance(store_data, dict):
            self.store_data = {}
            store_data = self.store_data

        row = store_data.get(code)
        if isinstance(row, Mapping):
            return row

        fetched = self._fetch_product_from_api(code)
        if fetched:
            return self._cache_store_product(code, fetched, persist=True)
        return None

    def _find_existing_products(
        self,
        *,
        product_code: str,
        name: str,
        number: str,
        set_name: str,
        variant_code: str | None = None,
    ) -> list[Mapping[str, Any]]:
        sanitized_code = str(product_code or "").strip()
        normalized_name = normalize(name) if name else ""
        normalized_set = normalize(set_name) if set_name else ""
        normalized_number = sanitize_number(str(number or ""))
        matches: dict[str, Mapping[str, Any]] = {}
        _ = variant_code  # kept for signature compatibility

        def _coerce_row(row: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
            if not isinstance(row, Mapping):
                return None
            if isinstance(row, dict):
                return row
            try:
                return dict(row)
            except Exception:
                return None

        def _append_candidate(row: Mapping[str, Any] | None) -> None:
            candidate = _coerce_row(row)
            if not candidate:
                return
            code_value = str(
                candidate.get("product_code")
                or candidate.get("code")
                or candidate.get("producer_code")
                or ""
            ).strip()
            if not code_value:
                return

            candidate_name = normalize(str(candidate.get("name") or candidate.get("nazwa") or ""))
            candidate_number = sanitize_number(
                str(
                    candidate.get("producer_code")
                    or candidate.get("number")
                    or candidate.get("numer")
                    or ""
                )
            )
            candidate_set = normalize(str(candidate.get("set") or candidate.get("set_name") or ""))
            if sanitized_code and code_value != sanitized_code:
                if normalized_number and candidate_number and candidate_number != normalized_number:
                    return
                if normalized_name and candidate_name and candidate_name != normalized_name:
                    return
                if normalized_set and candidate_set and candidate_set != normalized_set:
                    return

            if code_value not in matches:
                matches[code_value] = candidate

        if sanitized_code:
            cached = self._get_store_product(sanitized_code)
            if cached:
                _append_candidate(cached)

        product_map = getattr(self, "product_code_map", {})
        if isinstance(product_map, Mapping) and sanitized_code:
            existing = product_map.get(sanitized_code)
            if isinstance(existing, Mapping):
                _append_candidate(existing)

        store_cache = getattr(self, "store_data", {})
        if isinstance(store_cache, Mapping):
            for row in store_cache.values():
                _append_candidate(row)

        client = self._get_product_client()
        if client is not None:
            queries: list[dict[str, str]] = []
            if sanitized_code:
                queries.append({"filters[code]": sanitized_code})
            if normalized_number:
                queries.append({"filters[producer_code]": normalized_number})
            phrase_parts = [part for part in (name, number, set_name) if part]
            if phrase_parts:
                queries.append({"filters[search]": " ".join(phrase_parts)})

            for params in queries:
                try:
                    response = client.search_products(filters=params, page=1, per_page=20)
                except Exception as exc:
                    logger.warning("Shoper duplicate lookup failed: %s", exc)
                    continue

                for product in csv_utils.iter_api_products(response):
                    normalised = csv_utils.normalise_api_product(product)
                    if not normalised:
                        continue
                    code_value, row = normalised
                    cached = self._cache_store_product(code_value, row, persist=False)
                    _append_candidate(cached)

        try:
            csv_matches = csv_utils.find_duplicates(
                name, number, set_name, variant_code
            )
        except Exception:
            csv_matches = []
        for row in csv_matches:
            _append_candidate(row)

        return list(matches.values())

    def open_auctions_window(self):
        """Open a queue editor for Discord auctions and save to ``aukcje.csv``."""
        if self.start_frame is not None:
            self.start_frame.destroy()
            self.start_frame = None
        if getattr(self, "pricing_frame", None):
            self.pricing_frame.destroy()
            self.pricing_frame = None
        if getattr(self, "shoper_frame", None):
            self.shoper_frame.destroy()
            self.shoper_frame = None
        if getattr(self, "frame", None):
            self.frame.destroy()
            self.frame = None
        if getattr(self, "magazyn_frame", None):
            self.magazyn_frame.destroy()
            self.magazyn_frame = None
            labels = getattr(self, "mag_card_image_labels", [])
            for i in range(len(labels)):
                labels[i] = None
        if getattr(self, "location_frame", None):
            self.location_frame.destroy()
            self.location_frame = None
        if getattr(self, "auction_frame", None):
            self.auction_frame.destroy()
        if getattr(self, "auction_run_window", None):
            try:
                self.auction_run_window.close()
            except Exception:
                pass
            finally:
                self.auction_run_window = None
        if getattr(self, "statistics_frame", None):
            self.statistics_frame.destroy()
            self.statistics_frame = None
        try:
            import bot
            self.bot = bot
            if not getattr(bot, "_thread_started", False):
                threading.Thread(target=bot.run_bot, daemon=True).start()
                bot._thread_started = True
        except Exception as e:
            logger.exception("Failed to start bot")
            messagebox.showerror("Błąd", str(e))

        self.root.minsize(1200, 800)
        self.auction_frame = tk.Frame(
            self.root, bg=self.root.cget("background")
        )
        self.auction_frame.pack(expand=True, fill="both", padx=10, pady=10)

        container = tk.Frame(
            self.auction_frame, bg=self.root.cget("background")
        )
        container.pack(expand=True, fill="both")

        refresh_tree = self._build_auction_widgets(container)
        try:
            self._load_auction_queue()
        except FileNotFoundError:
            messagebox.showerror(
                "Błąd", f"Nie znaleziono pliku {csv_utils.WAREHOUSE_CSV}"
            )
            self.auction_queue = []
        except ValueError as exc:
            messagebox.showerror("Błąd", str(exc))
            self.auction_queue = []
        except (OSError, csv.Error, UnicodeDecodeError) as exc:
            logger.exception("Failed to load auction queue")
            messagebox.showerror("Błąd", str(exc))
            self.auction_queue = []

        refresh_tree()
        self._update_auction_status()

    def open_statistics_window(self):
        """Display inventory statistics inside the main window."""
        if self.start_frame is not None:
            self.start_frame.destroy()
            self.start_frame = None
        for attr in (
            "pricing_frame",
            "shoper_frame",
            "frame",
            "magazyn_frame",
            "location_frame",
            "auction_frame",
            "statistics_frame",
        ):
            if getattr(self, attr, None):
                getattr(self, attr).destroy()
                setattr(self, attr, None)

        start_var = tk.StringVar(
            value=(datetime.date.today() - datetime.timedelta(days=6)).isoformat()
        )
        end_var = tk.StringVar(value=datetime.date.today().isoformat())

        self.root.minsize(1200, 800)
        self.statistics_frame = tk.Frame(
            self.root, bg=self.root.cget("background")
        )
        self.statistics_frame.pack(expand=True, fill="both", padx=10, pady=10)

        filter_frame = ctk.CTkFrame(self.statistics_frame, fg_color=BG_COLOR)
        filter_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(filter_frame, text="Od:", text_color=TEXT_COLOR).pack(
            side="left", padx=5
        )
        ctk.CTkEntry(filter_frame, textvariable=start_var, width=100).pack(
            side="left"
        )
        ctk.CTkLabel(filter_frame, text="Do:", text_color=TEXT_COLOR).pack(
            side="left", padx=5
        )
        ctk.CTkEntry(filter_frame, textvariable=end_var, width=100).pack(
            side="left"
        )

        summary_frame = ctk.CTkFrame(self.statistics_frame, fg_color=BG_COLOR)
        summary_frame.pack(fill="x", pady=5)
        self.stats_total_label = ctk.CTkLabel(
            summary_frame,
            text="",
            text_color=TEXT_COLOR,
            font=("Segoe UI", 20, "bold"),
        )
        self.stats_total_label.pack(anchor="w")
        self.stats_count_label = ctk.CTkLabel(
            summary_frame,
            text="",
            text_color=TEXT_COLOR,
            font=("Segoe UI", 20, "bold"),
        )
        self.stats_count_label.pack(anchor="w")
        self.stats_max_sale_label = ctk.CTkLabel(
            summary_frame,
            text="",
            text_color=TEXT_COLOR,
            font=("Segoe UI", 20, "bold"),
        )
        self.stats_max_sale_label.pack(anchor="w")
        self.stats_max_order_label = ctk.CTkLabel(
            summary_frame,
            text="",
            text_color=TEXT_COLOR,
            font=("Segoe UI", 20, "bold"),
        )
        self.stats_max_order_label.pack(anchor="w")
        self.stats_sold_total_label = ctk.CTkLabel(
            summary_frame,
            text="",
            text_color=TEXT_COLOR,
            font=("Segoe UI", 20, "bold"),
        )
        self.stats_sold_total_label.pack(anchor="w")

        # Additional metrics
        self.stats_avg_price_label = ctk.CTkLabel(
            summary_frame,
            text="",
            text_color=TEXT_COLOR,
            font=("Segoe UI", 20, "bold"),
        )
        self.stats_avg_price_label.pack(anchor="w")
        self.stats_sold_ratio_label = ctk.CTkLabel(
            summary_frame,
            text="",
            text_color=TEXT_COLOR,
            font=("Segoe UI", 20, "bold"),
        )
        self.stats_sold_ratio_label.pack(anchor="w")
        self.stats_unsold_ratio_label = ctk.CTkLabel(
            summary_frame,
            text="",
            text_color=TEXT_COLOR,
            font=("Segoe UI", 20, "bold"),
        )
        self.stats_unsold_ratio_label.pack(anchor="w")

        # Top lists containers
        lists_frame = ctk.CTkFrame(self.statistics_frame, fg_color=BG_COLOR)
        lists_frame.pack(fill="both", expand=False, pady=(5, 10))
        lists_frame.grid_columnconfigure((0,1), weight=1)
        lists_frame.grid_rowconfigure((0,1), weight=1)
        self.top_sets_frame = ctk.CTkFrame(lists_frame, fg_color=LIGHT_BG_COLOR)
        self.top_sets_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.top_boxes_frame = ctk.CTkFrame(lists_frame, fg_color=LIGHT_BG_COLOR)
        self.top_boxes_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        self.top_values_frame = ctk.CTkFrame(lists_frame, fg_color=LIGHT_BG_COLOR)
        self.top_values_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.top_boxes_value_frame = ctk.CTkFrame(lists_frame, fg_color=LIGHT_BG_COLOR)
        self.top_boxes_value_frame.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)

        chart_frame = tk.Frame(self.statistics_frame, bg=self.root.cget("background"))
        chart_frame.pack(expand=True, fill="both", pady=5)

        def _update():
            try:
                start = datetime.date.fromisoformat(start_var.get())
                end = datetime.date.fromisoformat(end_var.get())
            except ValueError:
                messagebox.showerror("Błąd", "Niepoprawny format daty (RRRR-MM-DD)")
                return
            data = stats_utils.get_statistics(start, end)
            cumulative = data.get("cumulative", {})
            count = cumulative.get("count", 0)
            total_value = cumulative.get("total_value", 0.0)
            daily = data.get("daily", {})
            max_order = data.get("max_order", 0)
            max_price = data.get("max_price", 0.0)
            avg_price = float(data.get("average_price", 0.0))
            sold_ratio = float(data.get("sold_ratio", 0.0))
            unsold_ratio = float(data.get("unsold_ratio", 0.0))

            # Compute sold count/total from Shoper orders within range
            sold_count_api, sold_total_api = self._compute_shoper_sales(start, end)

            self.stats_total_label.configure(
                text=f"Wartość kolekcji: {total_value:.2f} zł"
            )
            self.stats_count_label.configure(text=f"Liczba kart: {count}")
            self.stats_max_sale_label.configure(
                text=f"Najdroższa sprzedaż: {max_price:.2f} zł"
            )
            self.stats_max_order_label.configure(
                text=f"Największe zamówienie: {max_order}"
            )
            self.stats_sold_total_label.configure(
                text=f"Wartość sprzedanych (wg Shoper): {sold_total_api:.2f} zł ({sold_count_api} szt.)"
            )
            self.stats_avg_price_label.configure(
                text=f"Średnia cena: {avg_price:.2f} zł"
            )
            self.stats_sold_ratio_label.configure(
                text=f"Udział sprzedanych: {sold_ratio*100:.1f}%"
            )
            self.stats_unsold_ratio_label.configure(
                text=f"Udział niesprzedanych: {unsold_ratio*100:.1f}%"
            )

            # Render top lists
            def render_pairs(frame, title, pairs):
                for w in getattr(frame, "winfo_children", lambda: [])():
                    try:
                        w.destroy()
                    except Exception:
                        pass
                ctk.CTkLabel(frame, text=title, text_color=TEXT_COLOR, font=("Segoe UI", 18, "bold")).pack(anchor="w", padx=8, pady=(6, 2))
                if not pairs:
                    ctk.CTkLabel(frame, text="Brak danych", text_color=TEXT_COLOR).pack(anchor="w", padx=8, pady=(0, 6))
                    return
                for name, val in pairs:
                    ctk.CTkLabel(frame, text=f"• {name}: {val}", text_color=TEXT_COLOR).pack(anchor="w", padx=12)

            render_pairs(self.top_sets_frame, "Top sety (ilość)", data.get("top_sets_by_count", []))
            render_pairs(self.top_boxes_frame, "Top kartony (ilość)", data.get("top_boxes_by_count", []))
            render_pairs(self.top_values_frame, "Top sety (wartość)", data.get("top_sets_by_value", []))
            render_pairs(self.top_boxes_value_frame, "Top kartony (wartość)", data.get("top_boxes_by_value", []))

            if Figure and FigureCanvasTkAgg and daily:
                dates = list(daily.keys())
                added_vals = [v.get("added", 0) for v in daily.values()]
                sold_vals = [v.get("sold", 0) for v in daily.values()]
                fig = Figure(figsize=(8, 4), facecolor=BG_COLOR)
                ax1 = fig.add_subplot(121)
                ax1.set_facecolor(BG_COLOR)
                ax1.bar(range(len(dates)), added_vals, color="#4a90e2")
                ax1.set_title("Dodane", color="#BBBBBB")
                ax1.set_xticks(range(len(dates)))
                ax1.set_xticklabels(
                    dates, rotation=45, ha="right", color="#BBBBBB", fontsize=8
                )
                ax1.tick_params(axis="y", colors="#BBBBBB")
                for spine in ax1.spines.values():
                    spine.set_color("#BBBBBB")
                ax2 = fig.add_subplot(122)
                ax2.set_facecolor(BG_COLOR)
                ax2.bar(range(len(dates)), sold_vals, color="#e74c3c")
                ax2.set_title("Sprzedane", color="#BBBBBB")
                ax2.set_xticks(range(len(dates)))
                ax2.set_xticklabels(
                    dates, rotation=45, ha="right", color="#BBBBBB", fontsize=8
                )
                ax2.tick_params(axis="y", colors="#BBBBBB")
                for spine in ax2.spines.values():
                    spine.set_color("#BBBBBB")
                fig.tight_layout()
                if getattr(self, "statistics_chart", None):
                    self.statistics_chart.get_tk_widget().destroy()
                canvas = FigureCanvasTkAgg(fig, master=chart_frame)
                canvas.draw()
                canvas.get_tk_widget().pack(expand=True, fill="both")
                self.statistics_chart = canvas
            elif getattr(self, "statistics_chart", None):
                self.statistics_chart.get_tk_widget().destroy()
                self.statistics_chart = None

        ctk.CTkButton(
            filter_frame,
            text="Odśwież",
            command=_update,
            fg_color=FETCH_BUTTON_COLOR,
        ).pack(side="left", padx=5)
        def _export():
            try:
                start = datetime.date.fromisoformat(start_var.get())
                end = datetime.date.fromisoformat(end_var.get())
            except ValueError:
                messagebox.showerror("Błąd", "Niepoprawny format daty (RRRR-MM-DD)")
                return
            data = stats_utils.get_statistics(start, end)
            path = filedialog.asksaveasfilename(
                title="Zapisz statystyki",
                defaultextension=".csv",
                filetypes=[("CSV", "*.csv")],
                initialfile=f"statystyki_{start}_{end}.csv",
            )
            if path:
                try:
                    stats_utils.export_statistics_csv(data, path)
                    self.set_status(f"Zapisano: {os.path.basename(path)}", temporary=True)
                except Exception as exc:
                    logger.exception("Failed to export statistics CSV")
                    messagebox.showerror("Błąd", str(exc))

        ctk.CTkButton(
            filter_frame,
            text="Eksport CSV",
            command=_export,
            fg_color="#4a4a4a",
        ).pack(side="left", padx=5)
        self.create_button(
            self.statistics_frame,
            text="Powrót",
            command=self.back_to_welcome,
            fg_color=NAV_BUTTON_COLOR,
        ).pack(pady=5)
        _update()

    def _build_auction_widgets(self, container):
        """Create auction editor widgets and return a refresh callback."""
        left_panel = tk.Frame(container, bg=self.root.cget("background"))
        left_panel.pack(side="right", fill="y", padx=10, pady=10)

        self.auction_image_label = ctk.CTkLabel(left_panel, text="")
        self.auction_image_label.pack(pady=5)
        self.auction_photo = None

        self.selected_card_name_var = tk.StringVar(value="")
        tk.Label(
            left_panel,
            textvariable=self.selected_card_name_var,
            bg=self.root.cget("background"),
            fg="white",
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor="w", pady=(0, 2))

        self.selected_card_price_var = tk.StringVar(value="Aktualna cena: -")
        tk.Label(
            left_panel,
            textvariable=self.selected_card_price_var,
            bg=self.root.cget("background"),
            fg="white",
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor="w", pady=(0, 8))

        form = tk.Frame(left_panel, bg=self.root.cget("background"))
        form.pack(pady=5, anchor="w")

        labels = ["Cena start", "Kwota przebicia", "Czas [s]"]
        vars = []
        for lbl in labels:
            tk.Label(form, text=lbl, bg=self.root.cget("background"), fg="white").pack(anchor="w")
            var = tk.StringVar()
            ctk.CTkEntry(form, textvariable=var, width=100).pack(anchor="w", pady=2)
            vars.append(var)

        self.current_price_var = tk.StringVar()

        win = tk.Frame(container, bg=self.root.cget("background"))
        win.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        style = ttk.Style(win)
        style.configure(
            "Auction.Treeview",
            background=BG_COLOR,
            fieldbackground=BG_COLOR,
            foreground=TEXT_COLOR,
            font=("Segoe UI", 14),
        )
        style.map("Auction.Treeview", background=[("selected", HOVER_COLOR)])
        style.configure(
            "Auction.Treeview.Heading",
            background=NAV_BUTTON_COLOR,
            foreground=TEXT_COLOR,
            font=("Segoe UI", 14, "bold"),
        )
        style.map(
            "Auction.Treeview.Heading",
            background=[("active", HOVER_COLOR), ("pressed", HOVER_COLOR)],
            foreground=[("active", TEXT_COLOR), ("pressed", TEXT_COLOR)],
        )

        def sort_tree(tree, col, reverse):
            sort_flags = getattr(tree, "_sort_reverse", {})
            actual_reverse = sort_flags.get(col, reverse)

            def parse_value(value):
                if value is None:
                    return (1, "")
                if isinstance(value, str):
                    stripped = value.strip()
                else:
                    stripped = value
                if isinstance(stripped, str):
                    try:
                        number = float(stripped.replace(",", "."))
                    except ValueError:
                        return (1, stripped.lower())
                    else:
                        return (0, number)
                return (0, stripped)

            items = list(tree.get_children(""))
            items.sort(key=lambda item: parse_value(tree.set(item, col)), reverse=actual_reverse)
            for index, item in enumerate(items):
                tree.move(item, "", index)

            sort_flags[col] = not actual_reverse
            setattr(tree, "_sort_reverse", sort_flags)

        tree = ttk.Treeview(
            win,
            columns=("name", "price", "warehouse_code"),
            show="headings",
            height=15,
            style="Auction.Treeview",
        )
        tree._sort_reverse = {}
        for col, txt, width in [
            ("name", "Karta", 200),
            ("price", "Cena", 80),
            ("warehouse_code", "Kod magazynu", 120),
        ]:
            if col in {"name", "price"}:
                tree.heading(col, text=txt, command=lambda c=col: sort_tree(tree, c, False))
            else:
                tree.heading(col, text=txt)
            tree.column(col, width=width, stretch=True)
        tree.pack(padx=5, pady=5, fill="both", expand=True)

        self.info_var = tk.StringVar()
        tk.Label(
            win,
            textvariable=self.info_var,
            bg=self.root.cget("background"),
            fg="white",
            font=("Segoe UI", 16, "bold"),
        ).pack(pady=2)

        status_frame = tk.Frame(win, bg=self.root.cget("background"))
        status_frame.pack(pady=2)

        tk.Label(
            status_frame,
            text="Aktualna cena:",
            bg=self.root.cget("background"),
            fg=CURRENT_PRICE_COLOR,
        ).grid(row=0, column=0, padx=2, sticky="e")
        tk.Label(
            status_frame,
            textvariable=self.current_price_var,
            bg=self.root.cget("background"),
            fg=CURRENT_PRICE_COLOR,
            font=("Segoe UI", 16, "bold"),
        ).grid(row=0, column=1, padx=2, sticky="w")

        def refresh_tree(select_index: Optional[int] = None):
            try:
                current_selection = tree.selection()
            except tk.TclError:
                current_selection = ()
            current_index: Optional[int] = None
            if current_selection:
                try:
                    current_index = tree.index(current_selection[0])
                except tk.TclError:
                    current_index = None
            if select_index is not None:
                current_index = select_index
            for r in tree.get_children():
                tree.delete(r)
            for row in self.auction_queue:
                tree.insert(
                    "",
                    "end",
                    values=(
                        row.get("name") or row.get("nazwa_karty"),
                        row.get("price") or row.get("cena_początkowa"),
                        row.get("warehouse_code", ""),
                    ),
                )
            if self.auction_queue:
                nxt = self.auction_queue[0]
                nazwa = nxt.get('name') or nxt.get('nazwa_karty')
                numer = nxt.get('numer_karty')
                if numer:
                    self.info_var.set(f"Następna karta: {nazwa} ({numer})")
                else:
                    self.info_var.set(f"Następna karta: {nazwa}")
            else:
                self.info_var.set("Brak kart w kolejce")
                name_var = getattr(self, "selected_card_name_var", None)
                if name_var is not None:
                    name_var.set("")
                price_var = getattr(self, "selected_card_price_var", None)
                if price_var is not None:
                    price_var.set("Aktualna cena: -")
            items = tree.get_children()
            target_index: Optional[int] = current_index
            if not items:
                try:
                    tree.selection_remove(tree.selection())
                except tk.TclError:
                    pass
                target_index = None
            else:
                if target_index is None or not (0 <= target_index < len(items)):
                    target_index = 0
                try:
                    tree.selection_set(items[target_index])
                    tree.focus(items[target_index])
                except tk.TclError:
                    pass
            show_selected()
            self.refresh_auction_preview(select_index=target_index)

        def load_image(path: Optional[str]):
            if not path:
                return
            try:
                if urlparse(path).scheme in ("http", "https"):
                    resp = requests.get(path, timeout=5)
                    resp.raise_for_status()
                    img = load_rgba_image(io.BytesIO(resp.content))
                else:
                    if os.path.exists(path):
                        img = load_rgba_image(path)
                    else:
                        return
                if img is None:
                    return
                img.thumbnail((400, 560))
                photo = _create_image(img)
                self.auction_photo = photo
                self.auction_image_label.configure(image=photo)
            except (requests.RequestException, OSError, UnidentifiedImageError) as exc:
                logger.warning("Failed to load auction image %s: %s", path, exc)

        def show_selected(event=None):
            name_var = getattr(self, "selected_card_name_var", None)
            if name_var is not None:
                name_var.set("")
            price_var = getattr(self, "selected_card_price_var", None)
            if price_var is not None:
                price_var.set("Aktualna cena: -")
            self._current_auction_row = None
            sel = tree.selection()
            if not sel:
                return
            idx = tree.index(sel[0])
            if 0 <= idx < len(self.auction_queue):
                row = self.auction_queue[idx]
                self._current_auction_row = row
                if name_var is not None:
                    name = (row.get("name") or row.get("nazwa_karty") or row.get("nazwa") or "").strip()
                    number = (
                        row.get("numer_karty")
                        or row.get("number")
                        or row.get("numer")
                        or ""
                    ).strip()
                    display = name
                    if number:
                        display = f"{display} ({number})" if display else number
                    name_var.set(display)
                if price_var is not None:
                    price_value = (
                        row.get("price")
                        or row.get("cena_początkowa")
                        or row.get("cena")
                        or row.get("start_price")
                    )
                    if price_value not in (None, ""):
                        price_var.set(f"Aktualna cena: {price_value}")
                    else:
                        price_var.set("Aktualna cena: -")
                path = row.get("images 1") or self._guess_scan_path(
                    row.get("nazwa_karty", ""), row.get("numer_karty", "")
                )
                load_image(path)

        def add_row():
            start, step, czas = [v.get().strip() for v in vars]
            selected = getattr(self, "_current_auction_row", None)

            def _entry_value(key: str) -> str:
                entries = getattr(self, "entries", None)
                if isinstance(entries, dict):
                    widget = entries.get(key)
                    if widget is not None:
                        getter = getattr(widget, "get", None)
                        if callable(getter):
                            try:
                                return str(getter()).strip()
                            except Exception:
                                return ""
                return ""

            name = ""
            number = ""
            base_price = ""
            if isinstance(selected, dict):
                name = (
                    str(
                        selected.get("nazwa_karty")
                        or selected.get("name")
                        or selected.get("nazwa")
                        or ""
                    ).strip()
                )
                number = (
                    str(
                        selected.get("numer_karty")
                        or selected.get("number")
                        or selected.get("numer")
                        or ""
                    ).strip()
                )
                base_price = str(
                    selected.get("price")
                    or selected.get("cena")
                    or selected.get("cena_początkowa")
                    or ""
                ).strip()
            if not name:
                name = _entry_value("nazwa") or _entry_value("name")
            if not number:
                number = _entry_value("numer") or _entry_value("number")
            if not base_price:
                base_price = _entry_value("cena") or _entry_value("price")

            start_price = start or base_price or "0"
            price_value = base_price or start_price
            row = {
                "nazwa_karty": name,
                "numer_karty": number,
                "opis": "",
                "cena_początkowa": start_price,
                "kwota_przebicia": step or "1",
                "czas_trwania": czas or "30",
                "price": price_value,
            }
            if isinstance(selected, dict):
                for key in ("warehouse_code", "images 1"):
                    value = selected.get(key)
                    if value:
                        row[key] = value
            self.auction_queue.append(row)
            for v in vars:
                v.set("")
            refresh_tree(select_index=len(self.auction_queue) - 1)

        def import_selected():
            previous_count = len(self.auction_queue)
            rows = self.load_auction_list()
            if not rows:
                return
            refresh_tree()
            if getattr(self, "auction_frame", None):
                try:
                    self.auction_frame.destroy()
                except tk.TclError:
                    pass
                self.auction_frame = None
            if self.auction_queue:
                initial_index = min(previous_count, len(self.auction_queue) - 1)
            else:
                initial_index = None
            self.open_auction_preview_window(self.auction_queue, initial_index)
            self.open_auction_run_window()

        button_bar = tk.Frame(win, bg=self.root.cget("background"))
        button_bar.pack(pady=10)
        self.create_button(
            button_bar,
            text="Dodaj",
            command=add_row,
            fg_color=SAVE_BUTTON_COLOR,
        ).pack(side="left", padx=5)
        self.create_button(
            button_bar,
            text="Wczytaj listę",
            command=import_selected,
            fg_color=FETCH_BUTTON_COLOR,
        ).pack(side="left", padx=5)
        self.create_button(
            button_bar,
            text="Powrót do menu",
            command=self.back_to_welcome,
            fg_color=NAV_BUTTON_COLOR,
        ).pack(side="left", padx=5)

        tree.bind("<<TreeviewSelect>>", show_selected)

        return refresh_tree

    def load_auction_list(self) -> Optional[list[dict]]:
        """Prompt for auction rows and append them to ``self.auction_queue``."""

        rows: list[dict] = []
        treeview = getattr(self, "inventory_tree", None)
        if treeview is not None:
            try:
                exists = str(treeview.winfo_exists()) == "1"
            except tk.TclError:
                exists = False
            else:
                if exists:
                    try:
                        selection = treeview.selection()
                        codes = [treeview.item(i, "values")[0] for i in selection]
                    except tk.TclError:
                        codes = []
                    if codes:
                        try:
                            rows = self.read_inventory_rows(
                                codes, csv_utils.WAREHOUSE_CSV
                            )
                        except (OSError, csv.Error, UnicodeDecodeError) as exc:
                            logger.exception("Failed to read inventory rows")
                            messagebox.showerror("Błąd", str(exc))
                            return None
        if not rows:
            path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
            if not path:
                return None
            try:
                rows = self.read_inventory_rows([], path)
            except (OSError, csv.Error, UnicodeDecodeError) as exc:
                logger.exception("Failed to read inventory rows")
                messagebox.showerror("Błąd", str(exc))
                return None
        if not rows:
            return None
        self.auction_queue.extend(rows)
        self.refresh_auction_preview()
        return rows

    def open_auction_preview_window(
        self,
        cards: Optional[Iterable[dict]] = None,
        initial_index: Optional[int] = None,
    ):
        """Open the auction preview window with queue details and controls."""

        existing = getattr(self, "auction_preview_window", None)
        if existing:
            try:
                if str(existing.winfo_exists()) == "1":
                    existing.destroy()
            except tk.TclError:
                pass
        self._clear_auction_preview_traces()
        self.auction_preview_window = None
        self.auction_preview_tree = None
        self.auction_preview_next_var = None
        self.auction_preview_image_label = None
        self.auction_preview_photo = None
        self._auction_preview_selected_index = None

        top = ctk.CTkToplevel(self.root)
        top.title("Podgląd licytacji")
        try:
            top.configure(fg_color=BG_COLOR)
        except tk.TclError:
            pass
        try:
            top.minsize(520, 360)
        except tk.TclError:
            pass
        if hasattr(top, "transient"):
            top.transient(self.root)
        if hasattr(top, "lift"):
            top.lift()
        self.auction_preview_window = top

        container = ctk.CTkFrame(top, fg_color=BG_COLOR)
        container.pack(expand=True, fill="both", padx=10, pady=10)
        container.grid_columnconfigure(0, weight=1)
        container.grid_columnconfigure(1, weight=1)
        container.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(
            container,
            text="Podgląd kolejki licytacji",
            font=("Segoe UI", 28, "bold"),
            text_color=TEXT_COLOR,
        ).grid(row=0, column=0, columnspan=2, pady=(0, 10))

        next_var = tk.StringVar()
        self.auction_preview_next_var = next_var
        ctk.CTkLabel(
            container,
            textvariable=next_var,
            text_color=TEXT_COLOR,
            font=("Segoe UI", 20),
        ).grid(row=1, column=0, columnspan=2, pady=(0, 10))

        main_frame = ctk.CTkFrame(container, fg_color=BG_COLOR)
        main_frame.grid(row=2, column=0, columnspan=2, sticky="nsew")
        main_frame.grid_columnconfigure(0, weight=3)
        main_frame.grid_columnconfigure(1, weight=2)
        main_frame.grid_rowconfigure(0, weight=1)

        style = ttk.Style(top)
        style.configure(
            "AuctionPreview.Treeview",
            background=BG_COLOR,
            fieldbackground=BG_COLOR,
            foreground=TEXT_COLOR,
            font=("Segoe UI", 14),
        )
        style.map("AuctionPreview.Treeview", background=[("selected", HOVER_COLOR)])
        style.configure(
            "AuctionPreview.Treeview.Heading",
            background=NAV_BUTTON_COLOR,
            foreground=TEXT_COLOR,
            font=("Segoe UI", 14, "bold"),
        )
        style.map(
            "AuctionPreview.Treeview.Heading",
            background=[("active", HOVER_COLOR), ("pressed", HOVER_COLOR)],
            foreground=[("active", TEXT_COLOR), ("pressed", TEXT_COLOR)],
        )

        list_frame = ctk.CTkFrame(main_frame, fg_color=BG_COLOR)
        list_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        tree = ttk.Treeview(
            list_frame,
            columns=("name", "number", "start", "step", "time"),
            show="headings",
            style="AuctionPreview.Treeview",
        )
        headings = [
            ("name", "Karta", "w", 280),
            ("number", "Numer", "center", 120),
            ("start", "Cena startowa", "center", 120),
            ("step", "Minimalne przebicie", "center", 150),
            ("time", "Czas [s]", "center", 90),
        ]
        for column, text, anchor, width in headings:
            tree.heading(column, text=text)
            tree.column(column, anchor=anchor, width=width, stretch=False)
        tree.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        tree.configure(yscrollcommand=scrollbar.set)
        tree.bind("<<TreeviewSelect>>", self._handle_auction_preview_select)
        self.auction_preview_tree = tree

        preview_frame = ctk.CTkFrame(main_frame, fg_color=BG_COLOR)
        preview_frame.grid(row=0, column=1, sticky="nsew")
        preview_frame.grid_columnconfigure(0, weight=1)

        self.auction_preview_image_label = ctk.CTkLabel(
            preview_frame,
            text="Brak podglądu",
            text_color=TEXT_COLOR,
        )
        self.auction_preview_image_label.grid(row=0, column=0, pady=(0, 8))

        ctk.CTkLabel(
            preview_frame,
            textvariable=self.auction_preview_name_var,
            text_color=TEXT_COLOR,
            font=("Segoe UI", 20, "bold"),
        ).grid(row=1, column=0, sticky="w", pady=(0, 4))

        ctk.CTkLabel(
            preview_frame,
            textvariable=self.auction_preview_price_var,
            text_color=TEXT_COLOR,
            font=("Segoe UI", 18),
        ).grid(row=2, column=0, sticky="w")

        form_frame = ctk.CTkFrame(preview_frame, fg_color=BG_COLOR)
        form_frame.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        form_frame.grid_columnconfigure(1, weight=1)

        self._clear_auction_preview_traces()
        fields = [
            ("Cena startowa", self.auction_preview_start_var, "start"),
            ("Czas licytacji [s]", self.auction_preview_time_var, "time"),
            ("Minimalna kwota przebicia", self.auction_preview_step_var, "step"),
        ]
        for row_idx, (label, var, field_key) in enumerate(fields):
            ctk.CTkLabel(
                form_frame,
                text=label,
                text_color=TEXT_COLOR,
                font=("Segoe UI", 16),
            ).grid(row=row_idx, column=0, sticky="w", padx=(0, 8), pady=4)
            entry = ctk.CTkEntry(form_frame, textvariable=var, width=140)
            entry.grid(row=row_idx, column=1, sticky="ew", pady=4)
            trace_id = var.trace_add(
                "write",
                lambda *_args, key=field_key: self._on_preview_field_change(key),
            )
            self._auction_preview_trace_ids.append((var, trace_id))

        info_frame = ctk.CTkFrame(preview_frame, fg_color=BG_COLOR)
        info_frame.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        info_frame.grid_columnconfigure(1, weight=1)
        info_labels = [
            ("Pozostały czas", self.auction_preview_timer_var),
            ("Prowadzi", self.auction_preview_leader_var),
            ("Aktualna kwota", self.auction_preview_amount_var),
        ]
        for row_idx, (label, var) in enumerate(info_labels):
            ctk.CTkLabel(
                info_frame,
                text=f"{label}:",
                text_color=TEXT_COLOR,
                font=("Segoe UI", 16),
            ).grid(row=row_idx, column=0, sticky="w", pady=2)
            ctk.CTkLabel(
                info_frame,
                textvariable=var,
                text_color=TEXT_COLOR,
                font=("Segoe UI", 16, "bold"),
            ).grid(row=row_idx, column=1, sticky="w", pady=2)

        buttons_frame = ctk.CTkFrame(preview_frame, fg_color=BG_COLOR)
        buttons_frame.grid(row=5, column=0, sticky="ew", pady=(12, 0))
        button_specs = [
            ("Start licytacji", "start_auction", SAVE_BUTTON_COLOR),
            ("Następna karta", "next_card", FETCH_BUTTON_COLOR),
            ("Zakończ", "finish", NAV_BUTTON_COLOR),
        ]
        for text, action, color in button_specs:
            ctk.CTkButton(
                buttons_frame,
                text=text,
                fg_color=color,
                command=lambda act=action: self._call_auction_action(act),
            ).pack(side="left", expand=True, fill="x", padx=4)

        def on_close():
            self._clear_auction_preview_traces()
            self.auction_preview_window = None
            self.auction_preview_tree = None
            self.auction_preview_next_var = None
            self.auction_preview_image_label = None
            self.auction_preview_photo = None
            self._auction_preview_selected_index = None
            try:
                if str(top.winfo_exists()) == "1":
                    top.destroy()
            except tk.TclError:
                pass

        if hasattr(top, "protocol"):
            top.protocol("WM_DELETE_WINDOW", on_close)

        focus_index = initial_index
        if cards is not None:
            cards_list = list(cards)
            if focus_index is None and cards_list:
                first_card = cards_list[0]
                try:
                    focus_index = self.auction_queue.index(first_card)
                except ValueError:
                    focus_index = 0
        if focus_index is None and self.auction_queue:
            focus_index = 0

        self.refresh_auction_preview(select_index=focus_index)

    def open_auction_run_window(self):
        """Open or refresh the auction control window."""

        bot_module = getattr(self, "bot", None)
        if bot_module is None:
            try:
                import bot as bot_module  # type: ignore[import]
            except Exception as exc:
                logger.exception("Failed to import bot module")
                messagebox.showerror("Błąd", str(exc))
                return
            self.bot = bot_module

        existing = getattr(self, "auction_run_window", None)
        if existing is not None:
            try:
                existing.close()
            except Exception:
                pass

        try:
            self.auction_run_window = AuctionRunWindow(self)
        except Exception:
            logger.exception("Failed to open auction run window")
            messagebox.showerror(
                "Błąd",
                "Nie udało się otworzyć okna sterowania aukcją.",
            )
    def refresh_auction_preview(self, select_index: Optional[int] = None) -> None:
        """Refresh data shown in the auction preview window if it exists."""

        tree = getattr(self, "auction_preview_tree", None)
        window = getattr(self, "auction_preview_window", None)
        if not tree or not window:
            return
        try:
            exists = str(window.winfo_exists()) == "1"
        except tk.TclError:
            exists = False
        if not exists:
            self.auction_preview_tree = None
            self.auction_preview_window = None
            self.auction_preview_next_var = None
            self.auction_preview_image_label = None
            self.auction_preview_photo = None
            self._auction_preview_selected_index = None
            return

        if select_index is None:
            try:
                current_selection = tree.selection()
            except tk.TclError:
                current_selection = ()
            if current_selection:
                try:
                    select_index = tree.index(current_selection[0])
                except tk.TclError:
                    select_index = None

        for item_id in tree.get_children():
            tree.delete(item_id)

        for row in self.auction_queue:
            values = (
                row.get("nazwa_karty") or row.get("name") or "",
                row.get("numer_karty") or row.get("number") or "",
                row.get("cena_początkowa") or row.get("price") or "",
                row.get("kwota_przebicia") or row.get("przebicie") or "",
                row.get("czas_trwania") or row.get("czas") or "",
            )
            tree.insert(
                "",
                "end",
                values=tuple(
                    str(value) if value is not None else "" for value in values
                ),
            )

        next_var = getattr(self, "auction_preview_next_var", None)
        if next_var is not None:
            if self.auction_queue:
                nxt = self.auction_queue[0]
                name = str(nxt.get("nazwa_karty") or nxt.get("name") or "").strip()
                number = str(nxt.get("numer_karty") or nxt.get("number") or "").strip()
                if name and number:
                    text = f"Następna karta: {name} ({number})"
                elif name:
                    text = f"Następna karta: {name}"
                else:
                    text = "Następna karta: -"
            else:
                text = "Brak kart w kolejce"
            next_var.set(text)

        items = tree.get_children()
        if not items:
            try:
                tree.selection_remove(tree.selection())
            except tk.TclError:
                pass
            self._update_auction_preview_selection(None)
            return

        if select_index is None:
            select_index = 0
        select_index = max(0, min(select_index, len(items) - 1))
        item_id = items[select_index]
        try:
            tree.selection_set(item_id)
            tree.focus(item_id)
            tree.see(item_id)
        except tk.TclError:
            pass
        self._update_auction_preview_selection(select_index)

    def _clear_auction_preview_traces(self) -> None:
        for var, trace_id in list(getattr(self, "_auction_preview_trace_ids", [])):
            try:
                var.trace_remove("write", trace_id)
            except tk.TclError:
                pass
        self._auction_preview_trace_ids = []

    def _handle_auction_preview_select(self, event=None) -> None:
        del event
        tree = getattr(self, "auction_preview_tree", None)
        if not tree:
            return
        try:
            selection = tree.selection()
        except tk.TclError:
            selection = ()
        if not selection:
            self._update_auction_preview_selection(None)
            return
        try:
            index = tree.index(selection[0])
        except tk.TclError:
            index = None
        self._update_auction_preview_selection(index)

    def _update_auction_preview_selection(self, index: Optional[int]) -> None:
        if index is None or not (0 <= index < len(self.auction_queue)):
            self._auction_preview_selected_index = None
            self._clear_auction_preview_details()
            return
        row = self.auction_queue[index]
        self._auction_preview_selected_index = index
        self._auction_preview_updating = True
        try:
            name = (row.get("nazwa_karty") or row.get("name") or row.get("nazwa") or "").strip()
            number = (
                row.get("numer_karty")
                or row.get("number")
                or row.get("numer")
                or ""
            ).strip()
            display = name
            if number:
                display = f"{display} ({number})" if display else number
            self.auction_preview_name_var.set(display)

            start_value = row.get("cena_początkowa") or row.get("price") or row.get("cena") or "0"
            step_value = row.get("kwota_przebicia") or row.get("przebicie") or "1"
            time_value = row.get("czas_trwania") or row.get("czas") or "30"

            self.auction_preview_price_var.set(
                f"Cena: {self._format_preview_price(start_value)}"
            )
            self.auction_preview_start_var.set(str(start_value) if start_value is not None else "")
            self.auction_preview_step_var.set(str(step_value) if step_value is not None else "")
            self.auction_preview_time_var.set(str(time_value) if time_value is not None else "30")
        finally:
            self._auction_preview_updating = False

        self._update_preview_image(row)
        self.auction_preview_amount_var.set(self._format_preview_price(start_value))
        time_text = str(row.get("czas_trwania") or row.get("czas") or "30").strip()
        if time_text:
            self.auction_preview_timer_var.set(f"{time_text} s")
        else:
            self.auction_preview_timer_var.set("0 s")
        leader = row.get("zwyciezca") or row.get("leader") or "-"
        leader_text = str(leader).strip() or "-"
        self.auction_preview_leader_var.set(leader_text)

    def _clear_auction_preview_details(self) -> None:
        self._auction_preview_updating = True
        try:
            self.auction_preview_name_var.set("")
            self.auction_preview_price_var.set("Cena: -")
            self.auction_preview_start_var.set("")
            self.auction_preview_time_var.set("30")
            self.auction_preview_step_var.set("")
            self.auction_preview_timer_var.set("0 s")
            self.auction_preview_leader_var.set("-")
            self.auction_preview_amount_var.set("-")
        finally:
            self._auction_preview_updating = False
        label = getattr(self, "auction_preview_image_label", None)
        if label is not None:
            try:
                label.configure(image=None, text="Brak podglądu")
            except tk.TclError:
                pass
        self.auction_preview_photo = None

    def _format_preview_price(self, value: object) -> str:
        if value in (None, "", "-"):
            return "-"
        text = str(value).strip()
        if not text:
            return "-"
        try:
            number = float(text.replace(",", "."))
        except ValueError:
            return text
        else:
            return f"{number:.2f} PLN"

    def _compute_preview_remaining_seconds(self, data: dict) -> Optional[int]:
        start_str = data.get("start_time")
        duration = data.get("czas")
        if not start_str or duration in (None, ""):
            return None
        try:
            start = datetime.datetime.fromisoformat(str(start_str).rstrip("Z"))
            duration_int = int(duration)
        except (ValueError, TypeError):
            return None
        end = start + datetime.timedelta(seconds=duration_int)
        remaining = int((end - datetime.datetime.utcnow()).total_seconds())
        return max(remaining, 0)

    def _resolve_preview_image_source(self, row: Optional[dict]) -> Optional[str]:
        if not row:
            return None
        for key in ("images 1", "image", "obraz_url", "local_image"):
            value = row.get(key)
            if value:
                return str(value)
        name = row.get("nazwa_karty") or row.get("name") or row.get("nazwa") or ""
        number = row.get("numer_karty") or row.get("number") or row.get("numer") or ""
        return self._guess_scan_path(str(name), str(number))

    def _update_preview_image(self, row: Optional[dict]) -> None:
        label = getattr(self, "auction_preview_image_label", None)
        if label is None:
            return
        source = self._resolve_preview_image_source(row)
        if not source:
            try:
                label.configure(image=None, text="Brak podglądu")
            except tk.TclError:
                pass
            self.auction_preview_photo = None
            return
        img = _get_thumbnail(source, (260, 360))
        if img is None:
            try:
                label.configure(image=None, text="Brak podglądu")
            except tk.TclError:
                pass
            self.auction_preview_photo = None
            return
        self.auction_preview_photo = _create_image(img)
        try:
            label.configure(image=self.auction_preview_photo, text="")
        except tk.TclError:
            pass

    def _on_preview_field_change(self, field: str) -> None:
        if self._auction_preview_updating:
            return
        index = self._auction_preview_selected_index
        if index is None or not (0 <= index < len(self.auction_queue)):
            return
        row = self.auction_queue[index]
        if field == "start":
            value = self.auction_preview_start_var.get().strip()
            if not value:
                value = "0"
            row["cena_początkowa"] = value
            row["price"] = value
            row["cena"] = value
        elif field == "time":
            value = self.auction_preview_time_var.get().strip() or "30"
            self.auction_preview_time_var.set(value)
            row["czas_trwania"] = value
            row["czas"] = value
        elif field == "step":
            value = self.auction_preview_step_var.get().strip() or "1"
            self.auction_preview_step_var.set(value)
            row["kwota_przebicia"] = value
            row["przebicie"] = value
        self.refresh_auction_preview(select_index=index)

    def _call_auction_action(self, action: str) -> None:
        run_window = getattr(self, "auction_run_window", None)
        if run_window is None:
            self.open_auction_run_window()
            run_window = getattr(self, "auction_run_window", None)
        if run_window is None:
            return
        method = getattr(run_window, action, None)
        if callable(method):
            try:
                method()
            except Exception as exc:
                logger.exception("Failed to execute auction action %s", action)
                messagebox.showerror("Błąd", str(exc))

    def _guess_scan_path(self, name: str, number: str) -> Optional[str]:
        name_norm = str(name).strip().lower().replace(" ", "_")
        number_norm = str(number).strip().lower().replace("/", "-")
        if not name_norm and not number_norm:
            return None
        candidates = [
            f"{name_norm}_{number_norm}",
            f"{name_norm}-{number_norm}",
            f"{name_norm} {number_norm}",
            number_norm,
        ]
        exts = [".jpg", ".png", ".jpeg"]
        for root_dir, _dirs, files in os.walk(SCANS_DIR):
            lower = {f.lower(): f for f in files}
            for candidate in candidates:
                if not candidate:
                    continue
                for ext in exts:
                    fname = candidate + ext
                    if fname in lower:
                        return os.path.join(root_dir, lower[fname])
        return None

    def _load_auction_queue(self):
        """Load auction queue from inventory CSV into ``self.auction_queue``."""
        path = getattr(
            csv_utils,
            "WAREHOUSE_CSV",
            getattr(csv_utils, "INVENTORY_CSV", "magazyn.csv"),
        )
        self.auction_queue = self.read_inventory_rows([], path)

    def read_inventory_rows(self, codes, path=None):
        """Return rows from ``path`` filtered by ``codes``."""
        if path is None:
            path = getattr(
                csv_utils,
                "WAREHOUSE_CSV",
                getattr(csv_utils, "INVENTORY_CSV", "magazyn.csv"),
            )
        with open(path, newline="", encoding="utf-8") as f:
            sample = f.read(2048)
            f.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=";,")
            except csv.Error:
                dialect = csv.excel
            reader = csv.DictReader(f, dialect=dialect)
            rows = [
                {norm_header(k): v for k, v in r.items() if k is not None}
                for r in reader
            ]

        headers = [norm_header(h) for h in (reader.fieldnames or [])]
        if "nazwa_karty" not in headers:
            if "name" in headers:
                for row in rows:
                    if "nazwa_karty" not in row:
                        name_val = str(row.get("name", "")).strip()
                        parts = name_val.rsplit(" ", 1)
                        if len(parts) == 2 and re.search(r"\d", parts[1]):
                            row["nazwa_karty"], row["numer_karty"] = parts
                        else:
                            row["nazwa_karty"] = name_val
                            row["numer_karty"] = ""
                    row["cena_początkowa"] = row.get("price", row.get("cena_początkowa", "0"))
                    row.setdefault("kwota_przebicia", "1")
                    row.setdefault("czas_trwania", "30")
            else:
                raise ValueError("Nie rozpoznano formatu pliku CSV")
        for row in rows:
            row.setdefault("price", "0")
            row.setdefault("product_code", "")
            if "image" in row and "images 1" not in row:
                row["images 1"] = row.pop("image")
        if codes:
            wanted = {str(c) for c in codes}
            rows = [r for r in rows if str(r.get("product_code")) in wanted]
        return rows

    def lookup_inventory_entry(self, key):
        """Return first row from ``WAREHOUSE_CSV`` matching ``key``."""
        parts = key.split("|")
        if len(parts) < 3:
            return None
        name, number, set_name = parts[:3]

        try:
            with open(csv_utils.WAREHOUSE_CSV, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f, delimiter=";")
                for raw in reader:
                    row = {norm_header(k): v for k, v in raw.items() if k is not None}
                    row_name = (row.get("nazwa") or row.get("nazwa_karty") or row.get("name") or "").strip()
                    row_number = (
                        row.get("numer")
                        or row.get("numer_karty")
                        or row.get("number")
                        or ""
                    ).strip()
                    row_set = row.get("set", "").strip()
                    if (
                        row_name == name and row_number == number and row_set == set_name
                    ):
                        return {
                            "nazwa": row_name,
                            "numer": row_number,
                            "set": row_set,
                        }
        except FileNotFoundError:
            return None

        return None

    def _update_auction_status(self):
        """Update status panel with info from ``aktualna_aukcja.json``."""
        path = os.path.join("templates", "aktualna_aukcja.json")
        data: Optional[dict] = None
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)

                self.info_var.set(
                    f"Aktualna: {data.get('nazwa')} ({data.get('numer')})"
                )

                self.current_price_var.set(str(data.get("ostateczna_cena", "")))
                name_var = getattr(self, "selected_card_name_var", None)
                if name_var is not None:
                    name = (data.get("nazwa") or "").strip()
                    number = (data.get("numer") or "").strip()
                    display = name
                    if number:
                        display = f"{display} ({number})" if display else number
                    name_var.set(display)
                    preview_name_var = getattr(self, "auction_preview_name_var", None)
                    if preview_name_var is not None:
                        preview_name_var.set(display)
                price_var = getattr(self, "selected_card_price_var", None)
                if price_var is not None:
                    price_value = data.get("ostateczna_cena")
                    if price_value not in (None, ""):
                        price_var.set(f"Aktualna cena: {price_value}")
                    else:
                        price_var.set("Aktualna cena: -")
                preview_price_var = getattr(self, "auction_preview_price_var", None)
                if preview_price_var is not None:
                    preview_price_var.set(
                        f"Cena: {self._format_preview_price(data.get('ostateczna_cena'))}"
                    )
                amount_var = getattr(self, "auction_preview_amount_var", None)
                if amount_var is not None:
                    amount_var.set(self._format_preview_price(data.get("ostateczna_cena")))
                leader_var = getattr(self, "auction_preview_leader_var", None)
                if leader_var is not None:
                    leader = (data.get("zwyciezca") or "").strip() or "-"
                    leader_var.set(leader)
                timer_var = getattr(self, "auction_preview_timer_var", None)
                if timer_var is not None:
                    remaining = self._compute_preview_remaining_seconds(data)
                    if remaining is not None:
                        timer_var.set(f"{remaining} s")
                img_path = data.get("obraz")
                if img_path:
                    try:
                        if urlparse(img_path).scheme in ("http", "https"):
                            resp = requests.get(img_path, timeout=5)
                            resp.raise_for_status()
                            img = load_rgba_image(io.BytesIO(resp.content))
                        else:
                            if os.path.exists(img_path):
                                img = load_rgba_image(img_path)
                            else:
                                img = None
                        if img is not None:
                            img.thumbnail((400, 560))
                            photo = _create_image(img)
                            self.auction_photo = photo
                            self.auction_image_label.configure(image=photo)
                    except (requests.RequestException, OSError, UnidentifiedImageError) as exc:
                        logger.warning("Failed to load current auction image: %s", exc)
            except Exception as exc:
                logger.exception("Failed to update auction status")
        run_window = getattr(self, "auction_run_window", None)
        if run_window is not None:
            try:
                run_window.update_from_status(data)
            except Exception:
                logger.exception("Failed to update auction run window")
        if not data:
            amount_var = getattr(self, "auction_preview_amount_var", None)
            if amount_var is not None:
                amount_var.set("-")
            leader_var = getattr(self, "auction_preview_leader_var", None)
            if leader_var is not None:
                leader_var.set("-")
            timer_var = getattr(self, "auction_preview_timer_var", None)
            if timer_var is not None:
                timer_var.set("0 s")
        if self.auction_frame and self.auction_frame.winfo_exists():
            self.auction_frame.after(1000, self._update_auction_status)
        return data

    def _load_shoper_language_overrides(self) -> Mapping[str, int]:
        """Load user-provided language overrides from configuration."""

        overrides: dict[str, int] = {}

        def _register(code: Any, language_id: Any, *, context: str) -> None:
            normalized_code = _normalize_locale_code(code)
            if not normalized_code:
                return
            try:
                if isinstance(language_id, bool):
                    return
                if isinstance(language_id, (int, float)):
                    coerced_id = int(language_id)
                elif isinstance(language_id, str):
                    stripped = language_id.strip()
                    if not stripped:
                        return
                    coerced_id = int(float(stripped))
                else:
                    return
            except (TypeError, ValueError):
                logger.warning(
                    "Nieprawidłowa wartość language_id w %s: %r", context, language_id
                )
                return

            overrides[normalized_code] = coerced_id

        env_code = os.environ.get("SHOPER_LANGUAGE_CODE")
        env_id = os.environ.get("SHOPER_LANGUAGE_ID")
        if env_code and env_id:
            _register(env_code, env_id, context="zmiennych środowiskowych")

        raw_overrides = os.environ.get("SHOPER_LANGUAGE_OVERRIDES")
        if raw_overrides:
            try:
                parsed = json.loads(raw_overrides)
            except json.JSONDecodeError:
                logger.warning(
                    "Nie udało się zdekodować SHOPER_LANGUAGE_OVERRIDES jako JSON"
                )
            else:
                if isinstance(parsed, Mapping):
                    for code, language_id in parsed.items():
                        _register(code, language_id, context="SHOPER_LANGUAGE_OVERRIDES")
                elif isinstance(parsed, Iterable) and not isinstance(
                    parsed, (str, bytes, bytearray)
                ):
                    for entry in parsed:
                        if not isinstance(entry, Mapping):
                            continue
                        code = (
                            entry.get("code")
                            or entry.get("language_code")
                            or entry.get("lang_code")
                            or entry.get("locale")
                        )
                        language_id = (
                            entry.get("language_id")
                            or entry.get("id")
                            or entry.get("lang_id")
                        )
                        _register(code, language_id, context="SHOPER_LANGUAGE_OVERRIDES")

        return overrides

    def _ensure_shoper_languages_map(self) -> Mapping[str, Mapping[str, int]]:
        """Return cached Shoper language identifiers keyed by locale."""

        cache = getattr(self, "_shoper_languages_cache", None)
        if isinstance(cache, Mapping):
            by_code = cache.get("by_code")
            by_id = cache.get("by_id")
            if isinstance(by_code, Mapping) and isinstance(by_id, Mapping):
                return cache

        by_code: dict[str, int] = {}
        by_id: dict[int, str] = {}

        def _register(code: Any, language_id: Any) -> None:
            normalized_code = _normalize_locale_code(code)
            if not normalized_code:
                return
            try:
                if isinstance(language_id, bool):
                    return
                if isinstance(language_id, (int, float)):
                    coerced_id = int(language_id)
                elif isinstance(language_id, str):
                    stripped = language_id.strip()
                    if not stripped:
                        return
                    coerced_id = int(float(stripped))
                else:
                    return
            except (TypeError, ValueError):
                return

            by_code[normalized_code] = coerced_id
            by_id.setdefault(coerced_id, normalized_code)

        overrides = getattr(self, "shoper_language_overrides", None)
        if isinstance(overrides, Mapping):
            for code, language_id in overrides.items():
                _register(code, language_id)

        for code, language_id in HARDCODED_SHOPER_LANGUAGE_IDS.items():
            _register(code, language_id)

        client = getattr(self, "shoper_client", None)
        if client is not None and not _is_mock_object(client):
            try:
                response = client.get("languages")
            except Exception as exc:  # pragma: no cover - network dependent
                status_code = getattr(getattr(exc, "response", None), "status_code", None)
                if status_code == 403:
                    logger.info(
                        "Brak uprawnień do pobrania języków Shoper (403). "
                        "Używam konfiguracji lokalnej i wartości domyślnych."
                    )
                else:
                    logger.warning("Failed to fetch Shoper languages: %s", exc)
            else:
                def _iter_language_entries(payload: Any) -> Iterable[Mapping[str, Any]]:
                    if isinstance(payload, Mapping):
                        for key in ("list", "items", "data", "results", "languages"):
                            container = payload.get(key)
                            if isinstance(container, Mapping):
                                yield from _iter_language_entries(container)
                            elif isinstance(container, (list, tuple, set)):
                                for entry in container:
                                    if isinstance(entry, Mapping):
                                        yield entry
                        return
                    if isinstance(payload, (list, tuple, set)):
                        for entry in payload:
                            if isinstance(entry, Mapping):
                                yield entry

                for entry in _iter_language_entries(response):
                    language_id = (
                        entry.get("language_id")
                        or entry.get("id")
                        or entry.get("languageId")
                    )
                    if isinstance(entry.get("language"), Mapping):
                        nested = entry.get("language")
                        language_id = (
                            language_id
                            or nested.get("language_id")
                            or nested.get("id")
                        )
                        if not entry.get("code"):
                            entry = {**entry, **nested}

                    code = (
                        entry.get("code")
                        or entry.get("language_code")
                        or entry.get("lang_code")
                        or entry.get("symbol")
                    )
                    _register(code, language_id)

        self._shoper_languages_cache = {"by_code": by_code, "by_id": by_id}
        return self._shoper_languages_cache

    def _update_default_availability_value(self, value: Any) -> None:
        def _coerce_optional_int(raw: Any) -> Optional[int]:
            if raw in (None, ""):
                return None
            if isinstance(raw, bool):
                return int(raw)
            if isinstance(raw, (int, float)):
                try:
                    return int(raw)
                except (TypeError, ValueError):
                    return None
            if isinstance(raw, str):
                text = raw.strip()
                if not text:
                    return None
                if text.isdigit():
                    try:
                        return int(text)
                    except ValueError:
                        return None
                try:
                    return int(float(text))
                except ValueError:
                    return None
            return None

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
                elif first is not None:
                    label = str(first).strip()
            if len(value) > 1:
                identifier = _coerce_optional_int(value[1])
        elif isinstance(value, str):
            label = value.strip()
        elif value is not None:
            label = str(value).strip()

        cleaned = label or (str(identifier) if identifier is not None else "")

        if not cleaned:
            return

        self._default_availability_value = cleaned
        if identifier is not None:
            self._default_availability_id = identifier
        elif cleaned.isdigit():
            try:
                self._default_availability_id = int(cleaned)
            except ValueError:
                self._default_availability_id = None
        else:
            self._default_availability_id = None

        payload: Any
        if label is not None or identifier is not None:
            payload = {"available_label": label, "available_id": identifier}
        else:
            payload = cleaned

        try:
            csv_utils.set_default_availability(payload)
        except Exception:
            pass
        self._update_availability_choices()

    def _determine_default_availability_from_cache(
        self, cache: Mapping[str, Any] | None = None
    ) -> Optional[str]:
        if cache is None:
            cache = getattr(self, "_shoper_taxonomy_cache", {})
        if not isinstance(cache, Mapping):
            return None

        mapping = cache.get("availability") if isinstance(cache, Mapping) else None
        if not isinstance(mapping, Mapping):
            return None

        def _coerce_int_value(raw: Any) -> Optional[int]:
            if raw in (None, ""):
                return None
            if isinstance(raw, bool):
                return int(raw)
            if isinstance(raw, (int, float)):
                try:
                    return int(raw)
                except (TypeError, ValueError):
                    return None
            if isinstance(raw, str):
                stripped = raw.strip()
                if not stripped:
                    return None
                if stripped.isdigit():
                    try:
                        return int(stripped)
                    except ValueError:
                        return None
                try:
                    return int(float(stripped))
                except ValueError:
                    return None
            return None

        def _coerce_priority(raw: Any) -> float:
            if isinstance(raw, (int, float)) and not isinstance(raw, bool):
                return float(raw)
            if isinstance(raw, str):
                stripped = raw.strip()
                if not stripped:
                    return float("-inf")
                try:
                    return float(stripped)
                except ValueError:
                    return float("-inf")
            return float("-inf")

        available_id = _coerce_int_value(mapping.get("available_id"))
        best_id = available_id
        best_label: Optional[str] = None
        best_score = float("-inf")

        def _register_candidate(
            label_candidate: Any,
            candidate_id: Optional[int],
            *,
            explicit_score: Optional[float] = None,
        ) -> None:
            nonlocal best_label, best_id, best_score
            if not isinstance(label_candidate, str):
                return
            candidate_label = label_candidate.strip()
            if not candidate_label:
                return
            score = explicit_score if explicit_score is not None else _score_availability_label(candidate_label)
            if score == float("-inf"):
                return
            if score > best_score:
                best_score = score
                best_label = candidate_label
                if candidate_id is not None:
                    best_id = candidate_id
            elif score == best_score:
                if best_label is None:
                    best_label = candidate_label
                if best_id is None and candidate_id is not None:
                    best_id = candidate_id

        stored_label = mapping.get("available_label")
        stored_priority = _coerce_priority(mapping.get("available_priority"))
        if isinstance(stored_label, str) and stored_label.strip():
            explicit = stored_priority if stored_priority > float("-inf") else 0.0
            _register_candidate(stored_label, available_id, explicit_score=explicit)

        by_id = mapping.get("by_id") if isinstance(mapping.get("by_id"), Mapping) else None
        if available_id is not None and isinstance(by_id, Mapping):
            entry = by_id.get(available_id)
            if isinstance(entry, Mapping):
                for key in ("label", "name", "title", "value", "text", "code"):
                    _register_candidate(entry.get(key), available_id)

        by_name = mapping.get("by_name") if isinstance(mapping.get("by_name"), Mapping) else None
        if isinstance(by_name, Mapping):
            for name, value in by_name.items():
                coerced_id = _coerce_int_value(value)
                _register_candidate(name, coerced_id)

        if isinstance(by_id, Mapping):
            for key, entry in by_id.items():
                if not isinstance(entry, Mapping):
                    continue
                coerced_id = _coerce_int_value(key)
                for field in ("label", "name", "title", "value", "text", "code"):
                    _register_candidate(entry.get(field), coerced_id)

        if best_label is not None:
            mapping["available_label"] = best_label
            if best_id is not None:
                mapping["available_id"] = best_id
            if best_score > float("-inf"):
                mapping["available_priority"] = best_score
            return best_label

        if best_id is not None:
            mapping["available_id"] = best_id
            return str(best_id)

        default_candidate = mapping.get("default")
        if isinstance(default_candidate, str):
            trimmed = default_candidate.strip()
            return trimmed or None
        coerced_default = _coerce_int_value(default_candidate)
        if coerced_default is not None:
            mapping.setdefault("available_id", coerced_default)
            return str(coerced_default)
        return None

    def _refresh_default_availability_from_cache(self) -> None:
        value = self._determine_default_availability_from_cache()
        if value:
            self._update_default_availability_value(value)
        self._update_availability_choices()

    def _get_default_availability_value(self) -> str:
        current = getattr(self, "_default_availability_value", None)
        if isinstance(current, str) and current.strip():
            return current

        value = self._determine_default_availability_from_cache()
        if not value:
            try:
                cache = self._ensure_shoper_taxonomy_cache()
            except Exception:
                cache = getattr(self, "_shoper_taxonomy_cache", {})
                value = self._determine_default_availability_from_cache(cache)
            else:
                value = self._determine_default_availability_from_cache(cache)

        if value:
            self._update_default_availability_value(value)
            resolved = getattr(self, "_default_availability_value", value)
            if isinstance(resolved, str) and resolved.strip():
                return resolved
            return value

        def _coerce_optional_int(raw: Any) -> Optional[int]:
            if raw in (None, ""):
                return None
            if isinstance(raw, bool):
                return int(raw)
            if isinstance(raw, (int, float)):
                try:
                    return int(raw)
                except (TypeError, ValueError):
                    return None
            if isinstance(raw, str):
                text = raw.strip()
                if not text:
                    return None
                if text.isdigit():
                    try:
                        return int(text)
                    except ValueError:
                        return None
                try:
                    return int(float(text))
                except ValueError:
                    return None
            return None

        cache = getattr(self, "_shoper_taxonomy_cache", {})
        mapping = cache.get("availability") if isinstance(cache, Mapping) else None
        fallback_label: Optional[str] = None
        fallback_id: Optional[int] = None

        if isinstance(mapping, Mapping):
            stored_label = mapping.get("available_label")
            if isinstance(stored_label, str) and stored_label.strip():
                fallback_label = stored_label.strip()

            stored_id = _coerce_optional_int(mapping.get("available_id"))
            if stored_id is not None:
                fallback_id = stored_id
                if not fallback_label:
                    by_id = mapping.get("by_id")
                    if isinstance(by_id, Mapping):
                        entry = by_id.get(stored_id) or by_id.get(str(stored_id))
                        if isinstance(entry, Mapping):
                            for key in ("label", "name", "title", "value", "text", "code"):
                                candidate = entry.get(key)
                                if isinstance(candidate, str) and candidate.strip():
                                    fallback_label = candidate.strip()
                                    break

            if not fallback_label:
                default_candidate = mapping.get("default")
                if isinstance(default_candidate, str) and default_candidate.strip():
                    fallback_label = default_candidate.strip()
                else:
                    coerced_default = _coerce_optional_int(default_candidate)
                    if coerced_default is not None and fallback_id is None:
                        fallback_id = coerced_default

        if not fallback_label and fallback_id is None:
            csv_default = csv_utils.get_default_availability()
            if isinstance(csv_default, str) and csv_default.strip():
                fallback_label = csv_default.strip()
            else:
                fallback_id = _coerce_optional_int(csv_default)

        if fallback_label or fallback_id is not None:
            payload: dict[str, Any] = {}
            if fallback_label:
                payload["available_label"] = fallback_label
            if fallback_id is not None:
                payload["available_id"] = fallback_id
            if payload:
                self._update_default_availability_value(payload)
                resolved = getattr(self, "_default_availability_value", None)
                if isinstance(resolved, str) and resolved.strip():
                    return resolved.strip()
                if fallback_label:
                    return fallback_label
                if fallback_id is not None:
                    return str(fallback_id)

        fallback = "1"
        self._update_default_availability_value(fallback)
        return fallback

    def _current_availability_default(self) -> Optional[str]:
        value = getattr(self, "_default_availability_value", None)
        if isinstance(value, str):
            cleaned = value.strip()
            if cleaned:
                return cleaned
        try:
            csv_default = csv_utils.get_default_availability()
        except Exception:
            csv_default = None
        if isinstance(csv_default, str):
            cleaned_csv = csv_default.strip()
            if cleaned_csv:
                return cleaned_csv
        return None

    def _get_known_availability_labels(self) -> list[str]:
        labels: list[str] = []
        seen: set[str] = set()

        def _register(value: Any) -> None:
            if isinstance(value, str):
                cleaned = value.strip()
                if cleaned and cleaned not in seen:
                    labels.append(cleaned)
                    seen.add(cleaned)

        cache = getattr(self, "_shoper_taxonomy_cache", None)
        mapping = cache.get("availability") if isinstance(cache, Mapping) else None
        if isinstance(mapping, Mapping):
            by_name = mapping.get("by_name")
            if isinstance(by_name, Mapping):
                for label in by_name.keys():
                    if label is None:
                        continue
                    _register(str(label))

            by_id = mapping.get("by_id")
            if isinstance(by_id, Mapping):
                for entry in by_id.values():
                    if isinstance(entry, Mapping):
                        for field in ("label", "name", "title", "text", "value", "code"):
                            if field in entry:
                                _register(entry[field])
                    else:
                        _register(entry)

            _register(mapping.get("available_label"))

        default_value = self._current_availability_default()
        if default_value:
            if default_value in labels:
                labels = [label for label in labels if label != default_value]
            labels.insert(0, default_value)

        return labels

    def _update_availability_choices(self) -> None:
        widget = getattr(self, "_availability_widget", None)
        if widget is None:
            return

        options = self._get_known_availability_labels()
        if not options:
            default_value = self._current_availability_default()
            if default_value:
                options = [default_value]

        combo_cls = getattr(ctk, "CTkComboBox", None)
        if options and combo_cls is not None and isinstance(widget, combo_cls):
            try:
                widget.configure(values=options)
            except Exception:
                pass

        var = self.entries.get("availability")
        if hasattr(var, "get") and hasattr(var, "set"):
            try:
                current_value = var.get()
            except Exception:
                current_value = ""
            if not str(current_value or "").strip():
                default_value = self._current_availability_default()
                if default_value:
                    try:
                        var.set(default_value)
                    except Exception:
                        pass

    def _ensure_shoper_taxonomy_cache(self) -> Mapping[str, Any]:
        """Ensure taxonomy cache contains data required to build payloads."""

        cache = getattr(self, "_shoper_taxonomy_cache", None)
        if not isinstance(cache, Mapping):
            cache = {}

        required_specs = {
            "category": {"endpoint": "categories", "id_field": "category_id"},
            "producer": {"endpoint": "producers", "id_field": "producer_id"},
            "tax": {"endpoint": "taxes", "id_field": "tax_id"},
            "unit": {"endpoint": "units", "id_field": "unit_id"},
            "availability": {
                "endpoint": "availabilities",
                "id_field": "availability_id",
            },
        }

        def _has_entries(kind: str) -> bool:
            value = cache.get(kind) if isinstance(cache, Mapping) else None
            if isinstance(value, Mapping):
                by_name = value.get("by_name")
                if isinstance(by_name, Mapping) and by_name:
                    return True
            return False

        missing = [kind for kind in required_specs if not _has_entries(kind)]
        if not missing:
            self._shoper_taxonomy_cache = dict(cache)
            self._refresh_default_availability_from_cache()
            return self._shoper_taxonomy_cache

        client = getattr(self, "shoper_client", None)
        if client is None:
            raise RuntimeError(
                "Brak klienta Shoper – nie można pobrać słowników produktów"
            )

        def _iter_items(items: Iterable[Any]) -> Iterable[Mapping[str, Any]]:
            for item in items:
                if isinstance(item, Mapping):
                    yield item
                    children = item.get("children")
                    if isinstance(children, (list, tuple, set)):
                        yield from _iter_items(children)

        def _collect_strings(value: Any) -> Iterable[str]:
            if isinstance(value, str):
                stripped = value.strip()
                if stripped:
                    yield stripped
            elif isinstance(value, Mapping):
                for element in value.values():
                    yield from _collect_strings(element)
            elif isinstance(value, (list, tuple, set)):
                for element in value:
                    yield from _collect_strings(element)

        def _normalize_taxonomy_key(value: Any) -> str:
            if value is None:
                return ""
            if isinstance(value, str):
                text = value
            else:
                text = str(value)
            text = unicodedata.normalize("NFKD", text)
            text = "".join(ch for ch in text if not unicodedata.combining(ch))
            return text.strip().lower()

        def _coerce_int(value: Any) -> Optional[int]:
            try:
                if isinstance(value, bool):
                    return int(value)
                if isinstance(value, (int, float)):
                    return int(value)
                if isinstance(value, str):
                    stripped = value.strip()
                    if not stripped:
                        return None
                    return int(float(stripped))
            except (TypeError, ValueError):
                return None
            return None

        updated_cache: dict[str, Mapping[str, Any] | dict[str, Any]] = dict(cache)
        default_name_keys = (
            "name",
            "label",
            "title",
            "text",
            "value",
            "code",
            "symbol",
        )

        def _fetch_taxonomy_items(endpoint: str) -> list[Any]:
            collected: list[Any] = []
            seen_pages: set[int] = set()
            next_params: Optional[dict[str, Any]] = None

            def _extract_items(response: Any) -> list[Any]:
                if isinstance(response, Mapping):
                    for key in ("list", "items", "data", "results"):
                        raw_items = response.get(key)
                        if isinstance(raw_items, (list, tuple, set)):
                            return list(raw_items)
                    tree = response.get("tree")
                    if isinstance(tree, (list, tuple, set)):
                        return list(tree)
                    return []
                if isinstance(response, (list, tuple, set)):
                    return list(response)
                return []

            def _coerce_page(value: Any) -> Optional[int]:
                if isinstance(value, bool):
                    return None
                return _coerce_int(value)

            while True:
                if next_params:
                    response = client.get(endpoint, params=next_params)
                else:
                    response = client.get(endpoint)

                items = _extract_items(response)
                if items:
                    collected.extend(items)

                next_page: Optional[int] = None
                current_page: Optional[int] = None
                total_pages: Optional[int] = None

                if isinstance(response, Mapping):
                    current_page = _coerce_page(response.get("page"))
                    total_pages = _coerce_page(response.get("pages"))

                    pagination = response.get("pagination")
                    if isinstance(pagination, Mapping):
                        current_page = current_page or _coerce_page(
                            pagination.get("page")
                            or pagination.get("current")
                            or pagination.get("current_page")
                        )
                        total_pages = total_pages or _coerce_page(
                            pagination.get("pages")
                            or pagination.get("total")
                            or pagination.get("total_pages")
                        )

                        candidate = pagination.get("next_page") or pagination.get("next")
                        if isinstance(candidate, Mapping):
                            candidate = (
                                candidate.get("page")
                                or candidate.get("number")
                                or candidate.get("value")
                            )
                        if not isinstance(candidate, bool):
                            next_page = _coerce_page(candidate)

                    if next_page is None:
                        candidate = response.get("next_page") or response.get("next")
                        if isinstance(candidate, Mapping):
                            candidate = (
                                candidate.get("page")
                                or candidate.get("number")
                                or candidate.get("value")
                            )
                        if not isinstance(candidate, bool):
                            next_page = _coerce_page(candidate)

                    if next_page is None and current_page is not None and total_pages is not None:
                        if current_page < total_pages:
                            next_page = current_page + 1

                if current_page is not None:
                    seen_pages.add(current_page)

                if (
                    next_page is not None
                    and next_page not in seen_pages
                    and next_page != (next_params or {}).get("page")
                ):
                    seen_pages.add(next_page)
                    next_params = {"page": next_page}
                    continue

                break

            return collected

        for kind in missing:
            spec = required_specs[kind]
            items = _fetch_taxonomy_items(spec["endpoint"])

            by_id: dict[int, Mapping[str, Any]] = {}
            by_name: dict[str, int] = {}
            aliases: dict[str, int] = {}
            default_id: Optional[int] = None
            available_id: Optional[int] = None
            available_label: Optional[str] = None
            available_score: float = float("-inf")

            for entry in _iter_items(items):
                raw_id = (
                    entry.get(spec["id_field"]) or entry.get("id") or entry.get("value")
                )
                coerced_id = _coerce_int(raw_id)
                if coerced_id is None:
                    continue
                by_id[coerced_id] = entry
                aliases[str(coerced_id)] = coerced_id
                if entry.get("default") or entry.get("is_default"):
                    default_id = coerced_id

                names: set[str] = set()
                for key in default_name_keys:
                    if key in entry:
                        names.update(_collect_strings(entry.get(key)))
                if "translations" in entry:
                    names.update(_collect_strings(entry.get("translations")))
                if "name" not in entry and "translation" in entry:
                    names.update(_collect_strings(entry.get("translation")))

                if kind == "availability" and names:
                    entry_best_score = float("-inf")
                    entry_best_label: Optional[str] = None
                    for candidate_name in names:
                        score = _score_availability_label(candidate_name)
                        if score == float("-inf"):
                            continue
                        stripped_candidate = str(candidate_name).strip()
                        if not stripped_candidate:
                            continue
                        if score > entry_best_score:
                            entry_best_score = score
                            entry_best_label = stripped_candidate
                    if entry_best_label is not None and entry_best_score > available_score:
                        available_id = coerced_id
                        available_label = entry_best_label
                        available_score = entry_best_score

                for name in names:
                    normalized = _normalize_taxonomy_key(name)
                    if not normalized:
                        continue
                    if name not in by_name:
                        by_name[name] = coerced_id
                    aliases.setdefault(normalized, coerced_id)

            mapping: dict[str, Any] = {"by_id": by_id, "by_name": by_name}
            if aliases:
                mapping["aliases"] = aliases
            if default_id is not None:
                mapping["default"] = default_id
            if kind == "availability":
                if available_id is not None:
                    mapping["available_id"] = available_id
                if available_label:
                    mapping["available_label"] = available_label
                if available_score > float("-inf"):
                    mapping["available_priority"] = available_score
            if "default" not in mapping and by_id:
                try:
                    mapping["default"] = next(iter(sorted(by_id)))
                except TypeError:
                    mapping["default"] = next(iter(by_id))
            if (
                kind == "availability"
                and mapping.get("available_id") in (None, "")
                and by_id
            ):
                try:
                    fallback_available = next(iter(sorted(by_id)))
                except TypeError:
                    fallback_available = next(iter(by_id))
                mapping["available_id"] = fallback_available
                if not mapping.get("available_label"):
                    candidate_entry = by_id.get(fallback_available)
                    if isinstance(candidate_entry, Mapping):
                        labels = list(_collect_strings(candidate_entry.get("name")))
                        if not labels:
                            labels = list(_collect_strings(candidate_entry))
                        if labels:
                            mapping["available_label"] = labels[0]
            updated_cache[kind] = mapping

        self._shoper_taxonomy_cache = updated_cache
        self._refresh_default_availability_from_cache()
        return self._shoper_taxonomy_cache

    def _build_shoper_payload(self, card: dict) -> dict:
        """Map internal card data to the structure expected by the API."""
        # Name taken strictly from the 'Nazwa' field in the editor
        name = str(card.get("nazwa") or "").strip()

        product_code = card.get("product_code")
        if isinstance(product_code, str):
            product_code = product_code.strip()

        def _coerce_float(value: Any, *, default: float = 0.0) -> float:
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str):
                raw = value.strip()
                if not raw:
                    return default
                normalized = raw.replace("−", "-").replace(",", ".")
                cleaned = re.sub(r"[^0-9.\-]", "", normalized)
                if cleaned.count("-") > 1:
                    cleaned = cleaned.replace("-", "")
                if "-" in cleaned and not cleaned.startswith("-"):
                    cleaned = cleaned.replace("-", "")
                if cleaned.count(".") > 1:
                    dot_parts = cleaned.split(".")
                    cleaned = "".join(dot_parts[:-1]) + "." + dot_parts[-1]
                if not re.search(r"\d", cleaned):
                    return default
                if cleaned in {"-", ".", "-."}:
                    return default
                try:
                    return float(cleaned)
                except ValueError:
                    return default
            return default

        def _coerce_int(value: Any, *, default: int = 0) -> int:
            if isinstance(value, bool):
                return int(value)
            if isinstance(value, (int, float)):
                try:
                    return int(value)
                except (TypeError, ValueError):
                    return default
            if isinstance(value, str):
                raw = value.strip()
                if not raw:
                    return default
                try:
                    return int(float(raw))
                except ValueError:
                    return default
            return default

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
                match = re.search(r"(?:^|\s)([-+]?\d+)(?=\s|$)", raw)
                if match:
                    try:
                        return int(match.group(1))
                    except ValueError:
                        return None
                try:
                    return int(float(raw))
                except ValueError:
                    return None
            return None

        def _normalize_taxonomy_key(value: Any) -> str:
            if value is None:
                return ""
            if isinstance(value, str):
                text = value
            else:
                text = str(value)
            text = unicodedata.normalize("NFKD", text)
            text = "".join(ch for ch in text if not unicodedata.combining(ch))
            return text.strip().lower()

        taxonomy_cache = getattr(self, "_shoper_taxonomy_cache", {}) or {}
        taxonomy_lookup_cache: dict[str, dict[str, Any]] = {}

        def _taxonomy_lookup(kind: str) -> dict[str, Any]:
            if kind in taxonomy_lookup_cache:
                return taxonomy_lookup_cache[kind]
            mapping = taxonomy_cache.get(kind) if isinstance(taxonomy_cache, Mapping) else {}
            lookup: dict[str, Any] = {}
            candidates: Mapping[str, Any] | None = None
            if isinstance(mapping, Mapping):
                candidates = mapping.get("by_name")
                if not isinstance(candidates, Mapping):
                    candidates = {
                        key: value
                        for key, value in mapping.items()
                        if isinstance(key, str) and key not in {"by_id", "default", "aliases"}
                    }
            if isinstance(candidates, Mapping):
                for key, value in candidates.items():
                    normalized_key = _normalize_taxonomy_key(key)
                    if normalized_key:
                        lookup[normalized_key] = value
            taxonomy_lookup_cache[kind] = lookup
            return lookup

        def _resolve_taxonomy_id(kind: str, raw_value: Any) -> Optional[int]:
            mapping = taxonomy_cache.get(kind) if isinstance(taxonomy_cache, Mapping) else {}
            coerced = _coerce_optional_int(raw_value)
            if coerced is not None and isinstance(mapping, Mapping):
                by_id = mapping.get("by_id") if isinstance(mapping, Mapping) else None
                if isinstance(by_id, Mapping) and coerced in by_id:
                    return coerced
                aliases_map = mapping.get("aliases") if isinstance(mapping, Mapping) else None
                if isinstance(aliases_map, Mapping):
                    normalized_numeric = _normalize_taxonomy_key(str(raw_value))
                    candidate_keys = []
                    if normalized_numeric:
                        candidate_keys.append(normalized_numeric)
                    candidate_keys.append(str(coerced))
                    for candidate_key in candidate_keys:
                        alias_target = aliases_map.get(candidate_key)
                        if alias_target is None:
                            for key, value in aliases_map.items():
                                if _normalize_taxonomy_key(key) == candidate_key:
                                    alias_target = value
                                    break
                        if _coerce_optional_int(alias_target) == coerced:
                            return coerced
            normalized_value = _normalize_taxonomy_key(raw_value)
            has_explicit_value = False
            if isinstance(raw_value, str):
                has_explicit_value = bool(raw_value.strip())
            elif raw_value not in (None,):
                has_explicit_value = True

            if normalized_value:
                lookup = _taxonomy_lookup(kind)
                aliases = None
                if isinstance(mapping, Mapping):
                    aliases = mapping.get("aliases")

                def _try_lookup(normalized_key: str) -> Optional[int]:
                    if not normalized_key:
                        return None
                    candidate = lookup.get(normalized_key)
                    if candidate is not None:
                        resolved = _coerce_optional_int(candidate)
                        if resolved is not None:
                            return resolved
                    if isinstance(aliases, Mapping):
                        alias_target = aliases.get(normalized_key)
                        if alias_target is None:
                            for key, value in aliases.items():
                                if _normalize_taxonomy_key(key) == normalized_key:
                                    alias_target = value
                                    break
                        if alias_target is not None and alias_target != raw_value:
                            resolved = _resolve_taxonomy_id(kind, alias_target)
                            if resolved is not None:
                                return resolved
                    return None

                resolved = _try_lookup(normalized_value)
                if resolved is not None:
                    return resolved

                if kind == "category" and isinstance(raw_value, str):
                    path_segments = [
                        segment.strip()
                        for segment in re.split(r"[>/]", raw_value)
                        if isinstance(segment, str) and segment.strip()
                    ]
                    if path_segments:
                        for start_index in range(len(path_segments) - 1, -1, -1):
                            candidate_value = " > ".join(path_segments[start_index:])
                            normalized_candidate = _normalize_taxonomy_key(candidate_value)
                            if normalized_candidate == normalized_value:
                                continue
                            resolved = _try_lookup(normalized_candidate)
                            if resolved is not None:
                                return resolved

            fallback_candidates: list[Any] = []
            if kind == "availability" and not has_explicit_value:
                if isinstance(mapping, Mapping):
                    fallback_candidates.append(mapping.get("available_id"))
                csv_default = csv_utils.get_default_availability_id()
                if csv_default is not None:
                    fallback_candidates.append(csv_default)
            if not has_explicit_value and isinstance(mapping, Mapping):
                fallback_candidates.append(mapping.get("default"))
                by_id_map = mapping.get("by_id")
                if isinstance(by_id_map, Mapping) and by_id_map:
                    try:
                        first_candidate = next(iter(sorted(by_id_map)))
                    except TypeError:
                        first_candidate = next(iter(by_id_map))
                    if first_candidate not in fallback_candidates:
                        fallback_candidates.append(first_candidate)
            for candidate in fallback_candidates:
                resolved = _coerce_optional_int(candidate)
                if resolved is not None:
                    return resolved
            return None

        translation_locale = (
            card.get("translation_locale")
            or card.get("locale")
            or getattr(self, "default_translation_locale", None)
            or DEFAULT_TRANSLATION_LOCALE
        )
        if isinstance(translation_locale, str):
            translation_locale = translation_locale.strip().replace("-", "_") or DEFAULT_TRANSLATION_LOCALE
        else:
            translation_locale = DEFAULT_TRANSLATION_LOCALE
        if "_" in translation_locale:
            lang_part, country_part = translation_locale.split("_", 1)
            translation_locale = f"{lang_part.lower()}_{country_part.upper()}"
        else:
            translation_locale = translation_locale.lower()

        translation_entry: dict[str, Any] = {
            "name": name or (product_code or ""),
        }

        def _store_translation(
            entry: dict[str, Any], field: str, value: Any, *, overwrite: bool = False
        ) -> None:
            if isinstance(value, str):
                trimmed = value.strip()
                if not trimmed:
                    return
                existing = entry.get(field)
                if overwrite or not isinstance(existing, str) or not existing.strip():
                    entry[field] = trimmed

        translations_data = card.get("translations")
        translation_candidates: list[
            tuple[Optional[str], Optional[int], Mapping[str, Any]]
        ] = []

        def _collect_translation_candidate(
            locale_hint: Any, data: Mapping[str, Any]
        ) -> None:
            normalized_hint = _normalize_locale_code(locale_hint)
            language_id: Optional[int] = None
            for key in ("language_id", "lang_id"):
                language_id = _coerce_optional_int(data.get(key))
                if language_id is not None:
                    break
            language_info = data.get("language")
            if language_id is None and isinstance(language_info, Mapping):
                for key in ("language_id", "id"):
                    language_id = _coerce_optional_int(language_info.get(key))
                    if language_id is not None:
                        break
                if normalized_hint is None:
                    normalized_hint = _normalize_locale_code(
                        language_info.get("code")
                        or language_info.get("language_code")
                        or language_info.get("lang_code")
                        or language_info.get("lang")
                        or language_info.get("locale")
                    )

            explicit_locale: Optional[str] = None
            for key in ("language_code", "lang_code", "lang", "language", "locale", "code"):
                if key not in data:
                    continue
                value = data.get(key)
                if isinstance(value, Mapping):
                    value = (
                        value.get("code")
                        or value.get("language_code")
                        or value.get("lang_code")
                        or value.get("lang")
                        or value.get("locale")
                    )
                explicit_locale = _normalize_locale_code(value)
                if explicit_locale:
                    break

            translation_candidates.append((explicit_locale or normalized_hint, language_id, data))

        if isinstance(translations_data, Mapping):
            for key, value in translations_data.items():
                if key == "list" and isinstance(value, Iterable) and not isinstance(
                    value, (str, bytes, bytearray)
                ):
                    for element in value:
                        if isinstance(element, Mapping):
                            _collect_translation_candidate(None, element)
                elif isinstance(value, Mapping):
                    _collect_translation_candidate(key, value)
        elif isinstance(translations_data, Iterable) and not isinstance(
            translations_data, (str, bytes, bytearray)
        ):
            for element in translations_data:
                if isinstance(element, Mapping):
                    _collect_translation_candidate(None, element)

        languages_map = self._ensure_shoper_languages_map()
        language_id_by_code = (
            languages_map.get("by_code") if isinstance(languages_map, Mapping) else {}
        )
        if not isinstance(language_id_by_code, Mapping):
            language_id_by_code = {}
        language_code_by_id = (
            languages_map.get("by_id") if isinstance(languages_map, Mapping) else {}
        )
        if not isinstance(language_code_by_id, Mapping):
            language_code_by_id = {}

        translations_by_locale: dict[str, dict[str, Any]] = {
            translation_locale: translation_entry
        }
        locale_language_ids: dict[str, Optional[int]] = {}

        translation_source: Optional[Mapping[str, Any]] = None
        for locale_candidate, language_id, data in translation_candidates:
            resolved_locale = locale_candidate or (
                language_code_by_id.get(language_id)
                if language_id is not None
                else None
            )
            if resolved_locale == translation_locale:
                translation_source = data
                if language_id is not None:
                    locale_language_ids[translation_locale] = language_id
                break

        if translation_source:
            for field in (
                "short_description",
                "description",
                "seo_title",
                "seo_description",
                "seo_keywords",
                "permalink",
            ):
                _store_translation(translation_entry, field, translation_source.get(field))

        for field in (
            "short_description",
            "description",
            "seo_title",
            "seo_description",
            "seo_keywords",
            "permalink",
        ):
            _store_translation(translation_entry, field, card.get(field))

        for locale_candidate, language_id, data in translation_candidates:
            resolved_locale = locale_candidate or (
                language_code_by_id.get(language_id)
                if language_id is not None
                else None
            )
            if not resolved_locale:
                continue
            entry = translations_by_locale.get(resolved_locale)
            if entry is None:
                entry = {"name": name or (product_code or "")}
                translations_by_locale[resolved_locale] = entry
            if data is translation_source and resolved_locale == translation_locale:
                continue
            for field in (
                "name",
                "short_description",
                "description",
                "seo_title",
                "seo_description",
                "seo_keywords",
                "permalink",
            ):
                overwrite = field == "name" and resolved_locale != translation_locale
                _store_translation(entry, field, data.get(field), overwrite=overwrite)
            if language_id is not None:
                locale_language_ids[resolved_locale] = language_id
            elif resolved_locale not in locale_language_ids:
                locale_language_ids[resolved_locale] = language_id_by_code.get(
                    resolved_locale
                )

        locale_language_ids.setdefault(
            translation_locale, language_id_by_code.get(translation_locale)
        )

        translations_payload: list[dict[str, Any]] = []
        has_selected_locale = False
        for locale_key, entry in translations_by_locale.items():
            language_id = locale_language_ids.get(locale_key)
            if language_id is None:
                language_id = language_id_by_code.get(locale_key)
            if language_id is None and "_" not in locale_key:
                expanded_locale = f"{locale_key.lower()}_{locale_key.upper()}"
                language_id = language_id_by_code.get(expanded_locale)
            if language_id is None:
                continue
            normalized_entry = dict(entry)
            # Force the proper product name rather than falling back to code
            normalized_entry["name"] = (name or (product_code or ""))
            normalized_entry["language_id"] = int(language_id)
            normalized_entry["language_code"] = locale_key
            translations_payload.append(normalized_entry)
            if locale_key == translation_locale:
                has_selected_locale = True

        if not has_selected_locale:
            raise RuntimeError(
                "Nieznany identyfikator języka Shoper dla "
                f"'{translation_locale}'. Dodaj mapowanie języka poprzez "
                "SHOPER_LANGUAGE_OVERRIDES lub ustaw zmienne "
                "SHOPER_LANGUAGE_CODE/SHOPER_LANGUAGE_ID."
            )

        price_value = _coerce_float(card.get("price", card.get("cena")), default=0.0)

        payload = {
            "product_code": product_code,
            "active": _coerce_int(card.get("active", 1), default=1),
            "price": price_value,
            "translations": translations_payload,
        }

        def _has_value(value: Any) -> bool:
            if value is None:
                return False
            if isinstance(value, str):
                return bool(value.strip())
            if isinstance(value, (list, tuple, set, dict)):
                return bool(value)
            return True

        priority = card.get("priority")
        if _has_value(priority):
            payload["priority"] = _coerce_int(priority)

        weight = card.get("weight")
        weight_value = _coerce_float(weight, default=0.01)
        if weight_value:
            payload["weight"] = weight_value

        other_price = card.get("other_price")
        if _has_value(other_price):
            payload["other_price"] = other_price

        warehouse_code = card.get("warehouse_code")
        if isinstance(warehouse_code, str):
            warehouse_code = warehouse_code.strip()
        if _has_value(warehouse_code):
            payload["warehouse_code"] = warehouse_code

        stock_value = card.get("ilość")
        if stock_value in (None, ""):
            stock_value = card.get("stock")
        if stock_value in (None, ""):
            stock_value = 1
        stock_block: dict[str, Any] = {
            "stock": _coerce_int(stock_value, default=1),
            "price": price_value,
        }
        warnlevel = card.get("stock_warnlevel")
        if _has_value(warnlevel):
            coerced_warn = _coerce_int(warnlevel)
            if coerced_warn:
                stock_block["warn_level"] = coerced_warn
        if stock_block:
            payload["stock"] = stock_block

        # Enrich with fields expected by store example schema
        # Duplicate code alongside product_code
        if product_code:
            payload["code"] = product_code
            if isinstance(payload.get("stock"), dict):
                payload["stock"].setdefault("code", product_code)

        # EAN defaults
        ean_value = card.get("ean")
        if isinstance(ean_value, str):
            ean_value = ean_value.strip()
        if not _has_value(ean_value):
            ean_value = ""
        payload.setdefault("ean", ean_value)
        if isinstance(payload.get("stock"), dict):
            payload["stock"].setdefault("ean", ean_value)

        # Loyalty/new/bestseller/type/unit price calc defaults
        payload.setdefault("in_loyalty", 0)
        payload.setdefault("bestseller", 0)
        payload.setdefault("newproduct", 0)
        payload.setdefault("unit_price_calculation", 0)
        payload.setdefault("type", 0)

        # Other price and pkwiu defaults
        payload.setdefault("other_price", "0.00")
        payload.setdefault("pkwiu", payload.get("pkwiu", ""))

        # Categories list mirrors category_id if set
        if isinstance(payload.get("category_id"), (int, float)):
            try:
                payload["categories"] = [int(payload["category_id"]) ]
            except Exception:
                pass

        # Ensure collections/tags arrays exist (even empty)
        payload.setdefault("collections", payload.get("collections", []))
        payload.setdefault("tags", payload.get("tags", []))

        # Stock defaults to active and delivery id
        if isinstance(payload.get("stock"), dict):
            payload["stock"].setdefault("active", 1)
            try:
                default_delivery = os.getenv("SHOPER_DEFAULT_DELIVERY_ID", "3").strip()
                if default_delivery:
                    payload["stock"].setdefault("delivery_id", int(float(default_delivery)))
            except Exception:
                pass

            # Add additional_codes.producer from card number if available
            producer_num = card.get("numer")
            if _has_value(producer_num):
                try:
                    producer_text = str(producer_num).strip()
                    add_codes = payload["stock"].setdefault("additional_codes", {})
                    if isinstance(add_codes, dict):
                        add_codes.setdefault("producer", producer_text)
                except Exception:
                    pass
            # Mirror top-level additional_producer for convenience
            if _has_value(producer_num):
                payload.setdefault("additional_producer", str(producer_num).strip())

        # Optional fields present in example responses
        payload.setdefault("promo_price", None)
        payload.setdefault("options", [])
        payload.setdefault("related", [])
        payload.setdefault("feeds_excludes", [])
        payload.setdefault("is_product_of_day", False)
        # Neutral defaults (server may override)
        if "currency_id" not in payload:
            payload["currency_id"] = None
        if "gauge_id" not in payload:
            payload["gauge_id"] = None

        for field in ("pkwiu",):
            value = card.get(field)
            if isinstance(value, str):
                value = value.strip()
            if _has_value(value):
                payload[field] = value

        def _iter_taxonomy_candidate_values(
            candidate: Any,
            *,
            target_field: str,
            legacy_field: str,
            cache_key: str,
        ) -> list[Any]:
            if not isinstance(candidate, Mapping):
                return [candidate]

            values: list[Any] = []
            possible_keys = [
                target_field,
                legacy_field,
                f"{cache_key}_id",
                "value",
                "name",
                "id",
            ]

            for key in possible_keys:
                if not key:
                    continue
                if key in candidate:
                    value = candidate[key]
                    if isinstance(value, Mapping):
                        continue
                    if value not in values:
                        values.append(value)

            if not values:
                for value in candidate.values():
                    if isinstance(value, Mapping):
                        continue
                    if value not in values:
                        values.append(value)

            return values or [candidate]

        taxonomy_fields = (
            ("category_id", "category", "category"),
            ("producer_id", "producer", "producer"),
            ("tax_id", "vat", "tax"),
            ("unit_id", "unit", "unit"),
            ("availability_id", "availability", "availability"),
        )

        if any(
            _has_value(card.get(target_field))
            or _has_value(card.get(legacy_field))
            for target_field, legacy_field, _ in taxonomy_fields
        ):
            taxonomy_cache = self._ensure_shoper_taxonomy_cache()
            taxonomy_lookup_cache.clear()

        taxonomy_labels = {
            "category": "kategorii",
            "producer": "producenta",
            "tax": "stawki VAT",
            "unit": "jednostki",
            "availability": "dostępności",
        }
        missing_required: list[tuple[str, Any]] = []

        for target_field, legacy_field, cache_key in taxonomy_fields:
            candidates: list[Any] = []
            target_value = card.get(target_field)
            legacy_value = card.get(legacy_field)
            if _has_value(target_value):
                candidates.append(target_value)
            if _has_value(legacy_value):
                candidates.append(legacy_value)

            resolved_value: Optional[int] = None
            for candidate in candidates:
                candidate_values = _iter_taxonomy_candidate_values(
                    candidate,
                    target_field=target_field,
                    legacy_field=legacy_field,
                    cache_key=cache_key,
                )
                for candidate_value in candidate_values:
                    resolved_value = _resolve_taxonomy_id(cache_key, candidate_value)
                    if resolved_value is not None:
                        break
                if resolved_value is not None:
                    break

            if resolved_value is None and not candidates:
                resolved_value = _resolve_taxonomy_id(cache_key, None)

            if resolved_value is not None:
                payload[target_field] = resolved_value
                if target_field == "availability_id":
                    stock_entry = payload.get("stock")
                    if isinstance(stock_entry, dict):
                        stock_entry["availability_id"] = resolved_value
                continue

            if candidates:
                missing_required.append((cache_key, candidates[0]))

        if missing_required:
            details = []
            for kind, value in missing_required:
                label = taxonomy_labels.get(kind, kind)
                text = value if isinstance(value, str) else str(value)
                details.append(f"{label}: {text}")
            message = "Nie znaleziono identyfikatorów Shoper dla: " + ", ".join(details)
            raise RuntimeError(message)

        # Mirror categories list after category_id was resolved
        if isinstance(payload.get("category_id"), (int, float)):
            try:
                payload["categories"] = [int(payload["category_id"]) ]
            except Exception:
                pass

        # Enforce default availability_id if not explicitly set by taxonomy mapping
        try:
            default_av_raw = os.getenv("SHOPER_DEFAULT_AVAILABILITY_ID", "4").strip()
            default_av = int(float(default_av_raw)) if default_av_raw else 4
        except Exception:
            default_av = 4
        stock_entry = payload.get("stock") if isinstance(payload.get("stock"), dict) else None
        top_av = payload.get("availability_id")
        stock_av = stock_entry.get("availability_id") if isinstance(stock_entry, dict) else None
        if (top_av in (None, "")) and (stock_av in (None, "")):
            payload["availability_id"] = default_av
            if isinstance(stock_entry, dict):
                stock_entry["availability_id"] = default_av

        group_value = card.get("group_id")
        if _has_value(group_value):
            coerced_group = _coerce_optional_int(group_value)
            payload["group_id"] = coerced_group if coerced_group is not None else group_value

        if card.get("virtual"):
            payload["virtual"] = bool(card.get("virtual"))

        for field in ("tags", "collections", "additional_codes"):
            values = card.get(field)
            if isinstance(values, (list, tuple, set)):
                cleaned = [str(item).strip() for item in values if str(item).strip()]
            elif isinstance(values, str):
                cleaned = [part.strip() for part in re.split(r"[;,]", values) if part.strip()]
            else:
                cleaned = []
            if cleaned:
                payload[field] = cleaned

        dimensions = card.get("dimensions")
        if isinstance(dimensions, Mapping):
            dims: dict[str, float] = {}
            for key in ("width", "height", "length"):
                value = dimensions.get(key)
                if not _has_value(value):
                    continue
                try:
                    dims[key] = float(value)
                except (TypeError, ValueError):
                    continue
            if dims:
                payload["dimensions"] = dims
                # Also expose legacy flat fields similar to example
                def _fmt4(val: float) -> str:
                    try:
                        return f"{float(val):0.4f}"
                    except Exception:
                        return "0.0000"
                if "width" in dims:
                    payload.setdefault("dimension_w", _fmt4(dims["width"]))
                if "height" in dims:
                    payload.setdefault("dimension_h", _fmt4(dims["height"]))
                if "length" in dims:
                    payload.setdefault("dimension_l", _fmt4(dims["length"]))
                payload.setdefault("vol_weight", "0.0000")

        image_value = card.get("image1")
        # Build images list from a single value or an iterable.
        # Supports absolute http/https URLs and filenames joined with SHOPER_IMAGE_BASE/SHOPER_IMAGE_BASE_URL.
        base_images_url = (
            os.getenv("SHOPER_IMAGE_BASE_URL", "")
            or os.getenv("SHOPER_IMAGE_BASE", "")
        ).strip().rstrip("/")

        def _resolve_image_url(value: str) -> str | None:
            if not isinstance(value, str):
                return None
            candidate = value.strip()
            if not candidate:
                return None
            parsed = urlparse(candidate)
            if parsed.scheme in ("http", "https"):
                return candidate
            if base_images_url and not parsed.scheme:
                # Treat as filename or relative path - join with base URL
                return f"{base_images_url}/{candidate.lstrip('/')}"
            return None

        images_list: list[str] = []
        if isinstance(image_value, str):
            resolved = _resolve_image_url(image_value)
            if resolved:
                images_list.append(resolved)
        elif isinstance(image_value, (list, tuple, set)):
            for item in image_value:
                resolved = _resolve_image_url(item)
                if resolved:
                    images_list.append(resolved)
        if images_list:
            payload["images"] = images_list
        return payload

    def _extract_order_products(self, order: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
        """Return a flat list of product mappings from ``order``."""

        if not isinstance(order, Mapping):
            return []

        def _coerce_products(value: Any) -> list[Mapping[str, Any]]:
            if not value:
                return []
            if isinstance(value, Mapping):
                for key in ("list", "items", "data", "values"):
                    if key in value:
                        nested = _coerce_products(value[key])
                        if nested:
                            return nested
                results: list[Mapping[str, Any]] = []
                if any(
                    key in value
                    for key in ("name", "product_id", "quantity", "warehouse_code", "product_code")
                ):
                    results.append(value)
                for subvalue in value.values():
                    if isinstance(subvalue, (Mapping, list, tuple, set)):
                        results.extend(_coerce_products(subvalue))
                return [item for item in results if isinstance(item, Mapping)]
            if isinstance(value, (list, tuple, set)):
                collected: list[Mapping[str, Any]] = []
                for item in value:
                    collected.extend(_coerce_products(item))
                return collected
            return []

        for container_key in ("products", "order_products", "items", "orderItems"):
            raw = order.get(container_key)
            if not raw:
                continue
            products = _coerce_products(raw)
            if products:
                return products
        return []

    def _prepare_order_items(
        self, order: Mapping[str, Any] | None
    ) -> tuple[list[dict[str, Any]], dict[str, str], int]:
        """Normalise order data into UI-friendly item structures."""

        items: list[dict[str, Any]] = []
        code_map: dict[str, str] = {}
        total_quantity = 0

        for item in self._extract_order_products(order):
            if not isinstance(item, Mapping):
                continue

            code_raw = (
                item.get("warehouse_code")
                or item.get("product_code")
                or item.get("code", "")
            )
            if isinstance(code_raw, (list, tuple, set)):
                code_display = ";".join(str(c).strip() for c in code_raw if str(c).strip())
            else:
                code_display = str(code_raw or "")
            codes = [c.strip() for c in code_display.split(";") if c.strip()]
            locations = [self.location_from_code(code) for code in codes]
            location_text = "; ".join(l for l in locations if l)
            quantity = _coerce_quantity(item.get("quantity"))
            total_quantity += quantity
            product_code = csv_utils.infer_product_code(item)
            for code in codes:
                code_map[code] = product_code
            items.append(
                {
                    "name": item.get("name"),
                    "quantity": quantity,
                    "code": code_display,
                    "location": location_text,
                }
            )

        return items, code_map, total_quantity

    def show_orders(self, widget=None):
        """Display new orders with storage location hints."""
        try:
            if widget is None:
                widget = getattr(self, "orders_output", None)
            if widget is None:
                return
            status_filters = {"status_id[in]": "1,2,3,4"}
            logger.info(
                "Requesting Shoper orders with filters: %s",
                status_filters,
            )
            orders = self.shoper_client.list_orders(status_filters)
            orders_list_raw = orders.get("list", orders)
            if isinstance(orders_list_raw, Mapping):
                orders_list_raw = orders_list_raw.get("list", [])
            orders_list = [o for o in orders_list_raw if o]
            if orders_list:
                order_ids = [
                    order.get("order_id") or order.get("id")
                    for order in orders_list
                    if isinstance(order, Mapping)
                ]
                logger.info(
                    "Received %d Shoper orders, sample ids: %s",
                    len(orders_list),
                    order_ids[:5],
                )
            else:
                logger.info("Received 0 Shoper orders")
            self.pending_orders = orders_list
            choose_nearest_locations(orders_list, self.output_data)

            rendered_orders: list[dict[str, Any]] = []
            lines: list[str] = []

            for order in orders_list:
                oid = order.get("order_id") or order.get("id")
                title = f"Zamówienie #{oid}" if oid else "Zamówienie"
                status = (
                    order.get("status_label")
                    or order.get("status_name")
                    or order.get("status")
                    or order.get("order_status")
                )
                status_type = order.get("status_type")
                if isinstance(status_type, Mapping):
                    status_type = status_type.get("type") or status_type.get("id")
                if not status_type and isinstance(order.get("status"), Mapping):
                    status_type = order["status"].get("type")
                customer_name = ""
                # 1. Spróbuj pobrać dane z adresu rozliczeniowego (zgodnie z dokumentacją API)
                billing_address = order.get("billing_address")
                if isinstance(billing_address, Mapping):
                    customer_name = " ".join(
                        part for part in (billing_address.get("firstname"), billing_address.get("lastname")) if part
                    ).strip()

                # 2. Jeśli się nie uda, spróbuj z obiektu 'user'
                if not customer_name:
                    user = order.get("user")
                    if isinstance(user, Mapping):
                        customer_name = " ".join(
                            part
                            for part in (
                                user.get("firstname") or user.get("first_name"),
                                user.get("lastname") or user.get("last_name"),
                            )
                            if part
                        ).strip()

                # 3. W ostateczności, spróbuj pola 'customer'
                if not customer_name:
                    customer = order.get("customer")
                    if isinstance(customer, str):
                        customer_name = customer.strip()


                created = (
                    order.get("order_date")
                    or order.get("created_at")
                    or order.get("date_add")
                    or order.get("date")
                )
                total_value = _format_order_total(order)

                items, code_map, total_quantity = self._prepare_order_items(order)
                lines.append(title)
                for product in items:
                    lines.append(
                        " - {name} x{quantity} [{code}] {location}".format(
                            name=product.get("name"),
                            quantity=product.get("quantity"),
                            code=product.get("code", ""),
                            location=product.get("location", ""),
                        )
                    )

                rendered_orders.append(
                    {
                        "title": title,
                        "status": status,
                        "status_type": status_type,
                        "customer": customer_name,
                        "created": created,
                        "total": total_value,
                        "quantity": total_quantity,
                        "items": items,
                        "data": order,
                        "_code_map": code_map,
                    }
                )

            if hasattr(widget, "render_orders"):
                widget.render_orders(rendered_orders)
            elif hasattr(widget, "delete"):
                widget.delete("1.0", tk.END)
                widget.insert(tk.END, "\n".join(lines))
        except (requests.RequestException, RuntimeError) as e:
            logger.exception("Failed to list orders")
            messagebox.showerror("Błąd", str(e))

    @staticmethod
    def _candidate_product_codes(item: Mapping[str, Any] | None) -> list[str]:
        """Return potential product codes for ``item`` preserving priority."""

        if not isinstance(item, Mapping):
            return []

        candidates: list[str] = []
        for key in ("code", "product_code", "producer_code"):
            value = str(item.get(key) or "").strip()
            if value and value not in candidates:
                candidates.append(value)

        inferred = csv_utils.infer_product_code(item)
        if inferred:
            normalized = str(inferred).strip()
            if normalized and normalized not in candidates:
                candidates.append(normalized)

        return candidates

    @staticmethod
    def _parse_warehouse_codes(value: Any) -> list[str]:
        """Split ``value`` into a list of unique warehouse codes."""

        if not value:
            return []

        if isinstance(value, (list, tuple, set)):
            raw_codes = value
        else:
            raw_codes = str(value).split(";")

        cleaned: list[str] = []
        for raw in raw_codes:
            code = str(raw).strip()
            if code and code not in cleaned:
                cleaned.append(code)

        return cleaned

    def show_order_details(self, entry: Mapping[str, Any] | None):
        """Display order details with a grid of selectable card thumbnails and diagnostic logging."""
        if not entry:
            return

        order = entry.get("data", {})
        oid = order.get("order_id") or order.get("id")
        title = f"Szczegóły zamówienia #{oid}" if oid else "Szczegóły zamówienia"

        top = ctk.CTkToplevel(self.root)
        top.transient(self.root)
        top.grab_set()
        top.lift()
        top.focus_force()
        top.protocol("WM_DELETE_WINDOW", top.destroy)
        top.geometry("900x700")
        top.title(title)
        top.configure(fg_color=BG_COLOR)

        # --- Nagłówek z danymi zamówienia ---
        header = ctk.CTkFrame(top, fg_color=BG_COLOR, corner_radius=0)
        header.pack(fill="x", padx=20, pady=(20, 10))
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(header, text=title, text_color=TEXT_COLOR, font=ctk.CTkFont(size=24, weight="bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        status_obj = entry.get("status")
        status_name = status_obj.get('name') if isinstance(status_obj, dict) else status_obj

        meta_info = { "Klient:": entry.get("customer"), "Data:": entry.get("created"), "Status:": status_name, "Wartość:": entry.get("total") }
        for i, (label, value) in enumerate(meta_info.items()):
            if value:
                ctk.CTkLabel(header, text=label, text_color="#AAAAAA", font=ctk.CTkFont(size=16)).grid(row=i + 1, column=0, sticky="w", padx=(0, 15))
                ctk.CTkLabel(header, text=str(value), text_color=TEXT_COLOR, font=ctk.CTkFont(size=16, weight="bold")).grid(row=i + 1, column=1, sticky="w")

        # --- Siatka z produktami ---
        items_frame = ctk.CTkScrollableFrame(top, fg_color=LIGHT_BG_COLOR)
        items_frame.pack(expand=True, fill="both", padx=20, pady=10)

        selection_vars = {}
        warehouse_map: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
        items = order.get("products", [])

        # --- LOGIKA DIAGNOSTYCZNA ---
        print("\n--- DIAGNOSTYKA DOPASOWANIA PRODUKTÓW ---")
        
        # Krok 1: Sprawdzenie, czy dane z store_export.csv są w ogóle załadowane
        self._ensure_store_cache()
        if not self.store_data:
            print("[BŁĄD KRYTYCZNY] Nie udało się zbudować lokalnego bufora produktów Shoper.")
            ctk.CTkLabel(items_frame, text="BŁĄD: Nie wczytano danych produktów z Shoper!", text_color="red").pack()
            return

        print(f"Załadowano {len(self.store_data)} produktów z API Shoper (cache).")
        sample_codes = list(self.store_data.keys())[:3]
        print(f"Przykładowe kody z cache: {sample_codes}")

        if not items:
            ctk.CTkLabel(items_frame, text="Brak produktów w zamówieniu.", font=ctk.CTkFont(size=16)).pack(pady=20)
        else:
            for i, item in enumerate(items):
                shoper_code = item.get("code")
                name = item.get("name", "Brak nazwy")
                quantity = _coerce_quantity(item.get('quantity'))

                print(f"\n-> Przetwarzanie produktu: '{name}'")
                print(f"   - Kod z API Shoper: '{shoper_code}'")

                # Upewniamy się, że porównujemy czyste kody (bez spacji itp.)
                clean_shoper_code = str(shoper_code).strip() if shoper_code else None
                product_codes = self._candidate_product_codes(item)
                warehouse_codes = self._parse_warehouse_codes(item.get("warehouse_code"))

                for code in product_codes:
                    bucket = warehouse_map[code]
                    if warehouse_codes:
                        existing = {entry.get("warehouse_code") for entry in bucket}
                        for warehouse_code in warehouse_codes:
                            if warehouse_code not in existing:
                                bucket.append({"warehouse_code": warehouse_code})
                                existing.add(warehouse_code)
                    elif not bucket:
                        warehouse_map.setdefault(code, [])

                product_info_map: dict[str, Mapping[str, Any]] = {}
                for lookup_code in product_codes:
                    product_info = self._get_store_product(lookup_code)
                    if product_info:
                        product_info_map[lookup_code] = product_info

                image_path = None
                for lookup_code, info in product_info_map.items():
                    image_path = csv_utils.product_image_url(info)
                    if image_path:
                        break

                if image_path:
                    image_path = _resolve_image_url(image_path)
                    print(f"   - ZNALEZIONO DOPASOWANIE! Link do obrazka: {image_path}")
                else:
                    print("   - NIE ZNALEZIONO OBRAZKA. Sprawdzam, dlaczego...")
                    cached_row = getattr(self, "store_data", {}).get(clean_shoper_code)
                    if cached_row:
                        print(
                            f"   - Błąd: Kod '{clean_shoper_code}' istnieje w buforze, ale w jego danych brakuje linku do obrazka."
                        )
                    else:
                        print(
                            f"   - Błąd: Kod '{clean_shoper_code}' nie został znaleziony w lokalnym buforze produktów."
                        )

                if product_codes:
                    print(f"   - Rozpoznane kody produktu: {product_codes}")
                if warehouse_codes:
                    print(f"   - Kody magazynowe: {warehouse_codes}")
                else:
                    print("   - Brak powiązanych kodów magazynowych.")

                card_frame = ctk.CTkFrame(items_frame, fg_color=BG_COLOR, corner_radius=8)

                thumb_label = ctk.CTkLabel(card_frame, text="?", width=120, height=168, fg_color=FIELD_BG_COLOR, corner_radius=6)
                thumb_label.pack(padx=10, pady=(10, 5))
                if image_path:
                    image_path = _resolve_image_url(image_path)
                    try:
                        img = _get_thumbnail(image_path, (120, 168))
                        if img:
                            photo = _create_image(img)
                            thumb_label.configure(image=photo, text="")
                            thumb_label.image = photo
                    except Exception as e:
                        logger.warning(f"Błąd ładowania miniaturki dla {shoper_code}: {e}")

                ctk.CTkLabel(card_frame, text=name, wraplength=120, font=ctk.CTkFont(size=12)).pack(padx=10, pady=(0, 5))

                var = tk.BooleanVar(value=True)
                chk = ctk.CTkCheckBox(card_frame, text=f"x{quantity}", variable=var, font=ctk.CTkFont(size=14, weight="bold"))
                chk.pack(pady=(0, 10))

                selection_data = {"var": var, "quantity": quantity, "lookup_keys": product_codes}
                if clean_shoper_code:
                    selection_vars[clean_shoper_code] = selection_data
                elif product_codes:
                    selection_vars[product_codes[0]] = selection_data

                row, col = divmod(i, 4)
                card_frame.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
                items_frame.grid_columnconfigure(col, weight=1)

        # ... (reszta kodu - przyciski - bez zmian) ...
        buttons = ctk.CTkFrame(top, fg_color="transparent")
        buttons.pack(fill="x", padx=20, pady=(10, 20))
        buttons.grid_columnconfigure((0, 1, 2), weight=1)

        def _mark_selected():
            products_to_sell = {
                code: data["quantity"]
                for code, data in selection_vars.items()
                if data["var"].get()
            }
            if not products_to_sell:
                messagebox.showwarning("Zamówienia", "Zaznacz przynajmniej jedną kartę.")
                return

            selected_codes: list[str] = []
            for product_code, quantity in products_to_sell.items():
                available = list(warehouse_map.get(product_code, []))
                taken = 0
                for option in available:
                    raw_code = option.get("warehouse_code") if isinstance(option, Mapping) else None
                    if not raw_code:
                        continue
                    code_text = str(raw_code).strip()
                    if not code_text or code_text in selected_codes:
                        continue
                    selected_codes.append(code_text)
                    taken += 1
                    if taken >= quantity:
                        break

            success = self.complete_order(
                order,
                selected_warehouses=selected_codes,
                product_counts=Counter(products_to_sell),
            )
            if success:
                top.destroy()

        def _print_list():
            any_unselected = any(not data["var"].get() for data in selection_vars.values())
            selected_codes: set[str] = set()
            for key, data in selection_vars.items():
                if not data["var"].get():
                    continue
                lookups = data.get("lookup_keys", []) or []
                for lookup in lookups:
                    if lookup:
                        selected_codes.add(lookup)
                if not lookups and key:
                    selected_codes.add(key)

            entry_for_print: Mapping[str, Any] | None = entry
            map_for_print: Mapping[str, list[dict[str, str]]] = warehouse_map

            if any_unselected and selected_codes:
                filtered_items: list[Mapping[str, Any]] = []
                for item in items:
                    for candidate in self._candidate_product_codes(item):
                        if candidate and candidate in selected_codes:
                            filtered_items.append(item)
                            break

                if not filtered_items:
                    messagebox.showwarning("Drukowanie", "Brak zaznaczonych pozycji do wydruku.")
                    return

                order_copy = dict(order)
                order_copy["products"] = filtered_items
                entry_for_print = dict(entry)
                entry_for_print["data"] = order_copy

                filtered_map: dict[str, list[dict[str, str]]] = {}
                for item in filtered_items:
                    for candidate in self._candidate_product_codes(item):
                        if not candidate:
                            continue
                        if candidate in warehouse_map:
                            filtered_map[candidate] = warehouse_map[candidate]
                        else:
                            filtered_map.setdefault(candidate, [])
                map_for_print = filtered_map or warehouse_map

            try:
                self.print_order_items(entry_for_print, product_code_to_image, map_for_print)
            except Exception as exc:
                logger.exception("Failed to generate print preview: %s", exc)
                messagebox.showerror("Drukowanie", "Nie udało się przygotować listy do wydruku.")

        self.create_button(buttons, text="Oznacz jako sprzedane", command=_mark_selected, fg_color=SAVE_BUTTON_COLOR).grid(row=0, column=0, padx=4, pady=8, sticky="ew")
        self.create_button(buttons, text="Drukuj listę", command=_print_list, fg_color=SAVE_BUTTON_COLOR).grid(row=0, column=1, padx=4, pady=8, sticky="ew")
        self.create_button(buttons, text="Zamknij", command=top.destroy, fg_color=NAV_BUTTON_COLOR).grid(row=0, column=2, padx=4, pady=8, sticky="ew")

    def complete_order(
        self,
        order: Mapping[str, Any],
        selected_warehouses: list[str] | None = None,
        product_counts: Mapping[str, int] | None = None,
    ) -> bool:
        """Finalize the order using Shoper API operations."""

        selected_codes = [
            str(code).strip()
            for code in (selected_warehouses or [])
            if str(code).strip()
        ]
        counts = Counter(product_counts or {})
        if not selected_codes and not counts:
            messagebox.showwarning("Błąd", "Nie wybrano żadnych kart do oznaczenia.")
            return False

        self.ensure_shoper_client()
        client = getattr(self, "shoper_client", None)
        if client is None:
            messagebox.showerror("Błąd", "Brak konfiguracji połączenia z API Shoper.")
            return False

        marked_count = 0
        if selected_codes:
            try:
                response = client.mark_products_sold(selected_codes)
            except Exception as exc:
                logger.exception("Failed to mark items as sold via Shoper: %s", exc)
                messagebox.showerror(
                    "Błąd",
                    _("Nie udało się oznaczyć kart jako sprzedanych: {err}").format(err=exc),
                )
                return False
            # Update local overlay so magazyn reflects SOLD immediately
            try:
                for c in selected_codes:
                    c2 = str(c).strip()
                    if c2:
                        self._locally_sold_codes.add(c2)
            except Exception:
                pass
            if isinstance(response, Mapping):
                raw_count = (
                    response.get("count")
                    or response.get("marked")
                    or response.get("success")
                )
                try:
                    marked_count = int(raw_count)
                except (TypeError, ValueError):
                    marked_count = len(selected_codes)
            else:
                marked_count = len(selected_codes)

        updated_products: list[str] = []
        for product_code, quantity in counts.items():
            try:
                qty_int = int(quantity)
            except (TypeError, ValueError):
                continue
            if qty_int <= 0:
                continue

            row = self._get_store_product(product_code)
            if not isinstance(row, Mapping):
                logger.warning(
                    "Product %s not found in Shoper when completing order", product_code
                )
                continue

            product_id = row.get("product_id") or row.get("id")
            if not product_id:
                logger.warning("Missing product_id for %s", product_code)
                continue

            stock_value = _coerce_quantity(row.get("stock"))
            new_stock = max(0, stock_value - qty_int)
            warn_level = row.get("warn_level") or row.get("stock_warnlevel")
            try:
                client.update_product_stock(product_id, new_stock, warn_level=warn_level)
            except Exception as exc:
                logger.exception("Failed to update stock for %s: %s", product_code, exc)
                messagebox.showerror(
                    "Błąd",
                    _(
                        "Nie udało się zaktualizować stanu produktu {code}: {err}"
                    ).format(code=product_code, err=exc),
                )
                return False

            updated_row = dict(row)
            updated_row["stock"] = str(new_stock)
            updated_row["product_id"] = str(product_id)
            self._cache_store_product(product_code, updated_row, persist=True)
            updated_products.append(product_code)

        if hasattr(self, "update_inventory_stats"):
            try:
                self.update_inventory_stats(force=True)
            except Exception:
                logger.exception("Failed to refresh inventory stats")

        if getattr(self, "inventory_service", None):
            try:
                self.inventory_service.fetch_snapshot()
            except Exception:
                logger.debug("Inventory snapshot refresh failed", exc_info=True)

        summary_parts: list[str] = []
        if marked_count:
            summary_parts.append(
                _("Oznaczono jako sprzedane: {count}").format(count=marked_count)
            )
        if updated_products:
            summary_parts.append(
                _("Zaktualizowano stany produktów: {codes}").format(
                    codes=", ".join(updated_products)
                )
            )
        if not summary_parts:
            summary_parts.append(_("Brak zmian"))

        messagebox.showinfo("Operacja zakończona", "; ".join(summary_parts))

        if hasattr(self, "show_orders") and self.orders_output:
            try:
                self.show_orders(self.orders_output)
            except Exception:
                logger.exception("Failed to refresh order list")
        return True

    def confirm_order(self):
        """Confirm the first pending order and mark codes as sold."""

        orders = getattr(self, "pending_orders", [])
        if not orders:
            return
        order = orders.pop(0)
        success = self.complete_order(order)
        if not success:
            orders.insert(0, order)

    def print_order_items(
        self,
        order_entry: Mapping[str, Any],
        image_map: Mapping[str, str],
        warehouse_map: Mapping[str, list],
    ) -> None:
        """Generate an HTML file with thumbnails for printing."""

        order_data = order_entry.get("data", {})
        items = order_data.get("products", [])

        html_parts = [
            "<html><head><title>Lista do zebrania</title><style>",
            "body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 20px; }",
            ".header { border-bottom: 2px solid #333; padding-bottom: 15px; margin-bottom: 25px; }",
            "h1 { margin: 0; } .details p { margin: 5px 0; font-size: 1.1em; }",
            ".item { display: flex; align-items: flex-start; border-bottom: 1px solid #ccc; padding: 15px 0; }",
            ".item img { width: 80px; height: auto; margin-right: 20px; border-radius: 4px; }",
            ".item-info { flex-grow: 1; }",
            ".item-name { font-size: 1.3em; font-weight: bold; margin-bottom: 5px; }",
            ".item-details { font-family: monospace; color: #555; }",
            ".summary { border-top: 2px solid #333; padding-top: 15px; margin-top: 25px; font-size: 1.2em; text-align: right; }",
            "</style></head><body>"
        ]

        # --- Nagłówek zamówienia ---
        html_parts.append(f"<div class='header'><h1>{html.escape(order_entry.get('title', ''))}</h1><div class='details'>")
        if order_entry.get('customer'): html_parts.append(f"<p><b>Klient:</b> {html.escape(order_entry['customer'])}</p>")
        if order_entry.get('created'): html_parts.append(f"<p><b>Data:</b> {html.escape(order_entry['created'])}</p>")
        if order_entry.get('total'): html_parts.append(f"<p><b>Wartość:</b> {html.escape(order_entry['total'])}</p>")
        html_parts.append("</div></div>")

        total_quantity = 0
        # --- Lista produktów ---
        for item in items:
            name = item.get("name") or "Brak nazwy"
            quantity = _coerce_quantity(item.get('quantity'))
            total_quantity += quantity
            product_codes = self._candidate_product_codes(item)
            display_code = product_codes[0] if product_codes else ""

            image_path = None
            for code in product_codes:
                image_path = image_map.get(code)
                if image_path:
                    break
            img_tag = '<div style="width:80px; height:112px; border:1px solid #ccc; text-align:center; display:flex; align-items:center; justify-content:center; background:#f0f0f0; margin-right:20px; border-radius:4px;">?</div>'
            if image_path and os.path.exists(image_path):
                try:
                    with open(image_path, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode("ascii")
                    mime, _ = mimetypes.guess_type(image_path)
                    img_tag = f'<img src="data:{mime or "image/png"};base64,{b64}">'
                except Exception as e:
                    logger.warning(f"Could not embed image {image_path}: {e}")

            # Znajdź kody magazynowe do pobrania
            codes_to_pick: list[Mapping[str, Any]] = []
            for code in product_codes:
                options = warehouse_map.get(code)
                if options:
                    codes_to_pick = list(options)[:quantity]
                    break

            html_parts.append("<div class='item'>")
            html_parts.append(img_tag)
            html_parts.append("<div class='item-info'>")
            html_parts.append(f"<div class='item-name'>{html.escape(name)} (x{quantity})</div>")
            html_parts.append(
                f"<div class='item-details'><b>Kod produktu:</b> {html.escape(display_code or '')}</div>"
            )
            if codes_to_pick:
                for code in codes_to_pick:
                    location = self.location_from_code(code.get('warehouse_code', ''))
                    html_parts.append(f"<div class='item-details'><b>Do pobrania:</b> {html.escape(code.get('warehouse_code', ''))} ({location})</div>")
            else:
                html_parts.append("<div class='item-details' style='color:red;'><b>Do pobrania:</b> BRAK W MAGAZYNIE!</div>")
            html_parts.append("</div></div>")

        # --- Podsumowanie ---
        html_parts.append(f"<div class='summary'><p><b>Łączna liczba sztuk do zebrania: {total_quantity}</b></p></div>")
        html_parts.append("</body></html>")
        html_content = "".join(html_parts)

        try:
            with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8", suffix=".html") as tmp:
                tmp.write(html_content)
                tmp_path = Path(tmp.name)

            webbrowser.open(f"file://{tmp_path.resolve()}")
            messagebox.showinfo("Drukowanie", "Lista do druku została otwarta w przeglądarce. Użyj opcji 'Drukuj' (Ctrl+P).")
        except Exception as e:
            messagebox.showerror("Błąd", f"Nie udało się otworzyć listy do druku: {e}")

    @staticmethod
    def location_from_code(code: str) -> str:
        return storage.location_from_code(code)

    def build_home_box_preview(self, parent):
        """Create a minimal box preview showing only overall fill percentages."""

        container = ctk.CTkFrame(parent, fg_color=BG_COLOR)
        container.pack(expand=True, fill="both", padx=10, pady=10)

        self.mag_box_order = list(range(1, BOX_COUNT + 1)) + [SPECIAL_BOX_NUMBER]
        self.home_percent_labels = {}
        self.home_box_canvases = {}
        self.mag_labels = []

        base_dir = Path(__file__).resolve().parents[1]
        if not hasattr(self, "_box_photo"):
            img = Image.open(base_dir / "box.png").resize(
                (BOX_THUMB_SIZE, BOX_THUMB_SIZE), Image.LANCZOS
            ).convert("RGBA")
            self._box_photo = ImageTk.PhotoImage(img)
        if not hasattr(self, "_box100_photo"):
            img = Image.open(base_dir / "box100.png").resize(
                (BOX_THUMB_SIZE, BOX_THUMB_SIZE), Image.LANCZOS
            ).convert("RGBA")
            self._box100_photo = ImageTk.PhotoImage(img)

        for i, box_num in enumerate(self.mag_box_order):
            frame = ctk.CTkFrame(container, fg_color=BG_COLOR)
            lbl = ctk.CTkLabel(
                frame,
                text=f"K{box_num}",
                fg_color=BG_COLOR,
                text_color=TEXT_COLOR,
                font=("Segoe UI", 24, "bold"),
            )
            lbl.pack()
            self.mag_labels.append(lbl)

            try:
                canvas = tk.Canvas(
                    frame,
                    width=BOX_THUMB_SIZE,
                    height=BOX_THUMB_SIZE,
                    bg=BG_COLOR,
                    highlightthickness=0,
                )
            except TypeError:
                # Some test doubles do not accept ``bg`` in the constructor.
                canvas = tk.Canvas(
                    frame,
                    width=BOX_THUMB_SIZE,
                    height=BOX_THUMB_SIZE,
                    highlightthickness=0,
                )
                canvas.config(bg=BG_COLOR)
            img = self._box100_photo if box_num == SPECIAL_BOX_NUMBER else self._box_photo
            canvas.create_image(0, 0, anchor="nw", image=img)
            canvas.image = img
            canvas.pack()
            self.home_box_canvases[box_num] = canvas

            pct_label = ctk.CTkLabel(
                frame,
                text="0%",
                width=40,
                fg_color=BG_COLOR,
                text_color=_occupancy_color(0),
                font=("Segoe UI", 24, "bold"),
            )
            pct_label.pack(pady=(5, 0))
            self.home_percent_labels[box_num] = pct_label

            row, col_idx = divmod(i, WAREHOUSE_GRID_COLUMNS)
            if box_num == SPECIAL_BOX_NUMBER:
                row = 0
                col_idx = WAREHOUSE_GRID_COLUMNS
            frame.grid(row=row, column=col_idx, padx=5, pady=5)

    def build_box_preview(self, parent):
        """Create a scrollable grid of frames and progress bars for boxes."""

        container = ctk.CTkFrame(parent, fg_color=BG_COLOR)
        container.pack(expand=True, fill="both", padx=10, pady=10)

        self.mag_box_order = list(range(1, BOX_COUNT + 1)) + [SPECIAL_BOX_NUMBER]
        self.mag_progressbars = {}
        self.mag_percent_labels = {}
        self.mag_labels = []
        for i, box_num in enumerate(self.mag_box_order):
            frame = ctk.CTkFrame(container, fg_color=BG_COLOR)
            lbl = ctk.CTkLabel(
                frame,
                text=f"K{box_num}",
                fg_color=BG_COLOR,
                text_color=TEXT_COLOR,
                font=("Segoe UI", 24, "bold"),
            )
            lbl.pack(anchor="w")
            self.mag_labels.append(lbl)
            for col in range(
                1, BOX_COLUMNS.get(box_num, STANDARD_BOX_COLUMNS) + 1
            ):
                row_frame = ctk.CTkFrame(frame, fg_color=BG_COLOR)
                row_frame.pack(fill="x", padx=2, pady=2)
                bar = ctk.CTkProgressBar(
                    row_frame,
                    orientation="horizontal",
                    fg_color=FREE_COLOR,
                    progress_color=OCCUPIED_COLOR,
                )
                bar.set(0)
                bar.pack(side="left", fill="x", expand=True)
                pct_label = ctk.CTkLabel(
                    row_frame,
                    text="0%",
                    width=40,
                    fg_color=BG_COLOR,
                    text_color=_occupancy_color(0),
                    font=("Segoe UI", 24, "bold"),
                )
                pct_label.pack(side="left", padx=(5, 0))
                self.mag_progressbars[(box_num, col)] = bar
                self.mag_percent_labels[(box_num, col)] = pct_label
            row, col_idx = divmod(i, WAREHOUSE_GRID_COLUMNS)
            if box_num == SPECIAL_BOX_NUMBER:
                row = 0
                col_idx = WAREHOUSE_GRID_COLUMNS
            frame.grid(row=row, column=col_idx, padx=5, pady=5)

        # Internal helpers used by the magazyn window; populated lazily.
        self.mag_card_images = []
        self.mag_card_rows = []
        self.mag_card_labels = []
        self.mag_sold_labels = []
        self.mag_card_image_labels: list[Optional[ctk.CTkLabel]] = []

    def reload_mag_cards(self, force: bool = False) -> None:
        """(Re)load warehouse card data using the configured inventory service.

        Args:
            force: When ``True`` the underlying service is instructed to fetch a
                fresh snapshot instead of relying on a cached copy.
        """

        thumb_size = CARD_THUMB_SIZE
        placeholder_img = Image.new("RGB", (thumb_size, thumb_size), "#111111")
        self.mag_placeholder_photo = _create_image(placeholder_img)

        # reset containers
        for frame in getattr(self, "_mag_frame_pool", []):
            if frame is None:
                continue
            destroy = getattr(frame, "destroy", None)
            if callable(destroy):
                try:
                    destroy()
                except Exception:
                    pass
        self._mag_frame_pool = []

        self.mag_card_rows = []
        self.mag_card_images = []
        self.mag_card_image_labels = []
        self.mag_card_frames = []
        self._image_threads = []
        self._mag_image_paths = []
        self._mag_loaded_images = {}
        self._mag_loading_indices = set()

        inventory_service = getattr(self, "inventory_service", None)
        if inventory_service is None:
            inventory_service = WarehouseInventoryService.create_default()
            try:
                setattr(self, "inventory_service", inventory_service)
            except Exception:
                pass

        # Seed local sold overlay from current orders (if any). If orders have
        # suggested warehouse codes attached, mark those codes as sold locally
        # so the magazyn view reflects it immediately.
        try:
            pending = getattr(self, "pending_orders", []) or []
        except Exception:
            pending = []
        try:
            for order in pending:
                for item in (order or {}).get("products", []) or []:
                    raw = (item or {}).get("warehouse_code") or ""
                    for code in str(raw).split(";"):
                        code = str(code).strip()
                        if code:
                            self._locally_sold_codes.add(code)
        except Exception:
            # best-effort: ignore malformed orders payloads
            pass

        snapshot = None
        try:
            if force:
                fetch_snapshot = getattr(inventory_service, "fetch_snapshot", None)
                if callable(fetch_snapshot):
                    snapshot = fetch_snapshot()
            else:
                get_snapshot = getattr(inventory_service, "get_snapshot", None)
                if callable(get_snapshot):
                    snapshot = get_snapshot()
                if snapshot is None:
                    fetch_snapshot = getattr(
                        inventory_service, "fetch_snapshot", None
                    )
                    if callable(fetch_snapshot):
                        snapshot = fetch_snapshot()
            if snapshot is None and not force:
                fetch_snapshot = getattr(inventory_service, "fetch_snapshot", None)
                if callable(fetch_snapshot):
                    snapshot = fetch_snapshot()
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Failed to fetch warehouse inventory snapshot")
            snapshot = None

        items = list(getattr(snapshot, "items", ()) or [])
        column_occ = dict(getattr(snapshot, "column_occupancy", {}) or {})
        version = getattr(snapshot, "version", None)

        self._mag_snapshot = snapshot
        self._mag_inventory_version = version
        self._mag_column_occ = column_occ

        groups: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)

        def _safe_int(value: Any) -> int:
            try:
                if isinstance(value, bool):
                    return int(value)
                if isinstance(value, (int, float)):
                    return int(value)
                if isinstance(value, str):
                    raw = value.strip()
                    if not raw:
                        return 0
                    return int(float(raw))
            except (TypeError, ValueError):
                return 0
            return 0

        def _normalise_item(item: Any) -> dict[str, Any]:
            locations = [
                {
                    "code": loc.code,
                    "box": loc.box,
                    "column": loc.column,
                    "position": loc.position,
                }
                for loc in getattr(item, "locations", ())
            ]
            warehouse_code = getattr(item, "warehouse_code", "") or ""
            if not warehouse_code and locations:
                warehouse_code = ";".join(
                    dict.fromkeys(loc.get("code") for loc in locations if loc.get("code"))
                )
            price = getattr(item, "price", "")
            if isinstance(price, (int, float)):
                price = f"{price}"
            row = {
                "name": getattr(item, "name", ""),
                "number": getattr(item, "number", ""),
                "set": getattr(item, "set", ""),
                "variant": getattr(item, "variant", "") or "common",
                "sold": "1" if getattr(item, "sold", False) else "",
                "price": price,
                "image": getattr(item, "image", ""),
                "added_at": getattr(item, "added_at", ""),
                "warehouse_code": warehouse_code,
                "quantity": getattr(item, "quantity", 1) or 1,
                "_source": getattr(item, "source", ""),
                "_raw": getattr(item, "raw", {}),
                "_locations": locations,
            }
            return row

        for item in items:
            row = _normalise_item(item)
            key = (
                row.get("name", ""),
                row.get("number", ""),
                row.get("set", ""),
                row.get("variant", "") or "common",
                row.get("sold", ""),
            )
            groups[key].append(row)

        for rows in groups.values():
            combined = dict(rows[0])
            added_dates: list[datetime.date] = []
            total_quantity = 0
            all_locations: list[dict[str, Any]] = []
            image_path = combined.get("image") or ""
            # Try to enrich from store cache/API if image is missing
            lookup_code = combined.get("number") or combined.get("code") or ""
            for entry in rows:
                total_quantity += _safe_int(entry.get("quantity", 1))
                all_locations.extend(entry.get("_locations", []))
                value = str(entry.get("added_at") or "").strip()
                if value:
                    try:
                        added_dates.append(datetime.date.fromisoformat(value))
                    except ValueError:
                        logger.warning("Skipping invalid added_at: %s", value)
                if not image_path and entry.get("image"):
                    image_path = entry.get("image")
            # If still no image, look into product cache / API by product code
            if not image_path and lookup_code:
                try:
                    self._ensure_store_cache()
                    prod = self._get_store_product(str(lookup_code).strip())
                except Exception:
                    prod = None
                if prod:
                    try:
                        from . import csv_utils as _cu
                        candidate = _cu.product_image_url(prod)
                        if candidate:
                            image_path = candidate
                    except Exception:
                        pass
            if added_dates:
                combined["added_at"] = max(added_dates).isoformat()
            combined["image"] = image_path or ""
            combined["variant"] = combined.get("variant") or "common"
            combined["_count"] = len(rows)
            combined["quantity"] = max(total_quantity, combined.get("_count", 1))
            combined["_locations"] = all_locations
            combined["warehouse_code"] = ";".join(
                dict.fromkeys(
                    loc.get("code") for loc in all_locations if loc.get("code")
                )
            )
            # Mark listing status from API cache if available
            is_active = None
            if lookup_code:
                row_cached = None
                try:
                    row_cached = getattr(self, "store_data", {}).get(str(lookup_code).strip())
                except Exception:
                    row_cached = None
                if isinstance(row_cached, Mapping):
                    val = row_cached.get("active")
                    try:
                        is_active = bool(int(val)) if val not in (None, "") else None
                    except Exception:
                        if isinstance(val, str):
                            is_active = val.strip().lower() in {"1", "true", "yes", "on"}
            if is_active is not None:
                combined["_active"] = is_active

            idx = len(self.mag_card_rows)
            self.mag_card_rows.append(combined)
            self.mag_card_images.append(self.mag_placeholder_photo)
            raw_img = combined.get("image") or ""
            self._mag_image_paths.append(_resolve_image_url(raw_img) if raw_img else "")
            self.mag_card_image_labels.append(None)

        self._mag_frame_pool = [None] * len(self.mag_card_rows)
        self._mag_prev_thumb = 0

        def _ensure_image(index: int) -> None:
            if index < 0 or index >= len(self._mag_image_paths):
                return
            if index in self._mag_loaded_images or index in self._mag_loading_indices:
                return

            path = self._mag_image_paths[index]
            if not path:
                return

            self._mag_loading_indices.add(index)

            def _worker(i=index, img_path=path):
                img = _load_image(img_path)
                if img is None:
                    self._mag_loading_indices.discard(i)
                    return

                def _update(image=img):
                    self._mag_loading_indices.discard(i)
                    img_resized = _resize_to_width(image, thumb_size)
                    photo = _create_image(img_resized)
                    self._mag_loaded_images[i] = photo
                    self.mag_card_images[i] = photo
                    lbl = self.mag_card_image_labels[i]
                    exists_fn = getattr(lbl, "winfo_exists", None)
                    if lbl and (exists_fn is None or exists_fn()):
                        if hasattr(lbl, "configure"):
                            try:
                                lbl.configure(image=photo)
                            except tk.TclError:
                                pass
                        else:
                            lbl.image = photo
                    relayout = getattr(self, "_relayout_mag_cards", None)
                    if callable(relayout):
                        after2 = getattr(self.root, "after", None)
                        if callable(after2):
                            after2(0, relayout)
                        else:
                            relayout()

                after = getattr(self.root, "after", None)
                if callable(after):
                    after(0, _update)
                else:
                    _update()

            th = threading.Thread(target=_worker, daemon=True)
            th.start()
            self._image_threads.append(th)

        self._ensure_mag_image = _ensure_image

    def show_magazyn_view(self):
        """Display storage occupancy inside the main window."""
        # Unbind previous resize handlers if they exist before rebuilding the
        # magazine view. This prevents ``_relayout_mag_cards`` from being
        # triggered after the associated widgets are destroyed.
        if getattr(self, "_mag_bind_id", None) or getattr(self, "_root_mag_bind_id", None):
            mag_frame = getattr(self, "mag_list_frame", None)
            if mag_frame is not None:
                unbind = getattr(mag_frame, "unbind", None)
                if callable(unbind) and getattr(self, "_mag_bind_id", None):
                    unbind("<Configure>", self._mag_bind_id)
            if getattr(self, "_root_mag_bind_id", None):
                root_unbind = getattr(self.root, "unbind", None)
                if callable(root_unbind):
                    root_unbind("<Configure>", self._root_mag_bind_id)
            self._mag_bind_id = None
            self._root_mag_bind_id = None

        self.root.title("Podgląd magazynu")
        current_root = self.root
        if self.start_frame is not None:
            self.start_frame.destroy()
            self.start_frame = None
        if getattr(self, "pricing_frame", None):
            self.pricing_frame.destroy()
            self.pricing_frame = None
        if getattr(self, "shoper_frame", None):
            self.shoper_frame.destroy()
            self.shoper_frame = None
        if getattr(self, "frame", None):
            self.frame.destroy()
            self.frame = None
        if getattr(self, "magazyn_frame", None):
            self.magazyn_frame.destroy()
            self.magazyn_frame = None
            labels = getattr(self, "mag_card_image_labels", [])
            for i in range(len(labels)):
                labels[i] = None
        if getattr(self, "location_frame", None):
            self.location_frame.destroy()
            self.location_frame = None

        if all(hasattr(self.root, attr) for attr in ("winfo_screenwidth", "winfo_screenheight", "minsize")):
            screen_w = self.root.winfo_screenwidth()
            screen_h = self.root.winfo_screenheight()
            min_w = int(screen_w * 0.75)
            min_h = int(screen_h * 0.75)
            self.root.minsize(min_w, min_h)
        self.magazyn_frame = ctk.CTkFrame(self.root, fg_color=BG_COLOR)
        self.magazyn_frame.pack(expand=True, fill="both", padx=10, pady=10)

        # Reset box preview containers; tests or callers may rebuild preview
        # manually using :func:`build_box_preview` when needed.
        self.mag_progressbars = {}
        self.mag_percent_labels = {}
        self.mag_labels = []
        self.mag_box_order = []

        self._mag_filtered_total = 0
        self._mag_canvas_bind_id = None

        control_frame = ctk.CTkFrame(self.magazyn_frame, fg_color=BG_COLOR)
        control_frame.pack(fill="x", padx=10, pady=(10, 0))

        # Enable/disable pagination; allow forcing scroll-only via env
        supports_pagination = isinstance(getattr(tk, "StringVar", None), type)
        try:
            _scroll_only = os.getenv("WAREHOUSE_SCROLL_ONLY", "").strip().lower()
            if _scroll_only in {"1", "true", "yes", "on"}:
                supports_pagination = False
        except Exception:
            pass
        if not supports_pagination:
            if not getattr(tk, "_mag_pagination_fallback_used", False):
                try:
                    setattr(tk, "_mag_pagination_fallback_used", True)
                except Exception:
                    pass
            else:
                supports_pagination = True
        try:
            setattr(self, "_mag_pagination_supported", supports_pagination)
        except Exception:
            self._mag_pagination_supported = supports_pagination  # type: ignore[attr-defined]

        def _safe_var(value=""):
            try:
                var = tk.StringVar(value=value)
                return var
            except (tk.TclError, RuntimeError):
                class _Var:
                    def __init__(self, val):
                        self._val = val
                        self._callbacks: list[callable] = []

                    def get(self):
                        return self._val

                    def set(self, val):
                        self._val = val
                        for cb in list(self._callbacks):
                            cb()

                    def trace_add(self, mode, callback):
                        self._callbacks.append(lambda *a, **k: callback())

                return _Var(value)

        self.mag_search_var = _safe_var()
        search_entry = ctk.CTkEntry(
            control_frame,
            textvariable=self.mag_search_var,
            placeholder_text="Szukaj",
            width=250,
        )
        search_entry.pack(side="left", padx=5, pady=5)

        search_button = ctk.CTkButton(
            control_frame, text="Szukaj", fg_color=FETCH_BUTTON_COLOR
        )
        search_button.pack(side="left", padx=5, pady=5)

        self.mag_sort_var = _safe_var("added")
        sort_menu = ctk.CTkOptionMenu(
            control_frame,
            variable=self.mag_sort_var,
            values=["added", "price", "name", "quantity"],
        )
        sort_menu.pack(side="left", padx=5, pady=5)

        self.mag_sold_filter_var = _safe_var("unsold")
        sold_filter_menu = ctk.CTkOptionMenu(
            control_frame,
            variable=self.mag_sold_filter_var,
            values=["all", "sold", "unsold"],
        )
        sold_filter_menu.pack(side="left", padx=5, pady=5)

        list_frame = ctk.CTkScrollableFrame(self.magazyn_frame, fg_color=LIGHT_BG_COLOR)
        list_frame.pack(expand=True, fill="both", padx=10, pady=10)
        # store reference for resize handling
        self.mag_list_frame = list_frame

        pagination_frame = ctk.CTkFrame(self.magazyn_frame, fg_color=BG_COLOR)
        pagination_frame.pack(fill="x", padx=10, pady=(0, 5))
        self._mag_pagination_frame = pagination_frame

        # Populate warehouse card data from CSV
        try:
            CardEditorApp.reload_mag_cards(self, force=False)
        except Exception:  # pragma: no cover - defensive
            logger.exception("Failed to reload warehouse cards")

        def _relayout_mag_cards(event=None):
            """Recompute thumbnail size and update scroll region on resize."""
            if getattr(self, "_mag_layout_running", False):
                return
            self._mag_layout_running = True
            try:
                exists_fn = getattr(self.mag_list_frame, "winfo_exists", lambda: True)
                if not self.mag_list_frame or not exists_fn():
                    return
                global CARD_THUMB_SIZE
                width = 0
                canvas = getattr(self.mag_list_frame, "_parent_canvas", None)
                if canvas is not None:
                    width_fn = getattr(canvas, "winfo_width", None)
                    if callable(width_fn):
                        width = width_fn()
                if width <= 1:
                    width_fn = getattr(self.magazyn_frame, "winfo_width", lambda: 0)
                    width = width_fn()
                max_thumb = MAX_CARD_THUMB_SIZE
                if width <= 1:
                    width = max_thumb * 4 + MAG_CARD_GAP * 6
                cols = max(1, width // (max_thumb + MAG_CARD_GAP * 2))
                thumb = max(
                    32,
                    min((width - MAG_CARD_GAP * 2 * cols) // cols, max_thumb),
                )
                if thumb != self._mag_prev_thumb:
                    self._mag_prev_thumb = thumb
                    CARD_THUMB_SIZE = thumb
                    placeholder = Image.new("RGB", (thumb, thumb), "#111111")
                    old_placeholder = getattr(self, "mag_placeholder_photo", None)
                    self.mag_placeholder_photo = _create_image(placeholder)
                    for i, img in enumerate(list(self.mag_card_images)):
                        photo = img
                        if photo is None or photo is old_placeholder:
                            photo = self.mag_placeholder_photo
                            self.mag_card_images[i] = photo
                        else:
                            if hasattr(photo, "configure") and hasattr(photo, "_light_image"):
                                try:
                                    w, h = photo._light_image.size
                                    new_h = max(1, int(h * thumb / w)) if w else thumb
                                    photo.configure(size=(thumb, new_h))
                                except Exception:
                                    pass
                        lbl = self.mag_card_image_labels[i]
                        if lbl is not None:
                            # Ensure the label widget still exists before updating.
                            exists_fn = getattr(lbl, "winfo_exists", None)
                            try:
                                exists = True if exists_fn is None else bool(exists_fn())
                            except Exception:
                                exists = False
                            if exists:
                                if hasattr(lbl, "configure"):
                                    lbl.configure(image=photo)
                                else:
                                    lbl.image = photo

                col_conf = getattr(self.mag_list_frame, "grid_columnconfigure", None)
                if callable(col_conf):
                    prev_cols = getattr(self, "_mag_prev_cols", 0)
                    total = max(prev_cols, cols)
                    for i in range(total):
                        weight = 1 if i < cols else 0
                        col_conf(i, weight=weight)
                    self._mag_prev_cols = cols
                for i, frame in enumerate(self.mag_card_frames):
                    if frame is None:
                        continue
                    exists_fn = getattr(frame, "winfo_exists", None)
                    try:
                        exists = True if exists_fn is None else bool(exists_fn())
                    except Exception:
                        exists = False
                    if not exists:
                        continue
                    r = i // cols
                    c = i % cols
                    grid = getattr(frame, "grid", None)
                    if callable(grid):
                        grid(
                            row=r,
                            column=c,
                            padx=MAG_CARD_GAP,
                            pady=MAG_CARD_GAP,
                            sticky="nsew",
                        )

                canvas = getattr(self.mag_list_frame, "_parent_canvas", None)
                if canvas is not None:
                    def _update_scroll_region():
                        yview_fn = getattr(canvas, "yview", None)
                        try:
                            yview = yview_fn() if callable(yview_fn) else None
                        except Exception:
                            yview = None
                        bbox = canvas.bbox("all") or (0, 0, 0, 0)
                        canvas.configure(scrollregion=bbox)
                        if yview:
                            moveto = getattr(canvas, "yview_moveto", None)
                            if callable(moveto):
                                try:
                                    moveto(yview[0])
                                except Exception:
                                    pass

                    after_idle = getattr(canvas, "after_idle", None)
                    if callable(after_idle):
                        after_idle(_update_scroll_region)
                    else:
                        _update_scroll_region()
            finally:
                self._mag_layout_running = False

        # Expose relayout function for worker threads
        self._relayout_mag_cards = _relayout_mag_cards

        def _remove_pagination_buttons() -> None:
            for attr in ("mag_prev_button", "mag_next_button"):
                btn = getattr(self, attr, None)
                if btn is None:
                    continue
                destroy = getattr(btn, "destroy", None)
                if callable(destroy):
                    try:
                        destroy()
                    except Exception:
                        pass
                try:
                    delattr(self, attr)
                except Exception:
                    pass

        def _update_mag_list(*_):
            query_raw = self.mag_search_var.get().strip()
            sort_key = self.mag_sort_var.get()
            status_filter = self.mag_sold_filter_var.get()

            normalized_query = normalize(query_raw, keep_spaces=True)
            tokens = [tok for tok in normalized_query.split() if tok]
            if "sold" in tokens or "unsold" in tokens:
                status_filter = "all"

            def _matches(row: dict) -> bool:
                # Treat as sold if CSV/API flag is set OR the card's
                # warehouse code matches a locally marked-as-sold code
                csv_sold = str(row.get("sold") or "").lower() in {"1", "true", "yes"}
                try:
                    local_sold = getattr(self, "_locally_sold_codes", set())
                except Exception:
                    local_sold = set()
                row_codes = [
                    c.strip() for c in str(row.get("warehouse_code") or "").split(";") if c.strip()
                ]
                is_sold = csv_sold or any(c in local_sold for c in row_codes)
                if status_filter == "sold" and not is_sold:
                    return False
                if status_filter == "unsold" and is_sold:
                    return False
                price_str = str(row.get("price", "")).replace(",", ".")
                fields = [
                    normalize(row.get("name", "")),
                    normalize(str(row.get("number", ""))),
                    normalize(row.get("set", "")),
                    normalize(row.get("warehouse_code", "")),
                    normalize(row.get("variant") or ""),
                    normalize(price_str),
                ]
                for token in tokens:
                    if token == "sold":
                        if not is_sold:
                            return False
                        continue
                    if token == "unsold":
                        if is_sold:
                            return False
                        continue
                    if not any(token in field for field in fields):
                        return False
                return True

            indices = [i for i, r in enumerate(self.mag_card_rows) if _matches(r)]
            if sort_key == "added":
                indices.sort(
                    key=lambda i: self.mag_card_rows[i].get("added_at") or "",
                    reverse=True,
                )
            elif sort_key == "name":
                indices.sort(key=lambda i: self.mag_card_rows[i].get("name", ""))
            elif sort_key == "price":
                def _price(i: int) -> float:
                    val = str(self.mag_card_rows[i].get("price", "0")).replace(",", ".")
                    try:
                        return float(val)
                    except ValueError:
                        return 0.0

                indices.sort(key=_price)
            elif sort_key == "quantity":
                def _quantity(i: int) -> int:
                    try:
                        return int(self.mag_card_rows[i].get("_count", 1))
                    except (TypeError, ValueError):
                        return 1

                indices.sort(key=_quantity, reverse=True)

            total_cards = len(indices)
            self._mag_filtered_total = total_cards

            page_size = getattr(self, "mag_page_size", MAG_PAGE_SIZE) or MAG_PAGE_SIZE
            supports = getattr(self, "_mag_pagination_supported", True)
            needs_pagination = bool(supports and page_size and total_cards > page_size)

            if needs_pagination:
                max_page = max(0, (total_cards - 1) // page_size)
                current_page = getattr(self, "mag_page", 0)
                if not isinstance(current_page, int):
                    try:
                        current_page = int(current_page)
                    except Exception:
                        current_page = 0
                current_page = max(0, min(current_page, max_page))
                start = current_page * page_size
                end = start + page_size
                visible_indices = indices[start:end]
                self.mag_page = current_page
                self.mag_page_size = page_size
                self._mag_total_pages = max_page + 1

                prev_btn = getattr(self, "mag_prev_button", None)
                if prev_btn is None:
                    prev_btn = self.create_button(
                        pagination_frame,
                        text="Poprzednia",
                        command=lambda delta=-1: _go_to_page(delta),
                        fg_color=NAV_BUTTON_COLOR,
                        width=120,
                        height=40,
                    )
                    prev_btn.pack(side="left", padx=5)
                    self.mag_prev_button = prev_btn
                next_btn = getattr(self, "mag_next_button", None)
                if next_btn is None:
                    next_btn = self.create_button(
                        pagination_frame,
                        text="Następna",
                        command=lambda delta=1: _go_to_page(delta),
                        fg_color=NAV_BUTTON_COLOR,
                        width=120,
                        height=40,
                    )
                    next_btn.pack(side="right", padx=5)
                    self.mag_next_button = next_btn
                _configure_widget(
                    self.mag_prev_button,
                    state="disabled" if current_page <= 0 else "normal",
                )
                _configure_widget(
                    self.mag_next_button,
                    state="disabled" if current_page >= max_page else "normal",
                )
            else:
                visible_indices = indices
                self.mag_page_size = page_size
                self._mag_total_pages = 1
                _remove_pagination_buttons()
                if hasattr(self, "mag_page"):
                    try:
                        delattr(self, "mag_page")
                    except Exception:
                        self.mag_page = 0

            indices = list(visible_indices)
            self._mag_visible_indices = list(indices)

            unbind = getattr(self.mag_list_frame, "unbind", None)
            if callable(unbind) and getattr(self, "_mag_bind_id", None):
                unbind("<Configure>", self._mag_bind_id)
                self._mag_bind_id = None
            canvas_obj = getattr(self.mag_list_frame, "_parent_canvas", None)
            canvas_unbind = getattr(canvas_obj, "unbind", None)
            if callable(canvas_unbind) and getattr(self, "_mag_canvas_bind_id", None):
                try:
                    canvas_unbind("<Configure>", self._mag_canvas_bind_id)
                except Exception:
                    pass
                self._mag_canvas_bind_id = None
            root_unbind = getattr(current_root, "unbind", None)
            if callable(root_unbind) and getattr(self, "_root_mag_bind_id", None):
                root_unbind("<Configure>", self._root_mag_bind_id)
                self._root_mag_bind_id = None

            frames = getattr(self, "mag_card_frames", [])
            for frame in frames:
                forget = getattr(frame, "grid_forget", None)
                if callable(forget):
                    try:
                        forget()
                    except Exception:
                        pass
            self.mag_card_frames = []
            self.mag_card_labels = []
            self.mag_sold_labels = []

            labels = getattr(self, "mag_card_image_labels", [])
            for i in range(len(labels)):
                labels[i] = None

            pool = getattr(self, "_mag_frame_pool", [])
            if len(pool) < len(self.mag_card_rows):
                pool.extend([None] * (len(self.mag_card_rows) - len(pool)))

            def _widget_exists(widget: object) -> bool:
                if widget is None:
                    return False
                exists_fn = getattr(widget, "winfo_exists", None)
                if callable(exists_fn):
                    try:
                        return bool(exists_fn())
                    except Exception:
                        return False
                return True

            displayed: set[int] = set()

            for idx in indices:
                row = self.mag_card_rows[idx]
                frame = pool[idx] if idx < len(pool) else None
                if not _widget_exists(frame) or getattr(frame, "master", None) is not list_frame:
                    if _widget_exists(frame):
                        destroy = getattr(frame, "destroy", None)
                        if callable(destroy):
                            try:
                                destroy()
                            except Exception:
                                pass
                    frame = ctk.CTkFrame(list_frame, fg_color=BG_COLOR)
                    if hasattr(frame, "grid_columnconfigure"):
                        frame.grid_columnconfigure(0, weight=1)
                    img_label = ctk.CTkLabel(frame, image=self.mag_card_images[idx], text="")
                    img_label.grid(row=0, column=0, sticky="n")
                    if hasattr(ctk, "CTkFont"):
                        unsold_font: Any = ctk.CTkFont(size=20)
                    else:
                        unsold_font = ("TkDefaultFont", 20)
                    label = ctk.CTkLabel(
                        frame,
                        text="",
                        text_color=TEXT_COLOR,
                        width=CARD_THUMB_SIZE,
                        wraplength=CARD_THUMB_SIZE,
                        justify="center",
                        font=unsold_font,
                    )
                    label.grid(row=1, column=0, sticky="new")
                    frame._mag_unsold_font = unsold_font  # type: ignore[attr-defined]
                    frame._mag_sold_font = None  # type: ignore[attr-defined]
                    frame._mag_image_label = img_label  # type: ignore[attr-defined]
                    frame._mag_name_label = label  # type: ignore[attr-defined]
                    frame._mag_badge_label = None  # type: ignore[attr-defined]
                    pool[idx] = frame
                else:
                    img_label = getattr(frame, "_mag_image_label", None)
                    if not _widget_exists(img_label):
                        img_label = ctk.CTkLabel(frame, image=self.mag_card_images[idx], text="")
                        img_label.grid(row=0, column=0, sticky="n")
                        frame._mag_image_label = img_label  # type: ignore[attr-defined]
                    label = getattr(frame, "_mag_name_label", None)
                    if not _widget_exists(label):
                        unsold_font = getattr(frame, "_mag_unsold_font", None)
                        if unsold_font is None:
                            if hasattr(ctk, "CTkFont"):
                                unsold_font = ctk.CTkFont(size=20)
                            else:
                                unsold_font = ("TkDefaultFont", 20)
                            frame._mag_unsold_font = unsold_font  # type: ignore[attr-defined]
                        label = ctk.CTkLabel(
                            frame,
                            text="",
                            text_color=TEXT_COLOR,
                            width=CARD_THUMB_SIZE,
                            wraplength=CARD_THUMB_SIZE,
                            justify="center",
                            font=unsold_font,
                        )
                        label.grid(row=1, column=0, sticky="new")
                        frame._mag_name_label = label  # type: ignore[attr-defined]
                    else:
                        unsold_font = getattr(frame, "_mag_unsold_font", None)

                img_label = getattr(frame, "_mag_image_label", None)
                label = getattr(frame, "_mag_name_label", None)
                if not (_widget_exists(img_label) and _widget_exists(label)):
                    continue

                photo = self.mag_card_images[idx]
                if hasattr(img_label, "configure"):
                    img_label.configure(image=photo)
                else:
                    img_label.image = photo  # type: ignore[attr-defined]
                self.mag_card_image_labels[idx] = img_label

                is_sold = str(row.get("sold") or "").lower() in {"1", "true", "yes"}
                text = row.get("name", "")
                # Listing status indicator from API cache
                is_active = row.get("_active")
                if is_sold:
                    text = f"[SOLD] {text}"
                    sold_font = getattr(frame, "_mag_sold_font", None)
                    if sold_font is None:
                        if hasattr(ctk, "CTkFont"):
                            sold_font = ctk.CTkFont(size=20, overstrike=True)
                        else:
                            sold_font = ("TkDefaultFont", 20, "overstrike")
                        frame._mag_sold_font = sold_font  # type: ignore[attr-defined]
                    sold_kwargs = {"text": text, "text_color": SOLD_COLOR}
                    if sold_font is not None:
                        sold_kwargs["font"] = sold_font
                    _configure_widget(label, **sold_kwargs)
                    self.mag_sold_labels.append(label)
                else:
                    unsold_font = getattr(frame, "_mag_unsold_font", None)
                    if is_active is True:
                        text = f"[WYST] {text}"
                    elif is_active is False:
                        text = f"[OFF] {text}"
                    unsold_kwargs = {"text": text, "text_color": TEXT_COLOR}
                    if unsold_font is not None:
                        unsold_kwargs["font"] = unsold_font
                    _configure_widget(label, **unsold_kwargs)
                    self.mag_card_labels.append(label)

                count = int(row.get("_count", 1))
                badge = getattr(frame, "_mag_badge_label", None)
                if count > 1:
                    if not _widget_exists(badge):
                        badge = ctk.CTkLabel(
                            frame,
                            text=str(count),
                            fg_color="#FF0000",
                            text_color="white",
                            width=20,
                            height=20,
                            corner_radius=10,
                        )
                        frame._mag_badge_label = badge  # type: ignore[attr-defined]
                    else:
                        badge.configure(text=str(count))
                    place = getattr(badge, "place", None)
                    if callable(place):
                        place(in_=img_label, relx=1.0, rely=0.0, anchor="ne")
                        lift = getattr(badge, "lift", None)
                        if callable(lift):
                            lift()
                    else:
                        grid_badge = getattr(badge, "grid", None)
                        if callable(grid_badge):
                            grid_badge(row=0, column=0, sticky="ne")
                        else:
                            badge.pack()
                elif _widget_exists(badge):
                    forget_badge = getattr(badge, "place_forget", None)
                    if callable(forget_badge):
                        forget_badge()
                    else:
                        grid_forget = getattr(badge, "grid_forget", None)
                        if callable(grid_forget):
                            grid_forget()

                ensure = getattr(self, "_ensure_mag_image", None)
                if callable(ensure):
                    ensure(idx)

                for widget in (img_label, label):
                    widget.bind("<Button-1>", lambda e, r=row: self.show_card_details(r))
                    widget.bind(
                        "<Double-Button-1>",
                        lambda e, r=row: self.show_card_details(r),
                    )

                self.mag_card_frames.append(frame)
                displayed.add(idx)

            try:
                _relayout_mag_cards()
            except Exception:
                pass

            for i in range(len(self.mag_card_image_labels)):
                if i not in displayed:
                    self.mag_card_image_labels[i] = None
            canvas = getattr(list_frame, "_parent_canvas", None)
            if canvas is not None:
                def _update_scroll_region():
                    bbox = canvas.bbox("all") or (0, 0, 0, 0)
                    canvas.configure(scrollregion=bbox)

                canvas_after_idle = getattr(canvas, "after_idle", None)
                if callable(canvas_after_idle):
                    canvas_after_idle(_update_scroll_region)
                else:
                    _update_scroll_region()

            list_after_idle = getattr(list_frame, "after_idle", None)
            if callable(list_after_idle):
                list_after_idle(_relayout_mag_cards)
            else:
                _relayout_mag_cards()

            bind = getattr(self.mag_list_frame, "bind", None)
            if callable(bind):
                self._mag_bind_id = bind("<Configure>", _relayout_mag_cards)
            canvas_bind = getattr(canvas, "bind", None)
            if callable(canvas_bind):
                self._mag_canvas_bind_id = canvas_bind("<Configure>", _relayout_mag_cards)
            root_bind = getattr(current_root, "bind", None)
            if callable(root_bind):
                self._root_mag_bind_id = root_bind("<Configure>", _relayout_mag_cards)

        self._update_mag_list = _update_mag_list

        def _go_to_page(delta: int) -> None:
            page_size = getattr(self, "mag_page_size", MAG_PAGE_SIZE) or MAG_PAGE_SIZE
            total_cards = getattr(self, "_mag_filtered_total", 0)
            if not page_size or total_cards <= page_size:
                return
            try:
                current = int(getattr(self, "mag_page", 0))
            except Exception:
                current = 0
            max_page = max(0, (total_cards - 1) // page_size)
            new_page = max(0, min(current + delta, max_page))
            if new_page != current:
                self.mag_page = new_page
                _update_mag_list()

        def _reset_and_update():
            if hasattr(self, "mag_page"):
                try:
                    self.mag_page = 0
                except Exception:
                    setattr(self, "mag_page", 0)
            _update_mag_list()

        if hasattr(search_entry, "bind"):
            search_entry.bind("<Return>", lambda _e: _reset_and_update())
        if hasattr(search_button, "configure"):
            search_button.configure(command=_reset_and_update)
        else:
            search_button.command = _reset_and_update
        self.mag_sold_filter_var.trace_add("write", lambda *_: _reset_and_update())
        if hasattr(sort_menu, "configure"):
            sort_menu.configure(command=lambda *_: _reset_and_update())
        else:
            sort_menu.command = lambda *_: _reset_and_update()
        if hasattr(sold_filter_menu, "configure"):
            sold_filter_menu.configure(command=lambda *_: _reset_and_update())
        else:
            sold_filter_menu.command = lambda *_: _reset_and_update()
        _update_mag_list()

        btn_frame = ctk.CTkFrame(self.magazyn_frame, fg_color=BG_COLOR)
        btn_frame.pack(pady=5)

        def _close_mag_window():
            """Return to the previous screen and remove magazyn bindings."""
            mag_frame = getattr(self, "mag_list_frame", None)
            if mag_frame is not None:
                unbind = getattr(mag_frame, "unbind", None)
                if callable(unbind) and getattr(self, "_mag_bind_id", None):
                    unbind("<Configure>", self._mag_bind_id)
                canvas = getattr(mag_frame, "_parent_canvas", None)
                canvas_unbind = getattr(canvas, "unbind", None)
                if callable(canvas_unbind) and getattr(self, "_mag_canvas_bind_id", None):
                    try:
                        canvas_unbind("<Configure>", self._mag_canvas_bind_id)
                    except Exception:
                        pass
            self._mag_canvas_bind_id = None
            if getattr(self, "_root_mag_bind_id", None):
                root_unbind = getattr(current_root, "unbind", None)
                if callable(root_unbind):
                    root_unbind("<Configure>", self._root_mag_bind_id)
            self._mag_bind_id = None
            self._root_mag_bind_id = None
            if hasattr(self, "back_to_welcome"):
                self.back_to_welcome()

        self.create_button(
            btn_frame,
            text="Odśwież",
            command=self.refresh_magazyn,
            fg_color=FETCH_BUTTON_COLOR,
        ).pack(side="left", padx=5)

        self.create_button(
            btn_frame,
            text="Powrót",
            command=_close_mag_window,
            fg_color=NAV_BUTTON_COLOR,
        ).pack(side="left", padx=5)

        stats_frame = ctk.CTkFrame(self.magazyn_frame, fg_color=BG_COLOR)
        # Center statistics below the action buttons
        stats_frame.pack(pady=(0, 10), anchor="center")

        font = ("Segoe UI", 16, "bold")
        # Prefer Shoper API statistics for sold/unsold; fallback to CSV
        try:
            from .stats_service import get_cached_or_compute
            client = getattr(self, "shoper_client", None)
            if client is None:
                inv = getattr(self, "inventory_service", None) or WarehouseInventoryService.create_default()
                client = getattr(inv, "_client", None)
            api_stats = get_cached_or_compute(client) if client else None
        except Exception:
            api_stats = None
        if api_stats:
            unsold_count = int(api_stats.get("unsold_count", 0))
            unsold_total = float(api_stats.get("unsold_total", 0.0))
            sold_count = int(api_stats.get("sold_count", 0))
            sold_total = float(api_stats.get("sold_total", 0.0))
        else:
            unsold_count, unsold_total, sold_count, sold_total = csv_utils.get_inventory_stats()
        if not getattr(self, "mag_card_rows", []):
            messagebox.showinfo("Magazyn", "Brak kart w magazynie")
        self.mag_inventory_count_label = ctk.CTkLabel(
            stats_frame,
            text=f"📊 Łączna liczba kart: {unsold_count}",
            text_color=TEXT_COLOR,
            font=font,
        )
        self.mag_inventory_count_label.pack()
        self.mag_inventory_value_label = ctk.CTkLabel(
            stats_frame,
            text=f"💰 Łączna wartość: {unsold_total:.2f} PLN",
            text_color="#FFD700",
            font=font,
        )
        self.mag_inventory_value_label.pack()
        self.mag_sold_count_label = ctk.CTkLabel(
            stats_frame,
            text=f"Sprzedane karty: {sold_count}",
            text_color=TEXT_COLOR,
            font=font,
        )
        self.mag_sold_count_label.pack()
        self.mag_sold_value_label = ctk.CTkLabel(
            stats_frame,
            text=f"Wartość sprzedanych: {sold_total:.2f} PLN",
            text_color=TEXT_COLOR,
            font=font,
        )
        self.mag_sold_value_label.pack()

        # legend for color coding in the storage view
        legend_frame = ctk.CTkFrame(self.magazyn_frame, fg_color=BG_COLOR)
        legend_frame.pack(pady=(0, 10))
        legend_items = [
            (FREE_COLOR, "≥30% free"),
            (OCCUPIED_COLOR, "Occupied capacity segment"),
            (SOLD_COLOR, "Sold item"),
        ]
        for color, desc in legend_items:
            swatch = ctk.CTkLabel(legend_frame, text="", width=15, height=15, fg_color=color)
            swatch.pack(side="left", padx=5)
            ctk.CTkLabel(
                legend_frame, text=desc, text_color=TEXT_COLOR
            ).pack(side="left", padx=(0, 10))
            try:
                Tooltip(swatch, desc)
            except Exception as exc:
                logger.exception("Failed to create tooltip")

        self.refresh_magazyn()
        # Ensure the statistics reflect the latest warehouse state
        if hasattr(self, "update_inventory_stats"):
            try:
                self.update_inventory_stats()
            except Exception as exc:
                logger.exception("Failed to update inventory stats")

    def open_magazyn_window(self):
        """Legacy wrapper for :meth:`show_magazyn_view`.

        Existing callers expecting ``open_magazyn_window`` can still invoke it,
        but it simply delegates to :meth:`show_magazyn_view` and renders the
        view inside the main application window.
        """
        self.show_magazyn_view()

    def compute_box_occupancy(self) -> dict[int, int]:
        """Return dictionary of used slots per storage box."""
        return storage.compute_box_occupancy()

    def repack_column(self, box: int, column: int):
        """Renumber codes in the given column so there are no gaps."""
        storage.repack_column(box, column)
        self.refresh_magazyn()

    def refresh_home_preview(self):
        """Refresh box preview on the welcome screen."""
        if not getattr(self, "home_percent_labels", None):
            return

        inventory_service = getattr(self, "inventory_service", None)
        if inventory_service is None:
            inventory_service = WarehouseInventoryService.create_default()
            try:
                setattr(self, "inventory_service", inventory_service)
            except Exception:
                pass

        try:
            snapshot = inventory_service.get_snapshot()
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Failed to load inventory snapshot for home preview")
            snapshot = None

        column_occ: dict[int, dict[int, int]] = {}
        if snapshot is not None:
            for (box, column), count in snapshot.column_occupancy.items():
                column_occ.setdefault(box, {})[column] = count

        for box, lbl in self.home_percent_labels.items():
            columns = BOX_COLUMNS.get(box, STANDARD_BOX_COLUMNS)
            total_capacity = BOX_CAPACITY_MAP.get(
                box, columns * BOX_COLUMN_CAPACITY
            )
            box_data = column_occ.get(box, {})
            box_used = sum(box_data.values())
            value = box_used / total_capacity if total_capacity else 0
            lbl.configure(text=f"{value * 100:.0f}%", text_color=_occupancy_color(value))

            canvas = self.home_box_canvases.get(box)
            if canvas is not None:
                draw_box_usage(canvas, box, box_data)

    def refresh_magazyn(self):
        """Refresh storage view and update column usage bars."""
        inventory_service = getattr(self, "inventory_service", None)
        if inventory_service is None:
            inventory_service = WarehouseInventoryService.create_default()
            try:
                setattr(self, "inventory_service", inventory_service)
            except Exception:
                pass

        try:
            current_version = inventory_service.get_version()
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Failed to obtain inventory version")
            current_version = self._mag_inventory_version

        previous_version = getattr(self, "_mag_inventory_version", None)
        if previous_version is None:
            legacy_version = getattr(self, "_mag_csv_mtime", None)
            if legacy_version is not None:
                previous_version = legacy_version
                try:
                    setattr(self, "_mag_inventory_version", legacy_version)
                except Exception:
                    pass

        if previous_version != current_version:
            reload_fn = getattr(self, "reload_mag_cards", None)
            if callable(reload_fn):
                reload_fn(force=True)
        update_fn = getattr(self, "_update_mag_list", None)
        if callable(update_fn):
            try:
                update_fn()
            except Exception:  # pragma: no cover - defensive logging
                logger.exception("Failed to update magazyn list")

        if not getattr(self, "mag_progressbars", None):
            return

        col_occ = getattr(self, "_mag_column_occ", {})

        for (box, col), bar in self.mag_progressbars.items():
            filled = col_occ.get((box, col), 0)
            columns = BOX_COLUMNS.get(box, STANDARD_BOX_COLUMNS)
            total_capacity = BOX_CAPACITY_MAP.get(
                box, columns * BOX_COLUMN_CAPACITY
            )
            col_capacity = total_capacity / columns if columns else BOX_COLUMN_CAPACITY
            value = filled / col_capacity if col_capacity else 0
            bar.set(value)
            lbl = self.mag_percent_labels.get((box, col))
            if lbl:
                lbl.configure(text=f"{value * 100:.0f}%", text_color=_occupancy_color(value))

        if hasattr(self, "update_inventory_stats"):
            try:
                self.update_inventory_stats()
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.exception("Failed to update inventory stats")

    def show_card_details(self, row: dict):
        """Display details for a selected warehouse card."""

        top = ctk.CTkToplevel(self.root)
        if hasattr(top, "transient"):
            top.transient(self.root)
        if hasattr(top, "grab_set"):
            top.grab_set()
        if hasattr(top, "lift"):
            top.lift()
        if hasattr(top, "focus_force"):
            top.focus_force()

        def close_details():
            if hasattr(top, "grab_release"):
                top.grab_release()
            top.destroy()

        if hasattr(top, "protocol"):
            top.protocol("WM_DELETE_WINDOW", close_details)
        top.title(row.get("name", _("Karta")))
        if hasattr(top, "overrideredirect"):
            top.overrideredirect(True)
        # ensure enough space for side-by-side layout
        if hasattr(top, "geometry"):
            top.geometry("600x400")
            try:
                top.minsize(600, 400)
            except tk.TclError:
                pass

        container = ctk.CTkFrame(top)
        container.pack(expand=True, fill="both", padx=10, pady=10)

        left = ctk.CTkFrame(container)
        left.pack(side="left", padx=(0, 10), pady=10)

        right = ctk.CTkFrame(container)
        right.pack(side="left", fill="both", expand=True, pady=10)

        img_path = row.get("image") or ""
        img = _load_image(img_path)
        text = ""
        if img is None:
            logger.info("Missing image for %s", img_path)
            img = Image.new("RGB", (300, 300), "#111111")
            text = "Brak skanu"
        img.thumbnail((300, 300))
        photo = _create_image(img)
        img_lbl = ctk.CTkLabel(left, image=photo, text=text, compound="center", text_color="white")
        img_lbl.image = photo  # keep reference
        img_lbl.pack()

        fields = [
            ("name", "Name"),
            ("number", "Number"),
            ("set", "Set"),
            ("price", "Price"),
            ("warehouse_code", "Warehouse Code"),
        ]
        row_idx = 0
        selected_var = None
        selected_default = ""
        for key, label in fields:
            val = row.get(key, "")
            if key == "warehouse_code":
                codes = [c.strip() for c in str(val).split(";") if c.strip()]
                if codes:
                    selected_default = codes[0]
                    pattern = re.compile(r"K(\d+)R(\d+)P(\d+)")
                    parsed = []
                    for code in codes:
                        m = pattern.fullmatch(code)
                        if m:
                            parsed.append((code, m.group(1), m.group(2), m.group(3)))
                        else:  # pragma: no cover - unexpected format
                            parsed.append((code, "", "", ""))

                    if len(parsed) > 1:
                        ctk.CTkLabel(
                            right,
                            text=_("Kody magazynowe:"),
                            font=("Inter", 16),
                        ).grid(row=row_idx, column=0, sticky="w", pady=2)
                        row_idx += 1
                        try:
                            selected_var = tk.StringVar(value=selected_default)
                        except (tk.TclError, RuntimeError):
                            selected_var = SimpleNamespace(get=lambda: selected_default)

                        def update_labels(selected: str) -> None:
                            info = next((p for p in parsed if p[0] == selected), parsed[0])
                            karton_lbl.configure(text=f"Karton: {info[1]}")
                            kolumna_lbl.configure(text=f"Kolumna: {info[2]}")
                            pozycja_lbl.configure(text=f"Pozycja: {info[3]}")

                        ctk.CTkOptionMenu(
                            right,
                            values=[p[0] for p in parsed],
                            variable=selected_var,
                            command=update_labels,
                        ).grid(row=row_idx, column=0, sticky="w", pady=2)
                        row_idx += 1

                        karton_lbl = ctk.CTkLabel(
                            right,
                            text=f"Karton: {parsed[0][1]}",
                            font=("Inter", 16),
                        )
                        karton_lbl.grid(row=row_idx, column=0, sticky="w", pady=2)
                        row_idx += 1
                        kolumna_lbl = ctk.CTkLabel(
                            right,
                            text=f"Kolumna: {parsed[0][2]}",
                            font=("Inter", 16),
                        )
                        kolumna_lbl.grid(row=row_idx, column=0, sticky="w", pady=2)
                        row_idx += 1
                        pozycja_lbl = ctk.CTkLabel(
                            right,
                            text=f"Pozycja: {parsed[0][3]}",
                            font=("Inter", 16),
                        )
                        pozycja_lbl.grid(row=row_idx, column=0, sticky="w", pady=2)
                        row_idx += 1
                        continue

                    # single code
                    c = parsed[0]
                    ctk.CTkLabel(
                        right,
                        text=f"Karton: {c[1]}",
                        font=("Inter", 16),
                    ).grid(row=row_idx, column=0, sticky="w", pady=2)
                    row_idx += 1
                    ctk.CTkLabel(
                        right,
                        text=f"Kolumna: {c[2]}",
                        font=("Inter", 16),
                    ).grid(row=row_idx, column=0, sticky="w", pady=2)
                    row_idx += 1
                    ctk.CTkLabel(
                        right,
                        text=f"Pozycja: {c[3]}",
                        font=("Inter", 16),
                    ).grid(row=row_idx, column=0, sticky="w", pady=2)
                    row_idx += 1
                    continue

            ctk.CTkLabel(
                right,
                text=f"{label}: {val}",
                font=("Inter", 16),
            ).grid(row=row_idx, column=0, sticky="w", pady=2)
            row_idx += 1

        buttons_frame = ctk.CTkFrame(top)
        buttons_frame.pack(side="bottom", pady=10)

        ctk.CTkButton(
            buttons_frame,
            text="Sprzedano",
            command=lambda: self.mark_as_sold(
                row,
                top,
                selected_var.get() if selected_var is not None else selected_default,
            ),
            fg_color=SAVE_BUTTON_COLOR,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            buttons_frame,
            text="Zamknij",
            command=close_details,
            fg_color=NAV_BUTTON_COLOR,
        ).pack(side="left", padx=5)

    def mark_as_sold(
        self,
        row: dict,
        window=None,
        warehouse_code: Optional[str] = None,
    ):
        """Mark the card as sold, update CSV and refresh views."""

        codes = [
            c.strip()
            for c in str(row.get("warehouse_code", "")).split(";")
            if c.strip()
        ]
        target = warehouse_code or (codes[0] if codes else "")
        product_code = csv_utils.infer_product_code(row)
        counts = Counter({product_code: 1}) if product_code else Counter()
        success = self.complete_order(
            row,
            selected_warehouses=[target] if target else [],
            product_counts=counts,
        )
        if not success:
            return

        # Locally record the chosen code as sold for immediate UI update
        try:
            if target:
                self._locally_sold_codes.add(str(target).strip())
        except Exception:
            pass

        if window is not None:
            try:
                window.destroy()
            except tk.TclError:
                pass

        # Refresh the magazyn view in-place rather than reopening the window.
        if hasattr(self, "refresh_magazyn"):
            try:
                self.refresh_magazyn()
            except Exception:
                logger.exception("Failed to refresh magazyn view")
        elif hasattr(self, "show_magazyn_view"):
            # Fallback for environments where the magazyn view was not yet
            # initialised; rebuild it inside the main window.
            try:
                self.show_magazyn_view()
            except Exception:
                logger.exception("Failed to display magazyn view")

    def toggle_sold(self, row: dict, window=None):
        """Inform the user that manual CSV toggling is no longer available."""

        messagebox.showinfo(
            "Magazyn",
            _(
                "Zmiana statusu sprzedane musi zostać wykonana bezpośrednio w panelu Shoper."
            ),
        )
        if window is not None:
            try:
                window.destroy()
            except tk.TclError:
                pass

    def setup_pricing_ui(self):
        """UI for quick card price lookup."""
        if self.start_frame is not None:
            self.start_frame.destroy()
            self.start_frame = None
        if getattr(self, "pricing_frame", None):
            self.pricing_frame.destroy()
        # Set a sensible minimum size and allow resizing
        self.root.minsize(1200, 800)
        self.pricing_frame = tk.Frame(
            self.root, bg=self.root.cget("background")
        )
        self.pricing_frame.pack(expand=True, fill="both", padx=10, pady=10)

        self.pricing_frame.columnconfigure(0, weight=1)
        self.pricing_frame.columnconfigure(1, weight=1)
        self.pricing_frame.rowconfigure(1, weight=1)

        logo_path = os.path.join(os.path.dirname(__file__), "banner22.png")
        if os.path.exists(logo_path):
            logo_img = load_rgba_image(logo_path)
            if logo_img:
                logo_img.thumbnail((200, 80))
                self.pricing_logo_photo = _create_image(logo_img)
                ctk.CTkLabel(
                    self.pricing_frame,
                    image=self.pricing_logo_photo,
                    text="",
                ).grid(row=0, column=0, columnspan=2, pady=(0, 10))

        self.input_frame = tk.Frame(
            self.pricing_frame, bg=self.root.cget("background")
        )
        self.input_frame.grid(row=1, column=0, sticky="nsew")

        self.image_frame = tk.Frame(
            self.pricing_frame, bg=self.root.cget("background")
        )
        self.image_frame.grid(row=1, column=1, sticky="nsew")

        self.input_frame.columnconfigure(0, weight=1)
        self.input_frame.columnconfigure(1, weight=1)
        self.input_frame.rowconfigure(5, weight=1)

        tk.Label(
            self.input_frame, text="Nazwa", bg=self.root.cget("background")
        ).grid(row=0, column=0, sticky="e")
        self.price_name_entry = ctk.CTkEntry(
            self.input_frame, width=200, placeholder_text="Nazwa karty"
        )
        self.price_name_entry.grid(row=0, column=1, sticky="ew")

        tk.Label(
            self.input_frame, text="Numer", bg=self.root.cget("background")
        ).grid(row=1, column=0, sticky="e")
        self.price_number_entry = ctk.CTkEntry(
            self.input_frame, width=200, placeholder_text="Numer"
        )
        self.price_number_entry.grid(row=1, column=1, sticky="ew")

        tk.Label(
            self.input_frame, text="Set", bg=self.root.cget("background")
        ).grid(row=2, column=0, sticky="e")
        self.price_set_entry = ctk.CTkEntry(
            self.input_frame, width=200, placeholder_text="Set"
        )
        self.price_set_entry.grid(row=2, column=1, sticky="ew")

        self.price_reverse_var = tk.BooleanVar()
        ctk.CTkCheckBox(
            self.input_frame,
            text="Reverse",
            variable=self.price_reverse_var,
        ).grid(row=3, column=0, columnspan=2, pady=5)

        self.price_reverse_var.trace_add("write", lambda *a: self.on_reverse_toggle())

        controls_frame = ctk.CTkFrame(
            self.image_frame,
            fg_color=BG_COLOR,
        )
        controls_frame.pack(fill="x", pady=(0, 10))
        controls_frame.columnconfigure(3, weight=1)

        ctk.CTkLabel(
            controls_frame,
            text="Widok:",
            text_color=TEXT_COLOR,
        ).grid(row=0, column=0, padx=(10, 5), pady=5, sticky="w")

        self._pricing_view_map = {"Lista": "list", "Siatka": "grid"}
        self.pricing_view_mode = tk.StringVar(value="list")
        self.pricing_view_display_var = ctk.StringVar(value="Lista")
        self.pricing_view_switch = ctk.CTkSegmentedButton(
            controls_frame,
            values=list(self._pricing_view_map.keys()),
            command=self.on_pricing_view_change,
            variable=self.pricing_view_display_var,
        )
        self.pricing_view_switch.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        self.pricing_view_switch.set("Lista")

        ctk.CTkLabel(
            controls_frame,
            text="Sortowanie:",
            text_color=TEXT_COLOR,
        ).grid(row=0, column=2, padx=(20, 5), pady=5, sticky="w")

        self._pricing_sort_map = {"Nazwa": "name", "Cena": "price"}
        self.pricing_sort_key = tk.StringVar(value="name")
        self.pricing_sort_display_var = ctk.StringVar(value="Nazwa")
        self.pricing_sort_menu = ctk.CTkOptionMenu(
            controls_frame,
            values=list(self._pricing_sort_map.keys()),
            command=self.on_pricing_sort_change,
            variable=self.pricing_sort_display_var,
        )
        self.pricing_sort_menu.grid(row=0, column=3, padx=5, pady=5, sticky="w")
        self.pricing_sort_menu.set("Nazwa")

        btn_frame = tk.Frame(
            self.input_frame, bg=self.root.cget("background")
        )
        btn_frame.grid(row=4, column=0, columnspan=2, pady=5, sticky="ew")
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)

        self.create_button(
            btn_frame,
            text="Wyszukaj",
            command=self.run_pricing_search,
            width=120,
            fg_color=FETCH_BUTTON_COLOR,
        ).grid(row=0, column=0, padx=5)

        self.create_button(
            btn_frame,
            text="Wyczyść",
            command=self.clear_price_pool,
            width=120,
            fg_color=NAV_BUTTON_COLOR,
        ).grid(row=0, column=1, padx=5)

        self.result_frame = tk.Frame(
            self.image_frame, bg=self.root.cget("background")
        )
        self.result_frame.pack(expand=True, fill="both", pady=10)

        self.search_results: list[dict[str, Any]] = []
        self.search_result_images: list[Any] = []
        self.search_result_logo_images: list[Any] = []
        self._primary_search_result: Optional[dict[str, Any]] = None

        self.pool_frame = tk.Frame(
            self.pricing_frame, bg=self.root.cget("background")
        )
        self.pool_frame.grid(row=2, column=0, columnspan=2, pady=5)
        self.pool_total_label = tk.Label(
            self.pool_frame,
            text="Suma puli: 0.00",
            bg=self.root.cget("background"),
            fg=TEXT_COLOR,
        )
        self.pool_total_label.pack(side="left")
        self.create_button(
            self.pool_frame,
            text="Powrót",
            command=self.back_to_welcome,
            width=120,
            fg_color=NAV_BUTTON_COLOR,
        ).pack(side="left", padx=5)

    def run_pricing_search(self):
        """Fetch and display pricing information."""
        name = self.price_name_entry.get()
        number = self.price_number_entry.get()
        set_name = self.price_set_entry.get()
        results = self.fetch_card_variants(name, number, set_name)
        self.search_results = results
        self.price_labels = []
        self.result_image_label = None
        self.set_logo_label = None
        self.add_pool_button = None
        self.card_info_labels = []
        if not results:
            for w in self.result_frame.winfo_children():
                w.destroy()
            self._primary_search_result = None
            messagebox.showinfo("Brak wyników", "Nie znaleziono karty.")
            return
        self.render_pricing_results()

    def render_pricing_results(self):
        """Render pricing search results according to current settings."""

        for widget in self.result_frame.winfo_children():
            widget.destroy()

        results = getattr(self, "search_results", [])
        if not results:
            ctk.CTkLabel(
                self.result_frame,
                text="Brak wyników do wyświetlenia.",
                text_color=TEXT_COLOR,
            ).pack(pady=20)
            self._primary_search_result = None
            return

        sorted_results = self._get_sorted_search_results(results)
        self.search_result_images = []
        self.search_result_logo_images = []
        self._primary_search_result = sorted_results[0] if sorted_results else None

        if self._primary_search_result:
            base_rate = self._primary_search_result.get("eur_pln_rate")
            price_eur = self._primary_search_result.get("price_eur")
            price_pln = self._primary_search_result.get("price_pln")
            if price_eur is not None and base_rate is None:
                try:
                    base_rate = float(self.get_exchange_rate())
                except (TypeError, ValueError):
                    base_rate = None
            self.current_price_info = {
                "price_pln": price_pln,
                "price_eur": price_eur or 0,
                "eur_pln_rate": base_rate or 0,
            }
        else:
            self.current_price_info = None

        view_mode = self.pricing_view_mode.get()
        if view_mode == "grid":
            self.render_results_grid(sorted_results)
        else:
            self.render_results_list(sorted_results)

    def _get_sorted_search_results(self, results: list[dict[str, Any]]):
        key = self.pricing_sort_key.get()
        reverse_flag = False

        if key == "price":
            def sort_key(res: dict[str, Any]):
                price = self._get_result_price(res)
                if price is None:
                    return (1, float("inf"), (res.get("name") or "").lower())
                return (0, price, (res.get("name") or "").lower())

            sorted_results = sorted(results, key=sort_key, reverse=reverse_flag)
        else:
            sorted_results = sorted(
                results,
                key=lambda res: (res.get("name") or "").lower(),
                reverse=reverse_flag,
            )
        return sorted_results

    def _get_result_price(self, result: dict[str, Any]) -> Optional[float]:
        price_pln = result.get("price_pln")
        if price_pln in {None, ""}:
            return None
        price = self.apply_variant_multiplier(
            price_pln, is_reverse=self.price_reverse_var.get()
        )
        try:
            return float(price)
        except (TypeError, ValueError):
            return None

    def _format_result_price(self, result: dict[str, Any]) -> str:
        price = self._get_result_price(result)
        if price is None:
            return "Cena: brak danych"
        return f"Cena: {price:.2f} PLN"

    def _build_result_image(self, url: str, size: tuple[int, int]) -> Optional[Any]:
        if not url:
            return None
        img = _get_thumbnail(url, size)
        if not img:
            return None
        return _create_image(img.copy()) if hasattr(img, "copy") else _create_image(img)

    def render_results_list(self, results: list[dict[str, Any]]):
        container = ctk.CTkFrame(self.result_frame, fg_color=BG_COLOR)
        container.pack(fill="both", expand=True)

        for result in results:
            item_frame = ctk.CTkFrame(
                container,
                fg_color=LIGHT_BG_COLOR,
                corner_radius=8,
            )
            item_frame.pack(fill="x", padx=10, pady=6)
            item_frame.grid_columnconfigure(1, weight=1)

            thumb_photo = self._build_result_image(result.get("image_url"), (160, 220))
            thumb_label = ctk.CTkLabel(item_frame, text="")
            thumb_label.grid(row=0, column=0, rowspan=3, padx=10, pady=10)
            if thumb_photo:
                thumb_label.configure(image=thumb_photo)
                thumb_label.image = thumb_photo
                self.search_result_images.append(thumb_photo)

            name = result.get("name") or "Nieznana karta"
            number = result.get("number") or "-"
            set_name = result.get("set") or "-"

            ctk.CTkLabel(
                item_frame,
                text=name,
                text_color=TEXT_COLOR,
                font=("Segoe UI", 18, "bold"),
            ).grid(row=0, column=1, sticky="w", padx=5, pady=(10, 2))

            ctk.CTkLabel(
                item_frame,
                text=f"#{number} | {set_name}",
                text_color=TEXT_COLOR,
                font=("Segoe UI", 14),
            ).grid(row=1, column=1, sticky="w", padx=5)

            ctk.CTkLabel(
                item_frame,
                text=self._format_result_price(result),
                text_color=TEXT_COLOR,
                font=("Segoe UI", 14),
            ).grid(row=2, column=1, sticky="w", padx=5, pady=(0, 10))

            logo_photo = self._build_result_image(result.get("set_logo_url"), (120, 40))
            if logo_photo:
                logo_label = ctk.CTkLabel(item_frame, text="", image=logo_photo)
                logo_label.grid(row=0, column=2, rowspan=2, padx=10, pady=10)
                logo_label.image = logo_photo
                self.search_result_logo_images.append(logo_photo)

            add_button = ctk.CTkButton(
                item_frame,
                text="Dodaj do kolekcji",
                width=180,
                height=36,
                fg_color=SAVE_BUTTON_COLOR,
                hover_color=HOVER_COLOR,
                command=lambda res=result: self.add_search_result_to_collection(res),
                font=("Segoe UI", 16, "bold"),
            )
            button_column = 3 if logo_photo else 2
            add_button.grid(
                row=0,
                column=button_column,
                rowspan=3,
                padx=10,
                pady=10,
                sticky="e",
            )

    def render_results_grid(self, results: list[dict[str, Any]]):
        grid_container = tk.Frame(
            self.result_frame,
            bg=self.root.cget("background"),
        )
        grid_container.pack(fill="both", expand=True)

        columns = 3
        for col in range(columns):
            grid_container.grid_columnconfigure(col, weight=1)

        for index, result in enumerate(results):
            row, col = divmod(index, columns)
            card_frame = ctk.CTkFrame(
                grid_container,
                fg_color=LIGHT_BG_COLOR,
                corner_radius=12,
            )
            card_frame.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")

            thumb_photo = self._build_result_image(result.get("image_url"), (200, 260))
            image_label = ctk.CTkLabel(card_frame, text="")
            image_label.pack(padx=10, pady=(12, 6))
            if thumb_photo:
                image_label.configure(image=thumb_photo)
                image_label.image = thumb_photo
                self.search_result_images.append(thumb_photo)

            name = result.get("name") or "Nieznana karta"
            number = result.get("number") or "-"
            set_name = result.get("set") or "-"
            price_text = self._format_result_price(result)

            ctk.CTkLabel(
                card_frame,
                text=name,
                text_color=TEXT_COLOR,
                font=("Segoe UI", 16, "bold"),
            ).pack(padx=10, pady=(0, 4))

            ctk.CTkLabel(
                card_frame,
                text=f"#{number} | {set_name}",
                text_color=TEXT_COLOR,
                font=("Segoe UI", 14),
            ).pack(padx=10)

            ctk.CTkLabel(
                card_frame,
                text=price_text,
                text_color=TEXT_COLOR,
                font=("Segoe UI", 14),
            ).pack(padx=10, pady=(4, 6))

            logo_photo = self._build_result_image(result.get("set_logo_url"), (120, 40))
            if logo_photo:
                logo_label = ctk.CTkLabel(card_frame, text="", image=logo_photo)
                logo_label.pack(padx=10, pady=(4, 10))
                logo_label.image = logo_photo
                self.search_result_logo_images.append(logo_photo)

            add_button = ctk.CTkButton(
                card_frame,
                text="+",
                width=36,
                height=36,
                fg_color=SAVE_BUTTON_COLOR,
                hover_color=HOVER_COLOR,
                font=("Segoe UI", 18, "bold"),
                command=lambda res=result: self.add_search_result_to_collection(res),
            )
            add_button.place(in_=image_label, relx=0.95, rely=0.05, anchor="ne")

    def on_pricing_view_change(self, selected_label: str):
        value = self._pricing_view_map.get(selected_label)
        if value:
            self.pricing_view_mode.set(value)
        if getattr(self, "search_results", None):
            self.render_pricing_results()

    def on_pricing_sort_change(self, selected_label: str):
        key = self._pricing_sort_map.get(selected_label)
        if key:
            self.pricing_sort_key.set(key)
        if getattr(self, "search_results", None):
            self.render_pricing_results()

    def add_search_result_to_collection(self, result: dict[str, Any]):
        if not result:
            return

        collection_entry = {
            "nazwa": result.get("name", ""),
            "numer": result.get("number", ""),
            "set": result.get("set", ""),
        }

        price_value = self._get_result_price(result)
        if price_value is not None:
            collection_entry["cena"] = f"{price_value:.2f}"
        else:
            collection_entry["cena"] = ""

        if getattr(self, "output_data", None) is None:
            self.output_data = []
        self.output_data.append(collection_entry)

        message = (
            f"Dodano do kolekcji: {collection_entry['nazwa']} "
            f"({collection_entry['numer']})"
        )
        try:
            self.log(message)
        except AttributeError:
            logger.info(message)
        try:
            messagebox.showinfo("Sukces", message)
        except tk.TclError:
            logger.info("%s", message)

    def display_price_info(self, info, is_reverse):
        """Show pricing data with optional reverse multiplier."""
        price_pln = self.apply_variant_multiplier(
            info["price_pln"], is_reverse=is_reverse
        )
        price_80 = round(price_pln * 0.8, 2)
        if not getattr(self, "price_labels", None):
            eur = tk.Label(
                self.result_frame,
                text=f"Cena EUR: {info['price_eur']}",
                fg="blue",
                bg=self.root.cget("background"),
            )
            rate = tk.Label(
                self.result_frame,
                text=f"Kurs EUR→PLN: {info['eur_pln_rate']}",
                fg="gray",
                bg=self.root.cget("background"),
            )
            pln = tk.Label(
                self.result_frame,
                text=f"Cena PLN: {price_pln}",
                fg="green",
                bg=self.root.cget("background"),
            )
            pln80 = tk.Label(
                self.result_frame,
                text=f"80% ceny PLN: {price_80}",
                fg="red",
                bg=self.root.cget("background"),
            )
            for lbl in (eur, rate, pln, pln80):
                lbl.pack()
            self.add_pool_button = self.create_button(
                self.result_frame,
                text="Dodaj do puli",
                command=self.add_to_price_pool,
                fg_color=SAVE_BUTTON_COLOR,
            )
            self.add_pool_button.pack(pady=5)
            self.price_labels = [eur, rate, pln, pln80]
        else:
            eur, rate, pln, pln80 = self.price_labels
            eur.config(text=f"Cena EUR: {info['price_eur']}")
            rate.config(text=f"Kurs EUR→PLN: {info['eur_pln_rate']}")
            pln.config(text=f"Cena PLN: {price_pln}")
            pln80.config(text=f"80% ceny PLN: {price_80}")

    def on_reverse_toggle(self, *args):
        if getattr(self, "search_results", None):
            self.render_pricing_results()
            return
        if getattr(self, "current_price_info", None):
            self.display_price_info(
                self.current_price_info, self.price_reverse_var.get()
            )

    def add_to_price_pool(self):
        price_source = getattr(self, "_primary_search_result", None)
        if price_source:
            price = self._get_result_price(price_source)
        elif getattr(self, "current_price_info", None):
            price = self.apply_variant_multiplier(
                self.current_price_info["price_pln"],
                is_reverse=self.price_reverse_var.get(),
            )
        else:
            return
        try:
            self.price_pool_total += float(price)
        except (TypeError, ValueError):
            return
        if self.pool_total_label:
            self.pool_total_label.config(
                text=f"Suma puli: {self.price_pool_total:.2f}"
            )

    def clear_price_pool(self):
        self.price_pool_total = 0.0
        if self.pool_total_label:
            self.pool_total_label.config(text="Suma puli: 0.00")

    def back_to_welcome(self):
        if getattr(self, "in_scan", False):
            if not messagebox.askyesno(
                "Potwierdzenie", "Czy na pewno chcesz przerwać?"
            ):
                return
        self.in_scan = False
        self._latest_export_rows = []
        self._summary_warehouse_written = False
        if getattr(self, "pricing_frame", None):
            self.pricing_frame.destroy()
            self.pricing_frame = None
        if getattr(self, "shoper_frame", None):
            self.shoper_frame.destroy()
            self.shoper_frame = None
        if getattr(self, "frame", None):
            self.frame.destroy()
            self.frame = None
        if getattr(self, "magazyn_frame", None):
            self.magazyn_frame.destroy()
            self.magazyn_frame = None
            labels = getattr(self, "mag_card_image_labels", [])
            for i in range(len(labels)):
                labels[i] = None
        if getattr(self, "location_frame", None):
            self.location_frame.destroy()
            self.location_frame = None
        if getattr(self, "auction_frame", None):
            self.auction_frame.destroy()
            self.auction_frame = None
        if getattr(self, "auction_run_window", None):
            try:
                self.auction_run_window.close()
            except Exception:
                pass
            finally:
                self.auction_run_window = None
        if getattr(self, "statistics_frame", None):
            self.statistics_frame.destroy()
            self.statistics_frame = None
        if getattr(self, "auction_preview_window", None):
            try:
                if str(self.auction_preview_window.winfo_exists()) == "1":
                    self.auction_preview_window.destroy()
            except tk.TclError:
                pass
            self.auction_preview_window = None
            self.auction_preview_tree = None
            self.auction_preview_next_var = None
        self.setup_welcome_screen()

    def _create_attribute_dropdown(self, parent, attribute_name, row, column):
        """Helper to create a label and combobox for an attribute."""
        grid_opts = {"padx": 5, "pady": 2, "sticky": "ew"}
        
        group_id_str = self.attributes_by_name.get(attribute_name)
        if not group_id_str:
            logger.warning(f"Attribute '{attribute_name}' not found in attributes_by_name map.")
            return row

        group_id = int(group_id_str)
        attr_data = self.attributes_map.get(str(group_id)) # Ensure key is string if needed
        if not attr_data:
            logger.warning(f"No data for group_id '{group_id}' in attributes_map.")
            return row

        options = list(attr_data.get("options", {}).keys())
        attribute_id = attr_data.get("attribute_id")

        ctk.CTkLabel(parent, text=attribute_name).grid(row=row, column=column, **grid_opts)
        
        entry_key = f'attribute:{group_id}:{attribute_id}'
        self.entries[entry_key] = tk.StringVar()
        dropdown = ctk.CTkComboBox(parent, variable=self.entries[entry_key], values=options)
        dropdown.grid(row=row, column=column + 1, **grid_opts)
        return row + 1

    def submit_product_to_shoper(self):
        """Gathers data from the UI, builds a Shoper product payload, and sends it via the API."""
        try:
            # 1. Gather data from UI
            card_data = {key: var.get() for key, var in self.entries.items()}

            # Basic fields
            name = card_data.get('nazwa', '')
            number = card_data.get('numer', '')
            price = card_data.get('cena', '0')
            quantity = card_data.get('ilosc', '1')
            category_name = card_data.get('kategoria_name', '')

            if not all([name, number, price, category_name]):
                messagebox.showerror("Błąd", "Uzupełnij wszystkie podstawowe pola (Nazwa, Numer, Cena, Kategoria).")
                return

            # 2. Map names to IDs
            category_id = self.categories_map.get(category_name)
            if not category_id:
                messagebox.showerror("Błąd", f"Nie znaleziono ID dla kategorii: {category_name}")
                return

            attributes_payload = {}
            for key, value in card_data.items():
                if not key.startswith('attribute:') or not value:
                    continue
                
                _, group_id_str, attr_id_str = key.split(':')
                group_id = int(group_id_str)
                
                attr_info = self.attributes_map.get(str(group_id)) # Ensure key is string if needed
                if not attr_info:
                    continue

                option_id = attr_info["options"].get(value)
                if option_id:
                    attributes_payload[group_id_str] = { option_id: value }

            # 3. Build the payload
            # Prefer explicit set name from editor; fallback to category display name
            set_display_name = card_data.get("set") or card_data.get("set_name") or category_name
            try:
                product_code = csv_utils.build_product_code(
                    set_display_name or "",
                    number or "",
                    getattr(self, "card_type_var", None).get() if hasattr(self, "card_type_var") else None,
                    None,
                )
            except Exception:
                product_code = f"PKM-{get_set_abbr(set_display_name or category_name).upper()}-{number}"

            shoper_payload = {
                "producer_id": 23, # Assuming "Pokémon" is always 23
                "tax_id": 1, # Assuming 23% VAT is always 1
                "category_id": category_id,
                "categories": [category_id],
                "code": product_code,
                "stock": {
                    "price": price,
                    "stock": quantity,
                    "active": 1,
                    "additional_codes": {
                        "producer": number
                    }
                },
                "translations": {
                    "pl_PL": {
                        "name": name,
                        "short_description": f'<ul><li><strong>{name}</strong></li><li>Zestaw: {category_name}</li><li>Numer karty: {number}</li></ul>',
                        "description": f'<h2>{name} – Pokémon TCG</h2><p><strong>Zestaw:</strong> {category_name}<br><strong>Numer karty:</strong> {number}</p>',
                        "active": 1,
                        "seo_title": f"{name} {number} {category_name}"
                    }
                },
                "attributes": attributes_payload
            }

            # 4. Call ShoperClient
            if not hasattr(self, 'shoper_client') or not self.shoper_client:
                self.ensure_shoper_client()
                if not self.shoper_client:
                    messagebox.showerror("Błąd", "Nie można połączyć się z API Shoper.")
                    return

            self.set_status("Wysyłanie produktu do Shoper...", temporary=False)
            response = self.shoper_client.add_product(shoper_payload)
            product_id = response.get("product_id") or response.get("id")

            if not product_id:
                raise RuntimeError(f"Nie udało się utworzyć produktu w Shoper. Odpowiedź: {response}")

            self.log(f"Produkt utworzony pomyślnie! ID: {product_id}")

            # Upload image
            if self.current_image_path and os.path.exists(self.current_image_path):
                self.set_status(f"Wysyłanie obrazka dla produktu ID: {product_id}...", temporary=False)
                self.shoper_client.upload_product_image(str(product_id), self.current_image_path, is_main=True)
                self.log(f"Obrazek dla produktu ID: {product_id} wysłany pomyślnie.")

            self.set_status("Gotowe!", temporary=True)
            messagebox.showinfo("Sukces", f"Produkt '{name}' został pomyślnie dodany do sklepu z ID: {product_id}")

        except Exception as e:
            logger.exception("Błąd podczas wysyłania produktu do Shoper")
            messagebox.showerror("Błąd krytyczny", f"Wystąpił błąd: {e}")
            self.set_status("Błąd wysyłania", temporary=True)

    def setup_editor_ui(self):
        # Provide a minimum size and allow the editor to expand
        self.root.minsize(1200, 800)
        self.frame = tk.Frame(
            self.root, bg=self.root.cget("background")
        )
        self.frame.pack(expand=True, fill="both", padx=10, pady=10)
        # Allow widgets inside the frame to expand properly
        for i in range(6):
            self.frame.columnconfigure(i, weight=1)
        self.frame.rowconfigure(2, weight=1)

        logo_path = os.path.join(os.path.dirname(__file__), "banner22.png")
        logo_img = load_rgba_image(logo_path) if os.path.exists(logo_path) else None
        if logo_img:
            logo_img.thumbnail((200, 80))
            self.logo_photo = _create_image(logo_img)
        else:
            self.logo_photo = None
        self.logo_label = ctk.CTkLabel(
            self.frame,
            image=self.logo_photo,
            text="",
        )
        self.logo_label.grid(row=0, column=0, columnspan=6, pady=(0, 10))

        # label for the upcoming warehouse code
        self.location_label = ctk.CTkLabel(self.frame, text="", text_color=TEXT_COLOR)
        self.location_label.grid(row=1, column=0, columnspan=6, pady=(0, 10))


        # Bottom frame for action buttons
        self.button_frame = ctk.CTkFrame(
            self.frame, fg_color="transparent"
        )
        # Do not stretch the button frame so that buttons remain centered
        self.button_frame.grid(row=15, column=0, columnspan=6, pady=10, sticky="ew")
        for col in range(5):
            self.button_frame.grid_columnconfigure(col, weight=1)

        button_specs = [
            ("Zakończ i zapisz", self.show_session_summary, SAVE_BUTTON_COLOR),
            ("Powrót", self.back_to_welcome, NAV_BUTTON_COLOR),
            ("\u23ee Poprzednia", self.previous_card, NAV_BUTTON_COLOR),
            ("Nast\u0119pna \u23ed", self.next_card, NAV_BUTTON_COLOR),
            ("\U0001F9FE \u015aci\u0105ga", self.toggle_cheatsheet, NAV_BUTTON_COLOR),
        ]
        self.bottom_buttons: list[ctk.CTkButton] = []
        for col, (text, command, color) in enumerate(button_specs):
            btn = self.create_button(
                self.button_frame,
                text=text,
                command=command,
                fg_color=color,
            )
            btn.grid(row=0, column=col, padx=5, sticky="ew")
            self.bottom_buttons.append(btn)

        # Keep a constant label size so the window does not resize when
        # scans of different dimensions are displayed
        self.image_label = ctk.CTkLabel(self.frame, width=400, height=560)
        self.image_label.grid(row=2, column=0, rowspan=12, sticky="nsew")
        self.image_label.grid_propagate(False)
        # Progress indicator below the card image
        self.progress_frame = ctk.CTkFrame(self.frame, fg_color="transparent")
        self.progress_frame.grid(row=14, column=0, pady=5, sticky="ew")
        self.progress_bar = ctk.CTkProgressBar(self.progress_frame)
        self.progress_bar.pack(fill="x")
        # optional textual progress display
        self.progress_label = ctk.CTkLabel(self.progress_frame, textvariable=self.progress_var)
        self.progress_label.pack()

        # Container for card information fields
        self.info_frame = ctk.CTkFrame(self.frame)
        self.info_frame.grid(
            row=2, column=1, columnspan=4, rowspan=12, padx=10, sticky="nsew"
        )
        self.info_frame.grid_columnconfigure(1, weight=1)
        self.info_frame.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(self.info_frame, text="Informacje o Karcie", font=("Segoe UI", 16, "bold")).grid(
            row=0, column=0, columnspan=4, pady=(5, 10), sticky="w"
        )

        self.entries = {}
        grid_opts = {"padx": 5, "pady": 2, "sticky": "ew"}
        
        # --- Left Column ---
        row = 1
        ctk.CTkLabel(self.info_frame, text="Nazwa").grid(row=row, column=0, **grid_opts)
        self.entries['nazwa'] = ctk.CTkEntry(self.info_frame, placeholder_text="Nazwa karty")
        self.entries['nazwa'].grid(row=row, column=1, **grid_opts)

        row += 1
        ctk.CTkLabel(self.info_frame, text="Numer").grid(row=row, column=0, **grid_opts)
        self.entries['numer'] = ctk.CTkEntry(self.info_frame, placeholder_text="Numer w secie")
        self.entries['numer'].grid(row=row, column=1, **grid_opts)

        row += 1
        ctk.CTkLabel(self.info_frame, text="Cena").grid(row=row, column=0, **grid_opts)
        self.entries['cena'] = ctk.CTkEntry(self.info_frame, placeholder_text="Cena (PLN)")
        self.entries['cena'].grid(row=row, column=1, **grid_opts)

        row += 1
        ctk.CTkLabel(self.info_frame, text="Ilość").grid(row=row, column=0, **grid_opts)
        self.entries['ilosc'] = ctk.CTkEntry(self.info_frame, placeholder_text="Ilość")
        self.entries['ilosc'].grid(row=row, column=1, **grid_opts)
        self.entries['ilosc'].insert(0, "1")


        # --- Right Column (Dynamic Attributes) ---
        row = 1
        ctk.CTkLabel(self.info_frame, text="Zestaw (Kategoria)").grid(row=row, column=2, **grid_opts)
        self.entries['kategoria_name'] = tk.StringVar()
        category_dropdown = ctk.CTkComboBox(self.info_frame, variable=self.entries['kategoria_name'], values=list(self.categories_map.keys()))
        category_dropdown.grid(row=row, column=3, **grid_opts)

        row += 1
        attributes_to_create = ["Jakość", "Język", "Energia", "Wykończenie", "Rzadkość", "Typ karty"]
        for attr_name in attributes_to_create:
            row = self._create_attribute_dropdown(self.info_frame, attr_name, row, 2)

        # --- Action Buttons ---
        row += 1 # Add some space
        self.api_button = self.create_button(
            self.info_frame,
            text="Pobierz cenę",
            command=self.fetch_card_data,
            fg_color=FETCH_BUTTON_COLOR,
            width=120,
        )
        self.api_button.grid(row=row, column=0, columnspan=2, sticky="ew", **grid_opts)

        self.shoper_button = self.create_button(
            self.info_frame,
            text="Wyślij do Shoper",
            command=self.submit_product_to_shoper,
            fg_color=SHOPER_BUTTON_COLOR, # Or another distinct color
            width=120,
        )
        self.shoper_button.grid(row=row, column=2, columnspan=2, sticky="ew", **grid_opts)

        self.log_widget = tk.Text(
            self.frame,
            height=4,
            state="disabled",
            bg=self.root.cget("background"),
            fg="white",
        )
        self.log_widget.grid(row=16, column=0, columnspan=6, sticky="ew")

    def _ensure_attribute_editor(self):
        if getattr(self, "_attribute_editor_initialized", False):
            return
        panel = getattr(self, "attribute_panel", None)
        if panel is None:
            return
        client = getattr(self, "shoper_client", None)
        if not client:
            status = getattr(self, "attribute_status_label", None)
            if status is not None:
                try:
                    status.configure(
                        text="Skonfiguruj Shoper API, aby pobrać atrybuty."
                    )
                except tk.TclError:
                    pass
            return
        try:
            cache = self._refresh_attribute_cache(force=True)
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.warning("Failed to load Shoper attributes: %s", exc)
            status = getattr(self, "attribute_status_label", None)
            if status is not None:
                try:
                    status.configure(text="Nie udało się pobrać atrybutów Shoper.")
                except tk.TclError:
                    pass
            return
        self._build_attribute_editor(cache)
        self._attribute_editor_initialized = True
        if self._pending_attribute_payload:
            self._apply_attribute_data(self._pending_attribute_payload)

    def _refresh_attribute_cache(self, *, force: bool = False) -> dict[str, Any]:
        """Return cached attribute metadata from Shoper.

        The cache is populated on first access or when ``force`` is ``True``.
        Every attribute is normalised with lookup tables so the editor can map
        user selections back to the identifiers expected by Shoper.  Any
        attribute with an unknown or unsupported type is exposed as a text
        field, allowing the UI to remain functional until the schema is
        updated.
        """

        if not force and self._attribute_cache:
            return self._attribute_cache
        client = getattr(self, "shoper_client", None)
        if not client:
            self._attribute_cache = {}
            return {}
        raw = client.get_attributes() or {}
        attr_list = raw.get("list", raw)
        if not isinstance(attr_list, Iterable):
            attr_list = []
        groups: dict[int, dict[str, Any]] = {}
        attributes: dict[int, dict[str, Any]] = {}
        name_map: dict[str, int] = {}
        for item in attr_list:
            if not isinstance(item, Mapping):
                continue
            attr_id_raw = item.get("attribute_id")
            try:
                attr_id = int(attr_id_raw)
            except (TypeError, ValueError):
                continue
            group_raw = item.get("attribute_group_id") or 0
            try:
                group_id = int(group_raw)
            except (TypeError, ValueError):
                group_id = 0
            group_name = (
                item.get("group_name")
                or item.get("attribute_group_name")
                or (item.get("attribute_group") or {}).get("name")
                or (item.get("group") or {}).get("name")
                or f"Grupa {group_id}"
            )
            group_entry = groups.setdefault(
                group_id, {"name": group_name, "attributes": []}
            )
            group_entry["attributes"].append(item)
            prepared = self._prepare_attribute_metadata(item, group_id, group_name)
            attributes[attr_id] = prepared
            attr_name = item.get("name") or item.get("attribute_name")
            if isinstance(attr_name, str) and attr_name.strip():
                name_map[attr_name.strip().lower()] = attr_id
        cache = {"groups": groups, "attributes": attributes, "by_name": name_map}
        self._attribute_cache = cache
        return cache

    @staticmethod
    def _extract_attribute_values(attr: Mapping[str, Any]) -> list[tuple[Any, str]]:
        values_source = (
            attr.get("dictionary")
            or attr.get("values")
            or attr.get("options")
            or []
        )
        items: list[tuple[Any, str]] = []
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
            if isinstance(key, str) and key.isdigit():
                try:
                    key = int(key)
                except ValueError:
                    pass
            if isinstance(label, str):
                label_text = label.strip() or str(key)
            else:
                label_text = str(label) if label is not None else str(key)
            items.append((key, label_text))
        return items

    def _prepare_attribute_metadata(
        self, attr: Mapping[str, Any], group_id: int, group_name: str
    ) -> dict[str, Any]:
        attr_type = str(attr.get("type") or attr.get("input_type") or "").lower()
        values = self._extract_attribute_values(attr)
        values_by_id: dict[Any, str] = {}
        values_by_name: dict[str, Any] = {}
        for key, label in values:
            values_by_id[key] = label
            if isinstance(label, str) and label.strip():
                values_by_name[label.strip().lower()] = key
            values_by_name[str(key).strip().lower()] = key
        multiple = bool(
            attr.get("multiple")
            or attr_type in {"multiselect", "checkbox", "checkboxes"}
        )
        if multiple and values:
            widget_type = "multiselect"
        elif values:
            widget_type = "select"
        else:
            widget_type = "text"
        return {
            "raw": attr,
            "type": attr_type,
            "group_id": group_id,
            "group_name": group_name,
            "values": values,
            "values_by_id": values_by_id,
            "values_by_name": values_by_name,
            "widget_type": widget_type,
        }

    def _clear_attribute_entries(self) -> None:
        for key in list(self.entries.keys()):
            if isinstance(key, str) and key.startswith("attribute:"):
                self.entries.pop(key, None)

    def _build_attribute_editor(self, cache: Mapping[str, Any]) -> None:
        panel = getattr(self, "attribute_panel", None)
        if panel is None:
            return
        status = getattr(self, "attribute_status_label", None)
        if status is not None:
            try:
                status.destroy()
            except tk.TclError:
                pass
            self.attribute_status_label = None
        content = getattr(self, "_attribute_content", None)
        if content is not None:
            try:
                content.destroy()
            except tk.TclError:
                pass
        self._attribute_content = ctk.CTkFrame(panel, fg_color="transparent")
        self._attribute_content.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self._attribute_content.grid_columnconfigure(0, weight=1)
        self._clear_attribute_entries()
        self.attribute_values = {}
        self._attribute_controls = {}
        self._finish_attribute_id = None
        self._finish_value_to_variant = {}
        self._finish_variant_to_value = {}
        self._finish_label_to_value = {}
        self._finish_value_to_label = {}
        groups = cache.get("groups", {}) if isinstance(cache, Mapping) else {}
        if not groups:
            ctk.CTkLabel(
                self._attribute_content,
                text="Brak dostępnych atrybutów.",
                text_color=TEXT_COLOR,
            ).grid(row=0, column=0, sticky="w", padx=5, pady=5)
            return
        def _group_sort(item: tuple[Any, Any]) -> Any:
            key = item[0]
            try:
                return int(key)
            except (TypeError, ValueError):
                return str(key)

        row = 0
        for group_id_raw, group_meta in sorted(groups.items(), key=_group_sort):
            try:
                group_id = int(group_id_raw)
            except (TypeError, ValueError):
                group_id = group_id_raw
            group_frame = ctk.CTkFrame(self._attribute_content, fg_color="transparent")
            top_pad = (6, 12) if row else (0, 12)
            group_frame.grid(row=row, column=0, sticky="ew", padx=5, pady=top_pad)
            group_frame.grid_columnconfigure(1, weight=1)
            row += 1
            attributes = (
                group_meta.get("attributes")
                if isinstance(group_meta, Mapping)
                else []
            )
            attr_row = 0
            for raw_attr in attributes:
                if not isinstance(raw_attr, Mapping):
                    continue
                attr_id_raw = raw_attr.get("attribute_id")
                try:
                    attr_id = int(attr_id_raw)
                except (TypeError, ValueError):
                    continue
                prepared = cache.get("attributes", {}).get(attr_id)
                if not prepared:
                    continue
                attr_name = (
                    raw_attr.get("name")
                    or raw_attr.get("attribute_name")
                    or f"Atrybut {attr_id}"
                )
                ctk.CTkLabel(
                    group_frame,
                    text=str(attr_name),
                    text_color=TEXT_COLOR,
                ).grid(row=attr_row, column=0, sticky="w", padx=(5, 10), pady=4)
                widget_type = prepared.get("widget_type") or "text"
                attr_key = f"attribute:{group_id}:{attr_id}"
                if widget_type == "select":
                    var = tk.StringVar()
                    value_to_label = {
                        key: label for key, label in prepared.get("values", [])
                    }
                    label_to_value = {
                        label: key for key, label in prepared.get("values", [])
                    }
                    display_values = [""] + [label for _, label in prepared.get("values", [])]

                    def _on_select(choice: str, gid=group_id, aid=attr_id, mapping=label_to_value):
                        selected = mapping.get(choice)
                        if selected is None and isinstance(choice, str) and choice.strip():
                            selected = choice.strip()
                        self._store_attribute_value(gid, aid, selected)

                    combo = ctk.CTkComboBox(
                        group_frame,
                        variable=var,
                        values=display_values,
                        width=200,
                        command=_on_select,
                    )
                    combo.grid(row=attr_row, column=1, sticky="ew", padx=5, pady=4)
                    control = {
                        "widget_type": "select",
                        "variable": var,
                        "value_to_label": value_to_label,
                        "meta": prepared,
                    }
                elif widget_type == "multiselect":
                    options_frame = ctk.CTkFrame(group_frame, fg_color="transparent")
                    options_frame.grid(row=attr_row, column=1, sticky="ew", padx=5, pady=4)
                    checkbox_vars: dict[Any, Any] = {}

                    def _on_toggle(gid=group_id, aid=attr_id, frame_vars=checkbox_vars):
                        selected: list[Any] = []
                        for value_id, bool_var in frame_vars.items():
                            try:
                                is_selected = bool(bool_var.get())
                            except Exception:
                                is_selected = False
                            if is_selected:
                                selected.append(value_id)
                        existing = []
                        current = self.attribute_values.get(gid, {}).get(aid)
                        if isinstance(current, list):
                            existing = [val for val in current if val not in frame_vars]
                        if existing:
                            combined = selected + [val for val in existing if val not in selected]
                        else:
                            combined = selected
                        self._store_attribute_value(gid, aid, combined)

                    for idx, (value_id, label) in enumerate(prepared.get("values", [])):
                        bool_var = _create_bool_var(False)
                        checkbox_vars[value_id] = bool_var
                        ctk.CTkCheckBox(
                            options_frame,
                            text=label,
                            variable=bool_var,
                            command=_on_toggle,
                        ).grid(row=idx // 2, column=idx % 2, sticky="w", padx=2, pady=2)
                    options_frame.grid_columnconfigure(0, weight=1)
                    options_frame.grid_columnconfigure(1, weight=1)
                    control = {
                        "widget_type": "multiselect",
                        "checkbox_vars": checkbox_vars,
                        "meta": prepared,
                    }
                else:
                    var = tk.StringVar()

                    def _on_text_change(*_args, gid=group_id, aid=attr_id, variable=var):
                        try:
                            text = variable.get()
                        except tk.TclError:
                            text = ""
                        cleaned = text.strip()
                        self._store_attribute_value(gid, aid, cleaned or None)

                    entry = ctk.CTkEntry(group_frame, textvariable=var, width=200)
                    entry.grid(row=attr_row, column=1, sticky="ew", padx=5, pady=4)
                    try:
                        var.trace_add("write", _on_text_change)
                    except AttributeError:  # pragma: no cover - Tk fallback
                        var.trace("w", lambda *a, **k: _on_text_change())
                    control = {
                        "widget_type": "text",
                        "variable": var,
                        "meta": prepared,
                    }
                attr_row += 1
                adapter = _AttributeEntryAdapter(self, group_id, attr_id)
                self.entries[attr_key] = adapter
                self._attribute_controls[(int(group_id), int(attr_id))] = control
                try:
                    gid_int = int(group_id)
                except (TypeError, ValueError):
                    gid_int = None
                if gid_int == CARD_FINISH_ATTRIBUTE_GROUP_ID:
                    name_norm = _normalize_finish_label(attr_name)
                    if name_norm.startswith("wykonczenie") or name_norm.endswith("finish"):
                        self._register_finish_attribute(int(attr_id), prepared, control)

        pending_finish = getattr(self, "_pending_finish_selection", None)
        if isinstance(pending_finish, CardFinishSelection):
            if self._apply_finish_selection(pending_finish):
                self._pending_finish_selection = None
        self._update_card_finish_display()
        _set_language_attribute_default(self)

    def _register_finish_attribute(
        self,
        attr_id: int,
        prepared: Mapping[str, Any],
        control: Mapping[str, Any] | None,
    ) -> None:
        self._finish_attribute_id = int(attr_id)
        mapping: dict[Any, CardFinishSelection] = {}
        reverse: dict[tuple[str, str], Any] = {}
        label_map: dict[str, Any] = {}
        value_label_map: dict[Any, str] = {}
        values = prepared.get("values") if isinstance(prepared, Mapping) else None
        if isinstance(values, Iterable):
            for value in values:
                try:
                    value_id, label = value
                except (TypeError, ValueError):
                    continue
                label_text = str(label).strip()
                value_label_map[value_id] = label_text
                normalized_label = _normalize_finish_label(label_text)
                code, ball = _deduce_finish_variant(normalized_label)
                code = normalize_card_type_code(code)
                ball_norm = _normalize_ball_suffix(ball)
                selection = CardFinishSelection(
                    code,
                    ball_norm,
                    label_text or None,
                    value_id,
                )
                mapping[value_id] = selection
                key = (selection.code, (selection.ball or ""))
                reverse.setdefault(key, value_id)
                if normalized_label and normalized_label not in label_map:
                    label_map[normalized_label] = value_id
        if isinstance(control, Mapping):
            value_to_label = control.get("value_to_label", {}) or {}
            if isinstance(value_to_label, Mapping):
                for key, label in value_to_label.items():
                    value_label_map.setdefault(key, str(label))
                    normalized_label = _normalize_finish_label(label)
                    if normalized_label and normalized_label not in label_map:
                        label_map[normalized_label] = key
        if mapping:
            self._finish_value_to_variant = mapping
            self._finish_variant_to_value = reverse
            self._finish_label_to_value = label_map
            self._finish_value_to_label = value_label_map
        self._update_card_finish_display()

    def _store_attribute_value(self, group_id: Any, attribute_id: Any, value: Any) -> None:
        try:
            gid = int(group_id)
        except (TypeError, ValueError):
            return
        try:
            aid = int(attribute_id)
        except (TypeError, ValueError):
            return
        changed = False
        if value in (None, "", []):
            group = self.attribute_values.get(gid)
            if isinstance(group, dict) and aid in group:
                previous = group.pop(aid, None)
                if previous is not None:
                    changed = True
                if not group:
                    self.attribute_values.pop(gid, None)
            if changed:
                self._on_attribute_value_changed(gid, aid)
            return
        if isinstance(value, (list, tuple, set)):
            collected: list[Any] = []
            for item in value:
                if isinstance(item, str):
                    stripped = item.strip()
                    if stripped:
                        collected.append(stripped)
                elif item is not None:
                    collected.append(item)
            if not collected:
                group = self.attribute_values.get(gid)
                if isinstance(group, dict) and aid in group:
                    previous = group.pop(aid, None)
                    if previous is not None:
                        changed = True
                    if not group:
                        self.attribute_values.pop(gid, None)
                if changed:
                    self._on_attribute_value_changed(gid, aid)
                return
            value_to_store: Any = list(dict.fromkeys(collected))
        else:
            if isinstance(value, str):
                stripped = value.strip()
                if not stripped:
                    group = self.attribute_values.get(gid)
                    if isinstance(group, dict) and aid in group:
                        previous = group.pop(aid, None)
                        if previous is not None:
                            changed = True
                        if not group:
                            self.attribute_values.pop(gid, None)
                    if changed:
                        self._on_attribute_value_changed(gid, aid)
                    return
                value_to_store = stripped
            else:
                value_to_store = value
        existing_group = self.attribute_values.get(gid)
        if isinstance(existing_group, dict):
            group = existing_group
        else:
            group = {}
            self.attribute_values[gid] = group
        previous = group.get(aid)
        if isinstance(previous, list) and isinstance(value_to_store, list):
            if previous == value_to_store:
                return
        elif previous == value_to_store:
            return
        group[aid] = value_to_store
        self._on_attribute_value_changed(gid, aid)

    def _on_attribute_value_changed(self, group_id: int, attribute_id: int) -> None:
        if group_id == LANGUAGE_ATTRIBUTE_GROUP_ID:
            try:
                self.update_set_options()
            except Exception:
                pass
        if group_id == CARD_FINISH_ATTRIBUTE_GROUP_ID:
            self._update_card_finish_display()

    def _normalize_attribute_selection(
        self, attr_meta: Mapping[str, Any] | None, raw_value: Any
    ) -> list[Any]:
        if attr_meta is None:
            attr_meta = {}
        if isinstance(raw_value, (list, tuple, set)):
            values = list(raw_value)
        elif raw_value in (None, ""):
            return []
        else:
            values = [raw_value]
        normalized: list[Any] = []
        values_by_id = attr_meta.get("values_by_id", {})
        values_by_name = attr_meta.get("values_by_name", {})
        for item in values:
            if isinstance(item, Mapping):
                candidate = (
                    item.get("value_id")
                    or item.get("id")
                    or item.get("value")
                )
                if candidate is not None:
                    normalized.append(candidate)
                    continue
                label = item.get("name") or item.get("label")
                if isinstance(label, str):
                    mapped = values_by_name.get(label.strip().lower())
                    if mapped is not None:
                        normalized.append(mapped)
                        continue
                continue
            if item in values_by_id:
                normalized.append(item)
                continue
            if isinstance(item, str):
                stripped = item.strip()
                if not stripped:
                    continue
                if stripped in values_by_id:
                    normalized.append(stripped)
                    continue
                mapped = values_by_name.get(stripped.lower())
                if mapped is not None:
                    normalized.append(mapped)
                    continue
                try:
                    numeric = int(stripped)
                except ValueError:
                    normalized.append(stripped)
                else:
                    if numeric in values_by_id:
                        normalized.append(numeric)
                    else:
                        normalized.append(numeric)
            else:
                normalized.append(item)
        return normalized

    def _set_attribute_selection(
        self, group_id: int, attribute_id: int, value: Any
    ) -> None:
        control = self._attribute_controls.get((group_id, attribute_id))
        if not control:
            return
        meta = control.get("meta")
        widget_type = control.get("widget_type") or "text"
        normalized = self._normalize_attribute_selection(meta, value)
        if widget_type == "multiselect":
            checkbox_vars = control.get("checkbox_vars", {})
            recognized: list[Any] = []
            extras: list[Any] = []
            for item in normalized:
                if item in checkbox_vars:
                    recognized.append(item)
                else:
                    extras.append(item)
            for option, var in checkbox_vars.items():
                try:
                    var.set(option in recognized)
                except Exception:
                    pass
            combined = recognized + [item for item in extras if item not in recognized]
            self._store_attribute_value(group_id, attribute_id, combined)
        elif widget_type == "select":
            value_to_label = control.get("value_to_label", {})
            chosen = None
            fallback = None
            for item in normalized:
                if item in value_to_label:
                    chosen = item
                    break
                if fallback is None:
                    fallback = item
            var = control.get("variable")
            if chosen is not None:
                label = value_to_label.get(chosen, str(chosen))
                try:
                    var.set(label)
                except Exception:
                    pass
                self._store_attribute_value(group_id, attribute_id, chosen)
            elif fallback is not None:
                try:
                    var.set(str(fallback))
                except Exception:
                    pass
                self._store_attribute_value(group_id, attribute_id, fallback)
            else:
                try:
                    var.set("")
                except Exception:
                    pass
                self._store_attribute_value(group_id, attribute_id, None)
        else:
            var = control.get("variable")
            text = ""
            if normalized:
                first = normalized[0]
                text = str(first)
            try:
                var.set(text)
            except Exception:
                pass
            self._store_attribute_value(group_id, attribute_id, text or None)

    def _apply_attribute_data(
        self, attributes: Optional[Mapping[Any, Mapping[Any, Any]]]
    ) -> None:
        if not attributes:
            self._pending_attribute_payload = None
            self._reset_attribute_editor()
            return
        if not self._attribute_controls:
            self._pending_attribute_payload = attributes
            return
        reset_editor = getattr(self, "_reset_attribute_editor", None)
        if callable(reset_editor):
            reset_editor()
        name_map = (
            self._attribute_cache.get("by_name")
            if isinstance(self._attribute_cache, Mapping)
            else {}
        ) or {}
        for group_key, values in attributes.items():
            try:
                group_id = int(group_key)
            except (TypeError, ValueError):
                continue
            if not isinstance(values, Mapping):
                continue
            for attr_key, raw_value in values.items():
                attr_id = self._resolve_attribute_id(attr_key, name_map)
                if attr_id is None:
                    continue
                self._set_attribute_selection(group_id, attr_id, raw_value)
        self._pending_attribute_payload = None

    def _reset_attribute_editor(self) -> None:
        self.attribute_values = {}
        for control in self._attribute_controls.values():
            widget_type = control.get("widget_type")
            if widget_type == "multiselect":
                for var in control.get("checkbox_vars", {}).values():
                    try:
                        var.set(False)
                    except Exception:
                        pass
            else:
                var = control.get("variable")
                if var is None:
                    continue
                try:
                    var.set("")
                except Exception:
                    pass
        _set_language_attribute_default(self)
        self._set_card_type_code(CARD_TYPE_DEFAULT)

    def _resolve_attribute_id(
        self, key: Any, name_map: Mapping[str, int] | None
    ) -> Optional[int]:
        if isinstance(key, int):
            return key
        if isinstance(key, str):
            stripped = key.strip()
            if not stripped:
                return None
            if stripped.isdigit():
                try:
                    return int(stripped)
                except ValueError:
                    return None
            lookup = (name_map or {}).get(stripped.lower())
            if lookup is not None:
                return lookup
        return None

    def _normalize_attribute_payload(
        self, attr_meta: Mapping[str, Any] | None, raw_value: Any
    ) -> list[Any]:
        normalized = self._normalize_attribute_selection(attr_meta, raw_value)
        widget_type = (attr_meta or {}).get("widget_type")
        if widget_type == "multiselect":
            seen: list[Any] = []
            for item in normalized:
                if item not in seen:
                    seen.append(item)
            return seen
        result: list[Any] = []
        if widget_type == "select":
            if normalized:
                result.append(normalized[0])
            return result
        for item in normalized:
            if isinstance(item, str):
                stripped = item.strip()
                if stripped:
                    result.append(stripped)
            elif item is not None:
                result.append(item)
        return result

    def update_set_options(self, event=None):
        # Strict mode: do not alter Set/Era from local JSON; rely on store/API
        try:
            _strict = str(os.getenv("SHOPER_STRICT_MODE", "")).strip().lower() in {"1", "true", "yes", "on"}
        except Exception:
            _strict = False
        if _strict:
            return
        lang = _get_current_language_code(self).upper()
        era = self.era_var.get().strip()
        if lang == "JP":
            self.sets_file = "tcg_sets_jp.json"
            sets_by_era = tcg_sets_jp_by_era
        else:
            self.sets_file = "tcg_sets.json"
            sets_by_era = tcg_sets_eng_by_era

        if era and era in sets_by_era:
            values = [item["name"] for item in sets_by_era[era]]
        else:
            values = [item["name"] for sets in sets_by_era.values() for item in sets]

        self.set_dropdown.configure(values=values)
        if getattr(self, "cheat_frame", None) is not None:
            self.create_cheat_frame()

    def _get_card_finish_selection(self) -> CardFinishSelection:
        attr_id = getattr(self, "_finish_attribute_id", None)
        pending = getattr(self, "_pending_finish_selection", None)
        if attr_id is None:
            if isinstance(pending, CardFinishSelection):
                return pending
            var = getattr(self, "card_type_var", None)
            code = CARD_TYPE_DEFAULT
            if var is not None:
                try:
                    code = normalize_card_type_code(var.get())
                except tk.TclError:
                    code = CARD_TYPE_DEFAULT
            label = CARD_TYPE_LABELS.get(code, DEFAULT_CARD_FINISH_LABEL)
            return CardFinishSelection(code, None, label, None)
        group_map: Mapping[int, Any] | None = None
        values = getattr(self, "attribute_values", None)
        if isinstance(values, Mapping):
            group_map = values.get(CARD_FINISH_ATTRIBUTE_GROUP_ID)
        raw_value: Any = None
        if isinstance(group_map, Mapping):
            raw_value = group_map.get(attr_id)
        if isinstance(raw_value, (list, tuple)):
            raw_value = raw_value[0] if raw_value else None
        if raw_value is None:
            if isinstance(pending, CardFinishSelection):
                return pending
            return DEFAULT_CARD_FINISH_SELECTION
        return self._decode_finish_value(raw_value)

    def _decode_finish_value(self, raw_value: Any) -> CardFinishSelection:
        mapping = getattr(self, "_finish_value_to_variant", {}) or {}
        if isinstance(raw_value, (list, tuple)):
            raw_value = raw_value[0] if raw_value else None
        if raw_value in mapping:
            return mapping[raw_value]
        attr_id = getattr(self, "_finish_attribute_id", None)
        label = None
        if attr_id is not None:
            control = _get_attribute_control(
                self, CARD_FINISH_ATTRIBUTE_GROUP_ID, attr_id
            )
        else:
            control = None
        if isinstance(control, Mapping):
            value_to_label = control.get("value_to_label", {}) or {}
            if isinstance(value_to_label, Mapping) and raw_value in value_to_label:
                label = value_to_label.get(raw_value)
        value_labels = getattr(self, "_finish_value_to_label", {}) or {}
        if label is None and raw_value in value_labels:
            label = value_labels.get(raw_value)
        if label is None and isinstance(raw_value, str):
            label = raw_value
        if label is not None:
            normalized = _normalize_finish_label(label)
            code, ball = _deduce_finish_variant(normalized)
            code = normalize_card_type_code(code)
            ball_norm = _normalize_ball_suffix(ball)
            label_text = str(label).strip() or CARD_TYPE_LABELS.get(
                code, DEFAULT_CARD_FINISH_LABEL
            )
            return CardFinishSelection(code, ball_norm, label_text, raw_value)
        code = CARD_TYPE_DEFAULT
        var = getattr(self, "card_type_var", None)
        if var is not None:
            try:
                code = normalize_card_type_code(var.get())
            except tk.TclError:
                code = CARD_TYPE_DEFAULT
        label_text = CARD_TYPE_LABELS.get(code, DEFAULT_CARD_FINISH_LABEL)
        return CardFinishSelection(code, None, label_text, raw_value)

    def _find_finish_value_for(
        self, selection: CardFinishSelection
    ) -> Any | None:
        reverse = getattr(self, "_finish_variant_to_value", {}) or {}
        ball_code = (selection.ball or "").upper()
        key = (selection.code, ball_code)
        if key in reverse:
            return reverse[key]
        if ball_code and (selection.code, "") in reverse:
            return reverse[(selection.code, "")]
        if selection.label:
            lookup = self._find_finish_value_by_label(selection.label)
            if lookup is not None:
                return lookup
        return None

    def _find_finish_value_by_label(self, label: Any) -> Any | None:
        normalized = _normalize_finish_label(label)
        if not normalized:
            return None
        lookup = getattr(self, "_finish_label_to_value", {}) or {}
        if normalized in lookup:
            return lookup[normalized]
        return None

    def _apply_finish_selection(self, selection: CardFinishSelection) -> bool:
        attr_id = getattr(self, "_finish_attribute_id", None)
        var = getattr(self, "card_type_var", None)
        if var is not None:
            try:
                var.set(selection.code)
            except tk.TclError:
                pass
        if attr_id is None:
            self._pending_finish_selection = selection
            return False
        value = selection.value
        if value is None:
            value = self._find_finish_value_for(selection)
        if value is None and selection.label:
            value = self._find_finish_value_by_label(selection.label)
        if value is None:
            return False
        self._set_attribute_selection(
            CARD_FINISH_ATTRIBUTE_GROUP_ID, attr_id, value
        )
        self._pending_finish_selection = None
        return True

    def _extract_finish_attribute_value(self, data: Mapping[str, Any] | None) -> Any:
        if not isinstance(data, Mapping):
            return None
        attr_maps: list[Mapping[str, Any]] = []
        for key in ("attributes", "attribute_values"):
            candidate = data.get(key)
            if isinstance(candidate, Mapping):
                attr_maps.append(candidate)
        attr_id = getattr(self, "_finish_attribute_id", None)
        for attr_map in attr_maps:
            group = attr_map.get(CARD_FINISH_ATTRIBUTE_GROUP_ID)
            if group is None:
                group = attr_map.get(str(CARD_FINISH_ATTRIBUTE_GROUP_ID))
            if not isinstance(group, Mapping):
                continue
            if attr_id is not None:
                if attr_id in group:
                    return group[attr_id]
                for attr_key, attr_value in group.items():
                    try:
                        if int(attr_key) == attr_id:
                            return attr_value
                    except (TypeError, ValueError):
                        continue
            if len(group) == 1:
                return next(iter(group.values()))
        return None

    def _extract_finish_selection_from_mapping(
        self, data: Mapping[str, Any] | None
    ) -> CardFinishSelection:
        if data is None:
            return DEFAULT_CARD_FINISH_SELECTION
        attr_value = self._extract_finish_attribute_value(data)
        if attr_value is not None:
            return self._decode_finish_value(attr_value)
        label = None
        if isinstance(data, Mapping):
            for key in ("typ", "type_label", "finish", "wykończenie"):
                if key in data and data[key]:
                    label = data[key]
                    break
        ball_candidate = None
        if isinstance(data, Mapping):
            for key in ("ball_type", "ball", "ball_suffix"):
                if key in data and data[key]:
                    ball_candidate = data[key]
                    break
        ball_code = _normalize_ball_suffix(ball_candidate)
        code = infer_card_type_code(data)
        code = normalize_card_type_code(code)
        label_text = str(label).strip() if isinstance(label, str) else label
        selection = CardFinishSelection(code, ball_code, label_text or None, None)
        value = None
        if label_text:
            value = self._find_finish_value_by_label(label_text)
        if value is None:
            value = self._find_finish_value_for(selection)
        if value is not None:
            selection = selection._replace(value=value)
        return selection

    def _update_card_finish_display(self) -> None:
        selection = self._get_card_finish_selection()
        label = selection.label or CARD_TYPE_LABELS.get(
            selection.code, DEFAULT_CARD_FINISH_LABEL
        )
        display_var = getattr(self, "card_type_display_var", None)
        if display_var is not None:
            try:
                display_var.set(label)
            except tk.TclError:
                pass
        var = getattr(self, "card_type_var", None)
        if var is not None:
            try:
                var.set(selection.code)
            except tk.TclError:
                pass

    def _get_card_type_code(self) -> str:
        selection = self._get_card_finish_selection()
        return normalize_card_type_code(selection.code)

    def _set_card_type_code(self, value: Any) -> None:
        code = normalize_card_type_code(value)
        label = CARD_TYPE_LABELS.get(code, DEFAULT_CARD_FINISH_LABEL)
        selection = CardFinishSelection(code, None, label, None)
        apply_finish = getattr(self, "_apply_finish_selection", None)
        success = False
        if callable(apply_finish):
            try:
                success = bool(apply_finish(selection))
            except Exception:
                success = False
        else:
            var = getattr(self, "card_type_var", None)
            if var is not None:
                try:
                    var.set(selection.code)
                except Exception:
                    pass
        if not success and hasattr(self, "_pending_finish_selection"):
            self._pending_finish_selection = selection
        updater = getattr(self, "_update_card_finish_display", None)
        if callable(updater):
            try:
                updater()
            except Exception:
                pass
        else:
            var = getattr(self, "card_type_var", None)
            if var is not None:
                try:
                    var.set(selection.code)
                except Exception:
                    pass

    def _set_card_type_from_mapping(self, data: Mapping[str, Any] | None) -> None:
        extractor = getattr(self, "_extract_finish_selection_from_mapping", None)
        if callable(extractor):
            try:
                selection = extractor(data)
            except Exception:
                selection = DEFAULT_CARD_FINISH_SELECTION
        else:
            code = infer_card_type_code(data)
            ball_candidate = None
            if isinstance(data, Mapping):
                ball_candidate = data.get("ball_type") or data.get("ball")
            selection = CardFinishSelection(
                normalize_card_type_code(code),
                _normalize_ball_suffix(ball_candidate),
                None,
                None,
            )
        apply_finish = getattr(self, "_apply_finish_selection", None)
        success = False
        if callable(apply_finish):
            try:
                success = bool(apply_finish(selection))
            except Exception:
                success = False
        else:
            var = getattr(self, "card_type_var", None)
            if var is not None:
                try:
                    var.set(selection.code)
                except Exception:
                    pass
        if not success and hasattr(self, "_pending_finish_selection"):
            self._pending_finish_selection = selection
        updater = getattr(self, "_update_card_finish_display", None)
        if callable(updater):
            try:
                updater()
            except Exception:
                pass
        else:
            var = getattr(self, "card_type_var", None)
            if var is not None:
                try:
                    var.set(selection.code)
                except Exception:
                    pass

    def filter_sets(self, event=None):
        typed = self.set_var.get().strip().lower()
        lang = _get_current_language_code(self).upper()
        era = self.era_var.get().strip()
        if lang == "JP":
            sets_by_era = tcg_sets_jp_by_era
            name_list_all = tcg_sets_jp
            code_map_all = tcg_sets_jp_code_map
            abbr_map_all = tcg_sets_jp_abbr_name_map
        else:
            sets_by_era = tcg_sets_eng_by_era
            name_list_all = tcg_sets_eng
            code_map_all = tcg_sets_eng_code_map
            abbr_map_all = tcg_sets_eng_abbr_name_map

        if era and era in sets_by_era:
            name_list = [item["name"] for item in sets_by_era[era]]
            code_map = {item["code"]: item["name"] for item in sets_by_era[era]}
            abbr_map = {
                item["abbr"]: item["name"]
                for item in sets_by_era[era]
                if "abbr" in item
            }
        else:
            name_list = name_list_all
            code_map = code_map_all
            abbr_map = abbr_map_all

        search_map = {n.lower(): n for n in name_list}
        search_map.update({c.lower(): n for c, n in code_map.items()})
        search_map.update({a.lower(): n for a, n in abbr_map.items()})

        if typed:
            matches = [search_map[k] for k in search_map if typed in k]
            if not matches:
                close = difflib.get_close_matches(typed, search_map.keys(), n=10, cutoff=0.6)
                matches = [search_map[k] for k in close]
            filtered = []
            seen = set()
            for name in matches:
                if name not in seen:
                    filtered.append(name)
                    seen.add(name)
        else:
            filtered = name_list
        self.set_dropdown.configure(values=filtered)

    def autocomplete_set(self, event=None):
        typed = self.set_var.get().strip().lower()
        lang = _get_current_language_code(self).upper()
        era = self.era_var.get().strip()
        if lang == "JP":
            sets_by_era = tcg_sets_jp_by_era
            code_map_all = tcg_sets_jp_code_map
            abbr_map_all = tcg_sets_jp_abbr_name_map
            name_list_all = tcg_sets_jp
        else:
            sets_by_era = tcg_sets_eng_by_era
            code_map_all = tcg_sets_eng_code_map
            abbr_map_all = tcg_sets_eng_abbr_name_map
            name_list_all = tcg_sets_eng

        if era and era in sets_by_era:
            name_list = [item["name"] for item in sets_by_era[era]]
            code_map = {item["code"]: item["name"] for item in sets_by_era[era]}
            abbr_map = {
                item.get("abbr"): item["name"]
                for item in sets_by_era[era]
                if "abbr" in item
            }
        else:
            name_list = name_list_all
            code_map = code_map_all
            abbr_map = abbr_map_all

        name = None
        if typed in code_map:
            name = code_map[typed]
        elif typed in abbr_map:
            name = abbr_map[typed]
        else:
            search_map = {n.lower(): n for n in name_list}
            search_map.update({c.lower(): n for c, n in code_map.items()})
            search_map.update({a.lower(): n for a, n in abbr_map.items()})
            close = difflib.get_close_matches(typed, search_map.keys(), n=1, cutoff=0.6)
            if close:
                name = search_map[close[0]]
        if name:
            self.set_var.set(name)
        event.widget.tk_focusNext().focus()
        return "break"

    def convert_eur_to_pln(self, event=None):
        eur_text = self.eur_entry.get().strip()
        try:
            eur = float(eur_text)
        except ValueError:
            self.pln_result_label.configure(text="Błąd")
            return "break"
        rate = self.get_exchange_rate()
        pln = eur * rate * PRICE_MULTIPLIER
        self.pln_result_label.configure(text=f"PLN: {pln:.2f}")
        return "break"

    def create_cheat_frame(self, show_headers: bool = True):
        """Create or refresh the cheatsheet frame with set logos."""
        if self.cheat_frame is not None:
            self.cheat_frame.destroy()
        self.cheat_frame = ctk.CTkScrollableFrame(
            self.frame,
            fg_color=self.root.cget("background"),
            width=240,
        )
        self.cheat_frame.grid(row=2, column=5, rowspan=12, sticky="nsew")

        lang = _get_current_language_code(self).upper()
        sets_by_era = (
            tcg_sets_jp_by_era if lang == "JP" else tcg_sets_eng_by_era
        )

        row = 0
        for era, sets in sets_by_era.items():
            if show_headers:
                ctk.CTkLabel(
                    self.cheat_frame,
                    text=era,
                    font=("Segoe UI", 12, "bold"),
                ).grid(row=row, column=0, columnspan=2, sticky="w", padx=5, pady=4)
                row += 1
            for item in sets:
                name = item["name"]
                code = item["code"]
                img = self.set_logos.get(code)
                if img:
                    ctk.CTkLabel(
                        self.cheat_frame,
                        image=img,
                        text="",
                    ).grid(row=row, column=0, sticky="w", padx=5, pady=2)
                else:
                    ctk.CTkLabel(
                        self.cheat_frame,
                        text="",
                        width=2,
                    ).grid(row=row, column=0, sticky="w", padx=5, pady=2)
                ctk.CTkLabel(
                    self.cheat_frame,
                    text=f"{name} ({code})",
                ).grid(row=row, column=1, sticky="w", padx=5, pady=2)
                row += 1

    def toggle_cheatsheet(self):
        """Show or hide the cheatsheet with set logos."""
        if self.cheat_frame is None:
            self.create_cheat_frame()
            return
        if self.cheat_frame.winfo_ismapped():
            self.cheat_frame.grid_remove()
        else:
            self.cheat_frame.grid()

    def start_browse_scans(self):
        """Wrapper for 'Dalej' button that closes the location frame."""
        if getattr(self, "location_frame", None):
            self.location_frame.destroy()
            self.location_frame = None
        self.browse_scans()

    def browse_scans(self):
        """Ask for a folder and load scans starting from the entered location."""
        try:
            box = int(self.start_box_var.get())
            column = int(self.start_col_var.get())
            pos = int(self.start_pos_var.get())
        except (tk.TclError, ValueError):
            messagebox.showerror("Błąd", "Podaj poprawne wartości liczbowe")
            return

        if box not in {*range(1, BOX_COUNT + 1), SPECIAL_BOX_NUMBER}:
            messagebox.showerror(
                "Błąd", f"Box musi być w zakresie 1-{BOX_COUNT} lub {SPECIAL_BOX_NUMBER}"
            )
            return

        if box == SPECIAL_BOX_NUMBER:
            special_columns = BOX_COLUMNS.get(SPECIAL_BOX_NUMBER, 1)
            if not (
                1 <= column <= special_columns
                and 1 <= pos <= BOX_COLUMN_CAPACITY
            ):
                messagebox.showerror(
                    "Błąd",
                    f"Dla boxu {SPECIAL_BOX_NUMBER} kolumna musi być 1-{special_columns}, "
                    f"pozycja 1-{BOX_COLUMN_CAPACITY}",
                )
                return
            self.starting_idx = (
                BOX_COUNT * BOX_CAPACITY
                + (column - 1) * BOX_COLUMN_CAPACITY
                + (pos - 1)
            )
        else:
            if not (1 <= column <= GRID_COLUMNS and 1 <= pos <= BOX_COLUMN_CAPACITY):
                messagebox.showerror(
                    "Błąd",
                    f"Podaj poprawne wartości (kolumna 1-{GRID_COLUMNS}, pozycja 1-{BOX_COLUMN_CAPACITY})",
                )
                return
            self.starting_idx = (
                (box - 1) * BOX_CAPACITY + (column - 1) * BOX_COLUMN_CAPACITY + (pos - 1)
            )
        folder = self.scan_folder_var.get().strip()
        if not folder:
            folder = filedialog.askdirectory()
            if not folder:
                return
            self.scan_folder_var.set(folder)
        self.in_scan = True
        CardEditorApp.load_images(self, folder)
        self.session_entries = [None] * len(self.cards)

    def load_images(self, folder):
        self.in_scan = True
        if self.start_frame is not None:
            self.start_frame.destroy()
            self.start_frame = None
        if getattr(self, "frame", None) is None:
            self.setup_editor_ui()
        self.folder_path = folder
        self.folder_name = os.path.basename(folder)
        self.session_entries = []
        self.cards = [
            os.path.join(folder, f)
            for f in os.listdir(folder)
            if f.lower().endswith((".jpg", ".png"))
        ]
        self.cards.sort()
        self.index = 0
        self.output_data = [None] * len(self.cards)
        self.card_counts = defaultdict(int)
        self.failed_cards = []
        total = len(self.cards)
        self.progress_var.set(f"0/{total} (0%)")
        self.log(f"Loaded {len(self.cards)} cards")
        self.show_card()

    def show_card(self):
        progress_cb = getattr(self, "_update_card_progress", None)
        if progress_cb:
            progress_cb(0, show=True)
        if self.index >= len(self.cards):
            if getattr(self, "failed_cards", None):
                msg = "Failed to load images:\n" + "\n".join(self.failed_cards)
                print(msg, file=sys.stderr)
                try:
                    messagebox.showerror("Errors", msg)
                except tk.TclError:
                    pass
            messagebox.showinfo("Koniec", "Wszystkie karty zostały zapisane.")
            self.show_session_summary()
            return

        total = len(self.cards) or 1
        percent = int((self.index + 1) / total * 100)
        self.progress_var.set(f"{self.index + 1}/{len(self.cards)} ({percent}%)")

        image_path = self.cards[self.index]
        filename = os.path.basename(image_path)
        self.current_image_path = image_path
        self.current_fingerprint = None
        self.current_location = ""
        cache_key = self.file_to_key.get(filename)
        if not cache_key:
            cache_key = self._guess_key_from_filename(image_path)
        inv_entry = self.lookup_inventory_entry(cache_key) if cache_key else None
        image = load_rgba_image(image_path)
        if image is None:
            print(f"Failed to load image {image_path}", file=sys.stderr)
            if getattr(self, "failed_cards", None) is not None:
                self.failed_cards.append(image_path)
            self.index += 1
            self.show_card()
            return
        image.thumbnail((400, 560))
        self.current_card_image = image.copy()
        img = _create_image(image)
        self.image_objects.append(img)
        self.image_objects = self.image_objects[-2:]
        self.current_card_photo = img
        self.image_label.configure(image=img)
        if hasattr(self, "location_label"):
            try:
                self.location_label.configure(text=self.next_free_location())
            except storage.NoFreeLocationError:
                try:
                    messagebox.showerror("Błąd", "Brak wolnych miejsc w magazynie")
                except tk.TclError:
                    pass
                self.location_label.configure(text="")

        attributes_to_apply: Optional[Mapping[Any, Any]] = None
        current_row = None
        cached_language_code: Optional[str] = None
        if (
            getattr(self, "output_data", None)
            and 0 <= self.index < len(self.output_data)
        ):
            candidate_row = self.output_data[self.index]
            if isinstance(candidate_row, Mapping):
                current_row = candidate_row
                attrs = candidate_row.get("attributes")
                if isinstance(attrs, Mapping):
                    attributes_to_apply = attrs

        for key, entry in list(self.entries.items()):
            if hasattr(entry, "winfo_exists"):
                try:
                    if not entry.winfo_exists():
                        self.entries.pop(key, None)
                        continue
                except tk.TclError:
                    self.entries.pop(key, None)
                    continue
            try:
                tk_entry_cls = getattr(tk, "Entry", None)
                ctk_entry_cls = getattr(ctk, "CTkEntry", None)
                entry_types = tuple(
                    t for t in (tk_entry_cls, ctk_entry_cls) if isinstance(t, type)
                )
                if entry_types and isinstance(entry, entry_types):
                    entry.delete(0, tk.END)
                elif isinstance(tk.StringVar, type) and isinstance(entry, tk.StringVar):
                    defaults = {
                        "stan": "NM",
                        "producer": "Pokémon",
                        "currency": "PLN",
                        "availability": self._get_default_availability_value(),
                        "unit": "szt.",
                        "delivery": "3 dni",
                        "active": "1",
                        "vat": "23%",
                    }
                    entry.set(defaults.get(key, ""))
                else:
                    bool_var_cls = getattr(tk, "BooleanVar", None)
                    if isinstance(bool_var_cls, type) and isinstance(entry, bool_var_cls):
                        entry.set(False)
            except tk.TclError:
                self.entries.pop(key, None)

        psa_var = getattr(self, "psa10_price_var", None)
        if hasattr(psa_var, "set"):
            try:
                psa_var.set("")
            except (tk.TclError, RuntimeError):
                psa_var.set("")

        if isinstance(current_row, Mapping) and hasattr(psa_var, "set"):
            try:
                psa_var.set(current_row.get("psa10_price", "") or "")
            except (tk.TclError, RuntimeError):
                psa_var.set(current_row.get("psa10_price", "") or "")

        reset_editor = getattr(self, "_reset_attribute_editor", None)
        if callable(reset_editor):
            reset_editor()
        skip_analysis = False
        self.selected_candidate_meta = None
        if cache_key and cache_key in self.card_cache:
            cached = self.card_cache[cache_key]
            entry_data = dict(cached.get("entries", {}) or {})
            for field, value in entry_data.items():
                if isinstance(field, str) and field.startswith("attribute:"):
                    continue
                if field == "język":
                    cached_language_code = _normalize_language_label(value) or cached_language_code
                    continue
                entry = self.entries.get(field)
                if isinstance(entry, (tk.Entry, ctk.CTkEntry)):
                    if field == "numer":
                        value = sanitize_number(str(value))
                    entry.insert(0, value)
                elif isinstance(entry, tk.StringVar):
                    entry.set(value)
            combined = dict(entry_data)
            types = cached.get("types")
            if isinstance(types, Mapping):
                combined.setdefault("types", types)
            if "typ" not in combined and cached.get("typ"):
                combined["typ"] = cached["typ"]
            if cached.get("card_type") and "card_type" not in combined:
                combined["card_type"] = cached["card_type"]
            self._set_card_type_from_mapping(combined)
            self.update_set_options()
            attrs = cached.get("attributes")
            if isinstance(attrs, Mapping):
                attributes_to_apply = attrs
            if hasattr(psa_var, "set"):
                try:
                    psa_var.set(cached.get("psa10_price", "") or "")
                except (tk.TclError, RuntimeError):
                    psa_var.set(cached.get("psa10_price", "") or "")

        elif inv_entry:
            self.entries["nazwa"].insert(0, inv_entry.get("nazwa", ""))
            self.entries["numer"].insert(
                0, sanitize_number(str(inv_entry.get("numer", "")))
            )
            self.entries["set"].set(inv_entry.get("set", ""))
            self.entries["era"].set(inv_entry.get("era", ""))
            self._set_card_type_from_mapping(inv_entry)
            self.update_set_options()
            skip_analysis = True
            logger.info(
                "Skipping analysis for %s: inventory entry found for key %s",
                filename,
                cache_key,
            )
            attrs = inv_entry.get("attributes") if isinstance(inv_entry, Mapping) else None
            if isinstance(attrs, Mapping):
                attributes_to_apply = attrs

        folder = os.path.basename(os.path.dirname(image_path))
        progress_cb = getattr(self, "_update_card_progress", None)

        if attributes_to_apply is None and isinstance(current_row, Mapping):
            attrs = current_row.get("attributes")
            if isinstance(attrs, Mapping):
                attributes_to_apply = attrs
        apply_attributes = getattr(self, "_apply_attribute_data", None)
        if callable(apply_attributes):
            apply_attributes(attributes_to_apply or {})
        if cached_language_code is None and isinstance(current_row, Mapping):
            cached_language_code = _normalize_language_label(current_row.get("język"))
        if cached_language_code is None and isinstance(inv_entry, Mapping):
            cached_language_code = _normalize_language_label(inv_entry.get("język"))
        current_lang = _extract_language_code_from_attributes(self)
        if cached_language_code and cached_language_code != current_lang:
            _apply_language_code_to_attribute(self, cached_language_code)

        fp_match = None
        if (
            not skip_analysis
            and getattr(self, "hash_db", None)
            and getattr(self, "auto_lookup", False)
        ):
            try:
                with Image.open(image_path) as img_fp:
                    try:
                        fp = compute_fingerprint(img_fp, use_orb=True)
                    except TypeError:
                        fp = compute_fingerprint(img_fp)
                self.current_fingerprint = fp
                lookup = getattr(self, "_lookup_fp_candidate", None)
                if lookup:
                    fp_match = lookup(fp)
                else:
                    fp_match = getattr(self.hash_db, "best_match", lambda *a, **k: None)(
                        fp, max_distance=HASH_MATCH_THRESHOLD
                    )
            except (OSError, UnidentifiedImageError, ValueError) as exc:
                logger.warning("Fingerprint lookup failed for %s: %s", image_path, exc)
                fp_match = None
            if fp_match:
                meta = fp_match.meta
                self.selected_candidate_meta = meta
                csv_row = None
                code = meta.get("warehouse_code")
                if code:
                    csv_row = csv_utils.get_row_by_code(code)
                    self.current_location = code
                    if hasattr(self, "location_label"):
                        self.location_label.configure(text=code)
                if csv_row:
                    name = csv_row.get("name", "")
                    number = sanitize_number(str(csv_row.get("number", "")))
                    set_name = csv_row.get("set", "")
                else:
                    name = meta.get("nazwa", meta.get("name", ""))
                    number = sanitize_number(
                        str(meta.get("numer", meta.get("number", "")))
                    )
                    set_name = meta.get("set", meta.get("set_name", ""))
                variant_source = csv_row if csv_row else meta
                variant_code = infer_card_type_code(variant_source)
                product_code = csv_utils.build_product_code(
                    set_name,
                    number,
                    variant_source.get("variant") if isinstance(variant_source, Mapping) else None,
                )
                duplicates = self._find_existing_products(
                    product_code=product_code,
                    name=name,
                    number=number,
                    set_name=set_name,
                    variant_code=variant_code,
                )
                if duplicates:
                    codes = ", ".join(
                        [
                            str(
                                duplicate.get("product_code")
                                or duplicate.get("code")
                                or duplicate.get("warehouse_code")
                                or ""
                            ).strip()
                            for duplicate in duplicates
                            if (
                                duplicate.get("product_code")
                                or duplicate.get("code")
                                or duplicate.get("warehouse_code")
                            )
                        ]
                    )
                    msg = _(
                        "Product already exists in Shoper: {codes}. Add anyway?"
                    ).format(codes=codes or "?")
                    if not messagebox.askyesno(_("Duplicate"), msg):
                        logger.info(
                            "Skipping duplicate card %s #%s in set %s", name, number, set_name
                        )
                        fp_match = None
                        skip_analysis = False
                    else:
                        self.current_location = self.next_free_location()
                        if hasattr(self, "location_label"):
                            self.location_label.configure(text=self.current_location)
                        logger.info(
                            "Assigned storage location %s to duplicate card", self.current_location
                        )
                if fp_match:
                    self.entries["nazwa"].delete(0, tk.END)
                    self.entries["numer"].delete(0, tk.END)
                    self.entries["nazwa"].insert(0, name)
                    self.entries["numer"].insert(0, number)
                    self.entries["set"].set("")
                    self.entries["set"].set(set_name)
                    era_name = get_set_era(set_name)
                    self.entries["era"].set(era_name)
                    cena = getattr(
                        self, "get_price_from_db", lambda *a, **k: None
                    )(name, number, set_name)
                    if cena is None:
                        cena = getattr(
                            self, "fetch_card_price", lambda *a, **k: None
                        )(name, number, set_name)
                    meta_code = infer_card_type_code(meta)
                    if cena is not None:
                        self.entries["cena"].delete(0, tk.END)
                        self.entries["cena"].insert(0, str(cena))
                        is_rev = getattr(self, "price_reverse_var", None)
                        price = self.apply_variant_multiplier(
                            cena,
                            card_type=meta_code,
                            is_reverse=is_rev.get() if is_rev else False,
                        )
                        try:
                            self.price_pool_total += float(price)
                        except (TypeError, ValueError):
                            pass
                        if getattr(self, "pool_total_label", None):
                            self.pool_total_label.config(
                                text=f"Suma puli: {self.price_pool_total:.2f}"
                            )
                    self._set_card_type_code(meta_code)
                    self.update_set_options()
                    skip_analysis = True
                    logger.info(
                        "Skipping analysis for %s: fingerprint match with distance %s",
                        filename,
                        fp_match.distance,
                    )
                    if progress_cb:
                        progress_cb(1.0)

        if not skip_analysis:
            if progress_cb:
                progress_cb(0, show=True)
            thread = threading.Thread(
                target=self._analyze_and_fill,
                args=(image_path, self.index),
                daemon=True,
            )
            self.current_analysis_thread = thread
            for btn_name in ("save_button", "next_button"):
                btn = getattr(self, btn_name, None)
                if btn is not None:
                    try:
                        btn.configure(state=tk.NORMAL)
                    except Exception:
                        pass
            thread.start()

        if getattr(self, "current_analysis_thread", None) is None:
            for btn_name in ("save_button", "next_button"):
                btn = getattr(self, btn_name, None)
                if btn is not None:
                    try:
                        btn.configure(state=tk.NORMAL)
                    except Exception:
                        pass

        # focus the name entry so the user can start typing immediately
        self.entries["nazwa"].focus_set()

    def _guess_key_from_filename(self, path: str):
        base = os.path.splitext(os.path.basename(path))[0]
        parts = re.split(r"[|_-]", base)
        if len(parts) >= 3:
            name = parts[0]
            number = parts[1]
            set_name = "_".join(parts[2:])
            return f"{name}|{number}|{set_name}|"
        return None

    def _update_card_progress(
        self, value: float, show: bool = False, hide: bool = False
    ):
        """Update the progress bar for analyzing a single card."""
        if not hasattr(self, "progress_bar"):
            return
        try:
            self.progress_bar.set(value)
            if show and hasattr(self, "progress_frame"):
                self.progress_frame.grid()
            elif hide and hasattr(self, "progress_frame"):
                remover = getattr(self.progress_frame, "grid_remove", None)
                if callable(remover):
                    remover()
                else:
                    forget = getattr(self.progress_frame, "grid_forget", None)
                    if callable(forget):
                        forget()
        except tk.TclError:
            pass

    def _show_candidates_dialog(self, candidates: list[Candidate]) -> Optional[Candidate]:
        """Present a dialog allowing the user to choose from *candidates*."""

        if not candidates:
            return None

        selection: dict[str, Optional[Candidate]] = {"candidate": None}
        event = threading.Event()

        def _ask_user():
            dialog = ctk.CTkToplevel(self.root)
            dialog.title(_("Possible duplicates"))

            radio_var = tk.IntVar(value=-1)

            frame = ctk.CTkScrollableFrame(dialog)
            frame.pack(fill="both", expand=True, padx=10, pady=10)

            for idx, cand in enumerate(candidates):
                code = cand.meta.get("warehouse_code", "")
                ctk.CTkRadioButton(
                    frame,
                    text=f"{code} (d={cand.distance})",
                    variable=radio_var,
                    value=idx,
                ).pack(anchor="w")

            def _select():
                sel = radio_var.get()
                if sel >= 0:
                    selection["candidate"] = candidates[sel]
                dialog.destroy()

            def _cancel():
                dialog.destroy()

            btn_frame = ctk.CTkFrame(dialog)
            btn_frame.pack(fill="x", padx=10, pady=5)
            ctk.CTkButton(
                btn_frame, text=_("Select"), command=_select, fg_color=SAVE_BUTTON_COLOR
            ).pack(side="left", expand=True)
            ctk.CTkButton(
                btn_frame, text=_("Skip"), command=_cancel, fg_color=NAV_BUTTON_COLOR
            ).pack(side="right", expand=True)

            dialog.transient(self.root)
            dialog.grab_set()
            self.root.wait_window(dialog)
            event.set()

        if threading.current_thread() is threading.main_thread():
            _ask_user()
        else:
            self.root.after(0, _ask_user)
            event.wait()

        return selection["candidate"]

    def _lookup_fp_candidate(self, fp) -> Optional[Candidate]:
        """Return candidate chosen by the user for the fingerprint ``fp``."""

        if not getattr(self, "hash_db", None):
            return None
        try:
            best = self.hash_db.best_match(fp, max_distance=HASH_MATCH_THRESHOLD)
            if not best:
                return None
            candidates = self.hash_db.candidates(
                fp, limit=5, max_distance=HASH_MATCH_THRESHOLD
            )
        except Exception as exc:
            logger.warning("Fingerprint lookup failed: %s", exc)
            return None
        candidates = [c for c in candidates if c.distance <= HASH_MATCH_THRESHOLD]
        if not candidates:
            return None
        return self._show_candidates_dialog(candidates)

    def update_set_area_preview(self, rect, image):
        """Overlay ``rect`` on ``image`` and display it on ``image_label``."""
        if not rect or image is None:
            return
        try:
            # determine dimensions of the image used for analysis
            with Image.open(getattr(self, "current_image_path", "")) as im:
                orig_w, orig_h = im.size
        except (OSError, UnidentifiedImageError):
            orig_w, orig_h = image.size

        orientation = getattr(self, "_analysis_orientation", 0)
        if orientation == 90:
            base_w, base_h = orig_h, orig_w
        else:
            base_w, base_h = orig_w, orig_h

        disp_w, disp_h = image.size
        scale_x = disp_w / base_w if base_w else 1
        scale_y = disp_h / base_h if base_h else 1
        scaled_rect = (
            int(rect[0] * scale_x),
            int(rect[1] * scale_y),
            int(rect[2] * scale_x),
            int(rect[3] * scale_y),
        )

        if getattr(self, "_preview_source_image", None) is not image:
            self._preview_source_image = image
            self._preview_base_image = image.copy()
        preview = self._preview_base_image.copy()
        draw = ImageDraw.Draw(preview)
        draw.rectangle(scaled_rect, outline="red", width=3)

        img = _create_image(preview)
        self.current_card_photo = img
        self.image_label.configure(image=img)

    def _analyze_and_fill(self, path, idx):
        translate = _get_current_language_code(self).upper() == "JP"
        update_progress = getattr(self, "_update_card_progress", None)
        if update_progress:
            self.root.after(0, lambda: update_progress(0, show=True))
        fp_match = None
        if getattr(self, "hash_db", None) and getattr(self, "auto_lookup", False):
            try:
                with Image.open(path) as img:
                    try:
                        fp = compute_fingerprint(img, use_orb=True)
                    except TypeError:
                        fp = compute_fingerprint(img)
                self.current_fingerprint = fp
                lookup = getattr(self, "_lookup_fp_candidate", None)
                if lookup:
                    fp_match = lookup(fp)
                    if fp_match:
                        self.selected_candidate_meta = fp_match.meta
                else:
                    fp_match = getattr(self.hash_db, "best_match", lambda *a, **k: None)(
                        fp, max_distance=HASH_MATCH_THRESHOLD
                    )
            except (OSError, UnidentifiedImageError, ValueError) as exc:
                logger.warning("Fingerprint lookup failed for %s: %s", path, exc)
                fp_match = None
        if update_progress:
            self.root.after(0, lambda: update_progress(0.5))

        if fp_match:
            meta = fp_match.meta
            csv_row = None
            code = meta.get("warehouse_code")
            if code:
                csv_row = csv_utils.get_row_by_code(code)
            if csv_row:
                result = {
                    "name": csv_row.get("name", ""),
                    "number": sanitize_number(str(csv_row.get("number", ""))),
                    "total": meta.get("total", ""),
                    "set": csv_row.get("set", ""),
                    "set_code": meta.get("set_code", ""),
                    "orientation": 0,
                    "set_format": meta.get("set_format", ""),
                    "variant": csv_row.get("variant"),
                    "price": csv_row.get("price"),
                    "era": get_set_era(csv_row.get("set", "")),
                    "warehouse_code": code,
                }
            else:
                result = {
                    "name": meta.get("nazwa", meta.get("name", "")),
                    "number": meta.get("numer", meta.get("number", "")),
                    "total": meta.get("total", ""),
                    "set": meta.get("set", meta.get("set_name", "")),
                    "set_code": meta.get("set_code", ""),
                    "orientation": 0,
                    "set_format": meta.get("set_format", ""),
                    "variant": meta.get("wariant") or meta.get("variant"),
                    "warehouse_code": code,
                }
        else:
            result = analyze_card_image(
                path,
                translate_name=translate,
                debug=True,
                preview_cb=getattr(self, "update_set_area_preview", None),
                preview_image=getattr(self, "current_card_image", None),
            )
        get_finish = getattr(self, "_get_card_finish_selection", None)
        if callable(get_finish):
            try:
                finish_selection = get_finish()
            except Exception:
                finish_selection = CardFinishSelection(
                    CARD_TYPE_DEFAULT,
                    None,
                    CARD_TYPE_LABELS.get(CARD_TYPE_DEFAULT, DEFAULT_CARD_FINISH_LABEL),
                    None,
                )
        else:
            var = getattr(self, "card_type_var", None)
            try:
                code_value = var.get() if var is not None else CARD_TYPE_DEFAULT
            except Exception:
                code_value = CARD_TYPE_DEFAULT
            code_value = normalize_card_type_code(code_value)
            finish_selection = CardFinishSelection(
                code_value,
                None,
                card_type_label(code_value),
                None,
            )
        ball_suffix = finish_selection.ball if finish_selection.ball in {"P", "M"} else None
        product_code = csv_utils.build_product_code(
            result.get("set", ""),
            result.get("number", ""),
            result.get("variant"),
            ball_suffix=ball_suffix,
        )
        result["product_code"] = product_code
        store_row = self._get_store_product(product_code)
        if isinstance(store_row, Mapping):
            result.update(store_row)
            cat = store_row.get("category", "")
            if isinstance(cat, str):
                parts = [p.strip() for p in cat.split(">")]
                if len(parts) >= 2:
                    result["era"] = parts[1]
        if update_progress:
            self.root.after(0, lambda: update_progress(1.0))

        self.root.after(0, lambda: self._apply_analysis_result(result, idx))

    def _apply_analysis_result(self, result, idx):
        if idx != self.index:
            return
        progress_cb = getattr(self, "_update_card_progress", None)
        if result:
            name = result.get("name", "")
            number = result.get("number", "")
            total = result.get("total") or ""
            if not total and isinstance(number, str):
                m = re.match(r"(\d+)\s*/\s*(\d+)", number)
                if m:
                    number, total = m.group(1), m.group(2)
            set_name = result.get("set", "")
            era_name = result.get("era", "") or get_set_era(set_name)
            price = result.get("price")
            number = sanitize_number(str(number))
            self.entries["nazwa"].delete(0, tk.END)
            self.entries["nazwa"].insert(0, name)
            self.entries["numer"].delete(0, tk.END)
            self.entries["numer"].insert(0, number)
            self.entries["era"].set(era_name)
            if price is not None:
                price_entry = self.entries.get("cena")
                if price_entry is not None:
                    price_entry.delete(0, tk.END)
                    price_entry.insert(0, price)
            self.update_set_options()
            self.entries["set"].set(set_name)

            field_sources: dict[str, tuple[str, ...]] = {
                "producer": ("producer", "manufacturer"),
                "category": ("category", "producer_category"),
                "short_description": ("short_description",),
                "description": ("description",),
                "price": ("price", "cena"),
            }
            entry_map = {
                "producer": "producer",
                "category": "category",
                "short_description": "short_description",
                "description": "description",
                "price": "cena",
            }
            for target, source_keys in field_sources.items():
                value = None
                for key in source_keys:
                    candidate = result.get(key)
                    if isinstance(candidate, str) and candidate.strip():
                        value = candidate
                        break
                if target == "category" and not value and era_name and set_name:
                    value = f"Karty Pokémon > {era_name} > {set_name}"
                if target == "price" and value is None and price is not None:
                    value = str(price)
                if value is None:
                    continue
                entry_key = entry_map.get(target)
                entry_widget = self.entries.get(entry_key) if entry_key else None
                if isinstance(entry_widget, (tk.Entry, ctk.CTkEntry)):
                    entry_widget.delete(0, tk.END)
                    entry_widget.insert(0, value)
                elif hasattr(entry_widget, "set") and callable(entry_widget.set):
                    entry_widget.set(value)
                result[target] = value
                if target == "price":
                    price = value

            code = result.get("warehouse_code")
            if code:
                self.current_location = code
                if hasattr(self, "location_label"):
                    self.location_label.configure(text=code)

            self._set_card_type_from_mapping(result)
            variant_code = infer_card_type_code(result)
            duplicates = self._find_existing_products(
                product_code=result.get("product_code", ""),
                name=name,
                number=number,
                set_name=set_name,
                variant_code=variant_code,
            )
            if duplicates:
                if progress_cb:
                    progress_cb(0, hide=True)
                csv_price = next(
                    (row.get("price") for row in duplicates if row.get("price")),
                    None,
                )
                if csv_price is not None:
                    price = csv_price
                    result["price"] = csv_price
                    price_entry = self.entries.get("cena")
                    if price_entry is not None:
                        price_entry.delete(0, tk.END)
                        price_entry.insert(0, csv_price)
                codes = ", ".join(
                    [
                        str(
                            duplicate.get("product_code")
                            or duplicate.get("code")
                            or duplicate.get("warehouse_code")
                            or ""
                        ).strip()
                        for duplicate in duplicates
                        if (
                            duplicate.get("product_code")
                            or duplicate.get("code")
                            or duplicate.get("warehouse_code")
                        )
                    ]
                )
                msg = _("Product already exists in Shoper: {codes}. Add anyway?").format(
                    codes=codes or "?"
                )
                if not messagebox.askyesno(_("Duplicate"), msg):
                    logger.info(
                        "Skipping duplicate card %s #%s in set %s", name, number, set_name
                    )
                    if progress_cb:
                        progress_cb(1.0, hide=True)
                    self.current_analysis_thread = None
                    return
                self.current_location = self.next_free_location()
                if hasattr(self, "location_label"):
                    self.location_label.configure(text=self.current_location)
                logger.info(
                    "Assigned storage location %s to duplicate card", self.current_location
                )
            elif progress_cb:
                progress_cb(1.0, hide=True)
            rect = result.get("rect")
            self._analysis_orientation = result.get("orientation", 0)
            if rect and hasattr(self, "current_card_image"):
                try:
                    self.update_set_area_preview(rect, self.current_card_image)
                except Exception:
                    logger.exception("Failed to update set area preview")
        for btn_name in ("save_button", "next_button"):
            btn = getattr(self, btn_name, None)
            if btn is not None:
                try:
                    btn.configure(state=tk.NORMAL)
                except Exception:
                    pass
        self.current_analysis_thread = None
        return

    def generate_location(self, idx):
        return storage.generate_location(idx)

    def next_free_location(self):
        """Return the next unused warehouse_code."""
        return storage.next_free_location(self)

    def load_price_db(self):
        if not os.path.exists(PRICE_DB_PATH):
            return []
        with open(PRICE_DB_PATH, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return list(reader)

    def load_set_logos(self):
        """Load set logos from SET_LOGO_DIR into self.set_logos."""
        self.set_logos.clear()
        if not os.path.isdir(SET_LOGO_DIR):
            return
        for file in os.listdir(SET_LOGO_DIR):
            path = os.path.join(SET_LOGO_DIR, file)
            if not os.path.isfile(path):
                continue
            if not file.lower().endswith((".png", ".jpg", ".jpeg", ".gif")):
                continue
            code = os.path.splitext(file)[0]
            if ALLOWED_SET_CODES and code not in ALLOWED_SET_CODES:
                continue
            img = load_rgba_image(path)
            if not img:
                continue
            img.thumbnail((40, 40))
            self.set_logos[code] = _create_image(img)

    def show_loading_screen(self):
        """Display a temporary loading screen during startup."""
        self.root.minsize(1200, 800)
        self.loading_frame = ctk.CTkFrame(self.root, fg_color=BG_COLOR)
        self.loading_frame.pack(expand=True, fill="both")
        logo_path = os.path.join(os.path.dirname(__file__), "banner22.png")
        if os.path.exists(logo_path):
            img = load_rgba_image(logo_path)
            if img:
                img.thumbnail((300, 150))
                self.loading_logo = _create_image(img)
                ctk.CTkLabel(
                    self.loading_frame,
                    image=self.loading_logo,
                    text="",
                ).pack(pady=10)

        gif_path = os.path.join(os.path.dirname(__file__), "simple_pokeball.gif")
        if os.path.exists(gif_path):
            from PIL import ImageSequence
            with Image.open(gif_path) as img:
                img.convert("RGBA")
                self.gif_frames = []
                self.gif_durations = []
                for frame in ImageSequence.Iterator(img):
                    self.gif_frames.append(
                        _create_image(frame.convert("RGBA"))
                    )
                    self.gif_durations.append(frame.info.get("duration", 100))

            self.gif_label = ctk.CTkLabel(
                self.loading_frame, text=""
            )
            self.gif_label.pack()
            self.animate_loading_gif(0)
        self.loading_label = ctk.CTkLabel(
            self.loading_frame,
            text="Ładowanie...",
            text_color=TEXT_COLOR,
            font=("Segoe UI", 16),
        )
        self.loading_label.pack(pady=10)
        self.root.update()

    def animate_loading_gif(self, index=0):
        """Cycle through frames of the loading GIF."""
        if not hasattr(self, "gif_frames"):
            return
        frame = self.gif_frames[index]
        self.gif_label.configure(image=frame)
        next_index = (index + 1) % len(self.gif_frames)
        delay = 100
        if hasattr(self, "gif_durations"):
            try:
                delay = self.gif_durations[index]
            except IndexError:
                pass
        self.gif_label.after(delay, self.animate_loading_gif, next_index)

    def startup_tasks(self):
        """Run initial setup tasks on the main thread."""
        last_check = storage.load_last_sets_check()
        now = datetime.datetime.now()

        def continue_startup():
            self.load_set_logos()
            self.finish_startup()

        if not last_check or last_check.year != now.year or last_check.month != now.month:
            def run_updates():
                self.update_sets()
                storage.save_last_sets_check(now)
                self.root.after(0, continue_startup)

            self.root.after(0, run_updates)
        else:
            self.root.after(0, continue_startup)

    def finish_startup(self):
        """Finalize initialization after background tasks complete."""
        if self.loading_frame is not None:
            self.loading_frame.destroy()
        self.shoper_client = None
        self.ensure_shoper_client()
        # The warehouse CSV is now bundled with the application, so no
        # network download is required during startup.
        self.setup_welcome_screen()

    def ensure_shoper_client(self):
        """Initialize ``ShoperClient`` using stored configuration.

        If configuration is missing or authentication fails, a configuration
        dialog is shown to the user.
        """
        global SHOPER_API_URL, SHOPER_API_TOKEN, SHOPER_CLIENT_ID
        url = os.getenv("SHOPER_API_URL", "").strip()
        token = os.getenv("SHOPER_API_TOKEN", "").strip()
        client_id = os.getenv("SHOPER_CLIENT_ID", "").strip()
        if not url or not token:
            self.open_config_dialog()
            return
        try:
            client = ShoperClient(url, token, client_id or None)
            try:
                # perform a simple request to verify credentials
                client.get("products", params={"page": 1, "per-page": 1})
            except RuntimeError as exc:
                messagebox.showerror("Błąd", f"Autoryzacja nieudana: {exc}")
                self.open_config_dialog()
                return
            self.shoper_client = client
            SHOPER_API_URL, SHOPER_API_TOKEN, SHOPER_CLIENT_ID = (
                url,
                token,
                client_id,
            )
        except (requests.RequestException, RuntimeError) as exc:
            messagebox.showerror("Błąd", f"Nie można połączyć się z API Shoper: {exc}")
            self.open_config_dialog()

    def download_set_symbols(self, sets):
        """Download logos for the provided set definitions."""
        os.makedirs(SET_LOGO_DIR, exist_ok=True)
        total = len(sets)
        for idx, item in enumerate(sets, start=1):
            name = item.get("name")
            code = item.get("code")
            if self.loading_label is not None:
                self.loading_label.configure(
                    text=f"Pobieram {idx}/{total}: {name}"
                )
                self.root.update()
            if not code:
                continue
            symbol_url = f"https://images.pokemontcg.io/{code}/symbol.png"
            try:
                res = requests.get(symbol_url, timeout=10)
                if res.status_code == 404:
                    alt = re.sub(r"(^sv)0(\d$)", r"\1\2", code)
                    if alt != code:
                        alt_url = f"https://images.pokemontcg.io/{alt}/symbol.png"
                        res = requests.get(alt_url, timeout=10)
                        if res.status_code == 200:
                            symbol_url = alt_url
                if res.status_code == 200:
                    parsed_path = urlparse(symbol_url).path
                    ext = os.path.splitext(parsed_path)[1] or ".png"
                    safe = code.replace("/", "_")
                    path = os.path.join(SET_LOGO_DIR, f"{safe}{ext}")
                    with open(path, "wb") as fh:
                        fh.write(res.content)
                else:
                    if res.status_code == 404:
                        print(f"[WARN] Symbol not found for {name}: {symbol_url}")
                    else:
                        print(
                            f"[ERROR] Failed to download symbol for {name} from {symbol_url}: {res.status_code}"
                        )
            except requests.RequestException as exc:
                print(f"[ERROR] {name}: {exc}")

    def update_sets(self):
        """Check remote API for new sets and update local files."""
        try:
            self.loading_label.configure(text="Sprawdzanie nowych setów...")
            self.root.update()
            with open(self.sets_file, encoding="utf-8") as f:
                current_sets = json.load(f)
        except (OSError, json.JSONDecodeError):
            current_sets = {}

        timeout = getattr(self, "API_TIMEOUT", 30)
        remote: list[dict] = []
        last_exc: Optional[Exception] = None
        for attempt in range(3):
            try:
                resp = requests.get(
                    "https://api.pokemontcg.io/v2/sets", timeout=timeout
                )
                resp.raise_for_status()
                remote = resp.json().get("data", [])
                break
            except requests.RequestException as exc:
                last_exc = exc
                if attempt < 2:
                    time.sleep(2**attempt)
        if not remote and last_exc is not None:
            self.log(f"[WARN] Using offline sets. Reason: {last_exc}")

        added = 0
        new_items = []
        existing_codes = {
            s.get("code", "").strip().lower()
            for sets in current_sets.values()
            for s in sets
        }

        for item in remote:
            series = item.get("series") or "Other"
            code = item.get("id")
            name = item.get("name")
            abbr = item.get("ptcgoCode")
            if not code or not name:
                continue
            code_key = code.strip().lower()
            if code_key in existing_codes:
                continue
            group = current_sets.setdefault(series, [])
            entry = {"name": name, "code": code}
            if abbr:
                entry["abbr"] = abbr
            group.append(entry)
            existing_codes.add(code_key)
            added += 1
            new_items.append({"name": name, "code": code})

        if added:
            with open(self.sets_file, "w", encoding="utf-8") as f:
                json.dump(current_sets, f, indent=2, ensure_ascii=False)
            reload_sets()
            refresh_logo_cache()
            names = ", ".join(item["name"] for item in new_items)
            self.loading_label.configure(
                text=f"Pobieram symbole setów 0/{added}..."
            )
            self.root.update()
            self.download_set_symbols(new_items)
            print(f"[INFO] Dodano {added} setów: {names}")

    def log(self, message: str):
        if self.log_widget:
            self.log_widget.configure(state="normal")
            self.log_widget.insert(tk.END, message + "\n")
            self.log_widget.see(tk.END)
            self.log_widget.configure(state="disabled")
        print(message)

    def get_price_from_db(self, name, number, set_name):
        name_input = normalize(name)
        number_input = number.strip().lower()
        set_input = set_name.strip().lower()

        for row in self.price_db:
            if (
                normalize(row.get("name", "")) == name_input
                and row.get("number", "").strip().lower() == number_input
                and row.get("set", "").strip().lower() == set_input
            ):
                try:
                    return float(row.get("price", 0))
                except (TypeError, ValueError):
                    return None
        return None

    def fetch_card_price(self, name, number, set_name, is_reverse=False, is_holo=False):
        name_api = normalize(name, keep_spaces=True)
        name_input = normalize(name)
        number_input = number.strip().lower()
        set_input = set_name.strip().lower()
        if set_input == "prismatic evolutions: additionals":
            set_code = "xpre"
        else:
            set_code = get_set_code(set_name)
        full_name = get_set_name(set_code)
        if hasattr(self, "set_var"):
            try:
                self.set_var.set(full_name)
            except tk.TclError:
                pass

        try:
            headers = {}
            if RAPIDAPI_KEY and RAPIDAPI_HOST:
                url = f"https://{RAPIDAPI_HOST}/cards/search"
                params = {"search": name_api}
                headers = {
                    "X-RapidAPI-Key": RAPIDAPI_KEY,
                    "X-RapidAPI-Host": RAPIDAPI_HOST,
                }
            else:
                url = "https://www.tcggo.com/api/cards/"
                params = {
                    "name": name_api,
                    "number": number_input,
                    "set": set_code,
                }
            response = requests.get(url, params=params, headers=headers, timeout=10)
            if response.status_code != 200:
                logger.warning("API error: %s", response.status_code)
                return None

            cards = response.json()
            if isinstance(cards, dict):
                if "cards" in cards:
                    cards = cards["cards"]
                elif "data" in cards:
                    cards = cards["data"]
                else:
                    cards = []
            candidates = []

            for card in cards:
                card_name_raw = card.get("name", "")
                card_number_raw = str(card.get("card_number", ""))
                card_set_info = card.get("episode", {})
                card_set_raw = ""
                if isinstance(card_set_info, dict):
                    card_set_raw = str(card_set_info.get("name", ""))

                card_name = normalize(card_name_raw)
                card_number = card_number_raw.lower()
                card_set = card_set_raw.lower()

                name_match = name_input in card_name
                number_match = number_input == card_number
                set_match = set_input in card_set or card_set.startswith(set_input)

                if name_match and number_match and set_match:
                    candidates.append(card)

            if candidates:
                best = candidates[0]
                price_eur = extract_cardmarket_price(best)
                if price_eur is not None:
                    eur_pln = self.get_exchange_rate()
                    price_pln = round(float(price_eur) * eur_pln * PRICE_MULTIPLIER, 2)
                    logger.info(
                        "Cena %s (%s, %s) = %s PLN",
                        best.get('name'),
                        number_input,
                        set_input,
                        price_pln,
                    )
                    return price_pln

            logger.debug("Nie znaleziono dokładnej karty. Zbliżone:")
            for card in cards:
                card_number = str(card.get("card_number", "")).lower()
                card_set = str(card.get("episode", {}).get("name", "")).lower()
                if number_input == card_number and set_input in card_set:
                    logger.debug(
                        "%s | %s | %s",
                        card.get('name'),
                        card_number,
                        card.get('episode', {}).get('name'),
                    )

        except requests.Timeout:
            logger.warning("Request timed out")
        except requests.RequestException as e:
            logger.warning("Fetching price from TCGGO failed: %s", e)
        except ValueError as e:
            logger.warning("Invalid JSON from TCGGO: %s", e)
        return None

    def fetch_psa10_price(self, name, number, set_name):
        """Return PSA10 price for a card converted to PLN.

        The function queries the card API similarly to ``fetch_card_price`` and
        looks up the PSA10 graded price under the
        ``prices.cardmarket.graded.psa.psa10`` path. If the nested structure or
        the value is missing at any point, an empty string is returned. The
        price is converted using the current EUR→PLN exchange rate and the
        result is formatted as an integer when possible or a float string
        otherwise.
        """

        name_api = normalize(name, keep_spaces=True)
        name_input = normalize(name)
        number_input = number.strip().lower()
        set_input = set_name.strip().lower()
        if set_input == "prismatic evolutions: additionals":
            set_code = "xpre"
        else:
            set_code = get_set_code(set_name)
        full_name = get_set_name(set_code)
        if hasattr(self, "set_var"):
            try:
                self.set_var.set(full_name)
            except tk.TclError:
                pass

        try:
            headers = {}
            if RAPIDAPI_KEY and RAPIDAPI_HOST:
                url = f"https://{RAPIDAPI_HOST}/cards/search"
                params = {"search": name_api}
                headers = {
                    "X-RapidAPI-Key": RAPIDAPI_KEY,
                    "X-RapidAPI-Host": RAPIDAPI_HOST,
                }
            else:
                url = "https://www.tcggo.com/api/cards/"
                params = {
                    "name": name_api,
                    "number": number_input,
                    "set": set_code,
                }

            response = requests.get(url, params=params, headers=headers, timeout=10)
            if response.status_code != 200:
                return ""

            cards = response.json()
            if isinstance(cards, dict):
                if "cards" in cards:
                    cards = cards["cards"]
                elif "data" in cards:
                    cards = cards["data"]
                else:
                    cards = []

            for card in cards:
                card_name_raw = card.get("name", "")
                card_number_raw = str(card.get("card_number", ""))
                card_set_info = card.get("episode", {})
                card_set_raw = ""
                if isinstance(card_set_info, dict):
                    card_set_raw = str(card_set_info.get("name", ""))

                card_name = normalize(card_name_raw)
                card_number = card_number_raw.lower()
                card_set = card_set_raw.lower()

                name_match = name_input in card_name
                number_match = number_input == card_number
                set_match = set_input in card_set or card_set.startswith(set_input)

                if name_match and number_match and set_match:
                    try:
                        graded = (
                            card.get("prices", {})
                            .get("cardmarket", {})
                            .get("graded")
                        )
                        psa10 = None
                        if isinstance(graded, list):
                            for entry in graded:
                                if (
                                    isinstance(entry, dict)
                                    and str(entry.get("company", "")).lower() == "psa"
                                    and str(entry.get("grade", ""))
                                    .replace(" ", "")
                                    .lower()
                                    in {"psa10", "10"}
                                ):
                                    psa10 = entry.get("price")
                                    break
                        elif isinstance(graded, dict):
                            psa10 = (
                                graded.get("psa", {})
                                .get("psa10")
                            )
                        if psa10 is None:
                            return ""
                        rate = self.get_exchange_rate()
                        price_pln = round(float(psa10) * rate, 2)
                        return (
                            str(int(price_pln))
                            if price_pln.is_integer()
                            else str(price_pln)
                        )
                    except (AttributeError, TypeError, ValueError):
                        return ""
            return ""
        except requests.Timeout:
            logger.warning("Request timed out")
        except requests.RequestException as e:
            logger.warning("Fetching PSA10 price failed: %s", e)
        except ValueError as e:
            logger.warning("Invalid JSON from TCGGO: %s", e)
        return ""

    def fetch_card_variants(self, name, number, set_name):
        """Return all matching cards from the API with prices."""
        name_api = normalize(name, keep_spaces=True)
        name_input = normalize(name)
        number_input = number.strip().lower()
        set_input = set_name.strip().lower()
        if set_input == "prismatic evolutions: additionals":
            set_code = "xpre"
        else:
            set_code = get_set_code(set_name)
        full_name = get_set_name(set_code)
        if hasattr(self, "set_var"):
            try:
                self.set_var.set(full_name)
            except tk.TclError:
                pass

        try:
            headers = {}
            if RAPIDAPI_KEY and RAPIDAPI_HOST:
                url = f"https://{RAPIDAPI_HOST}/cards/search"
                params = {"search": name_api}
                headers = {
                    "X-RapidAPI-Key": RAPIDAPI_KEY,
                    "X-RapidAPI-Host": RAPIDAPI_HOST,
                }
            else:
                url = "https://www.tcggo.com/api/cards/"
                params = {
                    "name": name_api,
                    "number": number_input,
                    "set": set_code,
                }

            response = requests.get(url, params=params, headers=headers, timeout=10)
            if response.status_code != 200:
                logger.warning("API error: %s", response.status_code)
                return []

            cards = response.json()
            if isinstance(cards, dict):
                if "cards" in cards:
                    cards = cards["cards"]
                elif "data" in cards:
                    cards = cards["data"]
                else:
                    cards = []

            results = []
            eur_pln = self.get_exchange_rate()
            for card in cards:
                card_name_raw = card.get("name", "")
                card_number_raw = str(card.get("card_number", ""))
                card_set_info = card.get("episode", {})
                card_set_raw = ""
                if isinstance(card_set_info, dict):
                    card_set_raw = str(card_set_info.get("name", ""))

                card_name = normalize(card_name_raw)
                card_number = card_number_raw.lower()
                card_set = card_set_raw.lower()

                name_match = name_input in card_name
                number_match = not number_input or number_input == card_number
                set_match = set_input in card_set or card_set.startswith(set_input)

                if name_match and number_match and set_match:
                    price_eur = extract_cardmarket_price(card)
                    price_pln = None
                    price_eur_value = None
                    if price_eur is not None:
                        try:
                            price_eur_value = round(float(price_eur), 2)
                        except (TypeError, ValueError):
                            price_eur_value = None
                    try:
                        eur_pln_rate = round(float(eur_pln), 4)
                    except (TypeError, ValueError):
                        eur_pln_rate = None

                    if price_eur_value is not None:
                        try:
                            price_pln = round(
                                float(price_eur_value)
                                * float(eur_pln)
                                * PRICE_MULTIPLIER,
                                2,
                            )
                        except (TypeError, ValueError):
                            price_pln = None

                    set_info = card.get("episode") or card.get("set") or {}
                    if not isinstance(set_info, dict):
                        set_info = {}
                    images = set_info.get("images", {})
                    if not isinstance(images, dict):
                        images = {}
                    set_logo = (
                        images.get("logo")
                        or images.get("logoUrl")
                        or images.get("logo_url")
                        or set_info.get("logo")
                    )
                    card_images = card.get("images", {})
                    if not isinstance(card_images, dict):
                        card_images = {}
                    image_url = (
                        card_images.get("large")
                        or card.get("image")
                        or card.get("imageUrl")
                        or card.get("image_url")
                    )

                    results.append(
                        {
                            "name": card.get("name", ""),
                            "number": card_number_raw,
                            "set": set_info.get("name", ""),
                            "price_pln": price_pln,
                            "price_eur": price_eur_value,
                            "eur_pln_rate": eur_pln_rate,
                            "image_url": image_url,
                            "set_logo_url": set_logo,
                        }
                    )
            return results
        except requests.Timeout:
            logger.warning("Request timed out")
        except requests.RequestException as e:
            logger.warning("Fetching variants from TCGGO failed: %s", e)
        except ValueError as e:
            logger.warning("Invalid JSON from TCGGO: %s", e)
        return []

    def lookup_card_info(self, name, number, set_name, is_holo=False, is_reverse=False):
        """Return image URL and pricing information for the first matching card."""
        name_api = normalize(name, keep_spaces=True)
        name_input = normalize(name)
        number_input = number.strip().lower()
        set_input = set_name.strip().lower()
        if set_input == "prismatic evolutions: additionals":
            set_code = "xpre"
        else:
            set_code = get_set_code(set_name)
        full_name = get_set_name(set_code)
        if hasattr(self, "set_var"):
            try:
                self.set_var.set(full_name)
            except tk.TclError:
                pass

        try:
            headers = {}
            if RAPIDAPI_KEY and RAPIDAPI_HOST:
                url = f"https://{RAPIDAPI_HOST}/cards/search"
                params = {"search": name_api}
                headers = {
                    "X-RapidAPI-Key": RAPIDAPI_KEY,
                    "X-RapidAPI-Host": RAPIDAPI_HOST,
                }
            else:
                url = "https://www.tcggo.com/api/cards/"
                params = {"name": name_api, "number": number_input, "set": set_code}

            response = requests.get(url, params=params, headers=headers, timeout=10)
            if response.status_code != 200:
                logger.warning("API error: %s", response.status_code)
                return None

            cards = response.json()
            if isinstance(cards, dict):
                if "cards" in cards:
                    cards = cards["cards"]
                elif "data" in cards:
                    cards = cards["data"]
                else:
                    cards = []

            for card in cards:
                card_name_raw = card.get("name", "")
                card_number_raw = str(card.get("card_number", ""))
                card_set_info = card.get("episode", {})
                card_set_raw = ""
                if isinstance(card_set_info, dict):
                    card_set_raw = str(card_set_info.get("name", ""))

                card_name = normalize(card_name_raw)
                card_number = card_number_raw.lower()
                card_set = card_set_raw.lower()

                name_match = name_input in card_name
                number_match = number_input == card_number
                set_match = set_input in card_set or card_set.startswith(set_input)

                if name_match and number_match and set_match:
                    price_eur = extract_cardmarket_price(card) or 0
                    base_rate = self.get_exchange_rate()
                    eur_pln = base_rate * PRICE_MULTIPLIER
                    price_pln = round(float(price_eur) * eur_pln, 2)
                    if is_holo or is_reverse:
                        price_pln = round(price_pln * HOLO_REVERSE_MULTIPLIER, 2)
                    set_info = card.get("episode") or card.get("set") or {}
                    images = (
                        set_info.get("images", {}) if isinstance(set_info, dict) else {}
                    )
                    set_logo = (
                        images.get("logo")
                        or images.get("logoUrl")
                        or images.get("logo_url")
                        or set_info.get("logo")
                    )
                    image_url = (
                        card.get("images", {}).get("large")
                        or card.get("image")
                        or card.get("imageUrl")
                        or card.get("image_url")
                    )
                    set_name_value = ""
                    if isinstance(set_info, dict):
                        set_name_value = set_info.get("name", "")
                    return {
                        "image_url": image_url,
                        "set_logo_url": set_logo,
                        "price_eur": round(float(price_eur), 2),
                        "eur_pln_rate": round(base_rate, 4),
                        "price_pln": price_pln,
                        "price_pln_80": round(price_pln * 0.8, 2),
                        "name": card_name_raw,
                        "number": card_number_raw,
                        "set": set_name_value,
                    }
        except requests.Timeout:
            logger.warning("Request timed out")
        except requests.RequestException as e:
            logger.warning("Lookup failed: %s", e)
        except ValueError as e:
            logger.warning("Invalid JSON from TCGGO: %s", e)
        return None

    # ZMIANA: Logika pobierania ceny nie szuka już setu, jeśli jest on znany.
    def fetch_card_data(self):
        name = self.entries["nazwa"].get()
        number_raw = self.entries["numer"].get()
        set_name = self.entries["set"].get()

        # INFO: Jeśli set nie jest znany, spróbuj go znaleźć przed szukaniem ceny.
        if not set_name:
            self.log("Set nie jest znany, próba dopasowania przed pobraniem ceny...")
            total = None
            if "/" in str(number_raw):
                num_part, total_part = str(number_raw).split("/", 1)
                number = sanitize_number(num_part)
                total = sanitize_number(total_part)
            else:
                number = sanitize_number(number_raw)

            api_sets = lookup_sets_from_api(name, number, total)
            if api_sets:
                selected_code, resolved_name = api_sets[0]
                if len(api_sets) > 1:
                    self.log(
                        f"Znaleziono {len(api_sets)} pasujących setów, "
                        f"wybieram: {resolved_name}."
                    )
                self.entries["set"].set(resolved_name)
                set_name = resolved_name  # Zaktualizuj zmienną lokalną
                if hasattr(self, "update_set_options"):
                    self.update_set_options()
            else:
                self.log("Nie udało się automatycznie dopasować setu.")

        card_type_code = self._get_card_type_code()

        number = sanitize_number(number_raw.split('/')[0])

        # Teraz pobierz cenę, mając już pewność co do setu (lub jego braku)
        cena = self.get_price_from_db(name, number, set_name)
        if cena is not None:
            cena = self.apply_variant_multiplier(cena, card_type=card_type_code)
            self.entries["cena"].delete(0, tk.END)
            self.entries["cena"].insert(0, str(cena))
            self.log(f"Price for {name} {number}: {cena} zł")
        else:
            fetched = self.fetch_card_price(name, number, set_name)
            if fetched is not None:
                fetched = self.apply_variant_multiplier(
                    fetched, card_type=card_type_code
                )
                self.entries["cena"].delete(0, tk.END)
                self.entries["cena"].insert(0, str(fetched))
                self.log(f"Price for {name} {number}: {fetched} zł")
            else:
                messagebox.showinfo(
                    "Brak wyników",
                    "Nie znaleziono ceny dla podanej karty w bazie danych.",
                )
                self.log(f"Card {name} {number} not found")

        psa10_price = self.fetch_psa10_price(name, number, set_name)
        if psa10_price:
            psa_var = getattr(self, "psa10_price_var", None)
            if hasattr(psa_var, "set"):
                try:
                    psa_var.set(psa10_price)
                except (tk.TclError, RuntimeError):
                    psa_var.set(psa10_price)
            self.log(f"PSA10 price for {name} {number}: {psa10_price} zł")
        else:
            self.log(f"PSA10 price for {name} {number} not found")

    def open_cardmarket_search(self):
        """Open a Cardmarket search for the current card in the default browser."""
        name = self.entries["nazwa"].get()
        number = sanitize_number(self.entries["numer"].get())
        search_terms = " ".join(t for t in [name, number] if t)
        params = urlencode({"searchString": search_terms})
        url = f"https://www.cardmarket.com/en/Pokemon/Products/Search?{params}"
        webbrowser.open(url)

    def get_exchange_rate(self):
        try:
            res = requests.get(
                "https://api.nbp.pl/api/exchangerates/rates/A/EUR/?format=json",
                timeout=10,
            )
            if res.status_code == 200:
                return res.json()["rates"][0]["mid"]
        except requests.Timeout:
            logger.warning("Exchange rate request timed out")
        except (requests.RequestException, ValueError, KeyError) as exc:
            logger.warning("Failed to fetch exchange rate: %s", exc)
        return 4.265

    def apply_variant_multiplier(
        self,
        price,
        card_type: Any = None,
        *,
        is_reverse: bool = False,
        is_holo: bool = False,
    ):
        """Apply holo/reverse or special variant multiplier when needed."""

        if price is None:
            return None
        code = csv_utils.try_normalize_variant_code(card_type)
        if not code:
            if is_holo:
                code = "H"
            elif is_reverse:
                code = "R"
            else:
                code = CARD_TYPE_DEFAULT
        multiplier = HOLO_REVERSE_MULTIPLIER if code in {"H", "R"} else 1

        try:
            return round(float(price) * multiplier, 2)
        except (TypeError, ValueError):
            return price

    def save_current_data(self):
        """Store the data for the currently displayed card without changing
        the index."""
        data: dict[str, Any] = {}
        raw_entries: dict[str, Any] = {}
        attribute_payload: dict[int, dict[int, Any]] = {}
        language_code = _get_current_language_code(self)
        for k, v in self.entries.items():
            try:
                if hasattr(v, "winfo_exists") and not v.winfo_exists():
                    continue
                value = v.get()
                if k == "język":
                    raw_entries[k] = language_code
                    continue
                raw_entries[k] = value
                if isinstance(k, str) and k.startswith("attribute:"):
                    parts = k.split(":", 2)
                    if len(parts) == 3:
                        try:
                            group_id = int(parts[1])
                            attr_id = int(parts[2])
                        except (TypeError, ValueError):
                            continue
                        normalized_value = value
                        if isinstance(normalized_value, (list, tuple, set)):
                            cleaned: list[Any] = []
                            for item in normalized_value:
                                if isinstance(item, str):
                                    stripped = item.strip()
                                    if stripped:
                                        cleaned.append(stripped)
                                elif item is not None:
                                    cleaned.append(item)
                            if not cleaned:
                                continue
                            normalized_value = cleaned
                        elif isinstance(normalized_value, str):
                            normalized_value = normalized_value.strip()
                            if not normalized_value:
                                continue
                        elif normalized_value is None:
                            continue
                        attribute_payload.setdefault(group_id, {})[attr_id] = normalized_value
                    continue
                data[k] = value
            except tk.TclError:
                continue
        raw_entries.setdefault("język", language_code)
        data["język"] = language_code
        psa_var = getattr(self, "psa10_price_var", None)
        if hasattr(psa_var, "get"):
            try:
                data["psa10_price"] = psa_var.get() or ""
            except (tk.TclError, RuntimeError):
                data["psa10_price"] = psa_var.get() or ""

        data.setdefault("nazwa", "")
        data.setdefault("numer", "")
        data.setdefault("set", "")
        data.setdefault("era", "")

        get_finish = getattr(self, "_get_card_finish_selection", None)
        if callable(get_finish):
            try:
                finish_selection = get_finish()
            except Exception:
                finish_selection = CardFinishSelection(
                    CARD_TYPE_DEFAULT,
                    None,
                    CARD_TYPE_LABELS.get(CARD_TYPE_DEFAULT, DEFAULT_CARD_FINISH_LABEL),
                    None,
                )
        else:
            var = getattr(self, "card_type_var", None)
            try:
                code_value = var.get() if var is not None else CARD_TYPE_DEFAULT
            except Exception:
                code_value = CARD_TYPE_DEFAULT
            code_value = normalize_card_type_code(code_value)
            finish_selection = CardFinishSelection(
                code_value,
                None,
                card_type_label(code_value),
                None,
            )
        card_type_code = normalize_card_type_code(finish_selection.code)
        ball_value = finish_selection.ball or ""
        if isinstance(ball_value, str):
            ball_value = ball_value.strip().upper()
        else:
            ball_value = ""
        if ball_value not in {"P", "M"}:
            ball_value = ""
        finish_label_value = finish_selection.label or card_type_label(card_type_code)
        finish_label = str(finish_label_value).strip() or card_type_label(card_type_code)
        raw_entries["card_type"] = card_type_code
        raw_entries["ball_type"] = ball_value
        data["ball_type"] = ball_value

        def _clean_text(value: Any) -> str:
            if isinstance(value, str):
                return value.strip()
            if value is None:
                return ""
            return str(value).strip()

        def _int_or_none(value: Any) -> int | None:
            if value in (None, ""):
                return None
            try:
                if isinstance(value, str):
                    value = value.strip()
                    if not value:
                        return None
                return int(float(str(value).replace(",", ".")))
            except (TypeError, ValueError):
                return None

        def _float_or_none(value: Any) -> float | None:
            if value in (None, ""):
                return None
            try:
                if isinstance(value, str):
                    cleaned = value.strip().replace(" ", "").replace(",", ".")
                    if not cleaned:
                        return None
                    return float(cleaned)
                return float(value)
            except (TypeError, ValueError):
                return None

        def _split_to_list(value: Any) -> list[str]:
            if value in (None, ""):
                return []
            if isinstance(value, str):
                parts = re.split(r"[;,]", value)
                return [part.strip() for part in parts if part.strip()]
            if isinstance(value, Mapping):
                return [
                    str(v).strip()
                    for v in value.values()
                    if str(v).strip()
                ]
            if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
                result: list[str] = []
                for item in value:
                    text = str(item).strip()
                    if text:
                        result.append(text)
                return result
            return []

        data.setdefault("psa10_price", "")

        for field in ("pkwiu",):
            if field in data:
                cleaned = _clean_text(data[field])
                if cleaned:
                    data[field] = cleaned
                else:
                    data.pop(field, None)

        list_fields = ("tags", "collections", "additional_codes")
        for field in list_fields:
            if field in data:
                values = _split_to_list(data[field])
                if values:
                    data[field] = values
                else:
                    data.pop(field, None)

        int_fields = ("producer_id", "group_id", "tax_id", "category_id", "unit_id")
        for field in int_fields:
            if field in data:
                value = _int_or_none(data[field])
                if value is not None:
                    data[field] = value
                else:
                    data.pop(field, None)

        if "virtual" in data:
            data["virtual"] = bool(data["virtual"])
            if not data["virtual"]:
                data.pop("virtual")

        dimensions: dict[str, float] = {}
        for axis, field in (
            ("width", "dimension_w"),
            ("height", "dimension_h"),
            ("length", "dimension_l"),
        ):
            if field in data:
                value = _float_or_none(data[field])
                if value is not None:
                    dimensions[axis] = value
                data.pop(field, None)
        if dimensions:
            data["dimensions"] = dimensions

        if attribute_payload:
            data["attributes"] = attribute_payload
        else:
            data.pop("attributes", None)

        name = data.get("nazwa")
        number = data.get("numer")
        set_name = data.get("set")
        if not data["psa10_price"]:
            fetched_psa = self.fetch_psa10_price(name, number, set_name)
            if fetched_psa:
                data["psa10_price"] = fetched_psa
                if hasattr(psa_var, "set"):
                    try:
                        psa_var.set(fetched_psa)
                    except (tk.TclError, RuntimeError):
                        psa_var.set(fetched_psa)
        data["card_type"] = card_type_code
        types = card_type_flags(card_type_code)
        data["types"] = types
        data["typ"] = finish_label
        data["variant"] = csv_utils.variant_code_to_name(card_type_code)
        existing_wc = ""
        if getattr(self, "output_data", None) and 0 <= self.index < len(self.output_data):
            current = self.output_data[self.index]
            if current and current.get("warehouse_code"):
                existing_wc = current["warehouse_code"]
        current_loc = getattr(self, "current_location", "")
        data["warehouse_code"] = existing_wc or current_loc or self.next_free_location()
        # remember last used location index for subsequent sessions
        idx = storage.location_to_index(data["warehouse_code"].split(";")[0].strip())
        storage.save_last_location(idx)
        fp = getattr(self, "current_fingerprint", None)
        if (
            fp is None
            and getattr(self, "current_image_path", None)
            and getattr(self, "hash_db", None)
        ):
            try:
                with Image.open(self.current_image_path) as img:
                    try:
                        fp = compute_fingerprint(img, use_orb=True)
                    except TypeError:
                        fp = compute_fingerprint(img)
            except (OSError, UnidentifiedImageError, ValueError) as exc:
                logger.warning(
                    "Failed to compute fingerprint for %s: %s",
                    self.current_image_path,
                    exc,
                )
                fp = None
            self.current_fingerprint = fp
        if fp is not None and getattr(self, "hash_db", None):
            if self.selected_candidate_meta:
                meta = self.selected_candidate_meta
            else:
                meta = {
                    k: data.get(k, "")
                    for k in (
                        "nazwa",
                        "numer",
                        "set",
                        "era",
                        "język",
                        "stan",
                        "typ",
                        "warehouse_code",
                    )
                }
            card_id = f"{meta.get('set', '')} {meta.get('numer', '')}".strip()
            try:
                self.hash_db.add_card_from_fp(fp, meta, card_id=card_id)
            except Exception as exc:
                logger.exception("Failed to store fingerprint")
            self.selected_candidate_meta = None
        key = f"{data['nazwa']}|{data['numer']}|{data['set']}|{data.get('era', '')}"
        data["ilość"] = 1
        self.card_cache[key] = {
            "entries": {k: v for k, v in raw_entries.items()},
            "types": types,
            "card_type": card_type_code,
            "ball_type": ball_value,
            "attributes": attribute_payload,
            "psa10_price": data.get("psa10_price", ""),
        }

        front_path = self.cards[self.index]
        front_file = os.path.basename(front_path)
        self.file_to_key[front_file] = key

        entry_widget_types: tuple[type, ...] = tuple(
            t
            for t in (getattr(tk, "Entry", None), getattr(ctk, "CTkEntry", None))
            if isinstance(t, type)
        )

        def _update_entry_value(key: str, value: Any) -> None:
            entry = self.entries.get(key)
            if isinstance(entry, tk.StringVar):
                entry.set(value if value is not None else "")
            elif entry_widget_types and isinstance(entry, entry_widget_types):
                try:
                    entry.delete(0, tk.END)
                    entry.insert(0, value if value is not None else "")
                except tk.TclError:
                    pass

        if not _clean_text(data.get("image1")):
            base_images_url = (
                os.getenv("SHOPER_IMAGE_BASE_URL", "")
                or os.getenv("SHOPER_IMAGE_BASE", "")
            ).strip().rstrip("/")
            if base_images_url:
                image_path = f"{base_images_url}/{front_file}"
                data["image1"] = image_path
                _update_entry_value("image1", image_path)
        ball_suffix = ball_value or None
        existing_code = _clean_text(data.get("product_code"))
        auto_code = csv_utils.build_product_code(
            set_name,
            number,
            card_type_code,
            ball_suffix=ball_suffix,
        )

        if existing_code:
            data["product_code"] = existing_code
        else:
            data["product_code"] = auto_code
            _update_entry_value("product_code", auto_code)

        def _set_if_empty(key: str, value: Any) -> None:
            current = data.get(key)
            if _clean_text(current):
                return
            data[key] = value
            _update_entry_value(key, value)

        data.setdefault("name", data.get("nazwa", ""))
        availability_default = self._get_default_availability_value()
        _set_if_empty("unit", "szt.")
        _set_if_empty("category", f"Karty Pokémon > {data['era']} > {data['set']}")
        _set_if_empty("producer", "Pokémon")
        # Strict mode: if category was auto-filled from Era/Set (legacy), clear it
        try:
            _strict = str(os.getenv("SHOPER_STRICT_MODE", "")).strip().lower() in {"1", "true", "yes", "on"}
        except Exception:
            _strict = False
        if _strict:
            _cat = data.get("category")
            if isinstance(_cat, str) and _cat.strip().startswith("Karty ") and " > " in _cat:
                data["category"] = ""
                _update_entry_value("category", "")

        if not _clean_text(data.get("producer_code")):
            producer_code = data.get("numer", "")
            data["producer_code"] = producer_code
            _update_entry_value("producer_code", producer_code)
        _set_if_empty("currency", "PLN")
        _set_if_empty("delivery", "3 dni")
        _set_if_empty("availability", availability_default)
        if not _clean_text(data.get("active")):
            data["active"] = "1"
            _update_entry_value("active", "1")
        _set_if_empty("vat", "23%")
        _set_if_empty(
            "seo_title",
            f"{data['nazwa']} {data['numer']} {data['set']}",
        )
        data.setdefault("seo_description", "")
        data.setdefault("seo_keywords", "")

        name = html.escape(data["nazwa"])
        number = html.escape(data["numer"])
        raw_set_name = data["set"]
        set_name = html.escape(raw_set_name)
        card_type = html.escape(data["typ"])
        condition = html.escape(data["stan"])
        psa10_price = html.escape(data.get("psa10_price", "") or "???")

        if not _clean_text(data.get("short_description")):
            short_description = (
                f'<ul style="margin:0 0 0.7em 1.2em; padding:0; font-size:1.14em;">'
                f'<li><strong>{name}</strong></li>'
                f'<li style="margin-top:0.3em;">Zestaw: {set_name}</li>'
                f'<li style="margin-top:0.3em;">Numer karty: {number}</li>'
                f'<li style="margin-top:0.3em;">Stan: {condition}</li>'
                f'<li style="margin-top:0.3em;">Typ: {card_type}</li>'
                "</ul>"
            )
            data["short_description"] = short_description
            _update_entry_value("short_description", short_description)

        psa10_date = html.escape(datetime.date.today().isoformat())
        slug = raw_set_name.replace(" ", "-")
        link_set = html.escape(f"https://kartoteka.shop/pl/c/{slug}")
        psa_icon_url = html.escape(PSA_ICON_URL)

        if not _clean_text(data.get("description")):
            description = (
                f'<div style="font-size:1.10em;line-height:1.7;">'
                f'<h2 style="margin:0 0 0.4em 0;">{name} – Pokémon TCG</h2>'
                f'<p><strong>Zestaw:</strong> {set_name}<br>'
                f'<strong>Numer karty:</strong> {number}<br>'
                f'<strong>Typ:</strong> {card_type}<br>'
                f'<strong>Stan:</strong> {condition}</p>'
                f'<div style="display:flex;align-items:center;margin:0.5em 0;">'
                f'<img src="{psa_icon_url}" alt="PSA 10" style="height:24px;width:auto;margin-right:0.4em;"/>'
                f'<span>Wartość tej karty w ocenie PSA 10 ({psa10_date}): ok. {psa10_price} PLN</span>'
                f'</div>'
                '<p>Dlaczego warto kupić w Kartoteka.shop?</p>'
                '<ul>'
                '<li>Oryginalne karty Pokémon</li>'
                '<li>Bezpieczna wysyłka i solidne opakowanie</li>'
                '<li>Profesjonalna obsługa klienta</li>'
                '</ul>'
                f'<p>Jeśli szukasz więcej kart z tego setu – sprawdź '
                f'<a href="{link_set}">pozostałe oferty</a>.</p>'
                '</div>'
            )
            data["description"] = description
            _update_entry_value("description", description)

        price = data.get("cena", "").strip()
        if price:
            data["cena"] = price
        else:
            cena_local = self.get_price_from_db(
                data["nazwa"], data["numer"], data["set"]
            )
            if cena_local is not None:
                cena_local = self.apply_variant_multiplier(
                    cena_local, card_type=card_type_code
                )
                data["cena"] = str(cena_local)
            else:
                fetched = self.fetch_card_price(
                    data["nazwa"],
                    data["numer"],
                    data["set"],
                )
                if fetched is not None:
                    fetched = self.apply_variant_multiplier(
                        fetched, card_type=card_type_code
                    )
                    data["cena"] = str(fetched)
                else:
                    data["cena"] = ""

        cena_value = data.get("cena", "")
        if cena_value is None:
            cena_value = ""
        data["price"] = cena_value

        self.output_data[self.index] = data
        if isinstance(getattr(self, "session_entries", None), list):
            if self.index >= len(self.session_entries):
                self.session_entries.extend([None] * (self.index + 1 - len(self.session_entries)))
            self.session_entries[self.index] = data.copy()
        if hasattr(self, "current_location"):
            self.current_location = ""

    def save_and_next(self):
        """Save the current card data and display the next scan."""
        if getattr(self, "current_analysis_thread", None):
            try:
                messagebox.showwarning("Info", "Trwa analiza karty, poczekaj.")
            except tk.TclError:
                pass
            return
        try:
            self.save_current_data()
        except storage.NoFreeLocationError:
            try:
                messagebox.showerror("Błąd", "Brak wolnych miejsc w magazynie")
            except tk.TclError:
                pass
            return
        if self.index < len(self.cards) - 1:
            self.index += 1
            self.show_card()
        else:
            try:
                messagebox.showinfo("Info", "To jest ostatnia karta.")
            except tk.TclError:
                pass

    def previous_card(self):
        """Save current data and display the previous scan."""
        if self.index <= 0:
            return
        self.save_current_data()
        self.index -= 1
        self.show_card()

    def next_card(self):
        """Save current data and move forward without increasing stock."""
        if self.index >= len(self.cards) - 1:
            return
        self.save_current_data()
        self.index += 1
        self.show_card()

    def remove_warehouse_code(self, code: str):
        """Remove a code and repack the affected column."""
        match = re.match(r"K(\d+)R(\d)P(\d+)", code or "")
        if not match:
            return
        box = int(match.group(1))
        column = int(match.group(2))
        for row in list(self.output_data):
            if not row:
                continue
            codes = [c.strip() for c in str(row.get("warehouse_code") or "").split(";") if c.strip()]
            if code in codes:
                codes.remove(code)
                if codes:
                    row["warehouse_code"] = ";".join(codes)
                else:
                    self.output_data.remove(row)
                break
        self.repack_column(box, column)
        if hasattr(self, "update_inventory_stats"):
            try:
                self.update_inventory_stats()
            except Exception as exc:
                logger.exception("Failed to update inventory stats")

    def load_csv_data(self):
        """Load a CSV file and merge duplicate rows."""
        csv_utils.load_csv_data(self)

    def show_session_summary(self):
        """Display a summary of the cards processed in the current session."""

        self.in_scan = False

        try:
            if getattr(self, "cards", None) and 0 <= getattr(self, "index", 0) < len(self.cards):
                self.save_current_data()
        except storage.NoFreeLocationError:
            try:
                messagebox.showerror("Błąd", "Brak wolnych miejsc w magazynie")
            except tk.TclError:
                pass
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Failed to save current card before summary")

        data_source: list[Mapping[str, Any]] = []
        if isinstance(self.session_entries, list) and any(
            isinstance(row, Mapping) for row in self.session_entries
        ):
            data_source = [row for row in self.session_entries if isinstance(row, Mapping)]
        elif isinstance(self.output_data, list):
            data_source = [row for row in self.output_data if isinstance(row, Mapping)]

        def _has_basic_fields(row: Mapping[str, Any]) -> bool:
            for key in (
                "nazwa",
                "name",
                "product_code",
                "code",
                "cena",
                "price",
                "warehouse_code",
                "kod_magazynowy",
                "location",
            ):
                value = str(row.get(key, "") or "").strip()
                if value:
                    return True
            return False

        try:
            exported_rows = csv_utils.export_csv(self)
        except Exception:
            logger.exception("Failed to prepare export data for summary")
            exported_rows = []

        self._latest_export_rows = list(exported_rows)

        session_codes: set[str] = set()
        code_locations: dict[str, set[str]] = {}
        for row in data_source:
            if not isinstance(row, Mapping):
                continue
            code = str(row.get("product_code") or row.get("code") or "").strip()
            if not code:
                continue
            session_codes.add(code)
            raw_locations = (
                row.get("warehouse_code")
                or row.get("kod_magazynowy")
                or row.get("location")
            )
            if raw_locations:
                if isinstance(raw_locations, (list, tuple, set)):
                    candidates = raw_locations
                else:
                    candidates = str(raw_locations).split(";")
                bucket = code_locations.setdefault(code, set())
                for candidate in candidates:
                    text = str(candidate).strip()
                    if text:
                        bucket.add(text)

        filtered_rows: list[Mapping[str, Any]] = []
        if exported_rows:
            for row in exported_rows:
                if not isinstance(row, Mapping):
                    continue
                code = str(row.get("product_code") or row.get("code") or "").strip()
                if session_codes and code and code not in session_codes:
                    continue
                row_copy = dict(row)
                locations = code_locations.get(code)
                if locations:
                    row_copy["warehouse_code"] = ";".join(sorted(locations))
                if _has_basic_fields(row_copy):
                    filtered_rows.append(row_copy)
        else:
            filtered_rows = [row for row in data_source if _has_basic_fields(row)]

        try:
            if filtered_rows and not getattr(self, "_summary_warehouse_written", False):
                csv_utils.append_warehouse_csv(self, exported_rows=filtered_rows)
                self._summary_warehouse_written = True
            elif not getattr(self, "_summary_warehouse_written", False):
                csv_utils.append_warehouse_csv(self)
                self._summary_warehouse_written = True
        except Exception:
            logger.exception("Failed to append session rows to warehouse")

        try:
            if exported_rows:
                for row in exported_rows:
                    if not isinstance(row, Mapping):
                        continue
                    code = str(row.get("product_code") or row.get("code") or "").strip()
                    if not code:
                        continue
                    snapshot = {
                        key: "" if value is None else str(value)
                        for key, value in row.items()
                    }
                    self._cache_store_product(code, snapshot, persist=False)
                self._persist_store_cache()
        except Exception:
            logger.exception("Failed to persist store cache")

        if getattr(self, "summary_frame", None) is not None:
            try:
                if self.summary_frame.winfo_exists():
                    self.summary_frame.destroy()
            except tk.TclError:
                pass
            self.summary_frame = None

        if getattr(self, "frame", None) is not None:
            try:
                self.frame.pack_forget()
            except tk.TclError:
                pass

        self.summary_frame = ctk.CTkFrame(self.root, fg_color=BG_COLOR)
        self.summary_frame.pack(expand=True, fill="both", padx=20, pady=20)

        ctk.CTkLabel(
            self.summary_frame,
            text="Podsumowanie sesji",
            font=("Segoe UI", 32, "bold"),
            text_color=TEXT_COLOR,
        ).pack(pady=(0, 10))

        ctk.CTkLabel(
            self.summary_frame,
            text=f"Zapisane karty: {len(filtered_rows)}",
            font=("Segoe UI", 20),
            text_color=TEXT_COLOR,
        ).pack()

        table_container = ctk.CTkScrollableFrame(
            self.summary_frame,
            fg_color=LIGHT_BG_COLOR,
        )
        table_container.pack(expand=True, fill="both", pady=(20, 10))

        headers = ["Nazwa", "Kod produktu", "Cena", "Kod magazynowy"]
        for col, header in enumerate(headers):
            table_container.grid_columnconfigure(col, weight=1)
            ctk.CTkLabel(
                table_container,
                text=header,
                font=("Segoe UI", 18, "bold"),
                text_color=TEXT_COLOR,
            ).grid(row=0, column=col, sticky="ew", padx=8, pady=(4, 6))

        def _format_value(row: Mapping[str, Any], keys: tuple[str, ...]) -> str:
            for key in keys:
                value = row.get(key)
                if value is None:
                    continue
                text = str(value).strip()
                if text:
                    return text
            return "-"

        if filtered_rows:
            for r_index, row in enumerate(filtered_rows, start=1):
                values = (
                    _format_value(row, ("nazwa", "name")),
                    _format_value(row, ("product_code", "code", "producer_code")),
                    _format_value(row, ("cena", "price")),
                    _format_value(
                        row,
                        (
                            "warehouse_code",
                            "kod_magazynowy",
                            "location",
                        ),
                    ),
                )
                for col, value in enumerate(values):
                    ctk.CTkLabel(
                        table_container,
                        text=value,
                        font=("Segoe UI", 16),
                        text_color=TEXT_COLOR,
                        anchor="w",
                        justify="left",
                    ).grid(row=r_index, column=col, sticky="ew", padx=8, pady=4)
        else:
            ctk.CTkLabel(
                table_container,
                text="Brak zapisanych kart do wyświetlenia.",
                font=("Segoe UI", 18),
                text_color=TEXT_COLOR,
            ).grid(row=1, column=0, columnspan=4, pady=20)

        button_frame = ctk.CTkFrame(self.summary_frame, fg_color="transparent")
        button_frame.pack(pady=(10, 0))

        def _export_session():
            try:
                rows = [
                    row
                    for row in getattr(self, "_latest_export_rows", [])
                    if isinstance(row, Mapping)
                ]
            except Exception:
                rows = []

            if not rows:
                try:
                    rows = [
                        row for row in csv_utils.export_csv(self) if isinstance(row, Mapping)
                    ]
                except Exception:
                    logger.exception("Failed to prepare export rows")
                    try:
                        messagebox.showerror("Błąd", "Nie udało się przygotować danych do zapisu.")
                    except tk.TclError:
                        pass
                    return

            if not rows:
                try:
                    messagebox.showinfo("Brak danych", "Brak kart do zapisania w pliku CSV.")
                except tk.TclError:
                    pass
                return

            save_path = filedialog.asksaveasfilename(
                initialfile=os.path.basename(csv_utils.STORE_EXPORT_CSV),
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv")],
            )
            if not save_path:
                return

            self._latest_export_rows = list(rows)

            try:
                csv_utils.write_store_csv(rows, save_path)
            except Exception:
                logger.exception("Failed to write CSV file")
                try:
                    messagebox.showerror("Błąd", "Nie udało się zapisać pliku CSV.")
                except tk.TclError:
                    pass
                return

            try:
                messagebox.showinfo("Sukces", "Zapisano dane do pliku CSV.")
            except tk.TclError:
                pass

            try:
                should_send = messagebox.askyesno("Wysyłka", "Czy wysłać plik do Shoper?")
            except tk.TclError:
                should_send = False

            if should_send:
                try:
                    csv_utils.send_csv_to_shoper(self, save_path)
                except Exception:
                    logger.exception("Failed to send CSV to Shoper")

            if hasattr(self, "back_to_welcome"):
                self.back_to_welcome()

        def _send_session_cards():
            if not filtered_rows:
                try:
                    messagebox.showinfo(
                        "Brak danych", "Brak kart do wysłania przez API."
                    )
                except tk.TclError:
                    pass
                return

            successes: list[str] = []
            failures: list[str] = []
            for row in filtered_rows:
                try:
                    response = self._send_card_to_shoper(row)
                except requests.RequestException as exc:
                    code = str(row.get("product_code") or row.get("code") or "?")
                    failures.append(f"{code}: {exc}")
                except Exception as exc:  # pragma: no cover - defensive logging
                    logger.exception("Failed to send card from summary")
                    code = str(row.get("product_code") or row.get("code") or "?")
                    failures.append(f"{code}: {exc}")
                else:
                    product_id = response.get("product_id") or response.get("id")
                    code = str(row.get("product_code") or row.get("code") or "?")
                    if product_id:
                        successes.append(f"{code}: ID {product_id}")
                    else:
                        successes.append(code)

            summary_lines: list[str] = []
            if successes:
                summary_lines.append("Sukcesy:")
                summary_lines.extend(f" • {item}" for item in successes)
            if failures:
                summary_lines.append("Niepowodzenia:")
                summary_lines.extend(f" • {item}" for item in failures)

            report_text = "\n".join(summary_lines) if summary_lines else "Brak wyników."
            try:
                if failures and not successes:
                    messagebox.showerror("Raport wysyłki", report_text)
                elif failures:
                    messagebox.showwarning("Raport wysyłki", report_text)
                else:
                    messagebox.showinfo("Raport wysyłki", report_text)
            except tk.TclError:
                pass

        export_btn = self.create_button(
            button_frame,
            text="Zapisz do CSV",
            command=_export_session,
            fg_color=SAVE_BUTTON_COLOR,
        )
        export_btn.grid(row=0, column=0, padx=10)

        send_btn = self.create_button(
            button_frame,
            text="Wyślij przez API",
            command=_send_session_cards,
            fg_color=FETCH_BUTTON_COLOR,
        )
        send_btn.grid(row=0, column=1, padx=10)

        return_btn = self.create_button(
            button_frame,
            text="Wróć do edycji",
            command=self.close_session_summary,
            fg_color=NAV_BUTTON_COLOR,
        )
        return_btn.grid(row=0, column=2, padx=10)

    def close_session_summary(self):
        """Hide the session summary and return to the editor view."""

        if getattr(self, "summary_frame", None) is not None:
            try:
                if self.summary_frame.winfo_exists():
                    self.summary_frame.destroy()
            except tk.TclError:
                pass
            self.summary_frame = None

        if getattr(self, "frame", None) is not None:
            try:
                self.frame.pack(expand=True, fill="both", padx=10, pady=10)
            except tk.TclError:
                pass

    def export_csv(self):  # pragma: no cover - backward compatibility
        self.show_session_summary()

    def open_config_dialog(self):
        """Display a dialog for editing Shoper API configuration."""
        url_var = tk.StringVar(value=os.getenv("SHOPER_API_URL", ""))
        token_var = tk.StringVar(value=os.getenv("SHOPER_API_TOKEN", ""))
        client_id_var = tk.StringVar(value=os.getenv("SHOPER_CLIENT_ID", ""))

        top = ctk.CTkToplevel(self.root)
        top.title("Konfiguracja Shoper API")
        top.grab_set()

        ctk.CTkLabel(top, text="Client ID:", text_color=TEXT_COLOR).grid(
            row=0, column=0, padx=10, pady=(10, 5), sticky="e"
        )
        client_id_entry = ctk.CTkEntry(top, textvariable=client_id_var, width=400)
        client_id_entry.grid(row=0, column=1, padx=10, pady=(10, 5))

        ctk.CTkLabel(top, text="URL API:", text_color=TEXT_COLOR).grid(
            row=1, column=0, padx=10, pady=5, sticky="e"
        )
        url_entry = ctk.CTkEntry(top, textvariable=url_var, width=400)
        url_entry.grid(row=1, column=1, padx=10, pady=5)

        ctk.CTkLabel(top, text="Token API:", text_color=TEXT_COLOR).grid(
            row=2, column=0, padx=10, pady=5, sticky="e"
        )
        token_entry = ctk.CTkEntry(top, textvariable=token_var, width=400)
        token_entry.grid(row=2, column=1, padx=10, pady=5)

        def save():
            url = url_var.get().strip()
            token = token_var.get().strip()
            client_id = client_id_var.get().strip()
            if not url or not token:
                messagebox.showerror(
                    "Błąd", "Podaj URL i token API (oraz Client ID jeśli wymagany)"
                )
                return
            set_key(ENV_FILE, "SHOPER_API_URL", url)
            set_key(ENV_FILE, "SHOPER_API_TOKEN", token)
            set_key(ENV_FILE, "SHOPER_CLIENT_ID", client_id)
            os.environ["SHOPER_API_URL"] = url
            os.environ["SHOPER_API_TOKEN"] = token
            os.environ["SHOPER_CLIENT_ID"] = client_id
            try:
                client = ShoperClient(url, token, client_id or None)
                try:
                    client.get("products", params={"page": 1, "per-page": 1})
                except RuntimeError as exc:
                    messagebox.showerror("Błąd", f"Autoryzacja nieudana: {exc}")
                    return
                self.shoper_client = client
                global SHOPER_API_URL, SHOPER_API_TOKEN, SHOPER_CLIENT_ID
                SHOPER_API_URL, SHOPER_API_TOKEN, SHOPER_CLIENT_ID = (
                    url,
                    token,
                    client_id,
                )
                messagebox.showinfo("Sukces", "Zapisano konfigurację Shoper API")
                top.destroy()
            except (requests.RequestException, RuntimeError) as exc:
                messagebox.showerror(
                    "Błąd", f"Nie można połączyć się z API Shoper: {exc}"
                )

        save_btn = ctk.CTkButton(
            top, text="Zapisz", command=save, fg_color=SAVE_BUTTON_COLOR
        )
        save_btn.grid(row=3, column=0, columnspan=2, pady=10)
        top.grid_columnconfigure(1, weight=1)
        self.root.wait_window(top)

    def send_csv_to_shoper(self, file_path: str):
        """Send a CSV file using the Shoper API or WebDAV fallback."""
        csv_utils.send_csv_to_shoper(self, file_path)



class AuctionRunWindow:
    """Window that monitors and controls live Discord auctions."""

    POLL_INTERVAL_MS = 1000
    IMAGE_SIZE = (320, 460)
    PARTICIPANT_LIMIT = 50

    def __init__(self, app: "CardEditorApp"):
        self.app = app
        self.bot = getattr(app, "bot", None)
        self.window = ctk.CTkToplevel(app.root)
        self.window.title("Panel aukcji")
        try:
            self.window.configure(fg_color=BG_COLOR)
        except tk.TclError:
            pass
        try:
            self.window.minsize(520, 720)
        except tk.TclError:
            pass
        if hasattr(self.window, "transient"):
            self.window.transient(app.root)
        if hasattr(self.window, "lift"):
            self.window.lift()
        self.window.protocol("WM_DELETE_WINDOW", self.close)

        self._current_image_source: Optional[str] = None
        self._photo = None
        self._poll_job: Optional[str] = None
        self._last_participants: list[str] = []

        self.title_var = tk.StringVar(value="Brak aktywnej aukcji")
        self.start_price_var = tk.StringVar(value="-")
        self.current_price_var = tk.StringVar(value="-")
        self.timer_var = tk.StringVar(value="0 s")
        self.step_var = tk.StringVar(value="1")

        container = ctk.CTkFrame(self.window, fg_color=BG_COLOR)
        container.pack(expand=True, fill="both", padx=12, pady=12)

        ctk.CTkLabel(
            container,
            textvariable=self.title_var,
            text_color=TEXT_COLOR,
            font=("Segoe UI", 26, "bold"),
        ).pack(pady=(0, 12))

        self.image_label = ctk.CTkLabel(
            container, text="Brak podglądu", text_color=TEXT_COLOR
        )
        self.image_label.pack(pady=(0, 12))

        info_frame = ctk.CTkFrame(container, fg_color=BG_COLOR)
        info_frame.pack(fill="x", pady=(0, 12))
        info_frame.grid_columnconfigure(1, weight=1)

        for row, (label, var) in enumerate(
            (
                ("Cena startowa:", self.start_price_var),
                ("Aktualna cena:", self.current_price_var),
                ("Pozostały czas:", self.timer_var),
            )
        ):
            ctk.CTkLabel(
                info_frame,
                text=label,
                text_color=TEXT_COLOR,
                font=("Segoe UI", 18),
            ).grid(row=row, column=0, sticky="w", padx=4, pady=2)
            ctk.CTkLabel(
                info_frame,
                textvariable=var,
                text_color=TEXT_COLOR,
                font=("Segoe UI", 18, "bold"),
            ).grid(row=row, column=1, sticky="w", padx=4, pady=2)

        ctk.CTkLabel(
            info_frame,
            text="Kwota przebicia:",
            text_color=TEXT_COLOR,
            font=("Segoe UI", 18),
        ).grid(row=3, column=0, sticky="w", padx=4, pady=2)
        self.step_entry = ctk.CTkEntry(
            info_frame,
            textvariable=self.step_var,
        )
        self.step_entry.grid(row=3, column=1, sticky="we", padx=4, pady=2)

        participants_frame = ctk.CTkFrame(container, fg_color=BG_COLOR)
        participants_frame.pack(expand=True, fill="both", pady=(0, 12))
        ctk.CTkLabel(
            participants_frame,
            text="Uczestnicy",
            text_color=TEXT_COLOR,
            font=("Segoe UI", 20, "bold"),
        ).pack(anchor="w")

        list_container = tk.Frame(participants_frame, bg=BG_COLOR, borderwidth=0)
        list_container.pack(expand=True, fill="both", pady=(6, 0))
        self.participants_list = tk.Listbox(
            list_container,
            height=12,
            bg=BG_COLOR,
            fg="white",
            highlightthickness=0,
            relief="flat",
            activestyle="none",
            exportselection=False,
        )
        self.participants_list.pack(expand=True, fill="both")
        self.participants_list.insert(tk.END, "Brak ofert")

        button_frame = ctk.CTkFrame(container, fg_color=BG_COLOR)
        button_frame.pack(fill="x")

        self.start_button = ctk.CTkButton(
            button_frame,
            text="Start aukcji",
            command=self.start_auction,
            fg_color=SAVE_BUTTON_COLOR,
        )
        self.start_button.pack(side="left", expand=True, fill="x", padx=4)

        self.next_button = ctk.CTkButton(
            button_frame,
            text="Następna karta",
            command=self.next_card,
            fg_color=FETCH_BUTTON_COLOR,
        )
        self.next_button.pack(side="left", expand=True, fill="x", padx=4)

        self.stop_button = ctk.CTkButton(
            button_frame,
            text="Zakończ",
            command=self.finish,
            fg_color=NAV_BUTTON_COLOR,
        )
        self.stop_button.pack(side="left", expand=True, fill="x", padx=4)

        self.sync_queue_with_bot()
        self._update_upcoming_info()
        self.app._update_auction_status()
        self._poll_status()

    def sync_queue_with_bot(self) -> None:
        """Populate the Discord bot queue with auctions from the editor."""

        bot_module = getattr(self.app, "bot", None)
        if bot_module is None or not hasattr(bot_module, "Aukcja"):
            return
        self.bot = bot_module
        auctions = []
        for row in self.app.auction_queue:
            auction = self._row_to_auction(row)
            if auction is not None:
                auctions.append(auction)
        bot_module.aukcje_kolejka = auctions

    def _row_to_auction(self, row: dict) -> Optional[object]:
        if self.bot is None or not hasattr(self.bot, "Aukcja"):
            return None
        nazwa = str(row.get("nazwa_karty") or row.get("name") or "").strip()
        numer = str(row.get("numer_karty") or row.get("number") or "").strip()
        opis = str(row.get("opis") or row.get("description") or "").strip()
        start = row.get("cena_początkowa") or row.get("price") or 0
        przebicie = row.get("kwota_przebicia") or row.get("przebicie") or 1
        czas = row.get("czas_trwania") or row.get("czas") or 30
        try:
            auction = self.bot.Aukcja(nazwa, numer, opis, start, przebicie, czas)
        except Exception:
            logger.exception("Failed to build auction from row: %s", row)
            return None
        try:
            start_value = float(str(start).replace(",", "."))
        except (TypeError, ValueError):
            start_value = getattr(auction, "cena", 0.0)
        try:
            step_value = float(str(przebicie).replace(",", "."))
        except (TypeError, ValueError):
            step_value = getattr(auction, "przebicie", 1.0)
        setattr(auction, "kwota_przebicia", step_value)
        setattr(auction, "start_price", start_value)
        setattr(auction, "source_row", row)
        image_path = row.get("images 1") or row.get("image")
        if image_path:
            setattr(auction, "local_image", image_path)
        return auction

    def start_auction(self) -> None:
        """Begin the next auction in the queue."""

        if not self._ensure_bot_ready():
            return
        queue = getattr(self.bot, "aukcje_kolejka", [])
        current = getattr(self.bot, "aktualna_aukcja", None)
        if not queue and current is None:
            messagebox.showinfo("Aukcja", "Brak kart w kolejce.")
            return
        if queue:
            step_value = self._parse_step_input()
            if step_value is None:
                return
            self._apply_step_to_auction(queue[0], step_value)
        coro = self.bot.start_next_auction(None)
        self._submit_bot_coro(coro, self.start_button)

    def next_card(self) -> None:
        """Trigger the next card in the queue."""

        if not self._ensure_bot_ready():
            return
        queue = getattr(self.bot, "aukcje_kolejka", [])
        if queue:
            step_value = self._parse_step_input()
            if step_value is None:
                return
            self._apply_step_to_auction(queue[0], step_value)
        coro = self.bot.start_next_auction(None)
        self._submit_bot_coro(coro, self.next_button)

    def finish(self) -> None:
        """Reset the current auction and close the window."""

        if self.bot is not None and hasattr(self.bot, "aktualna_aukcja"):
            self.bot.aktualna_aukcja = None
        self.close()

    def close(self) -> None:
        """Destroy the window and cancel pending callbacks."""

        if self._poll_job is not None and self.window is not None:
            try:
                self.window.after_cancel(self._poll_job)
            except tk.TclError:
                pass
            self._poll_job = None
        if self.window is not None:
            try:
                self.window.destroy()
            except tk.TclError:
                pass
        self.window = None
        if getattr(self.app, "auction_run_window", None) is self:
            self.app.auction_run_window = None

    def update_from_status(self, data: Optional[dict]) -> None:
        """Update displayed values based on the latest JSON payload."""

        if self.window is None:
            return
        self.bot = getattr(self.app, "bot", self.bot)
        auction = getattr(self.bot, "aktualna_aukcja", None) if self.bot else None
        if auction:
            self._display_auction(auction)
        else:
            self._update_upcoming_info()

        if data:
            price = data.get("ostateczna_cena")
            if price is not None:
                self._set_price(self.current_price_var, price)
            remaining = self._compute_remaining_seconds(data)
            if remaining is not None:
                self.timer_var.set(f"{remaining} s")
            obraz = data.get("obraz")
            if obraz:
                self._update_image(obraz)

        self._update_participants(data)

    def _display_auction(self, auction: object) -> None:
        name = getattr(auction, "nazwa", "")
        number = getattr(auction, "numer", "")
        title = name.strip()
        if number:
            title = f"{title} ({number})" if title else str(number)
        self.title_var.set(title or "Aukcja")
        start_price = getattr(auction, "start_price", getattr(auction, "cena", 0))
        self._set_price(self.start_price_var, start_price)
        self._set_price(self.current_price_var, getattr(auction, "cena", 0))
        self._set_step_display(
            getattr(auction, "kwota_przebicia", getattr(auction, "przebicie", None))
        )
        image_source = getattr(auction, "obraz_url", None) or getattr(auction, "local_image", None)
        if image_source:
            self._update_image(image_source)

    def _update_upcoming_info(self) -> None:
        bot_module = getattr(self.app, "bot", None)
        if bot_module is None:
            self.title_var.set("Brak połączenia z botem")
            self.start_price_var.set("-")
            self.current_price_var.set("-")
            self.timer_var.set("0 s")
            self._update_image(None)
            self._set_participant_entries([])
            return
        self.bot = bot_module
        if getattr(bot_module, "aktualna_aukcja", None):
            self._display_auction(bot_module.aktualna_aukcja)
            return
        queue = list(getattr(bot_module, "aukcje_kolejka", []))
        if queue:
            upcoming = queue[0]
            name = getattr(upcoming, "nazwa", "")
            number = getattr(upcoming, "numer", "")
            title = name.strip()
            if number:
                title = f"{title} ({number})" if title else str(number)
            self.title_var.set(title or "Następna karta")
            start_price = getattr(upcoming, "start_price", getattr(upcoming, "cena", 0))
            self._set_price(self.start_price_var, start_price)
            self._set_price(self.current_price_var, getattr(upcoming, "cena", start_price))
            self._set_step_display(
                getattr(upcoming, "kwota_przebicia", getattr(upcoming, "przebicie", None))
            )
            czas = getattr(upcoming, "czas", None)
            if czas is not None:
                try:
                    self.timer_var.set(f"{int(czas)} s")
                except (TypeError, ValueError):
                    self.timer_var.set(str(czas))
            image_source = getattr(upcoming, "local_image", None) or getattr(upcoming, "obraz_url", None)
            self._update_image(image_source)
        else:
            self.title_var.set("Brak aktywnej aukcji")
            self.start_price_var.set("-")
            self.current_price_var.set("-")
            self.timer_var.set("0 s")
            self._update_image(None)
            self._set_participant_entries([])

    def _set_price(self, var: tk.StringVar, value: object) -> None:
        text = "-"
        if value is not None:
            try:
                text = f"{float(value):.2f} PLN"
            except (TypeError, ValueError):
                text = str(value)
        var.set(text)

    def _set_step_display(self, value: object) -> None:
        if value is None:
            return
        text = self._format_step_value(value)
        if self.step_var.get() != text:
            self.step_var.set(text)

    def _format_step_value(self, value: object) -> str:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return str(value)
        if int(number) == number:
            return str(int(number))
        text = f"{number:.2f}"
        text = text.rstrip("0").rstrip(".")
        return text or "0"

    def _parse_step_input(self) -> Optional[float]:
        value = (self.step_var.get() or "").strip()
        if not value:
            value = "1"
        normalized = value.replace(",", ".")
        try:
            step = float(normalized)
        except ValueError:
            messagebox.showerror("Błąd", "Nieprawidłowa kwota przebicia.")
            return None
        if step <= 0:
            messagebox.showerror("Błąd", "Kwota przebicia musi być dodatnia.")
            return None
        self._set_step_display(step)
        return step

    def _apply_step_to_auction(self, auction: Optional[object], step_value: float) -> None:
        if auction is None:
            return
        try:
            step_float = float(step_value)
        except (TypeError, ValueError):
            return
        try:
            auction.przebicie = step_float
        except Exception:
            pass
        setattr(auction, "kwota_przebicia", step_float)
        source_row = getattr(auction, "source_row", None)
        if isinstance(source_row, dict):
            source_row["kwota_przebicia"] = self.step_var.get()

    def _update_image(self, source: Optional[str]) -> None:
        if source == self._current_image_source:
            return
        self._current_image_source = source
        if not source:
            self.image_label.configure(image=None, text="Brak podglądu")
            self._photo = None
            return
        img = _get_thumbnail(source, self.IMAGE_SIZE)
        if img is None:
            self.image_label.configure(image=None, text="Brak podglądu")
            self._photo = None
            return
        self._photo = _create_image(img)
        self.image_label.configure(image=self._photo, text="")

    def _update_participants(self, data: Optional[dict]) -> None:
        entries: list[str] = []
        auction = getattr(self.bot, "aktualna_aukcja", None) if self.bot else None
        history = None
        if auction and getattr(auction, "historia", None):
            try:
                history = list(auction.historia)
            except Exception:
                history = []
        elif data and data.get("historia"):
            history = list(data.get("historia", []))
        if history:
            trimmed = history[-self.PARTICIPANT_LIMIT :]
            for entry in trimmed:
                entries.append(self._format_history_entry(entry))
        self._set_participant_entries(entries)

    def _format_history_entry(self, entry: object) -> str:
        try:
            user, price, _timestamp = entry
        except (ValueError, TypeError):
            return str(entry)
        try:
            price_text = f"{float(price):.2f} PLN"
        except (TypeError, ValueError):
            price_text = str(price)
        return f"{user} – {price_text}"

    def _set_participant_entries(self, entries: list[str]) -> None:
        display = entries or ["Brak ofert"]
        if display == self._last_participants:
            return
        self.participants_list.delete(0, tk.END)
        for item in display:
            self.participants_list.insert(tk.END, item)
        self._last_participants = list(display)

    def _compute_remaining_seconds(self, data: dict) -> Optional[int]:
        start_str = data.get("start_time")
        if not start_str:
            return None
        try:
            start = datetime.datetime.fromisoformat(start_str.rstrip("Z"))
            duration = int(data.get("czas", 0))
            end = start + datetime.timedelta(seconds=duration)
            remaining = int((end - datetime.datetime.utcnow()).total_seconds())
            return max(remaining, 0)
        except (ValueError, TypeError):
            return None

    def _poll_status(self) -> None:
        if self.window is None:
            return
        try:
            self.app._update_auction_status()
        except Exception:
            logger.exception("Failed to refresh auction status")
        if self.window is not None:
            try:
                self._poll_job = self.window.after(
                    self.POLL_INTERVAL_MS, self._poll_status
                )
            except tk.TclError:
                self._poll_job = None

    def _ensure_bot_ready(self) -> bool:
        self.bot = getattr(self.app, "bot", self.bot)
        if self.bot is None:
            messagebox.showerror("Błąd", "Bot aukcyjny nie jest dostępny.")
            return False
        loop = getattr(self.bot, "loop", None)
        if loop is None or not getattr(loop, "is_running", lambda: False)():
            messagebox.showerror("Błąd", "Bot aukcyjny nie jest uruchomiony.")
            return False
        return True

    def _submit_bot_coro(
        self, coro: Awaitable[object], button: Optional["ctk.CTkButton"] = None
    ) -> None:
        if self.window is None:
            return
        loop = getattr(self.bot, "loop", None)
        if loop is None:
            messagebox.showerror("Błąd", "Brak aktywnej pętli asynchronicznej.")
            return
        if button is not None:
            try:
                button.configure(state="disabled")
            except tk.TclError:
                pass
        try:
            future = asyncio.run_coroutine_threadsafe(coro, loop)
        except RuntimeError as exc:
            logger.exception("Failed to submit coroutine to bot loop")
            messagebox.showerror("Błąd", str(exc))
            if button is not None:
                try:
                    button.configure(state="normal")
                except tk.TclError:
                    pass
            return

        def _on_done(fut):
            try:
                fut.result()
            except Exception as exc:  # pragma: no cover - network/discord errors
                logger.exception("Bot coroutine failed", exc_info=exc)
                if self.window is not None:
                    try:
                        self.window.after(0, lambda: messagebox.showerror("Błąd", str(exc)))
                    except tk.TclError:
                        pass
            finally:
                if button is not None and self.window is not None:
                    try:
                        self.window.after(0, lambda: button.configure(state="normal"))
                    except tk.TclError:
                        pass

        future.add_done_callback(_on_done)
