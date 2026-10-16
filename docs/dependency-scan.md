# Dependency scanning

Reusable GitHub Actions workflow that runs [Trivy](https://trivy.dev/) against committed lockfiles. Default posture is **report-only** (`soft_fail: true`): findings are printed and uploaded as artifacts and do not fail the job. A Trivy crash, an image digest that does not resolve, or a failed vulnerability database download still fails the job.

This is not a required check. `upload_sarif` stays off until GitHub Code Security is enabled for the repository.

The workflow is self-contained. It does not check out `foxglove/actions` a second time, and callers do not pass `actions_ref`.

## Workflow

| Workflow | What it scans |
| --- | --- |
| [`dependency-scan.yml`](../.github/workflows/dependency-scan.yml) | Each lockfile path passed in `lockfiles` |

Secret scanning, misconfiguration, and license scanning are off (`--scanners vuln` only). Misconfiguration stays on the Checkov workflows. `--pkg-types library` keeps the job on language lockfiles and off OS packages of the runner.

## Pinning `foxglove/actions`

`uses` is the only pin. There is no `actions_ref`.

```yaml
jobs:
  dependency-scan:
    permissions:
      contents: read
      actions: read
      security-events: write
    uses: foxglove/actions/.github/workflows/dependency-scan.yml@<full-commit-sha>
    with:
      lockfiles: yarn.lock,Cargo.lock
      soft_fail: true
```

Pin `uses` to the full 40-character commit SHA. Dependabot's `github-actions` updates will not move a bare SHA.

In this repository the reusable workflow already occupies `dependency-scan.yml`, so the local caller is [`dependencies.yml`](../.github/workflows/dependencies.yml) and uses `uses: ./.github/workflows/dependency-scan.yml`. Other repositories name their caller `dependency-scan.yml`.

## Inputs

| Input | Default | Role |
| --- | --- | --- |
| `lockfiles` | required | Comma-separated file paths. Each path is scanned on its own. |
| `soft_fail` | `true` | Findings stay green (`--exit-code 0`). `false` uses `--exit-code 1`. |
| `upload_sarif` | `false` | Upload SARIF to GitHub Code Scanning. Requires Code Security on private repos. |

Callers pass explicit files. A directory path fails the job, so testdata lockfiles, Nix flakes, and Terraform provider locks are not swept in. A path that escapes the repository (`..` or an absolute path) fails the job. Two lockfiles that share a basename fail the job, because the report file is named from the basename.

`soft_fail` does not hide a scanner failure. Missing report files fail the job.

## Caller triggers

| Event | What it covers |
| --- | --- |
| `pull_request` | Path-filtered to the lockfiles that caller scans and the caller workflow file |
| `push` to `main` | Same path filter |
| `schedule` | Weekly, on `main`. New advisories against an unchanged lockfile. Path filters do not apply |
| `workflow_dispatch` | Manual run |

`infra` also pushes `release/*`, matching its Checkov caller. Other callers do not.

Scheduled workflows run from the default branch only. This repository's caller uses Monday 09:17 UTC (`17 9 * * 1`).

Concurrency matches Checkov: `${{ github.workflow }}-${{ github.event.pull_request.number || github.ref }}`, cancel in progress.

Permissions on the caller and on the reusable workflow: `contents: read`, `actions: read`, `security-events: write`. The last one is unused while `upload_sarif` is false.

## This repository's lockfile

`yarn.lock` is Yarn Berry (`__metadata` version 8). Its only registry package is the devDependency `prettier`. `--include-dev-deps` is not passed, so a package count of zero on this caller is expected. That zero is not a failed Berry parse.

## Reporting

| Channel | Default |
| --- | --- |
| Job logs | Yes |
| `$GITHUB_STEP_SUMMARY` | Package count, finding count, ecosystem, counts by severity |
| Workflow artifacts (SARIF + JSON) | Yes. Name is `dependency-scan-<repo>-<run id>` |
| GitHub Code Scanning (`upload_sarif`) | Off. Each SARIF run has its own `automationDetails.id` (`dependency-scan/<basename>/`), so one upload can include every lockfile. |

The step summary reads the JSON. `--list-all-pkgs` defaults to true, so the package count is every package Trivy parsed, not only vulnerable ones. Dev dependencies are excluded. The summary says so.

Trivy 0.76 accepts one `--format` per invocation. The JSON run downloads the vulnerability database into a job-local cache. The SARIF run passes `--skip-db-update` and uses that cache. There is no cross-job cache. A registry or database outage fails the job.

No `.trivyignore` and no `trivy.yaml` ship with the workflow. A file a caller commits is still loaded by Trivy's defaults. Every severity is reported. There is no `--severity` filter.

## Pinning Trivy

The workflow runs `ghcr.io/aquasecurity/trivy` pinned by digest (Trivy `0.76.0`) through the `TRIVY_IMAGE` env at the top of `dependency-scan.yml`. The digest is the manifest list for tag `0.76.0`. To upgrade, resolve the new tag to its digest and update that env. `aquasecurity/trivy-action` is not used; it pulls a moving tag.

An image scan is a separate workflow and reuses this digest. This workflow does not scan images.

Usage telemetry to Aqua is disabled (`--disable-telemetry`).

On this pin, `--include-dev-deps` is not passed. Yarn and npm dev dependencies are excluded. The release's Python docs say `uv` dev dependencies are excluded unless that flag is set. Rust dev dependencies in `Cargo.lock` are still reported. The flag's help text lists npm, yarn, and gradle.

This pin reads `yarn.lock` (Berry and classic), `package-lock.json`, `Cargo.lock`, and `uv.lock`.
