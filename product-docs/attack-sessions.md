# Attack sessions

## Summary

Authenticated assessments establish a session with a fresh magic link for each run. A separate company-owned issuer delivers the link through private temporary storage; Attack Runner has no superadmin access. The resulting session cookie authenticates subsequent work beyond the link's short lifetime.

Scheduled authentication requires no employee login, personal mailbox, copied cookie, or weekly URL pasting. It must continue to work when the person who configured it leaves. The responsible operator still observes and can stop the assessment as specified in [Attack runner](attack-runner.md); operator coverage is distinct from authentication.

## Terms

- **Session cookie jar**: the run-local browser context or equivalent cookie store that retains the application's actual session cookie and server-issued updates.
- **Session maintenance**: the application's supported activity or refresh operation that preserves the established authenticated session for the run duration.
- **Login issuer**: a separately deployed service that holds minting authority and resolves the permitted test identity from trusted configuration.
- **Login handoff**: one private temporary object containing a fresh link and its run/attempt binding. It is separate from retained evidence.
- **Authentication mode**: the established session's provenance, such as ordinary magic-link login or superadmin impersonation; matching the target member does not make these modes equivalent.

## Decisions

### Minting authority stays outside Attack Runner

The issuer, scheduler and test account use company-owned identities with a team responsible for provisioning, recovery and revocation. Attack Runner, including its controller and auth adapter, receives no superadmin session, signing key, or permission to act as the issuer. It cannot change the issuer's deployment, identity mapping or access policy. The issuer is not a privileged step or helper on the Attack Runner worker.

The scheduler authorizes the run, attempt and profile, then requests issuance after the browser is ready. The issuer maps that authorization to an explicitly allowed party test identity. A runner-supplied email, member, org, redirect or storage destination cannot select a different identity or expand scope. Knowing a run ID is not authorization. Duplicate readiness signals do not create extra links or parallel attempts.

The harness receives the test login material and session only. It receives neither the issuer's credentials nor the runner's storage credentials. This boundary applies to mounted files, environment variables, cloud metadata and service-account impersonation permissions, not just prompt instructions.

### A private handoff belongs to one run and attempt

Use a dedicated private temporary GCS bucket for login handoffs, separate from the evidence and durable reconciliation stores. Publish an immutable object per authorized run/attempt; do not use a shared latest-link object. Attack Runner can read only its assigned object for a bounded time, with no list, write, delete, bucket-administration or other-run access. A secret-looking object name alone is not access control.

The runner may also read only the redacted cleanup-status record for its own authorized run/attempt. It cannot list other status records, read another attempt's status or handoff reference, or write/delete any status record. The issuer alone writes these records. This read-only status access grants no issuer-control or handoff-deletion authority; the harness receives neither status-store credentials nor access to other attempts.

The handoff binds the link to its run, attempt, approved profile, expected member/org, declared authentication mode, and issuance/expiry times. Before redemption, the trusted runner adapter checks these against its independently authorized configuration. After redemption, it verifies the actual identity and session mode using application-derived evidence before releasing attack work. The issuer's mode label is not proof of the resulting session mode. An untrusted payload cannot redefine the expected identity, mode or target.

### The ready worker logs in immediately

The runner prepares its worker before the separate issuer mints a fresh magic link. The worker retrieves and redeems the link immediately, once, before its 15-minute expiry. If delivery leaves insufficient time for bounded login and validation, fail preflight; do not begin attack work or ask a person to paste another link.

We use a fresh link for each run rather than a long-lived cookie secret, so each assessment has a distinct authentication establishment event. The resulting session cookie is retained in that run's cookie jar with its application-defined HttpOnly, domain, path, and security behavior.

Missing, stale, cancelled, wrongly bound or unexpected-mode handoffs stop preflight. A read retry may retrieve the same object before redemption, but an uncertain redemption is not retried blindly. End that attempt and require a separately identified, bounded restart with fresh authorization and preflight. A restart never resets the enclosing job's time or spend limit. There is no fallback to a personal credential or anonymous assessment.

### Authentication mode must match the intended coverage

The default contract remains an ordinary non-admin developer login. Superadmin can return a magic link directly, but the inspected implementation creates an impersonation session and takes a different sign-in branch. Private storage does not change those semantics.

**Decision pending app/auth review:** whether a separately issued impersonation session is acceptable for Authenticated Access Chains, and which sign-in or authorization checks it cannot cover. Until explicitly selected in the product contract and qualified, it is not a permitted substitution for ordinary login. If ordinary login is retained, the issuer needs a supported scoped mint operation or unattended company-owned mailbox integration. Both retain the same private handoff boundary.

Record the selected mode and coverage limitations in private run provenance. A valid non-admin starting session that subsequently demonstrates privilege escalation remains exploit evidence; the starting-identity check must not discard that causal transition.

The adapter must distinguish an impersonation session even when its envelope is incorrectly labelled ordinary. The inspected sign-in implementation emits an impersonation marker in its server response, but `/v1/me` does not expose session source. Capturing that response from the approved application in a fresh browser is a candidate mode check, not a qualified integration. Absence of a marker alone is not sufficient proof of ordinary login. Engineering must qualify both branches and ambiguous/missing evidence; if they cannot be distinguished, a session-bound application signal is a release dependency. Unknown or mismatched mode fails preflight. Worker instructions cannot replace this adapter gate.

### One logical session lasts for the assessment

The first path uses an authorized non-admin developer identity. Preflight validates the expected identity, role, and party context. Invalid credentials or an unexpected identity stop the assessment before attack work.

The default maintenance interval is 300 seconds, with validation before high-impact activity. Maintenance uses the same cookie jar and retains server-issued cookie updates. The selected operation must demonstrably maintain authentication beyond 15 minutes and through the configured run duration. A successful health check or a last-seen update alone does not prove that lifetime requirement.

The worker does not reopen the magic link, clear cookies, sign out, switch to Google SSO, or remint credentials to imitate continuity. A new login is a separately identified restart with fresh preflight.

### Session loss stops active work

When session validity becomes unknown, active work pauses while bounded diagnosis runs. Confirmed loss stops active assessment, records `SESSION_LOST_NEED_FRESH_MAGIC_LINK`, and preserves completed evidence and unfinished coverage. The assessment never silently continues anonymously. This prevents evidence from being attributed to the wrong security context.

### Edge denial is distinct from session loss

The adapter classifies edge challenges/blocks separately from application sign-in or authorization failures. Do not infer that a session expired from a challenge page or a generic HTTP error. A confirmed edge denial records `EDGE_CONTROL_BLOCKED`; insufficient evidence records `ACCESS_FAILURE_UNCLASSIFIED`. Stop active assessment with incomplete coverage when bounded diagnosis cannot establish application reachability, preserving prior confirmed observations. Do not remint or repeatedly redeem a magic link to work around an edge denial. A scoped party traffic policy must be supplied by the environment owner and recorded by the runner; this adapter cannot change edge controls itself.

### Credentials remain ephemeral

Live links exist only in the isolated issuer, the temporary handoff and the private run context. Cookies and authentication headers stay in the contexts that need them. No credential values enter committed files, retained reports, tickets, Slack or logs. Evidence records the validation result without credential values.

An issuer-owned cleanup service deletes the exact handoff object after successful-login acknowledgment, cancellation or expiry; it also removes abandoned handoffs after crashes. Run-local link material is erased after use and other run-local credentials during cleanup. Temporary storage has no version history, soft-delete recovery or retention lock. Its settings do not change the separate evidence-retention policy.

Storage reads are not single-use consumption; application redemption enforces link use. Deleting an object does not revoke an established session. Token expiry remains enforced by the application even if cleanup is delayed. Cleanup has bounded retries, a named owner and visible failure reporting; an expired link is not proof its stored bytes were deleted. A cleanup failure does not erase independently valid exploit evidence.

The issuer owns a durable private, credential-free cleanup record per run/attempt. Its stable reference is derived from the trusted configured issuer-status namespace and the scheduler's canonical run/attempt IDs, using the resource key `attempts/{runId}/{attemptId}/cleanup`. The IDs are encoded as individual path segments. Scheduler and issuer use this same rule; deriving a reference neither creates a record nor authorizes access. The issuer creates the record when it accepts issuance authorization, before minting. It records the handoff reference/generation when known, status (`pending`, `deleted`, `failed`, or `not_created`), update time and sanitized failure reason. `deleted` requires confirmed absence of the expected object generation under the qualified storage policy; `not_created` requires a confirmed failure before publication. Uncertain publication or deletion is never reported as either. The record remains `pending` during bounded retries and becomes `failed` when its configured retry/deadline policy is exhausted. A later confirmed recovery updates that record while preserving the failure history.

When writing its summary, the runner records the observed cleanup status, observation time and stable issuer-record reference for each attempt. An unavailable record is `unknown`, not successful cleanup. The summary is a snapshot: cleanup may finish later, and the issuer record is authoritative for that later outcome. This does not promise a rewrite of the completed summary or add cleanup to the assessment's synchronous lifecycle. Before recurring launch, the issuer team must configure and test a private operational failure destination and transport; their selection is an explicit release dependency. Assessment-summary delivery to Slack remains deferred.

The scheduler may request issuance only after authenticated readiness. The runner may report “issuance was never requested” only when it can establish that it stopped before sending readiness. In that case no issuer record or handoff exists, and the summary intentionally records cleanup status `unknown` with the pre-readiness failure reason rather than fabricating an issuer `not_created` result. Once readiness has been sent, or its transmission is uncertain, the runner cannot infer whether the scheduler requested issuance from a missing object reference or status response. It records `unknown` when the issuer outcome is unavailable and must not use the pre-issuance reason; an available issuer record supplies the observed status instead.

## Contracts

### Authentication adapter

The runner's adapter provides unattended handoff retrieval, immediate redemption, session validation, and a verified maintenance operation. Issuance and storage cleanup belong to the separate issuer service. Authentication establishment produces either a validated run-local cookie session or `PREFLIGHT_FAILED`; the existing edge-failure classifications still apply. No assessment begins after preflight failure.

The implementation uses a supported issuance path. It does not assume the app's test-only retrieval shortcut is available on party or that signing a JWT registers a usable magic token.

### Issuance and handoff lifecycle

```mermaid
sequenceDiagram
    participant S as Trusted scheduler
    participant I as Separate login issuer
    participant G as Private temporary storage
    participant R as Attack Runner
    participant B as Prepared test browser
    S->>S: Derive cleanup reference from configured namespace and run/attempt IDs
    S->>R: Start authorized run and attempt, with stable cleanup-record reference
    R->>B: Prepare browser
    R-->>S: Authenticated readiness
    S->>I: Authorize fixed profile and attempt
    I->>I: Create pending cleanup record at derived reference
    I->>I: Resolve allowed identity and mint fresh link
    I->>G: Create immutable handoff
    G-->>I: Confirm object reference and generation
    I-->>S: Published object reference and generation
    S-->>R: Assigned object and bounded read access
    R->>G: Read exact assigned object
    G-->>R: Link and run binding
    alt Valid binding, declared mode and remaining lifetime
        R->>B: Redeem once in prepared browser
        B-->>R: Application sign-in and session evidence
        R->>R: Validate actual identity and mode
        alt Login, identity and mode validation succeed
            R-->>I: Authenticated success acknowledgment
            I->>G: Delete exact handoff
            R-->>B: Release attack work after adapter preflight passes
            B->>B: Assess using maintained session cookie
        else Login or validation failed, or redemption uncertain
            R-->>S: End attempt, no assessment
            S->>I: Authenticated attempt termination
            I->>G: Cleanup abandoned handoff
        end
    else Missing, expired, cancelled or mismatched handoff
        R-->>S: Fail preflight, no assessment
        S->>I: Authenticated attempt termination or cancellation
        I->>G: Cleanup handoff if present
    end
    Note over I,G: Expiry cleanup also covers crashes and missing acknowledgments
    Note over I,R: Issuer owns cleanup record; summary records status as observed
    Note over R,B: No issuer authority in runner; no cloud credentials in harness
```

Issuance/storage failure is reported by the issuer to the scheduler, which ends the attempt and tells the runner to fail preflight. External cancellation likewise travels from scheduler to both runner and issuer. Lost termination messages are covered by issuer-owned expiry cleanup. The scheduler supplies a stable per-attempt cleanup-record reference at initial bootstrap, even if issuance later fails, and passes the object reference/generation after publication. A missing issuer record remains unknown; it is not proof that no handoff exists. The issuer authenticates acknowledgments against the authorized run/attempt; an acknowledgment cannot change the deletion target. Cleanup records reflect the storage operation's confirmed outcome or explicit failure, not merely a sent delete request. Retry and cleanup failures follow the rules above, including visible failure without discarding completed evidence.

## Product dimensions

| Dimension            | Decision                                                                                         | Source        |
| -------------------- | ------------------------------------------------------------------------------------------------ | ------------- |
| Access               | Company-owned non-admin test identity; separate issuer; no superadmin access in Attack Runner.   | This document |
| Seats and plans      | Not applicable; this contract does not grant a customer entitlement.                             | This document |
| Billing and metering | Not applicable; authentication is not a separate customer meter.                                 | This document |
| Limits               | Magic links expire after 15 minutes; default session maintenance runs every 300 seconds.         | This document |
| Security and data    | Per-attempt private handoff and run-local cookie jar; no credentials in retained evidence.       | This document |
| Deployment           | Separate issuer and runner identities; unattended bootstrap and maintenance on authorized party. | This document |
| Interfaces           | Authorized readiness, private handoff, sign-in, identity validation, maintenance and cleanup.    | This document |

## Alternatives considered

### Reusing the magic link or a long-lived cookie

A magic link establishes a session once; it is not a renewable session credential. A long-lived cookie secret bypasses fresh establishment and is not the primary authentication mechanism.

### Giving the runner superadmin access

Even if Strix cannot see a privileged credential, putting it in Attack Runner's controller grants the runner unnecessary authority. A separately deployed issuer limits the runner to the test login material supplied for its attempt.

### Employee-assisted authentication

Weekly manual minting, personal mailbox access or a saved employee SSO session ties the service to that person's availability and account lifecycle. One-time company-owned provisioning is required; recurring authentication is automated.

## Appendix

The inspected app commit establishes three relevant facts: magic tokens are registered and single-use with a 15-minute lifetime; the normal mint route delivers email and returns success rather than the token; sign-in issues a separate HttpOnly cookie. Session activity updates last-seen state, which alone does not establish sliding expiry. These facts constrain adapter selection; they do not demonstrate unattended party authentication.

Current source inspection also supports investigating a company-owned Google service account signing into superadmin and requesting an impersonation link. The verifier checks a Google-signed token, configured audience, verified email and provisioned membership; the mint route additionally checks elevated permission. Google supports service-account ID tokens with the needed email claims and a supplied audience. This is a feasibility inference, not a live-tested integration or approval of impersonation semantics. Account provisioning, permissions, session behavior and handoff isolation remain release dependencies.

## Resources

- [MagicTokenService](https://github.com/foxglove/app/blob/61452baeb3a610d0c12922600661bb5199f4e61a/packages/api/src/services/MagicTokenService.ts): token registration, lifetime, and redemption.
- [Magic-link route](https://github.com/foxglove/app/blob/61452baeb3a610d0c12922600661bb5199f4e61a/packages/api/src/routes/internal/auth/magic-link/index.ts): normal email delivery and test-only retrieval behavior.
- [Sign-in route](https://github.com/foxglove/app/blob/61452baeb3a610d0c12922600661bb5199f4e61a/packages/api/src/routes/v1/signin/index.ts): session-cookie creation.
- [SessionService](https://github.com/foxglove/app/blob/61452baeb3a610d0c12922600661bb5199f4e61a/packages/api/src/services/SessionService.ts): session activity handling.
- [Superadmin sign-in](https://github.com/foxglove/app/blob/fde9444416d7b4479a15337946170fec3ff4d507/packages/api/src/routes/internal/superadmin/signin/index.ts), [token verification](https://github.com/foxglove/app/blob/fde9444416d7b4479a15337946170fec3ff4d507/packages/api/src/lib/acl.ts), [impersonation minting](https://github.com/foxglove/app/blob/fde9444416d7b4479a15337946170fec3ff4d507/packages/api/src/routes/internal/superadmin/impersonate.ts) and [app sign-in branches](https://github.com/foxglove/app/blob/fde9444416d7b4479a15337946170fec3ff4d507/packages/api/src/routes/v1/signin/index.ts): candidate issuer integration and the authentication-mode distinction.
- [Google service-account ID tokens](https://docs.cloud.google.com/iam/docs/reference/credentials/rest/v1/projects.serviceAccounts/generateIdToken): non-interactive token issuance with audience and email claims.
- [GCS credential access boundaries](https://docs.cloud.google.com/iam/docs/downscoping-short-lived-credentials), [soft delete](https://docs.cloud.google.com/storage/docs/soft-delete) and [lifecycle processing](https://docs.cloud.google.com/storage/docs/lifecycle): handoff isolation and effective deletion behavior.

## References

- [Attack runner](attack-runner.md): operator coverage, private reporting and overall run lifecycle.
