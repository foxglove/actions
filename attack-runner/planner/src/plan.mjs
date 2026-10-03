// WP1.2–1.4 — deterministic reconciliation decision engine.
//
// Pure and side-effect free (E1-15): no network, secret reads, ticket writes,
// Slack, harness execution, or workflow changes. Output is an action PROPOSAL,
// never proof of delivery.

import { fingerprint } from "./normalize.mjs";

function decision(fields) {
  return {
    observationId: fields.observationId,
    outcome: fields.outcome,
    reason: fields.reason,
    exploitIdentity: {
      exploitId: fields.exploitId ?? null,
      matchReason: fields.matchReason ?? "",
    },
    target: fields.target ?? { type: "none", issueId: null },
    proposedActions: fields.proposedActions ?? [],
    evidenceReferences: fields.evidenceReferences ?? [],
    notificationEligible: fields.notificationEligible ?? false,
    neededEvidence: fields.neededEvidence ?? [],
  };
}

export function plan(input) {
  const run = input.run ?? {};
  const processed = new Set(
    (input.processedEvents ?? []).map((e) => e.eventId),
  );
  const existingIssues = input.existingIssues ?? [];
  const seenThisRun = new Set(); // fingerprints already counted in this run
  const decisions = [];
  const notObserved = [];

  for (const obs of input.observations ?? []) {
    // --- non-observation: summary-only, zero ticket writes ---
    if (obs.kind === "non-observation") {
      const exploitId = obs.retestTarget?.exploitId ?? null;
      const issueId = obs.retestTarget?.issueId ?? null;
      decisions.push(
        decision({
          observationId: obs.observationId,
          outcome: "not-observed",
          reason:
            "Run did not observe the tracked exploit; not an absence or fix claim. A resolved ticket receives no write.",
          exploitId,
          matchReason: obs.retestTarget ? "re-test target" : "",
          target: { type: "none", issueId: null },
        }),
      );
      notObserved.push({
        observationId: obs.observationId,
        exploitId,
        issueId,
        executionStatus: obs.execution?.status ?? "not-attempted",
        reason: obs.execution?.stopReason ?? "not observed in this run",
        attemptedCoverage: run.coverage?.tested ?? [],
        evidenceReferences: obs.evidence?.references ?? [],
      });
      continue;
    }

    // --- invalid / ambiguous required state: unresolved, no action ---
    if (obs.validity !== "valid") {
      const invalid = obs.validity === "invalid-evidence";
      decisions.push(
        decision({
          observationId: obs.observationId,
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
    const fp = fingerprint(obs.exploit?.chain);
    const evidenceReferences = obs.evidence?.references ?? [];
    if (fp === null) {
      decisions.push(
        decision({
          observationId: obs.observationId,
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

    const matches = existingIssues.filter(
      (iss) => fingerprint(iss.normalizedChain) === fp,
    );

    // Ambiguous: more than one existing exploit matches.
    if (matches.length > 1) {
      decisions.push(
        decision({
          observationId: obs.observationId,
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

    let outcome;
    let target;
    let exploitId;
    let matchReason;
    let eligible;
    let actions;

    if (matches.length === 0) {
      outcome = "new";
      exploitId = null;
      matchReason = "no candidate existing ticket";
      target = { type: "new-issue", issueId: null };
      eligible = true;
      actions = [{ type: "create-ticket" }];
    } else {
      const iss = matches[0];
      exploitId = iss.exploitId ?? null;
      target = { type: "existing-issue", issueId: iss.issueId };
      const claimedFixed =
        iss.state === "resolved" && iss.fixClaim?.claimed === true;
      if (claimedFixed) {
        outcome = "claimed-fixed-reproduces";
        matchReason =
          "same normalized causal chain as the closed ticket with a fix claim";
        eligible = true;
        actions = [{ type: "append-evidence" }, { type: "reopen-ticket" }];
      } else {
        outcome = "rediscovered-open";
        matchReason = "same normalized causal chain as the open ticket";
        eligible = false;
        actions = [{ type: "append-evidence" }];
      }
    }

    // Count once per exploit per run; replay or in-run duplicate => no mutation.
    const replayed = Boolean(obs.eventId && processed.has(obs.eventId));
    const duplicateInRun = seenThisRun.has(fp);
    if (replayed || duplicateInRun) {
      actions = [{ type: "none" }];
      eligible = false;
    } else {
      actions = [...actions, { type: "increment-confirmed-count", amount: 1 }];
      seenThisRun.add(fp);
    }

    decisions.push(
      decision({
        observationId: obs.observationId,
        outcome,
        reason: reasonFor(outcome),
        exploitId,
        matchReason,
        target,
        proposedActions: actions,
        evidenceReferences,
        notificationEligible: eligible,
      }),
    );
  }

  const runSummary = {
    coverage: run.coverage ?? { tested: [], untested: [], interrupted: [] },
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
      return "Valid confirmed positive contradicts an explicit fix claim; reopen the same ticket, never a duplicate.";
    default:
      return "";
  }
}
