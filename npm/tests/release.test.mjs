import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import test from "node:test";

const packageJson = JSON.parse(fs.readFileSync("package.json", "utf8"));
const script = path.resolve("scripts/check_release_ref.mjs");

function checkReleaseRef(...arguments_) {
  return spawnSync(process.execPath, [script, ...arguments_], {
    cwd: process.cwd(),
    encoding: "utf8",
  });
}

test("the release tag must match the package version", () => {
  const result = checkReleaseRef(`v${packageJson.version}`);

  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, new RegExp(`v${packageJson.version.replaceAll(".", "\\.")}`));
});

test("a mismatched release tag fails closed", () => {
  const result = checkReleaseRef("v0.0.0");

  assert.equal(result.status, 1);
  assert.match(result.stderr, /does not match/);
});

test("a missing release tag fails closed", () => {
  const result = checkReleaseRef();

  assert.equal(result.status, 1);
  assert.match(result.stderr, /Missing release tag/);
});
