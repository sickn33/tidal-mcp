# Changelog

All notable changes to TIDAL MCP are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `tidal_export_analysis` writes a playlist summary or a two-playlist comparison to a JSON file.
  It computes the derived result with the same code the read tools use and writes it through the
  same private, non-overwriting writer as a playlist export, so the derived export adds no new way
  to reach the filesystem. JSON only: a derived result is structured analysis, not a track list.

### Changed

- Playlist tools now resolve the playlist once per call and reuse that object, instead of
  re-fetching the same metadata for the track count, every page, and the title. Measured against a
  real account: collecting 50 tracks fell from 6 HTTP requests to 4, and collecting a 473-track
  playlist now costs 13 where every one of its 10 pages previously re-resolved the playlist.
  Summaries, comparisons, and exports benefit the same way.

### Fixed

- The README tool table summed to 126 against a documented total of 121: the collection group said
  24 while holding 22, the analysis group said 2 while holding 3, and prompts were counted as
  tools. A test now parses the table and fails the build unless its rows add up and no row counts a
  prompt as a tool.
- The landing page numbered its capability groups 1-18, 19-34, 35-52, 53-74, 75-110, 120-121, which
  left 111-119 unassigned and no longer matched the surface. The ranges now tile 1-121 with no gap
  or overlap, and a test enforces that.
- The authenticated smoke test writes an export while checking `tidal_export_playlist`. It now sets
  `TIDAL_MCP_EXPORT_DIR` to a temporary directory, so running it can never write into the caller's
  real export directory.

## [1.3.0] - 2026-10-07

### Added

- `tidal_export_playlist` writes a playlist to JSON or M3U inside the private export directory. It
  is the only tool that writes to local disk, so it is annotated as not read-only. It refuses to
  overwrite an existing file, sanitizes the requested name to a single path segment, and writes
  through a temporary file. Set `TIDAL_MCP_EXPORT_DIR` to place exports elsewhere.
- `tidal_compare_playlists` reports the shared, left-only, and right-only tracks of two playlists,
  matching on the normalized title and artist pair. TIDAL serves distinct ids for the same
  recording across releases, so comparing ids would report a shared song as two different ones.

### Fixed

- `playlist_title` returned the formatter's `Untitled Playlist` placeholder for a nameless
  playlist, which would have become an exported file name. It now reports `None` so an export
  falls back to a neutral name instead of inventing one.
- The smoke test's own expected-tool list had fallen behind, so the packaged check would have
  passed while ignoring newly registered tools. A test now asserts both tool lists agree.

### Documentation

- The coverage contract stated the server was built from "six handwritten workflow tools" and
  asserted 100% `tidalapi` coverage without listing what it excluded. It now names all 70
  exclusions in six groups whose sizes are derived from the surface test.

## [1.2.0] - 2026-10-07

### Added

- Two read tools that remove the pagination loop from the caller. `tidal_collect_playlist_tracks`
  walks a playlist's pages until the end or an explicit cap and reports `truncated`, so a capped
  result is never mistaken for a complete playlist. `tidal_summarize_playlist` derives duration,
  top artists, decade spread, explicit count, tracks without a parseable release date, and exact
  duplicates from metadata the read tools already return.
- Four built-in MCP prompts: `tidal_playlist_from_description`, `tidal_playlist_review`,
  `tidal_discovery_digest`, and `tidal_library_audit`. Each names the tools to use, and the ones
  that touch writes stop at the preview and require the user's approval before committing.

### Fixed

- The README, coverage contract, registry metadata, landing page, and llms files claimed a
  `credits` capability that does not exist. TIDAL exposes no credits endpoint and `tidalapi`'s
  `artist_roles` field stays `None` on real tracks, so the wording now lists only lyrics.
- The documented tool counts had drifted from the code. A test now derives them from the
  executable inventory and fails the build when a document disagrees.

## [1.1.1] - 2026-10-07

### Fixed

- `tidal_show_more_page_category` now expands personalized Home sections. Those categories
  advertise their follow-up path under `home/pages/...`, but the API answers the section only at
  `pages/...`, so the advertised path returned 404 for every Home category. A section with no
  items today is now reported as "no expandable items right now" instead of a generic upstream
  failure, because `tidalapi`'s page parser rejects the empty `rows` response TIDAL returns. Both
  behaviors were measured against a live account.

### Changed

- The authenticated read-only smoke test now also covers editorial page navigation, v2 mix items,
  video search, and the track ISRC field.

## [1.1.0] - 2026-10-07

### Added

- Editorial page navigation through four new read tools: `tidal_list_page_category_items`,
  `tidal_list_page_links`, `tidal_show_more_page_category`, and `tidal_open_page_link`. The browse
  tools previously returned only the first screen of a page, because nothing could follow a
  category's show-more endpoint or open a page link.
- `tidal_get_mix_v2_items` pages through the tracks and videos of a current-generation mix, which
  `tidalapi 0.8.11` stores privately and exposes only for legacy mixes.
- Video results in `tidal_search` through the new `videos` media type, and the International
  Standard Recording Code as an `isrc` field on every returned track.

### Fixed

- `urllib3` is now pinned to `>=2.8.0` and `PyJWT` is locked to `2.15.1`, closing a critical
  PyJWT PEM-detection bypass, several high and medium PyJWT advisories, and two high urllib3
  advisories that the previous dependency range still allowed.
- `execute_read` no longer re-wraps a precise local validation message, such as an out-of-range
  category index, into the generic "try again" TIDAL error. An internal handler `KeyError` was
  also reported as an unsupported operation; only an unknown operation name now says that.
- Favorite track, album, artist, playlist, and video listings no longer stop after the first page
  when TIDAL returns a short page. Favorite mixes keep the previous behaviour, as `tidalapi`
  exposes no mix counter.
- A counted favorites page that returns no items is now emitted as a page with `has_more`, instead
  of a bare value without pagination metadata that ended a walk early.
- Favorite playlist, favorite mix, playlist folder, public playlist, and combined playlist
  listings no longer fail for any request of 50 or more items, where the pagination probe asked
  TIDAL for 51. Those five now serve at most 50 items per page, whatever `limit` is requested.

## [1.0.1] - 2026-09-04

### Added

- Automated MCP Registry publication through GitHub OIDC after each npm release.
- Release-tag validation that fails closed when the GitHub tag and package version differ.
- A public-package mode for the authenticated read-only smoke test.

### Changed

- Expanded the release metadata gate to cover both lockfiles, Python runtime version, citation
  metadata, and the machine-readable `llms.txt` version.
- Moved npm releases onto the complete Trusted Publishing path, which automatically emits public
  provenance attestations without a long-lived write token.

## [1.0.0] - 2026-09-04

### Added

- npm distribution as `@sickn33/tidal-mcp` and official MCP Registry metadata.
- Complete 117-tool MCP surface covering the pinned `tidalapi 0.8.11` user-facing application API.
- Structured input and output schemas plus MCP safety annotations for every tool.
- Catalog, editorial, discovery, lyrics, favorites, playlist, folder, mix, image, and playback
  metadata reads.
- Deterministic multi-seed recommendation filters with source provenance.
- Universal local preview and single-use approval-token commit flow for remote mutations.
- Private persistent authentication and draft storage outside the repository.
- Real stdio and authenticated read-only smoke checks.
- Deterministic evaluation fixture and dated public competitive evidence.
- 100% statement and branch coverage gate.

### Security

- Raised the minimum supported `requests` and `urllib3` versions to patched releases.
- Removed the unused MCP CLI extra and its unnecessary runtime dependency surface.
- Updated the locked test toolchain to patched `pytest` and Pygments releases.

### Changed

- Replaced the original Flask sidecar architecture with one asynchronous MCP stdio process.
- Reworked result serialization around explicit public fields and paginated structured models.

### Removed

- Temporary OAuth storage, raw session exposure, and direct unapproved writes.
