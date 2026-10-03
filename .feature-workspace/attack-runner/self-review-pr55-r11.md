# Self-review record: PR foxglove/actions#55, round 11 (repair of round 10)

## Identity

- Mode: isolated review. Read-only: no edit of the repository, no commit, no push, no post.
- Base: origin/main (PR base). Previous review revision: 7426b97 plus the round 10 candidate. Round 10 verdict: fail (N1, N2). Candidate: the uncommitted working tree on top of 7426b97. `git diff HEAD` is byte-identical to the frozen `candidate-r11.diff` (cmp, before and after all probes).
- Reviewer prompt: `prompts/review.md` at the PR head (recognized). GitHub posting steps ignored. The reviewer payload (eight objectives, lifecycle table, six additions sub-checks) applied.
- Given intent (not reviewed): the product authority approved the rule "report ignored legacy tickets" (STATUS.md, "Decision - report ignored legacy tickets").
- Review type: delta since round 10, plus a recheck of the shared rule and the adjacent branches.

## Coverage

Inspected: the delta between `candidate-r10.diff` and `candidate-r11.diff` in full; fixture e1-59 (input, expected, `gen-e59.mjs`); the new mutant in `mutation-test.mjs`; EVIDENCE, STATUS, TRACEABILITY; the copy `.feature-workspace/attack-runner/self-review-pr55-r10.md`. `src/plan.mjs`, both schemas, and the README did not change since round 10. Their round 10 review stands and was re-verified by the gates below.
Exclusions: security and UI objectives (no new input surface, no UI); performance unchanged. Cost: unavailable.

## Dispositions of the round 10 findings

| ID  | Round 10                                        | Disposition        | Evidence                                                                                                                                                                                                                                                                                                                                                                    |
| --- | ----------------------------------------------- | ------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| N1  | Low, `unresolved` decision reference not pinned | fixed-and-verified | e1-59 gains `obs-5` and `SEC-UNKNOWN` (state `unknown`, matched by alias). The decision for `obs-5` is `unresolved` with target `SEC-UNKNOWN`; `SEC-UNKNOWN` is not listed; `unresolved` is `["obs-3","obs-5"]`. The probe mutant from round 10 now fails the gate (killed by e1-59). The new mutant `ignored-legacy-skips-unresolved` applies and is killed by e1-59 only. |
| N2  | Low, evidence gap (ajv line, provenance line)   | fixed-and-verified | The EVIDENCE round 9 gate line now reports "ajv 126 of 126 expected and actual outputs valid". The round 10 entry reports its own gates, including ajv and the oracle. The STATUS provenance line names e1-53..59 and the source fixtures. Each named source was checked against the generator scripts (see sub-check 5).                                                   |

## Delta recheck

- Lifecycle row added: alias-matched legacy ticket in state `unknown` -> `plan()` builds an `unresolved` decision with `target.issueId` set (`neededEvidence`: "current state of SEC-UNKNOWN") -> no proposed action -> not listed. Result: one defined outcome. The authored expected values match the actual output (fixture passes).
- The remaining reference paths keep their pins: resolved with claim (SEC-CLAIM), replayed (SEC-REPLAY), `rediscovered-open` (e1-51, e1-58), retest by `issueId` (e1-58), retest by `exploitId` only (SEC-EXONLY, listed), ambiguous alias match (SEC-AMB1, SEC-AMB2, listed).
- Probe mutants on the reference set (18, re-run on the candidate): all killed except three mutants that compare an `exploitId` with the `issueId` set. Those cannot match unless an `issueId` equals an `exploitId`, so they change nothing. A real `exploitId` reference mutant is killed by e1-59. The duplicate-id dedup mutant survives by design: the schema states that issueIds are assumed unique.
- In-run-duplicate equivalence from round 10 still holds: the fuzz (30000 inputs, 1091 with an in-run duplicate) gives 0 differences.
- Independent strict oracle (own six-key and array-semantics rules): 0 differences against all 63 authored `ignoredLegacyIssues` values, 55 tickets scanned. The only ticket where a weaker definition diverges is SEC-PARTIAL, which e1-59 pins.

## Findings

None new. Carried: none open. N1 and N2 are fixed-and-verified. F1 to F8 stay fixed-and-verified from round 10.

## Additions sub-checks

1. Supersession reconciliation: the STATUS provenance sentence replaces the old one (e1-53..56 only). No old sentence remains. The new fixture and mutant add no rule.
2. Effect-claim trace: "an `unresolved` decision that targets a legacy ticket keeps it out of the list" holds in code (`decisions.map(d => d.target?.issueId)` has no outcome filter) and in e1-59. The mutant name `ignored-legacy-skips-unresolved` states what the mutant does, and the mutant does it.
3. Acceptance-case parity: every branch of the new code has a positive and a negative case. Listed: idle, other-case environment, ambiguous alias match, `exploitId`-only retest, blank tuple key. Not listed: resolved with claim, replayed, `unresolved` with target, `rediscovered-open`, retest by `issueId`, other environment. Order is pinned.
4. Distinguishability trace: unchanged from round 10. Listed versus not listed differs for an idle ticket and a targeted ticket (e1-59). The README and schema say that an ambiguous-match ticket and a retest-by-`exploitId` ticket give the idle signal.
5. Cross-reference propagation: counts agree everywhere.
   - Fixture directories: 63. run-fixtures: 64 passed.
   - Mutants: 135, killed 132, 3 equivalent, 0 noapply, in STATUS (verification block and gate line), EVIDENCE (round 10 entry), and the TRACEABILITY header. 130 plus 5 equals 135.
   - Review rounds: "3–11" in STATUS. The review log list names r9, r10, and r11. The EVIDENCE round 10 entry names `self-review-pr55-r11.md`.
   - Provenance: `gen-e59.mjs` reads e1-01, e1-03, e1-04, e1-08, and e1-22 (the e1-22 read is the new one); `gen-e58.mjs` reads e1-51 and e1-04; `gen-e57.mjs` reads e1-55; the e1-53..56 script derives from e1-01 and e1-50. The STATUS list (e1-01, e1-03, e1-04, e1-08, e1-22, e1-50, e1-51, e1-55) matches.
   - The copy of the round 10 record in `.feature-workspace/` differs from the scratch record in blank lines and table padding only (compared with whitespace and blank lines removed). Acceptable.
6. Anchor-event and branch-outcome completeness: unchanged. The anchor is the order of `existingIssues`. The new branch has one defined result.

Names: case-insensitive grep over `.feature-workspace/` and `attack-runner/` for every author name and handle in `git log` and for the current user returns no match. This record contains none.

## Counts

- New comments: 0. Unresolved comments including carried findings: 0. Blockers: 0.

## Verdict

pass. Complete coverage, zero comments, gates green. N1 and N2 are fixed-and-verified. This pass applies to the candidate as reviewed, plus the single addition of this record.

## Rechecks

- `node run-fixtures.mjs`: 64 passed, 0 failed; structural 15 ok / 0 bad.
- `node check-fixtures.mjs`: PASS.
- `node mutation-test.mjs`: 135 mutants, 132 killed, 3 survived (3 equivalent), 0 noapply; PASS. The five round 8 and four round 9 mutants and the new mutant are killed for the intended reason (checked per fixture on a scratch copy: e1-59 for the five that rely on it).
- ajv 8.20 (draft 2020-12), `fixtures/*/expected.json` and `/tmp/aegis-planner-out/*.json` (written by run-fixtures) against `planner-output.schema.json`: 126 of 126 valid. Inputs: only the five negative inputs (e1-23, e1-27, e1-28, e1-38, e1-47) are invalid, by design; e1-58 and e1-59 inputs are valid. A missing field, a non-string item, and a non-array each fail.
- `prettier --check` on all 75 changed files: pass.
- Probes: 18 probe mutants on the reference set, the five new-mutant fixture checks, the strict oracle, and the in-run-duplicate equivalence fuzz (results above).
- Invalidated evidence: none. Next stage: commit the candidate with this record, then push after the coordinator gate.

## Reference check

EVIDENCE.md and STATUS.md name `self-review-pr55-r11.md`. That name is acceptable, and this record has verdict `pass`, so "added verbatim after a pass" holds. The record contains no personal name. The coordinator can copy it verbatim; a prettier pass changes only whitespace.
