"""
build_financials.py
Turns the raw XBRL values (data/amc_xbrl.csv.gz, data/cnk_xbrl.csv.gz) into one tidy
income statement per company: one row per quarter, one column per line.

Companies change how they tag the same line over the years (e.g. AMC's ticket revenue is
"AdmissionsRevenue" until 2017, then revenue split by "AdmissionMember" from 2018), so
each line has an ordered list of tags to try. The first one found for a quarter is used,
and the tag used is recorded.

Fourth quarters are not reported on their own: Q4 = full year (10-K) minus the first
nine months (Q3 10-Q), as in the attendance project.

Checks printed at the end: revenue lines add up to total revenue, cost lines add up to
total costs, and revenue minus costs equals operating income, for every quarter.

    python build_financials.py

Outputs: data/amc_income_statement.csv, data/cnk_income_statement.csv (US$ millions)
"""

import re

import numpy as np
import pandas as pd

# (line, [(tag, dimensions after normalising), ...]) in order of preference.
# Dimensions "" means the company total; "P=X" means split by product or service X.
AMC_LINES = {
    "revenue_total": [("Revenues", ""), ("RevenueFromContractWithCustomerExcludingAssessedTax", "")],
    "revenue_admissions": [("AdmissionsRevenue", ""),
                           ("RevenueFromContractWithCustomerExcludingAssessedTax", "P=Admission")],
    "revenue_food_beverage": [("FoodAndBeverageRevenue", ""),
                              ("RevenueFromContractWithCustomerExcludingAssessedTax", "P=FoodAndBeverage")],
    "revenue_other": [("OtherSalesRevenueNet", ""),
                      ("RevenueFromContractWithCustomerExcludingAssessedTax", "P=TotalOtherProductAndService")],
    "revenue_advertising": [("RevenueFromContractWithCustomerExcludingAssessedTax", "P=Advertising")],
    "cost_film": [("FilmExhibitionCosts", ""), ("CostOfGoodsAndServicesSold", "P=Admission")],
    "cost_food_beverage": [("FoodAndBeverageCostOfSales", ""), ("CostOfGoodsAndServicesSold", "P=FoodAndBeverage")],
    "cost_theatre_operating": [("OtherCostAndExpenseOperating", "")],
    "cost_rent": [("OperatingLeaseExpense", ""), ("LeaseAndRentalExpense", "")],
    "cost_ga_merger": [("MergerAcquisitionTransactionCosts", "")],
    "cost_ga_other": [("OtherGeneralAndAdministrativeExpense", "")],
    "cost_depreciation": [("DepreciationDepletionAndAmortization", "")],
    "costs_total": [("CostsAndExpenses", "")],
    "operating_income": [("OperatingIncomeLoss", "")],
    "interest_debt": [("InterestExpenseDebt", "")],
    "interest_finance_leases": [("FinanceLeaseInterestExpense", ""),
                                ("InterestExpenseCapitalAndFinancingLeaseObligations", "")],
    "interest_ncm_noncash": [("ExhibitorServiceAgreement", "")],
    "net_income": [("NetIncomeLoss", ""), ("NetIncomeLossAvailableToCommonStockholdersBasic", ""),
                   ("IncomeLossFromContinuingOperations", "")],   # no discontinued operations in 2016-17
}

CNK_LINES = {
    "revenue_total": [("RevenueFromContractWithCustomerExcludingAssessedTax", ""), ("SalesRevenueNet", ""),
                      ("Revenues", "ConsolidationItems=OperatingSegments")],
    "revenue_admissions": [("AdmissionsRevenue", ""),
                           ("RevenueFromContractWithCustomerExcludingAssessedTax", "P=AdmissionsRevenue"),
                           ("RevenueFromContractWithCustomerExcludingAssessedTax", "P=Admission")],
    "revenue_food_beverage": [("ConcessionsRevenue", ""),
                              ("RevenueFromContractWithCustomerExcludingAssessedTax", "P=Concessions"),
                              ("RevenueFromContractWithCustomerExcludingAssessedTax", "P=ConcessionsRevenues")],
    "revenue_other": [("OtherSalesRevenueNet", ""),
                      ("RevenueFromContractWithCustomerExcludingAssessedTax", "P=OtherRevenues"),
                      ("RevenueFromContractWithCustomerExcludingAssessedTax", "P=OtherRevenue")],
    "cost_film": [("FilmRentalsAndAdvertising", ""), ("FilmRentalsAndAdvertising", "ConsolidationItems=OperatingSegments")],
    "cost_food_beverage": [("ConcessionsCosts", ""), ("ConcessionSuppliesExpense", ""),
                           ("ConcessionSuppliesExpense", "ConsolidationItems=OperatingSegments")],
    "cost_labor": [("LaborAndRelatedExpense", "")],
    "cost_theatre_operating": [("OtherCostAndExpenseOperating", "")],   # utilities and other
    "cost_rent": [("FacilityLeaseExpense", "")],
    "cost_ga": [("GeneralAndAdministrativeExpense", "")],
    "cost_depreciation": [("DepreciationDepletionAndAmortization", "")],
    "costs_total": [("CostsAndExpenses", "")],
    "operating_income": [("OperatingIncomeLoss", "")],
    "interest_total": [("InterestExpense", ""), ("InterestExpenseNonoperating", "")],
    "net_income": [("NetIncomeLoss", "")],
}

# Dimension values that mean "the whole company" and can be dropped.
TOTAL_DIMS = [r"LegalEntityAxis=CnkMember", r"StatementBusinessSegmentsAxis=ConsolidatedMember"]


def normalise(dims):
    if not isinstance(dims, str) or not dims:
        return ""
    parts = []
    for d in dims.split(";"):
        d = re.sub(r"[A-Za-z-]+:", "", d)                     # drop prefixes like us-gaap:
        if any(re.fullmatch(t, d) for t in TOTAL_DIMS):
            continue
        d = d.replace("ProductOrServiceAxis=", "P=").replace("StatementBusinessSegmentsAxis=", "S=")
        d = d.replace("ConsolidationItemsAxis=", "ConsolidationItems=").replace("Member", "")
        parts.append(d)
    return ";".join(sorted(parts))


def load(path):
    x = pd.read_csv(path)
    # Older filings name their units "Unit1", "Unit2"..., so the unit cannot be used to
    # filter; every line picked below is a dollar amount.
    x = x[x["start"].notna()].copy()
    x["concept"] = x["concept"].str.split(":").str[1]
    x["dims"] = x["dimensions"].map(normalise)
    # Cinemark's 2023 filings combine the parent company and a subsidiary. The parent's
    # main statements are tagged with the parent as legal entity; an untagged copy of a
    # few lines elsewhere in the filing has the opposite sign. Prefer the parent's values.
    x["parent_tagged"] = x["dimensions"].fillna("").str.contains("LegalEntityAxis=cnk:CnkMember")
    x["days"] = (pd.to_datetime(x["end"]) - pd.to_datetime(x["start"])).dt.days
    x["kind"] = np.select([x["days"].between(80, 100), x["days"].between(260, 280),
                           x["days"].between(355, 375)], ["3m", "9m", "12m"], "other")
    return x[x["kind"] != "other"]


def pick(x, lines):
    """Value of each line for each period kind, using the first tag found."""
    rows = []
    for (end, kind), g in x.groupby(["end", "kind"]):
        row = {"end": end, "kind": kind}
        for line, candidates in lines.items():
            for concept, dims in candidates:
                hit = g[(g["concept"] == concept) & (g["dims"] == dims)]
                if len(hit):
                    row[line] = hit.sort_values(["filed", "parent_tagged"])["value"].iloc[-1] / 1e6
                    row[f"{line}__tag"] = f"{concept}|{dims}"
                    break
        rows.append(row)
    return pd.DataFrame(rows)


def quarterly(p, lines):
    p["end"] = pd.to_datetime(p["end"])
    q3m = p[p["kind"] == "3m"].set_index("end")
    out = []
    for end in sorted(set(p["end"])):
        if end.month == 12:
            fy = p[(p["kind"] == "12m") & (p["end"] == end)]
            ytd = p[(p["kind"] == "9m") & (p["end"] == pd.Timestamp(end.year, 9, 30))]
            if fy.empty or ytd.empty:
                continue
            row = {"quarter_end": end, "q4_derived": True}
            for line in lines:
                if line in fy and line in ytd and pd.notna(fy[line].iloc[0]) and pd.notna(ytd[line].iloc[0]):
                    row[line] = fy[line].iloc[0] - ytd[line].iloc[0]
        elif end in q3m.index:
            r = q3m.loc[end]
            row = {"quarter_end": end, "q4_derived": False}
            for line in lines:
                if line in r and pd.notna(r[line]):
                    row[line] = r[line]
        else:
            continue
        out.append(row)
    df = pd.DataFrame(out).sort_values("quarter_end")
    df.insert(0, "quarter", [f"{d.year} Q{d.quarter}" for d in df["quarter_end"]])
    return df


def checks(df, name, revenue_parts, cost_parts):
    print(f"\n=== {name}: checks (US$ millions; largest gap across quarters) ===")
    tests = {
        "revenue lines vs total revenue": df[revenue_parts].sum(axis=1, min_count=len(revenue_parts)) - df["revenue_total"],
        "cost lines vs total costs (gap = impairments and other)": df["costs_total"] - df[cost_parts].sum(axis=1, min_count=len(cost_parts)),
        "revenue - costs vs operating income": df["revenue_total"] - df["costs_total"] - df["operating_income"],
    }
    for label, gap in tests.items():
        g = gap.dropna()
        if len(g):
            worst = g.abs().idxmax()
            print(f"  {label}: {len(g)} quarters, largest gap {g.abs().max():,.1f} ({df.loc[worst, 'quarter']})")
        else:
            print(f"  {label}: not available")
    missing = df.drop(columns=["quarter", "quarter_end", "q4_derived"]).isna().sum()
    missing = missing[missing > 0]
    if len(missing):
        print("  Quarters missing a line:", missing.to_dict())


def tag_report(p, lines, path):
    """Which tag supplied each line, by year (for the record)."""
    cols = [f"{l}__tag" for l in lines if f"{l}__tag" in p]
    t = p[["end", "kind"] + cols].copy()
    t["year"] = pd.to_datetime(t["end"]).dt.year
    long = t.melt(id_vars=["year"], value_vars=cols, var_name="line", value_name="tag").dropna()
    long["line"] = long["line"].str.replace("__tag", "")
    long.groupby(["line", "tag"])["year"].agg(["min", "max"]).reset_index().to_csv(path, index=False)


def main():
    amc_p = pick(load("data/amc_xbrl.csv.gz"), AMC_LINES)
    amc = quarterly(amc_p, AMC_LINES)
    amc["cost_ga"] = amc[["cost_ga_merger", "cost_ga_other"]].sum(axis=1, min_count=1)
    amc["interest_total"] = amc[["interest_debt", "interest_finance_leases", "interest_ncm_noncash"]].sum(axis=1, min_count=1)
    parts = ["cost_film", "cost_food_beverage", "cost_theatre_operating", "cost_rent", "cost_ga", "cost_depreciation"]
    amc["cost_impairment_other"] = amc["costs_total"] - amc[parts].sum(axis=1, min_count=len(parts))
    checks(amc, "AMC", ["revenue_admissions", "revenue_food_beverage", "revenue_other"], parts)
    amc.round(3).to_csv("data/amc_income_statement.csv", index=False)
    tag_report(amc_p, AMC_LINES, "data/amc_tags_used.csv")

    cnk_p = pick(load("data/cnk_xbrl.csv.gz"), CNK_LINES)
    cnk = quarterly(cnk_p, CNK_LINES)
    parts = ["cost_film", "cost_food_beverage", "cost_labor", "cost_theatre_operating", "cost_rent",
             "cost_ga", "cost_depreciation"]
    cnk["cost_impairment_other"] = cnk["costs_total"] - cnk[parts].sum(axis=1, min_count=len(parts))
    checks(cnk, "Cinemark", ["revenue_admissions", "revenue_food_beverage", "revenue_other"], parts)
    cnk.round(3).to_csv("data/cnk_income_statement.csv", index=False)
    tag_report(cnk_p, CNK_LINES, "data/cnk_tags_used.csv")
    print("\nSaved data/amc_income_statement.csv and data/cnk_income_statement.csv")


if __name__ == "__main__":
    main()
