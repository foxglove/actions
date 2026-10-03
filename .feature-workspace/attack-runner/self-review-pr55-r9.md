# Self-review record: PR foxglove/actions#55, round 9 (report ignored legacy tickets)

## Identity

- Mode: isolated review. Read-only: no edit of the repository, no commit, no push, no post.
- Base: origin/main (PR base). Previous review revision: 7426b97 (round 8 candidate, committed). Candidate: the uncommitted working tree on top of 7426b97. `git diff HEAD` is byte-identical to the frozen `candidate-r9.diff` (cmp, sha256 60297b75...). The diff is unchanged after all probes.
- Reviewer prompt: `prompts/review.md` at the PR head, sha256 c0071167... (recognized). GitHub posting steps ignored. The reviewer payload (eight objectives, lifecycle table, six additions sub-checks) applied.
- Given intent (not reviewed): the product authority approved the rule "report ignored legacy tickets" (STATUS.md, section "Decision - report ignored legacy tickets"). A legacy ticket is one whose `normalizedChain` does not normalize.
- External comments addressed: (a) the `validateInput` comment disagreed with `plan()`; (b) no output signal for an ignored legacy ticket.

## Coverage

Inspected: the full diff (71 files); `src/plan.mjs` and `src/normalize.mjs` in full; both schemas; `mutation-test.mjs`; `run-fixtures.mjs` (header, invariants); README; STATUS, EVIDENCE, TRACEABILITY, retro-log; `gen-ignored-legacy.mjs` and `gen-e58.mjs`; `docs/aegis/review/acceptance.md` and `engineering-handoff.md` (no runSummary field list, no restatement of the legacy rule); fixture e1-58 input and expected; the eight earlier records for carried findings.
Exclusions: objective 5 (security) and objective 7 (UI): the change is a pure, offline planner with no new input surface and no UI. Objective 4: one extra O(n) pass and one Set per run; no module-level work. Cost: unavailable.

Comment (a): fixed-and-verified. `plan.mjs:63-65` now says `plan()` matches a legacy ticket only through an alias. `plan.mjs:322-324` says the same. Trace: `fingerprint()` returns null when `normalizeChain()` is null, so the exact-fingerprint test never matches a legacy ticket. Only the alias clause can match. Both comments agree with the code.

### Lifecycle trace of `runSummary.ignoredLegacyIssues` (`plan.mjs:531-544`)

Rule: listed if same environment (normalized), chain does not normalize, `issueId` not in `{decision.target.issueId} U {notObserved.issueId}`. Order is the order of `existingIssues`. A ticket enters the list only through the predicate `normalizeChain(...) === null`, which is the exact legacy definition, so a non-legacy ticket cannot appear. State is never read, so every state qualifies. All rows probed on the real planner in a scratch copy.

| Trigger and prior state                                                                 | Acting component               | Evidence it can observe                         | Stored state and permitted action | Terminal result and observable check                                                   |
| --------------------------------------------------------------------------------------- | ------------------------------ | ----------------------------------------------- | --------------------------------- | -------------------------------------------------------------------------------------- |
| Valid positive; one alias-matched legacy ticket (open, e1-51, e1-58)                    | `plan()` loop, then the filter | decision `target.issueId`                       | none                              | not listed (pinned by e1-51, e1-58, mutants `...decision-ref-off`, `...ref-check-off`) |
| Same, ticket state `unknown` or `resolved` without claim                                | `plan()`                       | decision `unresolved` with `target.issueId` set | none                              | not listed (probe I, J). Not pinned: see F2                                            |
| Same, observation replayed (`processedEvents`)                                          | `plan()`                       | decision keeps `target` and proposes `none`     | none                              | not listed (probe B). Not pinned: see F2                                               |
| Same, in-run duplicate of an alias-matched observation                                  | `plan()`                       | second decision keeps `target`                  | none                              | not listed (probe C). Not pinned: see F2                                               |
| Non-observation with `retestTarget.issueId` equal to a legacy ticket                    | `plan()`                       | `notObserved[].issueId`                         | none                              | not listed (e1-58; mutant `...notobserved-ref-off`)                                    |
| Non-observation with `retestTarget.exploitId` only                                      | `plan()`                       | `notObserved[].issueId` is null                 | none                              | listed (probe D). Not pinned: see F5                                                   |
| Legacy ticket in another environment                                                    | filter                         | `normEnv` compare                               | none                              | not listed (e1-54; mutant `...env-off`). Case or space variant not pinned: see F4      |
| Idle legacy ticket, any state (open, resolved, unknown)                                 | filter                         | none                                            | none                              | listed (e1-50, 53, 55, 56, 57, 58)                                                     |
| Two legacy tickets share the matching alias                                             | `plan()`                       | decision `unresolved`, `target` none            | none                              | both listed (probe A). Not pinned: see F6                                              |
| Observation `ambiguous-identity` or `invalid-evidence`; legacy ticket alias would match | `plan()`                       | no match computed                               | none                              | listed (probe H). Consistent with the rule                                             |
| Run with no observations                                                                | filter                         | none                                            | none                              | all same-environment legacy tickets listed (probe G)                                   |
| Input rejected by `validateInput`                                                       | `validateInput`                | exception                                       | no output                         | no summary; unchanged behavior                                                         |

Input order: kept by `filter` then `map`. Pinned only for reversal (e1-57 holds two entries). See F3.

### Eight objectives

1. Correctness: traces above. Probes A to L listed in Rechecks.
2. Design: one extra block at the end of `plan()`. The legacy test `normalizeChain(...) === null` now appears in two places (overlap check and this filter). Acceptable; no helper is needed.
3. Readability: the new comments describe current behavior. Finding F7 for the README definition.
4. Performance: Set lookup plus one pass. No concern.
5. Security: no new input surface. Excluded.
6. Tests: see F2 to F6 and the mutation results below.
7. Product: wording of the field in README, schema, STATUS. See F5, F6, F7.
8. API: schema field is required, `type: array`, `items: string`. Verified by ajv: a missing field, a non-string item, and a non-array each fail. Schema description agrees with the code (including "in input order", "in the run's environment"), apart from F5 and F6.

## Verification of the authored expected values

- All 62 `expected.json` contain the field; none is missing (scripted check). Only six list entries: e1-50, e1-53, e1-55, e1-56 (one each), e1-57 (two), e1-58 (one).
- Oracle `gen-ignored-legacy.mjs` legacy definition vs `normalizeChain`: it differs. The oracle omits two conditions: (i) `semantics` that is an array; (ii) a non-incidental transition whose six tuple keys are not all non-blank strings. `normalizeChain` returns null in both cases. The oracle is therefore weaker. Hidden defect: none today. A stricter independent oracle (implements the six-key rule) gives zero differences against all 62 authored values, and the two definitions agree on all 46 fixture tickets. The gap matters for the future: no fixture ticket has a `semantics` object with a blank key, so the oracle could not have caught a wrong decision there. See F7.
- The oracle reads the authored decisions and `notObserved` of each `expected.json`, not the planner output. It is independent of `plan.mjs` for the reference set.
- Fixture e1-58: three legacy tickets in environment `party`. SEC-ALIAS (alias-matched, open): `rediscovered-open` decision, targeted. SEC-RETEST (resolved) named by a non-observation `retestTarget` with both ids. SEC-IDLE (open): idle. Expected list: `["SEC-IDLE"]`. Passes the planner, run-fixtures, check-fixtures, and the input schema. With the HEAD `plan.mjs` and the new fixtures and schema, run-fixtures reports "1 passed, 62 failed" (63 checks), which matches the EVIDENCE sentence "62 of 63 failed".

## Mutants

- All five new mutants apply and are killed for the intended reason (checked per fixture on a scratch copy): `ignored-legacy-env-off` by e1-54; `ignored-legacy-includes-comparable` by e1-05, 11, 17o, 18b, 33, 34, 48, 49; `ignored-legacy-decision-ref-off` by e1-51 and e1-58; `ignored-legacy-notobserved-ref-off` by e1-58; `ignored-legacy-ref-check-off` by e1-51 and e1-58.
- `summary-unresolved-dropped` (re-anchored on `unresolved,\n    ignoredLegacyIssues,`, replaced by `unresolved: [],`) still tests what its name says. It is killed by 21 fixtures through the `unresolved` list and `batchStatus`. The re-anchor was needed because the old anchor line changed.
- Full gate: 130 mutants, 127 killed, 3 equivalent (the documented set), 0 noapply.
- Probe mutants that the gate does not kill (each run through `run-fixtures.mjs` on a scratch copy, exit 0):
  - `.sort()` on the list;
  - raw `iss.targetEnvironment === runEnv` (no `normEnv`);
  - references taken only from decisions that propose a write (excludes replayed and in-run-duplicate decisions);
  - references that skip `unresolved` decisions;
  - references that skip `claimed-fixed-reproduces` decisions;
  - references from `n.issueId ?? n.exploitId`;
  - a legacy test that checks only for a missing `semantics` object (misses a blank tuple key).
    Killed probe mutants: `rediscovered-open` references skipped (e1-51, e1-58), state-based filters (e1-50 to 58), loose emptiness test (e1-50, 55, 56, 57, 58).

## Findings

| ID  | Severity | Location                                                    | Disposition | Summary                                                                                                                                         |
| --- | -------- | ----------------------------------------------------------- | ----------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| F1  | Low      | `attack-runner/planner/schema/planner-output.schema.json:4` | open        | The title lost its em dash and now holds the escape `—`.                                                                                        |
| F2  | Medium   | `src/plan.mjs:533-536`, `mutation-test.mjs`                 | open        | The decision-reference set is pinned only for `rediscovered-open`.                                                                              |
| F3  | Low      | `src/plan.mjs:537-544`, fixture e1-57                       | open        | "In input order" is not pinned against a sort.                                                                                                  |
| F4  | Low      | `src/plan.mjs:539`                                          | open        | Case and space normalization of the environment is not pinned.                                                                                  |
| F5  | Low      | `src/plan.mjs:535`, schema line 152, README:73, STATUS:56   | open        | "references" does not say by which id; an `exploitId`-only retest target leaves the ticket listed.                                              |
| F6  | Low      | schema line 152, `src/plan.mjs:533-544`                     | open        | A ticket in a multi-alias ambiguity is listed, although the description says "ignored for matching". Duplicate `issueId` entries are undefined. |
| F7  | Low      | README.md:68; `gen-ignored-legacy.mjs`                      | open        | The README legacy definition and the oracle are narrower than `normalizeChain`.                                                                 |
| F8  | Low      | TRACEABILITY.md:27                                          | open        | The new row lists only the positive fixtures.                                                                                                   |

### F1 [Low] Schema title escape (implementation-mistake)

Trace: `git diff` of `planner-output.schema.json` line 4: `planner — output` became `planner — output`. `planner-input.schema.json:4` keeps the literal character. Cause: a JSON re-serialization of the file.
Effect: no semantic change; the diff has noise and the two schemas now differ in style. `prettier --check` passes either way.
Correction: restore the literal em dash on line 4. Keep only the three intended hunks.

### F2 [Medium] Reference by decision is pinned for one outcome only (test gap)

Requirement: the rule says no decision targets the ticket, so a legacy ticket targeted by a replayed, in-run-duplicate, or `unresolved` decision, or by a `claimed-fixed-reproduces` decision, is not listed. Payload names these paths.
Trace: `plan.mjs:533-536` uses every decision. The code is correct for all outcomes (probes B, C, I, J return `[]`). The fixtures pin only the `rediscovered-open` path (e1-51, e1-58). Five probe mutants on the reference set pass the whole gate (see Mutants).
Effect: a change that lists a ticket after a replay or after an unknown-state match, which is a false "ignored" signal for a ticket the run did use, passes every gate. The replay and retry path is common in operation.
Correction: add one fixture (for example e1-59) with alias-matched legacy tickets in four situations: unknown state, resolved without claim, open with fix claim, plus a replayed observation and an in-run duplicate. Expect `[]` for each matched ticket and add the mutants `ignored-legacy-ref-skip-unresolved` and `ignored-legacy-ref-skip-none`.

### F3 [Low] Input order is not pinned (test gap)

Trace: e1-57 is the only fixture with two entries. Its input order (`SEC-LEGACY-RESOLVED`, `SEC-LEGACY-UNKNOWN`) equals the sorted order. A reversal is killed; a `.sort()` is not (exit 0).
Correction: put two idle legacy tickets in non-alphabetical order in e1-58 (for example `SEC-IDLE-B` before `SEC-IDLE-A`) and add a sort mutant.

### F4 [Low] Environment normalization is not pinned (test gap)

Trace: all fixtures with a legacy ticket use `party` in the same case. A raw comparison passes the gate. The overlap check uses `normEnv` and e1-43 pins that side.
Correction: give one idle legacy ticket the environment `PARTY` and expect it listed; add the mutant.

### F5 [Low] "references" is not defined by id (semantic ambiguity)

Trace: `retestTarget` allows `exploitId` only (input schema lines 261-272). Probe D: a non-observation with `retestTarget {exploitId}` equal to the legacy ticket's `exploitId` leaves the ticket in the list; with `issueId` the ticket is not listed (probe D2). The code matches by `issueId` only. The schema, README, and STATUS text say "references" without a key.
Effect: a ticket that a re-test names by exploit is reported as ignored. No fixture pins either choice.
Correction (smallest): state "by issueId" in the schema description, README:73, and STATUS:56, and pin the exploitId-only case as listed. If the product authority wants a match by exploitId, change the code and the fixture instead. This is not a required open question: the rule as given supports the current code.

### F6 [Low] Multi-alias ambiguity and duplicate ids are undefined (effect claim)

Trace: two legacy tickets with the same alias give a `unresolved` decision with no target (probe A). Both tickets are listed. The schema says such a ticket "is ignored for matching (alias aside)". Here the alias took part in matching. The listing is useful to triage (the decision text names no ticket) and agrees with the literal rule. Duplicate `issueId` values in `existingIssues` give a duplicate entry when both are idle (probe E2) and hide an idle one when a same-id ticket is targeted (probe E). Neither the schema nor `validateInput` rejects duplicate ids.
Correction: pin the multi-alias case in a fixture and say in the schema description that such tickets are listed. State or reject duplicate `issueId` values.

### F7 [Low] Definition of "legacy" is narrower in README and in the oracle (cross-reference)

Trace: README.md:68 says a legacy ticket is one whose chain "has no structured semantics". STATUS, schema, and code say "does not normalize". Probe K (a `semantics` object with one blank key) and probe L (`semantics: []`) list the ticket, so the code follows the wider definition. The oracle script has the same narrow definition (see Verification). No fixture holds such a ticket, so the wide part is untested.
Correction: README.md:68 to "whose chain does not normalize (for example no structured semantics, a blank tuple key, or only incidental steps)". Add one idle ticket with a blank tuple key to e1-58, which also covers the oracle gap.

### F8 [Low] TRACEABILITY row omits the negative fixtures (enumeration)

Trace: TRACEABILITY.md:27 lists "e1-50, e1-53, e1-55..58", which are the fixtures that list a ticket. The negative cases that pin "not listed" (e1-51 alias-matched, e1-54 other environment, e1-05 and the triage group for comparable tickets) are absent. Two of the five new mutants are killed only there.
Correction: add e1-51 and e1-54 to the row.

## Additions sub-checks

1. Supersession reconciliation: the old `validateInput` comment is replaced. Remaining statements of the old claim: none (`grep legacy` over `attack-runner/` and `.feature-workspace/`; the "no signal" notes in earlier records are dated history). STATUS "Next actions" and the Gates block carry the new counts.
2. Effect-claim trace: "never blocks" and "state-independent" still hold (e1-57). "lists every same-environment legacy ticket that no decision targets and no non-observation references" holds in code; F5 and F6 note the id and alias edges. README "so triage can link or backfill it" holds. The signal does not tell when a `new` ticket was created for a finding that the ticket tracks; it lists candidates for investigation only. The README claims no more than that.
3. Acceptance-case parity: a positive case (e1-50 to 58) and negative cases (e1-51, e1-54, comparable tickets) exist. Gaps: F2 to F4.
4. Distinguishability trace: listed versus not listed is observable. An alias-matched ticket (not listed) and an idle ticket (listed) give different signals (e1-58). A ticket in a multi-alias ambiguity and an idle ticket give the same signal (F6).
5. Cross-reference propagation: counts agree everywhere. STATUS: 62 fixtures, 63 passed, 130 mutants, 127 killed, 5 new mutant names, rounds 3 to 9, `self-review-pr55-r9.md` in the list. EVIDENCE: 62 of 63 failed, 63 passed, 130/127/3/0, ajv 62 and 62. TRACEABILITY header: 62 fixtures, 130/127 (F8 for the row). retro-log: new entry parses as JSON. README: new sentence. Schema: description agrees. Contract documents (`acceptance.md`, `engineering-handoff.md`) list no runSummary fields; no change needed. Minor, not counted: STATUS.md:131 says e1-53..56 came from a script and does not name e1-57 and e1-58.
6. Anchor-event and branch-outcome completeness: the anchor is the order of `existingIssues`. Every branch has one result (table above), except the undefined duplicate-id case (F6).

Names: case-insensitive grep over `.feature-workspace/` and `attack-runner/` for every author name and handle found in `git log` (and the current user's name and email) returns no match. This record contains none.

## Counts

- New comments: 8 (F1 to F8). Unresolved comments including carried findings: 8. Carried from earlier rounds: none open.
- Blockers: 0 for correctness (the implementation matches the rule on every path traced). F2 is a Medium test gap.

## Verdict

fail. Eight open findings; none shows a defect in the planner output today. The code, schema, and expected values are correct for the traced inputs. The gaps are test pins (F2 to F4), wording (F5 to F7), one diff-noise change (F1), and one enumeration (F8).

## Rechecks

Commands and results, run on the candidate without editing the repository:

- `node run-fixtures.mjs`: 63 passed, 0 failed; structural 15 ok / 0 bad (run again after the probes).
- `node check-fixtures.mjs`: PASS.
- `node mutation-test.mjs`: 130 mutants, 127 killed, 3 survived (3 equivalent), 0 noapply; PASS.
- ajv 8.20 (draft 2020-12) over `fixtures/*/expected.json` and `/tmp/aegis-planner-out/*.json` against `planner-output.schema.json`: 124 of 124 valid, 0 invalid. Inputs: only the five negative inputs (e1-23, e1-27, e1-28, e1-38, e1-47) are invalid, by design; e1-58 input is valid. Negative checks: a missing field, a non-string item, and a non-array each fail.
- `prettier --check` on all 71 changed files: pass.
- Probes in a scratch directory: cases A to L (planner behavior), 17 probe mutants (five run through the full `run-fixtures.mjs`), the five new mutants per fixture, stricter independent oracle (0 differences).
- Invalidated evidence: none.
- Next stage: repair F1 to F8 (F2 first), then a delta review of the repair. The same gates must be re-run, including the mutation test, because fixtures and mutants change.

## Reference check

EVIDENCE.md and STATUS.md name `self-review-pr55-r9.md`. That name is acceptable. The earlier records (r3 to r8) sit in `.feature-workspace/attack-runner/` under the same pattern. This record has verdict `fail`, so the sentence "added verbatim after a pass" holds only for a later pass record. Copy this file under that name only if the author wants the failing record kept; otherwise copy the record of the passing re-review. The record contains no personal name, so it is safe to copy verbatim.
