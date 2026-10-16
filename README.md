# Foxglove GitHub Actions

Shared GitHub Actions workflows and prompts for the Foxglove organization.

## PR Review Workflow

### Review (`review.yml`)

An AI-powered PR review that combines technical and product perspectives in a single pass. Acts as both a technical leader and product steward — evaluating code quality, architecture, performance, and security alongside user-facing consistency, terminology, documentation, and UX. Review comments use ASD-STE100 Simplified Technical English. They do not use personality, humor, or rhetorical filler.

**Prompt:** [`prompts/review.md`](prompts/review.md)

**Job environment:** the reviewer runs with a shell and can execute commands to check its own claims rather than reasoning from the spec. Repos with a `.node-version` or `.nvmrc` get that Node version installed; repos with a `yarn.lock` get Corepack enabled. Both setup steps are best-effort and skip on repos that don't need them.

Dependencies are not installed. On Yarn repos the reviewer can install them itself when a finding turns on running the repo's own code. `node` and `yarn` are the only JS tooling in the allowlist, so npm and pnpm repos get the pinned runtime but no install path.

### Beefcake hand-off (optional)

A caller can set the `beefcake-dispatch-url` input and pass the `TAILSCALE_OAUTH_CLIENT_ID` and `TAILSCALE_OAUTH_SECRET` secrets to offer each review to beefcake, a local reviewer, first. When beefcake takes the review, the job prints its progress until it posts. When beefcake declines, fails, or takes longer than 15 minutes, the job runs the review as usual.

### Repository-specific review instructions

The shared prompt stays general-purpose. To add conventions or review policies specific to a repo (or a subtree within it), commit instruction files alongside the code — no workflow changes needed:

- **`AGENTS.md`** — general codebase conventions and agent guidance ([an emerging standard](https://agents.md/)). Used to judge idiomatic patterns.
- **`REVIEWING.md`** — review-specific policies and checklists (e.g. "require a linked desktop build for PRs that touch `packages/desktop`").

Each file applies to its own directory and all subdirectories; a file at the repo root applies repo-wide. When multiple files apply to a path, the more deeply nested one takes precedence. The workflow discovers these files automatically (tracked files only) and the reviewer applies them on top of the general guidance, so repo-specific rules don't have to live in this shared prompt.

## Usage

Add this workflow to your repository's `.github/workflows/` directory:

```yaml
# .github/workflows/pr-review.yml
name: PR Review

on:
  pull_request: {}

jobs:
  review:
    if: ${{ !github.event.pull_request.head.repo.fork }}
    permissions:
      actions: read
      contents: read
      pull-requests: write
      id-token: write
    uses: foxglove/actions/.github/workflows/review.yml@main
    secrets:
      ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

> **Note:** If your repository restricts the default `GITHUB_TOKEN` permissions, you may also need to add a top-level `permissions` block to explicitly grant the required access at the workflow level.
>
> ```yaml
> permissions:
>   actions: read
>   contents: read
>   pull-requests: write
>   id-token: write
> ```

## Checkov IaC scanning

Report-only Checkov scans for Terraform and Helm. Soft-fail by default; results go to job logs, the step summary, and workflow artifacts.

**Docs:** [`docs/checkov.md`](docs/checkov.md)

**Workflows:**

- [`checkov-helm.yml`](.github/workflows/checkov-helm.yml) — renders charts with env target values, then scans as kubernetes
- [`checkov-terraform.yml`](.github/workflows/checkov-terraform.yml) — prefer `mode: static`; plan mode has open security/privilege caveats (see docs)

Pass the same full SHA as `uses:` and `actions_ref` so scripts/config match the workflow revision.

**Shared config:** [`checkov/checkov.yml`](checkov/checkov.yml) · consumer stub: [`checkov/checkov.stub.yml`](checkov/checkov.stub.yml)

```yaml
jobs:
  checkov-helm:
    permissions:
      contents: read
      actions: read
      security-events: write
    # Keep uses: and actions_ref on the same ref.
    uses: foxglove/actions/.github/workflows/checkov-helm.yml@main
    with:
      actions_ref: main
      layout: sibling
      charts_root: charts

  checkov-terraform:
    permissions:
      contents: read
      actions: read
      security-events: write
    uses: foxglove/actions/.github/workflows/checkov-terraform.yml@main
    with:
      actions_ref: main
      directory: .
      mode: static
```

## Dependency scanning

Report-only Trivy scans of committed lockfiles. Soft-fail by default; results go to job logs, the step summary, and workflow artifacts. Findings do not fail the job. A scanner crash, a bad image digest, or a failed database download still does.

**Docs:** [`docs/dependency-scan.md`](docs/dependency-scan.md)

**Workflow:** [`dependency-scan.yml`](.github/workflows/dependency-scan.yml)

The workflow is self-contained. Callers pin `uses` to a full commit SHA and do not pass `actions_ref`. `aquasecurity/trivy-action` is not used. The image is `ghcr.io/aquasecurity/trivy` pinned by digest inside the workflow.

This repository's caller is [`dependencies.yml`](.github/workflows/dependencies.yml). `yarn.lock` contains only the devDependency `prettier`. Dev dependencies are excluded, so a package count of zero on that caller is expected and is not a failed Yarn Berry parse.

```yaml
jobs:
  dependency-scan:
    permissions:
      contents: read
      actions: read
      security-events: write
    # Full SHA of the commit on foxglove/actions main. Not @main.
    uses: foxglove/actions/.github/workflows/dependency-scan.yml@<full-commit-sha>
    with:
      lockfiles: yarn.lock,Cargo.lock
      soft_fail: true
```
