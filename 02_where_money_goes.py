"""
02_where_money_goes.py
Question 3: Where does the money go?

Splits every $100 of AMC's revenue into what it pays out (studios' share of tickets, the
cost of food and drinks, running the theatres, rent, overheads, depreciation, impairments)
and what is left (operating profit), then interest and net income.
Also: how much of each ticket dollar and each food-and-drink dollar AMC keeps, and what
that means per U.S. guest.

    python 02_where_money_goes.py
"""

import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from common import CHARTS, COLORS, RESULTS, annual, ensure_folders, income_statement, tidy, us_quarterly

COST_LINES = [
    ("cost_film", "Studios' share of tickets", "film"),
    ("cost_food_beverage", "Food and drink costs", "food_cost"),
    ("cost_theatre_operating", "Running the theatres (staff, utilities...)", "theatre_operating"),
    ("cost_rent", "Rent", "rent"),
    ("cost_ga", "Overheads (head office)", "ga"),
    ("cost_depreciation", "Depreciation", "depreciation"),
    ("cost_impairment_other", "Impairments and other", "impairment_other"),
]
SHOW_YEARS = [2017, 2018, 2019, 2022, 2023, 2024, 2025]


def main():
    ensure_folders()
    a = annual(income_statement("amc"))
    per100 = pd.DataFrame(index=a.index)
    for col, label, _ in COST_LINES:
        per100[label] = 100 * a[col] / a["revenue_total"]
    per100["Operating profit"] = 100 * a["operating_income"] / a["revenue_total"]
    per100["Interest"] = 100 * a["interest_total"] / a["revenue_total"]
    per100["Net income"] = 100 * a["net_income"] / a["revenue_total"]
    per100 = per100.round(1)
    per100.to_csv(os.path.join(RESULTS, "02_per_100_dollars_of_revenue.csv"))
    print("=== WHERE EACH $100 OF AMC REVENUE GOES (all countries) ===")
    print(per100.T.to_string())

    keep = pd.DataFrame({
        "studios_share_of_ticket_%": 100 * a["cost_film"] / a["revenue_admissions"],
        "amc_keeps_per_ticket_dollar_%": 100 * (1 - a["cost_film"] / a["revenue_admissions"]),
        "food_cost_%": 100 * a["cost_food_beverage"] / a["revenue_food_beverage"],
        "amc_keeps_per_food_dollar_%": 100 * (1 - a["cost_food_beverage"] / a["revenue_food_beverage"]),
    }).round(1)

    # Per U.S. guest: U.S. spend per guest x what AMC keeps of each (company-wide rates)
    us = us_quarterly().dropna(subset=["us_attendance_millions"])
    y = us.groupby("year").agg(att=("us_attendance_millions", "sum"), adm=("us_admissions_revenue_millions", "sum"),
                               fb=("us_fb_revenue_millions", "sum"), n=("quarter", "size"))
    y = y[y["n"] == 4]
    keep["us_ticket_per_guest"] = y["adm"] / y["att"]
    keep["us_food_per_guest"] = y["fb"] / y["att"]
    keep["kept_from_ticket_per_guest"] = keep["us_ticket_per_guest"] * keep["amc_keeps_per_ticket_dollar_%"] / 100
    keep["kept_from_food_per_guest"] = keep["us_food_per_guest"] * keep["amc_keeps_per_food_dollar_%"] / 100
    keep["food_share_of_kept_%"] = 100 * keep["kept_from_food_per_guest"] / (
        keep["kept_from_food_per_guest"] + keep["kept_from_ticket_per_guest"])
    keep = keep.round(2)
    keep.to_csv(os.path.join(RESULTS, "02_what_amc_keeps.csv"))
    print("\n=== WHAT AMC KEEPS FROM EACH DOLLAR, AND PER U.S. GUEST ===")
    print(keep.to_string())
    print("Per-guest amounts use U.S. spend and company-wide cost rates (U.S. cost rates are only "
          "reported from 2024).")

    # Charts
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.6), gridspec_kw={"width_ratios": [1.6, 1]})
    ax = axes[0]
    years = [y_ for y_ in SHOW_YEARS if y_ in per100.index]
    x = np.arange(len(years))
    bottom = np.zeros(len(years))
    for col, label, ckey in COST_LINES:
        vals = per100.loc[years, label].clip(lower=0).values
        ax.bar(x, vals, bottom=bottom, color=COLORS[ckey], label=label, width=0.65)
        bottom += vals
    op = per100.loc[years, "Operating profit"].values
    ax.bar(x, np.where(op > 0, op, 0), bottom=bottom, color=COLORS["operating_profit"],
           label="Operating profit", width=0.65)
    for i, (yr, v) in enumerate(zip(years, op)):
        ax.annotate(f"{v:+.1f}", (i, max(102, bottom[i] + 1)), ha="center", fontsize=8,
                    color=COLORS["operating_profit"] if v > 0 else COLORS["interest"])
    ax.axhline(100, color="#333", lw=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(years)
    ax.set_ylim(0, 122)
    ax.set_ylabel("\\$ per \\$100 of revenue")
    ax.set_title("Where each \\$100 of revenue goes (number on top: operating profit or loss)",
                 loc="left", fontsize=10)
    ax.legend(frameon=False, fontsize=7.5, loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=4)
    tidy(ax)

    ax = axes[1]
    yrs = [y_ for y_ in keep.dropna(subset=["kept_from_ticket_per_guest"]).index if y_ >= 2015]
    ax.bar(yrs, keep.loc[yrs, "kept_from_ticket_per_guest"], color=COLORS["admissions"],
           label="From the ticket (after the studios' share)")
    ax.bar(yrs, keep.loc[yrs, "kept_from_food_per_guest"], bottom=keep.loc[yrs, "kept_from_ticket_per_guest"],
           color=COLORS["food_beverage"], label="From food and drinks (after their cost)")
    ax.set_ylabel("\\$ per U.S. guest")
    ax.set_title("What AMC keeps from each U.S. guest", loc="left", fontsize=10)
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    ax.set_xticks(yrs)
    ax.tick_params(axis="x", labelsize=8, rotation=45)
    tidy(ax)
    fig.tight_layout()
    path = os.path.join(CHARTS, "02_where_money_goes.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    print(f"\nSaved {path}")


if __name__ == "__main__":
    main()
