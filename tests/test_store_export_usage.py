import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
import tkinter as tk
import importlib

# provide minimal customtkinter stub before importing modules
sys.modules["customtkinter"] = SimpleNamespace(
    CTkEntry=tk.Entry,
    CTkImage=MagicMock(),
    CTkButton=MagicMock,
    CTkToplevel=MagicMock,
)

sys.path.append(str(Path(__file__).resolve().parents[1]))
import kartoteka.ui as ui
import kartoteka.csv_utils as csv_utils
importlib.reload(ui)
importlib.reload(csv_utils)


class DummyVar:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


def test_normalise_api_product_extracts_fields():
    product = {
        "code": "PKM-PAL-1C",
        "translations": {"pl_PL": {"name": "Pikachu"}},
        "price": "99",
        "categories": [{"path": "Karty Pokémon > EraX > Paldea Evolved"}],
        "images": [{"url": "https://example.com/pikachu.png"}],
    }

    result = csv_utils.normalise_api_product(product)
    assert result is not None
    code, row = result
    assert code == "PKM-PAL-1C"
    assert row["name"] == "Pikachu"
    assert row["price"] == "99"
    assert row["category"] == "Karty Pokémon > EraX > Paldea Evolved"
    assert csv_utils.product_image_url(row) == "https://example.com/pikachu.png"


def test_analyze_and_fill_uses_store_cache(monkeypatch):
    store_row = csv_utils.normalize_store_cache_row(
        "PKM-PAL-1C",
        {
            "name": "Pikachu",
            "price": "99",
            "category": "Karty Pokémon > EraX > Paldea Evolved",
        },
    )
    store_data = {"PKM-PAL-1C": store_row}

    name_entry = MagicMock()
    num_entry = MagicMock()
    set_var = DummyVar("")
    era_var = DummyVar("")
    price_entry = MagicMock()
    card_type_var = DummyVar("C")
    for entry in (name_entry, num_entry, price_entry):
        entry.delete = MagicMock()
        entry.insert = MagicMock()

    dummy = SimpleNamespace(
        root=SimpleNamespace(after=lambda delay, func: func()),
        entries={
            "nazwa": name_entry,
            "numer": num_entry,
            "set": set_var,
            "era": era_var,
            "cena": price_entry,
            "card_type": card_type_var,
        },
        index=0,
        update_set_options=lambda: None,
        update_set_area_preview=lambda *a, **k: None,
        store_data=store_data,
        hash_db=None,
        auto_lookup=False,
        card_type_var=card_type_var,
    )
    dummy._apply_analysis_result = ui.CardEditorApp._apply_analysis_result.__get__(dummy, ui.CardEditorApp)
    dummy._get_card_type_code = ui.CardEditorApp._get_card_type_code.__get__(dummy, ui.CardEditorApp)
    dummy._set_card_type_code = ui.CardEditorApp._set_card_type_code.__get__(dummy, ui.CardEditorApp)
    dummy._set_card_type_from_mapping = ui.CardEditorApp._set_card_type_from_mapping.__get__(dummy, ui.CardEditorApp)

    dummy._persist_store_cache = lambda: None

    def get_store_product(code):
        return store_data.get(code)

    def cache_store_product(code, row, persist=True):
        store_data[code] = csv_utils.normalize_store_cache_row(code, row)
        return store_data[code]

    dummy._get_store_product = get_store_product
    dummy._cache_store_product = cache_store_product

    monkeypatch.setattr(
        ui,
        "analyze_card_image",
        lambda *a, **k: {"name": "Pikachu", "number": "1", "set": "Paldea Evolved"},
    )

    ui.CardEditorApp._analyze_and_fill(dummy, "x", 0)
    assert era_var.value == "EraX"
    price_entry.insert.assert_called_with(0, "99")
