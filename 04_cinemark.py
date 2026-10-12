"""
04_cinemark.py
Question 7: How does AMC compare with Cinemark?

The same "where each $100 goes" view for both companies. Line definitions differ a little:
Cinemark reports staff costs separately from utilities and other theatre costs (AMC
reports them together as operating expense), and Cinemark's film costs include its
advertising. Both companies include their international theatres (AMC: Europe;
Cinemark: Latin America).

    python 04_cinemark.py
"""

import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from common import CHARTS, COLORS, RESULTS, annual, ensure_folders, income_statement, tidy

YEARS = [2019, 2023, 2024, 2025]
LINES = [  # label, AMC columns, Cinemark columns, colour key
    ("Studios' share of tickets", ["cost_film"], ["cost_film"], "film"),
    ("Food and drink costs", ["cost_food_beverage"], ["cost_food_beverage"], "food_cost"),
    ("Running the theatres", ["cost_theatre_operating"], ["cost_labor", "cost_theatre_operating"], "theatre_operating"),
    ("Rent", ["cost_rent"], ["cost_rent"], "rent"),
    ("Overheads", ["cost_ga"], ["cost_ga"], "ga"),
    ("Depreciation", ["cost_depreciation"], ["cost_depreciation"], "depreciation"),
    ("Impairments and other", ["cost_impairment_other"], ["cost_impairment_other"], "impairment_other"),
]


def per_100(a, which):
    out = pd.DataFrame(index=a.index)
    for label, amc_cols, cnk_cols, _ in LINES:
        cols = amc_cols if which == "AMC" else cnk_cols
        out[label] = 100 * a[cols].sum(axis=1) / a["revenue_total"]
    out["Operating profit"] = 100 * a["operating_income"] / a["revenue_total"]
    out["Interest"] = 100 * a["interest_total"] / a["revenue_total"]
    out["Net income"] = 100 * a["net_income"] / a["revenue_total"]
    out["Tickets as % of revenue"] = 100 * a["revenue_admissions"] / a["revenue_total"]
    out["Food and drinks as % of revenue"] = 100 * a["revenue_food_beverage"] / a["revenue_total"]
    out["Studios' share of each ticket dollar"] = 100 * a["cost_film"] / a["revenue_admissions"]
    out["Cost of each food and drink dollar"] = 100 * a["cost_food_beverage"] / a["revenue_food_beverage"]
    out["Revenue ($m)"] = a["revenue_total"]
    return out


def main():
    ensure_folders()
    amc = per_100(annual(income_statement("amc")), "AMC")
    cnk = per_100(annual(income_statement("cnk")), "CNK")
    table = pd.concat({"AMC": amc.loc[YEARS].T, "Cinemark": cnk.loc[YEARS].T}, axis=1).round(1)
    table.to_csv(os.path.join(RESULTS, "04_amc_vs_cinemark.csv"))
    pd.set_option("display.width", 200)
    print("=== AMC VS CINEMARK: WHERE EACH $100 OF REVENUE GOES ===")
    print(table.to_string())

    # Chart: 2025 side by side, plus the gap line by line
    yr = 2025
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.2), gridspec_kw={"width_ratios": [1, 1.3]})
    ax = axes[0]
    for i, (name, d) in enumerate([("AMC", amc), ("Cinemark", cnk)]):
        bottom = 0
        for label, _, _, ckey in LINES:
            v = max(d.loc[yr, label], 0)
            ax.bar(i, v, bottom=bottom, color=COLORS[ckey], width=0.55, label=label if i == 0 else None)
            bottom += v
        op = d.loc[yr, "Operating profit"]
        if op > 0:
            ax.bar(i, op, bottom=bottom, color=COLORS["operating_profit"], width=0.55,
                   label="Operating profit" if name == "Cinemark" else None)
        ax.annotate(f"operating profit {op:+.1f}\ninterest {d.loc[yr, 'Interest']:.1f}\nnet income {d.loc[yr, 'Net income']:+.1f}",
                    (i, 101), ha="center", fontsize=8)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["AMC", "Cinemark"])
    ax.set_ylim(0, 118)
    ax.set_ylabel(f"\\$ per \\$100 of revenue, {yr}")
    ax.set_title(f"Where each \\$100 of revenue goes, {yr}", loc="left", fontsize=10)
    ax.legend(frameon=False, fontsize=7.5, loc="lower center", ncol=2, bbox_to_anchor=(0.5, -0.38))
    tidy(ax)

    ax = axes[1]
    labels = [l for l, *_ in LINES] + ["Interest"]
    gap = [amc.loc[yr, l] - cnk.loc[yr, l] for l in labels]
    y = np.arange(len(labels))
    ax.barh(y, gap, color=[COLORS["interest"] if g > 0 else COLORS["operating_profit"] for g in gap])
    for yi, g in zip(y, gap):
        ax.annotate(f"{g:+.1f}", (g, yi), xytext=(4 if g >= 0 else -4, 0), textcoords="offset points",
                    ha="left" if g >= 0 else "right", va="center", fontsize=8)
    ax.axvline(0, color="#333", lw=0.8)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=8.5)
    ax.invert_yaxis()
    ax.set_xlabel(f"AMC minus Cinemark, \\$ per \\$100 of revenue, {yr} (red: AMC spends more)")
    ax.set_title("Where AMC's costs are higher", loc="left", fontsize=10)
    tidy(ax)
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    path = os.path.join(CHARTS, "04_amc_vs_cinemark.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    print(f"\nSaved {path}")


if __name__ == "__main__":
    main()
