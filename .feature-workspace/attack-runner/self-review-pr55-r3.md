# Self-review PR #55, round 3 (isolated delta review)

## Review identity

- Mode: isolated reviewer, review only (no repository edits, commits, pushes, or GitHub posts).
- Base: main. Previous reviewed revision: c6872b4.
- Candidate: working tree on branch claude/exciting-cerf-vkmwu5. HEAD is 2d93dfb. The delta against c6872b4 is the committed commits bb8aaa9 and 2d93dfb plus ONE uncommitted change in `attack-runner/planner/run-fixtures.mjs` (the T3 invariant fix, 5 inserted lines, 2 deleted). The frozen diff `candidate.diff` is byte-identical to `git diff c6872b4`.
- Prompt: prompts/review.md at 2d93dfb (review-prompt.md) plus reviewer-payload.md (eight objectives, lifecycle trace, six additions sub-checks).
- Prior findings read: self-review-pr55-r2.md (M1, M2, L1-L5) and the four external threads T1-T4.

## Coverage

Inspected: full delta (14 files), `src/plan.mjs` (whole file), `src/normalize.mjs`, `run-fixtures.mjs` (invariants, structural-reject), `mutation-test.mjs` (harness and all new mutants), `check-fixtures.mjs`, fixtures e1-53..e1-56 (input and expected), `schema/planner-input.schema.json` (existingIssue anyOf), planner README, acceptance.md E1 rows, TRACEABILITY.md, STATUS.md, EVIDENCE.md, self-review-pr55-r2.md.

Objective evidence:

1. Correctness: traced the changed `uncomparable` filter against all alias shapes. Probes run (scratch copy, not in repo): `[]`, `[""]`, `["   "]`, non-array string alias, resolved and unknown-state legacy ticket, other-env legacy ticket (case and whitespace in env), replayed eventId plus legacy ticket. Results match the README claims (see "Claim verification").
2. Design: the filter keeps one rule (same env, chain does not normalize, no usable alias) in one place. No new API surface.
3. Readability: one stale comment (F3).
4. Performance: the filter is O(issues) per would-be-new observation. No module-level work added.
5. Security: no new trust boundary. The alias check is a type guard; non-array and non-string aliases fall into "uncomparable" (fail closed, no creation).
6. Tests: new fixtures and mutants checked for kill power (below). One survivor class found (F2).
7. Product/docs: README additions checked against code. Stale status counts found (F1).
8. API/operations: no schema change. The schema `fingerprintAliases` accepts any string, so the planner-side guard is the only filter (consistent with the delta).

Lifecycle trace (planner has no external actions; each branch ends in a proposal):

| Trigger and prior state                                                                              | Acting component                      | Evidence it can observe                                  | Stored state and permitted action                | Terminal result and observable check                                                                                                                                                          |
| ---------------------------------------------------------------------------------------------------- | ------------------------------------- | -------------------------------------------------------- | ------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Valid positive, no exact match, same-env ticket with unnormalizable chain and aliases `[]` or `[""]` | `plan()` uncomparable branch          | `existingIssues[].normalizedChain`, `fingerprintAliases` | No write                                         | `unresolved`, `neededEvidence` names the issueId; batch `partial` (e1-55, e1-56)                                                                                                              |
| Same, but ticket has one non-blank non-matching alias                                                | `plan()`                              | alias list                                               | Treated comparable; create allowed if no overlap | `new` + create-ticket + increment (e1-53)                                                                                                                                                     |
| Same, but ticket is in another environment                                                           | `plan()`                              | `targetEnvironment`                                      | Ignored                                          | `new` (e1-54)                                                                                                                                                                                 |
| Same as row 1 but observation `eventId` or key already processed                                     | `plan()` triage precedes replay check | `processedEvents`                                        | No write                                         | `unresolved` (not `[none]`); documented in README; verified by probe                                                                                                                          |
| Same-run duplicate of an exploit (any identity)                                                      | `plan()` `duplicateInRun`             | `countedThisRun`                                         | Second observation gets `[none]`                 | At most one `increment-confirmed-count` per identity, now asserted by `invariants()` (T3); verified by mutating `duplicateInRun` and `identityKey` in a scratch copy: invariant message fires |
| Malformed containers or ids                                                                          | `validateInput`                       | input shape                                              | Throw `PlannerInputError`                        | 5 new structural-reject cases assert `instanceof PlannerInputError`                                                                                                                           |

Exclusions: no external writes exist in the planner (E1-15), so partial-write, timeout, and late-response branches do not apply. Unavailable: cost and elapsed time (not measured).

## Gates (run by this reviewer)

- `node attack-runner/planner/run-fixtures.mjs`: 61 passed, 0 failed; structural 14 ok / 0 bad. PASS.
- `node attack-runner/planner/check-fixtures.mjs`: FIXTURE CHECK PASS (5 outcomes covered).
- `node attack-runner/planner/mutation-test.mjs`: 127 mutants, killed 124, survived 3 (3 equivalent), noapply 0. MUTATION TEST: PASS. Exit 0.
- ajv (`--spec=draft2020`, ajv-cli@5): e1-53, e1-54, e1-55, e1-56 `input.json` valid against planner-input; `expected.json` valid against planner-output; actual outputs in /tmp/aegis-planner-out/ for those four valid against planner-output.
- Fixture directories: 60 (e1-01..e1-56 including the `b` variants).

## External thread resolution (T1-T4)

| Thread                                                                 | Verdict                                     | Evidence                                                                                                                                                                                                                                                                                   |
| ---------------------------------------------------------------------- | ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| T1 count only non-empty aliases                                        | RESOLVED                                    | `plan.mjs:338` now `iss.fingerprintAliases.some(nonEmptyString)`. e1-55 (`[]`) and e1-56 (`[""]`) expect `unresolved`; mutants `unc-empty-alias-comparable` and `unc-blank-alias-comparable` are killed.                                                                                   |
| T2 fixtures and mutants for env check and alias clause                 | RESOLVED                                    | e1-54 (chainless ticket in staging, run in party, expects `new`) and e1-53 (alias-only non-matching alias, expects `new`). Mutants `unc-env-ignored` and `unc-alias-clause-off` are killed (mutation run: 0 unexpected survivors). Extra mutant `related-state-skip-restored` also killed. |
| T3 assert at most one increment per identity                           | RESOLVED in working tree, NOT YET COMMITTED | `run-fixtures.mjs:123-133`: key is `issueId ?? idempotencyKey ?? "?"`; the loop over `counts` pushes a problem when n > 1. Verified the invariant fires on mutated engines (e1-08b, e1-30). The fix must be committed before the thread can be answered.                                   |
| T4 README states one uncomparable ticket blocks all new tickets in env | RESOLVED                                    | `README.md:67-71` states it and names the backfill remedy.                                                                                                                                                                                                                                 |

Prior self-review r2 items: M2 fixed (fixtures and mutants), L1 accepted and documented (README "Triage wins over replay", verified), L2 fixed (blank aliases ignored), L5 fixed (5 structural cases assert `PlannerInputError`; the 5 formerly surviving guard mutants are now killed). M1 and L4 were already fixed at c6872b4 (ticket ids named in `neededEvidence`; dead guard absent in current `plan.mjs`).

## Claim verification

- "61 passed + 14 structural-reject" (STATUS.md:94): TRUE (measured).
- "127 mutants, 124 killed, 3 equivalent, 0 noapply" (STATUS.md:96): TRUE (measured). Mutant list matches names in STATUS.md:117-123 (5 `unc-*`/`related-*` plus 5 validation mutants).
- "5 structural-reject cases" (STATUS.md): TRUE (obs-object, existing-not-array, processed-not-array, missing-issueid, missing-observationid).
- README "naming the ticket(s) in `neededEvidence`": TRUE (`plan.mjs:348-352`, joined issueIds).
- README "state-independent": TRUE. Probes: resolved-state and unknown-state legacy tickets block creation; partial-overlap check at `plan.mjs:317-325` has no state test (e1-48, e1-49).
- README "Triage wins over replay": TRUE. All triage branches `continue` before the replay computation; probe with processed eventId plus legacy ticket returned `unresolved` and no actions. The statement that it only shows as `partial` holds.
- README "non-blank fingerprint alias": TRUE for `""` and for non-array alias; NOT PINNED for whitespace-only (F2).
- README Fixtures section (line 14-16) "maps to one acceptance criterion by its e1-NN prefix": FALSE for e1-21..e1-56 (acceptance.md defines E1-01..E1-20 only) (F4).
- STATUS.md:17-19, TRACEABILITY.md:3, EVIDENCE.md:88-89 (56 fixtures, 57 passed, 117/114): STALE (F1).
- Personal names: grep of `.feature-workspace/` and `attack-runner/` for the individual names recorded in STATUS.md history and for owner/author patterns returned no individual names. Only team handles (`@foxglove/...`) and "Foundations team" remain. PASS. (`product-docs/attack-sessions.md` on main is outside the PR; already flagged in STATUS.md.)

## Findings

### F1 [Medium] [cross-reference-propagation] Stale gate counts contradict the updated counts

- Location: `.feature-workspace/attack-runner/STATUS.md:17-19`, `.feature-workspace/attack-runner/TRACEABILITY.md:3`; also `.feature-workspace/attack-runner/EVIDENCE.md:88-89` (no entry for this delta).
- Trace: the delta updates STATUS.md:94-96 to 61 passed / 14 structural / 127 mutants / 124 killed. STATUS.md:17-19 in the same file still says "56 fixtures, 57 passed, 9 structural-reject, 117 mutants, 114 killed". TRACEABILITY.md:3 still says "56 fixtures ... 117 mutants, 114 killed". Measured: 60 fixture directories, 61 passed, 14 structural, 127/124. The same class of defect was F7 in self-review-pr55.md.
- Effect: two coexisting contradictory statements in the same file; the traceability header misstates the gate.
- Fix: update the three locations to 60 fixtures, 61 passed, 14 structural, 127 mutants, 124 killed. Add a dated EVIDENCE.md entry for this round (the 88-89 lines are a valid point-in-time record of the previous round; do not rewrite them).
- Disposition: open.

### F2 [Low] [test-parity] Whitespace-only alias is not pinned; fixture name overstates

- Location: `attack-runner/planner/fixtures/e1-56-blank-alias-legacy/input.json` (alias `""`), `attack-runner/planner/mutation-test.mjs` (new mutants), README.md:68.
- Trace: replaced `v.trim() !== ""` with `v !== ""` in `nonEmptyString` in a scratch copy; run-fixtures reported 61 passed, 0 failed. No fixture contains `"   "`. README says "non-blank". The `unc-blank-alias-comparable` mutant uses `.length > 0`, so it checks only the empty-string case.
- Effect: the "non-blank" claim covers whitespace-only strings, but nothing detects a regression there.
- Fix: change e1-56 alias to `["   "]` (or add e1-57 with `["   "]`) and add a mutant that removes `.trim()` from `nonEmptyString`. Keep one fixture for `""` if the empty case must stay pinned (e1-55 pins `[]`, not `[""]`).
- Disposition: open.

### F3 [Low] [comment-drift] validateInput comment states the old rule

- Location: `attack-runner/planner/src/plan.mjs:63-64`.
- Trace: the comment says an existing issue "with no comparable identity (chain does not normalize and no alias)". The delta changed the rule at line ~330 to "no non-blank alias" and updated that comment, but not this one.
- Effect: two comments describe the same rule differently; "no alias" reads as "empty list" only.
- Fix: write "no usable (non-blank) alias" at line 64.
- Disposition: open.

### F4 [Low] [semantic-model-gap] The "uncomparable ticket blocks creation" rule has no acceptance or traceability owner

- Location: `attack-runner/planner/README.md:14-16` and `.feature-workspace/attack-runner/TRACEABILITY.md` (rows); new fixtures e1-53..e1-56.
- Trace: acceptance.md defines E1-01..E1-20. README says each fixture maps to an acceptance criterion by its e1-NN prefix; e1-21..e1-56 map to none. No acceptance row or TRACEABILITY row covers the env-wide, state-agnostic block by one legacy ticket (it is a planner design choice made in earlier rounds, documented in README:67-71). E1-18 covers only ambiguous partial chains.
- Effect: a product-level trade-off (one legacy ticket, even a resolved one, halts new tickets in its environment) has no named acceptance owner. The README sentence about the prefix mapping is false as written.
- Fix: reword README:14-16 (fixtures with no acceptance row are hardening cases) and add one TRACEABILITY row that names this rule and its fixtures (e1-50..e1-56), with the acceptance owner marked as an open question like R3-M3. Do not invent the product decision.
- Disposition: open (non-blocking in behavior; documentation and ownership only).

## Counts

- New comments: 4 (1 Medium, 3 Low). No Critical or High.
- Unresolved comments total: 4 (no carried findings; T1-T4 and r2 M2, L1, L2, L5 resolved by the candidate; T3 resolution is uncommitted).
- Missed blockers in unchanged `attack-runner/` code affected by the delta: none found. Checked: ordering of the uncomparable branch before `incompleteTicketFields` (a would-be-new observation with incomplete material and an uncomparable ticket reports the uncomparable reason; both are `unresolved`, so no behavior difference); replay interplay (documented, safe); schema `anyOf` accepts `[]` and `[""]` aliases (consistent with planner guard).

## Verdict: fail

Four open findings (F1 Medium, F2-F4 Low). There are no code correctness defects and all gates pass. The `fail` follows the payload rule that open findings give `fail`. All four are documentation or test-parity edits. After F1-F4 are fixed and the T3 change is committed, the next pass should be a delta recheck of those files only.

## Rechecks

- Commands: the three gate scripts and ajv as listed above, all green. Scratch-copy mutation probes (duplicateInRun off, identityKey randomized, trim removed, alias-shape probes) were run outside the repo; the repository tree was not changed by this review.
- Invalidated evidence: any gate record before the T3 commit is not tied to a committed revision; re-run the gates after committing.
- Next stage: author fixes F1-F4, commits including the T3 change, replies on T1-T4, then a delta recheck.
- Elapsed time and cost: not measured.
