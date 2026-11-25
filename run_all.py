"""Regenerate every CSV, table and chart from the Northwind workbook.

Run from the project root:
    python run_all.py
"""

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent

STEPS = [
    ("Data check + CSV export", ["scripts/01_data_check.py"]),
    ("Shared loader self-check", ["-m", "src.load"]),
    ("Q3 country volume growth", ["-m", "src.q3_country_growth"]),
    ("Q2 lost customers", ["-m", "src.q2_lost_customers"]),
    ("Q1 discounts", ["-m", "src.q1_discounts"]),
]


def run_step(name, args):
    """Run one pipeline step with the current Python interpreter.

    Args:
        name (str): Label printed before the step runs.
        args (list[str]): Arguments after the interpreter, e.g. a
            script path or ``-m`` plus a module name.

    Returns:
        None.

    Raises:
        SystemExit: If the step exits with a non-zero code; the
            remaining steps are not run.
    """
    print(f"==> {name}", flush=True)
    start = time.time()
    result = subprocess.run([sys.executable, *args], cwd=ROOT,
                            stdout=subprocess.DEVNULL)
    if result.returncode != 0:
        raise SystemExit(f"Step failed: {name} (exit {result.returncode})")
    print(f"    done in {time.time() - start:.1f}s", flush=True)


def main():
    """Run all pipeline steps in order and list the outputs.

    Args:
        None.

    Returns:
        None. Prints each step and the files in ``results/``.
    """
    for name, args in STEPS:
        run_step(name, args)
    print("\nOutputs in results/:")
    for path in sorted((ROOT / "results").iterdir()):
        print(f"  {path.name}")


if __name__ == "__main__":
    main()
