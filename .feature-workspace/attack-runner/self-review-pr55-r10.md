# Self-review record: PR foxglove/actions#55, round 10 (repair of round 9)

## Identity

- Mode: isolated review. Read-only: no edit of the repository, no commit, no push, no post.
- Base: origin/main (PR base). Previous review revision: 7426b97 plus the round 9 candidate. Round 9 verdict: fail (F1 to F8). Candidate: the uncommitted working tree on top of 7426b97. `git diff HEAD` is byte-identical to the frozen `candidate-r10.diff` (cmp, before and after all probes).
- Reviewer prompt: `prompts/review.md` at the PR head (recognized). GitHub posting steps ignored. The reviewer payload (eight objectives, lifecycle table, six additions sub-checks) applied.
- Given intent (not reviewed): the product authority approved the rule "report ignored legacy tickets" (STATUS.md, "Decision - report ignored legacy tickets").
- Review type: delta since round 9, plus a recheck of the shared rule and the adjacent branches.

## Coverage

Inspected: the delta (plan.mjs unchanged since round 9 apart from the comment wording), schema, README, STATUS, EVIDENCE, TRACEABILITY, retro-log, `mutation-test.mjs`, fixture e1-59 (input, expected, `gen-e59.mjs`), the updated oracle `gen-ignored-legacy.mjs`, and the copy `.feature-workspace/attack-runner/self-review-pr55-r9.md`.
Exclusions: security and UI objectives (no new input surface, no UI); performance unchanged from round 9. Cost: unavailable.

## Dispositions of the round 9 findings

| ID  | Round 9                                   | Disposition                                                        | Evidence                                                                                                                                                                                                                                                                                                                                                                                                                       |
| --- | ----------------------------------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| F1  | Low, schema title escape                  | fixed-and-verified                                                 | `planner-output.schema.json:4` holds the literal em dash. The schema diff has two hunks only (the `required` entry and the new property).                                                                                                                                                                                                                                                                                      |
| F2  | Medium, references pinned for one outcome | fixed-and-verified for the paths added; one residual carried as N1 | e1-59 pins `claimed-fixed-reproduces` on a resolved alias-matched ticket (SEC-CLAIM) and a replayed match (SEC-REPLAY). Probe mutants "skip written-none decisions", "skip claimed-fixed", "only rediscovered-open" are killed by e1-59, as are the new mutants `ignored-legacy-written-decisions-only` and `ignored-legacy-rediscovered-only`. The `unresolved`-with-target path stays unpinned: see N1.                      |
| F3  | Low, input order                          | fixed-and-verified                                                 | e1-59 input order is SEC-ZIDLE before SEC-AIDLE. `.sort()` changes the list. Mutant `ignored-legacy-sorted` is killed by e1-59 only.                                                                                                                                                                                                                                                                                           |
| F4  | Low, environment normalization            | fixed-and-verified                                                 | SEC-AIDLE has environment `Party`. `ignored-legacy-raw-env` is killed by e1-59 only. A second raw variant (raw compare on one side) is also killed.                                                                                                                                                                                                                                                                            |
| F5  | Low, "references" by which id             | fixed-and-verified                                                 | Schema description, README, STATUS rule, and code comment say "whose `issueId` no decision targets and no notObserved entry references". e1-59 pins an `exploitId`-only retest target (SEC-EXONLY) as listed. A new probe mutant that also references by `exploitId` is killed by e1-59.                                                                                                                                       |
| F6  | Low, ambiguous alias match, duplicate ids | fixed-and-verified                                                 | e1-59 pins two alias-matched legacy tickets (SEC-AMB1, SEC-AMB2) under an `unresolved` decision with no target: both listed. The schema now says so and says "issueIds are assumed unique". The input schema does not state uniqueness and the planner does not reject duplicates; a duplicate id stays undefined behavior. This is documented, not enforced. Accepted.                                                        |
| F7  | Low, definition narrower                  | fixed-and-verified                                                 | README now says "chain does not normalize (for example, a transition has no structured semantics or misses a tuple key)". Oracle `gen-ignored-legacy.mjs` now applies the array-semantics rule and the six-key rule (read line by line; it matches `normalizeTransition`). e1-59 pins SEC-PARTIAL (a missing `violation` key) as listed. The probe mutant that tests only for a missing `semantics` object is killed by e1-59. |
| F8  | Low, TRACEABILITY enumeration             | fixed-and-verified                                                 | The row now reads "fixtures e1-50, e1-51, e1-53..59". It covers the negative cases e1-51 and e1-54.                                                                                                                                                                                                                                                                                                                            |

## Claim: a mutant that skips in-run-duplicate decisions is equivalent

Verified. Trace: `identityKey` is `iss.issueId` for a matched ticket (`plan.mjs`, before the replay test). `countedThisRun` receives an `identityKey` only in the non-replayed, non-duplicate branch, after the decision is built with `target.issueId` equal to that key. A later decision is an in-run duplicate only when its `identityKey` is in `countedThisRun`. Its target therefore equals the target of an earlier decision, which stays in the reference set. For a `new` exploit the key is the fingerprint and the target has no issue id, so nothing is lost. Decisions that `continue` before this point never add a key.
Test: a mutant that drops from the reference set exactly the decisions marked duplicate (not replayed) was compared with the real planner on 30000 random inputs (alias-matched legacy tickets, mixed states and environments, replays). 1091 inputs held an in-run duplicate with an existing-issue target. The two `ignoredLegacyIssues` lists differ in 0 inputs. The mutant is equivalent. It is not in the mutation test, so the documented equivalent set stays at 3. A replayed decision is not equivalent: it is pinned by SEC-REPLAY.

## Lifecycle trace (delta)

Rule unchanged: listed if same environment (normalized), chain does not normalize, `issueId` neither a decision target nor a `notObserved.issueId`; input order. State is never read. The round 9 table still holds. Changes in pinning:

| Trigger and prior state                                                                 | Acting component | Evidence it can observe                               | Stored state and permitted action | Terminal result and observable check        |
| --------------------------------------------------------------------------------------- | ---------------- | ----------------------------------------------------- | --------------------------------- | ------------------------------------------- |
| Alias-matched resolved legacy ticket with fix claim                                     | `plan()`         | decision `claimed-fixed-reproduces`, target SEC-CLAIM | reopen proposal                   | not listed (e1-59)                          |
| Alias-matched legacy ticket, observation replayed                                       | `plan()`         | decision keeps target, action `none`                  | none                              | not listed (e1-59)                          |
| Two legacy tickets share the matching alias                                             | `plan()`         | `unresolved`, no target                               | none                              | both listed (e1-59)                         |
| Non-observation, `retestTarget.exploitId` only                                          | `plan()`         | `notObserved.issueId` null                            | none                              | listed (e1-59)                              |
| Legacy ticket with a blank or missing tuple key                                         | `normalizeChain` | null                                                  | none                              | listed (e1-59)                              |
| Legacy ticket, environment `Party`, run `party`                                         | filter           | `normEnv`                                             | none                              | listed (e1-59)                              |
| Alias-matched legacy ticket, state `unknown`, `resolved` without claim, or unrecognized | `plan()`         | decision `unresolved` with target set                 | none                              | not listed (probed correct). Not pinned: N1 |

e1-59 expected values: six listed in input order (SEC-ZIDLE, SEC-AMB1, SEC-AMB2, SEC-EXONLY, SEC-PARTIAL, SEC-AIDLE); SEC-CLAIM and SEC-REPLAY not listed; `batchStatus` partial, `unresolved` `["obs-3"]`. I traced each decision against `plan.mjs` by hand and the fixture passes. The `authored-intent` placeholder in `reason` and `matchReason` follows the existing convention (those keys are stripped by the oracle).

## Findings

| ID  | Severity | Location                                       | Disposition | Summary                                                                                                                               |
| --- | -------- | ---------------------------------------------- | ----------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| N1  | Low      | `src/plan.mjs:533-536`, fixture e1-59          | open        | An `unresolved` decision that carries a target (unknown, unrecognized, or resolved-without-claim state) is not pinned as a reference. |
| N2  | Low      | EVIDENCE.md (round 9 entry), STATUS.md:131-134 | open        | The gate line after the repair omits ajv, and the fixture provenance sentence names only e1-53..56.                                   |

### N1 [Low] Reference by `unresolved` decision is unpinned (test gap; residual of F2)

Trace: probes with an alias-matched legacy ticket in state `unknown` and `resolved` without claim return `[]` (correct, the decision targets the ticket). A probe mutant that builds the reference set from non-`unresolved` decisions only passes the whole `run-fixtures.mjs` gate (exit 0, reproduced on a scratch copy). No fixture combines an alias-matched legacy ticket with these states: e1-22, e1-23, e1-24 use comparable tickets.
Effect: a change that lists a ticket after an unknown-state match, a false "ignored" signal for a ticket the run used, passes every gate.
Correction: add one alias-matched legacy ticket in state `unknown` to e1-59 (decision `unresolved`, target set, not listed) and add the mutant `ignored-legacy-unresolved-ref-off`.

### N2 [Low] Evidence record after the repair (completeness)

Trace: the round 9 entry in EVIDENCE.md reports ajv only in the first Gates bullet (62 expected, 62 actual, e1-58). The bullet after the repair lists run-fixtures, check-fixtures, and mutation-test only. Current ajv result: 126 of 126 valid (63 expected, 63 actual); e1-59 input valid. STATUS.md:131-134 still says e1-53..56 were authored by a script and omits e1-57 to e1-59.
Correction: add the ajv result to the post-repair bullet and extend the provenance sentence.

## Additions sub-checks

1. Supersession reconciliation: the F5 and F7 wording replaces the narrower README definition and the unqualified "references". Remaining old statements: none (grep for "no structured semantics" and "references" over README, schema, STATUS). The schema, README, STATUS rule, and code comment now use the same text.
2. Effect-claim trace: "lists, in input order, every same-environment legacy ticket whose issueId no decision targets and no non-observation references" holds in code and in e1-59. "legacy tickets in an ambiguous alias match are listed" holds (SEC-AMB1, SEC-AMB2). "can match only through an alias" holds. "issueIds are assumed unique" is an assumption, not an effect. "so triage can link or backfill it" holds. The claim "the in-run-duplicate mutant is equivalent" holds (above).
3. Acceptance-case parity: positive cases (e1-50, 53, 55 to 59) and negative cases (e1-51, e1-54, e1-58, e1-59 targeted tickets) exist. Residual: N1.
4. Distinguishability trace: an ambiguous-match ticket and an idle ticket give the same signal, and the schema now says so. A retest-by-`exploitId` ticket and an idle ticket give the same signal; the wording "by issueId" says so.
5. Cross-reference propagation: counts agree. Fixture directories: 63. run-fixtures: 64 passed (STATUS, EVIDENCE). Mutants: 134, 131 killed, 3 equivalent, 0 noapply (STATUS twice, EVIDENCE, TRACEABILITY header). Review rounds: 3 to 10 (STATUS). New mutants named in STATUS: nine in total (five round 8, four round 9 repair); 130 plus 4 equals 134. Review logs list includes r9 and r10. README, schema, STATUS, code comment agree on the rule text. retro-log parses as JSON. The copy of the round 9 record in `.feature-workspace/` differs from the scratch record only by prettier formatting (table padding, blank lines, and one code span where the spaces around `PARTY` were trimmed). Acceptable. See N2 for the two stale lines.
6. Anchor-event and branch-outcome completeness: the anchor is the order of `existingIssues`. Every branch in the table has one result.

Names: case-insensitive grep over `.feature-workspace/` and `attack-runner/` for every author name and handle in `git log` and for the current user returns no match. This record contains none.

## Counts

- New comments: 2 (N1, N2). Carried from round 9 and still open: 0 (F1 to F8 fixed-and-verified, the residual of F2 is N1). Unresolved comments including carried findings: 2. Blockers: 0.

## Verdict

fail. Two open Low findings. The planner output is correct on every traced path; the code did not change since round 9 except comments. N1 is a missing pin for one reference branch. N2 is an evidence-record gap. Both repairs are small.

## Rechecks

- `node run-fixtures.mjs`: 64 passed, 0 failed; structural 15 ok / 0 bad.
- `node check-fixtures.mjs`: PASS.
- `node mutation-test.mjs`: 134 mutants, 131 killed, 3 survived (3 equivalent), 0 noapply; PASS. The four new mutants and the re-anchored `summary-unresolved-dropped` are each killed for the intended reason (checked per fixture: e1-59 for the four new ones; 21 fixtures for the re-anchored one).
- ajv 8.20 (draft 2020-12), `fixtures/*/expected.json` and `/tmp/aegis-planner-out/*.json` (written by run-fixtures) against `planner-output.schema.json`: 126 of 126 valid. Inputs: only the five negative inputs (e1-23, e1-27, e1-28, e1-38, e1-47) are invalid, by design; e1-58 and e1-59 inputs are valid. A missing field, a non-string item, and a non-array each fail.
- `prettier --check` on all 74 changed files: pass.
- Probes: 17 round 9 probe mutants re-run against the candidate (survivors: `unresolved`-reference skip, the crude `exploitId` variants that cannot match, duplicate-id dedup); a strict independent oracle (own six-key rule) gives 0 differences on all 63 expected values; the in-run-duplicate equivalence fuzz (30000 inputs, 0 differences).
- Invalidated evidence: none. Next stage: repair N1 and N2, then a delta review. The mutation test must run again because fixtures and mutants change.

## Reference check

EVIDENCE.md and STATUS.md name `self-review-pr55-r10.md`. That name is acceptable. This record has verdict `fail`, so the phrase "added verbatim after a pass" holds only for a later pass record. This record contains no personal name, so a verbatim copy is safe.
