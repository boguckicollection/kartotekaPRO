import pytest

import kartoteka.csv_utils as csv_utils


def test_decrement_store_stock_is_no_longer_supported():
    with pytest.raises(RuntimeError):
        csv_utils.decrement_store_stock({"PKM-SET-1C": 1})
