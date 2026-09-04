# Contributing to TIDAL MCP

Contributions are welcome when they preserve the project's local-first security model and keep
public claims testable.

## Before opening a change

- Search existing issues and pull requests.
- Keep each change focused.
- Do not include account data, OAuth sessions, approval drafts, copyrighted lyrics, album artwork,
  or recordings.
- For new tools, identify the exact supported `tidalapi` operation and explain why it is a stable,
  user-facing capability rather than a raw implementation helper.

## Development setup

```bash
git clone https://github.com/sickn33/tidal-mcp.git
cd tidal-mcp
uv sync --all-groups
```

## Required verification

```bash
uv run ruff format --check .
uv run ruff check .
uv run pytest --cov=tidal_mcp --cov-report=term-missing
uv run python scripts/smoke_stdio.py
uv build
npm test
npm pack --dry-run
```

Statement and branch coverage must remain at 100%. Tests must use deterministic fakes unless a
test is explicitly documented as an opt-in live-account smoke test.

## Tool design contract

New MCP tools must:

- use the `tidal_` prefix and an action-oriented snake-case name;
- define bounded Pydantic inputs and structured outputs;
- carry accurate read-only, destructive, idempotent, and open-world annotations;
- return only allowlisted public fields;
- paginate list results;
- convert upstream failures into safe, actionable messages;
- keep blocking adapter calls outside the async protocol event loop;
- use preview and approval-token commit semantics for every remote mutation.

Do not expose raw endpoint methods, OAuth token loaders, media downloads, DRM operations, or an
unrestricted network proxy.

## Pull requests

Explain the user problem, implementation, safety impact, and verification performed. Update
`docs/API_COVERAGE.md`, tests, FAQ or use cases when behavior or public claims change.

By contributing, you agree that your contribution is licensed under the repository's MIT license.
