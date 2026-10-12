"""
03_breakeven_and_debt.py
Question 4: How closely does revenue follow attendance?
Question 5: How many guests does AMC need to break even?
Question 6: How much does the debt cost?

Break-even: costs are split into a part that moves with revenue (studios' share, food
costs, and the share of theatre running costs that rises with business) and a fixed part
(rent, head office, the rest of theatre running costs). The split comes from a straight-line
fit of each quarter's costs against its revenue, using the quarters since the business
settled after the pandemic. Break-even revenue = fixed costs / (1 - variable share).

Three levels of break-even:
  - cash operating: before depreciation and impairments (does a normal quarter pay its bills?)
  - operating profit: after depreciation
  - after interest: after the cost of the debt (roughly, before tax: a profit)

    python 03_breakeven_and_debt.py
"""

import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from common import CHARTS, COLORS, RESULTS, annual, ensure_folders, income_statement, tidy, us_quarterly

PERIODS = {
    "Before the pandemic (2017-2019)": ("2017-01-01", "2019-12-31"),
    "Since the recovery (2022 Q3 to 2026 Q2)": ("2022-07-01", "2026-06-30"),
}
LATEST_YEAR = 2025


def fit(df):
    """Cash operating costs (excluding depreciation and impairments) = fixed + v * revenue."""
    cash_costs = df["costs_total"] - df["cost_depreciation"] - df["cost_impairment_other"]
    v, fixed = np.polyfit(df["revenue_total"], cash_costs, 1)
    resid = cash_costs - (fixed + v * df["revenue_total"])
    r2 = 1 - (resid ** 2).sum() / ((cash_costs - cash_costs.mean()) ** 2).sum()
    return fixed, v, r2


def main():
    ensure_folders()
    q = income_statement("amc")
    us = us_quarterly()
    q = q.merge(us[["quarter", "us_attendance_millions", "us_admissions_revenue_millions", "us_fb_revenue_millions"]],
                on="quarter", how="left")

    # Q4: revenue vs attendance (U.S. tickets + food vs U.S. attendance, log changes a year apart)
    post = q[q["quarter_end"] >= "2022-07-01"].copy()
    us_rev = post["us_admissions_revenue_millions"] + post["us_fb_revenue_millions"]
    ql = q.set_index("quarter")
    print("=== Q4: DOES REVENUE MOVE ONE FOR ONE WITH ATTENDANCE? (U.S., since 2023, vs a year earlier) ===")
    rows = []
    for _, r in q[q["quarter_end"] >= "2023-01-01"].iterrows():
        prev = f"{int(r['quarter'][:4]) - 1}{r['quarter'][4:]}"
        if prev not in ql.index:
            continue
        p = ql.loc[prev]
        rows.append({"quarter": r["quarter"],
                     "attendance_change_%": 100 * (r["us_attendance_millions"] / p["us_attendance_millions"] - 1),
                     "us_revenue_change_%": 100 * ((r["us_admissions_revenue_millions"] + r["us_fb_revenue_millions"]) /
                                                   (p["us_admissions_revenue_millions"] + p["us_fb_revenue_millions"]) - 1),
                     "operating_profit_change_m": r["operating_income"] - p["operating_income"]})
    ch = pd.DataFrame(rows).dropna()
    slope = np.polyfit(ch["attendance_change_%"], ch["us_revenue_change_%"], 1)[0]
    print(f"  {len(ch)} quarters: each 1% more U.S. guests came with {slope:.2f}% more U.S. ticket and food revenue")
    ch.round(1).to_csv(os.path.join(RESULTS, "03_attendance_vs_revenue.csv"), index=False)

    # Q5: break-even
    last4 = q[q["quarter_end"].between("2025-07-01", "2026-06-30")]
    a = annual(q)
    rows = []
    for name, (s, e) in PERIODS.items():
        d = q[q["quarter_end"].between(s, e)]
        fixed, v, r2 = fit(d)
        # Depreciation and interest at their current level for the recent period (interest
        # has risen as debt was refinanced at higher rates), period average for 2017-19.
        dd = last4 if e == "2026-06-30" else d
        dep = dd["cost_depreciation"].mean()
        interest = dd["interest_total"].mean()
        rev = d["revenue_total"].mean()
        margin = 1 - v
        be_cash = fixed / margin
        be_op = (fixed + dep) / margin
        be_int = (fixed + dep + interest) / margin
        rows.append({"period": name, "quarters": len(d), "fit_r2": round(r2, 3),
                     "variable_share_of_revenue_%": round(100 * v, 1),
                     "kept_from_each_extra_dollar_%": round(100 * margin, 1),
                     "fixed_cash_costs_per_year_m": round(4 * fixed),
                     "depreciation_per_year_m (latest 4 quarters for the recent period)": round(4 * dep),
                     "interest_per_year_m (latest 4 quarters for the recent period)": round(4 * interest),
                     "average_revenue_per_year_m": round(4 * rev),
                     "breakeven_revenue_cash_m": round(4 * be_cash),
                     "breakeven_revenue_operating_m": round(4 * be_op),
                     "breakeven_revenue_after_interest_m": round(4 * be_int)})
    be = pd.DataFrame(rows).set_index("period")
    be.T.to_csv(os.path.join(RESULTS, "03_breakeven.csv"))
    print("\n=== Q5: HOW MUCH REVENUE AMC NEEDS (US$ millions per year) ===")
    print(be.T.to_string())

    cur = be.iloc[-1]
    rev_last = last4["revenue_total"].sum()
    att_last = last4["us_attendance_millions"].sum()
    print(f"\n  Revenue over the last four quarters (2025 Q3 to 2026 Q2): ${rev_last:,.0f}m; "
          f"U.S. attendance {att_last:.0f}m")
    for col, label in [("breakeven_revenue_cash_m", "pay its running costs"),
                       ("breakeven_revenue_operating_m", "make an operating profit"),
                       ("breakeven_revenue_after_interest_m", "cover interest too")]:
        need = cur[col] / rev_last - 1
        print(f"  To {label:25s}: ${cur[col]:,.0f}m, {100 * need:+.0f}% vs the last four quarters "
              f"= about {att_last * (1 + need):.0f}m U.S. guests at today's spend per guest")
    print("  (assumes spend per guest and the U.S./International mix stay as they are)")

    # Q6: the cost of debt, by year
    debt = pd.DataFrame({
        "operating_profit_before_depreciation_m": a["operating_income"] + a["cost_depreciation"] + a["cost_impairment_other"],
        "interest_m": a["interest_total"],
    })
    debt["left_after_interest_m"] = debt["operating_profit_before_depreciation_m"] - debt["interest_m"]
    debt["interest_per_$1_earned"] = (debt["interest_m"] / debt["operating_profit_before_depreciation_m"]).where(
        debt["operating_profit_before_depreciation_m"] > 100)
    debt = debt.round(1)
    debt.to_csv(os.path.join(RESULTS, "03_interest_burden.csv"))
    print("\n=== Q6: INTEREST VS WHAT THE THEATRES EARN BEFORE DEPRECIATION (US$ millions) ===")
    print(debt.to_string())

    # Charts
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.2))
    ax = axes[0]
    for name, (s, e), color in [(list(PERIODS)[0], PERIODS[list(PERIODS)[0]], "#7f8c8d"),
                                (list(PERIODS)[1], PERIODS[list(PERIODS)[1]], COLORS["AMC"])]:
        d = q[q["quarter_end"].between(s, e)]
        ax.scatter(d["revenue_total"], d["operating_income"] - d["interest_total"] + d["cost_impairment_other"],
                   color=color, s=26, label=name)
    ax.axhline(0, color="#333", lw=0.8)
    xs = np.linspace(700, 1700, 50)
    fixed, v, _ = fit(q[q["quarter_end"].between(*PERIODS[list(PERIODS)[1]])])
    ax.plot(xs, xs * (1 - v) - fixed - last4["cost_depreciation"].mean() - last4["interest_total"].mean(),
            color=COLORS["AMC"], lw=1, ls="--")
    be_q = cur["breakeven_revenue_after_interest_m"] / 4
    ax.axvline(be_q, color=COLORS["AMC"], lw=0.8, ls=":")
    ax.annotate(f"break-even\n\\${be_q:,.0f}m a quarter", (be_q, ax.get_ylim()[0]), xytext=(5, 10),
                textcoords="offset points", fontsize=8, color=COLORS["AMC"])
    ax.set_xlabel("Revenue in the quarter (\\$m)")
    ax.set_ylabel("Profit after interest, before impairments (\\$m)")
    ax.set_title("Each quarter: revenue vs profit after interest", loc="left", fontsize=10)
    ax.legend(frameon=False, fontsize=8)
    tidy(ax)

    ax = axes[1]
    yrs = [y for y in debt.index if y >= 2015]
    x = np.arange(len(yrs))
    ax.bar(x - 0.2, debt.loc[yrs, "operating_profit_before_depreciation_m"], width=0.4,
           color=COLORS["operating_profit"], label="Operating profit before depreciation")
    ax.bar(x + 0.2, debt.loc[yrs, "interest_m"], width=0.4, color=COLORS["interest"], label="Interest")
    ax.axhline(0, color="#333", lw=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(yrs, fontsize=8, rotation=45)
    ax.set_ylim(-1200, None)
    ax.set_ylabel("\\$m per year")
    ax.set_title("What the theatres earn vs what the debt costs", loc="left", fontsize=10)
    ax.legend(frameon=False, fontsize=8)
    tidy(ax)
    fig.tight_layout()
    path = os.path.join(CHARTS, "03_breakeven_and_debt.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    print(f"\nSaved {path}")


if __name__ == "__main__":
    main()
