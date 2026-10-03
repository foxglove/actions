# STATUS — Attack Runner

**Stage:** 2 (semantic model + plan) complete; entering Stage 3 build at WP0.1.
**Latest revision:** see branch `claude/exciting-cerf-vkmwu5` (this session's commit).
**Approved plan:** work-packet breakdown accepted by engineering lead.

## In progress

- **WP0.1** — offline planner I/O schema + fixtures. Artifacts under
  `attack-runner/planner/`. Status: initial contract + fixtures landed; the executable
  planner (`plan()`) is WP1.\*, not yet implemented.

## Open failures / blockers — Stage-1→2 gate (PM must resolve)

No build packet that depends on one of these starts until it is resolved. WP0.1 and the
E1 packets (WP1.\*) do **not** depend on any of these and may proceed.

1. Issuer-service ownership acceptance (proposed owners, no acceptance/rotation). BLOCKING.
2. Out-of-repo deps: issuer function + mailbox provisioning (owner/repo/timeline). BLOCKING.
3. Authorized target set + test identity (concrete party hosts/accounts). BLOCKING to run.
4. Mode-oracle fallback: app-owned session signal if ordinary≠impersonation undecidable.
5. DKIM trusted config (signing domain, selectors, sender, mailbox) + selector-investigation owner.
6. GCS project/bucket/authorized reader group.
7. Linear destination team + status/fix-claim/reopen mapping ("mapped open state").
8. Edge/Cloudflare scoped-policy owner (conditional on reachability probe I-23).
9. Concurrency depth required for v1 (WP2.10 now or deferred).
10. Operator coverage model for Mon 09:00 / manual runs.
11. Slack deferral confirmation (eligibility recorded, no transport).

Full PM message: `pm-clarifications.md`.

## Next action

1. Complete WP0.1 review (schema + fixtures exercise every E1 branch).
2. On PM gate resolution for the blocking items, sequence WP1.\* (E1 planner) build,
   test-first, one slice per context.
3. Create Linear tickets per packet once the destination team (item 7) is known.
