# PR-review study

Scripts for the Foxglove review study. They read `FOX_FINE_GRAINED_TOKEN` and do not print it. Cached pull requests, CI, org members, and classifier labels stay on disk under `data/` and are gitignored because this repository is public and several study repositories are private.

`STUDY_REPO` selects the repository. The default is `app`. Allowed names: `app`, `data-platform`, `infra`, `infra-admin`, `mcap`, `foxglove-sdk`, `actions`.

`app` keeps the pilot layout: `data/raw/app/`, `data/interim/`, `out/`. Each other repository writes `data/raw/<repo>/`, `data/interim/<repo>/`, and `out/<repo>/`.

## Clone used for blame and diffs

```bash
git clone --filter=blob:none https://github.com/foxglove/app.git /tmp/foxglove-app
```

Set `FOXGLOVE_APP_CLONE` if the app clone lives somewhere else. For any other repository, set `STUDY_CLONE` or use `/tmp/foxglove-<repo>`. Git must not use the actions-repo credentials. `common.git_env()` and `common.git_cred_helper()` point at three helper files. Override the paths with `STUDY_GIT_CONFIG`, `STUDY_GIT_ASKPASS`, and `STUDY_GIT_CRED`.

```bash
: > /tmp/empty-gitconfig
cat > /tmp/git-askpass.sh << 'EOF'
#!/bin/sh
case "$1" in
  *Username*) printf '%s\n' "x-access-token" ;;
  *) printf '%s\n' "$FOX_FINE_GRAINED_TOKEN" ;;
esac
EOF
cat > /tmp/git-cred.sh << 'EOF'
#!/bin/sh
echo "username=x-access-token"
echo "password=$FOX_FINE_GRAINED_TOKEN"
EOF
chmod 700 /tmp/git-askpass.sh /tmp/git-cred.sh
```

The helpers read `FOX_FINE_GRAINED_TOKEN` from the environment. They do not store it.

## Order

Run each step with `STUDY_REPO` set. Example: `STUDY_REPO=infra python3 scripts/fetch_prs.py`.

1. `python3 scripts/fetch_prs.py` — pull requests opened on or after 2026-04-01. For repositories other than `app`, this also writes `required_checks.json` from the active default-branch ruleset, or from classic branch protection when the ruleset lists no checks.
2. `python3 scripts/fetch_ci.py` — required checks at the first bot LGTM. Can run beside the pull-request fetch. `app` keeps its pre-registered job list, including the Storybook commit status. Other repositories match ruleset check names to Actions job names, then to commit statuses. A repository with no required checks is treated as mergeable at a known LGTM commit.
3. `python3 scripts/fetch_heads.py` — `refs/pull/N/head` into the local clone.
4. `python3 scripts/parse_prs.py` — `prs.jsonl` and `findings.jsonl` under that repository's interim directory.
5. Classify findings into `labels/batch_*.json` in that interim directory. Those batches omit the before/after timing field. Fields: `id`, `category`, `severity`, `is_real`, `rationale`.
6. `python3 scripts/link_changes.py` — later commits that touch the same path.
7. `python3 scripts/escapes.py` — fix-title blame links. `--workers` defaults to 4.
8. `python3 scripts/metrics.py` — tables and `summary.json`.
9. `python3 scripts/report_app.py` — `report.html` and `per-developer.html`.
10. `python3 scripts/report_pooled.py` — the seven-repository page at `out/pooled/report.html`. It reads the per-repository CSV files. It does not call GitHub. The primary model is `bot_sufficient ~ month + C(repo) + C(size) + C(tenure)`.

## Optional local files

These are not written by the scripts. The report and the recall estimate run without them.

`data/raw/app/meta/bot_history.json` lists config changes for the report appendix. Shape: `{"actions": [{"date": "2026-06-18", "repo": "foxglove/actions", "sha": "<commit>", "summary": "<one line>"}], "app_workflow": []}`. Build it from the `foxglove/actions` history. Do not commit it.

`data/raw/app/meta/linear_recall.json` is the Linear bug sample for escape recall. Shape: `{"tickets": [{"id": "FG-1", "title": "", "team": "", "created": "", "fix_prs": [123], "named_intro_prs": [456], "note": ""}]}`. `metrics.py` reports recall as unavailable when the file is absent.
