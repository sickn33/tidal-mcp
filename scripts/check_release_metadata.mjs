import assert from "node:assert/strict";
import fs from "node:fs";

const packageJson = JSON.parse(fs.readFileSync("package.json", "utf8"));
const packageLock = JSON.parse(fs.readFileSync("package-lock.json", "utf8"));
const serverJson = JSON.parse(fs.readFileSync("server.json", "utf8"));
const pyproject = fs.readFileSync("pyproject.toml", "utf8");
const uvLock = fs.readFileSync("uv.lock", "utf8");
const pythonPackage = fs.readFileSync("src/tidal_mcp/__init__.py", "utf8");
const pythonServer = fs.readFileSync("src/tidal_mcp/server.py", "utf8");
const citation = fs.readFileSync("CITATION.cff", "utf8");
const changelog = fs.readFileSync("CHANGELOG.md", "utf8");
const llms = fs.readFileSync("llms.txt", "utf8");
const readme = fs.readFileSync("README.md", "utf8");

const pythonVersion = pyproject.match(/^version = "([^"]+)"$/m)?.[1];
const uvVersion = uvLock.match(/\[\[package\]\]\nname = "tidal-mcp"\nversion = "([^"]+)"/m)?.[1];
const packageVersion = pythonPackage.match(/^__version__ = "([^"]+)"$/m)?.[1];
const serverVersion = pythonServer.match(/^\s*version="([^"]+)",$/m)?.[1];
const citationVersion = citation.match(/^version:\s*"?([^"\s]+)"?$/m)?.[1];
const llmsVersion = llms.match(/^Current version:\s*(\S+)$/m)?.[1];

assert.equal(packageJson.version, pythonVersion, "npm and Python versions must match");
assert.equal(uvVersion, packageJson.version, "uv lockfile project version must match npm");
assert.equal(packageLock.version, packageJson.version, "npm lockfile version must match npm");
assert.equal(
  packageLock.packages[""].version,
  packageJson.version,
  "npm lockfile root package version must match npm"
);
assert.equal(packageVersion, packageJson.version, "Python package runtime version must match npm");
assert.equal(serverVersion, packageJson.version, "MCP runtime version must match npm");
assert.equal(citationVersion, packageJson.version, "citation version must match npm");
assert.equal(llmsVersion, packageJson.version, "llms.txt version must match npm");
assert.match(changelog, new RegExp(`^## \\[${packageJson.version.replaceAll(".", "\\.")}\\]`, "m"));
assert.ok(
  readme.includes(`Version **${packageJson.version}**`),
  "README project status version must match npm"
);
assert.equal(serverJson.version, packageJson.version, "server.json version must match npm");
assert.equal(serverJson.name, packageJson.mcpName, "MCP registry names must match");
assert.equal(serverJson.packages.length, 1, "server.json must declare one release package");
assert.equal(serverJson.packages[0].registryType, "npm");
assert.equal(serverJson.packages[0].identifier, packageJson.name);
assert.equal(serverJson.packages[0].version, packageJson.version);

console.log(`Release metadata is synchronized at ${packageJson.name}@${packageJson.version}.`);
