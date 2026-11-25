"""Profile the Northwind workbook, run data-quality checks, export CSVs.

Run from the project root:
    .venv/bin/python scripts/01_data_check.py
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
XLSX = ROOT / "data" / "Northwind Database.xlsx"
CSV_DIR = ROOT / "data"

CSV_NAMES = {
    "Categories": "categories.csv",
    "Customers": "customers.csv",
    "Employees": "employees.csv",
    "Orders Details": "order_details.csv",
    "Orders": "orders.csv",
    "Shippers": "shippers.csv",
    "Product": "products.csv",
    "Suppliers": "suppliers.csv",
}

PRIMARY_KEYS = {
    "Categories": ["CategoryID"],
    "Customers": ["CustomerID"],
    "Employees": ["EmployeeID"],
    "Orders Details": ["OrderID", "ProductID"],
    "Orders": ["OrderID"],
    "Shippers": ["ShipperID"],
    "Product": ["ProductID"],
    "Suppliers": ["SupplierID"],
}

# (child sheet, child column, parent sheet, parent column)
FOREIGN_KEYS = [
    ("Orders Details", "OrderID", "Orders", "OrderID"),
    ("Orders Details", "ProductID", "Product", "ProductID"),
    ("Orders", "CustomerID", "Customers", "CustomerID"),
    ("Orders", "EmployeeID", "Employees", "EmployeeID"),
    ("Orders", "ShipVia", "Shippers", "ShipperID"),
    ("Product", "SupplierID", "Suppliers", "SupplierID"),
    ("Product", "CategoryID", "Categories", "CategoryID"),
    ("Employees", "ReportsTo", "Employees", "EmployeeID"),
]


def load_sheets(path):
    """Read every sheet of the workbook.

    Args:
        path (pathlib.Path): Workbook to read.

    Returns:
        dict[str, pandas.DataFrame]: One DataFrame per sheet, keyed by
            sheet name, in workbook order.
    """
    return pd.read_excel(path, sheet_name=None)


def section(title):
    """Print a section header.

    Args:
        title (str): Header text.

    Returns:
        None.
    """
    print(f"\n=== {title} ===")


def profile_sheets(sheets):
    """Print size, date range and missing values for each sheet.

    Args:
        sheets (dict[str, pandas.DataFrame]): Sheets keyed by name.

    Returns:
        None.
    """
    section("Sheet overview")
    for name, df in sheets.items():
        dates = df.select_dtypes(include="datetime")
        ranges = "; ".join(
            f"{c}: {dates[c].min():%Y-%m-%d} to {dates[c].max():%Y-%m-%d}"
            for c in dates
        )
        print(f"{name}: {len(df)} rows x {df.shape[1]} cols"
              f" | dates: {ranges or 'none'}")
    section("Missing values (count / % of rows)")
    for name, df in sheets.items():
        na = df.isna().sum()
        na = na[na > 0]
        for col, n in na.items():
            print(f"{name}.{col}: {n} ({n / len(df):.0%})")


def check_keys(sheets):
    """Print primary-key duplicates and foreign-key orphans.

    Args:
        sheets (dict[str, pandas.DataFrame]): Sheets keyed by name.

    Returns:
        None.
    """
    section("Primary keys (duplicates) and exact duplicate rows")
    for name, cols in PRIMARY_KEYS.items():
        df = sheets[name]
        print(f"{name} {cols}: {df.duplicated(cols).sum()} duplicate keys,"
              f" {df.duplicated().sum()} duplicate rows")
    section("Foreign keys (child values missing from parent)")
    for child, ccol, parent, pcol in FOREIGN_KEYS:
        values = sheets[child][ccol].dropna()
        orphans = sorted(set(values) - set(sheets[parent][pcol]))
        print(f"{child}.{ccol} -> {parent}.{pcol}: {len(orphans)} orphans"
              f" {orphans[:10]}")
    section("Parents never referenced")
    orders, details = sheets["Orders"], sheets["Orders Details"]
    no_orders = set(sheets["Customers"]["CustomerID"]) - set(
        orders["CustomerID"])
    print(f"Customers with no orders: {sorted(no_orders)}")
    unsold = set(sheets["Product"]["ProductID"]) - set(details["ProductID"])
    print(f"Products never sold: {sorted(unsold)}")
    no_lines = set(orders["OrderID"]) - set(details["OrderID"])
    print(f"Orders without order lines: {sorted(no_lines)}")


def check_orders(sheets):
    """Print plausibility checks on orders and order lines.

    Args:
        sheets (dict[str, pandas.DataFrame]): Sheets keyed by name.

    Returns:
        None.
    """
    orders, details = sheets["Orders"], sheets["Orders Details"]
    section("Orders: timing")
    months = orders["OrderDate"].dt.to_period("M").value_counts().sort_index()
    print("Orders per month:", months.to_dict())
    shipped = orders.dropna(subset=["ShippedDate"])
    days = (shipped["ShippedDate"] - shipped["OrderDate"]).dt.days
    print(f"Unshipped orders: {orders['ShippedDate'].isna().sum()},"
          f" latest unshipped order date:"
          f" {orders.loc[orders['ShippedDate'].isna(), 'OrderDate'].min():%Y-%m-%d}"
          f" .. {orders.loc[orders['ShippedDate'].isna(), 'OrderDate'].max():%Y-%m-%d}")
    print(f"Days order->ship: min {days.min()}, median {days.median()},"
          f" max {days.max()}, negative {int((days < 0).sum())}")
    late = (shipped["ShippedDate"] > shipped["RequiredDate"]).sum()
    print(f"Shipped after RequiredDate: {late} of {len(shipped)}")
    req = (orders["RequiredDate"] - orders["OrderDate"]).dt.days
    print("RequiredDate - OrderDate (days):", req.value_counts().to_dict())
    section("Orders: freight")
    print(orders["Freight"].describe().round(2).to_dict())
    print(f"Freight = 0: {(orders['Freight'] == 0).sum()}")
    section("Order lines: values")
    print(details[["UnitPrice", "Quantity", "Discount"]]
          .describe().round(3).to_string())
    print("Discount levels:", details["Discount"].value_counts()
          .sort_index().to_dict())
    rev = details["UnitPrice"] * details["Quantity"] * (1 - details["Discount"])
    print(f"Total net revenue: {rev.sum():,.2f}"
          f" | gross: {(details['UnitPrice'] * details['Quantity']).sum():,.2f}")
    section("Order lines: price vs product list price")
    merged = details.merge(sheets["Product"][["ProductID", "Price"]],
                           on="ProductID")
    ratio = (merged["UnitPrice"] / merged["Price"]).round(3)
    print("UnitPrice / Product.Price:", ratio.value_counts().head(8).to_dict())
    year = merged.merge(orders[["OrderID", "OrderDate"]], on="OrderID")
    year["match"] = year["UnitPrice"].round(2) == year["Price"].round(2)
    print("Share of lines at list price, by order year:",
          year.groupby(year["OrderDate"].dt.year)["match"].mean()
          .round(3).to_dict())
    section("Orders: ship-to vs customer country")
    cust = orders.merge(sheets["Customers"][["CustomerID", "Country"]],
                        on="CustomerID")
    diff = cust[cust["ShipCountry"] != cust["Country"]]
    print(f"Orders shipped to a different country than the customer's:"
          f" {len(diff)}")


def check_products(sheets):
    """Print checks on the extra and stock columns of the Product sheet.

    Args:
        sheets (dict[str, pandas.DataFrame]): Sheets keyed by name.

    Returns:
        None.
    """
    p = sheets["Product"]
    section("Product: extra columns")
    print("Columns:", list(p.columns))
    print("Cheap values:", p["Cheap"].value_counts().to_dict())
    print("Cheap.1 values:", p["Cheap.1"].value_counts().to_dict())
    print("IsCheap values:", p["IsCheap"].value_counts().to_dict())
    print("Cheap=='t' equals Cheap.1==1:",
          ((p["Cheap"] == "t") == (p["Cheap.1"] == 1)).all())
    print("Cheap=='t' equals IsCheap:", ((p["Cheap"] == "t") == p["IsCheap"]).all())
    for col in ["Cheap", "IsCheap"]:
        flag = p[col].isin(["t", True])
        print(f"{col} price range when true: {p.loc[flag, 'Price'].min()}-"
              f"{p.loc[flag, 'Price'].max()}; when false:"
              f" {p.loc[~flag, 'Price'].min()}-{p.loc[~flag, 'Price'].max()}")
    print("NewPrice / Price:", (p["NewPrice"] / p["Price"]).round(3)
          .value_counts().head(5).to_dict())
    np1 = p.dropna(subset=["NewPrice.1"])
    print(f"NewPrice.1 filled for {len(np1)} rows; NewPrice.1 / Price:",
          (np1["NewPrice.1"] / np1["Price"]).round(3).value_counts()
          .head(5).to_dict())
    print("NewPrice.1 filled rows are IsCheap:",
          np1["IsCheap"].value_counts().to_dict())
    print("Unnamed: 14 all empty:", p["Unnamed: 14"].isna().all())
    print(f"Discontinued: {p['Discontinued'].sum()},"
          f" stock 0: {(p['UnitsInStock'] == 0).sum()},"
          f" at/below reorder level (not discontinued):"
          f" {((p['UnitsInStock'] <= p['ReorderLevel']) & ~p['Discontinued'] & (p['ReorderLevel'] > 0)).sum()}")
    print("Product rows sorted by ProductID:",
          p["ProductID"].is_monotonic_increasing)


def check_text(sheets):
    """Print text oddities: stray spaces, empty and file-name columns.

    Args:
        sheets (dict[str, pandas.DataFrame]): Sheets keyed by name.

    Returns:
        None.
    """
    section("Text oddities")
    for name, df in sheets.items():
        for col in df.select_dtypes(include=["object", "string"]):
            s = df[col].dropna().astype(str)
            n = (s != s.str.strip()).sum()
            if n:
                print(f"{name}.{col}: {n} values with leading/trailing spaces")
    print("Categories.Picture all empty:",
          sheets["Categories"]["Picture"].isna().all())
    e = sheets["Employees"]
    print("Employees.Photo values:", e["Photo"].tolist())
    print("Employees hire dates:", e["HireDate"].dt.date.tolist())
    print("Employees birth dates:", e["BirthDate"].dt.date.tolist())


def export_csvs(sheets, out_dir):
    """Write each sheet to its own UTF-8 CSV.

    Sheets are written unchanged, except that fully empty "Unnamed"
    columns are dropped.

    Args:
        sheets (dict[str, pandas.DataFrame]): Sheets keyed by name.
        out_dir (pathlib.Path): Folder that receives the CSV files.

    Returns:
        None. Writes one CSV per entry in ``CSV_NAMES``.
    """
    section("CSV export")
    for name, df in sheets.items():
        empty_unnamed = [c for c in df.columns
                         if str(c).startswith("Unnamed") and df[c].isna().all()]
        out = out_dir / CSV_NAMES[name]
        df.drop(columns=empty_unnamed).to_csv(out, index=False,
                                              encoding="utf-8")
        print(f"{name} -> {out.relative_to(ROOT)}"
              f" (dropped empty columns: {empty_unnamed or 'none'})")


def main():
    """Run all profiling and checks, then export the CSVs.

    Args:
        None.

    Returns:
        None.
    """
    sheets = load_sheets(XLSX)
    profile_sheets(sheets)
    check_keys(sheets)
    check_orders(sheets)
    check_products(sheets)
    check_text(sheets)
    export_csvs(sheets, CSV_DIR)


if __name__ == "__main__":
    main()
