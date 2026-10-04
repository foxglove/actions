"""Draft report for one study repository. Chart titles are computed from the data.

STUDY_REPO selects the repository. app keeps writing out/. Other repositories
write out/<repo>/ so the app report stays in place.
"""

from __future__ import annotations

import json
import html
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from common import current_study

S = current_study()
ROOT = S.root
OUT = S.out
CHARTS = OUT / "charts"
APP = "#0072B2"
GRAY = "#B0B0B0"
ORANGE = "#E69F00"
VERM = "#D55E00"
GREEN = "#009E73"
SKY = "#56B4E9"
PURPLE = "#CC79A7"
BLACK = "#222222"

MONTH_LABELS = {
    "2026-04": "Apr",
    "2026-05": "May",
    "2026-06": "Jun",
    "2026-07": "Jul",
    "2026-08": "Aug",
    "2026-09": "Sep",
}

# Config changes that can move the LGTM pool. Dates are annotations, not causes.
ANNOTATIONS = [
    ("2026-06-18", "LGTM wording;\ndrafts skipped"),
    ("2026-07-26", "Opus 5"),
    ("2026-07-28", "back to\nOpus 4.8"),
    ("2026-09-22", "Opus 5.5;\ninline findings"),
]


def pct(x) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "n/a"
    return f"{100 * x:.0f}%"


def hours(x) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "n/a"
    if x < 0:
        return f"−{abs(x):.1f} h"
    return f"{x:.1f} h"


def save_fig(fig, name: str) -> str:
    CHARTS.mkdir(parents=True, exist_ok=True)
    svg_path = CHARTS / f"{name}.svg"
    png_path = CHARTS / f"{name}.png"
    fig.savefig(svg_path, format="svg", bbox_inches="tight")
    fig.savefig(png_path, format="png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    return svg_path.read_text()


def style_ax(ax, title: str, xlabel: str, ylabel: str):
    ax.set_title(title, loc="left", fontsize=11, color=BLACK, pad=10, wrap=True)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", color="#eeeeee")
    ax.set_axisbelow(True)


def overlap(lo_a, hi_a, lo_b, hi_b) -> str:
    if None in (lo_a, hi_a, lo_b, hi_b):
        return "unknown"
    if hi_a < lo_b:
        return "up"
    if hi_b < lo_a:
        return "down"
    return "flat"


def monthly_title(monthly: pd.DataFrame, rate_col: str, what: str) -> str:
    if monthly.empty:
        return f"{what} is not estimated"
    a = monthly.iloc[0]
    b = monthly.iloc[-1]
    move = overlap(a[f"{rate_col}_lo"], a[f"{rate_col}_hi"], b[f"{rate_col}_lo"], b[f"{rate_col}_hi"])
    na, nb = int(a[f"{rate_col}_n"]), int(b[f"{rate_col}_n"])
    if na < 10 or nb < 10:
        return (
            f"{what} cannot be compared from {MONTH_LABELS.get(a['month'], a['month'])} "
            f"to September because a month has n<10 (n={na} and n={nb})"
        )
    word = {"up": "rose", "down": "fell", "flat": "showed no clear change", "unknown": "is incomplete"}[move]
    return (
        f"{what} {word} from {pct(a[f'{rate_col}_rate'])} in {MONTH_LABELS.get(a['month'], a['month'])} "
        f"to {pct(b[f'{rate_col}_rate'])} in September"
    )


def chart_sufficiency(monthly: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=(9.2, 4.6))
    x = np.arange(len(monthly))
    y = monthly["bot_sufficient_rate"].astype(float)
    lo = monthly["bot_sufficient_lo"].astype(float)
    hi = monthly["bot_sufficient_hi"].astype(float)
    n = monthly["bot_sufficient_n"].astype(int)
    colors = [APP if ni >= 10 else GRAY for ni in n]
    ax.fill_between(x, lo, hi, color=APP, alpha=0.15, label="95% Wilson interval")
    ax.plot(x, y, color=APP, marker="o")
    for i, (xi, yi, ni) in enumerate(zip(x, y, n)):
        ax.scatter([xi], [yi], color=colors[i], zorder=3)
        ax.annotate(f"n={ni}", (xi, yi), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=8)
    ax.set_xticks(x, [MONTH_LABELS[m] for m in monthly["month"]])
    ax.set_ylim(0, 1)
    ax.axvspan(5 - 0.5, 5 + 0.5, color="#f4f4f4", zorder=0)
    style_ax(
        ax,
        monthly_title(monthly, "bot_sufficient", "Bot-sufficient rate in app"),
        "PR open month",
        "Share of merged human PRs with a bot LGTM",
    )
    fig.text(0.01, -0.02, "September has a partial 30-day follow-up window. Gray points have n<10.", fontsize=8, color="#555")
    return save_fig(fig, "bot_sufficient_by_month")


def chart_buckets(monthly: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=(9.2, 4.6))
    x = np.arange(len(monthly))
    series = [
        ("A_rate", "A human catch CI would miss", VERM),
        ("Aci_rate", "A-ci", ORANGE),
        ("B_rate", "B escaped, lower bound", PURPLE),
        ("D_rate", "D introduced after LGTM", SKY),
    ]
    for col, label, color in series:
        y = monthly[col].astype(float)
        n = monthly["bot_sufficient_n"].astype(int)
        ax.plot(x, y, marker="o", label=label, color=color)
        for xi, yi, ni in zip(x, y, n):
            if ni < 10:
                ax.scatter([xi], [yi], color=GRAY, zorder=3)
    ax.set_xticks(x, [MONTH_LABELS[m] for m in monthly["month"]])
    ax.set_ylim(0, max(0.2, float(np.nanmax(monthly[["A_rate", "Aci_rate", "B_rate", "D_rate"]].values)) * 1.4))
    ax.legend(frameon=False, fontsize=8)
    ax.axvspan(5 - 0.5, 5 + 0.5, color="#f4f4f4", zorder=0)
    style_ax(ax, "Bucket rates in app, with September's follow-up still open", "PR open month", "Share of merged human PRs with a bot LGTM")
    return save_fig(fig, "bucket_rates_by_month")


def chart_categories(findings: pd.DataFrame) -> str:
    cats = [
        "BUG",
        "SECURITY",
        "DATA_LOSS_OR_CORRUPTION",
        "PERF",
        "DESIGN/ARCHITECTURE",
        "TEST_GAP",
        "NIT/STYLE",
        "QUESTION/NO_CHANGE",
    ]
    colors = [VERM, "#000000", ORANGE, PURPLE, SKY, GREEN, GRAY, "#DDDDDD"]
    sub = findings[(findings["timing"] == "after") & (findings["in_cohort"] == True) & (findings["is_real"] == True)]
    months = list(MONTH_LABELS)
    fig, ax = plt.subplots(figsize=(9.2, 4.6))
    bottom = np.zeros(len(months))
    for cat, color in zip(cats, colors):
        heights = []
        for month in months:
            g = sub[sub["month"] == month]
            heights.append((g["category"] == cat).sum() / len(g) if len(g) else 0)
        ax.bar(range(len(months)), heights, bottom=bottom, color=color, label=cat, width=0.8)
        bottom += np.array(heights)
    for i, month in enumerate(months):
        n = int((sub["month"] == month).sum())
        ax.annotate(f"n={n}", (i, 1.02), ha="center", fontsize=8, color=GRAY if n < 10 else BLACK)
    ax.set_xticks(range(len(months)), [MONTH_LABELS[m] for m in months])
    ax.set_ylim(0, 1.15)
    ax.legend(frameon=False, fontsize=7, ncol=2)
    style_ax(ax, "Mix of real human findings after the bot LGTM, by month", "PR open month", "Share of real findings after LGTM")
    return save_fig(fig, "categories_after_lgtm")


def chart_time(monthly: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=(9.2, 4.6))
    x = np.arange(len(monthly))
    for col, label, color in (
        ("lgtm_to_merge", "LGTM to merge", APP),
        ("lgtm_to_approval", "LGTM to first human approval", ORANGE),
    ):
        p50 = monthly[f"{col}_p50"].astype(float)
        p90 = monthly[f"{col}_p90"].astype(float)
        ax.plot(x, p50, marker="o", color=color, label=f"{label} p50")
        ax.fill_between(x, p50, p90, color=color, alpha=0.12)
    ax.set_yscale("log")
    ax.set_xticks(x, [MONTH_LABELS[m] for m in monthly["month"]])
    style_ax(ax, "Calendar time after the bot LGTM, p50 line and p50 to p90 band", "PR open month", "Hours (log scale)")
    ax.legend(frameon=False, fontsize=8)
    return save_fig(fig, "time_after_lgtm")


def chart_coverage(monthly: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=(9.2, 4.2))
    x = np.arange(len(monthly))
    y = monthly["bot_coverage_rate"].astype(float)
    n = monthly["bot_coverage_n"].astype(int)
    ax.bar(x, y, color=[APP if ni >= 10 else GRAY for ni in n])
    for xi, yi, ni in zip(x, y, n):
        ax.annotate(f"n={ni}", (xi, yi), textcoords="offset points", xytext=(0, 4), ha="center", fontsize=8)
    ax.axvline(2, color=ORANGE, ls="--", lw=1, label="18 Jun: LGTM text starts")
    ax.set_xticks(x, [MONTH_LABELS[m] for m in monthly["month"]])
    ax.set_ylim(0, 1.15)
    ax.legend(frameon=False, fontsize=8)
    style_ax(ax, monthly_title(monthly, "bot_coverage", "Bot LGTM coverage in app"), "PR open month", "Share of opened PRs with a bot LGTM")
    return save_fig(fig, "bot_coverage")


def chart_size_time(prs: pd.DataFrame) -> str:
    order = ["XS", "S", "M", "L", "XL"]
    data, labels, ns = [], [], []
    merged = prs[(prs["in_cohort"] == True) & (prs["author_type"] == "human") & (prs["merged"] == True) & (prs["bot_lgtm"] == True)]
    for bucket in order:
        vals = merged.loc[merged["size_bucket"] == bucket, "lgtm_to_merge_h"].dropna()
        vals = vals[vals > 0]
        data.append(vals.values if len(vals) else np.array([np.nan]))
        labels.append(bucket)
        ns.append(len(vals))
    fig, ax = plt.subplots(figsize=(8.4, 4.4))
    bp = ax.boxplot(data, tick_labels=[f"{lb}\nn={n}" for lb, n in zip(labels, ns)], showfliers=False)
    for i, n in enumerate(ns, start=1):
        if n < 10:
            plt.setp(bp["boxes"][i - 1], color=GRAY)
    ax.set_yscale("log")
    # title from ends
    meds = [float(np.median(v)) if len(v) and np.isfinite(v).any() else None for v in data]
    title = "Time from bot LGTM to merge by PR size"
    if meds[0] and meds[-1]:
        title = f"Median LGTM-to-merge time is {meds[0]:.1f} h on XS PRs and {meds[-1]:.1f} h on XL PRs"
    style_ax(ax, title, "Size (additions + deletions)", "Hours from first bot LGTM to merge (log scale)")
    return save_fig(fig, "lgtm_to_merge_by_size")


def chart_ecdf(prs: pd.DataFrame) -> str:
    merged = prs[(prs["in_cohort"] == True) & (prs["author_type"] == "human") & (prs["merged"] == True) & (prs["bot_lgtm"] == True)]
    vals = np.sort(merged["lgtm_to_merge_h"].dropna().values)
    vals = vals[vals > 0]
    fig, ax = plt.subplots(figsize=(8.4, 4.4))
    if len(vals):
        y = np.arange(1, len(vals) + 1) / len(vals)
        ax.plot(vals, y, color=APP)
        p50 = np.median(vals)
        ax.axvline(p50, color=ORANGE, ls="--", lw=1)
        title = f"Half of app PRs merged within {p50:.1f} hours of the bot LGTM (n={len(vals)})"
    else:
        title = "No merged bot-LGTM PRs to plot"
    ax.set_xscale("log")
    style_ax(ax, title, "Hours from first bot LGTM to merge (log scale)", "Cumulative share of PRs")
    return save_fig(fig, "ecdf_lgtm_to_merge")


def chart_buckets_stacked(prs: pd.DataFrame) -> str:
    merged = prs[(prs["in_cohort"] == True) & (prs["author_type"] == "human") & (prs["merged"] == True) & (prs["bot_lgtm"] == True)]
    n = len(merged)
    counts = {
        "A": int(merged["in_A"].sum()) if n else 0,
        "A-ci": int(merged["in_Aci"].sum()) if n else 0,
        "B": int(merged["in_B"].sum()) if n else 0,
        "D": int(merged["in_D"].sum()) if n else 0,
    }
    # C is the remainder only for PRs in none of these. Overlap means the bar is not a partition.
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    labels = list(counts)
    vals = [counts[k] / n if n else 0 for k in labels]
    colors = [VERM, ORANGE, PURPLE, SKY]
    ax.bar(labels, vals, color=colors)
    for i, (lab, v) in enumerate(zip(labels, vals)):
        ax.annotate(f"n={counts[lab]}", (i, v), textcoords="offset points", xytext=(0, 4), ha="center", fontsize=8)
    style_ax(
        ax,
        f"Bucket membership overlaps; B is a lower bound (n={n} merged human PRs with a bot LGTM)",
        "Bucket",
        "Share of PRs (a PR can be in more than one)",
    )
    return save_fig(fig, "buckets_overall")


def chart_funnel(prs: pd.DataFrame, findings: pd.DataFrame) -> str:
    merged = prs[(prs["in_cohort"] == True) & (prs["author_type"] == "human") & (prs["merged"] == True) & (prs["bot_lgtm"] == True)]
    ids = set(merged["number"].astype(int))
    after = findings[(findings["timing"] == "after") & (findings["pr"].isin(ids))]
    with_comments = set(after["pr"].astype(int))
    defects = after[after["category"].isin(["BUG", "SECURITY", "DATA_LOSS_OR_CORRUPTION"]) & (after["is_real"] == True)]
    with_defect = set(defects["pr"].astype(int))
    changed = set(defects[defects["code_change"] == True]["pr"].astype(int))
    not_ci = set(merged[merged["in_A"] == True]["number"].astype(int))
    stages = [
        ("Bot LGTM, merged", len(ids)),
        ("Human finding after LGTM", len(with_comments)),
        ("Real bug / security / data loss", len(with_defect)),
        ("That finding changed code", len(changed)),
        ("And CI would not have caught it", len(not_ci)),
    ]
    fig, ax = plt.subplots(figsize=(9.2, 4.2))
    ys = np.arange(len(stages))[::-1]
    ax.barh(ys, [s[1] for s in stages], color=APP)
    for y, (lab, n) in zip(ys, stages):
        ax.annotate(f"{lab}  n={n}", (n, y), textcoords="offset points", xytext=(6, 0), va="center", fontsize=8)
    ax.set_yticks([])
    top, last = stages[0][1], stages[-1][1]
    if top:
        share = last / top
        title = (
            f"{last} of {top} merged bot-LGTM PRs ({share:.0%}) end in a defect catch CI would not have caught"
        )
    else:
        title = "No merged bot-LGTM PRs to put in the catch funnel"
    style_ax(ax, title, "Pull requests", "")
    return save_fig(fig, "catch_funnel")


def chart_approval(comp: pd.DataFrame) -> str:
    sub = comp[comp["month"] == "all"]
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    if sub.empty:
        style_ax(ax, "Approval comparison has no rows", "", "")
        return save_fig(fig, "approval_comparison")
    xs = np.arange(len(sub))
    rates = sub["rate"].astype(float).fillna(0)
    lo = sub["lo"].astype(float)
    hi = sub["hi"].astype(float)
    colors = [GRAY if int(n) < 10 else APP for n in sub["n"]]
    ax.bar(xs, rates, color=colors)
    # A zero rate can sit a float-epsilon below the Wilson lower bound.
    low_err = np.clip(rates.to_numpy() - lo.fillna(rates).to_numpy(), 0, None)
    high_err = np.clip(hi.fillna(rates).to_numpy() - rates.to_numpy(), 0, None)
    ax.errorbar(xs, rates, yerr=[low_err, high_err], fmt="none", ecolor=BLACK, capsize=4)
    ax.set_xticks(xs, [f"{g}\nn={n}" for g, n in zip(sub["group"], sub["n"])])
    ax.set_ylim(0, 1)
    n0 = int(sub.loc[sub["group"] == "no_human_approval", "n"].iloc[0]) if (sub["group"] == "no_human_approval").any() else 0
    title = (
        "Escape-rate comparison is thin because few PRs merged with no human approval"
        if n0 < 30
        else "Escape rate for PRs merged with and without a human approval"
    )
    style_ax(ax, title, "Observed merge path", "Bucket B rate (Wilson 95% interval)")
    return save_fig(fig, "approval_comparison")


def dev_heatmap(dev: pd.DataFrame) -> str:
    total = dev[dev["month"] == "all"].sort_values("authored_prs", ascending=False)
    people = total["person"].head(25).tolist()
    months = list(MONTH_LABELS)
    mat = np.full((len(people), len(months)), np.nan)
    annot_n = np.zeros_like(mat)
    for i, person in enumerate(people):
        for j, month in enumerate(months):
            row = dev[(dev["person"] == person) & (dev["month"] == month)]
            if row.empty:
                continue
            r = row.iloc[0]
            annot_n[i, j] = r["bot_sufficient_n"]
            if r["bot_sufficient_n"] and r["bot_sufficient_rate"] == r["bot_sufficient_rate"]:
                mat[i, j] = r["bot_sufficient_rate"]
    fig_h = max(4.5, 0.28 * len(people) + 1.5)
    fig, ax = plt.subplots(figsize=(8.6, fig_h))
    cmap = plt.cm.Blues.copy()
    cmap.set_bad("#f3f3f3")
    im = ax.imshow(mat, aspect="auto", cmap=cmap, vmin=0, vmax=1)
    for i in range(len(people)):
        for j in range(len(months)):
            n = annot_n[i, j]
            if n <= 0:
                continue
            color = "#666" if n < 10 else "black"
            ax.text(j, i, f"{int(n)}", ha="center", va="center", fontsize=7, color=color)
    ax.set_xticks(range(len(months)), [MONTH_LABELS[m] for m in months])
    ax.set_yticks(range(len(people)), people, fontsize=8)
    fig.colorbar(im, ax=ax, fraction=0.03, label="Bot-sufficient rate")
    ax.set_title("Bot-sufficient rate on each author's PRs (cell text is n; gray text is n<10)", loc="left", fontsize=11)
    return save_fig(fig, "dev_heatmap")


def dev_scatter(dev: pd.DataFrame) -> str:
    total = dev[(dev["month"] == "all") & (dev["reviews"] > 0)].copy()
    fig, ax = plt.subplots(figsize=(8.2, 5.2))
    if total.empty:
        style_ax(ax, "No reviewer rows", "", "")
        return save_fig(fig, "reviewer_scatter")
    x = total["response_hours_p50"].astype(float)
    y = total["hm_catch_per_review"].astype(float)
    s = total["reviews"].astype(float)
    colors = [APP if n >= 10 else GRAY for n in total["reviews"]]
    ax.scatter(x, y, s=np.clip(s, 20, 400), c=colors, alpha=0.85)
    ax.set_xscale("log")
    style_ax(
        ax,
        "Reviewer response time and high/medium defect comments per review (bubble = review count)",
        "Median hours from later of review request or bot LGTM to first review (log scale)",
        "High/medium bug, security, or data-loss findings per review",
    )
    return save_fig(fig, "reviewer_scatter")


def dev_load(dev: pd.DataFrame) -> str:
    months = list(MONTH_LABELS)
    fig, ax = plt.subplots(figsize=(9.2, 4.6))
    # top 8 reviewers by total reviews, rest as other
    total = dev[dev["month"] == "all"].sort_values("reviews", ascending=False)
    top = total.head(8)["person"].tolist()
    bottom = np.zeros(len(months))
    cmap = plt.cm.tab10.colors
    for i, person in enumerate(top):
        heights = []
        for month in months:
            row = dev[(dev["person"] == person) & (dev["month"] == month)]
            month_total = dev[dev["month"] == month]["reviews"].sum()
            val = float(row["reviews"].iloc[0]) / month_total if len(row) and month_total else 0
            heights.append(val)
        ax.bar(range(len(months)), heights, bottom=bottom, color=cmap[i % 10], label=person, width=0.8)
        bottom += np.array(heights)
    other = 1 - bottom
    ax.bar(range(len(months)), np.clip(other, 0, 1), bottom=bottom, color=GRAY, label="everyone else")
    ax.set_xticks(range(len(months)), [MONTH_LABELS[m] for m in months])
    ax.set_ylim(0, 1.05)
    ax.legend(frameon=False, fontsize=7, ncol=2)
    style_ax(ax, "Share of human reviews in app, by month", "PR open month", "Share of reviews")
    return save_fig(fig, "review_load")


def _flag(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series(False, index=df.index)
    return df[col].fillna(False).astype(bool)


def overlap_counts(df: pd.DataFrame) -> dict[str, int]:
    """Exclusive regions for the headline pull requests."""
    a = _flag(df, "in_A")
    ac = _flag(df, "in_Aci")
    b = _flag(df, "in_B")
    d = _flag(df, "in_D")
    return {
        "n": int(len(df)),
        "A": int(a.sum()),
        "Aci": int(ac.sum()),
        "B": int(b.sum()),
        "D": int(d.sum()),
        "A_only": int((a & ~b).sum()),
        "B_only": int((~a & b).sum()),
        "AB": int((a & b).sum()),
        "sufficient": int((~a & ~b).sum()),
        "abd_A": int((a & ~b & ~d).sum()),
        "abd_B": int((~a & b & ~d).sum()),
        "abd_D": int((~a & ~b & d).sum()),
        "abd_AB": int((a & b & ~d).sum()),
        "abd_AD": int((a & ~b & d).sum()),
        "abd_BD": int((~a & b & d).sum()),
        "abd_ABD": int((a & b & d).sum()),
        "A_not_Aci": int((a & ~ac).sum()),
        "Aci_not_A": int((~a & ac).sum()),
        "A_and_Aci": int((a & ac).sum()),
        "C": int((~a & ~ac & ~b & ~d).sum()),
    }


def _circle(cx: int, cy: int, r: int, fill: str) -> str:
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" fill-opacity="0.38" stroke="{fill}" stroke-width="2"/>'


def _vlabel(x: int, y: int, number: int, caption: str) -> str:
    return (
        f'<text x="{x}" y="{y}" text-anchor="middle" font-family="Helvetica, Arial, sans-serif" font-size="18" font-weight="700" fill="{BLACK}">{number}</text>'
        f'<text x="{x}" y="{y + 16}" text-anchor="middle" font-family="Helvetica, Arial, sans-serif" font-size="11" fill="{BLACK}">{html.escape(caption)}</text>'
    )


def venn_ab(c: dict[str, int]) -> str:
    """Two circles: bucket A and bucket B. Their union is what removes bot-sufficient."""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 300" role="img" aria-label="Venn diagram of bucket A and bucket B">
{_circle(220, 145, 115, VERM)}
{_circle(390, 145, 115, PURPLE)}
{_vlabel(165, 140, c["A_only"], "A only")}
{_vlabel(445, 140, c["B_only"], "B only")}
{_vlabel(305, 140, c["AB"], "A and B")}
<text x="320" y="278" text-anchor="middle" font-family="Helvetica, Arial, sans-serif" font-size="13" fill="{BLACK}">{c["sufficient"]} pull requests are outside both circles. Those are bot-sufficient.</text>
</svg>"""


def venn_abd(c: dict[str, int]) -> str:
    """Three circles: A, B, and D. A-ci is drawn separately because it is a different claim."""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 430" role="img" aria-label="Venn diagram of buckets A, B, and D">
{_circle(230, 155, 112, VERM)}
{_circle(390, 155, 112, PURPLE)}
{_circle(310, 255, 112, SKY)}
{_vlabel(165, 130, c["abd_A"], "A only")}
{_vlabel(455, 130, c["abd_B"], "B only")}
{_vlabel(310, 355, c["abd_D"], "D only")}
{_vlabel(310, 118, c["abd_AB"], "A and B")}
{_vlabel(230, 230, c["abd_AD"], "A and D")}
{_vlabel(390, 230, c["abd_BD"], "B and D")}
{_vlabel(310, 200, c["abd_ABD"], "A, B, and D")}
</svg>"""


def venn_aci(c: dict[str, int]) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 280" role="img" aria-label="Venn diagram of bucket A and bucket A-ci">
{_circle(230, 140, 105, VERM)}
{_circle(390, 140, 105, ORANGE)}
{_vlabel(175, 135, c["A_not_Aci"], "A only")}
{_vlabel(445, 135, c["Aci_not_A"], "A-ci only")}
{_vlabel(310, 135, c["A_and_Aci"], "both")}
<text x="320" y="262" text-anchor="middle" font-family="Helvetica, Arial, sans-serif" font-size="13" fill="{BLACK}">A-ci stays in the bot-sufficient count. A does not.</text>
</svg>"""


def flowchart_svg(counts: dict) -> str:
    steps = [
        ("Opened PRs", counts.get("cohort", "")),
        ("Bot LGTM", counts.get("lgtm", "")),
        ("CI at that SHA", counts.get("ci", "")),
        ("Human review", counts.get("human", "")),
        ("Merged", counts.get("merged", "")),
        ("30-day follow-up", counts.get("follow", "")),
        ("A / A-ci / B / D / C", ""),
    ]
    w, h = 920, 120
    box_w, box_h = 110, 54
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">']
    for i, (label, n) in enumerate(steps):
        x = 12 + i * 130
        parts.append(f'<rect x="{x}" y="28" width="{box_w}" height="{box_h}" rx="6" fill="#E8F1FA" stroke="{APP}"/>')
        parts.append(f'<text x="{x + box_w/2}" y="50" text-anchor="middle" font-size="11" font-family="sans-serif">{html.escape(label)}</text>')
        parts.append(f'<text x="{x + box_w/2}" y="68" text-anchor="middle" font-size="11" font-family="sans-serif" fill="#333">{html.escape(str(n))}</text>')
        if i < len(steps) - 1:
            parts.append(f'<path d="M{x+box_w} 55 H{x+128}" stroke="{APP}" marker-end="url(#a)"/>')
    parts.insert(1, f'<defs><marker id="a" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6" fill="{APP}"/></marker></defs>')
    parts.append("</svg>")
    return "".join(parts)


def examples(findings: pd.DataFrame, prs: pd.DataFrame, n: int = 10) -> str:
    real = findings[findings["category"].notna()].copy()
    if real.empty:
        return "<p>No classified findings.</p>"
    take = real.sample(n=min(n, len(real)), random_state=20260401)
    bits = []
    for _, row in take.iterrows():
        bits.append(
            "<li><p><a href=\"{url}\">PR {pr}</a> · {cat} / {sev} · real={real}</p><p>{body}</p><p><em>{why}</em></p></li>".format(
                url=html.escape(str(row.get("pr_url") or "")),
                pr=row["pr"],
                cat=html.escape(str(row.get("category"))),
                sev=html.escape(str(row.get("severity"))),
                real=row.get("is_real"),
                body=html.escape(str(row.get("body") or "")[:500]),
                why=html.escape(str(row.get("rationale") or "")),
            )
        )
    return "<ol>" + "".join(bits) + "</ol>"


def bucket_examples(prs: pd.DataFrame, findings: pd.DataFrame, escapes: pd.DataFrame) -> str:
    parts = []
    for flag, title in (("in_A", "Bucket A"), ("in_B", "Bucket B"), ("in_D", "Bucket D")):
        rows = prs[prs[flag] == True].head(5) if flag in prs.columns else prs.iloc[0:0]
        parts.append(f"<h3>{title}</h3>")
        if rows.empty:
            parts.append("<p>None in this pilot run.</p>")
            continue
        parts.append("<ul>")
        for _, row in rows.iterrows():
            parts.append(
                f"<li><a href=\"{html.escape(str(row['url']))}\">#{int(row['number'])} {html.escape(str(row['title'])[:140])}</a></li>"
            )
        parts.append("</ul>")
    return "".join(parts)


def write_label_sample(findings: pd.DataFrame) -> None:
    pool = findings[findings["in_cohort"] == True].copy()
    if pool.empty:
        pool = findings.copy()
    sample = pool.sample(n=min(100, len(pool)), random_state=20260401)
    out = pd.DataFrame(
        {
            "finding_id": sample["finding_id"],
            "pr_url": sample["pr_url"],
            "path": sample["path"],
            "comment": sample["body"],
            "diff_hunk": sample["diff_hunk"] if "diff_hunk" in sample.columns else "",
            "your_category": "",
            "your_severity": "",
        }
    )
    # diff hunk may not be in findings.csv. That's ok if absent.
    out.to_csv(OUT / "labeling_sample.csv", index=False)


def main() -> None:
    CHARTS.mkdir(parents=True, exist_ok=True)
    monthly = pd.read_csv(OUT / "monthly.csv")
    prs = pd.read_csv(OUT / "prs.csv")
    findings = pd.read_csv(OUT / "findings.csv")
    for frame, cols in (
        (prs, ["in_cohort", "bot_lgtm", "merged", "in_A", "in_Aci", "in_B", "in_D", "mergeable_at_lgtm", "ci_known", "sha_unknown", "fetch_error"]),
        (findings, ["in_cohort", "is_real", "code_change"]),
    ):
        for col in cols:
            if col in frame.columns:
                frame[col] = frame[col].map(lambda v: bool(v) if isinstance(v, (bool, np.bool_)) else str(v).lower() == "true")
    comp = pd.read_csv(OUT / "approval_comparison.csv")
    dev = pd.read_csv(OUT / "per_developer.csv")
    summary = json.loads((OUT / "summary.json").read_text())
    escapes = pd.DataFrame()
    escapes_path = OUT / "escapes.csv"
    if escapes_path.exists() and escapes_path.stat().st_size > 0:
        try:
            escapes = pd.read_csv(escapes_path)
        except pd.errors.EmptyDataError:
            escapes = pd.DataFrame()
    history_path = S.meta / "bot_history.json"
    if not history_path.exists():
        history_path = ROOT / "data" / "raw" / "app" / "meta" / "bot_history.json"
    history = json.loads(history_path.read_text()) if history_path.exists() else {}
    rules_path = S.meta / "rulesets.json"
    rules = json.loads(rules_path.read_text()) if rules_path.exists() else []
    main_rules = next((r for r in rules if r.get("name") == "main branch protections"), None)
    if main_rules is None:
        active = [
            r
            for r in rules
            if r.get("enforcement") == "active" and r.get("target") == "branch"
        ]
        main_rules = active[0] if active else {}

    svgs = {
        "suff": chart_sufficiency(monthly),
        "buckets": chart_buckets(monthly),
        "cats": chart_categories(findings),
        "time": chart_time(monthly),
        "cov": chart_coverage(monthly),
        "size": chart_size_time(prs),
        "ecdf": chart_ecdf(prs),
        "stack": chart_buckets_stacked(prs),
        "funnel": chart_funnel(prs, findings),
        "appr": chart_approval(comp),
    }
    dev_svgs = {
        "heat": dev_heatmap(dev),
        "scatter": dev_scatter(dev),
        "load": dev_load(dev),
    }
    write_label_sample(findings)

    reg = summary.get("regressions", {})
    def reg_line(block: dict) -> str:
        if not block or not block.get("ok"):
            return f"not fit ({(block or {}).get('error', 'no result')})"
        lo, hi = block["month_ci"]
        return (
            f"month coefficient {block['month_coef']:.3f} "
            f"(95% CI {lo:.3f} to {hi:.3f}, n={block['n']}, p={block['month_pvalue']:.3f})"
        )

    cohort_n = int((prs["in_cohort"] == True).sum())
    lgtm_n = int(((prs["in_cohort"] == True) & (prs["bot_lgtm"] == True)).sum())
    merged_lgtm = prs[(prs["in_cohort"] == True) & (prs["author_type"] == "human") & (prs["merged"] == True) & (prs["bot_lgtm"] == True)]
    flow = flowchart_svg(
        {
            "cohort": cohort_n,
            "lgtm": lgtm_n,
            "ci": int(merged_lgtm["ci_known"].sum()) if "ci_known" in merged_lgtm.columns else "see CI section",
            "human": int(merged_lgtm["human_approval_count"].gt(0).sum()) if len(merged_lgtm) else 0,
            "merged": int(len(merged_lgtm)),
            "follow": "30 days, September partial",
        }
    )
    no_appr = int(((merged_lgtm["human_approval_count"] == 0) & (merged_lgtm["review_dismissals"].fillna(0) == 0)).sum()) if len(merged_lgtm) else 0
    rebased_after = 0
    if "code_change_confidence" in findings.columns and "timing" in findings.columns:
        after_mask = findings["timing"].eq("after")
        if "in_cohort" in findings.columns:
            after_mask = after_mask & findings["in_cohort"].eq(True)
        rebased_after = int((after_mask & findings["code_change_confidence"].eq("rebased_unknown")).sum())
    if "mergeable_at_lgtm" in merged_lgtm.columns and "ci_known" in merged_lgtm.columns:
        known = merged_lgtm[merged_lgtm["ci_known"] == True]
        not_mergeable = int((known["mergeable_at_lgtm"] == False).sum())
        known_n = int(len(known))
    else:
        not_mergeable = int(summary.get("not_mergeable") or 0)
        known_n = int(summary.get("ci_known_headline") or 0)

    def headline_flag(column: str, summary_key: str) -> int:
        if column in merged_lgtm.columns:
            return int(merged_lgtm[column].sum())
        return int(summary.get(summary_key) or 0)

    if "ci_known" in merged_lgtm.columns:
        missing_ci = merged_lgtm[merged_lgtm["ci_known"] != True]
        sha_unknown_n = int(missing_ci["sha_unknown"].fillna(False).sum()) if "sha_unknown" in missing_ci.columns else 0
        fetch_error_n = int(missing_ci["fetch_error"].fillna(False).sum()) if "fetch_error" in missing_ci.columns else 0
        no_file_n = int(len(missing_ci) - sha_unknown_n - fetch_error_n)
    else:
        sha_unknown_n = headline_flag("sha_unknown", "lgtm_sha_unknown")
        fetch_error_n = headline_flag("fetch_error", "ci_fetch_error")
        no_file_n = int(len(merged_lgtm) - known_n - sha_unknown_n - fetch_error_n)
    members_path = S.meta / "members.json"
    member_n = len(json.loads(members_path.read_text())) if members_path.exists() else None
    member_phrase = f"{member_n} members" if member_n is not None else "the org member snapshot"
    examples_path = S.interim / "lgtm_examples.json"
    lgtm_examples = []
    if examples_path.exists():
        lgtm_examples = [row for row in json.loads(examples_path.read_text()) if (row.get("body") or "").strip() == "LGTM"][:3]
    if lgtm_examples:
        example_html = "".join(
            f'<li><a href="{html.escape(row["url"])}">{html.escape(S.name)}#{row["number"]}</a> {html.escape(row.get("kind") or "review")} body <code>LGTM</code></li>'
            for row in lgtm_examples
        )
    else:
        rel_examples = html.escape(str((S.interim / "lgtm_examples.json").relative_to(ROOT)))
        example_html = f"<li>Exact LGTM examples are written to <code>{rel_examples}</code> by <code>parse_prs.py</code>.</li>"
    bypass = main_rules.get("bypass_actors") or []
    if bypass:
        bypass_txt = ", ".join(
            f'{html.escape(str(row.get("actor_type")))} {html.escape(str(row.get("actor_id")))} ({html.escape(str(row.get("bypass_mode")))})'
            for row in bypass
        )
    else:
        bypass_txt = "none recorded"

    def section_charts(*keys):
        return "".join(f'<div class="chart">{svgs[k]}</div>' for k in keys)

    regions = overlap_counts(merged_lgtm)
    venn_ab_svg = venn_ab(regions)
    venn_abd_svg = venn_abd(regions)
    venn_aci_svg = venn_aci(regions)
    suff_n = regions["sufficient"]
    suff_pct = (100.0 * suff_n / regions["n"]) if regions["n"] else 0.0
    unc = reg.get("uncontrolled") or {}
    ctrl = reg.get("controlled") or {}

    def slope_sentence(block: dict, label: str) -> str:
        if not block or not block.get("ok"):
            return f"The {label} model was not fit."
        lo, hi = block["month_ci"]
        side = "includes zero" if lo <= 0 <= hi else "excludes zero"
        return (
            f"the {label} coefficient is {block['month_coef']:.2f} "
            f"(95% CI {lo:.2f} to {hi:.2f}, {side})"
        )

    if unc.get("ok") and ctrl.get("ok"):
        slope_html = (
            f"With no controls, {slope_sentence(unc, 'month')}. "
            f"With size and tenure, {slope_sentence(ctrl, 'month')}. "
            "The fit also warned that it did not fully converge. "
            "A slope from a fit that did not settle is not a month trend."
        )
    else:
        fit_error = str(unc.get("error") or "no result")
        if "same outcome" in fit_error:
            slope_html = (
                f"The month model was not fit ({html.escape(fit_error)}). "
                "A slope needs both sufficient and not-sufficient pull requests."
            )
        else:
            slope_html = (
                f"The month model was not fit ({html.escape(fit_error)}). "
                "The fit needs at least 30 headline pull requests and both outcomes. "
                "This repository cannot support that slope."
            )
    rel_out = "out" if S.name == "app" else f"out/{S.name}"
    if "month" in merged_lgtm.columns and len(merged_lgtm):
        apr_n = int((merged_lgtm["month"] == "2026-04").sum())
        may_n = int((merged_lgtm["month"] == "2026-05").sum())
    else:
        apr_n = 0
        may_n = 0
    recall = summary.get("recall") or {}
    if recall.get("available") and recall.get("tickets_with_app_fix_pr"):
        recall_hit = int(recall.get("fix_prs_selected_by_heuristic") or 0)
        recall_base = int(recall.get("tickets_with_app_fix_pr") or 0)
        recall_sentence = f"The Linear sample matched {recall_hit} of {recall_base} bug-ticket fix pull requests."
        recall_step = f"The current Linear sample found the fix pull request for {recall_hit} of {recall_base} tickets."
    else:
        recall_sentence = "No Linear bug sample is loaded for this repository, so escape recall is not estimated."
        recall_step = "No Linear sample is loaded for this repository."
    if S.name == "app":
        scope_html = "Pilot for <code>foxglove/app</code> only. Pull requests opened 1 Apr 2026 through 30 Sep 2026. The other six repositories are not in this draft."
        draft_note = "app stops reviewing drafts unless opted in"
        ci_caveat = "The Checks API returns 403 for this token. Job conclusions are fetched for every selected workflow run. A skipped required job counts as a pass, because GitHub reports it as Success and does not block merge. A 30-SHA comparison of a workflow-level proxy agreed on 23 SHAs and is not used. <code>Storybook / app screenshots</code> is read from commit statuses."
        person_caveat = "Monthly per-person cells are often n&lt;10. Rates sit next to the person's repo (app only, in this pilot) and size mix."
        next_keep = "<li>Keep this pilot on <code>app</code> until the label check and the escape recall check are in. The other six repositories wait on that review.</li>"
        bot_first = "First appearance in app: 15 Feb 2026, before the window (<code>#12483</code>)."
        protection_html = (
            "Classic branch protection is unset. Active ruleset "
            f"\"{html.escape(str(main_rules.get('name') or ''))}\" targets the default branch, "
            "requires 1 approving review, does not dismiss stale reviews on push, requires linear history, "
            f"and requires the status checks listed in the method. Bypass actors: {bypass_txt}. "
            "A disabled ruleset named \"no merges - active incident\" also exists."
        )
        dev_intro = "The pilot is one repo, so the repo mix column is app."
        page_title = "App pilot: bot LGTM and human review"
        dev_title = "Per-developer stats, app pilot"
    else:
        scope_html = (
            f"Repository <code>foxglove/{html.escape(S.name)}</code>. "
            "Pull requests opened 1 Apr 2026 through 30 Sep 2026. "
            "The definitions match the app pilot."
        )
        draft_note = "the shared review workflow stops reviewing drafts unless opted in"
        req_path = S.meta / "required_checks.json"
        req_contexts: list[str] = []
        if req_path.exists():
            req_contexts = list(json.loads(req_path.read_text()).get("contexts") or [])
        if req_contexts:
            req_phrase = ", ".join(html.escape(c) for c in req_contexts)
            ci_caveat = (
                "The Checks API returns 403 for this token. Job conclusions come from Actions workflow runs. "
                "A skipped required job counts as a pass, because GitHub reports it as Success and does not block merge. "
                "A required name that is not a job name is read from commit statuses. "
                f"Required checks: {req_phrase}."
            )
        else:
            ci_caveat = (
                "This repository has no required status checks on main. "
                "The mergeable flag is true whenever the LGTM commit is known. "
                "The Checks API returns 403 for this token."
            )
        person_caveat = f"Monthly per-person cells are often n&lt;10. This page is <code>{html.escape(S.name)}</code> only."
        next_keep = (
            f"<li>This page is <code>{html.escape(S.name)}</code> alone. "
            "A model that pools the repositories is a later step. It is not in this report.</li>"
        )
        bot_first = "The reviewer is the shared <code>foxglove/actions</code> workflow. This page does not date its first comment in this repository."
        review_n = None
        for rule in main_rules.get("rules") or []:
            if rule.get("type") == "pull_request":
                review_n = (rule.get("parameters") or {}).get("required_approving_review_count")
        if review_n is None and not main_rules:
            protection_html = "No active branch ruleset was saved for this repository."
        else:
            review_phrase = (
                f"requires {int(review_n)} approving review"
                if review_n is not None
                else "does not record a required approving review count in the saved ruleset"
            )
            protection_html = (
                f"Active ruleset \"{html.escape(str(main_rules.get('name') or ''))}\" "
                f"targets the default branch and {review_phrase}. "
                f"Bypass actors: {bypass_txt}. Required check names are in the caveats."
            )
        dev_intro = f"This page is one repository, {html.escape(S.name)}."
        page_title = f"{S.name}: bot LGTM and human review"
        dev_title = f"Per-developer stats, {S.name}"

    body = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>{html.escape(page_title)}</title>
<style>
body {{ font-family: Helvetica, Arial, sans-serif; max-width: 980px; margin: 32px auto; color: #222; line-height: 1.5; }}
h1,h2,h3 {{ line-height: 1.25; }}
.chart svg {{ max-width: 100%; height: auto; }}
.assessment {{ background: #f4f8fb; border: 1px solid #d5e3ee; border-radius: 8px; padding: 16px 20px; margin: 16px 0 28px; }}
.venn {{ margin: 8px 0 20px; }}
table {{ border-collapse: collapse; font-size: 13px; }}
td, th {{ border-bottom: 1px solid #ddd; padding: 4px 8px; text-align: left; }}
code {{ font-family: ui-monospace, monospace; font-size: 0.92em; }}
</style></head><body>
<h1>Is the first bot LGTM becoming sufficient?</h1>
<p>{scope_html}</p>
<section class="assessment">
<h2>Assessment</h2>
<p><strong>This study does not answer whether the first LGTM is becoming sufficient month over month.</strong></p>
<p>The level, on the definition below, is {suff_n} of {regions["n"]} merged human pull requests ({suff_pct:.0f}%). Each of those pull requests has a bot LGTM and shows neither bucket A nor bucket B. {slope_html}</p>
<p>Four facts keep the month question open:</p>
<ul>
<li>April has {apr_n} headline pull requests and May has {may_n}. The exact comment <code>LGTM</code> starts on 18 Jun 2026, so the early months are a different signal.</li>
<li>The bot's model and prompt changed on 18 Jun, from 26 Jul to 28 Jul, and on 22 Sep. One slope across those changes mixes a definition change with a catch-rate change.</li>
<li>September's 30-day follow-up was still open on 3 Oct 2026. Later fixes for September are still missing.</li>
<li>Bucket B only counts a fix when the title looks like a fix and git blame can name the source pull request. Missed fixes would lower the sufficient share. {html.escape(recall_sentence)} Sentry is not connected.</li>
</ul>
<p>{not_mergeable} of {known_n} headline pull requests were not mergeable at the first LGTM commit. {no_appr} merged with no human approval. Those two facts are about process. They do not identify a month trend.</p>
</section>
<h2>Where the categories overlap</h2>
<p>A pull request can sit in more than one bucket. Read the number in each region. The circles are the sets. The caption under a number is that region only.</p>
<h3>A and B decide bot-sufficient</h3>
<p>Bucket A is a real medium or high bug, security, or data-loss comment after the LGTM. The author acknowledged it, or a later commit changed that file, and CI at the counterfactual commit would not have caught it. Bucket B is a later fix whose blamed line was already in that commit, merged within 30 days. A pull request in A or B is not bot-sufficient.</p>
<div class="venn chart">{venn_ab_svg}</div>
<h3>A, B, and D: when the line existed</h3>
<p>Bucket D is a later fix whose blamed line was absent at the counterfactual commit and present on the final head, merged within 30 days. D alone leaves the pull request bot-sufficient. The center of this diagram is the small set that is A, B, and D together.</p>
<div class="venn chart">{venn_abd_svg}</div>
<h3>A and A-ci</h3>
<p>A-ci is the same kind of comment as A, and the comment names CI, a test, or lint, while a required check was already failing. A-ci stays bot-sufficient. The study cannot read check logs, so A-ci is a low count.</p>
<div class="venn chart">{venn_aci_svg}</div>
<p>Bucket C is the {regions["C"]} headline pull requests in none of A, A-ci, B, or D. Bot-sufficient is larger than C: it also includes D-only and A-ci-only, because those two do not contain A or B. In this run that adds {regions["sufficient"] - regions["C"]} pull requests, for {regions["sufficient"]} bot-sufficient in total.</p>
<p>The rest of this page is the evidence behind the assessment.</p>
<h2>1. Counts behind the assessment</h2>
<ul>
<li>Headline pull requests: {len(merged_lgtm)}. Human author, merged, and at least one bot LGTM.</li>
<li>Month model with no controls: {html.escape(reg_line(reg.get('uncontrolled') or {}))}.</li>
<li>Same model with size and tenure: {html.escape(reg_line(reg.get('controlled') or {}))}.</li>
<li>Merged with no human approval: {no_appr}.</li>
<li>Not mergeable at the first bot LGTM commit: {not_mergeable} of {known_n}. Missing CI data: {sha_unknown_n} with an unknown LGTM commit after a rebase, {fetch_error_n} whose CI fetch failed before any check result, and {no_file_n} with no CI fetch result.</li>
<li>Findings after the LGTM whose later edit could not be checked, because the pull request was rebased: {rebased_after}. Those findings stay out of bucket A unless the author acknowledged them.</li>
</ul>
{section_charts('suff','time','funnel')}
<h2>2. Method</h2>
<p>The study measures defect-catching: bugs, security issues, and data loss or corruption, with other comment categories kept as context. It does not measure knowledge sharing, shared ownership, mentoring, or design alignment. A bot-sufficient PR is one where those defect catches were not observed. It is not a claim that human review added nothing.</p>
{flow}
<p>First bot LGTM is the earliest <code>claude</code> / <code>claude[bot]</code> review or comment whose body contains the token <code>LGTM</code>. From 18 Jun 2026 the prompt requires that body to be exactly <code>LGTM</code>, submitted as a comment, not as an approval. Before that, a clean review often submitted nothing. April and May coverage is therefore a property of the signal, not only of the bot's judgment. Comment LGTMs use the last commit at or before the comment.</p>
<p>Counterfactual merge SHA: the commit the first LGTM reviewed, if required checks passed there; otherwise the first later commit where those checks passed and the latest bot review on that commit was still an LGTM. Stale reviews are not dismissed on push.</p>
<p>Bucket A is a real medium or high bug, security, or data-loss finding after the LGTM that led to a code change or an explicit author acknowledgment, and that CI at the counterfactual SHA would not have caught. A-ci is that same finding when the comment ties it to a failing required check. A-ci counts as bot-sufficient. Bucket B is a later fix whose blamed lines were already in the counterfactual SHA. Bucket D is a later fix whose lines were added after that SHA. B is a lower bound. Bucket C is none of A, A-ci, B, or D.</p>
<p>Primary model, chosen before looking at results: <code>bot_sufficient ~ month</code> (April = 0 … September = 5), then the same model plus size bucket and author-tenure bucket. Repo is constant in this pilot, so it is omitted. Engagement (non-nit human comments after the LGTM) is a sensitivity check only.</p>
<h2>3. The month charts, read with the assessment</h2>
<p>These charts describe the same pull requests. They do not turn the month coefficient into a trend. Gray points have fewer than 10 pull requests. The shaded month is September, whose follow-up window was still open.</p>
{section_charts('suff','buckets','cats','cov')}
<p>Uncontrolled: {html.escape(reg_line(reg.get('uncontrolled') or {}))}. With size and tenure: {html.escape(reg_line(reg.get('controlled') or {}))}. With engagement added: {html.escape(reg_line(reg.get('engagement') or {}))}.</p>
<p>Bot config changes worth lining up with the chart: 18 Jun 2026 (the word LGTM, and {html.escape(draft_note)}), 26 Jul to 28 Jul (Opus 5, then a return to Opus 4.8), 22 Sep (Opus 5.5 and inline-only findings). If the rate moves at those dates, the pool of LGTM'd pull requests changed definition, along with the bot's catch rate.</p>
<h2>4. Time, catch value, counterfactual</h2>
{section_charts('time','size','ecdf','funnel','stack','appr')}
<p>Times are calendar hours between recorded timestamps. They include nights, weekends, and time waiting on the author or CI. They are total delay, not reviewer effort. A negative LGTM-to-approval time means the human approved before the bot's first LGTM; those PRs stay in the distribution.</p>
<p>Merged with no human approval: {no_appr} of {len(merged_lgtm)} headline PRs. Branch protection on <code>main</code> requires one approving review, so these merges bypassed that rule. The bypass list on the current ruleset is the <code>foxglovebot</code> team. Who actually merged is in the PR table. This group was chosen by people. If it is small, the escape-rate contrast is not a usable comparison and the counterfactual rests on buckets A, A-ci, B, and D.</p>
<h2>5. Caveats</h2>
<ul>
<li>Defect-catching only. Bot-sufficient does not mean human review has no other value.</li>
<li>Reviewers see the LGTM and may comment less as trust grows. The engagement sensitivity check is there for that reason. The check is partly downstream of the same behavior that creates bucket A.</li>
<li>Bucket A depends on the classifier. Bucket B depends on a fix-title and blame heuristic. Recall of that heuristic is estimated from Linear bug tickets when the escape step has run; Sentry is not connected, so recall is incomplete and B is a lower bound.</li>
<li>{ci_caveat}</li>
<li>The ruleset audit log is 403. The required-check list and the one-approval rule are the ruleset as of its <code>updated_at</code> ({html.escape(str(main_rules.get('updated_at')))}), applied across the whole window.</li>
<li>Current org membership is a snapshot of {member_phrase}. The audit log cannot separate people who left from external collaborators. The member list is not committed.</li>
<li>Squash merges collapse the PR into one commit. B versus D uses the file text at the LGTM SHA and at the final head. Non-unique lines are low confidence and are not counted in the headline B or D rates.</li>
<li>A-ci requires the review comment to mention CI, tests, or lint, because check logs are not readable. That under-counts A-ci.</li>
<li>September's follow-up window runs only through 3 Oct 2026.</li>
<li>The classifier is Grok, reading findings about a Claude review bot. Agreement with a hand-labeled sample is not computed until <code>labeling_sample.csv</code> is filled in.</li>
<li>{person_caveat}</li>
</ul>
<h2>6. Next steps</h2>
<ol>
<li>Hand-label <code>{html.escape(rel_out)}/labeling_sample.csv</code> (100 findings). Compare those labels with the classifier before treating bucket A as settled. Cohen's kappa uses the empty columns <code>your_category</code> and <code>your_severity</code>.</li>
<li>Leave the month question open until two conditions hold. The LGTM definition stays stable for several months, and September's 30-day window has closed. Recompute September after 31 Oct 2026. Fit separate periods at 18 Jun, from 26 Jul to 28 Jul, and at 22 Sep, instead of one slope from April to September.</li>
<li>Raise the recall of bucket B before reading the sufficient share as a ceiling. Connect Sentry, or search for fixes beyond the title words, and rerun <code>scripts/escapes.py</code>. {html.escape(recall_step)}</li>
{next_keep}
<li>Treat A-ci as incomplete until check logs are readable. The comment has to name CI, a test, or lint today.</li>
</ol>
<h2>7. Appendix</h2>
<h3>Bot</h3>
<p>Login: <code>claude[bot]</code> on REST, <code>claude</code> on GraphQL. The bot submits <code>COMMENT</code> reviews, never <code>APPROVE</code>. {bot_first}</p>
<h3>Three LGTM examples</h3>
<ul>
{example_html}
</ul>
<h3>Branch protection</h3>
<p>{protection_html}</p>
<h3>Config changes in foxglove/actions during the window</h3>
<ul>
{''.join(f'<li>{html.escape(r["date"])} {html.escape(r["summary"])}</li>' for r in history.get('actions', []))}
</ul>
<h3>Classified findings</h3>
{examples(findings, prs)}
<h3>Bucket examples</h3>
{bucket_examples(prs, findings, escapes)}
<p>Hand-label file: <code>{html.escape(rel_out)}/labeling_sample.csv</code>. Classifier labels are not in that file. Cohen's kappa waits on the filled columns <code>your_category</code> and <code>your_severity</code>.</p>
</body></html>
"""
    (OUT / "report.html").write_text(body)

    # per-developer page keeps names; it is the only place they appear in a rendered report
    dev_html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>{html.escape(dev_title)}</title>
<style>
body {{ font-family: Helvetica, Arial, sans-serif; max-width: 1100px; margin: 24px auto; color: #222; }}
table {{ border-collapse: collapse; font-size: 12px; }}
td, th {{ border-bottom: 1px solid #ddd; padding: 3px 6px; text-align: left; }}
.chart svg {{ max-width: 100%; height: auto; }}
</style></head><body>
<h1>Per-developer stats for foxglove/{html.escape(S.name)}</h1>
<p>Rates are shown for every person, including months with n&lt;10, and those cells are marked low-sample in the table. This is not a ranking. People who work on lower-risk code will show lower catch and escape rates. {dev_intro}</p>
<div class="chart">{dev_svgs['heat']}</div>
<div class="chart">{dev_svgs['scatter']}</div>
<div class="chart">{dev_svgs['load']}</div>
<h2>Author and reviewer table</h2>
<p>One row per person per month, plus a six-month total (<code>month=all</code>). Sortable by opening the CSV <code>{html.escape(rel_out)}/per_developer.csv</code>.</p>
{dev_table(dev)}
</body></html>
"""
    (OUT / "per-developer.html").write_text(dev_html)
    (OUT / "report.md").write_text(
        markdown_summary(summary, len(merged_lgtm), no_appr, not_mergeable, known_n, sha_unknown_n, fetch_error_n, no_file_n, reg_line, rel_out)
    )
    print("wrote report", flush=True)


def dev_table(dev: pd.DataFrame) -> str:
    show = dev.copy()
    cols = [
        "person",
        "month",
        "current_org_member",
        "authored_prs",
        "low_sample_author",
        "bot_sufficient_rate",
        "bot_sufficient_n",
        "A",
        "B",
        "D",
        "reviews",
        "low_sample_reviewer",
        "findings_raised_per_review",
        "hm_catch_per_review",
    ]
    cols = [c for c in cols if c in show.columns]
    show = show[cols].sort_values(["person", "month"])
    return show.to_html(index=False, float_format=lambda v: f"{v:.2f}")


def markdown_summary(summary, n, no_appr, not_mergeable, known_n, sha_unknown_n, fetch_error_n, no_file_n, reg_line, rel_out) -> str:
    reg = summary.get("regressions", {})
    unc = reg.get("uncontrolled") or {}
    if unc.get("ok"):
        lead = "The study does not answer that question. The level on this definition is the bot-sufficient count below. The month slope includes zero, and the fit did not fully converge."
    else:
        lead = "The study does not answer that question. The level on this definition is the bot-sufficient count below. The month model was not fit, so there is no slope to read."
    return f"""# Is the first bot LGTM becoming sufficient?

{lead}

Bot-sufficient means no bucket A and no bucket B on a merged human pull request that the bot LGTM'd. It means those two defect signals were not observed.

- Headline PRs: {n}
- Uncontrolled month coefficient: {reg_line(reg.get('uncontrolled') or {})}
- With size and tenure controls: {reg_line(reg.get('controlled') or {})}
- Merged with no human approval: {no_appr}
- Not mergeable at the first bot LGTM commit: {not_mergeable} of {known_n} headline PRs with CI data. No CI data: {sha_unknown_n} PRs with an unknown LGTM commit after a rebase, {fetch_error_n} PRs whose CI fetch failed before any check result, and {no_file_n} PRs with no CI fetch result.

The full reading, the Venn diagrams, and the next steps are in `{rel_out}/report.html`. Per-developer stats are in `{rel_out}/per-developer.html`.

September has a partial follow-up window. The LGTM string itself dates from 18 Jun 2026.
"""


if __name__ == "__main__":
    main()
