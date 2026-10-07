# API coverage contract

This document defines what “complete” means for TIDAL MCP. The supported adapter is
`tidalapi 0.8.11`; the executable source of truth is `src/tidal_mcp/catalog.py` plus the ten
handwritten workflow tools in `src/tidal_mcp/server.py`.

## Coverage result

- 122 MCP tools with input and output schemas.
- 84 read-only tools.
- 36 exact local mutation-preview tools.
- 2 approval-token commit tools.
- 100% statement and branch test coverage, enforced by `fail_under = 100`.
- 100% coverage of stable, user-facing `tidalapi 0.8.11` operations that can be represented
  safely as catalog, library, playlist, folder, editorial, recommendation, or playback-metadata
  workflows.

## What is deliberately not covered

“Complete” above is bounded, and the bound is executable rather than a claim. `tests/test_tidalapi_surface.py`
enumerates every public method across the 16 supported `tidalapi` classes and requires each one to
appear either as covered or as an explicit exclusion. There are 123 covered methods and 70
exclusions; a method that appears in neither list fails the build, so the surface cannot drift
silently in either direction.

The 70 exclusions fall into six groups, and the group sizes sum to exactly 70:

| Group | Count | Members | Why it is excluded |
| --- | ---: | --- | --- |
| Parsers and factories | 38 | `parse_track`, `parse_playlist`, `parse_v2_mix`, `factory`, and siblings | Internal deserialization. The client consumes their results; exposing them would let a caller construct objects the server cannot trust. |
| Authentication plumbing | 15 | `login_oauth`, `load_session_from_file`, `token_refresh`, `pkce_login_url`, and siblings | Authentication runs in the separate `tidal-auth` command. Keeping it out of the protocol is what prevents credentials from entering model context. |
| Unbounded paginated helpers | 7 | `Playlist.tracks_paginated`, `Favorites.albums_paginated`, and siblings | They fetch an entire collection in one call with no cap. The MCP tools page explicitly instead, or use `tidal_collect_playlist_tracks`, which enforces one. |
| Redundant aliases | 3 | `Artist.get_ep_singles`, `Artist.get_other`, `Artist.items` | The first two alias the covered `get_albums_ep_singles` and `get_albums_other`; `items` always returns an empty list. |
| Page traversal implemented directly | 3 | `Page.next`, `PageCategory.show_more`, `PageCategoryV2.view_all` | The editorial tools read the private `_more` record and load the endpoint themselves, because `view_all()` calls a `Session.view_all` method that does not exist in `tidalapi 0.8.11`. |
| Internal plumbing | 4 | `Stream.get_manifest_data`, `Stream.get_stream_manifest`, `PageCategoryV2.register_subclass`, `Session.convert_type` | Reachable only from the groups above, or superseded by `tidal_get_track_audio_resolution` and `tidal_get_track_playback_info`. |

`Stream.get_stream_manifest` itself works; it is excluded because the playback-metadata tools
already cover bit depth and sample rate. `Stream.get_mimetype`, which is genuinely broken upstream
and raises `AttributeError`, is not part of the accounted surface because it is not a method of an
enumerated class.

## Read surface

| TIDAL surface | MCP coverage |
| --- | --- |
| Session/account | Authentication status; current or public user lookup; user image |
| Search and identifiers | Multi-type search including videos; track, album, artist, playlist, video, mix, user; barcode and ISRC lookup |
| Tracks | Metadata, radio tracks, radio mix, lyrics, playback metadata, temporary playback URL |
| Albums | Metadata, tracks, mixed items, review, similar albums, audio resolutions, cover/video art, page |
| Artists | Metadata, albums, EPs/singles, other appearances, bio, radio, radio mix, related artists, top tracks, videos, image, page |
| Videos | Metadata, image, temporary playback URL |
| Playlists | Metadata, paginated tracks/items, item and track counts, square/wide images |
| Collection | Favorite tracks, albums, artists, playlists, videos, mixes, folders, aggregate counts |
| User playlists | Owned, public, and combined owned/favorite views |
| Mixes | Legacy and v2 metadata/images plus paginated mix items for both mix generations |
| Discovery pages | Home, Explore, For You, genre hubs, hi-res, local genres, mixes, moods, videos |
| Editorial navigation | Category items, section links, show-more/view-all expansion, and opening a page link |
| Derived analysis | Full-playlist collection with an explicit cap, a deterministic playlist summary (duration, top artists, decades, explicit count, duplicates), and a set comparison of two playlists |
| Local export | A playlist written to JSON or M3U, plus a summary or comparison written to JSON, all inside the private export directory and never overwriting an existing file |
| Genres | Complete genre list and paginated tracks, albums, artists, playlists, or videos by genre |
| Folders | Folder metadata and paginated contents |
| Recommendations | Multi-seed Track Radio, deduplication, provenance, deterministic metadata filters |

Catalog search returns videos alongside tracks, albums, artists, and playlists when the caller
requests them. Video results use the same public-item shape as the other video tools, because
`tidalapi` exposes videos with a different field set than the other catalog objects.

Editorial pages are navigated in four steps. `tidal_list_page_category_items` returns the catalog
objects inside one category, resolving lazy `PageItem` wrappers through `PageItem.get()`.
`tidal_list_page_links` returns the `PageLink` entries of a link list, with the linked API path as
the item id, and `tidal_open_page_link` follows one of them. `tidal_show_more_page_category` loads
the show-more or view-all page for a category. Both page generations store that follow-up endpoint
as a private `_more` record; the version-1 `show_more()` helper and the version-2 `view_all()`
helper reach the same endpoint, but `tidalapi 0.8.11`'s `view_all()` calls a `Session.view_all`
method that does not exist, so the endpoint is loaded directly for both. Pagination slices a
category before any wrapper is resolved, so a request never dereferences more items than it asked
for.

Two upstream quirks were measured against a live account and are handled locally. Personalized
Home categories advertise follow-up paths under `home/pages/...`, but that prefix is a client-side
navigation artifact: the API answers the same section only at `pages/...`, and the advertised
path returns 404 for every Home section, so the prefix is stripped before the request. A section
whose expansion currently has no items answers with an empty `rows` list, which `tidalapi`'s page
parser rejects because it reads `items` instead; that case is reported as a clear "no expandable
items right now" message rather than a generic upstream failure. `tidal_show_more_page_category`
is therefore empty-capable by design, and callers should treat "no expandable items" as a normal
outcome for a personalized section.

All list tools use explicit bounds and return pagination metadata. Objects are serialized through
a public-field allowlist; OAuth tokens, session objects, request clients, and internal attributes
cannot enter tool results.

`tidal_list_favorite_tracks`, `tidal_list_favorite_albums`, `tidal_list_favorite_artists`,
`tidal_list_favorite_playlists`, and `tidal_list_favorite_videos` report `has_more` as true when
either the over-fetched page still holds an extra item beyond `limit` or the account's exact count
for that collection places a later offset inside the collection, so neither signal can mask the
other. TIDAL's favorites endpoints omit unavailable items inside a requested window, so a page can
be short: a request for 51 items at offset 0 returned 48 items for a collection of 657. Only the
favorite-track endpoint was measured; the sibling listings share the endpoint family and were
changed by symmetry. A counted favorites page that comes back empty is still returned as a page,
with `items`, `count`, and a computed `has_more`, so a consumer must not read an empty page as the
end of a walk. `tidal_list_favorite_mixes` has no exact counter, because `tidalapi 0.8.11` exposes
none, so its cursor rests on the over-fetched page alone, clamped as described below once the
requested `limit` reaches 50. Catalog search, album tracks, and playlist items still infer
`has_more` from an over-fetched page; those endpoints were measured and did not return short
pages. The `tidalapi` playlist counter also counts playlist folders, while the favorites playlist
listing does not return folders, so for `tidal_list_favorite_playlists` the count is an upper
bound that can exceed the number of items the endpoint will ever serve.
Consumers should walk pages until `has_more` is false, accept pages containing fewer items than
`limit`, accept empty pages, and treat collection counts as upper bounds, because they include
items TIDAL declines to serve.

Pagination detects a further page by requesting one item beyond `limit`. Five operations cannot:
on `tidalapi 0.8.11` `tidal_list_favorite_playlists`, `tidal_list_favorite_mixes`,
`tidal_list_playlist_folders`, `tidal_list_public_playlists`, and
`tidal_list_playlists_and_favorites` answer a 51-item request with HTTP 400 while a 50-item
request succeeds, so for exactly those five the page itself is clamped to 50 items. The schema
admits a `limit` up to 100, but these five serve at most 50 items per page however large the
requested `limit` is: the envelope reports the clamped `limit`, not the requested one, and
`next_offset` advances by the clamped page size, so no window is skipped. No other paginated read
is clamped; every one of them still requests one item beyond `limit`. A clamped page that fills
its window reports `has_more` as true, because a full window cannot be distinguished from a
truncated one, so the last page of such a walk can come back empty. An empty page is therefore
never an end-of-walk signal on these surfaces either; `has_more` is the only authoritative one.
`tidal_list_favorite_playlists` additionally carries its exact collection counter, so its cursor
does not rely on the clamped signal alone.

## Local export

`tidal_export_playlist` is the only tool that writes to local disk, so it is annotated as not
read-only rather than pretending to be a pure read. Its bounds: the target directory is fixed by
configuration and defaults to a subdirectory of the private data directory, a caller-supplied name
is reduced to a single safe path segment, an existing file is refused rather than replaced, and the
content is written through a temporary file so a reader never sees a partial export. The export
holds public metadata and TIDAL URLs only, because the project never downloads media.

`tidal_export_analysis` writes a summary or a comparison as JSON. It computes the derived result
with the same code the read tools use and writes it through the same private, non-overwriting
writer as a playlist export, so it adds no new way to reach the filesystem. It is JSON-only: a
derived result is structured analysis, not a track list, so an M3U would carry no meaning.

`tidal_compare_playlists` matches tracks on the normalized title and artist pair rather than on
track id. TIDAL serves distinct ids for the same recording across releases, so comparing ids would
report a shared song as two different ones. Its counts are over distinct matches, so a track
duplicated inside one playlist does not inflate a result.

## Built-in prompts

Four MCP prompts are registered alongside the tools. They are guidance, not capability: every one
names read-only tools, and the prompts that reach a write stop at `tidal_preview_*` and require the
user's approval before `tidal_commit_action`. A prompt therefore cannot bypass the approval gate.

## Mutation surface

Every mutation has a named `tidal_preview_*` tool. A preview may read public target metadata and
write a private local draft, but it cannot modify TIDAL. `tidal_commit_action` accepts only an
unexpired token for the exact recorded action and payload.

| Surface | Covered actions |
| --- | --- |
| Playlists | Create, edit, delete, clear, merge, public/private visibility |
| Playlist items | Add by ID or ISRC; move by ID, index, or index list; remove by ID, index, or index list |
| Favorites | Add/remove tracks, albums, artists, playlists, videos, and mixes; add track by ISRC |
| Folders | Create, rename, delete, add items, move items to folder/root, remove collection-tree items |

Drafts are owner-only files, expire after 15 minutes by default, are atomically claimed across
processes, and cannot be replayed after an uncertain write. A successful replay is idempotent and
returns the stored result.

## Explicit non-goals

The following callable methods are intentionally not MCP tools and do not reduce the application
coverage claim:

- OAuth token loaders, refresh-token methods, and raw session serialization. Authentication stays
  in the separate interactive `tidal-auth` command so credentials never pass through MCP.
- `parse_*`, `factory`, `convert_type`, and other library implementation helpers. These transform
  Python objects and are not user-facing TIDAL operations.
- Arbitrary raw endpoint access such as `Page.get(endpoint)`. Exposing an unconstrained endpoint
  would bypass schemas and the operation allowlist.
- Manifest extraction, media downloading, DRM handling, or file conversion. The server returns
  playback metadata and TIDAL-provided temporary URLs only.
- UPnP/DLNA renderer control. It is a device-network subsystem rather than a TIDAL API surface and
  would require a separate optional plugin with independent discovery and security boundaries.
- Invented or undocumented endpoints not present in the pinned adapter.

These boundaries are deliberate: “complete” means every stable, documentable user operation in
the pinned adapter, not turning private implementation helpers into unsafe generic RPC calls.
