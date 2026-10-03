# STATUS — Attack Runner

**Stage:** 3 (Build), in progress.
**Working branch:** `claude/exciting-cerf-vkmwu5`.
**Approved plan:** work-packet breakdown accepted by engineering lead.

## Done

- **WP0.1** — offline planner I/O contract + fixtures (`attack-runner/planner/`).
  Schemas validate with ajv (draft 2020-12); fixture guard passes.

## In progress

- **WP1.1–WP1.4** — planner implemented (`attack-runner/planner/src/`):
  normalization/identity from structured `semantics` (WP1.1), five-outcome decision
  engine (WP1.2), count-once/replay dedup + eligibility (WP1.3), non-observation
  zero-writes + invalid→unresolved (WP1.4). Oracle `run-fixtures.mjs`: **7/7 pass**,
  deterministic, no input mutation (WP1.5 partial).
- **Self-review gate:** round-1 isolated review complete (1 blocker/8 major/8 minor);
  correctness + oracle-gap findings fixed this slice, remainder routed to E1 slices below.
  See `review-wp1.md` disposition. Oracle: 9/9 + structural-reject.

## Remaining in WP1 (next slices)

Fixtures currently cover E1-01,02,03,04,08,12,17. Still to add + implement:
E1-05 (known issue absent, no re-test → no closure), E1-06 (interrupted re-test),
E1-07 (positive survives later session loss), E1-09 (same open finding, different run),
E1-10 (cross-repo / cross-harness single ticket), E1-11 (ambiguous match + unknown repo),
E1-13 (mixed batch not wholly successful), E1-14 (production impact unknown),
E1-18 (independent control failures stay distinct), E1-19 (notification eligibility once),
E1-20 (fingerprint-version migration/aliases).

## Open failures / blockers — Stage-1→2 gate (PM must resolve)

WP0.1 and WP1.\* do not depend on these; E2/Release packets do. 11 items; see
`pm-clarifications.md`. Blocking: (1) issuer-service ownership acceptance,
(2) out-of-repo issuer-function + mailbox dependencies. (Spawned task: "Get PM answers".)

## Next action

1. Incorporate self-review findings for WP1.1–1.4 (follow-up commit).
2. Add the remaining E1 fixtures + extend `plan()` to cover them (test-first).
3. On PM gate resolution, sequence the E2 packets.
