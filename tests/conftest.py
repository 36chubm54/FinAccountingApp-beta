from __future__ import annotations

import shutil
from collections.abc import Generator
from pathlib import Path
from uuid import uuid4

import pytest

_LOCAL_TMP_ROOT = Path(__file__).resolve().parent / "_tmp"
_LOCAL_TMP_ROOT.mkdir(exist_ok=True)

for stale_dir in _LOCAL_TMP_ROOT.glob("pytest-*"):
    if stale_dir.is_dir():
        shutil.rmtree(stale_dir, ignore_errors=True)


@pytest.fixture
def tmp_path() -> Generator[Path, None, None]:
    path = _LOCAL_TMP_ROOT / f"pytest-{uuid4().hex}"
    path.mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
