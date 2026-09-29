// Reports which input field needs correction so invalid evidence cannot silently produce a ticket proposal.
export class InputError extends Error {
  // Callers must not put the rejected value in message because the planner copies this text into its output.
  constructor(path, message) {
    super(`${path}: ${message}`);
    this.name = "InputError";
    this.path = path;
  }
}

// Shape-checking helper: rejects a missing or non-record value before callers inspect its fields.
export function object(value, path) {
  if (!value || typeof value !== "object" || Array.isArray(value))
    throw new InputError(path, "expected object");
  return value;
}
// Text-checking helper: rejects empty text and malformed Unicode before identity encoding or report output.
export function string(value, path) {
  if (typeof value !== "string" || !value.trim())
    throw new InputError(path, "expected nonempty string");
  if (!value.isWellFormed())
    throw new InputError(path, "expected well-formed Unicode");
  return value;
}
// State-checking helper: prevents an unknown status from being treated as a supported lifecycle decision.
export function oneOf(value, choices, path) {
  if (!choices.includes(value))
    throw new InputError(path, `expected ${choices.join("|")}`);
  return value;
}
// Collection helper: rejects the wrong container type before callers validate each independent item.
export function list(value, path) {
  if (!Array.isArray(value)) throw new InputError(path, "expected array");
  return value;
}
// List helper for references and instructions; callers can require at least one entry where missing evidence blocks a proposal.
export function strings(value, path, nonempty = false) {
  const a = list(value, path).map((v, i) => string(v, `${path}[${i}]`));
  if (nonempty && !a.length)
    throw new InputError(path, "expected at least one item");
  return a;
}
// Optional-field helper: permits absent metadata without accepting malformed text when it is supplied.
function optionalString(value, path) {
  if (value !== undefined) string(value, path);
}
// Identity helper: rejects repeated keys where they would make a referenced record or step ambiguous.
function unique(values, path) {
  if (new Set(values).size !== values.length)
    throw new InputError(path, "duplicate identity");
}
// Checks the structure of one attack step so matching can compare actors, resources and controls.
// References identify supplied evidence; this check does not verify a live exploit.
function transition(value, path) {
  const t = object(value, path);
  const proseFields = [
    "actorCapability",
    "resourceRelation",
    "targetClass",
    "operation",
    "expectedBoundary",
    "observedEffect",
  ];
  for (const k of [
    "stepId",
    "actorTenantRef",
    "resourceTenantRef",
    ...proseFields,
  ])
    string(t[k], `${path}.${k}`);
  strings(t.prerequisiteStepIds, `${path}.prerequisiteStepIds`);
  strings(t.evidenceRefs, `${path}.evidenceRefs`, true);
  for (const k of ["actorTenantRef", "resourceTenantRef"])
    if (!/^[A-Za-z0-9][A-Za-z0-9._:-]*$/.test(t[k]))
      throw new InputError(
        `${path}.${k}`,
        "expected a safe opaque tenant reference",
      );
  const allowedPlaceholders = new Set(["{actorTenant}", "{resourceTenant}"]);
  const tenantPlaceholder = /\{\s*(actor|resource)[\s_-]*tenant\s*\}/gi;
  for (const k of proseFields) {
    const unknown = [...t[k].matchAll(tenantPlaceholder)]
      .map(([token]) => token)
      .find((token) => !allowedPlaceholders.has(token));
    if (unknown)
      throw new InputError(
        `${path}.${k}`,
        "unknown placeholder; use actorTenant or resourceTenant exactly",
      );
  }
  return t;
}
// Checks that a chain has uniquely named steps and valid, cycle-free dependencies,
// so a ticket can describe how the observed effect was reached.
function chain(value, path) {
  const ts = list(value, path).map((v, i) => transition(v, `${path}[${i}]`));
  if (!ts.length)
    throw new InputError(path, "expected at least one transition");
  unique(
    ts.map((t) => t.stepId),
    `${path}.stepId`,
  );
  const ids = new Set(ts.map((t) => t.stepId));
  for (let i = 0; i < ts.length; i++)
    for (const p of ts[i].prerequisiteStepIds) {
      if (!ids.has(p) || p === ts[i].stepId)
        throw new InputError(
          `${path}[${i}].prerequisiteStepIds`,
          "invalid prerequisite reference",
        );
    }
  const byId = new Map(ts.map((t) => [t.stepId, t])),
    visited = new Set(),
    active = new Set();
  // Traversal helper: rejects circular prerequisites because they cannot describe an executable attack path.
  function visit(id) {
    if (active.has(id)) throw new InputError(path, "causal prerequisite cycle");
    if (visited.has(id)) return;
    active.add(id);
    for (const p of byId.get(id).prerequisiteStepIds) visit(p);
    active.delete(id);
    visited.add(id);
  }
  for (const id of ids) visit(id);
  return ts;
}
// Rejects invalid shared run, session, stored-ticket or action state before any finding is processed.
// One bad shared record can make all ticket decisions unsafe; per-finding validation is separate.
export function validateEnvelope(input) {
  const x = object(input, "$");
  if (x.schemaVersion !== 1)
    throw new InputError("$.schemaVersion", "expected 1");
  const r = object(x.run, "$.run");
  for (const k of [
    "id",
    "pathId",
    "instructionsRevision",
    "instructionsSha256",
    "operatorId",
    "evidencePrefix",
    "evidenceRetentionPolicyRef",
  ])
    string(r[k], `$.run.${k}`);
  if (!/^[A-Za-z0-9._-]+$/.test(r.id))
    throw new InputError("$.run.id", "expected opaque path-safe run ID");
  if (!/^[a-f0-9]{64}$/i.test(r.instructionsSha256))
    throw new InputError(
      "$.run.instructionsSha256",
      "expected 64 hexadecimal characters",
    );
  const prefix =
    /^gs:\/\/([a-z0-9][a-z0-9._-]{2,221})\/([A-Za-z0-9._/-]+)\/$/.exec(
      r.evidencePrefix,
    );
  if (!prefix)
    throw new InputError(
      "$.run.evidencePrefix",
      "expected path-safe gs:// bucket prefix ending in / without query or fragment",
    );
  const segments = prefix[2].split("/");
  if (
    segments.some((segment) => !segment || segment === "." || segment === "..")
  )
    throw new InputError(
      "$.run.evidencePrefix",
      "expected nonempty path segments without traversal",
    );
  if (!segments.includes(r.id))
    throw new InputError(
      "$.run.evidencePrefix",
      "expected a path segment equal to run ID",
    );
  oneOf(r.environment, ["party"], "$.run.environment");
  const targets = strings(r.authorizedTargets, "$.run.authorizedTargets", true);
  for (let i = 0; i < targets.length; i++) {
    let url;
    try {
      url = new URL(targets[i]);
    } catch {
      throw new InputError(
        `$.run.authorizedTargets[${i}]`,
        "expected absolute HTTPS URL",
      );
    }
    if (
      url.protocol !== "https:" ||
      !url.hostname ||
      url.username ||
      url.password ||
      url.search ||
      url.hash
    )
      throw new InputError(
        `$.run.authorizedTargets[${i}]`,
        "expected credential-free HTTPS URL without query or fragment",
      );
  }
  const harness = object(r.harness, "$.run.harness");
  string(harness.name, "$.run.harness.name");
  string(harness.revision, "$.run.harness.revision");
  const model = object(r.model, "$.run.model");
  string(model.provider, "$.run.model.provider");
  string(model.id, "$.run.model.id");
  optionalString(model.effort, "$.run.model.effort");
  if (
    typeof r.budgetUsd !== "number" ||
    !Number.isFinite(r.budgetUsd) ||
    r.budgetUsd <= 0
  )
    throw new InputError("$.run.budgetUsd", "expected positive finite number");
  if (
    typeof r.deadline !== "string" ||
    !/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z$/.test(r.deadline) ||
    Number.isNaN(Date.parse(r.deadline))
  )
    throw new InputError("$.run.deadline", "expected UTC ISO timestamp");
  oneOf(
    r.session,
    ["not_started", "validated", "lost", "unknown"],
    "$.run.session",
  );
  oneOf(
    r.assessment,
    ["not_started", "completed", "interrupted"],
    "$.run.assessment",
  );
  optionalString(r.stopReason, "$.run.stopReason");
  optionalString(r.edgePolicyRef, "$.run.edgePolicyRef");
  const sessions = list(x.sessionEvents, "$.sessionEvents").map((v, i) => {
    const s = object(v, `$.sessionEvents[${i}]`);
    string(s.ref, `$.sessionEvents[${i}].ref`);
    if (!Number.isSafeInteger(s.sequence) || s.sequence < 0)
      throw new InputError(
        `$.sessionEvents[${i}].sequence`,
        "expected nonnegative integer",
      );
    oneOf(
      s.state,
      ["validated", "rotated", "lost"],
      `$.sessionEvents[${i}].state`,
    );
    for (const k of ["actorRole", "partyRef", "jarRef"])
      optionalString(s[k], `$.sessionEvents[${i}].${k}`);
    if (s.state === "validated" && (!s.actorRole || !s.partyRef || !s.jarRef))
      throw new InputError(
        `$.sessionEvents[${i}]`,
        "validated event needs actorRole, partyRef, jarRef",
      );
    if (s.state === "validated" && s.actorRole !== "non-admin-developer")
      throw new InputError(
        `$.sessionEvents[${i}].actorRole`,
        "expected non-admin-developer for a validated session",
      );
    return s;
  });
  unique(
    sessions.map((s) => s.ref),
    "$.sessionEvents.ref",
  );
  unique(
    sessions.map((s) => s.sequence),
    "$.sessionEvents.sequence",
  );
  sessions.sort((a, b) => a.sequence - b.sequence);
  const existing = list(x.existing, "$.existing").map((v, i) => {
    const p = `$.existing[${i}]`,
      e = object(v, p);
    for (const k of [
      "exploitId",
      "linearIssueId",
      "surface",
      "violatedBoundary",
    ])
      string(e[k], `${p}.${k}`);
    oneOf(e.environment, ["party"], `${p}.environment`);
    oneOf(e.state, ["open", "claimed_fixed", "unknown"], `${p}.state`);
    if (![true, false, null].includes(e.issueOpen))
      throw new InputError(`${p}.issueOpen`, "expected boolean or null");
    if (e.state === "claimed_fixed" && (!e.fixClaimId || !e.claimRef))
      throw new InputError(p, "claimed_fixed needs fixClaimId and claimRef");
    optionalString(e.fixClaimId, `${p}.fixClaimId`);
    optionalString(e.claimRef, `${p}.claimRef`);
    if (!Number.isSafeInteger(e.identityVersion) || e.identityVersion < 1)
      throw new InputError(`${p}.identityVersion`, "expected positive integer");
    strings(e.fingerprintAliases, `${p}.fingerprintAliases`);
    chain(e.normalizedChain, `${p}.normalizedChain`);
    if (e.identityAliases !== undefined) {
      list(e.identityAliases, `${p}.identityAliases`).forEach((alias, j) => {
        const ap = `${p}.identityAliases[${j}]`,
          a = object(alias, ap);
        oneOf(a.environment, ["party"], `${ap}.environment`);
        string(a.surface, `${ap}.surface`);
        string(a.violatedBoundary, `${ap}.violatedBoundary`);
        chain(a.normalizedChain, `${ap}.normalizedChain`);
      });
    }
    if (e.confirmedRunIds !== null)
      strings(e.confirmedRunIds, `${p}.confirmedRunIds`);
    if (
      e.historicalCount !== null &&
      (!Number.isSafeInteger(e.historicalCount) || e.historicalCount < 0)
    )
      throw new InputError(
        `${p}.historicalCount`,
        "expected nonnegative integer or null",
      );
    return e;
  });
  unique(
    existing.map((e) => e.exploitId),
    "$.existing.exploitId",
  );
  unique(
    existing.map((e) => e.linearIssueId),
    "$.existing.linearIssueId",
  );
  const actions = list(x.processedActions, "$.processedActions").map((v, i) => {
    const p = `$.processedActions[${i}]`,
      a = object(v, p);
    string(a.key, `${p}.key`);
    oneOf(
      a.action,
      ["create", "append_evidence", "increment_run_count", "reopen", "notify"],
      `${p}.action`,
    );
    oneOf(a.state, ["applied", "pending", "uncertain", "failed"], `${p}.state`);
    optionalString(a.externalMarker, `${p}.externalMarker`);
    return a;
  });
  unique(
    actions.map((a) => `${a.action}:${a.key}`),
    "$.processedActions",
  );
  for (const k of ["coverage", "retests", "observations"]) list(x[k], `$.${k}`);
  return { ...x, sessionEvents: sessions, existing, processedActions: actions };
}

// Checks one finding's required fields, chain and declared causes before matching it to tickets.
// A failure isolates this finding; it does not discard independent valid findings or prove evidence authenticity.
export function validateObservation(value, path) {
  const o = object(value, path);
  for (const k of [
    "observationId",
    "rawFindingRef",
    "sessionRef",
    "surface",
    "violatedBoundary",
    "actorRole",
    "impact",
    "severity",
  ])
    string(o[k], `${path}.${k}`);
  oneOf(o.status, ["confirmed", "incomplete"], `${path}.status`);
  oneOf(o.environment, ["party"], `${path}.environment`);
  if (!Number.isSafeInteger(o.observedSequence) || o.observedSequence < 0)
    throw new InputError(
      `${path}.observedSequence`,
      "expected nonnegative integer",
    );
  const transitions = chain(o.transitions, `${path}.transitions`);
  const incidental =
    o.incidentalStepIds === undefined
      ? []
      : strings(o.incidentalStepIds, `${path}.incidentalStepIds`);
  unique(incidental, `${path}.incidentalStepIds`);
  const ids = new Set(transitions.map((t) => t.stepId));
  for (const id of incidental)
    if (!ids.has(id))
      throw new InputError(`${path}.incidentalStepIds`, "unknown transition");
  const remaining = transitions.filter((t) => !incidental.includes(t.stepId));
  if (!remaining.length)
    throw new InputError(`${path}.transitions`, "no causal transition remains");
  if (
    remaining.some((t) =>
      t.prerequisiteStepIds.some((id) => incidental.includes(id)),
    )
  )
    throw new InputError(
      `${path}.incidentalStepIds`,
      "incidental step is a causal prerequisite",
    );
  const prerequisites = new Set(
    remaining.flatMap((t) => t.prerequisiteStepIds),
  );
  const terminals = remaining.filter((t) => !prerequisites.has(t.stepId));
  if (o.causes !== undefined) {
    const causes = list(o.causes, `${path}.causes`);
    if (!causes.length)
      throw new InputError(`${path}.causes`, "expected at least one cause");
    for (let i = 0; i < causes.length; i++) {
      const c = object(causes[i], `${path}.causes[${i}]`);
      for (const k of [
        "causeId",
        "surface",
        "violatedBoundary",
        "terminalStepId",
        "impact",
        "severity",
      ])
        string(c[k], `${path}.causes[${i}].${k}`);
      strings(c.remediation, `${path}.causes[${i}].remediation`, true);
      strings(c.retest, `${path}.causes[${i}].retest`, true);
      const cp = object(
        c.productionImpact,
        `${path}.causes[${i}].productionImpact`,
      );
      oneOf(
        cp.value,
        ["yes", "no", "unknown"],
        `${path}.causes[${i}].productionImpact.value`,
      );
      string(cp.rationale, `${path}.causes[${i}].productionImpact.rationale`);
      if (c.components !== undefined)
        strings(c.components, `${path}.causes[${i}].components`);
      if (c.blockedSteps !== undefined)
        strings(c.blockedSteps, `${path}.causes[${i}].blockedSteps`);
      if (c.dangerousNotExecuted !== undefined)
        strings(
          c.dangerousNotExecuted,
          `${path}.causes[${i}].dangerousNotExecuted`,
        );
      if (!transitions.some((t) => t.stepId === c.terminalStepId))
        throw new InputError(
          `${path}.causes[${i}].terminalStepId`,
          "unknown transition",
        );
    }
    unique(
      causes.map((c) => c.causeId),
      `${path}.causes.causeId`,
    );
    unique(
      causes.map((c) => c.terminalStepId),
      `${path}.causes.terminalStepId`,
    );
    if (
      causes.length !== terminals.length ||
      causes.some((c) => !terminals.some((t) => t.stepId === c.terminalStepId))
    )
      throw new InputError(
        `${path}.causes`,
        "every non-incidental terminal control needs exactly one cause",
      );
  } else if (terminals.length !== 1) {
    throw new InputError(
      `${path}.transitions`,
      "multiple terminal controls need explicit causes or incidentalStepIds",
    );
  }
  strings(o.preconditions, `${path}.preconditions`, true);
  const p = object(o.productionImpact, `${path}.productionImpact`);
  oneOf(p.value, ["yes", "no", "unknown"], `${path}.productionImpact.value`);
  string(p.rationale, `${path}.productionImpact.rationale`);
  strings(o.remediation, `${path}.remediation`, true);
  strings(o.retest, `${path}.retest`, true);
  if (o.components !== undefined) strings(o.components, `${path}.components`);
  if (o.blockedSteps !== undefined)
    strings(o.blockedSteps, `${path}.blockedSteps`);
  if (o.dangerousNotExecuted !== undefined)
    strings(o.dangerousNotExecuted, `${path}.dangerousNotExecuted`);
  return o;
}
// Keeps retest execution state separate from observation results. Checks the supplied links and attempts
// so an interrupted or unattempted test cannot be presented as a completed retest.
export function validateRetest(value, path) {
  const r = object(value, path);
  string(r.exploitId, `${path}.exploitId`);
  string(r.targetSurface, `${path}.targetSurface`);
  strings(r.attemptedOperations, `${path}.attemptedOperations`);
  strings(r.observedObservationIds, `${path}.observedObservationIds`);
  oneOf(
    r.execution,
    ["completed", "interrupted", "not_attempted"],
    `${path}.execution`,
  );
  if (r.execution === "not_attempted" && r.observedObservationIds.length)
    throw new InputError(
      `${path}.observedObservationIds`,
      "a not_attempted retest cannot cite observations",
    );
  strings(r.conditions, `${path}.conditions`);
  strings(r.evidenceRefs, `${path}.evidenceRefs`);
  optionalString(r.stopReason, `${path}.stopReason`);
  return r;
}
// Checks coverage fields for the run summary, including tested, interrupted and not_attempted states;
// missing coverage must not become a claim that an exploit is absent.
export function validateCoverage(value, path) {
  const c = object(value, path);
  string(c.surface, `${path}.surface`);
  optionalString(c.target, `${path}.target`);
  oneOf(c.status, ["tested", "interrupted", "not_attempted"], `${path}.status`);
  strings(c.attemptedOperations, `${path}.attemptedOperations`);
  strings(c.conditions, `${path}.conditions`);
  strings(c.evidenceRefs, `${path}.evidenceRefs`);
  optionalString(c.stopReason, `${path}.stopReason`);
  return c;
}
