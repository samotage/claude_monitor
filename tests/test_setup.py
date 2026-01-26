"""Verify project setup is correct."""

import sys
from pathlib import Path


def test_python_version():
    """Verify Python version is 3.10+."""
    assert sys.version_info >= (3, 10), "Python 3.10+ required"


def test_src_directory_exists():
    """Verify src/ directory structure exists."""
    project_root = Path(__file__).parent.parent
    src = project_root / "src"

    assert src.exists(), "src/ directory should exist"
    assert (src / "__init__.py").exists(), "src/__init__.py should exist"
    assert (src / "models").is_dir(), "src/models/ should exist"
    assert (src / "services").is_dir(), "src/services/ should exist"
    assert (src / "backends").is_dir(), "src/backends/ should exist"
    assert (src / "routes").is_dir(), "src/routes/ should exist"


def test_src_importable():
    """Verify src package is importable."""
    import src

    assert src.__version__ == "2.0.0"


def test_pydantic_available():
    """Verify pydantic is installed."""
    import pydantic

    assert pydantic.VERSION.startswith("2.")
