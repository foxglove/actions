# Gitleaks secret scanning

Reusable workflow that runs the MIT [Gitleaks](https://github.com/gitleaks/gitleaks) CLI against git history. Default posture is **report-only** (`soft_fail: true`): findings are written to the job summary and uploaded as an artifact, and exit code 2 does not fail the job.

The workflow shells out to the CLI. It does not use `gitleaks/gitleaks-action` and it does not read `GITLEAKS_LICENSE`.

The check run is `gitleaks / gitleaks` (caller job id `gitleaks`, called job `gitleaks`). It is not a required check.

## Workflow

| Workflow | What it scans |
| --- | --- |
| [`gitleaks.yml`](../.github/workflows/gitleaks.yml) | Git history of the caller repository |

`workflow_call` only. One job, `gitleaks`, on `ubuntu-24.04` with `timeout-minutes: 45`. The hosted runner is x64. The pinned asset is `linux_x64`; do not move the job to the arm64 ARC runners or to `ubuntu-latest`.

Permissions on this workflow and on every caller: `contents: read`. No `security-events` (no SARIF upload), no `pull-requests` (the job does not edit the PR), no `actions: read`. Version and digest live in the workflow file, so there is no `actions_ref` input and no second checkout.

## Pinning Gitleaks

| | |
| --- | --- |
| Version | `8.30.1` |
| Asset | `gitleaks_8.30.1_linux_x64.tar.gz` |
| sha256 | `551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb` |

The install step downloads that asset, checks it with `sha256sum -c` against the digest above, extracts the `gitleaks` binary, and runs `gitleaks version`. The digest is the trust anchor. The checksums file published next to the asset is not: a replaced release can ship a matching pair.

A failed download, a checksum mismatch, a tarball without the binary, or a version string other than `8.30.1` fails the job before a scan starts.

## Inputs

| Input | Type | Default | Behavior |
| --- | --- | --- | --- |
| `soft_fail` | boolean | `true` | Exit code 2 (leaks found) leaves the job green. Callers pass `true` explicitly. |
| `inventory` | boolean | `false` | Full history. Honored on `pull_request` only. Any other event with `inventory: true` fails the job. |
| `config_file` | string | `""` | Passed as `--config` when set. On `pull_request`, read from the base commit, and empty uses the base `.gitleaks.toml` or the built-in rules. A path that is not a blob on the base commit fails the job. On other events, empty uses Gitleaks' own lookup, and a missing file fails the job. |

`soft_fail` applies only to exit 2. Exit 1 still fails the job.

On `pull_request`, `.gitleaks.toml`, `.gitleaksignore`, and `config_file` are read from the base commit. The PR head is checked out for the scan range, and Gitleaks would otherwise load those files from that tree. A pull request could add a secret and an allowlist or an ignore entry in the same diff, and the summary would show no findings. `config_file`, when set, is the config. If it is empty and the base commit has no `.gitleaks.toml`, the built-in rules are used. The head's copies are not loaded. `GITLEAKS_CONFIG` and `GITLEAKS_CONFIG_TOML` are unset for that run.

The same runs pass `--ignore-gitleaks-allow`. A `gitleaks:allow` comment in the scanned diff cannot hide a finding. `push` and `workflow_dispatch` keep the default, which honors that comment.

The job fails on `pull_request` when the loaded base config has `[extend]` with `path`. Gitleaks resolves that path against the working tree, which is the PR head, so the pull request can change the extended file. `useDefault = true` does not use a path. No caller has a config today.

On `push` and `workflow_dispatch`, the checked-out commit is the one that was pushed or dispatched, and those files are read from that tree.

First callers omit `config_file`. None of the caller repos has a `.gitleaks.toml` today, so those runs use the built-in rules. This workflow does not add a config file, a `.gitleaksignore`, or a `baseline-path` input.

## Caller

No path filters. A secret can land in any file, so callers run on every pull request and on the same push branches Checkov already listens to.

| Repo | `push` branches | Also |
| --- | --- | --- |
| `app` | `main` | `pull_request`, `workflow_dispatch` |
| `data-platform` | `main` | `pull_request`, `workflow_dispatch` |
| `infra` | `main`, `release/*` | `pull_request`, `workflow_dispatch` |
| `infra-admin` | `main`, `release/*` | `pull_request`, `workflow_dispatch` |

`@main` is intentional. Consumers follow `foxglove/actions` without a pin bump.

```yaml
name: Gitleaks

on:
  push:
    branches: [main] # infra and infra-admin also list release/*
  pull_request:
  workflow_dispatch:

concurrency:
  group: ${{ github.workflow }}-${{ github.event.pull_request.number || github.run_id }}
  cancel-in-progress: true

permissions:
  contents: read

jobs:
  # @main is intentional. Consumers follow foxglove/actions without a pin bump.
  gitleaks:
    uses: foxglove/actions/.github/workflows/gitleaks.yml@main
    with:
      soft_fail: true
      inventory: false
```

Pull request runs share a group, so a new commit cancels the previous scan of that PR. Push and `workflow_dispatch` use `github.run_id`, so each run has its own group and always completes. A push scan is only `before..sha`. `cancel-in-progress: false` on a shared ref group still skips a queued push. Other PRs are separate groups. Concurrency stays on the caller.

## Checkout and scan range

Checkout uses `actions/checkout` `v6.1.0` (`d23441a48e516b6c34aea4fa41551a30e30af803`) with `fetch-depth: 0` and `lfs: false`. A depth-1 checkout only has the tip, so `base..head` cannot see the commits in between. LFS stays off because Gitleaks reads git blobs.

On `pull_request`, the workflow checks out `github.event.pull_request.head.sha`. For that event `github.sha` is the synthetic merge commit, which is the wrong end of the range. The job fails if `HEAD` is not that SHA.

The command is `gitleaks git` (`detect` is hidden in 8.30.1). An empty `--log-opts` runs `git log -p -U0 --full-history --all`, which is the inventory scan. Every other run passes `--log-opts`, or a full clone would scan every ref on every pull request.

| Event | `--log-opts` | What is scanned |
| --- | --- | --- |
| `pull_request`, `inventory: false` | `base.sha..head.sha` | Commits reachable from the PR head and not from the base tip |
| `push`, and `before` is a real parent | `before..sha` | Commits in that push |
| `push`, and `before` is all zeros | `-n 1` | The tip commit. The all-zero parent is not a fetchable object |
| `workflow_dispatch` | `-n 1` | The tip of the ref that was dispatched |
| `pull_request` with `inventory: true` | omitted | `git log --full-history --all` on the full clone |

`--log-opts` is one argument. The CLI splits that value on spaces. The range is one token (`abc..def`). `-n 1` is two tokens.

Both ends of a range must already be in the clone. The job fails before the scan if either SHA is missing. Gitleaks 8.30.1 itself exits 0 and writes `[]` when `git log` fails, so a missing parent would otherwise look like a clean scan.

## Redaction and reporting

The scan always passes `--redact` with no percent. In 8.30.1 the default when the flag is present is 100, which replaces the secret in `Secret` and `Match` with the literal `REDACTED` before the report is written. The workflow does not pass `--verbose` and does not change the log level. Verbose output prints the secret.

```text
gitleaks git .
  --redact
  --no-banner
  --exit-code 2
  --report-format json
  --report-path gitleaks-report.json
  --log-opts=<range>    # omitted when inventory is true
```

The job summary is built from that JSON with `jq`:

- the checked-out commit
- total findings
- count by rule id
- up to 40 rows of rule id, file, commit, and start line

No match text in the summary, even redacted. When there are more than 40 findings, the summary says how many were omitted.

The artifact name is `gitleaks`. `if-no-files-found: error`. A missing report after exit 0 or 2 fails the job. A successful scan writes the file (an empty result is `[]`).

When `inventory` is true, the same markdown is written to `gitleaks-inventory.md` and included in the artifact. Copy that file into the caller PR body. Leave match text out.

## Exit codes

`findingSummaryAndExit` in 8.30.1 exits 1 on a scan error it returns, including a partial scan, before it looks at findings. Leaks use `--exit-code 2` (the CLI default is 1). `logging.Fatal` (report write failure, bad flag) is also exit 1.

| Result | Exit | Job |
| --- | --- | --- |
| No leaks | 0 | green |
| Leaks found, `soft_fail: true` | 2 | green |
| Leaks found, `soft_fail: false` | 2 | red |
| Scan error or partial scan | 1 | red |
| `git log` cannot resolve the range, or the scan log contains a git fatal error | 1 | red |
| Download, checksum, or install failure | step fails | red |
| `inventory: true` on anything other than `pull_request` | config error | red |
| Missing report after exit 0 or 2 | 1 | red |

## One-time history inventory

One inventory per caller, on the pull request that adds the caller. It does not block the merge: with `soft_fail: true` the job stays green when findings exist. The merged diff has `inventory: false`.

`workflow_dispatch` cannot run a new workflow file until that file is on the default branch, so the first inventory has to be a `pull_request` run.

1. Merge this workflow to `main` first. Callers use `@main`.
2. On the caller PR, set `inventory: true` and push.
3. Wait for `gitleaks / gitleaks` to finish. Concurrency cancels an in-progress run, so do not push the follow-up commit while the inventory is still running.
4. Copy the step summary into the PR body under `## Gitleaks history inventory`. Include the commit SHA, the finding count, the count by rule, and the capped row list. Leave match text out.
5. Set `inventory: false` and push.
6. The reviewer checks that section and the `false` before merge.

A later `push` with `inventory: true` fails the job, so a forgotten `true` does not turn every pull request into a full-history scan. That failure is still not a required check.

Order for the callers: `infra-admin`, then `infra`, then `data-platform`, then `app`. Leave `soft_fail: true`.
