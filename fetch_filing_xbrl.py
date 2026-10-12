"""
fetch_filing_xbrl.py
Reads the full XBRL data file of every 10-Q and 10-K that AMC and Cinemark filed since
2015, and saves every number in it.

Why this is needed: the SEC's summary file (fetch_financials.py) leaves out values that
companies tag with their own labels (e.g. AMC's film exhibition costs) or split by
segment or product (e.g. admissions vs food and beverage revenue, U.S. vs International).
After 2017 most of AMC's revenue and cost detail is reported that way.

Run from the project folder (takes about 5 to 10 minutes):
    pip install requests pandas
    python fetch_filing_xbrl.py

Put your name and email in SEC_USER_AGENT first, and the placeholder back before
publishing the code.

Output (compressed, one per company):
    data/<ticker>_xbrl.csv.gz   one row per value: concept, period, segment/product
                                dimensions, value, and the filing it came from.
Only values for the filing's own period are kept (the quarter, the year to date, or the
year-end balance), not the comparison periods repeated from earlier reports.

Independent project using public SEC filings. Not affiliated with AMC Entertainment.
"""

import io
import os
import time
import xml.etree.ElementTree as ET

import pandas as pd
import requests

SEC_USER_AGENT = "Your Name your-email@example.com"   # <-- change this before running

COMPANIES = {"amc": 1411579, "cnk": 1385280}
FORMS = ["10-Q", "10-K"]
START = pd.Timestamp("2015-01-01")

XBRLI = "{http://www.xbrl.org/2003/instance}"
XBRLDI = "{http://xbrl.org/2006/xbrldi}"
SKIP_FILES = ("_cal.xml", "_def.xml", "_lab.xml", "_pre.xml", "FilingSummary.xml")


def get(url, as_json=False):
    for attempt in range(3):
        r = requests.get(url, headers={"User-Agent": SEC_USER_AGENT}, timeout=120)
        if r.status_code == 429:          # too many requests: wait and retry
            time.sleep(5)
            continue
        r.raise_for_status()
        time.sleep(0.15)                  # under the SEC's limit of 10 requests a second
        return r.json() if as_json else r.content
    r.raise_for_status()


def filings(cik):
    sub = get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json", as_json=True)
    print(f"  {sub.get('name')} (CIK {cik})")
    frames = [pd.DataFrame(sub["filings"]["recent"])]
    for page in sub["filings"].get("files", []):
        frames.append(pd.DataFrame(get(f"https://data.sec.gov/submissions/{page['name']}", as_json=True)))
    f = pd.concat([x for x in frames if len(x)], ignore_index=True)
    f = f[f["form"].isin(FORMS)].copy()
    f["reportDate"] = pd.to_datetime(f["reportDate"], errors="coerce")
    return f[f["reportDate"] >= START].sort_values("reportDate")


def instance_url(cik, accession):
    folder = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace('-', '')}"
    items = get(f"{folder}/index.json", as_json=True)["directory"]["item"]
    names = [i["name"] for i in items]
    # Inline XBRL filings (2019 on) have an extracted instance named *_htm.xml;
    # older filings have a plain instance, e.g. amc-20171231.xml.
    for n in names:
        if n.endswith("_htm.xml"):
            return f"{folder}/{n}"
    for n in names:
        if n.endswith(".xml") and not n.endswith(SKIP_FILES):
            return f"{folder}/{n}"
    return None


def parse_instance(content):
    """All numeric facts in an XBRL instance, with their period and dimensions."""
    prefixes = {}
    for event, (prefix, uri) in ET.iterparse(io.BytesIO(content), events=["start-ns"]):
        prefixes.setdefault(uri, prefix)
    root = ET.fromstring(content)

    units = {}
    for u in root.iter(f"{XBRLI}unit"):
        measures = [m.text.split(":")[-1] for m in u.iter(f"{XBRLI}measure") if m.text]
        units[u.get("id")] = "/".join(measures)

    contexts = {}
    for ctx in root.iter(f"{XBRLI}context"):
        period = ctx.find(f"{XBRLI}period")
        start = period.findtext(f"{XBRLI}startDate")
        end = period.findtext(f"{XBRLI}endDate") or period.findtext(f"{XBRLI}instant")
        dims = []
        for m in ctx.iter(f"{XBRLDI}explicitMember"):
            dims.append(f"{m.get('dimension')}={(m.text or '').strip()}")
        for m in ctx.iter(f"{XBRLDI}typedMember"):
            dims.append(f"{m.get('dimension')}=typed")
        contexts[ctx.get("id")] = (start, end, ";".join(sorted(dims)))

    rows = []
    for el in root:
        ref = el.get("contextRef")
        if ref is None or el.get("unitRef") is None or el.text is None:
            continue                       # text blocks and non-numeric facts
        try:
            value = float(el.text.strip())
        except ValueError:
            continue
        uri, local = el.tag[1:].split("}")
        start, end, dims = contexts.get(ref, (None, None, ""))
        rows.append({"concept": f"{prefixes.get(uri, uri)}:{local}", "start": start, "end": end,
                     "dimensions": dims, "value": value,
                     "unit": units.get(el.get("unitRef"), el.get("unitRef"))})
    return pd.DataFrame(rows)


def main():
    if "example.com" in SEC_USER_AGENT:
        raise SystemExit("Set SEC_USER_AGENT at the top of fetch_filing_xbrl.py to your name and email first.")
    os.makedirs("data", exist_ok=True)
    for ticker, cik in COMPANIES.items():
        out, missing = [], []
        fl = filings(cik)
        print(f"    {len(fl)} reports to read")
        for _, f in fl.iterrows():
            acc = f["accessionNumber"]
            try:
                url = instance_url(cik, acc)
                if url is None:
                    missing.append(acc)
                    continue
                facts = parse_instance(get(url))
            except Exception as e:                       # keep going; report at the end
                missing.append(f"{acc} ({type(e).__name__})")
                continue
            facts = facts[facts["end"] == f["reportDate"].strftime("%Y-%m-%d")]
            facts.insert(0, "report_date", f["reportDate"].strftime("%Y-%m-%d"))
            facts.insert(1, "form", f["form"])
            facts.insert(2, "filed", f["filingDate"])
            facts.insert(3, "accession", acc)
            out.append(facts.drop_duplicates())
            print(f"    {f['form']:5s} {f['reportDate']:%Y-%m-%d}: {len(facts):5,} values")
        df = pd.concat(out, ignore_index=True)
        path = os.path.join("data", f"{ticker}_xbrl.csv.gz")
        df.to_csv(path, index=False, compression="gzip")
        print(f"  Saved {len(df):,} values from {len(out)} reports to {path}")
        if missing:
            print(f"  Could not read {len(missing)} reports: {missing}")


if __name__ == "__main__":
    main()
