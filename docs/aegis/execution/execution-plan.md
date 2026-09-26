# Attack Runner execution plan

Planning baseline: the read-only export of foxglove/actions PR #48 reviewed head `9f74dba474d684c131c53e1ade024f25eb664863` (merged as `65cd875e6a4feaa1b5ab29f008ea0b73b43b4dce`). Recheck current `main` and applicable tracked instructions before coding. This plan implements the seven canonical product/review files named in [README.md](README.md); it records no live validation. Scope code to foxglove/actions. Other-repository or infrastructure changes are release dependencies with separate owners.

## Architectural decision

Use a small TypeScript/Node CLI in this repository, with pure reconciliation functions, narrow adapters, a GitHub Actions entry point, and pinned Strix OSS as the **assessment engine**. A narrow Python bridge in actions uses Strix's pinned `run_strix_scan` API to keep its sandbox/Caido session available until trusted evidence export; direct headless CLI cleanup would destroy that session first. Strix owns agent/tool execution and emits native `vulnerabilities.json`, `coverage.json`, `run.json` and local event traces; our code owns product-specific identity, authenticated-evidence validation, Linear lifecycle, private evidence and delivery. Do not rebuild Strix's browser, scanner, finding writer or internal dedupe. The snapshot has Yarn 4.12 and Prettier but no prescribed runtime; add a TS build and only selected adapter dependencies. Pin Node/Python/Strix and use Node's built-in test runner for the planner. Keep offline fixtures runnable without network or credentials. `feasibility.md` records source-level evidence and remaining release gates.

| Option                                         | Benefit                                                                                                            | Cost/decision                                                                                                                    |
| ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------- |
| Node/TypeScript CLI in actions **(recommend)** | Fits existing workflow/JS patterns; one typed contract from planner through runner; simple local/offline execution | Requires adding TS build and narrowly chosen SDKs after discovery                                                                |
| Python orchestration CLI in actions            | Could share language with the required Strix bridge                                                                | Replaces the repository's JS workflow pattern for planner/delivery without removing the bridge or external gates                 |
| Existing Temporal + dedicated worker           | Reuses Foxglove's configured platform pattern for durable activities                                               | Needs a new isolated worker/identity and cannot make Linear writes atomic; deployed availability for this workload is unverified |
| Generic new orchestrator                       | No advantage shown over Actions or existing Temporal                                                               | Adds another deployment; defer                                                                                                   |

Keep a _pure offline plan_ distinct from delivery. Equal normalized inputs and journal snapshots yield equal proposals. For this bounded release, use one Actions concurrency group for all party Attack Runner dispatches and a **separate permanent private GCS corpus journal object**, updated with generation preconditions (`ifGenerationMatch=0` on creation, observed generation on replacement). The journal contains stable identities, aliases, per-run/per-claim action states and pending write markers; 30-day evidence objects never serve as the ledger. Immediately before first create, read the entire corpus journal and relevant Linear candidates, match causally, then reserve a pending stable identity/create marker with CAS. A pending/uncertain create does **not** auto-expire or transfer to another writer; block all new first-creates while one is unresolved, since a paraphrase may match it. After a crash, reconcile against Linear by marker and actual state before retrying a proven absent action; if readback is inconclusive, retain `uncertain` and require an operator resolution before another create. No blind replay or stale-owner lease steal. Actions concurrency is routine serialization, GCS CAS detects journal races, and neither alone fences Linear; the durable pending state and conservative stop rule handle that gap. This trades automated liveness for safety, as the approved contract permits bounded manual recovery. If this journal or readback is unavailable, live delivery is blocked. Temporal already exists at Foxglove, but a dedicated attack worker adds a deployment and does not remove the external-write uncertainty; see `orchestration.md`.

## Early feasibility, before integration investment

Time-box these read-only investigations and controlled, separately authorized tests early. Record tested revision, actor, environment, exact command/API request shape, redacted result, and whether evidence is fixture or live. A failed gate blocks live release; it does not prompt a silent substitute.

1. **Auth and session:** At inspected app commit `1d3459d…`, `/auth/magic-link` emails the token and exposes a Redis lookup ID only when `NODE_ENV=test`; its token is 15-minute/single-use. Thus the concrete live dependency is an approved unattended mailbox retrieval path or an app-owned secure retrieval interface, plus a supported cookie/session maintenance operation. Neither is established by source. Validate same cookie jar, server cookie updates, expected non-admin developer identity/party context, maintenance every 300 seconds and before high-impact chains, and authenticated operation beyond 15 minutes through the configured duration. Never use the test-only route as party capability.
2. **Harness/model/limits:** Pin Strix source candidate `ae38fe70cd0260555a2ac745ca585e16bf3d6c74` and immutable sandbox image digest. Source confirms `run_strix_scan(cleanup_on_exit=False)`, reusable sandbox/Caido bundle, native result files and a Docker-network selector; the Python bridge protocol is specified below. Source does **not** prove browser jar continuity, maintenance, egress containment or provider availability. Strix's budget hook checks cost after responses, so set its $100 stop but require a provider/gateway hard **per-run credential** cap at $100 before live calls; if that cap cannot be provisioned, launch blocks. Keep the 60-minute external deadline and reporting reserve. Resolve Sonnet-4-8 to an actual permitted provider ID; strongest permitted model remains the rule and no silent fallback is allowed.
3. **Access and delivery:** Inspect actual party targets, every Strix browser/HTTP/shell/plugin network tool and its containment options, runner/harness egress, deployed Cloudflare signals, scope-limited policy ownership, Linear team/labels/open-state and explicit fix-claim mapping, historical count representation, action-marker readability, and candidate GCS/ledger IAM. A `cf-mitigated: challenge` signal supports challenge attribution; generic 403/429 alone does not. Prove reachability from the same network/client path the harness uses. Record unknowns as unknowns.

## Concrete contracts and responsibility

Define versioned JSON schemas (`schemaVersion: 1`) and validate at trust boundaries. Parse in two stages: reject an unreadable document, invalid shared run/configuration, malformed collection framing, or invalid trusted existing-identity/action snapshot as a whole, skip all delivery, and attempt a failure summary. Then validate each independently framed observation, retest, and coverage item; quarantine an invalid item under a stable input index/reference and reason, reconcile valid items, and mark the run partial/failed rather than clean. An item cannot override shared identity, authorization, or session history. Use opaque strings for IDs/references and ISO timestamps; reject unrecognized enum values needed for writes. The following shape is the minimum shared logical API after ingestion; no secret value enters it:

```ts
type PlannerInput = {
  schemaVersion: 1;
  run: {
    id: string;
    environment: "party";
    authorizedTargets: string[];
    pathId: string;
    instructionsRevision: string;
    instructionsSha256: string;
    harness: { name: string; revision: string };
    model: { provider: string; id: string; effort?: string };
    budgetUsd: number;
    deadline: string;
    operatorId: string;
    edgePolicyRef?: string;
    evidencePrefix: string;
    evidenceRetentionPolicyRef: string;
    session: "not_started" | "validated" | "lost" | "unknown";
    assessment: "not_started" | "completed" | "interrupted";
    stopReason?: string;
  };
  sessionEvents: Array<{
    ref: string;
    sequence: number;
    state: "validated" | "rotated" | "lost";
    actorRole?: string;
    partyRef?: string;
    jarRef?: string;
  }>;
  coverage: Array<{
    surface: string;
    target?: string;
    status: "tested" | "interrupted" | "not_attempted";
    attemptedOperations: string[];
    conditions: string[];
    stopReason?: string;
    evidenceRefs: string[];
  }>;
  retests: Array<{
    exploitId: string;
    targetSurface: string;
    attemptedOperations: string[];
    observedObservationIds: string[];
    execution: "completed" | "interrupted" | "not_attempted";
    conditions: string[];
    stopReason?: string;
    evidenceRefs: string[];
  }>;
  observations: Observation[];
  existing: ExistingExploit[];
  processedActions: Array<{
    key: string;
    action:
      | "create"
      | "append_evidence"
      | "increment_run_count"
      | "reopen"
      | "notify";
    state: "applied" | "pending" | "uncertain" | "failed";
    externalMarker?: string;
  }>;
};
type Observation = {
  observationId: string;
  status: "confirmed" | "incomplete";
  rawFindingRef: string;
  sessionRef: string;
  observedSequence: number;
  environment: "party";
  surface: string;
  violatedBoundary: string;
  transitions: Array<{
    stepId: string;
    actorCapability: string;
    resourceRelation: string;
    targetClass: string;
    operation: string;
    expectedBoundary: string;
    observedEffect: string;
    prerequisiteStepIds: string[];
    evidenceRefs: string[];
  }>;
  preconditions: string[];
  actorRole: string;
  impact: string;
  severity: string;
  productionImpact: { value: "yes" | "no" | "unknown"; rationale: string };
  remediation: string[];
  retest: string[];
  components?: string[];
  blockedSteps?: string[];
  dangerousNotExecuted?: string[];
};
type ExistingExploit = {
  exploitId: string;
  linearIssueId: string;
  state: "open" | "claimed_fixed" | "unknown";
  issueOpen: boolean | null;
  fixClaimId?: string;
  claimRef?: string;
  environment: "party";
  surface: string;
  violatedBoundary: string;
  normalizedChain: Observation["transitions"];
  identityVersion: number;
  fingerprintAliases: string[];
  confirmedRunIds: string[] | null;
  historicalCount: number | null;
};
type PlannerOutput = {
  schemaVersion: 1;
  runId: string;
  decisions: Array<{
    observationId?: string;
    outcome:
      | "new"
      | "rediscovered"
      | "contradicts_fix"
      | "not_observed"
      | "unresolved";
    reason: string;
    normalizedMatchReason?: string;
    exploitId?: string;
    issueId?: string;
    confirmationKey?: string;
    episodeKey?: string;
    evidenceRefs: string[];
    proposedActions: Array<
      "create" | "append_evidence" | "increment_run_count" | "reopen"
    >;
    ticketDraft?: {
      labels: string[];
      boundary: string;
      affectedSurface: string;
      preconditions: string[];
      actorRole: string;
      demonstratedImpact: string;
      severity: string;
      productionImpact: Observation["productionImpact"];
      activityChain: Observation["transitions"];
      blockedSteps: string[];
      dangerousNotExecuted: string[];
      remediation: string[];
      retest: string[];
      runId: string;
      evidenceRefs: string[];
      components?: string[];
    };
    countChange?: { runId: string; historicalCount: number | null };
    notificationEligible: boolean;
    neededEvidence?: string[];
  }>;
  summary: {
    coverage: PlannerInput["coverage"];
    stopReason?: string;
    proposedIssueIds: string[];
    unresolved: string[];
    nonObservations: PlannerInput["retests"];
  };
};
```

Persist run records separately from this planner input/output with stage states (`configuration`, `authentication`, `assessment`, `reconciliation`, `delivery`, `reporting`), actual usage availability, edge observations/counts and per-action delivery result (`proposed`, `applied`, `failed`, `uncertain`). Summary schema includes **actual** opened/reopened/updated issue links, quarantined item references/reasons, all unresolved/failed actions, coverage, non-observation, stop reason, evidence availability, retention policy, and spend/time availability. Never turn a proposal into an applied result by formatting the summary. The Strix adapter reads its native JSON/coverage/usage files as **candidate** observations and preserves raw evidence privately; no native field alone establishes the product's causal identity or session provenance. The trusted runner owns GCS credentials and redaction/persistence. Use a restrictive temporary directory, no core dumps, bounded captured subprocess output, and cleanup on success, crash, cancellation, and timeout where execution remains possible. A redaction failure blocks upload/ticket delivery of that artifact and leaves only a credential-free diagnostic; inspect residual files and all public/retained sinks in tests.

The selected command is `python src/attack-runner/strix_bridge.py --profile <private-json>` from the trusted Node runner, with pinned Strix source/image and explicit `STRIX_LLM`/provider settings. Build an allowlisted child environment **before Python import**, including `STRIX_TELEMETRY=0`, `STRIX_NO_UPDATE_CHECK=1`, `OPENAI_AGENTS_DISABLE_TRACING=1`, and no inherited `TRACELOOP_*`, OTEL, PostHog, Scarf, optional web-search, MCP or cloud credentials. The pinned Strix CLI has **no telemetry flag**; `STRIX_TELEMETRY=0` is its documented switch and also applies to the bridge's Strix imports. The private runtime file and Strix `run.json` may contain the fresh magic link and must never be copied to a public artifact or unredacted ticket. Strix-native PostHog/Scarf sends, update checks, optional trace export and dependency analytics must be absent in an instrumented startup, normal, failure and cancellation probe; a qualified model-provider call is a separate required data path. No optional Attack Runner telemetry is enabled. See `feasibility.md` and reviewer telemetry inventory.

Bridge protocol: one long-lived Python process receives a private `prepare` JSON with run ID, image digest, target set and committed instruction hash. It calls `session_manager.create_or_reuse(scan_id, image=..., local_sources=[])`, awaits `bundle['caido_client'].get()`, starts `agent-browser` in that sandbox and checks a blank-page snapshot, then emits a credential-free `ready` record on a private pipe. Only then does Node request/retrieve the fresh link from the authorized test mailbox and send it on the same private pipe. Bridge substitutes the link into the private instruction copy, creates Strix `ReportState`, and calls `run_strix_scan(..., scan_id=..., image=..., cleanup_on_exit=False, max_budget_usd=100, mcp_connection_requests=[])`; the cached sandbox is reused. Before its `finally` calls `session_manager.cleanup(scan_id)`, export the cited Caido requests/responses through `list_requests_with_client`/`get_request_with_client` into private redacted evidence, plus native report/coverage/usage and session validation events. Failed export makes associated findings incomplete, not confirmed. Bridge cancellation stops assessment, exports available prior evidence if executable, then always cleans up. Node enforces the outer deadline and treats hard kill as interrupted with potentially unavailable evidence. The precise browser command and shared jar/maintenance behavior require the controlled qualification described in `feasibility.md`.

The trusted adapter converts raw results to `Observation` with evidence references and a credential-free session provenance. It confirms an observation only when its ordered request/evidence trace starts from the validated non-admin developer identity, party, and authorized cookie jar; a rotated cookie in the same jar retains continuity. A demonstrated privilege escalation or unauthorized capability reached from that validated session remains a confirmed exploit transition. An anonymous, wrong starting identity, unattributed session, or post-loss effect is incomplete. Earlier valid positives survive later loss. For one raw finding with multiple independently exploitable control failures, split at each independently actionable violated boundary before planner matching, retaining shared prerequisites/evidence in both observations; a multi-component chain with one cause stays one observation. The **planner owns** canonical transition normalization, causal matching against both current-run observations and existing issue snapshots, triage, stable exploit ID assignment, and action proposals. Normalize away prose, titles, incidental reconnaissance/order, run IDs, generated resource IDs, repository, model/harness/path, and timestamps; retain actor/tenant/resource relationships, violated control, logical surface, causally relevant transitions/prerequisites, and corrective outcome. Compare candidates by evidence-backed boundaries, not a prose hash or model similarity score. Fingerprint vN is an index only; stable IDs and aliases survive normalization changes. Ambiguous/partial evidence or multiple plausible matches yields `unresolved`, never speculative create/merge. Unknown repository metadata does not block creation.

Native Strix mapping is deliberately narrow: `vulnerabilities.json[].id` becomes `rawFindingRef` (run-scoped only); `title`, `description`, `technical_analysis`, `poc_description`, `evidence`, `http_exchange_ids` are candidate chain text/evidence; `severity`, `impact`, `remediation_steps`, `fix_verification` are candidate ticket material; `coverage.json` supplies candidate attempted/gap context; `run.json.status` and `llm_usage` supply assessment/usage context. None supplies a stable exploit ID, tenant/actor relation or authorized-session proof by itself. The adapter must extract explicit actor → resource → operation → observed effect and prerequisite edges from cited trace material; unsupported claims stay `incomplete`. Canonical cause key is the tuple `(environment, logical surface, starting actor/tenant relation, violated control, target resource relation, demonstrated effect, ordered prerequisite/control transitions)`. Component/repository/title/model and incidental IDs do not enter identity. If one raw report supports two independent cause keys, split it; if more than one existing issue matches or a required tuple member lacks evidence, output `unresolved` with missing fields/candidate IDs. `feasibility.md` includes a worked case.

The Linear adapter maps vendor statuses to `open|claimed_fixed|unknown` only with team-confirmed rules and an explicit claim reference; unknown mapping blocks lifecycle writes. It formats one full-chain ticket with Bug/pentesting/harness labels, severity, qualified production impact, demonstrated/blocked/unexecuted distinctions, all remediation, end-to-end retest, and authenticated evidence references. A resolved ticket with non-observation receives **zero** Linear writes, regardless of retest completion. A confirmed contradiction targets the same closed issue; failed reopen stays failed/pending and cannot create a replacement. Count one confirmed exploit per distinct run, preserve unknown historical count as unknown, and never count a replay. Notification eligibility is metadata only; no Slack transport in this release.

E2 keys have separate owners: `exploitId + runId` uniquely owns that run's evidence and count actions, while `exploitId + fixClaimId` owns only contradiction notification eligibility and reopen state. Create has a stable exploit-level key. Run B against the same claim still adds its own evidence/count once, without a second notification or unnecessary reopen. Store each action's state independently in the generation-CAS corpus journal. Current first-party Linear schema accepts optional caller-supplied UUIDv4 `id` on issue and comment creation; generate random UUIDv4 once, persist it **before** dispatch, and read back that exact ID after lost acknowledgment. Put an opaque action marker in the created ticket and each evidence/count comment; inspect issue body/comments/state and legacy content before marking applied. Reopen needs same-issue state/history readback. The schema does **not** prove duplicate POST idempotency: if readback is inconclusive, leave `uncertain`, stop automatic retry and surface operator recovery. New fix claim ID makes a new eligible episode. Ledger history outlives evidence expiry.

For each action, CAS journal state `proposed → pending(key, issueId?, marker) → applied(externalRef)` only after positive readback, or `pending → uncertain` on lost acknowledgment/timeout. `failed` records a known rejection. After a crash, inspect Linear: exactly one matching ID/marker and expected state permits `applied`; null/not-found read is **not** proof that a timed-out write did not commit, so an uncertain create/comment is never automatically retried. An operator resolves it from external evidence or documents a safe manual disposition. Never release an uncertain first-create reservation automatically. A count is a **derived number of distinct confirmed run keys**, not a blind increment; an unknown legacy historical count stays unknown and is never overwritten with a guessed total. Evidence and count markers have separate per-run action types, so one partial write cannot silently complete the other. Reopen is attempted only for the same closed claimed-fixed issue; a successful state transition without proof of which claim/action caused it remains uncertain until reconciled.

## Ordered reviewable slices

| Slice                              | Deliverable and exit oracle                                                                                                                                                                                                                                                               | Dependency                                                                       |
| ---------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| 0. Contract and feasibility        | Schemas, synthetic fixtures, selected Strix-file/CLI and journal interfaces, pinned source evidence in `feasibility.md`, qualification matrix, and current-`main` check. Record externally blocked auth, provider, Linear and GCS inputs.                                                 | None; start immediately                                                          |
| 1. Offline planner                 | Pure CLI, e.g. `yarn attack-runner plan --input fixture.json --output plan.json`, two-stage validation, deterministic output, causal matcher, multi-cause decomposition, triage, stable identity aliases, separate replay/episode keys, semantic fixture tests. No network/secret access. | Slice 0 schema; can proceed while live investigations continue                   |
| 2. Trusted run shell               | Profile validation; authorized target set; Monday LA schedule/manual workflow with named operator coverage and visible skip; private preflight; stage/run record; redacted diagnostic. 60-minute overall deadline and reporting reserve.                                                  | Authorized targets/operator and secure destination contract                      |
| 3. Auth/harness adapter            | Dedicated test-mailbox retrieval, fresh mint/once-only redeem, identity provenance, same cookie jar and maintenance, edge classification, isolated Strix egress, pinned bridge/model/path, native-file normalization and enforced stop/usage.                                             | Authorized mailbox, demonstrated auth, harness/model/edge and egress feasibility |
| 4. Durable reconciliation/delivery | GCS generation-CAS corpus journal, global first-create pending state, Linear status/action-marker readback, safe manual recovery of unknown writes, complete ticket formatting, actual-delivery summaries.                                                                                | Confirmed Linear mapping/readback and private journal bucket/IAM                 |
| 5. Private report and release      | Redaction, guarded GCS upload and bounded retries, lifecycle/reader/audit qualification, workflow failure semantics, controlled end-to-end and concurrent cases. Enable schedule only after live gates pass.                                                                              | Provisioned GCS/ledger, authorized test environment and staffed operator         |

Use GitHub's documented timezone schedule: `cron: '0 9 * * 1'` with `timezone: America/Los_Angeles`, plus `workflow_dispatch`; verify the deployed workflow is accepted and simulate DST transitions. GitHub schedules may be delayed or dropped, so validate named on-call coverage at actual start and a tested stop procedure; a strict start SLA needs an external scheduler. One environment-wide Actions concurrency group covers both entry points, with cancellation of an already-running Attack Runner disabled. Manual dispatch bypasses only the clock gate, never target, storage or operator validation. Put all Strix browser/HTTP/shell/plugin traffic in an isolated network path with no direct egress except the audited HTTP capture/proxy route; a direct connection must be denied even when its target host is authorized, or its result cannot confirm a finding. At each captured connection, constrain the explicit authorized host set within `*.foxglove.party`, redirects/pivots and resolved IPs; deny unapproved party hosts, other domains, loopback/private/metadata destinations and DNS rebinding. Inspect target-owned browser feature-flag/analytics calls separately: if a required app dependency lies outside party, obtain a narrow app/security-approved route or mark coverage incomplete; never treat it as Strix analytics or silently alter target behavior. Keep trusted runner auth, model provider, Linear and GCS traffic outside the restricted harness path. The pinned Strix source offers `STRIX_DOCKER_SANDBOX_NETWORK`, but also gives its container `NET_ADMIN`/`NET_RAW` and host-gateway; prove actual containment of every network-capable tool rather than assuming the env var enforces it. Use non-destructive test data and stop signals.

The workflow remains non-required for unrelated merges but stage failure remains a failed workflow. Before auth, fail closed if the private sink is missing/unsafe/unwritable or target/operator profile invalid. During assessment, pause on unknown session/access, stop after bounded diagnosis, retain prior positives, and mark interrupted coverage. Reserve time for evidence/reconciliation/reporting inside the 60-minute deadline and stop new attack work before spend/time exhaustion. Reporting retries have an explicit finite cap (propose three attempts with bounded backoff) and stop at the earlier cap or deadline; retries never repeat ticket writes. Whole-input reconciliation failure skips delivery but attempts a failure summary. If summary persistence fails, return `ReportFailed`, diagnostic with run ID/stage/cause/summary unavailable if execution permits, and failed or timed-out workflow status. A persisted failure summary does not convert a failed run into success. Hard timeout may prevent the final diagnostic.

Private GCS is a provisioned release dependency: a permanent journal object in a restricted namespace **outside** evidence lifecycle, plus dedicated 30-day evidence storage with uniform bucket-level access, enforced public access prevention, run-scoped evidence-writer authority, authenticated engineering/security readers, read audit, encrypted storage/transport, tested anonymous/unauthorized denial, and no Strix storage credential. Partition evidence under immutable run-ID prefixes and verify that its writer can create only that run's objects, cannot read/list or overwrite unrelated runs, and has no bucket administration; journal access belongs only to the trusted delivery step. Qualify whether GCS IAM conditions can enforce the exact evidence prefix/permission set; if not, a trusted upload broker validating run identity is an explicit infrastructure dependency. Do not assert that plain bucket-level identity is run-scoped. Set 30-day evidence lifecycle and document effective noncurrent-version, soft-delete, and deletion-delay behavior; owner-approved extensions are recorded per case. Expired evidence references become unavailable while ticket chain/remediation and the permanent journal survive. Never emit exploit details, raw credentials, full ticket links, signed URLs, or evidence in public artifacts/logs/job summaries/PR comments.

## Acceptance trace and verification oracle

`Fixture` means pure planner semantic assertions with network and credential access disabled. `Controlled` means a purpose-built integration test against qualified adapters/services, not a mock-only claim. `Revision` means command/result evidence tied to the final commit or patch hash **of each delivered slice**; rerun affected checks after any change to that slice. Missing live evidence is **untested**, never passed.

| ID    | Slice | Verification oracle                                                                                                                                                                                                                                                                                                                 |
| ----- | ----- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| E1-01 | 1     | Fixture: one full-chain create proposal with unknown repo allowed                                                                                                                                                                                                                                                                   |
| E1-02 | 1     | Fixture: same open issue, one evidence/count proposal, no notification                                                                                                                                                                                                                                                              |
| E1-03 | 1     | Fixture: closed/open claimed-fix target same issue and claim; reopen only closed                                                                                                                                                                                                                                                    |
| E1-04 | 1     | Fixture: completed/interrupted/unattempted retest of resolved issue produces summary only, zero writes                                                                                                                                                                                                                              |
| E1-05 | 1     | Fixture: absent old issue and no retest yields no fix/closure conclusion                                                                                                                                                                                                                                                            |
| E1-06 | 1     | Fixture: auth/session/timeout/network interruption produces non-observation plus cause/incomplete coverage                                                                                                                                                                                                                          |
| E1-07 | 1,3   | Fixture/controlled: validated non-admin start and exploit-derived admin cookie/token plus forbidden operation remain confirmed even if later `/me` shows admin; maintenance failure stops new ordinary work but does not erase that chain; post-loss, anonymous, wrong starting identity and unattributed effects are incomplete    |
| E1-08 | 1,4   | Fixture/controlled: duplicate within input and replayed per-run action each yield at most one evidence/count mutation                                                                                                                                                                                                               |
| E1-09 | 1,4   | Fixture/controlled: second run against same fix claim adds one evidence/count, no second notification                                                                                                                                                                                                                               |
| E1-10 | 1     | Fixture: cross-repo/harness/path evidence is one ticket; independent exploit separate                                                                                                                                                                                                                                               |
| E1-11 | 1     | Fixture: two plausible matches unresolved; unknown ownership alone permits creation                                                                                                                                                                                                                                                 |
| E1-12 | 1     | Fixture: invalid item identity/state quarantined, valid positive survives later non-observation; invalid shared envelope explicitly fails                                                                                                                                                                                           |
| E1-13 | 1     | Fixture: mixed valid/invalid items yield valid decisions and partial failure state with item references/reasons                                                                                                                                                                                                                     |
| E1-14 | 1     | Fixture: party-only evidence keeps production impact unknown with rationale                                                                                                                                                                                                                                                         |
| E1-15 | 1     | Sandbox CLI fixture: no network, secrets, harness, writes, or workflow changes                                                                                                                                                                                                                                                      |
| E1-16 | 0–5   | At each delivered slice's final revision, record commit/patch hash, exact commands, exit results, review and affected rechecks                                                                                                                                                                                                      |
| E1-17 | 1     | Fixture: paraphrase/resource ID/recon/evidence-order changes preserve causal match with reason                                                                                                                                                                                                                                      |
| E1-18 | 1     | Fixture: one raw finding with two independent boundaries splits into two identities with shared prerequisites/evidence; single cause across components stays one; partial chain triaged                                                                                                                                             |
| E1-19 | 1     | Fixture: replayed create/claim contradiction eligible once; new claim eligible; rediscovery/non-observation not; every run has summary proposal                                                                                                                                                                                     |
| E1-20 | 1     | Fixture: fingerprint v1→v2 alias retains stable exploit ID and issue                                                                                                                                                                                                                                                                |
| I-01  | 3     | Controlled party auth: successive runs get distinct link; ready worker redeems once before expiry; failed establishment starts no assessment                                                                                                                                                                                        |
| I-02  | 3     | Controlled full-duration session: same jar and server updates, valid past 15 min, 300-second/pre-chain checks; loss stops work and retains evidence                                                                                                                                                                                 |
| I-03  | 3     | Controlled bridge run: ready pipe precedes mint; selected committed file/revision/hash reaches Strix, placeholder unchanged; Caido export precedes cleanup; crash/cancel/timeout leaves no live secret bytes in local or public/retained sinks                                                                                      |
| I-04  | 3     | Controlled near-limit spend/time test: measured usage and stop before cap with reporting reserve; unavailable enforcement blocks release                                                                                                                                                                                            |
| I-05  | 4–5   | Controlled mixed ownership: private summary contains complete actual ticket links and failed/unresolved actions; no repo filter or Slack                                                                                                                                                                                            |
| I-06  | 4     | Controlled lost acknowledgment for each create/evidence/count/reopen action: external marker/readback and ledger agree, or action stays uncertain without unsafe retry; second run counts once                                                                                                                                      |
| I-07  | 3     | Bridge adapter matrix varies each setting independently; resolved values recorded, unsupported explicit error, identity policy stable; browser/shell/plugin HTTP paths must each yield cited Caido exchange plus validated jar/actor/sequence or stay unresolved                                                                    |
| I-08  | 2,5   | Verify accepted timezone cron across DST plus manual/weekly staffing tests: Monday 09:00 LA, visible unstaffed skip, one-hour deadline, failed assessment stays failed/non-gating                                                                                                                                                   |
| I-09  | 4     | Controlled cross-component partial fix: one full-chain issue and remaining remediation; no automatic resolved claim                                                                                                                                                                                                                 |
| I-10  | 5     | Controlled end-to-end positive and zero-finding/stop traces from run through coverage, decisions, actual writes, private summary, stop reason                                                                                                                                                                                       |
| I-11  | 4     | Controlled two confirmations of one claim: evidence/count once per run, reopen same issue only as needed, alert eligible once; failed/unmapped transition remains pending/failed                                                                                                                                                    |
| I-12  | 0,3   | Qualification record + default-resolution test: exact Sonnet-4-8 provider ID, $100/60 min, verified Strix behavior; unavailable blocks launch without substitution                                                                                                                                                                  |
| I-13  | 5     | Fault injection: repeated GCS failure/cap/deadline yields ReportFailed and visible failure/timeout, no repeated Linear writes or retained-coverage claim                                                                                                                                                                            |
| I-14  | 1,5   | Corrupt shared envelope: zero ticket writes, redacted failure summary attempted, workflow fails even if summary persists; mixed bad item plus valid positive delivers only the latter under partial-failure status                                                                                                                  |
| I-15  | 2,5   | Provisioning/IAM and fault test: unsafe/unwritable sink fails before auth; authorized read works, public/unauthorized and cross-run writer read/write/list denied; no harness credential/public evidence; injected redactor failure blocks artifact delivery, cleanup leaves no live credential bytes; post-run upload follows I-13 |
| I-16  | 3,5   | Controlled challenge/block prelogin and after positive; generic 403/429 unclassified; counts/phase/request ID/coverage and policy scope in private record; positive survives, no edge-only exploit                                                                                                                                  |
| I-17  | 5     | Lifecycle configuration and expiry/extension test: effective recoverable retention documented, approved extension recorded, expired evidence marked unavailable, ticket chain and durable ledger remain                                                                                                                             |

For E1-07, use one targeted fixture in which a validated non-admin session obtains an admin cookie/token through the exploit, performs a forbidden operation, then loses the session; keep that causal escalation confirmed even when later `/me` shows admin, while quarantining an identical later effect from an anonymous or wrong starting identity. Additional release test beyond the 37 IDs: two concurrent runs describe the same new exploit using paraphrases that yield different provisional keys, then target the same claimed-fixed issue, while one Linear acknowledgment is lost. Assert one issue, one confirmation per run, correct final open state, one eligible contradiction per claim episode, and honest actual/uncertain summaries. From the actual isolated harness path, ask every available network-capable tool to reach an unapproved party host and an off-scope/local destination; inspect egress logs to prove none left the boundary, including redirect and changed DNS resolution cases. Inspect the rendered Linear ticket body for all ticketDraft fields, including blocked/unexecuted steps and run/evidence references. Run required repository formatting/tests at each delivered slice's final revision; record exact commands and exits. Do not infer live auth, edge, budget, or delivery success from offline fixtures.

## Genuine decisions still requiring evidence

- App/auth owner: authorize a dedicated test mailbox or secure app-owned retrieval route, identify a supported session-maintenance request and verify the party deployment; the test-only Redis shortcut is excluded.
- Harness/provider owner: publish an immutable Strix image digest and qualify cookie handoff, per-request authenticated provenance, isolated network path, exact permitted Sonnet-4-8 provider ID, usage accounting and strict $100 stop. Source inspection alone has not passed these.
- Delivery/infrastructure owner: provision permanent GCS journal and run-scoped evidence sink; confirm Linear team/status/fix-claim mappings, readable action markers and operator recovery procedure. No unknown Linear write is automatically retried.
- Operator/security owner: approve exact party targets, staffed rotation/stop mechanism, scoped edge policy and effective evidence retention. These are inputs, not facts established by this plan.
