# Read-only evaluation

Run the same production MCP tool definitions against deterministic local fixtures:

```bash
uv run python -m evaluations.fixture_server
```

Use `read_only.xml` as the evaluation question set. Every question is independent and
uses only tools annotated read-only. The fixture process has writes disabled and never
contacts TIDAL, so answers remain stable across runs.
