from collections.abc import Callable
from pathlib import Path

import openpyxl
import pytest


@pytest.fixture
def make_xlsx(tmp_path: Path) -> Callable:
    """openpyxl の Workbook を builder で構築して保存し、パスを返す。"""

    def _make(builder: Callable[[openpyxl.Workbook], None], name: str = "test.xlsx") -> Path:
        wb = openpyxl.Workbook()
        builder(wb)
        path = tmp_path / name
        wb.save(path)
        return path

    return _make
