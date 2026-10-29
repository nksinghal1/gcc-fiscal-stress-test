"""Independent checks of the fiscal model.   python verify.py

1. Breakeven regressions against statsmodels.
2. Brent AR(1) coefficients against statsmodels, and a loop re-implementation of the bootstrap paths.
3. A plain-Python loop re-implementation of the buffer simulation (same random draws).
4. Hand arithmetic for one runway number.
"""
import sys
from pathlib import Path

import numpy as np
import statsmodels.api as sm

sys.path.insert(0, str(Path(__file__).resolve().parent))
from src import breakeven as be, data, sim  # noqa: E402


def main():
    panel = data.load_panel()
    worst = 0.0
    # 1. regressions
    for c in data.COUNTRIES:
        x, y, _ = be.sample(panel, c, 2010, 2025)
        a, b, r2, _ = be.ols(x, y)
        m = sm.OLS(y, sm.add_constant(x)).fit()
        worst = max(worst, abs(a - m.params[0]), abs(b - m.params[1]), abs(r2 - m.rsquared))
    print(f"1. regressions vs statsmodels: max abs difference {worst:.2e}")
    assert worst < 1e-8

    # 2. Brent AR(1)
    monthly = data.load_brent_monthly()
    c0, phi, resid = sim.fit_ar1(monthly)
    y = np.log(monthly.values)
    m = sm.OLS(y[1:], sm.add_constant(y[:-1])).fit()
    d2 = max(abs(c0 - m.params[0]), abs(phi - m.params[1]))
    print(f"2a. AR(1) coefficients vs statsmodels: {d2:.2e}")
    assert d2 < 1e-9
    n, years, block, p0, seed = 50, 4, 6, 100.0, 11
    got = sim.brent_paths(monthly, p0, n, years, block=block, seed=seed)
    rng = np.random.default_rng(seed)
    H = 3 + 12 * years
    nb = int(np.ceil(H / block))
    starts = rng.integers(0, len(resid), size=(n, nb))
    lr = np.log(p0 + 0 * 1.0)
    mu = c0 / (1 - phi)
    d3 = 0.0
    for i in range(n):
        es = []
        for k in range(nb):
            for j in range(block):
                es.append(resid[(starts[i, k] + j) % len(resid)])
        es = es[:H]
        yy, prices = np.log(p0), []
        for t in range(H):
            yy = mu + phi * (yy - mu) + es[t]
            prices.append(np.exp(yy))
        ann = [np.mean(prices[3 + 12 * k: 3 + 12 * (k + 1)]) for k in range(years)]
        d3 = max(d3, max(abs(np.array(ann) - got[i])) / 100)
    print(f"2b. Brent paths vs loop re-implementation: {d3:.2e} (relative)")
    assert d3 < 1e-9

    # 3. buffer simulation loop
    worst = 0.0
    for c in data.COUNTRIES:
        r, bs, res = be.summarise_country(panel, c, 2010, 2025, n=300)
        for g, ret, b0 in ((0.03, 0.0, 300.0), (0.05, 0.03, 50.0)):
            brent = sim.brent_paths(monthly, 102.0, 40, 10, seed=3)
            s = sim.simulate_buffer(brent, bs, res, 1000.0, b0, g=g, ret=ret, seed=5)
            rng = np.random.default_rng(5)
            k = rng.integers(0, len(bs), 40)
            e = rng.choice(res, size=(40, 10))
            for i in range(40):
                B = b0
                for t in range(10):
                    pct = bs[k[i], 0] + bs[k[i], 1] * brent[i, t] + e[i, t]
                    flow = pct / 100 * 1000.0 * (1 + g) ** (t + 1)
                    B = B * (1 + ret) + flow
                    worst = max(worst, abs(B - s["buffer"][i, t]) / 1000)
    print(f"3. buffer simulation vs loop re-implementation: {worst:.2e} (relative to GDP)")
    assert worst < 1e-9

    # 4. one runway number by hand: Saudi Arabia at $70 flat, buffer = reserves
    x, y, _ = be.sample(panel, "SAU", 2010, 2025)
    a, b, _, _ = be.ols(x, y)
    gdp = float(panel.loc[("SAU", 2026), "gdp_usd_bn"]); res_bn = float(panel.loc["SAU", "reserves_bn"].dropna().iloc[-1])
    bal = a + b * 70
    runway = res_bn / (-bal / 100 * gdp)
    print(f"4. Saudi at $70: balance {bal:.2f}% GDP, deficit ${-bal / 100 * gdp:.1f}bn, reserves ${res_bn:.0f}bn -> {runway:.1f} years")
    print("PASS")


if __name__ == "__main__":
    main()
