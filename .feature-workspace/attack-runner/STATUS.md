# STATUS — Attack Runner

**Stage:** 3 (Build) — E1 offline planner implemented and hardened through three review
rounds plus a committed mutation-testing gate (0 unexpected survivors).
**Working branch:** `claude/exciting-cerf-vkmwu5`.

## Done

- **WP0.1** — planner I/O contract + fixtures.
- **WP1.1–WP1.5** — planner (`attack-runner/planner/src/`): structured-semantics identity
  (env in identity + case-insensitive, incidental exclusion, duplicate-step collapse, chain
  order significant, fingerprint aliases, partial/superset triage); five-outcome engine;
  count-once keyed on matched identity; replay/in-run dedup with emitted idempotency key;
  non-observation zero-writes; strict input validation; complete-ticket-material gate;
  append-remediation; run status in summary; non-production runs cannot assert prod impact.
- **Verification** — `run-fixtures.mjs` (deep-equal authored expected + invariants on actual
  - round-trip + mutation self-test + structural-reject), 60 fixtures, **61 passed / 0 failed**
    - 14 structural-reject; `check-fixtures.mjs` PASS; `mutation-test.mjs` (committed convergence
      gate) **128 mutants, 125 killed, 0 unexpected survivors** (3 documented equivalents);
      inputs/expected/actual schema-valid via ajv (negative-input fixtures marked
      `INPUT_SCHEMA_INVALID`).
- **Reviews** — rounds 1, 2, 3 + a PR #55 review round and an isolated self-review complete;
  findings fixed or routed (`review-wp1*.md`, `self-review-pr55.md`). Round 2
  fixed a weak-oracle workflow failure; round 3 drove mutation survivors 46 → 4 (equivalents).

## Open product question (R3-M3, for the acceptance owner)

Cross-run fix-claim **notification-episode** dedup (acceptance E1-19 / exploit-findings:54):
the planner computes eligibility per run correctly, but "notify once per episode across runs"
needs either an acceptance.md amendment (declare it Engineering 2's durable-state job) or a new
planner input field carrying "this fix-claim contradiction was already notified". Needs the
acceptance owner's decision; not unilaterally closed.

## Open product question (R3-F4, for the acceptance owner)

**Uncomparable legacy ticket blocks creation.** A same-environment ticket in any state
(open, resolved, or unknown) with no
normalizable chain and no non-blank alias routes every would-be-`new` observation in that
environment to `unresolved` (fixtures e1-50, e1-53..56; README "Triage rules worth knowing").
This follows the "ambiguity routes to triage" rule (E1-18, exploit-findings.md:24,85), but no
acceptance criterion names it. Decide: ratify it as an E1 criterion (and its pre-first-run
backfill duty), or narrow it. Until then it is implemented, gated, and unratified.

## Coverage note

E1-01..E1-15, E1-17..E1-20 exercised and mutation-gated. Cross-run episode dedup + durable
count totals = Engineering 2 (handoff). E1-10 remediation **union** proposed via
`append-remediation`; actual union is delivery (WP2.7). E1-16 = Stage-4 handoff check.

## Next

- Stage 4 conformance packaging for the offline planner.
- **PM gate CLEARED** → E2 / Release unblocked (table below). Creating per-packet Linear
  tickets in Foundations is an outward write — confirm with the user first. Most E2 adapters
  need live runtime evidence / other repos (issuer, mailbox, GCS, Strix, party env).

## PM gate — Stage-1→2 (E2 / Release) — ✅ CLEARED 2026-10-02

WP1 did not depend on these; the E2/Release packets do. All 11 `pm-clarifications.md`
items were resolved interactively by the release/product-decision authority
(**Foundations team**) on 2026-10-02 (spawned task: "Get PM answers"). Two non-blocking
**pre-first-run follow-ups** remain (concrete test service-account value — item 3; concrete
GCS project/bucket name — item 6); both are needed before the first live run, not before
E2/Release build sequencing.

Human oracle: **Foundations team** (authority per `GOAL.md` / `attack-sessions.md`).
Append-only detail per item in `retro-log.json`.

| #   | Decision                                                                                                                                                                                                                                                                                                                               | Accountable owner                                                                                                            | Date       | Notes / reservations                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- | ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Accept proposed issuer owners as the team that owns the company issuer function + test identity + mailbox access.                                                                                                                                                                                                                      | `@foxglove/data-curation-search`; sign-off **Foundations team**                                                              | 2026-10-02 | No separate on-call rotation yet — **accepted as-is for v1**.                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| 2   | Issuer function + mailbox provisioning owned by the **App repo**. Build unassigned ("any available engineer"); land within ~1 week (target 2026-10-09).                                                                                                                                                                                | App repo (app/auth code owners); interim magic-link minting by **Foundations team**                                          | 2026-10-02 | Docs (`attack-sessions.md` 18–19/149–154, `engineering-handoff.md`) attribute these to "app/auth code owners" — consistent. If a distinct auth repo exists, app-vs-auth split of each piece is a sub-point for the owning team. Interim manual minting (by the release authority) matches `attack-sessions.md:150`.                                                                                                                                                                                         |
| 3   | Authorized target set = **all hosts** under `*.foxglove.party` (full wildcard). Test identity = a **service account minted by the Foundations team**. Run window = **Mondays 09:00 PT** + manual runs.                                                                                                                                 | Scope/authorization: **Foundations team**; test account minting: **Foundations team**                                        | 2026-10-02 | Full wildcard authorized — explicitly overrides the drafted "maximum boundary, not every host" caution; production stays out of scope (`party ≠ production` invariant). ⚠ **Pre-first-run follow-up:** concrete service-account identity/data not yet named. No separate maintenance blackout window provided.                                                                                                                                                                                              |
| 4   | Starting session is **ordinary by default**. **No** app-owned session-bound mode signal is pre-authorized as a v1 release dependency.                                                                                                                                                                                                  | **Foundations team**                                                                                                         | 2026-10-02 | Treated as low-risk: the runner starts ordinary and the demonstrated ordinary→admin escalation is itself the exploit (`exploit-findings.md:5,79`); pause/stop on reaching admin aligns with "minimum evidence necessary; stop before irreversible damage" (`instructions.md:51`). Reservation: if the feasibility spike shows ordinary vs. impersonation genuinely cannot be distinguished from app evidence, reopen with PM — not auto-triggered.                                                          |
| 5   | **App/auth code owners** confirm the 4 DKIM trusted-config values (`d=` signing domain, `s=` selector(s), `From` sender, `To` mailbox) against a genuine message, and own the `DKIM_SELECTOR_UNAPPROVED` investigation path.                                                                                                           | App/auth code owners (Item-1 owners)                                                                                         | 2026-10-02 | They own SendGrid domain authentication, so they read the real values off a genuine magic-link email and confirm selector legitimacy before adding one (`attack-sessions.md:51,150`, `engineering-handoff.md:94`). `To` mailbox is the one the Foundations team provisions (Item 2).                                                                                                                                                                                                                        |
| 6   | **GCS confirmed** (accepted contract stands — no re-spec). Authorized reader group = **all of Engineering + CEO**. Provisioned by the **Infra team** through the infra process.                                                                                                                                                        | Reader-group/storage decision: **Foundations team**; provisioning: **Infra team**                                            | 2026-10-02 | PM's "decided against GCS?" reconciled against the accepted contract (`attack-runner.md:46,48,50,156`, `engineering-handoff.md:20,75,111`, I-15/I-17, WP2.8, `GOAL.md:11`) → GCS stands. **GCS confirmed by PM 2026-10-02 ("we are good on GCS").** ⚠ **Pre-provision follow-up:** concrete project + bucket name TBD ("name it later"); I-15 requires the destination to exist and be access-tested before launch. Note: reader group is broader than the docs' "designated engineering/security readers." |
| 7   | Destination team = **Foundations** (`id 18ec7d7b-6e5c-4670-bfea-6087b092d784`), for now. Mapping (built from Foundations' live Linear states): **fix-claim signal** = ticket reaches completed state `Done`; **mapped open state** (reopen target when a `Done` exploit reproduces) = `Todo`; **ambiguous reconciliation** → `Triage`. | **Foundations team** (team choice); mapping researched from live Foundations states under PM "research as needed" delegation | 2026-10-02 | Foundations states: Triage, Idea, Backlog, Todo, In Progress, In Review, Done, Canceled, Duplicate. Mapping aligns with the five reconciliation outcomes / "ambiguous → triage" (WP1.2) and claimed-fixed-but-reproduces reopen (`exploit-findings.md:34`). **Mapping confirmed by PM 2026-10-02.**                                                                                                                                                                                                         |
| 8   | Edge/Cloudflare scoped-policy approval owned by **Engineering** (conditional — only if the I-23 reachability probe shows the runner path is blocked).                                                                                                                                                                                  | **Engineering** (specific environment owner named at trigger time)                                                           | 2026-10-02 | Conditional item; scope limited to a narrow party-only policy — no whole-zone or production change (`attack-paths.md` scope rules). ⚠ Specific person to be named if/when I-23 triggers.                                                                                                                                                                                                                                                                                                                    |
| 9   | **Defer WP2.10** (concurrency coordination mechanism + test) for v1, relying on the single weekly run / one active attempt assumption.                                                                                                                                                                                                 | **Foundations team**                                                                                                         | 2026-10-02 | Residual risk accepted for v1: a manual run fired during the active Monday 09:00 run, or a retry after a lost Linear ack, could duplicate a ticket or double-count. Operational guardrail: do not fire a manual run while the scheduled run is active (ties to Item 10 coverage). Revisit if run cadence/parallelism increases.                                                                                                                                                                             |
| 10  | Operator who observes/can stop each Mon 09:00 PT + manual run = **the release authority for now**, transitioning to the **Foundations team**. **Skip policy:** runs are **attended-only** — when no operator is available, the run **does not proceed unattended** (skip/defer until covered).                                         | **Release authority** now → **Foundations team**                                                                             | 2026-10-02 | Operator coverage is distinct from authentication (`attack-sessions.md:7`). Fail-closed: no coverage → no unattended run.                                                                                                                                                                                                                                                                                                                                                                                   |
| 11  | **Slack delivery stays deferred for v1** — notification eligibility is computed and recorded in the run summary, but nothing is sent.                                                                                                                                                                                                  | **Foundations team**                                                                                                         | 2026-10-02 | Confirms the non-goal in `GOAL.md` and `engineering-handoff.md:20` ("Slack delivery is deferred"); eligibility-recorded-no-transport behavior unchanged.                                                                                                                                                                                                                                                                                                                                                    |

## Next action

1. ~~Round-3 verification review of the WP1 rework~~ done. Current work is PR #55 review
   handling; see the CHECKPOINT section below.
2. Stage 4 conformance packaging.
3. **PM gate is cleared** (table above) — sequence the E2 / Release packets; create Linear
   tickets per packet in the **Foundations** team (item 7).
4. Before the **first live run** (not before build): mint the concrete test service account
   (item 3) and provision + access-test the GCS project/bucket (item 6, Infra team).
5. Carry forward the recorded reservations (items 2, 4, 8, 9, 10).

---

## CHECKPOINT — session handoff (2026-10-03)

**Where things are:** Offline planner (WP1/E1) is built, converged, and under review as
draft PR **foxglove/actions#55** (branch `claude/exciting-cerf-vkmwu5` → `main`). Three
Claude-review batches + three isolated self-reviews done in session 1 (verdict **SHIP** on
c6872b4). Session 2 (this session owns the PR, per the user) ran self-review rounds 3–5 on the
c6872b4 delta; see `EVIDENCE.md` for verdicts. PM gate is CLEARED (table above).

**Gates (all green) — run these to confirm on resume:**

- `node attack-runner/planner/run-fixtures.mjs` → 61 passed, 0 failed + 14 structural-reject
- `node attack-runner/planner/check-fixtures.mjs` → PASS
- `node attack-runner/planner/mutation-test.mjs` → 128 mutants, 125 killed, 3 equivalent, 0 noapply
- ajv: inputs (only the 5 `INPUT_SCHEMA_INVALID`-marked fail, by design), expected, actual all valid.
- Fixtures e1-01..52 came from a session-local generator that no longer exists; e1-53..56
  were authored by a small script deriving from e1-01/e1-50. New fixtures: author them the
  same way (derive from an existing fixture, deep-equal the authored expected), then prettier.

**Remaining work, in priority order** (session 2 progress inline):

1. ~~Reply to + resolve the PR #55 review threads~~ **DONE** (session 2): all fixed threads
   replied and resolved. Left OPEN on purpose: the `.feature-workspace` thread (author to
   confirm) and the T3 `counts` invariant thread until its fix is pushed. Note: session 1 was
   still subscribed and also replied; several threads carry duplicate replies.
2. ~~M2 coverage~~ **DONE** (bb8aaa9): fixtures e1-53..56 + mutants `unc-env-ignored`,
   `unc-alias-clause-off`, `unc-empty-alias-comparable`, `unc-blank-alias-comparable`,
   `related-state-skip-restored`.
3. ~~Minor~~ **DONE**: L2 (blank aliases ignored, e1-56); L5 (5 structural-reject cases +
   `obs/existing/processed-array-off`, `issueid-off`, `obsid-off` mutants); L1 accepted and
   documented in README ("Triage wins over replay").
4. **Flag to user:** `product-docs/attack-sessions.md` on `main` still names individuals
   (source contract, outside this PR). Ask whether to open a follow-up PR to scrub it there.
5. Reply on the T3 thread (comment 4171668354) with the fix commit, then resolve it.
6. **R3-F4** open product question (above) needs the acceptance owner.
7. When PR is green + approved: it's a DRAFT — mark ready-for-review when the user says.

**Review logs:** `review-wp1.md`, `review-wp1-round2.md`, `review-wp1-round3.md`,
`self-review-pr55.md`, `self-review-pr55-r2.md`, `self-review-pr55-r3.md`,
`self-review-pr55-r4.md`, `self-review-pr55-r5.md`. **PR:** `pr.json`.
