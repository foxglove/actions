# EVIDENCE — append-only stage verdicts

## 2026-10-03 — Stage 2 (semantic model + plan)

- Verdict: **pass** (engineering-lead approved the work-packet breakdown).
- Reviewed: product docs, acceptance criteria, engineering handoff, attack-path
  instructions, attack-sessions product decisions, and the feature-pipeline skill.
- Artifact: approved plan + this feature workspace.
- Open: 11 PM clarification items recorded as the Stage-1→2 gate (`STATUS.md`).
- cost: unavailable (cloud session transcript not local; per Claude adapter).

## 2026-10-03 — WP0.1 (offline planner contract + fixtures) — in progress

- Artifact: `attack-runner/planner/` (input/output JSON Schema, fixtures, README).
- Oracle: schema review + fixtures exercising every E1 reconciliation branch.
- Exit evidence pending: executable validation is WP1.\* (planner not yet implemented).
- cost: unavailable.

## 2026-10-03 — WP1.1–WP1.4 (planner implementation)

- Artifact: `attack-runner/planner/src/{normalize,plan,index}.mjs` + `run-fixtures.mjs`.
- Oracle: `node attack-runner/planner/run-fixtures.mjs` → **7 passed, 0 failed**
  (semantic assertions; determinism + input-immutability checked).
- Guard: `node attack-runner/planner/check-fixtures.mjs` → PASS.
- Schema: all fixture inputs validate against the updated input schema (ajv draft2020).
- Negative control: oracle confirmed to reject a deliberately wrong engine.
- Self-review: isolated adversarial review launched; result pending in `review-wp1.md`.
- cost: unavailable (cloud session transcript not local).

## 2026-10-03 — WP1.1–WP1.4 review + repair (round 1)

- Isolated adversarial review: 1 blocker, 8 major, 8 minor (`review-wp1.md`).
- Repaired B1, M1, M2, M4, M6, M8 and m2/m4/m5/m8 (+ M3a); remainder routed to E1 slices.
- Oracle `run-fixtures.mjs`: **9 passed, 0 failed**, + 3 structural-reject PASS;
  invariants asserted on actual output; determinism, permutation-invariance, immutability.
- `check-fixtures.mjs`: PASS. Inputs validate against input schema; all actual outputs
  validate against output schema (ajv draft2020).
- cost: unavailable (cloud transcript not local).

## 2026-10-03 — WP1 E1 coverage complete (remaining slices)

- Added fixtures E1-05, E1-06, E1-07, E1-09, E1-10, E1-11, E1-14, E1-18, E1-19, E1-20
  (E1-13 covered by e1-12). Logic added: fingerprint aliases (E1-20), no-impact-promotion
  oracle invariant (E1-14).
- Oracle: **19 passed, 0 failed** + 3 structural-reject. Guard PASS. Inputs and all actual
  outputs validate against the schemas (ajv draft2020).
- cost: unavailable (cloud transcript not local).

## 2026-10-03 — WP1 round-2 review + repair

- Round-2 isolated review: 1 blocker, 9 major, 9 minor; 39/60 wrong engines had passed the
  old oracle (`review-wp1-round2.md`).
- Reworked the representation and oracle: round-trippable structured ticket material;
  strict input validation; state/validity validation; count-by-matched-identity; partial-
  chain triage + duplicate-step collapse; append-remediation; run status in the summary.
- Oracle rebuilt to deep-equal authored full expected (minus prose) + invariants on actual
  - round-trip + mutation self-test + schema validation. Result: **21 passed, 0 failed** +
    5 structural-reject; inputs, expected, and all actual outputs valid (ajv draft2020);
    guard PASS.
- cost: unavailable (cloud transcript not local).

## 2026-10-03 — WP1 round-3 repair + mutation convergence gate

- Round-3 review: NOT CONVERGED (1 blocker/3 major/6 minor); the blocker was a coverage gap
  (46/112 wrong engines passed the fixture-only oracle).
- Added committed `mutation-test.mjs`; drove survivors 46 → 15 → **4** (all documented
  equivalents) by adding 27 behavior fixtures and fixing genuine bugs (replay count-mark,
  usable-identity validation, in-run partial triage, strict claimed boolean, non-prod impact
  downgrade, dup observationId, schema alignment, path-aware strip, frozen-clone aliasing).
- Found+fixed a real order-dependent counting bug via the harness (replayed obs suppressing a
  fresh same-run count).
- Gates: run-fixtures 48/0 + 5 structural-reject; check-fixtures PASS; mutation-test 102 killed
  / 0 unexpected; ajv valid (ex. 4 marked negative-input fixtures). R3-M3 left as an open
  acceptance-owner question.
- cost: unavailable (cloud transcript not local).

## 2026-10-03 — PR #55 review round + isolated self-review

- Claude PR review (2 batches) + a required isolated self-review (verdict HOLD: 3 major,
  5 minor) before pushing. Fixes: idempotency fp-key double-count; in-run duplicate stays
  `new`+none; partial-overlap triage is state-independent and no longer skips non-open
  tickets (F1); an uncomparable legacy ticket no longer throws the batch — it triages the
  would-be-new finding (F2); input validation (dup id, fixClaim boolean, runId, issue env,
  processedEvents entry) and the new logic are now pinned by structural tests + mutants (F3);
  CI workflow push→main + actions @v6 + dead overlap guard removed; README outcomes table
  corrected; ≤1-create-ticket-per-fingerprint oracle invariant added; names replaced with
  team/role (public repo); stale counts corrected.
- Gates: run-fixtures **57/0** + 9 structural-reject; check-fixtures PASS; mutation-test
  **117 mutants, 114 killed, 0 unexpected** (3 equivalents), 0 noapply; ajv valid.
- Deferred/minor: in-run duplicate remediation-union (F4) and duplicate-observationId
  dedup-vs-reject (F5) — documented on the PR threads. product-docs/attack-sessions.md on
  `main` still names an individual (source contract, outside this PR) — flagged to the user.
- cost: unavailable (cloud transcript not local).

## 2026-10-03 — PR #55 review round 2 (session 2)

- Resumed from the checkpoint. bb8aaa9 (M2 fixtures e1-53..56 + mutants, L2, L5) and 2d93dfb
  (README triage rules, workspace de-personalization) were pushed **without** the isolated
  self-review gate: an escape (workflow failure), recorded in `retro-log.json`.
- External Claude review on c6872b4 raised T1–T4. T1, T2, T4 fixed in bb8aaa9/2d93dfb; T3
  (count-per-identity oracle invariant never asserted) fixed in this candidate.
- Isolated self-review round 3 (`self-review-pr55-r3.md`, effective prompt
  `prompts/review.md` sha256 c0071167…ef4d7, recognized): verdict fail on F1 (stale counts),
  F2 (whitespace alias untested), F3 (stale comment), F4 (uncomparable rule has no acceptance
  owner). F1–F3 repaired; F4 routed to the acceptance owner (STATUS "R3-F4", TRACEABILITY row).
- Self-review round 4 (`self-review-pr55-r4.md`): verdict fail on F5 (names in the copied r3
  record), F6 (stale STATUS checkpoint), F7 (retro-log wording and stage), F8 (this entry had
  no gate record), F9 (R3-F4 omitted that a ticket in any state blocks). All five repaired.
  Gates on the round-4 candidate: run-fixtures 61/0 + 14 structural-reject; check-fixtures
  PASS; mutation-test 128 mutants, 125 killed, 3 equivalent, 0 noapply; ajv valid for e1-53..56.
- Round 5 record: `self-review-pr55-r5.md` (added verbatim after the round completes).
- cost: unavailable (cloud transcript not local).

## 2026-10-03 — Decision R3-F4: ignore legacy tickets (session 2)

- Human oracle: the user, as the product decision authority, answered the R3-F4 question:
  ignore legacy tickets. Recorded in STATUS ("Decision R3-F4") and `retro-log.json`.
- Stage 3, test first: e1-50, e1-55 and e1-56 changed to expect `new`; run-fixtures then
  reported 58 passed, 3 failed (the expected failure). After the triage branch was removed:
  61 passed, 0 failed.
- Gates after the code change: run-fixtures 61/0 + 15 structural-reject; check-fixtures
  PASS; mutation-test 124 mutants, 121 killed, 3 equivalent, 0 noapply.
- Same session: the user confirmed `.feature-workspace` stays (thread resolved), approved a
  follow-up PR that removes names from `product-docs/attack-sessions.md`, and approved marking
  PR #55 ready for review once CI is green.
- Self-review round 6 (`self-review-pr55-r6.md`): verdict fail on four Low findings: F1 stale
  STATUS text, F2 code comments, F3 the term "comparable", F4 no fixture for a legacy ticket
  in a non-open state. All four repaired: fixture e1-57 and mutant
  `legacy-ticket-state-blocks` added. Gates: run-fixtures 62/0 + 15 structural-reject;
  check-fixtures PASS; mutation-test 125 mutants, 122 killed, 3 equivalent, 0 noapply.
- Self-review round 7 (`self-review-pr55-r7.md`): verdict fail on F5 (TRACEABILITY and
  retro-log still used the retired term "comparable identity"); repaired to "legacy ticket".
- Self-review round 8 record: `self-review-pr55-r8.md` (added verbatim after a pass).
- cost: unavailable (cloud transcript not local).

## 2026-10-03 — Report ignored legacy tickets (session 2)

- External Claude review of 7426b97: (1) the `validateInput` comment said `plan()` ignores a
  legacy ticket, but it still matches through an alias; (2) the output gives no signal when a
  legacy ticket is ignored. Human oracle: the user approved adding the signal.
- Stage 3, test first: schema field added; every expected.json updated by an independent
  oracle script; fixture e1-58 added. run-fixtures then reported 62 of 63 failed. After the
  implementation: 63 passed, 0 failed.
- Gates: run-fixtures 63/0 + 15 structural-reject; check-fixtures PASS; mutation-test
  130 mutants, 127 killed, 3 equivalent, 0 noapply; ajv: all 62 expected and 62 actual
  outputs valid; e1-58 input valid.
- Self-review round 9 (`self-review-pr55-r9.md`): verdict fail, 1 Medium and 7 Low. F1 the
  schema title's em dash was re-serialized; F2 decision references were pinned only for
  `rediscovered-open`; F3 input order unpinned; F4 environment normalization unpinned; F5
  "references" did not say "by issueId"; F6 ambiguous alias match and duplicate issueIds
  undefined; F7 the legacy definition was narrower than `normalizeChain`; F8 TRACEABILITY
  omitted the negative fixtures. All repaired: fixture e1-59, four mutants, wording in the
  schema, README, STATUS and code, a stricter oracle (it agrees on all 63 fixtures).
- Gates after the repair: run-fixtures 64/0 + 15 structural-reject; check-fixtures PASS;
  mutation-test 134 mutants, 131 killed, 3 equivalent, 0 noapply; ajv 126 of 126 expected
  and actual outputs valid.
- Self-review round 10 (`self-review-pr55-r10.md`): verdict fail on two Low findings. N1: an
  `unresolved` decision that targets a legacy ticket was not pinned as a reference. N2: this
  entry omitted the ajv result, and the STATUS fixture-provenance line named only e1-53..56.
  Both repaired: e1-59 gains an alias-matched unknown-state legacy ticket; new mutant
  `ignored-legacy-skips-unresolved`.
- Gates after the repair: run-fixtures 64/0 + 15 structural-reject; check-fixtures PASS;
  mutation-test 135 mutants, 132 killed, 3 equivalent, 0 noapply; ajv 126 of 126 expected
  and actual outputs valid; the independent oracle agrees on all 63 fixtures.
- Self-review round 11 record: `self-review-pr55-r11.md` (added verbatim after a pass).
- cost: unavailable (cloud transcript not local).

## 2026-10-03 — Backfill-reminder wording and the PM decision index (session 2)

- External review of aaaf8b0 asked whether `ignoredLegacyIssues` should list tickets on runs
  that create no ticket. Human oracle: the user decided it is a standing backfill reminder that
  does not depend on whether the run creates a ticket. Only wording changed: the code comment, schema description, README and STATUS.
  Fixtures e1-58 and e1-59 already pin runs with no `create-ticket` and a non-empty list.
- The user decided that the PM gate answers belong in the product and Aegis docs (convention:
  foxglove/app#19116). foxglove/actions#57 records them after five isolated review rounds;
  `pm-clarifications.md` is now the index from each question to its record.
- Gates: run-fixtures 64/0 + 15 structural-reject; prettier clean. No planner logic changed.
- Self-review round 12 (`self-review-pr55-r12.md`): verdict fail on seven wording findings. F1:
  the schema said an alias removes a ticket from the list, but only a normalized chain does.
  F2: "listed on every run" omitted the exclusions. F3: the PM table rows 1 and 7 were not
  marked superseded. F4: the operator change was not recorded. F5: "table above". F6: the
  `pm-clarifications.md` intro still called the items open. F7: two index answers were
  incomplete. All repaired.
- Self-review round 13 (`self-review-pr55-r13.md`): verdict fail on two Low findings. F8:
  "stays eligible" reused the notification term and hid the alias-match exclusion; F9: two
  "see below" pointers. Both repaired with the reviewer's wording.
- Self-review round 14 record: `self-review-pr55-r14.md` (added verbatim after a pass).
- cost: unavailable (cloud transcript not local).

## 2026-10-03 — Review records removed from the workspace (session 2)

- At the user's request, the review records `review-wp1.md`, `review-wp1-round2.md`,
  `review-wp1-round3.md`, `self-review-pr55.md` and `self-review-pr55-r2.md` to
  `self-review-pr55-r14.md` are removed from `.feature-workspace/attack-runner/`. The
  entries above keep the verdict and findings of each failing round; passing rounds are only
  named there. The records never reach `main`, which squash-merges. They remain at commit
  2029ecf on the PR #55 head: `git fetch origin refs/pull/55/head`, then
  `git show 2029ecf:.feature-workspace/attack-runner/<file>`.
- The workspace now holds only the pipeline state: GOAL, MODEL, TRACEABILITY, STATUS,
  EVIDENCE, retro-log, pr.json and the PM decision index.
- cost: unavailable (cloud transcript not local).
