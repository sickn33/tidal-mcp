import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

import { invocationFor, packageRoot } from "../launcher.mjs";

test("the default npx command starts the MCP server", () => {
  assert.deepEqual(invocationFor("tidal-mcp", []), {
    entrypoint: "tidal-mcp",
    argv: [],
  });
});

test("the friendly auth subcommand starts the authentication CLI", () => {
  assert.deepEqual(invocationFor("tidal-mcp", ["auth", "--status"]), {
    entrypoint: "tidal-auth",
    argv: ["--status"],
  });
});

test("the published package contains the Python project", () => {
  assert.equal(fs.existsSync(path.join(packageRoot, "pyproject.toml")), true);
  assert.equal(fs.existsSync(path.join(packageRoot, "src", "tidal_mcp", "server.py")), true);
});
