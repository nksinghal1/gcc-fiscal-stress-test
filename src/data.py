"""Country-year panel from the raw IMF / World Bank / FRED pulls."""
from pathlib import Path

import numpy as np
import pandas as pd

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
COUNTRIES = ["SAU", "ARE", "QAT", "KWT", "OMN", "BHR"]
NAMES = {"SAU": "Saudi Arabia", "ARE": "UAE", "QAT": "Qatar", "KWT": "Kuwait", "OMN": "Oman", "BHR": "Bahrain"}
LAST_ACTUAL = 2025


def load_panel():
    imf = pd.read_csv(RAW / "imf_datamapper.csv")
    wb = pd.read_csv(RAW / "worldbank.csv")
    br = pd.read_csv(RAW / "brent_annual.csv", index_col=0)["brent_usd"]

    p = imf.pivot_table(index=["country", "year"], columns="indicator", values="value")
    p = p.rename(columns={"GGXCNL_NGDP": "bal", "GGXWDG_NGDP": "debt", "NGDPD": "gdp_usd_bn",
                          "NGDP_RPCH": "growth", "BCA_NGDPD": "ca"})
    res = wb[wb.indicator == "FI.RES.TOTL.CD"].pivot(index="country", columns="year", values="value") / 1e9
    res = res.stack().rename("reserves_bn")
    res.index.names = ["country", "year"]
    p = p.join(res)
    p["brent"] = p.index.get_level_values("year").map(br)
    p["brent_2yr"] = (p["brent"] + p.groupby(level=0)["brent"].shift(1)) / 2
    p["actual"] = p.index.get_level_values("year") <= LAST_ACTUAL
    return p.loc[COUNTRIES]


def load_brent_monthly():
    return pd.read_csv(RAW / "brent_monthly.csv", index_col=0, parse_dates=True)["brent_usd"].dropna()


if __name__ == "__main__":
    p = load_panel()
    print(p.loc["SAU"].tail(6).round(1))
