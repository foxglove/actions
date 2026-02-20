# PR Description

You are writing a pull request description for a Foxglove repository.

## Template

If the repository contains `.github/pull_request_template.md`, read it and follow its structure exactly. If the template is absent, use the canonical structure below.

The canonical Foxglove PR description has three required sections in this order:

```
### Changelog

<one-sentence summary or "None">

### Docs

<docs update summary, link, or "None">

### Description

<body>
```

## Section Rules

### Changelog

Write a single sentence summarizing the **public, user-impacting** change (API, UI/UX, performance, behavior). This sentence should be suitable for inclusion in a release changelog read by end users.

- Write from the user's perspective, not the developer's. Describe what changed for them, not how the code changed internally.
- Write "None" if there is no public-facing change (refactors, internal tooling, CI, test-only changes, docs-only changes).
- Features behind a feature flag should have "None" — they are not yet user-visible.
- Do not list multiple items. Distill the change into one sentence.

### Docs

Describe documentation updates made in this PR, or link to a separate docs PR or documentation tracking ticket (e.g. a Linear issue or a GitHub PR in another repo).

- Write "None" if no documentation changes are needed.
- Features behind a feature flag do not need documentation.
- If documentation is handled in a separate PR, provide the link (e.g. `https://github.com/foxglove/app/pull/12345`).

### Description

This is the main body. It must cover three things:

1. **Problem** — What issue or need motivated this change?
2. **What changed** — What was added, modified, or removed?
3. **Why** — Why is this the right approach? What alternatives were considered?

Write as if you are advocating for this change to a skeptical reader. Be direct, specific, and concise. Do not pad with filler.

#### Manual testing

After the description body, describe manual testing that validates the change.

- If you are an AI agent and cannot perform manual testing, insert a TODO checklist of manual testing steps for human reviewers to follow. For example:

  ```
  Manual testing TODO for reviewers:
  - [ ] Verify X behaves correctly when Y
  - [ ] Confirm Z appears in the UI after doing W
  ```

- If no manual testing is needed (e.g. the change is fully covered by automated tests, or is a trivial docs/config change), omit this subsection entirely.

#### Before/After visuals

For user-facing visual changes (UI, screenshots, screen recordings), include a Before/After comparison table:

```html
<table><tr><th>Before</th><th>After</th></tr><tr><td>

<!-- screenshot or video of old behavior -->

</td><td>

<!-- screenshot or video of new behavior -->

</td></tr></table>
```

- Only include this table when there are actual visual changes to show.
- Do not use this section to restate code changes visible in the diff.
- Delete the table entirely if there are no visual changes.

#### Issue links

Link relevant GitHub or Linear issues at the end of the Description section, each on its own line:

- GitHub: `Fixes: https://github.com/<org>/<repo>/issues/123`
- Linear: `Fixes: [ABC-123](https://linear.app/foxglove/issue/ABC-123)`

Use "Fixes:" when the PR fully resolves the issue (this auto-closes it on merge). Use "Related:" or "Part of:" for partial progress. Omit this subsection if there are no linked issues.

## Writing Style

- Be direct and concise. Lead with the point, then explain why.
- Use plain language. Avoid jargon that wouldn't be clear to someone unfamiliar with this specific codebase.
- Do not restate the diff. The reviewer can read the code; the description should explain context that the code cannot convey on its own.
- Do not narrate your development process ("First I tried X, then I realized Y"). Describe the end state and rationale.
- Maintain a professional, engineering-focused tone. No conversational filler.

## Cleanup

- Remove all HTML comments (`<!-- ... -->`) from the template before submitting. The final description should contain no placeholder comments.
- Remove any unused sections (e.g. the Before/After table if there are no visuals, the issue links subsection if there are no linked issues).
- Do not leave empty sections. Every section heading must have content below it.
