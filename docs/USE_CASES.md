# TIDAL MCP use cases and prompt cookbook

These examples show workflows an MCP-capable assistant can compose from the server's typed tools.
Read workflows can run immediately after authentication. Write workflows must stop at the preview
until the user approves the exact change.

## Analyze a playlist

> Analyze my playlist “Road Trip”. Read every page, reconcile its track and item counts, then
> report duration, top artists and albums, release-year distribution, explicit tracks, duplicate
> candidates, and ordering patterns. Do not modify anything.

Useful tools include `tidal_list_playlists`, `tidal_get_playlist`,
`tidal_get_playlist_track_count`, `tidal_get_playlist_item_count`,
`tidal_get_playlist_tracks`, and `tidal_get_playlist_items`.

## Build constrained recommendations

> Use three representative tracks from my playlist as seeds. Find 25 recommendations, exclude
> tracks already present, allow at most two tracks per artist, and keep only non-explicit releases
> from 2020 onward. Explain which rules removed candidates.

`tidal_recommend_tracks` performs deterministic metadata filtering and retains seed provenance.
Mood, energy, tempo, and acoustic character should be described as model inference unless returned
by a specific upstream field.

## Create a playlist safely

> Prepare a playlist called “Late Night Discovery” from these ordered track IDs. Show its title,
> description, order, resolved tracks, expiry, and write status. Do not commit until I approve.

The assistant first calls `tidal_preview_create_playlist`. After the user approves the exact
preview, it can pass the returned token to `tidal_commit_action`.

## Audit a music collection

> Summarize my favorite track, album, artist, playlist, video, mix, and folder counts. Sample each
> collection with pagination and identify where the catalog is concentrated.

The server exposes dedicated favorite-list and aggregate-count tools rather than requiring raw
endpoint access.

## Explore an artist deeply

> Find the exact artist, then compare main albums, EPs and singles, other appearances, top tracks,
> videos, biography, radio, radio mix, and related artists. Keep TIDAL facts separate from your
> interpretation.

Exact IDs should be carried between calls to avoid ambiguity between artists with similar names.

## Compare editions of a release

> Resolve this barcode and list every matching album edition. Compare release dates, track counts,
> duration, explicit flag, audio resolutions, and TIDAL URLs.

The same approach works with ISRCs for multiple recordings or catalog editions of a track.

## Inspect lyrics responsibly

> Retrieve the lyrics metadata for this track, tell me whether synchronized subtitles exist, and
> summarize the theme without reproducing substantial copyrighted text.

The tool can expose the available lyrics response; the client remains responsible for appropriate
copyright handling.

## Organize playlist folders

> List my playlist folders and their contents. Prepare a move of these exact playlists into the
> “Training” folder. Show the targets and destructive flag before asking me to approve.

Folder creation, rename, deletion, insertion, movement, and removal use the same preview-token
commit boundary as playlist writes.

## Detect stale or surprising metadata

> Compare the playlist object's reported track count with the dedicated track count, total item
> count, and all paginated pages. Explain any discrepancy and state which values are directly
> observed.

This workflow helps distinguish cached metadata from pagination bugs or mixed track/video content.
