# Self-review PR 55, round 12

## Identity

- Repository: foxglove/actions, PR 55, branch `claude/exciting-cerf-vkmwu5`.
- Base of the candidate: HEAD `aaaf8b0`. Candidate: the uncommitted diff against HEAD (208 lines, 6 files).
- Previous review: round 11 (`self-review-pr55-r11.md`).
- Dependency: docs PR foxglove/actions#57 (branch `claude/aegis-pm-decisions-docs`, commit `ad2ae4d`). Its base is PR #56 (branch `claude/confident-dirac-zal2xi`). The stack was read through the GitHub REST API.
- Mode: isolated reviewer. Review only. No file in the repository was changed.

## Verdict

**fail.** 7 new findings: 0 High, 2 Medium, 5 Low. Unresolved carried findings: 0. All 7 are open.

## Coverage

- Inspected: the full diff; `attack-runner/planner/src/plan.mjs` (the `ignoredLegacyIssues` code and the `validateInput` comment); the README, schema, STATUS (all sections, including the PM gate table), EVIDENCE, TRACEABILITY and `retro-log.json`; fixtures e1-50, e1-53, e1-55 to e1-59 (inputs and expected outputs); the #57 worktree docs `attack-sessions.md`, `attack-paths.md`, `attack-runner.md`, `exploit-findings.md` and `engineering-handoff.md`.
- Gates:
  - `node attack-runner/planner/run-fixtures.mjs`: 64 passed, 0 failed, structural 15 ok, 0 bad.
  - `npx prettier@3 --check attack-runner .feature-workspace`: all files pass.
  - Mutation test and `check-fixtures.mjs` were not run. The diff changes no planner logic, only one code comment.
- Personal names: none in the diff. The words checked were the user handle and the email domain. The diff names teams and roles only (Foundations team, Infra team, Engineering, the CEO, the release authority).
- Objectives 1 and 6 (correctness, tests): the planner behavior is unchanged. A script over all fixtures confirmed that e1-58 and e1-59 have no `create-ticket` action and a non-empty list. Fixtures e1-50, e1-53, e1-55, e1-56 and e1-57 pin the other half: a `create-ticket` run with a non-empty list. The mutants `ignored-legacy-*` exist in `mutation-test.mjs`.
- Objectives 2, 4, 5 and 8: not affected by the change.
- Objective 3 and 7 (comments, documentation): findings F1 to F7.
- Lifecycle branches: no code branch is added. The branch table below covers the one changed rule.

| Trigger and prior state                                      | Acting component | Evidence it can observe       | Stored state and permitted action | Terminal result and observable check                           |
| ------------------------------------------------------------ | ---------------- | ----------------------------- | --------------------------------- | -------------------------------------------------------------- |
| Legacy ticket in the run environment, no decision targets it | `plan()`         | `existingIssues`, `decisions` | None                              | Listed. e1-58 `SEC-IDLE`; e1-59 `SEC-ZIDLE`                    |
| Legacy ticket, an alias match makes a decision target it     | `plan()`         | same                          | None                              | Not listed on that run. e1-58 `SEC-ALIAS`; e1-59 `SEC-CLAIM`   |
| Legacy ticket, a non-observation references its `issueId`    | `plan()`         | `notObserved`                 | None                              | Not listed on that run. e1-58 `SEC-RETEST`                     |
| Legacy ticket with an alias, ambiguous or unmatched this run | `plan()`         | same                          | None                              | Listed. e1-53 `SEC-ALIAS`; e1-59 `SEC-AMB1`, `SEC-AMB2`        |
| Legacy ticket in another environment                         | `plan()`         | `targetEnvironment`           | None                              | Not listed                                                     |
| Ticket with a normalized chain                               | `plan()`         | `normalizeChain`              | None                              | Not legacy, never listed                                       |
| Run creates a ticket, or creates none, with a legacy ticket  | `plan()`         | `decisions`                   | None                              | Listed in both cases. e1-50 to e1-57 (create) and e1-58, e1-59 |

## Checks of the three changes

### (a) Backfill-reminder wording

- The code lists a ticket when the environment matches, `normalizeChain` returns null, and no decision or `notObserved` entry references the `issueId`. It does not look at `create-ticket`. The statement "whether or not the run creates a ticket" is true. Fixtures e1-58 and e1-59 pin it, and the other fixtures pin the create case.
- No older text still says the list shows only "when the risk applies". `grep` for "risk applies" in the README, schema, STATUS, EVIDENCE and code finds only the question text in STATUS:72. That line is the question of the earlier decision, and the follow-up decision follows it.
- The new wording over-claims in two places (F1, F2). "Until it is backfilled" and "on every run" do not match the exclusions in the code.

### (b) PM decision index

- All 16 links in `pm-clarifications.md` resolve in the #57 worktree: every target file exists and every anchor matches a heading (checked with a script, 0 bad). The relative paths are correct from `.feature-workspace/attack-runner/`.
- Answers 2, 3, 4, 5, 6, 7, 9 and 11 match the decision table and the docs. Answers 1, 8 and 10 state less or differ (F4, F7).
- The links point to anchors that exist only after #57 merges. This is a merge-order dependency of #55 on #57, not a defect. The files exist on `main` already.

### (c) STATUS and EVIDENCE

- The EVIDENCE gate line matches the run: 64 passed, 0 failed, 15 structural-reject, prettier clean.
- "Stacked on foxglove/actions#56" is true (the REST API shows the base of #57 is the head of #56).
- The statements "foxglove/app#19116" and "five isolated review rounds" were not verifiable from this environment. They are author claims.

## Findings

### F1 (Medium, open): the schema says an alias ends the reminder, but an alias does not

- Location: `attack-runner/planner/schema/planner-output.schema.json:152`.
- Trace: the text says a ticket is listed "until it gets a normalized chain or an alias". `plan()` treats a ticket as legacy when `normalizeChain` returns null. An alias does not change that. Fixture e1-53 lists the alias-only ticket `SEC-ALIAS`. Fixture e1-59 lists `SEC-AMB1` and `SEC-AMB2`, which have aliases. A ticket with an alias leaves the list only on a run where a decision targets it.
- Effect: a consumer who adds an alias expects the reminder to stop. The reminder continues until a normalized chain exists.
- Smallest fix: write "until it gets a normalized chain. A ticket that has an alias is omitted only on a run where a decision targets it."

### F2 (Low, open): "listed on every run" omits the exclusions

- Locations: `attack-runner/planner/README.md:74`, `attack-runner/planner/src/plan.mjs:532`, `.feature-workspace/attack-runner/STATUS.md:78`, `.feature-workspace/attack-runner/EVIDENCE.md:172`.
- Trace: the text says a ticket is listed "on every run". The code omits it on a run where a decision targets it or a non-observation references it (e1-58 `SEC-ALIAS`, `SEC-RETEST`; e1-59 `SEC-CLAIM`). The code also omits it on a run in another environment. The README sentence before it states the exclusions, but the new sentence states the absolute rule.
- Smallest fix: write "on every run in its environment where no decision targets it and no non-observation references it".

### F3 (Medium, open): the PM gate table still states two superseded decisions

- Location: `.feature-workspace/attack-runner/STATUS.md:122` (row 1) and `:128` (row 7).
- Trace: row 7 says "ambiguous reconciliation → `Triage`" and "Mapping confirmed by PM", and its notes say the mapping "aligns with ... ambiguous → triage". The new section at STATUS:56 says an ambiguous reconciliation creates no ticket and that there is no `Triage` mapping. Row 1 says the issuer team owns the "test identity". The new section at STATUS:58 says the Foundations team owns the test service account entirely. The change adds the new rule but does not reconcile the old rows. The index answers are meant to be checked against this table.
- Effect: two contradictory statements stay in the document set. A reader of the table alone implements a `Triage` mapping.
- Smallest fix: edit rows 1 and 7 to the new decision. Mark the old text as superseded on 2026-10-03.

### F4 (Low, open): the item 10 answer is not in the decision table

- Location: `.feature-workspace/attack-runner/pm-clarifications.md:84`.
- Trace: the answer says "the Foundations team is the operator". Table row 10 says the operator is "the release authority for now, transitioning to the Foundations team". The docs (`attack-runner.md`, "Runs are weekly and manually invocable") record the Foundations team as the operator. Commit `6b1bbfa` in #57 records the Foundations team as the release authority. STATUS:51-67 does not list this change among the decisions made while writing the docs.
- Smallest fix: add a bullet to the STATUS section "Decisions recorded in the product docs": the release authority is the Foundations team, so the operator transition is complete.

### F5 (Low, open): "table above" points the wrong way

- Location: `.feature-workspace/attack-runner/STATUS.md:52`.
- Trace: the section is at line 51. The PM gate table starts at line 108. The table is below.
- Smallest fix: write "table below".

### F6 (Low, open): the introduction still says the items are open

- Location: `.feature-workspace/attack-runner/pm-clarifications.md:4` and `:9`.
- Trace: line 4 says "These are the open product decisions that gate the Stage-1 to Stage-2 handoff". Line 9 says "Items 1-2 are flagged proposed/pending in the docs themselves". The new Status paragraph at line 94 says every item is answered. Both statements coexist.
- Smallest fix: change the introduction to past tense, or start the file with the Status paragraph. Say that the file is an index.

### F7 (Low, open): two answers state less than the docs record

- Location: `.feature-workspace/attack-runner/pm-clarifications.md:19` and `:69`.
- Trace, item 1: the question names the owner of the "test identity". The answer names the issuer function and mailbox access only. The docs (`attack-sessions.md`, "Product decisions") state that the Foundations team owns the company test identity. The answer to item 3 carries this fact, but item 1 does not.
- Trace, item 8: the answer states the policy approval without its condition. The docs and the table make it conditional on a blocked runner path (probe I-23).
- Smallest fix: add "the Foundations team owns the test identity" to the item 1 answer. Add "if the runner path is blocked" to the item 8 answer.

## Additions sub-checks

- Supersession reconciliation: F3, F4, F6 (a new rule or status coexists with old text).
- Effect-claim trace: F1 and F2 (the reminder claim does not hold under the code's own guards).
- Acceptance-case parity: no new field or rule is added. The existing fixtures pin both halves of the changed claim. No finding.
- Distinguishability trace: not applicable.
- Cross-reference propagation: searched for "risk applies", "ignoredLegacy", "triage" and "test identity" across the changed document set. Findings F2, F3 and F5.
- Anchor-event and branch-outcome completeness: the new wording names no event. F2 shows the missing exclusion branches.

## Rechecks

- `node attack-runner/planner/run-fixtures.mjs`: 64 passed, 0 failed, structural 15 ok, 0 bad.
- `npx prettier@3 --check attack-runner .feature-workspace`: pass.
- Link check: 16 links, 0 missing files, 0 missing anchors.
- Cost and elapsed time: unavailable.

## Next stage

Repair F1 to F7, then run round 13 on the new diff. This record is a fail record.

## Copy of this record into the workspace

The file name `self-review-pr55-r12.md` is acceptable for the copy. The record has no personal names and passes prettier. The EVIDENCE and STATUS references say the record is added "verbatim after a pass". This record is a fail. Copy it only if the verdict is changed by a repair round. Otherwise rename the references to the round that passes, and keep this record as the round 12 fail record.
