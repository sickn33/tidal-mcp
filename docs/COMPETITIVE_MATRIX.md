# Public TIDAL MCP comparison

Snapshot date: **September 4, 2026**.

## Result

TIDAL MCP has the broadest explicitly registered TIDAL tool surface found in the reviewed public
repositories. It also combines structured outputs, a universal preview-token write gate, and a
100% statement-and-branch coverage requirement.

| Implementation | Registered tools | Inspected commit | Notable scope |
| --- | ---: | --- | --- |
| **TIDAL MCP 1.0** | **112** | September 4, 2026 snapshot | Complete pinned `tidalapi` application surface; 74 reads, 36 previews, 2 commits |
| **TIDAL MCP, current** | **117** | current repository | The snapshot plus editorial page navigation, v2 mix items, and video search; 73 reads, 36 previews, 2 commits |
| [michalu/tidal-mcp](https://github.com/michalu/tidal-mcp) | 78 | `dc21c646ce49` | Broad consumer API surface plus UPnP/DLNA playback and multiple transports |
| [lucaperret/tidal-cli](https://github.com/lucaperret/tidal-cli) | 40 | `24f20a852978` | Official API v2 CLI plus hosted MCP, playback, library, and sharing workflows |
| [teobouancheau/tidal-mcp](https://github.com/teobouancheau/tidal-mcp) | 35 | `2ffa136e7fc0` | Official developer API, typed TypeScript, local and Streamable HTTP transports |
| [farbfoto/TIDALMCP](https://github.com/farbfoto/TIDALMCP) | 32 | `dfcffa6cfef9` | Catalog and account workflows |
| [keenanbb/tidal-mcp](https://github.com/keenanbb/tidal-mcp) | 27 | `0a5729e2d372` | Catalog, library, recommendations, and playlist workflows |
| [avmeg8/tidal-mcp](https://github.com/avmeg8/tidal-mcp) | 27 | `8a828e34804a` | Catalog and library workflows |
| [dragomirweb/tidal-mcp](https://github.com/dragomirweb/tidal-mcp) | 19 | `bbf77ae14ec6` | Core TIDAL workflows with Docker distribution |
| [ibeal/tidal-mcp](https://github.com/ibeal/tidal-mcp) | 19 | `bf086bbdeffc` | Consumer API search, recommendations, library, and playlist workflows |
| [damilola-elegbede-org/tidal-mcp](https://github.com/damilola-elegbede-org/tidal-mcp) | 15 | `0652be0d8ff1` | Core catalog and account workflows |
| [redDawne/tidal-mcp-server](https://github.com/redDawne/tidal-mcp-server) | 9 | `6561074d5a15` | Compact server surface |
| [yuhuacheng/tidal-mcp](https://github.com/yuhuacheng/tidal-mcp) | 7 | `537aea1b8ea2` | Original recommendations and playlist implementation |
| [mikeysrecipes/tidal-mcp](https://github.com/mikeysrecipes/tidal-mcp) | 7 | `1119bed54868` | Compact server surface |

## Method

1. Search the public web and GitHub for repositories matching TIDAL plus MCP or Model Context
   Protocol.
2. Exclude results about tidal-energy software, Tidal Cyber, unrelated projects named “Retidal,”
   clients with no MCP server, and exact forks without a distinct implementation.
3. Clone each qualifying default branch on the snapshot date.
4. Count explicit MCP registrations in executable Python or TypeScript source:
   `@mcp.tool`, equivalent decorated tools, `server.registerTool`, and `server.tool`.
5. Inspect the source and README for transport, authentication, mutation, test, and scope claims.

Dynamic aliases or generic raw-endpoint dispatchers are not inflated into hypothetical tool
counts. Commit hashes make the snapshot reproducible. The compact research record is preserved in
[`research-results/tidal-mcp-landscape-2026-09-04`](../research-results/tidal-mcp-landscape-2026-09-04/brief.md).

## What the comparison proves

At the inspected commits:

- TIDAL MCP exposed **112** named tools on September 4, 2026, and now exposes **117**; the
  next-largest reviewed surface exposes **78**.
- Every TIDAL MCP tool has bounded inputs, structured output, and MCP safety annotations.
- Every remote mutation passes through a local preview and separate approval-token commit.
- The repository's deterministic gate requires 100% statement and branch coverage.

## What it does not prove

- More tools do not automatically produce better answers.
- The review cannot guarantee that no unindexed or private implementation exists.
- A local consumer-endpoint adapter and an official developer-API integration have different
  compatibility, credential, policy, and maintenance tradeoffs.
- The snapshot can become stale as repositories change.
- It does not guarantee future compatibility with TIDAL endpoint changes.

For those reasons, public wording should be **“the most complete public TIDAL MCP implementation
found in the September 4, 2026 review,”** not an unsupported permanent or official claim.
