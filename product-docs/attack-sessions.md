# Attack sessions

## Summary

Authenticated assessments establish a session with a fresh magic link for each run. The resulting session cookie, not the magic link, authenticates subsequent work. This contract lets a bounded assessment continue beyond the magic link's short lifetime without changing identity.

## Terms

- **Session cookie jar**: the run-local browser context or equivalent cookie store that retains the application's actual session cookie and server-issued updates.
- **Session maintenance**: the application's supported activity or refresh operation that preserves the established authenticated session for the run duration.

## Decisions

### The ready worker logs in immediately

The runner prepares its worker before minting and retrieving a fresh magic link. The worker redeems the link immediately, once, before its 15-minute expiry. Unattended minting and retrieval belong to the runner; manual URL pasting is not the recurring service contract.

We use a fresh link for each run rather than a long-lived cookie secret, so each assessment has a distinct authentication establishment event. The resulting session cookie is retained in that run's cookie jar with its application-defined HttpOnly, domain, path, and security behavior.

### One logical session lasts for the assessment

The first path uses an authorized non-admin developer identity. Preflight validates the expected identity, role, and party context. Invalid credentials or an unexpected identity stop the assessment before attack work.

The default maintenance interval is 300 seconds, with validation before high-impact activity. Maintenance uses the same cookie jar and retains server-issued cookie updates. The selected operation must demonstrably maintain authentication beyond 15 minutes and through the configured run duration. A successful health check or a last-seen update alone does not prove that lifetime requirement.

The worker does not reopen the magic link, clear cookies, sign out, switch to Google SSO, or remint credentials to imitate continuity. A new login is a separately identified restart with fresh preflight.

### Session loss stops active work

When session validity becomes unknown, active work pauses while bounded diagnosis runs. Confirmed loss stops active assessment, records `SESSION_LOST_NEED_FRESH_MAGIC_LINK`, and preserves completed evidence and unfinished coverage. The assessment never silently continues anonymously. This prevents evidence from being attributed to the wrong security context.

### Edge denial is distinct from session loss

The adapter classifies edge challenges/blocks separately from application sign-in or authorization failures. Do not infer that a session expired from a challenge page or a generic HTTP error. A confirmed edge denial records `EDGE_CONTROL_BLOCKED`; insufficient evidence records `ACCESS_FAILURE_UNCLASSIFIED`. Stop active assessment with incomplete coverage when bounded diagnosis cannot establish application reachability, preserving prior confirmed observations. Do not remint or repeatedly redeem a magic link to work around an edge denial. A scoped party traffic policy must be supplied by the environment owner and recorded by the runner; this adapter cannot change edge controls itself.

### Credentials remain ephemeral

Live links, cookies, and authentication headers stay in the private run context. They are absent from committed files, retained reports, tickets, and logs. Run-local credential material is removed during cleanup. Evidence records the validation result without credential values.

## Contracts

### Authentication adapter

The adapter provides unattended issuance/retrieval, immediate redemption, session validation, and a verified maintenance operation. Authentication establishment produces either a validated run-local cookie session or `PREFLIGHT_FAILED`. No assessment begins after preflight failure.

The implementation uses a supported issuance path. It does not assume the app's test-only retrieval shortcut is available on party or that signing a JWT registers a usable magic token.

## Product dimensions

| Dimension            | Decision                                                                                          | Source        |
| -------------------- | ------------------------------------------------------------------------------------------------- | ------------- |
| Access               | The first path uses an authorized non-admin developer test identity; preflight checks it.         | This document |
| Seats and plans      | Not applicable; this contract does not grant a customer entitlement.                              | This document |
| Billing and metering | Not applicable; authentication is not a separate customer meter.                                  | This document |
| Limits               | Magic links expire after 15 minutes; default session maintenance runs every 300 seconds.          | This document |
| Security and data    | A private run-local cookie jar retains the session; credentials do not enter durable evidence.    | This document |
| Deployment           | The issuance and maintenance mechanisms must work on the authorized party environment.            | This document |
| Interfaces           | Magic-link issuance/retrieval, application sign-in, identity validation, and session maintenance. | This document |

## Alternatives considered

### Reusing the magic link or a long-lived cookie

A magic link establishes a session once; it is not a renewable session credential. A long-lived cookie secret bypasses fresh establishment and is not the primary authentication mechanism.

## Appendix

The inspected app commit establishes three relevant facts: magic tokens are registered and single-use with a 15-minute lifetime; the normal mint route delivers email and returns success rather than the token; sign-in issues a separate HttpOnly cookie. Session activity updates last-seen state, which alone does not establish sliding expiry. These facts constrain adapter selection; they do not demonstrate unattended party authentication.

## Resources

- [MagicTokenService](https://github.com/foxglove/app/blob/61452baeb3a610d0c12922600661bb5199f4e61a/packages/api/src/services/MagicTokenService.ts): token registration, lifetime, and redemption.
- [Magic-link route](https://github.com/foxglove/app/blob/61452baeb3a610d0c12922600661bb5199f4e61a/packages/api/src/routes/internal/auth/magic-link/index.ts): normal email delivery and test-only retrieval behavior.
- [Sign-in route](https://github.com/foxglove/app/blob/61452baeb3a610d0c12922600661bb5199f4e61a/packages/api/src/routes/v1/signin/index.ts): session-cookie creation.
- [SessionService](https://github.com/foxglove/app/blob/61452baeb3a610d0c12922600661bb5199f4e61a/packages/api/src/services/SessionService.ts): session activity handling.

## References

None.
