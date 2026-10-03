#!/usr/bin/env node
// WP0.1 fixture guard: dependency-free structural + branch-coverage + invariant check.
// JSON Schema conformance is checked separately with ajv (see README). This guard runs
// with plain Node so it can gate CI without a network install.
import fs from "node:fs";
import path from "node:path";

const root = path.join(
  path.dirname(new URL(import.meta.url).pathname),
  "fixtures",
);
const required = [
  "new",
  "rediscovered-open",
  "claimed-fixed-reproduces",
  "not-observed",
  "unresolved",
];
const outcomes = new Set();
let ok = true;
const fail = (dir, msg) => {
  ok = false;
  console.log(`INVARIANT FAIL ${dir}: ${msg}`);
};

for (const name of fs.readdirSync(root)) {
  const dir = path.join(root, name);
  if (!fs.statSync(dir).isDirectory()) continue;
  let input, expected;
  try {
    input = JSON.parse(fs.readFileSync(path.join(dir, "input.json"), "utf8"));
    expected = JSON.parse(
      fs.readFileSync(path.join(dir, "expected.json"), "utf8"),
    );
  } catch (e) {
    fail(name, `invalid JSON: ${e.message}`);
    continue;
  }
  const processed = new Set(
    (input.processedEvents || []).map((e) => e.eventId),
  );
  for (const dec of expected.decisions || []) {
    outcomes.add(dec.outcome);
    const writes = (dec.proposedActions || []).filter((a) => a.type !== "none");
    if (dec.outcome === "not-observed" && writes.length)
      fail(name, "not-observed must propose zero writes");
    if (dec.outcome === "unresolved" && writes.length)
      fail(name, "unresolved must propose no create/merge/lifecycle action");
  }
  for (const obs of input.observations || []) {
    if (obs.eventId && processed.has(obs.eventId)) {
      const dec = (expected.decisions || []).find(
        (x) => x.observationId === obs.observationId,
      );
      const writes = (dec?.proposedActions || []).filter(
        (a) => a.type !== "none",
      );
      if (writes.length)
        fail(name, "replayed (already-processed) event must not mutate");
    }
  }
}

const missing = required.filter((o) => !outcomes.has(o));
console.log("outcomes covered:", [...outcomes].sort().join(", ") || "(none)");
if (missing.length)
  fail("(coverage)", `missing outcome branches: ${missing.join(", ")}`);
console.log(ok ? "FIXTURE CHECK: PASS" : "FIXTURE CHECK: FAIL");
process.exit(ok ? 0 : 1);
