import importlib
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

sys.modules.setdefault("customtkinter", MagicMock())
sys.path.append(str(Path(__file__).resolve().parents[1]))
import kartoteka.ui as ui
importlib.reload(ui)


def test_send_card_to_shoper_updates_existing_product():
    update_mock = MagicMock(return_value={"product_id": "789"})
    add_mock = MagicMock()

    client = SimpleNamespace(
        update_product=update_mock,
        add_product=add_mock,
        add_product_attribute=MagicMock(),
    )

    app = ui.CardEditorApp.__new__(ui.CardEditorApp)
    app.shoper_client = client
    app.store_data = {"ABC": {"product_code": "ABC", "product_id": "789"}}
    app.product_code_map = {}
    app._build_shoper_payload = lambda card: {"product_code": "ABC", "name": "Test"}
    app._refresh_attribute_cache = lambda *a, **k: {"attributes": {}, "by_name": {}}
    app._resolve_attribute_id = lambda *a, **k: None
    app._normalize_attribute_payload = lambda *a, **k: []
    app._update_local_product_caches = lambda *a, **k: None

    card = {"product_code": "ABC", "attributes": {}}

    result = ui.CardEditorApp._send_card_to_shoper(app, card)

    update_mock.assert_called_once_with(
        "789", {"product_code": "ABC", "name": "Test"}
    )
    add_mock.assert_not_called()
    assert result.get("product_id") == "789"


class _DummyLogger:
    def __init__(self):
        self.messages: list[str] = []

    def isEnabledFor(self, level):  # pragma: no cover - signature mirror
        return True

    def debug(self, msg, *args, **kwargs):
        if args:
            msg = msg % args
        elif kwargs:
            msg = msg % kwargs
        self.messages.append(str(msg))

    def warning(self, msg, *args, **kwargs):  # pragma: no cover - signature mirror
        if args:
            msg = msg % args
        elif kwargs:
            msg = msg % kwargs
        self.messages.append(str(msg))


def test_send_card_to_shoper_logs_payload_before_request(monkeypatch):
    dummy_logger = _DummyLogger()
    monkeypatch.setattr(ui, "logger", dummy_logger)

    add_called_with = {}

    def add_product(payload):
        add_called_with.update(payload)
        assert dummy_logger.messages, "Payload should be logged before API call"
        assert "\"price\": 12.34" in dummy_logger.messages[-1]
        return {"product_id": "123"}

    app = ui.CardEditorApp.__new__(ui.CardEditorApp)
    app.shoper_client = SimpleNamespace(
        add_product=add_product,
        update_product=MagicMock(),
        add_product_attribute=MagicMock(),
    )
    app.store_data = {}
    app.product_code_map = {}
    app._build_shoper_payload = lambda card: {
        "product_code": "XYZ",
        "name": "Test product",
        "price": 12.34,
    }
    app._refresh_attribute_cache = lambda *a, **k: {"attributes": {}, "by_name": {}}
    app._resolve_attribute_id = lambda *a, **k: None
    app._normalize_attribute_payload = lambda *a, **k: []
    app._update_local_product_caches = lambda *a, **k: None

    card = {"product_code": "XYZ", "attributes": {}}

    result = ui.CardEditorApp._send_card_to_shoper(app, card)

    assert add_called_with["price"] == 12.34
    assert result.get("product_id") == "123"
