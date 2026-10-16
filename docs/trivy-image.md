# Trivy image scanning

Reusable GitHub Actions workflow that runs [Trivy](https://trivy.dev/) `image` against container images already present on the job's Docker daemon. Default posture is **report-only** (`soft_fail: true`): vulnerability findings are printed and uploaded as artifacts and do not fail the job. A missing image, a failed `docker pull` of the pinned Trivy image, or a Trivy crash still fails the job.

Vulnerability scanning only (`--scanners vuln`). Trivy 0.76's default scanner list includes `secret`; this workflow does not use that scanner. No Aqua API key and telemetry is disabled.

## Workflow

| Workflow                                                    | What it scans                                      |
| ----------------------------------------------------------- | -------------------------------------------------- |
| [`trivy-image.yml`](../.github/workflows/trivy-image.yml)   | Local image tags passed in `images`                |

## Pinning `foxglove/actions`

`uses: foxglove/actions/.github/workflows/trivy-image.yml@<ref>` only pins the workflow YAML. Scripts and shared config are loaded from a second checkout. Pass the **same full commit SHA** as `actions_ref`:

```yaml
jobs:
  trivy:
    permissions:
      contents: read
      actions: read
      security-events: write
    # Keep uses: and actions_ref on the same ref. Dependabot updates uses: only.
    uses: foxglove/actions/.github/workflows/trivy-image.yml@<full-commit-sha>
    with:
      actions_ref: <full-commit-sha>
      images: api:latest
      soft_fail: true
      upload_sarif: false
```

Use the same ref for `uses` and `actions_ref`. After the workflow is on `main`, `@main` is fine for both. Update them in the same commit.

| Phase                 | `uses:` ref                         | `actions_ref`   |
| --------------------- | ----------------------------------- | --------------- |
| Stacked development  | Full commit SHA of the actions PR   | Same SHA        |
| After that PR merges | `@main`                             | `main`          |

Do not point `uses:` at a SHA that is not on the actions branch under test. GitHub will not find the workflow file.

## Images must be on this job

The job runs `docker image inspect` on every tag in `images` and fails if any tag is missing. It does not build images and it does not `docker pull` the tags under scan (`--image-src docker`, so Trivy will not fall through to a registry).

`needs:` does not share a Docker daemon between jobs, and a caller cannot add steps inside `uses:`. Pass `image_artifact` with the name of an Actions artifact whose file is a `docker save` tarball. One tar may contain multiple images. The scan job downloads that artifact and runs `docker load` before inspect. Leave `image_artifact` empty to scan tags that are already local on this runner.

After load, a tag that is still missing fails the job.

Caller sequence: build, `docker save`, `upload-artifact`, then call this workflow with `needs:` on the build job.

```yaml
jobs:
  build:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803 # v6.1.0
      - name: Build
        run: docker build -t api:latest .
      - name: Save image
        run: docker save -o api.tar api:latest
      - uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02 # v4.6.2
        with:
          name: api-image
          path: api.tar
          if-no-files-found: error

  trivy:
    needs: build
    permissions:
      contents: read
      actions: read
      security-events: write
    # Keep uses: and actions_ref on the same full commit SHA.
    uses: foxglove/actions/.github/workflows/trivy-image.yml@<full-commit-sha>
    with:
      actions_ref: <full-commit-sha>
      images: api:latest
      image_artifact: api-image
      soft_fail: true
      upload_sarif: false
```

The scan job runs on `ubuntu-24.04` unless the caller sets `runner`. Trivy reads image contents through the Docker API, so an image built for another architecture can be scanned once it is loaded. Large images (CUDA or a large virtualenv) need a runner with more disk: `docker load` of those tarballs fills the default runner.

Callers should path-filter on Dockerfiles (and this workflow file) so unrelated PRs skip the scan. This reusable workflow has no path filters of its own.

## Inputs

| Input              | Default                              | Purpose                                                                 |
| ------------------ | ------------------------------------ | ----------------------------------------------------------------------- |
| `images`           | required                             | Comma-separated image references to scan                                |
| `image_artifact`   | empty                                | Actions artifact name of a `docker save` tarball. Empty skips download  |
| `actions_ref`      | `main`                               | Second checkout of `foxglove/actions`                                   |
| `soft_fail`        | `true`                               | `true`: vulnerabilities exit 0. `false`: `--exit-code 1`               |
| `severity`         | `UNKNOWN,LOW,MEDIUM,HIGH,CRITICAL`   | Passed to `--severity`                                                  |
| `ignore_unfixed`   | `false`                              | `--ignore-unfixed`. Observe keeps unfixed findings                      |
| `config_file`      | empty                                | Consumer `trivy.yaml`. Missing path fails the job                       |
| `ignore_file`      | empty                                | `.trivyignore` path. Empty leaves Trivy's default lookup. Missing path fails |
| `upload_sarif`     | `false`                              | Upload SARIF to Code Scanning when Code Security is enabled             |
| `artifact_suffix`  | `default`                            | Artifact name `trivy-image-<suffix>`                                    |
| `timeout_minutes`  | `30`                                 | Job timeout. Each Trivy invocation has its own 15m cap                  |
| `runner`           | `ubuntu-24.04`                       | `runs-on` for the scan job. Large images (CUDA/venv) need more disk     |

Each image is scanned once to JSON. Table and SARIF are `trivy convert` from that file. `--exit-code` is on the table convert. Raise `timeout_minutes` when several images no longer fit.

Workflow outputs: `finding_count`, `critical_count`, `high_count`.

## Fail policy

| Condition                                      | Job result                                      |
| ---------------------------------------------- | ----------------------------------------------- |
| Vulnerabilities, `soft_fail: true`             | Success. Counts in the step summary and artifacts |
| Vulnerabilities, `soft_fail: false`            | Failure                                         |
| Image missing, Trivy crash, pinned image pull fails | Failure                                    |

`soft_fail` applies only to vulnerability findings on the table convert. A JSON or SARIF report that fails to write still fails the job. A missing image after `docker load` still fails the job.

## Config resolution

1. `config_file` workflow input. The job fails if the path does not exist.
2. Consumer repo root `trivy.yaml`, if it contains non-comment settings.
3. Shared defaults: [`trivy/trivy.yaml`](../trivy/trivy.yaml).

**Replace, do not merge.** When a consumer `trivy.yaml` has any non-comment key, Trivy is given **only** that file. Copy needed keys from the shared file when you start customizing.

`--scanners vuln`, `--severity`, `--ignore-unfixed`, and `--exit-code` are always passed from the workflow inputs and override the config file. `severity` and `ignore_unfixed` are those inputs. A consumer config cannot turn the secret scanner on through this workflow, and uncommenting `severity` or `ignore-unfixed` in `trivy.yaml` does nothing.

Stub template: [`trivy/trivy.stub.yaml`](../trivy/trivy.stub.yaml). Its examples are keys the workflow does not override (`db.repository`, `vulnerability.vex`). CVE suppressions go in `.trivyignore` (one id per line) or `ignore_file`, not in `trivy.yaml`.

## Reporting

| Channel                                | Default |
| -------------------------------------- | ------- |
| Job logs (Trivy table)                 | Yes     |
| `$GITHUB_STEP_SUMMARY`                 | Yes     |
| Workflow artifacts (SARIF + JSON)      | Yes     |
| GitHub Code Scanning (`upload_sarif`)  | Off     |

`upload_sarif` stays off until Code Scanning is enabled. Each image's SARIF gets its own `automationDetails.id` (`trivy-image-<artifact_suffix>/<image>/`). The upload step does not set `category`, because one category on every file is rejected when `images` has more than one entry.

## Pinning Trivy

The workflow runs `aquasec/trivy` pinned by digest (Trivy `0.76.0`) through the `TRIVY_IMAGE` env at the top of `trivy-image.yml`. The digest is the multi-arch **index**, so amd64 and arm64 runners pull their own build. To upgrade, resolve the new tag's manifest-list digest (`Docker-Content-Digest` on the index, not a single-platform manifest) and update that env. `aquasecurity/trivy-action` is not used; it pulls a moving tag.

## Caller permissions

```yaml
permissions:
  contents: read
  actions: read
  security-events: write
```

Put that block on the caller job. `security-events: write` is what the SARIF upload step needs; leave it on even while `upload_sarif` is false so turning upload on does not require a permissions edit.
