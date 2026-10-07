"""Deterministic fake TIDAL client used by protocol and evaluation tests."""

from __future__ import annotations

from collections.abc import Sequence

from tidal_mcp.models import (
    Album,
    Artist,
    ArtistShare,
    CatalogResult,
    CollectedTracks,
    CollectionComparison,
    CommitPlaylistResult,
    ComparisonEntry,
    MutationResult,
    Playlist,
    PlaylistPage,
    PlaylistSummary,
    SearchResponse,
    SearchType,
    Track,
    TrackPage,
)


def track(
    track_id: str,
    title: str,
    artist: str,
    *,
    artist_id: str,
    year: int,
    duration: int = 210,
    explicit: bool = False,
    seeds: list[str] | None = None,
) -> Track:
    return Track(
        id=track_id,
        title=title,
        artist=artist,
        artist_id=artist_id,
        album=f"{title} Album",
        album_id=f"album-{track_id}",
        duration_seconds=duration,
        explicit=explicit,
        release_date=f"{year}-01-01",
        url=f"https://tidal.com/browse/track/{track_id}",
        source_seed_ids=seeds or [],
    )


TRACKS = {
    "seed-1": track("seed-1", "Night Seed", "Lumen", artist_id="artist-lumen", year=2022),
    "seed-2": track("seed-2", "Dawn Seed", "Aster", artist_id="artist-aster", year=2023),
    "t-1": track("t-1", "Glass Harbor", "Northline", artist_id="artist-north", year=2021),
    "t-2": track("t-2", "Quiet Signals", "Northline", artist_id="artist-north", year=2022),
    "t-3": track("t-3", "Blue Static", "Velour", artist_id="artist-velour", year=2024),
    "t-4": track(
        "t-4",
        "Red Letters",
        "Velour",
        artist_id="artist-velour",
        year=2024,
        explicit=True,
    ),
    "t-5": track(
        "t-5",
        "Long Orbit",
        "Aster",
        artist_id="artist-aster",
        year=2018,
        duration=420,
    ),
}

PLAYLIST = Playlist(
    id="playlist-1",
    title="Evening Test",
    description="A deterministic fixture playlist.",
    creator="fixture-user",
    track_count=3,
    duration_seconds=630,
    created_at="2026-01-01T12:00:00+00:00",
    updated_at="2026-01-02T12:00:00+00:00",
    url="https://tidal.com/browse/playlist/playlist-1",
)


class FakeMusicClient:
    def __init__(self) -> None:
        self.create_calls = 0
        self.last_created: tuple[str, str, list[str]] | None = None

    def search(
        self,
        query: str,
        media_types: Sequence[SearchType],
        limit: int,
        offset: int,
    ) -> SearchResponse:
        requested = set(media_types)
        catalog = [TRACKS["t-1"], TRACKS["t-2"], TRACKS["t-3"]]
        page = catalog[offset : offset + limit]
        return SearchResponse(
            query=query,
            limit=limit,
            offset=offset,
            tracks=page if SearchType.TRACKS in requested else [],
            albums=(
                [
                    Album(
                        id="album-1",
                        title="Fixture Album",
                        artist="Northline",
                        artist_id="artist-north",
                        release_date="2022-02-02",
                        track_count=9,
                        duration_seconds=1900,
                        explicit=False,
                        url="https://tidal.com/browse/album/album-1",
                    )
                ]
                if SearchType.ALBUMS in requested
                else []
            ),
            artists=(
                [
                    Artist(
                        id="artist-north",
                        name="Northline",
                        url="https://tidal.com/browse/artist/artist-north",
                    )
                ]
                if SearchType.ARTISTS in requested
                else []
            ),
            playlists=[PLAYLIST] if SearchType.PLAYLISTS in requested else [],
            has_more=offset + limit < len(catalog),
            next_offset=offset + limit if offset + limit < len(catalog) else None,
        )

    def list_favorite_tracks(self, limit: int, offset: int) -> TrackPage:
        items = [TRACKS["t-3"], TRACKS["t-2"], TRACKS["t-1"]]
        return self._page(items, limit, offset)

    def list_playlists(self, limit: int, offset: int) -> PlaylistPage:
        items = [PLAYLIST][offset : offset + limit]
        return PlaylistPage(
            items=items,
            count=len(items),
            limit=limit,
            offset=offset,
            has_more=False,
            next_offset=None,
        )

    def get_playlist_tracks(self, playlist_id: str, limit: int, offset: int) -> TrackPage:
        items = [TRACKS["t-1"], TRACKS["t-2"], TRACKS["t-3"]]
        return self._page(items, limit, offset)

    def collect_playlist_tracks(self, playlist_id: str, max_items: int) -> CollectedTracks:
        del playlist_id
        items = [TRACKS["t-1"], TRACKS["t-2"], TRACKS["t-3"]][:max_items]
        return CollectedTracks(
            playlist_id="playlist-1",
            items=items,
            count=len(items),
            max_items=max_items,
            truncated=False,
            pages_fetched=1,
        )

    def summarize_playlist(
        self, playlist_id: str, max_items: int, top_artists: int
    ) -> PlaylistSummary:
        del playlist_id, max_items
        return PlaylistSummary(
            playlist_id="playlist-1",
            title=PLAYLIST.title,
            tracks_analyzed=3,
            max_items=10,
            truncated=False,
            total_duration_seconds=630,
            distinct_artists=2,
            top_artists=[ArtistShare(artist="Northline", track_count=2)][:top_artists],
            decade_counts={"2020s": 3},
            explicit_tracks=0,
            tracks_without_release_date=0,
            duplicate_tracks=[],
        )

    def collect_playlist_for_export(self, playlist_id: str, max_items: int):
        return "Fixture Playlist", self.collect_playlist_tracks(playlist_id, max_items)

    def compare_playlists(
        self, left_playlist_id: str, right_playlist_id: str, max_items: int
    ) -> CollectionComparison:
        del max_items
        return CollectionComparison(
            left_playlist_id=left_playlist_id,
            right_playlist_id=right_playlist_id,
            left_title="Left",
            right_title="Right",
            left_track_count=2,
            right_track_count=1,
            max_items=500,
            truncated=False,
            shared_count=1,
            left_only_count=1,
            right_only_count=0,
            shared=[ComparisonEntry(title="Shared", artist="Band", left_track_ids=["1"])],
            left_only=[ComparisonEntry(title="Left Only", artist="A", left_track_ids=["2"])],
            right_only=[],
        )

    def playlist_title(self, playlist_id: str) -> str:
        del playlist_id
        return "Fixture Playlist"

    def get_track_radio(self, track_id: str, limit: int) -> list[Track]:
        radios = {
            "seed-1": [
                TRACKS["t-1"].model_copy(update={"source_seed_ids": ["seed-1"]}),
                TRACKS["t-2"].model_copy(update={"source_seed_ids": ["seed-1"]}),
                TRACKS["t-4"].model_copy(update={"source_seed_ids": ["seed-1"]}),
            ],
            "seed-2": [
                TRACKS["t-1"].model_copy(update={"source_seed_ids": ["seed-2"]}),
                TRACKS["t-3"].model_copy(update={"source_seed_ids": ["seed-2"]}),
                TRACKS["t-5"].model_copy(update={"source_seed_ids": ["seed-2"]}),
            ],
        }
        return radios.get(track_id, [])[:limit]

    def resolve_tracks(self, track_ids: Sequence[str]) -> list[Track]:
        return [TRACKS[item] for item in track_ids]

    def create_playlist(
        self,
        title: str,
        description: str,
        track_ids: Sequence[str],
    ) -> CommitPlaylistResult:
        self.create_calls += 1
        self.last_created = (title, description, list(track_ids))
        created = PLAYLIST.model_copy(
            update={
                "id": "created-1",
                "title": title,
                "description": description,
                "track_count": len(track_ids),
                "url": "https://tidal.com/browse/playlist/created-1",
            }
        )
        return CommitPlaylistResult(
            status="success",
            message=f"Created playlist {title!r}.",
            playlist=created,
            tracks_requested=len(track_ids),
            tracks_added=len(track_ids),
        )

    def execute_read(self, operation: str, params: dict[str, object]) -> CatalogResult:
        return CatalogResult(
            operation=operation,
            value={"received": params},
        )

    def preview_mutation(self, action: str, payload: dict[str, object]) -> dict[str, object]:
        preview: dict[str, object] = {"action": action, "parameters": payload}
        if action == "create_playlist":
            preview["tracks"] = [
                TRACKS[track_id].model_dump() for track_id in payload.get("track_ids", [])
            ]
        return preview

    def execute_mutation(self, action: str, payload: dict[str, object]) -> MutationResult:
        self.create_calls += 1
        if action == "create_playlist":
            track_ids = list(payload.get("track_ids", []))
            self.last_created = (
                str(payload["title"]),
                str(payload.get("description", "")),
                track_ids,
            )
        return MutationResult(
            status="success",
            action=action,
            message=f"Committed {action}.",
            affected_ids=["fixture-target"],
            details={"payload": payload},
        )

    @staticmethod
    def _page(items: list[Track], limit: int, offset: int) -> TrackPage:
        page = items[offset : offset + limit]
        has_more = offset + limit < len(items)
        return TrackPage(
            items=page,
            count=len(page),
            limit=limit,
            offset=offset,
            has_more=has_more,
            next_offset=offset + limit if has_more else None,
        )
