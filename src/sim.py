"""Brent bootstrap and fiscal-buffer simulation."""
import numpy as np


def fit_ar1(monthly):
    """AR(1) on monthly log Brent: y_t = c + phi*y_{t-1} + e_t. Returns c, phi, residuals."""
    y = np.log(monthly.values)
    X = np.column_stack([np.ones(len(y) - 1), y[:-1]])
    (c, phi), *_ = np.linalg.lstsq(X, y[1:], rcond=None)
    return c, phi, y[1:] - X @ np.array([c, phi])


def brent_paths(monthly, p0, n, years, block=6, seed=0, mode="ar1", mu=None):
    """Annual-average Brent for years 2027..2026+years, starting from price p0 at Sep 2026.

    mode 'ar1': mean-reverting log price (phi, long-run level fitted on 1990-2026 monthly data, or
    long-run level `mu` in $/bbl if given), with block-bootstrapped residuals.
    mode 'rw': random walk with the historical monthly log returns demeaned (zero drift).
    The first three simulated months (Oct-Dec 2026) are dropped from the annual averages.
    """
    rng = np.random.default_rng(seed)
    c, phi, resid = fit_ar1(monthly)
    H = 3 + 12 * years
    nb = int(np.ceil(H / block))
    starts = rng.integers(0, len(resid), size=(n, nb))
    idx = (starts[:, :, None] + np.arange(block)) % len(resid)
    e = resid[idx.reshape(n, -1)[:, :H]]
    y = np.full(n, np.log(p0))
    out = np.zeros((n, H))
    if mode == "ar1":
        long_run = np.log(mu) if mu is not None else c / (1 - phi)
        for t in range(H):
            y = long_run + phi * (y - long_run) + e[:, t]
            out[:, t] = y
    else:
        lr = np.diff(np.log(monthly.values))
        lr = lr - lr.mean()
        starts = rng.integers(0, len(lr), size=(n, nb))
        idx = (starts[:, :, None] + np.arange(block)) % len(lr)
        r = lr[idx.reshape(n, -1)[:, :H]]
        out = np.log(p0) + np.cumsum(r, axis=1)
    price = np.exp(out)
    return price[:, 3:].reshape(n, years, 12).mean(axis=2)


def simulate_buffer(brent, a_b_draws, resid, gdp0_bn, buffer0_bn, g=0.03, ret=0.0, seed=0):
    """brent: (n, Y) annual prices. a_b_draws: (M, 2) bootstrap (a, b). resid: residual pool.

    Returns dict with balance_bn (n, Y) and buffer (n, Y).
    """
    rng = np.random.default_rng(seed)
    n, Y = brent.shape
    k = rng.integers(0, len(a_b_draws), n)
    a, b = a_b_draws[k, 0][:, None], a_b_draws[k, 1][:, None]
    e = rng.choice(resid, size=(n, Y))
    bal_pct = a + b * brent + e
    gdp = gdp0_bn * (1 + g) ** np.arange(1, Y + 1)
    bal_bn = bal_pct / 100 * gdp
    buf = np.zeros((n, Y))
    B = np.full(n, buffer0_bn, dtype=float)
    for t in range(Y):
        B = B * (1 + ret) + bal_bn[:, t]
        buf[:, t] = B
    return dict(bal_pct=bal_pct, bal_bn=bal_bn, buffer=buf)


def stress_metrics(sim, horizon_years):
    buf = sim["buffer"][:, :horizon_years]
    bal = sim["bal_pct"][:, :horizon_years]
    return dict(p_deficit_any=float((bal < 0).any(1).mean()),
                p_exhausted=float((buf < 0).any(1).mean()),
                median_end_buffer=float(np.median(buf[:, -1])),
                p5_end_buffer=float(np.percentile(buf[:, -1], 5)))
