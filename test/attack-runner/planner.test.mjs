import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import {
  plan,
  identityOf,
  canonical,
} from "../../src/attack-runner/planner.mjs";

const fixture = JSON.parse(
  await readFile(new URL("./fixtures/F1-new.json", import.meta.url)),
);
// Returns a copy of the base fixture that one test can change safely.
const fresh = () => structuredClone(fixture);
// Builds an existing-ticket snapshot from the fixture's demonstrated exploit.
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
// Returns the first decision from a planned fixture.
const first = (x) => plan(x).decisions[0];

test("E1-01 E1-14: full proposal includes unknown ownership and qualified production impact", () => {
  const x = fresh();
  delete x.observations[0].components;
  const d = first(x);
  assert.equal(d.outcome, "new");
  assert.deepEqual(d.proposedActions, ["create"]);
  assert.deepEqual(d.ticketDraft.labels, ["Bug", "pentesting", "harness"]);
  assert.deepEqual(d.ticketDraft.components, ["unknown"]);
  assert.equal(d.ticketDraft.activityChain.length, 2);
  assert.equal(d.ticketDraft.productionImpact.value, "unknown");
  assert.ok(d.ticketDraft.remediation.length && d.ticketDraft.retest.length);
  x.processedActions = [
    { key: d.episodeKey, action: "notify", state: "failed" },
  ];
  assert.equal(first(x).notificationEligible, true);
});

test("E1-02 E1-09: open issue gains one per-run evidence/count and no notification", () => {
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

test("E1-03 E1-19: explicit fix claim reopens only closed issue, eligibility once per claim", () => {
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

test("E1-04 E1-05 E1-06: scoped non-observation remains summary-only for all execution states", () => {
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

test("E1-07: pre-loss positive survives; post-loss and wrong start are unresolved", () => {
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
    jarRef: "J-F1",
  });
  // Invalid shared session sequence must reject, rather than manufacture provenance.
  assert.throws(() => plan(x), /sequence/);
  x.sessionEvents[1].sequence = 2;
  x.observations[0].observedSequence = 3;
  x.sessionEvents[2].sequence = 4;
  assert.equal(first(x).outcome, "new");
});

test("E1-08: duplicate observations and applied event state avoid repeat mutations", () => {
  const x = fresh();
  x.existing = [existing(x)];
  x.observations.push(structuredClone(x.observations[0]));
  x.observations[1].observationId = "O-F1-COPY";
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
    observationId: "O-F1-COPY",
  });
  assert.deepEqual(
    plan(x).decisions.map((d) => d.outcome),
    ["contradicts_fix", "contradicts_fix"],
  );
});

test("E1-10 E1-17 E1-20: repository/path/model and fingerprint version do not change established identity", () => {
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

test("E1-11 E1-18: different control separates identity; plausible duplicate is unresolved", () => {
  const x = fresh();
  x.existing = [existing(x)];
  const alternate = structuredClone(x.observations[0]);
  alternate.observationId = "O-SHARE";
  alternate.violatedBoundary = "share token validation";
  alternate.transitions.at(-1).expectedBoundary = "deny invalid share token";
  x.observations.push(alternate);
  let ds = plan(x).decisions;
  assert.equal(ds[0].outcome, "rediscovered");
  assert.equal(ds[1].outcome, "new");
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

test("E1-18: one raw finding with two explicit causes splits and retains shared prerequisite", () => {
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
  assert.ok(p.decisions.every((d) => d.evidenceRefs.includes("E-F1-LIST")));
  assert.deepEqual(
    p.decisions.map((d) => d.ticketDraft.remediation),
    [["fix ownership"], ["fix share token"]],
  );
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

test("E1-20: reviewed structured alias preserves exploit ID across normalization version", () => {
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

test("E1-17: DAG prerequisite order does not change causal identity", () => {
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

test("E1-18: actor and resource tenant equality remains part of identity", () => {
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

test("E1-10: equivalent cross-component evidence merges into one complete ticket regardless of order", () => {
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

test("E1-08: confirmed run without action marker pauses evidence replay", () => {
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
    fp = `v2:${createHash("sha256")
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
    jarRef: "J-F1",
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
      observedObservationIds: ["O-F1"],
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
  x.observations[0] = { observationId: "O-F1", status: "confirmed" };
  x.retests = [
    {
      exploitId: "EXP-1",
      targetSurface: "export-download",
      attemptedOperations: ["download-other-tenant-export"],
      observedObservationIds: ["O-F1"],
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

test("E1-12 E1-13: independent invalid item is quarantined; shared snapshot fails closed", () => {
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
  const badPrefix = fresh();
  badPrefix.run.evidencePrefix = "public";
  assert.throws(() => plan(badPrefix), /evidencePrefix/);
  badPrefix.run.evidencePrefix = "gs://synthetic-private-fixture/other-run/";
  assert.throws(() => plan(badPrefix), /evidencePrefix/);
  for (const suffix of [
    "?token=FAKE_SECRET/",
    "#FAKE_SECRET/",
    "../R-F1-NEW/",
    "%2e%2e/R-F1-NEW/",
    "/R-F1-NEW/",
  ]) {
    badPrefix.run.evidencePrefix = `gs://synthetic-private-fixture/R-F1-NEW/${suffix}`;
    assert.throws(() => plan(badPrefix), /evidencePrefix/);
  }
});

test("E1-15 E1-19: planner is deterministic and proposes a summary without external calls", () => {
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
