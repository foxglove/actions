# Integrating Risk Assessment Policy into Code Review

## Purpose

Our [Risk Management Policy](https://www.notion.so/foxglovehq/Risk-Management-Policy-96c7f18abfe04fc1a796fcdf9ecf1c5d) defines a three-tier risk model (low/moderate/high), but our automated code review enforces a cruder binary: "low risk" (auto-approve) vs "not low risk" (defer to human). The risk logic lives entirely inside a prose prompt with no machine-readable output, so nothing else in our CI/CD pipeline can act on it. This work aligns our tooling to the policy, makes risk classification a first-class, reusable primitive, and lets us enforce appropriate review and deployment gates based on actual assessed risk.

## Context

Today the AI review prompt ([`prompts/review.md#L33-L72`](https://github.com/foxglove/actions/blob/d7ac809e519261864e315a2d8d15ea3daa3a4701/prompts/review.md#L33-L72)) is the only place risk classification happens. It tells Claude when to `APPROVE` vs `COMMENT`, but the result is buried in a natural-language review — no other workflow can consume it. Repositories cannot customize risk rules without forking the prompt, and there is no way to require additional approvals or gate deployments based on risk level.

We recently shipped a [machine-readable risk assessment format in the infra repo](https://github.com/foxglove/infra/pull/923) that aligns with the Risk Management Policy's three-tier model. That work validates the format and proves it out in one repo — the next step is extracting it into reusable actions here so every Foxglove repo can adopt the same structured risk assessment without reimplementing it.

The [Risk Management Policy appendix](https://www.notion.so/foxglovehq/Risk-Management-Policy-96c7f18abfe04fc1a796fcdf9ecf1c5d?source=copy_link#7bb90e829e89475fb9a8096eb689e25c) scores risk as likelihood (1-3) x impact (1-3) and maps the product to three tiers:

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

Build a reusable AI agent risk assessor that runs on every PR, identifies net-new risks introduced by the change, classifies them using the policy's three-tier model, and creates follow-up actions for any moderate or high risks. This replaces the idea of a deterministic file-pattern classifier — experience over the past week has shown that heuristics like `private: true`, file paths, and directory conventions are poor proxies for actual risk. The agent can reason about what a change *does*, not just what files it touches.

### Scope

1. **Risk assessment agent action** — A reusable workflow that runs an AI agent on each PR. The agent reads the diff, evaluates it against the Risk Management Policy's likelihood × impact framework, and produces a structured risk assessment: tier (low/moderate/high), identified risk signals, and reasoning. For any net-new moderate or high risks, the agent creates follow-up actions (e.g., GitHub issues, review comments with required mitigations) so risks are tracked and addressed rather than just flagged.

2. **Risk assessment prompt** — A dedicated prompt (separate from the review prompt) that grounds the agent in the Risk Management Policy. Defines what constitutes a net-new risk, how to score likelihood and impact, and what follow-up actions to create for each tier. Lives in `prompts/risk-assessment.md` alongside the existing `prompts/review.md`.

3. **Update the review prompt to use low/moderate/high** — Replace the binary "low / not low risk" model in `prompts/review.md` with the three-tier model. Update the approval policy so Claude uses the tiers to decide `APPROVE` vs `COMMENT`. The review agent consumes the risk assessment output rather than re-deriving risk independently.

4. **Risk label workflow** — A thin reusable workflow that consumes the agent's risk assessment output and applies `risk:low`, `risk:moderate`, or `risk:high` labels to PRs automatically.

### Out of scope

- Deterministic file-pattern-based risk classification. Not useful in practice.
- Risk-gated approval enforcement (status checks that block merge based on tier). Natural follow-on once the agent is proven.
- Deployment gate workflows. Depends on per-repo CD pipeline structure.
- Non-technical risk categories (Reputational, Contractual, Regulatory, etc.) from the policy.

### Metrics

- **Coverage**: percentage of PRs across Foxglove repos that receive an automated risk assessment.
- **Follow-up rate**: percentage of moderate/high risk assessments that result in a tracked follow-up action.
- **Review efficiency**: change in time-to-first-human-review for moderate and high PRs after risk labels and follow-up actions ship.

## Potential risks, dependencies & blockers

- Running an additional AI agent per PR adds cost and latency. Need to evaluate whether the risk assessment agent can share a workflow run with the existing review agent or must run separately.
- Updating the review prompt from binary to three-tier changes approval behavior. Needs careful rollout — a miscalibrated moderate threshold could either auto-approve things that shouldn't be or create unnecessary friction.
- Follow-up action format needs to align with whatever the infra repo is already producing so we don't end up with two competing formats.
