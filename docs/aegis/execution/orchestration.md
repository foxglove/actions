# Orchestration decision evidence

Inspected 2026-09-25. This is evidence for Developer's architecture choice, not proof that any new workload is deployed. Final choices belong in execution-plan.md.

## Repository evidence

- Foxglove already has Temporal. [infra/stacks/console/temporal.tf](https://github.com/foxglove/infra/blob/fd924e0d85f952e7a0ef2269a89a1043db1d0f14/stacks/console/temporal.tf), fetched directly from GitHub, defines a per-environment Temporal Cloud namespace, API-key authentication, 30-day history retention and per-service accounts. Source declarations do not verify the current deployed namespace, credentials or service ownership.
- [app managed-execution worker](https://github.com/foxglove/app/blob/1d3459dceb5c438db22f5877312e428a1668dba7/packages/managed-execution/src/worker.ts), fetched directly from GitHub, registers an explicit activity bundle on the `managed-execution` queue. It is not an arbitrary shell-job endpoint. Local app snapshot `b2678ef3781af1578bec4501630dd50307011fb0` exports only `managedExecutionWorkerPing` from that bundle; this last observation is local, not a current remote inventory.
- At the same local app snapshot, `packages/temporal-workflows-worker/src/worker.ts` registers workflow exports on `foxglove-workflows`. Existing deployment patterns are reusable references; adding an assessment worker still requires explicit registration, identity, deployment and isolation.
- Approved Attack Runner product prose requires one bounded weekly/manual run, distinct assessment/reconciliation/delivery status, and safe retry with surviving original identities/evidence. It explicitly excludes a later automatic report-recovery service. It does not require live attack continuation after worker death. Do not invent that requirement to justify a workflow platform.

## Meaningful options

| Option                                                 | Reuse and benefits                                                                                     | Remaining work and cost                                                                                                                                                        | Judgment for this release                                                                                                            |
| ------------------------------------------------------ | ------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------ |
| GitHub Actions dispatch/schedule + bounded runner      | Matches required actions workflow entry point; process owns one assessment; existing failure/cancel UI | Explicit persistent ticket-action journal and private evidence; crash recovery is bounded/manual; runner isolation still required                                              | Recommended baseline if Developer can keep recovery small and concrete                                                               |
| Temporal orchestration + dedicated assessment worker   | Existing organizational platform; durable step progression, activity retries and checkpoint primitives | Worker registration/deployment and scoped service identity; payload/log privacy; handle cancellation and external effects; changes outside actions are deployment dependencies | Credible alternative, not dismissed as a new platform; select if a concrete requirement removes more custom machinery than this adds |
| New generic workflow framework or another job platform | No established benefit over the two above for this contract                                            | Another integration and operational owner; same external-effect semantics remain                                                                                               | Do not introduce without evidence of a requirement the first two cannot meet                                                         |

Recommendation is an engineering inference from the bounded product contract, not a comparative benchmark. If the chosen plan grows automatic multi-stage recovery, multi-worker coordination or long-lived waits, reconsider Temporal before building that engine ourselves. Temporal does not remove causal finding matching, Linear delivery reconciliation or app authentication integration.

## Specific implementation consequences

GitHub currently documents IANA timezone scheduling. Use the following as the intended workflow schedule, then verify GitHub accepts the workflow before enabling it:

```yaml
on:
  schedule:
    - cron: "0 9 * * 1"
      timezone: America/Los_Angeles
  workflow_dispatch:
```

Do not build dual UTC cron entries and custom DST switching. GitHub schedules can be delayed or dropped, and public-repository inactivity can disable them. Preflight must validate current operator coverage at actual start, not infer availability from the scheduled time. This schedule is not an exact-start SLA. [GitHub schedule documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)

For Temporal, put side effects in Activities and define retries deliberately. Activity retries need idempotent application behavior; heartbeat details support checkpoints but do not preserve a browser process or cookie jar automatically. Never retry the whole pentest invisibly as if it were the same uninterrupted observation. An unknown Linear acknowledgment still needs readback/reconciliation. [Temporal Activities](https://docs.temporal.io/activities), [workflow replay](https://docs.temporal.io/workflow-execution)

A Temporal-based alternative should use a dedicated assessment queue/worker with a metadata-only workflow payload and private evidence references; source code can live in actions, but worker deployment remains a named infrastructure dependency. Existing namespace history retention is not a replacement for long-lived finding identity. Existing workers must not receive new attack tooling merely because they already run.

For a small GCS-backed journal, generation preconditions can protect object updates: `ifGenerationMatch=0` for initial creation and the observed generation for replacement; conflicting updates return 412. This is a candidate single-object compare-and-swap mechanism, not a transaction over Linear plus storage. It cannot fence a stale process from writing to Linear. The chosen delivery algorithm must address that boundary separately; do not equate storage CAS or a lease with exactly-once external delivery. [GCS request preconditions](https://docs.cloud.google.com/storage/docs/request-preconditions)

## Verification boundary

Executed: repository reads, GitHub source fetches and current primary documentation reads. No Temporal server, namespace, worker, schedule, GitHub workflow, GCS bucket or external mutation was created or exercised. Developer and reviewers must evaluate the chosen architecture against these facts and mark remaining critical unknowns explicitly.
