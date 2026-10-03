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
