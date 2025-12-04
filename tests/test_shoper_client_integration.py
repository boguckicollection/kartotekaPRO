import os
import sys
import uuid
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from shoper_client import ShoperClient  # noqa: E402


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("SHOPER_API_URL") or not os.getenv("SHOPER_API_TOKEN"),
    reason="Shoper sandbox credentials not configured",
)
def test_add_product_succeeds_against_sandbox():
    client = ShoperClient(
        base_url=os.getenv("SHOPER_API_URL"),
        token=os.getenv("SHOPER_API_TOKEN"),
        client_id=os.getenv("SHOPER_CLIENT_ID"),
    )

    product_code = f"TEST-{uuid.uuid4().hex[:10]}"
    language_id = int(os.getenv("SHOPER_LANGUAGE_ID", "1"))
    language_code = os.getenv("SHOPER_LANGUAGE_CODE", "pl_PL")

    payload = {
        "product_code": product_code,
        "active": 0,
        "price": 0.0,
        "translations": [
            {
                "language_id": language_id,
                "language_code": language_code,
                "name": product_code,
            }
        ],
        "stock": {"stock": 0},
    }

    response = client.add_product(payload)

    assert isinstance(response, dict)
    assert response == {} or response.get("product_id") or response.get("product")
