# Authenticated Access Chains

Attack-path ID: authenticated-access-chains

Parent: Aegis → Attack → Attack Runner

This path assesses authorization boundaries and connected exploit chains from one established non-admin developer session on the authorized party environment. It does not define the runner's harness, model, money budget, or duration; those are explicit run settings supplied by the runner.

## Inputs and preconditions

The runner provides the authorized party targets/test identity, resolved limits, a private run-local evidence directory, the approved edge-access profile and a fresh magic link in a private run-local copy. The trusted runner owns guarded artifact persistence; do not request storage credentials or publish evidence to public workflow artifacts, logs, job summaries or comments. The committed file retains this placeholder:

REPLACE_WITH_FRESH_MAGIC_LINK

The runner prepares the sandbox, then retrieves this run's short-lived link from a private handoff supplied by a separate company-owned issuer. Attack Runner has no superadmin access. Do not request issuer or storage credentials, invent a mint endpoint, use a test-only retrieval shortcut on party, or ask a human to log in on a different machine as a substitute. If required inputs are unavailable, report preflight failure.

The harness adapter must pass this file's resolved contents to the worker. The run record identifies the attack path, committed Git revision/content hash, and resolved harness/model configuration without exposing credentials.

## 1. Establish the session immediately

Open the freshly issued magic link immediately in the prepared sandbox/headless browser. The link expires after 15 minutes and is single-use. Complete login once; do not wait for expiry.

Retain the issued session cookie in this run's browser context/cookie jar. Use the application's real session-cookie mechanism, preserving HttpOnly/domain/path/security behavior; the magic-link JWT is not the session credential.

Validate the expected authenticated non-admin developer identity using the configured party session endpoint (initially /v1/me). An application sign-in error, expired/invalid link, wrong identity/role, or failed validation is PREFLIGHT_FAILED. Classify an edge challenge/block separately as described below; an edge response alone does not prove invalid credentials. On failed validation or unresolved edge access, stop the assessment. Do not continue anonymously.

Before supplying this link, the trusted runner adapter checks the handoff's declared authentication mode against the authorized profile. After login, the adapter must verify the actual session mode and starting identity from application evidence, record mode/coverage limitations in private run provenance, and explicitly signal that preflight passed. Wait for that signal before any attack activity; a missing or failed signal stops assessment. The worker does not receive the handoff envelope or own this mode comparison. A valid non-admin starting session that gains privileges through a demonstrated exploit remains exploit evidence, not an invalid starting identity.

Do not log the live magic link, cookie, or authentication headers. Evidence should report identity/role validation without credential values.

## 2. Maintain that session

After establishment, all authenticated activity uses the same cookie session. Preserve cookie-jar updates returned by the server; do not replace it with a fresh anonymous browser profile.

The runner/adapter supplies the verified application maintenance operation. Default cadence is every 300 seconds, plus validation before a high-impact chain. This operation must keep the established session usable, not merely record a successful health check. Record successful checks as SESSION_OK without credentials.

Do not re-open the original magic link, mint another link to imitate session continuity, clear cookies, sign out, or use Google SSO during this run. A replacement cookie issued by the server as part of normal session maintenance is retained in the same jar.

If maintenance fails or session validity becomes unknown, suspend active assessment while the runner diagnoses within its bounded policy. A confirmed lost/revoked session emits SESSION_LOST_NEED_FRESH_MAGIC_LINK and stops active work. Preserve completed observations and unfinished coverage. A new login requires a separately identified restart and fresh preflight; never silently substitute an anonymous run.

### Edge-access failures

Use the runner's response classification. A confirmed edge challenge/block emits EDGE_CONTROL_BLOCKED; insufficient attribution emits ACCESS_FAILURE_UNCLASSIFIED. A generic 403/429 is not by itself proof of Cloudflare blocking or application denial. Preserve the phase, affected surface, redacted signal/request identifier and observed counts for the private summary. Suspend work and use only the runner's bounded diagnosis policy; if application reachability remains unavailable, stop with incomplete coverage. Do not evade challenges, change edge policy, repeatedly redeem links or continue anonymously. Preserve completed positive evidence, and never turn an edge block into a no-issue result or an exploit ticket by itself.

## 3. Follow the authenticated attack path

1. Establish the actor, role, organization context, and authorized target boundary.
2. Map surfaces reachable by that actor and record expected authorization boundaries.
3. Validate whether the actor can cross role, tenant, or resource boundaries under the authorized non-destructive test scope. Prioritize authorization flaws, object access, session/token handling, sharing and file flows, and administrative/internal controls.
4. For each confirmed weakness, investigate whether it enables a further authorized step. Record the prerequisite that each step creates for the next.
5. Demonstrate impact with the minimum evidence necessary. Stop before irreversible damage; distinguish demonstrated effects from controls that were only reachable and actions not executed.
6. Identify the corrective behavior required to break the exploit chain and how engineering can verify that correction.

A chain can cross services or repository boundaries. Repository boundaries do not terminate investigation within the authorized target scope and do not split one exploit into separate tickets. Prior-run findings are not assumed; re-establish required evidence in this run or cite a supplied artifact explicitly.

## 4. Boundaries and stop conditions

Only explicitly authorized targets within \*.foxglove.party are in scope. The supplied target set limits the wildcard; it is not permission to assess every reachable host. Production, non-party services, and other unapproved destinations are excluded even when returned by a target. Do not follow a redirect or pivot outside the authorized boundary.

Preserve the source policy against permanent damage: no mass deletion, billing/payment changes, IAM wiping, destructive encryption, or denial-of-service flooding. Use controlled test data and non-destructive evidence. A reachable endpoint or HTTP success alone is not proof that an unexecuted damaging action would succeed.

Honor the supplied time and spend limits and stop signals. Stop active work when a limit is reached or authentication is lost; preserve partial evidence and label untested or interrupted work. Runtime limits and target enforcement are the runner's responsibility as well as constraints on this instruction body.

## 5. Exploit evidence and ticket material

Produce a complete list of actionable exploits irrespective of repository. For every proposed ticket supply:

- The weakness, affected authorization boundary/surface, observed impact, severity, and qualified production-impact assessment.
- Preconditions and the actor/session role, with secrets omitted.
- An ordered activity chain: action → relevant request or operation → observed result → evidence reference → what became possible next.
- Confirmed steps, blocked steps, and dangerous actions not executed, clearly distinguished.
- What must be fixed to prevent the exploit; include all affected components in the remediation checklist when the chain crosses services/repos.
- How to re-test the end-to-end exploit after remediation.
- Run/artifact references and known affected components/repos as metadata; unknown repository ownership is allowed.
- A structured causal chain with actor/resource relationships, logical surface and operation, expected boundary, observed capability transition, prerequisites, and evidence. Preserve semantic dependencies; do not invent an identity from a title or prose hash. The reconciler determines the stable exploit identity before opening tickets.

One independently actionable exploit has one ticket proposal even if remediation spans repositories. Separate independent exploits may have linked proposals, each with its own evidence chain and remediation. The reconciler owns matching to existing Linear tickets; the harness supplies evidence and must not create tickets or send Slack messages itself.

## 6. Report contract

Retain the source report sections:

- Preflight — PASS/FAIL and redacted identity/role validation.
- Session keep-alive — mechanism, cadence, checks, and loss events.
- Edge access — approved policy reference, observed challenge/block/unclassified-failure counts, phase, available request identifiers and affected coverage; omit sensitive request values.
- Findings — actionable exploits and complete ticket material.
- Chains — ordered demonstrated paths, prerequisites, blocked steps, and evidence.
- Dangerous but not executed — reachable controls versus unperformed effects.
- Coverage map — tested, untested, and interrupted surfaces.
- Budget leftover — remaining work and time/spend information actually available.

On preflight failure, report the failure and stop. On interruption/session loss, retain completed evidence and mark coverage incomplete. If an exploit was not observed, report “not observed in this run,” with attempted coverage, conditions, and why work ended. This applies even to a completed targeted re-test: it never proves the exploit is absent or fixed. Preserve any valid positive evidence despite later non-observation.
