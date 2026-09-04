import assert from "node:assert/strict";
import fs from "node:fs";

const packageJson = JSON.parse(fs.readFileSync("package.json", "utf8"));
const serverJson = JSON.parse(fs.readFileSync("server.json", "utf8"));
const pyproject = fs.readFileSync("pyproject.toml", "utf8");

const pythonVersion = pyproject.match(/^version = "([^"]+)"$/m)?.[1];

assert.equal(packageJson.version, pythonVersion, "npm and Python versions must match");
assert.equal(serverJson.version, packageJson.version, "server.json version must match npm");
assert.equal(serverJson.name, packageJson.mcpName, "MCP registry names must match");
assert.equal(serverJson.packages.length, 1, "server.json must declare one release package");
assert.equal(serverJson.packages[0].registryType, "npm");
assert.equal(serverJson.packages[0].identifier, packageJson.name);
assert.equal(serverJson.packages[0].version, packageJson.version);

console.log(`Release metadata is synchronized at ${packageJson.name}@${packageJson.version}.`);
