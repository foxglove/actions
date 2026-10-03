# Attack Runner — offline planner

The offline planner is the deterministic core of exploit reconciliation. It consumes one
assessment run of **normalized** observations plus existing-ticket snapshots and emits a
**proposed** set of ticket/counter/lifecycle actions and run-summary entries. It performs
no I/O: no network calls, secret reads, ticket writes, Slack messages, harness execution,
or workflow changes (acceptance `E1-15`). Building it first makes identity, evidence, and
lifecycle rules testable before any live authentication, network, or external-write
integration (engineering handoff, "Recommended implementation sequence").

## Status

- **WP0.1** contract (schemas + fixtures) and **WP1.1–WP1.4** implementation are landed.
- `plan()` is implemented in `src/plan.mjs`; identity/normalization in `src/normalize.mjs`.
- Covers the representative cases E1-01, 02, 03, 03b (open+fix-claim), 04, 08, 08b (in-run
  duplicate), 12, 17. Remaining E1 criteria are tracked in
  `../../.feature-workspace/attack-runner/STATUS.md`.

## Entry point

```
import { plan } from "./src/index.mjs";
const proposal = plan(input); // pure; throws PlannerInputError on structurally unreadable input
```

- `input` conforms to [`schema/planner-input.schema.json`](schema/planner-input.schema.json).
- the return value conforms to [`schema/planner-output.schema.json`](schema/planner-output.schema.json).
- Pure and total: equal normalized input and prior-event state produce the same logical plan.
  The outcome multiset is invariant under observation reordering.

Run the example:

```
node attack-runner/planner/example.mjs e1-03-claimed-fixed-reproduces
```

## Normalized vs. planner-owned

The planner receives **normalized states**, not raw vendor data. The adapter boundary
(Engineering 2) owns normalization and must not hide untested identity decisions there:

- **Mapped at the adapter boundary (not the planner):** vendor issue status →
  `existingIssues[].state` (`open` | `resolved` | `unknown`); the explicit fix claim →
  `fixClaim`. The planner never sees a raw `"Done"` label.
- **Owned by the planner:** matching an observed causal chain to an existing exploit
  identity; the five outcomes; counting once per run; replay/in-run dedup; notification
  eligibility; triage-evidence needs.

Identity is built only from the structured `semantics` tuple on each transition plus the
target environment. Prose, titles, resource IDs, repository names, harness/model, path
revision, and transitions flagged `semantics.incidental` are excluded. Missing semantics
never become a silent identity — they route to `unresolved`.

## Outcomes

| Outcome                    | When                                                                                    | Proposed actions                                                           |
| -------------------------- | --------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| `new`                      | valid positive, identity established, no match                                          | create ticket (with full ticket material); count once                      |
| `rediscovered-open`        | valid positive, one open match, no fix claim; or an in-run duplicate                    | append evidence; count once (none for a duplicate)                         |
| `claimed-fixed-reproduces` | valid positive contradicts a fix claim (open or closed)                                 | append evidence; reopen **only if closed**; count once; identify the claim |
| `not-observed`             | run ends without observing a tracked exploit                                            | **zero writes**; summary-only with coverage + stop reason                  |
| `unresolved`               | invalid evidence / ambiguous identity / unknown ticket state / resolved without a claim | none; record the missing evidence                                          |

The output is an **action proposal, not proof of delivery.** It never reports a resolved
ticket as written, never claims a reopen succeeded, and never turns a non-observation or an
edge block into an absence/fixed claim.

## Verification

```
node attack-runner/planner/run-fixtures.mjs     # deep-equal vs authored expected + invariants + round-trip + mutation self-test + structural-reject
node attack-runner/planner/check-fixtures.mjs   # dependency-free branch-coverage + invariant guard
```

The oracle writes each actual output to a temp dir for JSON Schema validation (ajv draft2020):

```
npx ajv-cli@5 validate --spec=draft2020 -s attack-runner/planner/schema/planner-input.schema.json  -d "attack-runner/planner/fixtures/*/input.json"
npx ajv-cli@5 validate --spec=draft2020 -s attack-runner/planner/schema/planner-output.schema.json -d "attack-runner/planner/fixtures/*/expected.json"
npx ajv-cli@5 validate --spec=draft2020 -s attack-runner/planner/schema/planner-output.schema.json -d "/tmp/aegis-planner-out/*.json"
```

Each `expected.json` is the full authored output (its `reason`/`matchReason` are placeholders the
oracle ignores). The oracle deep-compares everything else, so a wrong engine cannot hide a
mis-set field; the built-in mutation self-test proves the comparison is tight.
