import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, writeFileSync, rmSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const cli = fileURLToPath(
  new URL("../../src/attack-runner/cli.mjs", import.meta.url),
);
const fixture = JSON.parse(
  readFileSync(new URL("./fixtures/F1-new.json", import.meta.url), "utf8"),
);
function run(input) {
  const dir = mkdtempSync(join(tmpdir(), "attack-runner-cli-"));
  try {
    const path = join(dir, "input.json");
    writeFileSync(path, input);
    return spawnSync(process.execPath, [cli, "plan", "--input", path], {
      encoding: "utf8",
    });
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

test("CLI exits 0 for a complete plan and 2 for unresolved identity", () => {
  const good = run(JSON.stringify(fixture));
  assert.equal(good.status, 0);
  assert.equal(JSON.parse(good.stdout).decisions[0].outcome, "new");
  const x = structuredClone(fixture);
  x.observations[0].status = "incomplete";
  const unresolved = run(JSON.stringify(x));
  assert.equal(unresolved.status, 2);
  assert.equal(JSON.parse(unresolved.stdout).status, "needs_review");
});

test("CLI rejects malformed shared input and never echoes malformed source bytes", () => {
  const secret = "FAKE_SECRET_ABC123_NOT_JSON";
  const invalid = run(secret);
  assert.equal(invalid.status, 1);
  assert.equal(invalid.stdout, "");
  assert.match(invalid.stderr, /Input is not valid JSON/);
  assert.ok(!invalid.stderr.includes(secret.slice(0, 8)));
  const shared = run("{}");
  assert.equal(shared.status, 1);
  assert.match(shared.stderr, /schemaVersion/);
});

test("CLI exits 3 and keeps an existing output file unchanged", () => {
  const dir = mkdtempSync(join(tmpdir(), "attack-runner-cli-output-"));
  try {
    const input = join(dir, "input.json");
    const output = join(dir, "plan.json");
    const existing = "existing content\n";
    writeFileSync(input, JSON.stringify(fixture));
    writeFileSync(output, existing);

    const result = spawnSync(
      process.execPath,
      [cli, "plan", "--input", input, "--output", output],
      { encoding: "utf8" },
    );

    assert.equal(result.status, 3);
    assert.equal(result.stdout, "");
    assert.match(result.stderr, /Output file already exists/);
    assert.equal(readFileSync(output, "utf8"), existing);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("CLI exits 3 and identifies a missing output directory", () => {
  const dir = mkdtempSync(join(tmpdir(), "attack-runner-cli-output-"));
  try {
    const input = join(dir, "input.json");
    const output = join(dir, "missing", "plan.json");
    writeFileSync(input, JSON.stringify(fixture));

    const result = spawnSync(
      process.execPath,
      [cli, "plan", "--input", input, "--output", output],
      { encoding: "utf8" },
    );

    assert.equal(result.status, 3);
    assert.equal(result.stdout, "");
    assert.match(result.stderr, /Cannot write output file \(ENOENT\)/);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
