# Foxglove GitHub Actions

Shared GitHub Actions workflows and prompts for the Foxglove organization.

## PR Review Workflow

### Review (`review.yml`)

An AI-powered PR review that combines technical and product perspectives in a single pass. Acts as both a technical leader and product steward — evaluating code quality, architecture, performance, and security alongside user-facing consistency, terminology, documentation, and UX. Review comments use ASD-STE100 Simplified Technical English. They do not use personality, humor, or rhetorical filler.

**Prompt:** [`prompts/review.md`](prompts/review.md)

### Review jury

Three AI reviewers ("jurors") review each PR independently with the same prompt:

| Juror | Model             | Harness                                                                                           | Secret              |
| ----- | ----------------- | ------------------------------------------------------------------------------------------------- | ------------------- |
| Opus  | `claude-opus-5-5` | Claude Code ([`anthropics/claude-code-action`](https://github.com/anthropics/claude-code-action)) | `ANTHROPIC_API_KEY` |
| Astra | `gpt-6-astra`     | Codex ([`openai/codex-action`](https://github.com/openai/codex-action))                           | `OPENAI_API_KEY`    |
| Grok  | `grok-4.7`        | [Grok Build](https://x.ai/cli)                                                                    | `XAI_API_KEY`       |

Each juror returns a JSON verdict that matches [`prompts/review-verdict.schema.json`](prompts/review-verdict.schema.json): its new comments, its replies on other authors' threads, the earlier jury threads it considers fixed, and its LGTM vote. A final job ([`.github/scripts/review-jury.js`](.github/scripts/review-jury.js)) merges the verdicts and publishes one review as `github-actions[bot]`:

- **Comments come from every juror, without duplicates.** Comments that describe the same issue become one comment that names every juror that raised it. A comment that an open review thread already covers is dropped. An Opus call groups the duplicates; if that call fails, only comments with identical text are merged.
- **LGTM needs a majority.** The review body starts with `LGTM` only when at least 2 of the 3 jurors vote for it, so a PR can get LGTM together with comments from the minority. A juror's LGTM vote counts only when the juror raises no comments, and a juror that is absent or fails counts as a vote against. The body lists the vote of each juror, and it does not contain `LGTM` when the majority is missing.
- **Threads resolve by majority.** The jury replies to and resolves one of its earlier threads only when at least 2 jurors report it fixed. Replies to other authors' threads come from every juror, without duplicates.
- Juror text is published only after the API keys and token-shaped strings are removed from it, because a prompt injection in a PR could make a juror copy its key into a comment.
- Earlier jury reviews that have no open threads are minimized as outdated. Threads and reviews from the single-model reviewer that came before the jury (`claude[bot]`) count as the jury's own.

Add the `skip-claude-review` label to a PR to skip the review.

**Job environment:** each juror runs with a shell and can execute commands to check its own claims rather than reasoning from the spec. Repos with a `.node-version` or `.nvmrc` get that Node version installed; repos with a `yarn.lock` get Corepack enabled. Both setup steps are best-effort and skip on repos that don't need them. The jurors read prior reviews and threads from a file that the workflow prepares, and none of them can write to the PR.

Dependencies are not installed. The jurors' sandboxes differ:

- **Opus** has network access, so on Yarn repos it can install dependencies itself when a finding turns on running the repo's own code. `node` and `yarn` are the only JS tooling in its allowlist, so npm and pnpm repos get the pinned runtime but no install path.
- **Astra** and **Grok** run in read-only sandboxes without network access: they can read the repo and run commands that do not write files. Astra runs on the Node version that `openai/codex-action` installs, not the repo's pinned version.

### Repository-specific review instructions

The shared prompt stays general-purpose. To add conventions or review policies specific to a repo (or a subtree within it), commit instruction files alongside the code — no workflow changes needed:

- **`AGENTS.md`** — general codebase conventions and agent guidance ([an emerging standard](https://agents.md/)). Used to judge idiomatic patterns.
- **`REVIEWING.md`** — review-specific policies and checklists (e.g. "require a linked desktop build for PRs that touch `packages/desktop`").

Each file applies to its own directory and all subdirectories; a file at the repo root applies repo-wide. When multiple files apply to a path, the more deeply nested one takes precedence. The workflow discovers these files automatically (tracked files only) and the jurors apply them on top of the general guidance, so repo-specific rules don't have to live in this shared prompt.

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
      contents: read
      pull-requests: write
    uses: foxglove/actions/.github/workflows/review.yml@main
    secrets:
      ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
      OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
      XAI_API_KEY: ${{ secrets.XAI_API_KEY }}
```

`ANTHROPIC_API_KEY` is required. `OPENAI_API_KEY` and `XAI_API_KEY` are optional so that existing callers keep working, but a juror without its key does not vote: LGTM then needs both of the other jurors, and it is not possible when two keys are missing. The review body names each juror that did not vote and the missing secret.

> **Note:** If your repository restricts the default `GITHUB_TOKEN` permissions, you may also need to add a top-level `permissions` block to explicitly grant the required access at the workflow level.
>
> ```yaml
> permissions:
>   contents: read
>   pull-requests: write
> ```

## Development

```sh
yarn install
yarn test
yarn prettier --check .
```
