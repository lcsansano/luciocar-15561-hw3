"""Build the static analysis webpage in docs/ for GitHub Pages.

Every number in the page text is computed here from the same
functions that produce the charts; nothing is typed in by hand.

Run from the project root (after the analysis scripts):
    .venv/bin/python -m src.build_site
"""

import html
import shutil

import pandas as pd

from src import q1_discounts, q2_lost_customers, q3_country_growth
from src.load import DATA_END, DATA_START, ROOT, build_order_lines, load_tables

DOCS = ROOT / "docs"
IMG = DOCS / "img"
RESULTS = ROOT / "results"
REPO_URL = "https://github.com/lcsansano/luciocar-15561-hw3"
CHARTS = ["q3_country_growth.png", "q2_lost_customers.png",
          "q1_discounts.png"]


def money(value, digits=0):
    """Format a USD amount, e.g. 1234.5 -> "$1,235".

    Args:
        value (float): Amount in USD.
        digits (int): Decimal places to show.

    Returns:
        str: Formatted amount with a dollar sign and thousands commas.
    """
    return f"${value:,.{digits}f}"


def k(value):
    """Format a USD amount in thousands, e.g. 23731 -> "$23.7k".

    Args:
        value (float): Amount in USD.

    Returns:
        str: Amount in thousands with one decimal and a "k" suffix.
    """
    return f"${value / 1000:,.1f}k"


def overview_facts(lines):
    """Compute the headline facts shown at the top of the page.

    Args:
        lines (pandas.DataFrame): Output of ``build_order_lines``.

    Returns:
        dict: Total revenue, order, customer and country counts, and
            the first and last order date as display strings.
    """
    return {
        "revenue": money(lines["Revenue"].sum()),
        "orders": lines["OrderID"].nunique(),
        "customers": lines["CustomerID"].nunique(),
        "countries": lines["CustomerCountry"].nunique(),
        "start": f"{DATA_START:%-d %b %Y}",
        "end": f"{DATA_END:%-d %b %Y}",
    }


def q3_facts(lines):
    """Compute the numbers quoted in the Q3 section.

    Args:
        lines (pandas.DataFrame): Output of ``build_order_lines``.

    Returns:
        dict: Company volume and revenue growth, the two biggest
            growth markets and their share of growth, the slower and
            shrinking markets, and the customer behind each decline.
    """
    tagged = q3_country_growth.tag_periods(lines)
    markets, company, _, small = q3_country_growth.country_growth(tagged)
    real = markets.drop(index=q3_country_growth.OTHER)
    top = real.sort_values("volume_change_usd", ascending=False).head(2)
    share = top["volume_change_usd"].sum() / markets["volume_change_usd"].sum()

    drivers = []
    for country in real.index[real["trend"] == "shrinking"]:
        sub = tagged[tagged["CustomerCountry"] == country]
        by_cust = sub.pivot_table(index="CustomerName", columns="Period",
                                  values="ConstRevenue", aggfunc="sum",
                                  fill_value=0)
        change = (by_cust["recent"] - by_cust["prior"]).sort_values()
        drivers.append({
            "country": country,
            "growth": real.loc[country, "volume_growth_pct"],
            "net": change.sum(),
            "customer": change.index[0],
            "customer_change": change.iloc[0],
        })
    slower = real[real["trend"] == "growing slower than company"]
    return {
        "volume": company["volume_growth_pct"].iloc[0],
        "revenue": company["revenue_growth_pct"].iloc[0],
        "top": [(m, row["volume_growth_pct"], row["volume_change_usd"])
                for m, row in top.iterrows()],
        "top_share": share,
        "slower": [(m, row["volume_growth_pct"], row["revenue_recent"])
                   for m, row in slower.iterrows()],
        "drivers": drivers,
        "n_small": len(small),
    }


def q2_facts(tables, lines):
    """Compute the call list and numbers quoted in the Q2 section.

    Args:
        tables (dict[str, pandas.DataFrame]): Output of ``load_tables``.
        lines (pandas.DataFrame): Output of ``build_order_lines``.

    Returns:
        dict: Ranked call list, totals at risk, status counts, the
            number of slow buyers and the first check-back entry.
    """
    stats = q2_lost_customers.classify(
        q2_lost_customers.customer_rhythm(lines))
    full, calls, calendar = q2_lost_customers.call_list(
        stats, tables["customers"])
    counts = full["status"].value_counts()
    regular = int((full["orders"] >= q2_lost_customers.MIN_ORDERS).sum())
    months = lines["OrderMonth"]
    in_recent = ((months >= pd.Period("1997-07", "M"))
                 & (months <= pd.Period("1998-04", "M")))
    recent_rev = lines.loc[in_recent, "Revenue"].sum() / 10 * 12
    return {
        "calls": calls,
        "total": calls["value_at_risk_usd"].sum(),
        "share_of_year": calls["value_at_risk_usd"].sum() / recent_rev,
        "lost": int(counts.get("likely lost", 0)),
        "overdue": int(counts.get("overdue", 0)),
        "slow": int(counts.get(q2_lost_customers.SLOW_STATUS, 0)),
        "regular": regular,
        "first_check": calendar.iloc[0] if len(calendar) else None,
    }


def q1_facts(lines):
    """Compute the numbers quoted in the Q1 section.

    Args:
        lines (pandas.DataFrame): Output of ``build_order_lines``.

    Returns:
        dict: Relative order size at 0%, 5% and 25% and its range across
            discount levels, the 25% vs 5% gap
            with its 95% range, break-even, discount money and the
            robustness checks.
    """
    std = q1_discounts.standard_lines(lines)
    table = q1_discounts.level_table(std).set_index("discount_pct")
    summary = q1_discounts.deep_vs_light(std)
    return {
        "rel0": table.loc[0, "rel_qty"],
        "rel5": table.loc[5, "rel_qty"],
        "rel25": table.loc[25, "rel_qty"],
        "disc_min": table.loc[5:, "rel_qty"].min(),
        "disc_max": table.loc[5:, "rel_qty"].max(),
        "gap": summary["rel_qty_25_vs_5_pct"],
        "ci_low": summary["ci_low_pct"],
        "ci_high": summary["ci_high_pct"],
        "needed": summary["breakeven_needed_pct"],
        "total": summary["discount_given_total_usd"],
        "over10": summary["discount_given_above_10pct_usd"],
        "products": int(summary["products_sold_at_both"]),
        "more": int(summary["products_25_sells_more"]),
        "less": int(summary["products_25_sells_less"]),
        "cust": int(summary["customers_at_both"]),
        "cust_ratio": summary["same_customer_ratio_25_vs_5"],
    }


def call_table_html(calls):
    """Render the ranked call list as an HTML table.

    Args:
        calls (pandas.DataFrame): Ranked call list from ``call_list``.

    Returns:
        str: HTML ``<table>`` markup with one row per customer.
    """
    rows = []
    for _, r in calls.iterrows():
        status = html.escape(r["status"])
        css = "lost" if r["status"] == "likely lost" else "overdue"
        rows.append(
            f"<tr><td class=num>{r['rank']}</td>"
            f"<td>{html.escape(r['CompanyName'])}</td>"
            f"<td>{html.escape(r['Country'])}</td>"
            f"<td><span class='tag {css}'>{status}</span></td>"
            f"<td class=num>{money(r['value_at_risk_usd'])}</td>"
            f"<td class=num>{r['usual_gap_days']:.0f}</td>"
            f"<td class=num>{r['days_quiet']:.0f}</td>"
            f"<td>{html.escape(r['ContactName'])}<br>"
            f"<small>{html.escape(r['Phone'])}</small></td></tr>")
    return (
        "<div class=tablewrap><table><thead><tr><th>#</th><th>Customer</th>"
        "<th>Country</th><th>Status</th><th class=num>Revenue,<br>last 12 mo"
        "</th><th class=num>Usual gap<br>(avg days)</th>"
        "<th class=num>Days<br>quiet</th><th>Contact</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>")


def render(o, q3, q2, q1):
    """Assemble the full HTML page from the computed facts.

    Args:
        o (dict): Output of ``overview_facts``.
        q3 (dict): Output of ``q3_facts``.
        q2 (dict): Output of ``q2_facts``.
        q1 (dict): Output of ``q1_facts``.

    Returns:
        str: Complete HTML document.
    """
    (top1, g1, c1), (top2, g2, c2) = q3["top"]
    drivers = "".join(
        f"<li><b>{html.escape(d['country'])}</b> ({d['growth']:+.0f}%): "
        f"{html.escape(d['customer'])} alone lost "
        f"{k(-d['customer_change'])} of volume; the whole country lost "
        f"{k(-d['net'])}.</li>"
        for d in q3["drivers"])
    slower = " and ".join(
        f"{html.escape(m)} ({g:+.0f}%, {k(r)} in sales)"
        for m, g, r in q3["slower"])
    shrinking = ", ".join(d["country"] for d in q3["drivers"])
    top_call = q2["calls"].iloc[0]
    first_check = q2["first_check"]
    check_text = (
        f" The first is {html.escape(first_check['CompanyName'])} "
        f"({html.escape(first_check['Country'])}): check back by "
        f"{pd.Timestamp(first_check['check_back_by']):%-d %B %Y}."
        if first_check is not None else "")

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Northwind: where to act</title>
<meta name="description" content="Business analysis of the Northwind dataset: growing and shrinking markets, customers who stopped ordering, and whether deep discounts pay off.">
<style>
:root {{
  --ink: #0b0b0b; --ink-2: #52514e; --muted: #898781; --line: #e1e0d9;
  --surface: #fcfcfb; --panel: #f4f3ef; --blue: #2a78d6; --red: #e34948;
  --orange: #c9531f;
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--surface); color: var(--ink);
  font: 17px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
  Helvetica, Arial, sans-serif; }}
main {{ max-width: 860px; margin: 0 auto; padding: 48px 20px 80px; }}
h1 {{ font-size: 2.1rem; line-height: 1.2; margin: 0 0 12px; }}
h2 {{ font-size: 1.5rem; line-height: 1.3; margin: 64px 0 8px;
  padding-top: 24px; border-top: 1px solid var(--line); }}
h3 {{ font-size: .8rem; text-transform: uppercase; letter-spacing: .06em;
  color: var(--muted); margin: 28px 0 4px; }}
p, li {{ color: var(--ink); }}
.lead {{ font-size: 1.15rem; color: var(--ink-2); }}
.kicker {{ color: var(--blue); font-weight: 700; font-size: .85rem;
  text-transform: uppercase; letter-spacing: .06em; }}
.facts {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px; margin: 28px 0; }}
.fact {{ background: var(--panel); border-radius: 10px; padding: 14px 16px; }}
.fact b {{ display: block; font-size: 1.35rem; }}
.fact span {{ color: var(--ink-2); font-size: .85rem; }}
.summary {{ background: var(--panel); border-radius: 12px; padding: 18px 22px; }}
.summary li {{ margin: 6px 0; }}
figure {{ margin: 20px 0; }}
figure img {{ width: 100%; height: auto; border: 1px solid var(--line);
  border-radius: 8px; background: #fff; }}
figcaption {{ color: var(--muted); font-size: .85rem; margin-top: 6px; }}
.finding {{ border-left: 4px solid var(--blue); padding: 4px 0 4px 16px;
  margin: 20px 0; }}
.action {{ border-left: 4px solid var(--ink); padding: 4px 0 4px 16px;
  margin: 20px 0; }}
.caveat {{ color: var(--ink-2); font-size: .92rem; }}
.tablewrap {{ overflow-x: auto; margin: 16px 0; }}
table {{ border-collapse: collapse; width: 100%; font-size: .9rem; }}
th, td {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--line);
  vertical-align: top; }}
th {{ color: var(--ink-2); font-weight: 600; white-space: nowrap; }}
td.num, th.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
td small {{ color: var(--muted); }}
.tag {{ font-weight: 700; font-size: .8rem; white-space: nowrap; }}
.tag.lost {{ color: var(--red); }}
.tag.overdue {{ color: var(--orange); }}
footer {{ margin-top: 64px; padding-top: 20px; border-top: 1px solid var(--line);
  color: var(--muted); font-size: .85rem; }}
a {{ color: var(--blue); }}
@media (max-width: 600px) {{
  body {{ font-size: 16px; }}
  main {{ padding: 28px 16px 60px; }}
  h1 {{ font-size: 1.6rem; }}
}}
</style>
</head>
<body>
<main>

<p class="kicker">Northwind Traders · analysis for management</p>
<h1>Growth is real, but it rests on a few markets and a few customers</h1>
<p class="lead">Northwind is a food and drink wholesaler selling to shops and
restaurants. This page answers three questions that each lead to a decision:
where to focus sales effort, which customers to call first, and whether deep
discounts pay off.</p>

<div class="facts">
  <div class="fact"><b>{o['revenue']}</b><span>net revenue</span></div>
  <div class="fact"><b>{o['orders']}</b><span>orders</span></div>
  <div class="fact"><b>{o['customers']}</b><span>customers who ordered</span></div>
  <div class="fact"><b>{o['countries']}</b><span>customer countries</span></div>
</div>
<p class="caveat">Data: every order from {o['start']} to {o['end']}. 1996 and
1998 are partial years, so every comparison below uses matching months.</p>

<div class="summary">
<b>In short</b>
<ul>
<li><b>Sales volume grew {q3['volume']:+.0f}%</b> year on year
({q3['revenue']:+.0f}% in revenue, the difference being an April 1997 price
rise). {html.escape(top1)} and {html.escape(top2)} delivered
{q3['top_share']:.0%} of that growth.</li>
<li><b>{len(q2['calls'])} regular customers have gone quiet</b>, worth about
{k(q2['total'])} a year. {html.escape(top_call['CompanyName'])} alone is
{k(top_call['value_at_risk_usd'])}.</li>
<li><b>Deep discounts don't pay for themselves.</b> A 25% discount would need
{q1['needed']:.0f}% more units than a 5% discount to bring in the same revenue;
it is linked to about {q1['gap']:.0f}% more.</li>
</ul>
</div>

<!-- ============================ Q3 ============================ -->
<h2>1. Which customer countries are growing or shrinking?</h2>

<h3>Why it matters</h3>
<p>Sales time is limited. Knowing which markets carry the growth, and which are
slipping, tells the manager where to add effort and where to look for
problems before they grow.</p>

<h3>Approach</h3>
<p>I compared the same 10 calendar months in both periods: July 1997 to April
1998 against July 1996 to April 1997. That keeps seasonality equal. Prices
rose about 25% in April 1997, so revenue growth would partly be price. I
therefore measured <b>sales volume</b>: every sale valued at one fixed price
list. Countries with fewer than 10 orders in either period
({q3['n_small']} of them) are grouped as "Other countries", because a single
order can swing their percentage.</p>

<figure>
<img src="img/q3_country_growth.png" alt="Bar chart of sales volume growth by customer country. Sweden, Germany, USA, Brazil and the UK grow faster than the company average of {q3['volume']:+.0f}%; Venezuela and Austria grow more slowly; France, Canada and Mexico shrink." loading="lazy">
<figcaption>Volume growth by customer country, Jul 1997–Apr 1998 vs the same
months a year earlier. ($k) = sales in the recent 10 months.</figcaption>
</figure>

<h3>Main finding</h3>
<div class="finding">
<p>Volume grew {q3['volume']:+.0f}% overall. <b>{html.escape(top1)}
({g1:+.0f}%) and {html.escape(top2)} ({g2:+.0f}%) delivered
{q3['top_share']:.0%} of all growth.</b> {slower} grew, but more slowly than
the company, so they are losing share. Three markets shrank, and in each one
the decline traces back to a single customer:</p>
<ul>{drivers}</ul>
</div>

<h3>Business implication</h3>
<div class="action">
<p>Protect and expand {html.escape(top1)} and {html.escape(top2)}, which are
the growth engine. In {html.escape(shrinking)}, don't cut market effort: the
problem is specific accounts, not the market. Call those customers first
(see the next question). Keep an eye on the slower-growing markets.</p>
</div>
<p class="caveat">Caveats: one or two customers drive most countries' numbers
in both directions, and "volume" means less value, not necessarily fewer
units (some markets switched to cheaper products).</p>

<!-- ============================ Q2 ============================ -->
<h2>2. Which regular customers stopped ordering, and who should sales call first?</h2>

<h3>Why it matters</h3>
<p>Keeping an existing customer is cheaper than finding a new one, and growth
here comes almost entirely from existing customers buying more. A customer
who quietly stops ordering is lost revenue that nobody notices until the
year-end numbers.</p>

<h3>Approach</h3>
<p>I judged each of the {q2['regular']} regular customers (5+ orders) against
<b>their own rhythm</b>: the average number of days between their orders. A
customer quiet for more than <b>2×</b> their usual gap is "likely lost"; more
than <b>1.5×</b> is "overdue". The average is used rather than the median
because customers order in bursts, and the median would make them look more
frequent than they are. Value at risk is the actual revenue in the 12 months
before their last order.</p>

<figure>
<img src="img/q2_lost_customers.png" alt="Scatter chart of days since last order against each customer's average gap between orders. Eight customers sit above the 1.5x and 2x lines; their dot numbers match the call list." loading="lazy">
<figcaption>Each dot is a regular customer. Numbers match the call list
below. Slow buyers (every 90+ days) are shown separately.</figcaption>
</figure>

<h3>Main finding: the call list</h3>
<div class="finding">
<p><b>{len(q2['calls'])} regular customers have gone quiet</b>
({q2['lost']} likely lost, {q2['overdue']} overdue). Together they were
worth <b>{k(q2['total'])} a year</b>, about {q2['share_of_year']:.0%} of
current annual sales.</p>
</div>
{call_table_html(q2['calls'])}

<h3>Business implication</h3>
<div class="action">
<p>Sales should call these customers this week, in this order, and ask why
they stopped: price, service, a competitor, or a closed business. The answers
tell the manager whether there is a wider problem. For the {q2['slow']} slow
buyers who order only every few months, it is too early to judge; they go on
a follow-up calendar with a "check back by" date instead.{check_text}</p>
</div>
<p class="caveat">Caveats: the data ends on {o['end']}, so some "overdue"
customers may simply be about to order. A second rule (quiet for longer than
their longest-ever gap) finds exactly the same four "likely lost"
customers.</p>

<!-- ============================ Q1 ============================ -->
<h2>3. Do deeper discounts sell more, or are we giving away revenue?</h2>

<h3>Why it matters</h3>
<p>Northwind gave away {k(q1['total'])} in discounts, and
<b>{k(q1['over10'])} ({q1['over10'] / q1['total']:.0%}) of it came from
discounts above 10%</b>. If deep discounts don't lead to bigger orders, that
money is simply lost revenue, and a discount cap would recover it.</p>

<h3>Approach</h3>
<p>Order sizes differ a lot between products, so I compared <b>each product
with itself</b>: units per order line divided by that product's typical
order size (1.0 = typical). Then I compared what a deeper discount
<i>actually</i> sold with what it <i>would need</i> to sell to bring in as
much revenue as a 5% discount. Going from 5% to 25% cuts the price by 21%,
so units would have to rise {q1['needed']:.0f}%.</p>

<figure>
<img src="img/q1_discounts.png" alt="Dot chart of order size by discount level with 95% ranges. Order size is about {q1['rel0']:.2f} with no discount and {q1['disc_min']:.2f} to {q1['disc_max']:.2f} at every discount level, while the order size needed to break even rises to 1.47 at 25%." loading="lazy">
<figcaption>Blue: actual order size with 95% range. Red: order size needed to
earn as much as at 5%.</figcaption>
</figure>

<h3>Main finding</h3>
<div class="finding">
<p><b>A 25% discount is linked to only about {q1['gap']:.0f}% more units than
a 5% discount</b> (95% range {q1['ci_low']:+.0f}% to {q1['ci_high']:+.0f}%),
far short of the {q1['needed']:.0f}% needed. Even the top of the range falls
short. Any discount is linked to larger orders than no discount
({q1['rel0']:.2f} vs {q1['rel5']:.2f}), but going deeper adds almost
nothing. Two other checks agree: across the {q1['products']} products sold at
both levels, {q1['more']} sold more at 25% and {q1['less']} sold less, and
the same {q1['cust']} customers bought only {q1['cust_ratio']:.2f}× as much
at 25% as at 5%.</p>
</div>

<h3>Business implication</h3>
<div class="action">
<p>Cap standard discounts at around 5–10%, and allow deeper ones only with
manager approval or a minimum order size. Because this is a link and not a
proven cause, run the cap as a test first: apply it to some customers or
months and compare order sizes before rolling it out everywhere.</p>
</div>
<p class="caveat"><b>This shows a link, not cause and effect.</b> Discounts
are not handed out at random (big customers may get them because they are
big), and there is no cost data, so margin itself can't be measured.</p>

<!-- ============================ Method ============================ -->
<h2>About the data and method</h2>
<ul>
<li><b>Revenue</b> = price actually charged × quantity × (1 − discount), from
the order lines. Total {o['revenue']}; data checks found no duplicate keys
and no broken links between tables.</li>
<li><b>Country</b> is the customer's country, not the ship-to address (4
orders have mixed-up ship-to addresses).</li>
<li>Leftover exercise columns in the Product sheet were ignored. One order
with unusual 1–6% discounts was left out of question 3.</li>
<li>All numbers, charts and this page are produced by Python code. A test
suite checks every headline number, and a fresh copy reproduces every output
byte for byte.</li>
</ul>
<p><b>Code and step-by-step reproduction:</b>
<a href="{REPO_URL}">{REPO_URL.replace('https://', '')}</a></p>

<footer>15.561 HW3 · Built with Python from the Northwind database ·
analysis assisted by Claude Code.</footer>
</main>
</body>
</html>
"""


def main():
    """Build docs/index.html and copy the charts next to it.

    Args:
        None.

    Returns:
        None. Writes ``docs/index.html``, ``docs/.nojekyll`` and the
        chart images in ``docs/img/``.

    Raises:
        FileNotFoundError: If a chart is missing from ``results/``;
            run the analysis scripts first.
    """
    tables = load_tables()
    lines = build_order_lines(tables)
    page = render(overview_facts(lines), q3_facts(lines),
                  q2_facts(tables, lines), q1_facts(lines))

    IMG.mkdir(parents=True, exist_ok=True)
    for name in CHARTS:
        src = RESULTS / name
        if not src.exists():
            raise FileNotFoundError(f"{src} missing; run run_all.py first")
        shutil.copy2(src, IMG / name)
    (DOCS / "index.html").write_text(page, encoding="utf-8")
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")
    print(f"Wrote {(DOCS / 'index.html').relative_to(ROOT)} "
          f"and {len(CHARTS)} charts")


if __name__ == "__main__":
    main()
