# Self-review PR #55, round 7 (isolated delta recheck after the round-6 repairs)

## Review identity

- Mode: isolated reviewer, review only. No repository edit, commit, push, or GitHub post.
- Base: main. Previous reviews: round 3 (fail), round 4 (fail), round 5 (pass), round 6 (fail, F1-F4; record `self-review-pr55-r6.md`).
- Candidate: the working tree on branch claude/exciting-cerf-vkmwu5 compared with HEAD 7503a34. New files are intent-to-add. 14 files changed. `candidate-r7.diff` is byte-identical to `git diff HEAD`.
- Prompt: prompts/review.md at the PR head, sha256 c007116786a0bb1064a99229a375ab8f773d85c97e87e65542434703004ef4d7 (recognized).
- Given decision (not reviewed): STATUS "Decision R3-F4". A same-environment ticket whose chain does not normalize and whose aliases do not match is ignored.

## Coverage

Delta since round 6 read in full: `src/plan.mjs` (comments at lines 63-64 and 321-322), `mutation-test.mjs` (new mutant `legacy-ticket-state-blocks`), README (rule bullet and overlap bullet), fixture e1-57 (input and expected), STATUS.md, EVIDENCE.md, TRACEABILITY.md, retro-log.json, and the repository copy of the round-6 record. The code logic did not change since round 6: only comments changed in `plan.mjs`. The round-6 lifecycle table therefore still holds, and e1-57 now adds the resolved-with-claim and unknown rows of that table as fixtures.

Lifecycle check of the new fixture: run environment party. Two legacy tickets (chain without semantics, no aliases): `SEC-LEGACY-RESOLVED` (resolved, fix claim `fix-ref`) and `SEC-LEGACY-UNKNOWN` (unknown). One valid positive with an event id and no processed events. Result: `new`, create-ticket plus count, `notificationEligible` true, `batchStatus` complete, no unresolved. This matches the code: `matches` is empty, `relatedToIssue` skips both tickets, and the state of a skipped ticket is never read.

## Gates (run by this reviewer)

- `run-fixtures.mjs`: 62 passed, 0 failed; structural 15 ok / 0 bad. PASS.
- `check-fixtures.mjs`: FIXTURE CHECK PASS.
- `mutation-test.mjs`: 125 mutants, killed 122, survived 3 (3 equivalent), noapply 0. PASS, exit 0.
- ajv (draft2020): e1-57 input, expected, and actual output valid. e1-50 input, expected, actual valid. e1-55 and e1-56 expected valid. 8 of 8 valid.
- `prettier@3 --check` on all 14 changed files: formatted.
- F4 mutations of plan.mjs:323 reproduced on the new tree: `return iss.state === "resolved";` exit 1 (killed); `return iss.state === "unknown";` exit 1 (killed); `return iss.state !== "open";` is the committed mutant (killed in the mutation gate).
- Test-first reproduction: HEAD `plan.mjs` with the current fixtures gives 58 passed, 4 failed (e1-50, e1-55, e1-56, e1-57). The EVIDENCE text "58 passed, 3 failed" describes the state before e1-57 and stays correct.
- Fixture directories: 61.
- Personal names: grep over `.feature-workspace/` and `attack-runner/` for the author and commit-history names, and for `Firstname Lastname` patterns in the round-6 copy: 0 hits.
- The repository copy `.feature-workspace/attack-runner/self-review-pr55-r6.md` is byte-identical to the round-6 record (`cmp`).

## Count verification

| Location                             | Stated                                                         | Measured     | Result                        |
| ------------------------------------ | -------------------------------------------------------------- | ------------ | ----------------------------- |
| STATUS Verification bullet           | 61 fixtures, 62 passed, 15 structural, 125 mutants, 122 killed | same         | match                         |
| STATUS Gates list                    | 62 + 15; 125/122/3/0 noapply                                   | same         | match                         |
| TRACEABILITY header                  | 61 fixtures, 125 mutants, 122 killed                           | same         | match                         |
| TRACEABILITY row                     | fixtures e1-50, e1-53..57                                      | e1-57 exists | match                         |
| EVIDENCE new entry (round 6 repairs) | 62/0 + 15; 125/122/3/0                                         | same         | match                         |
| EVIDENCE older entries               | 128/125, 117/114, 14 structural: dated records                 | n/a          | not stale                     |
| STATUS checkpoint                    | rounds 3-7; log list r3 to r7                                  | n/a          | accurate                      |
| PR #55 body                          | 47 fixtures, 48 passed, 112 mutants                            | 61, 62, 125  | stale before this change (I1) |

## Disposition of round-6 findings

| ID                   | Disposition          | Evidence                                                                                                                                                                                                                                                                       |
| -------------------- | -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| F1 STATUS stale text | fixed-and-verified   | Action 6 is struck and says "decided ... and implemented". The checkpoint says rounds 3-7. The retired `unc-*` mutants and `uncomparable-off` carry a "retired" note. No "Implement it" remains.                                                                               |
| F2 code comments     | fixed-and-verified   | The `validateInput` comment has no review label and no "alias matches" wording. A comment at plan.mjs:321-322 states the rule at the line that implements it. No `R3-F4` remains in `src/`.                                                                                    |
| F3 term "comparable" | partly fixed: see F5 | README, STATUS decision text, and the `plan.mjs` comments now use "legacy ticket" with one definition (chain does not normalize). The README overlap bullet says "existing ticket with a normalized chain (any state)". Two restatements still use "comparable identity" (F5). |
| F4 state gap         | fixed-and-verified   | e1-57 and `legacy-ticket-state-blocks` kill the resolved and unknown variants (reproduced). Residual: see I2.                                                                                                                                                                  |

## Fixture directory names "uncomparable" (e1-50, e1-54)

Acceptable. Every document and the tests refer to these fixtures by the `e1-NN` prefix. The README no longer uses the word. The directory name is an identifier, not a statement of a rule. A rename changes 4 references and gains no behavior. Keep the names. This is informational and not counted.

## Additions sub-checks

1. Supersession: the old rule appears only in dated EVIDENCE entries and in the older retro-log entry (dated history). The README, the STATUS decision, the TRACEABILITY row, and the code comments state the new rule. No contradictory pair found.
2. Effect-claim trace: "whatever its state" (README, STATUS) holds in code (no state read). It is pinned for open, resolved, and unknown (I2 for the unrecognized state). "Matches only through a fingerprint alias" holds (plan.mjs:285-291). "The mutant `legacy-ticket-state-blocks` pins the rule for resolved and unknown tickets" holds (reproduced).
3. Acceptance-case parity: the new mutant has its fixture (e1-57). The new comments add no behavior.
4. Distinguishability: no new signal claim.
5. Cross-reference propagation: counts agree everywhere (table). The term "comparable identity" survives in two restatements (F5). The PR body does not state the rule.
6. Anchor-event and branch-outcome completeness: EVIDENCE and STATUS name `self-review-pr55-r7.md`, "added verbatim after a pass". The branch outcome (fail, repair, new round) is stated below.

## Findings

### F5 (Low, cross-reference propagation) .feature-workspace/attack-runner/TRACEABILITY.md:26

The row says "Ticket without comparable identity is ignored". The round-6 correction (F3) replaced this term with "legacy ticket" in README, STATUS, and `plan.mjs`. The same phrase remains in `.feature-workspace/attack-runner/retro-log.json` (new entry: "A ticket without a comparable identity takes no part in matching"). The old phrase also means something different (chain does not normalize and no alias) from the new definition (chain does not normalize). Correction: write "Legacy ticket (chain does not normalize) is ignored: matches only by alias, never blocks `new` (decision R3-F4, 2026-10-03)" in the TRACEABILITY row, and use "legacy ticket" in the retro-log note. Disposition: open.

### Informational (not counted)

- I1: the PR #55 body states 47 fixtures, 48 passed, 112 mutants. These numbers were stale before this change. Update them when the PR goes to ready-for-review.
- I2: the fixtures pin the state-independence for open, resolved, and unknown. A variant that blocks only for an unrecognized state string passes the gate (reproduced: `iss.state !== "open" && iss.state !== "resolved" && iss.state !== "unknown"`, exit 0). The README says "whatever its state". The risk is low, because no plausible implementation reads the state of a skipped ticket for one garbage value only. Add a third legacy ticket with an unrecognized state to e1-57 if the claim must be literal.
- I3: the planner gives no signal when it ignores a legacy ticket. The decision accepts this risk.

## Arrangement check: records in the repository

Acceptable. The round-6 copy is byte-identical and records a `fail` with the repairs listed in EVIDENCE. The round-7 file is added only after a `pass`, in the same push as the commit, as a byte-for-byte copy. It contains no personal name and passes `prettier --check`. EVIDENCE.md and STATUS.md carry no round-7 verdict text.

## Counts

- New comments: 1 (F5).
- Unresolved comments: 1. F1, F2, F4 are closed. F3 is closed except for F5.
- Missed blockers in unchanged code: none found.

## Verdict: fail

All gates are green and the code is correct on every path. One Low finding remains: the retired term "comparable identity" in the TRACEABILITY row and the retro-log note (F5). A mixed result blocks the commit. After the repair, review the delta (two documentation lines), then copy the pass record.

## Rechecks

- Commands run: the three gate scripts; ajv for e1-50, e1-55, e1-56, e1-57; `prettier@3 --check` on 14 files; name greps; `cmp` of the round-6 copy; `git diff HEAD` comparison with `candidate-r7.diff`; three state mutations of plan.mjs:323 in scratch copies; the test-first reproduction with the HEAD `plan.mjs`.
- Invalidated evidence: none. The round-6 trace holds because only comments changed in the code.
- Next stage: repair F5, run the gates again (documentation only), review the delta, then commit with the pass record in the same push.
- Elapsed time and cost: not measured.
