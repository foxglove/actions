# Self-review PR 55, round 13

## Identity

- Repository: foxglove/actions, PR 55, branch `claude/exciting-cerf-vkmwu5`.
- Base of the candidate: HEAD `aaaf8b0`. Candidate: the uncommitted diff against HEAD, frozen as `pr55-r13.diff` (7 files, 214 insertions, 10 deletions).
- Previous review: round 12 (`self-review-pr55-r12.md`, verdict fail, 7 findings). This is round 2 for this commit.
- Dependency: docs PR foxglove/actions#57 at commit `ad2ae4d` (unchanged since round 12).
- Mode: isolated reviewer. Review only. No repository file was changed.

## Verdict

**fail.** 2 new findings (0 High, 0 Medium, 2 Low). All 7 findings of round 12 are fixed and verified. Unresolved carried findings: 0. Unresolved total: 2.

## Dispositions of round 12

| ID  | Disposition        | Evidence                                                                                                                                                                                                                                                              |
| --- | ------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| F1  | fixed-and-verified | The schema no longer says an alias ends the reminder. It says "an alias alone does not remove it". Fixtures e1-53 (`SEC-ALIAS`) and e1-59 (`SEC-AMB1`, `SEC-AMB2`) list tickets that have aliases.                                                                    |
| F2  | fixed-and-verified | "Listed on every run" is removed from the README, the code comment, the schema, STATUS and EVIDENCE. The new text says the list does not depend on whether the run creates a ticket. The exclusions stay in the sentence before it. STATUS adds the environment rule. |
| F3  | fixed-and-verified | Rows 1 and 7 of the PM gate table carry "Superseded 2026-10-03". The cross-reference in those notes is wrong (see F9).                                                                                                                                                |
| F4  | fixed-and-verified | STATUS records that the Foundations team is the release authority (PR 56), so it is the operator. This matches `attack-runner.md` in the #57 worktree.                                                                                                                |
| F5  | fixed-and-verified | `STATUS.md:52` now says "table below". The table starts at line 112.                                                                                                                                                                                                  |
| F6  | fixed-and-verified | The intro of `pm-clarifications.md` is in the past tense, says all items are answered, and says items 1 and 2 were flagged when written.                                                                                                                              |
| F7  | fixed-and-verified | The item 1 answer states that the Foundations team owns the test identity (matches `attack-sessions.md`, "Product decisions"). The item 8 answer is conditional on the I-23 probe (matches `attack-runner.md`, "Edge controls must not hide missing coverage").       |

## Coverage

- Inspected: the full delta (README, schema description, `plan.mjs` comment, STATUS, EVIDENCE, `pm-clarifications.md`, the copied round 12 record) and the code at `src/plan.mjs:529-550`.
- `self-review-pr55-r12.md` in the workspace is byte-identical to the round 12 record (checked with `cmp`).
- Gates:
  - `node attack-runner/planner/run-fixtures.mjs`: 64 passed, 0 failed, structural 15 ok, 0 bad.
  - `npx prettier@3 --check attack-runner .feature-workspace`: pass.
- Personal names: none in the diff. Teams and roles only.
- Links: the link list of `pm-clarifications.md` is unchanged from round 12 (16 links, 0 bad). The new answer text changes no link.

## Eligibility wording against the code

The code lists an issue when all three conditions hold:

1. `normEnv(targetEnvironment)` equals `normEnv(runEnv)`.
2. `normalizeChain(normalizedChain)` is null.
3. No `decisions[].target.issueId` and no `notObserved[].issueId` equals its `issueId`.

The create-ticket state is not read. Findings against the new text:

- "Does not depend on whether the run creates a ticket": matches the code. Fixtures e1-50 to e1-57 (create) and e1-58, e1-59 (no create) pin both cases.
- "Stays eligible until its chain normalizes": matches condition 2. A normalized chain makes the ticket not legacy.
- "An alias alone does not remove it": matches. An alias does not enter the filter. Only a match through the alias creates a decision with `target.issueId`, which is condition 3. The text states this exclusion in the sentence before it ("no decision targets"), but it does not say that an alias match is the way a decision targets a legacy ticket. e1-58 `SEC-ALIAS` and e1-59 `SEC-CLAIM` are absent for this reason.
- The term "eligible" is new in this change (F8).

## Findings

### F8 (Low, open): "eligible" names a second concept

- Locations: `attack-runner/planner/README.md:75`, `attack-runner/planner/src/plan.mjs:533`, `.feature-workspace/attack-runner/STATUS.md:82`.
- Trace: the code and the schema already use `eligible` and `notificationEligible` for notification eligibility (`plan.mjs:359-521`, schema `notificationEligible`). The new sentence uses "eligible" for list membership. One word then has two meanings. The sentence "A ticket stays eligible until its chain normalizes" also hides the exclusion path. A ticket with an alias leaves the list on a run where an observation matches the alias, because a decision then targets it.
- Effect: a reader who adds an alias to a legacy ticket cannot tell from the text why the ticket disappears on one run and returns on the next.
- Smallest fix: write "A ticket is listed on each run until its chain normalizes, except on a run where a decision targets it or a non-observation references it. An alias alone does not end the reminder."

### F9 (Low, open): "see below" points to a section above

- Location: `.feature-workspace/attack-runner/STATUS.md:126` (row 1 note) and `:132` (row 7 note).
- Trace: both notes end with "(see below)". The section "Decisions recorded in the product docs" is at line 50. The table starts at line 112. The section is above the table. This is the same direction error as round 12 F5, in new text.
- Smallest fix: write "(see above)", or name the section: "(see 'Decisions recorded in the product docs')".

## Additions sub-checks

- Supersession reconciliation: the rows 1 and 7 notes, the item 10 bullet, and the intro of `pm-clarifications.md` reconcile the old text. Row 10 is not marked superseded, but the new bullet states the transition is complete and row 10 is not contradicted. No finding. Residual: the `retro-log.json` entries are append-only history and keep the `Triage` text. They are not restatements of a current rule.
- Effect-claim trace: the three claims in the new wording hold under the code's guards (see the section above). F8 covers the unstated exclusion.
- Acceptance-case parity: no field or rule is added. Existing fixtures pin both halves. No finding.
- Distinguishability trace: not applicable.
- Cross-reference propagation: searched for "eligible", "every run", "until it is backfilled", "risk applies", "table above" and "see below" across the changed set. Findings F8 and F9. No other location states the old rule.
- Anchor-event and branch-outcome completeness: the exclusion branches (decision target, non-observation reference, other environment) are in the sentence before the new text in the README and schema. They are not repeated in the new sentence (F8).

## Observation (not counted)

The copy of the round 12 record in the workspace ends with a section "Copy of this record into the workspace". That section was an instruction to the author. It is now a stale sentence inside a durable record. The process requires a verbatim copy, so no change is requested.

## Rechecks

- `run-fixtures.mjs`: 64 passed, 0 failed, 15 structural ok.
- `prettier@3 --check`: pass.
- Mutation test and `check-fixtures.mjs` were not run. The delta changes no planner logic.
- Cost and elapsed time: unavailable.

## Next stage

Repair F8 and F9, then run round 14 on the new diff. This is a fail record. The EVIDENCE entry for round 13 says "added verbatim after a pass". Copy this record only after the verdict is pass, or change the reference to the round that passes.

## Copy of this record into the workspace

The file name `self-review-pr55-r13.md` is acceptable. The record has no personal names and passes prettier. Do not copy it as a pass record.
