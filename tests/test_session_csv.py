import csv
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.modules.setdefault("customtkinter", MagicMock())
sys.path.append(str(Path(__file__).resolve().parents[1]))
import kartoteka.ui as ui
import kartoteka.csv_utils as csv_utils


class DummyVar:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


def make_dummy():
    return SimpleNamespace(
        entries={
            "nazwa": DummyVar("Charizard"),
            "numer": DummyVar("4"),
            "set": DummyVar("Base"),
            "era": DummyVar(""),
            "język": DummyVar("ENG"),
            "stan": DummyVar("NM"),
            "cena": DummyVar(""),
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
        session_entries=[None],
        get_price_from_db=lambda *a: None,
        fetch_card_price=lambda *a: None,
        fetch_psa10_price=lambda *a, **k: "",
    )


def test_session_entries_initialized_on_browse():
    dummy = SimpleNamespace(
        start_box_var=DummyVar("1"),
        start_col_var=DummyVar("1"),
        start_pos_var=DummyVar("1"),
        scan_folder_var=DummyVar("folder"),
        session_entries=[],
    )

    def fake_load_images(self, folder):
        self.cards = ["card1.jpg", "card2.jpg", "card3.jpg"]

    with patch.object(ui.CardEditorApp, "load_images", fake_load_images):
        ui.CardEditorApp.browse_scans(dummy)

    assert dummy.session_entries == [None, None, None]


def test_save_current_updates_session_entries():
    dummy = make_dummy()

    ui.CardEditorApp.save_current_data(dummy)

    saved = dummy.session_entries[0]
    assert saved is not None
    assert saved["name"]
    assert saved["currency"] == "PLN"
    assert saved["producer_code"] == "4"
    assert saved["ilość"] == 1
    assert saved["active"] == "1"
    assert saved["vat"] == "23%"
    assert saved["seo_title"] == "Charizard 4 Base"
    assert saved["delivery"] == "3 dni"
    assert dummy.output_data[0] is not None
    assert dummy.output_data[0]["product_code"] == "PKM-BAS-4C"
    assert dummy.output_data[0]["warehouse_code"] == "K1R1P1"
    assert dummy.output_data[0]["name"] == "Charizard"


def test_export_prefers_session_entries(tmp_path, monkeypatch):
    monkeypatch.setenv("STORE_CACHE_JSON", str(tmp_path / "cache.json"))
    globals()["csv_utils"] = importlib.reload(csv_utils)

    session_row = {
        "nazwa": "Eevee",
        "numer": "3",
        "set": "Jungle",
        "product_code": "PC_SESSION",
        "cena": "15",
        "category": "Karty Pokémon > Era1 > Jungle",
        "producer": "Pokemon",
        "short_description": "s",
        "description": "d",
        "image1": "img.jpg",
    }

    dummy = SimpleNamespace(
        session_entries=[session_row],
        output_data=[{
            "nazwa": "Fallback",
            "product_code": "PC_OUTPUT",
            "cena": "5",
            "category": "Karty",
            "producer": "Pokemon",
            "short_description": "s",
            "description": "d",
            "image1": "img.jpg",
        }],
    )

    rows = csv_utils.export_csv(dummy)
    assert len(rows) == 1
    assert rows[0]["product_code"] == "PC_SESSION"

