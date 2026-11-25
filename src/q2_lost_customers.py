"""Q2: Which regular customers stopped ordering, and who should sales call first?

Rules (each customer is judged against their own rhythm):
  - Regular customer: at least 5 orders in the data.
  - Usual gap: average days between orders
    = (last order - first order) / (number of orders - 1).
  - Days quiet: days from the last order to the end of the data (1998-05-06).
  - Likely lost: quiet for more than 2x the usual gap and more than 60 days.
  - Overdue: quiet for more than 1.5x the usual gap and more than 45 days.
  - Value at risk: sales at today's list prices in the 12 months up to the
    customer's last order (what a normal year with them was worth).
  - Call order: likely lost first, then overdue; within each, by value at risk.
  - Slow buyers (usual gap of 90+ days) who are not yet flagged are marked
    "too early to tell": in a 22-month window they cannot be quiet long
    enough to judge. They go on a follow-up calendar instead.
  - Check back by: last order + 2x usual gap, the date by which a customer
    who keeps their rhythm should have ordered again.

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


def customer_rhythm(lines):
    lines = lines.assign(ConstRevenue=lines["Quantity"] * lines["ListPrice"]
                         * (1 - lines["Discount"]))
    orders = (lines.groupby(["CustomerID", "OrderID", "OrderDate"])
              ["ConstRevenue"].sum().reset_index())

    rows = []
    for cust, grp in orders.groupby("CustomerID"):
        first, last = grp["OrderDate"].min(), grp["OrderDate"].max()
        n = len(grp)
        year_before_last = grp[grp["OrderDate"] > last - pd.Timedelta(days=365)]
        rows.append({
            "CustomerID": cust,
            "orders": n,
            "first_order": first,
            "last_order": last,
            "usual_gap_days": (last - first).days / (n - 1) if n > 1 else None,
            "days_quiet": (DATA_END - last).days,
            "value_at_risk_usd": year_before_last["ConstRevenue"].sum(),
            "lifetime_sales_usd": grp["ConstRevenue"].sum(),
        })
    stats = pd.DataFrame(rows)
    stats["quiet_vs_usual"] = stats["days_quiet"] / stats["usual_gap_days"]
    gap = pd.to_timedelta(stats["usual_gap_days"] * LOST_RATIO, unit="D")
    stats["check_back_by"] = (stats["last_order"] + gap).dt.date
    for col in ["first_order", "last_order"]:
        stats[col] = stats[col].dt.date
    return stats


def classify(stats):
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
    contact = customers[["CustomerID", "CompanyName", "ContactName",
                         "ContactTitle", "City", "Country", "Phone"]]
    full = stats.merge(contact, on="CustomerID", how="left",
                       validate="one_to_one")
    rank = {"likely lost": 0, "overdue": 1}
    calls = full[full["status"].isin(rank)].copy()
    calls["_r"] = calls["status"].map(rank)
    calls = (calls.sort_values(["_r", "value_at_risk_usd"],
                               ascending=[True, False])
             .drop(columns="_r").reset_index(drop=True))
    calls.insert(0, "priority", range(1, len(calls) + 1))
    calendar = (full[full["status"] == SLOW_STATUS]
                .sort_values("check_back_by").reset_index(drop=True))
    return full, calls, calendar


def plot_rhythm(full, out_path):
    regular = full[full["orders"] >= MIN_ORDERS]
    colors = {"likely lost": RED, "overdue": ORANGE, "active": GRAY,
              SLOW_STATUS: GRAY}
    names = {"likely lost": f"Likely lost (quiet > {LOST_RATIO:g}× usual gap)",
             "overdue": f"Overdue (quiet > {OVERDUE_RATIO:g}× usual gap)",
             "active": "Ordering as usual",
             SLOW_STATUS: f"Slow buyer (orders every {SLOW_GAP_DAYS}+ days): "
                          "too early to tell"}

    fig, ax = plt.subplots(figsize=(9, 7), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)

    xmax = regular["usual_gap_days"].max() * 1.08
    ymax = regular["days_quiet"].max() * 1.12
    for ratio, style in [(1, ":"), (OVERDUE_RATIO, "--"), (LOST_RATIO, "-")]:
        x_end = min(xmax, ymax / ratio)
        ax.plot([0, x_end], [0, ratio * x_end], color=MUTED, linewidth=0.8,
                linestyle=style, zorder=1)
        ax.text(x_end, ratio * x_end, f" {ratio:g}× usual gap", color=MUTED,
                fontsize=8, va="bottom" if x_end < xmax else "center",
                ha="center" if x_end < xmax else "left")

    ax.axvspan(SLOW_GAP_DAYS, xmax, color="#f0efec", zorder=0)
    ax.text(SLOW_GAP_DAYS + 2, ymax * 0.97,
            "Slow buyers:\ntoo early to tell", fontsize=8, color=INK_2,
            va="top")

    size = 20 + regular["value_at_risk_usd"] / 120
    for status in ["active", SLOW_STATUS, "overdue", "likely lost"]:
        sub = regular[regular["status"] == status]
        hollow = status == SLOW_STATUS
        ax.scatter(sub["usual_gap_days"], sub["days_quiet"],
                   s=size[sub.index], alpha=0.85, zorder=3,
                   facecolor="none" if hollow else colors[status],
                   edgecolor=MUTED if hollow else SURFACE,
                   linewidth=1.2 if hollow else 1.5, label=names[status])

    flagged = regular[regular["status"].isin(["likely lost", "overdue"])]
    for _, row in flagged.iterrows():
        ax.annotate(f"{row['CompanyName']} (${row['value_at_risk_usd']/1000:.0f}k)",
                    (row["usual_gap_days"], row["days_quiet"]),
                    xytext=(7, 0), textcoords="offset points", fontsize=8,
                    color=INK, va="center")

    ax.set_xlim(0, xmax)
    ax.set_ylim(0, ymax)
    ax.set_xlabel("Usual gap between this customer's orders (days)",
                  color=INK_2, fontsize=9.5)
    ax.set_ylabel(f"Days since last order (as of {DATA_END:%d %b %Y})",
                  color=INK_2, fontsize=9.5)
    ax.grid(color=GRID, linewidth=0.6, zorder=0)
    ax.tick_params(colors=MUTED, labelsize=8.5)
    for side in ["top", "right"]:
        ax.spines[side].set_visible(False)
    for side in ["left", "bottom"]:
        ax.spines[side].set_color(GRID)

    fig.suptitle("Regular customers who have gone quiet", x=0.02, ha="left",
                 fontsize=13, fontweight="bold", color=INK)
    fig.text(0.02, 0.925,
             f"Each dot is a customer with {MIN_ORDERS}+ orders, judged against "
             "their own ordering rhythm. Dot size = sales in the\n12 months "
             "before their last order (today's prices); labels show that value.",
             ha="left", va="top", fontsize=9, color=INK_2)
    handles = [plt.Line2D([], [], marker="o", linestyle="", markersize=8,
                          color=colors[s], label=names[s])
               for s in ["likely lost", "overdue", "active"]]
    handles.append(plt.Line2D([], [], marker="o", linestyle="", markersize=8,
                              markerfacecolor="none", markeredgecolor=MUTED,
                              label=names[SLOW_STATUS]))
    fig.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.06, 0.035),
               ncol=2, frameon=False, fontsize=8.5, labelcolor=INK_2)
    fig.text(0.02, 0.01, "Source: Northwind database. Data ends 6 May 1998.",
             fontsize=7.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.1, 1, 0.89))
    fig.savefig(out_path, facecolor=SURFACE)
    plt.close(fig)


def main():
    RESULTS.mkdir(exist_ok=True)
    tables = load_tables()
    stats = classify(customer_rhythm(build_order_lines(tables)))
    full, calls, calendar = call_list(stats, tables["customers"])

    if full["orders"].sum() != 830:
        raise ValueError("order count does not reconcile")

    full.round(2).to_csv(RESULTS / "q2_customer_rhythm.csv", index=False)
    cols = ["priority", "status", "CompanyName", "Country", "ContactName",
            "ContactTitle", "Phone", "last_order", "days_quiet",
            "usual_gap_days", "orders", "value_at_risk_usd", "check_back_by"]
    calls[cols].round(1).to_csv(RESULTS / "q2_call_list.csv", index=False)
    cal_cols = ["check_back_by", "CompanyName", "Country", "ContactName",
                "Phone", "last_order", "usual_gap_days", "orders",
                "value_at_risk_usd"]
    calendar[cal_cols].round(1).to_csv(
        RESULTS / "q2_check_back_calendar.csv", index=False)
    plot_rhythm(full, RESULTS / "q2_lost_customers.png")

    with pd.option_context("display.width", 250):
        print(calls[cols].round(0).to_string(index=False))
    print("\nFollow-up calendar (slow buyers):")
    print(calendar[cal_cols].round(0).to_string(index=False))
    print("\nStatus counts:", full["status"].value_counts().to_dict())
    print(f"Value at risk: likely lost ${calls.loc[calls.status=='likely lost','value_at_risk_usd'].sum():,.0f},"
          f" overdue ${calls.loc[calls.status=='overdue','value_at_risk_usd'].sum():,.0f}")


if __name__ == "__main__":
    main()
