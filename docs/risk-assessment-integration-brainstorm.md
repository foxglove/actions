# Risk Assessment Actions Integration — Brainstorm

This document explores ways to extract and extend the risk assessment logic currently embedded in the AI review prompt (`prompts/review.md`) into standalone, reusable GitHub Actions that any Foxglove repository can consume.

## Current State

Risk classification today lives entirely inside the Claude review prompt. It tells the AI reviewer how to decide between `APPROVE` and `COMMENT`, but:

- There is no machine-readable risk output other workflows can consume.
- Risk classification cannot be used independently of the full AI review.
- Repositories cannot customize risk rules without forking the prompt.
- There is no way to gate deployments, require additional approvals, or enforce checklists based on assessed risk.

## Integration Ideas

### 1. Deterministic Risk Classifier Action

A lightweight composite action (no AI cost) that performs static analysis on the PR diff and outputs a structured risk classification.

**How it works:**
- Analyzes changed file paths against configurable patterns (e.g., `**/migrations/**`, `**/api/**`, `**/*.proto`).
- Checks `package.json` for `private: true` to determine export visibility.
- Detects database migration files, schema changes, public API surface changes.
- Outputs a risk level (`low`, `elevated`, `high`) and a list of risk signals as structured JSON.

**Example config (`.github/risk-assessment.yml`):**
```yaml
high_risk_patterns:
  - "**/migrations/**"
  - "**/schema/**"
  - "**/*.proto"
  - "**/public-api/**"
elevated_risk_patterns:
  - "**/components/**"
  - "**/pages/**"
  - "**/handlers/**"
low_risk_override:
  - "docs/**"
  - "**/*.md"
  - ".github/**"
```

**Outputs:**
```yaml
outputs:
  risk_level: "low" | "elevated" | "high"
  risk_signals: '["db-migration", "public-api-change"]'
  summary: "PR modifies database migrations and public API surface"
```

**Advantages:** Fast, free, deterministic, easy to reason about. Pairs well with the AI review (Claude can consume the structured output as additional context).

---

### 2. Risk-Aware Label Action

Automatically applies GitHub labels based on the assessed risk level so that teams get visual signal on the PR list page without opening each PR.

**How it works:**
- Runs the deterministic classifier (idea 1) or consumes its output.
- Applies labels like `risk:low`, `risk:elevated`, `risk:high`, and optionally signal-specific labels like `risk:db-migration`, `risk:public-api`.
- Removes stale risk labels on re-assessment (e.g., when the PR is updated).

**Reusable workflow:**
```yaml
jobs:
  risk-label:
    uses: foxglove/actions/.github/workflows/risk-label.yml@main
    permissions:
      contents: read
      pull-requests: write
```

**Advantages:** Zero friction — everyone on the team sees risk level at a glance. Useful for prioritizing review queues.

---

### 3. Risk-Gated Approval Policy

A status check that enforces different approval requirements based on risk level.

**How it works:**
- Runs the risk classifier.
- For `low` risk: passes immediately (or requires 1 approval).
- For `elevated` risk: requires at least 1 human approval.
- For `high` risk: requires 2 human approvals, or approval from a specific team (e.g., `@foxglove/infra`).
- Reports as a GitHub status check that branch protection rules can enforce.

**Example usage in a consuming repo:**
```yaml
jobs:
  risk-gate:
    uses: foxglove/actions/.github/workflows/risk-gate.yml@main
    with:
      elevated_approvals: 1
      high_approvals: 2
      high_required_team: "foxglove/infra"
```

**Advantages:** Codifies the "human must approve" policy that the AI review currently enforces only by convention (submitting `COMMENT` vs `APPROVE`). Makes it a hard gate.

---

### 4. Structured Risk Output from Claude Review

Extend the existing AI review to emit a machine-readable risk assessment alongside the natural-language review.

**How it works:**
- Add a structured output section to the review prompt instructing Claude to write a hidden HTML comment or a specific artifact with the risk classification.
- A post-processing step in the workflow parses the structured output and sets it as workflow outputs or writes it to a PR comment with a known format.
- Downstream workflows can consume these outputs.

**Prompt addition:**
```markdown
## Structured Risk Output

After completing your review, emit a risk assessment block as an HTML comment
in the review body:

<!--RISK_ASSESSMENT
level: low | elevated | high
signals:
  - signal-name-1
  - signal-name-2
reasoning: One-line summary of why this risk level was chosen.
-->
```

**Post-processing step:**
```yaml
- name: Parse risk assessment
  id: risk
  run: |
    # Extract the RISK_ASSESSMENT block from the review comment
    # Set outputs for downstream jobs
```

**Advantages:** Leverages the AI's deeper understanding of code semantics (not just file patterns). Can catch risks that static patterns miss (e.g., a subtle auth bypass in a non-obvious file).

**Trade-offs:** Depends on the AI review running (cost, latency). Less deterministic than pattern matching.

---

### 5. Deployment Gate Workflow

A reusable workflow that sits in the deployment pipeline and uses risk assessment to control rollout.

**How it works:**
- Consumes risk output (from idea 1 or 4).
- For `low` risk: auto-proceeds with deployment.
- For `elevated` risk: requires a manual approval step (`environment: production` with required reviewers).
- For `high` risk: requires manual approval + posts a Slack notification to the infra team.
- Optionally enforces a deployment checklist (rollback plan documented, monitoring dashboards linked).

**Example:**
```yaml
jobs:
  assess:
    uses: foxglove/actions/.github/workflows/risk-assess.yml@main
    outputs:
      risk_level: ${{ jobs.assess.outputs.risk_level }}

  deploy:
    needs: assess
    if: needs.assess.outputs.risk_level == 'low'
    runs-on: ubuntu-latest
    steps:
      - run: echo "Auto-deploying low-risk change"

  deploy-gated:
    needs: assess
    if: needs.assess.outputs.risk_level != 'low'
    environment: production
    runs-on: ubuntu-latest
    steps:
      - run: echo "Deploying after manual approval"
```

**Advantages:** Ties risk assessment directly to deployment safety. Prevents high-risk changes from auto-deploying.

---

### 6. Risk-Aware PR Checklist Enforcer

Dynamically adjusts what PR authors must fill out based on the risk level of their changes.

**How it works:**
- Runs the risk classifier on PR open/update.
- Posts or updates a comment with a checklist appropriate to the risk level.
- For `low` risk: minimal checklist (tests pass, linter clean).
- For `elevated` risk: adds items like "screenshots attached", "tested locally", "docs updated".
- For `high` risk: adds "rollback plan documented", "infra team notified", "monitoring dashboards linked", "deploy order specified".
- Optionally enforces that checklist items are checked before the PR can merge (via status check).

**Advantages:** Shifts left — ensures authors think about risk before review. Reduces back-and-forth in reviews.

---

### 7. Risk Assessment Context Injection for Claude Review

Rather than having Claude re-derive risk from scratch, pre-compute the deterministic risk signals and inject them into the Claude review as additional context.

**How it works:**
- Run the deterministic classifier (idea 1) as a prior job.
- Pass the structured risk output into the Claude review prompt as `CONTEXT.risk_assessment`.
- Claude can use this as a starting point, override it with deeper analysis, and focus review effort on the flagged areas.

**Modified workflow:**
```yaml
jobs:
  risk:
    uses: foxglove/actions/.github/workflows/risk-assess.yml@main
    outputs:
      risk_level: ${{ jobs.risk.outputs.risk_level }}
      risk_signals: ${{ jobs.risk.outputs.risk_signals }}

  review:
    needs: risk
    uses: foxglove/actions/.github/workflows/review.yml@main
    with:
      risk_context: |
        Pre-computed risk level: ${{ needs.risk.outputs.risk_level }}
        Detected signals: ${{ needs.risk.outputs.risk_signals }}
    secrets:
      ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

**Advantages:** Makes the AI review faster and more focused. The deterministic classifier catches the obvious signals; Claude focuses on subtle issues. Also provides a risk assessment even if the Claude review fails or is skipped.

---

### 8. Repo-Specific Risk Rule Overrides

Allow consuming repositories to extend the base risk rules with repo-specific configuration.

**How it works:**
- The base risk classifier ships with sensible defaults (the rules currently in `prompts/review.md`).
- Repos can place a `.github/risk-rules.yml` (or similar) that adds, removes, or overrides rules.
- The classifier merges base + repo-specific rules at runtime.

**Example `.github/risk-rules.yml`:**
```yaml
extends: default

additional_high_risk:
  - pattern: "**/billing/**"
    reason: "Changes to billing logic require finance team review"
  - pattern: "**/auth/**"
    reason: "Authentication changes require security review"

override_low_risk:
  - pattern: "**/internal-tools/**"
    reason: "Internal tooling changes are lower risk for this repo"

required_reviewers:
  high:
    teams: ["foxglove/security", "foxglove/infra"]
  elevated:
    count: 1
```

**Advantages:** One set of reusable actions, but each repo can tune for its own risk profile.

---

## Recommended Phased Approach

**Phase 1 — Foundation:**
- Build idea 1 (deterministic risk classifier) as a composite action under `actions/risk-assess/`.
- Build idea 2 (risk labels) as a thin reusable workflow that wraps the classifier.
- Ship both with documentation and a migration guide.

**Phase 2 — AI integration:**
- Build idea 7 (inject risk context into Claude review) to make the AI review risk-aware without duplicating classification logic.
- Build idea 4 (structured risk output) so the AI review's risk decision is machine-readable.

**Phase 3 — Policy enforcement:**
- Build idea 3 (risk-gated approvals) for repos that want hard gates.
- Build idea 5 (deployment gate) for repos with CD pipelines.
- Build idea 8 (repo-specific overrides) once the base rules are proven stable.

**Phase 4 — Developer experience:**
- Build idea 6 (PR checklist enforcer) for teams that want guided PR authoring.
- Add a dashboard or summary comment that shows the risk assessment, classification reasoning, and what policies were applied.

## Open Questions

- Should the deterministic classifier run as a **composite action** (`action.yml`) or a **reusable workflow** (`workflow_call`)? A composite action is more flexible (can be called as a step within any job), but a reusable workflow matches the current pattern in this repo.
- How should we handle **risk assessment for monorepos** where different directories have different risk profiles?
- Should risk classification be **append-only** (signals accumulate, risk only goes up) or should it support **explicit low-risk overrides** (e.g., "this migration is a no-op, mark as low risk")?
- How do we handle **risk disagreement** between the deterministic classifier and Claude? Which takes precedence?
- Should risk assessment results be **persisted** (e.g., as PR metadata, check run annotations) for auditability?
