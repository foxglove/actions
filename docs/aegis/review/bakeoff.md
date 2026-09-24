# Attack Runner implementation bakeoff

## Decision to make

Which coding-agent setup produces acceptable Attack Runner code with the lowest total delivery cost and reasonable human effort? This is a comparison of development setups. The runtime assessment model remains Sonnet-4-8; the bakeoff does not compare attack models or live exploit discovery rates.

This is a proposed evaluation protocol for human review. No implementation trial has run and no winner is established. Model usage for preparing these documents is not a bakeoff result. The $100/60-minute assessment defaults do not fund or limit the coding comparison.

## Keep the first comparison small

Use the offline E1 reconciler as the common task if PM-1 is accepted. It tests ticket identity, non-observation, reopening proposals, counting, and summary decisions without live credentials or external writes. E1 success qualifies a coding setup for this slice; it does not prove skill at auth or production integration.

Retain the previously proposed Astra High reference and Sol Medium challenger as the initial two routes. Confirm available exact model IDs and actual rates before launch. A third, lower-cost route is optional only when it answers a declared question after the two-route screen. Do not assume any route passes because of its model family or price.

Keep the coding client, tool permissions, context, dependencies, and workflow the same if testing model/effort. If a different client, skill, or tool bundle is part of the experiment, label the result a setup comparison and list those differences. Do not attribute the result to model choice alone.

## Freeze before dispatch

The coordinator fills and approves these values before any contestant starts. Empty fields mean the bakeoff is not ready; workers must not each invent their own contract.

| Input                   | Required frozen value                                                                                                                                    | Current state                                                                    |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| Approved intent         | Product/acceptance revision and recorded design approval                                                                                                 | Human review pending                                                             |
| Starting point          | Same actions commit plus exact approved docs snapshot; isolated worktrees                                                                                | Docs baseline is `79830ef8e1aa16d482ceedfaa985ee3ede1ed6cd`; refresh at dispatch |
| Implementation contract | Language/runtime, file boundaries, CLI/API entry point, normalized input/output schema, failure shape, ordering expectations, stable identity/versioning | Not yet defined                                                                  |
| Evidence boundary       | Which fields the planner receives already normalized and which matching/normalization it must implement, with examples                                   | Not yet defined; do not hide matching outside the tested task                    |
| Test oracle             | Shared fixtures and expected semantic decisions for E1-01 through E1-20; independently reviewed                                                          | Not yet executable                                                               |
| Verification commands   | Identical setup, test, static-check, and example commands with locked dependency versions                                                                | Not yet defined; existing docs check uses Prettier                               |
| Agent settings          | Exact model, effort, client version, tools, instructions, context policy, and allowed network/secret access                                              | Proposed routes above; resolve before dispatch                                   |
| Effort limits           | Same wall-clock and monetary ceilings, timeout handling, and repair-round cap                                                                            | Set numeric ceilings before dispatch; proposed maximum two repair rounds         |
| Review setup            | Evaluator identity, rubric, hidden fixture set/hash, and anonymized candidate labels                                                                     | Not yet assigned                                                                 |
| Cost record             | Usage source, price date, cache accounting, shared-cost allocation, and human time measurement                                                           | Not yet configured                                                               |

Develop the test oracle separately from either candidate implementation. Include paraphrases, distinct control failures with similar text, unknown repositories, fingerprint version changes, resolved tickets with no observation, positive evidence before session loss, replay, and a genuinely new fix claim. Expected decisions must be checked by a reviewer familiar with the product rules.

Hold out additional input variations for the same published requirements. Hidden requirements are not permitted. If a test exposes an ambiguous spec rather than a code defect, resolve it once, give both candidates the same clarification, and invalidate the affected comparison results. An offline test can evaluate normalized causal semantics; it does not establish that arbitrary natural-language exploit extraction works.

## Conduct and repair policy

1. Start independent workspaces and fresh task context from the same inputs. Do not give one agent another agent's implementation, diagnosis, or prior solution.
2. Capture each first submitted revision and evaluate it before providing feedback. Preserve first-pass results even if repairs later pass.
3. Give each route the same structured feedback and at most two repair rounds within its fixed ceilings. Score the final revision, not an earlier passing snapshot. Report which held-out cases were disclosed during repairs.
4. Evaluate final candidates with identical checks and independent code review. Hide route names from the reviewer where practical. Use fresh withheld variations within the same published behaviors for final evaluation after feedback.
5. If a route needs a stronger model, freeze its unassisted result first. Record the subsequent attempt as an assisted route and charge all rescue cost to it. It must not be reported as a clean success by the cheaper route alone.

Avoid a single lucky run deciding the standard workflow. Screen each route once. If a cheaper candidate passes, repeat it and the reference from fresh workspaces at least once to check repeatability; randomize or alternate run order. If results disagree, add a paired repeat or report uncertainty rather than a confident winner. Report every attempt, including timeouts and abandoned repairs. Two repeats are a practical pilot, not statistical proof of broad superiority.

## Quality gate and scorecard

A candidate is eligible only when all E1 criteria pass on its final revision, required repository checks pass, there is no external activity forbidden by E1-15, and independent review finds no unresolved defect that could cause a wrong ticket identity, lifecycle action, counter, or evidence claim. Report integration criteria as not evaluated in E1. Do not trade correctness for token savings.

| Measure          | Record per attempt                                                                                                                     |
| ---------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| Reproducibility  | Task ID, approved spec/schema/fixture hashes, starting commit, final commit or patch hash, exact agent configuration                   |
| Quality          | E1 results, failed IDs, review findings, first-pass and final eligibility, untested integration cases                                  |
| Effort           | Repair rounds, tool failures, escalations, human intervention minutes, review minutes                                                  |
| Time             | Wall-clock time to first submission and to accepted final result; provider outages separately labeled                                  |
| Tokens and money | Uncached input, cache reads/writes where exposed, output/reasoning usage as reported, tools/compute, all failed/repair/rescue attempts |
| Evidence         | Commands and outputs, test report, diff, review result, limitations, summary example                                                   |

Calculate delivery cost as all attempted model/tool/compute cost plus allocated shared setup/evaluation cost. Report human minutes separately unless a common hourly valuation was selected before the bakeoff. For repeated attempts, divide total attempted cost by the number of accepted deliveries; report no successful delivery when that count is zero. Missing billing remains unknown, not zero. Token counts alone are not dollars, and subscription usage must not be presented as measured marginal spend.

Choose among eligible routes using total delivery cost, human effort, and time. Do not silently omit the strong reviewer or failed candidate costs. A small difference on this pilot may be inconclusive; the outcome is a provisional route for this task class.

## Cache and context discipline

Keep shared instructions and reference content stable, with task-specific updates later in the context. Fetch only files needed for the slice. Do not add padding or unrelated documents merely to chase cache hits. Record actual cache usage and charges; identical-looking prompts are not evidence of a hit, and a different model/client may not reuse the same cache. If the client does not expose cache controls or accounting, label that limitation rather than inventing savings.

Record whether runs were cold, warm, or unknown. Do not call a cached repeated attempt an independent from-scratch cost estimate. Cache configuration is part of the setup and must be disclosed. For API-managed clients, use only the selected provider/model's supported cache configuration; this packet does not prescribe a universal caching flag. These recommendations follow the exact-prefix constraints in [OpenAI's prompt-caching documentation](https://developers.openai.com/api/docs/guides/prompt-caching).

## After selecting a route

Use the passing lower-cost route for bounded implementation slices with the approved contract. Keep independent review for authentication, exploit identity, ticket writes/reopening, and limit enforcement. Escalate an unresolved product question immediately; escalate a coding attempt after its capped repairs fail. Supply the stronger reviewer with the failing case, current diff, and exact decisions rather than restarting the entire research process.

Do not build a generic factory first. The initial machinery is an approved task packet, common fixtures, isolated workspaces, an evaluator, and a scorecard. Add orchestration only where measured repeated work justifies it.

## Basis for the protocol

The route and repeat limits above are proposed local operating choices, not provider guarantees. OpenAI recommends comparing the same inputs and keeping the lightest model/effort that meets the quality target in its [model-selection guide](https://developers.openai.com/api/docs/guides/model-selection). Its [evaluation guidance](https://developers.openai.com/api/docs/guides/evaluation-best-practices) supports task-specific tests and calibration with human review. No provider benchmark establishes a winner for this repository.
