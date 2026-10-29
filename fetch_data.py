"""Pull data for the GCC fiscal stress test.

    set FRED_API_KEY=your_key        (Command Prompt)
    python fetch_data.py

Writes data/raw/imf_datamapper.csv, worldbank.csv, brent_annual.csv, brent_monthly.csv.
IMF values for the latest WEO projection years are flagged in the 'projection' column.
"""
import os
import sys
import time
from pathlib import Path

import pandas as pd
import requests

RAW = Path(__file__).resolve().parent / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

COUNTRIES = {"SAU": "Saudi Arabia", "ARE": "UAE", "QAT": "Qatar", "KWT": "Kuwait", "OMN": "Oman", "BHR": "Bahrain"}
HEAD = {"User-Agent": "Mozilla/5.0 (research script; contact via GitHub)"}

IMF = {
    "GGXCNL_NGDP": "General government net lending/borrowing, % GDP",
    "GGXWDG_NGDP": "General government gross debt, % GDP",
    "NGDPD": "GDP, current prices, USD bn",
    "NGDP_RPCH": "Real GDP growth, %",
    "BCA_NGDPD": "Current account balance, % GDP",
}
WB = {
    "NY.GDP.PETR.RT.ZS": "Oil rents, % GDP",
    "TX.VAL.FUEL.ZS.UN": "Fuel exports, % merchandise exports",
    "FI.RES.TOTL.CD": "Total reserves incl. gold, USD",
    "NY.GDP.MKTP.CD": "GDP, current USD",
}
LAST_ACTUAL_YEAR = 2025   # IMF WEO values after this year are projections


def get_json(url, tries=4):
    for i in range(tries):
        try:
            r = requests.get(url, headers=HEAD, timeout=60)
            r.raise_for_status()
            return r.json()
        except Exception as e:  # noqa: BLE001
            print(f"   retry {i + 1} for {url[:90]}... ({e})")
            time.sleep(2 * (i + 1))
    sys.exit(f"Could not fetch {url}")


def discover_imf():
    """Find IMF DataMapper ids for general-government revenue / expenditure / primary balance (% GDP)."""
    import re
    j = get_json("https://www.imf.org/external/datamapper/api/v1/indicators")
    found = {}
    for k, v in j.get("indicators", {}).items():
        lab = (v.get("label") or "")
        low = lab.lower()
        if re.search(r"(revenue|expenditure|primary)", low) and "general government" in low and "gdp" in low:
            found[k] = lab
    print("IMF candidates found:", found)
    return found


def pull_imf():
    rows = []
    ctry = "/".join(COUNTRIES)
    extra = discover_imf()
    IMF.update(extra)
    for ind in IMF:
        j = get_json(f"https://www.imf.org/external/datamapper/api/v1/{ind}/{ctry}")
        vals = j.get("values", {}).get(ind, {})
        for c, series in vals.items():
            if c not in COUNTRIES:
                continue
            for y, v in series.items():
                rows.append(dict(country=c, year=int(y), indicator=ind, value=v))
    df = pd.DataFrame(rows)
    df["projection"] = df.year > LAST_ACTUAL_YEAR
    df.to_csv(RAW / "imf_datamapper.csv", index=False)
    return df


def pull_wb():
    rows = []
    ctry = ";".join(COUNTRIES)
    for ind in WB:
        j = get_json(f"https://api.worldbank.org/v2/country/{ctry}/indicator/{ind}?format=json&per_page=20000&date=1990:2026")
        for rec in (j[1] if len(j) > 1 and j[1] else []):
            if rec["value"] is not None:
                rows.append(dict(country=rec["countryiso3code"], year=int(rec["date"]), indicator=ind, value=rec["value"]))
    df = pd.DataFrame(rows)
    df.to_csv(RAW / "worldbank.csv", index=False)
    return df


def pull_brent():
    from fredapi import Fred
    key = os.environ.get("FRED_API_KEY") or sys.exit("FRED_API_KEY is not set. Command Prompt: set FRED_API_KEY=your_key")
    s = Fred(api_key=key).get_series("POILBREUSDM", observation_start="1990-01-01")
    s.rename("brent_usd").to_csv(RAW / "brent_monthly.csv")
    a = s.groupby(s.index.year).mean().rename("brent_usd")
    a.to_csv(RAW / "brent_annual.csv")
    return s, a


def coverage(df, labels, name):
    print(f"\n{name}: first-last year (n obs) by country")
    for ind, desc in labels.items():
        parts = []
        for c in COUNTRIES:
            s = df[(df.indicator == ind) & (df.country == c)]
            parts.append(f"{c} {s.year.min()}-{s.year.max()} ({len(s)})" if len(s) else f"{c} NONE")
        print(f"  {ind:20s} {desc[:40]:40s} " + " | ".join(parts))


def main():
    print("Pulling IMF DataMapper...")
    imf = pull_imf()
    coverage(imf, IMF, "IMF")
    print("\nPulling World Bank...")
    wb = pull_wb()
    coverage(wb, WB, "WORLD BANK")
    print("\nPulling Brent from FRED...")
    m, a = pull_brent()
    print(f"  monthly {m.index[0].date()} -> {m.index[-1].date()} (n={len(m)}); annual {a.index[0]}-{a.index[-1]}")
    print(a.loc[2018:].round(1).to_dict())
    print("\nSaved to", RAW)


if __name__ == "__main__":
    main()
