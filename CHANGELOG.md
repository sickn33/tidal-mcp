# Changelog

All notable changes to TIDAL MCP are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- Favorite track, album, artist, playlist, and video listings no longer stop after the first page
  when TIDAL returns a short page. Favorite mixes keep the previous behaviour, as `tidalapi`
  exposes no mix counter.
- A counted favorites page that returns no items is now emitted as a page with `has_more`, instead
  of a bare value without pagination metadata that ended a walk early.

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
- Complete 112-tool MCP surface covering the pinned `tidalapi 0.8.11` user-facing application API.
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
