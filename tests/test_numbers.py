"""The headline numbers quoted for each question."""

import pytest

from src import q1_discounts, q2_lost_customers, q3_country_growth


# ---------- Q3: country volume growth ----------

@pytest.fixture(scope="module")
def q3(lines):
    """Run the Q3 pipeline once for this module.

    Args:
        lines (pandas.DataFrame): ``lines`` fixture.

    Returns:
        tuple: Tagged lines, then the four items returned by
            ``country_growth``.
    """
    tagged = q3_country_growth.tag_periods(lines)
    markets, company, detail, small = q3_country_growth.country_growth(tagged)
    return tagged, markets, company, detail, small


def test_q3_periods_are_matching_10_months(q3):
    """Check that both periods cover exactly 10 months.

    Args:
        q3 (tuple): ``q3`` fixture (tagged lines, markets, company,
            all countries, small-country names).

    Returns:
        None.
    """
    tagged = q3[0]
    for period in ["prior", "recent"]:
        months = tagged.loc[tagged["Period"] == period, "OrderMonth"].nunique()
        assert months == 10


def test_q3_company_growth(q3):
    """Check company volume and revenue growth.

    Args:
        q3 (tuple): ``q3`` fixture (tagged lines, markets, company,
            all countries, small-country names).

    Returns:
        None.
    """
    company = q3[2]
    assert company["volume_growth_pct"].iloc[0] == pytest.approx(55.5, abs=0.1)
    assert company["revenue_growth_pct"].iloc[0] == pytest.approx(89.8, abs=0.1)


def test_q3_markets_add_up_to_company(q3):
    """Check that market totals add up to the company total.

    Args:
        q3 (tuple): ``q3`` fixture (tagged lines, markets, company,
            all countries, small-country names).

    Returns:
        None.
    """
    _, markets, company, _, _ = q3
    q3_country_growth.check_totals(markets, company)  # raises if not
    assert markets["volume_change_usd"].sum() == pytest.approx(
        company["volume_change_usd"].iloc[0], abs=0.01)


def test_q3_volume_equals_revenue_in_recent_period(q3):
    """Check that recent volume equals recent revenue.

    Args:
        q3 (tuple): ``q3`` fixture (tagged lines, markets, company,
            all countries, small-country names).

    Returns:
        None.
    """
    company = q3[2]
    assert company["volume_usd_recent"].iloc[0] == pytest.approx(
        company["revenue_recent"].iloc[0], abs=0.01)


def test_q3_shrinking_markets(q3):
    """Check which markets are labelled shrinking.

    Args:
        q3 (tuple): ``q3`` fixture (tagged lines, markets, company,
            all countries, small-country names).

    Returns:
        None.
    """
    markets = q3[1]
    shrinking = set(markets.index[markets["trend"] == "shrinking"])
    assert shrinking == {"France", "Canada", "Mexico"}


def test_q3_small_countries_grouped(q3):
    """Check that the 11 small countries are grouped into Other.

    Args:
        q3 (tuple): ``q3`` fixture (tagged lines, markets, company,
            all countries, small-country names).

    Returns:
        None.
    """
    markets, small = q3[1], q3[4]
    assert len(small) == 11
    assert not set(small) & set(markets.index)
    assert q3_country_growth.OTHER in markets.index


# ---------- Q2: lost customers ----------

@pytest.fixture(scope="module")
def q2(tables, lines):
    """Run the Q2 pipeline once for this module.

    Args:
        tables (dict[str, pandas.DataFrame]): ``tables`` fixture.
        lines (pandas.DataFrame): ``lines`` fixture.

    Returns:
        tuple: The three items returned by ``call_list``.
    """
    stats = q2_lost_customers.classify(q2_lost_customers.customer_rhythm(lines))
    return q2_lost_customers.call_list(stats, tables["customers"])


def test_q2_call_list(q2):
    """Check the call list's size, order, top customer and total.

    Args:
        q2 (tuple): ``q2`` fixture (all customers, call list,
            calendar).

    Returns:
        None.
    """
    _, calls, _ = q2
    assert len(calls) == 8
    assert calls.iloc[0]["CompanyName"] == "Mère Paillarde"
    assert calls["value_at_risk_usd"].is_monotonic_decreasing
    assert calls["value_at_risk_usd"].sum() == pytest.approx(89_548, abs=1)


def test_q2_status_counts(q2):
    """Check how many customers get each status.

    Args:
        q2 (tuple): ``q2`` fixture (all customers, call list,
            calendar).

    Returns:
        None.
    """
    full = q2[0]
    assert full["status"].value_counts().to_dict() == {
        "active": 48, "not regular (<5 orders)": 17,
        "too early to tell (slow buyer)": 16, "overdue": 4, "likely lost": 4}


def test_q2_reconciles_with_orders(q2, lines):
    """Check that customer totals match orders and revenue.

    Args:
        q2 (tuple): ``q2`` fixture (all customers, call list,
            calendar).
        lines (pandas.DataFrame): ``lines`` fixture.

    Returns:
        None.
    """
    full = q2[0]
    assert full["orders"].sum() == 830
    assert full["lifetime_revenue_usd"].sum() == pytest.approx(
        lines["Revenue"].sum(), abs=0.01)


def test_q2_usual_gap_is_average(q2):
    """Check that the usual gap is the average, not the median.

    Args:
        q2 (tuple): ``q2`` fixture (all customers, call list,
            calendar).

    Returns:
        None.
    """
    full = q2[0]
    mere = full.set_index("CompanyName").loc["Mère Paillarde"]
    assert mere["usual_gap_days"] == pytest.approx(31.5, abs=0.1)  # 378 / 12
    assert mere["median_gap_days"] == pytest.approx(17.5, abs=0.1)


def test_q2_likely_lost_also_past_longest_gap(q2, orders):
    """Check that the longest-gap rule finds the same lost customers.

    Args:
        q2 (tuple): ``q2`` fixture (all customers, call list,
            calendar).
        orders (pandas.DataFrame): ``orders`` fixture.

    Returns:
        None.
    """
    full = q2[0]
    longest = (orders.sort_values("OrderDate").groupby("CustomerID")["OrderDate"]
               .apply(lambda d: d.diff().dt.days.max()))
    regular = full[full["orders"] >= q2_lost_customers.MIN_ORDERS].set_index("CustomerID")
    past = set(regular.index[regular["days_quiet"] > longest[regular.index]])
    lost = set(regular.index[regular["status"] == "likely lost"])
    assert past == lost


# ---------- Q1: discounts ----------

@pytest.fixture(scope="module")
def q1(lines):
    """Run the Q1 pipeline once for this module.

    Args:
        lines (pandas.DataFrame): ``lines`` fixture.

    Returns:
        tuple: Output of ``level_table`` and of ``deep_vs_light``.
    """
    std = q1_discounts.standard_lines(lines)
    return q1_discounts.level_table(std), q1_discounts.deep_vs_light(std)


def test_q1_headline(q1):
    """Check the 25% vs 5% gap against break-even.

    Args:
        q1 (tuple): ``q1`` fixture (level table, summary).

    Returns:
        None.
    """
    _, summary = q1
    assert summary["rel_qty_25_vs_5_pct"] == pytest.approx(2.7, abs=0.1)
    assert summary["breakeven_needed_pct"] == pytest.approx(26.67, abs=0.01)
    assert summary["ci_high_pct"] < summary["breakeven_needed_pct"]


def test_q1_discount_money(q1):
    """Check total discount given and the share above 10%.

    Args:
        q1 (tuple): ``q1`` fixture (level table, summary).

    Returns:
        None.
    """
    _, summary = q1
    assert summary["discount_given_total_usd"] == pytest.approx(88_653, abs=1)
    assert summary["discount_given_above_10pct_usd"] == pytest.approx(70_717, abs=1)


def test_q1_robustness_checks(q1):
    """Check the per-product and same-customer comparisons.

    Args:
        q1 (tuple): ``q1`` fixture (level table, summary).

    Returns:
        None.
    """
    _, summary = q1
    assert summary["products_sold_at_both"] == 55
    assert summary["products_25_sells_more"] == 30
    assert summary["same_customer_ratio_25_vs_5"] == pytest.approx(1.08, abs=0.01)


def test_q1_levels(q1):
    """Check the discount levels and line count.

    Args:
        q1 (tuple): ``q1`` fixture (level table, summary).

    Returns:
        None.
    """
    table, _ = q1
    assert list(table["discount_pct"]) == [0, 5, 10, 15, 20, 25]
    assert table["lines"].sum() == 2147  # 2155 minus order 11077's 8 lines
