"""Every script runs end to end and writes its outputs."""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

SCRIPTS = [
    (["scripts/01_data_check.py"], ["data/orders.csv", "data/order_details.csv"]),
    (["-m", "src.load"], []),
    (["-m", "src.q3_country_growth"],
     ["results/q3_country_growth.csv", "results/q3_country_growth.png"]),
    (["-m", "src.q2_lost_customers"],
     ["results/q2_call_list.csv", "results/q2_call_list.png",
      "results/q2_lost_customers.png", "results/q2_check_back_calendar.csv"]),
    (["-m", "src.q1_discounts"],
     ["results/q1_discount_levels.csv", "results/q1_discounts.png"]),
    (["-m", "src.build_site"],
     ["docs/index.html", "docs/img/q3_country_growth.png",
      "docs/img/q2_lost_customers.png", "docs/img/q1_discounts.png"]),
    (["run_all.py"], ["results/q1_summary.csv", "results/q2_call_list.png",
                      "results/q3_country_growth.png", "docs/index.html"]),
]


@pytest.mark.parametrize("args,outputs", SCRIPTS, ids=lambda v: " ".join(v)
                         if isinstance(v, list) and v and v[0] != "results" else None)
def test_script_runs(args, outputs):
    """Run one script and check that it writes its outputs.

    Args:
        args (list[str]): Arguments after the Python interpreter.
        outputs (list[str]): Files, relative to the project root, that
            must exist and be non-empty afterwards.

    Returns:
        None.
    """
    result = subprocess.run([sys.executable, *args], cwd=ROOT,
                            capture_output=True, text=True, timeout=300)
    assert result.returncode == 0, result.stderr[-2000:]
    for out in outputs:
        path = ROOT / out
        assert path.exists() and path.stat().st_size > 0, out
