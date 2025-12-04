import csv
import importlib
from collections.abc import Mapping
from types import SimpleNamespace
from unittest.mock import MagicMock
from pathlib import Path
import sys

import requests

sys.path.append(str(Path(__file__).resolve().parent))
sys.modules.setdefault("customtkinter", MagicMock())
sys.path.append(str(Path(__file__).resolve().parents[1]))

import kartoteka.csv_utils as csv_utils
import kartoteka.ui as ui
from tests.ctk_mocks import (
    DummyCTkButton,
    DummyCTkFrame,
    DummyCTkLabel,
    DummyCTkScrollableFrame,
)


def _reload_csv_utils(monkeypatch, tmp_path):
    monkeypatch.setenv("STORE_CACHE_JSON", str(tmp_path / "cache.json"))
    globals()["csv_utils"] = importlib.reload(csv_utils)
    return csv_utils


def _make_app(rows):
    return SimpleNamespace(output_data=rows, session_entries=[])


def test_export_csv_overrides_cached_price(tmp_path, monkeypatch):
    module = _reload_csv_utils(monkeypatch, tmp_path)

    cached_row = {
        "product_code": "PC1",
        "name": "Pikachu",
        "category": "Karty Pokémon > Era1 > Base",
        "producer": "Pokemon",
        "short_description": "s",
        "description": "d",
        "price": "0.10",
        "currency": "PLN",
        "vat": "5%",
        "stock": "3",
    }

    session_row = {
        "nazwa": "Pikachu",
        "numer": "1",
        "set": "Base",
        "era": "Era1",
        "product_code": "PC1",
        "cena": "10",
        "category": "Karty Pokémon > Era1 > Base",
        "producer": "Pokemon",
        "short_description": "s",
        "description": "d",
        "image1": "img.jpg",
        "currency": "EUR",
        "vat": "8%",
    }

    app = SimpleNamespace(
        output_data=[session_row],
        session_entries=[],
        store_data={"PC1": cached_row},
    )

    rows = module.export_csv(app)

    assert len(rows) == 1
    row = rows[0]
    assert row["product_code"] == "PC1"
    assert row["price"] == "10"
    assert row["currency"] == "EUR"
    assert row["vat"] == "8%"


def test_export_csv_overrides_cached_cena(tmp_path, monkeypatch):
    module = _reload_csv_utils(monkeypatch, tmp_path)

    cached_row = {
        "product_code": "PC1",
        "name": "Pikachu",
        "category": "Karty Pokémon > Era1 > Base",
        "producer": "Pokemon",
        "short_description": "s",
        "description": "d",
        "price": "0.10",
        "cena": "0.10",
        "currency": "PLN",
        "vat": "5%",
        "stock": "3",
    }

    session_row = {
        "nazwa": "Pikachu",
        "numer": "1",
        "set": "Base",
        "era": "Era1",
        "product_code": "PC1",
        "cena": "10",
        "category": "Karty Pokémon > Era1 > Base",
        "producer": "Pokemon",
        "short_description": "s",
        "description": "d",
        "image1": "img.jpg",
    }

    app = SimpleNamespace(
        output_data=[session_row],
        session_entries=[],
        store_data={"PC1": cached_row},
    )

    rows = module.export_csv(app)

    assert len(rows) == 1
    row = rows[0]
    assert row["product_code"] == "PC1"
    assert row["price"] == "10"
    assert row["cena"] == "10"


def test_export_includes_new_fields(tmp_path, monkeypatch):
    module = _reload_csv_utils(monkeypatch, tmp_path)

    app = _make_app(
        [
            {
                "nazwa": "Pikachu",
                "numer": "1",
                "set": "Base",
                "era": "Era1",
                "product_code": 1,
                "cena": "10",
                "category": "Karty Pokémon > Era1 > Base",
                "producer": "Pokemon",
                "short_description": "s",
                "description": "d",
                "image1": "img.jpg",
            }
        ]
    )

    rows = module.export_csv(app)
    assert len(rows) == 1
    row = rows[0]
    assert row["name"] == "Pikachu"
    assert row["category"] == "Karty Pokémon > Era1 > Base"
    assert row["currency"] == "PLN"
    assert row["producer_code"] == "1"
    assert row["stock"] == "1"
    assert row["active"] == "1"
    assert row["vat"] == "23%"
    assert row["images 1"] == "img.jpg"
    assert row["price"] == "10"

    out_path = tmp_path / "out.csv"
    module.write_store_csv(rows, out_path)
    with open(out_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        saved = list(reader)
        assert reader.fieldnames == module.STORE_FIELDNAMES
        assert saved[0]["name"] == "Pikachu"


def test_merge_by_product_code(tmp_path, monkeypatch):
    module = _reload_csv_utils(monkeypatch, tmp_path)

    app = _make_app(
        [
            {
                "nazwa": "Pikachu",
                "numer": "1",
                "set": "Base",
                "era": "Era1",
                "product_code": "PC1",
                "cena": "10",
                "category": "Karty Pokémon > Era1 > Base",
                "producer": "Pokemon",
                "short_description": "s",
                "description": "d",
                "image1": "img.jpg",
            },
            {
                "nazwa": "Charmander",
                "numer": "2",
                "set": "Base",
                "era": "Era2",
                "product_code": "PC1",
                "cena": "5",
                "category": "Karty Pokémon > Era2 > Base",
                "producer": "Pokemon",
                "short_description": "s",
                "description": "d",
                "image1": "img.jpg",
            },
        ]
    )

    rows = module.export_csv(app)
    assert len(rows) == 1
    assert rows[0]["product_code"] == "PC1"
    assert rows[0]["stock"] == "2"


def test_export_appends_warehouse(tmp_path, monkeypatch):
    module = _reload_csv_utils(monkeypatch, tmp_path)

    inv_path = tmp_path / "inv.csv"
    row_data = {
        "nazwa": "Pikachu",
        "numer": "1",
        "set": "Base",
        "era": "Era1",
        "product_code": 1,
        "cena": "10",
        "category": "Karty Pokémon > Era1 > Base",
        "producer": "Pokemon",
        "short_description": "s",
        "description": "d",
        "image1": "img.jpg",
        "warehouse_code": "K1R1P1",
    }
    app = SimpleNamespace(
        output_data=[row_data],
        session_entries=[],
        update_inventory_stats=MagicMock(),
    )

    rows = module.export_csv(app)
    module.append_warehouse_csv(app, path=str(inv_path), exported_rows=rows)

    with open(inv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        saved = list(reader)
        assert reader.fieldnames == module.WAREHOUSE_FIELDNAMES
        row = saved[0]
        assert row["name"] == "Pikachu"
        assert row["number"] == "1"
        assert row["set"] == "Base"
        assert row["warehouse_code"] == "K1R1P1"
        assert row["price"] == "10"
        assert row["image"] == "img.jpg"
        assert row["variant"] == "common"
        assert row.get("sold", "") == ""


def test_session_summary_send_button_handles_errors(tmp_path, monkeypatch):
    module = _reload_csv_utils(monkeypatch, tmp_path)
    monkeypatch.setattr(ui, "csv_utils", module)

    append_calls: list[list[dict[str, str]]] = []

    def fake_append(app, path=module.WAREHOUSE_CSV, exported_rows=None, **kwargs):
        rows = [dict(row) for row in exported_rows or []]
        append_calls.append(rows)

    monkeypatch.setattr(ui.csv_utils, "append_warehouse_csv", fake_append)
    saved_cache: list[list[dict[str, str]]] = []
    monkeypatch.setattr(
        ui.csv_utils,
        "save_store_cache",
        lambda rows: saved_cache.append([dict(row) for row in rows]),
    )

    messages: list[tuple[str, str]] = []
    monkeypatch.setattr(
        ui.messagebox,
        "showinfo",
        lambda title, message: messages.append(("info", message)),
    )
    monkeypatch.setattr(
        ui.messagebox,
        "showwarning",
        lambda title, message: messages.append(("warning", message)),
    )
    monkeypatch.setattr(
        ui.messagebox,
        "showerror",
        lambda title, message: messages.append(("error", message)),
    )

    monkeypatch.setattr(ui.ctk, "CTkFrame", DummyCTkFrame)
    monkeypatch.setattr(ui.ctk, "CTkScrollableFrame", DummyCTkScrollableFrame)

    created_labels: list[DummyCTkLabel] = []

    class RecordingLabel(DummyCTkLabel):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            created_labels.append(self)

    monkeypatch.setattr(ui.ctk, "CTkLabel", RecordingLabel)
    monkeypatch.setattr(ui.ctk, "CTkButton", DummyCTkButton)

    class DummyShoperClient:
        def __init__(self):
            self.calls: list[dict[str, str]] = []

        def add_product(self, payload):
            self.calls.append(payload)
            return {"product_id": len(self.calls)}

    class DummyApp:
        def __init__(self):
            self.session_entries = [
                {
                    "nazwa": "Pikachu",
                    "numer": "1",
                    "set": "Base",
                    "product_code": "PC1",
                    "cena": "10",
                    "category": "Karty Pokémon > Era1 > Base",
                    "producer": "Pokemon",
                    "short_description": "s",
                    "description": "d",
                    "image1": "img1.jpg",
                    "warehouse_code": "K1R1P1",
                },
                {
                    "nazwa": "Eevee",
                    "numer": "2",
                    "set": "Jungle",
                    "product_code": "PC2",
                    "cena": "5",
                    "category": "Karty Pokémon > Era1 > Jungle",
                    "producer": "Pokemon",
                    "short_description": "s",
                    "description": "d",
                    "image1": "img2.jpg",
                    "warehouse_code": "K1R1P2",
                },
            ]
            self.output_data = list(self.session_entries)
            self.cards: list[str] = []
            self.index = 0
            self.store_data: dict[str, dict[str, str]] = {
                "PC1": {
                    "product_code": "PC1",
                    "name": "Pikachu",
                    "category": "Karty Pokémon > Era1 > Base",
                    "producer": "Pokemon",
                    "short_description": "s",
                    "description": "d",
                    "price": "0.10",
                    "currency": "PLN",
                    "vat": "5%",
                    "stock": "3",
                }
            }
            self._cached_products = []
            self._latest_export_rows: list[dict[str, str]] = []
            self._summary_warehouse_written = False
            self.frame = SimpleNamespace(
                winfo_exists=lambda: False,
                pack_forget=lambda *a, **k: None,
                pack=lambda *a, **k: None,
            )
            self.summary_frame = None
            self.root = SimpleNamespace(cget=lambda key: "#000000")
            self.in_scan = True
            self.buttons = {}
            self.shoper_client = DummyShoperClient()
            self.sent_rows: list[dict[str, str]] = []

        def save_current_data(self):
            self.save_called = True

        def back_to_welcome(self):
            self.back_called = True

        def create_button(self, master=None, **kwargs):
            button = DummyCTkButton(master, **kwargs)
            text = kwargs.get("text")
            if text:
                self.buttons[text] = kwargs.get("command")
            return button

        def close_session_summary(self):
            self.closed = True

        def _cache_store_product(self, code, row, persist=False):
            snapshot = dict(row) if isinstance(row, Mapping) else {}
            self.store_data[code] = snapshot
            self._cached_products.append((code, snapshot))
            if persist:
                self._persist_store_cache()
            return snapshot

        def _persist_store_cache(self):
            ui.csv_utils.save_store_cache(self.store_data.values())

        def _send_card_to_shoper(self, card):
            self.sent_rows.append(dict(card))
            response = self.shoper_client.add_product(card)
            if card.get("product_code") == "PC2":
                raise requests.RequestException("awaria")
            return response

    app = DummyApp()

    ui.CardEditorApp.show_session_summary(app)

    assert len(append_calls) == 1
    exported = append_calls[0]
    assert {row["product_code"] for row in exported} == {"PC1", "PC2"}
    assert saved_cache and len(saved_cache[0]) == len(exported)

    data_labels = [lbl for lbl in created_labels if lbl.font == ("Segoe UI", 16)]
    assert len(data_labels) == len(app.session_entries) * 4
    assert {"Pikachu", "Eevee"}.issubset({lbl.text for lbl in data_labels})
    assert data_labels[2].text == "10"

    send_cmd = app.buttons["Wyślij przez API"]
    send_cmd()

    assert len(app.sent_rows) == 2
    assert len(app.shoper_client.calls) == 2
    pikachu_payload = next(row for row in app.sent_rows if row["product_code"] == "PC1")
    assert pikachu_payload["price"] == "10"

    warning_messages = [text for kind, text in messages if kind == "warning"]
    assert warning_messages
    assert "PC1" in warning_messages[0]
    assert "PC2: awaria" in warning_messages[0]
