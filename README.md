# Foxglove GitHub Actions

Shared GitHub Actions workflows and prompts for the Foxglove organization.

## PR Review Workflow

### Review (`review.yml`)

An AI-powered PR review that combines technical and product perspectives in a single pass. Acts as a CTO who is both a technical leader and product steward — evaluating code quality, architecture, performance, and security alongside user-facing consistency, terminology, documentation, and UX.

**Prompt:** [`prompts/review.md`](prompts/review.md)

### Repository-specific review instructions

The shared prompt stays general-purpose. To add conventions or review policies specific to a repo (or a subtree within it), commit instruction files alongside the code — no workflow changes needed:

- **`AGENTS.md`** — general codebase conventions and agent guidance ([an emerging standard](https://agents.md/)). Used to judge idiomatic patterns.
- **`REVIEWING.md`** — review-specific policies and checklists (e.g. "require a linked desktop build for PRs that touch `packages/desktop`").

Each file applies to its own directory and all subdirectories; a file at the repo root applies repo-wide. When multiple files apply to a path, the more deeply nested one takes precedence. The reviewer discovers these files automatically and applies them on top of the general guidance, so repo-specific rules don't have to live in this shared prompt.

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
