# Self-review PR #55, round 6 (isolated review of the R3-F4 decision implementation)

## Review identity

- Mode: isolated reviewer, review only. No repository edit, commit, push, or GitHub post. Reads of the PR body through the REST API only.
- Base: main. Original reviewed revision: c6872b4. Previous reviews: round 3 (fail, F1-F4), round 4 (fail, F5-F9), round 5 (pass).
- Candidate: the uncommitted working tree on branch claude/exciting-cerf-vkmwu5 compared with HEAD 7503a34 (HEAD and origin are equal). 11 modified tracked files. `candidate-r6.diff` is byte-identical to `git diff HEAD` (sha256 de9c9973…d39e).
- Prompt: prompts/review.md at the PR head, sha256 c007116786a0bb1064a99229a375ab8f773d85c97e87e65542434703004ef4d7. It matches the recognized value in EVIDENCE.md.
- Given decision (not reviewed): STATUS "Decision R3-F4". A same-environment ticket whose chain does not normalize and whose aliases do not match is ignored. It takes no part in matching or overlap triage. It never blocks a `new` ticket.

## Coverage

Files read in full: `src/plan.mjs`, `mutation-test.mjs` (changed region and gate tail), `run-fixtures.mjs` (structural block), the planner README, fixtures e1-50, e1-53..56 (input and expected), the input schema (`existingIssues`), STATUS.md, EVIDENCE.md, TRACEABILITY.md, retro-log.json, the round-5 record, the payload, and the review prompt. Contract documents checked: `product-docs/exploit-findings.md` (lines 16, 24, 85), `docs/aegis/review/acceptance.md` (E1-18), and the PR #55 body (read-only REST call).

Objectives:

- Correctness: traced every path in the table below, plus 15 direct probes of `plan()` (see Rechecks).
- Design: the removal leaves one guard (`if (issNorm === null) return false;`, plan.mjs:323). The other uses of `normalizeChain` and `nonEmptyString` stay in use.
- Readability: findings F2 and F3.
- Performance: the change removes one filter pass per observation. No new work.
- Security: no new input path. The validation of `existingIssues` is unchanged.
- Tests: finding F4. The retired mutants have no remaining source; the new mutant applies (noapply 0).
- Product and UX: the README rule and the accepted risk are stated. Finding F3 covers the terminology.
- API and operations: schema unchanged. The planner has no external action (E1-15). No migration step applies.

### Lifecycle trace

The planner is pure (E1-15). The reachable branches for an observation that reaches the existing-ticket comparison, with a legacy ticket L (chain does not normalize, no matching alias) present in the run environment:

| Trigger and prior state                                     | Acting component              | Evidence it can observe               | Stored state and permitted action                           | Terminal result and observable check                                               |
| ----------------------------------------------------------- | ----------------------------- | ------------------------------------- | ----------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| Valid positive, L only, L open (e1-50, e1-55, e1-56)        | `plan()` `matches` filter     | `issFp` is null; no alias equals `fp` | `matches` is empty; `relatedToIssue` skips L (plan.mjs:323) | `new` with create-ticket and count; `batchStatus` complete (fixtures)              |
| Same, L in resolved, unknown, or unrecognized state         | same                          | same; the code never reads L state    | same                                                        | `new` (probe; no fixture, see F4)                                                  |
| Same, L in another environment (e1-54)                      | same                          | env differs                           | skipped by the env test                                     | `new` (fixture)                                                                    |
| Exact match on a different, comparable ticket (e1-50 obs-2) | `matches` filter              | fingerprint equal                     | one match; L is not in `matches`                            | `rediscovered-open` (fixture)                                                      |
| Alias of L equals `fp` (e1-51, probe)                       | `matches` filter              | alias equals `fp`                     | L is a match, so it is not ignored                          | open: `rediscovered-open`; unknown or resolved without claim: `unresolved` (probe) |
| Two legacy tickets share the matching alias                 | `matches` filter              | two matches                           | none                                                        | `unresolved` (multiple matches) (probe)                                            |
| Non-matching non-blank alias on L (e1-53)                   | `matches` filter              | no equal alias                        | none                                                        | `new` (fixture)                                                                    |
| Partial or superset overlap with a comparable ticket        | `relatedToIssue`              | `isSubsequence` on normalized chains  | unchanged                                                   | `unresolved` (e1-48, e1-49; unchanged code)                                        |
| In-run overlap between two positives                        | `runPositives`/`relatedInRun` | run chains only                       | no existing ticket is read                                  | `unresolved` or `new` as before (e1-44; L has no input to this check)              |
| Replay by `eventId` or key, L present                       | replay block after `new`      | `processedIds`, `processedKeys`       | `actions` is `none`; no count                               | `new` with action `none`; `batchStatus` complete (probe)                           |
| In-run duplicate, L present                                 | `countedThisRun`              | `identityKey` equals `fp`             | second observation gets `none`                              | `new` with action `none` (probe)                                                   |
| Legacy ticket with no `normalizedChain` field at all        | `normalizeChain`              | null                                  | none                                                        | ignored (probe)                                                                    |
| Missing `targetEnvironment` on any existing ticket          | `validateInput`               | field absent                          | batch error (unchanged, required by the schema)             | `PlannerInputError`; out of scope for this decision                                |

No other path treats a non-comparable ticket specially. Searched: `grep` for `uncomparable`, `comparable`, `legacy`, `nonEmptyString`, and every `iss.` use in `plan.mjs`. The removed `uncomparable` block was the only special case. `nonEmptyString` now serves only `validateInput`.

## Gates (run by this reviewer)

- `run-fixtures.mjs`: 61 passed, 0 failed; structural 15 ok / 0 bad. Exit 0. PASS.
- `check-fixtures.mjs`: FIXTURE CHECK PASS.
- `mutation-test.mjs`: 124 mutants, killed 121, survived 3 (3 equivalent), noapply 0. MUTATION TEST PASS, exit 0.
- ajv (draft2020, ajv-cli@5): e1-50, e1-55, e1-56. `expected.json` valid against the output schema. `input.json` valid against the input schema. The regenerated actual outputs are valid. 9 of 9 valid.
- `prettier@3 --check` on the 11 changed files: all formatted. The record file also passes.
- Test-first claim (EVIDENCE): `plan.mjs` from HEAD with the new fixtures gives "58 passed, 3 failed" (e1-50, e1-55, e1-56). Reproduced.
- `blank-runid` claim: with the `nonempty-no-trim` mutation the case `blank-runid` fails (killed). With the case removed the mutation passes 61/0 and 14 ok / 0 bad (survives). `blank-runid` is the only killer, and it is correct: `run.runId` of two spaces throws `PlannerInputError`.
- Fixture directories: 60.
- Personal names: grep for the author and commit-history names, and for `Firstname Lastname` patterns, over `.feature-workspace/` and `attack-runner/`: 0 hits.

## Count verification

| Location                                      | Stated                                                         | Measured                                                                                                                                             | Result                        |
| --------------------------------------------- | -------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------- |
| STATUS Verification bullet                    | 60 fixtures, 61 passed, 15 structural, 124 mutants, 121 killed | same                                                                                                                                                 | match                         |
| STATUS Gates list                             | 61 + 15; 124/121/3/0 noapply                                   | same                                                                                                                                                 | match                         |
| TRACEABILITY header                           | 60 fixtures, 124 mutants, 121 killed                           | same                                                                                                                                                 | match                         |
| EVIDENCE new entry                            | 58/3 first, then 61/0 + 15; 124/121/3/0                        | same (58/3 reproduced)                                                                                                                               | match                         |
| EVIDENCE older entries (117/114, 128/125, 14) | dated records of earlier rounds                                | n/a                                                                                                                                                  | not stale                     |
| Retired mutants (STATUS: "five")              | five removed                                                   | `uncomparable-off`, `unc-env-ignored`, `unc-alias-clause-off`, `unc-empty-alias-comparable`, `unc-blank-alias-comparable` removed; 128 - 5 + 1 = 124 | match                         |
| README                                        | no counts                                                      | n/a                                                                                                                                                  | n/a                           |
| PR #55 body                                   | 47 fixtures, 48 passed, 112 mutants, 4 survivors               | 60, 61, 124, 3                                                                                                                                       | stale before this change (I1) |

## Additions sub-checks

1. Supersession reconciliation: the README outcome row, the README rule bullet, the STATUS question section, the TRACEABILITY row, and the `plan.mjs` comment all replace the old rule. The old "Open product question (R3-F4)" section is gone. One old statement remains: STATUS.md:134 says "Implement it" (F1). The dated EVIDENCE entries keep the old rule as history. That is acceptable.
2. Effect-claim trace: "never blocks a `new` ticket" holds on all paths in the table. "Takes no part in overlap triage" holds (plan.mjs:323). "Matches only through a fingerprint alias" holds (plan.mjs:285-291). "Backfill a chain or an alias to make it match" holds. "The mutant `legacy-ticket-triages` pins the rule" holds for an open legacy ticket only (F4). "`blank-runid` kills `nonempty-no-trim`" holds (reproduced).
3. Acceptance-case parity: the rule applies to every state of L. The fixtures pin only the open state (F4).
4. Distinguishability: no claim of a separating signal. The `new` decision for a finding tracked only on L has the same `matchReason` as any other `new`. The accepted risk is documented, so this is not a defect.
5. Cross-reference propagation: counts and the rule agree in STATUS, TRACEABILITY, EVIDENCE, README, and retro-log. The contract documents do not restate the old rule (`exploit-findings.md:24,85` and E1-18 cover ambiguity, not legacy tickets). The PR body does not state the old rule. Remaining stale items: F1 and F3.
6. Anchor-event and branch-outcome completeness: each branch in the table has one defined result. EVIDENCE names the record file `self-review-pr55-r6.md` for this commit.

## Findings

### F1 (Low, stale text) STATUS.md:134

Next action 6 says "R3-F4 decided: ignore legacy tickets (section above). Implement it." The same change implements the rule (STATUS.md:43). A reader that resumes from the checkpoint reads an open instruction for finished work. Two related lines are also stale: STATUS.md:105 says session 2 ran "self-review rounds 3-5", and STATUS.md:124-125 lists the retired mutants `unc-env-ignored`, `unc-alias-clause-off`, `unc-empty-alias-comparable`, and `unc-blank-alias-comparable` as DONE with no mark that they no longer exist. Correction: strike action 6 and mark it done with the commit, change "3-5" to "3-6", and add "(retired in R3-F4)" to the mutant list. Disposition: open.

### F2 (Low, readability) attack-runner/planner/src/plan.mjs:63-66

The comment refers to the review label "product decision R3-F4". A source comment must describe the current behavior, not the review process. The comment also sits in `validateInput`, which never reads an observation, so "no alias matches" has no meaning there. The line that implements the rule (plan.mjs:323, `if (issNorm === null) return false;`) has no comment. Correction: keep the "not a batch error" reason in `validateInput` without the label, and add one comment at plan.mjs:323: a ticket whose chain does not normalize cannot overlap, and it matches only through an alias. Disposition: open.

### F3 (Low, terminology) attack-runner/planner/README.md:68 and :75

One term has three meanings. README.md:68 uses "comparable identity" for "no structured semantics" (the paragraph then covers every chainless ticket, whatever its aliases). README.md:75 uses "comparable ticket" for "chain normalizes". STATUS.md:37-40 uses "comparable identity" for "normalizable chain or non-blank alias". `plan.mjs:63` uses "chain normalizes or an alias matches". A ticket with a non-matching alias is "comparable" in STATUS and "legacy" in README. The fixture directories e1-50 and e1-54 still carry the retired term "uncomparable". Correction: write "ticket with a normalized chain" at README.md:75, name the README.md:68 bullet "Tickets whose chain has no structured semantics are ignored", and use the same definition in STATUS and the `plan.mjs` comment. Renaming the two directories is optional. If renamed, update the references "e1-50, e1-53..56" only if the numbers change. Disposition: open.

### F4 (Low, test gap) attack-runner/planner/mutation-test.mjs:687-691

The README and STATUS rule applies to a legacy ticket in any state. All six fixtures that hold a legacy ticket (e1-50, e1-51, e1-53..56) use state `open`. These mutations of plan.mjs:323 pass `run-fixtures.mjs` with exit 0 (reproduced):

- `if (issNorm === null) return iss.state !== "open";`
- `if (issNorm === null) return iss.state === "resolved";`
- `if (issNorm === null) return iss.state === "unknown";`

So an implementation that again blocks on a closed or unknown legacy ticket passes every gate. Closed tickets are the most common legacy tickets. Correction: add a fixture (for example `e1-57`) with legacy tickets in states `resolved`, `unknown`, and an unrecognized state, plus one valid positive. Expect `new` and a complete batch. Add the mutant `legacy-ticket-state-blocks` with the first mutation above. Then update the counts in STATUS, TRACEABILITY, and EVIDENCE (61 fixtures, 62 passed, 125 mutants, 122 killed) and the TRACEABILITY fixture range. Disposition: open.

### Informational (not counted)

- I1: the PR #55 body states 47 fixtures, 48 passed, 112 mutants, and 4 survivors. These numbers were stale before this change. The body does not state the old rule. Update the numbers when the PR goes to ready-for-review.
- I2: no fixture pairs a legacy ticket with a replayed or duplicate observation. The code that handles replay and duplicates never reads existing-ticket data apart from `matches`, so one guard at plan.mjs:323 decides all three. The probes confirm `new` with action `none`.
- I3: the planner gives no signal when it ignores a legacy ticket. The decision accepts this risk. A later change can add a `neededEvidence` or summary note if triage needs it. It is a product choice and not a defect here.

## Arrangement check: the record file named `self-review-pr55-r6.md`

Acceptable, with these conditions:

- This verdict is `fail`. The record is copied only after a `pass`. After the repair of F1-F4 and a new review of the delta, the pass record uses the same file name, or a new round name with updated references in EVIDENCE.md and STATUS.md. The file must exist in the same push as the commit, so no reference points to a missing file.
- The copy is byte-for-byte. The record contains no personal name and passes `prettier --check`.
- EVIDENCE.md:126 and STATUS.md:139 name the file and carry no verdict text. That is acceptable because both point to the file.
- The repository has no content gate for this path, so the late addition cannot change a gate result.

## Counts

- New comments: 4 (F1, F2, F3, F4).
- Unresolved comments: 4. No carried finding from rounds 3 to 5 remains open.
- Missed blockers in unchanged code: none found.

## Verdict: fail

The code implements the decision on every path in the table, and the gates are green. Four Low findings remain open: a stale instruction in STATUS (F1), a process label and a misplaced comment in `plan.mjs` (F2), a term with three meanings (F3), and a state gap in the tests that lets a state-based block pass every gate (F4). A mixed result blocks the commit until the findings are fixed and the delta is reviewed.

## Rechecks

- Commands run: the three gate scripts; ajv for e1-50, e1-55, e1-56 (input, expected, actual); `prettier@3 --check`; a test-first reproduction in a scratch copy with the HEAD `plan.mjs`; `blank-runid` kill and survive checks in a scratch copy; 5 state and alias mutations of plan.mjs:323 in scratch copies; a 15-case probe of `plan()` (states open, resolved, unknown, unrecognized; missing chain fields; empty chain; replay by `eventId` and by key; in-run duplicate; alias match in three states; two aliases that match); name greps; a `git diff HEAD` hash comparison; a PR body read through REST.
- Invalidated evidence: none. The repository stayed unchanged (no untracked file; only the 11 tracked modifications).
- Next stage: repair F1-F4, run the three gates again, review the delta, then commit with the pass record and push in one step. Then reply on the PR and mark it ready after CI passes.
- Elapsed time and cost: not measured.
