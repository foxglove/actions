# WP1.\* adversarial review (offline planner)

Reviewed: attack-runner/planner/src/{normalize,plan,index}.mjs, run-fixtures.mjs, check-fixtures.mjs, both schemas, all 7 fixtures.
Baseline: `run-fixtures.mjs` 7/7 PASS, `check-fixtures.mjs` PASS, all inputs/expected/actual outputs validate against the schemas (ajv 2020). The passing suite does NOT demonstrate contract conformance; findings below were reproduced with probes (script: scratchpad/probe.mjs, built from the fixtures with one field mutated each).

Totals: 1 blocker, 8 major, 8 minor.

What is correct (so it is not re-litigated): non-observation is structurally zero-write (plan.mjs:38-61 returns before any state lookup, issue state is never read); invalid/ambiguous validity -> unresolved with neededEvidence; a valid positive survives an invalid peer (e1-12); identity uses only `semantics`, missing semantics -> fingerprint null -> unresolved, never a prose identity; input not mutated; no I/O.

Line refs: plan.mjs = src/plan.mjs, norm = src/normalize.mjs, oracle = run-fixtures.mjs.

---

## BLOCKER

### B1 [implementation-mistake] `create-ticket` carries no ticket material (E1-01)

plan.mjs:140 emits bare `{type:"create-ticket"}`. E1-01 requires "exactly one ticket proposal containing exploit identity, labels, severity, production-impact assessment/rationale, ordered activity chain with evidence, what must be fixed, re-test expectations; unknown repo does not block". Output schema describes `ticketMaterial` as "Required for create-ticket" in prose but not in `required`/`if-then`, so the bare action validates. expected.json (e1-01, e1-12) encode the bare action, and the oracle only compares action _type_ strings (run-fixtures.mjs:16-19), so the defect is baked into the fixture and cannot fail.
Also missing from a new-ticket proposal: labels (Bug/pentesting/harness), normalizedChain + fingerprintVersion (without which the adapter cannot persist the lookup aid and a later run's `existingIssues[].normalizedChain` has no source), explicit `ownership: unknown` when affectedRepositories empty, productionImpact (E1-14).
Scenario: run e1-01 -> engineer-facing adapter has nothing to create the ticket from.
Fix: build ticketMaterial from obs.exploit (+ normalizedChain, fingerprint, labels, ownership), make it schema-required via if/then, assert it in the oracle (and in e1-14-style fixture for impact unknown).

---

## MAJOR

### M1 [implementation-mistake] Open ticket with explicit fix claim is mislabeled `rediscovered-open`; claim never identified (E1-03, handoff row 3)

plan.mjs:145-146: `claimedFixed = state==="resolved" && fixClaim.claimed`. E1-03 says "ticket closed OR already open ... targets the same ticket and fix claim; proposes evidence plus reopen only if closed". Probe: e1-02 with `fixClaim:{claimed:true}` -> `rediscovered-open`, notificationEligible=false, claim ignored. The contradiction of a recorded fix claim on an already-open ticket is lost (and never eligible). Additionally the decision never outputs `fixClaim.reference` in ANY case (output schema has no field for it), though handoff says "identify the claim". e1-03 expected has no claim reference either.
Fix: claimedFixed = fixClaim.claimed===true (any state); reopen-ticket only if state==="resolved"; add `fixClaimRef` to decision + schema; fixture "open + claim".

### M2 [implementation-mistake + semantic-model-gap] Unknown / missing / claim-less resolved state is treated as open and produces writes

Handoff: existing issue is "open, explicitly claimed fixed, or unknown"; table: "unknown state required for a write -> unresolved". Schema `state` enum is only open|resolved (no unknown), and the code (plan.mjs:145-153) treats everything that is not (resolved && claimed) as open. Probes: `state:"unknown"`, `state` deleted, and `state:"resolved"` with no claim all yield `rediscovered-open` + `append-evidence` + `increment-confirmed-count` on that ticket. A resolved ticket with no explicit claim is therefore written to and counted as "open" with no reopen/lifecycle handling, i.e. an undefined and contract-violating write.
Fix: add `unknown` to the enum; unresolved (neededEvidence: ticket state) for unknown/missing state and for resolved-without-claim; only `open` -> rediscovered-open.

### M3 [implementation-mistake + semantic-model-gap] Replay/in-run dedup can still double-count; replay protection depends on an optional eventId

(a) plan.mjs:162-170: a replayed observation does not add its fingerprint to `seenThisRun`. Probe: obs-1 (eventId in processedEvents) + obs-2 same chain with a new eventId in the same run -> obs-1 `none`, obs-2 `append-evidence + increment-confirmed-count`. The run's count for that exploit was already applied by the replayed event, so this is a second count in one run (violates "one confirmed count per exploit per run", E1-08).
(b) `eventId` is optional (input schema) and `processedEvents` carries only eventId (no runId/exploit key). Probes: observation with no eventId, or a transport retry carrying a regenerated eventId, are counted again. Idempotence per (runId, exploit) is not modelled anywhere, only per opaque id.
(c) in-run duplicate drops the second observation's evidence entirely (action none) although alternate evidence of the same control failure is useful (minor).
Fix: derive an idempotency key (runId + fingerprint/exploitId) checked against processedEvents; require eventId (schema) or fall back to the derived key; mark seen even when replayed.

### M4 [implementation-mistake] No input validation: empty/unreadable batch accepted silently; non-"confirmed-positive" kinds treated as positives

acceptance.md:33: "return an explicit failure rather than silently accepting an empty batch". Probes: `plan({})` -> `{runId:undefined, decisions:[]}` (success shape); `plan({observations:"abc"})` iterates characters and emits 3 `unresolved` decisions with observationId null; `plan(null)` throws an accidental TypeError. A missing/bogus `kind` (e.g. "suspected", or deleted) with validity "valid" falls through to the positive path (plan.mjs:38 only tests for "non-observation") and proposes `create-ticket`. Missing observationId passes through as null. runId may be undefined. The schemas are never enforced by the code.
Fix: explicit input validation returning/throwing a structured failure (not an empty plan); closed switch on kind with unknown -> unresolved.

### M5 [semantic-model-gap] Whole-chain exact-equality identity: incidental/extra transitions create duplicate tickets; unmatchable existing issues become speculative `new`; partial chains never route to triage (E1-17, E1-18)

norm:40-53 fingerprints the full ordered tuple list. Spec: matching core is "causally relevant transitions", excluding "incidental reconnaissance". The transition has no causal/incidental marker, so any recon transition with a semantics tuple changes the fingerprint. Probe: e1-02 observation with one extra leading recon transition -> `new` + create-ticket + eligible (duplicate of SEC-101). A subset/superset or partially overlapping chain is also `new`, never ambiguous, so E1-18 "ambiguous partial chain routes to triage" is unreachable (only `matches.length>1` is ever ambiguous, plan.mjs:110-130). Separately, an existing issue lacking `normalizedChain` (schema-optional) or with incomplete semantics is invisible: probe -> positive becomes `new` (plan.mjs:106 compares null to fp), a speculative duplicate of a ticket the planner could not compare. Handoff: "unknown state required for a write -> unresolved".
Fix: add a `causal` flag (or define the matching core explicitly), detect partial overlap -> unresolved, and treat existing issues with exploitId/ticket of unknown identity as ambiguity candidates (unresolved) rather than absent.

### M6 [semantic-model-gap] Target environment and prerequisites are not part of identity

norm:8-9 documents environment as constant and drops it; norm:24-36 also ignores `prerequisites` although the contract says "causally relevant transitions" and "semantic ordering ... prerequisites". Probe: run.targetEnvironment="production" observation matches and appends to a "party" ticket (rediscovered-open); changing a transition's `prerequisites` to something unrelated leaves the fingerprint identical. The existingIssue schema has no environment at all, so it cannot even be compared. E1-17 says "causal prerequisites preserved".
Fix: carry environment on existing issues and include it in the match (mismatch -> not same exploit / unresolved); encode prerequisites as structured references (indices) in the tuple.

### M7 [implementation-mistake] `not-observed` summary entries misreport attempted coverage and execution status (E1-04, E1-06)

plan.mjs:58 sets `attemptedCoverage: run.coverage.tested` for every non-observation, regardless of that observation's execution status. Probe: execution `not-attempted` -> entry lists `["exports.download"]` as attempted coverage; interrupted/session-lost re-tests do the same. That reads as completed coverage, exactly what E1-06 forbids. plan.mjs:56 defaults a missing `execution` to `"not-attempted"` (schema requires it, but unvalidated; fabricating a status is wrong; should be unresolved/unknown). `reason` defaults to "not observed in this run" without carrying session/edge conditions; handoff/E1-04 want "attempts, conditions, coverage, evidence references, and stop reason"; an EDGE_CONTROL_BLOCKED run is not linked to the entry (a `completed` entry in a blocked run looks complete). Observations also have no per-observation `attempted` field in the schema, so attempts cannot be represented honestly.
Fix: add per-observation attempted/conditions to the input schema; attemptedCoverage only from it; link edgeAccess/session status into the entry.

### M8 [oracle-gap] The oracle cannot fail a wrong engine on most invariants

run-fixtures.mjs project() is a whitelist projection of both got and want (lines 21-50), so:

- Anything not whitelisted is never compared: `reason`, `matchReason`, `neededEvidence` text, `ticketMaterial` (B1 passes), `runSummary.coverage`, `runSummary.stopReason`, notObserved `reason/attemptedCoverage/evidenceReferences` (M7 passes). An engine whose reason says "exploit fixed/absent" passes.
- Extra top-level or summary fields are ignored: an engine that adds `issueWrites:[{issueId:"SEC-101",action:"comment"}]` for a resolved ticket still passes the "zero writes" fixture (only decision.proposedActions are looked at).
- Invariants are not asserted on the actual output at all: check-fixtures.mjs applies "not-observed => zero writes", "unresolved => no writes", "replay => no mutation" to expected.json only (lines 129-151); nothing checks them on plan()'s output, or checks one-count-per-exploit-per-run on any output.
- The actual output is never schema-validated in the suite (ajv is README-only and never run; I ran it manually and it passes), and expected.json are hand-written, not generated.
- determinism check compares the same projection (which sorts decisions) so order-sensitivity (which of two duplicates is counted) is invisible; input-immutability is checked by stringify only (no deep freeze; output aliasing, m1, undetected).
  Fix: assert invariants generically on raw output for every fixture, deep-equal whole output (minus an explicit free-text allowlist), schema-validate both, deep-freeze inputs, permutation test.

---

## MINOR

### m1 [oracle-gap] Fixture coverage is thin for the targeted subset

Missing: in-run duplicate (E1-08 requires BOTH in-run duplicate and replay; only replay is fixtured), open-ticket-with-claim (E1-03 "already open"), non-observation with interrupted/timed-out/session-lost/not-attempted (E1-04 says all four; only `completed`), non-observation + valid positive for same exploit (E1-12 second half; probe shows the summary lists the exploit as not-observed while a positive exists in the same run, unflagged), unknown state, ambiguous (multiple matches or `ambiguous-identity`, `unresolved` branch only covered by invalid-evidence), missing semantics, distinct-exploit-similar-title negative (E1-18), cross-repo/harness (E1-10), production-impact unknown (E1-14). e1-17 expected text claims "recon detail" differs but the input contains no recon step, and the semantics tuple is copy-pasted identical to the existing issue, so the fixture only proves equal tuples match (tautological; the hard part, deriving the tuple from paraphrase, is supplied by the fixture author).

### m2 [implementation-mistake] Output aliases input arrays

plan.mjs:20 (`evidenceReferences`), :58 (`attemptedCoverage`), :188 (`coverage`) return references to input objects. Probe: pushing to `decision.evidenceReferences` / `runSummary.coverage.tested` mutates the caller's input. Not an I/O violation, but weakens E1-15 "no input mutation" for consumers and is undetected by the oracle.

### m3 [implementation-mistake] Decision text/labels are not evidence-backed or can mislead

`matchReason` is a fixed string (plan.mjs: "same normalized causal chain as the open ticket") not tied to the matched tuple/fingerprint/version; E1-17 requires "a recorded normalized-chain match reason", and for `new` the contract wants "why a distinct ticket is warranted". Replay decisions reuse the normal `rediscovered-open` reason (expected.json says "already fully applied", the code does not). Second in-run duplicate of a new exploit is labelled `outcome:"new"`, target `new-issue`, with action `none` (a consumer keyed on outcome would see two new tickets). `reasonFor` default returns "" which would violate output schema minLength.

### m4 [semantic-model-gap] No batch-level status or run-summary completeness (E1-13)

Output has no field saying the batch had unresolved/failed items, and runSummary lacks proposed ticket list / unresolved list / proposed-vs-acknowledged separation (spec "Each run produces a summary output"). Consumers must derive "not wholly successful" themselves.

### m5 [semantic-model-gap] Semantic tuple is free text; coercion can create identity

Schema description says "controlled-vocabulary" but every field is an unconstrained string, no enum or pattern. norm:30-33 coerces with String(): an object/array value becomes "[object object]" and is accepted as identity (probe: surface:{a:1} -> `new`, identity established); only trim+lowercase is applied, so "export download api" != "export-download-api" (probe -> duplicate `new`). Identity quality is entirely delegated to an unverified upstream author/LLM, contrary to "do not hide untested identity decisions at an undocumented boundary".

### m6 [semantic-model-gap] Model cannot express E1-10 / E1-19 / E1-20 pieces (outside current subset, but the schema forecloses them)

No action to append new remediation items/repos to an existing ticket (E1-10 "retains all remediation items"); no fix-claim episode state, so a second run contradicting the same already-contradicted claim (ticket resolved again with the stale `fixClaim`) is again `claimed-fixed-reproduces` + notificationEligible=true (E1-19 once per episode); fingerprint version/aliases are not carried on existing issues (norm recomputes the fingerprint from the stored chain, which silently handles a version bump but gives no stable-ID alias path and no migration signal).

### m7 [implementation-mistake] Non-observation bypasses validity check

plan.mjs:38 runs before the validity test (65): a `non-observation` with `validity:"invalid-evidence"` or "ambiguous-identity" still becomes `not-observed`. Malformed evidence should stay unresolved. Low impact since no write results.

### m8 [workflow-failure] README is stale and Status text contradicts delivered state

README.md says "Status: ... `plan()` ... is WP1._ and is not implemented yet" and "Both passed at WP0.1 landing"; no runnable example is provided/documented (handoff: "short runnable example"); `npm`/ajv schema validation is documented but not wired into any script. STATUS.md still says WP1._ not yet implemented. E1-16 final-revision evidence has nothing to attach to yet.

---

## Invariant scorecard (against the code, with probes)

| Invariant                                           | Result                                                                                      |
| --------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| Resolved ticket gets zero writes on non-observation | HOLDS in code (structural). Not robustly asserted by oracle (M8).                           |
| One confirmed count per exploit per run             | FAILS: replay + fresh dup (M3a), regenerated/absent eventId (M3b).                          |
| Replay/dup => no mutation                           | HOLDS only for exact eventId in processedEvents.                                            |
| Valid positive survives invalid peer                | HOLDS.                                                                                      |
| Non-observation never asserts absence/fixed         | HOLDS in text; not oracle-checked; coverage misreport (M7).                                 |
| Output is a proposal, never claims delivery         | HOLDS (no delivered/reopened wording).                                                      |
| Missing semantics never becomes identity            | HOLDS for missing; FAILS for malformed values (m5) and for unmatchable existing issue (M5). |
| Purity/determinism                                  | HOLDS logically; aliasing (m2); counted-duplicate choice is input-order dependent (m3/M3).  |
| Reopen the SAME ticket                              | HOLDS for resolved+claim; FAILS for open+claim (M1).                                        |

---

## Disposition (2026-10-03, follow-up commit)

Routed per feature-pipeline: correctness defects + the oracle gap fixed now; remaining
items tracked to their proper E1 slices. Oracle now: 9/9 + structural-reject, invariants
on actual output, determinism, permutation-invariance, immutability; actual outputs
schema-valid.

| ID  | Disposition                                                                                                                                                                                                                                              |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| B1  | FIXED — `create-ticket` carries full `ticketMaterial` (identity, Bug/pentesting/harness labels, severity, productionImpact, chain, remediation, re-test, ownership, normalizedChain+fingerprintVersion); schema-required via if/then; oracle asserts it. |
| M1  | FIXED — open ticket with a fix claim → `claimed-fixed-reproduces` (no reopen); `fixClaimRef` emitted; fixture `e1-03b`.                                                                                                                                  |
| M2  | FIXED — `unknown` added to state enum; unknown/missing state and resolved-without-claim → `unresolved`; only open → rediscovered-open.                                                                                                                   |
| M3  | PARTIAL — (a) fingerprint marked seen even on replay (no same-run double count); (b) derived idempotency key `runId+fingerprint` + optional `processedEvents[].key`; cross-run durable dedup remains Engineering 2 per handoff.                          |
| M4  | FIXED — `PlannerInputError` on structurally unreadable input; unknown `kind` → unresolved; oracle structural-reject tests.                                                                                                                               |
| M5  | PARTIAL — incidental-recon exclusion + env in identity fixed; full partial-chain/subsequence triage → E1-18 slice; issue without `normalizedChain` is a documented non-matchable adapter input.                                                          |
| M6  | FIXED — `targetEnvironment` is part of the fingerprint; prod cannot merge into party.                                                                                                                                                                    |
| M7  | PARTIAL — `attemptedCoverage` no longer over-claims (completed-only); edge classification linked in `notObserved`; richer conditions → E1-06 slice.                                                                                                      |
| M8  | FIXED — oracle asserts invariants on ACTUAL output (ticket material, zero-write, batchStatus, aliasing), determinism, permutation-invariance, structural-reject; actual outputs validated against the output schema.                                     |
| m1  | PARTIAL — added `e1-03b` and `e1-08b`; `e1-17` now has a recon step (non-tautological); other fixtures → listed slices.                                                                                                                                  |
| m2  | FIXED — output arrays cloned; oracle asserts no aliasing.                                                                                                                                                                                                |
| m3  | ADDRESSED — in-run duplicate relabelled `rediscovered-open`; reasons corrected.                                                                                                                                                                          |
| m4  | FIXED — `batchStatus` + `unresolved` list in the summary + schema.                                                                                                                                                                                       |
| m5  | FIXED — non-string semantics → identity null → unresolved.                                                                                                                                                                                               |
| m6  | DEFERRED — remediation-append (E1-10), fix-claim episode (E1-19), fingerprint aliases (E1-20) → listed slices.                                                                                                                                           |
| m7  | DEFERRED (minor) — non-observation ignores validity by design; noted.                                                                                                                                                                                    |
| m8  | FIXED — README reflects implemented state; `example.mjs` added; schema validation documented and wired.                                                                                                                                                  |
