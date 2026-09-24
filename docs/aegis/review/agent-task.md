# E1 worker task template

This template is for dispatch after human design review and bakeoff preparation. It is not an instruction to start implementation now. Fill the launch record once and give the same task to every contestant. Keep reviewer-only held-out inputs out of contestant workspaces.

## Launch record

```text
Repository: foxglove/actions
Approved design revision and approval reference: REQUIRED
Common starting commit: REQUIRED
Normalized contract/schema and hash: REQUIRED
Shared fixture/oracle location and hash: REQUIRED
Allowed implementation paths: REQUIRED
Required setup/test/check/example commands: REQUIRED
Exact coding model/effort/client configuration: REQUIRED PER ROUTE
Time and monetary ceiling: REQUIRED
Repair-round ceiling: 2 unless changed for all routes before launch
Assigned evaluator: REQUIRED
```

## Task to give the worker

Implement only the offline reconciliation slice in the supplied actions checkout. Read `product-docs/exploit-findings.md`, its References, `docs/aegis/review/acceptance.md` E1-01 through E1-20, and the supplied frozen contract and fixtures. Use `docs/aegis/review/state-diagrams.md` to understand boundaries; the reviewed acceptance and product decisions remain authoritative. Read the runner/session/path documents only as needed to interpret the normalized inputs. Do not reload the originating conversation or research the initiative again.

Produce deterministic semantic decisions for proposed tickets, evidence/count changes, reopening, unresolved triage, and run-summary entries. Preserve the full exploit chain and remediation across repository boundaries. Non-observation is not a fix. An engineer-resolved ticket receives no mutation when its exploit is not observed; that information goes only to the run summary. Confirmed contradiction proposes reopening the same ticket, not creating another. Replays do not duplicate actions or counts.

Operate only within the supplied implementation paths in foxglove/actions. Do not edit another repository, redefine the schema or product decisions, weaken acceptance, or modify the common evaluation fixtures to make your implementation pass. Add focused implementation tests as appropriate. An apparent mistake or missing decision in the frozen contract goes to the coordinator with a minimal failing example; do not silently choose a different behavior.

The planner must make no network calls, read no secrets, and perform no Linear/Slack/harness/workflow actions. Use the supplied development dependency setup; do not investigate live authentication or execute attacks in this slice. Do not add a generic orchestration platform.

Run the required commands on the final revision. Deliver the code diff, an input/output example, a result for every E1 criterion, exact commands and exit results, remaining limitations, and the final commit or patch hash. Distinguish first-pass results from repaired results. Report time, usage/cost where available, cache accounting where exposed, and human interventions. Do not claim missing cost or unrun checks as zero or passing. Independent review determines acceptance.

Stop at the assigned ceilings or an unresolved contract/scope question and return the current diff plus the blocker. No push, PR publication, merge, or deployment is included in this worker assignment.
