# WP1 verification review, round 3 (offline planner)

Verdict: **NOT CONVERGED.** 1 blocker (oracle gap persists), 3 major, 6 minor.

Method: ran both scripts (green), ajv-validated all 20 inputs / expected / actual outputs (all valid), wrote 112 hand-built wrong engines (`/tmp/r3/mut.mjs`, each a single textual mutation of src/plan.mjs or src/normalize.mjs run through the real `run-fixtures.mjs`), and ran ~40 input-mutation probes (`/tmp/r3/probe.mjs`, `probe2.mjs`).

## 1. Baseline

- `node run-fixtures.mjs`: 21 passed / 0 failed, structural 5 ok. `check-fixtures.mjs`: PASS. Confirmed green.
- ajv draft2020: all 20 fixtures' input, expected, and actual output are schema-valid. (R2-m1 fixed.)

## BLOCKER

### R3-B1 [oracle-gap] Deep-equal is tight only on paths the 20 fixtures reach: 46 of 112 wrong engines still PASS 21/21

The rework fixed the projection weakness (the round-2 whitelist), but the fixtures do not drive many contract branches. A deep-equal oracle cannot catch a branch no fixture executes. Surviving wrong engines, grouped by the untested contract behavior:

- **Normalization (E1-17 has NO fixture at all; TRACEABILITY and README claim it):** lowercase removed; trim removed; `incidental` steps not skipped; consecutive-duplicate collapse removed; chain sorted (order erased). In every fixture the observed chain and the existing chain are byte-identical in prose and case, and no chain has an incidental or repeated step. Wording-independence, recon-step exclusion and evidence-order invariance are never exercised. (Probes confirm the real engine does these correctly today; nothing would notice a regression.)
- **Environment isolation (the focus item):** fingerprint-without-env is killed, but these survive: related-chain check ignoring env; matching an existing issue using the run env instead of the issue's env (`prod-env-cross-match`); env compare case-sensitive. No fixture has an existing issue in a different environment than the run.
- **Ticket state lifecycle:** unknown state treated as open; unrecognized state ("Done") treated as open; resolved-without-fix-claim reopening the ticket; resolved-without-claim silently returned as not-observed. No fixture has `state:"unknown"`, an unrecognized state, or resolved without a claim. This is the central "no reopen without an explicit claim, no write on unknown state" contract.
- **Fix-claim handling:** lax truthy `claimed` (`"false"` string would be a claim); a bare `reference` creating a claim.
- **Counting/replay:** key-only replay (`processedEvents[].key`) ignored; in-run dedup keyed on fingerprint instead of matched issue (the R2-M5 regression); count-set updated with the fingerprint only; a replayed observation not marked seen. No fixture has two observations that match one ticket via different fingerprints (alias + chain), and none uses `key`-only replay.
- **Ticket material:** `ownership` always "unknown" (no fixture is a `new` with repositories; e1-10 repos are on a rediscovery); production impact forced to "unknown"; ticket chain truncated to the first transition (no multi-step new ticket). The completeness gate is entirely untested: gate turned off, or any single field check removed (severity, impact enum, rationale, remediation, retest) all pass. No fixture has an incomplete positive.
- **Validity/kind:** unknown validity value accepted; unknown observation kind treated as positive; chain without semantics treated as identity (`nosemantics-new`); needed-evidence text for ambiguous identity replaced.
- **Non-observation summary fields:** invented exploitId when there is no retestTarget; `evidenceReferences` dropped; `edgeClassification` forced to none; `runSummary.edgeAccess` dropped; `sessionStatus` forced to ok. Every fixture has edgeAccess.none and session ok, so none of these fields is ever non-default.
- **Free-text stripped at all depths:** `strip()` drops every key named `reason`/`matchReason` recursively, including `runSummary.notObserved[].reason`, which carries the data field `stopReason`. A wrong engine that writes "fixed" there passes (`nonobs-reason-fixed`).
- **Invariant check vacuous:** `invariants()` compares `d.evidenceReferences === obs.evidence.references` against the ORIGINAL `input`, while plan() ran on a different deep-frozen clone, so the aliasing check can never fire (`evidence-aliased` survives).
- Also surviving: unresolved decisions dropping their target / fixClaimRef / neededEvidence; `[A,B]` vs `[B,A]`-style partial-chain superset direction (`subseq-no-reverse`), `related-exact-only-contig`.

Requirement for convergence: add fixtures (or table-driven oracle cases) for: E1-17 (case/whitespace/wording/incidental/dup step/multi-step order); cross-environment isolation both directions; state unknown, unrecognized, resolved-without-claim; open+claim; key-only replay; two observations hitting one ticket via alias; new with repositories and multi-step chain; each completeness-gate field; unknown kind/validity; non-observation with non-default edge/session/stopReason/no retestTarget. Compare `notObserved[].reason`. Fix the vacuous aliasing invariant (pass the frozen clone, or compare against it). Re-run `/tmp/r3/mut.mjs` and require zero survivors (or documented equivalents).

## MAJOR

### R3-M1 [semantic-model-gap] An existing issue whose chain is unusable (no semantics, empty, all incidental) and with no alias is silently ignored, so a matching observation creates a duplicate ticket and an alert

plan:249-256, 278-287. Validation only requires `normalizedChain` or `fingerprintAliases` to be an array. `normalizedChain:[{actorCapability:"prose only"}]` or `[]` normalizes to null, never matches, and is skipped by the related-chain check. Probe on e1-02 with that chain: outcome `new`, `create-ticket`, eligible. The contract: "Ambiguity routes to triage without speculative creation"; handoff: unknown state needed for a write means unresolved. The R2-M6 fix required env and chain-or-alias but never treated an existing ticket in the same environment that cannot be compared as a reason to triage. Fix: if any same-env existing issue has no comparable identity (null fp and no alias), return `unresolved` rather than `new`, or throw PlannerInputError.

### R3-M2 [semantic-model-gap] Partial/superset chains are triaged only against existing tickets, not against other observations in the same run (E1-18)

exploit-findings: the reconciler "compares it against relevant existing tickets and observations in the current run". Probe (e1-08b input, no existing issues): obs-1 chain [A], obs-2 chain [A,B] -> two `new`, two `create-ticket`, two eligible alerts, and the result is order-independent so the oracle's permutation check cannot flag it. The related check (plan:277-304) iterates `existingIssues` only. No fixture covers it.

### R3-M3 [semantic-model-gap, carried partial] A fix claim that stays on the snapshot alerts on every later run, and acceptance.md E1-19 was not amended to match the narrowing

plan:417-423 (open+claim) and 407-416 (resolved+claim) set eligible = true unconditionally. Within-run and same-event replay are right (processedEvents). STATUS says cross-run episode dedup is "Engineering 2" and narrows its own claim, but docs/aegis/review/acceptance.md E1-19 ("Same episode is notification-eligible once; new contradicted claim is a new eligible event") and exploit-findings:54 still require it, and the input has no field to carry "claim reference already contradicted/notified", so Engineering 2 cannot implement it correctly without a planner contract change. Needs an explicit disposition by the acceptance owner (amend E1-19 or add the input field plus fixtures), not a unilateral STATUS note. No fix-claim replay or new-episode fixture exists.

## MINOR

- **R3-m1 [oracle-gap]** e1-12b pairs the positive with a non-observation of a DIFFERENT exploit (the retest target SEC-101 is an admin-settings chain; the positive is export-download). The same-exploit half of E1-12 (positive preserved while a non-observation names the same exploit) remains untested. Probe: positive on SEC-101 plus non-observation targeting SEC-101 keeps the positive (correct) but the summary lists SEC-101 as `notObserved` for the run that confirmed it, with no link or flag.
- **R3-m2 [implementation-mistake]** "claimed strictly boolean" (R2-M2 disposition) is not validated: `fixClaim.claimed:"true"` on an open ticket is treated as no claim (`=== true`) and yields `rediscovered-open`, no alert, no PlannerInputError. Fails open (loses a contradiction) instead of failing closed.
- **R3-m3 [semantic-model-gap]** Production impact is validated only against the enum. A party run reporting `{value:"yes", rationale:"party exploit so prod"}` is emitted on the ticket unchanged; the E1-14 invariant only checks that the planner did not alter the source value.
- **R3-m4 [schema-vs-code]** Input schema requires `processedEvents[].eventId`, so the key-only entry the engine relies on for absent-eventId retries is schema-invalid. The schema's existingIssue requires only issueId/state while code also requires targetEnvironment and chain-or-alias, so a schema-valid input throws PlannerInputError. `ticketMaterial` schema is `additionalProperties:true` with no required fields.
- **R3-m5 [implementation-mistake]** Duplicate `observationId` values accepted (two decisions with the same id; `runSummary.unresolved` ambiguous). `severity` is free text ("banana" accepted); `affectedRepositories:"abc"` is spread into ownership `["a","b","c"]` (no type check; the schema is not enforced at runtime).
- **R3-m6 [workflow-failure]** Overclaim: STATUS.md says the oracle "schema-validates inputs/expected/actual" and README says it "writes each actual output ... for JSON Schema validation". run-fixtures.mjs imports no validator; the check is a manual npx step. TRACEABILITY lists E1-17 as covered although no e1-17 fixture exists (only a name in README prose).

## Verified correct (spot-checks, no action)

Resolved without claim -> unresolved; resolved+claim -> `claimed-fixed-reproduces` + reopen + eligible; open+claim -> evidence only, no reopen; state unknown/"Done" -> unresolved; production vs party and case/space-insensitive env handled correctly; case, whitespace, wording, incidental recon steps, duplicate steps do not change identity; superset/partial vs existing ticket -> unresolved; reordered chain stays distinct; two matching tickets -> unresolved; alias match works across versions; count-once by matched issue (dup observation -> `none`); key-only replay suppresses writes; non-observation proposes zero writes and `batchStatus` is partial for non-completed runs; round-trip of `ticketMaterial.chain` to `existingIssues[].normalizedChain` passes.

## Reproduction

`node /tmp/r3/mut.mjs` (112 single-mutation engines; prints survivors). Probes: `node /tmp/r3/probe.mjs`, `node /tmp/r3/probe2.mjs`. Survivors list at time of review: 46 (see section R3-B1).
