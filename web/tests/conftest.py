import importlib.util
from pathlib import Path

import pytest

# Pakai contoh workbook yang sama dengan tes bot (tests/conftest.py di root project).
_spec = importlib.util.spec_from_file_location(
    "bot_conftest", Path(__file__).resolve().parents[2] / "tests" / "conftest.py")
_bot_conftest = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_bot_conftest)


@pytest.fixture
def workbook_path(tmp_path):
    path = tmp_path / "handover.xlsx"
    _bot_conftest.make_sample_workbook(path)
    return path
