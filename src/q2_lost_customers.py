"""Q2: Regular customers who stopped ordering, and whom to call first.

Rules (each customer is judged against their own rhythm):
  - Regular customer: at least 5 orders in the data.
  - Usual gap: the AVERAGE number of days between orders = (last order -
    first order) / (number of orders - 1). Not the median: customers
    order in bursts (several orders a few days apart, then a long
    pause). The median picks up the short gaps inside a burst and makes
    customers look far more frequent than they are (e.g. Mere Paillarde:
    median 17.5 days, average 32 days), which would flag customers as
    lost too early. The average equals the customer's real long-run
    ordering frequency.
  - Days quiet: days from the last order to the end of the data
    (1998-05-06).
  - Likely lost: quiet for more than 2x the usual gap and more than 60
    days.
  - Overdue: quiet for more than 1.5x the usual gap and more than 45
    days.
  - Value at risk: actual revenue in the 12 months up to the customer's
    last order (what a normal year with them was worth).
  - Call list: likely-lost and overdue customers, ranked by value at
    risk.
  - Slow buyers (usual gap of 90+ days) who are not yet flagged are
    marked "too early to tell": in a 22-month window they cannot be
    quiet long enough to judge. They go on a follow-up calendar instead.
  - Check back by: last order + 2x usual gap, the date by which a
    customer who keeps their rhythm should have ordered again.

Run from the project root:
    .venv/bin/python -m src.q2_lost_customers
"""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from src.load import DATA_END, ROOT, build_order_lines, load_tables  # noqa: E402

RESULTS = ROOT / "results"
MIN_ORDERS = 5
LOST_RATIO, LOST_MIN_DAYS = 2.0, 60
OVERDUE_RATIO, OVERDUE_MIN_DAYS = 1.5, 45
SLOW_GAP_DAYS = 90
SLOW_STATUS = "too early to tell (slow buyer)"

RED = "#e34948"
ORANGE = "#eb6834"
GRAY = "#c3c2b7"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
SURFACE = "#fcfcfb"
BAND = "#f0efec"


def customer_rhythm(lines):
    """Measure each customer's ordering rhythm and recent value.

    Args:
        lines (pandas.DataFrame): Output of ``build_order_lines``.

    Returns:
        pandas.DataFrame: One row per customer with order count, first
            and last order date, ``usual_gap_days`` (average gap, None
            for one order), ``median_gap_days``, ``days_quiet``,
            ``value_at_risk_usd`` (actual revenue in the 365 days up to
            the last order), ``lifetime_revenue_usd``,
            ``quiet_vs_usual`` and ``check_back_by``.
    """
    orders = (lines.groupby(["CustomerID", "OrderID", "OrderDate"])
              ["Revenue"].sum().reset_index())

    rows = []
    for cust, grp in orders.groupby("CustomerID"):
        first, last = grp["OrderDate"].min(), grp["OrderDate"].max()
        n = len(grp)
        gaps = grp["OrderDate"].sort_values().diff().dt.days.dropna()
        year_before_last = grp[grp["OrderDate"] > last - pd.Timedelta(days=365)]
        rows.append({
            "CustomerID": cust,
            "orders": n,
            "first_order": first,
            "last_order": last,
            "usual_gap_days": (last - first).days / (n - 1) if n > 1 else None,
            "median_gap_days": gaps.median() if n > 1 else None,
            "days_quiet": (DATA_END - last).days,
            "value_at_risk_usd": year_before_last["Revenue"].sum(),
            "lifetime_revenue_usd": grp["Revenue"].sum(),
        })
    stats = pd.DataFrame(rows)
    stats["quiet_vs_usual"] = stats["days_quiet"] / stats["usual_gap_days"]
    gap = pd.to_timedelta(stats["usual_gap_days"] * LOST_RATIO, unit="D")
    stats["check_back_by"] = (stats["last_order"] + gap).dt.date
    for col in ["first_order", "last_order"]:
        stats[col] = stats[col].dt.date
    return stats


def classify(stats):
    """Label each customer's status from their rhythm.

    Args:
        stats (pandas.DataFrame): Output of ``customer_rhythm``.

    Returns:
        pandas.DataFrame: Copy of ``stats`` with ``status``: "likely
            lost", "overdue", "too early to tell (slow buyer)", "active"
            or "not regular (<5 orders)".
    """
    stats = stats.copy()
    regular = stats["orders"] >= MIN_ORDERS
    lost = (regular & (stats["quiet_vs_usual"] > LOST_RATIO)
            & (stats["days_quiet"] > LOST_MIN_DAYS))
    overdue = (regular & ~lost & (stats["quiet_vs_usual"] > OVERDUE_RATIO)
               & (stats["days_quiet"] > OVERDUE_MIN_DAYS))
    stats["status"] = "active"
    stats.loc[~regular, "status"] = "not regular (<5 orders)"
    slow = (regular & ~lost & ~overdue
            & (stats["usual_gap_days"] >= SLOW_GAP_DAYS))
    stats.loc[slow, "status"] = SLOW_STATUS
    stats.loc[overdue, "status"] = "overdue"
    stats.loc[lost, "status"] = "likely lost"
    return stats


def call_list(stats, customers):
    """Add contact details and build the call list and calendar.

    Args:
        stats (pandas.DataFrame): Output of ``classify``.
        customers (pandas.DataFrame): Customers table from
            ``load_tables``.

    Returns:
        tuple: Three items:
            - pandas.DataFrame: All customers with contact details.
            - pandas.DataFrame: Likely-lost and overdue customers ranked
              by value at risk, with a ``rank`` column starting at 1.
            - pandas.DataFrame: Slow buyers sorted by ``check_back_by``.
    """
    contact = customers[["CustomerID", "CompanyName", "ContactName",
                         "ContactTitle", "City", "Country", "Phone"]]
    full = stats.merge(contact, on="CustomerID", how="left",
                       validate="one_to_one")
    calls = (full[full["status"].isin(["likely lost", "overdue"])]
             .sort_values("value_at_risk_usd", ascending=False)
             .reset_index(drop=True))
    calls.insert(0, "rank", range(1, len(calls) + 1))
    calendar = (full[full["status"] == SLOW_STATUS]
                .sort_values("check_back_by").reset_index(drop=True))
    return full, calls, calendar


def style_axes(ax):
    """Apply the shared grid, tick and spine style to a chart.

    Args:
        ax (matplotlib.axes.Axes): Axes to style in place.

    Returns:
        None.
    """
    ax.grid(color=GRID, linewidth=0.6, zorder=0)
    ax.tick_params(colors=MUTED, labelsize=8.5)
    for side in ["top", "right"]:
        ax.spines[side].set_visible(False)
    for side in ["left", "bottom"]:
        ax.spines[side].set_color(GRID)


def plot_rhythm(full, calls, out_path):
    """Draw the days-quiet vs usual-gap scatter and save it.

    Args:
        full (pandas.DataFrame): All customers from ``call_list``; only
            regular customers are plotted.
        calls (pandas.DataFrame): Ranked call list from ``call_list``;
            its ranks are printed on the dots.
        out_path (pathlib.Path): Destination PNG, overwritten.

    Returns:
        None. Writes the chart to ``out_path``.
    """
    regular = full[full["orders"] >= MIN_ORDERS]
    colors = {"likely lost": RED, "overdue": ORANGE, "active": GRAY}

    fig, ax = plt.subplots(figsize=(9, 7), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)

    xmax = regular["usual_gap_days"].max() * 1.06
    ymax = regular["days_quiet"].max() * 1.12
    ax.axvspan(SLOW_GAP_DAYS, xmax, color=BAND, zorder=0)
    ax.text(SLOW_GAP_DAYS + 2, ymax * 0.97, "Slow buyers:\ntoo early to tell",
            fontsize=8, color=INK_2, va="top")

    for ratio, style in [(1, ":"), (OVERDUE_RATIO, "--"), (LOST_RATIO, "-")]:
        x_end = min(xmax, ymax / ratio)
        ax.plot([0, x_end], [0, ratio * x_end], color=MUTED, linewidth=0.8,
                linestyle=style, zorder=1)
        # Label sits inside the plot, just above the line near its end.
        lx = x_end * (0.9 if x_end < xmax else 0.97)
        ax.text(lx, ratio * lx + ymax * 0.008, f"{ratio:g}× usual gap",
                color=INK_2, fontsize=8, ha="right", va="bottom", zorder=2)

    size = 20 + regular["value_at_risk_usd"] / 110
    flagged = regular["status"].isin(["likely lost", "overdue"])
    size[flagged] = size[flagged].clip(lower=190)  # room for the rank number
    for status in ["active", SLOW_STATUS, "overdue", "likely lost"]:
        sub = regular[regular["status"] == status]
        hollow = status == SLOW_STATUS
        ax.scatter(sub["usual_gap_days"], sub["days_quiet"],
                   s=size[sub.index], alpha=0.9, zorder=3,
                   facecolor="none" if hollow else colors[status],
                   edgecolor=MUTED if hollow else SURFACE,
                   linewidth=1.2 if hollow else 1.5)

    # Numbered markers match the rank in the call-list table.
    for _, row in calls.iterrows():
        ax.annotate(str(row["rank"]),
                    (row["usual_gap_days"], row["days_quiet"]),
                    xytext=(0, 0), textcoords="offset points",
                    ha="center", va="center", fontsize=7.5,
                    fontweight="bold", color="white", zorder=5)

    ax.set_xlim(0, xmax)
    ax.set_ylim(0, ymax)
    ax.set_xlabel("Average gap between this customer's orders (days)",
                  color=INK_2, fontsize=9.5)
    ax.set_ylabel(f"Days since last order (as of {DATA_END:%d %b %Y})",
                  color=INK_2, fontsize=9.5)
    style_axes(ax)

    fig.suptitle(f"{len(calls)} regular customers have gone quiet — "
                 f"${calls['value_at_risk_usd'].sum()/1000:.0f}k a year at risk",
                 x=0.02, ha="left", fontsize=13, fontweight="bold", color=INK)
    fig.text(0.02, 0.93,
             f"Each dot is a customer with {MIN_ORDERS}+ orders, judged against "
             "their own ordering rhythm. Dot size = revenue in the 12 months\n"
             "before their last order. Numbers match the call list.",
             ha="left", va="top", fontsize=9, color=INK_2)

    handles = [
        plt.Line2D([], [], marker="o", linestyle="", markersize=8, color=RED,
                   label=f"Likely lost (quiet > {LOST_RATIO:g}× usual gap)"),
        plt.Line2D([], [], marker="o", linestyle="", markersize=8,
                   color=ORANGE,
                   label=f"Overdue (quiet > {OVERDUE_RATIO:g}× usual gap)"),
        plt.Line2D([], [], marker="o", linestyle="", markersize=8, color=GRAY,
                   label="Ordering as usual"),
        plt.Line2D([], [], marker="o", linestyle="", markersize=8,
                   markerfacecolor="none", markeredgecolor=MUTED,
                   label=f"Slow buyer (every {SLOW_GAP_DAYS}+ days): "
                         "too early to tell"),
    ]
    fig.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.06, 0.035),
               ncol=2, frameon=False, fontsize=8.5, labelcolor=INK_2)
    fig.text(0.02, 0.01, "Source: Northwind database. Data ends 6 May 1998.",
             fontsize=7.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.1, 1, 0.885))
    fig.savefig(out_path, facecolor=SURFACE)
    plt.close(fig)


def plot_call_table(calls, out_path):
    """Render the call list as a table image and save it.

    Args:
        calls (pandas.DataFrame): Ranked call list from ``call_list``.
        out_path (pathlib.Path): Destination PNG, overwritten.

    Returns:
        None. Writes the table to ``out_path``.
    """
    header = ["#", "Customer", "Country", "Status", "Revenue,\nlast 12 mo",
              "Usual gap\n(avg days)", "Days\nquiet", "Contact", "Phone"]
    rows = [[str(r["rank"]), r["CompanyName"], r["Country"], r["status"],
             f"${r['value_at_risk_usd']:,.0f}", f"{r['usual_gap_days']:.0f}",
             f"{r['days_quiet']:.0f}", r["ContactName"], r["Phone"]]
            for _, r in calls.iterrows()]

    fig, ax = plt.subplots(figsize=(11, 0.3 * len(rows) + 1.2), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    ax.axis("off")
    table = ax.table(cellText=rows, colLabels=header, loc="upper left",
                     cellLoc="left", colLoc="left",
                     colWidths=[0.03, 0.21, 0.08, 0.09, 0.1, 0.09, 0.06,
                                0.14, 0.12])
    table.auto_set_font_size(False)
    table.set_fontsize(8.5)
    table.scale(1, 1.55)
    for (r, c), cell in table.get_celld().items():
        cell.set_edgecolor(GRID)
        cell.set_linewidth(0.6)
        cell.set_facecolor(SURFACE)
        if r == 0:
            cell.set_text_props(color=INK_2, fontweight="bold")
            cell.set_height(cell.get_height() * 1.4)
        elif c == 3:
            status = rows[r - 1][3]
            cell.set_text_props(color=RED if status == "likely lost" else ORANGE,
                                fontweight="bold")
        if c in (4, 5, 6):
            cell._loc = "right"
            cell.PAD = 0.04
    ax.set_title("Call list for sales, ranked by revenue at risk", loc="left",
                 fontsize=12, fontweight="bold", color=INK, pad=12)
    fig.text(0.01, 0.01,
             "Revenue = actual sales in the 12 months before the customer's "
             "last order. Usual gap = average days between orders. "
             "Days quiet as of 6 May 1998.",
             fontsize=7.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(out_path, facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)


def main():
    """Run the Q2 analysis and write its CSVs, chart and table.

    Args:
        None.

    Returns:
        None. Writes ``results/q2_*`` and prints the call list.

    Raises:
        ValueError: If order counts or revenue do not reconcile.
    """
    RESULTS.mkdir(exist_ok=True)
    tables = load_tables()
    lines = build_order_lines(tables)
    stats = classify(customer_rhythm(lines))
    full, calls, calendar = call_list(stats, tables["customers"])

    if full["orders"].sum() != 830:
        raise ValueError("order count does not reconcile")
    if abs(full["lifetime_revenue_usd"].sum() - lines["Revenue"].sum()) > 0.01:
        raise ValueError("revenue does not reconcile")

    full.round(2).to_csv(RESULTS / "q2_customer_rhythm.csv", index=False)
    cols = ["rank", "status", "CompanyName", "Country", "value_at_risk_usd",
            "usual_gap_days", "days_quiet", "last_order", "orders",
            "ContactName", "ContactTitle", "Phone", "check_back_by"]
    calls[cols].round(1).to_csv(RESULTS / "q2_call_list.csv", index=False)
    cal_cols = ["check_back_by", "CompanyName", "Country", "ContactName",
                "Phone", "last_order", "usual_gap_days", "orders",
                "value_at_risk_usd"]
    calendar[cal_cols].round(1).to_csv(
        RESULTS / "q2_check_back_calendar.csv", index=False)
    plot_rhythm(full, calls, RESULTS / "q2_lost_customers.png")
    plot_call_table(calls, RESULTS / "q2_call_list.png")

    with pd.option_context("display.width", 250):
        print(calls[cols].round(0).to_string(index=False))
    print("\nStatus counts:", full["status"].value_counts().to_dict())
    print(f"Value at risk (actual revenue): ${calls['value_at_risk_usd'].sum():,.0f}")


if __name__ == "__main__":
    main()
