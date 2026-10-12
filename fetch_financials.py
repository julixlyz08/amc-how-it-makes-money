"""
fetch_financials.py
Downloads every number AMC and Cinemark have tagged in their SEC filings (the XBRL
"company facts"), for 10-Q and 10-K reports since 2014, and saves them as tables.

Run from the project folder:
    pip install requests pandas
    python fetch_financials.py

The SEC asks every script to identify itself: put your name and email in
SEC_USER_AGENT below before running (https://www.sec.gov/os/accessing-edgar-data).
Put the placeholder back before publishing the code.

Outputs (one set per company, e.g. data/amc_facts.csv):
    data/<ticker>_facts.csv     every tagged value: concept, period start/end, value, filing
    data/<ticker>_concepts.csv  one row per concept: its label, how many periods, first and
                                last period. Read this to see what each company reports.

Independent project using public SEC filings. Not affiliated with AMC Entertainment.
"""

import os
import time

import pandas as pd
import requests

SEC_USER_AGENT = "Your Name your-email@example.com"   # <-- change this before running

COMPANIES = {"amc": 1411579, "cnk": 1385280}   # SEC CIK numbers
FORMS = ["10-Q", "10-K", "10-Q/A", "10-K/A"]
START = pd.Timestamp("2014-01-01")


def get_json(url):
    r = requests.get(url, headers={"User-Agent": SEC_USER_AGENT}, timeout=60)
    r.raise_for_status()
    time.sleep(0.2)   # stay well under the SEC's limit of 10 requests a second
    return r.json()


def facts_table(cik):
    data = get_json(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json")
    print(f"  {data.get('entityName')} (CIK {cik})")
    rows = []
    for taxonomy, concepts in data["facts"].items():
        for concept, body in concepts.items():
            for unit, values in body.get("units", {}).items():
                for v in values:
                    if v.get("form") not in FORMS:
                        continue
                    rows.append({
                        "taxonomy": taxonomy,
                        "concept": concept,
                        "label": body.get("label") or "",
                        "unit": unit,
                        "start": v.get("start"),          # empty for balance-sheet values
                        "end": v.get("end"),
                        "value": v.get("val"),
                        "fiscal_year": v.get("fy"),
                        "fiscal_period": v.get("fp"),
                        "form": v.get("form"),
                        "filed": v.get("filed"),
                        "accession": v.get("accn"),
                    })
    df = pd.DataFrame(rows)
    df["end"] = pd.to_datetime(df["end"])
    df["start"] = pd.to_datetime(df["start"])
    df["period_days"] = (df["end"] - df["start"]).dt.days
    df = df[df["end"] >= START]
    # The same period appears in several filings (later reports repeat earlier periods
    # as comparisons, sometimes restated). Keep the most recent filing of each.
    df = (df.sort_values("filed")
            .drop_duplicates(["taxonomy", "concept", "unit", "start", "end"], keep="last")
            .sort_values(["concept", "end", "period_days"]))
    for c in ("start", "end"):
        df[c] = df[c].dt.strftime("%Y-%m-%d")
    return df


def concept_summary(df):
    g = df.groupby(["taxonomy", "concept", "label", "unit"])
    out = g.agg(periods=("value", "size"), first_end=("end", "min"), last_end=("end", "max"),
                has_duration=("start", lambda s: s.notna().any())).reset_index()
    return out.sort_values(["periods", "concept"], ascending=[False, True])


def main():
    if "example.com" in SEC_USER_AGENT:
        raise SystemExit("Set SEC_USER_AGENT at the top of fetch_financials.py to your name and email first.")
    os.makedirs("data", exist_ok=True)
    for ticker, cik in COMPANIES.items():
        df = facts_table(cik)
        s = concept_summary(df)
        df.to_csv(os.path.join("data", f"{ticker}_facts.csv"), index=False)
        s.to_csv(os.path.join("data", f"{ticker}_concepts.csv"), index=False)
        print(f"    {len(df):,} values across {len(s):,} concepts, "
              f"{df['end'].min()} to {df['end'].max()}")
        custom = s[~s["taxonomy"].isin(["us-gaap", "dei", "srt", "ifrs-full"])]
        print(f"    company-specific concepts: {len(custom)}")


if __name__ == "__main__":
    main()
