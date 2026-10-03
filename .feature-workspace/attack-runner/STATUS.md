# STATUS — Attack Runner

**Stage:** 3 (Build) — E1 offline planner complete; pending round-2 review then Stage 4.
**Working branch:** `claude/exciting-cerf-vkmwu5`.

## Done

- **WP0.1** — planner I/O contract + fixtures.
- **WP1.1–WP1.5** — planner implemented (`attack-runner/planner/src/`): identity/normalization
  from structured `semantics` + environment + incidental exclusion + fingerprint aliases;
  five-outcome decision engine; count-once/replay/in-run dedup; non-observation zero-writes;
  invalid/unknown-state/ambiguous → unresolved; structured input validation; batch status.
- **E1 criteria coverage (offline):** E1-01…E1-15, E1-17…E1-20 exercised by 19 fixtures.
  Oracle `run-fixtures.mjs`: **19 passed, 0 failed** + 3 structural-reject; asserts invariants
  on actual output (ticket material, zero-write, no-impact-promotion, batchStatus, aliasing),
  determinism, permutation-invariance, input immutability. Guard PASS; inputs and all actual
  outputs validate against the schemas (ajv draft2020).
- **Round-1 self-review** complete; findings fixed/deferred (`review-wp1.md`).

## Deferred to Engineering 2 / later stages (not E1)

- Cross-run durable notification + dedup state (handoff: E2 owns persistence).
- Remediation-union on rediscovery across repos (adapter/delivery concern, WP2.7).
- Fix-claim episode tracking across runs (WP2.7 / E2).

## In progress

- **Round-2 isolated review** over the complete WP1, then Stage 4 conformance.

## Open failures / blockers — Stage-1→2 gate (PM must resolve)

WP1 does not depend on these; E2/Release packets do. 11 items in `pm-clarifications.md`
(blocking: issuer-service ownership acceptance; out-of-repo issuer-function + mailbox).
Spawned task: "Get PM answers".

## Next action

1. Round-2 isolated review of WP1; fix any material findings (repeat until clean).
2. Stage 4 conformance packaging; then E2 once the PM gate clears.
