# Northwind: AI-Assisted Business Data Analysis (15.561 HW3)

Business analysis of the Northwind trading company, a fictional food and drink wholesaler. Data runs from July 1996 to May 1998.

**Webpage with the findings: https://lcsansano.github.io/luciocar-15561-hw3/**

Every number, chart and table in the analysis, including the webpage itself, is produced by the Python code in this repository from one input file, `data/Northwind Database.xlsx`. Nothing is typed in by hand.

## Business questions

| # | Question | Decision it informs | Main output |
|---|---|---|---|
| Q3 | Which customer countries are growing or shrinking? | Where to focus sales effort | `results/q3_country_growth.png` |
| Q2 | Which regular customers stopped ordering, and who should sales call first? | A ranked win-back call list | `results/q2_call_list.png`, `results/q2_lost_customers.png` |
| Q1 | Do deeper discounts sell more, or are we giving away revenue? | Whether to cap discounts | `results/q1_discounts.png` |

The webpage presents each question with why it matters, the approach, a chart, the main finding and the business implication.

---

## Reproduce everything, step by step

You need **Python 3.11 or newer** (tested with 3.13.1) and about 150 MB of disk space for the packages. Nothing else is required: no database and no account.

### 1. Get the code

Either clone the repository:

```bash
git clone https://github.com/lcsansano/luciocar-15561-hw3.git
cd luciocar-15561-hw3
```

Or download the ZIP: on the GitHub page, click **Code → Download ZIP**, unzip it, and open a terminal in the unzipped folder.

**Run every command below from this folder** (the one that contains `run_all.py`).

### 2. Create a virtual environment and install the pinned packages

macOS / Linux:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Windows (PowerShell):

```powershell
py -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

This installs the exact versions in `requirements.txt`: pandas, openpyxl, matplotlib and pytest.

### 3. Run the whole analysis

macOS / Linux:

```bash
.venv/bin/python run_all.py
```

Windows: `.venv\Scripts\python run_all.py`

It takes about 15 seconds the first time (Python and matplotlib set up caches), then about 5 seconds. It runs these 6 steps in order and stops at the first error:

| Step | Command it runs | What it does | Writes |
|---|---|---|---|
| 1 | `python scripts/01_data_check.py` | Profiles every sheet, checks keys, joins and oddities, and exports each sheet to CSV | `data/*.csv` |
| 2 | `python -m src.load` | Builds the joined order-line table and checks row counts, joins and total revenue ($1,265,793.04) | nothing (it's a check) |
| 3 | `python -m src.q3_country_growth` | Q3: volume growth by country | `results/q3_*` |
| 4 | `python -m src.q2_lost_customers` | Q2: lost-customer call list and follow-up calendar | `results/q2_*` |
| 5 | `python -m src.q1_discounts` | Q1: order size by discount level vs break-even | `results/q1_*` |
| 6 | `python -m src.build_site` | Builds the webpage: all text numbers are computed, and the charts are copied | `docs/index.html`, `docs/img/` |

You can also run any single step on its own with the command in the table, prefixed with `.venv/bin/`. For example: `.venv/bin/python -m src.q2_lost_customers`. Steps 3–5 only need the CSVs from step 1, and those are already included in the repository.

### 4. Check the results

```bash
.venv/bin/python -m pytest -q
```

Expected: `36 passed`. The tests check that:
- the loader is correct: row counts, complete joins, and revenue recomputed independently from the raw Excel file,
- every headline number quoted for Q3, Q2 and Q1 comes out exactly as reported,
- every script, and `run_all.py`, runs from scratch and writes its outputs,
- the webpage contains the right numbers, has all five parts for every question, and shows no missing values.

If a number changed, the matching test fails and names it.

### 5. Look at the outputs

Open `docs/index.html` in a browser to see the webpage locally. All other outputs land in `results/`:

| File | Content |
|---|---|
| `q3_country_growth.png` | Chart: volume growth by country, small countries grouped, with a "what to do" line |
| `q3_country_growth.csv` | Numbers behind the chart, per market |
| `q3_country_growth_all_countries.csv` | Same for every country, ungrouped |
| `q2_lost_customers.png` | Chart: days since last order vs each customer's usual gap |
| `q2_call_list.png` / `.csv` | Call list ranked by revenue at risk, with contact and phone |
| `q2_check_back_calendar.csv` | Slow buyers (every 90+ days) with a "check back by" date |
| `q2_customer_rhythm.csv` | All 89 customers who ordered, with status and rhythm |
| `q1_discounts.png` | Chart: order size by discount level vs what break-even would need |
| `q1_discount_levels.csv` / `q1_summary.csv` | Numbers per discount level and the robustness checks |

---

## Repository contents

| Path | Contents |
|---|---|
| `data/Northwind Database.xlsx` | The source dataset (8 sheets). The only input. |
| `data/*.csv` | One CSV per sheet, exported unchanged by step 1 (only a fully empty, unnamed Product column is dropped). |
| `run_all.py` | Runs steps 1–6 in order. |
| `docs/` | The published webpage (GitHub Pages serves this folder). Generated by `src/build_site.py`. |
| `scripts/01_data_check.py` | Data profiling and quality checks, plus the CSV export. |
| `src/load.py` | Shared loader used by every analysis. It applies the cleaning rules and builds the joined tables with built-in checks. |
| `src/q3_country_growth.py`, `src/q2_lost_customers.py`, `src/q1_discounts.py` | One script per business question. The method is explained in each file's top docstring. |
| `src/build_site.py` | Generates the webpage from the same functions that make the charts. |
| `tests/` | `pytest` tests (step 4). |
| `requirements.txt` | Pinned package versions. |
| `.claude/skills/python-docstrings/SKILL.md` | The course-provided docstring skill, used through Claude Code to document all Python code. |
| `CLAUDE.md` | Working rules given to the AI coding agent for this project. |

## Data notes and method choices

- **Time span:** orders run from 4 Jul 1996 to 6 May 1998, so 1996 and 1998 are partial years. Comparisons always use the same calendar months, never raw yearly totals.
- **Revenue** = `UnitPrice × Quantity × (1 − Discount)` from the order lines, i.e. the price actually charged. The catalogue price (`Product.Price`, called `ListPrice` in the code) is never used as revenue.
- **Price rise:** prices went up about 25% in April 1997. To show real growth, Q3 measures **volume**: every sale is valued at one fixed price list. This is the only place list prices are used, and the chart is labelled "volume". In the recent period, volume equals actual revenue.
- **Discounts** are stored with float noise (e.g. 0.0500000007) and are rounded to 2 decimals. One order (11077) has unusual 1–6% discounts and is left out of Q1.
- **Country** means the customer's country, not the ship-to country, because 4 orders have mixed-up ship-to addresses.
- **The Product sheet has leftover exercise columns** (`Cheap`, `NewPrice`, `IsCheap`, plus duplicates). They're ignored.
- **Q1 shows a link, not cause and effect:** discounts aren't handed out at random. There's no cost data, so margin itself can't be measured.

Data quality checks found no duplicate keys and no broken links between tables. Total net revenue matches the known Northwind figure.
