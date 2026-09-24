# Attack paths

## Summary

An **attack path** is a named, versioned set of instructions that defines an assessment's progression, authorized boundaries, stop conditions, and evidence requirements. The harness consumes a file from Git so an operator can reproduce what a run was instructed to do.

## Decisions

### Each path has a stable identity and its own file

Paths live at `docs/aegis/attacks/<attack-path-id>/instructions.md`. The first path is **Authenticated Access Chains**, with ID `authenticated-access-chains`. Additional paths use distinct IDs and files. A workflow selects a path; it does not embed another copy of the prompt in YAML.

This structure makes instructions reviewable in Git and prevents divergence between manual and scheduled runs. The selected instructions are authoritative for path mechanics; summaries do not override them.

### Paths are independent of harness and model selection

Harness, model, spend, and duration belong to the run profile. The path specifies behavior and accepts those resolved settings as inputs. The adapter passes the selected file contents to the harness. Changing the harness does not require rewriting the path's product intent.

### Authenticated Access Chains follows connected authorization failures

The first path starts from a validated non-admin developer session and maintains that session. It maps expected boundaries, tests authorized role/tenant/resource crossings, follows prerequisites into further permitted steps, and records the complete chain and corrective behavior.

Only explicitly authorized `*.foxglove.party` targets are in scope. A wildcard is a maximum boundary, not permission to assess every reachable host. Redirects and pivots do not expand the target set. The path avoids permanent damage, mass deletion, payment changes, IAM wiping, destructive encryption, and denial-of-service flooding. Reachability or HTTP success alone does not demonstrate an unexecuted destructive effect.

An exploit can cross services and repositories. The path follows its authorized chain and supplies complete ticket material rather than splitting by repository. The harness reports evidence; reconciliation owns ticket matching and external delivery.

## Contracts

### Instruction resolution

The runner resolves the selected Git revision and committed-content hash, copies the instruction file into the private run context, and substitutes ephemeral authentication material there. The committed placeholder remains unchanged. The run record identifies the path, revision, and hash without retaining secrets.

### Path inputs and outputs

Inputs include the authorized target set and identity, resolved runtime limits, evidence destination, and authentication/maintenance profile. Missing required inputs cause preflight failure.

Outputs contain preflight, session maintenance, findings, ordered chains, dangerous actions not executed, coverage, and available time/spend information. Interrupted work is explicit. Every actionable exploit includes evidence, remediation, and end-to-end re-test expectations.

## Product dimensions

| Dimension            | Decision                                                                                       | Source                                               |
| -------------------- | ---------------------------------------------------------------------------------------------- | ---------------------------------------------------- |
| Access               | Instructions operate within the supplied target authorization and first-path test identity.    | This document, [Attack sessions](attack-sessions.md) |
| Seats and plans      | Not applicable; paths are internal assessment assets.                                          | This document                                        |
| Billing and metering | Paths honor the supplied run budget; they do not define a billing meter.                       | This document                                        |
| Limits               | Paths obey the supplied time/spend bounds and authentication stop signals.                     | This document                                        |
| Security and data    | Git contains placeholders; ephemeral secrets stay in the run context and evidence is redacted. | [Attack sessions](attack-sessions.md)                |
| Deployment           | The first path is restricted to explicitly authorized party targets.                           | This document                                        |
| Interfaces           | One `instructions.md` file per path, selected and passed through a harness adapter.            | This document                                        |

## Resources

- [Authenticated Access Chains instructions](../docs/aegis/attacks/authenticated-access-chains/instructions.md): the first runtime instruction body.

## References

- [Attack sessions](attack-sessions.md): The first path establishes and maintains one authenticated session.
- [Exploit findings](exploit-findings.md): The path supplies a full activity chain and remediation for each exploit, independent of repository ownership.
