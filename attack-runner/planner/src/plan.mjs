// WP1.2–1.4 — deterministic reconciliation decision engine.
//
// Pure and side-effect free (E1-15): no network, secret reads, ticket writes,
// Slack, harness execution, or workflow changes. Output is an action PROPOSAL,
// never proof of delivery.

import {
  fingerprint,
  normalizeChain,
  isSubsequence,
  normEnv,
  FINGERPRINT_VERSION,
} from "./normalize.mjs";

export class PlannerInputError extends Error {
  constructor(message) {
    super(message);
    this.name = "PlannerInputError";
  }
}

const TICKET_LABELS = ["Bug", "pentesting", "harness"];
const nonEmptyString = (v) => typeof v === "string" && v.trim() !== "";

function validateInput(input) {
  if (input === null || typeof input !== "object" || Array.isArray(input))
    throw new PlannerInputError("input must be an object");
  const run = input.run;
  if (run === null || typeof run !== "object" || Array.isArray(run))
    throw new PlannerInputError("input.run is required");
  if (!nonEmptyString(run.runId))
    throw new PlannerInputError("run.runId is required");
  if (!nonEmptyString(run.targetEnvironment))
    throw new PlannerInputError("run.targetEnvironment is required");
  if (!Array.isArray(input.observations))
    throw new PlannerInputError("input.observations must be an array");
  for (const o of input.observations) {
    if (o === null || typeof o !== "object" || !nonEmptyString(o.observationId))
      throw new PlannerInputError(
        "each observation needs a string observationId",
      );
  }
  if (input.existingIssues !== undefined) {
    if (!Array.isArray(input.existingIssues))
      throw new PlannerInputError("input.existingIssues must be an array");
    for (const iss of input.existingIssues) {
      if (
        iss === null ||
        typeof iss !== "object" ||
        !nonEmptyString(iss.issueId)
      )
        throw new PlannerInputError(
          "each existing issue needs a string issueId",
        );
      if (!nonEmptyString(iss.targetEnvironment))
        throw new PlannerInputError(
          `existing issue ${iss.issueId} needs targetEnvironment`,
        );
      if (
        !Array.isArray(iss.normalizedChain) &&
        !Array.isArray(iss.fingerprintAliases)
      )
        throw new PlannerInputError(
          `existing issue ${iss.issueId} needs normalizedChain or fingerprintAliases`,
        );
    }
  }
  if (
    input.processedEvents !== undefined &&
    !Array.isArray(input.processedEvents)
  )
    throw new PlannerInputError("input.processedEvents must be an array");
}

function decision(fields) {
  const d = {
    observationId: fields.observationId,
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
  if (fields.idempotencyKey !== undefined)
    d.idempotencyKey = fields.idempotencyKey;
  return d;
}

// Required fields for a complete, non-hollow ticket (E1-01). Returns missing list.
function incompleteTicketFields(e) {
  const missing = [];
  if (!e || typeof e !== "object") return ["exploit"];
  if (!nonEmptyString(e.severity)) missing.push("severity");
  if (!["yes", "no", "unknown"].includes(e.productionImpact?.value))
    missing.push("productionImpact.value");
  if (!nonEmptyString(e.productionImpact?.rationale))
    missing.push("productionImpact.rationale");
  if (!Array.isArray(e.remediation) || e.remediation.length === 0)
    missing.push("remediation");
  if (!nonEmptyString(e.retestExpectations)) missing.push("retestExpectations");
  if (!Array.isArray(e.chain) || e.chain.length === 0) missing.push("chain");
  return missing;
}

function ticketMaterial(obs, fp, exploitId) {
  const e = obs.exploit;
  const repos = e.affectedRepositories ?? [];
  return {
    exploitId: exploitId ?? null,
    fingerprint: fp,
    fingerprintVersion: FINGERPRINT_VERSION,
    // Full structured chain, round-trippable as existingIssues[].normalizedChain (R2-B1).
    chain: JSON.parse(JSON.stringify(e.chain)),
    labels: [...TICKET_LABELS],
    severity: e.severity,
    productionImpact: { ...e.productionImpact },
    affectedSurfaces: [...(e.affectedSurfaces ?? [])],
    ownership: repos.length ? [...repos] : "unknown",
    remediation: JSON.parse(JSON.stringify(e.remediation)),
    retestExpectations: e.retestExpectations,
    evidenceReferences: [...(obs.evidence?.references ?? [])],
  };
}

export function plan(input) {
  validateInput(input);
  const run = input.run;
  const runEnv = run.targetEnvironment;
  const processedIds = new Set(
    (input.processedEvents ?? []).map((e) => e.eventId).filter(Boolean),
  );
  const processedKeys = new Set(
    (input.processedEvents ?? []).map((e) => e.key).filter(Boolean),
  );
  const existingIssues = input.existingIssues ?? [];
  const countedThisRun = new Set(); // keyed by matched identity (issueId/exploitId/fp)
  const decisions = [];
  const notObserved = [];

  for (const obs of input.observations) {
    const observationId = obs.observationId;

    if (obs.kind === "non-observation") {
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
        attemptedCoverage:
          status === "completed" ? [...(run.coverage?.tested ?? [])] : [],
        edgeClassification: run.edgeAccess?.classification ?? "none",
        evidenceReferences: [...(obs.evidence?.references ?? [])],
      });
      continue;
    }

    if (obs.kind !== "confirmed-positive") {
      decisions.push(
        decision({
          observationId,
          outcome: "unresolved",
          reason: `Unknown observation kind '${obs.kind ?? "(missing)"}'; not treated as a positive.`,
          matchReason: "unknown kind",
          neededEvidence: ["a recognized observation kind"],
        }),
      );
      continue;
    }

    if (
      !["valid", "invalid-evidence", "ambiguous-identity"].includes(
        obs.validity,
      )
    ) {
      decisions.push(
        decision({
          observationId,
          outcome: "unresolved",
          reason: `Unrecognized validity '${obs.validity ?? "(missing)"}'.`,
          matchReason: "unrecognized validity",
          neededEvidence: ["a recognized validity value"],
        }),
      );
      continue;
    }
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

    const fp = fingerprint(obs.exploit?.chain, runEnv);
    const evidenceReferences = obs.exploit
      ? (obs.evidence?.references ?? [])
      : [];
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

    const obsNorm = normalizeChain(obs.exploit.chain);
    const matches = existingIssues.filter((iss) => {
      const issFp = fingerprint(iss.normalizedChain, iss.targetEnvironment);
      if (issFp !== null && issFp === fp) return true;
      return (
        Array.isArray(iss.fingerprintAliases) &&
        iss.fingerprintAliases.includes(fp)
      );
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

    // No exact match: a related-but-not-equal chain (partial/superset) in the same
    // environment is ambiguous, not a new exploit (E1-18).
    if (matches.length === 0) {
      const related = existingIssues.some((iss) => {
        if (normEnv(iss.targetEnvironment) !== normEnv(runEnv)) return false;
        const issNorm = normalizeChain(iss.normalizedChain);
        if (issNorm === null) return false;
        if (fingerprint(iss.normalizedChain, iss.targetEnvironment) === fp)
          return false;
        return (
          isSubsequence(obsNorm, issNorm) || isSubsequence(issNorm, obsNorm)
        );
      });
      if (related) {
        decisions.push(
          decision({
            observationId,
            outcome: "unresolved",
            reason:
              "Partial or overlapping chain relative to an existing ticket; routed to triage.",
            matchReason: "ambiguous partial chain",
            evidenceReferences,
            neededEvidence: [
              "a complete chain to confirm the same or a distinct exploit",
            ],
          }),
        );
        continue;
      }
    }

    let outcome, target, matchReason, baseActions, fixClaimRef;
    let exploitId = null;
    let eligible = false;
    let identityKey = fp; // dedup/idempotency scope

    if (matches.length === 0) {
      const missing = incompleteTicketFields(obs.exploit);
      if (missing.length) {
        decisions.push(
          decision({
            observationId,
            outcome: "unresolved",
            reason:
              "Confirmed positive with incomplete ticket material; cannot create a compliant ticket.",
            matchReason: "incomplete ticket material",
            evidenceReferences,
            neededEvidence: missing.map((m) => `ticket material: ${m}`),
          }),
        );
        continue;
      }
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
      identityKey = iss.issueId;
      target = { type: "existing-issue", issueId: iss.issueId };
      const state = iss.state;
      const claimed = iss.fixClaim?.claimed === true;
      fixClaimRef = iss.fixClaim?.reference ?? null;

      if (!["open", "resolved", "unknown"].includes(state)) {
        decisions.push(
          decision({
            observationId,
            outcome: "unresolved",
            reason: `Existing ticket state '${state ?? "(missing)"}' is unrecognized; no write without a known state.`,
            exploitId,
            matchReason: "unrecognized ticket state",
            target,
            evidenceReferences,
            neededEvidence: [`current state of ${iss.issueId}`],
          }),
        );
        continue;
      }
      if (state === "unknown") {
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
      if (state === "resolved" && !claimed) {
        decisions.push(
          decision({
            observationId,
            outcome: "unresolved",
            reason:
              "Resolved ticket carries no explicit fix claim to contradict; triage rather than speculative reopen.",
            exploitId,
            matchReason: "resolved without fix claim",
            target,
            evidenceReferences,
            fixClaimRef,
            neededEvidence: [`explicit fix-claim reference for ${iss.issueId}`],
          }),
        );
        continue;
      }

      const rem =
        Array.isArray(obs.exploit?.remediation) &&
        obs.exploit.remediation.length
          ? [
              {
                type: "append-remediation",
                remediation: JSON.parse(
                  JSON.stringify(obs.exploit.remediation),
                ),
              },
            ]
          : [];
      if (state === "resolved") {
        outcome = "claimed-fixed-reproduces";
        matchReason =
          "same normalized causal chain as the closed ticket with a fix claim";
        eligible = true;
        baseActions = [
          { type: "append-evidence" },
          { type: "reopen-ticket" },
          ...rem,
        ];
      } else if (claimed) {
        outcome = "claimed-fixed-reproduces";
        matchReason =
          "same normalized causal chain as the open ticket with a fix claim";
        eligible = true;
        baseActions = [{ type: "append-evidence" }, ...rem];
      } else {
        outcome = "rediscovered-open";
        matchReason = "same normalized causal chain as the open ticket";
        eligible = false;
        baseActions = [{ type: "append-evidence" }, ...rem];
      }
    }

    const derivedKey = `${run.runId}:${exploitId ?? fp}`;
    const replayed =
      (obs.eventId && processedIds.has(obs.eventId)) ||
      processedKeys.has(derivedKey);
    const duplicateInRun = countedThisRun.has(identityKey);

    let actions;
    if (replayed || duplicateInRun) {
      actions = [{ type: "none" }];
      eligible = false;
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
    countedThisRun.add(identityKey);

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
        idempotencyKey: derivedKey,
        ...(fixClaimRef !== undefined ? { fixClaimRef } : {}),
      }),
    );
  }

  const unresolved = decisions
    .filter((d) => d.outcome === "unresolved")
    .map((d) => d.observationId);
  const completion = run.completion?.status ?? "unknown";
  const runSummary = {
    batchStatus:
      unresolved.length || completion !== "completed" ? "partial" : "complete",
    runCompletion: completion,
    sessionStatus: run.session?.status ?? "unknown",
    coverage: run.coverage ?? { tested: [], untested: [], interrupted: [] },
    unresolved,
    notObserved,
    edgeAccess: run.edgeAccess ?? { classification: "none" },
  };
  if (run.completion?.stopReason)
    runSummary.stopReason = run.completion.stopReason;

  return { runId: run.runId, decisions, runSummary };
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
