# Self-review PR #55, round 2 (final)

Verdict: SHIP (no Critical/High; 3 Medium recommended before push, all cheap; none is a functional defect in the code under review).

Gates run: run-fixtures 57 passed / 0 failed, structural 9 ok; check-fixtures PASS; mutation-test 117 mutants, 114 killed, 3 equivalent survivors, 0 noapply, PASS.

## Fix verification

1. validateInput legacy-ticket throw removed: CONFIRMED. An open ticket with no normalizedChain/alias no longer throws (probe 1, 4, 6, 8, 9, 17, 22 all return decisions). Exact-match obs alongside it still resolves (e1-50 obs-2, probe 10, 16).
2. State-independent triage + uncomparableInEnv: CONFIRMED correct.
   - partial overlap vs unknown-state and resolved-with-claim/no-claim tickets triages (e1-48, e1-49, probe 13).
   - different-env partial overlap and distinct chain vs resolved ticket still `new` (probe 14, 15).
   - uncomparable ticket triages a would-be-new obs, does not block exact match (probe 10/16), order independent (probe 11, outcome set identical both orders).
3. In-run duplicate of `new` stays `new` + `[none]` (probe 18); dup-relabel mutant killed; alias-only-chainless removed from allowlist and killed.
4. Structural-reject cases and the <=1 create-ticket invariant present and passing.
5. Fixtures e1-48..52 present, pass. Schema: existingIssue `anyOf` requires normalizedChain or fingerprintAliases, and `transition.semantics` is OPTIONAL, so a legacy ticket with a prose-only chain is schema-valid (this is why M1 matters).

## Findings

### M1 (Medium) uncomparableInEnv blast radius is env-wide, state-agnostic, and unnamed

plan.mjs:327-351. Any single same-env ticket whose chain lacks `semantics` (every pre-planner/legacy ticket is schema-valid in that form) and has no alias routes EVERY would-be-new observation in that environment to `unresolved` (probes 1, 2: open and resolved legacy tickets both block). In a real backlog this means the planner never proposes `create-ticket` for that environment until all legacy tickets are backfilled with a chain or alias. Fail-closed matches "ambiguity routes to triage without speculative creation" (exploit-findings.md:24,85) so it is not a contract violation, but:

- the decision names no ticket: neededEvidence is generic, target is `none`, so triage cannot tell which ticket needs normalization. Fix: list the uncomparable issueIds in neededEvidence (e.g. `normalized chain or alias for SEC-LEGACY`), and/or set matchReason detail.
- README does not state this consequence (line 63 says only "uncomparable ticket state"). Add one sentence: legacy tickets must be backfilled or all new findings in that env go to triage.
- Optional narrowing (judgment call, not required): skip uncomparable tickets with no `affectedSurfaces` overlap if that data is available; not done today and not required for safety.

### M2 (Medium) mutation coverage gaps in the new uncomparableInEnv branch

Probed with my own mutants (/tmp/r2/m.mjs); these SURVIVE the fixture suite:

- `unc-env-ignored` (drop the same-environment condition): a legacy ticket in another env would block new tickets. No fixture covers it (probe 3 behaves correctly today).
- `unc-alias-clause-off` (alias-bearing chainless ticket treated as uncomparable): e1-51 does not catch it because its obs EXACT-matches the alias and returns before the branch.
- `unc-alias-nolength` (empty `fingerprintAliases: []` treated as comparable): no fixture.
  Fix: add (a) fixture: alias-only ticket with non-matching alias + distinct obs -> `new`; (b) fixture: chainless legacy ticket in a different env + obs -> `new`; (c) fixture: legacy ticket with `fingerprintAliases: []` + obs -> `unresolved`; plus mutants for the three conditions above. The mutants killed today for this branch: `uncomparable-off`, chain-null check, evidenceReferences drop.

### L1 (Low) replay is pre-empted by uncomparable/partial triage

A replayed `new` (processedEvents contains its eventId) with a legacy ticket present reports `unresolved` instead of `[none]` (probe 12/12b), making every retry batchStatus `partial`. No write is proposed so idempotency is safe; only noise. Same pre-existing pattern for partial-overlap. Consider checking `replayed` before the triage branches, or accept and document.

### L2 (Low) junk aliases count as identity

`fingerprintAliases: [""]` (probe 7) makes a chainless ticket "comparable", so a new obs is created despite the ticket being effectively unidentifiable. Schema allows any string. Filter to non-empty strings in the uncomparable check.

### L3 (Low) fixClaim null/empty still kills the whole batch

`fixClaim: null` or `{}` on one existing issue throws PlannerInputError (probes 19, 20). Consistent with the schema (object with required boolean `claimed`), so defensible, but it is the same single-bad-ticket-kills-batch class fix 1 removed. Decide deliberately; at minimum the structural-reject test documents it.

### L4 (Low) dead code

plan.mjs:319-320 (`fingerprint(iss.normalizedChain,...) === fp -> return false`) is unreachable: an equal fingerprint is already in `matches`, and this block only runs when matches is empty. Mutant `relissue-selfexcl-off` survives (equivalent). Remove it (the fix list says the dead overlap guard was removed; this one remains). Likewise `p.norm !== null && p.fp !== null` in runPositives is redundant (both null together).

### L5 (Low/info) validateInput guards that survive mutation

`obs-array-off`, `existing-array-off`, `processed-array-off`, `issueid-off`, `obsid-off` survive because later code throws or rejects anyway (non-PlannerInputError TypeError or equivalent behavior), so the structural-reject test cannot distinguish. If the contract is "explicit PlannerInputError", assert error class/name in the structural-reject cases.

## Over-triage assessment

State-independent partial/superset triage is appropriate: partial overlap with a resolved/unknown ticket is exactly the ambiguity the contract routes to triage (acceptance E1-18). Distinct non-overlapping chains vs resolved tickets still create (probe 15); other-env tickets never triage (probe 14). Single-step observations that are a subsequence of any longer same-env chain will triage (pre-existing design, sparse subsequence per e1-34), which is conservative, not a defect.

## Mutants that should exist but do not

unc-env-ignored, unc-alias-clause-off, unc-alias-nolength (M2). Optional: dup-relabel (exists in my probe, killed, but not in the repo gate), state-skip-restored (killed in my probe; the repo has no explicit mutant re-adding the `iss.state !== "open"` skip, so a regression of fix 2 is only caught via fixtures e1-48/49, which is adequate but worth a named mutant).
