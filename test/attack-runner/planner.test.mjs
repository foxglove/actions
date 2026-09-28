import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import {
  plan,
  identityOf,
  canonical,
} from "../../src/attack-runner/planner.mjs";

// Acceptance IDs in test names refer to docs/aegis/review/acceptance.md
// (Offline planner acceptance). Names state the behavior; IDs preserve traceability.
const fixture = JSON.parse(
  await readFile(
    new URL("./fixtures/new-cross-tenant-export.json", import.meta.url),
  ),
);
// Fixture helper: gives each case its own cross-tenant exploit record so changes cannot affect another test.
const fresh = () => structuredClone(fixture);
// Fixture helper: creates a ticket for the same causal chain so tests can vary open, fixed and uncertain states.
function existing(x, state = "open", issueOpen = true) {
  const o = x.observations[0];
  return {
    exploitId: "EXP-1",
    linearIssueId: "LIN-1",
    state,
    issueOpen,
    fixClaimId: state === "claimed_fixed" ? "CLAIM-1" : undefined,
    claimRef: state === "claimed_fixed" ? "synthetic-claim-ref" : undefined,
    environment: o.environment,
    surface: o.surface,
    violatedBoundary: o.violatedBoundary,
    normalizedChain: structuredClone(o.transitions),
    identityVersion: 1,
    fingerprintAliases: [],
    confirmedRunIds: [],
    historicalCount: 7,
  };
}
// Assertion helper for single-finding cases: selects the ticket decision being tested.
const first = (x) => plan(x).decisions[0];

test("New exploit gets a complete ticket with unknown ownership and stated production-impact limits [E1-01 E1-14]", () => {
  const x = fresh();
  delete x.observations[0].components;
  const d = first(x);
  assert.equal(d.outcome, "new");
  assert.deepEqual(d.proposedActions, ["create"]);
  assert.deepEqual(d.ticketDraft.labels, ["Bug", "pentesting", "harness"]);
  assert.deepEqual(d.ticketDraft.components, ["unknown"]);
  assert.equal(d.ticketDraft.activityChain.length, 2);
  assert.equal(
    d.ticketDraft.activityChain[1].resourceRelation,
    "tenant-B export is not owned by tenant-A",
  );
  assert.ok(
    !JSON.stringify(d.ticketDraft.activityChain).includes("{actorTenant}"),
  );
  assert.ok(
    !JSON.stringify(d.ticketDraft.activityChain).includes("{resourceTenant}"),
  );
  assert.equal(d.ticketDraft.productionImpact.value, "unknown");
  assert.ok(d.ticketDraft.remediation.length && d.ticketDraft.retest.length);
  x.processedActions = [
    { key: d.episodeKey, action: "notify", state: "failed" },
  ];
  assert.equal(first(x).notificationEligible, true);
});

test("Open ticket receives evidence and one count per run without another notification [E1-02 E1-09]", () => {
  const x = fresh();
  x.existing = [existing(x)];
  const d = first(x);
  assert.equal(d.outcome, "rediscovered");
  assert.equal(d.issueId, "LIN-1");
  assert.deepEqual(d.proposedActions, [
    "append_evidence",
    "increment_run_count",
  ]);
  assert.equal(d.notificationEligible, false);
  assert.equal(d.countChange.historicalCount, 7);
  x.run.id = "R-SECOND";
  x.run.evidencePrefix = "gs://synthetic-private-fixture/R-SECOND/";
  assert.deepEqual(first(x).proposedActions, d.proposedActions);
  assert.notEqual(first(x).confirmationKey, d.confirmationKey);
});

test("Evidence against a fix reopens the same ticket only when it is closed [E1-03 E1-19]", () => {
  const x = fresh();
  x.existing = [existing(x, "claimed_fixed", false)];
  let d = first(x);
  assert.equal(d.outcome, "contradicts_fix");
  assert.equal(d.issueId, "LIN-1");
  assert.ok(d.reason.includes("CLAIM-1"));
  assert.ok(d.proposedActions.includes("reopen"));
  assert.equal(d.notificationEligible, true);
  x.existing[0].issueOpen = true;
  d = first(x);
  assert.ok(!d.proposedActions.includes("reopen"));
  x.processedActions = [
    { key: d.episodeKey, action: "notify", state: "applied" },
  ];
  x.run.id = "R-SECOND";
  x.run.evidencePrefix = "gs://synthetic-private-fixture/R-SECOND/";
  d = first(x);
  assert.equal(d.notificationEligible, false);
  assert.ok(d.proposedActions.includes("append_evidence"));
  x.existing[0].fixClaimId = "CLAIM-2";
  assert.equal(first(x).notificationEligible, true);
  x.processedActions = [
    { key: first(x).episodeKey, action: "notify", state: "failed" },
  ];
  assert.equal(first(x).notificationEligible, true);
});

test("No finding leaves the ticket unchanged whether the retest completed, stopped or never started [E1-04 E1-05 E1-06]", () => {
  for (const execution of ["completed", "interrupted", "not_attempted"]) {
    const x = fresh();
    x.observations = [];
    x.existing = [existing(fresh(), "claimed_fixed", false)];
    x.retests = [
      {
        exploitId: "EXP-1",
        targetSurface: "export-download",
        attemptedOperations: execution === "not_attempted" ? [] : ["download"],
        observedObservationIds: [],
        execution,
        conditions: ["fixture condition"],
        stopReason: execution === "interrupted" ? "session lost" : undefined,
        evidenceRefs: ["E-RETEST"],
      },
    ];
    const p = plan(x),
      d = p.decisions[0];
    assert.equal(d.outcome, "not_observed");
    assert.deepEqual(d.proposedActions, []);
    assert.equal(d.execution, execution);
    assert.equal(p.summary.nonObservations.length, 1);
    assert.equal(p.summary.deliveryState, "proposed_only");
  }
  const x = fresh();
  x.observations = [];
  x.existing = [existing(fresh(), "claimed_fixed", false)];
  assert.deepEqual(plan(x).decisions, []);
});

test("Evidence before session loss remains valid; evidence after loss or a wrong start needs review [E1-07]", () => {
  const x = fresh();
  x.sessionEvents.push({ ref: "LOST", sequence: 3, state: "lost" });
  assert.equal(first(x).outcome, "new");
  x.observations[0].observedSequence = 4;
  assert.equal(first(x).outcome, "unresolved");
  x.observations[0].observedSequence = 2;
  x.sessionEvents[0].actorRole = "admin";
  assert.throws(() => plan(x), /sessionEvents\[0\]\.actorRole/);
  x.sessionEvents[0].actorRole = "developer administrator";
  assert.throws(() => plan(x), /sessionEvents\[0\]\.actorRole/);
  x.sessionEvents[0].actorRole = "developer owner";
  assert.throws(() => plan(x), /sessionEvents\[0\]\.actorRole/);
  x.sessionEvents[0].actorRole = "non-admin-developer";
  x.sessionEvents.splice(1, 0, {
    ref: "ROTATED",
    sequence: 1.5,
    state: "rotated",
    jarRef: "cookie-jar-tenant-a",
  });
  // Invalid shared session sequence must reject, rather than manufacture provenance.
  assert.throws(() => plan(x), /sequence/);
  x.sessionEvents[1].sequence = 2;
  x.observations[0].observedSequence = 3;
  x.sessionEvents[2].sequence = 4;
  assert.equal(first(x).outcome, "new");
});

test("Duplicate observations and applied event state avoid repeat mutations [E1-08]", () => {
  const x = fresh();
  x.existing = [existing(x)];
  x.observations.push(structuredClone(x.observations[0]));
  x.observations[1].observationId = "observation-cross-tenant-export-copy";
  let ds = plan(x).decisions;
  assert.equal(
    ds.filter((d) => d.proposedActions.includes("append_evidence")).length,
    1,
  );
  const k = ds[0].actionKeys.append_evidence;
  x.processedActions = [
    { key: k, action: "append_evidence", state: "applied" },
    { key: k, action: "increment_run_count", state: "applied" },
  ];
  ds = plan(x).decisions;
  assert.ok(ds.every((d) => d.proposedActions.length === 0));
});

test("Duplicate observations keep the primary fix-contradiction outcome", () => {
  const x = fresh();
  x.existing = [existing(x, "claimed_fixed", false)];
  x.observations.push({
    ...structuredClone(x.observations[0]),
    observationId: "observation-cross-tenant-export-copy",
  });
  assert.deepEqual(
    plan(x).decisions.map((d) => d.outcome),
    ["contradicts_fix", "contradicts_fix"],
  );
});

test("Repository/path/model and fingerprint version do not change established identity [E1-10 E1-17 E1-20]", () => {
  const x = fresh();
  x.existing = [existing(x)];
  x.run.pathId = "other-path";
  x.run.model.id = "other-model";
  x.observations[0].components = ["another-repository"];
  x.existing[0].identityVersion = 1;
  x.existing[0].fingerprintAliases = ["v1:legacy"];
  assert.equal(first(x).outcome, "rediscovered");
  assert.equal(first(x).exploitId, "EXP-1");
  assert.ok(first(x).normalizedMatchReason.includes("causal prerequisites"));
  assert.equal(
    identityOf(x.observations[0]).surface,
    identityOf(x.existing[0]).surface,
  );
  const changed = x.observations[0];
  changed.transitions[0].stepId = "z-prerequisite";
  changed.transitions[1].prerequisiteStepIds = ["z-prerequisite"];
  changed.transitions[1].stepId = "a-control";
  changed.transitions[1].resourceRelation =
    "tenant-B export-456 is not owned by tenant-A";
  x.existing[0].normalizedChain[1].resourceRelation =
    "tenant-B export-123 is not owned by tenant-A";
  changed.transitions[1].evidenceRefs.reverse();
  changed.transitions.push({
    ...structuredClone(changed.transitions[0]),
    stepId: "zz-recon",
    prerequisiteStepIds: [],
    operation: "scan unrelated endpoint",
    expectedBoundary: "public documentation",
    targetClass: "documentation page",
  });
  changed.incidentalStepIds = ["zz-recon"];
  assert.equal(first(x).outcome, "rediscovered");
});

test("Different control separates identity; plausible duplicate is unresolved [E1-11 E1-18]", () => {
  const x = fresh();
  x.existing = [existing(x)];
  const alternate = structuredClone(x.observations[0]);
  alternate.observationId = "observation-share-token-bypass";
  alternate.violatedBoundary = "share token validation";
  alternate.transitions.at(-1).expectedBoundary = "deny invalid share token";
  x.observations.push(alternate);
  let ds = plan(x).decisions;
  assert.equal(
    ds.find((d) => d.sourceObservationId === x.observations[0].observationId)
      .outcome,
    "rediscovered",
  );
  assert.equal(
    ds.find((d) => d.sourceObservationId === alternate.observationId).outcome,
    "new",
  );
  x.observations = [structuredClone(fixture.observations[0])];
  x.existing.push({
    ...existing(x),
    exploitId: "EXP-2",
    linearIssueId: "LIN-2",
  });
  assert.equal(first(x).outcome, "unresolved");
  assert.deepEqual(first(x).proposedActions, []);
  assert.equal(plan(x).status, "needs_review");
});

test("One raw finding with two explicit causes splits and retains shared prerequisite [E1-18]", () => {
  const x = fresh(),
    o = x.observations[0];
  o.transitions.push({
    ...structuredClone(o.transitions[1]),
    stepId: "share",
    operation: "read export through share token",
    expectedBoundary: "deny invalid share token",
    observedEffect: "invalid share token returned export content",
    prerequisiteStepIds: ["list"],
    evidenceRefs: ["E-SHARE"],
  });
  o.causes = [
    {
      causeId: "ownership",
      surface: "export-download",
      violatedBoundary: "tenant ownership check on export download",
      terminalStepId: "download",
      impact: "ownership impact",
      severity: "high",
      productionImpact: o.productionImpact,
      remediation: ["fix ownership"],
      retest: ["test ownership"],
    },
    {
      causeId: "share",
      surface: "export-share",
      violatedBoundary: "share token validation",
      terminalStepId: "share",
      impact: "share impact",
      severity: "medium",
      productionImpact: o.productionImpact,
      remediation: ["fix share token"],
      retest: ["test share token"],
    },
  ];
  const p = plan(x);
  assert.deepEqual(
    p.decisions.map((d) => d.outcome),
    ["new", "new"],
  );
  assert.equal(p.decisions[0].ticketDraft.activityChain.length, 2);
  assert.equal(p.decisions[1].ticketDraft.activityChain.length, 2);
  assert.ok(
    p.decisions.every((d) =>
      d.evidenceRefs.includes("evidence-list-owned-exports"),
    ),
  );
  assert.deepEqual(
    p.decisions.map((d) => d.ticketDraft.remediation),
    [["fix ownership"], ["fix share token"]],
  );
  // Independent causes can share a surface and a broad boundary description.
  o.causes[1].surface = o.causes[0].surface;
  o.causes[1].violatedBoundary = o.causes[0].violatedBoundary;
  const shared = plan(x);
  assert.deepEqual(
    shared.decisions.map((d) => d.outcome),
    ["new", "new"],
  );
  assert.equal(new Set(shared.decisions.map((d) => d.exploitId)).size, 2);
  assert.ok(
    shared.decisions.every((d) => d.proposedActions.includes("create")),
  );
  // A separate observation is still ambiguous against those two candidates.
  const uncertain = structuredClone(o);
  delete uncertain.causes;
  uncertain.observationId = "Z-OTHER";
  uncertain.transitions = uncertain.transitions.filter(
    (t) => t.stepId !== "share",
  );
  uncertain.transitions[1].observedEffect = "different unexplained effect";
  x.observations.push(uncertain);
  assert.equal(plan(x).decisions.at(-1).outcome, "unresolved");
  x.observations.pop();
  delete o.causes;
  assert.equal(plan(x).status, "partial_failure");
  assert.equal(first(x).outcome, "unresolved");
  assert.deepEqual(first(x).proposedActions, []);
  o.causes = [
    {
      causeId: "ownership",
      surface: "export-download",
      violatedBoundary: "tenant ownership check on export download",
      terminalStepId: "download",
      impact: "ownership impact",
      severity: "high",
      productionImpact: o.productionImpact,
      remediation: ["fix ownership"],
      retest: ["test ownership"],
    },
  ];
  assert.equal(first(x).outcome, "unresolved");
});

test("Reviewed structured alias preserves exploit ID across normalization version [E1-20]", () => {
  const x = fresh(),
    e = existing(x);
  e.identityVersion = 1;
  e.identityAliases = [
    {
      environment: e.environment,
      surface: e.surface,
      violatedBoundary: e.violatedBoundary,
      normalizedChain: structuredClone(e.normalizedChain),
    },
  ];
  e.normalizedChain[1].targetClass = "legacy taxonomy for export operation";
  x.existing = [e];
  const d = first(x);
  assert.equal(d.outcome, "rediscovered");
  assert.equal(d.exploitId, "EXP-1");
  assert.match(d.normalizedMatchReason, /reviewed structured identity alias/);
});

test("Reordering independent prerequisites does not change exploit identity [E1-17]", () => {
  const x = fresh(),
    o = x.observations[0];
  o.transitions[0].operation = "z list exports";
  o.transitions.splice(1, 0, {
    ...structuredClone(o.transitions[0]),
    stepId: "middle",
    operation: "a prepare export",
    prerequisiteStepIds: ["list"],
    evidenceRefs: ["E-MIDDLE"],
  });
  o.transitions[2].prerequisiteStepIds = ["list", "middle"];
  const a = identityOf(o);
  o.transitions[2].prerequisiteStepIds.reverse();
  assert.deepEqual(identityOf(o), a);
});

test("Actor and resource tenant equality remains part of identity [E1-18]", () => {
  const x = fresh(),
    o = x.observations[0];
  o.violatedBoundary = "access check on export download";
  o.transitions[1].resourceRelation = "tenant-A export";
  o.transitions[1].resourceTenantRef = "tenant-A";
  const own = identityOf(o);
  o.transitions[1].resourceRelation = "tenant-B export";
  o.transitions[1].resourceTenantRef = "tenant-B";
  const other = identityOf(o);
  assert.notDeepEqual(own, other);
  assert.match(own.targetResourceRelation, /actor tenant/);
  assert.match(other.targetResourceRelation, /other tenant/);
});

test("Identity keeps security numbers and recognizes organization relations", () => {
  assert.notEqual(
    canonical("HTTP 200 returned export"),
    canonical("HTTP 403 returned export"),
  );
  const x = fresh(),
    o = x.observations[0];
  o.transitions.at(-1).actorCapability = "tenant-12 non-admin developer";
  o.transitions.at(-1).actorTenantRef = "12";
  o.transitions.at(-1).resourceRelation = "org-12 export";
  o.transitions.at(-1).resourceTenantRef = "12";
  const own = identityOf(o);
  o.transitions.at(-1).resourceRelation = "org-34 export";
  o.transitions.at(-1).resourceTenantRef = "34";
  const other = identityOf(o);
  assert.notDeepEqual(own, other);
  assert.match(own.targetResourceRelation, /actor tenant/);
  assert.match(other.targetResourceRelation, /other tenant/);
});

test("Identity ignores generated hex resource IDs after a space", () => {
  assert.equal(
    canonical("download export 7c1f9a2b"),
    canonical("download export 9d8e7f6a"),
  );
});

test("Tenant identity uses structured references instead of role prose", () => {
  const x = fresh(),
    o = x.observations[0];
  o.transitions.at(-1).actorCapability = "tenant-scoped workspace-member";
  o.transitions.at(-1).resourceRelation = "scoped export";
  o.transitions.at(-1).resourceTenantRef = "tenant-A";
  const own = identityOf(o);
  o.transitions.at(-1).resourceTenantRef = "tenant-B";
  const other = identityOf(o);
  assert.notDeepEqual(own, other);
  assert.match(own.targetResourceRelation, /actor tenant/);
  assert.match(other.targetResourceRelation, /other tenant/);
});

test("Opaque tenant references never rewrite prose", () => {
  const x = fresh(),
    o = x.observations[0],
    terminal = o.transitions.at(-1);
  terminal.actorTenantRef = "admin";
  terminal.resourceTenantRef = "export";
  terminal.actorCapability = "non-admin developer";
  terminal.resourceRelation = "export is available to an admin";
  const commonWords = identityOf(o);
  terminal.actorTenantRef = "acme";
  terminal.resourceTenantRef = "globex";
  assert.deepEqual(identityOf(o), commonWords);
});

test("Fixed tenant placeholders express structured relations", () => {
  const x = fresh(),
    o = x.observations[0],
    terminal = o.transitions.at(-1);
  terminal.actorTenantRef = "a";
  terminal.resourceTenantRef = "b";
  terminal.actorCapability = "{actorTenant} non-admin developer";
  terminal.resourceRelation =
    "{resourceTenant} export is not owned by {actorTenant}";
  const shortRefs = identityOf(o);
  terminal.actorTenantRef = "admin";
  terminal.resourceTenantRef = "export";
  assert.deepEqual(identityOf(o), shortRefs);
  assert.match(shortRefs.chain.at(-1).actorCapability, /actor tenant/);
  assert.match(shortRefs.chain.at(-1).resourceRelation, /other tenant/);
});

test("Unknown tenant placeholder variants are rejected", () => {
  for (const placeholder of [
    "{ActorTenant}",
    "{actor-tenant}",
    "{resource tenant}",
  ]) {
    const x = fresh();
    x.observations[0].transitions[0].actorCapability = `${placeholder} non-admin developer`;
    const p = plan(x);
    assert.equal(p.status, "partial_failure");
    assert.match(
      p.quarantined[0].reason,
      /actorCapability.*unknown placeholder/,
    );
  }
});

test("Route templates remain valid prose", () => {
  const x = fresh();
  x.observations[0].transitions[1].targetClass = "GET /api/exports/{exportId}";
  assert.equal(first(x).outcome, "new");
  assert.equal(
    first(x).ticketDraft.activityChain[1].targetClass,
    "GET /api/exports/{exportId}",
  );
});

test("Ambiguous terminal controls are quarantined before identity", () => {
  const x = fresh(),
    o = x.observations[0];
  o.transitions.push({
    ...structuredClone(o.transitions.at(-1)),
    stepId: "second-terminal",
  });
  const d = first(x);
  assert.equal(d.outcome, "unresolved");
  assert.deepEqual(d.neededEvidence, [
    "valid structured observation and evidence references",
  ]);
});

test("Equivalent cross-component evidence merges into one complete ticket regardless of order [E1-10]", () => {
  const x = fresh(),
    a = x.observations[0],
    b = structuredClone(a);
  a.observationId = "O-A";
  a.components = ["repo-A"];
  a.remediation = ["fix first component"];
  b.observationId = "O-B";
  b.components = ["repo-B"];
  b.remediation = ["fix second component"];
  b.retest = ["verify second component"];
  b.transitions[1].evidenceRefs = ["E-B"];
  x.observations = [b, a];
  const before = structuredClone(x);
  const p = plan(x);
  assert.deepEqual(x, before);
  const draft = p.decisions.find((d) =>
    d.proposedActions.includes("create"),
  ).ticketDraft;
  assert.deepEqual(draft.components, ["repo-A", "repo-B"]);
  assert.deepEqual(draft.remediation, [
    "fix first component",
    "fix second component",
  ]);
  assert.ok(draft.evidenceRefs.includes("E-B"));
  assert.ok(draft.activityChain[1].evidenceRefs.includes("E-B"));
  x.observations.reverse();
  const other = plan(x).decisions.find((d) =>
    d.proposedActions.includes("create"),
  ).ticketDraft;
  assert.deepEqual(other, draft);
});

test("Corroborating tenant refs merge evidence into the matching displayed step", () => {
  const x = fresh(),
    a = x.observations[0],
    b = structuredClone(a);
  a.observationId = "O-A";
  b.observationId = "O-B";
  b.transitions[0].actorTenantRef = "tenant-C";
  b.transitions[0].resourceTenantRef = "tenant-C";
  b.transitions[1].actorTenantRef = "tenant-C";
  b.transitions[1].resourceTenantRef = "tenant-D";
  b.transitions[1].evidenceRefs = [
    "evidence-download-other-tenant-export-repeat",
  ];
  x.observations = [a, b];
  const p = plan(x),
    draft = p.decisions.find((d) => d.ticketDraft).ticketDraft;
  assert.equal(new Set(p.decisions.map((d) => d.exploitId)).size, 1);
  assert.match(draft.activityChain[1].operation, /tenant-B/);
  assert.ok(
    draft.activityChain[1].evidenceRefs.includes(
      "evidence-download-other-tenant-export-repeat",
    ),
  );
});

test("Confirmed run without action marker pauses evidence replay [E1-08]", () => {
  const x = fresh();
  x.existing = [existing(x)];
  x.existing[0].confirmedRunIds = [x.run.id];
  const d = first(x);
  assert.deepEqual(d.proposedActions, []);
  assert.ok(d.neededEvidence.some((v) => v.includes("readback")));
  assert.equal(plan(x).status, "needs_review");
});

test("Fingerprint alias never overrides a different violated control", () => {
  const x = fresh(),
    fp = `v3:${createHash("sha256")
      .update(JSON.stringify(identityOf(x.observations[0])))
      .digest("hex")}`;
  x.existing = [existing(x)];
  x.existing[0].violatedBoundary = "independent share token bypass";
  x.existing[0].fingerprintAliases = [fp];
  const d = first(x);
  assert.notEqual(d.outcome, "rediscovered");
  assert.deepEqual(d.proposedActions, []);
});

test("Applied create without an established issue snapshot needs readback", () => {
  const x = fresh(),
    createKey = first(x).actionKeys.create;
  x.processedActions = [
    {
      action: "create",
      key: createKey,
      state: "applied",
      externalMarker: "L-created",
    },
  ];
  const d = first(x);
  assert.equal(d.outcome, "unresolved");
  assert.deepEqual(d.proposedActions, []);
  assert.equal(d.notificationEligible, false);
  x.observations.push({
    ...structuredClone(x.observations[0]),
    observationId: "O-SECOND",
  });
  assert.deepEqual(
    plan(x).decisions.map((item) => item.outcome),
    ["unresolved", "unresolved"],
  );
});

test("Unknown matched issue state stays unresolved across duplicate observations", () => {
  const x = fresh();
  x.existing = [existing(x, "unknown", null)];
  x.observations.push({
    ...structuredClone(x.observations[0]),
    observationId: "O-SECOND",
  });
  const p = plan(x);
  assert.equal(p.status, "needs_review");
  assert.deepEqual(
    p.decisions.map((d) => d.outcome),
    ["unresolved", "unresolved"],
  );
  assert.ok(p.decisions.every((d) => d.proposedActions.length === 0));
});

test("Same-jar rotation with changed party is not valid provenance", () => {
  const x = fresh();
  x.sessionEvents.push({
    ref: "ROTATED",
    sequence: 2,
    state: "rotated",
    jarRef: "cookie-jar-tenant-a",
    actorRole: "non-admin-developer",
    partyRef: "tenant-B",
  });
  x.observations[0].observedSequence = 3;
  assert.equal(first(x).outcome, "unresolved");
});

test("A retest observation linked to another exploit is unresolved", () => {
  const x = fresh(),
    d = first(x);
  x.retests = [
    {
      exploitId: "OTHER-EXPLOIT",
      targetSurface: "export-share",
      attemptedOperations: ["share"],
      observedObservationIds: [x.observations[0].observationId],
      execution: "completed",
      conditions: [],
      evidenceRefs: ["E-OTHER"],
    },
  ];
  assert.equal(plan(x).decisions[0].exploitId, d.exploitId);
  assert.equal(plan(x).decisions[1].outcome, "unresolved");
});

test("A positive exploit suppresses a contradictory non-observation", () => {
  const x = fresh();
  x.existing = [existing(x)];
  x.retests = [
    {
      exploitId: "EXP-1",
      targetSurface: "export-download",
      attemptedOperations: ["download-other-tenant-export"],
      observedObservationIds: [],
      execution: "completed",
      conditions: [],
      evidenceRefs: ["E-RETEST"],
    },
  ];
  const p = plan(x);
  assert.equal(p.decisions[0].outcome, "rediscovered");
  assert.ok(!p.decisions.some((d) => d.outcome === "not_observed"));
});

test("A retest linked to unresolved evidence stays unresolved", () => {
  const x = fresh();
  x.observations[0].status = "incomplete";
  x.retests = [
    {
      exploitId: "EXP-1",
      targetSurface: "export-download",
      attemptedOperations: ["download-other-tenant-export"],
      observedObservationIds: ["observation-cross-tenant-export"],
      execution: "completed",
      conditions: [],
      evidenceRefs: ["E-RETEST"],
    },
  ];
  const p = plan(x);
  assert.deepEqual(
    p.decisions.map((d) => d.outcome),
    ["unresolved", "unresolved"],
  );
  assert.ok(!p.decisions.some((d) => d.outcome === "not_observed"));
});

test("A retest linked to an invalid observation stays unresolved", () => {
  const x = fresh();
  x.observations[0] = {
    observationId: "observation-cross-tenant-export",
    status: "confirmed",
  };
  x.retests = [
    {
      exploitId: "EXP-1",
      targetSurface: "export-download",
      attemptedOperations: ["download-other-tenant-export"],
      observedObservationIds: ["observation-cross-tenant-export"],
      execution: "completed",
      conditions: [],
      evidenceRefs: ["E-RETEST"],
    },
  ];
  const p = plan(x);
  assert.ok(p.decisions.every((d) => d.outcome === "unresolved"));
  assert.ok(!p.decisions.some((d) => d.outcome === "not_observed"));
});

test("A retest linked to a missing observation stays unresolved", () => {
  const x = fresh();
  x.observations = [];
  x.retests = [
    {
      exploitId: "EXP-9",
      targetSurface: "export-download",
      attemptedOperations: ["download-other-tenant-export"],
      observedObservationIds: ["O-MISSING"],
      execution: "completed",
      conditions: [],
      evidenceRefs: ["E-RETEST"],
    },
  ];
  const p = plan(x);
  assert.equal(p.status, "needs_review");
  assert.equal(p.decisions[0].outcome, "unresolved");
  assert.ok(!p.decisions.some((d) => d.outcome === "not_observed"));
});

test("One invalid finding leaves valid findings usable; invalid shared data stops planning [E1-12 E1-13]", () => {
  const x = fresh();
  x.observations.push({ observationId: "BROKEN", status: "confirmed" });
  let p = plan(x);
  assert.equal(p.status, "partial_failure");
  assert.equal(p.quarantined.length, 1);
  assert.equal(p.decisions[0].outcome, "new");
  x.existing = [existing(fresh())];
  x.existing[0].state = "Done";
  assert.throws(() => plan(x), /existing\[0\]\.state/);
  assert.throws(() => plan({}), /schemaVersion/);
});

test("Malformed existing identities report their exact input path", () => {
  const x = fresh();
  x.existing = [existing(x)];
  x.existing[0].normalizedChain.push({
    ...structuredClone(x.existing[0].normalizedChain.at(-1)),
    stepId: "second-terminal",
  });
  assert.throws(() => plan(x), /existing\[0\]\.normalizedChain/);

  const y = fresh();
  y.existing = [existing(y)];
  y.existing[0].identityAliases = [
    {
      environment: "party",
      surface: y.existing[0].surface,
      violatedBoundary: y.existing[0].violatedBoundary,
      normalizedChain: structuredClone(y.existing[0].normalizedChain),
    },
  ];
  y.existing[0].identityAliases[0].normalizedChain.push({
    ...structuredClone(y.existing[0].identityAliases[0].normalizedChain.at(-1)),
    stepId: "second-terminal",
  });
  assert.throws(
    () => plan(y),
    /existing\[0\]\.identityAliases\[0\]\.normalizedChain/,
  );
});

test("Shared run contract rejects malformed target, hash, and evidence destination", () => {
  const badTarget = fresh();
  badTarget.run.authorizedTargets = ["http://outside.example"];
  assert.throws(() => plan(badTarget), /authorizedTargets/);
  const badHash = fresh();
  badHash.run.instructionsSha256 = "x";
  assert.throws(() => plan(badHash), /instructionsSha256/);
  const unsafeTenantRef = fresh();
  unsafeTenantRef.observations[0].transitions[0].actorTenantRef = "tenant ref";
  assert.equal(first(unsafeTenantRef).outcome, "unresolved");
  assert.match(first(unsafeTenantRef).reason, /actorTenantRef.*safe opaque/);
  const badPrefix = fresh();
  badPrefix.run.evidencePrefix = "public";
  assert.throws(() => plan(badPrefix), /evidencePrefix/);
  badPrefix.run.evidencePrefix = "gs://synthetic-private-fixture/other-run/";
  assert.throws(() => plan(badPrefix), /evidencePrefix/);
  for (const suffix of [
    "?token=FAKE_SECRET/",
    "#FAKE_SECRET/",
    "../run-new-cross-tenant-export/",
    "%2e%2e/run-new-cross-tenant-export/",
    "/run-new-cross-tenant-export/",
  ]) {
    badPrefix.run.evidencePrefix = `gs://synthetic-private-fixture/run-new-cross-tenant-export/${suffix}`;
    assert.throws(() => plan(badPrefix), /evidencePrefix/);
  }
});

test("Planner is deterministic and proposes a summary without external calls [E1-15 E1-19]", () => {
  const x = fresh();
  assert.deepEqual(plan(x), plan(structuredClone(x)));
  assert.equal(plan(x).summary.proposed, true);
  assert.equal(plan(x).summary.deliveryState, "proposed_only");
});

test("Pending and uncertain external actions are held for readback", () => {
  const x = fresh();
  x.existing = [existing(x)];
  const k = `run/EXP-1/${x.run.id}`;
  x.processedActions = [
    { key: k, action: "append_evidence", state: "uncertain" },
  ];
  const d = first(x);
  assert.ok(!d.proposedActions.includes("append_evidence"));
  assert.ok(d.proposedActions.includes("increment_run_count"));
  assert.equal(d.notificationEligible, false);
  assert.ok(d.neededEvidence.some((e) => e.includes("readback")));
});

test("An uncertain notification requires external readback", () => {
  const x = fresh(),
    episodeKey = first(x).episodeKey;
  x.processedActions = [
    { key: episodeKey, action: "notify", state: "uncertain" },
  ];
  const d = first(x);
  assert.equal(d.notificationEligible, false);
  assert.deepEqual(d.neededEvidence, ["notify external readback"]);
  assert.equal(plan(x).status, "needs_review");
});

test("Different prerequisite controls cannot share an exploit identity", () => {
  const a = fresh().observations[0];
  const root = a.transitions[0];
  a.transitions = [
    {
      ...structuredClone(root),
      stepId: "left",
      operation: "prepare",
      expectedBoundary: "left control",
    },
    {
      ...structuredClone(root),
      stepId: "right",
      operation: "prepare",
      expectedBoundary: "right control",
    },
    {
      ...structuredClone(root),
      stepId: "middle",
      operation: "use capability",
      prerequisiteStepIds: ["left"],
    },
    {
      ...structuredClone(a.transitions[1]),
      prerequisiteStepIds: ["left", "right", "middle"],
    },
  ];
  const b = structuredClone(a);
  b.transitions[2].prerequisiteStepIds = ["right"];
  assert.notDeepEqual(identityOf(a), identityOf(b));
});

test("Conflicting duplicate observation IDs cannot authorize any action", () => {
  const x = fresh();
  const duplicate = structuredClone(x.observations[0]);
  duplicate.violatedBoundary = "another independent control";
  x.observations.push(duplicate);
  for (const observations of [x.observations, [...x.observations].reverse()]) {
    const p = plan({ ...x, observations });
    assert.ok(p.decisions.every((d) => d.proposedActions.length === 0));
    assert.ok(p.decisions.every((d) => d.outcome === "unresolved"));
  }
});

test("An unrelated observation with a hash suffix cannot satisfy a retest citation", () => {
  const x = fresh();
  x.observations[0].observationId = "missing#unrelated";
  const exploitId = first(x).exploitId;
  x.retests = [
    {
      exploitId,
      targetSurface: "export-download",
      attemptedOperations: ["download"],
      observedObservationIds: ["missing"],
      execution: "completed",
      conditions: [],
      evidenceRefs: [],
    },
  ];
  assert.ok(plan(x).decisions.some((d) => d.outcome === "unresolved"));
});

test("Step evidence follows full semantics when operation and boundary are shared", () => {
  const x = fresh(),
    a = x.observations[0];
  a.observationId = "O-A";
  const root = a.transitions[0];
  const second = {
    ...structuredClone(root),
    stepId: "second",
    targetClass: "another resource class",
    evidenceRefs: ["E-SECOND"],
  };
  a.transitions[1].prerequisiteStepIds = [root.stepId, second.stepId];
  a.transitions.splice(1, 0, second);
  const b = structuredClone(a);
  b.observationId = "O-B";
  b.transitions[0].evidenceRefs = ["E-FIRST-B"];
  b.transitions[1].evidenceRefs = ["E-SECOND-B"];
  b.transitions.reverse();
  // Renaming and reordering graph nodes must not change their meaning.
  for (const t of b.transitions) {
    t.stepId = `copy-${t.stepId}`;
    t.prerequisiteStepIds = t.prerequisiteStepIds.map((id) => `copy-${id}`);
  }
  assert.deepEqual(identityOf(a), identityOf(b));
  x.observations.push(b);
  const draft = plan(x).decisions.find((d) => d.ticketDraft).ticketDraft;
  const firstStep = draft.activityChain.find((t) => t.stepId === root.stepId);
  const secondStep = draft.activityChain.find((t) => t.stepId === "second");
  assert.ok(firstStep.evidenceRefs.includes("E-FIRST-B"));
  assert.ok(!firstStep.evidenceRefs.includes("E-SECOND-B"));
  assert.ok(secondStep.evidenceRefs.includes("E-SECOND-B"));
  assert.ok(!secondStep.evidenceRefs.includes("E-FIRST-B"));
});

test("An invalid duplicate ID also blocks its valid copy", () => {
  const x = fresh();
  x.observations.push({ observationId: x.observations[0].observationId });
  const p = plan(x);
  assert.equal(p.status, "partial_failure");
  assert.ok(p.decisions.every((d) => d.proposedActions.length === 0));
});

test("Split and unsplit IDs cannot collide or share retest provenance", () => {
  const x = fresh(),
    o = x.observations[0];
  o.observationId = "O";
  o.causes = [
    {
      causeId: "C1",
      terminalStepId: "download",
      surface: o.surface,
      violatedBoundary: o.violatedBoundary,
      impact: o.impact,
      severity: o.severity,
      productionImpact: o.productionImpact,
      remediation: o.remediation,
      retest: o.retest,
    },
  ];
  const other = structuredClone(o);
  delete other.causes;
  other.observationId = "O#C1";
  other.surface = "another surface";
  other.violatedBoundary = "another independent control";
  x.observations.push(other);
  const initial = plan(x);
  assert.deepEqual(
    new Set(initial.decisions.map((d) => d.observationId)),
    new Set(["O#C1", "O%23C1"]),
  );
  assert.ok(initial.decisions.every((d) => d.outcome === "new"));
  for (const [sourceId, outputId] of [
    ["O", "O#C1"],
    ["O#C1", "O%23C1"],
  ]) {
    x.retests = [
      {
        exploitId: initial.decisions.find((d) => d.observationId === outputId)
          .exploitId,
        targetSurface: "export-download",
        attemptedOperations: ["download"],
        observedObservationIds: [sourceId],
        execution: "completed",
        conditions: [],
        evidenceRefs: [],
      },
    ];
    assert.ok(plan(x).decisions.every((d) => d.outcome !== "unresolved"));
  }
});

test("Invalid findings use the same output ID rules and preserve raw provenance", () => {
  const x = fresh();
  x.observations[0].observationId = "O#C1";
  x.observations.push({ observationId: "O%23C1" }, {}, { observationId: 7 });
  const p = plan(x);
  const valid = p.decisions.find((d) => d.outcome === "new");
  const invalid = p.decisions.find((d) => d.sourceObservationId === "O%23C1");
  assert.equal(valid.observationId, "O%23C1");
  assert.equal(valid.sourceObservationId, "O#C1");
  assert.equal(invalid.observationId, "O%2523C1");
  assert.equal(invalid.inputIndex, 1);
  for (const inputIndex of [2, 3]) {
    const d = p.decisions.find((d) => d.inputIndex === inputIndex);
    assert.equal(d.observationId, undefined);
    assert.equal(d.sourceObservationId, undefined);
    assert.equal(d.outcome, "unresolved");
  }
});

test("Malformed Unicode cannot crash ID encoding or discard valid findings", () => {
  const x = fresh();
  const invalid = structuredClone(x.observations[0]);
  invalid.observationId = "\ud800";
  x.observations.push(invalid);
  const p = plan(x);
  assert.equal(p.status, "partial_failure");
  assert.equal(p.decisions[0].outcome, "new");
  const rejected = p.decisions.find((d) => d.inputIndex === 1);
  assert.equal(rejected.observationId, undefined);
  assert.equal(rejected.sourceObservationId, "\ud800");
});

test("Retesting one cause ignores its siblings but still checks every cited source", () => {
  const x = fresh(),
    o = x.observations[0];
  x.existing = [existing(x)];
  const share = {
    ...structuredClone(o.transitions[1]),
    stepId: "share",
    operation: "use share token",
    expectedBoundary: "deny invalid share token",
    observedEffect: "share token returned export content",
  };
  o.transitions.push(share);
  o.causes = [
    {
      causeId: "ownership",
      terminalStepId: "download",
      surface: o.surface,
      violatedBoundary: o.violatedBoundary,
      impact: o.impact,
      severity: o.severity,
      productionImpact: o.productionImpact,
      remediation: o.remediation,
      retest: o.retest,
    },
    {
      causeId: "share",
      terminalStepId: "share",
      surface: "export-share",
      violatedBoundary: "share token control",
      impact: "export read with invalid share token",
      severity: "high",
      productionImpact: o.productionImpact,
      remediation: ["check share token"],
      retest: ["deny invalid share token"],
    },
  ];
  x.retests = [
    {
      exploitId: "EXP-1",
      targetSurface: o.surface,
      attemptedOperations: ["download"],
      observedObservationIds: [o.observationId],
      execution: "completed",
      conditions: [],
      evidenceRefs: ["evidence-retest-export"],
    },
  ];
  let p = plan(x);
  assert.equal(p.status, "planned");
  assert.deepEqual(
    p.decisions.filter((d) => d.exploitId === "EXP-1").map((d) => d.outcome),
    ["rediscovered"],
  );

  // A separate ticket makes only the share cause ambiguous; ownership still matches.
  const ambiguousShare = {
    ...structuredClone(x.existing[0]),
    exploitId: "EXP-SHARE",
    linearIssueId: "LIN-SHARE",
    surface: "export-share",
    violatedBoundary: "share token control",
    normalizedChain: [
      structuredClone(o.transitions[0]),
      structuredClone(share),
    ],
  };
  ambiguousShare.normalizedChain[1].observedEffect =
    "different effect requiring identity review";
  x.existing.push(ambiguousShare);
  p = plan(x);
  assert.equal(p.status, "needs_review");
  assert.ok(
    p.decisions.some(
      (d) => d.observationId?.endsWith("#share") && d.outcome === "unresolved",
    ),
  );
  assert.deepEqual(
    p.decisions.filter((d) => d.exploitId === "EXP-1").map((d) => d.outcome),
    ["rediscovered"],
  );

  // Matching one cited source cannot excuse a second source about another exploit.
  const unrelated = structuredClone(fixture.observations[0]);
  unrelated.observationId = "unrelated-source";
  unrelated.surface = "different-surface";
  unrelated.violatedBoundary = "different-control";
  x.observations.push(unrelated);
  x.retests[0].observedObservationIds.push(
    unrelated.observationId,
    unrelated.observationId,
    o.observationId,
  );
  p = plan(x);
  const blockedRetest = p.decisions.find(
    (d) => d.exploitId === "EXP-1" && d.outcome === "unresolved",
  );
  assert.deepEqual(blockedRetest.unsupportedObservationIds, [
    "unrelated-source",
  ]);
});
