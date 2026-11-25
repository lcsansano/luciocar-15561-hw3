"""Q1: Do deeper discounts sell more, or are we giving away revenue?

This shows a LINK between discount level and order size, not cause and
effect: discounts are not handed out at random (big customers or big orders
may get them because they are big). For the cap decision that is enough: if
25% lines do not sell much more than 5% lines, the extra 20 points of
discount do not pay for themselves either way.

Method:
  - Order lines at the standard discount levels (0, 5, 10, 15, 20, 25%);
    order 11077's one-off 1-6% discounts (8 lines) are left out.
  - Relative quantity = line quantity / that product's average line
    quantity, so 1.0 means "a typical order size for this product". This
    compares products with themselves (cheese vs cheese, not cheese vs beer).
  - 95% interval for each level from 5,000 bootstrap resamples (seed 42).
  - Break-even: compared with 5%, a deeper discount d keeps revenue flat only
    if quantity rises by 0.95 / (1 - d). At 25% that is +26.7%.

Run from the project root:
    .venv/bin/python -m src.q1_discounts
"""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.load import ROOT, build_order_lines  # noqa: E402

RESULTS = ROOT / "results"
LEVELS = [0.0, 0.05, 0.10, 0.15, 0.20, 0.25]
BASE = 0.05
N_BOOT = 5000
SEED = 42

BLUE = "#2a78d6"
RED = "#e34948"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
SURFACE = "#fcfcfb"


def standard_lines(lines):
    lines = lines[lines["Discount"].isin(LEVELS)].copy()
    product_mean = lines.groupby("ProductID")["Quantity"].transform("mean")
    lines["RelQty"] = lines["Quantity"] / product_mean
    return lines


def level_table(lines):
    rng = np.random.default_rng(SEED)
    rows = []
    for level, grp in lines.groupby("Discount"):
        rel = grp["RelQty"].to_numpy()
        boots = rng.choice(rel, size=(N_BOOT, len(rel))).mean(axis=1)
        rows.append({
            "discount_pct": round(level * 100),
            "lines": len(grp),
            "avg_units_per_line": grp["Quantity"].mean(),
            "rel_qty": rel.mean(),
            "rel_qty_ci_low": np.percentile(boots, 2.5),
            "rel_qty_ci_high": np.percentile(boots, 97.5),
            "discount_given_usd": grp["DiscountAmount"].sum(),
            "revenue_usd": grp["Revenue"].sum(),
        })
    table = pd.DataFrame(rows)
    base = table.loc[table["discount_pct"] == BASE * 100, "rel_qty"].iloc[0]
    table["breakeven_rel_qty"] = base * (1 - BASE) / (1 - table["discount_pct"] / 100)
    table.loc[table["discount_pct"] < BASE * 100, "breakeven_rel_qty"] = np.nan
    table["vs_5pct_actual_pct"] = (table["rel_qty"] / base - 1) * 100
    table["vs_5pct_needed_pct"] = (table["breakeven_rel_qty"] / base - 1) * 100
    return table


def deep_vs_light(lines):
    """Robustness checks for 25% vs 5% that compare like with like."""
    rng = np.random.default_rng(SEED)
    low = lines.loc[lines["Discount"] == 0.05, "RelQty"].to_numpy()
    high = lines.loc[lines["Discount"] == 0.25, "RelQty"].to_numpy()
    boots = (rng.choice(high, (N_BOOT, len(high))).mean(axis=1)
             / rng.choice(low, (N_BOOT, len(low))).mean(axis=1) - 1) * 100

    both = lines[lines["Discount"].isin([0.05, 0.25])]
    per_product = both.pivot_table(index="ProductID", columns="Discount",
                                   values="Quantity", aggfunc="median").dropna()
    ratio = per_product[0.25] / per_product[0.05]

    per_cust = both.groupby("CustomerID")["Discount"].nunique()
    same_cust = both[both["CustomerID"].isin(per_cust[per_cust == 2].index)]
    cust_ratio = (same_cust.loc[same_cust["Discount"] == 0.25, "RelQty"].mean()
                  / same_cust.loc[same_cust["Discount"] == 0.05, "RelQty"].mean())

    total = lines["DiscountAmount"].sum()
    over_10 = lines.loc[lines["Discount"] > 0.10, "DiscountAmount"].sum()
    return pd.Series({
        "rel_qty_25_vs_5_pct": (high.mean() / low.mean() - 1) * 100,
        "ci_low_pct": np.percentile(boots, 2.5),
        "ci_high_pct": np.percentile(boots, 97.5),
        "breakeven_needed_pct": ((1 - 0.05) / (1 - 0.25) - 1) * 100,
        "products_sold_at_both": len(ratio),
        "products_25_sells_more": int((ratio > 1).sum()),
        "products_25_sells_less": int((ratio < 1).sum()),
        "median_product_ratio_25_vs_5": ratio.median(),
        "customers_at_both": same_cust["CustomerID"].nunique(),
        "same_customer_ratio_25_vs_5": cust_ratio,
        "discount_given_total_usd": total,
        "discount_given_above_10pct_usd": over_10,
    })


def plot_levels(table, summary, out_path):
    fig, ax = plt.subplots(figsize=(9, 6), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    x = table["discount_pct"]

    # Discount levels are categories: dots and ranges only, no connecting line.
    be = table.dropna(subset=["breakeven_rel_qty"])
    ax.scatter(be["discount_pct"], be["breakeven_rel_qty"], marker="_",
               s=420, linewidth=2.5, color=RED, zorder=4)
    for _, row in be[be["discount_pct"] > BASE * 100].iterrows():
        ax.text(row["discount_pct"] - 1.1, row["breakeven_rel_qty"],
                f"{row['breakeven_rel_qty']:.2f}", color=RED, fontsize=8,
                ha="right", va="center")

    ax.vlines(x, table["rel_qty_ci_low"], table["rel_qty_ci_high"],
              color=BLUE, linewidth=2, alpha=0.45, zorder=3)
    ax.scatter(x, table["rel_qty"], s=70, color=BLUE, edgecolor=SURFACE,
               linewidth=1.5, zorder=5)
    for _, row in table.iterrows():
        ax.text(row["discount_pct"] + 1.1, row["rel_qty"],
                f"{row['rel_qty']:.2f}", color=INK_2, fontsize=8.5,
                ha="left", va="center")
        ax.text(row["discount_pct"], 0.66,
                f"{row['lines']:.0f} lines\n"
                + (f"${row['discount_given_usd']/1000:.0f}k given"
                   if row["discount_given_usd"] else "—"),
                ha="center", va="bottom", fontsize=7.5, color=MUTED)
    handles = [
        plt.Line2D([], [], marker="o", linestyle="", markersize=8,
                   color=BLUE, label="Actual order size (bar = 95% range)"),
        plt.Line2D([], [], marker="_", linestyle="", markersize=16,
                   markeredgewidth=2.5, color=RED,
                   label="Order size needed to earn as much as at 5%"),
    ]
    ax.legend(handles=handles, loc="upper left", frameon=False, fontsize=8.5,
              labelcolor=INK_2)

    ax.set_xticks(x, [f"{v:.0f}%" for v in x])
    ax.set_xlim(-2.5, 28.5)
    ax.set_ylim(0.62, 1.62)
    ax.set_xlabel("Discount on the order line", color=INK_2, fontsize=9.5)
    ax.set_ylabel("Units per line vs the product's average (1.0 = typical)",
                  color=INK_2, fontsize=9.5)
    ax.axhline(1, color="#c3c2b7", linewidth=0.8, zorder=1)
    ax.grid(axis="y", color=GRID, linewidth=0.6, zorder=0)
    ax.tick_params(colors=MUTED, labelsize=8.5)
    for side in ["top", "right"]:
        ax.spines[side].set_visible(False)
    for side in ["left", "bottom"]:
        ax.spines[side].set_color(GRID)

    fig.suptitle(
        f"A 25% discount would need {summary['breakeven_needed_pct']:.0f}% "
        "more units than 5% to pay off. "
        f"It gets about {summary['rel_qty_25_vs_5_pct']:.0f}%.",
        x=0.02, ha="left", fontsize=13, fontweight="bold", color=INK)
    fig.text(
        0.02, 0.925,
        "This shows a link, not cause and effect. Each product is compared "
        "with itself (1.0 = its typical order size).\n"
        f"25% vs 5%: +{summary['rel_qty_25_vs_5_pct']:.0f}% units "
        f"(95% range {summary['ci_low_pct']:+.0f}% to "
        f"{summary['ci_high_pct']:+.0f}%). Even the top of the range "
        "falls short of break-even.",
        ha="left", va="top", fontsize=9, color=INK_2)
    fig.text(0.02, 0.01,
             "This is a link, not proof of cause: discounts are not given at "
             "random. No cost data, so margin itself cannot be measured.\n"
             "Order 11077's one-off 1–6% discounts left out. Source: "
             "Northwind database.",
             fontsize=7.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.05, 1, 0.87))
    fig.savefig(out_path, facecolor=SURFACE)
    plt.close(fig)


def main():
    RESULTS.mkdir(exist_ok=True)
    all_lines = build_order_lines()
    lines = standard_lines(all_lines)
    table = level_table(lines)
    summary = deep_vs_light(lines)

    if abs(table["discount_given_usd"].sum()
           - all_lines.loc[all_lines["Discount"].isin(LEVELS),
                           "DiscountAmount"].sum()) > 0.01:
        raise ValueError("discount totals do not reconcile")

    table.round(3).to_csv(RESULTS / "q1_discount_levels.csv", index=False)
    summary.round(3).to_csv(RESULTS / "q1_summary.csv", header=["value"])
    plot_levels(table, summary, RESULTS / "q1_discounts.png")

    with pd.option_context("display.width", 200):
        print(table.round(2).to_string(index=False))
        print()
        print(summary.round(2).to_string())


if __name__ == "__main__":
    main()
