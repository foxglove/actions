// WP1.2–1.4 — deterministic reconciliation decision engine.
//
// Pure and side-effect free (E1-15): no network, secret reads, ticket writes,
// Slack, harness execution, or workflow changes. Output is an action PROPOSAL,
// never proof of delivery.

import {
  fingerprint,
  normalizeChain,
  FINGERPRINT_VERSION,
} from "./normalize.mjs";

export class PlannerInputError extends Error {
  constructor(message) {
    super(message);
    this.name = "PlannerInputError";
  }
}

const TICKET_LABELS = ["Bug", "pentesting", "harness"];

function decision(fields) {
  const d = {
    observationId: fields.observationId ?? null,
    outcome: fields.outcome,
    reason: fields.reason ?? "",
    exploitIdentity: {
      exploitId: fields.exploitId ?? null,
      matchReason: fields.matchReason ?? "",
    },
    target: fields.target ?? { type: "none", issueId: null },
    proposedActions: fields.proposedActions ?? [],
    evidenceReferences: [...(fields.evidenceReferences ?? [])],
    notificationEligible: fields.notificationEligible ?? false,
    neededEvidence: [...(fields.neededEvidence ?? [])],
  };
  if (fields.fixClaimRef !== undefined) d.fixClaimRef = fields.fixClaimRef;
  return d;
}

function ticketMaterial(obs, fp, exploitId) {
  const e = obs.exploit ?? {};
  const repos = e.affectedRepositories ?? [];
  return {
    exploitId: exploitId ?? null,
    fingerprintVersion: FINGERPRINT_VERSION,
    normalizedChain: normalizeChain(e.chain) ?? [],
    labels: [...TICKET_LABELS],
    severity: e.severity ?? null,
    productionImpact: e.productionImpact ?? {
      value: "unknown",
      rationale: "not established",
    },
    affectedSurfaces: [...(e.affectedSurfaces ?? [])],
    ownership: repos.length ? [...repos] : "unknown",
    remediation: [...(e.remediation ?? [])],
    retestExpectations: e.retestExpectations ?? null,
  };
}

export function plan(input) {
  // Structurally unreadable input fails explicitly (acceptance.md:33) — never a
  // silent empty success.
  if (input === null || typeof input !== "object" || Array.isArray(input)) {
    throw new PlannerInputError("input must be an object");
  }
  if (typeof input.run !== "object" || input.run === null) {
    throw new PlannerInputError("input.run is required");
  }
  if (!Array.isArray(input.observations)) {
    throw new PlannerInputError("input.observations must be an array");
  }
  if (
    input.existingIssues !== undefined &&
    !Array.isArray(input.existingIssues)
  ) {
    throw new PlannerInputError("input.existingIssues must be an array");
  }

  const run = input.run;
  const runEnv = run.targetEnvironment;
  const processedIds = new Set(
    (input.processedEvents ?? []).map((e) => e.eventId).filter(Boolean),
  );
  const processedKeys = new Set(
    (input.processedEvents ?? []).map((e) => e.key).filter(Boolean),
  );
  const existingIssues = input.existingIssues ?? [];
  const seenThisRun = new Set();
  const decisions = [];
  const notObserved = [];

  for (const obs of input.observations) {
    const observationId = obs?.observationId ?? null;

    // --- non-observation: summary-only, zero ticket writes ---
    if (obs?.kind === "non-observation") {
      const exploitId = obs.retestTarget?.exploitId ?? null;
      const issueId = obs.retestTarget?.issueId ?? null;
      const status = obs.execution?.status ?? "not-attempted";
      decisions.push(
        decision({
          observationId,
          outcome: "not-observed",
          reason:
            "Run did not observe the tracked exploit; not an absence or fix claim. A resolved ticket receives no write.",
          exploitId,
          matchReason: obs.retestTarget ? "re-test target" : "",
        }),
      );
      notObserved.push({
        observationId,
        exploitId,
        issueId,
        executionStatus: status,
        reason: obs.execution?.stopReason ?? "not observed in this run",
        // Only a completed re-test actually attempted the tested surfaces; an
        // interrupted/not-attempted re-test must not claim that coverage (M7).
        attemptedCoverage:
          status === "completed" ? [...(run.coverage?.tested ?? [])] : [],
        edgeClassification: run.edgeAccess?.classification ?? "none",
        evidenceReferences: [...(obs.evidence?.references ?? [])],
      });
      continue;
    }

    // --- unknown / missing kind: not a positive; route to triage ---
    if (obs?.kind !== "confirmed-positive") {
      decisions.push(
        decision({
          observationId,
          outcome: "unresolved",
          reason: `Unknown observation kind '${obs?.kind ?? "(missing)"}'; not treated as a positive.`,
          matchReason: "unknown kind",
          neededEvidence: ["a recognized observation kind"],
        }),
      );
      continue;
    }

    // --- invalid / ambiguous required state: unresolved, no action ---
    if (obs.validity !== "valid") {
      const invalid = obs.validity === "invalid-evidence";
      decisions.push(
        decision({
          observationId,
          outcome: "unresolved",
          reason: invalid
            ? "Required evidence is invalid; no speculative creation, merge, or lifecycle action."
            : "Exploit identity is ambiguous; routed to triage without merge or creation.",
          matchReason: "identity not established",
          neededEvidence: [
            invalid
              ? "request and observed result for the unproven transition"
              : "disambiguating evidence to establish a single exploit identity",
          ],
        }),
      );
      continue;
    }

    // --- valid confirmed positive ---
    const fp = fingerprint(obs.exploit?.chain, runEnv);
    const evidenceReferences = obs.evidence?.references ?? [];
    if (fp === null) {
      decisions.push(
        decision({
          observationId,
          outcome: "unresolved",
          reason:
            "Chain lacks structured semantics; identity cannot be established from prose.",
          matchReason: "no structured semantics",
          evidenceReferences,
          neededEvidence: [
            "structured causal-chain semantics for every transition",
          ],
        }),
      );
      continue;
    }

    // Match on the re-computed fingerprint of the stored structured chain, or on a
    // recorded alias. Re-fingerprinting both sides with the current normalizer keeps
    // identity stable across a fingerprint-version change; aliases cover a ticket that
    // only stored a prior-version fingerprint string (E1-20).
    const matches = existingIssues.filter((iss) => {
      const issFp = fingerprint(iss.normalizedChain, iss.targetEnvironment);
      if (issFp !== null && issFp === fp) return true;
      return Array.isArray(iss.fingerprintAliases) && iss.fingerprintAliases.includes(fp);
    });

    if (matches.length > 1) {
      decisions.push(
        decision({
          observationId,
          outcome: "unresolved",
          reason:
            "Multiple plausible exploit matches; ambiguous, routed to triage.",
          matchReason: "multiple plausible matches",
          evidenceReferences,
          neededEvidence: [
            "disambiguating evidence to select a single existing ticket",
          ],
        }),
      );
      continue;
    }

    // Idempotency key per (run, exploit) so a retry with a regenerated/absent
    // eventId within scope is still recognized (M3). Cross-run durable dedup is
    // Engineering 2's responsibility (handoff).
    const derivedKey = `${run.runId}:${fp}`;
    const replayed =
      (obs.eventId && processedIds.has(obs.eventId)) ||
      processedKeys.has(derivedKey);
    const duplicateInRun = seenThisRun.has(fp);

    let outcome;
    let target;
    let exploitId = null;
    let matchReason;
    let eligible = false;
    let baseActions;
    let fixClaimRef;

    if (matches.length === 0) {
      outcome = "new";
      matchReason = "no candidate existing ticket";
      target = { type: "new-issue", issueId: null };
      eligible = true;
      baseActions = [
        {
          type: "create-ticket",
          ticketMaterial: ticketMaterial(obs, fp, null),
        },
      ];
    } else {
      const iss = matches[0];
      exploitId = iss.exploitId ?? null;
      target = { type: "existing-issue", issueId: iss.issueId };
      const state = iss.state;
      const claimed = iss.fixClaim?.claimed === true;
      fixClaimRef = iss.fixClaim?.reference ?? null;

      if (state === "unknown" || state === undefined || state === null) {
        // Unknown required state for a write -> unresolved (handoff decision table).
        decisions.push(
          decision({
            observationId,
            outcome: "unresolved",
            reason:
              "Existing ticket state is unknown; no write without a known state.",
            exploitId,
            matchReason: "unknown ticket state",
            target,
            evidenceReferences,
            neededEvidence: [`current state of ${iss.issueId}`],
          }),
        );
        continue;
      }

      if (state === "resolved") {
        if (!claimed) {
          // Resolved with no explicit fix claim: do not infer a contradiction.
          decisions.push(
            decision({
              observationId,
              outcome: "unresolved",
              reason:
                "Resolved ticket carries no explicit fix claim to contradict; routed to triage rather than a speculative reopen.",
              exploitId,
              matchReason: "resolved without fix claim",
              target,
              evidenceReferences,
              fixClaimRef,
              neededEvidence: [
                `explicit fix-claim reference for ${iss.issueId}`,
              ],
            }),
          );
          continue;
        }
        outcome = "claimed-fixed-reproduces";
        matchReason =
          "same normalized causal chain as the closed ticket with a fix claim";
        eligible = true;
        baseActions = [{ type: "append-evidence" }, { type: "reopen-ticket" }];
      } else if (claimed) {
        // Open ticket that still carries a fix claim: contradiction, stays open.
        outcome = "claimed-fixed-reproduces";
        matchReason =
          "same normalized causal chain as the open ticket with a fix claim";
        eligible = true;
        baseActions = [{ type: "append-evidence" }];
      } else {
        outcome = "rediscovered-open";
        matchReason = "same normalized causal chain as the open ticket";
        eligible = false;
        baseActions = [{ type: "append-evidence" }];
      }
    }

    // Count once per exploit per run; replay or in-run duplicate => no mutation.
    let actions;
    if (replayed || duplicateInRun) {
      actions = [{ type: "none" }];
      eligible = false;
      // A second sighting in the same run is a rediscovery, not a new ticket.
      if (duplicateInRun && outcome === "new") {
        outcome = "rediscovered-open";
        matchReason = "duplicate of an exploit already identified in this run";
      }
    } else {
      actions = [
        ...baseActions,
        { type: "increment-confirmed-count", amount: 1 },
      ];
    }
    seenThisRun.add(fp); // mark seen even on replay so a later same-run dup cannot re-count

    decisions.push(
      decision({
        observationId,
        outcome,
        reason: reasonFor(outcome),
        exploitId,
        matchReason,
        target,
        proposedActions: actions,
        evidenceReferences,
        notificationEligible: eligible,
        ...(fixClaimRef !== undefined ? { fixClaimRef } : {}),
      }),
    );
  }

  const unresolved = decisions
    .filter((d) => d.outcome === "unresolved")
    .map((d) => d.observationId);
  const runSummary = {
    batchStatus: unresolved.length ? "partial" : "complete",
    coverage: run.coverage ?? { tested: [], untested: [], interrupted: [] },
    unresolved,
    notObserved,
    edgeAccess: run.edgeAccess ?? { classification: "none" },
  };
  if (run.completion?.stopReason)
    runSummary.stopReason = run.completion.stopReason;

  return { runId: run.runId ?? null, decisions, runSummary };
}

function reasonFor(outcome) {
  switch (outcome) {
    case "new":
      return "Valid confirmed positive; identity established; no existing match.";
    case "rediscovered-open":
      return "Valid confirmed positive; exactly one open match on the normalized causal chain.";
    case "claimed-fixed-reproduces":
      return "Valid confirmed positive contradicts an explicit fix claim; reopen only if closed, never a duplicate.";
    default:
      return "";
  }
}
