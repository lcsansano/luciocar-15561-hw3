# Northwind: AI-Assisted Business Data Analysis (15.561 HW3)

Analysis of the Northwind trading company dataset. Python code here generates every number, chart and table on the project webpage.

> Status: setup only. The analysis code, webpage and full reproduction steps will be added as the work progresses.

## Repository contents

| Path | Contents |
|---|---|
| `data/Northwind Database.xlsx` | The source dataset (8 sheets: Orders, Orders Details, Product, Customers, Suppliers, Employees, Categories, Shippers). |
| `data/*.csv` | One CSV per sheet, exported unchanged by `scripts/01_data_check.py` (only a fully empty, unnamed Product column is dropped). |
| `src/load.py` | Shared loader. It reads the CSVs, applies the cleaning rules (rounded discounts, Product exercise columns dropped), and joins order lines with orders, customers, products, categories and employees. It computes `Revenue = UnitPrice × Quantity × (1 − Discount)` and builds a one-row-per-order table. It stops with an error if row counts, joins or the revenue total ($1,265,793.04) don't match. |
| `scripts/q1_discount_check.py` | Within-product check: do 25% discounts sell more units than 5%? |
| `scripts/01_data_check.py` | Profiles every sheet and checks keys, joins, missing values and oddities, then writes the CSVs. |
| `requirements.txt` | Pinned Python packages. |
| `.claude/skills/python-docstrings/SKILL.md` | The course-provided docstring skill, installed for Claude Code and used to document all Python code. |
| `CLAUDE.md` | Working rules given to the AI coding agent for this project. |

## Data notes
- Orders span 4 Jul 1996 – 6 May 1998, so 1996 and 1998 are partial years.
- Dates in the workbook are stored as Excel serial numbers (origin 1899-12-30).
- Revenue per order line = `UnitPrice × Quantity × (1 − Discount)` from the *Orders Details* sheet.

## Reproducing the results
Requires Python 3.11+.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/01_data_check.py   # data checks + CSV export
.venv/bin/python -m src.load                # build and verify the joined tables
```

Run all commands from the repository root.

_The analysis scripts and the webpage build will be added here._
