import importlib
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest
import requests

sys.modules.setdefault("customtkinter", MagicMock())
sys.path.append(str(Path(__file__).resolve().parents[1]))
import kartoteka.ui as ui  # noqa: E402
importlib.reload(ui)


@pytest.fixture
def shoper_availability_entries() -> List[Dict[str, Any]]:
    return [
        {"availability_id": 1, "name": "Dostępny"},
        {"availability_id": 4, "name": "Średnia ilość"},
    ]


def _translation_dict(translations):
    mapping = {}
    for entry in translations:
        if not isinstance(entry, dict):
            continue
        code = entry.get("language_code")
        if not code:
            continue
        mapping[code] = entry
    return mapping


def test_ensure_taxonomy_cache_prefers_high_priority_availability(
    shoper_availability_entries: List[Dict[str, Any]]
):
    app = ui.CardEditorApp.__new__(ui.CardEditorApp)
    app._shoper_taxonomy_cache = {
        "category": {"by_name": {"placeholder": 1}},
        "producer": {"by_name": {"placeholder": 1}},
        "tax": {"by_name": {"placeholder": 1}},
        "unit": {"by_name": {"placeholder": 1}},
    }

    def _fake_get(endpoint: str, params: Optional[Dict[str, Any]] = None):
        if endpoint == "availabilities":
            return {"list": shoper_availability_entries}
        return {"list": []}

    app.shoper_client = MagicMock()
    app.shoper_client.get.side_effect = _fake_get

    cache = app._ensure_shoper_taxonomy_cache()
    availability = cache.get("availability", {})

    assert availability.get("available_id") == 4
    assert availability.get("available_label") == "Średnia ilość"


def test_build_shoper_payload_forwards_optional_fields():
    app = ui.CardEditorApp.__new__(ui.CardEditorApp)
    app.shoper_client = MagicMock()
    app._shoper_taxonomy_cache = {
        "category": {"by_name": {"karty": 44}},
        "producer": {"by_name": {"pokemon": 11}},
        "tax": {"by_name": {"23%": 33}},
        "unit": {"by_name": {"szt.": 55}},
        "availability": {
            "by_name": {"3": 3, "dostępny": 3, "dostepny": 3},
        },
    }
    card = {
        "nazwa": "Sample",
        "numer": "5",
        "product_code": "PKM-TEST",
        "cena": 12.5,
        "vat": "23%",
        "unit": "szt.",
        "category": "Karty",
        "producer": "Pokemon",
        "short_description": "short",
        "description": "desc",
        "seo_title": "SEO Title",
        "seo_description": "SEO Desc",
        "seo_keywords": "key1, key2",
        "permalink": "sample-product",
        "availability": "Dostępny",
        "delivery": "24h",
        "ilość": 2,
        "stock_warnlevel": 1,
        "producer_id": 11,
        "group_id": 22,
        "tax_id": 33,
        "category_id": 44,
        "unit_id": 55,
        "type": "virtual",
        "code": "CODE-123",
        "ean": "1234567890123",
        "pkwiu": "58.11",
        "tags": ["tag1", "tag2"],
        "collections": ["coll"],
        "additional_codes": ["A1"],
        "dimensions": {"width": 1.1, "height": 2.2},
        "virtual": True,
        "image1": "img.jpg",
    }

    payload = app._build_shoper_payload(card)

    app.shoper_client.get.assert_not_called()

    translations = _translation_dict(payload["translations"])
    assert "pl_PL" in translations
    pl_translation = translations["pl_PL"]
    assert pl_translation["language_id"] == 1
    assert pl_translation["name"] == "Sample 5"
    assert pl_translation["short_description"] == "short"
    assert pl_translation["description"] == "desc"
    assert pl_translation["seo_title"] == "SEO Title"
    assert pl_translation["seo_description"] == "SEO Desc"
    assert pl_translation["seo_keywords"] == "key1, key2"
    assert pl_translation["permalink"] == "sample-product"
    stock_payload = payload["stock"]
    assert stock_payload["stock"] == 2
    assert stock_payload["warn_level"] == 1
    assert stock_payload["price"] == pytest.approx(12.5)
    assert stock_payload["availability_id"] == 3
    assert "ean" not in payload
    assert "type" not in payload
    assert payload["producer_id"] == 11
    assert payload["group_id"] == 22
    assert payload["tax_id"] == 33
    assert payload["category_id"] == 44
    assert payload["unit_id"] == 55
    assert payload["availability_id"] == 3
    for field in ("name", "short_description", "description", "category", "producer", "delivery", "unit", "vat", "availability"):
        assert field not in payload
    assert "code" not in payload
    assert payload["pkwiu"] == "58.11"
    assert payload["dimensions"] == {"width": 1.1, "height": 2.2}
    assert payload["tags"] == ["tag1", "tag2"]
    assert payload["collections"] == ["coll"]
    assert payload["additional_codes"] == ["A1"]
    assert payload["virtual"] is True
    assert "images" not in payload

    minimal = {"nazwa": "Sample", "product_code": "PKM-EMPTY"}
    minimal_payload = app._build_shoper_payload(minimal)
    minimal_stock = minimal_payload["stock"]
    assert minimal_stock["stock"] == 1
    assert minimal_stock["price"] == pytest.approx(0.0)
    minimal_availability = minimal_stock.get("availability_id")
    if minimal_availability is not None:
        assert minimal_availability == minimal_payload.get("availability_id")
    assert "ean" not in minimal_payload
    assert "dimensions" not in minimal_payload
    minimal_translations = _translation_dict(minimal_payload["translations"])
    assert minimal_translations["pl_PL"]["name"] == "Sample"
    for field in ("name", "short_description", "description", "category", "producer", "unit", "vat", "availability"):
        assert field not in minimal_payload


def test_build_shoper_payload_coerces_currency_suffixed_price():
    app = ui.CardEditorApp.__new__(ui.CardEditorApp)
    app.shoper_client = MagicMock()
    app._shoper_taxonomy_cache = {
        "producer": {"by_name": {}},
        "tax": {"by_name": {}},
        "unit": {"by_name": {}},
        "availability": {"by_name": {}},
    }

    card = {
        "nazwa": "Sample",
        "product_code": "PKM-CURRENCY",
        "cena": "14,99 zł",
    }

    payload = app._build_shoper_payload(card)

    assert payload["price"] == pytest.approx(14.99)


def test_build_shoper_payload_prefers_price_field():
    app = ui.CardEditorApp.__new__(ui.CardEditorApp)
    app.shoper_client = MagicMock()
    app._shoper_taxonomy_cache = {
        "producer": {"by_name": {}},
        "tax": {"by_name": {}},
        "unit": {"by_name": {}},
        "availability": {"by_name": {}},
    }

    card = {
        "nazwa": "Sample",
        "product_code": "PKM-PRICE",
        "cena": "0.10",
        "price": "10",
    }

    payload = app._build_shoper_payload(card)

    assert payload["price"] == pytest.approx(10.0)


def test_build_shoper_payload_uses_fallback_availability_when_missing_defaults():
    app = ui.CardEditorApp.__new__(ui.CardEditorApp)
    app.shoper_client = MagicMock()
    app._shoper_taxonomy_cache = {
        "producer": {"by_name": {}},
        "tax": {"by_name": {}},
        "unit": {"by_name": {}},
        "availability": {
            "by_id": {
                7: {"availability_id": 7, "name": "Dostępny"},
                9: {"availability_id": 9, "name": "Brak"},
            },
            "by_name": {},
        },
    }

    payload = app._build_shoper_payload({
        "nazwa": "Sample",
        "product_code": "PKM-FALLBACK",
    })

    assert payload["availability_id"] == 7
    assert payload["stock"]["availability_id"] == 7


def test_build_shoper_payload_rejects_unknown_availability_id():
    app = ui.CardEditorApp.__new__(ui.CardEditorApp)
    app.shoper_client = MagicMock()
    app._shoper_taxonomy_cache = {
        "category": {"by_name": {"placeholder": 1}},
        "producer": {"by_name": {"placeholder": 1}},
        "tax": {"by_name": {"placeholder": 1}},
        "unit": {"by_name": {"placeholder": 1}},
        "availability": {
            "by_id": {5: {"availability_id": 5}},
            "by_name": {"dostepny": 5},
            "aliases": {"dostepny": 5, "5": 5},
        },
    }

    card = {
        "nazwa": "Sample",
        "product_code": "PKM-AVAIL",
        "availability": "999",
    }

    with pytest.raises(
        RuntimeError, match=r"Nie znaleziono identyfikatorów Shoper dla: dostępności: 999"
    ):
        app._build_shoper_payload(card)


def test_build_shoper_payload_uses_overrides_when_languages_forbidden():
    app = ui.CardEditorApp.__new__(ui.CardEditorApp)
    app.shoper_language_overrides = {"de_DE": 99}

    class _FakeResponse:
        status_code = 403

    class _FakeClient:
        def __init__(self):
            self.calls: list[str] = []

        def get(self, endpoint):
            self.calls.append(endpoint)
            error = requests.HTTPError("Forbidden")
            error.response = _FakeResponse()
            raise error

    fake_client = _FakeClient()
    app.shoper_client = fake_client
    app._shoper_taxonomy_cache = {
        "producer": {"by_name": {}},
        "tax": {"by_name": {}},
        "unit": {"by_name": {}},
        "availability": {"by_name": {}},
    }

    card = {
        "nazwa": "Karta",
        "product_code": "PKM-DE",
        "translation_locale": "de_DE",
        "translations": [
            {
                "language_code": "de_DE",
                "name": "Karte",
                "short_description": "Kurzbeschreibung",
            }
        ],
    }

    payload = app._build_shoper_payload(card)

    assert fake_client.calls == ["languages"]
    translations = _translation_dict(payload["translations"])
    assert translations["de_DE"]["language_id"] == 99
    assert translations["de_DE"]["short_description"] == "Kurzbeschreibung"


def test_build_shoper_payload_raises_for_unknown_translation_locale():
    app = ui.CardEditorApp.__new__(ui.CardEditorApp)
    app._ensure_shoper_languages_map = lambda: {"by_code": {}, "by_id": {}}

    card = {
        "nazwa": "Karta", 
        "product_code": "PKM-NO-ID",
        "translation_locale": "de_DE",
        "translations": [{"language_code": "de_DE", "name": "Karte"}],
    }

    with pytest.raises(RuntimeError, match=r"SHOPER_LANGUAGE_OVERRIDES"):
        app._build_shoper_payload(card)


def test_build_shoper_payload_resolves_paginated_taxonomy_entries():
    app = ui.CardEditorApp.__new__(ui.CardEditorApp)
    category_pages = iter(
        [
            {"page": 1, "pages": 2, "list": [{"category_id": 1, "name": "Visible"}]},
            {"page": 2, "pages": 2, "list": [{"category_id": 42, "name": "Hidden Jewel"}]},
        ]
    )

    recorded_params: List[Optional[Dict[str, Any]]] = []

    def fake_get(endpoint, params=None):
        if endpoint != "categories":
            pytest.fail(f"Unexpected endpoint requested: {endpoint}")
        recorded_params.append(params)
        try:
            return next(category_pages)
        except StopIteration:  # pragma: no cover - sanity guard for failing pagination
            pytest.fail("Pagination requested more pages than available")

    app.shoper_client = MagicMock()
    app.shoper_client.get.side_effect = fake_get
    app._shoper_taxonomy_cache = {
        "producer": {"by_name": {"pokemon": 11}},
        "tax": {"by_name": {"23%": 33}},
        "unit": {"by_name": {"szt.": 55}},
        "availability": {"by_name": {"dostepny": 3}},
    }

    card = {"nazwa": "Card", "product_code": "PKM-PAGE", "category": "Hidden Jewel"}

    payload = app._build_shoper_payload(card)

    assert payload["category_id"] == 42
    assert app._shoper_taxonomy_cache["category"]["by_id"][42]["name"] == "Hidden Jewel"
    assert app.shoper_client.get.call_count == 2
    assert recorded_params[0] in (None, {})
    assert recorded_params[1] == {"page": 2}


def test_build_shoper_payload_resolves_category_path_segments():
    app = ui.CardEditorApp.__new__(ui.CardEditorApp)
    app.shoper_client = MagicMock()
    app._shoper_taxonomy_cache = {
        "category": {
            "by_name": {
                "Prismatic Evolutions": 128,
            },
            "default": 999,
        }
    }

    card = {
        "nazwa": "Card",
        "product_code": "PKM-PATH",
        "category": "Karty Pokémon > Scarlet & Violet > Prismatic Evolutions",
    }

    payload = app._build_shoper_payload(card)

    assert payload["category_id"] == 128


def test_build_shoper_payload_resolves_numeric_prefix_taxonomy_alias():
    app = ui.CardEditorApp.__new__(ui.CardEditorApp)
    app.shoper_client = MagicMock()
    app._shoper_taxonomy_cache = {
        "category": {
            "by_name": {"Paradox Rift": 57},
            "by_id": {57: {"category_id": 57}},
            "aliases": {"57": 57, "paradox rift": 57},
        },
        "producer": {"by_name": {}},
        "tax": {"by_name": {}},
        "unit": {"by_name": {}},
        "availability": {"by_name": {}},
    }

    card = {
        "nazwa": "Card",
        "product_code": "PKM-ALIAS",
        "category": "57 Paradox Rift",
    }

    payload = app._build_shoper_payload(card)

    assert payload["category_id"] == 57


def test_build_shoper_payload_accepts_dict_taxonomy_values():
    app = ui.CardEditorApp.__new__(ui.CardEditorApp)
    app.shoper_client = MagicMock()
    app._shoper_taxonomy_cache = {
        "category": {
            "by_name": {"karty": 44},
            "by_id": {44: {"category_id": 44}},
            "aliases": {"44": 44},
        },
        "producer": {
            "by_name": {"pokemon": 11},
            "by_id": {11: {"producer_id": 11}},
            "aliases": {"11": 11},
        },
        "tax": {"by_name": {"23%": 33}},
        "unit": {
            "by_name": {"szt.": 55},
            "by_id": {55: {"unit_id": 55}},
            "aliases": {"55": 55},
        },
        "availability": {
            "by_name": {"dostępny": 3},
            "by_id": {3: {"availability_id": 3}},
            "aliases": {"3": 3},
        },
    }

    card = {
        "nazwa": "Sample",
        "product_code": "PKM-DICT",
        "category": {"name": "Karty"},
        "producer": {"producer_id": 11, "name": "Pokemon"},
        "vat": {"value": "23%"},
        "unit": {"unit_id": 55},
        "availability": {"availability_id": 3, "name": "Dostępny"},
    }

    payload = app._build_shoper_payload(card)

    assert payload["category_id"] == 44
    assert payload["producer_id"] == 11
    assert payload["tax_id"] == 33
    assert payload["unit_id"] == 55
    assert payload["availability_id"] == 3


def test_build_shoper_payload_prefers_translation_locale_content():
    app = ui.CardEditorApp.__new__(ui.CardEditorApp)
    app.shoper_client = MagicMock()
    card = {
        "nazwa": "Sample",
        "product_code": "PKM-TRANS",
        "short_description": "legacy short",
        "description": "legacy desc",
        "seo_title": "legacy title",
        "seo_description": "legacy seo desc",
        "seo_keywords": "legacy keywords",
        "permalink": "legacy-link",
        "translations": [
            {
                "translation_id": 1,
                "language_code": "pl_PL",
                "short_description": "translated short",
                "description": "translated desc",
                "seo_title": "translated title",
                "seo_description": "translated seo desc",
                "seo_keywords": "translated keywords",
                "permalink": "translated-link",
            },
            {
                "translation_id": 2,
                "language_code": "en_US",
                "short_description": "english short",
            },
        ],
    }

    payload = app._build_shoper_payload(card)

    translations = _translation_dict(payload["translations"])
    pl_translation = translations["pl_PL"]
    assert pl_translation["name"] == "Sample"
    assert pl_translation["short_description"] == "translated short"
    assert pl_translation["description"] == "translated desc"
    assert pl_translation["seo_title"] == "translated title"
    assert pl_translation["seo_description"] == "translated seo desc"
    assert pl_translation["seo_keywords"] == "translated keywords"
    assert pl_translation["permalink"] == "translated-link"

    en_translation = translations["en_US"]
    assert en_translation["language_id"] == 2
    assert en_translation["short_description"] == "english short"


def test_build_shoper_payload_fetches_taxonomy_when_missing():
    app = ui.CardEditorApp.__new__(ui.CardEditorApp)
    client = MagicMock()
    responses = {
        "categories": {"list": [{"category_id": 44, "name": "Karty"}]},
        "producers": {"list": [{"producer_id": 11, "name": "Pokemon"}]},
        "taxes": {"list": [{"tax_id": 33, "name": "23%"}]},
        "units": {"list": [{"unit_id": 55, "name": "szt."}]},
        "availabilities": {
            "list": [
                {"availability_id": 3, "name": "Dostępny"},
                {"availability_id": 7, "name": "Niedostępny", "default": True},
            ]
        },
    }

    def _fake_get(endpoint, **kwargs):
        return responses[endpoint]

    client.get.side_effect = _fake_get
    app.shoper_client = client
    app._shoper_taxonomy_cache = {}

    card = {
        "nazwa": "Sample",
        "product_code": "PKM-TEST",
        "category": "Karty",
        "producer": "Pokemon",
        "vat": "23%",
        "unit": "szt.",
        "availability": "Dostępny",
    }

    payload = app._build_shoper_payload(card)

    assert payload["category_id"] == 44
    assert payload["producer_id"] == 11
    assert payload["tax_id"] == 33
    assert payload["unit_id"] == 55
    assert payload["availability_id"] == 3
    assert client.get.call_count == 5
    for endpoint in ("categories", "producers", "taxes", "units", "availabilities"):
        assert any(call.args[0] == endpoint for call in client.get.call_args_list)

    cache = app._shoper_taxonomy_cache
    assert cache["category"]["by_name"]["Karty"] == 44
    assert cache["availability"]["aliases"]["3"] == 3
    assert cache["availability"]["available_label"] == "Dostępny"
    assert cache["availability"]["available_id"] == 3
    assert getattr(app, "_default_availability_value", None) == "Dostępny"
    assert ui.csv_utils.get_default_availability() == "Dostępny"


def test_build_shoper_payload_prefers_cached_available_over_default():
    app = ui.CardEditorApp.__new__(ui.CardEditorApp)
    app._default_availability_value = None
    app._default_availability_id = None
    ui.csv_utils.set_default_availability({"available_label": "Domyślny", "available_id": 1})

    availability_mapping = {
        "available_label": "Dostępny od ręki",
        "available_id": 4,
        "default": 1,
        "by_name": {"Dostępny od ręki": 4, "Domyślny": 1},
        "by_id": {
            1: {"availability_id": 1, "name": "Domyślny"},
            4: {"availability_id": 4, "name": "Dostępny od ręki"},
        },
        "aliases": {"dostepny od reki": 4, "4": 4, "domyslny": 1, "1": 1},
    }

    app._shoper_taxonomy_cache = {
        "category": {"by_name": {"Karty": 44}},
        "producer": {"by_name": {"Pokemon": 11}},
        "tax": {"by_name": {"23%": 33}},
        "unit": {"by_name": {"szt.": 55}},
        "availability": availability_mapping,
    }

    card = {
        "nazwa": "Sample",
        "product_code": "PKM-CACHED",
        "category": "Karty",
        "producer": "Pokemon",
        "vat": "23%",
        "unit": "szt.",
    }

    payload = app._build_shoper_payload(card)

    assert payload["availability_id"] == 4


def test_build_shoper_payload_uses_cached_default_availability_when_missing():
    app = ui.CardEditorApp.__new__(ui.CardEditorApp)
    app._default_availability_value = None
    app._default_availability_id = None
    ui.csv_utils.set_default_availability({"available_label": "Dostępny", "available_id": 1})

    availability_mapping = {
        "available_label": "Przedsprzedaż",
        "available_id": 9,
        "default": 9,
        "by_name": {"Przedsprzedaż": 9},
        "by_id": {
            9: {"availability_id": 9, "name": "Przedsprzedaż"},
        },
        "aliases": {"przedsprzedaz": 9, "9": 9},
    }

    app._shoper_taxonomy_cache = {
        "category": {"by_name": {"Karty": 44}},
        "producer": {"by_name": {"Pokemon": 11}},
        "tax": {"by_name": {"23%": 33}},
        "unit": {"by_name": {"szt.": 55}},
        "availability": availability_mapping,
    }

    card = {
        "nazwa": "Sample",
        "product_code": "PKM-TEST",
        "category": "Karty",
        "producer": "Pokemon",
        "vat": "23%",
        "unit": "szt.",
    }

    payload = app._build_shoper_payload(card)

    assert payload["availability_id"] == 9
    assert getattr(app, "_default_availability_value", None) == "Przedsprzedaż"
    assert ui.csv_utils.get_default_availability() == "Przedsprzedaż"


def test_build_shoper_payload_recognises_average_quantity_default():
    app = ui.CardEditorApp.__new__(ui.CardEditorApp)
    app.shoper_client = MagicMock()
    app._default_availability_value = None
    app._default_availability_id = None
    ui.csv_utils.set_default_availability("1")

    availability_mapping = {
        "default": "Średnia ilość",
        "by_name": {"Średnia ilość": 4},
        "by_id": {4: {"availability_id": 4, "name": "Średnia ilość"}},
    }

    app._shoper_taxonomy_cache = {
        "category": {"by_name": {}},
        "producer": {"by_name": {}},
        "tax": {"by_name": {}},
        "unit": {"by_name": {}},
        "availability": availability_mapping,
    }

    app._refresh_default_availability_from_cache()
    availability_mapping["default"] = availability_mapping.get("available_id") or availability_mapping.get(
        "default"
    )

    card = {"nazwa": "Sample", "product_code": "PKM-AVERAGE"}

    payload = app._build_shoper_payload(card)

    assert payload["availability_id"] == 4


def test_build_shoper_payload_missing_required_taxonomy_raises():
    app = ui.CardEditorApp.__new__(ui.CardEditorApp)
    client = MagicMock()
    client.get.return_value = {"list": [{"category_id": 1, "name": "Inna"}]}
    app.shoper_client = client
    app._shoper_taxonomy_cache = {}

    card = {
        "nazwa": "Sample",
        "product_code": "PKM-TEST",
        "category": "Nieznana",
    }

    with pytest.raises(RuntimeError) as excinfo:
        app._build_shoper_payload(card)

    message = str(excinfo.value)
    assert "kategorii" in message
    assert "Nieznana" in message
