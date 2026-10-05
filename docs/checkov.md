# Checkov IaC scanning

Reusable GitHub Actions workflows that run [Checkov](https://www.checkov.io/) against Terraform and Helm. Default posture is **report-only** (`soft_fail: true`): findings are printed and uploaded as artifacts, but the job stays green.

Local OSS only — no Bridgecrew / Prisma API key, and `skip_results_upload` / `skip_download` are set so results stay in GitHub Actions.

## Workflows

| Workflow                                                              | Frameworks                                          | Typical callers                                     |
| --------------------------------------------------------------------- | --------------------------------------------------- | --------------------------------------------------- |
| [`checkov-helm.yml`](../.github/workflows/checkov-helm.yml)           | Helm                                                | Repos with charts under `deploy/` or `charts/`      |
| [`checkov-terraform.yml`](../.github/workflows/checkov-terraform.yml) | Terraform (static) and/or Terraform Cloud plan JSON | Repos with `.tf` and optional TFC speculative plans |

## Usage

### Helm

```yaml
jobs:
  checkov-helm:
    permissions:
      contents: read
      actions: read
      security-events: write
    uses: foxglove/actions/.github/workflows/checkov-helm.yml@main
    with:
      directory: deploy
      # upload_sarif: false   # default; needs GitHub Code Security on private repos
```

### Terraform

```yaml
jobs:
  checkov-terraform:
    permissions:
      contents: read
      actions: read
      checks: read
      security-events: write
    uses: foxglove/actions/.github/workflows/checkov-terraform.yml@main
    with:
      directory: .
      mode: both # static | plan | both
    secrets:
      TFE_TOKEN: ${{ secrets.TFE_TOKEN }} # optional until plan mode is wired
```

`mode`:

- `static` — scan `.tf` in `directory` (full inventory; no TFC required)
- `plan` — download speculative plan JSON from Terraform Cloud for the commit and scan it
- `both` — run static then plan (default)

## Config resolution

1. `config_file` workflow input, if the path exists
2. Consumer repo root `checkov.yml`, if it contains non-comment settings
3. Shared defaults from this repo: [`checkov/checkov.yml`](../checkov/checkov.yml)

Commit a commented stub `checkov.yml` in consumers so per-repo skips can be added later without inventing a new file.

## Terraform Cloud plan mode

PR speculative plans already run in Terraform Cloud via the GitHub App. Plan mode **reuses** that JSON; it does not run `terraform plan` in Actions.

Requirements:

1. Read-only TFC API token stored as Actions secret `TFE_TOKEN` (plan/run read; no apply)
2. TFC check runs on the commit (used to discover `run-…` IDs)
3. Patience: the workflow polls until plans are ready or `plan_timeout_seconds` elapses, then soft-skips

If `TFE_TOKEN` is missing or no plans appear, plan mode logs a skip in the step summary and exits successfully. Static mode (when enabled) still runs.

## Reporting

| Channel                               | Default                                                            |
| ------------------------------------- | ------------------------------------------------------------------ |
| Job logs                              | Yes                                                                |
| `$GITHUB_STEP_SUMMARY`                | Yes                                                                |
| Workflow artifacts (SARIF + JSON)     | Yes                                                                |
| GitHub Code Scanning (`upload_sarif`) | Off — enable after Code Security is turned on for the private repo |

## Noise tuning (later)

Full-open first: no skip lists. When ready to reduce noise, prefer consumer `checkov.yml`:

```yaml
skip-check:
  - CKV_AWS_144

skip-path:
  - .*/\.terraform/.*

soft-fail-on:
  - LOW

hard-fail-on:
  - CRITICAL

# baseline: .checkov.baseline
#   checkov -d . --create-baseline
```

Or pass `skip_path` / flip `soft_fail` on the workflow inputs when you move from report-only to enforcement.

## Pinning

Workflows pin `bridgecrewio/checkov-action@v12.1347.0` (Checkov image `3.3.23`). Bump deliberately in this repo when upgrading.
