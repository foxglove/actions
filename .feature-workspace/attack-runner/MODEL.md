# MODEL — Attack Runner semantic model

The committed product diagrams are the authoritative semantic model. This file
links them and records the invariants and unresolved owners the build must honor.

## Authoritative state machines (committed)

- Run / session lifecycle — `product-docs/attack-runner.md#run-and-session-lifecycle`
- Ticket lifecycle — `product-docs/exploit-findings.md#ticket-lifecycle`
- Finding reconciliation and delivery — `product-docs/exploit-findings.md#finding-reconciliation-and-delivery`
- Issuance and login lifecycle — `product-docs/attack-sessions.md#issuance-and-login-lifecycle`

## Independent state dimensions (keep separate; they vary independently)

1. **Observation** — confirmed-positive vs. non-observation.
2. **Execution / coverage** — completed, interrupted, timed-out, session-lost, not-attempted.
3. **Ticket state** — open, resolved, reopen-pending, delivery-uncertain.
4. **Delivery state** — applied, failed, pending/uncertain.
5. **Presentation** — run summary artifact (never a Linear write).

Facts, uncertainty, permission-to-act, delivery state, and presentation must not
collapse into one field. A non-observation never becomes "absent/fixed"; a failed
delivery never erases a valid positive observation.

## Core invariants

- One ticket per independently actionable exploit; identity follows evidence-backed
  causal transitions, not titles/wording/repo/harness/path.
- Non-observation never asserts absence or a fix; a resolved ticket receives zero
  writes on non-observation (comment, evidence, counter, lifecycle).
- Confirmed contradiction of a fix claim reopens the same closed ticket; a failed
  reopen is never recovered by creating a replacement ticket.
- One confirmed count per exploit per distinct run; replay/retries do not increment.
- Attack tools stay gated until a verified non-admin ordinary session (`PREFLIGHT_PASSED`).
- Credentials and exploit evidence never reach public workflow output/artifacts.
- The offline planner is deterministic and side-effect free; it proposes actions,
  it does not prove delivery.

## Unresolved product decisions (owners)

Tracked as the Stage-1→2 gate in `STATUS.md` (11 items). Build packets that depend on
an unresolved item do not start until it is resolved by the named owner.
