#!/usr/bin/env node
// Mutation test (committed convergence gate for the offline planner).
// Copies the planner into a temp dir, applies each single-line mutation, and runs
// the real oracle (run-fixtures.mjs). A mutation that still PASSES is a "survivor" —
// a behavior no fixture pins. The suite must have zero survivors except the
// documented EQUIVALENT mutants below (mutations that cannot change observable
// behavior, so no test can kill them).
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { execFileSync } from "node:child_process";

const here = path.dirname(fileURLToPath(import.meta.url));
const base = fs.mkdtempSync(path.join(os.tmpdir(), "aegis-mut-"));
for (const d of ["src", "fixtures", "schema"])
  fs.cpSync(path.join(here, d), path.join(base, d), { recursive: true });
fs.copyFileSync(
  path.join(here, "run-fixtures.mjs"),
  path.join(base, "run-fixtures.mjs"),
);

// Equivalent mutants / harness artifacts that cannot be killed by any fixture:
const EQUIVALENT = new Set([
  // count-mark now lives only in the non-replay branch, so the added !replayed guard is a no-op.
  "replayed-not-added-to-counted",
  // validateInput forces fixClaim.claimed to be boolean, so `=== true` and `!!` coincide.
  "claimed-lax-truthy",
  // matches[0] is only reached with exactly one match (>1 routes to unresolved earlier).
  "match-any-state-open-only",
]);

const mutants = [
  // [name, file, find, replace]
  [
    "fp-no-env",
    "src/normalize.mjs",
    "return `${FINGERPRINT_VERSION}:${JSON.stringify({ env, chain: normalized })}`",
    "return `${FINGERPRINT_VERSION}:${JSON.stringify({ chain: normalized })}`",
  ],
  ["no-lowercase", "src/normalize.mjs", ".trim().toLowerCase()", ".trim()"],
  [
    "no-trim",
    "src/normalize.mjs",
    "value.trim().toLowerCase()",
    "value.toLowerCase()",
  ],
  [
    "incidental-not-skipped",
    "src/normalize.mjs",
    "if (s.incidental === true) return { ok: true, skip: true };",
    "",
  ],
  [
    "no-dup-collapse",
    "src/normalize.mjs",
    "tupleKey(tuples[tuples.length - 1]) === tupleKey(r.tuple)",
    "false",
  ],
  [
    "sorted-chain",
    "src/normalize.mjs",
    "return tuples.length === 0 ? null : tuples;",
    "return tuples.length === 0 ? null : tuples.sort((a,b)=>tupleKey(a)<tupleKey(b)?-1:1);",
  ],
  [
    "first-tuple-only",
    "src/normalize.mjs",
    "return tuples.length === 0 ? null : tuples;",
    "return tuples.length === 0 ? null : tuples.slice(0,1);",
  ],
  [
    "last-tuple-only",
    "src/normalize.mjs",
    "return tuples.length === 0 ? null : tuples;",
    "return tuples.length === 0 ? null : tuples.slice(-1);",
  ],
  ["tuple-drops-violation", "src/normalize.mjs", '  "violation",\n];', "];"],
  ["tuple-drops-surface", "src/normalize.mjs", '  "surface",\n', ""],
  ["tuple-drops-actorRole", "src/normalize.mjs", '  "actorRole",\n', ""],
  [
    "tuple-drops-resourceRelation",
    "src/normalize.mjs",
    '  "resourceRelation",\n',
    "",
  ],
  ["tuple-drops-operation", "src/normalize.mjs", '  "operation",\n', ""],
  ["tuple-drops-boundaryType", "src/normalize.mjs", '  "boundaryType",\n', ""],
  [
    "subseq-no-reverse",
    "src/plan.mjs",
    "isSubsequence(obsNorm, issNorm) || isSubsequence(issNorm, obsNorm)",
    "isSubsequence(obsNorm, issNorm)",
  ],
  [
    "subseq-only-reverse",
    "src/plan.mjs",
    "isSubsequence(obsNorm, issNorm) || isSubsequence(issNorm, obsNorm)",
    "isSubsequence(issNorm, obsNorm)",
  ],
  [
    "related-ignores-env",
    "src/plan.mjs",
    "if (normEnv(iss.targetEnvironment) !== normEnv(runEnv)) return false;",
    "",
  ],
  [
    "related-disabled",
    "src/plan.mjs",
    "if (relatedToIssue || relatedInRun) {",
    "if (false) {",
  ],
  [
    "related-exact-only-contig",
    "src/plan.mjs",
    "isSubsequence(obsNorm, issNorm) || isSubsequence(issNorm, obsNorm)",
    "(obsNorm.length!==issNorm.length && JSON.stringify(issNorm).includes(JSON.stringify(obsNorm).slice(1,-1)))",
  ],
  [
    "alias-ignored",
    "src/plan.mjs",
    "iss.fingerprintAliases.includes(fp)",
    "false",
  ],
  [
    "alias-only-chainless",
    "src/plan.mjs",
    "Array.isArray(iss.fingerprintAliases) &&",
    "!Array.isArray(iss.normalizedChain) && Array.isArray(iss.fingerprintAliases) &&",
  ],
  [
    "multi-match-picks-first",
    "src/plan.mjs",
    "if (matches.length > 1) {",
    "if (matches.length > 5) {",
  ],
  [
    "multi-match-new",
    "src/plan.mjs",
    "if (matches.length > 1) {",
    "if (false) {",
  ],
  [
    "match-any-state-open-only",
    "src/plan.mjs",
    "const iss = matches[0];",
    "const iss = matches.find(m=>m.state==='open')??matches[0];",
  ],
  [
    "unknown-state-as-open",
    "src/plan.mjs",
    'if (state === "unknown") {',
    "if (false) {",
  ],
  [
    "unrecognized-state-open",
    "src/plan.mjs",
    'if (!["open", "resolved", "unknown"].includes(state)) {',
    "if (false) {",
  ],
  [
    "resolved-no-claim-reopens",
    "src/plan.mjs",
    'if (state === "resolved" && !claimed) {',
    "if (false) {",
  ],
  [
    "resolved-no-claim-silent",
    "src/plan.mjs",
    'outcome: "unresolved",\n            reason:\n              "Resolved ticket carries',
    'outcome: "not-observed",\n            reason:\n              "Resolved ticket carries',
  ],
  [
    "resolved-claim-no-reopen",
    "src/plan.mjs",
    '{ type: "reopen-ticket" },',
    "",
  ],
  [
    "open-claim-reopens",
    "src/plan.mjs",
    'baseActions = [{ type: "append-evidence" }, ...rem];\n      } else {',
    'baseActions = [{ type: "append-evidence" },{ type: "reopen-ticket" }, ...rem];\n      } else {',
  ],
  [
    "open-claim-not-eligible",
    "src/plan.mjs",
    'outcome = "claimed-fixed-reproduces";\n        matchReason =\n          "same normalized causal chain as the open ticket with a fix claim";\n        eligible = true;',
    'outcome = "claimed-fixed-reproduces";\n        matchReason =\n          "same normalized causal chain as the open ticket with a fix claim";\n        eligible = false;',
  ],
  [
    "open-claim-as-rediscovered",
    "src/plan.mjs",
    "} else if (claimed) {",
    "} else if (false) {",
  ],
  [
    "rediscovered-eligible",
    "src/plan.mjs",
    'eligible = false;\n        baseActions = [{ type: "append-evidence" }, ...rem];\n      }',
    'eligible = true;\n        baseActions = [{ type: "append-evidence" }, ...rem];\n      }',
  ],
  [
    "resolved-claim-not-eligible",
    "src/plan.mjs",
    'eligible = true;\n        baseActions = [\n          { type: "append-evidence" },\n          { type: "reopen-ticket" },',
    'eligible = false;\n        baseActions = [\n          { type: "append-evidence" },\n          { type: "reopen-ticket" },',
  ],
  [
    "new-not-eligible",
    "src/plan.mjs",
    'target = { type: "new-issue", issueId: null };\n      eligible = true;',
    'target = { type: "new-issue", issueId: null };\n      eligible = false;',
  ],
  [
    "claimed-lax-truthy",
    "src/plan.mjs",
    "iss.fixClaim?.claimed === true",
    "!!iss.fixClaim?.claimed",
  ],
  [
    "claimed-ignores-ref-absent",
    "src/plan.mjs",
    "iss.fixClaim?.claimed === true",
    "(iss.fixClaim?.claimed === true || !!iss.fixClaim?.reference)",
  ],
  [
    "fixClaimRef-dropped",
    "src/plan.mjs",
    "...(fixClaimRef !== undefined ? { fixClaimRef } : {}),",
    "",
  ],
  [
    "exploitId-dropped",
    "src/plan.mjs",
    "exploitId = iss.exploitId ?? null;",
    "exploitId = null;",
  ],
  ["count-amount-2", "src/plan.mjs", "amount: 1", "amount: 2"],
  [
    "no-count-on-new",
    "src/plan.mjs",
    '      actions = [\n        ...baseActions,\n        { type: "increment-confirmed-count", amount: 1 },\n      ];',
    "      actions = outcome==='new'?[...baseActions]:[...baseActions,{ type: \"increment-confirmed-count\", amount: 1 }];",
  ],
  [
    "no-count-on-claimed",
    "src/plan.mjs",
    '      actions = [\n        ...baseActions,\n        { type: "increment-confirmed-count", amount: 1 },\n      ];',
    "      actions = outcome==='claimed-fixed-reproduces'?[...baseActions]:[...baseActions,{ type: \"increment-confirmed-count\", amount: 1 }];",
  ],
  [
    "replay-ignored",
    "src/plan.mjs",
    "(obs.eventId && processedIds.has(obs.eventId)) ||",
    "false ||",
  ],
  [
    "replay-key-ignored",
    "src/plan.mjs",
    "processedKeys.has(derivedKey) ||\n      processedKeys.has(fpKey);",
    "false;",
  ],
  [
    "replay-still-eligible",
    "src/plan.mjs",
    'actions = [{ type: "none" }];\n      eligible = false;',
    'actions = [{ type: "none" }];',
  ],
  [
    "dup-in-run-ignored",
    "src/plan.mjs",
    "const duplicateInRun = countedThisRun.has(identityKey);",
    "const duplicateInRun = false;",
  ],
  [
    "dup-keyed-on-fp",
    "src/plan.mjs",
    "const duplicateInRun = countedThisRun.has(identityKey);",
    "const duplicateInRun = countedThisRun.has(fp);",
  ],
  [
    "dup-add-fp-only",
    "src/plan.mjs",
    "countedThisRun.add(identityKey);",
    "countedThisRun.add(fp);",
  ],
  [
    "replayed-not-added-to-counted",
    "src/plan.mjs",
    "countedThisRun.add(identityKey);",
    "if(!replayed) countedThisRun.add(identityKey);",
  ],
  [
    "idem-key-no-run",
    "src/plan.mjs",
    "`${run.runId}:${exploitId ?? fp}`",
    "`${exploitId ?? fp}`",
  ],
  [
    "idem-key-fp-only",
    "src/plan.mjs",
    "`${run.runId}:${exploitId ?? fp}`",
    "`${run.runId}:${fp}`",
  ],
  [
    "nonobs-writes",
    "src/plan.mjs",
    'matchReason: obs.retestTarget ? "re-test target" : "",',
    "matchReason: \"\", proposedActions:[{type:'append-evidence'}],",
  ],
  [
    "nonobs-exploitId-invented",
    "src/plan.mjs",
    "const exploitId = obs.retestTarget?.exploitId ?? null;",
    "const exploitId = obs.retestTarget?.exploitId ?? 'exp-x';",
  ],
  [
    "nonobs-always-attempted",
    "src/plan.mjs",
    'status === "completed" ? [...(run.coverage?.tested ?? [])] : [],',
    "[...(run.coverage?.tested ?? [])],",
  ],
  [
    "nonobs-never-attempted",
    "src/plan.mjs",
    'status === "completed" ? [...(run.coverage?.tested ?? [])] : [],',
    "[],",
  ],
  [
    "nonobs-status-dropped",
    "src/plan.mjs",
    "executionStatus: status,",
    "executionStatus: 'completed',",
  ],
  [
    "nonobs-reason-fixed",
    "src/plan.mjs",
    'reason: obs.execution?.stopReason ?? "not observed in this run",',
    "reason: 'fixed',",
  ],
  [
    "nonobs-edge-dropped",
    "src/plan.mjs",
    'edgeClassification: run.edgeAccess?.classification ?? "none",',
    "edgeClassification: 'none',",
  ],
  [
    "nonobs-evidence-dropped",
    "src/plan.mjs",
    "evidenceReferences: [...(obs.evidence?.references ?? [])],\n      });",
    "evidenceReferences: [],\n      });",
  ],
  [
    "nonobs-issueId-dropped",
    "src/plan.mjs",
    "issueId,\n        executionStatus",
    "issueId:null,\n        executionStatus",
  ],
  [
    "summary-complete-always",
    "src/plan.mjs",
    'unresolved.length || completion !== "completed" ? "partial" : "complete"',
    'unresolved.length ? "partial" : "complete"',
  ],
  [
    "summary-partial-ignores-unresolved",
    "src/plan.mjs",
    'unresolved.length || completion !== "completed" ? "partial" : "complete"',
    'completion !== "completed" ? "partial" : "complete"',
  ],
  [
    "summary-unresolved-dropped",
    "src/plan.mjs",
    "    unresolved,\n    notObserved,",
    "    unresolved: [],\n    notObserved,",
  ],
  [
    "summary-coverage-empty",
    "src/plan.mjs",
    "coverage: run.coverage ?? { tested: [], untested: [], interrupted: [] },",
    "coverage: { tested: [], untested: [], interrupted: [] },",
  ],
  [
    "summary-stopreason-dropped",
    "src/plan.mjs",
    "if (run.completion?.stopReason)",
    "if (false)",
  ],
  [
    "summary-edge-dropped",
    "src/plan.mjs",
    'edgeAccess: run.edgeAccess ?? { classification: "none" },',
    'edgeAccess: { classification: "none" },',
  ],
  [
    "summary-session-dropped",
    "src/plan.mjs",
    'sessionStatus: run.session?.status ?? "unknown",',
    "sessionStatus: 'ok',",
  ],
  [
    "summary-runcompletion-dropped",
    "src/plan.mjs",
    "runCompletion: completion,",
    "runCompletion: 'completed',",
  ],
  [
    "tm-labels-missing",
    "src/plan.mjs",
    'const TICKET_LABELS = ["Bug", "pentesting", "harness"];',
    'const TICKET_LABELS = ["Bug", "pentesting"];',
  ],
  [
    "tm-ownership-always-unknown",
    "src/plan.mjs",
    'ownership: repos.length ? [...repos] : "unknown",',
    'ownership: "unknown",',
  ],
  [
    "tm-ownership-empty",
    "src/plan.mjs",
    'ownership: repos.length ? [...repos] : "unknown",',
    "ownership: [...repos],",
  ],
  [
    "tm-impact-forced-unknown",
    "src/plan.mjs",
    "productionImpact: impact,",
    "productionImpact: { value:'unknown', rationale: e.productionImpact.rationale },",
  ],
  [
    "tm-impact-promoted-yes",
    "src/plan.mjs",
    "productionImpact: impact,",
    "productionImpact: { ...e.productionImpact, value: e.productionImpact.value==='unknown'?'yes':e.productionImpact.value },",
  ],
  [
    "tm-impact-rationale-dropped",
    "src/plan.mjs",
    "productionImpact: impact,",
    "productionImpact: { value:e.productionImpact.value, rationale:'x' },",
  ],
  [
    "tm-severity",
    "src/plan.mjs",
    "severity: e.severity,",
    "severity: 'critical',",
  ],
  [
    "tm-surfaces-dropped",
    "src/plan.mjs",
    "affectedSurfaces: [...(e.affectedSurfaces ?? [])],",
    "affectedSurfaces: [],",
  ],
  [
    "tm-remediation-dropped",
    "src/plan.mjs",
    "remediation: JSON.parse(JSON.stringify(e.remediation)),",
    "remediation: [],",
  ],
  [
    "tm-retest-dropped",
    "src/plan.mjs",
    "retestExpectations: e.retestExpectations,",
    "retestExpectations: 'x',",
  ],
  [
    "tm-chain-normalized-flat",
    "src/plan.mjs",
    "chain: JSON.parse(JSON.stringify(e.chain)),",
    "chain: normalizeChain(e.chain),",
  ],
  [
    "tm-chain-first-only",
    "src/plan.mjs",
    "chain: JSON.parse(JSON.stringify(e.chain)),",
    "chain: JSON.parse(JSON.stringify(e.chain)).slice(0,1),",
  ],
  [
    "tm-evidence-dropped",
    "src/plan.mjs",
    "evidenceReferences: [...(obs.evidence?.references ?? [])],\n  };",
    "evidenceReferences: [],\n  };",
  ],
  [
    "tm-fingerprint-dropped",
    "src/plan.mjs",
    "fingerprint: fp,",
    "fingerprint: 'x',",
  ],
  [
    "tm-exploitId",
    "src/plan.mjs",
    "exploitId: exploitId ?? null,\n    fingerprint",
    "exploitId: 'x',\n    fingerprint",
  ],
  [
    "incomplete-gate-off",
    "src/plan.mjs",
    "if (missing.length) {",
    "if (false) {",
  ],
  [
    "incomplete-no-severity",
    "src/plan.mjs",
    'if (!["low", "medium", "high", "critical"].includes(e.severity))\n    missing.push("severity");',
    "",
  ],
  [
    "incomplete-no-impact-enum",
    "src/plan.mjs",
    'if (!["yes", "no", "unknown"].includes(e.productionImpact?.value))',
    "if (false)",
  ],
  [
    "incomplete-no-rationale",
    "src/plan.mjs",
    "if (!nonEmptyString(e.productionImpact?.rationale))",
    "if (false)",
  ],
  [
    "incomplete-no-remediation",
    "src/plan.mjs",
    "if (!Array.isArray(e.remediation) || e.remediation.length === 0)",
    "if (false)",
  ],
  [
    "incomplete-no-retest",
    "src/plan.mjs",
    'if (!nonEmptyString(e.retestExpectations)) missing.push("retestExpectations");',
    "",
  ],
  [
    "rem-never-appended",
    "src/plan.mjs",
    "Array.isArray(obs.exploit?.remediation) &&",
    "false &&",
  ],
  [
    "rem-on-resolved-missing",
    "src/plan.mjs",
    '{ type: "reopen-ticket" },\n          ...rem,',
    '{ type: "reopen-ticket" },',
  ],
  [
    "rem-on-open-missing",
    "src/plan.mjs",
    'outcome = "rediscovered-open";\n        matchReason = "same normalized causal chain as the open ticket";\n        eligible = false;\n        baseActions = [{ type: "append-evidence" }, ...rem];',
    'outcome = "rediscovered-open";\n        matchReason = "same normalized causal chain as the open ticket";\n        eligible = false;\n        baseActions = [{ type: "append-evidence" }];',
  ],
  [
    "validity-invalid-treated-valid",
    "src/plan.mjs",
    'if (obs.validity !== "valid") {',
    "if (false) {",
  ],
  [
    "validity-ambig-needed-evidence",
    "src/plan.mjs",
    '"disambiguating evidence to establish a single exploit identity"',
    "'x'",
  ],
  [
    "validity-unknown-accepted",
    "src/plan.mjs",
    'if (\n      !["valid", "invalid-evidence", "ambiguous-identity"].includes(\n        obs.validity,\n      )\n    ) {',
    "if (false) {",
  ],
  [
    "kind-unknown-as-positive",
    "src/plan.mjs",
    'if (obs.kind !== "confirmed-positive") {',
    "if (false) {",
  ],
  ["nosemantics-new", "src/plan.mjs", "if (fp === null) {", "if (false) {"],
  [
    "unresolved-evidence-dropped",
    "src/plan.mjs",
    'matchReason: "no structured semantics",\n          evidenceReferences,',
    'matchReason: "no structured semantics",',
  ],
  [
    "decision-order-reversed",
    "src/plan.mjs",
    "return { runId: run.runId, decisions, runSummary };",
    "return { runId: run.runId, decisions: decisions.reverse(), runSummary };",
  ],
  [
    "evidence-aliased",
    "src/plan.mjs",
    "evidenceReferences: [...(fields.evidenceReferences ?? [])],",
    "evidenceReferences: fields.evidenceReferences ?? [],",
  ],
  [
    "extra-top-level-field",
    "src/plan.mjs",
    "return { runId: run.runId, decisions, runSummary };",
    "return { runId: run.runId, decisions, runSummary, closeCandidates: [] };",
  ],
  [
    "extra-field-on-decision",
    "src/plan.mjs",
    "    neededEvidence: [...(fields.neededEvidence ?? [])],\n  };",
    "    neededEvidence: [...(fields.neededEvidence ?? [])],\n    closeCandidate:false\n  };",
  ],
  [
    "prod-env-cross-match",
    "src/plan.mjs",
    "const issFp = fingerprint(iss.normalizedChain, iss.targetEnvironment);",
    "const issFp = fingerprint(iss.normalizedChain, runEnv);",
  ],
  [
    "env-case-sensitive",
    "src/normalize.mjs",
    'String(env ?? "")\n    .trim()\n    .toLowerCase();',
    'String(env ?? "");',
  ],
  [
    "mutates-input",
    "src/plan.mjs",
    "const existingIssues = input.existingIssues ?? [];",
    "const existingIssues = input.existingIssues ?? []; input.__touched = true;",
  ],
  [
    "state-unknown-reason-fixed",
    "src/plan.mjs",
    'neededEvidence: [`current state of ${iss.issueId}`],\n          }),\n        );\n        continue;\n      }\n      if (state === "resolved"',
    'neededEvidence: [],\n          }),\n        );\n        continue;\n      }\n      if (state === "resolved"',
  ],
  [
    "target-existing-wrong-type",
    "src/plan.mjs",
    'target = { type: "existing-issue", issueId: iss.issueId };',
    'target = { type: "existing-issue", issueId: iss.issueId, extra:1 };',
  ],
  [
    "unresolved-target-dropped-on-state",
    "src/plan.mjs",
    'matchReason: "unknown ticket state",\n            target,',
    'matchReason: "unknown ticket state",',
  ],
  [
    "resolved-nonclaim-target-dropped",
    "src/plan.mjs",
    'matchReason: "resolved without fix claim",\n            target,',
    'matchReason: "resolved without fix claim",',
  ],
  [
    "resolved-nonclaim-fixclaimref-dropped",
    "src/plan.mjs",
    "            evidenceReferences,\n            fixClaimRef,\n",
    "            evidenceReferences,\n",
  ],
  // --- guards and logic added while addressing PR #55 review ---
  [
    "dupid-check-off",
    "src/plan.mjs",
    "if (seenIds.has(o.observationId))",
    "if (false)",
  ],
  [
    "fixclaim-boolean-off",
    "src/plan.mjs",
    'typeof iss.fixClaim.claimed !== "boolean"',
    "false",
  ],
  [
    "runid-check-off",
    "src/plan.mjs",
    "if (!nonEmptyString(run.runId))",
    "if (false)",
  ],
  [
    "issue-env-check-off",
    "src/plan.mjs",
    "if (!nonEmptyString(iss.targetEnvironment))",
    "if (false)",
  ],
  [
    "processed-entry-check-off",
    "src/plan.mjs",
    'if (e === null || typeof e !== "object" || Array.isArray(e))',
    "if (false)",
  ],
  [
    "uncomparable-off",
    "src/plan.mjs",
    "if (uncomparable.length) {",
    "if (false) {",
  ],
  [
    "unc-env-ignored",
    "src/plan.mjs",
    "normEnv(iss.targetEnvironment) === normEnv(runEnv) &&\n          normalizeChain(iss.normalizedChain) === null &&",
    "normalizeChain(iss.normalizedChain) === null &&",
  ],
  [
    "unc-alias-clause-off",
    "src/plan.mjs",
    "iss.fingerprintAliases.some(nonEmptyString)",
    "false",
  ],
  [
    "unc-empty-alias-comparable",
    "src/plan.mjs",
    "iss.fingerprintAliases.some(nonEmptyString)",
    "true",
  ],
  [
    "unc-blank-alias-comparable",
    "src/plan.mjs",
    "iss.fingerprintAliases.some(nonEmptyString)",
    "iss.fingerprintAliases.length > 0",
  ],
  [
    "related-state-skip-restored",
    "src/plan.mjs",
    "if (normEnv(iss.targetEnvironment) !== normEnv(runEnv)) return false;",
    'if (normEnv(iss.targetEnvironment) !== normEnv(runEnv)) return false;\n        if (iss.state !== "open") return false;',
  ],
  [
    "nonempty-no-trim",
    "src/plan.mjs",
    'typeof v === "string" && v.trim() !== ""',
    'typeof v === "string" && v !== ""',
  ],
  [
    "obs-array-off",
    "src/plan.mjs",
    "if (!Array.isArray(input.observations))",
    "if (false)",
  ],
  [
    "existing-array-off",
    "src/plan.mjs",
    "if (!Array.isArray(input.existingIssues))",
    "if (false)",
  ],
  [
    "processed-array-off",
    "src/plan.mjs",
    "if (!Array.isArray(input.processedEvents))",
    "if (false)",
  ],
  ["issueid-off", "src/plan.mjs", "!nonEmptyString(iss.issueId)", "false"],
  [
    "obsid-off",
    "src/plan.mjs",
    'typeof o !== "object" || !nonEmptyString(o.observationId)',
    'typeof o !== "object"',
  ],
  [
    "runpositives-validity-off",
    "src/plan.mjs",
    '.filter((o) => o?.kind === "confirmed-positive" && o.validity === "valid")',
    '.filter((o) => o?.kind === "confirmed-positive")',
  ],
];

let survived = [],
  killed = 0,
  noapply = [];
for (const [name, file, find, rep] of mutants) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "aegis-m-"));
  fs.cpSync(base, dir, { recursive: true });
  const fp = path.join(dir, file);
  const s = fs.readFileSync(fp, "utf8");
  if (!s.includes(find)) {
    noapply.push(name);
    fs.rmSync(dir, { recursive: true, force: true });
    continue;
  }
  fs.writeFileSync(
    fp,
    s.replace(find, () => rep),
  );
  let code = 0;
  try {
    execFileSync("node", [path.join(dir, "run-fixtures.mjs")], {
      stdio: "pipe",
    });
  } catch (e) {
    code = e.status;
  }
  if (code === 0) survived.push(name);
  else killed++;
  fs.rmSync(dir, { recursive: true, force: true });
}
fs.rmSync(base, { recursive: true, force: true });

const unexpected = survived.filter((n) => !EQUIVALENT.has(n));
const missingEquiv = [...EQUIVALENT].filter(
  (n) => !survived.includes(n) && !noapply.includes(n),
);
console.log(
  `mutants: ${mutants.length}, killed ${killed}, survived ${survived.length} (${survived.filter((n) => EQUIVALENT.has(n)).length} equivalent), noapply ${noapply.length}`,
);
if (unexpected.length) {
  console.log(
    "UNEXPECTED SURVIVORS (coverage gaps):\n  " + unexpected.join("\n  "),
  );
}
if (noapply.length) {
  // A mutant whose find-string is absent exercises nothing. Fail so a refactor that
  // silently drops coverage is caught; update or remove the listed mutants.
  console.log("MUTANTS THAT DID NOT APPLY:\n  " + noapply.join("\n  "));
}
const ok = !unexpected.length && !noapply.length;
console.log(ok ? "MUTATION TEST: PASS" : "MUTATION TEST: FAIL");
process.exit(ok ? 0 : 1);
