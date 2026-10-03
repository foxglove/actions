# App PR-review pilot

Scripts for the `foxglove/app` pilot. They read `FOX_FINE_GRAINED_TOKEN` and do not print it. Cached pull requests, CI, org members, and classifier labels stay on disk under `data/` and are gitignored because this repository is public and `foxglove/app` is private.

## Clone used for blame and diffs

```bash
git clone --filter=blob:none https://github.com/foxglove/app.git /tmp/foxglove-app
```

Set `FOXGLOVE_APP_CLONE` if the clone lives somewhere else. The fetch scripts expect `/tmp/empty-gitconfig`, `/tmp/git-askpass.sh`, and `/tmp/git-cred.sh` so Git does not use the actions-repo credentials. `git_env()` in `common.py` points at those paths.

## Order

1. `python3 scripts/fetch_prs.py` — pull requests opened on or after 2026-04-01.
2. `python3 scripts/fetch_ci.py` — required checks at the first bot LGTM. Can run beside the pull-request fetch.
3. `python3 scripts/fetch_heads.py` — `refs/pull/N/head` into the local clone.
4. `python3 scripts/parse_prs.py` — `data/interim/prs.jsonl` and `findings.jsonl`.
5. Classify findings into `data/interim/labels/batch_*.json`. Those batches omit the before/after timing field.
6. `python3 scripts/link_changes.py` — later commits that touch the same path.
7. `python3 scripts/escapes.py` — fix-title blame links.
8. `python3 scripts/metrics.py` — tables and `out/summary.json`.
9. `python3 scripts/report_app.py` — `out/report.html` and `out/per-developer.html`.
