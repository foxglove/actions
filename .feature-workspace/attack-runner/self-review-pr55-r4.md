# Self-review PR #55, round 4 (isolated delta recheck)

## Review identity

- Mode: isolated reviewer, review only (no repository edits, commits, pushes, or GitHub posts).
- Base: main. Original reviewed revision: c6872b4. Previous review: round 3 (`self-review-pr55-r3.md`, verdict fail, F1-F4, T1-T4).
- Candidate: working tree on branch claude/exciting-cerf-vkmwu5. HEAD is 2d93dfb (also origin). Everything in this round's delta is UNCOMMITTED: 9 modified tracked files plus the untracked `.feature-workspace/attack-runner/self-review-pr55-r3.md`. `candidate-r4.diff` is byte-identical to `git diff c6872b4`.
- Prompt: prompts/review.md at 2d93dfb. Its sha256 is c007116786a0bb1064a99229a375ab8f773d85c97e87e65542434703004ef4d7, which matches the sha256 recorded in EVIDENCE.md ("c0071167…ef4d7").
- Inputs: reviewer-payload.md, acceptance.md, engineering-handoff.md, planner README and schemas, `product-docs/exploit-findings.md`, r2 and r3 records.

## Coverage

Round-4 delta inspected in full: `plan.mjs` (comment only), `run-fixtures.mjs` (T3 invariant), `mutation-test.mjs` (`nonempty-no-trim`), e1-56 input, README fixtures wording, STATUS.md (counts, "R3-F4" section, checkpoint, remaining work), TRACEABILITY.md (header and new row), EVIDENCE.md (new entry), retro-log.json (3 new entries). Also read: STATUS.md whole, exploit-findings.md lines 24 and 85, acceptance.md E1-11..E1-13, retro-log.json structure, the repo copy of the r3 record.

Lifecycle trace: unchanged from round 3. The only behavior-relevant change is the e1-56 input (`["", "  "]`); `plan.mjs` logic did not change. Row "uncomparable ticket with blank aliases" now has two blank shapes pinned: empty string and whitespace-only string. No external-action branches exist (E1-15).

## Gates (run by this reviewer)

- `run-fixtures.mjs`: 61 passed, 0 failed; structural 14 ok / 0 bad. PASS.
- `check-fixtures.mjs`: FIXTURE CHECK PASS.
- `mutation-test.mjs`: 128 mutants, killed 125, survived 3 (3 equivalent), noapply 0. PASS, exit 0.
- ajv (draft2020): e1-56 `input.json` valid (input schema); `expected.json` and actual output valid (output schema).
- `npx prettier@3 --check attack-runner/planner .feature-workspace`: all files formatted.
- Fixture directories: 60.

## Count verification (every stated count vs measured)

| Location              | Stated                                                                                      | Measured                   | Result                                                                   |
| --------------------- | ------------------------------------------------------------------------------------------- | -------------------------- | ------------------------------------------------------------------------ |
| STATUS.md:17-19       | 60 fixtures, 61 passed, 14 structural, 128 mutants, 125 killed, 0 unexpected, 3 equivalents | 60, 61, 14, 128, 125, 0, 3 | match                                                                    |
| STATUS.md:103-105     | 61 passed + 14 structural; 128/125/3/0 noapply                                              | same                       | match                                                                    |
| TRACEABILITY.md:3     | 60 fixtures, 128 mutants, 125 killed                                                        | same                       | match                                                                    |
| EVIDENCE.md:88-89     | 57/0 + 9; 117/114                                                                           | n/a                        | dated entry for the earlier round; valid point-in-time record, not stale |
| EVIDENCE.md new entry | no counts; "see the round-4 review record"                                                  | n/a                        | no wrong count; dangling pointer (F8)                                    |
| README.md             | no counts                                                                                   | n/a                        | n/a                                                                      |

## Disposition of round-3 findings and T3

| ID                  | Disposition                                                                     | Evidence                                                                                                                                                                                                                                                    |
| ------------------- | ------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| F1 stale counts     | fixed-and-verified                                                              | All three current-status locations match measured values (table above). EVIDENCE.md has a new entry. Remaining defect in the entry: F8.                                                                                                                     |
| F2 whitespace alias | fixed-and-verified                                                              | e1-56 aliases are `["", "  "]`. The new mutant `nonempty-no-trim` applies (noapply 0) and is killed (125 killed). I confirmed in round 3 that without this fixture the trim removal survived. `unc-blank-alias-comparable` is still killed (list length 2). |
| F3 comment drift    | fixed-and-verified                                                              | `plan.mjs:64` now reads "no non-blank alias". The line is longer than 90 columns, but prettier does not wrap comments and `--check` passes.                                                                                                                 |
| F4 acceptance owner | routed; open as a product question; routing record accurate but incomplete (F9) | See "F4 routing audit".                                                                                                                                                                                                                                     |
| T3 count invariant  | fixed-and-verified in the working tree; NOT COMMITTED                           | `run-fixtures.mjs:124,131-133`. Unchanged from round 3 (invariant fires on mutated engines). The thread stays open until the fix is pushed, as STATUS item 5 says.                                                                                          |

## F4 routing audit (completeness and accuracy only; the product decision is out of scope)

Present and accurate:

- STATUS.md "Open product question (R3-F4)": states the rule, the fixtures (e1-50, e1-53..56; e1-51 is related but omitted, immaterial), the nearest authority (E1-18; `exploit-findings.md:24` "Ambiguous matches remain unresolved for triage"; `:85` reconciler "records why a candidate is the same exploit or why a distinct ticket is warranted"; both verified), the two options (ratify with a backfill duty, or narrow), and the interim status ("implemented, gated, and unratified").
- TRACEABILITY.md: new row, owner WP1.2, oracle "fixtures e1-50, e1-53..56; acceptance pending". WP1.2 is the five-outcome engine; correct.
- STATUS.md remaining-work item 6 names R3-F4 as needing the acceptance owner.
- EVIDENCE.md new entry and retro-log "review" entry both record "F4 routed to the acceptance owner (R3-F4)".
- README fixtures wording no longer claims every fixture maps to a criterion. Check: up to e1-20 the prefixes follow acceptance rows (e1-12-mixed-valid-invalid also exercises E1-13; the wording says "exercises", which holds). The README still states the rule as fact without "unratified"; acceptable for a package README.

Gap: F9 (the record omits that tickets of any state block creation).

## Additions sub-checks on the new text

1. Supersession: README prefix wording replaces the old claim (old text removed). STATUS remaining-work item 1 replaces the old thread-reply instructions. NOT reconciled: STATUS checkpoint "Where things are" still says "final self-review verdict SHIP ... M1, M2, and L3/L4 applied", which contradicts the round-3 verdict fail (F6).
2. Effect-claim trace: "F1-F3 repaired" in EVIDENCE verified. STATUS "follows the ambiguity routes to triage rule (E1-18, exploit-findings.md:24,85)" verified. retro-log escape entry says the external review of the unguarded commits "found no new defect"; round 3 found F1-F3 in those same commits, so the claim is unsupported (F7).
3. Acceptance-case parity: the one new value (whitespace alias) has a fixture and a mutant. The new TRACEABILITY row lists its fixtures. Pass.
4. Distinguishability: e1-56 `["", "  "]` separates trim from no-trim (mutant killed). Pass. README "up to e1-20" claim spot-checked against acceptance rows E1-11..E1-13.
5. Cross-reference propagation: counts propagate correctly (table). STATUS "Review logs" (lines 129-130) omits `self-review-pr55-r3.md` and r4; checkpoint verdict stale (F6). My own round-3 record, copied into the repo, introduced personal names (F5). STATUS remaining-work items 2-3 do not list `nonempty-no-trim` (immaterial, listed under F6 for the fix pass).
6. Anchor-event and branch outcome: EVIDENCE says "see the round-4 review record" with no file name or counts, so the entry does not resolve standalone (F8). The retro-log entries say "Session 2 pushed ... before loading the feature-pipeline skill"; HEAD and origin confirm both commits were pushed; the skill claim could not be checked here.

Personal-name check: grep of `.feature-workspace/` and `attack-runner/` found the names of individuals only in `.feature-workspace/attack-runner/self-review-pr55-r3.md:69` (see F5). No other occurrence.

## Findings

### F5 [Medium] [workflow-failure] The repo copy of the round-3 record reintroduces personal names

- Location: `.feature-workspace/attack-runner/self-review-pr55-r3.md:69` (untracked file, not yet committed).
- Trace: the line lists the individual names that the PR de-personalized (a name, a surname, and two handles). The earlier pass removed these names from `.feature-workspace/` because the repository is public. The round-3 record, which this reviewer wrote with those names, was copied into the repo. grep confirms it is the only hit.
- Effect: committing the file undoes the de-personalization requirement. This reviewer caused the defect; the same sentence exists in the scratchpad original.
- Fix: replace the list with "the individual names previously present in the STATUS history". Keep the grep result statement. Apply the same rule to the round-4 record, which does not repeat the names.
- Disposition: open.

### F6 [Low] [supersession] STATUS checkpoint and review-log list state the old review result

- Location: `.feature-workspace/attack-runner/STATUS.md:96-98` and `:129-130`.
- Trace: the checkpoint says "three isolated self-reviews done; final self-review verdict SHIP (... M2 ... applied)". Round 3 returned fail; round 4 (this record) is the latest. The log list ends at `self-review-pr55-r2.md`. "Next action 1" (`STATUS.md` "Round-3 verification review") is also stale (pre-existing; same fix pass).
- Effect: two coexisting statements of the review state; a resuming session reads SHIP.
- Fix: change the sentence to name the latest record and its verdict, list `self-review-pr55-r3.md` and `-r4.md` in "Review logs", and update or remove "Next action 1". Optionally add `nonempty-no-trim` to the item 2-3 mutant lists.
- Disposition: open.

### F7 [Low] [effect-claim] retro-log escape entry understates the escape

- Location: `.feature-workspace/attack-runner/retro-log.json`, first new entry (ts 2026-10-03, type escape).
- Trace: the note says "The external review of those commits found no new defect, but the gate was skipped." The isolated round-3 review of those commits found F1 (stale counts), F2, and F3, and the retro-log's own third new entry records them. The external review's threads T1-T4 were raised on c6872b4, not on bb8aaa9 or 2d93dfb.
- Effect: the retrospective record says the gate skip cost nothing; the evidence says it let three defects through.
- Fix: replace the clause with "the gate, run later, found F1-F3 in those commits". Also confirm the `stage` value: the entry before these uses stage "3" for a review, the new entries use "6", and STATUS says Stage 3.
- Disposition: open.

### F8 [Low] [anchor] EVIDENCE entry points to an unnamed record

- Location: `.feature-workspace/attack-runner/EVIDENCE.md`, last bullet group ("Gates on the repaired candidate: see the round-4 review record").
- Trace: no file name, no counts, and no verdict. The entry names the round-3 record by file name only.
- Effect: a reader cannot find the round-4 record or the gate result from this entry alone; EVIDENCE.md is the file the payload says to link the record from.
- Fix: name `self-review-pr55-r4.md` (copy this record into `.feature-workspace/attack-runner/`) and state the measured gates: 61 passed, 14 structural, 128 mutants, 125 killed, 3 equivalent, 0 noapply, ajv valid. Add the final verdict after the last round.
- Disposition: open.

### F9 [Low] [routing-completeness] R3-F4 routing omits the state-independence of the block

- Location: `.feature-workspace/attack-runner/STATUS.md` "Open product question (R3-F4)".
- Trace: the section says "A same-environment ticket ..." but does not say that a ticket of any state blocks creation. Probes in round 3: a resolved-state and an unknown-state legacy ticket both route would-be-new observations to `unresolved`; the filter at `plan.mjs:~332-339` has no state test. Round-2 finding M1 identified this as the main blast radius.
- Effect: the acceptance owner choosing between "ratify" and "narrow" lacks the fact that closed legacy tickets block too.
- Fix: add "of any state (resolved and unknown included)" to the section. Optionally name e1-51 with the other alias fixtures.
- Disposition: open.

## Counts

- New comments: 5 (1 Medium F5, 4 Low F6-F9).
- Unresolved comments in total: 6 (the 5 new plus F4 carried as a routed open product question).
- Fixed and verified this round: F1, F2, F3, T3 (T3 uncommitted).
- Missed blockers in unchanged `attack-runner/` code: none found. The delta changes no planner logic apart from a comment.

## Verdict: fail

Open findings exist (F5 Medium, F6-F9 Low, F4 routed). All gates pass, and the code and fixtures need no further change. The remaining work is documentation and record repair, plus committing the uncommitted changes. F5 should be repaired before any commit that includes the round-3 record.

## Rechecks

- Commands run: `run-fixtures.mjs`, `check-fixtures.mjs`, `mutation-test.mjs`, ajv on e1-56 (input, expected, actual), prettier check, grep for personal names and stale counts, comparison of `candidate-r4.diff` with `git diff c6872b4`.
- Invalidated evidence: gate results before this uncommitted candidate are not tied to a revision; re-run the gates after the commit.
- Next stage: the author repairs F5-F9 and commits all changes (including T3), then replies on the T3 thread. A delta recheck of those documentation files only is enough.
- Not checked: the claims about PR thread state and about the skill location in the retro-log and STATUS (no GitHub read performed). Elapsed time and cost: not measured.
