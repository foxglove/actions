"""Six-month report across every study repository.

The per-repository pages fit month alone. The plan's primary model is
bot_sufficient ~ month + C(repo) + C(size) + C(tenure). This script reads the
already written prs.csv and findings.csv files. It does not call GitHub.
"""

from __future__ import annotations

import html
import json
import warnings
from datetime import datetime
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
    GREEN,
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


def hour_p50(frame: pd.DataFrame, column: str) -> float | None:
    values = frame[column].dropna().astype(float)
    if values.empty:
        return None
    return float(np.percentile(values, 50))


def hour_phrase(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.1f} h"


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


def _flag(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns or frame.empty:
        return pd.Series(False, index=frame.index)
    return frame[column].fillna(False).astype(bool)


def exclusive_buckets(frame: pd.DataFrame) -> dict[str, int]:
    """Mutually exclusive slices. They add up to the headline count."""
    a = _flag(frame, "in_A")
    ac = _flag(frame, "in_Aci")
    b = _flag(frame, "in_B")
    d = _flag(frame, "in_D")
    return {
        "n": int(len(frame)),
        "C": int((~a & ~ac & ~b & ~d).sum()),
        "D_only": int((~a & ~b & d & ~ac).sum()),
        "Aci_only": int((~a & ~b & ac & ~d).sum()),
        "D_and_Aci": int((~a & ~b & d & ac).sum()),
        "A_only": int((a & ~b).sum()),
        "B_only": int((b & ~a).sum()),
        "AB": int((a & b).sum()),
    }


def funnel_html(steps: list[tuple[str, str, int]]) -> str:
    """Each row is inside the row above it. The bars shrink with the count."""
    if not steps:
        return ""
    top = max(steps[0][2], 1)
    items = []
    for label, detail, count in steps:
        width = max(1.5, 100.0 * count / top)
        items.append(
            "<li>"
            f'<div class="funnel-copy"><strong>{html.escape(label)}</strong>'
            f"<span>{html.escape(detail)}</span></div>"
            '<div class="funnel-meter">'
            f'<div class="funnel-scale"><i style="width:{width:.1f}%"></i></div>'
            f"<b>{count:,}</b></div></li>"
        )
    return '<ol class="funnel">' + "".join(items) + "</ol>"


def partition_html(parts_data: list[tuple[str, int, str]], total: int) -> str:
    """One bar. The slices are exclusive and sum to the headline."""
    segs = []
    legend = []
    for label, count, color in parts_data:
        legend.append(
            f'<li><i style="background:{color}"></i>{html.escape(label)} · {count:,}</li>'
        )
        if total <= 0 or count <= 0:
            continue
        width = 100.0 * count / total
        inner = html.escape(f"{count:,}") if width >= 8 else ""
        segs.append(
            f'<i style="width:{width:.2f}%;background:{color}" title="{html.escape(label)} {count:,}">{inner}</i>'
        )
    return (
        '<div class="part" role="img" aria-label="Headline pull requests split into C, D, A-ci, A, and B">'
        f'<div class="part-bar">{"".join(segs)}</div>'
        f'<ul class="legend">{"".join(legend)}</ul></div>'
    )


def _repo_row(label: str, opened: pd.DataFrame, human_merged: pd.DataFrame, group: pd.DataFrame, strong: bool) -> str:
    n = int(len(group))
    suff = int(group["bot_sufficient"].sum()) if n else 0
    known = group[group["ci_known"] == True] if n else group
    not_mergeable = int((known["mergeable_at_lgtm"] == False).sum()) if n else 0
    bucket_c = exclusive_buckets(group)["C"] if n else 0
    name = f"<strong>{html.escape(label)}</strong>" if strong else html.escape(label)
    return (
        "<tr>"
        f"<td>{name}</td>"
        f"<td>{len(opened)}</td>"
        f"<td>{len(human_merged)}</td>"
        f"<td>{n}</td>"
        f"<td>{bucket_c}</td>"
        f"<td>{suff} ({pct(suff, n)})</td>"
        f"<td>{n - suff}</td>"
        f"<td>{not_mergeable}</td>"
        f"<td>{int(group['in_A'].sum()) if n else 0}</td>"
        f"<td>{int(group['in_B'].sum()) if n else 0}</td>"
        f"<td>{int(group['in_D'].sum()) if n else 0}</td>"
        "</tr>"
    )


def repo_table(prs: pd.DataFrame, head: pd.DataFrame) -> str:
    rows = []
    for repo in REPOS:
        opened = prs[(prs["repo"] == repo) & (prs["in_cohort"] == True)]
        human_merged = opened[(opened["author_type"] == "human") & (opened["merged"] == True)]
        rows.append(_repo_row(repo, opened, human_merged, head[head["repo"] == repo], False))
    opened = prs[prs["in_cohort"] == True]
    human_merged = opened[(opened["author_type"] == "human") & (opened["merged"] == True)]
    rows.append(_repo_row("All seven", opened, human_merged, head, True))
    return (
        '<div class="table-scroll"><table class="nums"><thead><tr>'
        "<th>Repository</th><th>Opened in window</th><th>Human, merged</th>"
        "<th>Headline</th><th>C</th><th>Bot-sufficient</th><th>A or B</th><th>Not mergeable at LGTM</th>"
        "<th>A</th><th>B</th><th>D</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></div>"
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


APP_CI_PATHS = {
    ".github/workflows/ci.yml",
    ".github/workflows/playwright.yml",
    ".github/workflows/storybook.yml",
}


def _parse_ts(value: object) -> datetime | None:
    if value is None or isinstance(value, float):
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def minute_phrase(value: float | None) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "no required checks"
    if value < 1:
        return f"{value:.1f} min"
    return f"{value:.0f} min"


def ci_wait(head: pd.DataFrame) -> dict:
    """Wall-clock minutes of required pull_request workflows on the first LGTM commit."""
    rows = []
    app_parts: dict[str, list[float]] = {path: [] for path in APP_CI_PATHS}
    for repo in REPOS:
        ci = ROOT / "data" / "raw" / repo / "ci"
        req_path = ROOT / "data" / "raw" / repo / "meta" / "required_checks.json"
        contexts: set[str] = set()
        if req_path.exists():
            contexts = set(json.loads(req_path.read_text()).get("contexts") or [])
        lookup = {
            int(number): row
            for number, row in head.loc[head["repo"] == repo].set_index("number").iterrows()
        }
        for number, pr in lookup.items():
            created = _parse_ts(pr.get("created_at") if hasattr(pr, "get") else pr["created_at"])
            lgtm_at = _parse_ts(pr["first_lgtm_at"])
            appr_at = _parse_ts(pr["first_human_approval_at"]) if pd.notna(pr["first_human_approval_at"]) else None
            merged_at = _parse_ts(pr["merged_at"]) if pd.notna(pr["merged_at"]) else None

            def _gap(a: datetime | None, b: datetime | None) -> float | None:
                if a is None or b is None:
                    return None
                return (b - a).total_seconds() / 3600.0

            record = {
                "repo": repo,
                "wall": None,
                "first_passed": None,
                "open_lgtm": _gap(created, lgtm_at),
                "lgtm_appr": _gap(lgtm_at, appr_at),
                "open_appr": _gap(created, appr_at),
                "open_merge": _gap(created, merged_at),
                "ci0": None,
                "ci1": None,
            }
            eval_path = ci / "eval" / f"{int(number)}.json"
            if not eval_path.exists():
                rows.append(record)
                continue
            evals = json.loads(eval_path.read_text()).get("evals") or []
            if not evals:
                rows.append(record)
                continue
            first = evals[0]
            record["first_passed"] = bool(first.get("passed"))
            runs_path = ci / "runs" / f"{first['sha']}.json"
            if not runs_path.exists():
                rows.append(record)
                continue
            runs = json.loads(runs_path.read_text()).get("workflow_runs") or []
            picked: dict[str, dict] = {}
            for run in runs:
                if run.get("event") != "pull_request":
                    continue
                path = run.get("path") or ""
                if repo == "app" and path not in APP_CI_PATHS:
                    continue
                if repo != "app" and not contexts:
                    continue
                good = 1 if run.get("conclusion") in ("success", "failure") else 0
                rank = (good, run.get("updated_at") or "")
                prev = picked.get(path)
                if prev is None or rank > (
                    1 if prev.get("conclusion") in ("success", "failure") else 0,
                    prev.get("updated_at") or "",
                ):
                    picked[path] = run
            if repo != "app" and contexts:
                kept = {}
                for path, run in picked.items():
                    job_path = ci / "jobs" / f"{run['id']}.json"
                    if not job_path.exists():
                        continue
                    names = {job.get("name") for job in json.loads(job_path.read_text()).get("jobs") or []}
                    wf = run.get("name") or ""
                    if names & contexts or any(f"{wf} / {name}" in contexts for name in names):
                        kept[path] = run
                picked = kept
            starts = []
            ends = []
            for path, run in picked.items():
                start = _parse_ts(run.get("run_started_at") or run.get("created_at"))
                end = _parse_ts(run.get("updated_at"))
                if start is None or end is None or end < start:
                    continue
                starts.append(start)
                ends.append(end)
                if repo == "app":
                    app_parts[path].append((end - start).total_seconds() / 60.0)
            wall = (max(ends) - min(starts)).total_seconds() / 60.0 if starts else None
            record["wall"] = wall
            record["first_passed"] = bool(first.get("passed"))
            if starts:
                record["ci0"] = (min(starts) - created).total_seconds() / 3600.0 if created else None
                record["ci1"] = (max(ends) - created).total_seconds() / 3600.0 if created else None
            rows.append(record)
    frame = pd.DataFrame(rows)
    by_repo = {}
    for repo in REPOS:
        group = frame[frame["repo"] == repo] if len(frame) else frame
        walls = group["wall"].dropna() if len(group) else pd.Series(dtype=float)
        by_repo[repo] = {
            "n": int(len(group)),
            "not_green": int((group["first_passed"] == False).sum()) if len(group) else 0,
            "p50": float(walls.median()) if len(walls) else None,
            "p90": float(walls.quantile(0.9)) if len(walls) else None,
        }

    def part(path: str) -> float | None:
        series = pd.Series(app_parts[path], dtype=float)
        return float(series.median()) if len(series) else None

    green = head[head["mergeable_at_lgtm"] == True]["lgtm_to_merge_h"].dropna()
    red = head[head["mergeable_at_lgtm"] == False]["lgtm_to_merge_h"].dropna()
    after = frame[frame["lgtm_appr"].notna() & (frame["lgtm_appr"] >= 0)]

    def p50(column: str) -> float | None:
        series = after[column].dropna() if column in after.columns else pd.Series(dtype=float)
        return float(series.median()) if len(series) else None

    return {
        "by_repo": by_repo,
        "app_ci": part(".github/workflows/ci.yml"),
        "app_playwright": part(".github/workflows/playwright.yml"),
        "app_storybook": part(".github/workflows/storybook.yml"),
        "green_to_merge_p50": float(green.median()) if len(green) else None,
        "red_to_merge_p50": float(red.median()) if len(red) else None,
        "gantt": {
            "n": int(len(after)),
            "lgtm": p50("open_lgtm"),
            "ci0": p50("ci0"),
            "ci1": p50("ci1"),
            "appr": p50("open_appr"),
            "merge": p50("open_merge"),
            "lgtm_appr": p50("lgtm_appr"),
            "appr_merge": float((after.loc[after["open_merge"].notna() & after["open_appr"].notna(), "open_merge"] - after.loc[after["open_merge"].notna() & after["open_appr"].notna(), "open_appr"]).median()) if (after["open_merge"].notna() & after["open_appr"].notna()).any() else None,
            "ci_still_at_lgtm": int(((frame["ci1"] > frame["open_lgtm"]) & frame["ci1"].notna()).sum()),
            "ci_known": int(frame["ci1"].notna().sum()),
            "appr_before": int((frame["lgtm_appr"] < 0).sum()),
            "ci_minutes": float(((after["ci1"] - after["ci0"]).dropna() * 60).median()) if after["ci0"].notna().any() else None,
        },
    }


def _clock(hours: float | None) -> str:
    if hours is None:
        return "n/a"
    if abs(hours) < 1:
        return f"{hours * 60:.0f} min"
    return f"{hours:.1f} h"


def gantt_html(gantt: dict, axis_hours: float, zoom: bool) -> str:
    """Median clocks from pull request open. Tests overlap stage 1.

    The layout is HTML so the labels stay full size on a phone and on a desktop.
    """
    lgtm = float(gantt["lgtm"] or 0)
    ci0 = float(gantt["ci0"] or 0)
    ci_len = float(gantt.get("ci_minutes") or 0) / 60.0
    human = float(gantt.get("lgtm_appr") or 0)
    tail = float(gantt.get("appr_merge") or 0)
    bars = [
        ("1. Open to bot LGTM", 0.0, lgtm, "#0072B2", _clock(lgtm)),
        ("Tests, required CI", ci0, ci0 + ci_len, "#E69F00", _clock(ci_len)),
        ("2. Human, to approval", lgtm, lgtm + human, "#009E73", _clock(human)),
        ("3. Approval to merge", lgtm + human, lgtm + human + tail, "#56B4E9", _clock(tail)),
    ]
    if zoom:
        bars = bars[:3]
    axis = float(axis_hours) if axis_hours else 1.0
    ticks = list(range(int(axis) + 1)) if zoom else list(range(0, int(axis) + 1, 6))
    if ticks[-1] != int(axis):
        ticks.append(int(axis))
    rows = []
    for label, start, end, color, duration in bars:
        start_c = max(0.0, start)
        end_c = max(start_c, end)
        clipped = end_c > axis + 1e-9
        vis_end = min(end_c, axis)
        left = 100.0 * min(start_c, axis) / axis
        width = max(100.0 * (vis_end - min(start_c, axis)) / axis, 0.6)
        note = f"{duration}, continues past {axis:.0f} h" if clipped else duration
        rows.append(
            '<div class="gantt-row">'
            f'<div class="gantt-name"><i style="background:{color}"></i>'
            f"<span><strong>{html.escape(label)}</strong><em>{html.escape(note)}</em></span></div>"
            '<div class="gantt-track">'
            f'<b style="left:{left:.2f}%;width:{width:.2f}%;background:{color}"></b>'
            "</div></div>"
        )
    tick_html = "".join(f"<span>{tick} h</span>" for tick in ticks)
    title = "First 3 hours" if zoom else "Open to merge"
    return (
        f'<figure class="gantt" aria-label="Gantt chart, {html.escape(title)}">'
        f"<figcaption>{html.escape(title)}</figcaption>"
        + "".join(rows)
        + f'<div class="gantt-axis-row"><div></div><div class="gantt-axis">{tick_html}</div></div>'
        "</figure>"
    )


def ci_table(wait: dict) -> str:
    rows = []
    for repo in REPOS:
        block = wait["by_repo"][repo]
        rows.append(
            "<tr>"
            f"<td>{html.escape(repo)}</td>"
            f"<td>{block['n']}</td>"
            f"<td>{block['not_green']}</td>"
            f"<td>{minute_phrase(block['p50'])}</td>"
            f"<td>{minute_phrase(block['p90'])}</td>"
            "</tr>"
        )
    return (
        '<div class="table-scroll"><table class="nums"><thead><tr><th>Repository</th><th>Headline</th>'
        "<th>First LGTM commit not green</th><th>CI median</th><th>CI p90</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></div>"
    )


def main() -> None:
    prs = load_prs()
    findings = load_findings()
    head = headline(prs)
    six = head[head["repo"] != "app"].copy()
    regions = overlap_counts(head)
    slices = exclusive_buckets(head)
    wait = ci_wait(head)
    on_headline = pd.Series(
        [(repo, int(pr)) in set(zip(head["repo"], head["number"].astype(int))) for repo, pr in zip(findings["repo"], findings["pr"])],
        index=findings.index,
    )
    comments = findings.loc[on_headline]
    after_comments = comments[comments["timing"] == "after"]
    real_after = after_comments[after_comments["is_real"] == True]
    defect_after = real_after[
        real_after["category"].isin(["BUG", "SECURITY", "DATA_LOSS_OR_CORRUPTION"])
        & real_after["severity"].isin(["medium", "high"])
    ]
    comment_counts = {
        "on_headline": int(len(comments)),
        "after": int(len(after_comments)),
        "real_after": int(len(real_after)),
        "nit_after": int((real_after["category"] == "NIT/STYLE").sum()),
        "mh_defect": int(len(defect_after)),
        "bucket_a": int((comments["bucket_a"] == True).sum()),
        "bucket_aci": int((comments["bucket_a_ci"] == True).sum()),
    }
    comment_counts["entered"] = comment_counts["bucket_a"] + comment_counts["bucket_aci"]
    opened_n = int((prs["in_cohort"] == True).sum())
    human_merged_n = int(
        ((prs["in_cohort"] == True) & (prs["author_type"] == "human") & (prs["merged"] == True)).sum()
    )
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
    mergeable = head[head["mergeable_at_lgtm"] == True]
    mergeable_n = int(len(mergeable))
    mergeable_miss = int((~mergeable["bot_sufficient"]).sum()) if mergeable_n else 0
    apr_n = int((head["month"] == "2026-04").sum())
    may_n = int((head["month"] == "2026-05").sum())
    suff_n = int(head["bot_sufficient"].sum())
    n = int(len(head))
    six_n = int(len(six))
    six_suff = int(six["bot_sufficient"].sum())
    app_head = head[head["repo"] == "app"]
    app_n = int(len(app_head))
    app_miss = app_n - int(app_head["bot_sufficient"].sum())
    six_miss = six_n - six_suff
    jun = monthly[monthly["month"] >= "2026-06"]
    jun_phrase = ", ".join(
        f"{MONTH_LABELS[row.month]} {pct(int(row.k), int(row.n))} (n={int(row.n)})" for row in jun.itertuples()
    )
    sizes = ["XS", "S", "M", "L", "XL"]
    app_only = head[head["repo"] == "app"]
    other_only = head[head["repo"] != "app"]

    def _size_share(frame: pd.DataFrame) -> pd.Series:
        return frame["size_bucket"].value_counts(normalize=True).reindex(sizes).fillna(0.0)

    def _size_rate(frame: pd.DataFrame) -> pd.Series:
        return frame.groupby("size_bucket")["bot_sufficient"].mean().reindex(sizes)

    app_at_other_mix = float((_size_rate(app_only) * _size_share(other_only)).sum())
    other_at_app_mix = float((_size_rate(other_only) * _size_share(app_only)).sum())
    large = app_only[app_only["size_bucket"].isin(["L", "XL"])]
    large_miss = int((~large["bot_sufficient"]).sum())
    app_miss_n = int((~app_only["bot_sufficient"]).sum())
    headline_keys = set(zip(app_only["repo"], app_only["number"].astype(int)))
    on_headline = pd.Series(
        [(repo, int(pr)) in headline_keys for repo, pr in zip(findings["repo"], findings["pr"])],
        index=findings.index,
    )
    a_findings = findings.loc[on_headline & (findings["bucket_a"] == True)].copy()

    def _area(path: object) -> str:
        if not isinstance(path, str) or not path:
            return "(no path)"
        parts = path.split("/")
        if parts[0] == "packages" and len(parts) > 1:
            return "/".join(parts[:2])
        return parts[0]

    a_findings["area"] = a_findings["path"].map(_area)
    area_counts = a_findings["area"].value_counts()
    area_phrase = ", ".join(f"{name} {int(count)}" for name, count in area_counts.head(3).items())
    a_bug_n = int((a_findings["category"] == "BUG").sum())
    a_finding_n = int(len(a_findings))
    a_all = comments[comments["bucket_a"] == True]
    a_pr_n = int(head["in_A"].sum())
    a_app_n = int(app_only["in_A"].sum())
    a_high_n = int((a_all["severity"] == "high").sum())
    a_sec_n = int((a_all["category"] == "SECURITY").sum())
    a_loss_n = int((a_all["category"] == "DATA_LOSS_OR_CORRUPTION").sum())
    a_bug_all = int((a_all["category"] == "BUG").sum())
    a_change_n = int((a_all["code_change"] == True).sum())
    a_finding_all = int(len(a_all))
    top_areas = ["packages/app", "packages/api", "packages/viz"]
    top_area_n = int(area_counts.reindex(top_areas).fillna(0).sum())
    green_a_n = int(((head["mergeable_at_lgtm"] == True) & (head["in_A"] == True)).sum())
    b_n = int(head["in_B"].sum())
    b_app_n = int(app_only["in_B"].sum())
    b_xl_n = int(app_only.loc[app_only["size_bucket"] == "XL", "in_B"].sum())
    size_help_rows = []
    for size in sizes:
        group = app_only[app_only["size_bucket"] == size]
        n_s = int(len(group))
        a_s = int(group["in_A"].sum())
        rate = (100.0 * a_s / n_s) if n_s else 0
        share = "<1%" if 0 < rate < 1 else pct(a_s, n_s)
        size_help_rows.append(
            f"<tr><td>{size}</td><td>{n_s}</td><td>{a_s}</td><td>{share}</td></tr>"
        )
    other_a_bits = []
    other_a_zero = []
    for repo in REPOS:
        if repo == "app":
            continue
        count = int(head.loc[head["repo"] == repo, "in_A"].sum())
        if count:
            other_a_bits.append(f"{repo} {count}")
        else:
            other_a_zero.append(repo)
    other_a_phrase = ", ".join(other_a_bits)
    if len(other_a_zero) > 1:
        other_a_zero_phrase = ", ".join(other_a_zero[:-1]) + ", and " + other_a_zero[-1]
    else:
        other_a_zero_phrase = ", ".join(other_a_zero)
    area_bits = [f"{name} ({int(area_counts.get(name, 0))})" for name in top_areas]
    area_named = ", ".join(area_bits[:-1]) + ", and " + area_bits[-1]

    def _approval(frame: pd.DataFrame) -> str:
        return hour_phrase(hour_p50(frame, "lgtm_to_approval_h"))

    xl_app = app_only[app_only["size_bucket"] == "XL"]
    l_app = app_only[app_only["size_bucket"] == "L"]
    xl_a_wait = _approval(xl_app[xl_app["in_A"] == True])
    xl_rest_wait = _approval(xl_app[xl_app["in_A"] != True])
    l_a_wait = _approval(l_app[l_app["in_A"] == True])
    l_rest_wait = _approval(l_app[l_app["in_A"] != True])
    p50_approval = hour_p50(head, "lgtm_to_approval_h")
    p50_merge = hour_p50(head, "lgtm_to_merge_h")
    p50_after = hour_p50(head, "approval_to_merge_h")
    month_wait = []
    for month in MONTHS:
        if month < "2026-06":
            continue
        group = head[head["month"] == month]
        month_wait.append(f"{MONTH_LABELS[month]} {hour_phrase(hour_p50(group, 'lgtm_to_approval_h'))}")
    wait_phrase = ", ".join(month_wait)

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
    gantt = wait["gantt"]
    chain = (gantt["lgtm"] or 0) + (gantt["lgtm_appr"] or 0) + (gantt["appr_merge"] or 0)
    gantt_axis = max(6, int(chain + 2))
    gantt_axis = ((gantt_axis + 5) // 6) * 6

    body = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>All repositories: bot LGTM and human review</title>
<style>
body {{ font-family: Helvetica, Arial, sans-serif; max-width: 980px; margin: 0 auto; padding: 16px 16px 72px; color: #222; line-height: 1.5; font-size: 16px; }}
h1 {{ font-size: 1.45rem; line-height: 1.25; }}
h2 {{ font-size: 1.2rem; line-height: 1.3; margin-top: 1.6em; }}
h3 {{ font-size: 1.05rem; line-height: 1.3; }}
.nav {{ display: flex; flex-wrap: wrap; gap: 8px 14px; margin: 8px 0 4px; }}
.nav a {{ color: #0b4f8a; }}
.assessment {{ background: #f4f8fb; border: 1px solid #d5e3ee; border-radius: 8px; padding: 14px 14px; margin: 16px 0 28px; }}
.chart {{ overflow-x: auto; -webkit-overflow-scrolling: touch; margin: 12px 0 20px; }}
.chart svg {{ display: block; width: 100%; min-width: 680px; height: auto; }}
.swipe-hint {{ display: none; color: #555; font-size: 0.92rem; margin: 0 0 6px; }}
.table-scroll {{ overflow-x: auto; -webkit-overflow-scrolling: touch; margin: 8px 0 18px; }}
table {{ border-collapse: collapse; width: 100%; font-size: 15px; }}
td, th {{ border-bottom: 1px solid #ddd; padding: 8px 10px; text-align: left; vertical-align: top; }}
table.nums {{ min-width: 640px; }}
table.def td:first-child {{ font-weight: 700; white-space: nowrap; }}
code {{ font-family: ui-monospace, monospace; font-size: 0.92em; }}
.gantt {{ margin: 4px 0 22px; }}
.gantt figcaption {{ font-weight: 700; margin: 0 0 8px; }}
.gantt-row, .gantt-axis-row {{ display: grid; grid-template-columns: minmax(190px, 250px) minmax(0, 1fr); gap: 6px 12px; align-items: center; margin: 0 0 10px; }}
.gantt-name {{ display: flex; gap: 8px; align-items: flex-start; min-width: 0; }}
.gantt-name i {{ width: 12px; height: 12px; border-radius: 2px; margin-top: 5px; flex: none; }}
.gantt-name span {{ display: flex; flex-direction: column; min-width: 0; }}
.gantt-name em {{ font-style: normal; color: #555; font-size: 0.92rem; }}
.gantt-track {{ position: relative; height: 22px; background: #eee; border-radius: 4px; }}
.gantt-track b {{ position: absolute; top: 3px; height: 16px; border-radius: 3px; min-width: 6px; }}
.gantt-axis {{ display: flex; justify-content: space-between; color: #555; font-size: 12px; }}
.funnel {{ list-style: none; padding: 0; margin: 8px 0 18px; }}
.funnel li {{ display: grid; grid-template-columns: minmax(180px, 34%) minmax(0, 1fr); gap: 4px 16px; align-items: center; margin: 0 0 12px; }}
.funnel-copy {{ display: flex; flex-direction: column; min-width: 0; }}
.funnel-copy span {{ color: #555; font-size: 0.92rem; }}
.funnel-meter {{ display: flex; align-items: center; gap: 8px; min-width: 0; }}
.funnel-scale {{ flex: 1; height: 22px; background: #eee; border-radius: 4px; min-width: 0; }}
.funnel-scale i {{ display: block; height: 100%; background: #0072B2; border-radius: 4px; }}
.funnel-meter b {{ flex: none; min-width: 4.2em; text-align: right; }}
.part {{ margin: 8px 0 18px; }}
.part-bar {{ display: flex; height: 40px; border-radius: 6px; overflow: hidden; background: #eee; }}
.part-bar > i {{ display: flex; align-items: center; justify-content: center; color: #fff; font-style: normal; font-size: 12px; overflow: hidden; min-width: 2px; }}
.legend {{ display: flex; flex-wrap: wrap; gap: 8px 16px; list-style: none; padding: 10px 0 0; margin: 0; }}
.legend li {{ display: flex; align-items: center; gap: 6px; }}
.legend i {{ width: 12px; height: 12px; border-radius: 2px; flex: none; }}
@media (min-width: 900px) {{
  body {{ padding: 28px 32px 80px; font-size: 17px; }}
  h1 {{ font-size: 1.85rem; }}
  .assessment {{ padding: 18px 20px; }}
}}
@media (max-width: 640px) {{
  .swipe-hint {{ display: block; }}
  .gantt-row, .gantt-axis-row, .funnel li {{ grid-template-columns: 1fr; gap: 4px; }}
  .gantt-axis-row > :first-child {{ display: none; }}
  .gantt-track {{ height: 28px; }}
  .gantt-track b {{ top: 5px; height: 18px; }}
  table.def, table.def thead, table.def tbody, table.def tr, table.def td {{ display: block; width: auto; }}
  table.def thead {{ position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }}
  table.def tr {{ border: 1px solid #ddd; border-radius: 8px; margin: 0 0 12px; padding: 8px 12px; }}
  table.def td {{ border: 0; padding: 4px 0; white-space: normal; }}
  table.def td::before {{ content: attr(data-label); display: block; font-size: 12px; color: #555; font-weight: 700; }}
}}
</style></head><body>
<h1>Conclusion: keep human review, and the months are flat</h1>
<p>All seven repositories. Pull requests opened 1 Apr 2026 through 30 Sep 2026.</p>
<p class="nav"><a href="#path">The wait</a><a href="#change">What to change</a><a href="#helps">Where review helps</a><a href="#buckets">Buckets</a><a href="#app">Why app is lower</a></p>
<h2 id="path">The path from open to merge</h2>
<p>Stage 1 is open to the first bot LGTM. Tests run during stage 1. Stage 2 is the wait for a human approval. Stage 3 is approval to merge.</p>
<p>The bars cover the {gantt["n"]} headline pull requests where a person approved after the bot. {gantt["appr_before"]} approvals came before the bot. Those pull requests are left off the bars.</p>
<p>Each bar is as long as the median wait for that stage. Tests start at their median start, during stage 1. Stage 2 starts at the end of stage 1. Stage 3 starts at the end of stage 2. The first chart runs through merge. The second chart is the first 3 hours, so stage 1 and the tests are wide enough to see.</p>
{gantt_html(gantt, gantt_axis, False)}
<p>Tests are still running at the LGTM on {gantt["ci_still_at_lgtm"]} of {gantt["ci_known"]} pull requests.</p>
{gantt_html(gantt, 3, True)}
<p>Adding the three stage medians gives {_clock(chain)}. The median time from open to merge is {_clock(gantt["merge"])}. A pull request that is slow at one stage is often a different pull request from one that is slow at the next, so the open-to-merge median is the longer clock.</p>
<p>The long green bar is the human review. That stage is where bucket A is found. <a href="#helps">Where human review helps</a> counts those catches.</p>
<section class="assessment">
<h2 id="change">How to change code review</h2>
<p><strong>Keep a human approval on app. Treat a bot LGTM as a merge signal only after the required checks pass on that commit. Try a lighter review only as a pilot in one owned area.</strong></p>
<p>{suff_n} of {n} headline pull requests are bot-sufficient ({pct(suff_n, n)}). Bot-sufficient means neither bucket A nor bucket B. Bucket C is {slices["C"]} of those {suff_n}. C is the usual case: no A, no A-ci, no B, and no D. The funnel below counts every bucket, including C. The other {n - suff_n} pull requests are in A or B.</p>
<p>On app, {app_miss} of {app_n} headline pull requests are in A or B ({pct(app_miss, app_n)}). Keep the human approval there.</p>
<p>On actions, mcap, foxglove-sdk, infra, infra-admin, and data-platform, {six_miss} of {six_n} are in A or B ({pct(six_miss, six_n)}). A lighter pilot fits that group. Limit it to one area with one owner. Merge only after required checks pass. Revert quickly if production signals fail. Keep it a pilot until that pilot has a result.</p>
<p>{not_mergeable} of {len(known)} headline pull requests were not mergeable at the first LGTM commit. Required checks were still failing, or had not run. Wait for those checks. On app that wait is a median of {minute_phrase(wait["by_repo"]["app"]["p50"])}. It blocks a red build. It does not catch bucket A. Bucket A is a label on a human comment, and those comments are the bugs CI would not have caught. Among the {mergeable_n} pull requests that were already mergeable at that commit, {mergeable_miss} are still in A or B ({pct(mergeable_miss, mergeable_n)}).</p>
<p>The wait is the human approval. Median time from LGTM to the first human approval is {hour_phrase(p50_approval)}. Median time from that approval to merge is {hour_phrase(p50_after)}. Median time from LGTM to merge is {hour_phrase(p50_merge)}. These are calendar hours. They include nights and weekends. {no_appr} headline pull requests merged with no human approval. That group is too small for a comparison.</p>
<h2 id="helps">Where human review helps</h2>
<p>Human review helps when a person finds a real bug after the bot has said LGTM, and CI at that commit would not have caught it. That catch is bucket A.</p>
<p><strong>The catches sit on large app changes, in packages/app, packages/api, and packages/viz.</strong></p>
<p>{a_pr_n} of {n} headline pull requests are in bucket A. {a_app_n} of those {a_pr_n} are in app. Those pull requests carry {a_finding_all} comments. {a_bug_all} are bugs, {a_loss_n} are data loss, and {a_sec_n} are security. {a_high_n} are high severity. {a_change_n} of the {a_finding_all} were followed by a commit that changed that file.</p>
<p>App, by size. The share is the portion of headline pull requests in that size that are in bucket A.</p>
<table><thead><tr><th>App size</th><th>Headline</th><th>Bucket A</th><th>Share</th></tr></thead><tbody>
{"".join(size_help_rows)}
</tbody></table>
<p>On app, {top_area_n} of {a_finding_n} bucket A findings are in {html.escape(area_named)}. Those three paths are the place to aim a deeper read and a better bot check.</p>
<p>Outside app, bucket A is {a_pr_n - a_app_n} pull requests: {other_a_phrase}. {other_a_zero_phrase} have none in this window.</p>
<p>{green_a_n} of the {mergeable_n} pull requests that were already green at the LGTM commit are still in bucket A. The required checks had passed. The person still found the bug.</p>
<p>On app the wait is longer when the pull request is in bucket A. For XL the median from LGTM to approval is {xl_a_wait} with a bucket A catch and {xl_rest_wait} without one. For L the medians are {l_a_wait} and {l_rest_wait}. The file change is in the record, so the longer clock includes the fix.</p>
<p>Bucket B is a later fix of a line that was already in the LGTM commit. That bug merged. B is {b_n} headline pull requests. {b_app_n} are in app. {b_xl_n} are XL app changes. A comment in bucket A is the help. A later fix in bucket B is a bug that shipped.</p>
<h2>How the months are moving</h2>
<p><strong>From June through September the bot-sufficient share stays near 88%. This study does not show it rising or falling.</strong></p>
<p>The monthly shares are {jun_phrase}. April has {apr_n} headline pull requests and May has {may_n}. The word LGTM starts on 18 Jun 2026, so those two months are a different signal.</p>
<p>With repository, size, and tenure in the model, {all_ctrl}. With month alone, {all_unc}. On actions, mcap, foxglove-sdk, infra, infra-admin, and data-platform, with repository, size, and tenure, {six_ctrl}. With month alone on those six, {six_unc}.</p>
<p>Median hours from LGTM to the first human approval, by month: {wait_phrase}. That series is the clock, not the defect rate. It is not a fitted trend.</p>
<p>Four facts keep a month trend off the table:</p>
<ul>
<li>The bot's model and prompt changed on 18 Jun, from 26 Jul to 28 Jul, and on 22 Sep. One slope across those dates mixes a definition change with a catch-rate change.</li>
<li>September's 30-day follow-up was still open on 3 Oct 2026. Later fixes for September are still missing.</li>
<li>Bucket B only counts a fix when the title looks like a fix and git blame can name the source pull request. The Linear check of that search exists for app only. Sentry is not connected. Missed fixes would lower the sufficient share.</li>
<li>The controlled fit warned that it did not fully settle. A coefficient from a fit that did not settle is not a trend.</li>
</ul>
</section>
<h2 id="buckets">What A, B, C, and D mean</h2>
<p>There are five labels. C is the one the other letters leave out. A pull request can carry more than one of A, A-ci, B, and D. C means it carries none of them.</p>
<table class="def">
<thead><tr><th>Bucket</th><th>What it is</th><th>Bot-sufficient?</th></tr></thead>
<tbody>
<tr><td data-label="Bucket">C</td><td data-label="What it is">None of the four signals below. This is the ordinary headline pull request.</td><td data-label="Bot-sufficient?">Yes</td></tr>
<tr><td data-label="Bucket">A</td><td data-label="What it is">A real medium or high bug, security issue, or data-loss comment after the first bot LGTM. The author acknowledged it, or a later commit changed that file. CI at the counterfactual commit would not have caught it.</td><td data-label="Bot-sufficient?">No</td></tr>
<tr><td data-label="Bucket">A-ci</td><td data-label="What it is">The same kind of comment as A, and the comment names CI, a test, or lint, while a required check was already failing.</td><td data-label="Bot-sufficient?">Yes. The check was already red.</td></tr>
<tr><td data-label="Bucket">B</td><td data-label="What it is">A later fix. Blame shows the fixed line was already in the LGTM commit. The fix merged within 30 days. The line text is unique, and the match is medium or high confidence. B misses fixes the title search does not see, so it is a lower bound.</td><td data-label="Bot-sufficient?">No</td></tr>
<tr><td data-label="Bucket">D</td><td data-label="What it is">A later fix whose blamed line was not in the LGTM commit. The line was added before the final head. The fix merged within 30 days.</td><td data-label="Bot-sufficient?">Yes, when D is alone. The line was not there at the LGTM.</td></tr>
</tbody>
</table>
<p>Read the funnel from top to bottom. Each row is inside the row above it. The last row is bucket C.</p>
{funnel_html([
    ("Opened in the window", "1 Apr through 30 Sep 2026", opened_n),
    ("Human author, merged", "May have no bot LGTM", human_merged_n),
    ("Headline", "Also has a bot LGTM", n),
    ("Bot-sufficient", "Not in A and not in B", suff_n),
    ("Bucket C", "Also not in A-ci and not in D", slices["C"]),
])}
<p>The bar below splits the {n} headline pull requests into slices that do not overlap. They sum to {n}. C is the long green slice. A or B is the part that removes bot-sufficient.</p>
{partition_html([
    ("C", slices["C"], GREEN),
    ("D only", slices["D_only"], SKY),
    ("A-ci only", slices["Aci_only"], ORANGE),
    ("D and A-ci", slices["D_and_Aci"], "#0072B2"),
    ("A only", slices["A_only"], VERM),
    ("B only", slices["B_only"], PURPLE),
    ("A and B", slices["AB"], "#000000"),
], n)}
<h2>How long we wait for CI, and whether it is worth it</h2>
<p>The clock below is the wall-clock time of the required pull_request workflows on the first LGTM commit. Workflows run together, so the wait is the span from the earliest start to the latest finish, not the sum of the jobs. actions has no required checks, so it has no CI gate.</p>
{ci_table(wait)}
<p>On app the three required workflows overlap. Storybook is the long one, at a median of {minute_phrase(wait["app_storybook"])}. The main CI workflow is {minute_phrase(wait["app_ci"])}. Playwright is {minute_phrase(wait["app_playwright"])}. Together they take a median of {minute_phrase(wait["by_repo"]["app"]["p50"])}, and the 90th percentile is {minute_phrase(wait["by_repo"]["app"]["p90"])}.</p>
<p><strong>The CI wait is worth it as a gate on a red build. It is not worth treating as the bug catch.</strong> {not_mergeable} of {n} first LGTM commits were not green. Merging at the LGTM without that wait would merge those commits with a failing or missing required check. When the commit was already green, the median calendar time from LGTM to merge is {hour_phrase(wait["green_to_merge_p50"])}. When it was not green, that median is {hour_phrase(wait["red_to_merge_p50"])}. Those are calendar hours. They include nights, more commits, and the human approval. They are not extra hours of CI compute.</p>
<p>The human approval is the longer wait. Its median is {hour_phrase(p50_approval)}. App CI is about {minute_phrase(wait["by_repo"]["app"]["p50"])}. The comment record agrees that CI is not where the bugs in this study are found. {comment_counts["bucket_aci"]} comments are A-ci: the comment names a check that was already failing. {comment_counts["bucket_a"]} comments are bucket A: a real medium or high bug, security issue, or data-loss comment that CI at that commit would not have caught.</p>
<h2>How bugs were classified from comments</h2>
<p>A bug in this study is a label on a human comment. It is not a ticket from Linear or Sentry. The comment is a review comment, a review body, or an issue comment. The author of the pull request is excluded. The bot is excluded. Each comment is marked before or after the first bot LGTM.</p>
<p>The classifier read the comment, the diff hunk, and the replies. It assigned a category, a severity, whether the issue is real, and a one-line rationale. It was not told which side of the LGTM the comment sat on. A label is real only when the hunk or a reply shows a real issue. A medium or high bug, security issue, or data-loss label needs that support. A nit, a question, or a style note stays out of bucket A.</p>
<p>Bucket A keeps a comment only when all of these hold. It is after the LGTM. It is real. It is a bug, a security issue, or data loss. The severity is medium or high. The author acknowledged it, or a later commit changed that file. If the comment also names CI, a test, or lint, and a required check was already failing, the comment is A-ci instead.</p>
<p>Bucket B and bucket D do not come from this comment pass. They come from a later pull request whose title looks like a fix, then from git blame on the lines that fix changed.</p>
<p>Read this funnel from top to bottom. Each row is inside the row above it. The last row is the comments that became bucket A or A-ci.</p>
{funnel_html([
    ("Human comments on headline pull requests", "Review comments, review bodies, and issue comments", comment_counts["on_headline"]),
    ("After the first bot LGTM", "Comments before the LGTM stay out of A", comment_counts["after"]),
    ("Marked real", "The hunk or a reply shows a real issue", comment_counts["real_after"]),
    ("Medium or high bug, security, or data loss", "Nits and questions are out", comment_counts["mh_defect"]),
    ("Became A or A-ci", "Author ack or a later edit of that file", comment_counts["entered"]),
])}
<p>{comment_counts["bucket_a"]} of those last-row comments are bucket A. {comment_counts["bucket_aci"]} are A-ci. {comment_counts["nit_after"]} real comments after the LGTM are nits, and they do not enter A. The app labels and the other repositories' labels were separate passes with the same rubric. Hand labels in <code>labeling_sample.csv</code> are still empty, so a second reader has not checked the agreement.</p>
<h2 id="app">Why app is lower, and how to shift left</h2>
<p>App is {pct(app_n - app_miss, app_n)} bot-sufficient ({app_n - app_miss} of {app_n}). The other six repositories together are {pct(six_suff, six_n)} ({six_suff} of {six_n}). The 88% line in the month chart is all seven repositories together, and app is most of that count.</p>
<p>App pull requests are larger. The median app headline pull request is {int(app_only['lines'].median())} lines. The median in the other six is {int(other_only['lines'].median())} lines. Size buckets are XS under 50 lines, S under 200, M under 500, L under 1,000, and XL at 1,000 or more.</p>
<p>Give app the other repositories' size mix and its bot-sufficient share would be {pct(round(app_at_other_mix * 1000), 1000)}. Give the other repositories app's size mix and their share would be {pct(round(other_at_app_mix * 1000), 1000)}. Size mix is a large part of the gap. A gap remains inside the same size bucket, and it is widest on L and XL.</p>
<p>On app, XS is {pct(int(app_only.loc[app_only.size_bucket=='XS','bot_sufficient'].sum()), int((app_only.size_bucket=='XS').sum()))} and S is {pct(int(app_only.loc[app_only.size_bucket=='S','bot_sufficient'].sum()), int((app_only.size_bucket=='S').sum()))}. L is {pct(int(app_only.loc[app_only.size_bucket=='L','bot_sufficient'].sum()), int((app_only.size_bucket=='L').sum()))}. XL is {pct(int(app_only.loc[app_only.size_bucket=='XL','bot_sufficient'].sum()), int((app_only.size_bucket=='XL').sum()))}. L and XL are {len(large)} of {app_n} app headline pull requests and {large_miss} of {app_miss_n} app misses.</p>
<p>Bucket A on app is {int(app_only.in_A.sum())} pull requests. Bucket B is {int(app_only.in_B.sum())}. Both rise with size. On XL, A is {int(app_only.loc[app_only.size_bucket=='XL','in_A'].sum())} of {int((app_only.size_bucket=='XL').sum())} and B is {int(app_only.loc[app_only.size_bucket=='XL','in_B'].sum())} of {int((app_only.size_bucket=='XL').sum())}. B is a later fix of a line that was already in the LGTM commit. That count comes from the later fix.</p>
<p>The {a_finding_n} bucket A findings on app are mostly bugs ({a_bug_n}). The paths with the most are {html.escape(area_phrase)}. A-ci on app is {int(app_only.in_Aci.sum())} pull requests. Today's required checks are not the net that catches these.</p>
<p><strong>Shift left by splitting L and XL app changes, and by aiming tests and the bot at packages/app, packages/api, and packages/viz.</strong> App pull requests under 200 lines are already in the mid-90s, which is where the other repositories sit. A bot LGTM on a 1,000-line app diff is the case that later shows a bug or a fix. Catch that diff before the LGTM: smaller pull requests, a test for the behavior in those three packages, and a bot pass that withholds LGTM on a large diff until it has looked for a bug.</p>
<h2>Counts by repository</h2>
<p>Headline means a human author, merged, opened in the window, and at least one bot comment that contains the word LGTM. Opened-in-window is every pull request in that window, including ones with no LGTM.</p>
{repo_table(prs, head)}
<p>Per-repository pages, with their own Venn diagrams, are <code>out/report.html</code> for app and <code>out/&lt;repo&gt;/report.html</code> for the other six. Per-developer pages sit beside those files.</p>
<h2>Where A, B, and D overlap</h2>
<p>The funnel already counted bucket C. These circles are only the pull requests that carry A, B, D, or A-ci. A pull request can sit in more than one circle. C is everyone outside the circles: {regions["C"]} headline pull requests.</p>
<p class="swipe-hint">Swipe each chart sideways to read the labels.</p>
<h3>A and B decide bot-sufficient</h3>
<p>Bucket A is a real medium or high bug, security, or data-loss comment after the LGTM. The author acknowledged it, or a later commit changed that file, and CI at the counterfactual commit would not have caught it. Bucket B is a later fix whose blamed line was already in that commit, merged within 30 days. A pull request in A or B is not bot-sufficient.</p>
<div class="chart">{venn_ab(regions)}</div>
<h3>A, B, and D</h3>
<p>Bucket D is a later fix whose blamed line was absent at the counterfactual commit and present on the final head, merged within 30 days. D alone leaves the pull request bot-sufficient.</p>
<div class="chart">{venn_abd(regions)}</div>
<h3>A and A-ci</h3>
<p>A-ci is the same kind of comment as A, and the comment names CI, a test, or lint, while a required check was already failing. A-ci stays bot-sufficient.</p>
<div class="chart">{venn_aci(regions)}</div>
<p>Bucket C is the {regions["C"]} headline pull requests outside every circle. Bot-sufficient is C plus the pull requests that are D only or A-ci only. That adds {regions["sufficient"] - regions["C"]} pull requests, for {regions["sufficient"]} bot-sufficient in total.</p>
<h2>1. The month charts</h2>
<p class="swipe-hint">Swipe each chart sideways to read the axis.</p>
<p>These charts describe the same pull requests. They do not turn the month coefficient into a trend. Gray points have fewer than 10 pull requests. The shaded month is September.</p>
<div class="chart">{svgs["pooled"]}</div>
<div class="chart">{svgs["by_repo"]}</div>
<div class="chart">{svgs["buckets"]}</div>
<div class="chart">{svgs["cats"]}</div>
<p>Engagement sensitivity, still with repository, size, and tenure: {html.escape(engage)}. Restricting the controlled model to a body that is exactly <code>LGTM</code> leaves out {n - int(len(exact))} headline pull requests. {html.escape(exact_line)}.</p>
<h2>2. Time after the LGTM</h2>
<p class="swipe-hint">Swipe the chart sideways to read the axis.</p>
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
<li>Keep human approval on app. If you run a lighter review, pick one owned area in the other six repositories, require green checks on the LGTM commit, and revert quickly when production signals fail.</li>
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
<h3>Bucket C</h3>
<p>Bucket C has no defect example. A pull request is in C when it shows none of A, A-ci, B, or D. There are {slices["C"]} of them.</p>
</body></html>
"""
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "report.html").write_text(body)
    (OUT / "output.html").write_text(body)
    (OUT / "report.md").write_text(
        f"""# Conclusion: keep human review, and the months are flat

Bucket C is the ordinary case: none of A, A-ci, B, or D. C is {slices["C"]} of {n} headline pull requests. Bot-sufficient is C plus D-only and A-ci-only, {suff_n} of {n}. A or B is the other {n - suff_n}. The funnel in the HTML puts those rows in order.

Keep a human approval on app. {app_miss} of {app_n} headline pull requests there are in bucket A or B ({pct(app_miss, app_n)}).

Human review helps in bucket A: a real bug after the bot LGTM that CI would not have caught. {a_pr_n} headline pull requests are in A, and {a_app_n} of them are in app. On app the share is {pct(int(app_only.loc[app_only.size_bucket=='XL','in_A'].sum()), int((app_only.size_bucket=='XL').sum()))} for XL and {pct(int(app_only.loc[app_only.size_bucket=='XS','in_A'].sum()), int((app_only.size_bucket=='XS').sum()))} for XS. {top_area_n} of {a_finding_n} app findings are in {html.escape(area_phrase)}. Bucket B is a bug that still merged: {b_n} pull requests, {b_xl_n} of them XL app changes.

Treat a bot LGTM as a merge signal only after the required checks pass on that commit. {not_mergeable} of {len(known)} headline pull requests were not mergeable at the first LGTM. Among the {mergeable_n} that were already mergeable, {mergeable_miss} are still in A or B ({pct(mergeable_miss, mergeable_n)}).

A lighter review can be a pilot in one owned area of actions, mcap, foxglove-sdk, infra, infra-admin, or data-platform. Those six have {six_miss} of {six_n} in A or B ({pct(six_miss, six_n)}). Merge only after checks pass. Revert quickly if production signals fail.

From June through September the bot-sufficient share stays near 88%: {jun_phrase}. With repository, size, and tenure, {all_ctrl}.

Median time from LGTM to the first human approval is {hour_phrase(p50_approval)}. Median time from that approval to merge is {hour_phrase(p50_after)}.

App is {pct(app_n - app_miss, app_n)} bot-sufficient. The other six are {pct(six_suff, six_n)}. App's median headline pull request is {int(app_only['lines'].median())} lines. Theirs is {int(other_only['lines'].median())} lines. L and XL app pull requests are {large_miss} of {app_miss_n} app misses. Shift left by splitting those changes, and by aiming tests and the bot at {html.escape(area_phrase)}.

Required CI on the first LGTM commit takes a median of {minute_phrase(wait["by_repo"]["app"]["p50"])} on app. {not_mergeable} of {n} of those commits were not green. That wait is worth it as a gate on a red build. It does not catch bucket A. Bucket A is a label on a human comment: {comment_counts["bucket_a"]} comments passed the rubric, and {comment_counts["bucket_aci"]} named a check that was already failing.

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
