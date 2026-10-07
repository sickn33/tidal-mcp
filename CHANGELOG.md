# Changelog

All notable changes to TIDAL MCP are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
