"""Q3: Which customer countries are growing or shrinking?

Fair comparison:
  1. Same calendar months: Jul 1996-Apr 1997 ("prior") vs Jul 1997-Apr 1998
     ("recent"), 10 full months each. May-Jun 1997 and the 6 days of May 1998
     are left out so neither period gets extra months.
  2. Constant prices: prices rose about 25% during 1997, so revenue growth
     would partly be price. Each line is valued at today's list price
     (Quantity x ListPrice x (1 - Discount)), which measures real volume.
     Every 1998 line was sold at list price, so recent-period values barely
     change.

Run from the project root:
    .venv/bin/python -m src.q3_country_growth
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from src.load import ROOT, build_order_lines  # noqa: E402

RESULTS = ROOT / "results"
PERIODS = {
    "prior": ("1996-07", "1997-04"),
    "recent": ("1997-07", "1998-04"),
}
SMALL_SAMPLE_ORDERS = 10

# Colors from the dataviz reference palette (light mode).
BLUE = "#2a78d6"        # growing faster than the company
LIGHT_BLUE = "#86b6ef"  # growing, but slower than the company
RED = "#e34948"         # shrinking
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
SURFACE = "#fcfcfb"


def tag_periods(lines):
    lines = lines.copy()
    lines["Period"] = pd.NA
    for name, (start, end) in PERIODS.items():
        in_period = (lines["OrderMonth"] >= pd.Period(start, "M")) & (
            lines["OrderMonth"] <= pd.Period(end, "M"))
        lines.loc[in_period, "Period"] = name
    lines["ConstRevenue"] = (lines["Quantity"] * lines["ListPrice"]
                             * (1 - lines["Discount"]))
    return lines.dropna(subset=["Period"])


def country_growth(lines):
    stats = (lines.groupby(["CustomerCountry", "Period"])
             .agg(orders=("OrderID", "nunique"),
                  customers=("CustomerID", "nunique"),
                  units=("Quantity", "sum"),
                  revenue=("Revenue", "sum"),
                  const_revenue=("ConstRevenue", "sum"))
             .unstack("Period", fill_value=0))
    stats.columns = [f"{metric}_{period}" for metric, period in stats.columns]

    total = lines.groupby("Period").agg(
        orders=("OrderID", "nunique"), customers=("CustomerID", "nunique"),
        units=("Quantity", "sum"), revenue=("Revenue", "sum"),
        const_revenue=("ConstRevenue", "sum"))
    total_row = {f"{m}_{p}": total.loc[p, m]
                 for m in total.columns for p in total.index}
    stats.loc["All countries"] = total_row

    stats["const_change_usd"] = (stats["const_revenue_recent"]
                                 - stats["const_revenue_prior"])
    stats["real_growth_pct"] = (stats["const_revenue_recent"]
                                / stats["const_revenue_prior"] - 1) * 100
    stats["nominal_growth_pct"] = (stats["revenue_recent"]
                                   / stats["revenue_prior"] - 1) * 100
    stats["units_growth_pct"] = (stats["units_recent"]
                                 / stats["units_prior"] - 1) * 100

    company = stats.loc["All countries", "real_growth_pct"]
    stats["trend"] = "growing faster than company"
    stats.loc[stats["real_growth_pct"] < company, "trend"] = (
        "growing slower than company")
    stats.loc[stats["real_growth_pct"] < 0, "trend"] = "shrinking"
    stats.loc["All countries", "trend"] = "company total"
    stats["small_sample"] = (stats[["orders_prior", "orders_recent"]]
                             .min(axis=1) < SMALL_SAMPLE_ORDERS)
    stats.loc["All countries", "small_sample"] = False

    stats = stats.sort_values("const_change_usd", ascending=False)
    stats.index.name = "CustomerCountry"
    return stats


def check_totals(stats, lines):
    countries = stats.drop(index="All countries")
    for col, src in [("revenue", "Revenue"), ("const_revenue", "ConstRevenue")]:
        for period in PERIODS:
            by_country = countries[f"{col}_{period}"].sum()
            direct = lines.loc[lines["Period"] == period, src].sum()
            if abs(by_country - direct) > 0.01:
                raise ValueError(f"{col}_{period}: {by_country} != {direct}")


def plot_growth(stats, out_path):
    company = stats.loc["All countries"]
    data = stats.drop(index="All countries").sort_values("const_change_usd")
    colors = {"growing faster than company": BLUE,
              "growing slower than company": LIGHT_BLUE,
              "shrinking": RED}

    fig, ax = plt.subplots(figsize=(9, 8.5), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)

    y = range(len(data))
    ax.barh(y, data["const_change_usd"] / 1000, height=0.62,
            color=[colors[t] for t in data["trend"]], zorder=2)

    for i, (country, row) in enumerate(data.iterrows()):
        value = row["const_change_usd"] / 1000
        label = f"{row['real_growth_pct']:+.0f}%"
        offset = 1.2 if value >= 0 else -1.2
        ax.text(value + offset, i, label, va="center",
                ha="left" if value >= 0 else "right", fontsize=8.5,
                color=INK_2)

    labels = [f"{c}*" if s else c
              for c, s in zip(data.index, data["small_sample"])]
    ax.set_yticks(list(y), labels, fontsize=9.5, color=INK)
    ax.axvline(0, color="#c3c2b7", linewidth=1, zorder=3)
    ax.grid(axis="x", color=GRID, linewidth=0.6, zorder=0)
    ax.tick_params(axis="x", colors=MUTED, labelsize=8.5)
    ax.tick_params(axis="y", length=0)
    for side in ["top", "right", "left", "bottom"]:
        ax.spines[side].set_visible(False)
    ax.set_xlabel("Change in sales at constant prices (thousand USD)",
                  color=INK_2, fontsize=9.5)
    lo, hi = ax.get_xlim()
    ax.set_xlim(lo - 6, hi + 10)

    fig.suptitle("Where Northwind's sales grew and shrank, by customer country",
                 x=0.02, ha="left", fontsize=13, fontweight="bold", color=INK)
    fig.text(
        0.02, 0.935,
        "Jul 1997–Apr 1998 vs the same 10 months a year earlier, valued at "
        "today's list prices.\nLabels show real growth. Company overall: "
        f"{company['real_growth_pct']:+.0f}% real "
        f"({company['nominal_growth_pct']:+.0f}% before removing price rises).",
        ha="left", va="top", fontsize=9, color=INK_2)

    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in colors.values()]
    names = [f"Growing faster than company (>{company['real_growth_pct']:.0f}%)",
             "Growing, but slower than company", "Shrinking"]
    ax.legend(handles, names, loc="lower right", frameon=False, fontsize=8.5,
              labelcolor=INK_2)
    fig.text(0.02, 0.01,
             f"* Fewer than {SMALL_SAMPLE_ORDERS} orders in one of the periods; "
             "percentages can swing on a single order.\n"
             "Country = customer's country (not ship-to). "
             "Source: Northwind database.",
             fontsize=7.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.04, 1, 0.915))
    fig.savefig(out_path, facecolor=SURFACE)
    plt.close(fig)


def main():
    RESULTS.mkdir(exist_ok=True)
    lines = tag_periods(build_order_lines())
    stats = country_growth(lines)
    check_totals(stats, lines)

    csv_path = RESULTS / "q3_country_growth.csv"
    stats.round(2).to_csv(csv_path)
    png_path = RESULTS / "q3_country_growth.png"
    plot_growth(stats, png_path)

    cols = ["orders_prior", "orders_recent", "const_revenue_prior",
            "const_revenue_recent", "const_change_usd", "real_growth_pct",
            "nominal_growth_pct", "trend", "small_sample"]
    with pd.option_context("display.width", 200):
        print(stats[cols].round(1).to_string())
    print(f"\nSaved {csv_path.relative_to(ROOT)} and "
          f"{png_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
