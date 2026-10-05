# Checkov IaC scanning

Reusable GitHub Actions workflows that run [Checkov](https://www.checkov.io/) against Terraform and Helm. Default posture is **report-only** (`soft_fail: true`): findings are printed and uploaded as artifacts, but the job stays green.

Local OSS only — no Bridgecrew / Prisma API key, and `skip_results_upload` / `skip_download` are set so results stay in GitHub Actions.

## Workflows

| Workflow                                                              | What it scans                                                       |
| --------------------------------------------------------------------- | ------------------------------------------------------------------- |
| [`checkov-helm.yml`](../.github/workflows/checkov-helm.yml)           | Renders charts with env target values, then scans as **kubernetes** |
| [`checkov-terraform.yml`](../.github/workflows/checkov-terraform.yml) | Static Terraform HCL; optional TFC plan mode (see caveats below)    |

## Pinning `foxglove/actions`

`uses: foxglove/actions/.github/workflows/….yml@<ref>` only pins the workflow YAML. Scripts and shared config are loaded from a second checkout. Pass the **same full commit SHA** as `actions_ref`:

```yaml
jobs:
  checkov-helm:
    uses: foxglove/actions/.github/workflows/checkov-helm.yml@e7cb50b44827f5d73eccbbc59b2b3a1c8a9632dc
    with:
      actions_ref: e7cb50b44827f5d73eccbbc59b2b3a1c8a9632dc
      layout: shared
      chart_dirs: deploy/api,deploy/billing
      targets_dir: deploy/targets
```

After this repo’s Checkov PR merges, callers can use `@main` for both `uses` and `actions_ref`.

## Helm layouts

| `layout`  | Inputs                           | Used by                                                                  |
| --------- | -------------------------------- | ------------------------------------------------------------------------ |
| `sibling` | `charts_root` (default `charts`) | `infra` — each `charts/<name>/chart` + `charts/<name>/targets/**/*.yaml` |
| `shared`  | `chart_dirs`, `targets_dir`      | `app`, `data-platform` — each chart × each file in `targets_dir`         |

Rendered manifests land in `checkov-rendered/` and are scanned with `framework: kubernetes`.

## Terraform modes

| `mode`             | Behavior                                             |
| ------------------ | ---------------------------------------------------- |
| `static` (default) | Scan `.tf` under `directory`. No TFC credentials.    |
| `plan`             | Download speculative plan JSON from TFC and scan it. |
| `both`             | Static then plan.                                    |

**Recommended for now: `static` only.** Plan mode is implemented but not wired in consumers until the security model below is accepted.

### Plan mode spike findings

Verified against Foxglove’s TFC + GitHub integration:

1. **TFC reports via commit statuses**, not check runs (`Terraform Cloud/foxglove/<workspace>`). Discovery must use the Statuses API; check-runs alone will never find plans.
2. **`GET /runs/:id/plan/json-output` requires workspace admin** (user or team token). Organization tokens cannot call it ([HashiCorp docs](https://developer.hashicorp.com/terraform/cloud-docs/api-docs/plans)).
3. **Unredacted plan JSON can contain Terraform `sensitive` values in plaintext.** Uploading those files as Actions artifacts would expose them to anyone with repo read access.
4. There is an undocumented/redacted plan endpoint (`json-output-redacted`) that may work with lower privileges, but it is not a full security boundary and needs a dedicated follow-up before we enable plan mode in CI.

Until that follow-up: do not set `TFE_TOKEN` on consumers; keep `mode: static`. Raw plan JSON is never uploaded as a workflow artifact even if plan mode is used.

## Config resolution

1. `config_file` workflow input, if the path exists
2. Consumer repo root `checkov.yml`, if it contains non-comment settings
3. Shared defaults: [`checkov/checkov.yml`](../checkov/checkov.yml)

**Replace, do not merge.** When a consumer `checkov.yml` has any non-comment key, Checkov uses **only** that file. Shared defaults are ignored. Copy needed keys from the shared file when you start customizing.

Stub template: [`checkov/checkov.stub.yml`](../checkov/checkov.stub.yml).

## Reporting

| Channel                                   | Default   |
| ----------------------------------------- | --------- |
| Job logs                                  | Yes       |
| `$GITHUB_STEP_SUMMARY`                    | Yes       |
| Workflow artifacts (Checkov SARIF + JSON) | Yes       |
| Raw TFC plan JSON artifacts               | **Never** |
| GitHub Code Scanning (`upload_sarif`)     | Off       |

## Noise tuning (later)

```yaml
skip-check:
  - CKV_AWS_144

skip-path:
  - .*/\.terraform/.*

soft-fail-on:
  - LOW

hard-fail-on:
  - CRITICAL
```

## Pinning Checkov

Workflows pin `bridgecrewio/checkov-action@v12.1347.0` (Checkov image `3.3.23`). Bump deliberately in this repo when upgrading.
