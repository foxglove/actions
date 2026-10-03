# Attack Runner — product decisions needed from PM

Prepared by the engineering lead from the product docs + engineering handoff. These were the
open product decisions that gated the Stage-1 → Stage-2 handoff ("no unresolved decision
delegated to code"). The offline planner (WP0.1 / E1) is **not** blocked by any of these and
is already in progress; the items below gate the authentication, delivery, infra, and release
packets (E2 / Release).

When written, items 1–2 were flagged _proposed/pending_ in the docs. Ordered by blocking impact. All items are now answered; see **Status** at the end.

## Blocking

1. **Issuer-service ownership — needs acceptance.**
   `attack-sessions.md` lists the issuer owners as _proposed_
   (`@foxglove/data-curation-search`) and notes "no separate
   on-call rotation yet." Which team accepts operational ownership of the new company issuer
   function + test identity + mailbox access, and who signs off (person + date)?

   **Answer (2026-10-02):** `@foxglove/data-curation-search` owns the issuer function and mailbox access; the release authority accepted them; no on-call rotation in v1. The Foundations team owns the test identity (decided 2026-10-03). **Recorded in:** [Attack sessions — product decisions](../../product-docs/attack-sessions.md#product-decisions).

2. **Out-of-repo dependencies — owner + timeline.**
   The company **issuer function** and the dedicated **mailbox provisioning** live in the
   app/auth repos as separate dependencies of the `foxglove/actions` change. Which repo owns
   each, who builds them, and by when? (The actions service cannot ship without them.)

   **Answer:** the app repository owns the issuer function and mailbox provisioning (app/auth code owners). **Recorded in:** [Attack sessions — issuance authority](../../product-docs/attack-sessions.md#issuance-authority-stays-outside-attack-runner). Not recorded (rollout, for Linear): the build owner and timeline, and interim manual link minting.

3. **Authorized target set + test identity.**
   The concrete authorized `*.foxglove.party` hosts, the test account(s)/data, and any
   maintenance restrictions are not enumerated. Please supply the explicit list (the wildcard
   is a maximum boundary, not permission to assess every host).

   **Answer:** every host under `*.foxglove.party`; production never; the Foundations team owns the test service account; no maintenance blackout window. **Recorded in:** [Attack paths](../../product-docs/attack-paths.md#authenticated-access-chains-follows-connected-authorization-failures), [Attack runner — first release](../../product-docs/attack-runner.md#the-first-release-assesses-party-with-a-maintained-session), [engineering handoff — dependencies](../../docs/aegis/review/engineering-handoff.md#engineering-discovery-and-release-dependencies). Still open before the first live run: the concrete service account and its data.

## Needed before the dependent packet

4. **Mode-oracle fallback.**
   If the feasibility spike shows the post-redemption **ordinary vs. impersonation** mode
   cannot be reliably distinguished from app-derived evidence, an app-owned session-bound
   signal becomes a release dependency (app-repo work). Do you pre-authorize that contingency,
   and who owns it?

   **Answer:** the starting session is ordinary by default; an app-owned session-bound mode signal is not pre-authorized. **Recorded in:** [Attack sessions — authentication mode](../../product-docs/attack-sessions.md#authentication-mode-must-match-the-intended-coverage).

5. **DKIM trusted configuration.**
   App/auth owners must confirm, against a genuine message: the signing `d=` domain, the
   approved SendGrid `s=` selector(s), the application `From` sender, and the company mailbox
   `To` address. Who confirms these, and who owns the `DKIM_SELECTOR_UNAPPROVED` investigation
   path (a valid signature with an unapproved selector)?

   **Answer:** the app/auth code owners confirm the four values against a genuine message and own the `DKIM_SELECTOR_UNAPPROVED` investigation. **Recorded in:** [Attack sessions — company mailbox](../../product-docs/attack-sessions.md#the-link-is-delivered-to-a-company-mailbox), [engineering handoff](../../docs/aegis/review/engineering-handoff.md#authentication-issuer-and-mailbox-delivery).

6. **Private evidence storage.**
   Which GCS project and bucket, and which **authorized reader group** (engineering/security)?
   Who provisions it through the infra process?

   **Answer:** GCS stands; readers are all of Engineering and the CEO; the Infra team provisions it. **Recorded in:** [Attack runner — private storage](../../product-docs/attack-runner.md#evidence-is-retained-in-private-storage). Still open before the first live run: the project and bucket names.

7. **Linear destination + status mapping.**
   Which Linear team receives exploit tickets, and what is the exact mapping for status, the
   fix-claim signal, and the **"mapped open state"** used when reopening a contradicted ticket?

   **Answer:** the Linear Foundations team; `Done` holds the fix claim; `Todo` is the reopen state; an ambiguous reconciliation creates no ticket (the run summary is its triage record). **Recorded in:** [Exploit findings — ticket lifecycle](../../product-docs/exploit-findings.md#ticket-lifecycle).

8. **Edge / Cloudflare policy owner.**
   If the reachability probe (I-23) shows the runner path is blocked, who is the environment
   owner that approves a narrowly-scoped party-only policy? (No whole-zone or production change.)

   **Answer:** if the I-23 probe shows the runner path is blocked, Engineering approves a scoped party-only policy and the party environment owner configures it. **Recorded in:** [Attack runner — edge controls](../../product-docs/attack-runner.md#edge-controls-must-not-hide-missing-coverage).

## Confirmations

9. **Concurrency depth for v1.**
   v1 is described as one weekly run with one active attempt, yet the handoff still asks for a
   concurrency coordination mechanism + test (WP2.10). Is that required for the first release,
   or deferred under the single-run assumption?

   **Answer:** deferred for v1; the operator does not dispatch a manual run during an active run. **Recorded in:** [engineering handoff — concurrent delivery](../../docs/aegis/review/engineering-handoff.md#concurrent-delivery), [Attack runner — runs](../../product-docs/attack-runner.md#runs-are-weekly-and-manually-invocable).

10. **Operator coverage model.**
    Who observes/stops each Monday 09:00 and each manual run, given there is no on-call
    rotation yet? What is the skip policy when coverage is unavailable?

    **Answer:** the Foundations team is the operator; runs are attended only, and a run without coverage is skipped. **Recorded in:** [Attack runner — runs](../../product-docs/attack-runner.md#runs-are-weekly-and-manually-invocable).

11. **Slack deferral.**
    Confirm Slack delivery stays deferred for v1 — notification _eligibility_ is computed and
    recorded in the run summary, but nothing is sent.

    **Answer:** confirmed. **Recorded in:** [Attack runner — findings](../../product-docs/attack-runner.md#findings-cross-repository-boundaries), [Exploit findings — summary output](../../product-docs/exploit-findings.md#each-run-produces-a-summary-output).

---

**Status:** every item is answered (2026-10-02, with follow-ups on 2026-10-03). The decisions are
recorded in the product and Aegis docs by foxglove/actions#57; this file is the index from each
question to its record, for later implementation packets.

Context for whoever picks this up: full breakdown and traceability in
`.feature-workspace/attack-runner/` (this repo, branch `claude/exciting-cerf-vkmwu5`); product
contract in `product-docs/` and `docs/aegis/review/`.
