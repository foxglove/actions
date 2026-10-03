"""Join PR, finding, CI, and escape tables into the study outputs.

Primary outcome, fixed before looking at results:
  bot_sufficient ~ month_index
and the same model with size-bucket and tenure-bucket controls.
Repo is constant in this pilot, so it is not a covariate.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import pandas as pd

from common import (
    MONTHS,
    SIZE_ORDER,
    hours_between,
    month_index,
    parse_ts,
    percentile,
    wilson_interval,
)

ROOT = Path(__file__).resolve().parents[1]
INTERIM = ROOT / "data" / "interim"
OUT = ROOT / "out"
DEFECTS = {"BUG", "SECURITY", "DATA_LOSS_OR_CORRUPTION"}
WEIGHT = {"high": 3, "medium": 2, "low": 1}


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def ci_index() -> dict[int, dict]:
    out = {}
    eval_dir = ROOT / "data" / "raw" / "app" / "ci" / "eval"
    for path in eval_dir.glob("*.json"):
        data = json.loads(path.read_text())
        shas = data.get("shas") or []
        chosen = None
        mergeable = False
        first_eval = None
        for ev in data.get("evals") or []:
            if first_eval is None:
                first_eval = ev
            if ev.get("passed"):
                chosen = ev.get("sha")
                mergeable = bool(shas) and ev.get("sha") == shas[0]
                break
        if chosen is None and shas:
            chosen = shas[0]
        out[int(data["number"])] = {
            "counterfactual_sha": chosen,
            "mergeable_at_lgtm": mergeable if chosen else False,
            "lgtm_sha_failed_checks": (first_eval or {}).get("failed") or [],
            "lgtm_sha_missing_checks": (first_eval or {}).get("missing") or [],
            "lgtm_sha_passed": bool(first_eval and first_eval.get("passed")),
            "ci_known": True,
        }
    return out


def load_labels() -> dict[str, dict]:
    """Merge classifier batch files, then any hand-edits in labels.jsonl."""
    labels: dict[str, dict] = {}
    label_dir = INTERIM / "labels"
    if label_dir.exists():
        for path in sorted(label_dir.glob("batch_*.json")):
            try:
                rows = json.loads(path.read_text())
            except json.JSONDecodeError:
                continue
            for row in rows:
                fid = row.get("finding_id") or row.get("id")
                if not fid:
                    continue
                labels[fid] = {
                    "finding_id": fid,
                    "category": row.get("category"),
                    "severity": row.get("severity"),
                    "is_real": row.get("is_real"),
                    "rationale": row.get("rationale"),
                }
    path = INTERIM / "labels.jsonl"
    if path.exists():
        for row in read_jsonl(path):
            labels[row["finding_id"]] = row
    if labels:
        with path.open("w") as fh:
            for row in labels.values():
                fh.write(json.dumps(row, separators=(",", ":")) + "\n")
    return labels


def recall_estimate(links: list[dict]) -> dict:
    """How many Linear bug tickets' fix PRs the escape heuristic also selected.

    This is candidate-filter recall, not a full trace to the introducing commit.
    Tickets that name an introducer are checked separately. Sentry is not connected.
    """
    path = ROOT / "data" / "raw" / "app" / "meta" / "linear_recall.json"
    if not path.exists():
        return {"available": False, "reason": "no linear sample"}
    sample = json.loads(path.read_text())
    found_fixes = {int(link["fix_pr"]) for link in links}
    rows = []
    app_fixes = 0
    found = 0
    named = 0
    named_hit = 0
    for ticket in sample.get("tickets") or []:
        fixes = [int(n) for n in ticket.get("fix_prs") or []]
        named_intros = [int(n) for n in ticket.get("named_intro_prs") or []]
        hit_fixes = [n for n in fixes if n in found_fixes]
        if fixes:
            app_fixes += 1
            if hit_fixes:
                found += 1
        intro_hit = []
        if named_intros:
            named += 1
            for intro in named_intros:
                if any(int(link.get("intro_pr") or 0) == intro and int(link.get("fix_pr") or 0) in fixes for link in links):
                    intro_hit.append(intro)
            if intro_hit:
                named_hit += 1
        rows.append(
            {
                "id": ticket.get("id"),
                "fix_prs": fixes,
                "heuristic_found_fix": hit_fixes,
                "named_intro_prs": named_intros,
                "named_intro_found": intro_hit,
            }
        )
    return {
        "available": True,
        "sentry_mcp": False,
        "tickets": len(sample.get("tickets") or []),
        "tickets_with_app_fix_pr": app_fixes,
        "fix_prs_selected_by_heuristic": found,
        "candidate_recall": (found / app_fixes) if app_fixes else None,
        "named_introducer_tickets": named,
        "named_introducer_hits": named_hit,
        "note": sample.get("note"),
        "rows": rows,
    }


def finding_is_a(f: dict) -> bool:
    if f.get("timing") != "after":
        return False
    if not f.get("is_real"):
        return False
    if f.get("category") not in DEFECTS:
        return False
    if f.get("severity") not in ("medium", "high"):
        return False
    return bool(f.get("code_change") or f.get("author_acknowledged"))


def aci_for_finding(f: dict, ci: dict | None) -> bool:
    """A-ci only when a required check failed and the finding points at that failure.

    Check-run logs are not available with this token, so a failed required check
    is not enough on its own. The comment has to name CI, a test, or lint.
    """
    if not ci or ci.get("lgtm_sha_passed"):
        return False
    failed = ci.get("lgtm_sha_failed_checks") or []
    if not failed:
        return False
    text = f"{f.get('body') or ''}\n{f.get('path') or ''}".lower()
    if any(token in text for token in ("ci", "test", "lint", "typecheck", "tsc", "failing check")):
        return True
    return False


def escape_flags(links: list[dict]) -> dict[int, dict]:
    """Per introducer PR: B and D from line presence, within 30 days, medium/high confidence."""
    flags: dict[int, dict] = {}
    for link in links:
        if not link.get("intro_in_cohort") or not link.get("intro_bot_lgtm") or not link.get("intro_merged"):
            continue
        if link.get("confidence") == "low":
            bucket = "low_confidence"
        else:
            pres = link.get("presence") or []
            at_cf = [p.get("at_counterfactual") for p in pres]
            # Exact line text that occurs once is usable. A duplicated line is
            # an ambiguous file-text match under squash merges, so it stays
            # out of headline B/D.
            present_cf = any(v == "unique" for v in at_cf)
            added_later = any(
                p.get("at_counterfactual") == "absent" and p.get("at_head") == "unique" for p in pres
            )
            dup_only = any(v == "duplicate" for v in at_cf) or any(
                p.get("at_counterfactual") == "absent" and p.get("at_head") == "duplicate" for p in pres
            )
            if present_cf and link.get("within_30_days"):
                bucket = "B"
            elif added_later and link.get("within_30_days"):
                bucket = "D"
            elif link.get("within_30_days") is False and (present_cf or added_later):
                bucket = "after_30"
            elif dup_only:
                bucket = "low_confidence"
            else:
                bucket = "ambiguous"
        rec = flags.setdefault(
            int(link["intro_pr"]),
            {"B": False, "D": False, "low_confidence": False, "after_30": False, "examples": []},
        )
        if bucket == "B":
            rec["B"] = True
        elif bucket == "D":
            rec["D"] = True
        elif bucket == "low_confidence":
            rec["low_confidence"] = True
        elif bucket == "after_30":
            rec["after_30"] = True
        if len(rec["examples"]) < 3:
            rec["examples"].append(
                {
                    "fix_pr": link.get("fix_pr"),
                    "fix_url": link.get("fix_url"),
                    "fix_title": link.get("fix_title"),
                    "confidence": link.get("confidence"),
                    "bucket": bucket,
                    "within_30_days": link.get("within_30_days"),
                }
            )
    return flags


def series_stats(values: list[float]) -> dict:
    return {
        "n": len(values),
        "p50": percentile(values, 0.50),
        "p75": percentile(values, 0.75),
        "p90": percentile(values, 0.90),
    }


def rate_row(k: int, n: int) -> dict:
    lo, hi = wilson_interval(k, n)
    return {"k": k, "n": n, "rate": (k / n) if n else None, "lo": lo, "hi": hi}


def fit_logit(df: pd.DataFrame, formula: str) -> dict:
    import statsmodels.formula.api as smf

    try:
        model = smf.logit(formula, data=df).fit(disp=False)
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:400], "formula": formula}
    params = model.params
    conf = model.conf_int()
    if "month_index" not in params:
        return {"ok": False, "error": "month_index dropped", "formula": formula}
    lo, hi = conf.loc["month_index"].tolist()
    return {
        "ok": True,
        "formula": formula,
        "n": int(model.nobs),
        "month_coef": float(params["month_index"]),
        "month_ci": [float(lo), float(hi)],
        "month_pvalue": float(model.pvalues["month_index"]),
        "pseudo_r2": float(model.prsquared),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    prs = read_jsonl(INTERIM / "prs.jsonl")
    findings = read_jsonl(INTERIM / "findings.jsonl")
    labels = load_labels()
    links = read_jsonl(INTERIM / "escapes.jsonl") if (INTERIM / "escapes.jsonl").exists() else []
    ci = ci_index()
    esc = escape_flags(links)

    labeled = 0
    for f in findings:
        lab = labels.get(f["finding_id"])
        if not lab:
            f["category"] = None
            f["severity"] = None
            f["is_real"] = None
            f["rationale"] = None
            continue
        labeled += 1
        f["category"] = lab.get("category")
        f["severity"] = lab.get("severity")
        f["is_real"] = bool(lab.get("is_real"))
        f["rationale"] = lab.get("rationale")
    print(f"findings {len(findings)} labeled {labeled}", flush=True)

    by_pr_findings: dict[int, list] = defaultdict(list)
    for f in findings:
        by_pr_findings[int(f["pr"])].append(f)

    pr_rows = []
    for pr in prs:
        number = int(pr["number"])
        info = ci.get(number, {})
        pr.update(info)
        pr["ci_known"] = bool(info.get("ci_known"))
        flags = esc.get(number, {})
        fs = by_pr_findings.get(number, [])
        a_findings = []
        aci_findings = []
        for f in fs:
            if not finding_is_a(f):
                continue
            if aci_for_finding(f, info):
                f["bucket_a_ci"] = True
                aci_findings.append(f)
            else:
                f["bucket_a"] = True
                a_findings.append(f)
        in_a = bool(a_findings)
        in_aci = bool(aci_findings)
        in_b = bool(flags.get("B"))
        in_d = bool(flags.get("D"))
        bot_sufficient = bool(pr.get("merged") and pr.get("bot_lgtm") and pr.get("in_cohort") and not in_a and not in_b)
        after = [f for f in fs if f.get("timing") == "after" and f.get("is_real")]
        weight = sum(WEIGHT.get(f.get("severity"), 0) for f in after)
        weight_high = sum(1 for f in after if f.get("severity") == "high")
        # Engagement control: comments after LGTM except NIT/STYLE. Questions stay in.
        substantive_after = [
            f
            for f in fs
            if f.get("timing") == "after" and f.get("category") not in (None, "NIT/STYLE")
        ]
        pr["in_A"] = in_a
        pr["in_Aci"] = in_aci
        pr["in_B"] = in_b
        pr["in_D"] = in_d
        pr["in_C"] = bool(
            pr.get("merged") and pr.get("bot_lgtm") and pr.get("in_cohort") and not in_a and not in_aci and not in_b and not in_d
        )
        pr["bot_sufficient"] = bot_sufficient
        pr["severity_weight_after"] = weight
        pr["high_findings_after"] = weight_high
        pr["substantive_comments_after"] = len(substantive_after)
        pr["human_comments_after"] = sum(1 for f in fs if f.get("timing") == "after")
        pr["a_finding_ids"] = [f["finding_id"] for f in a_findings]
        pr["aci_finding_ids"] = [f["finding_id"] for f in aci_findings]
        pr["escape_examples"] = flags.get("examples") or []
        pr_rows.append(pr)

    # Flat PR csv
    flat_keys = [
        "number", "url", "title", "author", "author_type", "current_org_member", "tenure_bucket",
        "author_tenure_days", "created_at", "merged_at", "closed_at", "month", "in_cohort", "lines",
        "size_bucket", "additions", "deletions", "merged", "merged_by", "bot_reviewed", "bot_lgtm",
        "first_lgtm_at", "first_lgtm_sha", "first_lgtm_exact", "bot_reviews_before_lgtm",
        "bot_rereview_after_lgtm", "human_review_before_lgtm", "first_human_approval_at",
        "first_human_approver", "human_approval_count", "review_dismissals", "open_to_lgtm_h",
        "open_to_approval_h", "lgtm_to_approval_h", "lgtm_to_merge_h", "approval_to_merge_h",
        "approval_before_lgtm", "mergeable_at_lgtm", "counterfactual_sha", "ci_known", "in_A", "in_Aci", "in_B",
        "in_D", "in_C", "bot_sufficient", "substantive_comments_after", "closed_by",
    ]
    pd.DataFrame([{k: pr.get(k) for k in flat_keys} for pr in pr_rows]).to_csv(OUT / "prs.csv", index=False)

    finding_keys = [
        "finding_id", "pr", "pr_url", "pr_author", "month", "in_cohort", "source", "timing", "at",
        "login", "path", "body", "category", "severity", "is_real", "rationale",         "author_acknowledged",
        "code_change", "code_change_confidence", "diff_hunk", "bucket_a", "bucket_a_ci",
    ]
    pd.DataFrame([{k: f.get(k) for k in finding_keys} for f in findings]).to_csv(OUT / "findings.csv", index=False)
    if links:
        pd.DataFrame(links).drop(columns=["presence"], errors="ignore").to_csv(OUT / "escapes.csv", index=False)
    else:
        pd.DataFrame().to_csv(OUT / "escapes.csv", index=False)

    cohort = [p for p in pr_rows if p.get("in_cohort")]
    human_cohort = [p for p in cohort if p.get("author_type") == "human"]
    headline = [
        p
        for p in human_cohort
        if p.get("merged") and p.get("bot_lgtm")
    ]

    def monthly_block(rows: list[dict]) -> list[dict]:
        out_rows = []
        for month in MONTHS:
            group = [p for p in rows if p.get("month") == month]
            lgtm = [p for p in group if p.get("bot_lgtm")]
            merged_lgtm = [p for p in lgtm if p.get("merged")]
            human = [p for p in group if p.get("author_type") == "human"]
            human_merged_lgtm = [p for p in merged_lgtm if p.get("author_type") == "human"]
            suff = [p for p in human_merged_lgtm if p.get("bot_sufficient")]
            def count(flag):
                return sum(1 for p in human_merged_lgtm if p.get(flag))
            b_rate = rate_row(count("in_B"), len(human_merged_lgtm))
            out_rows.append(
                {
                    "month": month,
                    "partial_followup": month == "2026-09",
                    "prs": len(group),
                    "human_prs": len(human),
                    "bot_lgtm": len(lgtm),
                    "bot_coverage": rate_row(len(lgtm), len(group)),
                    "merged_lgtm_human": len(human_merged_lgtm),
                    "bot_sufficient": rate_row(len(suff), len(human_merged_lgtm)),
                    "bot_sufficient_all_pr": rate_row(len(suff), len(human)),
                    "A": rate_row(count("in_A"), len(human_merged_lgtm)),
                    "Aci": rate_row(count("in_Aci"), len(human_merged_lgtm)),
                    "B": b_rate,
                    "D": rate_row(count("in_D"), len(human_merged_lgtm)),
                    "not_mergeable_at_lgtm": sum(1 for p in human_merged_lgtm if p.get("ci_known") and not p.get("mergeable_at_lgtm")),
                    "ci_known": sum(1 for p in human_merged_lgtm if p.get("ci_known")),
                    "human_before_lgtm": sum(1 for p in lgtm if p.get("human_review_before_lgtm")),
                    "no_human_approval": sum(
                        1
                        for p in human_merged_lgtm
                        if p.get("human_approval_count", 0) == 0 and not p.get("review_dismissals")
                    ),
                    "lgtm_to_approval": series_stats(
                        [p["lgtm_to_approval_h"] for p in human_merged_lgtm if p.get("lgtm_to_approval_h") is not None]
                    ),
                    "lgtm_to_merge": series_stats(
                        [p["lgtm_to_merge_h"] for p in human_merged_lgtm if p.get("lgtm_to_merge_h") is not None]
                    ),
                    "approval_to_merge": series_stats(
                        [p["approval_to_merge_h"] for p in human_merged_lgtm if p.get("approval_to_merge_h") is not None]
                    ),
                    "substantive_comments_after_mean": (
                        sum(p.get("substantive_comments_after") or 0 for p in human_merged_lgtm) / len(human_merged_lgtm)
                        if human_merged_lgtm
                        else None
                    ),
                    "severity_weight_mean": (
                        sum(p.get("severity_weight_after") or 0 for p in human_merged_lgtm) / len(human_merged_lgtm)
                        if human_merged_lgtm
                        else None
                    ),
                    "high_only_mean": (
                        sum(p.get("high_findings_after") or 0 for p in human_merged_lgtm) / len(human_merged_lgtm)
                        if human_merged_lgtm
                        else None
                    ),
                }
            )
        return out_rows

    monthly = monthly_block(cohort)
    # approval comparison
    comp_rows = []
    for month in [None, *MONTHS]:
        pool = headline if month is None else [p for p in headline if p.get("month") == month]
        for name, pred in (
            ("no_human_approval", lambda p: p.get("human_approval_count", 0) == 0 and not p.get("review_dismissals")),
            ("human_approval", lambda p: p.get("human_approval_count", 0) > 0),
        ):
            group = [p for p in pool if pred(p)]
            comp_rows.append(
                {
                    "month": month or "all",
                    "group": name,
                    "n": len(group),
                    "escapes_B": sum(1 for p in group if p.get("in_B")),
                    **{k: v for k, v in rate_row(sum(1 for p in group if p.get("in_B")), len(group)).items()},
                }
            )
    pd.DataFrame(comp_rows).to_csv(OUT / "approval_comparison.csv", index=False)

    # monthly csv flattened
    flat_monthly = []
    for row in monthly:
        flat = {"month": row["month"], "partial_followup": row["partial_followup"], "prs": row["prs"]}
        for key in ("bot_coverage", "bot_sufficient", "bot_sufficient_all_pr", "A", "Aci", "B", "D"):
            block = row[key]
            flat[f"{key}_k"] = block["k"]
            flat[f"{key}_n"] = block["n"]
            flat[f"{key}_rate"] = block["rate"]
            flat[f"{key}_lo"] = block["lo"]
            flat[f"{key}_hi"] = block["hi"]
        for key in ("lgtm_to_approval", "lgtm_to_merge", "approval_to_merge"):
            for stat in ("n", "p50", "p75", "p90"):
                flat[f"{key}_{stat}"] = row[key][stat]
        flat["substantive_comments_after_mean"] = row["substantive_comments_after_mean"]
        flat["severity_weight_mean"] = row["severity_weight_mean"]
        flat["high_only_mean"] = row["high_only_mean"]
        flat["no_human_approval"] = row["no_human_approval"]
        flat["not_mergeable_at_lgtm"] = row["not_mergeable_at_lgtm"]
        flat["human_before_lgtm"] = row["human_before_lgtm"]
        flat_monthly.append(flat)
    pd.DataFrame(flat_monthly).to_csv(OUT / "monthly.csv", index=False)

    # regression on human merged LGTM PRs
    reg_df = pd.DataFrame(
        [
            {
                "bot_sufficient": int(bool(p.get("bot_sufficient"))),
                "month_index": month_index(p["month"]),
                "size_bucket": p.get("size_bucket") or "S",
                "tenure_bucket": p.get("tenure_bucket") or "unknown",
                "substantive_comments_after": p.get("substantive_comments_after") or 0,
                "month": p.get("month"),
            }
            for p in headline
            if p.get("month") in MONTHS
        ]
    )
    regressions = {}
    if len(reg_df) >= 30 and reg_df["bot_sufficient"].nunique() > 1:
        regressions["uncontrolled"] = fit_logit(reg_df, "bot_sufficient ~ month_index")
        regressions["controlled"] = fit_logit(
            reg_df,
            "bot_sufficient ~ month_index + C(size_bucket, Treatment(reference='S')) + C(tenure_bucket, Treatment(reference='2y+'))",
        )
        regressions["engagement"] = fit_logit(
            reg_df,
            "bot_sufficient ~ month_index + C(size_bucket, Treatment(reference='S')) + C(tenure_bucket, Treatment(reference='2y+')) + substantive_comments_after",
        )
    else:
        regressions["uncontrolled"] = {"ok": False, "error": f"n={len(reg_df)}"}

    # category mix after LGTM by month
    cat_rows = []
    for month in MONTHS:
        counts = defaultdict(int)
        for f in findings:
            if f.get("month") != month or f.get("timing") != "after" or not f.get("in_cohort"):
                continue
            if not f.get("is_real"):
                continue
            counts[f.get("category") or "UNLABELED"] += 1
        cat_rows.append({"month": month, **counts, "total": sum(counts.values())})

    # zero-comment approvals after LGTM
    zero_comment_approvals = 0
    approvals_after = 0
    request_to_approval = []
    for p in headline:
        lgtm_at = parse_ts(p.get("first_lgtm_at"))
        for appr in p.get("human_approvals") or []:
            at = parse_ts(appr.get("at"))
            if lgtm_at and at and at >= lgtm_at:
                approvals_after += 1
                body_empty = not (appr.get("body") or "").strip()
                inline = any(
                    f.get("login") == appr.get("login") and f.get("timing") == "after"
                    for f in by_pr_findings.get(int(p["number"]), [])
                )
                if body_empty and not inline:
                    zero_comment_approvals += 1
        reqs = [parse_ts(t) for t in (p.get("review_request_ats") or []) if parse_ts(t)]
        appr_at = parse_ts(p.get("first_human_approval_at"))
        if reqs and appr_at:
            anchor = max([t for t in reqs if t <= appr_at], default=reqs[0])
            if lgtm_at:
                anchor = max(anchor, lgtm_at) if anchor < appr_at else anchor
            delta = hours_between(anchor, appr_at)
            if delta is not None and delta >= 0:
                request_to_approval.append(delta)

    # per developer
    people = set()
    for p in cohort:
        people.add(p.get("author"))
        for rev in p.get("human_reviews") or []:
            people.add(rev.get("login"))
        for f in by_pr_findings.get(int(p["number"]), []):
            people.add(f.get("login"))
    people.discard(None)

    dev_rows = []
    periods = [*MONTHS, "all"]
    for person in sorted(people):
        for period in periods:
            authored = [
                p
                for p in cohort
                if p.get("author") == person and (period == "all" or p.get("month") == period)
            ]
            reviews = []
            for p in cohort:
                if period != "all" and p.get("month") != period:
                    continue
                for rev in p.get("human_reviews") or []:
                    if rev.get("login") == person:
                        reviews.append((p, rev))
            if not authored and not reviews:
                continue
            merged_lgtm = [p for p in authored if p.get("merged") and p.get("bot_lgtm")]
            suff = [p for p in merged_lgtm if p.get("bot_sufficient")]
            findings_received = []
            for p in authored:
                for f in by_pr_findings.get(int(p["number"]), []):
                    if f.get("timing") == "after":
                        findings_received.append(f)
            raised = []
            for p in cohort:
                if period != "all" and p.get("month") != period:
                    continue
                for f in by_pr_findings.get(int(p["number"]), []):
                    if f.get("login") == person and f.get("timing") == "after":
                        raised.append(f)
            cat_recv = defaultdict(int)
            sev_recv = defaultdict(int)
            for f in findings_received:
                cat_recv[f.get("category") or "UNLABELED"] += 1
                sev_recv[f.get("severity") or "UNLABELED"] += 1
            cat_raised = defaultdict(int)
            sev_raised = defaultdict(int)
            for f in raised:
                cat_raised[f.get("category") or "UNLABELED"] += 1
                sev_raised[f.get("severity") or "UNLABELED"] += 1
            sizes = defaultdict(int)
            repos = {"app": len(authored)}
            for p in authored:
                sizes[p.get("size_bucket")] += 1
            member = None
            if authored:
                member = authored[0].get("current_org_member")
            else:
                member = next((p.get("current_org_member") for p, _rev in reviews if p.get("author") == person), None)
            # current member flag from any authored pr, else unknown; membership is of the person not the author role
            if member is None:
                member = any(p.get("author") == person and p.get("current_org_member") for p in cohort)
                if not any(p.get("author") == person for p in cohort):
                    member = None
            hm_raised = [
                f
                for f in raised
                if f.get("is_real")
                and f.get("severity") in ("high", "medium")
                and f.get("category") in DEFECTS
            ]
            response_hours = []
            first_by_pr: dict[int, datetime] = {}
            for p, rev in reviews:
                at = parse_ts(rev.get("at"))
                if not at:
                    continue
                num = int(p["number"])
                if num not in first_by_pr or at < first_by_pr[num]:
                    first_by_pr[num] = at
            pr_by_num = {int(p["number"]): p for p, _rev in reviews}
            for num, at in first_by_pr.items():
                p = pr_by_num[num]
                lgtm_at = parse_ts(p.get("first_lgtm_at"))
                reqs = [parse_ts(t) for t in (p.get("review_request_ats") or []) if parse_ts(t) and parse_ts(t) <= at]
                anchors = [t for t in (reqs[-1:] if reqs else []) ]
                if lgtm_at and lgtm_at <= at:
                    anchors.append(lgtm_at)
                if not anchors:
                    continue
                delta = hours_between(max(anchors), at)
                if delta is not None and delta >= 0:
                    response_hours.append(delta)
            approved_escape = 0
            for p, rev in reviews:
                if rev.get("state") == "APPROVED" and p.get("in_B"):
                    approved_escape += 1
            zero_after = 0
            for p, rev in reviews:
                if rev.get("state") != "APPROVED":
                    continue
                lgtm_at = parse_ts(p.get("first_lgtm_at"))
                at = parse_ts(rev.get("at"))
                if not (lgtm_at and at and at >= lgtm_at):
                    continue
                inline = any(f.get("login") == person for f in by_pr_findings.get(int(p["number"]), []) if f.get("timing") == "after")
                if rev.get("body_empty") and not inline:
                    zero_after += 1
            dev_rows.append(
                {
                    "person": person,
                    "month": period,
                    "current_org_member": member if authored else next(
                        (True for p in cohort if p.get("author") == person and p.get("current_org_member")),
                        member,
                    ),
                    "authored_prs": len(authored),
                    "low_sample_author": len(authored) < 10,
                    "size_mix": dict(sizes),
                    "repo": "app",
                    "bot_sufficient_k": len(suff),
                    "bot_sufficient_n": len(merged_lgtm),
                    "bot_sufficient_rate": (len(suff) / len(merged_lgtm)) if merged_lgtm else None,
                    "A": sum(1 for p in merged_lgtm if p.get("in_A")),
                    "B": sum(1 for p in merged_lgtm if p.get("in_B")),
                    "D": sum(1 for p in merged_lgtm if p.get("in_D")),
                    "findings_received_after": len(findings_received),
                    "findings_received_per_pr": (len(findings_received) / len(authored)) if authored else None,
                    "received_by_category": dict(cat_recv),
                    "received_by_severity": dict(sev_recv),
                    "lgtm_to_approval_p50": percentile(
                        [p["lgtm_to_approval_h"] for p in merged_lgtm if p.get("lgtm_to_approval_h") is not None], 0.5
                    ),
                    "lgtm_to_merge_p50": percentile(
                        [p["lgtm_to_merge_h"] for p in merged_lgtm if p.get("lgtm_to_merge_h") is not None], 0.5
                    ),
                    "lgtm_to_approval_p75": percentile(
                        [p["lgtm_to_approval_h"] for p in merged_lgtm if p.get("lgtm_to_approval_h") is not None], 0.75
                    ),
                    "lgtm_to_merge_p75": percentile(
                        [p["lgtm_to_merge_h"] for p in merged_lgtm if p.get("lgtm_to_merge_h") is not None], 0.75
                    ),
                    "lgtm_to_approval_p90": percentile(
                        [p["lgtm_to_approval_h"] for p in merged_lgtm if p.get("lgtm_to_approval_h") is not None], 0.9
                    ),
                    "lgtm_to_merge_p90": percentile(
                        [p["lgtm_to_merge_h"] for p in merged_lgtm if p.get("lgtm_to_merge_h") is not None], 0.9
                    ),
                    "hm_catch_per_review": (len(hm_raised) / len(reviews)) if reviews else None,
                    "response_hours_p50": percentile(response_hours, 0.5),
                    "reviews": len(reviews),
                    "low_sample_reviewer": len(reviews) < 10,
                    "findings_raised_after": len(raised),
                    "findings_raised_per_review": (len(raised) / len(reviews)) if reviews else None,
                    "raised_code_change_share": (
                        sum(1 for f in raised if f.get("code_change")) / len(raised) if raised else None
                    ),
                    "raised_by_category": dict(cat_raised),
                    "raised_by_severity": dict(sev_raised),
                    "zero_comment_approvals_after_lgtm": zero_after,
                    "escapes_in_approved_prs": approved_escape,
                }
            )
    pd.DataFrame(dev_rows).to_csv(OUT / "per_developer.csv", index=False)

    # size-split time
    size_time = []
    for bucket in SIZE_ORDER:
        group = [p for p in headline if p.get("size_bucket") == bucket and p.get("lgtm_to_merge_h") is not None]
        size_time.append({"size_bucket": bucket, **series_stats([p["lgtm_to_merge_h"] for p in group])})

    summary = {
        "cohort_prs": len(cohort),
        "human_cohort": len(human_cohort),
        "bot_cohort": sum(1 for p in cohort if p.get("author_type") == "bot"),
        "current_member_authors": len({p["author"] for p in human_cohort if p.get("current_org_member")}),
        "other_human_authors": len({p["author"] for p in human_cohort if not p.get("current_org_member")}),
        "headline_n": len(headline),
        "monthly": monthly,
        "regressions": regressions,
        "categories_after_lgtm": cat_rows,
        "zero_comment_approval_share": rate_row(zero_comment_approvals, approvals_after),
        "request_to_approval": series_stats(request_to_approval),
        "size_time": size_time,
        "not_mergeable": sum(1 for p in headline if p.get("ci_known") and not p.get("mergeable_at_lgtm")),
        "ci_known_headline": sum(1 for p in headline if p.get("ci_known")),
        "human_before_lgtm": sum(1 for p in cohort if p.get("bot_lgtm") and p.get("human_review_before_lgtm")),
        "lgtm_prs": sum(1 for p in cohort if p.get("bot_lgtm")),
        "labeled_findings": labeled,
        "findings": len(findings),
        "escape_links": len(links),
        "recall": recall_estimate(links),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(json.dumps({k: summary[k] for k in ("cohort_prs", "headline_n", "labeled_findings", "findings")}, indent=2))


if __name__ == "__main__":
    main()
