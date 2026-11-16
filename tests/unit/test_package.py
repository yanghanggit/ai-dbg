"""Package structure / import smoke tests."""

from pathlib import Path

import ai_dbg


def test_package_structure() -> None:
    """The src-layout package directory exists."""
    src_path = Path(__file__).parent.parent.parent / "src"
    assert (src_path / "ai_dbg" / "__init__.py").exists()


def test_import_main_package() -> None:
    """The installed package imports and exposes its version."""
    assert ai_dbg.__version__ == "0.1.0"
