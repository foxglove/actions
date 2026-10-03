#!/usr/bin/env node
// Runnable example: feed one fixture through plan() and print the proposal.
// Usage: node attack-runner/planner/example.mjs [fixture-name]
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { plan } from "./src/index.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const name = process.argv[2] ?? "e1-03-claimed-fixed-resolved";
const input = JSON.parse(
  fs.readFileSync(path.join(here, "fixtures", name, "input.json"), "utf8"),
);
console.log(JSON.stringify(plan(input), null, 2));
