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

Build reusable AI agent actions for two modes of risk assessment, both grounded in the Risk Management Policy:

- **Initial assessment** — Run when adopting a new tool, standing up a new product, or introducing a new system. Produces a full risk assessment artifact committed to the same repo as the thing being assessed. Creates Linear issues with due dates for any identified follow-ups.
- **Incremental assessment** — Run on every PR. Scoped to only the changes in the PR, informed by the repo's existing risk assessment doc. Should rarely surface net-new findings, but determines the PR's risk tier so the review agent knows whether it can approve or must defer to a human.

This replaces the idea of a deterministic file-pattern classifier — experience over the past week has shown that heuristics like `private: true`, file paths, and directory conventions are poor proxies for actual risk. The agent can reason about what a change *does*, not just what files it touches.

### Scope

1. **Initial risk assessment agent** — A reusable workflow for comprehensive risk assessment of new products, tools, or systems. The agent evaluates the subject against the policy's likelihood x impact framework across all risk categories, produces a structured risk assessment artifact (committed to the repo alongside what it's assessing, not buried in infra), and creates Linear issues with due dates for any moderate or high follow-ups.

2. **Incremental risk assessment agent** — A reusable workflow that runs on each PR. The agent reads the diff and the repo's existing risk assessment doc, evaluates whether the change introduces net-new risks, and outputs a risk tier (low/moderate/high). New findings should be rare — most PRs operate within the risk profile already documented. When net-new risks are found, the agent creates Linear issues with due dates.

3. **Risk assessment prompt** — A dedicated prompt (separate from the review prompt) grounded in the Risk Management Policy. Covers both initial and incremental modes: what constitutes a net-new risk, how to score likelihood and impact, when to create Linear follow-ups vs when to simply inform the review tier. Lives in `prompts/risk-assessment.md` alongside the existing `prompts/review.md`.

4. **Update the review prompt to use low/moderate/high** — Replace the binary "low / not low risk" model in `prompts/review.md` with the three-tier model. Approval policy: only low-risk PRs with no blockers may receive `APPROVE`; anything moderate or high gets `COMMENT` so a human must approve. The review agent consumes the incremental risk assessment output rather than re-deriving risk independently.

5. **Risk label workflow** — A thin reusable workflow that consumes the incremental agent's output and applies `risk:low`, `risk:moderate`, or `risk:high` labels to PRs automatically.

### Out of scope

- Deterministic file-pattern-based risk classification. Not useful in practice.
- Deployment gate workflows. Depends on per-repo CD pipeline structure.

### Metrics

- **Initial coverage**: percentage of products and tools with a documented initial risk assessment.
- **Incremental coverage**: percentage of PRs across Foxglove repos that receive an automated incremental risk assessment.
- **Remediation rate**: percentage of risk findings with Linear issues that are closed on-time.
- **Agent approval rate**: change in the rate at which the review agent approves PRs once risk assessment informs its approval decisions.

## Potential risks, dependencies & blockers

- Running an additional AI agent per PR adds cost and latency. Need to evaluate whether the incremental risk assessment can share a workflow run with the existing review agent or must run separately.
- The incremental agent depends on a risk assessment doc existing in the repo. Repos that haven't done an initial assessment yet will have no baseline — the incremental agent needs a sensible fallback (e.g., treat everything as moderate until an initial assessment is completed).
- Linear integration requires API access from GitHub Actions. Need to ensure the reusable workflow can accept a Linear API token as a secret.
