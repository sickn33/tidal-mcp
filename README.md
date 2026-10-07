# TIDAL MCP — Complete, Safety-First TIDAL Server for AI Assistants

![Abstract sound waves becoming a network of MCP tools](assets/tidal-mcp-hero.webp)

[![CI](https://github.com/sickn33/tidal-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/sickn33/tidal-mcp/actions/workflows/ci.yml)
[![Website](https://img.shields.io/badge/website-live-B8FF3D?logo=githubpages&logoColor=111111)](https://sickn33.github.io/tidal-mcp/)
[![npm](https://img.shields.io/npm/v/%40sickn33%2Ftidal-mcp?logo=npm)](https://www.npmjs.com/package/@sickn33/tidal-mcp)
[![Python 3.11–3.13](https://img.shields.io/badge/Python-3.11%E2%80%933.13-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![MCP Python SDK 2.x](https://img.shields.io/badge/MCP%20Python%20SDK-2.x-6C5CE7)](https://modelcontextprotocol.io/)
[![Tests: 100% statements + branches](https://img.shields.io/badge/tests-100%25%20statements%20%2B%20branches-brightgreen)](#verified-quality)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**TIDAL MCP** connects Codex, Claude Desktop, Claude Code, Cursor, and other
stdio-compatible Model Context Protocol clients to a TIDAL account. Search the catalog,
analyze playlists, discover music, read lyrics, manage favorites, organize folders,
and safely create or edit playlists through **121 typed MCP tools**.

> **Positioning:** in the September 4, 2026 review, this was the most complete public TIDAL MCP
> implementation found in a reproducible review of the current GitHub landscape. The claim is
> based on registered tool coverage, structured schemas, mutation safety, and automated test
> evidence—not marketing alone. See the [dated comparison](docs/COMPETITIVE_MATRIX.md).

<!-- mcp-name: io.github.sickn33/tidal-mcp -->

## Why this TIDAL MCP exists

Most TIDAL integrations expose a small selection of search and playlist commands. TIDAL MCP is
built as a complete local control surface for AI agents while keeping credentials and approvals
on your machine.

- **121 discoverable tools:** 83 reads, 36 mutation previews, and 2 approval-token commits.
- **Broad account coverage:** catalog, editorial pages, recommendations, lyrics, favorites,
  playlists, folders, mixes, images, and playback metadata.
- **Safe writes:** mutations are off by default and always require preview → explicit approval →
  commit.
- **Private authentication:** OAuth session data never travels through MCP tool responses.
- **Typed and bounded:** every input and output has a schema, limits, and MCP safety annotations.
- **Verified quality:** 100% statement and branch test coverage plus a real stdio handshake and an
  optional authenticated read-only smoke test.

## What can an AI assistant do with TIDAL?

Ask naturally:

- “Analyze my entire workout playlist: artist concentration, eras, duplicates, duration, and
  sequencing.”
- “Find 20 tracks related to these three songs, exclude anything already in my playlist, and use
  at most two tracks per artist.”
- “Compare an artist’s albums, EPs, singles, appearances, top tracks, biography, and related
  artists.”
- “Show my favorite albums and playlists, then summarize how my collection is distributed.”
- “Prepare a new playlist from these recommendations and show me the exact changes before doing
  anything.”
- “Move these playlists into a folder, but ask for confirmation before changing my account.”

See [real-world workflows and prompt examples](docs/USE_CASES.md).

## Tool coverage

| Surface | Tools | Examples |
| --- | ---: | --- |
| Authentication, search, recommendations | 3 | status, multi-type search, deterministic multi-seed recommendations |
| Catalog, editorial, discovery | 54 | tracks, albums, artists, videos, lyrics, genres, Home, Explore, For You |
| Collection, playlists, folders | 22 | favorites, counts, playlist items, owned/public playlists, folders, mixes |
| Derived analysis | 3 | full-playlist collection, playlist summary, playlist comparison |
| Local export | 1 | playlist to JSON or M3U in the private export directory |
| Exact mutation previews | 36 | playlist CRUD, item moves, visibility, favorites, folders |
| Approval-token commits | 2 | universal commit and compatible playlist-creation alias |

The table sums to the **121** registered tools. Four MCP prompts are registered alongside them
(playlist-from-description, playlist review, discovery digest, library audit); prompts are guidance
over the tools, so they are not counted as tools.

Every list operation is bounded and paginated. Every result uses a public-field allowlist so OAuth
tokens, request clients, and internal session data cannot enter model context. The complete map is
in [API_COVERAGE.md](docs/API_COVERAGE.md).

## Quick start

### Requirements

- macOS or Linux; macOS is live-account tested
- Node.js 18 or newer
- Python 3.11–3.13
- [`uv`](https://docs.astral.sh/uv/)
- A TIDAL account

### 1. Install and authenticate

```bash
npx -y @sickn33/tidal-mcp auth
```

Open the device-authorization URL, approve access in TIDAL, and return to the terminal. The session
is stored in your private operating-system application-data directory, not in the repository.

Check or remove it at any time:

```bash
npx -y @sickn33/tidal-mcp auth --status
npx -y @sickn33/tidal-mcp auth --logout --yes
```

To install from source for development instead:

```bash
git clone https://github.com/sickn33/tidal-mcp.git
cd tidal-mcp
uv sync
uv run tidal-auth
```

### 2. Connect an MCP client

Use npm directly; the package launches the pinned Python implementation locally through `uvx`:

```json
{
  "mcpServers": {
    "tidal": {
      "command": "npx",
      "args": [
        "-y",
        "@sickn33/tidal-mcp"
      ]
    }
  }
}
```

Restart or reconnect your MCP client, then ask: **“Check my TIDAL authentication status.”**

## Enable safe account writes

Remote writes are disabled unless the MCP process receives:

```json
"env": {
  "TIDAL_MCP_ENABLE_WRITES": "1"
}
```

Enabling the flag does **not** make mutations automatic. Every change still uses three explicit
steps:

1. A named `tidal_preview_*` tool records the exact parameters and target metadata in a private,
   short-lived local draft.
2. The assistant presents that preview to the user.
3. Only after approval does `tidal_commit_action` accept the single-use token and execute exactly
   the recorded action.

Successful token replays return the stored result. Expired tokens fail closed. Ambiguous failed
writes are locked to reduce duplicate effects. Destructive previews are clearly annotated.

## Supported TIDAL operations

- **Search and lookup:** tracks, albums, artists, playlists, videos, mixes, users, barcodes, ISRCs.
- **Track intelligence:** details, radio, radio mixes, lyrics, playback metadata, temporary
  account-scoped URLs.
- **Artists and albums:** discographies, EPs and singles, appearances, biographies, reviews,
  related artists, similar albums, resolutions, artwork, and editorial pages.
- **Discovery:** Home, Explore, For You, genres, moods, mixes, videos, hi-res, and local genre hubs.
- **Editorial navigation:** read the items and links inside a page category, expand a
  show-more/view-all section, and open a page link to keep browsing past the first screen.
- **Collection:** favorite tracks, albums, artists, playlists, videos, mixes, folders, and counts.
- **Playlists:** metadata, tracks, mixed items, counts, images, create/edit/delete/clear/merge,
  visibility, add/remove/reorder operations.
- **Folders:** inspect, create, rename, delete, and move collection-tree items.

The server intentionally does not download media, bypass DRM, expose raw OAuth methods, or provide
an unrestricted private-endpoint proxy.

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `TIDAL_MCP_ENABLE_WRITES` | `0` | Permit approval-token commits for allowlisted account mutations |
| `TIDAL_MCP_DATA_DIR` | OS application-data directory | Session and draft root |
| `TIDAL_MCP_SESSION_FILE` | `<data-dir>/session.json` | Override the OAuth session path |
| `TIDAL_MCP_DRAFT_TTL_SECONDS` | `900` | Approval lifetime, between 60 and 3600 seconds |
| `TIDAL_MCP_EXPORT_DIR` | `<data-dir>/exports` | Where `tidal_export_playlist` writes; created privately |

New private directories use mode `0700` and sensitive files use `0600` on systems supporting POSIX
permissions. Existing custom parent directories are never silently permission-rewritten.

## Verified quality

```bash
uv sync --all-groups
uv run ruff format --check .
uv run ruff check .
uv run pytest --cov=tidal_mcp --cov-report=term-missing
uv run python scripts/smoke_stdio.py
uv build
```

The coverage gate is **100% for statements and branches**. Tests exercise every registered read
and mutation route through the MCP schemas and the pinned `tidalapi` adapter without contacting
TIDAL. The stdio smoke test launches the packaged protocol process and verifies all 121 tool
schemas.

Official releases are published from GitHub Actions through npm Trusted Publishing, with no
long-lived npm write token. npm attaches provenance automatically, and the same release workflow
publishes the matching metadata to the official MCP Registry through GitHub OIDC.

An optional authenticated smoke test performs representative reads only:

```bash
uv run python scripts/smoke_live_read_only.py
```

Release maintainers can test the exact public npm package through the same MCP client path:

```bash
uv run python scripts/smoke_live_read_only.py \
  --command npx \
  --server-arg=-y \
  --server-arg=@sickn33/tidal-mcp@1.3.0
```

The deterministic [evaluation suite](docs/EVALUATION.md) and the dated
[competitive matrix](docs/COMPETITIVE_MATRIX.md) make quality claims inspectable.

## Architecture and compatibility

TIDAL provides developer APIs, but developer credentials are issued separately and the official
surface does not cover every consumer-account workflow. This local server therefore pins
`tidalapi 0.8.11`, an unofficial adapter around TIDAL’s consumer endpoints, for broad device-login
coverage. TIDAL changes can require maintenance; the pinned dependency and live smoke test make
that risk visible.

The server uses the MCP Python SDK over stdio. Blocking upstream calls run outside the async
protocol event loop. It does not launch a Flask sidecar or store authentication in temporary
directories.

## Documentation

- [Complete API coverage](docs/API_COVERAGE.md)
- [Use cases and prompt cookbook](docs/USE_CASES.md)
- [Frequently asked questions](docs/FAQ.md)
- [Security policy](SECURITY.md)
- [Competitive evidence](docs/COMPETITIVE_MATRIX.md)
- [Deterministic evaluation](docs/EVALUATION.md)
- [Contributing](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)

## Project status

Version **1.3.0** adds playlist export to JSON or M3U and a set comparison of two playlists, on top of the full-playlist collection, summaries, and prompts added in 1.2.0. npm is the primary installation channel, and every release is also published to the official MCP Registry.

## License, attribution, and trademark notice

MIT. This repository preserves the history and license of
[`yuhuacheng/tidal-mcp`](https://github.com/yuhuacheng/tidal-mcp); see [NOTICE.md](NOTICE.md).

TIDAL is a trademark of its respective owner. This is an independent, unofficial community
project and is not affiliated with, endorsed by, or sponsored by TIDAL. No TIDAL logo or album
artwork is bundled with the project.
