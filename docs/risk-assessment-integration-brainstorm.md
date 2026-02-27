# Integrating Risk Assessment Policy into Code Review

## Purpose

Our [Risk Management Policy](https://www.notion.so/foxglovehq/Risk-Management-Policy-96c7f18abfe04fc1a796fcdf9ecf1c5d) defines a three-tier risk model (low/moderate/high), but our automated code review enforces a cruder binary: "low risk" (auto-approve) vs "not low risk" (defer to human). The risk logic lives entirely inside a prose prompt with no machine-readable output, so nothing else in our CI/CD pipeline can act on it. This work aligns our tooling to the policy, makes risk classification a first-class, reusable primitive, and lets us enforce appropriate review and deployment gates based on actual assessed risk.

## Context

Today the AI review prompt (`prompts/review.md`) is the only place risk classification happens. It tells Claude when to `APPROVE` vs `COMMENT`, but the result is buried in a natural-language review — no other workflow can consume it. Repositories cannot customize risk rules without forking the prompt, and there is no way to require additional approvals or gate deployments based on risk level.

We recently shipped a machine-readable risk assessment format in the infra repo that aligns with the Risk Management Policy's three-tier model. That work validates the format and proves it out in one repo — the next step is extracting it into reusable actions here so every Foxglove repo can adopt the same structured risk assessment without reimplementing it.

The Risk Management Policy scores risk as likelihood (1-3) x impact (1-3) and maps the product to three tiers:

| Score | Tier | Definition |
|-------|------|------------|
| 1-2 | **Low** | Limited adverse effect on operations, assets, or customers. |
| 3-6 | **Moderate** | Serious adverse effect on operations, assets, or customers. |
| 7-9 | **High** | Severe adverse effect on operations, assets, or customers. |

The current prompt's criteria map onto those tiers as follows:

| Criterion | Tier |
|---|---|
| Docs-only, test-only, private-package internals | **Low** |
| Customer-facing UI/UX, public API surface changes, externally-consumed packages | **Moderate** |
| Broad blast radius / backwards-compatibility risk, database schema / migrations | **High** |

## Solution

Build a deterministic risk classifier and update the AI review so that every PR gets a structured, three-tier risk assessment aligned to the Risk Management Policy. Expose the result as a reusable action other workflows can consume for labeling, approval gating, and deployment control.

### Scope

1. **Deterministic risk classifier action** — A composite action that analyzes the PR diff against configurable file-path patterns (e.g., `**/migrations/**` = high, `**/components/**` = moderate, `docs/**` = low), checks `package.json` for `private: true`, and outputs a structured risk level plus a list of detected signals. Ships with sensible defaults derived from the policy; repos can override via `.github/risk-assessment.yml`.

2. **Update the AI review prompt to use low/moderate/high** — Replace the binary "low / not low risk" model in `prompts/review.md` with the three-tier model. Update the approval policy so Claude uses the tiers to decide `APPROVE` vs `COMMENT`. Add a structured output block (HTML comment in the review body) so the risk assessment is machine-readable.

3. **Inject deterministic risk context into the AI review** — Run the classifier before the Claude review and pass its output as `CONTEXT.risk_assessment`. The deterministic classifier sets a floor; Claude can upgrade the tier but not downgrade it. This makes the AI review faster (less re-derivation) and provides a risk assessment even when the AI review is skipped or fails.

4. **Risk label workflow** — A thin reusable workflow that consumes the classifier output and applies `risk:low`, `risk:moderate`, or `risk:high` labels to PRs automatically.

### Out of scope

- Risk-gated approval enforcement (status checks that block merge based on tier). Natural follow-on once the classifier is proven.
- Deployment gate workflows. Depends on per-repo CD pipeline structure.
- Dynamic PR checklists scaled to risk tier.
- Non-technical risk categories (Reputational, Contractual, Regulatory, etc.) from the policy.

### Metrics

- **Coverage**: percentage of PRs across Foxglove repos that receive an automated risk classification.
- **Accuracy**: rate at which the AI review agrees with the deterministic classifier's tier (measured by comparing the classifier output to Claude's structured risk output on the same PR).
- **Review efficiency**: change in time-to-first-human-review for moderate and high PRs after labels ship (do labels help reviewers prioritize?).

## Potential risks, dependencies & blockers

- The deterministic classifier is weakest in the **moderate** tier. File-path patterns can flag UI and API files, but cannot determine whether a change is actually customer-facing or breaking. The AI review is the backstop, but if it fails or is skipped, moderate-tier accuracy will be lower.
- Updating the review prompt from binary to three-tier changes approval behavior. Needs careful rollout — a miscalibrated moderate threshold could either auto-approve things that shouldn't be or create unnecessary friction.
- The classifier depends on repos having consistent directory conventions (e.g., migrations in a `migrations/` directory). Repos with non-standard layouts will need overrides from day one.
