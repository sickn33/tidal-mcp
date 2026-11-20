"""Saved-track search and playlist discovery over bounded, read-only TIDAL operations."""

from __future__ import annotations

import unicodedata

from tidal_mcp.client import MusicClient
from tidal_mcp.exceptions import TidalClientError, TrackRadioUnavailableError
from tidal_mcp.filtering import filter_recommendations, recording_code
from tidal_mcp.models import (
    AppliedRecommendationFilters,
    FavoriteTrackSearch,
    PlaylistRecommendations,
    RecommendationFilters,
    RecommendationResponse,
    Track,
)


def _search_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def search_favorite_tracks(
    client: MusicClient, query: str, scan_limit: int, offset: int
) -> FavoriteTrackSearch:
    terms = _search_text(query).split()
    if not terms:
        raise TidalClientError("Provide a title, artist, or album to search for.")
    page = client.favorite_track_window(scan_limit, offset)
    matches = []
    for track in page.items:
        text = _search_text(f"{track.title} {track.artist} {track.album or ''}")
        if all(term in text for term in terms):
            matches.append(track)
    return FavoriteTrackSearch(
        query=query,
        items=matches,
        count=len(matches),
        scanned_count=page.count,
        limit=scan_limit,
        offset=offset,
        has_more=page.has_more,
        next_offset=page.next_offset,
    )


def _radio_candidates(
    client: MusicClient, seed_ids: list[str], limit: int, *, skip_unavailable: bool
) -> tuple[list[Track], list[str]]:
    by_id: dict[str, Track] = {}
    unavailable = []
    for seed_id in dict.fromkeys(seed_ids):
        try:
            radio = client.get_track_radio(seed_id, limit)
        except TrackRadioUnavailableError:
            if not skip_unavailable:
                raise
            unavailable.append(seed_id)
            continue
        for track in radio:
            existing = by_id.get(track.id)
            if existing is None:
                by_id[track.id] = track
            else:
                sources = dict.fromkeys([*existing.source_seed_ids, *track.source_seed_ids])
                by_id[track.id] = existing.model_copy(update={"source_seed_ids": list(sources)})
    return list(by_id.values()), unavailable


def _applied_filters(
    filters: RecommendationFilters | None, seed_ids: list[str]
) -> AppliedRecommendationFilters:
    requested = filters or RecommendationFilters()
    exclusions = list(dict.fromkeys([*requested.exclude_track_ids, *seed_ids]))
    return AppliedRecommendationFilters(
        **(requested.model_dump() | {"exclude_track_ids": exclusions})
    )


def recommend_tracks(
    client: MusicClient,
    seed_ids: list[str],
    limit_per_seed: int,
    max_results: int,
    filters: RecommendationFilters | None,
) -> RecommendationResponse:
    applied = _applied_filters(filters, seed_ids)
    candidates, _ = _radio_candidates(client, seed_ids, limit_per_seed, skip_unavailable=False)
    accepted, _ = filter_recommendations(candidates, applied)
    returned = accepted[:max_results]
    return RecommendationResponse(
        seed_track_ids=seed_ids,
        items=returned,
        candidate_count=len(candidates),
        returned_count=len(returned),
        filtered_out_count=len(candidates) - len(returned),
        filters=applied,
    )


def recommend_for_playlist(
    client: MusicClient,
    playlist_id: str,
    max_playlist_tracks: int,
    seed_count: int,
    limit_per_seed: int,
    max_results: int,
    filters: RecommendationFilters | None,
) -> PlaylistRecommendations:
    tracks = client.complete_playlist_tracks(playlist_id, max_playlist_tracks)
    playlist_ids = dict.fromkeys(track.id for track in tracks)
    playlist_codes = {code for track in tracks if (code := recording_code(track))}

    ordered_ids = list(playlist_ids)
    count = min(seed_count, len(ordered_ids))
    # Include both ends of the playlist when there are at least two seeds.
    seeds = [ordered_ids[i * (len(ordered_ids) - 1) // max(1, count - 1)] for i in range(count)]
    candidates, unavailable = _radio_candidates(
        client, seeds, limit_per_seed, skip_unavailable=True
    )
    new = [
        track
        for track in candidates
        if track.id not in playlist_ids and recording_code(track) not in playlist_codes
    ]
    applied = _applied_filters(filters, seeds)
    accepted, _ = filter_recommendations(new, applied, distinct_recordings=True)
    returned = accepted[:max_results]
    return PlaylistRecommendations(
        playlist_id=playlist_id,
        playlist_tracks_checked=len(tracks),
        seed_track_ids=seeds,
        unavailable_seed_ids=unavailable,
        items=returned,
        candidate_count=len(candidates),
        already_in_playlist_count=len(candidates) - len(new),
        returned_count=len(returned),
        filtered_out_count=len(candidates) - len(returned),
        filters=applied,
    )
