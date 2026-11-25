"""Q3: Which customer countries are growing or shrinking?

This measures VOLUME growth, not revenue growth.

Fair comparison:
  1. Same calendar months: Jul 1996-Apr 1997 ("prior") vs Jul 1997-Apr
     1998 ("recent"), 10 full months each. Using 10 months instead of
     only Jan-Apr gives 2.5x more orders per country (less noise from
     single orders) while still comparing identical months, so
     seasonality cancels. May-Jun 1997 and the 6 days of May 1998 are
     left out so neither period gets extra months. A Jan-Apr only check
     agrees on the shrinking markets.
  2. Fixed prices: prices rose about 25% in April 1997, so most "prior"
     lines were sold at old prices and every "recent" line at today's
     prices. Comparing actual revenue would count the price rise as
     growth. Every line is therefore valued at one fixed price list
     (today's list price): Quantity x ListPrice x (1 - Discount).
     ListPrice is used only as a fixed weight to add up different
     products, never as revenue. In the recent period this equals actual
     revenue, because every line was sold at list price.
  3. Countries with fewer than 10 orders in either period are grouped
     into "Other countries", because one order can swing their
     percentage.

Run from the project root:
    .venv/bin/python -m src.q3_country_growth
"""

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
OTHER = "Other countries"

BLUE = "#2a78d6"        # growing faster than the company
LIGHT_BLUE = "#86b6ef"  # growing, but slower than the company
RED = "#e34948"         # shrinking
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
SURFACE = "#fcfcfb"


def tag_periods(lines):
    """Keep lines in the two comparison periods and add volume.

    Args:
        lines (pandas.DataFrame): Output of ``build_order_lines``.

    Returns:
        pandas.DataFrame: Lines inside ``PERIODS`` only, with ``Period``
            ("prior" or "recent") and ``ConstRevenue`` (Quantity x
            ListPrice x (1 - Discount), the fixed-price volume) added.
    """
    lines = lines.copy()
    lines["Period"] = pd.NA
    for name, (start, end) in PERIODS.items():
        in_period = (lines["OrderMonth"] >= pd.Period(start, "M")) & (
            lines["OrderMonth"] <= pd.Period(end, "M"))
        lines.loc[in_period, "Period"] = name
    lines["ConstRevenue"] = (lines["Quantity"] * lines["ListPrice"]
                             * (1 - lines["Discount"]))
    return lines.dropna(subset=["Period"])


def summarise(lines, key):
    """Total orders, customers, units, revenue and volume per group.

    Args:
        lines (pandas.DataFrame): Output of ``tag_periods``.
        key (str): Column to group by, e.g. "CustomerCountry".

    Returns:
        pandas.DataFrame: One row per ``key`` value with columns
            ``<metric>_prior`` and ``<metric>_recent`` for orders,
            customers, units, revenue and volume_usd.
    """
    stats = (lines.groupby([key, "Period"])
             .agg(orders=("OrderID", "nunique"),
                  customers=("CustomerID", "nunique"),
                  units=("Quantity", "sum"),
                  revenue=("Revenue", "sum"),
                  volume_usd=("ConstRevenue", "sum"))
             .unstack("Period", fill_value=0))
    stats.columns = [f"{metric}_{period}" for metric, period in stats.columns]
    return stats


def add_growth(stats, company_growth=None):
    """Add change and growth columns, plus a trend label if asked.

    Modifies ``stats`` in place and also returns it.

    Args:
        stats (pandas.DataFrame): Output of ``summarise``.
        company_growth (float | None): Company volume growth in percent;
            when given, each row gets a ``trend`` label relative to it.

    Returns:
        pandas.DataFrame: ``stats`` with ``volume_change_usd`` and
            volume, revenue and units growth in percent (and
            ``trend``).
    """
    stats["volume_change_usd"] = stats["volume_usd_recent"] - stats["volume_usd_prior"]
    stats["volume_growth_pct"] = (stats["volume_usd_recent"]
                                  / stats["volume_usd_prior"] - 1) * 100
    stats["revenue_growth_pct"] = (stats["revenue_recent"]
                                   / stats["revenue_prior"] - 1) * 100
    stats["units_growth_pct"] = (stats["units_recent"]
                                 / stats["units_prior"] - 1) * 100
    if company_growth is not None:
        stats["trend"] = "growing faster than company"
        stats.loc[stats["volume_growth_pct"] < company_growth, "trend"] = (
            "growing slower than company")
        stats.loc[stats["volume_growth_pct"] < 0, "trend"] = "shrinking"
    return stats


def country_growth(lines):
    """Compute volume growth per market, grouping small countries.

    Countries with fewer than ``SMALL_SAMPLE_ORDERS`` orders in either
    period are combined into ``OTHER``.

    Args:
        lines (pandas.DataFrame): Output of ``tag_periods``.

    Returns:
        tuple: Four items:
            - pandas.DataFrame: Markets (countries plus ``OTHER``),
              sorted by volume growth, highest first.
            - pandas.DataFrame: One-row company total.
            - pandas.DataFrame: Every country ungrouped, with a
              ``grouped_into_other`` flag.
            - list[str]: Names of the countries grouped into ``OTHER``.
    """
    by_country = summarise(lines, "CustomerCountry")
    small = (by_country[["orders_prior", "orders_recent"]].min(axis=1)
             < SMALL_SAMPLE_ORDERS)

    grouped = lines.assign(Market=lines["CustomerCountry"].where(
        ~lines["CustomerCountry"].isin(by_country.index[small]), OTHER))
    markets = summarise(grouped, "Market")
    company = add_growth(summarise(lines.assign(All="All countries"), "All"))
    company_growth = company["volume_growth_pct"].iloc[0]
    markets = add_growth(markets, company_growth)
    markets.loc[OTHER, "trend"] = "group of small countries"

    detail = add_growth(by_country, company_growth)
    detail["grouped_into_other"] = small
    markets = markets.sort_values("volume_growth_pct", ascending=False)
    markets.index.name = "Market"
    return markets, company, detail, sorted(by_country.index[small])


def check_totals(markets, company):
    """Verify that the markets add up to the company total.

    Args:
        markets (pandas.DataFrame): Market table from
            ``country_growth``.
        company (pandas.DataFrame): Company table from
            ``country_growth``.

    Returns:
        None.

    Raises:
        ValueError: If orders, revenue or volume in either period do not
            add up within one cent.
    """
    for col in ["revenue_prior", "revenue_recent", "volume_usd_prior",
                "volume_usd_recent", "orders_prior", "orders_recent"]:
        if abs(markets[col].sum() - company[col].iloc[0]) > 0.01:
            raise ValueError(f"{col} does not reconcile")


def manager_action(markets):
    """Write the recommended action shown under the chart.

    Args:
        markets (pandas.DataFrame): Market table from
            ``country_growth``; needs at least one "shrinking" market.

    Returns:
        str: Two-line recommendation naming the two markets with the
            largest volume gain and the shrinking markets.
    """
    real = markets.drop(index=OTHER)
    top = real.sort_values("volume_change_usd", ascending=False).head(2)
    share = top["volume_change_usd"].sum() / markets["volume_change_usd"].sum()
    shrinking = real[real["trend"] == "shrinking"].index.tolist()
    return (f"What to do: protect and expand {top.index[0]} and {top.index[1]} "
            f"({share:.0%} of all volume growth).\nIn "
            f"{', '.join(shrinking[:-1])} and {shrinking[-1]}, one or two "
            "customers cause the drop: call them (Q2) before cutting effort.")


def plot_growth(markets, company, small_names, out_path):
    """Draw the volume-growth bar chart and save it.

    Args:
        markets (pandas.DataFrame): Market table from
            ``country_growth``.
        company (pandas.DataFrame): Company table from
            ``country_growth``.
        small_names (list[str]): Countries grouped into ``OTHER``,
            listed in the footnote.
        out_path (pathlib.Path): Destination PNG, overwritten.

    Returns:
        None. Writes the chart to ``out_path``.
    """
    company_growth = company["volume_growth_pct"].iloc[0]
    company_rev = company["revenue_growth_pct"].iloc[0]
    data = markets.sort_values("volume_growth_pct")
    colors = {"growing faster than company": BLUE,
              "growing slower than company": LIGHT_BLUE,
              "shrinking": RED, "group of small countries": "#c3c2b7"}

    fig, ax = plt.subplots(figsize=(9, 7), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)

    y = range(len(data))
    ax.barh(y, data["volume_growth_pct"], height=0.62,
            color=[colors[t] for t in data["trend"]], zorder=2)
    for i, (_, row) in enumerate(data.iterrows()):
        v = row["volume_growth_pct"]
        ax.text(v + (2 if v >= 0 else -2), i, f"{v:+.0f}%", va="center",
                ha="left" if v >= 0 else "right", fontsize=8.5, color=INK_2,
                zorder=4, bbox=dict(facecolor=SURFACE, edgecolor="none",
                                    pad=1))

    labels = [f"{m}  (${row['revenue_recent']/1000:.0f}k)"
              for m, row in data.iterrows()]
    ax.set_yticks(list(y), labels, fontsize=9.5, color=INK)
    ax.axvline(0, color="#c3c2b7", linewidth=1, zorder=3)
    ax.axvline(company_growth, color=INK_2, linewidth=1, linestyle="--",
               zorder=3)
    ax.text(company_growth + 1.5, len(data) - 0.55,
            f"Company average {company_growth:+.0f}%", fontsize=8,
            color=INK_2, va="bottom")
    ax.grid(axis="x", color=GRID, linewidth=0.6, zorder=0)
    ax.tick_params(axis="x", colors=MUTED, labelsize=8.5)
    ax.tick_params(axis="y", length=0)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:+.0f}%")
    for side in ["top", "right", "left", "bottom"]:
        ax.spines[side].set_visible(False)
    ax.set_xlabel("Sales volume growth, Jul 1997–Apr 1998 vs Jul 1996–Apr 1997",
                  color=INK_2, fontsize=9.5)
    lo, hi = ax.get_xlim()
    ax.set_xlim(lo - 12, hi + 15)
    ax.set_ylim(-0.6, len(data) + 0.3)

    fig.suptitle("Sales volume growth by customer country (%)", x=0.02,
                 ha="left", fontsize=13, fontweight="bold", color=INK)
    fig.text(
        0.02, 0.935,
        "Volume = units sold, valued at one fixed price list so the April 1997 "
        "price rise doesn't count as growth.\n"
        f"Same 10 months in both periods. Company volume {company_growth:+.0f}% "
        f"(revenue {company_rev:+.0f}%, the difference is the price rise). "
        "($k) = recent 10-month sales.",
        ha="left", va="top", fontsize=8.5, color=INK_2)

    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in colors.values()]
    names = ["Growing faster than company", "Growing, slower than company",
             "Shrinking", "Small countries combined"]
    ax.legend(handles, names, loc="lower right", frameon=False, fontsize=8.5,
              labelcolor=INK_2)

    fig.text(0.02, 0.105, manager_action(markets), fontsize=9.5,
             color=INK, fontweight="bold", va="top", ha="left")
    fig.text(0.02, 0.012,
             f"Other countries (under {SMALL_SAMPLE_ORDERS} orders in a period): "
             f"{', '.join(small_names)}.\nCountry = customer's country "
             "(not ship-to). Source: Northwind database.",
             fontsize=7.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.12, 1, 0.885))
    fig.savefig(out_path, facecolor=SURFACE)
    plt.close(fig)


def main():
    """Run the Q3 analysis and write its CSVs and chart.

    Args:
        None.

    Returns:
        None. Writes ``results/q3_*`` and prints the market table.

    Raises:
        ValueError: If the market totals do not reconcile.
    """
    RESULTS.mkdir(exist_ok=True)
    lines = tag_periods(build_order_lines())
    markets, company, detail, small_names = country_growth(lines)
    check_totals(markets, company)

    markets.round(2).to_csv(RESULTS / "q3_country_growth.csv")
    detail.sort_values("volume_change_usd", ascending=False).round(2).to_csv(
        RESULTS / "q3_country_growth_all_countries.csv")
    plot_growth(markets, company, small_names, RESULTS / "q3_country_growth.png")

    cols = ["orders_prior", "orders_recent", "revenue_recent",
            "volume_change_usd", "volume_growth_pct", "revenue_growth_pct",
            "trend"]
    with pd.option_context("display.width", 200):
        print(markets[cols].round(1).to_string())
    print(f"\nCompany: volume {company['volume_growth_pct'].iloc[0]:+.1f}%, "
          f"revenue {company['revenue_growth_pct'].iloc[0]:+.1f}%")
    print(manager_action(markets))


if __name__ == "__main__":
    main()
