# GOAL — Attack Runner

Feature: Aegis → Attack Runner. Feature-pipeline durable state (Claude adapter).
Base repo: `foxglove/actions`. Working branch: `claude/exciting-cerf-vkmwu5`.

## Objective

Ship a weekly/manual GitHub Actions service that runs an authenticated security
assessment of the `*.foxglove.party` environment from a maintained non-admin
session, reconciles demonstrated exploits into one Linear ticket per exploit, and
writes redacted evidence to a private GCS bucket.

## Non-goals (first release)

Production assessment, deliberate anonymous phases, additional attack paths beyond
Authenticated Access Chains, CI scanner gates, automated CI-gap ticketing, formal
deployed-version tracking, Slack delivery (eligibility recorded, no transport).

## Allowed actions

- Implementation changes land only in `foxglove/actions`.
- Other repos (issuer function, mailbox, app mode-signal, Cloudflare/edge policy,
  GCS/infra, Linear config) are tracked external dependencies — never silent scope
  expansion.
- Planning and the offline planner (E1) perform no live minting, assessment, or
  external delivery.

## Base / dependency revisions

- Product contract: product docs + `docs/aegis/review/{acceptance,engineering-handoff}.md`
  (accepted via `foxglove/actions` PR #48). Pin exact base SHA at build start.
- Harness: Strix OSS — release/commit to be pinned (WP0.2 / I-12).
- Model: Sonnet-4-8 — provider identifier to be resolved (WP0.2 / I-12).

## Acceptance criteria

The `E1-*` and `I-*` criteria in `docs/aegis/review/acceptance.md`. Each work packet
in `TRACEABILITY.md` names the criteria that judge it.

## Cost / latency bounds (runtime product, not this planning work)

Per run: $100 budget, 75-minute total job limit (preflight + run duration + reporting
reserve), 60-minute default run duration. Config validation rejects a profile whose
duration + reserve + preflight exceeds the job limit.

## Stop conditions

- A work packet does not enter build while a product decision it needs is unresolved
  (semantic-model gate; see `STATUS.md` open items).
- Live release is blocked until the operational-qualification evidence (`I-*`) is
  recorded and the named owners accept.

## Approval status

Objective + Stage 2 breakdown: approved by engineering lead (this session).
Release authority / product decisions: the release authority, moving to the Foundations team over time (see attack-sessions.md).
