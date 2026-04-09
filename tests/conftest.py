from __future__ import annotations

import os
import shutil
import sys
from collections.abc import Generator
from functools import lru_cache
from pathlib import Path
from uuid import uuid4

import pytest

_LOCAL_TMP_ROOT = Path(__file__).resolve().parent / "_tmp"
_LOCAL_TMP_ROOT.mkdir(exist_ok=True)

_PYTHON_ROOT = Path(sys.executable).resolve().parent
_TCL_DIR = _PYTHON_ROOT / "tcl"
_TCL_LIBRARY = _TCL_DIR / "tcl8.6"
_TK_LIBRARY = _TCL_DIR / "tk8.6"

if _TCL_LIBRARY.exists():
    os.environ.setdefault("TCL_LIBRARY", str(_TCL_LIBRARY))
if _TK_LIBRARY.exists():
    os.environ.setdefault("TK_LIBRARY", str(_TK_LIBRARY))

for stale_dir in _LOCAL_TMP_ROOT.glob("pytest-*"):
    if stale_dir.is_dir():
        shutil.rmtree(stale_dir, ignore_errors=True)


def _detect_tk_skip_reason() -> str | None:
    required = {
        "init.tcl": _TCL_LIBRARY / "init.tcl",
        "tk.tcl": _TK_LIBRARY / "tk.tcl",
        "menu.tcl": _TK_LIBRARY / "menu.tcl",
    }
    missing = [name for name, path in required.items() if not path.exists()]
    if missing:
        return f"Tk GUI tests are skipped: incomplete Tcl/Tk runtime (missing {', '.join(missing)})"
    try:
        import tkinter as tk
    except Exception as exc:
        return f"Tkinter is unavailable in this environment: {exc}"
    try:
        root = tk.Tk()
        root.withdraw()
        root.destroy()
    except Exception as exc:
        return f"Tk GUI tests are skipped: {exc}"
    return None


_TK_SKIP_REASON = _detect_tk_skip_reason()


@lru_cache(maxsize=256)
def _file_uses_tk(file_path: str) -> bool:
    path = Path(file_path)
    if not path.exists() or path.suffix != ".py":
        return False
    try:
        content = path.read_text(encoding="utf-8")
    except Exception:
        return False
    return ("import tkinter" in content) or ("from tkinter import" in content)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    if _TK_SKIP_REASON is None:
        return
    skip_tk = pytest.mark.skip(reason=_TK_SKIP_REASON)
    for item in items:
        if _file_uses_tk(str(item.fspath)):
            item.add_marker(skip_tk)


@pytest.fixture(autouse=True)
def _skip_unusable_tk_runtime(request: pytest.FixtureRequest) -> None:
    if not _file_uses_tk(str(request.node.fspath)):
        return
    try:
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        root.destroy()
    except Exception as exc:
        pytest.skip(f"Tk GUI runtime is unavailable for this test: {exc}")


@pytest.fixture
def tmp_path() -> Generator[Path, None, None]:
    path = _LOCAL_TMP_ROOT / f"pytest-{uuid4().hex}"
    path.mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
