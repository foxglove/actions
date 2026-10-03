# Pre-push review, PR #55 (offline reconciliation planner, fix round)

Verdict: HOLD. 0 blocker, 3 major, 5 minor.

Commands run: run-fixtures (52 passed, 0 failed), check-fixtures (PASS), mutation-test (110 mutants, 106 killed, 4 waived, 0 noapply, PASS). Probes and extra mutants are in /tmp/rv (t.mjs, fuzz.mjs, mut.mjs, m2.mjs).

## Verification of the six claimed fixes

1. fpKey replay (plan.mjs:482-490): verified. `${runId}:${fp}` stops the double-count when attempt 1 created the ticket (key run:fp) and attempt 2 sees it with an exploitId (key run:exp). Fixture e1-45 pins it. Over-suppression: none found. fp includes env+chain and the run id is in the key, so a different exploit or a different run cannot collide. Replay only suppresses when the same run already recorded that identity.
2. In-run duplicate of `new` stays `new` with [{none}] (plan.mjs:493-499): verified. No expected.json has a `rediscovered-open` decision whose target is not existing-issue. Probe confirms two `new` decisions with one create-ticket (see F6 for the consumer-side consequence).
3. runPositives and order independence: verified. A 3000-trial shuffle fuzz (random chains, mixed validity, open/resolved/unknown tickets, replayed eventId) gave identical outcome-by-observationId and action multisets. The superset check against invalid-evidence siblings is correctly excluded. The skip-non-open part is NOT sound (F1).
4. validateInput additions: present and behave as described, but see F2 (too strict) and F3 (unpinned).
5. mutation-test: passes and fails on noapply as intended, but it does not gate the code added this round (F3).
6. Names: both JSON files parse; no personal names remain in .feature-workspace/attack-runner (grep of names, emails and "Firstname Lastname" patterns). Attribution problems in F8.

## Findings

### F1 [semantic-model-gap + implementation-mistake] MAJOR: related-check skips every non-open ticket, including unknown-state and resolved-with-fix-claim

plan.mjs:318-321 (`if (iss.state !== "open") return false;`).

- The planner's own rule is "no write without a known state" (plan.mjs:412-427). Here an `unknown` ticket whose chain is a sub/superchain of the observation is ignored, so a speculative new ticket is created. Also applies to unrecognized states (e.g. "closed").
  - Probe A3: obs [1,2], existing S1 [1,2,3] state "unknown" -> `new` + create-ticket + count. Probe A5: state "closed" -> same.
  - Fix: skip only `resolved`; unknown and unrecognized stay blocking. Open and unknown both route to triage.
- Resolved ticket with an explicit fix claim and an overlapping chain: partial/superset observation creates a new ticket instead of triage. This is the E1-03 contradiction case arriving as a partial chain, which E1-18 says routes to triage "without creating a speculative duplicate".
  - Probe A: obs [1,2], resolved+claim S1 [1,2,3] -> `new`. Probe A2: obs [1,2,3], S1 [1,2] -> `new`.
  - Suggested rule: skip only resolved tickets with no fix claim, or keep resolved+claim blocking. Needs a product decision, but silent new-ticket creation is the wrong default.
- Not pinned by any fixture (see F3), so a regression here is invisible.

### F2 [implementation-mistake / semantic-model-gap] MAJOR: one legacy ticket without structured semantics aborts the entire batch

plan.mjs:63-72. `existingIssues[]` with a prose-only or empty `normalizedChain` and no aliases now throws PlannerInputError for the whole run.

- The input schema permits that shape (the `transition` def does not require `semantics`; `normalizedChain: []` is schema-valid; the anyOf only requires the key to be present).
- Probe F/F2: one chain-less existing ticket plus one valid new positive -> THROW; no decisions and no run summary are produced.
- Contradicts E1-07 (valid positive before later failure is reconciled), E1-12/E1-13 (valid decisions retained; only a "structurally unreadable entire input may fail as a whole"), and the README claim that missing semantics "route to unresolved".
- A pre-existing Linear ticket the adapter could not normalize is the common case, and it takes down every other finding in the run.
- Fix: do not throw. Treat the ticket as non-matchable for the exact match, and either route every valid positive in the run to unresolved with a neededEvidence entry, or add a run-level warning. Alternatively tighten the schema and document that the adapter must pre-filter, plus a fixture.

### F3 [oracle-gap] MAJOR: the code added this round is not gated by fixtures or by mutation-test.mjs

Extra single-line mutants I applied against the committed oracle all SURVIVED (run-fixtures still PASS):

- plan.mjs:321 state guard removed, and changed to `=== "resolved"` (the F1 behavior has no fixture with a non-open overlapping ticket)
- runPositives `validity === "valid"` filter dropped (no fixture with an invalid-evidence sibling overlap)
- validateInput: duplicate observationId check; usable-identity check; `fixClaim.claimed` boolean check; existing-issue `targetEnvironment`/`issueId` checks; observation null/shape check; `run.runId` check; `existingIssues`/`processedEvents` array checks. Only the processedEvents element check and the missing runEnv check were killed. The structural-reject list is {null, {}, obs-not-array, missing-env, processed-null, bad-existing}, which pins only a subset.
- processedIds `.filter(Boolean)` removal.
  The `alias-only-chainless` waiver in EQUIVALENT is wrong. Its find-string matches the validateInput check at plan.mjs:68, not the matcher, so the matcher mutant never ran. I applied the correct mutant (require a chain before the alias match at plan.mjs:290-293) and it survives. No fixture has an alias-only (chain-less) existing ticket, though validation and the schema explicitly allow one. This is a real gap hidden by the waiver.
  The mutation test therefore still passes and does gate most of the older logic, but it does not meaningfully gate this round's changes. Add fixtures and mutants for each item above.

### F4 [semantic-model-gap] minor (pre-existing, not a regression): in-run duplicate discards the second observation's remediation, ownership and evidence

plan.mjs:494-499. Probe C: two valid observations of the same fp, the second with remediation for another repo -> second decision is `none`; its remediation appears in no action. Per-run ticket material comes only from the first observation, which also makes ticket content depend on observation order (outcomes and counts do not).
E1-10 says one ticket keeps "all remediation items" when the exploit spans repos; cross-run this works through append-remediation, but within one run it is lost.

### F5 [semantic-model-gap] minor: duplicate observationId rejects the whole batch

plan.mjs:43-44. E1-08 expects a duplicated finding in one run to collapse to one mutation. A harness that re-emits the same observation (same id) now yields a PlannerInputError and no plan, instead of a deduped decision. Schema has no uniqueness constraint. Either dedupe identical ids or make the contract explicit in the schema and README.

### F6 [workflow-failure / doc drift] minor: README still describes the old model, and consumers keying on outcome see two `new`

README.md:60 lists "or an in-run duplicate" under `rediscovered-open` ("none for a duplicate"). The code now keeps a duplicate of a new exploit as `new` with [{none}]. A consumer counting `outcome === "new"` sees two decisions for one ticket (the issue round 1 flagged and round 2 "fixed" by the relabel, now reverted). Document that ticket creation is signalled only by the `create-ticket` action and `notificationEligible`, not by the `new` label; add an oracle invariant that each fp has exactly one create-ticket.

### F7 [workflow-failure] minor: recorded evidence is stale (E1-16)

STATUS.md:17-19 and TRACEABILITY.md:3 state 47 fixtures, 48 passed, 112 mutants / 102 killed. Actual: 51 fixture directories, 52 passed, 110 mutants / 106 killed (4 waived). EVIDENCE.md:72 also stale. E1-16 requires evidence matching the final revision.

### F8 [workflow-failure] minor: attribution rewrite introduced nonsense and misquotes

- Item 10 reads "Foundations team for now, transitioning to the Foundations team" and "Owner now: Foundations team; future owner: Foundations team" (retro-log.json:118,126; STATUS.md:68). The global replace erased the transition.
- STATUS.md:60 quotes `attack-sessions.md:150` as "interim Foundations team"; that line says "interim Kumar Pasumarthy".
- GOAL.md:56 says release authority is "Foundations team (per attack-sessions.md)"; attack-sessions.md:22 names an individual, with ownership moving to a team later. The retro-log "oracle" and "Sign-off" fields now attribute those decisions to a team the cited doc does not name.
- Both JSON files parse. product-docs/attack-sessions.md still contains the personal name (source doc, outside the changed set; confirm that is intended).
