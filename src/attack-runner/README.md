# Attack Runner ticket planner

This command reads one normalized test-run record. It writes a plan for ticket actions and the run summary. It does not connect to Strix, Linear, Google Cloud Storage, or another network service. It does not apply the planned actions.

## Run

Use Node.js 24, as recorded in the repository's `.node-version`. Both the planner CI and the existing Claude review workflow read this file to select Node.js before running checks.

From the repository root:

```sh
yarn attack-runner plan \
  --input test/attack-runner/fixtures/new-cross-tenant-export.json \
  --output new-plan.json
```

The command reads JSON from `--input`. It writes JSON to `--output`. If `--output` is absent, it writes JSON to standard output.

The command does not replace an existing output file. If another write error creates an incomplete file, the command tries to remove it. The error states when removal fails and incomplete output may remain.

## Input

The input must contain these top-level fields:

- `schemaVersion`: must be `1`.
- `run`: run identity, authorization, tool, model, budget, deadline, session, and assessment data.
- `sessionEvents`: ordered session evidence.
- `coverage`, `observations`, and `retests`: assessment results and evidence references.
- `existing`: relevant existing tickets.
- `processedActions`: external actions that were applied or have an unknown result.

`run` requires `id`, `pathId`, `instructionsRevision`, `instructionsSha256`, `operatorId`, `evidencePrefix`, `evidenceRetentionPolicyRef`, `environment`, `authorizedTargets`, `harness`, `model`, `budgetUsd`, `deadline`, `session`, and `assessment`. `run.stopReason` and `run.edgePolicyRef` are optional. `run.model.effort` is optional.

The input must not contain a password, session cookie, magic link, or other credential. See [`contract.mjs`](contract.mjs) for the complete input checks and [`new-cross-tenant-export.json`](../../test/attack-runner/fixtures/new-cross-tenant-export.json) for a runnable example.

Each causal step must include `actorTenantRef` and `resourceTenantRef`. These structured fields define the tenant relationship used for exploit identity. Each value is an opaque identifier. The planner compares the values only for exact equality and never searches for them in prose. When a prose field must describe a tenant relation, use the exact `{actorTenant}` or `{resourceTenant}` placeholder. Tenant-like variants such as `{ActorTenant}` are invalid. Other brace text, such as the route template `{exportId}`, is ordinary prose. Identity uses the relative tenant relation. The proposed ticket expands the two tenant placeholders to concrete references for its human reader.

Each step identity includes the complete meaning of its prerequisites. Fingerprints use version `v3`. Existing tickets retain their exploit ID when their stored chain matches; an older fingerprint alone is not enough to establish a match. Step evidence merges only when there is one matching step in each chain. Otherwise, the evidence remains at ticket level.

Each source observation must have a unique `observationId` within the run. All copies of a duplicate ID stop for review, including a valid copy whose duplicate is invalid. Retest citations use the exact source observation ID. Each observation decision includes the raw input ID as `sourceObservationId` when that ID is a string. Invalid observations also include their input array index as `inputIndex`. An invalid observation has no `observationId` when its raw ID is not a string or is not well-formed Unicode. Unsplit output IDs, including invalid observations, use `encodeURIComponent(observationId)`. For findings split into independent causes, output IDs use `encodeURIComponent(observationId)#encodeURIComponent(causeId)`; retests still cite the source ID.

A blocked retest decision lists the exact raw source IDs in `unsupportedObservationIds`. These are the citations that have no resolved cause matching the retested exploit, or that refer to invalid observations. Other causes from a supporting source keep their own decisions.

A `validated` session event must set `actorRole` to `non-admin-developer`.

## Exit codes

| Code | Meaning                                                                                            |
| ---- | -------------------------------------------------------------------------------------------------- |
| `0`  | The planner processed all items.                                                                   |
| `1`  | The arguments are invalid, the input file cannot be read or parsed, or shared run data is invalid. |
| `2`  | The planner produced a plan, but one or more items need review.                                    |
| `3`  | The planner could not write the requested output file. It prints the reason to standard error.     |

## Acceptance test references

Test names describe the behavior first. The `E1-xx` suffixes map to the stable cases in [Offline planner acceptance](../../docs/aegis/review/acceptance.md#offline-planner-acceptance). For example, `E1-01` covers a new confirmed exploit and `E1-04` covers no ticket change when an exploit is not observed after an engineer resolves it. Related cases may share one test. These IDs are traceability labels, not fixture names or a claim that integration criteria pass.

The `new-cross-tenant-export.json` fixture describes an unauthorized export read after an authorized metadata request. Its run, session, observation and evidence IDs are named for that scenario. All values are synthetic.

Retests must name an existing exploit or an eligible new exploit proposal. Their
target surface must match the exploit's normalized surface or a reviewed identity
alias. Unknown exploits and surface mismatches require review and cannot produce
a `not_observed` result.

`summary.proposedExploitIds` lists exploit IDs with a proposed create action.
These are not assigned Linear issue IDs. A decision's `issueId`, when present,
comes from the supplied existing-ticket record.
