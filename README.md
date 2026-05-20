# Foxglove GitHub Actions

Shared GitHub Actions workflows and prompts for the Foxglove organization.

## PR Review Workflow

### Review (`review.yml`)

An AI-powered PR review that combines technical and product perspectives in a single pass. Acts as a CTO who is both a technical leader and product steward — evaluating code quality, architecture, performance, and security alongside user-facing consistency, terminology, documentation, and UX.

**Prompt:** [`prompts/review.md`](prompts/review.md)

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

## Testing Prompt Changes

Pull requests in private Foxglove downstream repositories can temporarily test review prompt changes without changing their workflow file. Add a repo-local prompt file:

> `.github/foxglove-review.md`

When present, `review.yml` uses that file as the Claude review prompt for the pull request. If the file is absent, the workflow uses [`prompts/review.md`](prompts/review.md) from this repository.

Before merging the downstream pull request, move the accepted prompt changes back to this repository and remove the repo-local prompt file unless that repository intentionally needs a permanent override.

Repo-local prompts are restricted to downstream private repositories owned by `foxglove`. They only replace the prompt text; workflow code, helper scripts, action versions, and token handling continue to come from `foxglove/actions`.
