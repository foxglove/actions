# Foxglove GitHub Actions

Shared GitHub Actions workflows and prompts for the Foxglove organization.

## PR Review Workflows

### Technical Review (`review.yml`)

An AI-powered code review that acts as a technical reviewer (CTO persona). Focuses on correctness, architecture, performance, security, and code quality.

**Prompt:** [`prompts/review.md`](prompts/review.md)

### Product Review (`product-review.yml`)

An AI-powered product review that acts as a product manager. Focuses on user-facing consistency, terminology, documentation completeness, interaction patterns, and UX quality. Automatically skips PRs with no user-facing impact.

**Prompt:** [`prompts/product-review.md`](prompts/product-review.md)

## Usage

Add the workflows to your repository's `.github/workflows/` directory:

```yaml
# .github/workflows/review.yml
name: PR Review
on:
  pull_request:
    types: [opened, synchronize, reopened]
  pull_request_review_comment:
    types: [created]
  issue_comment:
    types: [created]

jobs:
  review:
    uses: foxglove/actions/.github/workflows/review.yml@main
    secrets:
      ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}

  product-review:
    uses: foxglove/actions/.github/workflows/product-review.yml@main
    secrets:
      ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```
