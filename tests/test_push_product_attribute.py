import importlib
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

sys.modules.setdefault("customtkinter", MagicMock())
sys.path.append(str(Path(__file__).resolve().parents[1]))
import kartoteka.ui as ui
importlib.reload(ui)

class DummyVar:
    def __init__(self, value):
        self.value = value
    def get(self):
        return self.value

class DummyText:
    def delete(self, *a, **k):
        pass
    def insert(self, *a, **k):
        pass
def test_push_product_posts_multiple_attributes(monkeypatch):
    calls = []

    def _add_attribute(product_id, attribute_id, values):
        calls.append((product_id, attribute_id, values))

    fake_client = SimpleNamespace(
        add_product=lambda data: {"product_id": 3},
        get_attributes=lambda: {},
        add_product_attribute=MagicMock(side_effect=_add_attribute),
    )

    app = ui.CardEditorApp.__new__(ui.CardEditorApp)
    app.output_data = [
        {
            "foo": "bar",
            "card_type": "R",
            "attributes": {
                10: {102: ["Foil", "Promo"]},
                11: {103: "Signed by artist"},
            },
        }
    ]
    app.index = 0
    app.save_current_data = lambda: None
    app._build_shoper_payload = lambda card: {"name": "x"}
    app.shoper_client = fake_client
    app.entries = {}
    app.attribute_values = {}
    app._attribute_controls = {}
    app._attribute_cache = {
        "attributes": {
            101: {
                "values": [(3, "Reverse"), (4, "Holo")],
                "values_by_id": {3: "Reverse", 4: "Holo"},
                "values_by_name": {"reverse": 3, "holo": 4},
                "widget_type": "select",
            },
            102: {
                "values": [(11, "Foil"), (12, "Promo")],
                "values_by_id": {11: "Foil", 12: "Promo"},
                "values_by_name": {"foil": 11, "promo": 12},
                "widget_type": "multiselect",
            },
            103: {
                "values": [],
                "values_by_id": {},
                "values_by_name": {},
                "widget_type": "text",
            },
        },
        "by_name": {"typ": 101, "rarity": 102, "uwagi": 103},
        "groups": {},
    }

    def _refresh_cache(force=False):
        return app._attribute_cache

    app._refresh_attribute_cache = _refresh_cache.__get__(app, ui.CardEditorApp)
    app._normalize_attribute_selection = (
        ui.CardEditorApp._normalize_attribute_selection.__get__(app, ui.CardEditorApp)
    )
    app._normalize_attribute_payload = (
        ui.CardEditorApp._normalize_attribute_payload.__get__(app, ui.CardEditorApp)
    )
    app._resolve_attribute_id = (
        ui.CardEditorApp._resolve_attribute_id.__get__(app, ui.CardEditorApp)
    )

    monkeypatch.setattr(ui.messagebox, "showerror", lambda *a, **k: None)
    monkeypatch.setattr(ui.messagebox, "showinfo", lambda *a, **k: None)
    monkeypatch.setattr(ui.tk, "Text", DummyText, raising=False)
    monkeypatch.setattr(ui.tk, "END", "end", raising=False)

    widget = DummyText()
    ui.CardEditorApp.push_product(app, widget)

    assert calls == [
        (3, 102, [11, 12]),
        (3, 103, ["Signed by artist"]),
        (3, 101, [3]),
    ]
