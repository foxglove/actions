# Attack sessions

## Summary

Authenticated assessments establish a session with a fresh ordinary magic link for each run. A company-owned issuer function triggers the application's supported ordinary-login email for the approved test identity and delivers it to a company-owned mailbox. Attack Runner reads the link from that mailbox and signs in; it has no superadmin access. The resulting session cookie authenticates subsequent work beyond the link's short lifetime.

Scheduled authentication requires no employee login, personal mailbox, copied cookie, or weekly URL pasting. It must continue to work when the person who configured it leaves. The responsible operator still observes and can stop the assessment as specified in [Attack runner](attack-runner.md); operator coverage is distinct from authentication.

Attack Runner holds no superadmin, signing, issuer, or mailbox-administration authority. The issuer resolves the test identity from trusted configuration; the runner verifies the actual identity and mode after redemption; and missing, ambiguous, mismatched, expired, or unqualified authentication fails closed.

## Product decisions

Owners marked _proposed_ are derived from application code ownership; the named team has not yet accepted operational ownership of a new issuer service.

| Decision                  | Selected outcome                                                                                                                                                                                                                                                                                                                                                                             | Accountable owner                                                                                 | Accepted coverage/risk                                                                                                                                                                                                                                                                                                                                                                                                                                                              | Qualification evidence                                                                                                                             |
| ------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| Authentication mode       | Ordinary non-admin developer magic-link login is required. A superadmin-issued impersonation session is not a permitted substitute.                                                                                                                                                                                                                                                          | Kumar Pasumarthy (release authority; moves to a team over time)                                   | The assessment covers what an ordinary non-admin developer can reach. It does not cover superadmin-only behavior. Impersonation evidence cannot substitute for ordinary-mode coverage.                                                                                                                                                                                                                                                                                              | Post-redemption mode and identity verification from application-derived evidence; qualification of the mode oracle is executable engineering work. |
| Ordinary-login delivery   | The issuer triggers the supported ordinary magic-link email and delivers it to a company-owned mailbox the runner reads. No scoped mint operation is required, and no new app endpoint is invented.                                                                                                                                                                                          | App/auth code owners (proposed)                                                                   | Delivery depends on email arriving before the link lifetime is too short. A late email fails preflight rather than starting an unauthenticated assessment. Because the magic-link route is public, a party that knows the mailbox address can send a second link into the window and force runs to fail preflight; the run fails closed, and the mailbox address is kept in trusted configuration and not published, which reduces but does not remove this denial-of-service risk. | Unattended two-run and employee-removal qualification (I-01, I-18) with the real mailbox and workload identity.                                    |
| Issuer ownership          | The issuer owner owns the issuer function, the company test identity, its provisioning/rotation/revocation, identity-to-profile mapping, deployment approval, and mailbox access.                                                                                                                                                                                                            | App/auth code owners (proposed): `@foxglove/data-curation-search`, `@wimagguc`, `@dante-foxglove` | A single team would own both the auth surface and the issuer function. There is no separate on-call rotation yet.                                                                                                                                                                                                                                                                                                                                                                   | The named team must accept operational ownership; record the accepting person and date.                                                            |
| Cleanup and alerting      | Not applicable. There is no stored handoff object to delete, so there is no issuer-owned cleanup and no cleanup-failure alert.                                                                                                                                                                                                                                                               | App/auth code owners (proposed; mailbox hygiene only)                                             | A redeemed link is inert; an unredeemed link expires in 15 minutes. Mailbox-message retention is ordinary mailbox hygiene, not a live-credential control.                                                                                                                                                                                                                                                                                                                           | Single-use and expiry are inspected app facts (see [Appendix](#appendix)); concurrent-redemption behavior is qualified before release.             |
| Authentication thresholds | Preflight deadline 5 minutes; minimum remaining link lifetime at retrieval 10 minutes; required authenticated-session duration equals the configured run duration (default 60 minutes, configurable) plus a reporting reserve; maintenance every 300 seconds and before high-impact activity; one bounded in-job restart; at most 2 attempts per job without resetting time or spend limits. | Kumar Pasumarthy                                                                                  | The run duration is a configurable setting so a longer assessment can be scheduled later. The other values are fixed defaults.                                                                                                                                                                                                                                                                                                                                                      | Each value requires runtime qualification against the real application and edge before live release.                                               |
| Release authority         | Kumar Pasumarthy accepts auth coverage and limitations, the unattended issuer path, the actual-mode oracle, full-duration session continuity, issuer/runner/harness isolation, and edge-policy effects. Ownership moves to a team over time.                                                                                                                                                 | Kumar Pasumarthy                                                                                  | A single accountable owner for the first release.                                                                                                                                                                                                                                                                                                                                                                                                                                   | Recorded here; re-recorded when ownership moves to a team.                                                                                         |

## Terms

- **Session cookie jar**: the run-local browser context or equivalent cookie store that retains the application's actual session cookie and server-issued updates.
- **Session maintenance**: the application's supported activity or refresh operation that preserves the established authenticated session for the run duration.
- **Login issuer**: a company-owned function, which may be a scheduled operation of an existing company service, that triggers the supported ordinary magic-link email for the approved test identity. It uses company-owned identities and is outside Attack Runner.
- **Company mailbox**: a mailbox dedicated to the test identity and used for no other purpose, which receives the emailed ordinary magic link. Attack Runner has read-only access to this one mailbox and to no other mailbox; it has no mailbox administration authority.
- **Authentication mode**: the established session's provenance, such as ordinary magic-link login or superadmin impersonation; matching the target member does not make these modes equivalent.
- **Party environment owner**: the team that operates the authorized party environment and its edge controls, and supplies any scoped assessment-traffic policy.

## Decisions

### Issuance authority stays outside Attack Runner

The issuer, scheduler and test account use company-owned identities with a team responsible for provisioning, recovery and revocation. Attack Runner, including its controller and auth adapter, receives no superadmin session, signing key, or permission to act as the issuer. It cannot change the issuer's deployment, identity mapping or access policy. The issuer is not a privileged step or helper on the Attack Runner worker.

The scheduler authorizes the run, attempt and profile, then requests issuance after authenticated readiness, so the worker is already prepared when the link arrives and the adapter's minimum-remaining-lifetime check can pass. The issuer maps that authorization to an explicitly allowed party test identity and triggers the ordinary magic-link email for that identity. A runner-supplied email, member, org or redirect cannot select a different identity or expand scope. Knowing a run ID is not authorization. Duplicate readiness signals do not trigger extra emails or parallel attempts.

The inspected ordinary magic-link route is public: it requires no authentication and emails a link to any supplied address, rate-limited only. Any party, not only the issuer, can therefore trigger a link email to the mailbox. Issuer and runner separation is an operational choice, not a security boundary for issuance. The enforced controls are the dedicated read-only mailbox, single-use and 15-minute expiry, the pre-redemption sender and URL checks below, and post-redemption identity and mode verification. The runner still receives no superadmin, signing, issuer, or mailbox-administration credentials.

The harness receives the test login material and session only. It receives neither the issuer's credentials nor mailbox-administration credentials. This boundary applies to mounted files, environment variables, cloud metadata and service-account impersonation permissions, not just prompt instructions.

### The link is delivered to a company mailbox

The issuer triggers the supported ordinary magic-link email for the approved test identity, addressed to the company mailbox. The mailbox is dedicated to that identity and is used for no other purpose; the runner has read-only access to this one mailbox and to no other. After the worker signals readiness, it requires exactly one ordinary magic link for the approved test identity delivered after that readiness time. Readiness precedes issuance, and the runner observes its own readiness time, so this lower bound needs no timestamp from the issuer. If no message or more than one message matches within the window, the runner fails preflight rather than guessing. Earlier messages hold only redeemed or expired links; single-use and 15-minute expiry are the accepted mitigation for stale messages.

Before redemption, the adapter checks the selected message against trusted configuration, not against values the message asserts about itself:

- The message passes sender authentication from the expected sender. The runner reads the message through a mailbox API and does not see the SMTP connection, so it cannot compute SPF itself. The first release verifies the DKIM signature itself, with `d=` aligned to the application's sending domain. The adapter does not trust an `Authentication-Results` header in the message, because a sender can forge that header with a matching `header.d`. A forged, unsigned or misaligned message fails preflight, and the runner does not open its URL.
- The link host and path match the approved application sign-in URL from trusted configuration. A link to any other host or path fails preflight.
- The remaining lifetime is at least the configured minimum, computed as 15 minutes after the runner's readiness time, not from the message received time or the unverified token claims. Issuance occurs after readiness, so the link expires no earlier than 15 minutes after readiness; the message received time would overstate the remaining lifetime because the token lifetime starts at issuance. The adapter holds no signing key and cannot verify token claims before redemption.

The expected identity and profile come from independently authorized configuration and the dedicated recipient mailbox. The link URL necessarily comes from the message; what is trusted is the configuration the adapter checks it against. The authentication mode is verified only after redemption, from application-derived evidence. An untrusted message cannot redefine the expected identity, mode or target.

The first release runs one weekly assessment with one active attempt at a time, so overlapping runs that could share the mailbox are out of scope; see [Attack runner](attack-runner.md#runs-are-weekly-and-manually-invocable). The scheduler authorizes one attempt; a bounded restart is a new attempt within the original job limits.

### The ready worker logs in immediately

The runner prepares its worker before the issuer triggers the ordinary magic-link email. The worker retrieves the link from the mailbox and, after the pre-redemption checks pass, redeems it immediately, once, before its 15-minute expiry. The adapter requires a configured minimum remaining lifetime, initially 10 minutes, sufficient for bounded login and identity validation. If the email is missing, too old, fails a pre-redemption check, or leaves insufficient lifetime, fail preflight; do not begin attack work or ask a person to paste another link.

We use a fresh link for each run rather than a long-lived cookie secret, so each assessment has a distinct authentication establishment event. The resulting session cookie is retained in that run's cookie jar with its application-defined HttpOnly, domain, path, and security behavior.

Missing, stale, cancelled, wrongly bound or unexpected-mode links stop preflight. A read retry may return the same message before redemption, but an uncertain redemption is not retried blindly. End that attempt and require a separately identified, bounded restart with fresh authorization and preflight. A restart never resets the enclosing job's time or spend limit. There is no fallback to a personal credential or anonymous assessment.

### Authentication mode must match the intended coverage

The product contract is an ordinary non-admin developer login. Superadmin can return a magic link directly, but the inspected implementation creates an impersonation session and takes a different sign-in branch. Email delivery does not change those semantics. A superadmin-generated impersonation session is not a permitted substitution for ordinary login.

Record the selected mode and coverage limitations in private run provenance. A valid non-admin starting session that subsequently demonstrates privilege escalation remains exploit evidence; the starting-identity check must not discard that causal transition.

The adapter must distinguish an impersonation session even when a message is incorrectly presented as ordinary. The inspected sign-in implementation emits an impersonation marker in its server response, but `/v1/me` does not expose session source. Capturing that response from the approved application in a fresh browser is a candidate mode check, not a qualified integration. Absence of a marker alone is not sufficient proof of ordinary login. Engineering must qualify both branches and ambiguous or missing evidence; if they cannot be distinguished, a session-bound application signal is a release dependency. Unknown or mismatched mode fails preflight. Worker instructions cannot replace this adapter gate.

### One logical session lasts for the assessment

The first path uses an authorized non-admin developer identity. Preflight validates the expected identity, role, and party context. Invalid credentials or an unexpected identity stop the assessment before attack work.

The default maintenance interval is 300 seconds, with validation before high-impact activity. Maintenance uses the same cookie jar and retains server-issued cookie updates. The selected operation must demonstrably maintain authentication beyond 15 minutes and through the configured run duration. The run duration is a configurable run setting, initially 60 minutes, so a longer assessment can be scheduled later; maintenance must hold for whatever duration is configured. A successful health check or a last-seen update alone does not prove that lifetime requirement.

The worker does not reopen the magic link, clear cookies, sign out, switch to Google SSO, or remint credentials to imitate continuity. A new login is a separately identified restart with fresh preflight.

### Session loss stops active work

When session validity becomes unknown, active work pauses while bounded diagnosis runs. Confirmed loss stops active assessment, records `SESSION_LOST_NEED_FRESH_MAGIC_LINK`, and preserves completed evidence and unfinished coverage. The assessment never silently continues anonymously. This prevents evidence from being attributed to the wrong security context.

### Edge denial is distinct from session loss

The adapter classifies edge challenges/blocks separately from application sign-in or authorization failures. Do not infer that a session expired from a challenge page or a generic HTTP error. A confirmed edge denial records `EDGE_CONTROL_BLOCKED`; insufficient evidence records `ACCESS_FAILURE_UNCLASSIFIED`. Stop active assessment with incomplete coverage when bounded diagnosis cannot establish application reachability, preserving prior confirmed observations. Do not remint or repeatedly redeem a magic link to work around an edge denial. A scoped party traffic policy must be supplied by the party environment owner and recorded by the runner; this adapter cannot change edge controls itself.

### Credentials remain ephemeral

Live links exist only in the issuer, the company mailbox and the private run context. Cookies and authentication headers stay in the contexts that need them. No credential values enter committed files, retained reports, tickets, Slack or logs. Evidence records the validation result without credential values.

A magic link is single-use and expires 15 minutes after issuance; the application enforces both. A redeemed link is inert, and an unredeemed link expires without action. Run-local link material and other run-local credentials are erased when the run container is torn down. The delivered email remains in the company mailbox until ordinary mailbox retention removes it; because the link is single-use and short-lived, that message holds no reusable credential after redemption or expiry. Mailbox retention is owned by the issuer owner as ordinary mailbox hygiene; it is separate from the evidence-retention policy in [Attack runner](attack-runner.md#evidence-is-retained-in-private-storage).

There is no stored handoff object with an independent lifetime, so there is no issuer-owned deletion step and no cleanup-failure alert. Deleting a mailbox message does not revoke an established session, and application expiry does not depend on message deletion. A mailbox or delivery problem does not erase independently valid exploit evidence.

## Contracts

### Authentication adapter

The runner's adapter provides unattended mailbox retrieval, the pre-redemption sender and URL checks, immediate redemption, session validation, and a verified maintenance operation. Triggering the ordinary magic-link email belongs to the issuer function. The adapter emits exactly one terminal result by the configured preflight deadline: `PREFLIGHT_PASSED` after it verifies the approved mode and starting identity, or `PREFLIGHT_FAILED` after any failure or timeout. `PREFLIGHT_FAILED` includes the failure classification, such as `EDGE_CONTROL_BLOCKED`, `ACCESS_FAILURE_UNCLASSIFIED`, or an application login failure. A missing, ambiguous, forged, wrong-URL, or short-lifetime message is an application login failure, not an edge denial. Attack tools remain blocked unless the result is `PREFLIGHT_PASSED`.

The implementation uses a supported ordinary-login path. It does not assume the app's test-only retrieval shortcut is available on party or that signing a JWT registers a usable magic token.

### Issuance and login lifecycle

```mermaid
sequenceDiagram
    participant S as Trusted scheduler
    participant I as Company issuer function
    participant M as Company mailbox
    participant R as Attack Runner
    participant B as Prepared test browser
    S->>R: Start authorized run and attempt
    R->>B: Prepare browser
    R-->>S: Authenticated readiness
    S->>I: Authorize fixed profile and attempt
    I->>I: Resolve allowed identity
    I->>M: Trigger ordinary magic-link email for the test identity
    R->>M: Read the one matching message for this attempt
    M-->>R: Ordinary magic link
    alt Exactly one match, valid sender, allowed URL and sufficient lifetime
        R->>B: Redeem once in prepared browser
        B-->>R: Application sign-in and session evidence
        R->>R: Validate actual identity and mode
        alt Login, identity and mode validation succeed
            R-->>B: Release attack work after adapter preflight passes
            B->>B: Assess using maintained session cookie
        else Login or validation failed, or redemption uncertain
            R-->>S: End attempt, no assessment
        end
    else Missing, expired, mismatched, ambiguous, or failed sender/URL check
        R-->>S: Fail preflight, no assessment
    end
    Note over I,M: Public ordinary-login route; single-use, 15-minute expiry; no stored handoff object
    Note over R,B: No issuer or mailbox-admin authority in runner; no cloud credentials in harness
```

Issuance failure is reported by the issuer to the scheduler, which ends the attempt and tells the runner to fail preflight. External cancellation likewise travels from scheduler to both runner and issuer. An unredeemed link expires on its own; there is no deletion step to reconcile. The issuer authorizes issuance against the authorized run/attempt; a runner-supplied value cannot change the target identity. A late or missing email fails preflight and starts no assessment; a bounded restart is a new attempt within the original job limits.

## Qualification states

These invariants are selected product behavior. Each still needs runtime qualification with observable evidence before live release. Source inspection is not live qualification. Owners marked _proposed_ are not yet team-accepted.

| Invariant                                                        | Owner                                                           | Observable oracle                                                                                                         | Required evidence                                                                                                                               | Failure behavior                                  | Downstream work gated |
| ---------------------------------------------------------------- | --------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------- | --------------------- |
| Ordinary session established unattended from the company mailbox | App/auth code owners (proposed)                                 | Redeemed session's identity, role and mode from application-derived evidence                                              | Two clean scheduled runs and an employee-removal fixture (I-01, I-18) with the real mailbox and workload identity                               | Preflight fails; no assessment                    | Live scheduled runs   |
| Message is genuine and points at the approved sign-in URL        | Attack Runner owner (proposed: Aegis; interim Kumar Pasumarthy) | DKIM signature verification (`d=` aligned to the sending domain) and a link host/path match against trusted configuration | Forged sender, misaligned domain, forged `Authentication-Results` header, and wrong-host link each fail preflight before redemption (I-20)      | Preflight fails; URL not opened                   | Live scheduled runs   |
| Actual mode is ordinary, not impersonation                       | App/auth code owners (proposed)                                 | Session-bound application signal captured in a fresh browser; `/v1/me` does not expose session source                     | Ordinary and impersonation branches, a mislabelled message, and missing/ambiguous evidence distinguished (I-22)                                 | Preflight fails; attack tools stay gated          | Live scheduled runs   |
| Session holds for the configured run duration                    | App/auth code owners (proposed)                                 | Authenticated request after the 15-minute link expiry and through the configured duration                                 | Maintenance verified beyond 15 minutes and for the configured duration, retaining server cookie updates (I-02)                                  | Session loss stops active work; evidence retained | Live scheduled runs   |
| Runner cannot reach issuer or mailbox authority                  | Attack Runner owner (proposed: Aegis; interim Kumar Pasumarthy) | Attempted issuer/mailbox-admin access is denied; the runner reads no mailbox other than the dedicated one                 | Denied superadmin, signing, mailbox administration, and other-mailbox access; no issuer or mailbox credential in the harness environment (I-19) | Access denied                                     | Live scheduled runs   |
| Link lifetime and single use are effective                       | App/auth code owners (proposed)                                 | Application redemption and expiry behavior                                                                                | Single-use and concurrent-redemption behavior verified against the application (I-20, I-21)                                                     | Preflight fails on an unusable link               | Live scheduled runs   |
| Edge reachability is established or the run fails visibly        | Party environment owner                                         | Reachability from the real runner/harness network path                                                                    | Edge challenge/block classification and scoped-policy recording (I-16)                                                                          | Visible run failure; incomplete coverage          | Live scheduled runs   |

## Product dimensions

| Dimension            | Decision                                                                                                                                                                         | Source        |
| -------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------- |
| Access               | Company-owned non-admin test identity; company issuer function; no superadmin access in Attack Runner.                                                                           | This document |
| Seats and plans      | Not applicable; this contract does not grant a customer entitlement.                                                                                                             | This document |
| Billing and metering | Not applicable; authentication is not a separate customer meter.                                                                                                                 | This document |
| Limits               | Magic links expire after 15 minutes; minimum remaining lifetime at retrieval 10 minutes; preflight deadline 5 minutes; session maintenance every 300 seconds.                    | This document |
| Security and data    | Ordinary link emailed to a dedicated company mailbox with read-only access; sender and URL checked before redemption; run-local cookie jar; no credentials in retained evidence. | This document |
| Deployment           | Company issuer and runner identities; unattended trigger, delivery and maintenance on authorized party.                                                                          | This document |
| Interfaces           | Authorized readiness, ordinary magic-link email, mailbox read, sign-in, identity validation and maintenance.                                                                     | This document |

## Alternatives considered

### Reusing the magic link or a long-lived cookie

A magic link establishes a session once; it is not a renewable session credential. A long-lived cookie secret bypasses fresh establishment and is not the primary authentication mechanism.

### Superadmin-issued impersonation session

Superadmin can return a magic link directly, but its inspected implementation creates an impersonation session on a different sign-in branch. Impersonation cannot exercise the ordinary sign-in and authorization path, and its cookie is window-scoped. It is easier to automate, but ease of automation is not a coverage reason. Ordinary login is required; impersonation is not a permitted substitute.

### Storing the link in shared temporary storage with a deletion step

A design that copies the link into a private per-attempt storage object and has the issuer delete it and record cleanup status adds a stored credential with an independent lifetime, a deletion step, a cleanup record, and a cleanup-failure alerting path. Email delivery to a dedicated mailbox removes all of that. Single-use and 15-minute expiry are the credential-lifetime controls, and a redeemed or expired message holds no reusable credential.

### Giving the runner superadmin access

Even if Strix cannot see a privileged credential, putting it in Attack Runner's controller grants the runner unnecessary authority. A company issuer function limits the runner to the ordinary login material supplied for its attempt.

### Employee-assisted authentication

Weekly manual minting, personal mailbox access or a saved employee SSO session ties the service to that person's availability and account lifecycle. One-time company-owned provisioning is required; recurring authentication is automated through the company issuer function and mailbox.

## Appendix

The inspected app commit establishes these relevant facts: magic tokens are registered and single-use with a 15-minute lifetime; the normal ordinary-login route is public, emails the link and returns success rather than the token, except that in `test` it also returns a `requestId` that retrieves the link from Redis, the test-only retrieval shortcut, not the link itself; a magic token creates an ordinary session unless it carries an impersonator claim; and the impersonation branch, taken only for a token with that claim, sets a distinct session marker. Session activity updates last-seen state, which alone does not establish sliding expiry. These facts constrain adapter selection; they do not demonstrate unattended party authentication.

Source inspection also shows a superadmin impersonation path that returns a link directly and creates an impersonation session. That path is not selected; ordinary login is required. It is recorded here only to explain why the adapter verifies actual mode after redemption.

## Resources

- [MagicTokenService](https://github.com/foxglove/app/blob/61452baeb3a610d0c12922600661bb5199f4e61a/packages/api/src/services/MagicTokenService.ts): token registration, lifetime, and single-use redemption.
- [Magic-link route](https://github.com/foxglove/app/blob/61452baeb3a610d0c12922600661bb5199f4e61a/packages/api/src/routes/internal/auth/magic-link/index.ts): public ordinary-login email delivery and test-only retrieval behavior.
- [Sign-in route](https://github.com/foxglove/app/blob/61452baeb3a610d0c12922600661bb5199f4e61a/packages/api/src/routes/v1/signin/index.ts): ordinary versus impersonation session creation and the session-cookie behavior.
- [SessionService](https://github.com/foxglove/app/blob/61452baeb3a610d0c12922600661bb5199f4e61a/packages/api/src/services/SessionService.ts): session activity handling.
- [Superadmin impersonation minting](https://github.com/foxglove/app/blob/fde9444416d7b4479a15337946170fec3ff4d507/packages/api/src/routes/internal/superadmin/impersonate.ts): the impersonation path that is not selected and the authentication-mode distinction.

## References

- [Attack runner](attack-runner.md): operator coverage, private reporting and overall run lifecycle.
