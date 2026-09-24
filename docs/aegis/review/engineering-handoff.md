# Attack Runner engineering handoff

This document translates the proposed product behavior into implementation boundaries, inputs/outputs, and evidence needed to ship. It is not a second product specification. Update the product documents when behavior changes; keep work status in implementation issues and PRs.

**Review audience:** Automated reviewers are encouraged to review this handoff and the [acceptance criteria](acceptance.md) as technical review targets. Check consistency, missing interfaces, failure/retry behavior, unproven assumptions, and gaps in verification. Human review of these two documents is optional. Raise a focused product question when a genuine decision is missing; routine implementation choices do not require a separate human approval gate.

## Product contract

Read [Attack runner](../../../product-docs/attack-runner.md), [Exploit findings](../../../product-docs/exploit-findings.md), [Attack sessions](../../../product-docs/attack-sessions.md), and [Attack paths](../../../product-docs/attack-paths.md), including their References. The [instructions file](../attacks/authenticated-access-chains/instructions.md) owns first-path mechanics. The product documents contain the [run/session lifecycle](../../../product-docs/attack-runner.md#run-and-session-lifecycle), [ticket lifecycle](../../../product-docs/exploit-findings.md#ticket-lifecycle), and [finding reconciliation and delivery](../../../product-docs/exploit-findings.md#finding-reconciliation-and-delivery) diagrams. The PR description provides proposal context, not the canonical behavioral contract.

Preserve these invariants in implementation:

- One complete ticket per independently actionable exploit, irrespective of repository; identity follows evidence-backed causal boundaries and transitions rather than wording.
- A non-observed exploit is not proven absent or fixed. Engineer-resolved tickets receive no writes for non-observation; only the run summary records coverage and stop reason.
- Confirmed contradiction of a fix claim reopens the same closed ticket with evidence. Unknown or failed delivery is not reported as successful.
- Count a confirmed exploit once per distinct run; replay does not increment it. Unknown historical counts stay unknown.
- Establish a fresh magic-link login immediately, then preserve the same cookie session with verified maintenance. Stop on session loss and retain completed evidence.
- Keep runtime settings interchangeable. Sonnet-4-8 is the selected assessment default; verify its provider identifier and pinned Strix support rather than silently substituting.
- Produce the run summary artifact. Slack delivery is deferred.

## Recommended implementation sequence

Build a small deterministic offline planner first. It consumes synthetic run observations and existing-ticket snapshots and emits proposed actions, with no external writes. This makes identity, evidence, and lifecycle rules testable before integration. Investigate authentication and harness compatibility early so feasibility problems surface before substantial integration work. This is an implementation recommendation, not an intermediate product release.

| Stage                    | Deliverable                                                                                     | Exit evidence                                                                               |
| ------------------------ | ----------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| Contract and feasibility | Concrete schema/entry point, representative fixtures, documented auth/harness findings          | No incompatible interface assumptions; unresolved dependencies explicit                     |
| E1 offline planner       | Reconciliation code, synthetic fixtures, tests, and runnable examples                           | Planner acceptance cases pass; E1-16 records final-revision checks and review evidence      |
| E2 integration           | Authentication and harness adapters, normalized observations, Linear delivery, summary artifact | Controlled integration acceptance, including retries and partial failures                   |
| Release                  | Weekly/manual workflow, bounded operation, evidence handling                                    | Verified target scope, full-duration session continuity, usage limits, and end-to-end trace |

The complete shipping product remains the weekly/manual service. Scope implementation changes to foxglove/actions. If an existing external interface is insufficient, record the required other-repository change as a separate dependency instead of silently expanding this change. Documentation review alone does not launch live assessments.

## Offline planner contract

Define the concrete input/output schema, entry point, and test fixtures before implementing the planner and adapters. They must implement the product decisions linked above. Specify which inputs are already normalized and which matching or normalization decisions the planner owns; do not hide untested identity decisions at an undocumented boundary.

Inputs describe one assessment run, normalized observations, relevant existing issue snapshots, explicit observation and execution/coverage results, and previously processed event identities. Required meaning includes:

- Run identity and evidence location; completion/session/coverage information sufficient to judge each observation.
- Exploit identity, target environment, affected surfaces, severity, and production-impact assessment; ordered activity-chain evidence, remediation, and fix-verification expectations. Affected repositories/components are optional metadata, not a required matching key.
- Existing issue identity and whether it is still open, explicitly claimed fixed, or unknown; a reference identifying the fix claim when applicable.
- Re-test target/identity, what was attempted and observed, execution/coverage status, and stop reason. Non-observation never asserts that the exploit is absent or fixed.
- Previously processed run/finding identities for replay handling.

Engineering documents one concrete JSON/API shape shared by the planner and its adapters. Vendor issue status strings must be mapped explicitly at the adapter boundary. The offline planner receives normalized states, not a guessed interpretation of a title or “Done” label.

Outputs contain a per-finding decision, reason, evidence references, target issue or new-issue proposal, and proposed evidence/counter/lifecycle changes and summary entries. Incomplete decisions contain a reason and needed evidence, with no misleading resolved/fixed action. Emit machine-readable results plus a short runnable example. The output is an action proposal, not proof of successful delivery.

| Evidence and issue state                                                    | Product outcome                    | Proposed action                                                                                                                                                                                                                     |
| --------------------------------------------------------------------------- | ---------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Valid confirmed positive; identity established; no match                    | new                                | Propose one exploit ticket with the full activity chain, remediation, and required evidence, regardless of affected repositories                                                                                                    |
| Valid confirmed positive; exactly one open match                            | rediscovered (still open)          | Append evidence and count this run once; no Slack event                                                                                                                                                                             |
| Valid confirmed positive; exactly one explicit fix claim                    | claimed-fixed but still reproduces | Append evidence, identify the claim, and propose reopening the same ticket if closed; no duplicate ticket                                                                                                                           |
| Run ends without observing a tracked exploit                                | not observed in this run           | Record attempts, conditions, coverage, evidence references, and stop reason in the run summary. A resolved ticket receives no comment, attachment, counter change, or lifecycle update; no absence/fixed claim or automatic closure |
| Invalid evidence, ambiguous identity, or unknown state required for a write | unresolved processing              | Explain the missing evidence; no speculative creation, merge, or lifecycle action. Interrupted coverage alone does not invalidate an independently confirmed positive                                                               |

A session lost after a completed positive observation does not erase that observation. Process independently valid evidence while marking unfinished coverage as interrupted. When no exploit was observed, retain that scoped observation separately from the execution status. Never translate overall run failure into “everything still exists” or “everything is fixed.”

Determinism means equal normalized input and prior-event state produce the same logical plan. Stable ordering is useful, but tests should assess semantic results rather than incidental field order. The planner is not required to provide distributed exactly-once delivery; Engineering 2 must persist deduplication state and coordinate actual writes.

## Engineering discovery and release dependencies

| Dependency                  | Evidence needed                                                                                                                                                                                       | Needed by                                |
| --------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------- |
| Unattended authentication   | Choose and validate a supported party issuance/delivery/retrieval path; identify the required access without committing credentials. The normal app route returns success, not a raw token.           | E2                                       |
| Cookie continuity           | Verify the actual maintenance operation, server cookie updates, and authentication beyond 15 minutes through the full configured duration. `/v1/me` or last-seen activity alone is not renewal proof. | E2                                       |
| Harness and model           | Pin a Strix release/commit, validate provider/model/effort support and instruction-file handling, resolve Sonnet-4-8 to the exact supported provider identifier, and fail explicitly if unavailable.  | E2                                       |
| Spend and cancellation      | Demonstrate measured usage and timely stopping, including cleanup time; unsupported hard limits block live release.                                                                                   | E2/release                               |
| Linear mapping and delivery | Confirm destination team, label/status/fix-claim mapping, historical counts, stable exploit identity, durable deduplication, and recovery after an uncertain write.                                   | E2                                       |
| Summary output              | Define the artifact format, ticket-link fields, actual-versus-proposed delivery states, and notification-eligibility deduplication; Slack transport is deferred.                                      | E2                                       |
| Evidence handling           | Choose artifact access, redaction, retention, and cleanup; this GitHub repository is public, so restricted operator details must not enter a public change.                                           | Before publication/release as applicable |
| Controlled environment      | Identify authorized target set, test accounts/data, and maintenance restrictions for validation.                                                                                                      | E2/release                               |

These are engineering evidence requirements, not a request to reopen the corrected product scope. No live minting, assessment, or delivery has been performed.

## Concurrent delivery

A retry after an uncertain write and two independent runs racing to create the same exploit ticket are different cases. Choose a coordination mechanism before integration, such as serialized reconciliation or durable identity/event coordination. Preserve one ticket per exploit while counting each independently confirmed run once. A failed reopen must not be recovered by creating a replacement ticket.

Add a controlled concurrent-run test once the mechanism is defined: two runs identify the same new exploit, or both contradict a fix claim, while one delivery loses its acknowledgment. Verify ticket uniqueness, per-run counts, correct final lifecycle, and honest summaries. The current I-06 retry criterion does not by itself prove concurrent behavior. The concrete concurrency mechanism and additional test remain engineering work; no claim of verification is implied.

## Verification and completion

Turn the [acceptance criteria](acceptance.md) into executable tests at the appropriate boundaries. Use semantic assertions and representative fixtures, including paraphrases, independent failures with similar titles, partial chains, replay, and resolved-ticket non-observation. Keep expected outcomes tied to the product rules rather than mirroring the implementation.

Deliver the code revision, input/output examples, applicable criterion results, exact verification commands and exit outcomes, and unresolved limitations. Reassess applicable checks after changes to the delivered code. Mark integration cases not yet run as untested; do not present fixture success as proof of real session lifetime, enforced spend limits, or successful external delivery.

Completion requires the relevant acceptance cases and repository checks to pass with no unresolved material defect. Automated review can supply findings and verification; optional human review of this document does not waive implementation correctness or the established product-review process.
