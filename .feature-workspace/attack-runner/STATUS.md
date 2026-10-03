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
  - round-trip + mutation self-test + structural-reject), 63 fixtures, **64 passed / 0 failed**
    - 15 structural-reject; `check-fixtures.mjs` PASS; `mutation-test.mjs` (committed convergence
      gate) **135 mutants, 132 killed, 0 unexpected survivors** (3 documented equivalents);
      inputs/expected/actual schema-valid via ajv (negative-input fixtures marked
      `INPUT_SCHEMA_INVALID`).
- **Reviews** — rounds 1, 2, 3 + a PR #55 review round and an isolated self-review complete;
  findings fixed or routed (see `EVIDENCE.md`). Round 2
  fixed a weak-oracle workflow failure; round 3 drove mutation survivors 46 → 4 (equivalents).

## Open product question (R3-M3, for the acceptance owner)

Cross-run fix-claim **notification-episode** dedup (acceptance E1-19 / exploit-findings:54):
the planner computes eligibility per run correctly, but "notify once per episode across runs"
needs either an acceptance.md amendment (declare it Engineering 2's durable-state job) or a new
planner input field carrying "this fix-claim contradiction was already notified". Needs the
acceptance owner's decision; not unilaterally closed.

## Decision R3-F4 — legacy tickets are ignored (2026-10-03)

**Question:** must a same-environment ticket in any state with no normalizable chain and no
non-blank alias block creation of every new ticket in its environment?
**Answer (the user, as the product decision authority, 2026-10-03):** no. **Ignore legacy
tickets.** A legacy ticket (its chain does not normalize) matches only through a
fingerprint alias, takes no part in overlap triage, and never blocks a `new` ticket,
whatever its state. Accepted risk: a
finding already tracked only on such a ticket can get a duplicate ticket until the legacy
ticket is backfilled with a chain or an alias.
**Implemented (session 2):** fixtures e1-50, e1-55 and e1-56 now expect `new`; the failure
was observed before the code change. The triage branch is removed; the mutant
`legacy-ticket-triages` pins the rule; fixture e1-57 and the mutant
`legacy-ticket-state-blocks` pin it for resolved and unknown tickets. The five mutants of the removed branch are retired.
The structural case `blank-runid` now pins whitespace rejection (it kills `nonempty-no-trim`).

## Decisions recorded in the product docs (2026-10-03)

The PM gate answers (table below) move into `product-docs/` and `docs/aegis/` in a separate
docs PR, foxglove/actions#57, stacked on foxglove/actions#56. `pm-clarifications.md` stays as the index from each
question to the doc section that records its answer. While writing them, the user decided:

- **Item 7 — ambiguous reconciliation:** creates no ticket; the run summary is its triage
  record. There is no Linear `Triage` mapping (the `Done` and `Todo` mappings stand).
- **Items 1 and 3 — test identity:** the Foundations team owns the test service account
  entirely (creation, provisioning, rotation, revocation). The issuer owner keeps the issuer
  function, identity-to-profile mapping, deployment approval, and mailbox access.
- **Reasons:** every `*.foxglove.party` host is in scope because Attack Runner is a
  penetration test of the whole party environment and Engineering fixes what it finds; all
  of Engineering and the CEO read evidence because security is every engineer's
  responsibility.
- **Item 10 — operator:** the Foundations team is now the release authority (foxglove/actions#56),
  so the operator is the Foundations team; the table's "release authority for now" transition
  is complete.
- Kept out of the docs: the interim manual minting and the "~1 week" timeline (item 2;
  rollout, for Linear) and the two pre-first-run items (items 3 and 6; listed as dependencies
  in the engineering handoff).

## Decision — report ignored legacy tickets (2026-10-03)

**Question (external review of 7426b97):** the output gives no signal when a legacy ticket is
ignored, so triage cannot see when the accepted duplicate-ticket risk applies.
**Answer (the user, 2026-10-03):** add it. **Rule:** `runSummary.ignoredLegacyIssues` is
always present. It lists, in input order, the `issueId` of every existing ticket that is in
the run's environment, whose chain does not normalize, and whose `issueId` no decision
targets and no `notObserved` entry references. Decisions are unchanged.
**Follow-up decision (the user, 2026-10-03, after external review of aaaf8b0):** the list is a
**standing backfill reminder**. It does not depend on whether the run creates a ticket, and
it is not limited to runs with a `create-ticket`. A ticket is listed on each run until its
chain normalizes, except on a run where a decision targets it or a non-observation
references it. An alias alone does not end the reminder. Fixtures e1-58 and e1-59 pin runs
with no `create-ticket` and a non-empty list.
**Implemented (session 2):** schema field (required); every expected.json gained the
field from an independent oracle script; new fixture e1-58 (alias-matched, retest-referenced
and idle legacy tickets; only the idle one is listed). The failure was observed first
(62 of 63 failed). Mutants: `ignored-legacy-env-off`, `ignored-legacy-includes-comparable`,
`ignored-legacy-decision-ref-off`, `ignored-legacy-notobserved-ref-off`,
`ignored-legacy-ref-check-off`. The `validateInput` comment is fixed. After self-review
round 9: fixture e1-59 (claimed-fixed and replayed alias matches, ambiguous alias match,
exploitId-only retest, incomplete tuple, environment variant, input order) and mutants
`ignored-legacy-sorted`, `ignored-legacy-raw-env`, `ignored-legacy-written-decisions-only`,
`ignored-legacy-rediscovered-only`. After round 10: e1-59 adds an alias-matched
unknown-state legacy ticket (an `unresolved` decision targets it; not listed) and the mutant
`ignored-legacy-skips-unresolved`.

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
| 1   | Accept proposed issuer owners as the team that owns the company issuer function + test identity + mailbox access.                                                                                                                                                                                                                      | `@foxglove/data-curation-search`; sign-off **Foundations team**                                                              | 2026-10-02 | No separate on-call rotation yet — **accepted as-is for v1**. **Superseded 2026-10-03:** the Foundations team, not the issuer owners, owns the test identity (see above).                                                                                                                                                                                                                                                                                                                                   |
| 2   | Issuer function + mailbox provisioning owned by the **App repo**. Build unassigned ("any available engineer"); land within ~1 week (target 2026-10-09).                                                                                                                                                                                | App repo (app/auth code owners); interim magic-link minting by **Foundations team**                                          | 2026-10-02 | Docs (`attack-sessions.md` 18–19/149–154, `engineering-handoff.md`) attribute these to "app/auth code owners" — consistent. If a distinct auth repo exists, app-vs-auth split of each piece is a sub-point for the owning team. Interim manual minting (by the release authority) matches `attack-sessions.md:150`.                                                                                                                                                                                         |
| 3   | Authorized target set = **all hosts** under `*.foxglove.party` (full wildcard). Test identity = a **service account minted by the Foundations team**. Run window = **Mondays 09:00 PT** + manual runs.                                                                                                                                 | Scope/authorization: **Foundations team**; test account minting: **Foundations team**                                        | 2026-10-02 | Full wildcard authorized — explicitly overrides the drafted "maximum boundary, not every host" caution; production stays out of scope (`party ≠ production` invariant). ⚠ **Pre-first-run follow-up:** concrete service-account identity/data not yet named. No separate maintenance blackout window provided.                                                                                                                                                                                              |
| 4   | Starting session is **ordinary by default**. **No** app-owned session-bound mode signal is pre-authorized as a v1 release dependency.                                                                                                                                                                                                  | **Foundations team**                                                                                                         | 2026-10-02 | Treated as low-risk: the runner starts ordinary and the demonstrated ordinary→admin escalation is itself the exploit (`exploit-findings.md:5,79`); pause/stop on reaching admin aligns with "minimum evidence necessary; stop before irreversible damage" (`instructions.md:51`). Reservation: if the feasibility spike shows ordinary vs. impersonation genuinely cannot be distinguished from app evidence, reopen with PM — not auto-triggered.                                                          |
| 5   | **App/auth code owners** confirm the 4 DKIM trusted-config values (`d=` signing domain, `s=` selector(s), `From` sender, `To` mailbox) against a genuine message, and own the `DKIM_SELECTOR_UNAPPROVED` investigation path.                                                                                                           | App/auth code owners (Item-1 owners)                                                                                         | 2026-10-02 | They own SendGrid domain authentication, so they read the real values off a genuine magic-link email and confirm selector legitimacy before adding one (`attack-sessions.md:51,150`, `engineering-handoff.md:94`). `To` mailbox is the one the Foundations team provisions (Item 2).                                                                                                                                                                                                                        |
| 6   | **GCS confirmed** (accepted contract stands — no re-spec). Authorized reader group = **all of Engineering + CEO**. Provisioned by the **Infra team** through the infra process.                                                                                                                                                        | Reader-group/storage decision: **Foundations team**; provisioning: **Infra team**                                            | 2026-10-02 | PM's "decided against GCS?" reconciled against the accepted contract (`attack-runner.md:46,48,50,156`, `engineering-handoff.md:20,75,111`, I-15/I-17, WP2.8, `GOAL.md:11`) → GCS stands. **GCS confirmed by PM 2026-10-02 ("we are good on GCS").** ⚠ **Pre-provision follow-up:** concrete project + bucket name TBD ("name it later"); I-15 requires the destination to exist and be access-tested before launch. Note: reader group is broader than the docs' "designated engineering/security readers." |
| 7   | Destination team = **Foundations** (`id 18ec7d7b-6e5c-4670-bfea-6087b092d784`), for now. Mapping (built from Foundations' live Linear states): **fix-claim signal** = ticket reaches completed state `Done`; **mapped open state** (reopen target when a `Done` exploit reproduces) = `Todo`; **ambiguous reconciliation** → `Triage`. | **Foundations team** (team choice); mapping researched from live Foundations states under PM "research as needed" delegation | 2026-10-02 | Foundations states: Triage, Idea, Backlog, Todo, In Progress, In Review, Done, Canceled, Duplicate. Mapping aligns with the five reconciliation outcomes / "ambiguous → triage" (WP1.2) and claimed-fixed-but-reproduces reopen (`exploit-findings.md:34`). **Mapping confirmed by PM 2026-10-02.** **Superseded 2026-10-03:** an ambiguous reconciliation creates no ticket; there is no `Triage` mapping (see above).                                                                                     |
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
PR **foxglove/actions#55** (branch `claude/exciting-cerf-vkmwu5` → `main`). Three
Claude-review batches + three isolated self-reviews done in session 1 (verdict **SHIP** on
c6872b4). Session 2 (this session owns the PR, per the user) ran self-review rounds 3–14 on the
commits after c6872b4; see `EVIDENCE.md` for verdicts. PM gate is CLEARED (table above).

**Gates (all green) — run these to confirm on resume:**

- `node attack-runner/planner/run-fixtures.mjs` → 64 passed, 0 failed + 15 structural-reject
- `node attack-runner/planner/check-fixtures.mjs` → PASS
- `node attack-runner/planner/mutation-test.mjs` → 135 mutants, 132 killed, 3 equivalent, 0 noapply
- ajv: inputs (only the 5 `INPUT_SCHEMA_INVALID`-marked fail, by design), expected, actual all valid.
- Fixtures e1-01..52 came from a session-local generator that no longer exists; e1-53..59
  were authored by small scripts that derive them from existing fixtures (e1-01, e1-03,
  e1-04, e1-08, e1-22, e1-50, e1-51, e1-55). The `runSummary.ignoredLegacyIssues` values in
  every expected.json came from an independent oracle script. New fixtures: author them the
  same way (derive from an existing fixture, deep-equal the authored expected), then prettier.

**Remaining work, in priority order** (session 2 progress inline):

1. ~~Reply to + resolve the PR #55 review threads~~ **DONE** (session 2): all fixed threads
   replied and resolved. Left OPEN on purpose: the `.feature-workspace` thread (author to
   confirm) and the T3 `counts` invariant thread until its fix is pushed. Note: session 1 was
   still subscribed and also replied; several threads carry duplicate replies.
2. ~~M2 coverage~~ **DONE** (bb8aaa9): fixtures e1-53..56 + mutants `unc-env-ignored`,
   `unc-alias-clause-off`, `unc-empty-alias-comparable`, `unc-blank-alias-comparable`,
   `related-state-skip-restored`. The four `unc-*` mutants (and `uncomparable-off`) were
   later **retired** with the triage branch they mutated (decision R3-F4).
3. ~~Minor~~ **DONE**: L2 (blank aliases ignored, e1-56); L5 (5 structural-reject cases +
   `obs/existing/processed-array-off`, `issueid-off`, `obsid-off` mutants); L1 accepted and
   documented in README ("Triage wins over replay").
4. **Names on `main`:** the user approved a follow-up PR that replaces the named individuals
   in `product-docs/attack-sessions.md` with teams (branch `claude/confident-dirac-zal2xi`).
5. ~~T3 thread~~ done (7503a34, replied and resolved). ~~`.feature-workspace` thread~~ the
   user confirmed the directory stays; replied and resolved.
6. ~~R3-F4~~ decided (ignore legacy tickets) and implemented; see the section above.
7. ~~Mark PR #55 ready for review~~ **DONE** 2026-10-03, with CI green on 2029ecf. PR #55,
   #56 and #57 wait on human review; #57 merges after #56.

**Review logs:** the review records (`review-wp1*.md`, `self-review-pr55*.md`) were removed
from the workspace on 2026-10-03 at the user's request; `EVIDENCE.md` keeps each round's
verdict and findings for failing rounds. The records never reach `main`, which
squash-merges; they remain at commit 2029ecf on the PR #55 head (`git fetch origin
refs/pull/55/head`, then `git show 2029ecf:.feature-workspace/attack-runner/<file>`). **PR:** `pr.json`.
