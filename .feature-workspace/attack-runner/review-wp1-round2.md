# WP1 adversarial review, round 2 (offline planner)

Scope: attack-runner/planner/{src/normalize.mjs, src/plan.mjs, run-fixtures.mjs, check-fixtures.mjs, schema/_, fixtures/_ (19)}.
Judged against product-docs/exploit-findings.md, acceptance.md (E1-01..E1-20), engineering-handoff.md. Round-1 items (missing ticket material, fix-claim/state classification, input validation, environment-in-identity, weak oracle) are not re-litigated except where the follow-up left a hole or introduced a new one.

Method: baseline `run-fixtures.mjs` 19/19 + 3 structural PASS, `check-fixtures.mjs` PASS. Then (a) ~50 input mutation probes (scratch: /tmp/claude-0/p/probe\*.mjs), (b) ajv validation of every input/expected/actual (/tmp/claude-0/ajv/v.mjs), (c) mutation testing of the engine: 60 hand-built wrong engines run through the real oracle (/tmp/claude-0/p/mut.mjs). 39 of the 60 wrong engines PASSED the oracle (listed in section O).

Totals: 1 blocker, 9 major, 9 minor.

Line refs: plan = src/plan.mjs, norm = src/normalize.mjs, oracle = run-fixtures.mjs.

---

## BLOCKER

### R2-B1 [implementation-mistake + oracle-gap] The planner's own `ticketMaterial.normalizedChain` cannot be consumed as `existingIssues[].normalizedChain`; the plan -> persist -> plan loop creates a duplicate ticket every run

plan:41-57 (`normalizedChain: normalizeChain(e.chain)`) emits flat tuples `{actorRole, resourceRelation, ...}`. norm:22-25 only accepts transitions that carry a `semantics` object, and input schema `existingIssue.normalizedChain` is `$ref transition` (requires actorCapability etc. plus `semantics`). The round-1 disposition (B1) states the purpose of emitting `normalizedChain`: so the adapter can persist the lookup aid that a later run's `existingIssues[].normalizedChain` is fed from.

Reproduced (/tmp/claude-0/p/probe3.mjs): run e1-01 -> take `ticketMaterial.normalizedChain` -> supply it as the open existing issue in the next run with the same observation -> outcome `new` + `create-ticket` + notification-eligible. Wrapping each tuple as `{semantics: tuple}` makes it match (`rediscovered-open`). So the one ticket-per-exploit guarantee (E1-09 "same open finding in a different run: one additional count") fails in the intended flow, and every run raises a new-exploit notification for an existing ticket.

No fixture performs a round trip: every existing-issue chain in the fixtures is hand-authored in full transition shape, so the suite cannot see it.
Fix: make the two shapes one (emit transitions with `semantics`, or accept flat tuples in `normalizeTransition`), add a round-trip oracle test (plan output -> persisted shape -> plan again must be `rediscovered-open`, one count).

---

## MAJOR

### R2-M1 [implementation-mistake] `create-ticket` material still lacks the ordered activity chain with evidence, and silently accepts missing required content (E1-01)

plan:41-57. E1-01 requires "ordered activity chain with evidence, what must be fixed, re-test expectations"; exploit-findings "Ticket material" additionally requires preconditions/actor-session role, per-step action/request/observed result/evidence reference/what becomes possible next, run/artifact references. `ticketMaterial` carries only the six-field semantic tuple (no prose steps, no per-step evidence, no prerequisites, no evidenceLocation/runId link). Probes (probe2 E/G): positive with `severity`/`productionImpact` absent -> ticket with `severity:null`; positive with no `remediation`/`retestExpectations` (fixture e1-12 itself, and e1-18/e1-11) -> `remediation:[]`, `retestExpectations:null`, still `create-ticket` + eligible. "What must be fixed" and "how to verify" are exactly the content a ticket must have (exploit-findings "Tickets carry actionable evidence"); the input schema marks only chain/severity/productionImpact required, the code validates nothing, and the oracle accepts null/[] (`tm[k] === undefined`, oracle:91). Missing required ticket content should be `unresolved` with neededEvidence (or schema-required), not a hollow ticket.

### R2-M2 [implementation-mistake] Non-enum / vendor `state` strings are treated as open and produce writes (handoff: "planner receives normalized states, not a guessed interpretation of 'Done'")

plan:241-299. Only `unknown`/undefined/null route to unresolved; every other value that is not exactly `"resolved"` falls to the open branches. Probes: `state:"Open"`, `state:"done"`, `state:"Done"`, `"closed"` -> `rediscovered-open` + `append-evidence` + `increment-confirmed-count` (and with a claim -> `claimed-fixed-reproduces` eligible, no reopen even though the vendor ticket may be closed). A fix-claim given as `claimed:"true"` on an open ticket is silently treated as unclaimed (plan:242 strict `=== true`). Same pattern for observation `validity`: `"VALID"` or missing -> reported as "Exploit identity is ambiguous" (plan:~140, wrong reason, but still no write). Planner never validates its enums, so an adapter mapping bug turns into writes on the wrong lifecycle path. Fix: closed switch on state; anything else -> unresolved (or PlannerInputError).

### R2-M3 [semantic-model-gap + oracle-gap] Fix-claim episode is not modelled: an open ticket carrying a claim alerts again on every run (E1-19)

plan:289-296 (open + claim -> `claimed-fixed-reproduces`, `eligible = true`, unconditional). exploit-findings: "Repeat events for the same exploit/fix-claim episode ... do not create another alert." Reopen in run N leaves the claim on the snapshot in run N+1 unless the adapter clears it; probe: open+claim, new run -> `claimed-fixed-reproduces`, `notificationEligible:true`, one more count and alert, forever. Likewise resolved+claim contradicted in consecutive runs. Input has no field to say "this claim (by reference) was already contradicted/notified", so even the replay-vs-new-episode distinction E1-19 asks for is expressible only by eventId replay. The e1-19 fixture (named "notification-eligibility") only contains new / routine rediscovery / replayed-new; there is NO fix-claim replay and NO "new claim after reopen" case, so E1-19's two fix-claim halves have no test. STATUS.md/TRACEABILITY.md list E1-19 as exercised (WP1.3) while STATUS "Deferred" lists "fix-claim episode tracking" as E2: contradictory, and acceptance E1-19 puts it in the planner fixture scope.
Fix: add `fixClaim.contradictedRuns/episodeId/notified` (or `lastContradictedReference`) to the input; eligibility only when the claim reference has not been contradicted; fixtures for same-episode replay, repeat in next run, and new-claim episode.

### R2-M4 [semantic-model-gap] Replay protection key is never emitted and breaks across fingerprint versions (E1-08 x E1-20)

plan:212-215: the only replay protection that survives a missing/regenerated eventId is `processedEvents[].key === "${runId}:${fp}"`, where `fp` is the whole fingerprint string including `FINGERPRINT_VERSION` and the JSON of the tuple. (1) No decision output includes this key or the fingerprint (only `new` carries `fingerprintVersion` + chain), so an adapter has no way to know what string to persist; it must re-implement normalizer internals. (2) After a normalization bump, any persisted key (v1) no longer matches the v2 fp (probe C): a transport retry across a deploy double-counts and re-creates. (3) Schema: `processedEvents[].eventId` is `required`, so the documented "absent eventId" key-only entry is schema-invalid (input schema). Fix: emit an `idempotencyKey` per decision, build it from (runId + stable exploitId/alias set) rather than a version-bearing hash, and allow key-only processed events.

### R2-M5 [implementation-mistake] Count-once dedup keys on fingerprint, not on the matched exploit/ticket

plan:216, 320 (`seenThisRun` holds fp). Two observations with different fingerprints that match the SAME existing issue (via `fingerprintAliases`, exactly the E1-20 migration case) are both counted in the same run (probe A: both `rediscovered-open`, both `append-evidence`+`increment-confirmed-count` on SEC-101). Violates "one confirmed count per exploit per run". Fix: dedup key = matched issueId/exploitId when matched, fp otherwise. No fixture or invariant checks count-once on the actual output generically.

### R2-M6 [semantic-model-gap] Environment became identity, but a missing environment silently produces speculative duplicates or cross-environment matches (introduced by the round-1 env fix)

norm:50-61, plan:186-190, input schema (`existingIssue.targetEnvironment` and `normalizedChain` optional, `run.targetEnvironment` only checked by the schema, not the code). Probes: existing issue with identical chain but no `targetEnvironment` -> `new` + `create-ticket` + eligible (duplicate ticket + alert, instead of unresolved/triage; planner cannot say "this ticket's environment is unknown"); existing issue with no chain and no aliases -> same. Conversely run with no `targetEnvironment` and an existing issue with none -> they MATCH (both normalize to `""`, probe P), merging unknown-environment observations into unknown-environment tickets. Contract: "unknown state required for a write -> unresolved", environment is part of the matching core. Fix: validate `run.targetEnvironment` (PlannerInputError); for existing issues with unknown environment or unusable chain that cannot be excluded, return `unresolved`, never `new`.

### R2-M7 [semantic-model-gap] Partial / superset chains create a speculative new ticket and an alert; E1-18 second half has no behavior and no test

plan:186-190 requires exact equality of tuple lists. Probes: existing [A,B], observed [A] -> `new`, eligible; existing [A], observed [A,B] -> `new`, eligible. E1-18: "ambiguous partial evidence routes to triage without merging or creating a speculative duplicate"; handoff: ambiguity -> unresolved. The e1-18 fixture is only the "distinct control failures" half (two disjoint single-step chains). Round 1 deferred M5 "to the E1-18 slice"; the slice was marked complete (STATUS, TRACEABILITY) and the behavior is still absent. Related: repeated identical transitions ([A,A] vs [A], probe) and `prerequisites` changes (prose strings, ignored by identity; probe "prereq different" still matches) are false distinctions/false matches that the contract's "causal prerequisites preserved" (E1-17) would care about.

### R2-M8 [semantic-model-gap + oracle-gap] E1-10 "retains all remediation items" is unrepresentable and the fixture passes vacuously

e1-10 observes repos `['app','api']` and a remediation item against an open ticket; planner emits only `append-evidence` + `increment-confirmed-count` (plan:296-301). There is no action to add remediation items/repos/ownership to the existing ticket, so a cross-repo rediscovery with a new component fix loses it. STATUS defers this to "WP2.7/E2" ("adapter concern") but the acceptance row is an E1 planner criterion and the planner is the only place that sees both snapshots (existing issues carry no remediation field, so the adapter cannot do the union). The fixture e1-10 only tests "no duplicate"; no harness/model/path-revision input field exists either (observation `exploit` is `additionalProperties:false`), so the exclusion claim is untestable.

### R2-M9 [semantic-model-gap] `batchStatus: "complete"` is reported for interrupted / failed / skipped runs; run status is not carried to the summary

plan:342. `batchStatus` depends only on unresolved decisions. Probe: `run.completion.status:"failed-before-assessment"`, `"skipped-unstaffed"` with zero observations -> `batchStatus:"complete"`, empty `notObserved`, no completion/session status in `runSummary` (only `stopReason` when present). A consumer reading the summary sees "complete" with no decisions: a clean-bill reading that exploit-findings forbids ("No observation must not become a clean bill of health", "unfinished coverage ... explicit"). E1-07 "unfinished items remain incomplete" relies on coverage passthrough only. Oracle:`batchStatus` check re-derives the same rule from the output, so it validates the defect.

---

## MINOR

### R2-m1 [oracle-gap] expected.json files are schema-INVALID in 11 of 19 fixtures and still carry the pre-B1 bare create-ticket

ajv (/tmp/claude-0/ajv/v.mjs): expected.json fails the output schema in e1-01, 06, 07, 08b, 09, 10, 11, 12, 14, 18, 19, 20 (missing `ticketMaterial` on create-ticket per the schema's own if/then; `reason: ""` violates minLength 1). Actual outputs are all valid. README concedes `expected.json` is "a semantic target (bare action types)", so the contract fixtures contradict the contract schema, and no script validates them (ajv is only in README text; run-fixtures never imports it; the claim "all actual outputs validate" is a manual one-off). Anyone treating fixtures as the contract examples copies the defect.

### R2-m2 [oracle-gap] Same-exploit non-observation plus positive (E1-12 second half) is untested; summary then contradicts itself

e1-07 pairs a positive with a non-observation for an UNRELATED exploit (exp-other). Probe B: positive on SEC-101 + non-observation targeting SEC-101/same exploitId -> positive preserved (good) but `runSummary.notObserved` says "not observed in this run ... attemptedCoverage [exports.download]" for an exploit that the same run confirmed. No fixture would catch an engine that cancels the positive; nothing flags/links the contradiction.

### R2-m3 [implementation-mistake] In-run duplicate output is internally inconsistent and drops alternate evidence

plan:305-315. Second sighting of a `new` exploit is `outcome:"rediscovered-open"` with `target:{type:"new-issue"}`, `exploitId:null` (probe e1-08b). A consumer keyed on outcome expects an existing-issue target. The duplicate's evidence references are also discarded (`none`), although contract says alternate evidence of the same control failure should not create another ticket (not that it be lost).

### R2-m4 [semantic-model-gap] Unknown historical count is never represented or tested

`confirmedRunCount` is never read by code or oracle (grep) and no fixture sets it to null. Planner emits `increment-confirmed-count amount:1` without saying whether the base is known; an adapter doing `count + 1` on null invents a total. "Unknown history remains unknown" has no test anywhere.

### R2-m5 [implementation-mistake] Unvalidated production-impact value and no party-vs-production guard

plan:46-52 copies `productionImpact` verbatim: `{value:"maybe"}`, or `{value:"yes", rationale:"party exploit so prod too"}` from a party run, appear on the ticket; the oracle only checks the planner did not change the source value. E1-14's "party evidence not promoted" is therefore only checked against the planner's own mutation, not against the claim itself.

### R2-m6 [implementation-mistake] Partial structural validation: other malformed inputs throw raw TypeError or yield untyped output

Probes: `existingIssues:[null]`, `processedEvents:"x"`, `processedEvents:[null]` -> TypeError (not PlannerInputError); `runId` missing accepted (derivedKey `undefined:fp`, output `runId:null` violates output schema `string, minLength 1`); missing/duplicate `observationId` accepted (null id emitted, schema requires string minLength 1; duplicate ids make the oracle's id-keyed projection ambiguous); existing issue without `issueId` -> `target.issueId` undefined. Oracle structural tests cover only 3 inputs.

### R2-m7 [semantic-model-gap] `not-observed` attempted-coverage is run-wide, and non-completed attempts record nothing

plan:119-121: `completed` -> ALL `run.coverage.tested`, whatever this re-test actually touched; any other status -> `[]` even if part of the re-test ran (E1-04/E1-06 want "attempts, conditions"). Conditions beyond the stop reason are not carried. Also `reason` for a non-observation with no stopReason is the fixed text "not observed in this run".

### R2-m8 [semantic-model-gap] Self-declared `incidental`, stable exploit ID and migration are not planner outputs

`semantics.incidental:true` is trusted: a real step flagged incidental by an upstream author silently disappears from identity (all-incidental -> unresolved, one real step -> merges with any chain sharing the other step). `new` outputs `exploitId:null` although the contract assigns a stable ID once identity is established; an alias match emits no migration/new-alias signal. These are boundary-trust issues the handoff asked to be documented ("do not hide untested identity decisions at an undocumented boundary"); README documents the flag but not the trust.

### R2-m9 [workflow-failure] STATUS/TRACEABILITY/EVIDENCE overclaim coverage

STATUS.md: "E1-01…E1-15, E1-17…E1-20 exercised by 19 fixtures", TRACEABILITY rows for E1-10, E1-18, E1-19, E1-12 list items that the fixtures do not exercise (R2-M3, M7, M8, m2). README "Status: Covers ... E1-01, 02, 03, 03b, 04, 08, 08b, 12, 17" is stale vs the 19 fixtures. "E1-15 zero side effects" has no executable test (no I/O guard beyond the source importing nothing). E1-16 final-revision hash/results still to be recorded after the fixes this review requests.

---

## O. Oracle strength (mutation test result)

Wrong engines the oracle does NOT fail (all PASSED 19/19):

- Ticket content: ownership always "unknown" / repos dropped / `[]` instead of "unknown"; severity forced null; normalizedChain emptied; remediation dropped; retestExpectations null; rationale dropped; affectedSurfaces dropped; exploitId in material wrong.
- Fix claim: `fixClaimRef` never emitted (zero tests on "identify the claim"); reason text wrong; target object with an extra field.
- Summary: `attemptedCoverage` always the full tested list (over-claim) or always empty; notObserved `reason` = "exploit fixed"; notObserved edgeClassification dropped; evidenceReferences dropped; `runSummary.coverage` replaced by empty; `stopReason` dropped or set to "all clear"; `edgeAccess` dropped; extra top-level `issueWrites:[{action:"comment"}]` on resolved tickets; extra `closeCandidates` list; `exploitIdentity.matchReason` = "exploit fixed".
- Counting/replay: replay not marking the fingerprint seen (R1 M3a regression undetected); derived idempotency key ignored entirely; unknown-state handling replaced by open handling (no fixture has state:"unknown", resolved-without-claim, or missing state).
- Identity: lowercase and trim normalization removed; chain order sorted; adjacent-duplicate collapse; only-first / only-last tuple (no fixture has a multi-step non-incidental chain).
- Misc: decision order reversed; a non-observation without retestTarget getting an invented exploitId; coverage aliasing/mutation of input arrays.

Reasons: the oracle projects both sides to a whitelist (run-fixtures.mjs:33-66) that omits `fixClaimRef`, `ticketMaterial`, `reason/matchReason`, summary `coverage/stopReason/unresolved` details and all notObserved fields except four; it ignores extra top-level/summary fields; checkInvariants (oracle:68-107) tests ticket material presence not content, and asserts no generic "one count per exploit per run", "reopen only when resolved", "claimed-fixed always targets existing issue", "notificationEligible only on new/claimed-fixed non-replay", or "no summary field mentions absence/fixed". Schema validation of actual output is not part of the run. The permutation check compares only an outcome/action tally.

## Invariants with NO test anywhere

- Unknown/missing/invalid ticket state -> unresolved; resolved-without-claim -> unresolved (no fixture).
- Fix-claim identification (`fixClaimRef`) and fix-claim replay / new-episode (E1-19).
- Idempotency via derived key; replay with an absent eventId.
- Unknown historical count preserved.
- Same-exploit positive + non-observation (E1-12 second half); non-observation with timed-out / session-lost / not-attempted (e1-06 covers one interrupted status only).
- Unknown `kind`; `ambiguous-identity` validity; missing semantics; multi-step chains; case/whitespace normalization; environment missing.
- Ownership-unknown value on the ticket (E1-11 "ownership marked unknown"); remediation retention (E1-10).
- Round trip of planner output into the next run's snapshot.
- E1-15 no-I/O.

## Schema vs code vs fixtures consistency (summary)

- Code emits `runId`/`observationId` null where output schema requires non-empty strings (R2-m6).
- `processedEvents[].eventId` required vs the documented key-only use (R2-M4).
- `ticketMaterial` schema is `additionalProperties:true` with no required fields; only presence of the action is enforced (R2-M1).
- Output `proposedActions` rules ("MUST be empty for not-observed", replay -> none) are prose only; not machine-enforced.
- Existing-issue `normalizedChain` input shape differs from the emitted `ticketMaterial.normalizedChain` (R2-B1).
- expected.json vs output schema (R2-m1).

---

## Disposition (2026-10-03, round-2 repair)

The core workflow failure — a weak oracle (39/60 wrong engines passed) — is fixed by
rebuilding the oracle: it now **deep-compares** plan() output to an authored full expected
output (ignoring only free-text `reason`/`matchReason`), asserts invariants on the actual
output, proves input->output **round-trip**, runs a **mutation self-test** (a perturbed
output must be rejected), and schema-validates inputs, expected, and actual outputs.
Oracle: 21/21 + 5 structural-reject.

| ID         | Disposition                                                                                                                                                                       |
| ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| R2-B1      | FIXED — `ticketMaterial.chain` is the structured chain; the oracle's round-trip test feeds it back as `existingIssues[].normalizedChain` and asserts `rediscovered-open`.         |
| R2-M1      | FIXED — complete ticket material required (chain, severity, impact+rationale, remediation, retest); an incomplete positive routes to `unresolved`; oracle rejects hollow tickets. |
| R2-M2      | FIXED — ticket state must be open/resolved/unknown (else unresolved); `claimed` strictly boolean; validity values validated.                                                      |
| R2-M3      | PARTIAL — within-run eligibility correct; cross-run fix-claim **episode** dedup is Engineering 2 (documented); E1-19 claim narrowed accordingly.                                  |
| R2-M4      | PARTIAL — `idempotencyKey` (runId + exploitId/fingerprint) now emitted; durable cross-run persistence + version migration remain Engineering 2.                                   |
| R2-M5      | FIXED — count dedup keys on the matched **issue identity**, not the fingerprint.                                                                                                  |
| R2-M6      | FIXED — run env required; each existing issue requires env + (chain or alias); malformed input throws `PlannerInputError`.                                                        |
| R2-M7      | FIXED — partial/overlapping chain → `unresolved` triage; consecutive duplicate steps collapse.                                                                                    |
| R2-M8      | FIXED — `append-remediation` action on rediscovery/claimed-fixed carries the observation's remediation for union (E1-10).                                                         |
| R2-M9      | FIXED — summary carries `runCompletion` + `sessionStatus`; `batchStatus` is `partial` for any non-completed run.                                                                  |
| Oracle gap | FIXED — deep-equal + invariants + round-trip + mutation self-test + schema validation (see above).                                                                                |
| R2-m1      | FIXED — authored expected files are now schema-valid.                                                                                                                             |
| R2-m2      | FIXED — fixture `e1-12b` (positive + non-observation in one run).                                                                                                                 |
| R2-m3      | ADDRESSED — in-run duplicate → `rediscovered-open` with `none`; evidence retained on the decision; no second write by design.                                                     |
| R2-m4      | DEFERRED — unknown historical **count total** representation is Engineering 2's counting store; the planner proposes increments, not totals.                                      |
| R2-m5      | FIXED — `productionImpact.value` validated to the enum; invalid → incomplete → unresolved; never promoted.                                                                        |
| R2-m6      | FIXED — hardened input validation (runId/observationId required; null guards).                                                                                                    |
| R2-m7      | DEFERRED — richer attempt conditions → E1-06 depth; status + edge classification recorded now.                                                                                    |
| R2-m8      | PARTIAL — the `incidental` flag is an adapter-contract input; a new exploit's stable ID is assigned by Engineering 2 on creation (documented).                                    |
| R2-m9      | FIXED — STATUS/TRACEABILITY/README corrected; E1-15 exercised by determinism + immutability + no-I/O-by-construction; E1-16 is a Stage-4/handoff check.                           |
