# Attack Runner — offline planner

The offline planner is the deterministic core of exploit reconciliation. It consumes one
assessment run of **normalized** observations plus existing-ticket snapshots and emits a
**proposed** set of ticket/counter/lifecycle actions and run-summary entries. It performs
no I/O: no network calls, secret reads, ticket writes, Slack messages, harness execution,
or workflow changes (acceptance `E1-15`). Building it first makes identity, evidence, and
lifecycle rules testable before any live authentication, network, or external-write
integration (engineering handoff, "Recommended implementation sequence").

## Fixtures and coverage

`plan()` is implemented in `src/plan.mjs`; identity/normalization in `src/normalize.mjs`.
Each directory under `fixtures/` maps to one acceptance criterion by its `e1-NN` prefix and
holds an `input.json` plus the full authored `expected.json`. A directory with an
`INPUT_SCHEMA_INVALID` marker carries intentionally out-of-contract input to test defensive
handling. The mutation test (below) is the coverage gate: it fails if any source mutation
survives the fixtures.

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
node attack-runner/planner/example.mjs e1-03-claimed-fixed-resolved
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

| Outcome                    | When                                                                                                                           | Proposed actions                                                                                                       |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------- |
| `new`                      | valid positive, identity established, no match (incl. a replay or in-run duplicate of a new exploit — same outcome, no action) | create ticket (with full ticket material); count once. A replay/in-run duplicate keeps the outcome but proposes `none` |
| `rediscovered-open`        | valid positive, one open match, no fix claim                                                                                   | append evidence (+ remediation); count once                                                                            |
| `claimed-fixed-reproduces` | valid positive contradicts a fix claim (open or closed)                                                                        | append evidence; reopen **only if closed**; count once; identify the claim                                             |
| `not-observed`             | run ends without observing a tracked exploit                                                                                   | **zero writes**; summary-only with coverage + stop reason                                                              |
| `unresolved`               | invalid evidence / ambiguous or partial identity / unknown or uncomparable ticket state / resolved without a claim             | none; record the missing evidence                                                                                      |

Triage rules worth knowing:

- **Uncomparable tickets block creation in their environment.** A same-environment ticket
  whose chain has no structured semantics and that has no non-blank fingerprint alias
  sends every would-be-`new` observation in that environment to `unresolved`, naming the
  ticket(s) in `neededEvidence`. Backfill a normalized chain or an alias on legacy
  tickets, or new findings in that environment stay in triage.
- **Partial overlap is a sparse, state-independent subsequence check.** A chain that is
  an in-order subsequence of (or contains) another same-environment chain, whether on an
  existing ticket of any state or another positive in the same run, is ambiguous and goes
  to triage rather than a speculative ticket (E1-18). This is deliberately conservative.
- **Triage wins over replay.** A replayed observation (already-processed `eventId` or
  key) that lands in one of the triage branches above reports `unresolved` rather than
  `[none]`. Both propose no write, so idempotency holds; the retry only shows as a
  `partial` batch.

The output is an **action proposal, not proof of delivery.** It never reports a resolved
ticket as written, never claims a reopen succeeded, and never turns a non-observation or an
edge block into an absence/fixed claim.

## Verification

```
node attack-runner/planner/run-fixtures.mjs     # deep-equal vs authored expected + invariants + round-trip + mutation self-test + structural-reject
node attack-runner/planner/check-fixtures.mjs   # dependency-free branch-coverage + invariant guard
node attack-runner/planner/mutation-test.mjs    # convergence gate: applies single-line source mutations, requires 0 unexpected survivors
```

JSON Schema validation is a separate step (ajv is not a repo dependency). The oracle writes
each actual output to a temp dir; validate inputs, expected, and actual outputs with:

```
npx ajv-cli@5 validate --spec=draft2020 -s attack-runner/planner/schema/planner-input.schema.json  -d "attack-runner/planner/fixtures/*/input.json"
npx ajv-cli@5 validate --spec=draft2020 -s attack-runner/planner/schema/planner-output.schema.json -d "attack-runner/planner/fixtures/*/expected.json"
npx ajv-cli@5 validate --spec=draft2020 -s attack-runner/planner/schema/planner-output.schema.json -d "/tmp/aegis-planner-out/*.json"
```

Fixtures carrying a `INPUT_SCHEMA_INVALID` marker hold intentionally out-of-contract input
(to test defensive handling) and are excluded from input-schema validation. `expected.json`
is the full authored output (its `reason`/`matchReason` are ignored by the oracle).
