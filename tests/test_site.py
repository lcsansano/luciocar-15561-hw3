"""The webpage: built from the data, complete and with correct numbers."""

import re

import pytest

from src import build_site


@pytest.fixture(scope="module")
def page(tables, lines):
    """Render the webpage once for this module.

    Args:
        tables (dict[str, pandas.DataFrame]): ``tables`` fixture.
        lines (pandas.DataFrame): ``lines`` fixture.

    Returns:
        str: Full HTML of the page.
    """
    return build_site.render(build_site.overview_facts(lines),
                             build_site.q3_facts(lines),
                             build_site.q2_facts(tables, lines),
                             build_site.q1_facts(lines))


def test_headline_numbers_on_page(page):
    """Check that the key numbers appear in the page text.

    Args:
        page (str): ``page`` fixture.

    Returns:
        None.
    """
    for text in ["$1,265,793", "+56%", "+90%", "$89.5k", "27%",
                 "Mère Paillarde", "$70.7k"]:
        assert text in page, text


def test_every_question_has_all_parts(page):
    """Check each question has why, approach, chart, finding, action.

    Args:
        page (str): ``page`` fixture.

    Returns:
        None.
    """
    sections = page.split("<h2>")[1:4]
    assert len(sections) == 3
    for sec in sections:
        for part in ["Why it matters", "Approach", "<img ",
                     "Main finding", "Business implication"]:
            assert part in sec, part


def test_no_broken_values(page):
    """Check that no missing or malformed values leaked into the page.

    Args:
        page (str): ``page`` fixture.

    Returns:
        None.
    """
    body = re.sub(r"<style>.*?</style>", " ", page, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", body)
    for bad in [" nan", "None", "$-", "{", "}"]:
        assert bad not in text, bad


def test_call_list_table(page):
    """Check that the call list table has one row per customer.

    Args:
        page (str): ``page`` fixture.

    Returns:
        None.
    """
    assert page.count("<tr><td class=num>") == 8
