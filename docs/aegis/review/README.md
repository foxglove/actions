# Attack Runner review packet

**Prepared for human review; approval pending.** This packet incorporates Kumar's product review and covers changes only to foxglove/actions. Start with the [human review brief](human-review.md), then inspect the linked decisions and acceptance. The package is prepared as a draft PR for Kumar to inspect before human reviewers are requested. No implementation or live assessment has started.

Aegis is the whole initiative. Attack Runner is the accepted name for this project within Aegis / Attack. Authenticated Access Chains is the accepted first attack-path name.

## Review contents

| Artifact                                                                       | Purpose                                                                                |
| ------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------- |
| [Attack runner](../../../product-docs/attack-runner.md)                        | Outcome, scope, cadence, interchangeable settings, and run record                      |
| [Attack sessions](../../../product-docs/attack-sessions.md)                    | Fresh-link establishment, cookie continuity, maintenance, and failure behavior         |
| [Attack paths](../../../product-docs/attack-paths.md)                          | Named Git-tracked paths and the harness instruction contract                           |
| [Exploit findings](../../../product-docs/exploit-findings.md)                  | Repository-independent identity, full exploit chains, and corrective work              |
| [Runtime instructions](../attacks/authenticated-access-chains/instructions.md) | Exact proposed first-path instructions passed to the harness                           |
| [Engineering handoff](engineering-handoff.md)                                  | Remaining PM choices, discovery, sequencing, and two-route comparison                  |
| [Acceptance criteria](acceptance.md)                                           | Preserved E1 and integration scenarios with observable outcomes                        |
| [State diagrams](state-diagrams.md)                                            | Run, exploit, and delivery states with every acceptance criterion mapped               |
| [Human review brief](human-review.md)                                          | Scope, focused reviewer questions, approval boundaries, and response template          |
| [Bakeoff protocol](bakeoff.md)                                                 | Common inputs, independent attempts, quality gates, cost accounting, and repair limits |
| [Worker task template](agent-task.md)                                          | Bounded post-approval assignment; required launch fields are not yet filled            |

## What changed from the earlier draft

- Aegis remains the initiative; the project and first attack path have distinct names.
- A ready worker obtains a fresh magic link and immediately establishes a session. It keeps the same cookie session alive beyond link expiry and through the assessment.
- The mint/retrieval and actual renewal mechanisms are engineering discoveries to prove, not invented endpoint choices.
- Harness, model, instructions, budget, and time are independently configurable. Strix OSS is first; Sonnet-4-8 is the selected default assessment model. Engineering verifies its exact provider identifier and adapter support.
- Tickets represent complete exploits irrespective of repository. Every ticket carries the activity chain, required fixes, and end-to-end verification. PM-4 and PM-6 have been revised accordingly.
- PM-2 now reports “not observed in this run,” with coverage and stop reason; a test never certifies that an exploit is absent or fixed. PM-3 and PM-5 are accepted: no automatic closure and one confirmed count per run. Non-observation leaves engineer-resolved tickets untouched; attempted, interrupted, or not-attempted coverage appears only in the run summary.
- PM-7 produces a summary artifact including tickets opened/reopened/updated; Slack delivery is deferred. PM-8 reopens the same ticket when new evidence contradicts a fix claim.
- Structured causal chains drive deduplication before ticket creation; prose differences alone do not change exploit identity. The concrete normalization/schema implementation remains for engineering review.
- PM-1 is explained as an implementation-order choice in the handoff. The product is still the complete weekly/manual service. Stages and acceptance criteria remain outside evergreen product documents.

## How Roman's approach is applied

The four flat `product-docs/*.md` files describe lasting intended behavior in present tense, with reasons, shared contracts, product dimensions, and explicit dependencies. They contain no author, status, rollout plan, or open-question section. Present tense describes intent; it is not evidence that behavior is built or that this draft has been accepted.

This review directory contains the local human-review packet. Its motivation, choices, and delivery sequence can form the eventual PR description and implementation work items. Accepted lasting decisions move into product docs. The proposed document edits are the change proposal; this packet must not become a parallel evergreen specification.

Runtime instructions retain the requested `docs/aegis/attacks/` location because the harness consumes them as versioned assets. This adapts Roman's app-repository convention to this repository; it does not import all of `foxglove/app`'s documentation policy or introduce a global agent policy.

For future behavioral changes, edit the relevant product doc before or with implementation and review its direct dependents. Dependency changes propagate only when they change a dependent's decisions. Keep review discussion, test evidence, and rollout work separate from enduring behavior.

## Source authority and review boundary

Kumar's latest corrections take precedence over conflicting older Drive text. In particular, discard per-repository ticket splitting, app-only ticket eligibility, the old path name, and any instruction to reopen an expired magic link. Source documents are historical inputs and have not been edited.

The corrected requirements and previously locked source scope populate the product documents. Auth issuance/renewal, exact model mapping/support, retention, and external state handling still require the evidence identified in the handoff. The updated observation and reopening policies supersede the source's older outcome language and the previous PM recommendations. Do not merge unresolved behavior as if it were accepted, and do not start implementation before the requested review sequence.

Repository baseline inspected: `79830ef8e1aa16d482ceedfaa985ee3ede1ed6cd`. These additions contain documentation only. The workflow named in the product doc does not yet exist.

## Sources

- [Roman's evergreen product-doc discussion](https://foxglove.slack.com/archives/C0C2VE27PUM/p1790117488852189).
- [Product-doc convention proposal, app PR 19116](https://github.com/foxglove/app/pull/19116).
- [Embedded viewer example, app PR 19120](https://github.com/foxglove/app/pull/19120).
- [Project Aegis](https://app.notion.com/p/foxglovehq/Project-Aegis-3e4cbc8e56a381caa0e4eeaeec1c5164).
- [Original shipping scope](https://docs.google.com/document/d/1C210loxpi1wWnBlFIbxKNfUFHGHVXyxejv2pCRAZFfE/edit).
- [Original locked decisions](https://docs.google.com/document/d/1f2cnN_GPa7IXF1d0KbaICKEkteVgkHiAKjiPtncD3Co/edit).
- [Original design](https://docs.google.com/document/d/1Rk_8QTrlz9_h95B-DSOeSQqi3pfwu6q4bZRtT2KOuqI/edit).
- [Original instructions](https://docs.google.com/document/d/1V4VFVgS4Itrox7K1y3u0r26yY_VLfXmIYKd2em0OJxE/edit).
