# Attack Runner — offline planner (WP0.1 contract)

The offline planner is the deterministic core of exploit reconciliation. It consumes one
assessment run of **normalized** observations plus existing-ticket snapshots and emits a
**proposed** set of ticket/counter/lifecycle actions and run-summary entries. It performs
no I/O: no network calls, secret reads, ticket writes, Slack messages, harness execution,
or workflow changes (acceptance `E1-15`).

Building the planner first makes the identity, evidence, and lifecycle rules testable before
any live authentication, network, or external-write integration (engineering handoff,
"Recommended implementation sequence").

## Status

This directory is the **WP0.1** deliverable: the input/output contract and representative
fixtures. The executable `plan()` function is **WP1.\*** and is not implemented yet.

## Entry point (contract)

A single pure function, to be implemented under this directory in WP1.\*:

```
plan(input: PlannerInput): PlannerOutput
```

- `PlannerInput` conforms to [`schema/planner-input.schema.json`](schema/planner-input.schema.json).
- `PlannerOutput` conforms to [`schema/planner-output.schema.json`](schema/planner-output.schema.json).
- Pure and total: equal normalized input and prior-event state produce the same logical plan.
  Tests assert semantic results, not incidental field order.

## Normalized vs. planner-owned

The planner receives **normalized states**, not raw vendor data. The adapter boundary
(Engineering 2) owns normalization and must not hide untested identity decisions there:

- **Mapped at the adapter boundary (not the planner):** vendor issue status strings →
  `existingIssues[].state` (`open` | `resolved`); the explicit fix claim → `fixClaim`.
  The planner never sees a raw `"Done"` label.
- **Owned by the planner:** matching an observed causal chain to an existing exploit
  identity; choosing one of the five outcomes; counting (once per distinct run); replay
  dedup against `processedEvents`; notification eligibility; and what evidence is still
  needed for an `unresolved` decision.

Identity is built only from evidence-backed causal transitions (actor capability, target +
operation, expected boundary, observed transition, prerequisites, evidence). Titles, prose,
resource IDs, repository names, harness/model, and path revision are excluded from matching.
Affected repositories are optional metadata, never a matching key.

## Outcomes (handoff decision table)

| Outcome                    | When                                                           | Proposed actions                                                     |
| -------------------------- | -------------------------------------------------------------- | -------------------------------------------------------------------- |
| `new`                      | valid positive, identity established, no match                 | create one ticket; count once                                        |
| `rediscovered-open`        | valid positive, exactly one open match                         | append evidence; count once; not notification-eligible               |
| `claimed-fixed-reproduces` | valid positive contradicts an explicit fix claim               | append evidence; reopen if closed; count once; notification-eligible |
| `not-observed`             | run ends without observing a tracked exploit                   | **zero writes**; summary-only record with coverage + stop reason     |
| `unresolved`               | invalid evidence / ambiguous identity / unknown required state | none; record the missing evidence                                    |

The output is an **action proposal, not proof of delivery.** It never reports a resolved
ticket as written, never claims a reopen succeeded, and never turns a non-observation or an
edge block into an absence/fixed claim.

## Verifying the fixtures

Representative fixtures live in [`fixtures/`](fixtures), one directory per branch, each with
`input.json` and the expected `expected.json`.

1. Dependency-free guard (branch coverage + core invariants):

   ```
   node attack-runner/planner/check-fixtures.mjs
   ```

2. JSON Schema conformance (draft 2020-12), when a validator is available:

   ```
   npx ajv-cli@5 validate --spec=draft2020 \
     -s attack-runner/planner/schema/planner-input.schema.json  -d "attack-runner/planner/fixtures/*/input.json"
   npx ajv-cli@5 validate --spec=draft2020 \
     -s attack-runner/planner/schema/planner-output.schema.json -d "attack-runner/planner/fixtures/*/expected.json"
   ```

Both passed at WP0.1 landing (see `.feature-workspace/attack-runner/EVIDENCE.md`). When
WP1.\* implements `plan()`, these `expected.json` files become its assertion targets.
