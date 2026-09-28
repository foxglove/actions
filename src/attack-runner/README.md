# Attack Runner ticket planner

This command reads one normalized test-run record. It writes a plan for ticket actions and the run summary. It does not connect to Strix, Linear, Google Cloud Storage, or another network service. It does not apply the planned actions.

## Run

From the repository root:

```sh
yarn attack-runner plan \
  --input test/attack-runner/fixtures/F1-new.json \
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

The input must not contain a password, session cookie, magic link, or other credential. See [`contract.mjs`](contract.mjs) for the complete input checks and [`F1-new.json`](../../test/attack-runner/fixtures/F1-new.json) for a runnable example.

Each causal step must include `actorTenantRef` and `resourceTenantRef`. These structured fields define the tenant relationship used for exploit identity. Each value is an opaque identifier. The planner compares the values only for exact equality and never searches for them in prose. When a prose field must describe a tenant relation, use the exact `{actorTenant}` or `{resourceTenant}` placeholder. Tenant-like variants such as `{ActorTenant}` are invalid. Other brace text, such as the route template `{exportId}`, is ordinary prose. Identity uses the relative tenant relation. The proposed ticket expands the two tenant placeholders to concrete references for its human reader.

A `validated` session event must set `actorRole` to `non-admin-developer`.

## Exit codes

| Code | Meaning                                                                                            |
| ---- | -------------------------------------------------------------------------------------------------- |
| `0`  | The planner processed all items.                                                                   |
| `1`  | The arguments are invalid, the input file cannot be read or parsed, or shared run data is invalid. |
| `2`  | The planner produced a plan, but one or more items need review.                                    |
| `3`  | The planner could not write the requested output file. It prints the reason to standard error.     |
