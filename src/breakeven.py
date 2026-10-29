"""Fiscal balance (% GDP) on annual Brent, per country: fit, bootstrap and out-of-sample test."""
import numpy as np
import pandas as pd


def sample(panel, c, start, end, x="brent"):
    d = panel.loc[c]
    d = d[d.actual].loc[start:end, ["bal", x]].dropna()
    return d[x].values, d["bal"].values, d.index.values


def ols(x, y):
    X = np.column_stack([np.ones_like(x), x])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    r2 = 1 - resid.var() / y.var()
    return beta[0], beta[1], r2, resid


def breakeven(a, b):
    return -a / b if b > 0 else np.nan


def pairs_bootstrap(x, y, n=3000, seed=0):
    rng = np.random.default_rng(seed)
    out = np.zeros((n, 2))
    k = 0
    while k < n:
        i = rng.integers(0, len(x), len(x))
        if np.ptp(x[i]) < 1e-9:
            continue
        a, b, _, _ = ols(x[i], y[i])
        out[k] = (a, b); k += 1
    return out


def summarise_country(panel, c, start=2010, end=2025, x="brent", n=3000):
    xs, ys, yrs = sample(panel, c, start, end, x)
    a, b, r2, resid = ols(xs, ys)
    bs = pairs_bootstrap(xs, ys, n, seed=1)
    be = np.array([breakeven(*r) for r in bs])
    valid = be[(bs[:, 1] > 0.02) & np.isfinite(be)]
    return dict(country=c, start=start, end=end, x=x, n=len(xs), a=a, b=b, r2=r2,
                breakeven=breakeven(a, b),
                be_lo=np.percentile(valid, 5) if len(valid) else np.nan,
                be_hi=np.percentile(valid, 95) if len(valid) else np.nan,
                slope_lo=np.percentile(bs[:, 1], 5), slope_hi=np.percentile(bs[:, 1], 95),
                share_slope_le_0p02=float((bs[:, 1] <= 0.02).mean()),
                resid_sd=resid.std(ddof=2)), bs, resid


def out_of_sample(panel, c, first_fit_end=2015, last=2025, start=2010):
    """Expanding-window one-step-ahead forecast of the balance using same-year Brent."""
    rows = []
    for t in range(first_fit_end + 1, last + 1):
        xs, ys, _ = sample(panel, c, start, t - 1)
        a, b, _, _ = ols(xs, ys)
        d = panel.loc[c].loc[t]
        pred = a + b * d["brent"]
        prev = panel.loc[c].loc[t - 1, "bal"]
        rows.append(dict(country=c, year=t, actual=d["bal"], pred=pred, naive=prev))
    r = pd.DataFrame(rows)
    return r
