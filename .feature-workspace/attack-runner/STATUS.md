# STATUS — Attack Runner

**Stage:** 3 (Build) — E1 offline planner implemented and hardened through two review
rounds; round-3 verification pending.
**Working branch:** `claude/exciting-cerf-vkmwu5`.

## Done

- **WP0.1** — planner I/O contract + fixtures.
- **WP1.1–WP1.5** — planner (`attack-runner/planner/src/`): structured-semantics identity
  (env in identity, incidental exclusion, duplicate-step collapse, fingerprint aliases,
  partial-chain triage); five-outcome engine; count-once keyed on matched identity;
  replay/in-run dedup with emitted idempotency key; non-observation zero-writes; strict
  input validation; complete-ticket-material gate; append-remediation; run status in summary.
- **Oracle** (`run-fixtures.mjs`): deep-equals authored full expected (minus prose),
  asserts invariants on actual output, proves input→output round-trip, runs a mutation
  self-test (proves tightness), and schema-validates inputs/expected/actual. 20 fixtures;
  **21 passed / 0 failed** + 5 structural-reject. Guard PASS.
- **Reviews:** round 1 and round 2 complete; findings fixed or routed (see
  `review-wp1.md`, `review-wp1-round2.md`). Round 2 exposed and fixed a weak-oracle
  workflow failure.

## Honest coverage note (corrected after round 2)

- E1-01..E1-15, E1-17, E1-18, E1-20 are exercised and deep-equal-verified.
- **Within-run** behavior only for E1-19 (eligibility) and E1-09 (per-run count):
  **cross-run** notification-episode dedup and durable count totals are Engineering 2
  (durable state), per the handoff — not claimed as done here.
- E1-10 remediation-**union** is proposed via `append-remediation`; the actual union is a
  delivery/adapter concern (WP2.7).
- E1-16 is the final-revision handoff check (Stage 4 / WP3.2).

## In progress

- **Round-3 verification review**; then Stage 4 conformance packaging.

## Blockers — Stage-1→2 gate (PM must resolve)

11 items in `pm-clarifications.md` (blocking: issuer-service ownership acceptance;
out-of-repo issuer-function + mailbox). E2/Release wait on these; WP1 does not.
Spawned task: "Get PM answers".

## Next action

1. Round-3 review; fix any material findings (skill cap: 5 rounds).
2. Stage 4 conformance; E2 once the PM gate clears.
