"""Check whether deeper discounts sell more units within the same product.

Run from the project root:
    .venv/bin/python scripts/q1_discount_check.py
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
STANDARD_LEVELS = [0.0, 0.05, 0.10, 0.15, 0.20, 0.25]


def load_lines(data_dir):
    """Load order lines with rounded discounts at standard levels only.

    Args:
        data_dir (pathlib.Path): Folder holding the exported CSVs.

    Returns:
        pandas.DataFrame: Order lines with ``Discount`` rounded to two
            decimals and restricted to ``STANDARD_LEVELS``; adds
            ``GrossValue`` and ``DiscountGiven`` in USD.
    """
    lines = pd.read_csv(data_dir / "order_details.csv")
    lines["Discount"] = lines["Discount"].round(2)
    lines = lines[lines["Discount"].isin(STANDARD_LEVELS)].copy()
    lines["GrossValue"] = lines["UnitPrice"] * lines["Quantity"]
    lines["DiscountGiven"] = lines["GrossValue"] * lines["Discount"]
    return lines


def within_product_effect(lines):
    """Compare quantity by discount level after removing product differences.

    Each line's quantity is divided by its product's mean quantity, so
    1.0 means "a typical order size for that product".

    Args:
        lines (pandas.DataFrame): Output of ``load_lines``.

    Returns:
        pandas.DataFrame: One row per discount level with line count,
            mean raw quantity, mean relative quantity, median relative
            quantity, and the USD discount given.
    """
    lines = lines.copy()
    product_mean = lines.groupby("ProductID")["Quantity"].transform("mean")
    lines["RelQty"] = lines["Quantity"] / product_mean
    return lines.groupby("Discount").agg(
        lines=("Quantity", "size"),
        mean_qty=("Quantity", "mean"),
        mean_rel_qty=("RelQty", "mean"),
        median_rel_qty=("RelQty", "median"),
        discount_given_usd=("DiscountGiven", "sum"),
    ).round(3)


def paired_comparison(lines, low, high):
    """Compare median quantity at two discount levels within each product.

    Only products sold at both levels are included.

    Args:
        lines (pandas.DataFrame): Output of ``load_lines``.
        low (float): Lower discount level, e.g. 0.05.
        high (float): Higher discount level, e.g. 0.25.

    Returns:
        pandas.DataFrame: One row per product with the median quantity
            and line count at each level, plus ``ratio`` (high / low).
    """
    sub = lines[lines["Discount"].isin([low, high])]
    stats = sub.pivot_table(index="ProductID", columns="Discount",
                            values="Quantity", aggfunc=["median", "size"])
    stats.columns = [f"{agg}_{lvl:.2f}" for agg, lvl in stats.columns]
    stats = stats.dropna()
    stats["ratio"] = stats[f"median_{high:.2f}"] / stats[f"median_{low:.2f}"]
    return stats


def main():
    """Print the within-product discount comparison.

    Args:
        None.

    Returns:
        None.
    """
    lines = load_lines(DATA)
    print(f"Lines at standard discount levels: {len(lines)}")
    print("\nQuantity by discount level (RelQty 1.0 = product's typical size):")
    print(within_product_effect(lines).to_string())

    pairs = paired_comparison(lines, 0.05, 0.25)
    print(f"\nProducts sold at both 5% and 25%: {len(pairs)}")
    print(f"  25% median qty > 5%: {(pairs['ratio'] > 1).sum()}")
    print(f"  25% median qty = 5%: {(pairs['ratio'] == 1).sum()}")
    print(f"  25% median qty < 5%: {(pairs['ratio'] < 1).sum()}")
    print(f"  median of per-product ratios (25% / 5%):"
          f" {pairs['ratio'].median():.2f}")

    total_given = lines["DiscountGiven"].sum()
    over_10 = lines.loc[lines["Discount"] > 0.10, "DiscountGiven"].sum()
    print(f"\nTotal discount given: ${total_given:,.0f};"
          f" from levels above 10%: ${over_10:,.0f}"
          f" ({over_10 / total_given:.0%})")


if __name__ == "__main__":
    main()
