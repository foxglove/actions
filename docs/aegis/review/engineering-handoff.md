# Attack Runner engineering handoff

Prepared for human design review. The decision register records product choices already incorporated; the proposed schema, sequencing, and engineering discoveries remain to be reviewed. It is a temporary review aid; after review, move accepted lasting decisions into the appropriate product document and move build work into the change proposal or work tracker. Do not maintain a second permanent specification here.

## Product decision register

Kumar's review resolves the following product choices. The package remains a draft for further review; these decisions are not implementation or publication approval.

| ID            | Review result                                                                                                                                                                                                   | Lasting location                       |
| ------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------- |
| PM-1          | Sequencing recommendation explained below; not yet accepted.                                                                                                                                                    | Implementation work plan               |
| PM-2          | Replace “no longer reproduces” with “not observed in this run,” with coverage and stop reason. No test grants a clean bill of health.                                                                           | Exploit findings                       |
| PM-3          | Accepted: never automatically close a ticket because a run did not observe the exploit. Resolved tickets remain untouched; non-observation, interrupted, and not-attempted coverage go only in the run summary. | Exploit findings                       |
| PM-4 / PM-6   | Exploit identity and full chain/remediation are independent of repository. Deduplicate structured causal chains before opening tickets.                                                                         | Exploit findings                       |
| PM-5          | Accepted: one confirmed count per exploit per run; replay does not increment; unknown history remains unknown.                                                                                                  | Exploit findings                       |
| PM-7          | Accepted event eligibility and suppression policy. For now produce a summary output, including tickets opened; Slack delivery is deferred.                                                                      | Exploit findings                       |
| PM-8          | Corrected: contradictory confirmed evidence reopens the same closed ticket and adds new evidence; already-open tickets remain open. Do not create a duplicate.                                                  | Exploit findings                       |
| Default model | Sonnet-4-8 is the selected assessment default. Exact provider identifier and pinned-harness compatibility require verification, not a new model choice.                                                         | Attack runner                          |
| Names         | Accepted: Attack Runner and Authenticated Access Chains.                                                                                                                                                        | Product documents and instruction path |

## PM-1: implementation order, not product scope

The recommendation is to build and compare a small offline reconciler before wiring it to live assessment and Linear. It reads synthetic run results plus existing-ticket snapshots and outputs what it would create, update, reopen, count, or leave unresolved. It makes no external writes. This isolates the difficult ticket-identity and evidence rules and lets us test paraphrases, partial chains, replay, and claimed fixes cheaply and repeatably.

After that passes, connect the same logic to the authentication/harness adapters, actual Linear writes, and summary artifact. The first shipping product remains the complete weekly/manual service. This does not call for a factory framework or a production intermediate release. Authentication and model compatibility can be investigated early to expose feasibility problems; they do not need to wait for the comparison.

The choice requested from Kumar is simply whether to use this implementation order or start with one thin live end-to-end path. The offline-first order gives a fairer code-setup comparison and exercises deduplication first. A thin live path instead exposes integration problems sooner but makes initial correctness and cost comparisons noisier. Recommendation: keep offline-first, with early bounded authentication/harness feasibility checks. PM-1 remains a recommendation until Kumar decides; no renewed approval is needed for the product choices above.

## Proposed delivery sequence

| Stage               | Deliverable                                                                            | Exit evidence                                                                                            |
| ------------------- | -------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| Kumar review        | Product docs, runtime instructions, pending choices, acceptance                        | Kumar reviews the remaining proposals and requests changes or accepts them                               |
| Human design review | A cohesive change proposal built from these document edits                             | Kumar initiates review; reviewers resolve product choices before acceptance                              |
| E1 comparison       | Offline planner, synthetic fixtures, tests, examples                                   | Reviewed shared contract and E1 acceptance on the final delivered revision                               |
| E2 integration      | Authentication and harness adapters, normalization, Linear delivery and summary output | Controlled integration acceptance, including retries and partial failures                                |
| Release             | Weekly/manual workflow and bounded operation                                           | Verified target authorization, session continuity, usage limits, artifact handling, and end-to-end trace |

The complete product remains the weekly service. E1 is a proposed way to start implementation, not a reduction of shipping scope. Do not implement or run the service from this review packet alone.

## Proposed offline contract

The concrete schema and implementation sequencing remain draft recommendations. They must implement the accepted product policies above. Freeze one concrete schema and fixture contract for both comparison routes before comparison.

Inputs describe one assessment run, normalized observations, relevant existing issue snapshots, explicit observation and execution/coverage results, and previously processed event identities. Required meaning includes:

- Run identity and evidence location; completion/session/coverage information sufficient to judge each observation.
- Exploit identity, target environment, affected surfaces, severity, and production-impact assessment; ordered activity-chain evidence, remediation, and fix-verification expectations. Affected repositories/components are optional metadata, not a required matching key.
- Existing issue identity and whether it is still open, explicitly claimed fixed, or unknown; a reference identifying the fix claim when applicable.
- Re-test target/identity, what was attempted and observed, execution/coverage status, and stop reason. Non-observation never asserts that the exploit is absent or fixed.
- Previously processed run/finding identities for replay handling.

Engineering chooses the concrete JSON/API shape once, before the comparison, and documents it for both workers. Vendor issue status strings must be mapped explicitly at the adapter boundary. The offline planner receives normalized states, not a guessed interpretation of a title or “Done” label.

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

## Proposed comparison and quality gate

The proposed coding routes are A: Astra High and B: Sol Medium. These build the implementation; Sonnet-4-8 is the separate runtime assessment model and stays fixed across controlled integration comparisons. Both receive the same approved design, technical input/output contract, base revision, fixtures, dependencies, and execution instructions in isolated workspaces. The [bakeoff protocol](bakeoff.md) defines the required launch record, review, attempt limits, and cost accounting; the [worker template](agent-task.md) supplies the bounded assignment. Publish acceptance expectations to both; QA may add unseen data variations only within those published requirements. Apply the same review rubric and tests to both. Give both any product clarification before scoring. Record specification changes and re-evaluate affected results.

Quality is the eligibility gate: all E1 cases pass, required repository checks pass, and no unresolved material defect remains on the evaluated revision. Among eligible routes compare total attempted cost, repair rounds, human intervention minutes, and elapsed time. Record unknown billing as unknown. One feature selects a provisional route; it does not establish general model superiority.

## Keeping the comparison useful

Use two routes first, not three by default. Add a third only if the first two expose a specific unanswered capability or cost question. Supply the same small relevant context bundle and stable instructions to both; preserve prefix caching where the provider supports it. Do not claim cache savings without observed usage data. Reuse the common acceptance harness and compare total attempted cost, including failed attempts, review, and repairs. Do not rerun broad research or the full test suite after an editorial-only change.

The first slice needs a shared contract and evidence capture, not a general-purpose factory platform. Build additional orchestration only when repeated runs demonstrate a concrete bottleneck.
