# Attack sessions

## Summary

Each assessment uses one fresh ordinary magic-link login as a company-owned non-admin test user. A separate login issuer returns the link to the ready runner in a private authenticated response. The runner keeps the resulting session cookie for the full test. It has no superadmin or signing authority.

Authentication needs no employee login, personal mailbox, copied cookie, or manual transfer. The responsible operator must still be available to observe and stop the assessment, as specified in [Attack runner](attack-runner.md).

## Terms

- **Login issuer**: a separately deployed company service that can request an ordinary test-user link from the app backend.
- **Login handoff**: the private response containing one fresh link and its authorized run/attempt binding. It is not a stored GCS object.
- **Session cookie jar**: the attempt-local browser context that retains the real session cookie and server-issued updates.
- **Authentication mode**: the session source, such as ordinary magic-link login or impersonation. A matching member ID does not make these modes equivalent.
- **Session maintenance**: supported activity or refresh that keeps the same logical session usable. A successful health check alone does not prove continuity.

## Approved product decisions

Product approver: Kumar. Approval date: 2026-09-30 UTC. Approved decision revision: `AR-PM-2026-09-30-r3`, comprising reviewed packet `AR-PM-2026-09-29-r2` and the explicit amendments for restricted superadmin backend minting, direct response delivery and a 15-minute maximum login wait. The table below records the selected outcomes and coverage limits.

Delivery uses a private request-response channel. No temporary GCS login object is part of this contract. Authority separation, identity/mode checks, unknown outcomes and evidence preservation remain required. Private GCS for redacted assessment evidence is unchanged.

| Decision             | Selected outcome                                                                                                                                                          | Accountable owner                  | Accepted coverage/risk                                                                                                                         | Qualification evidence                                                                                              | Blocks engineering?                                 |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------- |
| Mode                 | Ordinary non-admin magic-link login only                                                                                                                                  | Foundations                        | Impersonation results cannot substitute for this profile                                                                                       | Application-derived mode and identity, I-22                                                                         | Qualification blocks live use                       |
| Link creation        | Restricted ordinary-link operation in the superadmin/app backend; separate issuer calls it                                                                                | Foundations                        | Direct mint tests ordinary redemption and downstream access; it does not test email delivery, mailbox ownership, employee SSO or impersonation | Authorized company identity, fixed test-user mapping, token registration and denied out-of-scope minting, I-18–I-20 | App dependency; no existing endpoint assumed        |
| Delivery             | Private authenticated request-response to the authorized runner; no temporary GCS login object                                                                            | Foundations                        | Lost or uncertain response ends the attempt; no durable secret recovery or automatic new login                                                 | Duplicate/concurrent requests, interrupted response and isolation, I-19–I-21                                        | Qualification blocks live use                       |
| Service operations   | Foundations owns service/on-call, company credentials, test-user provisioning/recovery/rotation/revocation, allowed profiles, deployment/change approval, IAM and cleanup | Foundations                        | Operator coverage for assessment is a separate requirement                                                                                     | Provisioned identities, access tests and operational runbook                                                        | Configuration and qualification required            |
| Alerts               | Reuse existing Console operational alerting and its normal delivery-failure handling                                                                                      | Foundations                        | No new alert fallback or delivery guarantee; operational alerts are separate from deferred assessment-summary Slack delivery                   | Correct environment route, sanitized test alert and shared failure behavior, I-21                                   | Qualification blocks recurring launch               |
| Cleanup              | Clear issuer-controlled link material within 15 minutes of the earliest login acknowledgment, cancellation/termination or link expiry                                     | Foundations                        | Expiry is not erasure; issuer status does not certify runner cleanup or revoke a session                                                       | Timed success, cancellation, crash and uncertain cleanup cases, I-21                                                | Qualification blocks live use                       |
| Operational settings | Foundations approves bounded cleanup retries, private credential-free record retention, and persistent-failure escalation/resumption through existing operations review   | Foundations                        | These values are required configuration; no retention duration is inferred from the evidence bucket                                            | Recorded settings and failure/recovery cases, I-21                                                                  | Missing owner-approved configuration blocks launch  |
| Login deadline       | At most 15 minutes from the runner's first readiness request until identity/mode validation; original job deadline still applies                                          | Foundations                        | This is maximum login wait, not minimum remaining link lifetime                                                                                | Deadline and delayed response cases, I-20                                                                           | Qualification blocks live use                       |
| Link margin          | Redeem immediately; Foundations approves the minimum remaining lifetime and clock allowance before qualification                                                          | Foundations                        | A 15-minute link cannot have 15 minutes remaining after delivery                                                                               | Reject a link with less than the approved margin; enforce token expiry, I-20                                        | Missing approved configuration blocks qualification |
| Session duration     | Same logical session for the full configured assessment                                                                                                                   | Foundations                        | Cookie lifetime in source does not prove deployed continuity                                                                                   | Controlled full-duration run, I-02                                                                                  | Qualification blocks live use                       |
| Checks and refresh   | Check every 300 seconds and before high-impact activity; use supported refresh at 80% of a verified session lifetime if needed during the test                            | Foundations                        | Link lifetime is not the refresh timer; current ordinary flow has no separate refresh operation                                                | Measured expiry/activity behavior and retained cookie updates, I-02                                                 | Qualification blocks live use                       |
| Failure and attempts | Stop on failed or unknown session validity; one login attempt per job                                                                                                     | Foundations                        | No same-job restart, anonymous fallback or reset of time/spend limits                                                                          | Session failure, ambiguous redemption and duplicate request cases, I-02/I-20                                        | Qualification blocks live use                       |
| Release authority    | Human PR reviewers accept evidence, with Foundations responsible for authentication and operations                                                                        | Human PR reviewers and Foundations | Source review is not live qualification; edge exceptions limit normal-edge coverage                                                            | Reviewed evidence for all auth, isolation, continuity, cleanup and edge cases                                       | Human acceptance required before live release       |

**Verdict: READY_FOR_ENGINEERING_QUALIFICATION.** This permits qualification of the chosen contract, not implementation or live release on the strength of these documents alone. Named owners must approve the remaining configuration values. A required app change is a separate implementation dependency. No product mode, authority boundary or fallback may be selected for implementation convenience.

## Decisions

### Minting authority stays outside Attack Runner

Foundations modifies the superadmin backend to support restricted ordinary-link creation. Code creates each link automatically; Foundations is the team responsible for the service. Preserve the existing impersonation operation for its existing consumers. Do not reuse its impersonation semantics for this profile or change all superadmin links to ordinary mode.

The separate issuer holds the app-facing authority. The scheduler authorizes one run, attempt and profile. After preparing the browser, the runner requests only that authorized result from the issuer. Its request cannot choose arbitrary emails, members, organizations, redirects or destinations. Knowing a run ID is not authorization. A runner's permission to receive its own result grants no mint, issuer-impersonation, deployment or policy authority.

Authenticate the issuer's app call with a company-owned identity and a restricted grant. The app must validate its authority for the approved test identity before asserting verified email. Existing email-based verification assumptions must not be bypassed by merely setting `emailVerified`. Keep signing keys and app/superadmin credentials outside the runner and harness, including their files, environment and metadata access.

### A private response belongs to one run and attempt

The issuer returns the link over the authenticated request-response channel to the independently authorized runner. The response binds schema version, run, attempt, approved profile, expected member/org, declared ordinary mode, allowed sign-in URL and issuance/expiry times. The adapter checks these against trusted bootstrap configuration before redemption. The payload cannot change the expected identity or target.

Claim the authorized attempt before minting. Duplicate or concurrent requests cannot cause additional minting or parallel redemption. Do not retry a credential response or a mint operation after an uncertain outcome. Return only redacted attempt state for duplicates; end a lost-response attempt visibly. A later test is a new authorized job, not a restart of this job. Record uncertain mint or delivery as unknown, not as proof that no link exists.

Keep the link out of persistent storage, request/response logs, traces, caches and retained reports. No temporary GCS login bucket is part of this contract. Secret-free attempt and cleanup records remain durable. The harness receives only the test link/session and its private local files, not issuer, status-service or evidence-storage credentials.

### The ready worker logs in immediately

The ready worker redeems the fresh link once and keeps the resulting cookie in this attempt's cookie jar. Preserve the application's HttpOnly, domain, path and security behavior. Erase the run-local link after use.

The preflight deadline is the earlier of 15 minutes after the runner sends its first readiness request and the original job deadline. Duplicate readiness requests cannot reset either clock. The link has its own 15-minute lifetime from creation. Foundations approves a minimum remaining lifetime sufficient for bounded redemption plus clock allowance. Missing configuration or insufficient time fails preflight. Complete identity and mode validation within the preflight deadline even if the link was redeemed earlier.

Missing, stale, cancelled, wrongly bound or unexpected-mode responses fail preflight. Uncertain redemption ends the attempt. There is one login attempt per job and no fallback to a saved cookie, personal credential, impersonation or anonymous assessment.

### Authentication mode must match the intended coverage

Only ordinary non-admin login is approved. Direct mint excludes email delivery and mailbox ownership from coverage. It does not establish employee SSO or impersonation behavior. Record these limits and the verified mode in private run provenance and in relevant exploit-ticket evidence. Do not substitute evidence across modes.

After redemption, verify the actual member, organization, starting role and mode using application-derived evidence bound to that session. `/v1/me` provides identity but not session source in the inspected code. An issuer label, mutable cookie, UI label, or absence of an impersonation marker is insufficient proof of ordinary mode. Foundations must provide and qualify a reliable application signal. Unknown, ambiguous or mismatched mode fails preflight.

A valid non-admin starting session can later demonstrate privilege escalation. Preserve that causal transition as exploit evidence. Do not discard it because the observed role changed during the attack.

### One logical session lasts for the assessment

Use the same cookie jar through the configured authenticated work window. Check it every 300 seconds and before high-impact activity. Retain server-issued cookie updates. If a verified session lifetime requires supported refresh during the test, perform it at 80% of that lifetime; do not calculate it from magic-link expiry. An unsupported required refresh blocks qualification.

Source sets a ten-year Max-Age for hosted persistent cookies and provides a job that removes sessions after 90 days without recorded activity. Browser restrictions, revocation and deployed behavior can differ. Authenticated requests queue last-seen updates; that is not a separate token-refresh operation. There is no reason in this source to remint at 12 minutes. Prove the same session works beyond magic-link expiry and for the full configured duration. A single successful `/v1/me` response or last-seen update is not that proof.

Do not reopen the link, remint, clear cookies, sign out or switch to Google SSO to imitate continuity.

### Session loss stops active work

A failed check or unknown session validity stops active assessment. Confirmed loss records `SESSION_LOST_NEED_FRESH_MAGIC_LINK`; an unknown cause stays unknown. This diagnostic does not authorize a second login in the job. Preserve completed evidence and unfinished coverage. Do not resume attacks after diagnosis in that job.

### Edge denial is distinct from session loss

Classify confirmed challenges/blocks as `EDGE_CONTROL_BLOCKED`. Insufficient evidence is `ACCESS_FAILURE_UNCLASSIFIED`, not a guessed session expiry. Stop affected assessment and record incomplete coverage. Bounded diagnosis may explain the failure within the remaining job time; it does not resume attacks or start another login. Prior confirmed positives remain valid. The environment owner approves and records any narrowly scoped party traffic policy; the adapter cannot change edge controls.

### Credentials remain ephemeral

Live links exist only in the issuer/app response path and the private run context. Cookies and authentication headers stay in the contexts that need them. No credential values enter committed files, evidence artifacts, tickets, Slack, logs or traces.

The issuer releases its references to link buffers promptly after responding and no later than 15 minutes after the earliest cleanup trigger: login acknowledgment, cancellation/termination or link expiry. Cleanup also covers crashes and missing acknowledgments without runner cooperation. Foundations qualifies the app/issuer/proxy policy: no persistent response bodies, credential caches, body logging/tracing or credential-bearing crash dumps. Qualification uses configuration inspection and controlled synthetic-token tests; it does not claim to scan all process memory during each run. The runner separately clears its link after use and its other run-local credentials on termination. Issuer cleanup does not certify runner cleanup or revoke the established session.

The issuer creates a private, credential-free cleanup record before minting. Scheduler and issuer derive its stable reference from the configured status namespace and `attempts/{runId}/{attemptId}/cleanup`, encoding IDs as individual path segments. Bootstrap supplies that reference before readiness. Record scope, update time and sanitized reason with status `pending`, `cleared`, `failed` or `not_created`. `cleared` means the issuer completed the cleanup actions below. It does not prove that no credential bytes remain in process memory. `not_created` requires confirmed failure before token creation. Record issuance and delivery observations separately from cleanup. An uncertain mint or response does not prove `not_created` and does not override observed cleanup. If cleanup cannot be confirmed, it stays `pending` during bounded reconciliation and becomes `failed` at its deadline, retaining the uncertainty reason. Do not remint to resolve it. Later confirmed cleanup updates the record while preserving failure history.

Before writing `cleared`, the issuer records these attempt-bound results:

1. The response writer completed or was aborted and closed. A completed write does not prove that the runner received it.
2. The issuer released its owned references to the app response, link and response buffers. Its cleanup routine reports completion without recording their contents.
3. The attempt used the qualified app/issuer/proxy policy revision, with body persistence, credential caching, body logging/tracing and credential-bearing crash dumps disabled. Missing or mismatched configuration prevents `cleared`.

The record names the action results, policy revision and observation time. Qualification verifies these actions with instrumented synthetic-token fixtures, including fault injection. Per-run status records the actions; it does not repeat a global search for credential bytes. After a crash, a missing cleanup acknowledgment remains unknown. A supervisor may supply equivalent termination evidence only if qualification proves that the identified runtime owned all resources covered by the missing actions. Otherwise cleanup remains `pending`, then `failed` at the deadline. Token expiry is still enforced independently.

The runner can read only its own redacted status. Deny listing, other-attempt access and every status write/delete, including inherited grants. The harness has no status credentials. Acknowledgments and cancellation identify only the authorized attempt and cannot change the cleanup target. Delayed responses cannot restart a cancelled or expired attempt.

The summary stores `handoffCleanup` status, observation time and stable record reference. Unavailable status is `unknown`. It is an immutable snapshot, not a promise of future cleanup. Only a confirmed stop before sending readiness supports “issuance was never requested.” After sent or uncertain readiness, a missing response/status cannot prove no issuance. Cleanup failure never erases independently confirmed exploit evidence.

Foundations uses existing Console operational alerting and its normal delivery-failure handling, with sanitized attempt references and no credentials. Source routes dev alerts to `#alerts-dev` and other environments to `#alerts`. Foundations verifies the actual environment mapping, private destination/access and on-call responsibility before launch. Use existing incident escalation/resumption practices and owner-approved record retention/retry settings; do not introduce a separate alert-delivery system. Assessment-summary Slack delivery remains deferred.

## Contracts

### Authentication adapter

The adapter handles the authorized private response, immediate redemption, identity/mode verification and session checks. The separate issuer owns minting and issuer cleanup. Emit exactly one terminal preflight result by the deadline: `PREFLIGHT_PASSED` after successful verification or `PREFLIGHT_FAILED` with a classified or explicitly unknown cause. The adapter gates attack tools until it passes. A prompt alone cannot enforce this boundary.

Use the supported scoped mint operation once Foundations provides it. The normal route returns success after email delivery; its Redis retrieval shortcut is test-only. Signing a JWT without registering it is insufficient. This contract does not invent a deployed endpoint.

### Issuance and handoff lifecycle

```mermaid
sequenceDiagram
    participant S as Trusted scheduler
    participant R as Attack Runner
    participant I as Separate issuer
    participant A as App backend
    participant B as Prepared browser
    S->>I: Authorize fixed run, attempt and profile
    S->>R: Bootstrap trusted identity and cleanup reference
    R->>B: Prepare browser
    R->>I: Authenticated readiness request for authorized attempt
    I->>I: Claim once and create pending cleanup record
    I->>A: Request restricted ordinary test-user link
    alt App confirms rejection before token creation
        A-->>I: Confirmed pre-mint failure
        I->>I: Record not_created with sanitized reason
        I-->>R: Redacted attempt failure
        R-->>S: Fail preflight and end attempt, no attacks
        S->>I: Terminate attempt
    else Mint outcome uncertain, including timeout or generic error
        I->>I: Record unknown issuance and reconcile cleanup
        I-->>R: Redacted unknown outcome
        R-->>S: Fail preflight and end attempt, no attacks
        S->>I: Terminate attempt, no remint
    else App confirms token creation
        A-->>I: Fresh registered ordinary link
        I-->>R: Private response with link and attempt binding
        I->>I: Complete and record cleanup actions
        alt Response valid and enough time remains
            R->>B: Redeem once
            B-->>R: Application session evidence
            R->>R: Verify identity and actual ordinary mode
            alt Verification passes before deadline
                R-->>I: Authenticated login acknowledgment
                R->>B: Release attack work
                B->>B: Same session, checks every 300 seconds
            else Failed or uncertain login or verification
                R-->>S: Fail attempt, no attack work
                S->>I: Terminate attempt
            end
        else Missing, expired, cancelled or mismatched response
            R-->>S: Fail attempt, no retry mint or login
            S->>I: Terminate attempt
        end
    end
    Note over I,A: No runner superadmin or signing authority
    Note over I,R: Issuer cleanup covers lost responses and acknowledgments
    Note over R,B: Stop on session failure; preserve prior exploit evidence
```

Scheduler authorization alone does not mint. The issuer waits for authenticated readiness. If the app confirms failure before creating a token, the issuer records `not_created` and returns a redacted failure. A timeout or generic error does not establish that no token was created: the issuer records unknown issuance and reconciles cleanup, with no remint. The runner emits `PREFLIGHT_FAILED`, ends the attempt and informs the scheduler; the scheduler terminates authorization. If no issuer response arrives, the runner takes the same failure path by its deadline. Issuer cleanup continues independently. A post-mint error cannot produce `not_created`. Cancellation reaches both issuer and runner; expiry covers lost cancellation messages. The runner can terminate without waiting for issuer cleanup. A response sent does not prove receipt, and an acknowledgment sent does not prove cleanup.

## Product dimensions

| Dimension            | Decision                                                                              | Source        |
| -------------------- | ------------------------------------------------------------------------------------- | ------------- |
| Access               | Company-owned non-admin identity; separate issuer; no runner superadmin authority     | This document |
| Seats and plans      | Internal automation; no new customer entitlement                                      | This document |
| Billing and metering | Authentication is not a customer meter                                                | This document |
| Limits               | 15-minute login deadline; one attempt/job; 300-second checks; 15-minute cleanup bound | This document |
| Security and data    | Private response and attempt-local cookie jar; credential-free status records         | This document |
| Deployment           | Foundations owns issuer/app qualification on authorized party                         | This document |
| Interfaces           | Authorized request-response, sign-in, mode/identity signal, status and cleanup        | This document |

## Alternatives considered

- Impersonation: rejected as a substitute for ordinary-login coverage.
- Company mailbox integration: not selected; use restricted direct mint. Email delivery is outside this profile's coverage.
- Temporary GCS login objects: superseded by the approved private response. Private evidence storage remains.
- Runner-held superadmin/signing authority: rejected, including a privileged helper on the same worker.
- Reused cookies, repeated link redemption or employee-assisted login: rejected. Each job starts one new session automatically.
- Same-job restart: rejected. A lost or uncertain session ends active work.

## Resources

Source inspection at app revision `410706f8e4c71582d55128bae2c8d9a0ae0a4096` and infra revision `5903e26c466fbde7d843aa2896fa2d91f306f1db` supports feasibility only. No live authentication, isolation, continuity or alert test has passed in this documentation task.

- [MagicTokenService](https://github.com/foxglove/app/blob/410706f8e4c71582d55128bae2c8d9a0ae0a4096/packages/api/src/services/MagicTokenService.ts): signing, registration, expiry and redemption; existing verified-email assumption.
- [Magic-link route](https://github.com/foxglove/app/blob/410706f8e4c71582d55128bae2c8d9a0ae0a4096/packages/api/src/routes/internal/auth/magic-link/index.ts) and [browser fixture](https://github.com/foxglove/app/blob/410706f8e4c71582d55128bae2c8d9a0ae0a4096/packages/e2e/utils/baseTest.ts): email delivery, test-only link retrieval and cookie reuse.
- [Impersonation operation](https://github.com/foxglove/app/blob/410706f8e4c71582d55128bae2c8d9a0ae0a4096/packages/api/src/routes/internal/superadmin/impersonate.ts), [ordinary sign-in](https://github.com/foxglove/app/blob/410706f8e4c71582d55128bae2c8d9a0ae0a4096/packages/api/src/routes/v1/signin/index.ts) and [sign-in tests](https://github.com/foxglove/app/blob/410706f8e4c71582d55128bae2c8d9a0ae0a4096/packages/api/src/routes/v1/signin/index.test.ts): distinct modes and direct internal mint feasibility.
- [SessionService](https://github.com/foxglove/app/blob/410706f8e4c71582d55128bae2c8d9a0ae0a4096/packages/api/src/services/SessionService.ts), [unused-session cleanup](https://github.com/foxglove/app/blob/410706f8e4c71582d55128bae2c8d9a0ae0a4096/packages/api/src/jobs/DeleteUnusedSessions.ts) and [identity response](https://github.com/foxglove/app/blob/410706f8e4c71582d55128bae2c8d9a0ae0a4096/packages/api/src/routes/v1/me/index.ts): activity, inactive-session deletion and mode-signal gap.
- [Console alert example](https://github.com/foxglove/infra/blob/5903e26c466fbde7d843aa2896fa2d91f306f1db/stacks/console/temporal-workflows-alerts.tf) and [notification routes](https://github.com/foxglove/infra/blob/5903e26c466fbde7d843aa2896fa2d91f306f1db/stacks/console/main.tf): existing operational alert path, not evidence of deployed issuer alerts.

## References

- [Attack runner](attack-runner.md): operator coverage, private reporting and run lifecycle.
- [Engineering handoff](../docs/aegis/review/engineering-handoff.md#authentication-qualification): owners, oracles and remaining qualification work.
