#!/usr/bin/env node
import { realpathSync } from "node:fs";
import { open, readFile, unlink } from "node:fs/promises";
import { pathToFileURL } from "node:url";
import { plan } from "./planner.mjs";

// Helps the operator correct invalid arguments by showing the planner command and its required input.
function usage() {
  return "Usage: yarn attack-runner plan --input <fixture.json> [--output <plan.json>]";
}

// Preserves an earlier plan by refusing to overwrite it. On a failed write, removes the partial output
// when possible and reports cleanup failure so a consumer cannot mistake it for a complete plan.
export async function writeOutput(path, json, fs = { open, unlink }) {
  let file;
  try {
    file = await fs.open(path, "wx");
    await file.writeFile(json);
    await file.sync();
    await file.close();
  } catch (error) {
    let cleanupError;
    if (file) {
      await file.close().catch(() => {});
      await fs.unlink(path).catch((caught) => {
        if (caught.code !== "ENOENT") cleanupError = caught;
      });
    }
    let message =
      error.code === "EEXIST"
        ? "Output file already exists. Choose a new path or remove the existing file."
        : `Cannot write output file (${error.code ?? "unknown error"}).`;
    if (cleanupError) {
      message += ` Incomplete output may remain (${cleanupError.code ?? "unknown cleanup error"}).`;
    }
    const outputError = new Error(message);
    outputError.exitCode = 3;
    throw outputError;
  }
}

// Turns one local assessment record into ticket proposals for review. Returns 2 when items need
// review; a successful planner exit does not mean an attack completed or a ticket was written.
export async function main(args) {
  if (args[0] !== "plan") throw new Error(usage());
  let input, output;
  for (let i = 1; i < args.length; i += 2) {
    if (args[i] === "--input" && args[i + 1]) input = args[i + 1];
    else if (args[i] === "--output" && args[i + 1]) output = args[i + 1];
    else throw new Error(usage());
  }
  if (!input) throw new Error(usage());
  let source, raw;
  try {
    source = await readFile(input, "utf8");
  } catch {
    throw new Error("Cannot read input file");
  }
  try {
    raw = JSON.parse(source);
  } catch {
    throw new Error("Input is not valid JSON");
  }
  const result = plan(raw);
  const json = `${JSON.stringify(result, null, 2)}\n`;
  if (output) await writeOutput(output, json);
  else process.stdout.write(json);
  return result.status === "planned" ? 0 : 2;
}

if (
  process.argv[1] &&
  import.meta.url === pathToFileURL(realpathSync(process.argv[1])).href
) {
  try {
    process.exitCode = await main(process.argv.slice(2));
  } catch (e) {
    process.stderr.write(`Attack Runner planner: ${e.message}\n`);
    process.exitCode = e.exitCode ?? 1;
  }
}
