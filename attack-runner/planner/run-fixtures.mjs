#!/usr/bin/env node
// Oracle: deep-compares plan() output to an authored full expected output
// (ignoring only the free-text `reason`/`matchReason`), asserts contract invariants
// on the ACTUAL output, proves input->output round-trips, and self-tests that the
// comparison is tight (a mutated output must be rejected).

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
const strip = (x) => {
  if (Array.isArray(x)) return x.map(strip);
  if (x && typeof x === "object") {
    const o = {};
    // Drop the free-text `matchReason` anywhere, and `reason` ONLY on a decision
    // object (which has `outcome`). notObserved[].reason carries data and is kept.
    const dropReason = Object.prototype.hasOwnProperty.call(x, "outcome");
    for (const k of Object.keys(x).sort()) {
      if (k === "matchReason") continue;
      if (k === "reason" && dropReason) continue;
      o[k] = strip(x[k]);
    }
    return o;
  }
  return x;
};
const canon = (x) => JSON.stringify(strip(x));
const clone = (x) => JSON.parse(JSON.stringify(x));
const writeActions = (a) => (a ?? []).filter((x) => x.type !== "none");

const REQUIRED_LABELS = ["Bug", "harness", "pentesting"];
function invariants(input, out, problems) {
  for (const d of out.decisions ?? []) {
    if (
      (d.outcome === "not-observed" || d.outcome === "unresolved") &&
      writeActions(d.proposedActions).length
    )
      problems.push(`${d.outcome} proposes writes`);
    for (const a of d.proposedActions ?? []) {
      if (a.type === "create-ticket") {
        const tm = a.ticketMaterial;
        if (!tm) {
          problems.push("create-ticket missing ticketMaterial");
          continue;
        }
        for (const k of [
          "severity",
          "productionImpact",
          "chain",
          "remediation",
          "retestExpectations",
          "ownership",
          "labels",
          "fingerprint",
          "fingerprintVersion",
        ])
          if (tm[k] === undefined || tm[k] === null)
            problems.push(`ticketMaterial ${k} empty`);
        if (Array.isArray(tm.chain) && tm.chain.length === 0)
          problems.push("ticketMaterial chain empty");
        if (Array.isArray(tm.remediation) && tm.remediation.length === 0)
          problems.push("ticketMaterial remediation empty");
        if (REQUIRED_LABELS.some((l) => !(tm.labels ?? []).includes(l)))
          problems.push("labels incomplete");
        const src = (input.observations ?? []).find(
          (o) => o.observationId === d.observationId,
        );
        const want = src?.exploit?.productionImpact?.value;
        // Promotion (anything -> "yes" that the source did not already assert) is
        // forbidden; a downgrade (e.g. party "yes" -> "unknown") is allowed (E1-14).
        if (tm.productionImpact?.value === "yes" && want !== "yes")
          problems.push("productionImpact promoted to yes");
        if (
          (input.run?.targetEnvironment ?? "").toLowerCase() !== "production" &&
          tm.productionImpact?.value === "yes"
        )
          problems.push("production impact asserted from non-production run");
      }
    }
    for (const obs of input.observations ?? [])
      if (
        d.evidenceReferences &&
        d.evidenceReferences === obs?.evidence?.references
      )
        problems.push("evidenceReferences aliases input");
  }
  const unresolved = (out.decisions ?? []).filter(
    (d) => d.outcome === "unresolved",
  ).length;
  const want =
    unresolved || out.runSummary?.runCompletion !== "completed"
      ? "partial"
      : "complete";
  if (out.runSummary?.batchStatus !== want)
    problems.push(`batchStatus ${out.runSummary?.batchStatus} != ${want}`);

  // At most one create-ticket and one increment per identity per run (E1-08):
  // a fingerprint is ticketed/counted at most once, no matter how many observations.
  const creates = {};
  const counts = {};
  for (const d of out.decisions ?? []) {
    for (const a of d.proposedActions ?? []) {
      if (a.type === "create-ticket") {
        const fp = a.ticketMaterial?.fingerprint ?? "?";
        creates[fp] = (creates[fp] ?? 0) + 1;
      }
      if (a.type === "increment-confirmed-count") {
        const k =
          d.target?.issueId ?? d.exploitIdentity?.exploitId ?? a.amount + ":?";
        counts[k] = (counts[k] ?? 0) + 1;
      }
    }
  }
  for (const [fp, n] of Object.entries(creates))
    if (n > 1) problems.push(`${n} create-ticket for one fingerprint ${fp}`);
}

function selfTestTight(out, expected, problems) {
  // Mutating the actual output must break the comparison (proves it is not vacuous).
  if (!(out.decisions ?? []).length) return;
  const mutants = [];
  let m = clone(out);
  m.decisions[0].outcome =
    m.decisions[0].outcome === "new" ? "unresolved" : "new";
  mutants.push(["outcome", m]);
  m = clone(out);
  m.decisions[0].proposedActions.push({ type: "reopen-ticket" });
  mutants.push(["extra-action", m]);
  m = clone(out);
  m.decisions[0].notificationEligible = !m.decisions[0].notificationEligible;
  mutants.push(["eligibility", m]);
  m = clone(out);
  m.decisions[0].target = { type: "existing-issue", issueId: "__MUTANT__" };
  mutants.push(["target", m]);
  for (const [label, mut] of mutants)
    if (canon(mut) === canon(expected))
      problems.push(`oracle too loose: mutation '${label}' not detected`);
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
  let out;
  const frozen = deepFreeze(clone(input)); // the exact object plan() runs on
  try {
    out = plan(frozen);
  } catch (e) {
    problems.push(`threw: ${e.message}`);
  }
  if (out) {
    fs.writeFileSync(
      path.join(outDir, `${name}.json`),
      JSON.stringify(out, null, 2),
    );
    if (canon(out) !== canon(expected))
      problems.push("deep mismatch vs expected");
    if (canon(out) !== canon(plan(clone(input))))
      problems.push("non-deterministic");
    const rev = clone(input);
    rev.observations = [...(rev.observations ?? [])].reverse();
    const tally = (o) => {
      const t = {};
      for (const d of o.decisions ?? []) {
        t[`o:${d.outcome}`] = (t[`o:${d.outcome}`] ?? 0) + 1;
        for (const a of d.proposedActions ?? [])
          t[`a:${a.type}`] = (t[`a:${a.type}`] ?? 0) + 1;
      }
      return JSON.stringify(Object.entries(t).sort());
    };
    if (tally(out) !== tally(plan(rev)))
      problems.push("aggregate not permutation-invariant");
    invariants(frozen, out, problems);
    selfTestTight(out, expected, problems);
  }
  if (problems.length) {
    failed++;
    console.log(`FAIL ${name}: ${problems.join("; ")}`);
    if (out && canon(out) !== canon(expected)) {
      console.log("  exp:", canon(expected).slice(0, 400));
      console.log("  got:", canon(out).slice(0, 400));
    }
  } else {
    pass++;
    console.log(`PASS ${name}`);
  }
}

// Round-trip: a created ticket's material must be readable back as an existing issue.
{
  const first = plan(
    JSON.parse(
      fs.readFileSync(
        path.join(fixturesDir, "e1-01-new-no-match", "input.json"),
        "utf8",
      ),
    ),
  );
  const tm = first.decisions[0].proposedActions.find(
    (a) => a.type === "create-ticket",
  ).ticketMaterial;
  const second = plan({
    run: {
      runId: "run-rt",
      targetEnvironment: "party",
      evidenceLocation: "x",
      completion: { status: "completed" },
      session: { status: "ok" },
      coverage: { tested: [], untested: [], interrupted: [] },
      edgeAccess: { classification: "none" },
    },
    observations: [
      JSON.parse(
        fs.readFileSync(
          path.join(fixturesDir, "e1-01-new-no-match", "input.json"),
          "utf8",
        ),
      ).observations[0],
    ],
    existingIssues: [
      {
        issueId: "SEC-RT",
        exploitId: "exp-rt",
        state: "open",
        targetEnvironment: "party",
        fixClaim: { claimed: false, reference: null },
        normalizedChain: tm.chain,
      },
    ],
    processedEvents: [],
  });
  if (second.decisions[0].outcome === "rediscovered-open") {
    pass++;
    console.log(
      "PASS round-trip (ticketMaterial.chain -> existing normalizedChain)",
    );
  } else {
    failed++;
    console.log(`FAIL round-trip: got ${second.decisions[0].outcome}`);
  }
}

let structOk = 0,
  structBad = 0;
for (const [label, bad] of [
  ["null", null],
  ["{}", {}],
  [
    "obs-not-array",
    { run: { runId: "r", targetEnvironment: "party" }, observations: "x" },
  ],
  ["missing-env", { run: { runId: "r" }, observations: [] }],
  ["missing-runid", { run: { targetEnvironment: "party" }, observations: [] }],
  [
    "dup-observation-id",
    {
      run: { runId: "r", targetEnvironment: "party" },
      observations: [
        { observationId: "x", kind: "non-observation", validity: "valid" },
        { observationId: "x", kind: "non-observation", validity: "valid" },
      ],
    },
  ],
  [
    "fixclaim-nonboolean",
    {
      run: { runId: "r", targetEnvironment: "party" },
      observations: [],
      existingIssues: [
        {
          issueId: "I",
          state: "open",
          targetEnvironment: "party",
          normalizedChain: [],
          fixClaim: { claimed: "true" },
        },
      ],
    },
  ],
  [
    "processed-null",
    {
      run: { runId: "r", targetEnvironment: "party" },
      observations: [],
      processedEvents: [null],
    },
  ],
  [
    "bad-existing",
    {
      run: { runId: "r", targetEnvironment: "party" },
      observations: [],
      existingIssues: [{ issueId: "X" }],
    },
  ],
]) {
  let threw = false;
  try {
    plan(bad);
  } catch (e) {
    threw = e instanceof PlannerInputError;
  }
  if (threw) {
    structOk++;
    console.log(`PASS structural-reject(${label})`);
  } else {
    structBad++;
    console.log(`FAIL structural-reject(${label})`);
  }
}

console.log(
  `\n${pass} passed, ${failed} failed; structural ${structOk} ok / ${structBad} bad`,
);
console.log(`actual outputs: ${outDir}`);
process.exit(failed || structBad ? 1 : 0);
