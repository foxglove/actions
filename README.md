# Foxglove GitHub Actions

Shared GitHub Actions workflows and prompts for the Foxglove organization.

## PR Review Workflow

### Review (`review.yml`)

An AI-powered PR review that combines technical and product perspectives in a single pass. Acts as both a technical leader and product steward — evaluating code quality, architecture, performance, and security alongside user-facing consistency, terminology, documentation, and UX. Review comments use ASD-STE100 Simplified Technical English. They do not use personality, humor, or rhetorical filler.

**Prompt:** [`prompts/review.md`](prompts/review.md)

**Job environment:** the reviewer runs with a shell and can execute commands to check its own claims rather than reasoning from the spec. Repos with a `.node-version` or `.nvmrc` get that Node version installed; repos with a `yarn.lock` get Corepack enabled. Both setup steps are best-effort and skip on repos that don't need them.

Dependencies are not installed. On Yarn repos the reviewer can install them itself when a finding turns on running the repo's own code. `node` and `yarn` are the only JS tooling in the allowlist, so npm and pnpm repos get the pinned runtime but no install path.

**Check and comment author:** callers name their job `review`, and this job id is `beefcake`, so the status check is `review / beefcake`. The check passes when the posted review body on that commit is `LGTM`. A review comment or thread reply whose text is `LGTM` counts the same way, and so does a conversation comment when the job can read it. A hidden `<!-- beefcake-review -->` marker on that text still counts as `LGTM`. An approving review still passes. GitHub keeps the `pull_request` run's check separate from a later run, so a passing LGTM verdict re-runs an earlier failed `pull_request` run of this workflow on the same commit. That re-run checks for the existing LGTM before it offers the review to local beefcake, accepts an LGTM from foxglove-beefcake or claude, and passes without posting another review. It mints an installation token with `actions: write` only for that refresh, including when local beefcake posted the review and the review-token mint did not run. When the App cannot mint that token, the re-run uses the job token. A review that only has `Nit (optional):` comments also passes, including when that nit thread is still unresolved. The check fails when the review has a `Blocker:` or `Should fix:` comment, or when an unresolved thread starts with one of those labels. A summary body of `Prior unresolved thread(s) still open.` does not fail on its own. The review is still posted. When the mint succeeds, inline comments are posted as `foxglove-beefcake[bot]`. The cloud path mints an installation token for that GitHub App and passes it as `github_token`, along with that bot's id and name. The action then does not exchange an OIDC token for `claude[bot]`. Callers pass `BEEFCAKE_APP_ID` (the numeric App id) and `BEEFCAKE_APP_PRIVATE_KEY` (the PEM private key). Both secrets are optional on the workflow call. When the mint fails because those secrets are missing, the private key is empty, or the mint API returns an error, the job continues into the Claude review attempts and leaves `github_token` empty, so the action posts as `claude[bot]`. Threads from `claude[bot]` stay in scope for reply, resolve, and minimize.

### Beefcake hand-off (optional)

A caller can set the `beefcake-dispatch-url` input and pass the `TAILSCALE_OAUTH_CLIENT_ID` and `TAILSCALE_OAUTH_SECRET` secrets to offer each review to beefcake, a local reviewer, first. When beefcake takes the review, the job prints its progress until it posts. The check name is still `review / beefcake`, and the App secrets above are not read. A posted review fails this job only for a `Blocker:` or `Should fix:`, including an unresolved thread with one of those labels. A nit does not fail this job. When beefcake declines, fails, or takes longer than 15 minutes, the job runs the cloud review.

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
      BEEFCAKE_APP_ID: ${{ secrets.BEEFCAKE_APP_ID }}
      BEEFCAKE_APP_PRIVATE_KEY: ${{ secrets.BEEFCAKE_APP_PRIVATE_KEY }}
```

Create `BEEFCAKE_APP_ID` and `BEEFCAKE_APP_PRIVATE_KEY` as organization Actions secrets, or as repository secrets on each caller. Do not commit the private key. A caller that does not pass them still runs the beefcake hand-off. The cloud path posts as `claude[bot]` until a mint succeeds.

> **Note:** If your repository restricts the default `GITHUB_TOKEN` permissions, you may also need to add a top-level `permissions` block to explicitly grant the required access at the workflow level.
>
> ```yaml
> permissions:
>   actions: read
>   contents: read
>   pull-requests: write
>   id-token: write
> ```
