import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
                     "figure.dpi": 150, "axes.grid": True, "grid.alpha": 0.25})


def fig_scatter(panel, fits, names, path, sub):
    fig, axs = plt.subplots(2, 3, figsize=(10.5, 6), sharex=True)
    for ax, c in zip(axs.ravel(), names):
        d = panel.loc[c]; d = d[d.actual & (d.index >= 2010)]
        ax.scatter(d.brent, d.bal, s=22, color="#2a6f97")
        for y, r in d.iterrows():
            if y in (2015, 2020, 2022, 2025):
                ax.annotate(str(y), (r.brent, r.bal), fontsize=7, xytext=(3, 3), textcoords="offset points")
        f = fits[c]; xs = np.linspace(40, 115, 50)
        ax.plot(xs, f["a"] + f["b"] * xs, color="#c8553d", lw=1.8)
        ax.axhline(0, color="grey", lw=0.8)
        ax.set_title(f"{names[c]}  (breakeven ${f['breakeven']:.0f}, R²={f['r2']:.2f})", fontsize=9, loc="left", fontweight="bold")
    for ax in axs[1]: ax.set_xlabel("Brent, $/bbl annual average")
    for ax in axs[:, 0]: ax.set_ylabel("Fiscal balance, % GDP")
    fig.suptitle("Fiscal balance against oil price, 2010-2025", x=0.01, ha="left", fontweight="bold")
    fig.text(0.01, 0.005, sub, fontsize=7.5, color="#555")
    fig.tight_layout(rect=(0, 0.02, 1, 0.96)); fig.savefig(path); plt.close(fig)


def fig_breakeven(rows, names, path, sub):
    """rows: list of dicts with country, label, breakeven, be_lo, be_hi."""
    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    labels = sorted({r["label"] for r in rows}, key=lambda s: ["2010-2025 (base)", "2005-2025", "2014-2025", "2010-2021", "2yr avg Brent"].index(s)
                    if s in ["2010-2025 (base)", "2005-2025", "2014-2025", "2010-2021", "2yr avg Brent"] else 9)
    cols = ["#2a6f97", "#8d99ae", "#e9a23b", "#2a9d8f", "#c8553d"]
    cs = list(names)
    for j, lab in enumerate(labels):
        for i, c in enumerate(cs):
            r = [x for x in rows if x["country"] == c and x["label"] == lab]
            if not r: continue
            r = r[0]; xpos = i + (j - len(labels) / 2) * 0.14
            ax.errorbar(xpos, r["breakeven"], yerr=[[max(r["breakeven"] - r["be_lo"], 0)], [max(r["be_hi"] - r["breakeven"], 0)]],
                        fmt="o", color=cols[j % 5], ms=4, capsize=2, lw=1, label=lab if i == 0 else None)
    ax.set_xticks(range(len(cs))); ax.set_xticklabels([names[c] for c in cs])
    ax.set_ylabel("Brent price at which balance = 0, $/bbl"); ax.set_ylim(0, 200)
    ax.set_title("Implied fiscal breakeven oil price (90% bootstrap interval)", loc="left", fontweight="bold")
    ax.legend(frameon=False, fontsize=8, ncol=2); fig.text(0.01, 0.01, sub, fontsize=7.5, color="#555")
    fig.tight_layout(rect=(0, 0.03, 1, 1)); fig.savefig(path); plt.close(fig)


def fig_runway(tabs, prices, names, path, sub):
    fig, axs = plt.subplots(1, len(tabs), figsize=(5.2 * len(tabs), 4.2), sharey=True)
    for ax, (title, M) in zip(np.atleast_1d(axs), tabs.items()):
        im = ax.imshow(np.minimum(M, 30), aspect="auto", cmap="RdYlGn", vmin=0, vmax=30)
        ax.set_xticks(range(len(prices))); ax.set_xticklabels([f"${p}" for p in prices], fontsize=8)
        ax.set_yticks(range(len(names))); ax.set_yticklabels(list(names.values()))
        for i in range(M.shape[0]):
            for j in range(M.shape[1]):
                v = M[i, j]
                ax.text(j, i, "n/a" if np.isnan(v) else ("30+" if v >= 30 else f"{v:.0f}" if v >= 10 else f"{v:.1f}"),
                        ha="center", va="center", fontsize=8)
        ax.grid(False); ax.set_title(title, loc="left", fontweight="bold", fontsize=9); ax.set_xlabel("Brent, flat price")
    fig.suptitle("Years of buffer at a sustained flat oil price (green = longer)", x=0.01, ha="left", fontweight="bold")
    fig.text(0.01, 0.005, sub, fontsize=7.5, color="#555")
    fig.tight_layout(rect=(0, 0.03, 1, 0.94)); fig.savefig(path); plt.close(fig)


def fig_exhaust(vals, names, path, sub):
    fig, ax = plt.subplots(figsize=(8.5, 4.4))
    labs = list(next(iter(vals.values())).keys()); cols = ["#c8553d", "#e9a23b", "#2a9d8f"]
    w = 0.26
    for j, lab in enumerate(labs):
        ys = [vals[c][lab] * 100 for c in names]
        ax.bar(np.arange(len(names)) + (j - 1) * w, ys, w, color=cols[j], label=lab)
    ax.set_xticks(range(len(names))); ax.set_xticklabels(list(names.values()))
    ax.set_ylabel("Paths where the buffer runs out within 10 years, %"); ax.legend(frameon=False, fontsize=8)
    ax.set_title("Probability the buffer is exhausted within 10 years", loc="left", fontweight="bold")
    fig.text(0.01, 0.01, sub, fontsize=7.5, color="#555"); fig.tight_layout(rect=(0, 0.03, 1, 1)); fig.savefig(path); plt.close(fig)
