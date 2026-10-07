# TIDAL MCP FAQ

## What is TIDAL MCP?

TIDAL MCP is a local Model Context Protocol server that lets compatible AI assistants search and
organize a TIDAL account through typed tools. It covers catalog lookup, recommendations, lyrics,
favorites, playlists, folders, mixes, discovery pages, and safety-gated account mutations.

## Is this an official TIDAL product?

No. This is an independent, unofficial open-source project. It is not affiliated with, endorsed
by, or sponsored by TIDAL. TIDAL is a trademark of its respective owner.

## Is this the most complete TIDAL MCP server?

It is the broadest public implementation found in the dated September 4, 2026 comparison. TIDAL
MCP now exposes 121 registered tools; the next-largest reviewed public implementation exposes 78.
Tool count is not the only measure of quality, so the comparison also records schemas, mutation
safety, tests, transports, and notable scope. Read the evidence and limitations in
[COMPETITIVE_MATRIX.md](COMPETITIVE_MATRIX.md).

## Which AI clients can use it?

Any MCP client that can launch a local stdio server should be compatible. The implementation has
been exercised through a real MCP stdio subprocess and configured locally with Codex. Claude
Desktop, Claude Code, and Cursor also accept stdio MCP configurations, although client UI and
configuration paths can change independently.

## Does it require TIDAL developer credentials?

No developer client ID or secret is required. Authentication uses TIDAL device login through the
pinned unofficial `tidalapi` adapter. This offers broad consumer-account coverage but can require
maintenance when TIDAL changes its private endpoints.

## Where are my TIDAL credentials stored?

The OAuth session is stored outside the repository in the operating system's private application
data directory. Authentication happens through the separate `tidal-auth` command. Tool responses
serialize only allowlisted public fields and cannot expose the session object or OAuth tokens.

Never commit or share `session.json`.

## Can it analyze an entire playlist?

Yes. The server can list the authenticated user's playlists, resolve an exact playlist, paginate
through all its tracks or mixed items, compare reported counts, and return structured metadata for
analysis. An AI assistant can calculate duration, artist and album concentration, eras, explicit
content, duplicate candidates, and ordering patterns.

Musical attributes not exposed by the adapter—such as a guaranteed BPM, key, mood, or acoustic
profile for every track—must not be presented as API facts.

## Can it create or edit playlists?

Yes, when writes are explicitly enabled. Playlist creation, editing, deletion, clearing, merging,
visibility, item insertion, removal, and reordering are covered. Favorites and playlist folders
can also be managed.

## How are accidental writes prevented?

Writes are disabled by default. When enabled, a named preview tool creates a private local draft
containing the exact action, parameters, target metadata, expiry, and destructive flag. A separate
commit tool requires the draft's single-use approval token. The assistant should call it only after
the user approves the displayed preview.

## Does it download music or bypass DRM?

No. Media downloading, manifest extraction, DRM handling, and file conversion are explicit
non-goals. Some read tools return temporary, account-scoped playback metadata or URLs provided by
the upstream adapter.

## Does it control speakers or TIDAL Connect devices?

No. UPnP, DLNA, and device-network control are outside the current security boundary. They could
be implemented as a separate optional component, but they are not counted as TIDAL API coverage.

## Why are there 121 tools instead of one raw API tool?

Individual allowlisted tools are easier for an AI client to discover, validate, audit, and annotate
correctly. An unrestricted raw endpoint would bypass input schemas, public-field serialization,
and the mutation approval design.

## Why can playlist metadata and fetched item counts differ?

TIDAL can return a cached count on a playlist object while its dedicated count endpoint and
paginated item endpoint return a newer value. Agents should compare the dedicated track count,
item count, and fetched pages before declaring the discrepancy an error.

## Is Linux supported?

The project is designed for macOS and Linux. macOS has been tested against a real account. Linux is
covered by deterministic CI but should still be treated as community-supported until more live
account reports are available.

## Is there a hosted remote server?

No. Version 1.0 is intentionally local-first and uses stdio, keeping account sessions and approval
drafts on the user's machine. A future remote service would need a separate OAuth, tenancy,
origin-validation, abuse-prevention, and privacy design.

## How can I verify the claims?

Run the formatter, linter, full statement-and-branch coverage suite, real stdio smoke test, and
package build documented in the main README. The tool inventory is defined in
[`src/tidal_mcp/catalog.py`](../src/tidal_mcp/catalog.py) and
[`src/tidal_mcp/server.py`](../src/tidal_mcp/server.py).
