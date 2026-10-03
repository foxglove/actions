#!/usr/bin/env node
// WP1.* oracle: run plan() against every fixture and assert the SEMANTIC result
// (outcome, target, proposed-action set, evidence refs, eligibility, exploit id,
// whether triage evidence is needed) matches expected.json. Free-text `reason`
// and `matchReason` are documentation and are not asserted (semantic assertions,
// not incidental wording). Also checks determinism and input immutability (E1-15).

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { plan } from "./src/index.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const fixturesDir = path.join(here, "fixtures");

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
    .sort((a, b) => a.observationId.localeCompare(b.observationId));

const project = (out) => ({
  runId: out.runId,
  decisions: (out.decisions ?? [])
    .map(projectDecision)
    .sort((a, b) => a.observationId.localeCompare(b.observationId)),
  notObserved: projectNotObserved(out.runSummary?.notObserved),
  edgeClassification: out.runSummary?.edgeAccess?.classification ?? "none",
});

const eq = (a, b) => JSON.stringify(a) === JSON.stringify(b);

let pass = 0;
let failed = 0;
for (const name of fs.readdirSync(fixturesDir).sort()) {
  const dir = path.join(fixturesDir, name);
  if (!fs.statSync(dir).isDirectory()) continue;
  const input = JSON.parse(
    fs.readFileSync(path.join(dir, "input.json"), "utf8"),
  );
  const expected = JSON.parse(
    fs.readFileSync(path.join(dir, "expected.json"), "utf8"),
  );

  const before = JSON.stringify(input);
  const out = plan(input);
  const again = plan(JSON.parse(before));

  const got = project(out);
  const want = project(expected);

  const problems = [];
  if (!eq(got, want)) problems.push("semantic mismatch");
  if (!eq(project(out), project(again))) problems.push("non-deterministic");
  if (JSON.stringify(input) !== before) problems.push("mutated input");

  if (problems.length) {
    failed++;
    console.log(`FAIL ${name}: ${problems.join(", ")}`);
    console.log("  want:", JSON.stringify(want));
    console.log("  got :", JSON.stringify(got));
  } else {
    pass++;
    console.log(`PASS ${name}`);
  }
}

console.log(`\n${pass} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
