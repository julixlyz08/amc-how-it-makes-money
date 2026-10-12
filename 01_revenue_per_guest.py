"""
01_revenue_per_guest.py
Question 1: Where does AMC's revenue come from, and how has the mix changed?
Question 2: What does each guest bring in, and has it kept up with inflation?

Revenue mix: AMC as a whole (all countries), from the income statements.
Per guest: U.S. only, because attendance is only available for the U.S. (from the
attendance project's table of AMC's filings).

    python 01_revenue_per_guest.py
"""

import os

import matplotlib.pyplot as plt
import pandas as pd

from common import CHARTS, COLORS, RESULTS, annual, cpi_annual, ensure_folders, income_statement, tidy, us_quarterly

BASE_YEAR, LATEST_YEAR = 2015, 2025


def main():
    ensure_folders()
    amc = annual(income_statement("amc"))
    mix = pd.DataFrame({
        "revenue_total_m": amc["revenue_total"],
        "admissions_%": 100 * amc["revenue_admissions"] / amc["revenue_total"],
        "food_beverage_%": 100 * amc["revenue_food_beverage"] / amc["revenue_total"],
        "other_%": 100 * amc["revenue_other"] / amc["revenue_total"],
    }).round(1)
    mix.to_csv(os.path.join(RESULTS, "01_revenue_mix.csv"))
    print("=== WHERE AMC'S REVENUE COMES FROM (all countries, % of revenue) ===")
    print(mix.to_string())

    # U.S. per guest, by year
    us = us_quarterly().dropna(subset=["us_attendance_millions"])
    y = us.groupby("year").agg(attendance_m=("us_attendance_millions", "sum"),
                               admissions_m=("us_admissions_revenue_millions", "sum"),
                               fb_m=("us_fb_revenue_millions", "sum"), quarters=("quarter", "size"))
    y = y[y["quarters"] == 4]
    y["ticket_per_guest"] = y["admissions_m"] / y["attendance_m"]
    y["food_beverage_per_guest"] = y["fb_m"] / y["attendance_m"]
    y["spend_per_guest"] = y["ticket_per_guest"] + y["food_beverage_per_guest"]
    y["food_beverage_vs_ticket_%"] = 100 * y["food_beverage_per_guest"] / y["ticket_per_guest"]
    cpi = cpi_annual()
    factor = cpi[LATEST_YEAR] / cpi
    for c in ["ticket_per_guest", "food_beverage_per_guest", "spend_per_guest"]:
        y[f"{c}_in_{LATEST_YEAR}_dollars"] = y[c] * y.index.map(factor)
    per_guest = y.drop(columns=["quarters"]).round(2)
    per_guest.to_csv(os.path.join(RESULTS, "01_us_per_guest.csv"))
    print("\n=== WHAT EACH U.S. GUEST SPENDS ($, full years) ===")
    print(per_guest[["attendance_m", "ticket_per_guest", "food_beverage_per_guest", "spend_per_guest",
                     "food_beverage_vs_ticket_%"]].to_string())

    b, l = per_guest.loc[BASE_YEAR], per_guest.loc[LATEST_YEAR]
    inflation = 100 * (cpi[LATEST_YEAR] / cpi[BASE_YEAR] - 1)
    print(f"\n=== {BASE_YEAR} TO {LATEST_YEAR}: CHANGE IN SPEND PER U.S. GUEST ===")
    for c, label in [("ticket_per_guest", "Ticket"), ("food_beverage_per_guest", "Food and drinks"),
                     ("spend_per_guest", "Total")]:
        print(f"  {label:16s} ${b[c]:5.2f} -> ${l[c]:5.2f}  {100 * (l[c] / b[c] - 1):+5.0f}%  "
              f"(after inflation: {100 * (l[f'{c}_in_{LATEST_YEAR}_dollars'] / b[f'{c}_in_{LATEST_YEAR}_dollars'] - 1):+4.0f}%)")
    print(f"  Prices in general (CPI-U): {inflation:+.0f}%")
    print(f"  U.S. attendance: {b['attendance_m']:.0f}m -> {l['attendance_m']:.0f}m "
          f"({100 * (l['attendance_m'] / b['attendance_m'] - 1):+.0f}%)")

    # Charts
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    ax = axes[0]
    bottom = 0
    for col, label, color in [("admissions_%", "Tickets", COLORS["admissions"]),
                              ("food_beverage_%", "Food and drinks", COLORS["food_beverage"]),
                              ("other_%", "Other (advertising, fees, A-List...)", COLORS["other"])]:
        ax.bar(mix.index, mix[col], bottom=bottom, color=color, label=label, width=0.75)
        bottom = bottom + mix[col]
    ax.set_ylim(0, 100)
    ax.set_ylabel("% of revenue")
    ax.set_title("Where AMC's revenue comes from (all countries)", loc="left", fontsize=10)
    ax.legend(frameon=False, fontsize=8, loc="lower center", bbox_to_anchor=(0.5, -0.25), ncol=3)
    ax.set_xticks(mix.index)
    ax.tick_params(axis="x", labelsize=8)
    tidy(ax)

    ax = axes[1]
    idx = per_guest.index
    ax.plot(idx, per_guest["ticket_per_guest"], marker="o", color=COLORS["admissions"], label="Ticket")
    ax.plot(idx, per_guest["food_beverage_per_guest"], marker="o", color=COLORS["food_beverage"],
            label="Food and drinks")
    for c, color in [("ticket_per_guest", COLORS["admissions"]), ("food_beverage_per_guest", COLORS["food_beverage"])]:
        start = per_guest.loc[BASE_YEAR, c]
        ax.plot(idx, start * cpi.reindex(idx) / cpi[BASE_YEAR], ls=":", color=color, lw=1)
    ax.plot([], [], ls=":", color="#555", label=f"If it had only kept up with inflation since {BASE_YEAR}")
    ax.set_ylabel("\\$ per U.S. guest")
    ax.set_title("What each U.S. guest spends", loc="left", fontsize=10)
    ax.legend(frameon=False, fontsize=8)
    ax.set_xticks(idx)
    ax.tick_params(axis="x", labelsize=8)
    tidy(ax)
    fig.tight_layout()
    path = os.path.join(CHARTS, "01_revenue_per_guest.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    print(f"\nSaved {path}")


if __name__ == "__main__":
    main()
