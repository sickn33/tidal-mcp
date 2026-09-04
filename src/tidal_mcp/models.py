"""Validated input and output models exposed by the MCP tools."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SearchType(StrEnum):
    TRACKS = "tracks"
    ALBUMS = "albums"
    ARTISTS = "artists"
    PLAYLISTS = "playlists"


class Track(StrictModel):
    id: str = Field(description="TIDAL track identifier.")
    title: str
    artist: str
    artist_id: str | None = None
    album: str | None = None
    album_id: str | None = None
    duration_seconds: int | None = Field(default=None, ge=0)
    explicit: bool | None = None
    release_date: str | None = None
    url: str
    source_seed_ids: list[str] = Field(default_factory=list)


class Album(StrictModel):
    id: str
    title: str
    artist: str | None = None
    artist_id: str | None = None
    release_date: str | None = None
    track_count: int | None = Field(default=None, ge=0)
    duration_seconds: int | None = Field(default=None, ge=0)
    explicit: bool | None = None
    url: str


class Artist(StrictModel):
    id: str
    name: str
    url: str


class Playlist(StrictModel):
    id: str
    title: str
    description: str | None = None
    creator: str | None = None
    track_count: int | None = Field(default=None, ge=0)
    duration_seconds: int | None = Field(default=None, ge=0)
    created_at: str | None = None
    updated_at: str | None = None
    url: str


class AuthStatus(StrictModel):
    authenticated: bool
    message: str
    session_file: str
    user_id: str | None = None
    username: str | None = None
    login_command: str


class TrackPage(StrictModel):
    items: list[Track]
    count: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    has_more: bool
    next_offset: int | None = Field(default=None, ge=0)


class PlaylistPage(StrictModel):
    items: list[Playlist]
    count: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    has_more: bool
    next_offset: int | None = Field(default=None, ge=0)


class SearchResponse(StrictModel):
    query: str
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    tracks: list[Track] = Field(default_factory=list)
    albums: list[Album] = Field(default_factory=list)
    artists: list[Artist] = Field(default_factory=list)
    playlists: list[Playlist] = Field(default_factory=list)
    has_more: bool
    next_offset: int | None = Field(default=None, ge=0)


class RecommendationFilters(StrictModel):
    release_year_min: int | None = Field(default=None, ge=1900, le=2200)
    release_year_max: int | None = Field(default=None, ge=1900, le=2200)
    duration_seconds_min: int | None = Field(default=None, ge=0, le=7200)
    duration_seconds_max: int | None = Field(default=None, ge=1, le=7200)
    explicit: bool | None = Field(
        default=None,
        description="When set, retain only tracks matching this explicit-content flag.",
    )
    max_tracks_per_artist: int = Field(default=2, ge=1, le=20)
    exclude_track_ids: list[str] = Field(default_factory=list, max_length=200)

    @model_validator(mode="after")
    def validate_ranges(self) -> RecommendationFilters:
        if (
            self.release_year_min is not None
            and self.release_year_max is not None
            and self.release_year_min > self.release_year_max
        ):
            raise ValueError("release_year_min cannot exceed release_year_max")
        if (
            self.duration_seconds_min is not None
            and self.duration_seconds_max is not None
            and self.duration_seconds_min > self.duration_seconds_max
        ):
            raise ValueError("duration_seconds_min cannot exceed duration_seconds_max")
        return self


class RecommendationResponse(StrictModel):
    seed_track_ids: list[str]
    items: list[Track]
    candidate_count: int = Field(ge=0)
    returned_count: int = Field(ge=0)
    filtered_out_count: int = Field(ge=0)
    filters: RecommendationFilters


class CommitPlaylistResult(StrictModel):
    status: Literal["success", "partial"]
    message: str
    playlist: Playlist
    tracks_requested: int = Field(ge=0)
    tracks_added: int = Field(ge=0)
    warning: str | None = None


class PublicItem(StrictModel):
    """A stable, credential-free representation of any TIDAL catalog object."""

    type: str
    id: str | None = None
    title: str | None = None
    name: str | None = None
    url: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class CatalogResult(StrictModel):
    """Uniform result envelope used by the extended catalog and library tools."""

    operation: str
    item: PublicItem | None = None
    items: list[PublicItem] = Field(default_factory=list)
    text: str | None = None
    value: Any | None = None
    count: int = Field(default=0, ge=0)
    limit: int | None = Field(default=None, ge=1)
    offset: int | None = Field(default=None, ge=0)
    has_more: bool = False
    next_offset: int | None = Field(default=None, ge=0)
    warnings: list[str] = Field(default_factory=list)


class ActionDraft(StrictModel):
    """Exact, short-lived preview for one remote mutation."""

    approval_token: str
    action: str
    payload: dict[str, Any]
    preview: dict[str, Any]
    created_at: str
    expires_at: str
    writes_enabled: bool
    destructive: bool
    next_step: str


class MutationResult(StrictModel):
    """Stable result returned after committing an approved mutation."""

    status: Literal["success", "partial"]
    action: str
    message: str
    affected_ids: list[str] = Field(default_factory=list)
    item: PublicItem | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    warning: str | None = None


class ActionDraftRecord(StrictModel):
    approval_token: str
    action: str
    payload: dict[str, Any]
    preview: dict[str, Any]
    destructive: bool
    created_at: str
    expires_at: str
    state: Literal["pending", "committing", "committed", "failed"] = "pending"
    result: MutationResult | None = None
    failure_message: str | None = None
