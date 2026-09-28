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

The input must contain:

- The run ID and approved environment.
- The instruction-file hash.
- The private evidence location.
- The test coverage and stop reason.
- The findings and their evidence references.
- The relevant existing tickets.
- External actions that were applied or have an unknown result.

The input must not contain a password, session cookie, magic link, or other credential. See [`contract.mjs`](contract.mjs) for the complete input checks and [`F1-new.json`](../../test/attack-runner/fixtures/F1-new.json) for a runnable example.

## Exit codes

| Code | Meaning                                                                                            |
| ---- | -------------------------------------------------------------------------------------------------- |
| `0`  | The planner processed all items.                                                                   |
| `1`  | The input file or shared run data is invalid. The planner does not produce a plan.                 |
| `2`  | The planner produced a plan, but one or more items need review.                                    |
| `3`  | The planner could not write the requested output file. It prints the error code to standard error. |
