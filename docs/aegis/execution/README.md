# Attack Runner execution planning packet

This packet translates the product scope approved in [PR #48](https://github.com/foxglove/actions/pull/48) into implementation, review and QA instructions. It proposes no product code, deployed infrastructure or live assessment. Kumar is the human reviewer for these execution plans; Claude bot should review the whole packet. Additional human review is not required for this planning PR.

## Readiness and reading order

The Developer, Code Reviewer and QA agree that the **offline planner and a bounded local bridge feasibility spike are specified sufficiently to start after plan approval**. The complete live runner is **not yet ready for a one-pass implementation handoff**. Source inspection has narrowed the gaps but has not proved session continuity, complete request provenance, containment or spend enforcement at runtime.

| Document                                           | Purpose                                                                                                         |
| -------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| [Execution plan](execution-plan.md)                | Selected architecture, interfaces, implementation slices and acceptance mapping                                 |
| [Feasibility](feasibility.md)                      | Pinned Strix/app/Linear source evidence, native capabilities, adapter responsibilities and bounded bridge spike |
| [Orchestration](orchestration.md)                  | Actions versus Foxglove's existing Temporal patterns; recommendation and operational limits                     |
| [Code review plan](code-review-plan.md)            | Reviewer checklist, failure boundaries, current findings and readiness verdict                                  |
| [QA plan](qa-plan.md)                              | All 37 acceptance IDs, future commands, fixtures and observable outcomes                                        |
| [Telemetry inventory](telemetry.md)                | Strix analytics, dependency tracing, target-app analytics, service traffic and required opt-outs                |
| [Synthetic input](qa-fixtures/F1-new.example.json) | Literal example for the future offline planner; JSON syntax checked, no implementation run                      |

The selected design is a TypeScript runner with a narrow Python bridge to pinned Strix APIs. Strix performs assessment; our integration manages authentication, evidence attribution, cross-run finding identity, Linear delivery and private reporting. GitHub Actions runs the bounded job. A permanent private GCS journal records ticket actions; it is separate from expiring evidence. Temporal is a real existing organizational option, but the current contract does not require transparent continuation after worker death.

## Remaining gates

1. Select the approved test-account mailbox service/read API and demonstrate immediate one-time login plus supported cookie maintenance.
2. Run the bounded fake-app bridge spike to verify the shared browser session, Caido export before cleanup, request attribution across every enabled tool, proxy-bypass denial and cancellation behavior.
3. Resolve the selected assessment model to an accessible provider ID, immutable sandbox image/dependency lock and a demonstrated hard per-run budget boundary. Strix's native budget check happens after a response.
4. Qualify Linear mappings and lost-acknowledgment recovery, private storage/IAM/retention, operator coverage and edge access in the intended environment.
5. Verify telemetry opt-outs through startup, normal findings, failure, cancellation and cleanup. No optional metrics go to Strix. Source inspection is not a packet capture.

These gates must remain explicit when execution is delegated. An unavailable service, unknown outcome or failed test cannot become an implied pass. All test commands in the packet are future implementation contracts unless explicitly labeled executed.

## Claude review focus

Review the packet against the approved product documents, not only for prose consistency. Report actionable findings with the affected acceptance ID and concrete failure path. Check whether an ordinary SWE-II or an inexpensive qualified coding agent can implement and test the specified slices without inventing architecture. Focus on native Strix reuse, the Python bridge/session lifecycle, valid privilege-escalation evidence, causal ticket identity, uncertain external writes, private evidence, budget limits and telemetry. Distinguish a missing implementation decision from an honestly named live provisioning/qualification gate. Do not infer runtime success from the review verdict.

## Canonical product scope

The merged baseline is `65cd875e6a4feaa1b5ab29f008ea0b73b43b4dce`. These documents remain authoritative:

- [Attack runner](../../../product-docs/attack-runner.md)
- [Attack sessions](../../../product-docs/attack-sessions.md)
- [Attack paths](../../../product-docs/attack-paths.md)
- [Exploit findings](../../../product-docs/exploit-findings.md)
- [Authenticated Access Chains instructions](../attacks/authenticated-access-chains/instructions.md)
- [Acceptance criteria](../review/acceptance.md)
- [Engineering handoff](../review/engineering-handoff.md)

Later runtime clarifications in this packet: disable Strix metrics and inventory other telemetry; preserve the most-capable-permitted assessment-model objective without substituting the model silently. No non-observation establishes that an exploit is absent or fixed. No resolved ticket is changed by a negative result. Exploit-derived higher privileges or credentials remain evidence when their chain starts from the validated non-admin session.
