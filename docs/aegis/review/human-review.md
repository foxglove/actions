# Attack Runner human review

## Change being reviewed

Approve the intended behavior and implementation boundaries for Attack Runner in **foxglove/actions only**. This change adds product documents, a Git-tracked attack instruction file, acceptance criteria, state diagrams, and review/handoff material. It does not implement or run the service. The existing PR review workflows and prompts are unchanged. No changes to `foxglove/app`, `experimental`, or other repositories are included.

Attack Runner is the weekly/manual party assessment project within Aegis / Attack. It uses a fresh magic link to establish a maintained cookie session, runs a configurable harness/path, and reconciles demonstrated exploits into repository-independent Linear tickets. The first defaults are Strix OSS, Sonnet-4-8, Authenticated Access Chains, $100, and a 60-minute job limit.

Review the proposed behavior as a whole. The product documents express intent, not claims that integrations have been built. No implementation tests or live assessments have run.

## Suggested reading order

1. [State diagrams](state-diagrams.md): three machines and all 32 acceptance criteria mapped.
2. [Attack runner](../../../product-docs/attack-runner.md): scope, configuration, and provenance.
3. [Exploit findings](../../../product-docs/exploit-findings.md): the highest-risk decisions—identity, evidence, counting, and ticket updates.
4. [Attack sessions](../../../product-docs/attack-sessions.md), [attack paths](../../../product-docs/attack-paths.md), and the [instruction file](../attacks/authenticated-access-chains/instructions.md): authentication, target boundary, and runtime behavior.
5. [Acceptance](acceptance.md), [engineering handoff](engineering-handoff.md), and [bakeoff protocol](bakeoff.md): verification and implementation plan.

## Decisions already incorporated from product review

- The project is part of Aegis, not the whole initiative. Names and the Sonnet-4-8 assessment default are selected.
- Redeem a fresh magic link immediately once per run, retain the resulting cookie, and maintain that same session. Do not treat a health check as proof of renewal or reopen the link.
- Every exploit ticket contains its demonstrated chain, what must be fixed, and end-to-end verification expectations. Repository ownership is optional metadata.
- Deduplicate evidence-backed causal chains before creating tickets. Different prose does not mean a different exploit; similar prose does not prove equivalence.
- A run that does not observe an exploit never establishes that it is absent or fixed. E1-04 leaves an engineer-resolved ticket completely untouched. `RunSummaryEntry` writes only to the run artifact, not Linear.
- Confirmed evidence contradicting a fix claim reopens the same closed ticket with the new evidence. Replays do not duplicate tickets, counters, or eligible events.
- Count a confirmed exploit once per run. Unknown historical counts remain unknown.
- Produce the complete run summary, including actual ticket changes and failed/unresolved work. Slack delivery is deferred.

## Focused review requests

| Area                       | Question to resolve                                                                                                                                             | What approval establishes                                                                                                                       |
| -------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| Scope and sequencing       | Is offline reconciliation the first implementation slice, with bounded auth/harness feasibility work early?                                                     | PM-1 implementation order; the shipping product remains the whole weekly/manual service                                                         |
| Exploit identity           | Do causal transitions, boundaries, and corrective outcome distinguish same vs independent exploits adequately? Are ambiguous chains correctly routed to triage? | The behavior to encode in the common schema and fixture oracle                                                                                  |
| Ticket lifecycle           | Are E1-04 no-write behavior, confirmed-evidence reopening, fix-claim episode identity, and unknown lifecycle handling correct?                                  | Expected external side effects and counter semantics                                                                                            |
| Authentication feasibility | Can supported unattended issuance/retrieval and session maintenance be delivered from actions using existing interfaces?                                        | A named engineering discovery task; no invented endpoint and no implicit app-repo change                                                        |
| Delivery races             | Should overlapping scheduled/manual runs serialize reconciliation or coordinate through durable identity/event state?                                           | An implementation strategy and an added integration test for simultaneous creation/reopening; this coverage is not yet explicit in the 32 cases |
| Operating dependencies     | Who resolves Linear mappings, artifact access/retention, model ID compatibility, spend enforcement, and controlled test access?                                 | Named responsibility and required evidence before integration/release                                                                           |

The concurrency test is a proposed addition for review, not a claim that it is already accepted or covered by replay tests. Reviewers should also look for missing scenarios rather than treating the current matrix as exhaustive.

If an auth or other prerequisite requires a change outside actions, record it as a separate dependency. Do not expand this change or ask an implementation worker to modify another repository silently.

## Approval and handoff gates

**Design approval:** Reviewers agree on product behavior, resolve product ambiguities, and record the approved document revision. Feasibility questions may remain as explicitly owned engineering tasks; design approval is not evidence that authentication or budget enforcement works.

**Bakeoff start:** Freeze the common base, schema/entry point, dependencies, fixture inputs/expected results, commands, limits, and scoring rules in [bakeoff.md](bakeoff.md). Product prose alone is insufficient for an implementation comparison. This preparation is still outstanding.

**Implementation acceptance:** Evaluate the delivered revision against the relevant acceptance cases and independent review. A lower-cost worker cannot waive an acceptance criterion, silently change a decision, or declare its own work approved.

**Live release:** Satisfy the integration evidence and operating dependencies in the handoff. Product review does not launch assessments or authorize new target scope.

## Reviewer response

Record this response in the eventual review discussion or an accompanying review record. Do not mark approval here before a person reviews it.

```text
Reviewed revision or packet hash:
Reviewer and review area:
Decision: approve design / changes requested
Blocking findings, with file or acceptance ID:
PM-1 sequence decision:
Delivery concurrency strategy and required test:
Engineering dependencies, responsible person, and stage:
Any decision requiring product follow-up:
```

Approve a specific snapshot. If a subsequent change alters behavior, update the relevant acceptance/diagrams and obtain review of the changed decisions. Editorial fixes need not restart the whole review.

## Validation and publication status

The PR commit identifies the proposed snapshot; an accompanying review export records file hashes and validation results. Documentation formatting, relative links, Mermaid parsing, and the 32-ID coverage map are checked. These checks do not validate the future service.

The packet is prepared as a draft PR for Kumar to inspect first. Keep it in draft and do not request human reviewers until Kumar asks. No Slack message or Linear ticket is part of this change. The review request should point to the changed actions files, not ask reviewers to reconstruct the earlier conversation.
