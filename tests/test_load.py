"""The shared loader: row counts, joins, revenue, cleaning rules."""

import pandas as pd
import pytest

from src.load import DATA_DIR, DATA_END, DATA_START

TOTAL_REVENUE = 1_265_793.04


def test_row_counts(lines, orders):
    """Check line, order and customer counts.

    Args:
        lines (pandas.DataFrame): ``lines`` fixture.
        orders (pandas.DataFrame): ``orders`` fixture.

    Returns:
        None.
    """
    assert len(lines) == 2155
    assert len(orders) == 830
    assert lines["CustomerID"].nunique() == 89


def test_joins_complete(lines):
    """Check that no joined column is left empty.

    Args:
        lines (pandas.DataFrame): ``lines`` fixture.

    Returns:
        None.
    """
    for col in ["CustomerName", "CustomerCountry", "ProductName",
                "CategoryName", "EmployeeName", "OrderDate"]:
        assert lines[col].notna().all(), col


def test_revenue_total(lines, orders):
    """Check total revenue in lines and orders.

    Args:
        lines (pandas.DataFrame): ``lines`` fixture.
        orders (pandas.DataFrame): ``orders`` fixture.

    Returns:
        None.
    """
    assert lines["Revenue"].sum() == pytest.approx(TOTAL_REVENUE, abs=0.01)
    assert orders["Revenue"].sum() == pytest.approx(TOTAL_REVENUE, abs=0.01)


def test_revenue_matches_raw_excel(lines):
    """Check revenue against a recomputation from the raw workbook.

    Args:
        lines (pandas.DataFrame): ``lines`` fixture.

    Returns:
        None.
    """
    raw = pd.read_excel(DATA_DIR / "Northwind Database.xlsx",
                        sheet_name="Orders Details")
    raw_rev = (raw["UnitPrice"] * raw["Quantity"]
               * (1 - raw["Discount"].round(2))).sum()
    assert lines["Revenue"].sum() == pytest.approx(raw_rev, abs=0.01)


def test_revenue_uses_charged_price_not_list_price(lines):
    """Check that revenue uses UnitPrice, not ListPrice.

    Args:
        lines (pandas.DataFrame): ``lines`` fixture.

    Returns:
        None.
    """
    row = lines.iloc[0]
    expected = row["UnitPrice"] * row["Quantity"] * (1 - row["Discount"])
    assert row["Revenue"] == pytest.approx(expected)


def test_discounts_rounded(lines):
    """Check that discounts take only the known rounded levels.

    Args:
        lines (pandas.DataFrame): ``lines`` fixture.

    Returns:
        None.
    """
    assert set(lines["Discount"].unique()) <= {
        0.0, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.1, 0.15, 0.2, 0.25}


def test_product_exercise_columns_dropped(tables):
    """Check that the Product exercise columns are removed.

    Args:
        tables (dict[str, pandas.DataFrame]): ``tables`` fixture.

    Returns:
        None.
    """
    for col in ["Cheap", "NewPrice", "IsCheap"]:
        assert col not in tables["products"].columns


def test_date_range(lines):
    """Check the first and last order date.

    Args:
        lines (pandas.DataFrame): ``lines`` fixture.

    Returns:
        None.
    """
    assert lines["OrderDate"].min() == DATA_START
    assert lines["OrderDate"].max() == DATA_END


def test_unshipped_orders(orders):
    """Check the number of unshipped orders.

    Args:
        orders (pandas.DataFrame): ``orders`` fixture.

    Returns:
        None.
    """
    assert (~orders["IsShipped"]).sum() == 21


def test_postal_codes_keep_leading_zeros(tables):
    """Check that postal codes keep their leading zeros.

    Args:
        tables (dict[str, pandas.DataFrame]): ``tables`` fixture.

    Returns:
        None.
    """
    assert tables["customers"]["PostalCode"].dropna().str.startswith("0").sum() == 18
