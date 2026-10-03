#!/usr/bin/env node
// WP1.* oracle. Asserts the SEMANTIC result of plan() per fixture AND a set of
// contract invariants on the ACTUAL output (not expected.json), plus determinism,
// permutation-stability, input immutability, and structural-failure behavior.
// Free-text `reason`/`matchReason` are documentation and are not asserted.

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { plan, PlannerInputError } from "./src/index.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const fixturesDir = path.join(here, "fixtures");
const outDir = path.join(os.tmpdir(), "aegis-planner-out");
fs.rmSync(outDir, { recursive: true, force: true });
fs.mkdirSync(outDir, { recursive: true });

const deepFreeze = (o) => {
  if (o && typeof o === "object" && !Object.isFrozen(o)) {
    Object.values(o).forEach(deepFreeze);
    Object.freeze(o);
  }
  return o;
};
const writeActions = (actions) =>
  (actions ?? []).filter((a) => a.type !== "none");
const sortedActions = (actions) =>
  (actions ?? [])
    .map((a) => (a.amount !== undefined ? `${a.type}:${a.amount}` : a.type))
    .sort();

const projectDecision = (d) => ({
  observationId: d.observationId,
  outcome: d.outcome,
  targetType: d.target?.type ?? "none",
  targetIssueId: d.target?.issueId ?? null,
  exploitId: d.exploitIdentity?.exploitId ?? null,
  actions: sortedActions(d.proposedActions),
  evidenceReferences: [...(d.evidenceReferences ?? [])].sort(),
  notificationEligible: Boolean(d.notificationEligible),
  needsEvidence: (d.neededEvidence ?? []).length > 0,
});
const projectNotObserved = (n) =>
  [...(n ?? [])]
    .map((e) => ({
      observationId: e.observationId,
      exploitId: e.exploitId ?? null,
      issueId: e.issueId ?? null,
      executionStatus: e.executionStatus,
    }))
    .sort((a, b) =>
      String(a.observationId).localeCompare(String(b.observationId)),
    );
const project = (out) => ({
  runId: out.runId,
  decisions: (out.decisions ?? [])
    .map(projectDecision)
    .sort((a, b) =>
      String(a.observationId).localeCompare(String(b.observationId)),
    ),
  notObserved: projectNotObserved(out.runSummary?.notObserved),
  edgeClassification: out.runSummary?.edgeAccess?.classification ?? "none",
});
const eq = (a, b) => JSON.stringify(a) === JSON.stringify(b);

const REQUIRED_LABELS = ["Bug", "harness", "pentesting"];
function checkInvariants(name, input, out, problems) {
  for (const d of out.decisions ?? []) {
    if (d.outcome === "not-observed" || d.outcome === "unresolved") {
      if (writeActions(d.proposedActions).length)
        problems.push(`${d.outcome} has write actions`);
    }
    for (const a of d.proposedActions ?? []) {
      if (a.type === "create-ticket") {
        const tm = a.ticketMaterial;
        if (!tm) {
          problems.push("create-ticket missing ticketMaterial (B1)");
          continue;
        }
        for (const k of [
          "severity",
          "productionImpact",
          "normalizedChain",
          "retestExpectations",
          "remediation",
          "ownership",
          "labels",
          "fingerprintVersion",
        ])
          if (tm[k] === undefined) problems.push(`ticketMaterial missing ${k}`);
        if (REQUIRED_LABELS.some((l) => !(tm.labels ?? []).includes(l)))
          problems.push("ticketMaterial labels incomplete");
        // Party evidence must never be promoted to a stronger production-impact
        // claim than the source observation stated (E1-14).
        const src = (input.observations ?? []).find((o) => o.observationId === d.observationId);
        const srcImpact = src?.exploit?.productionImpact?.value;
        if (srcImpact !== undefined && tm.productionImpact?.value !== srcImpact)
          problems.push(`productionImpact promoted ${srcImpact} -> ${tm.productionImpact?.value} (E1-14)`);
      }
    }
    // aliasing: output arrays must not be the same reference as an input array
    for (const obs of input.observations ?? []) {
      if (
        d.evidenceReferences &&
        d.evidenceReferences === obs?.evidence?.references
      )
        problems.push("evidenceReferences aliases input array (m2)");
    }
  }
  const unresolved = (out.decisions ?? []).filter(
    (d) => d.outcome === "unresolved",
  ).length;
  const expectBatch = unresolved ? "partial" : "complete";
  if (out.runSummary?.batchStatus !== expectBatch)
    problems.push(
      `batchStatus ${out.runSummary?.batchStatus} != ${expectBatch} (E1-13)`,
    );
}

let pass = 0,
  failed = 0;
for (const name of fs.readdirSync(fixturesDir).sort()) {
  const dir = path.join(fixturesDir, name);
  if (!fs.statSync(dir).isDirectory()) continue;
  const input = JSON.parse(
    fs.readFileSync(path.join(dir, "input.json"), "utf8"),
  );
  const expected = JSON.parse(
    fs.readFileSync(path.join(dir, "expected.json"), "utf8"),
  );
  const problems = [];

  const frozen = deepFreeze(JSON.parse(JSON.stringify(input)));
  let out;
  try {
    out = plan(frozen);
  } catch (e) {
    problems.push(`threw on valid input: ${e.message}`);
  }

  if (out) {
    fs.writeFileSync(
      path.join(outDir, `${name}.json`),
      JSON.stringify(out, null, 2),
    );
    if (!eq(project(out), project(expected)))
      problems.push("semantic mismatch");
    const again = plan(JSON.parse(JSON.stringify(input)));
    if (!eq(project(out), project(again))) problems.push("non-deterministic");
    // Permutation invariance of the AGGREGATE (not per-id): reordering observations
    // must not change the multiset of outcomes or the total write actions. For an
    // in-run duplicate, which sighting is canonical may change with order, but the
    // one-count/one-create-per-exploit totals must not (E1-08).
    const shuffled = JSON.parse(JSON.stringify(input));
    shuffled.observations = [...(shuffled.observations ?? [])].reverse();
    const permuted = plan(shuffled);
    const tally = (o) => {
      const t = {};
      for (const d of o.decisions ?? []) {
        t[`outcome:${d.outcome}`] = (t[`outcome:${d.outcome}`] ?? 0) + 1;
        for (const a of d.proposedActions ?? [])
          t[`action:${a.type}`] = (t[`action:${a.type}`] ?? 0) + 1;
      }
      return t;
    };
    const canon = (t) =>
      JSON.stringify(Object.fromEntries(Object.entries(t).sort()));
    if (canon(tally(out)) !== canon(tally(permuted)))
      problems.push("aggregate not permutation-invariant");
    checkInvariants(name, input, out, problems);
  }

  if (problems.length) {
    failed++;
    console.log(`FAIL ${name}: ${problems.join("; ")}`);
    if (out) {
      console.log("  want:", JSON.stringify(project(expected)));
      console.log("  got :", JSON.stringify(project(out)));
    }
  } else {
    pass++;
    console.log(`PASS ${name}`);
  }
}

// Structural-failure behavior (acceptance.md:33): no silent empty success.
let structural = 0,
  structuralFail = 0;
for (const [label, bad] of [
  ["null", null],
  ["{}", {}],
  ["observations-not-array", { run: {}, observations: "abc" }],
]) {
  let threw = false;
  try {
    plan(bad);
  } catch (e) {
    threw = e instanceof PlannerInputError;
  }
  if (threw) {
    structural++;
    console.log(`PASS structural-reject(${label})`);
  } else {
    structuralFail++;
    console.log(`FAIL structural-reject(${label}): accepted or wrong error`);
  }
}

console.log(
  `\n${pass} passed, ${failed} failed; structural ${structural} ok / ${structuralFail} bad`,
);
console.log(`actual outputs: ${outDir}`);
process.exit(failed || structuralFail ? 1 : 0);
