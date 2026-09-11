# API coverage contract

This document defines what “complete” means for TIDAL MCP 1.0. The supported adapter is
`tidalapi 0.8.11`; the executable source of truth is `src/tidal_mcp/catalog.py` plus the six
handwritten workflow tools in `src/tidal_mcp/server.py`.

## Coverage result

- 112 MCP tools with input and output schemas.
- 74 read-only tools.
- 36 exact local mutation-preview tools.
- 2 approval-token commit tools.
- 100% statement and branch test coverage, enforced by `fail_under = 100`.
- 100% coverage of stable, user-facing `tidalapi 0.8.11` operations that can be represented
  safely as catalog, library, playlist, folder, editorial, recommendation, or playback-metadata
  workflows.

## Read surface

| TIDAL surface | MCP coverage |
| --- | --- |
| Session/account | Authentication status; current or public user lookup; user image |
| Search and identifiers | Multi-type search; track, album, artist, playlist, video, mix, user; barcode and ISRC lookup |
| Tracks | Metadata, radio tracks, radio mix, lyrics, playback metadata, temporary playback URL |
| Albums | Metadata, tracks, mixed items, review, similar albums, audio resolutions, cover/video art, page |
| Artists | Metadata, albums, EPs/singles, other appearances, bio, radio, radio mix, related artists, top tracks, videos, image, page |
| Videos | Metadata, image, temporary playback URL |
| Playlists | Metadata, paginated tracks/items, item and track counts, square/wide images |
| Collection | Favorite tracks, albums, artists, playlists, videos, mixes, folders, aggregate counts |
| User playlists | Owned, public, and combined owned/favorite views |
| Mixes | Legacy and v2 metadata/images plus paginated mix items |
| Discovery pages | Home, Explore, For You, genre hubs, hi-res, local genres, mixes, moods, videos |
| Genres | Complete genre list and paginated tracks, albums, artists, playlists, or videos by genre |
| Folders | Folder metadata and paginated contents |
| Recommendations | Multi-seed Track Radio, deduplication, provenance, deterministic metadata filters |

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
