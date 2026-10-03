# Self-review PR #55, round 8 (isolated delta recheck after the round-7 repair)

## Review identity

- Mode: isolated reviewer, review only. No repository edit, commit, push, or GitHub post.
- Base: main. Previous reviews: round 3 (fail), round 4 (fail), round 5 (pass), round 6 (fail, F1-F4), round 7 (fail, F5; record `self-review-pr55-r7.md`).
- Candidate: the working tree on branch claude/exciting-cerf-vkmwu5 compared with HEAD 7503a34. New files are intent-to-add. `candidate-r8.diff` is byte-identical to `git diff HEAD`.
- Prompt: prompts/review.md at the PR head, sha256 c007116786a0bb1064a99229a375ab8f773d85c97e87e65542434703004ef4d7 (recognized).
- Given decision (not reviewed): STATUS "Decision R3-F4". A same-environment ticket whose chain does not normalize and whose aliases do not match is ignored.

## Coverage

The diff of round 8 against `candidate-r7.diff` was computed per file. Four files changed: `EVIDENCE.md`, `STATUS.md`, `TRACEABILITY.md`, `retro-log.json`. One file was added: `.feature-workspace/attack-runner/self-review-pr55-r7.md`. No file under `attack-runner/` changed since round 7, so the code, the fixtures, the mutants, and the README are the content that rounds 6 and 7 reviewed. The round-6 lifecycle table and the round-7 trace therefore hold without change.

Read in full: the four changed documents (delta), the repository copy of the round-7 record, and the README, `plan.mjs` and `mutation-test.mjs` hits for "comparable".

## Gates (run by this reviewer)

- `run-fixtures.mjs`: 62 passed, 0 failed; structural 15 ok / 0 bad. PASS.
- `check-fixtures.mjs`: FIXTURE CHECK PASS.
- `mutation-test.mjs`: skipped by the rule in the request. The skip is valid: the per-file diff comparison shows no change under `attack-runner/` since round 7, and the mutation gate reads only `attack-runner/`. The round-7 result stands: 125 mutants, 122 killed, 3 equivalent, 0 noapply, exit 0.
- ajv: not re-run for the same reason (inputs, expected outputs, and the planner are unchanged). The round-7 result stands: 8 of 8 valid.
- `prettier@3 --check` on all 15 changed files (including both record copies): formatted.
- `retro-log.json` parses as JSON.
- Fixture directories: 61.
- Personal names: grep over `.feature-workspace/` and `attack-runner/` for the author and commit-history names: 0 hits.
- The repository copy `self-review-pr55-r7.md` is byte-identical to the round-7 record (`cmp`).

## Count verification

| Location                           | Stated                                                             | Measured    | Result                        |
| ---------------------------------- | ------------------------------------------------------------------ | ----------- | ----------------------------- |
| STATUS Verification bullet         | 61 fixtures, 62 passed, 15 structural, 125 mutants, 122 killed     | same        | match                         |
| STATUS Gates list                  | 62 + 15; 125/122/3/0 noapply                                       | same        | match                         |
| TRACEABILITY header and row        | 61 fixtures; 125/122; e1-50, e1-53..57                             | same        | match                         |
| EVIDENCE round-6 repairs entry     | 62/0 + 15; 125/122/3/0                                             | same        | match                         |
| STATUS checkpoint and log list     | rounds 3-8; r3 to r8                                               | n/a         | accurate                      |
| EVIDENCE round 7 and round 8 lines | verdict fail on F5; r8 record named, "added verbatim after a pass" | n/a         | accurate                      |
| PR #55 body                        | 47 fixtures, 48 passed, 112 mutants                                | 61, 62, 125 | stale before this change (I1) |

## Disposition of the round-7 finding

| ID  | Disposition        | Evidence                                                                                                                                                                                                                                                                                                                                                                                                   |
| --- | ------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| F5  | fixed-and-verified | The TRACEABILITY row now says "Legacy ticket (chain does not normalize) is ignored (decision R3-F4, 2026-10-03)". The retro-log note now says "A legacy ticket (its chain does not normalize) matches only through a fingerprint alias, takes no part in overlap triage, and never blocks a new ticket, whatever its state". Both match the README, the STATUS decision text, and the `plan.mjs` comments. |

Round-6 findings stay closed: F1, F2, F4 fixed-and-verified (round 7); F3 is closed through F5.

## Additions sub-checks

1. Supersession: the old rule appears only in dated history (EVIDENCE entries, the round-3 retro-log entry, the retired-mutant note in STATUS). The current statements agree. No contradictory pair found.
2. Effect-claim trace: the retro-log claim "matches only through a fingerprint alias ... whatever its state" holds in code (`plan.mjs:285-291` and `:323`, no state read) and is pinned by e1-50, e1-55, e1-56, e1-57 and the two mutants. The EVIDENCE round-7 line says the term was repaired in TRACEABILITY and retro-log. That holds.
3. Acceptance-case parity: no new required value or rule in this delta.
4. Distinguishability: no new signal claim.
5. Cross-reference propagation for "comparable": grep over `.feature-workspace/` and `attack-runner/` finds hits only in dated history and in retired-name notes. These are the round-3 retro-log entry ("uncomparable rule"), the STATUS note on the retired mutants (`unc-*-comparable`, `uncomparable-off`), the EVIDENCE round-2 to round-6 entries, and the round-2 to round-7 records. The README, `plan.mjs`, the STATUS decision text, the TRACEABILITY row, and the current retro-log note use "legacy ticket". The fixture directory names e1-50 and e1-54 keep the old word; round 7 judged that acceptable, and that judgment stands. Other terms checked: "backfill" (README and STATUS only, with one meaning), "blocks" (current text says a legacy ticket never blocks `new`), and the counts (table).
6. Anchor-event and branch-outcome completeness: EVIDENCE and STATUS name `self-review-pr55-r8.md` with "added verbatim after a pass". The outcome of each branch of the review (pass, fail) is stated below.

## Findings

None.

Informational (not counted; carried from round 7, no action required for this commit):

- I1: the PR #55 body states 47 fixtures, 48 passed, 112 mutants. These numbers were stale before this change. Update them when the PR goes to ready-for-review.
- I2: no fixture holds a legacy ticket with an unrecognized state string. A variant that blocks only for that value passes the gate. The risk is low.
- I3: the planner gives no signal when it ignores a legacy ticket. The decision accepts this risk.

## Arrangement check: records in the repository

Acceptable. The round-6 and round-7 copies are byte-identical to their records and show the fail verdicts and the repairs. The round-8 file is added after this pass, as a byte-for-byte copy, in the same push as the commit. It contains no personal name and passes `prettier --check`. EVIDENCE.md and STATUS.md carry no round-8 verdict text and point to the file. The only change after this review is the single addition of this record. Any other change needs a new review.

## Counts

- New comments: 0.
- Unresolved comments: 0.
- Missed blockers in unchanged code: none found.

## Verdict: pass

Complete coverage, zero comments, gates green. F5 is fixed-and-verified, and F1-F4 stay closed. The mutation test and ajv were not re-run because no file under `attack-runner/` changed since round 7. This pass applies to the candidate as reviewed plus the single addition of this record.

## Rechecks

- Commands run: per-file comparison of `candidate-r7.diff` and `candidate-r8.diff`; `cmp` of `candidate-r8.diff` with `git diff HEAD` and of the round-7 copy with the record; `run-fixtures.mjs`; `check-fixtures.mjs`; `prettier@3 --check` on 15 files; JSON parse of `retro-log.json`; grep for "comparable" and for the names; fixture directory count.
- Invalidated evidence: none.
- Next stage: copy this record as `.feature-workspace/attack-runner/self-review-pr55-r8.md`, commit with it in one push, push, then reply on the PR and mark it ready for review after CI passes.
- Elapsed time and cost: not measured.
