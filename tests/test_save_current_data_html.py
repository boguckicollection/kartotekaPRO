import importlib
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
import datetime

import pytest

sys.modules.setdefault("customtkinter", MagicMock())
sys.path.append(str(Path(__file__).resolve().parents[1]))
import kartoteka.ui as ui

class DummyVar:
    def __init__(self, value):
        self.value = value
    def get(self):
        return self.value
    def set(self, value):
        self.value = value


PSA10_PRICE = "123"


def make_dummy(*, db_price=None, fetched_price=None):
    return SimpleNamespace(
        entries={
            "nazwa": DummyVar("Charizard"),
            "numer": DummyVar("4"),
            "set": DummyVar("Base Set"),
            "era": DummyVar(""),
            "język": DummyVar("ENG"),
            "stan": DummyVar("NM"),
            "cena": DummyVar(""),
            "price": DummyVar(""),
            "card_type": DummyVar("C"),
        },
        psa10_price_var=DummyVar(""),
        type_vars={"Reverse": DummyVar(False), "Holo": DummyVar(False)},
        card_cache={},
        cards=["/tmp/char.jpg"],
        index=0,
        folder_name="folder",
        file_to_key={},
        product_code_map={},
        next_free_location=lambda: "K1R1P1",
        generate_location=lambda idx: "K1R1P1",
        output_data=[None],
        get_price_from_db=lambda *a: db_price,
        fetch_card_price=lambda *a: fetched_price,
        fetch_psa10_price=MagicMock(return_value=PSA10_PRICE),
        apply_variant_multiplier=lambda value, **_: value,
        _get_default_availability_value=lambda: "Dostępny",
    )


def test_html_generated():
    importlib.reload(ui)
    dummy = make_dummy()
    ui.CardEditorApp.save_current_data(dummy)
    data = dummy.output_data[0]
    dummy.fetch_psa10_price.assert_called_once_with("Charizard", "4", "Base Set")
    assert data["psa10_price"] == PSA10_PRICE
    assert data["active"] == "1"
    assert data["vat"] == "23%"
    assert data["seo_title"] == "Charizard 4 Base Set"
    assert data["short_description"].startswith("<ul")
    assert "<strong>Charizard</strong>" in data["short_description"]
    assert "Zestaw: Base Set" in data["short_description"]
    assert "Numer karty: 4" in data["short_description"]
    assert "Stan: NM" in data["short_description"]
    assert "Typ:" in data["short_description"]
    assert data["description"].startswith("<div")
    assert '<h2 style="margin:0 0 0.4em 0;">Charizard – Pokémon TCG</h2>' in data["description"]
    assert '<div style="display:flex;align-items:center;margin:0.5em 0;">' in data["description"]
    assert f'<img src="{ui.PSA_ICON_URL}"' in data["description"]
    today = datetime.date.today().isoformat()
    assert f"Wartość tej karty w ocenie PSA 10 ({today}): ok. {PSA10_PRICE} PLN" in data["description"]
    assert "<strong>Zestaw:</strong> Base Set" in data["description"]
    assert "<strong>Numer karty:</strong> 4" in data["description"]
    assert "<strong>Stan:</strong> NM" in data["description"]
    assert "<p>Dlaczego warto kupić w Kartoteka.shop?</p>" in data["description"]
    assert "<li>Oryginalne karty Pokémon</li>" in data["description"]
    assert "<li>Bezpieczna wysyłka i solidne opakowanie</li>" in data["description"]
    assert "<li>Profesjonalna obsługa klienta</li>" in data["description"]
    assert "https://kartoteka.shop/pl/c/Base-Set" in data["description"]
    assert dummy.product_code_map == {}
    assert data["product_code"] == "PKM-BAS-4C"
    assert data["warehouse_code"] == "K1R1P1"


def test_programmatically_populated_price_synced_to_shoper_payload():
    importlib.reload(ui)
    dummy = make_dummy(db_price=19.99)

    ui.CardEditorApp.save_current_data(dummy)
    data = dummy.output_data[0]

    assert data["cena"] == "19.99"
    assert data["price"] == "19.99"

    app = ui.CardEditorApp.__new__(ui.CardEditorApp)
    app.shoper_client = MagicMock()
    app._shoper_taxonomy_cache = {
        "category": {"by_name": {"Karty Pokémon >  > Base Set": 44}},
        "producer": {"by_name": {"Pokémon": 11, "Pokemon": 11}},
        "tax": {"by_name": {"23%": 33}},
        "unit": {"by_name": {"szt.": 55}},
        "availability": {"by_name": {"Dostępny": 3}},
    }

    payload = ui.CardEditorApp._build_shoper_payload(app, data)

    assert payload["price"] == pytest.approx(19.99)
