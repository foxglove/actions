import { createHash } from "node:crypto";
import {
  InputError,
  validateEnvelope,
  validateObservation,
  validateRetest,
  validateCoverage,
} from "./contract.mjs";

// Produces a stable digest for an already normalized identity.
const hash = (value) => createHash("sha256").update(value).digest("hex");
// Removes duplicate strings and returns them in stable order.
const sorted = (a) => [...new Set(a)].sort();

// These aliases remove wording variation only. An unrecognized causal change is
// triaged rather than inferred equivalent from title or a similarity score.
const aliases = [
  [/\b(organization|org|workspace)\b/g, "tenant"],
  [/\b(retrieve|fetch|read)\b/g, "download"],
  [/\b(permission|authorization|authz)\b/g, "access"],
  [/\b(identifier|id|uuid)\b/g, "identifier"],
  [/\b(denied|reject|prevent)\b/g, "deny"],
];
// Removes harmless wording and generated-identifier differences before identity comparison.
export function canonical(value) {
  let s = String(value).normalize("NFKC").toLowerCase();
  s = s.replace(/\b[0-9a-f]{8}-[0-9a-f-]{27,}\b/gi, "<id>");
  s = s.replace(/\b(export|resource)[-_ ]?[0-9a-f]{6,}\b/g, "$1 <id>");
  s = s.replace(/\b(?:[a-z]+[-_])?\d{2,}\b/g, "<id>");
  for (const [pattern, replacement] of aliases)
    s = s.replace(pattern, replacement);
  return s
    .replace(/[^a-z0-9<>]+/g, " ")
    .trim()
    .replace(/\s+/g, " ");
}

// Converts a validated prerequisite graph into an ordered semantic attack chain.
function causalChain(transitions) {
  const byId = new Map(transitions.map((t) => [t.stepId, t]));
  const prerequisites = new Set(
    transitions.flatMap((t) => t.prerequisiteStepIds),
  );
  const terminals = transitions.filter((t) => !prerequisites.has(t.stepId));
  if (terminals.length !== 1)
    throw new Error(
      "ambiguous terminal control; split independent causes or mark incidental steps explicitly",
    );
  const terminal = terminals[0];
  const actorTenant = /\btenant[-_]([a-z0-9]+)\b/i
    .exec(terminal.actorCapability)?.[1]
    ?.toLowerCase();
  // Expresses tenant references relative to the starting actor.
  const relative = (value) =>
    canonical(
      actorTenant
        ? value.replace(/\btenant[-_]([a-z0-9]+)\b/gi, (_, tenant) =>
            tenant.toLowerCase() === actorTenant
              ? "actor-tenant"
              : "other-tenant",
          )
        : value,
    );
  const levels = new Map();
  // Calculates each step's prerequisite depth for stable ordering.
  function level(id) {
    if (levels.has(id)) return levels.get(id);
    const t = byId.get(id);
    const n = t.prerequisiteStepIds.length
      ? 1 + Math.max(...t.prerequisiteStepIds.map(level))
      : 0;
    levels.set(id, n);
    return n;
  }
  level(terminal.stepId);
  const result = [...levels.keys()].map((id) => {
    const t = byId.get(id);
    return {
      depth: levels.get(id),
      actorCapability: relative(t.actorCapability),
      resourceRelation: relative(t.resourceRelation),
      targetClass: relative(t.targetClass),
      operation: relative(t.operation),
      expectedBoundary: relative(t.expectedBoundary),
      observedEffect: relative(t.observedEffect),
      prerequisites: sorted(
        t.prerequisiteStepIds.map((p) => byId.get(p).operation).map(relative),
      ),
    };
  });
  // A semantic sort preserves prerequisite depth without depending on step IDs
  // or the order in which an adapter supplied independent prerequisites.
  return result
    .sort(
      (a, b) =>
        a.depth - b.depth || JSON.stringify(a).localeCompare(JSON.stringify(b)),
    )
    .map(({ depth, ...transition }) => transition);
}
// Splits explicitly independent terminal controls into separate findings.
function splitCauses(o) {
  if (!o.causes)
    return [
      {
        ...o,
        transitions: o.transitions.filter(
          (t) => !o.incidentalStepIds?.includes(t.stepId),
        ),
      },
    ];
  const byId = new Map(o.transitions.map((t) => [t.stepId, t]));
  return o.causes.map((c) => {
    const included = new Set();
    // Includes the selected terminal step and every prerequisite needed to reach it.
    function include(id) {
      if (included.has(id)) return;
      included.add(id);
      for (const p of byId.get(id).prerequisiteStepIds) include(p);
    }
    include(c.terminalStepId);
    return {
      ...o,
      observationId: `${o.observationId}#${c.causeId}`,
      surface: c.surface,
      violatedBoundary: c.violatedBoundary,
      impact: c.impact,
      severity: c.severity,
      productionImpact: c.productionImpact,
      remediation: c.remediation,
      retest: c.retest,
      components: c.components,
      blockedSteps: c.blockedSteps,
      dangerousNotExecuted: c.dangerousNotExecuted,
      transitions: o.transitions.filter(
        (t) =>
          included.has(t.stepId) && !o.incidentalStepIds?.includes(t.stepId),
      ),
      causes: undefined,
    };
  });
}
// Builds the structured fields that define one exploit across runs and wording changes.
export function identityOf(record) {
  const chain = causalChain(
    (record.transitions ?? record.normalizedChain).filter(
      (t) => !record.incidentalStepIds?.includes(t.stepId),
    ),
  );
  const last = chain.at(-1);
  return {
    environment: record.environment,
    surface: canonical(record.surface),
    violatedBoundary: canonical(record.violatedBoundary),
    startingActorRelation: last.actorCapability,
    targetResourceRelation: last.resourceRelation,
    demonstratedEffect: last.observedEffect,
    chain,
  };
}
// Serializes a normalized exploit identity for stable hashing.
const identityString = (record) => JSON.stringify(identityOf(record));
// Creates the versioned exploit fingerprint used by this planner.
const fingerprint = (record) => `v2:${hash(identityString(record))}`;
// Collects each unique evidence reference from a finding's causal steps.
const evidenceOf = (o) => sorted(o.transitions.flatMap((t) => t.evidenceRefs));
// Encodes stable action-key segments without allowing path separators to alter identity.
const key = (...parts) => parts.map(encodeURIComponent).join("/");

// Explains whether two normalized identities match or need human review.
function candidateReason(a, b) {
  if (a.environment !== b.environment || a.surface !== b.surface)
    return "different surface or environment";
  if (a.violatedBoundary !== b.violatedBoundary)
    return "different violated control";
  if (JSON.stringify(a) === JSON.stringify(b))
    return "same environment, surface, violated control, actor/resource relation, effect, and causal prerequisites";
  return "same surface and violated control, but causal relation, effect, or prerequisites differ; human identity review needed";
}
// Creates a no-write decision when evidence is incomplete or ambiguous.
function evidenceDecision(o, reason, neededEvidence = []) {
  return {
    observationId: o?.observationId,
    outcome: "unresolved",
    reason,
    evidenceRefs: o?.transitions ? evidenceOf(o) : [],
    proposedActions: [],
    notificationEligible: false,
    neededEvidence,
  };
}
// Returns why an observation does not follow its validated starting session, or null.
function sessionIssue(o, events) {
  const start = events.find((s) => s.ref === o.sessionRef);
  if (
    !start ||
    start.state !== "validated" ||
    !start.actorRole ||
    !start.partyRef ||
    !start.jarRef
  )
    return "missing validated starting session";
  if (
    !/non.?admin|developer/.test(canonical(start.actorRole)) ||
    (/\badmin\b/.test(canonical(start.actorRole)) &&
      !/non.?admin/.test(canonical(start.actorRole)))
  )
    return "starting actor is not a validated non-admin developer";
  if (start.sequence >= o.observedSequence)
    return "observation does not follow session validation";
  const subsequent = events.filter(
    (s) => s.sequence > start.sequence && s.sequence <= o.observedSequence,
  );
  if (subsequent.some((s) => s.state === "lost"))
    return "observation occurred after session loss";
  if (subsequent.some((s) => s.state === "validated"))
    return "a new session was established after the referenced starting session";
  if (
    subsequent.some(
      (s) =>
        s.state === "rotated" &&
        (s.jarRef !== start.jarRef ||
          (s.actorRole && s.actorRole !== start.actorRole) ||
          (s.partyRef && s.partyRef !== start.partyRef)),
    )
  )
    return "cookie rotation changed the authorized jar, actor, or party";
  return null;
}
// Builds the complete proposed ticket content for a new exploit.
function ticketDraft(o, runId, evidenceRefs) {
  return {
    labels: ["Bug", "pentesting", "harness"],
    boundary: o.violatedBoundary,
    affectedSurface: o.surface,
    preconditions: [...o.preconditions],
    actorRole: o.actorRole,
    demonstratedImpact: o.impact,
    severity: o.severity,
    productionImpact: { ...o.productionImpact },
    activityChain: structuredClone(o.transitions),
    blockedSteps: [...(o.blockedSteps ?? [])],
    dangerousNotExecuted: [...(o.dangerousNotExecuted ?? [])],
    remediation: [...o.remediation],
    retest: [...o.retest],
    runId,
    evidenceRefs: [...evidenceRefs],
    components: o.components?.length ? [...o.components] : ["unknown"],
  };
}
// Combines corroborating observations into one proposed ticket without losing evidence.
function mergeDraft(draft, o) {
  // Produces stable set unions for ticket list fields.
  const union = (a, b) => sorted([...a, ...b]);
  draft.preconditions = union(draft.preconditions, o.preconditions);
  draft.remediation = union(draft.remediation, o.remediation);
  draft.retest = union(draft.retest, o.retest);
  draft.components = union(
    draft.components,
    o.components?.length ? o.components : ["unknown"],
  );
  draft.blockedSteps = union(draft.blockedSteps, o.blockedSteps ?? []);
  draft.dangerousNotExecuted = union(
    draft.dangerousNotExecuted,
    o.dangerousNotExecuted ?? [],
  );
  draft.evidenceRefs = union(draft.evidenceRefs, evidenceOf(o));
  draft.demonstratedImpact = union(draft.demonstratedImpact.split("\n"), [
    o.impact,
  ]).join("\n");
  const severityOrder = ["critical", "high", "medium", "low", "info"];
  // Maps a severity to its ordering rank.
  const rank = (s) => {
    const i = severityOrder.indexOf(s.toLowerCase());
    return i < 0 ? Infinity : i;
  };
  if (rank(o.severity) < rank(draft.severity)) draft.severity = o.severity;
  if (draft.productionImpact.value !== o.productionImpact.value)
    draft.productionImpact.value = "unknown";
  draft.productionImpact.rationale = union(
    draft.productionImpact.rationale.split("\n"),
    [o.productionImpact.rationale],
  ).join("\n");
  // Keep the first (stable ID ordered) complete chain. Attach corroborating
  // evidence to matching steps, and retain every reference at ticket level.
  for (const step of draft.activityChain) {
    const other = o.transitions.find(
      (t) =>
        canonical(t.operation) === canonical(step.operation) &&
        canonical(t.expectedBoundary) === canonical(step.expectedBoundary),
    );
    if (other) step.evidenceRefs = union(step.evidenceRefs, other.evidenceRefs);
  }
}
// Finds the recorded state of one external action attempt.
function actionState(input, action, actionKey) {
  return input.processedActions.find(
    (a) => a.action === action && a.key === actionKey,
  )?.state;
}
// Proposes an external action only when retry state makes it safe.
function addAction(input, decision, action, actionKey) {
  const state = actionState(input, action, actionKey);
  decision.actionKeys[action] = actionKey;
  if (!state || state === "failed") decision.proposedActions.push(action);
  else if (state === "pending" || state === "uncertain") {
    decision.reason += `; ${action} is ${state} and requires external readback before retry`;
    decision.neededEvidence = sorted([
      ...(decision.neededEvidence ?? []),
      `${action} external readback`,
    ]);
  }
}

// Produces deterministic ticket and summary proposals without making external calls.
export function plan(raw) {
  const input = validateEnvelope(raw);
  const quarantined = [],
    coverage = [],
    retests = [],
    observations = [];
  // Validates independent items while quarantining only the invalid item.
  function independent(collection, validate, dest) {
    input[collection].forEach((item, index) => {
      try {
        dest.push({
          value: validate(item, `$.${collection}[${index}]`),
          index,
        });
      } catch (e) {
        if (!(e instanceof InputError)) throw e;
        quarantined.push({
          collection,
          index,
          ref:
            item?.observationId ??
            item?.exploitId ??
            item?.surface ??
            `${collection}[${index}]`,
          reason: e.message,
        });
      }
    });
  }
  independent("coverage", validateCoverage, coverage);
  independent("retests", validateRetest, retests);
  independent("observations", validateObservation, observations);
  const decisions = [],
    known = input.existing.map((e) => ({
      record: e,
      identity: identityOf(e),
      identityAliases: e.identityAliases?.map(identityOf) ?? [],
      fingerprint: fingerprint(e),
      existing: true,
    }));
  const seenIds = new Set(),
    positiveExploits = new Set(),
    allCandidates = [...known];
  for (const o of observations
    .flatMap(({ value }) => splitCauses(value))
    .sort((a, b) => a.observationId.localeCompare(b.observationId))) {
    if (seenIds.has(o.observationId)) {
      decisions.push(
        evidenceDecision(o, "duplicate observationId in run", [
          "unique observation identity",
        ]),
      );
      continue;
    }
    seenIds.add(o.observationId);
    if (o.status !== "confirmed") {
      decisions.push(
        evidenceDecision(o, "observation is incomplete", [
          "confirmed trace and impact",
        ]),
      );
      continue;
    }
    const issue = sessionIssue(o, input.sessionEvents);
    if (issue) {
      decisions.push(
        evidenceDecision(o, issue, [
          "validated session provenance before observed effect",
        ]),
      );
      continue;
    }
    let identity;
    try {
      identity = identityOf(o);
    } catch (e) {
      decisions.push(
        evidenceDecision(o, e.message, ["acyclic causal prerequisites"]),
      );
      continue;
    }
    if (
      !identity.violatedBoundary ||
      !identity.surface ||
      !identity.startingActorRelation ||
      !identity.targetResourceRelation ||
      !identity.demonstratedEffect
    ) {
      decisions.push(
        evidenceDecision(o, "missing required causal identity", [
          "surface, control, actor/resource relation, demonstrated effect",
        ]),
      );
      continue;
    }
    const fp = fingerprint(o);
    const exact = allCandidates.filter((c) =>
      [c.identity, ...(c.identityAliases ?? [])].some(
        (i) => JSON.stringify(i) === JSON.stringify(identity),
      ),
    );
    const plausible = allCandidates.filter(
      (c) =>
        c.identity.environment === identity.environment &&
        c.identity.surface === identity.surface &&
        (c.identity.violatedBoundary === identity.violatedBoundary ||
          c.record.fingerprintAliases?.includes(fp)),
    );
    if (exact.length > 1 || (!exact.length && plausible.length)) {
      decisions.push(
        evidenceDecision(
          o,
          `ambiguous causal identity: ${sorted((exact.length ? exact : plausible).map((c) => c.record.exploitId)).join(", ")}`,
          ["review candidate identity and causal evidence"],
        ),
      );
      continue;
    }
    const match = exact[0];
    const exploitId =
      match?.record.exploitId ??
      `proposed-${hash(identityString(o)).slice(0, 20)}`;
    if (positiveExploits.has(exploitId)) {
      const primary = decisions.find((d) => d.exploitId === exploitId);
      primary.evidenceRefs = sorted([
        ...primary.evidenceRefs,
        ...evidenceOf(o),
      ]);
      if (primary.ticketDraft) mergeDraft(primary.ticketDraft, o);
      decisions.push({
        observationId: o.observationId,
        outcome: match?.existing ? "rediscovered" : "new",
        reason:
          "same exploit already confirmed in this run; evidence and count are proposed once",
        normalizedMatchReason: candidateReason(
          identity,
          match?.identity ?? identity,
        ),
        exploitId,
        issueId: match?.existing ? match.record.linearIssueId : undefined,
        evidenceRefs: evidenceOf(o),
        proposedActions: [],
        actionKeys: {},
        notificationEligible: false,
      });
      continue;
    }
    if (!match)
      allCandidates.push({
        record: { exploitId, ...o, fingerprintAliases: [fp] },
        identity,
        fingerprint: fp,
        existing: false,
      });
    const evidenceRefs = evidenceOf(o);
    const d = {
      observationId: o.observationId,
      outcome: "new",
      reason: "confirmed causal identity has no existing match",
      normalizedMatchReason: match
        ? JSON.stringify(identity) === JSON.stringify(match.identity)
          ? candidateReason(identity, match.identity)
          : "same complete causal identity as a reviewed structured identity alias"
        : "new normalized causal identity",
      exploitId,
      issueId: match?.existing ? match.record.linearIssueId : undefined,
      confirmationKey: key("confirmation", exploitId, input.run.id),
      evidenceRefs,
      proposedActions: [],
      actionKeys: {},
      notificationEligible: false,
    };
    if (match?.existing) {
      const e = match.record;
      if (
        e.state === "unknown" ||
        e.issueOpen === null ||
        (e.state === "open" && !e.issueOpen)
      ) {
        decisions.push(
          evidenceDecision(
            o,
            `matched issue ${e.linearIssueId} has unknown or inconsistent lifecycle state`,
            ["mapped issue state"],
          ),
        );
        continue;
      }
      if (e.state === "claimed_fixed") {
        d.outcome = "contradicts_fix";
        d.reason = `confirmed evidence contradicts fix claim ${e.fixClaimId} (${e.claimRef}) on issue ${e.linearIssueId}`;
        d.episodeKey = key("claim", exploitId, e.fixClaimId);
      } else {
        d.outcome = "rediscovered";
        d.reason = `same causal exploit remains open on issue ${e.linearIssueId}`;
      }
      const runKey = key("run", exploitId, input.run.id);
      const counted = e.confirmedRunIds?.includes(input.run.id) ?? false;
      const evidenceState = actionState(input, "append_evidence", runKey);
      if (counted && !evidenceState) {
        d.actionKeys.append_evidence = runKey;
        d.reason += "; run is confirmed but evidence action state is missing";
        d.neededEvidence = ["evidence comment readback for confirmed run"];
      } else addAction(input, d, "append_evidence", runKey);
      if (!counted) addAction(input, d, "increment_run_count", runKey);
      else {
        d.actionKeys.increment_run_count = runKey;
        const countState = actionState(input, "increment_run_count", runKey);
        if (countState === "pending" || countState === "uncertain")
          d.neededEvidence = sorted([
            ...(d.neededEvidence ?? []),
            "count action readback for confirmed run",
          ]);
      }
      if (d.outcome === "contradicts_fix") {
        if (!e.issueOpen) addAction(input, d, "reopen", d.episodeKey);
        const notifyState = actionState(input, "notify", d.episodeKey);
        d.notificationEligible = !notifyState;
      }
      d.countChange = {
        runId: input.run.id,
        historicalCount: e.historicalCount,
      };
    } else {
      const createKey = key("create", exploitId);
      const createState = actionState(input, "create", createKey);
      if (createState && createState !== "failed") {
        decisions.push(
          evidenceDecision(
            o,
            `create for ${exploitId} is ${createState} but no established issue snapshot matches`,
            ["external create readback and refreshed identity corpus"],
          ),
        );
        continue;
      }
      d.ticketDraft = ticketDraft(o, input.run.id, evidenceRefs);
      addAction(input, d, "create", createKey);
      d.notificationEligible = !actionState(
        input,
        "notify",
        key("new", exploitId),
      );
      d.episodeKey = key("new", exploitId);
      d.countChange = { runId: input.run.id, historicalCount: null };
    }
    if (d.neededEvidence?.length) d.notificationEligible = false;
    positiveExploits.add(exploitId);
    decisions.push(d);
  }
  for (const { value: r } of retests) {
    if (
      r.observedObservationIds.some((id) =>
        decisions.some(
          (d) =>
            (d.observationId === id || d.observationId?.startsWith(`${id}#`)) &&
            d.exploitId === r.exploitId &&
            !["unresolved", "not_observed"].includes(d.outcome),
        ),
      )
    )
      continue;
    decisions.push({
      outcome: "not_observed",
      exploitId: r.exploitId,
      reason: `not observed in this run; ${r.execution}${r.stopReason ? `; ${r.stopReason}` : ""}`,
      evidenceRefs: r.evidenceRefs,
      proposedActions: [],
      notificationEligible: false,
      execution: r.execution,
      attemptedOperations: r.attemptedOperations,
      conditions: r.conditions,
      stopReason: r.stopReason,
    });
  }
  for (const q of quarantined.filter((q) => q.collection === "observations")) {
    decisions.push({
      observationId: q.ref,
      outcome: "unresolved",
      reason: `invalid observation at ${q.collection}[${q.index}]: ${q.reason}`,
      evidenceRefs: [],
      proposedActions: [],
      notificationEligible: false,
      neededEvidence: ["valid structured observation and evidence references"],
    });
  }
  return {
    schemaVersion: 1,
    runId: input.run.id,
    status: quarantined.length
      ? "partial_failure"
      : decisions.some(
            (d) => d.outcome === "unresolved" || d.neededEvidence?.length,
          )
        ? "needs_review"
        : "planned",
    decisions,
    quarantined,
    summary: {
      proposed: true,
      coverage: coverage.map((x) => x.value),
      stopReason: input.run.stopReason,
      proposedIssueIds: sorted(
        decisions
          .filter((d) => d.proposedActions.includes("create"))
          .map((d) => d.exploitId),
      ),
      unresolved: decisions
        .filter((d) => d.outcome === "unresolved")
        .map((d) => d.reason),
      nonObservations: decisions.filter((d) => d.outcome === "not_observed"),
      quarantined,
      deliveryState: "proposed_only",
      evidencePrefix: input.run.evidencePrefix,
    },
  };
}
