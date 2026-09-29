import { createHash } from "node:crypto";
import {
  InputError,
  validateEnvelope,
  validateObservation,
  validateRetest,
  validateCoverage,
} from "./contract.mjs";

// Digest helper: gives an already normalized exploit or prerequisite a repeatable key across runs.
const hash = (value) => createHash("sha256").update(value).digest("hex");
// Set helper: keeps merged references unique and output stable when observations arrive in a different order.
const sorted = (a) => [...new Set(a)].sort();
// Ordering helper: prevents the host locale from changing which observation supplies the displayed ticket chain.
const compare = (a, b) => (a < b ? -1 : a > b ? 1 : 0);
// These aliases remove wording variation only. An unrecognized causal change is
// triaged rather than inferred equivalent from title or a similarity score.
const aliases = [
  [/\b(organization|org|workspace)\b/g, "tenant"],
  [/\b(retrieve|fetch|read)\b/g, "download"],
  [/\b(permission|authorization|authz)\b/g, "access"],
  [/\b(identifier|id|uuid)\b/g, "identifier"],
  [/\b(denied|reject|prevent)\b/g, "deny"],
];
// Normalizes the supported wording aliases and generated identifiers so they do not alone create another ticket.
// This is a limited matching rule, not proof that arbitrary paraphrases describe the same exploit.
export function canonical(value) {
  let s = String(value).normalize("NFKC").toLowerCase();
  s = s.replace(/\b[0-9a-f]{8}-[0-9a-f-]{27,}\b/gi, "<id>");
  s = s.replace(/\b(export|resource)[-_ ]?[0-9a-f]{6,}\b/g, "$1 <id>");
  s = s.replace(/\b(export|resource)[-_]\d{2,}\b/g, "$1 <id>");
  for (const [pattern, replacement] of aliases)
    s = s.replace(pattern, replacement);
  return s
    .replace(/[^a-z0-9<>]+/g, " ")
    .trim()
    .replace(/\s+/g, " ");
}

// Builds the chain used for ticket matching, retaining each step's actor/resource relations and prerequisites.
// Equal operation names must not hide different paths through security controls.
function causalChain(transitions, withStepIds = false) {
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
  const actorTenantRef = terminal.actorTenantRef;
  // Placeholder helper: compares tenant relationships across runs without replacing arbitrary words that resemble tenant IDs.
  const relative = (value, transition) =>
    canonical(
      value
        .replaceAll(
          "{actorTenant}",
          transition.actorTenantRef === actorTenantRef
            ? "actor-tenant"
            : "other-tenant",
        )
        .replaceAll(
          "{resourceTenant}",
          transition.resourceTenantRef === actorTenantRef
            ? "actor-tenant"
            : "other-tenant",
        ),
    );
  const levels = new Map();
  // Ordering helper: places prerequisites before their dependents without relying on adapter-chosen step IDs.
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
  const semantics = new Map();
  // Identity helper: includes full prerequisite meaning so different control failures do not match on operation names alone.
  function semantic(id) {
    if (semantics.has(id)) return semantics.get(id);
    const t = byId.get(id);
    const value = {
      actorCapability: relative(t.actorCapability, t),
      actorTenantRelation:
        t.actorTenantRef === actorTenantRef ? "actor tenant" : "other tenant",
      resourceRelation: relative(t.resourceRelation, t),
      resourceTenantRelation:
        t.resourceTenantRef === actorTenantRef
          ? "actor tenant"
          : "other tenant",
      targetClass: relative(t.targetClass, t),
      operation: relative(t.operation, t),
      expectedBoundary: relative(t.expectedBoundary, t),
      observedEffect: relative(t.observedEffect, t),
      prerequisites: sorted(
        t.prerequisiteStepIds.map((p) => hash(JSON.stringify(semantic(p)))),
      ),
    };
    semantics.set(id, value);
    return value;
  }
  const result = [...levels.keys()].map((id) => ({
    stepId: id,
    depth: levels.get(id),
    value: semantic(id),
  }));
  // A semantic sort preserves prerequisite depth without depending on step IDs
  // or the order in which an adapter supplied independent prerequisites.
  return result
    .sort(
      (a, b) =>
        a.depth - b.depth ||
        compare(JSON.stringify(a.value), JSON.stringify(b.value)),
    )
    .map(({ stepId, value }) => (withStepIds ? { stepId, value } : value));
}
// Keeps explicitly independent causes eligible for separate tickets while preserving their shared prerequisites.
// Encoded output IDs remain distinct; retests link through the original source observation ID.
function splitCauses(o) {
  if (!o.causes)
    return [
      {
        ...o,
        observationId: encodeURIComponent(o.observationId),
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
      observationId: `${encodeURIComponent(o.observationId)}#${encodeURIComponent(c.causeId)}`,
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
// Defines the matching contract for one exploit across runs. Repository, model and run metadata
// do not create a new identity; changes in the causal chain can require separate review.
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
    startingActorRelation: `${last.actorTenantRelation} ${last.actorCapability}`,
    targetResourceRelation: `${last.resourceTenantRelation} ${last.resourceRelation}`,
    demonstratedEffect: last.observedEffect,
    chain,
  };
}
// Serialization helper: feeds the same structured identity to fingerprint and proposed-ticket key generation.
const identityString = (record) => JSON.stringify(identityOf(record));
// Fingerprint helper: labels the normalization version; matching stored chains still preserves established exploit IDs.
const fingerprint = (record) => `v3:${hash(identityString(record))}`;
// Evidence helper: retains all unique chain references for the proposed ticket and run decision.
const evidenceOf = (o) => sorted(o.transitions.flatMap((t) => t.evidenceRefs));
// Replay-key helper: keeps supplied IDs within their own segments so different actions do not share a key accidentally.
const key = (...parts) => parts.map(encodeURIComponent).join("/");

// Explains a ticket match or ambiguity in the plan so a reviewer can assess why evidence is being grouped.
function candidateReason(a, b) {
  if (a.environment !== b.environment || a.surface !== b.surface)
    return "different surface or environment";
  if (a.violatedBoundary !== b.violatedBoundary)
    return "different violated control";
  if (JSON.stringify(a) === JSON.stringify(b))
    return "same environment, surface, violated control, actor/resource relation, effect, and causal prerequisites";
  return "same surface and violated control, but causal relation, effect, or prerequisites differ; human identity review needed";
}
// Stops speculative ticket creation or updates when evidence is incomplete or ambiguous, and states what review needs.
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
// Checks supplied session history before accepting a finding. Rejects wrong starts and post-loss evidence,
// while retaining completed positives; returns a reason or null, not proof of live authentication.
function sessionIssue(o, events) {
  const start = events.find((s) => s.ref === o.sessionRef);
  if (!start || start.state !== "validated")
    return "missing validated starting session";
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
// Display helper: shows concrete tenant references in the ticket after identity uses their relative relationships.
function displayTransition(transition) {
  const displayed = structuredClone(transition);
  for (const field of [
    "actorCapability",
    "resourceRelation",
    "targetClass",
    "operation",
    "expectedBoundary",
    "observedEffect",
  ])
    displayed[field] = displayed[field]
      .replaceAll("{actorTenant}", displayed.actorTenantRef)
      .replaceAll("{resourceTenant}", displayed.resourceTenantRef);
  return displayed;
}
// Prepares one actionable ticket: full activity chain, demonstrated impact, remediation and retest steps.
// Unknown ownership and unproven production impact remain explicit instead of blocking a valid proposal.
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
    activityChain: o.transitions.map(displayTransition),
    blockedSteps: [...(o.blockedSteps ?? [])],
    dangerousNotExecuted: [...(o.dangerousNotExecuted ?? [])],
    remediation: [...o.remediation],
    retest: [...o.retest],
    runId,
    evidenceRefs: [...evidenceRefs],
    components: o.components?.length ? [...o.components] : ["unknown"],
  };
}
// Combines corroborating findings into one ticket proposal, preserving all evidence at ticket level.
// Evidence attaches to a displayed step only when both chains have one unambiguous matching step.
function mergeDraft(draft, o, primaryTransitions) {
  // Merge helper: retains each distinct precondition, remediation step and reference in a repeatable order.
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
  // Severity helper: retains the higher supplied severity when corroborating observations disagree.
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
  const primarySteps = new Map(
    causalChain(primaryTransitions, true).map(({ stepId, value }) => [
      stepId,
      JSON.stringify(value),
    ]),
  );
  const otherSteps = causalChain(o.transitions, true);
  for (const step of draft.activityChain) {
    const matches = otherSteps.filter(
      ({ value }) => JSON.stringify(value) === primarySteps.get(step.stepId),
    );
    // Ambiguous step correspondence keeps evidence at ticket level only.
    if (
      matches.length !== 1 ||
      [...primarySteps.values()].filter(
        (value) => value === primarySteps.get(step.stepId),
      ).length !== 1
    )
      continue;
    const other = o.transitions.find((t) => t.stepId === matches[0].stepId);
    step.evidenceRefs = union(step.evidenceRefs, other.evidenceRefs);
  }
}
// Journal lookup helper: finds whether a proposed write already happened or needs external readback.
function actionState(input, action, actionKey) {
  return input.processedActions.find(
    (a) => a.action === action && a.key === actionKey,
  )?.state;
}
// Suppresses applied writes and holds pending or uncertain writes for readback; eligible new or failed actions remain proposals.
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

// Applies replay/readback rules to notification eligibility too. It records eligibility only and sends no message.
function setNotificationEligibility(input, decision, actionKey) {
  const state = actionState(input, "notify", actionKey);
  decision.notificationEligible = !state || state === "failed";
  if (state === "pending" || state === "uncertain")
    decision.neededEvidence = sorted([
      ...(decision.neededEvidence ?? []),
      "notify external readback",
    ]);
}

// Reconciles one run against existing tickets and prior actions. Produces create/update/reopen proposals,
// summary-only non-observations, or review requests; it never performs external writes.
export function plan(raw) {
  const input = validateEnvelope(raw);
  const quarantined = [],
    coverage = [],
    retests = [],
    observations = [];
  // Isolation helper: records invalid items for review while keeping independent valid findings available to the planner.
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
    known = input.existing.map((e, index) => {
      let identity;
      try {
        identity = identityOf(e);
      } catch (error) {
        throw new InputError(
          `$.existing[${index}].normalizedChain`,
          error.message,
        );
      }
      const identityAliases =
        e.identityAliases?.map((alias, aliasIndex) => {
          try {
            return identityOf(alias);
          } catch (error) {
            throw new InputError(
              `$.existing[${index}].identityAliases[${aliasIndex}].normalizedChain`,
              error.message,
            );
          }
        }) ?? [];
      return {
        record: e,
        identity,
        identityAliases,
        fingerprint: fingerprint(e),
        existing: true,
      };
    });
  const rawIdCounts = new Map();
  for (const item of input.observations) {
    const id = item?.observationId;
    if (typeof id === "string")
      rawIdCounts.set(id, (rawIdCounts.get(id) ?? 0) + 1);
  }
  const expanded = observations.flatMap(({ value }) =>
    splitCauses(value).map((observation) => ({
      observation,
      sourceId: value.observationId,
    })),
  );
  const expandedIdCounts = new Map();
  for (const { observation: o } of expanded)
    expandedIdCounts.set(
      o.observationId,
      (expandedIdCounts.get(o.observationId) ?? 0) + 1,
    );
  const decisionSources = new Map();
  for (const { observation: o, sourceId } of expanded) {
    if (!decisionSources.has(o.observationId))
      decisionSources.set(o.observationId, new Set());
    decisionSources.get(o.observationId).add(sourceId);
  }
  // Confirmed evidence survives a blocked ticket action; action eligibility is separate.
  const observedExploits = new Set();
  // Candidate matches are uncertain evidence, not absence. Retain raw sources for review.
  const ambiguousSources = new Map();
  const positiveExploits = new Set(),
    allCandidates = [...known];
  for (const { observation: o, sourceId } of expanded.sort((a, b) =>
    compare(a.observation.observationId, b.observation.observationId),
  )) {
    if (
      rawIdCounts.get(sourceId) > 1 ||
      expandedIdCounts.get(o.observationId) > 1
    ) {
      decisions.push(
        evidenceDecision(o, "duplicate observationId in run", [
          "unique observation identity",
        ]),
      );
      continue;
    }
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
        evidenceDecision(o, e.message, [
          "one terminal control and explicit actor/resource tenant references",
        ]),
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
    // Explicit independent causes from one source do not make each other ambiguous.
    // Exact matches still deduplicate; unrelated sources and stored tickets still need review.
    const plausible = allCandidates.filter(
      (c) =>
        c.sourceId !== sourceId &&
        c.identity.environment === identity.environment &&
        c.identity.surface === identity.surface &&
        (c.identity.violatedBoundary === identity.violatedBoundary ||
          c.record.fingerprintAliases?.includes(fp)),
    );
    if (exact.length > 1 || (!exact.length && plausible.length)) {
      const candidateExploitIds = sorted(
        (exact.length ? exact : plausible).map((c) => c.record.exploitId),
      );
      for (const id of candidateExploitIds) {
        if (!ambiguousSources.has(id)) ambiguousSources.set(id, new Set());
        ambiguousSources.get(id).add(sourceId);
      }
      decisions.push({
        ...evidenceDecision(
          o,
          `ambiguous causal identity: ${candidateExploitIds.join(", ")}`,
          ["review candidate identity and causal evidence"],
        ),
        candidateExploitIds,
      });
      continue;
    }
    const match = exact[0];
    const exploitId =
      match?.record.exploitId ??
      `proposed-${hash(identityString(o)).slice(0, 20)}`;
    observedExploits.add(exploitId);
    if (positiveExploits.has(exploitId)) {
      const primary = decisions.find((d) => d.exploitId === exploitId);
      primary.evidenceRefs = sorted([
        ...primary.evidenceRefs,
        ...evidenceOf(o),
      ]);
      if (primary.ticketDraft)
        mergeDraft(primary.ticketDraft, o, match.record.transitions);
      decisions.push({
        observationId: o.observationId,
        outcome: primary.outcome,
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
        sourceId,
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
        setNotificationEligibility(input, d, d.episodeKey);
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
      d.episodeKey = key("new", exploitId);
      setNotificationEligibility(input, d, d.episodeKey);
      d.countChange = { runId: input.run.id, historicalCount: null };
    }
    if (d.neededEvidence?.length) d.notificationEligible = false;
    positiveExploits.add(exploitId);
    decisions.push(d);
  }
  // Count raw records too: an invalid duplicate must not leave the other copy authoritative.
  const retestCounts = new Map();
  for (const r of input.retests) {
    if (typeof r?.exploitId === "string")
      retestCounts.set(r.exploitId, (retestCounts.get(r.exploitId) ?? 0) + 1);
  }
  for (const { value: r } of retests) {
    if (retestCounts.get(r.exploitId) > 1) {
      decisions.push({
        outcome: "unresolved",
        exploitId: r.exploitId,
        reason: "duplicate retest records name the same exploit",
        evidenceRefs: r.evidenceRefs,
        proposedActions: [],
        notificationEligible: false,
        neededEvidence: ["one combined retest record per exploit per run"],
      });
      continue;
    }
    // A retest must name a known exploit and a reviewed surface before it can report coverage.
    const candidate = allCandidates.find(
      (c) =>
        c.record.exploitId === r.exploitId &&
        (c.existing || positiveExploits.has(r.exploitId)),
    );
    const expectedSurfaces = candidate
      ? sorted([
          candidate.identity.surface,
          ...(candidate.identityAliases ?? []).map((a) => a.surface),
        ])
      : [];
    if (!candidate || !expectedSurfaces.includes(canonical(r.targetSurface))) {
      decisions.push({
        outcome: "unresolved",
        exploitId: r.exploitId,
        targetSurface: r.targetSurface,
        reason: candidate
          ? "retest surface does not match the known exploit"
          : "retest references an unknown exploit",
        expectedSurfaces,
        evidenceRefs: r.evidenceRefs,
        proposedActions: [],
        notificationEligible: false,
        neededEvidence: [
          candidate
            ? "retest of a reviewed exploit surface"
            : "known exploit record",
        ],
      });
      continue;
    }
    // Each source can contain several independent causes. It supports this retest
    // when one resolved cause matches; sibling causes keep their own decisions.
    const unsupportedObservationIds = sorted(r.observedObservationIds).filter(
      (id) => {
        const supportsExploit = decisions.some(
          (d) =>
            decisionSources.get(d.observationId)?.has(id) &&
            d.exploitId === r.exploitId &&
            d.outcome !== "unresolved",
        );
        return !supportsExploit;
      },
    );
    if (unsupportedObservationIds.length) {
      decisions.push({
        outcome: "unresolved",
        exploitId: r.exploitId,
        reason:
          "retest cites an unresolved, invalid, missing, or mismatched observation",
        unsupportedObservationIds,
        evidenceRefs: r.evidenceRefs,
        proposedActions: [],
        notificationEligible: false,
        neededEvidence: ["resolved observation linked to the retested exploit"],
      });
      continue;
    }
    if (observedExploits.has(r.exploitId)) continue;
    if (ambiguousSources.has(r.exploitId)) {
      decisions.push({
        outcome: "unresolved",
        exploitId: r.exploitId,
        reason: "confirmed evidence in this run possibly matches this exploit",
        ambiguousObservationIds: sorted([...ambiguousSources.get(r.exploitId)]),
        evidenceRefs: r.evidenceRefs,
        proposedActions: [],
        notificationEligible: false,
        neededEvidence: ["identity review of the ambiguous observations"],
      });
      continue;
    }
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
  // Preserve exact input provenance for every valid observation outcome.
  for (const d of decisions) {
    const sources = decisionSources.get(d.observationId);
    if (sources?.size === 1) d.sourceObservationId = [...sources][0];
  }
  for (const q of quarantined.filter((q) => q.collection === "observations")) {
    const rawId = input.observations[q.index]?.observationId;
    const sourceObservationId = typeof rawId === "string" ? rawId : undefined;
    decisions.push({
      observationId:
        sourceObservationId === undefined || !sourceObservationId.isWellFormed()
          ? undefined
          : encodeURIComponent(sourceObservationId),
      sourceObservationId,
      inputIndex: q.index,
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
      proposedExploitIds: sorted(
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
