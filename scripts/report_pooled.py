"""Six-month report across every study repository.

The per-repository pages fit month alone. The plan's primary model is
bot_sufficient ~ month + C(repo) + C(size) + C(tenure). This script reads the
already written prs.csv and findings.csv files. It does not call GitHub.
"""

from __future__ import annotations

import html
import json
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from common import MONTHS, wilson_interval

ROOT = Path(__file__).resolve().parents[1]
from report_app import (
    BLACK,
    GRAY,
    MONTH_LABELS,
    ORANGE,
    PURPLE,
    SKY,
    VERM,
    overlap_counts,
    style_ax,
    venn_ab,
    venn_abd,
    venn_aci,
)

OUT = ROOT / "out" / "pooled"
CHARTS = OUT / "charts"
REPOS = ["app", "data-platform", "infra", "infra-admin", "foxglove-sdk", "mcap", "actions"]
# Okabe-Ito, one color per repository, fixed.
REPO_COLOR = {
    "app": "#0072B2",
    "data-platform": "#E69F00",
    "infra": "#009E73",
    "infra-admin": "#D55E00",
    "foxglove-sdk": "#56B4E9",
    "mcap": "#CC79A7",
    "actions": "#000000",
}


def prs_path(repo: str) -> Path:
    return ROOT / "out" / "prs.csv" if repo == "app" else ROOT / "out" / repo / "prs.csv"


def findings_path(repo: str) -> Path:
    return ROOT / "out" / "findings.csv" if repo == "app" else ROOT / "out" / repo / "findings.csv"


def load_prs() -> pd.DataFrame:
    frames = []
    for repo in REPOS:
        frame = pd.read_csv(prs_path(repo))
        frame["repo"] = repo
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def load_findings() -> pd.DataFrame:
    frames = []
    for repo in REPOS:
        path = findings_path(repo)
        if not path.exists():
            continue
        frame = pd.read_csv(path)
        frame["repo"] = repo
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def headline(prs: pd.DataFrame) -> pd.DataFrame:
    return prs[
        (prs["in_cohort"] == True)
        & (prs["author_type"] == "human")
        & (prs["merged"] == True)
        & (prs["bot_lgtm"] == True)
        & (prs["month"].isin(MONTHS))
    ].copy()


def fit_logit(df: pd.DataFrame, formula: str) -> dict:
    import statsmodels.formula.api as smf

    if len(df) < 30:
        return {"ok": False, "error": f"n={len(df)}", "formula": formula}
    if df["bot_sufficient"].nunique() < 2:
        return {
            "ok": False,
            "error": f"n={len(df)}; every headline pull request has the same outcome",
            "formula": formula,
        }
    caught: list[warnings.WarningMessage] = []
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            model = smf.logit(formula, data=df).fit(disp=False, maxiter=200)
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:400], "formula": formula}
    if "month_index" not in model.params:
        return {"ok": False, "error": "month_index dropped", "formula": formula}
    lo, hi = model.conf_int().loc["month_index"].tolist()
    names = sorted({w.category.__name__ for w in caught})
    return {
        "ok": True,
        "formula": formula,
        "n": int(model.nobs),
        "month_coef": float(model.params["month_index"]),
        "month_ci": [float(lo), float(hi)],
        "month_pvalue": float(model.pvalues["month_index"]),
        "pseudo_r2": float(model.prsquared),
        "converged": bool(getattr(model, "mle_retvals", {}).get("converged", True)),
        "warnings": names,
    }


def reg_frame(frame: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(
        {
            "bot_sufficient": frame["bot_sufficient"].astype(int),
            "month_index": frame["month"].map({m: i for i, m in enumerate(MONTHS)}).astype(int),
            "repo": frame["repo"].astype(str),
            "size_bucket": frame["size_bucket"].fillna("S").astype(str),
            "tenure_bucket": frame["tenure_bucket"].fillna("unknown").astype(str),
            "substantive_comments_after": frame["substantive_comments_after"].fillna(0).astype(float),
        }
    )
    return out


def month_rows(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for month in MONTHS:
        group = frame[frame["month"] == month]
        n = int(len(group))
        k = int(group["bot_sufficient"].sum()) if n else 0
        lo, hi = wilson_interval(k, n)
        rows.append(
            {
                "month": month,
                "n": n,
                "k": k,
                "rate": (k / n) if n else None,
                "lo": lo,
                "hi": hi,
                "A": int(group["in_A"].sum()) if n else 0,
                "B": int(group["in_B"].sum()) if n else 0,
                "D": int(group["in_D"].sum()) if n else 0,
                "Aci": int(group["in_Aci"].sum()) if n else 0,
            }
        )
    return pd.DataFrame(rows)


def save_fig(fig, name: str) -> str:
    CHARTS.mkdir(parents=True, exist_ok=True)
    path = CHARTS / f"{name}.svg"
    fig.savefig(path, format="svg", bbox_inches="tight")
    fig.savefig(CHARTS / f"{name}.png", format="png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path.read_text()


def chart_pooled(monthly: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=(9.2, 4.6))
    x = np.arange(len(monthly))
    y = monthly["rate"].astype(float)
    n = monthly["n"].astype(int)
    ax.fill_between(x, monthly["lo"].astype(float), monthly["hi"].astype(float), color="#0072B2", alpha=0.15)
    ax.plot(x, y, color="#0072B2", marker="o")
    for xi, yi, ni in zip(x, y, n):
        ax.scatter([xi], [yi], color="#0072B2" if ni >= 10 else GRAY, zorder=3)
        above = yi < 0.92
        ax.annotate(
            f"n={ni}",
            (xi, yi),
            textcoords="offset points",
            xytext=(0, 8) if above else (0, -14),
            ha="center",
            fontsize=8,
            color=GRAY if ni < 10 else BLACK,
        )
    ax.set_xticks(x, [MONTH_LABELS[m] for m in monthly["month"]])
    ax.set_ylim(0, 1.08)
    ax.axvspan(5 - 0.5, 5 + 0.5, color="#f4f4f4", zorder=0)
    style_ax(
        ax,
        "Bot-sufficient share across all seven repositories",
        "PR open month",
        "Share of merged human PRs with a bot LGTM",
    )
    fig.text(0.01, -0.02, "September has a partial 30-day follow-up. Gray points have n<10.", fontsize=8, color="#555")
    return save_fig(fig, "bot_sufficient_by_month")


def chart_by_repo(frame: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=(9.2, 5.0))
    x = np.arange(len(MONTHS))
    for repo in REPOS:
        rows = []
        ns = []
        for month in MONTHS:
            group = frame[(frame["repo"] == repo) & (frame["month"] == month)]
            n = int(len(group))
            ns.append(n)
            rows.append((group["bot_sufficient"].sum() / n) if n else np.nan)
        ax.plot(x, rows, marker="o", color=REPO_COLOR[repo], label=repo, linewidth=1.6)
        for xi, yi, ni in zip(x, rows, ns):
            if ni < 10 and ni > 0:
                ax.scatter([xi], [yi], color=GRAY, zorder=3, s=18)
    ax.set_xticks(x, [MONTH_LABELS[m] for m in MONTHS])
    ax.set_ylim(0, 1.12)
    ax.axvspan(5 - 0.5, 5 + 0.5, color="#f4f4f4", zorder=0)
    ax.legend(frameon=False, fontsize=8, ncol=2)
    style_ax(
        ax,
        "Bot-sufficient share in each repository",
        "PR open month",
        "Share of merged human PRs with a bot LGTM",
    )
    fig.text(0.01, -0.02, "A gray point is a month with n<10. app is most of the pooled count.", fontsize=8, color="#555")
    return save_fig(fig, "bot_sufficient_by_repo")


def chart_buckets(monthly: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=(9.2, 4.6))
    x = np.arange(len(monthly))
    n = monthly["n"].replace(0, np.nan)
    for col, label, color in (
        ("A", "A", VERM),
        ("B", "B", PURPLE),
        ("D", "D", SKY),
        ("Aci", "A-ci", ORANGE),
    ):
        ax.plot(x, monthly[col] / n, marker="o", label=label, color=color)
    ax.set_xticks(x, [MONTH_LABELS[m] for m in monthly["month"]])
    ax.set_ylim(0, 0.35)
    ax.legend(frameon=False, fontsize=8)
    ax.axvspan(5 - 0.5, 5 + 0.5, color="#f4f4f4", zorder=0)
    style_ax(ax, "Bucket rates across all seven repositories", "PR open month", "Share of headline pull requests")
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
    colors = [VERM, "#000000", ORANGE, PURPLE, SKY, "#009E73", GRAY, "#DDDDDD"]
    sub = findings[(findings["timing"] == "after") & (findings["in_cohort"] == True) & (findings["is_real"] == True)]
    fig, ax = plt.subplots(figsize=(9.2, 4.6))
    bottom = np.zeros(len(MONTHS))
    for cat, color in zip(cats, colors):
        heights = []
        for month in MONTHS:
            group = sub[sub["month"] == month]
            heights.append((group["category"] == cat).mean() if len(group) else 0)
        ax.bar(range(len(MONTHS)), heights, bottom=bottom, color=color, label=cat, width=0.8)
        bottom += np.array(heights)
    for i, month in enumerate(MONTHS):
        n = int((sub["month"] == month).sum())
        ax.annotate(f"n={n}", (i, 1.02), ha="center", fontsize=8, color=GRAY if n < 10 else BLACK)
    ax.set_xticks(range(len(MONTHS)), [MONTH_LABELS[m] for m in MONTHS])
    ax.set_ylim(0, 1.15)
    ax.legend(frameon=False, fontsize=7, ncol=2)
    style_ax(ax, "Mix of real human findings after the bot LGTM", "PR open month", "Share of real findings after LGTM")
    return save_fig(fig, "categories_after_lgtm")


def chart_time(frame: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=(9.2, 4.6))
    x = np.arange(len(MONTHS))
    for col, label, color in (
        ("lgtm_to_merge_h", "LGTM to merge", "#0072B2"),
        ("lgtm_to_approval_h", "LGTM to first human approval", ORANGE),
    ):
        p50 = []
        p90 = []
        for month in MONTHS:
            values = frame.loc[frame["month"] == month, col].dropna().astype(float)
            p50.append(float(np.nanpercentile(values, 50)) if len(values) else np.nan)
            p90.append(float(np.nanpercentile(values, 90)) if len(values) else np.nan)
        ax.plot(x, p50, marker="o", color=color, label=f"{label} p50")
        ax.fill_between(x, p50, p90, color=color, alpha=0.12)
    ax.set_yscale("symlog", linthresh=1)
    ax.set_xticks(x, [MONTH_LABELS[m] for m in MONTHS])
    ax.legend(frameon=False, fontsize=8)
    style_ax(ax, "Calendar time after the bot LGTM, p50 line and p50 to p90 band", "PR open month", "Hours")
    return save_fig(fig, "time_after_lgtm")


def pct(k: int, n: int) -> str:
    if not n:
        return "n/a"
    return f"{100.0 * k / n:.0f}%"


def slope_sentence(block: dict, label: str) -> str:
    if not block or not block.get("ok"):
        err = (block or {}).get("error") or "no result"
        return f"The {label} model was not fit ({err})."
    lo, hi = block["month_ci"]
    side = "includes zero" if lo <= 0 <= hi else "excludes zero"
    sentence = (
        f"the {label} coefficient is {block['month_coef']:.2f} "
        f"(95% CI {lo:.2f} to {hi:.2f}, {side}, n={block['n']}, p={block['month_pvalue']:.3f})"
    )
    if block.get("warnings") or block.get("converged") is False:
        sentence += ". The fit warned that it did not fully settle, so this coefficient is not a month trend"
    return sentence


def repo_table(prs: pd.DataFrame, head: pd.DataFrame) -> str:
    rows = []
    for repo in REPOS:
        opened = prs[(prs["repo"] == repo) & (prs["in_cohort"] == True)]
        human_merged = opened[(opened["author_type"] == "human") & (opened["merged"] == True)]
        group = head[head["repo"] == repo]
        n = int(len(group))
        suff = int(group["bot_sufficient"].sum()) if n else 0
        rows.append(
            "<tr>"
            f"<td>{html.escape(repo)}</td>"
            f"<td>{len(opened)}</td>"
            f"<td>{len(human_merged)}</td>"
            f"<td>{n}</td>"
            f"<td>{suff} ({pct(suff, n)})</td>"
            f"<td>{int(group['in_A'].sum()) if n else 0}</td>"
            f"<td>{int(group['in_Aci'].sum()) if n else 0}</td>"
            f"<td>{int(group['in_B'].sum()) if n else 0}</td>"
            f"<td>{int(group['in_D'].sum()) if n else 0}</td>"
            "</tr>"
        )
    n = int(len(head))
    suff = int(head["bot_sufficient"].sum())
    opened = prs[prs["in_cohort"] == True]
    human_merged = opened[(opened["author_type"] == "human") & (opened["merged"] == True)]
    rows.append(
        "<tr>"
        "<td><strong>All seven</strong></td>"
        f"<td>{len(opened)}</td>"
        f"<td>{len(human_merged)}</td>"
        f"<td>{n}</td>"
        f"<td>{suff} ({pct(suff, n)})</td>"
        f"<td>{int(head['in_A'].sum())}</td>"
        f"<td>{int(head['in_Aci'].sum())}</td>"
        f"<td>{int(head['in_B'].sum())}</td>"
        f"<td>{int(head['in_D'].sum())}</td>"
        "</tr>"
    )
    return (
        "<table><thead><tr>"
        "<th>Repository</th><th>Opened in window</th><th>Human, merged</th>"
        "<th>Headline</th><th>Bot-sufficient</th><th>A</th><th>A-ci</th><th>B</th><th>D</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def examples(head: pd.DataFrame, flag: str) -> str:
    rows = head[head[flag] == True].head(5)
    if rows.empty:
        return "<p>None in this run.</p>"
    bits = []
    for _, row in rows.iterrows():
        bits.append(
            f"<li><a href=\"{html.escape(str(row['url']))}\">"
            f"{html.escape(str(row['repo']))}#{int(row['number'])} "
            f"{html.escape(str(row['title'])[:140])}</a></li>"
        )
    return "<ul>" + "".join(bits) + "</ul>"


def main() -> None:
    prs = load_prs()
    findings = load_findings()
    head = headline(prs)
    six = head[head["repo"] != "app"].copy()
    regions = overlap_counts(head)
    monthly = month_rows(head)
    reg = reg_frame(head)
    six_reg = reg_frame(six)
    controlled = (
        "bot_sufficient ~ month_index + C(repo, Treatment(reference='app')) "
        "+ C(size_bucket, Treatment(reference='S')) "
        "+ C(tenure_bucket, Treatment(reference='2y+'))"
    )
    six_controlled = (
        "bot_sufficient ~ month_index + C(repo, Treatment(reference='data-platform')) "
        "+ C(size_bucket, Treatment(reference='S')) "
        "+ C(tenure_bucket, Treatment(reference='2y+'))"
    )
    fits = {
        "all_uncontrolled": fit_logit(reg, "bot_sufficient ~ month_index"),
        "all_controlled": fit_logit(reg, controlled),
        "all_engagement": fit_logit(reg, controlled + " + substantive_comments_after"),
        "six_uncontrolled": fit_logit(six_reg, "bot_sufficient ~ month_index"),
        "six_controlled": fit_logit(six_reg, six_controlled),
    }
    exact = head[head["first_lgtm_exact"] == True]
    fits["exact_controlled"] = fit_logit(reg_frame(exact), controlled)

    no_appr = int(((head["human_approval_count"].fillna(0) == 0) & (head["review_dismissals"].fillna(0) == 0)).sum())
    known = head[head["ci_known"] == True]
    not_mergeable = int((known["mergeable_at_lgtm"] == False).sum())
    apr_n = int((head["month"] == "2026-04").sum())
    may_n = int((head["month"] == "2026-05").sum())
    suff_n = int(head["bot_sufficient"].sum())
    n = int(len(head))
    six_n = int(len(six))
    six_suff = int(six["bot_sufficient"].sum())

    svgs = {
        "pooled": chart_pooled(monthly),
        "by_repo": chart_by_repo(head),
        "buckets": chart_buckets(monthly),
        "cats": chart_categories(findings),
        "time": chart_time(head),
    }
    rel = "out/pooled"
    all_ctrl = slope_sentence(fits["all_controlled"], "month")
    all_unc = slope_sentence(fits["all_uncontrolled"], "month")
    six_ctrl = slope_sentence(fits["six_controlled"], "month")
    six_unc = slope_sentence(fits["six_uncontrolled"], "month")
    engage = slope_sentence(fits["all_engagement"], "month")
    exact_line = slope_sentence(fits["exact_controlled"], "month")

    body = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>All repositories: bot LGTM and human review</title>
<style>
body {{ font-family: Helvetica, Arial, sans-serif; max-width: 980px; margin: 32px auto; color: #222; line-height: 1.5; }}
h1,h2,h3 {{ line-height: 1.25; }}
.chart svg {{ max-width: 100%; height: auto; }}
.assessment {{ background: #f4f8fb; border: 1px solid #d5e3ee; border-radius: 8px; padding: 16px 20px; margin: 16px 0 28px; }}
table {{ border-collapse: collapse; font-size: 13px; }}
td, th {{ border-bottom: 1px solid #ddd; padding: 4px 8px; text-align: left; }}
code {{ font-family: ui-monospace, monospace; font-size: 0.92em; }}
</style></head><body>
<h1>Is the first bot LGTM becoming sufficient?</h1>
<p>All seven repositories. Pull requests opened 1 Apr 2026 through 30 Sep 2026. The bucket definitions match the app report. This page adds the model that pools the repositories.</p>
<section class="assessment">
<h2>Assessment</h2>
<p><strong>This study does not answer whether the first LGTM is becoming sufficient month over month.</strong></p>
<p>The level, on the same definition as the app report, is {suff_n} of {n} merged human pull requests ({pct(suff_n, n)}). Each of those pull requests has a bot LGTM and shows neither bucket A nor bucket B. app is {int((head['repo']=='app').sum())} of those {n}. The other six repositories together are {six_suff} of {six_n} ({pct(six_suff, six_n)}).</p>
<p>With repository, size, and tenure in the model, {all_ctrl}. With month alone, {all_unc}.</p>
<p>The same two fits on actions, mcap, foxglove-sdk, infra, infra-admin, and data-platform: with repository, size, and tenure, {six_ctrl}. With month alone, {six_unc}.</p>
<p>Four facts keep the month question open:</p>
<ul>
<li>April has {apr_n} headline pull requests and May has {may_n}. The exact comment <code>LGTM</code> starts on 18 Jun 2026. Before that, a clean bot pass was ordinary prose, and this study does not count that prose. The early months are a different signal.</li>
<li>The bot's model and prompt changed on 18 Jun, from 26 Jul to 28 Jul, and on 22 Sep. One slope across those changes mixes a definition change with a catch-rate change.</li>
<li>September's 30-day follow-up was still open on 3 Oct 2026. Later fixes for September are still missing.</li>
<li>Bucket B only counts a fix when the title looks like a fix and git blame can name the source pull request. The Linear check of that search exists for app only. Sentry is not connected. Missed fixes would lower the sufficient share.</li>
</ul>
<p>{not_mergeable} of {len(known)} headline pull requests with CI data were not mergeable at the first LGTM commit. {no_appr} merged with no human approval. Those two facts are about process. They do not identify a month trend.</p>
</section>
<h2>Counts by repository</h2>
<p>Headline means a human author, merged, opened in the window, and at least one bot comment that contains the word LGTM. Opened-in-window is every pull request in that window, including ones with no LGTM.</p>
{repo_table(prs, head)}
<p>Per-repository pages, with their own Venn diagrams, are <code>out/report.html</code> for app and <code>out/&lt;repo&gt;/report.html</code> for the other six. Per-developer pages sit beside those files.</p>
<h2>Where the categories overlap</h2>
<p>These circles use the {n} headline pull requests from all seven repositories. A pull request can sit in more than one bucket.</p>
<h3>A and B decide bot-sufficient</h3>
<p>Bucket A is a real medium or high bug, security, or data-loss comment after the LGTM. The author acknowledged it, or a later commit changed that file, and CI at the counterfactual commit would not have caught it. Bucket B is a later fix whose blamed line was already in that commit, merged within 30 days. A pull request in A or B is not bot-sufficient.</p>
<div class="chart">{venn_ab(regions)}</div>
<h3>A, B, and D</h3>
<p>Bucket D is a later fix whose blamed line was absent at the counterfactual commit and present on the final head, merged within 30 days. D alone leaves the pull request bot-sufficient.</p>
<div class="chart">{venn_abd(regions)}</div>
<h3>A and A-ci</h3>
<p>A-ci is the same kind of comment as A, and the comment names CI, a test, or lint, while a required check was already failing. A-ci stays bot-sufficient.</p>
<div class="chart">{venn_aci(regions)}</div>
<p>Bucket C is the {regions["C"]} headline pull requests in none of A, A-ci, B, or D. Bot-sufficient also includes D-only and A-ci-only. That adds {regions["sufficient"] - regions["C"]} pull requests, for {regions["sufficient"]} bot-sufficient in total.</p>
<h2>1. The month charts</h2>
<p>These charts describe the same pull requests. They do not turn the month coefficient into a trend. Gray points have fewer than 10 pull requests. The shaded month is September.</p>
<div class="chart">{svgs["pooled"]}</div>
<div class="chart">{svgs["by_repo"]}</div>
<div class="chart">{svgs["buckets"]}</div>
<div class="chart">{svgs["cats"]}</div>
<p>Engagement sensitivity, still with repository, size, and tenure: {html.escape(engage)}. Restricting the controlled model to a body that is exactly <code>LGTM</code> leaves out {n - int(len(exact))} headline pull requests. {html.escape(exact_line)}.</p>
<h2>2. Time after the LGTM</h2>
<div class="chart">{svgs["time"]}</div>
<p>Times are calendar hours. They include nights, weekends, and waiting on the author or CI. A negative LGTM-to-approval time means the human approved before the bot's first LGTM.</p>
<h2>3. Method</h2>
<p>The study measures defect-catching. It does not measure knowledge sharing, shared ownership, mentoring, or design alignment. Bot-sufficient means those defect catches were not observed. It is not a claim that human review added nothing.</p>
<p>First bot LGTM is the earliest <code>claude</code> / <code>claude[bot]</code> review or comment whose body contains the token <code>LGTM</code>. From 18 Jun 2026 the prompt requires that body to be exactly <code>LGTM</code>. Comment LGTMs use the last commit at or before the comment.</p>
<p>The primary model, chosen before looking at these pooled results, is <code>bot_sufficient ~ month + C(repo) + C(size) + C(tenure)</code>. April is month 0. September is month 5. The reference repository in the seven-repository fit is app. The reference in the six-repository fit is data-platform. Size reference is S. Tenure reference is 2y+.</p>
<h2>4. Caveats</h2>
<ul>
<li>app is {int((head['repo']=='app').sum())} of {n} headline pull requests. A model with no repository term mostly describes app. The controlled model includes the repository term for that reason.</li>
<li>April and May stay thin in every repository. Filling them requires a classifier for prose clean passes before 18 Jun 2026. That pass was not run for app, and it was not run here.</li>
<li>Bucket A depends on the classifier. The app labels and the other repositories' labels were separate passes with the same rubric. Hand labels in <code>labeling_sample.csv</code> are still empty, so agreement is not computed.</li>
<li>Bucket B is a lower bound. Recall against Linear bug tickets is estimated for app only.</li>
<li>The Checks API returns 403 for this token. A-ci is low because check logs are not readable.</li>
<li>September's follow-up window runs only through 3 Oct 2026.</li>
<li>Each repository page states its own CI and branch-protection limits. Those limits are not repeated here.</li>
</ul>
<h2>5. Next steps</h2>
<ol>
<li>Leave the month question open until the LGTM definition stays stable for several months and September's 30-day window has closed. Recompute September after 31 Oct 2026.</li>
<li>Classify prose clean passes before 18 Jun 2026 if April and May need to enter the headline. Mark 18 Jun as a definition break on every chart.</li>
<li>Hand-label each repository's <code>labeling_sample.csv</code> before treating bucket A as settled.</li>
<li>Raise the recall of bucket B. Connect Sentry, or search for fixes beyond the title words.</li>
<li>Treat A-ci as incomplete until check logs are readable.</li>
</ol>
<h2>6. Examples</h2>
<h3>Bucket A</h3>
{examples(head, "in_A")}
<h3>Bucket B</h3>
{examples(head, "in_B")}
<h3>Bucket D</h3>
{examples(head, "in_D")}
</body></html>
"""
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "report.html").write_text(body)
    lead = (
        "The study does not answer that question. "
        f"The level is {suff_n} of {n} headline pull requests ({pct(suff_n, n)}). "
        f"With repository, size, and tenure, {all_ctrl}. "
        "With repository, size, and tenure on actions, mcap, foxglove-sdk, infra, infra-admin, and data-platform, "
        f"{six_ctrl}."
    )
    (OUT / "report.md").write_text(
        f"""# Is the first bot LGTM becoming sufficient?

{lead}

Bot-sufficient means no bucket A and no bucket B on a merged human pull request that the bot LGTM'd.

- Headline pull requests, all seven repositories: {n}
- Bot-sufficient: {suff_n} ({pct(suff_n, n)})
- Headline pull requests in actions, mcap, foxglove-sdk, infra, infra-admin, and data-platform: {six_n}
- Bot-sufficient in those six: {six_suff} ({pct(six_suff, six_n)})
- Merged with no human approval: {no_appr}
- Not mergeable at the first bot LGTM commit: {not_mergeable} of {len(known)} headline pull requests with CI data

The full reading and the Venn diagrams are in `{rel}/report.html`.

September has a partial follow-up window. The LGTM string itself dates from 18 Jun 2026.
"""
    )
    summary = {
        "headline_n": n,
        "bot_sufficient": suff_n,
        "six_headline_n": six_n,
        "six_bot_sufficient": six_suff,
        "april": apr_n,
        "may": may_n,
        "no_human_approval": no_appr,
        "not_mergeable": not_mergeable,
        "ci_known": int(len(known)),
        "overlap": regions,
        "regressions": fits,
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    monthly.to_csv(OUT / "monthly.csv", index=False)
    print("wrote", OUT / "report.html", flush=True)
    for key, block in fits.items():
        print(key, "ok" if block.get("ok") else block.get("error"), block.get("month_coef"), block.get("month_ci"), block.get("warnings"), flush=True)


if __name__ == "__main__":
    main()
