"""
common.py
Shared loaders and chart helpers.
"""

import os

import numpy as np
import pandas as pd

DATA, CHARTS, RESULTS = "data", "charts", "results"

# 2015 annual average CPI-U (BLS). The monthly table used for later years starts in 2016.
CPI_2015_ANNUAL = 237.017

COLORS = {
    "admissions": "#1f4e79", "food_beverage": "#c0392b", "other": "#7f8c8d",
    "film": "#5b7fa6", "food_cost": "#d98880", "theatre_operating": "#b7950b", "rent": "#8e44ad",
    "ga": "#95a5a6", "depreciation": "#bdc3c7", "impairment_other": "#e5e7e9",
    "operating_profit": "#27ae60", "interest": "#922b21", "AMC": "#c0392b", "CNK": "#1f4e79",
}

# AMC's footprint changed with acquisitions: Carmike (closed 21 Dec 2016) and
# Odeon/UCI in Europe (closed 30 Nov 2016), Nordic (March 2017). Before 2017 the company
# is much smaller and almost entirely American, so comparisons of totals start in 2017.
FULL_FOOTPRINT_FROM = 2017


def ensure_folders():
    for d in (CHARTS, RESULTS):
        os.makedirs(d, exist_ok=True)


def income_statement(ticker):
    df = pd.read_csv(os.path.join(DATA, f"{ticker}_income_statement.csv"), parse_dates=["quarter_end"])
    df["year"] = df["quarter_end"].dt.year
    return df


def annual(df):
    """Full calendar years only (four quarters), summed."""
    num = df.select_dtypes("number").drop(columns=["year"], errors="ignore")
    g = num.groupby(df["year"])
    out = g.sum(min_count=1)
    return out[g.size() == 4]


def us_quarterly():
    """U.S. attendance, ticket and food and beverage figures from the attendance project."""
    raw = pd.read_csv(os.path.join(DATA, "amc_quarterly.csv"), encoding="utf-8-sig", dtype=str,
                      keep_default_na=False)
    df = pd.DataFrame({"quarter": raw["quarter"].str.strip()})
    for col in [c for c in raw.columns if c.startswith("us_")]:
        cleaned = raw[col].str.strip().str.replace(",", "", regex=False)
        df[col] = pd.to_numeric(cleaned.replace({"-": np.nan, "": np.nan}), errors="coerce")
    df["year"] = df["quarter"].str[:4].astype(int)
    return df


def cpi_annual():
    m = pd.read_csv(os.path.join(DATA, "cpi_monthly.csv"))
    a = m.groupby("year")["cpi_u"].mean()
    a.loc[2015] = CPI_2015_ANNUAL
    return a.sort_index()


def tidy(ax):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.grid(axis="y", alpha=0.3)
