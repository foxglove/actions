# Attack Runner — product decisions needed from PM

Prepared by the engineering lead from the product docs + engineering handoff. These are the
open product decisions that gate the Stage-1 → Stage-2 handoff ("no unresolved decision
delegated to code"). The offline planner (WP0.1 / E1) is **not** blocked by any of these and
is already in progress; the items below gate the authentication, delivery, infra, and release
packets (E2 / Release).

Items 1–2 are flagged _proposed/pending_ in the docs themselves. Ordered by blocking impact.

## Blocking

1. **Issuer-service ownership — needs acceptance.**
   `attack-sessions.md` lists the issuer owners as _proposed_
   (`@foxglove/data-curation-search`, `@wimagguc`, `@dante-foxglove`) and notes "no separate
   on-call rotation yet." Which team accepts operational ownership of the new company issuer
   function + test identity + mailbox access, and who signs off (person + date)?

2. **Out-of-repo dependencies — owner + timeline.**
   The company **issuer function** and the dedicated **mailbox provisioning** live in the
   app/auth repos as separate dependencies of the `foxglove/actions` change. Which repo owns
   each, who builds them, and by when? (The actions service cannot ship without them.)

3. **Authorized target set + test identity.**
   The concrete authorized `*.foxglove.party` hosts, the test account(s)/data, and any
   maintenance restrictions are not enumerated. Please supply the explicit list (the wildcard
   is a maximum boundary, not permission to assess every host).

## Needed before the dependent packet

4. **Mode-oracle fallback.**
   If the feasibility spike shows the post-redemption **ordinary vs. impersonation** mode
   cannot be reliably distinguished from app-derived evidence, an app-owned session-bound
   signal becomes a release dependency (app-repo work). Do you pre-authorize that contingency,
   and who owns it?

5. **DKIM trusted configuration.**
   App/auth owners must confirm, against a genuine message: the signing `d=` domain, the
   approved SendGrid `s=` selector(s), the application `From` sender, and the company mailbox
   `To` address. Who confirms these, and who owns the `DKIM_SELECTOR_UNAPPROVED` investigation
   path (a valid signature with an unapproved selector)?

6. **Private evidence storage.**
   Which GCS project and bucket, and which **authorized reader group** (engineering/security)?
   Who provisions it through the infra process?

7. **Linear destination + status mapping.**
   Which Linear team receives exploit tickets, and what is the exact mapping for status, the
   fix-claim signal, and the **"mapped open state"** used when reopening a contradicted ticket?

8. **Edge / Cloudflare policy owner.**
   If the reachability probe (I-23) shows the runner path is blocked, who is the environment
   owner that approves a narrowly-scoped party-only policy? (No whole-zone or production change.)

## Confirmations

9. **Concurrency depth for v1.**
   v1 is described as one weekly run with one active attempt, yet the handoff still asks for a
   concurrency coordination mechanism + test (WP2.10). Is that required for the first release,
   or deferred under the single-run assumption?

10. **Operator coverage model.**
    Who observes/stops each Monday 09:00 and each manual run, given there is no on-call
    rotation yet? What is the skip policy when coverage is unavailable?

11. **Slack deferral.**
    Confirm Slack delivery stays deferred for v1 — notification _eligibility_ is computed and
    recorded in the run summary, but nothing is sent.

---

Context for whoever picks this up: full breakdown and traceability in
`.feature-workspace/attack-runner/` (this repo, branch `claude/exciting-cerf-vkmwu5`); product
contract in `product-docs/` and `docs/aegis/review/`.
