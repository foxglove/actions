# Checkov IaC scanning

Reusable GitHub Actions workflows that run [Checkov](https://www.checkov.io/) against Terraform and Helm. Default posture is **report-only** (`soft_fail: true`): findings are printed and uploaded as artifacts and do not fail the job. A chart that does not render still fails the Helm job.

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
    # Keep uses: and actions_ref on the same ref. Dependabot updates uses: only.
    uses: foxglove/actions/.github/workflows/checkov-helm.yml@<full-commit-sha>
    with:
      actions_ref: <full-commit-sha>
      layout: shared
      chart_dirs: deploy/api,deploy/billing
      targets_dir: deploy/targets
```

Use the same ref for `uses` and `actions_ref`. After merge, `@main` is fine for both.

`checkov-terraform` requests only `contents: read`, `actions: read`, and `security-events: write` while plan mode is parked. Do not grant `checks` or `statuses` until plan mode is re-enabled (it will need `statuses: read`).

## Helm layouts

| `layout`  | Inputs                           | Used by                                                                  |
| --------- | -------------------------------- | ------------------------------------------------------------------------ |
| `sibling` | `charts_root` (default `charts`) | `infra` — each `charts/<name>/chart` + `charts/<name>/targets/**/*.yaml` |
| `shared`  | `chart_dirs`, `targets_dir`      | `app`, `data-platform` — each chart × each file in `targets_dir`         |

Rendered manifests land in `checkov-rendered/` and are scanned with `framework: kubernetes`.

`helm_set` is an optional comma-separated list of `key=value` pairs passed as `helm --set` on every render. Use it for values that deploy workflows inject with `--set` and that `required` rejects or that render invalid YAML when empty (for example `siteController.imageHash=checkov-placeholder`). Give full image placeholders a tag (`checkov-placeholder:checkov`) so `CKV_K8S_14` does not report a blank tag.

Target selection:

| Input                  | Effect                                                                                                                                                                                                                             |
| ---------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `exclude_targets`      | Comma-separated globs matched against target basenames. Use for overlay files that only render on top of another target.                                                                                                           |
| `max_targets_per_dir`  | Render the first N targets (sorted) in each target directory. `0` (default) renders all. Trades coverage of per-target values for runtime.                                                                                         |
| `target_group_pattern` | Bash regex matched against target basenames. With `max_targets_per_dir`, the cap applies per directory per matched substring, so `aws\|gcp\|azure` keeps the first N targets for each cloud. Non-matching targets share one group. |
| `helm_namespaces`      | Comma-separated `chart=namespace` pairs. The chart key is the directory basename. Unlisted charts use the basename, which is the namespace infra passes as `--namespace "$APP"`.                                                   |

The step summary lists every skipped target and the input that skipped it.

`exclude_targets` and `max_targets_per_dir` skip targets on purpose. A missing chart directory, a failed `helm template`, or a run that renders nothing fails the job. `soft_fail` applies only to Checkov findings: with `soft_fail: true` (default) findings are reported and the Checkov step stays green.

### Known Helm gaps

`charts/arc` in `infra` only templates a service account. Runner pods come from the upstream `gha-runner-scale-set` chart, with values generated in the deploy workflow. This scan does not cover those pods. Acceptable for the first pass.

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

1. `config_file` workflow input. The job fails if the path does not exist.
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

Workflows pin `bridgecrewio/checkov-action@7b1bd992e2c40a3404e3511944aeb8d014703d9a` (Checkov image `3.3.23`). The `v12.*` tags on that repo are from 2022 and must not be used. Bump the commit SHA deliberately when upgrading.
