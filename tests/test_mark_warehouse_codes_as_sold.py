import csv
import sys
import pytest

import kartoteka.csv_utils as csv_utils


def test_mark_warehouse_codes_as_sold_is_no_longer_supported():
    with pytest.raises(RuntimeError):
        csv_utils.mark_warehouse_codes_as_sold(["K1"])
