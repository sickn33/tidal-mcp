import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

export const packageRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

export function invocationFor(entrypoint, argv) {
  if (entrypoint === "tidal-mcp" && argv[0] === "auth") {
    return { entrypoint: "tidal-auth", argv: argv.slice(1) };
  }
  return { entrypoint, argv };
}

export function launch(entrypoint, argv = process.argv.slice(2)) {
  const invocation = invocationFor(entrypoint, argv);
  const uvx = process.env.TIDAL_MCP_UVX || "uvx";
  const child = spawn(
    uvx,
    ["--from", packageRoot, invocation.entrypoint, ...invocation.argv],
    { stdio: "inherit", env: process.env }
  );

  for (const signal of ["SIGINT", "SIGTERM", "SIGHUP"]) {
    const forward = () => {
      if (!child.killed) child.kill(signal);
    };
    process.once(signal, forward);
    child.once("exit", () => process.removeListener(signal, forward));
  }

  child.on("error", (error) => {
    if (error.code === "ENOENT") {
      console.error(
        "TIDAL MCP requires uv. Install it from https://docs.astral.sh/uv/ and run this command again."
      );
    } else {
      console.error(`Unable to start TIDAL MCP: ${error.message}`);
    }
    process.exitCode = 1;
  });

  child.on("exit", (code, signal) => {
    if (signal) {
      process.kill(process.pid, signal);
      return;
    }
    process.exitCode = code ?? 1;
  });
}
