"""GCC fiscal stress test.  Run after fetch_data.py:  python run_all.py"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from src import assumptions, breakeven as be, data, plots, sim  # noqa: E402

RES, FIG = ROOT / "results", ROOT / "figures"
RES.mkdir(exist_ok=True); FIG.mkdir(exist_ok=True)
N, YEARS = 20000, 10
GRID = [40, 50, 60, 70, 80, 90, 100, 110]


def main():
    panel = data.load_panel()
    monthly = data.load_brent_monthly()
    P0 = float(monthly.iloc[-1])
    print(f"Brent latest month {monthly.index[-1].date()}: ${P0:.1f}; 2026 YTD avg ${monthly.loc['2026'].mean():.1f}")

    # 1. breakevens ---------------------------------------------------------------------------
    variants = [("2010-2025 (base)", 2010, 2025, "brent"), ("2005-2025", 2005, 2025, "brent"),
                ("2014-2025", 2014, 2025, "brent"), ("2010-2021", 2010, 2021, "brent"),
                ("2yr avg Brent", 2010, 2025, "brent_2yr")]
    rows, boots, fits = [], {}, {}
    for lab, s, e, x in variants:
        for c in data.COUNTRIES:
            r, bs, resid = be.summarise_country(panel, c, s, e, x)
            r["label"] = lab; rows.append(r)
            if lab.endswith("(base)"):
                boots[c] = (bs, resid); fits[c] = r
    bt = pd.DataFrame(rows); bt.to_csv(RES / "breakeven_estimates.csv", index=False)
    print("\nBREAKEVEN (base sample 2010-2025)")
    print(bt[bt.label.str.endswith("(base)")][["country", "n", "a", "b", "r2", "breakeven", "be_lo", "be_hi", "share_slope_le_0p02", "resid_sd"]].round(2).to_string(index=False))
    print("\nBREAKEVEN across samples\n", bt.pivot(index="country", columns="label", values="breakeven").round(0).to_string())

    oos = pd.concat([be.out_of_sample(panel, c) for c in data.COUNTRIES])
    oos.to_csv(RES / "out_of_sample.csv", index=False)
    oos_s = oos.groupby("country").apply(lambda d: pd.Series(dict(
        rmse_model=float(((d.actual - d.pred) ** 2).mean() ** .5), rmse_naive=float(((d.actual - d.naive) ** 2).mean() ** .5),
        bias=float((d.actual - d.pred).mean()), n=len(d))), include_groups=False)
    oos_s.to_csv(RES / "out_of_sample_summary.csv")
    print("\nOUT-OF-SAMPLE one-step-ahead 2016-2025 (balance, % GDP)\n", oos_s.round(2).to_string())

    # 2. 2026 check: model vs IMF projection ------------------------------------------------------
    ytd = float(monthly.loc["2026"].mean())
    chk = []
    for c in data.COUNTRIES:
        f = fits[c]
        chk.append(dict(country=c, model_2026=f["a"] + f["b"] * ytd, imf_2026_projection=float(panel.loc[(c, 2026), "bal"])))
    chk = pd.DataFrame(chk); chk.to_csv(RES / "check_2026_vs_imf.csv", index=False)
    print(f"\n2026 CHECK (model at Brent YTD ${ytd:.0f} vs IMF projection), % GDP\n", chk.round(1).to_string(index=False))

    # 3. flat-price runway ---------------------------------------------------------------------------
    gdp26 = {c: float(panel.loc[(c, 2026), "gdp_usd_bn"]) for c in data.COUNTRIES}
    res_bn = {c: float(panel.loc[c, "reserves_bn"].dropna().iloc[-1]) for c in data.COUNTRIES}
    buffers = {c: {lab: res_bn[c] + sh * assumptions.SWF_BN[c] for lab, sh in assumptions.LIQUID_SHARES.items()} for c in data.COUNTRIES}
    print("\nBUFFERS (USD bn):"); print(pd.DataFrame(buffers).T.round(0).to_string())
    run_rows, tabs = [], {lab: np.full((6, len(GRID)), np.nan) for lab in assumptions.LIQUID_SHARES}
    for i, c in enumerate(data.COUNTRIES):
        f = fits[c]
        for j, p in enumerate(GRID):
            bal = f["a"] + f["b"] * p
            deficit = -bal / 100 * gdp26[c]
            for lab in assumptions.LIQUID_SHARES:
                yrs = buffers[c][lab] / deficit if deficit > 0 else np.inf
                tabs[lab][i, j] = np.inf if not np.isfinite(yrs) else yrs
                run_rows.append(dict(country=c, brent=p, balance_pct=bal, deficit_bn=max(deficit, 0), buffer=lab, runway_years=yrs))
    rw = pd.DataFrame(run_rows); rw.to_csv(RES / "runway_flat_price.csv", index=False)
    for lab in tabs: tabs[lab][np.isinf(tabs[lab])] = 99
    show = rw[rw.buffer == "reserves + 25% of fund assets"].pivot(index="country", columns="brent", values="runway_years").replace(np.inf, 99).round(1)
    print("\nRUNWAY years at flat Brent (buffer = reserves + 25% fund assets; 99 = no deficit)\n", show.loc[data.COUNTRIES].to_string())

    # 4. simulation ------------------------------------------------------------------------------------
    out_rows = []
    paths = {p0: sim.brent_paths(monthly, p0, N, YEARS, seed=3) for p0 in (P0, 80.0, 65.0)}
    c_ar, phi_ar, _ = sim.fit_ar1(monthly)
    print(f"AR(1) Brent: phi={phi_ar:.4f}, half-life {np.log(.5) / np.log(phi_ar):.0f} months, long-run level ${np.exp(c_ar / (1 - phi_ar)):.0f}")
    pc = np.percentile(paths[P0], [5, 25, 50, 75, 95], axis=0).T
    print("Simulated annual Brent percentiles (5,25,50,75,95), 2027 / 2029 / 2031 / 2036:\n", pc[[0, 2, 4, 9]].round(0))
    for p0, ann in paths.items():
        for c in data.COUNTRIES:
            bs, resid = boots[c]
            for lab in assumptions.LIQUID_SHARES:
                s = sim.simulate_buffer(ann, bs, resid, gdp26[c], buffers[c][lab], g=0.03, ret=0.0, seed=5)
                for h in (5, 10):
                    m = sim.stress_metrics(s, h); m.update(country=c, start_brent=round(p0, 0), buffer=lab, horizon=h)
                    out_rows.append(m)
    ot = pd.DataFrame(out_rows); ot.to_csv(RES / "simulation_results.csv", index=False)
    base = ot[(ot.start_brent == round(P0, 0)) & (ot.horizon == 10)].pivot(index="country", columns="buffer", values="p_exhausted").loc[data.COUNTRIES]
    print(f"\nP(buffer exhausted within 10y), start Brent ${P0:.0f}\n", (base * 100).round(1).to_string())
    b5 = ot[(ot.start_brent == round(P0, 0)) & (ot.horizon == 5)].pivot(index="country", columns="buffer", values="p_exhausted").loc[data.COUNTRIES]
    print("\nWithin 5y\n", (b5 * 100).round(1).to_string())
    anyd = ot[(ot.start_brent == round(P0, 0)) & (ot.horizon == 5) & (ot.buffer == "reserves only")].set_index("country").p_deficit_any
    print("\nP(at least one deficit year in 5y):", (anyd.loc[data.COUNTRIES] * 100).round(0).to_dict())
    for p0 in (80.0, 65.0):
        v = ot[(ot.start_brent == p0) & (ot.horizon == 10)].pivot(index="country", columns="buffer", values="p_exhausted").loc[data.COUNTRIES]
        print(f"\nStart Brent ${p0:.0f}, 10y exhausted %\n", (v * 100).round(1).to_string())

    # 4b. peak cumulative financing need, as % of 2026 GDP (independent of buffer assumptions) -----------------
    need = []
    for c in data.COUNTRIES:
        bs, resid = boots[c]
        s = sim.simulate_buffer(paths[P0], bs, resid, gdp26[c], 0.0, g=0.03, ret=0.0, seed=5)
        for h in (5, 10):
            peak = np.maximum(-s["buffer"][:, :h].min(axis=1), 0)
            need.append(dict(country=c, horizon=h, p50_need_pct_gdp=float(np.percentile(peak, 50) / gdp26[c] * 100),
                             p95_need_pct_gdp=float(np.percentile(peak, 95) / gdp26[c] * 100),
                             p95_need_bn=float(np.percentile(peak, 95)),
                             reserves_pct_gdp=res_bn[c] / gdp26[c] * 100,
                             reserves_plus_25pct_funds_pct_gdp=buffers[c]["reserves + 25% of fund assets"] / gdp26[c] * 100,
                             gross_debt_pct_gdp_2025=float(panel.loc[(c, 2025), "debt"])))
    need = pd.DataFrame(need); need.to_csv(RES / "financing_need.csv", index=False)
    print(f"\nPEAK CUMULATIVE FINANCING NEED (% of 2026 GDP), start Brent ${P0:.0f}")
    print(need[need.horizon == 10].set_index("country").loc[data.COUNTRIES].round(1).to_string())

    # 5. robustness on assumptions ------------------------------------------------------------------------
    rob = []
    ann = paths[P0]
    pm = {"AR(1), long-run $60": sim.brent_paths(monthly, P0, N, YEARS, seed=3, mu=60.0),
          "AR(1), long-run $85": sim.brent_paths(monthly, P0, N, YEARS, seed=3, mu=85.0),
          "random walk, zero drift": sim.brent_paths(monthly, P0, N, YEARS, seed=3, mode="rw")}
    for c in data.COUNTRIES:
        bs, resid = boots[c]
        for lab_v, a2 in pm.items():
            s = sim.simulate_buffer(a2, bs, resid, gdp26[c], buffers[c]["reserves + 25% of fund assets"], seed=5)
            rob.append(dict(country=c, variant="price model: " + lab_v, p_exhausted_10y=sim.stress_metrics(s, 10)["p_exhausted"]))
    for c in data.COUNTRIES:
        bs, resid = boots[c]
        for lab_v, kw in (("base", {}), ("GDP growth 0%", dict(g=0.0)), ("GDP growth 5%", dict(g=0.05)),
                          ("asset return 3%", dict(ret=0.03))):
            kk = dict(g=0.03, ret=0.0); kk.update(kw)
            s = sim.simulate_buffer(ann, bs, resid, gdp26[c], buffers[c]["reserves + 25% of fund assets"], seed=5, **kk)
            rob.append(dict(country=c, variant=lab_v, p_exhausted_10y=sim.stress_metrics(s, 10)["p_exhausted"]))
        # no parameter uncertainty (point estimate only)
        pt = np.array([[fits[c]["a"], fits[c]["b"]]])
        s = sim.simulate_buffer(ann, pt, resid, gdp26[c], buffers[c]["reserves + 25% of fund assets"], seed=5)
        rob.append(dict(country=c, variant="no parameter uncertainty", p_exhausted_10y=sim.stress_metrics(s, 10)["p_exhausted"]))
        # 2yr-avg Brent estimation would need different paths; skip
    rob = pd.DataFrame(rob); rob.to_csv(RES / "robustness_sim.csv", index=False)
    print("\nROBUSTNESS (10y exhausted %, reserves + 25% fund assets)\n",
          (rob.pivot(index="country", columns="variant", values="p_exhausted_10y").loc[data.COUNTRIES] * 100).round(1).to_string())

    # 6. figures ----------------------------------------------------------------------------------------
    sub = "IMF DataMapper (actual years to 2025), FRED Brent. Fiscal balance = IMF general government net lending/borrowing, % GDP."
    plots.fig_scatter(panel, fits, data.NAMES, FIG / "fig1_balance_vs_brent.png", sub)
    plots.fig_breakeven(rows, data.NAMES, FIG / "fig2_breakeven_intervals.png",
                        "Pairs bootstrap, 3,000 draws, 90% interval. Breakeven = overall balance incl. investment income, not the IMF's published breakevens.")
    two = {"Reserves only": tabs["reserves only"], "Reserves + 25% of fund assets": tabs["reserves + 25% of fund assets"]}
    plots.fig_runway(two, GRID, data.NAMES, FIG / "fig3_runway_flat_price.png",
                     "2026 GDP and 2025 reserves; fund assets are third-party estimates. Oman and Bahrain: reserves only (no fund figure found).")
    vals = {c: {lab: float(base.loc[c, lab]) for lab in assumptions.LIQUID_SHARES} for c in data.COUNTRIES}
    plots.fig_exhaust(vals, data.NAMES, FIG / "fig4_exhaustion_probability.png",
                      f"Mean-reverting Brent from ${P0:.0f}, {N:,} paths. Debt financing not modelled: Oman and Bahrain bars mean 'cannot self-fund', not default.")
    (RES / "summary.json").write_text(json.dumps(dict(brent_latest=P0, brent_ytd=ytd, paths=N, years=YEARS,
                                                      buffers_bn=buffers), indent=2, default=float))
    print("\nfigures + results written")


if __name__ == "__main__":
    main()
