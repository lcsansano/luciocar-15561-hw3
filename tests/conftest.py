"""Shared fixtures: load the data once per test session."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.load import build_order_lines, build_orders, load_tables  # noqa: E402


@pytest.fixture(scope="session")
def tables():
    """Provide the cleaned tables, loaded once per session.

    Args:
        None.

    Returns:
        dict[str, pandas.DataFrame]: Output of ``load_tables``.
    """
    return load_tables()


@pytest.fixture(scope="session")
def lines(tables):
    """Provide the joined order lines, built once per session.

    Args:
        tables (dict[str, pandas.DataFrame]): ``tables`` fixture.

    Returns:
        pandas.DataFrame: Output of ``build_order_lines``.
    """
    return build_order_lines(tables)


@pytest.fixture(scope="session")
def orders(lines):
    """Provide the one-row-per-order table, built once per session.

    Args:
        lines (pandas.DataFrame): ``lines`` fixture.

    Returns:
        pandas.DataFrame: Output of ``build_orders``.
    """
    return build_orders(lines)
