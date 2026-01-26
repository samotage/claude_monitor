"""Pytest configuration and shared fixtures for Claude Headspace tests."""

import shutil
from pathlib import Path

import pytest


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_data():
    """Clean up the data directory before and after tests.

    This ensures test isolation by removing any persisted state
    from previous test runs.
    """
    data_dir = Path(__file__).parent.parent / "data"

    # Clean up before tests
    if data_dir.exists():
        for item in data_dir.iterdir():
            if item.is_file() and item.suffix in (".json", ".yaml"):
                item.unlink()
            elif item.is_dir() and item.name != "projects":
                shutil.rmtree(item)

    yield

    # Clean up after tests (optional, helps keep repo clean)
    if data_dir.exists():
        for item in data_dir.iterdir():
            if item.is_file() and item.suffix in (".json", ".yaml"):
                item.unlink()
