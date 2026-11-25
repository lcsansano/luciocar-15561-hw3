"""Load the Northwind CSVs and build the joined order-line table.

Every analysis script should get its data from here, so the cleaning
rules
from notes/data_check.md are applied the same way everywhere.

Quick check (from the project root):
    .venv/bin/python -m src.load
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

# First and last order date in the data. 1996 and 1998 are partial years.
DATA_START = pd.Timestamp("1996-07-04")
DATA_END = pd.Timestamp("1998-05-06")

# Expected row counts, used as a guard against a changed or broken export.
EXPECTED_ROWS = {
    "orders": 830,
    "order_details": 2155,
    "customers": 91,
    "products": 77,
    "categories": 8,
    "employees": 9,
}

# Known total net revenue of the Northwind dataset (USD).
EXPECTED_REVENUE = 1_265_793.04

# Text columns that look numeric but must keep leading zeros.
TEXT_COLUMNS = {
    "customers": ["PostalCode", "Phone", "Fax"],
    "orders": ["ShipPostalCode"],
    "employees": ["PostalCode", "HomePhone"],
}

DATE_COLUMNS = {
    "orders": ["OrderDate", "RequiredDate", "ShippedDate"],
    "employees": ["BirthDate", "HireDate"],
}

# Leftover exercise columns in the Product sheet; not business data.
PRODUCT_EXERCISE_COLUMNS = ["Cheap", "NewPrice", "Cheap.1", "IsCheap",
                            "NewPrice.1"]


def load_tables(data_dir=DATA_DIR):
    """Read the six CSVs and apply the shared cleaning rules.

    Rounds ``Discount`` to two decimals (removes float noise) and drops
    the Product exercise columns (``Cheap``, ``NewPrice``, ``IsCheap``).

    Args:
        data_dir (pathlib.Path): Folder holding the exported CSVs.

    Returns:
        dict[str, pandas.DataFrame]: Tables keyed by ``orders``,
            ``order_details``, ``customers``, ``products``,
            ``categories`` and ``employees``.

    Raises:
        ValueError: If a CSV's row count differs from ``EXPECTED_ROWS``.
    """
    names = ["orders", "order_details", "customers", "products",
             "categories", "employees"]
    tables = {}
    for name in names:
        df = pd.read_csv(
            data_dir / f"{name}.csv",
            dtype={col: str for col in TEXT_COLUMNS.get(name, [])},
            parse_dates=DATE_COLUMNS.get(name, []),
        )
        expected = EXPECTED_ROWS[name]
        if len(df) != expected:
            raise ValueError(f"{name}.csv has {len(df)} rows, expected {expected}")
        tables[name] = df

    details = tables["order_details"]
    # Stored as floats with noise (0.0500000007); real levels are 0-25%.
    details["Discount"] = details["Discount"].round(2)

    tables["products"] = tables["products"].drop(
        columns=PRODUCT_EXERCISE_COLUMNS, errors="ignore")
    return tables


def build_order_lines(tables=None):
    """Join order lines with orders, customers, products and staff.

    Clashing columns are renamed (``CustomerCountry``,
    ``EmployeeCountry``; ``Product.Price`` becomes ``ListPrice``). Adds
    ``GrossRevenue``, ``Revenue`` (UnitPrice x Quantity x
    (1 - Discount)), ``DiscountAmount``, order year/month/quarter and
    ``IsShipped``.

    Args:
        tables (dict[str, pandas.DataFrame] | None): Output of
            ``load_tables``; loaded from the CSVs when None.

    Returns:
        pandas.DataFrame: One row per order line (2,155 rows).

    Raises:
        ValueError: If ``check_order_lines`` finds a broken join or a
            wrong revenue total.
    """
    if tables is None:
        tables = load_tables()

    orders = tables["orders"][[
        "OrderID", "CustomerID", "EmployeeID", "OrderDate", "RequiredDate",
        "ShippedDate", "ShipVia", "Freight", "ShipCountry",
    ]]
    customers = tables["customers"][[
        "CustomerID", "CompanyName", "City", "Country",
    ]].rename(columns={
        "CompanyName": "CustomerName",
        "City": "CustomerCity",
        "Country": "CustomerCountry",
    })
    products = tables["products"][[
        "ProductID", "ProductName", "CategoryID", "SupplierID", "Price",
        "Discontinued",
    ]].rename(columns={"Price": "ListPrice"})
    categories = tables["categories"][["CategoryID", "CategoryName"]]
    employees = tables["employees"][[
        "EmployeeID", "FirstName", "LastName", "Title", "Country", "HireDate",
    ]].rename(columns={
        "Title": "EmployeeTitle",
        "Country": "EmployeeCountry",
        "HireDate": "EmployeeHireDate",
    })
    employees = employees.assign(
        EmployeeName=employees["FirstName"] + " " + employees["LastName"]
    ).drop(columns=["FirstName", "LastName"])

    lines = (
        tables["order_details"]
        .merge(orders, on="OrderID", how="left", validate="many_to_one")
        .merge(customers, on="CustomerID", how="left", validate="many_to_one")
        .merge(products, on="ProductID", how="left", validate="many_to_one")
        .merge(categories, on="CategoryID", how="left",
               validate="many_to_one")
        .merge(employees, on="EmployeeID", how="left",
               validate="many_to_one")
    )

    # Revenue uses the price actually charged (UnitPrice), never ListPrice.
    lines["GrossRevenue"] = lines["UnitPrice"] * lines["Quantity"]
    lines["Revenue"] = lines["GrossRevenue"] * (1 - lines["Discount"])
    lines["DiscountAmount"] = lines["GrossRevenue"] - lines["Revenue"]

    lines["OrderYear"] = lines["OrderDate"].dt.year
    lines["OrderMonth"] = lines["OrderDate"].dt.to_period("M")
    lines["OrderQuarter"] = lines["OrderDate"].dt.to_period("Q")
    lines["IsShipped"] = lines["ShippedDate"].notna()

    check_order_lines(lines, tables)
    return lines


def build_orders(lines=None):
    """Aggregate order lines to one row per order.

    Args:
        lines (pandas.DataFrame | None): Output of
            ``build_order_lines``; built from the CSVs when None.

    Returns:
        pandas.DataFrame: One row per order (830 rows) with customer,
            employee and date columns plus ``Lines``, ``Units``,
            ``GrossRevenue``, ``Revenue`` and ``DiscountAmount``.
    """
    if lines is None:
        lines = build_order_lines()
    order_cols = [
        "OrderID", "CustomerID", "CustomerName", "CustomerCountry",
        "EmployeeID", "EmployeeName", "OrderDate", "RequiredDate",
        "ShippedDate", "ShipVia", "Freight", "OrderYear", "OrderMonth",
        "OrderQuarter", "IsShipped",
    ]
    totals = lines.groupby("OrderID").agg(
        Lines=("ProductID", "size"),
        Units=("Quantity", "sum"),
        GrossRevenue=("GrossRevenue", "sum"),
        Revenue=("Revenue", "sum"),
        DiscountAmount=("DiscountAmount", "sum"),
    )
    orders = (lines[order_cols].drop_duplicates("OrderID")
              .set_index("OrderID").join(totals).reset_index())
    return orders


def check_order_lines(lines, tables):
    """Verify the joined order lines against known totals.

    Args:
        lines (pandas.DataFrame): Output of ``build_order_lines``.
        tables (dict[str, pandas.DataFrame]): Source tables of the
            lines.

    Returns:
        None.

    Raises:
        ValueError: If the join changed the row count, a join left
            required columns empty, or total revenue differs from
            ``EXPECTED_REVENUE`` by more than one cent.
    """
    n_details = len(tables["order_details"])
    if len(lines) != n_details:
        raise ValueError(f"join changed row count: {len(lines)} != {n_details}")

    required = ["OrderDate", "CustomerName", "CustomerCountry", "ProductName",
                "CategoryName", "EmployeeName"]
    missing = lines[required].isna().sum()
    if missing.any():
        raise ValueError(f"unmatched joins:\n{missing[missing > 0]}")

    total = round(lines["Revenue"].sum(), 2)
    if abs(total - EXPECTED_REVENUE) > 0.01:
        raise ValueError(f"total revenue {total:,.2f} != {EXPECTED_REVENUE:,.2f}")


def main():
    """Build both tables and print a short summary of them.

    Args:
        None.

    Returns:
        None. Prints row counts, date range, revenue and columns.
    """
    tables = load_tables()
    lines = build_order_lines(tables)
    orders = build_orders(lines)
    print(f"order lines: {lines.shape[0]} rows x {lines.shape[1]} cols")
    print(f"orders:      {orders.shape[0]} rows x {orders.shape[1]} cols")
    print(f"date range:  {lines['OrderDate'].min():%Y-%m-%d} to "
          f"{lines['OrderDate'].max():%Y-%m-%d}")
    print(f"customers with orders: {lines['CustomerID'].nunique()}")
    print(f"total revenue: ${lines['Revenue'].sum():,.2f} "
          f"(gross ${lines['GrossRevenue'].sum():,.2f}, "
          f"discount ${lines['DiscountAmount'].sum():,.2f})")
    levels = sorted(float(v) for v in lines["Discount"].unique())
    print(f"discount levels: {levels}")
    print("columns:", ", ".join(lines.columns))


if __name__ == "__main__":
    main()
