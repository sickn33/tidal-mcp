"""Thin, typed adapter around the unofficial tidalapi package."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Any, NoReturn, Protocol

import requests
import tidalapi
import tidalapi.types as tidal_types

from tidal_mcp.exceptions import (
    AuthenticationRequiredError,
    PartialPlaylistCreationError,
    TidalClientError,
    TidalMCPError,
)
from tidal_mcp.formatting import (
    format_album,
    format_artist,
    format_catalog_result,
    format_playlist,
    format_track,
    public_item,
)
from tidal_mcp.models import (
    AuthStatus,
    CatalogResult,
    CommitPlaylistResult,
    MutationResult,
    PlaylistPage,
    SearchResponse,
    SearchType,
    Track,
    TrackPage,
)

LOGGER = logging.getLogger(__name__)


class MusicClient(Protocol):
    def search(
        self,
        query: str,
        media_types: Sequence[SearchType],
        limit: int,
        offset: int,
    ) -> SearchResponse: ...

    def list_favorite_tracks(self, limit: int, offset: int) -> TrackPage: ...

    def list_playlists(self, limit: int, offset: int) -> PlaylistPage: ...

    def get_playlist_tracks(self, playlist_id: str, limit: int, offset: int) -> TrackPage: ...

    def get_track_radio(self, track_id: str, limit: int) -> list[Track]: ...

    def resolve_tracks(self, track_ids: Sequence[str]) -> list[Track]: ...

    def create_playlist(
        self,
        title: str,
        description: str,
        track_ids: Sequence[str],
    ) -> CommitPlaylistResult: ...

    def execute_read(self, operation: str, params: dict[str, Any]) -> CatalogResult: ...

    def preview_mutation(self, action: str, payload: dict[str, Any]) -> dict[str, Any]: ...

    def execute_mutation(self, action: str, payload: dict[str, Any]) -> MutationResult: ...


def _sequence(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    try:
        return list(value)
    except TypeError:
        return []


def _search_bucket(result: Any, name: str) -> list[Any]:
    value = result.get(name) if isinstance(result, dict) else getattr(result, name, None)
    if hasattr(value, "items") and not isinstance(value, dict):
        value = value.items
    if isinstance(value, dict):
        value = value.get("items", [])
    return _sequence(value)


class TidalClient:
    """Authenticated TIDAL operations with stable model conversion."""

    def __init__(self, session: tidalapi.Session) -> None:
        self.session = session

    @classmethod
    def from_session_file(cls, session_file: Path) -> TidalClient:
        if not session_file.exists():
            raise AuthenticationRequiredError(
                "No TIDAL session exists. Run the `tidal-auth` command first."
            )
        session = tidalapi.Session()
        try:
            session.load_session_from_file(session_file)
        except requests.RequestException as exc:
            LOGGER.info("Could not reach TIDAL while loading the session (%s)", type(exc).__name__)
            raise TidalClientError(
                "TIDAL could not restore the saved session because the network request failed. "
                "Check connectivity and try again; the local session file was not changed."
            ) from exc
        except Exception as exc:
            LOGGER.info("Could not load the TIDAL session (%s)", type(exc).__name__)
            raise AuthenticationRequiredError(
                "The TIDAL session is unreadable. Run `tidal-auth` again."
            ) from exc
        try:
            authenticated = session.check_login()
        except Exception as exc:
            LOGGER.info("Could not validate the TIDAL session (%s)", type(exc).__name__)
            raise TidalClientError(
                "TIDAL could not validate the saved session. Check network access and try again; "
                "do not re-authenticate unless TIDAL reports that the session expired."
            ) from exc
        if not authenticated:
            raise AuthenticationRequiredError(
                "The TIDAL session expired. Run the `tidal-auth` command again."
            )
        return cls(session)

    @staticmethod
    def authentication_status(session_file: Path, login_command: str) -> AuthStatus:
        if not session_file.exists():
            return AuthStatus(
                authenticated=False,
                message="No local TIDAL session found.",
                session_file=str(session_file),
                login_command=login_command,
            )
        try:
            client = TidalClient.from_session_file(session_file)
            user = client.session.user
            return AuthStatus(
                authenticated=True,
                message="The local TIDAL session is valid.",
                session_file=str(session_file),
                user_id=str(getattr(user, "id", "")) or None,
                username=(
                    str(user.username) if getattr(user, "username", None) is not None else None
                ),
                login_command=login_command,
            )
        except TidalMCPError as exc:
            return AuthStatus(
                authenticated=False,
                message=str(exc),
                session_file=str(session_file),
                login_command=login_command,
            )

    def search(
        self,
        query: str,
        media_types: Sequence[SearchType],
        limit: int,
        offset: int,
    ) -> SearchResponse:
        try:
            result = self.session.search(query, limit=limit + 1, offset=offset)
            requested = set(media_types)
            tracks = (
                [format_track(item) for item in _search_bucket(result, "tracks")]
                if SearchType.TRACKS in requested
                else []
            )
            albums = (
                [format_album(item) for item in _search_bucket(result, "albums")]
                if SearchType.ALBUMS in requested
                else []
            )
            artists = (
                [format_artist(item) for item in _search_bucket(result, "artists")]
                if SearchType.ARTISTS in requested
                else []
            )
            playlists = (
                [format_playlist(item) for item in _search_bucket(result, "playlists")]
                if SearchType.PLAYLISTS in requested
                else []
            )
        except Exception as exc:
            self._raise_operation_error("search the catalog", exc)

        has_more = any(len(items) > limit for items in (tracks, albums, artists, playlists))
        return SearchResponse(
            query=query,
            limit=limit,
            offset=offset,
            tracks=tracks[:limit],
            albums=albums[:limit],
            artists=artists[:limit],
            playlists=playlists[:limit],
            has_more=has_more,
            next_offset=offset + limit if has_more else None,
        )

    def list_favorite_tracks(self, limit: int, offset: int) -> TrackPage:
        try:
            favorites = self.session.user.favorites
            try:
                items = favorites.tracks(
                    limit=limit + 1,
                    offset=offset,
                    order=tidal_types.ItemOrder.Date,
                    order_direction=tidal_types.OrderDirection.Descending,
                )
            except (AttributeError, TypeError):
                items = favorites.tracks(
                    limit=limit + 1,
                    offset=offset,
                    order="DATE",
                    order_direction="DESC",
                )
            tracks = [format_track(item) for item in items]
            total = self._favorites_total(favorites)
        except Exception as exc:
            self._raise_operation_error("list favorite tracks", exc)
        return self._track_page(tracks, limit, offset, total=total)

    def list_playlists(self, limit: int, offset: int) -> PlaylistPage:
        try:
            try:
                items = self.session.user.playlists(limit=limit + 1, offset=offset)
            except TypeError:
                items = list(self.session.user.playlists())[offset : offset + limit + 1]
            playlists = [format_playlist(item) for item in items]
        except Exception as exc:
            self._raise_operation_error("list playlists", exc)
        has_more = len(playlists) > limit
        return PlaylistPage(
            items=playlists[:limit],
            count=min(len(playlists), limit),
            limit=limit,
            offset=offset,
            has_more=has_more,
            next_offset=offset + limit if has_more else None,
        )

    def get_playlist_tracks(self, playlist_id: str, limit: int, offset: int) -> TrackPage:
        try:
            playlist = self.session.playlist(playlist_id)
            try:
                items = playlist.tracks(limit=limit + 1, offset=offset)
            except AttributeError:
                items = playlist.items(limit=limit + 1, offset=offset)
            tracks = [format_track(item) for item in items]
        except Exception as exc:
            self._raise_operation_error("read that playlist", exc)
        return self._track_page(tracks, limit, offset)

    def get_track_radio(self, track_id: str, limit: int) -> list[Track]:
        try:
            track = self.session.track(track_id)
            return [
                format_track(item, source_seed_ids=[track_id])
                for item in track.get_track_radio(limit=limit)
            ]
        except Exception as exc:
            self._raise_operation_error(f"get radio recommendations for track {track_id}", exc)

    def resolve_tracks(self, track_ids: Sequence[str]) -> list[Track]:
        resolved: list[Track] = []
        for track_id in track_ids:
            try:
                resolved.append(format_track(self.session.track(track_id)))
            except Exception as exc:
                self._raise_operation_error(f"resolve track {track_id}", exc)
        return resolved

    def create_playlist(
        self,
        title: str,
        description: str,
        track_ids: Sequence[str],
    ) -> CommitPlaylistResult:
        try:
            playlist_object = self.session.user.create_playlist(title, description)
        except Exception as exc:
            self._raise_operation_error("create the playlist", exc)

        try:
            add_result = playlist_object.add(list(track_ids)) if track_ids else []
            if isinstance(add_result, list):
                added_count = len(add_result)
            elif add_result is False:
                added_count = 0
            else:
                added_count = len(track_ids)
            try:
                playlist_object = self.session.playlist(playlist_object.id)
            except Exception:
                LOGGER.info("Could not refresh the newly-created playlist", exc_info=True)
            result = CommitPlaylistResult(
                status="success" if added_count == len(track_ids) else "partial",
                message=(
                    f"Created playlist {title!r} and added {added_count} of "
                    f"{len(track_ids)} requested tracks."
                ),
                playlist=format_playlist(playlist_object),
                tracks_requested=len(track_ids),
                tracks_added=added_count,
                warning=(
                    None
                    if added_count == len(track_ids)
                    else "TIDAL skipped one or more requested tracks."
                ),
            )
        except Exception as exc:
            LOGGER.info(
                "Playlist created but tracks could not be added (%s)",
                type(exc).__name__,
            )
            result = CommitPlaylistResult(
                status="partial",
                message=(f"Created playlist {title!r}, but TIDAL failed while adding its tracks."),
                playlist=format_playlist(playlist_object),
                tracks_requested=len(track_ids),
                tracks_added=0,
                warning=(
                    "The playlist exists. Inspect it before attempting another create operation."
                ),
            )
            raise PartialPlaylistCreationError(result) from exc
        return result

    @staticmethod
    def _slice(items: Sequence[Any], limit: int, offset: int) -> list[Any]:
        return list(items)[offset : offset + limit + 1]

    @staticmethod
    def _enum_value(enum_type: Any, value: str | None) -> Any:
        if value is None:
            return None
        return next(member for member in enum_type if member.value == value)

    def _ordered(
        self,
        method: Any,
        params: dict[str, Any],
        order_type: Any,
    ) -> list[Any]:
        return list(
            method(
                limit=params["limit"] + 1,
                offset=params["offset"],
                order=self._enum_value(order_type, params.get("order")),
                order_direction=self._enum_value(
                    tidal_types.OrderDirection,
                    params.get("order_direction"),
                ),
            )
        )

    def _genre_items(self, params: dict[str, Any]) -> list[Any]:
        genre = next(
            item for item in self.session.genre.get_genres() if item.path == params["genre_path"]
        )
        model = {
            "tracks": tidalapi.media.Track,
            "albums": tidalapi.album.Album,
            "artists": tidalapi.artist.Artist,
            "playlists": tidalapi.playlist.Playlist,
            "videos": tidalapi.media.Video,
        }[params["kind"]]
        return self._slice(genre.items(model), params["limit"], params["offset"])

    def execute_read(self, operation: str, params: dict[str, Any]) -> CatalogResult:
        """Execute one allowlisted read operation and return a stable public envelope."""
        p = params
        s = self.session
        favorites = s.user.favorites

        def page(values: Sequence[Any]) -> list[Any]:
            return self._slice(values, p["limit"], p["offset"])

        handlers = {
            "tidal_get_track": lambda: s.track(p["track_id"], with_album=p["with_album"]),
            "tidal_get_album": lambda: s.album(p["album_id"]),
            "tidal_get_artist": lambda: s.artist(p["artist_id"]),
            "tidal_get_playlist": lambda: s.playlist(p["playlist_id"]),
            "tidal_get_video": lambda: s.video(p["video_id"]),
            "tidal_get_mix": lambda: s.mix(p["mix_id"]),
            "tidal_get_mix_v2": lambda: s.mixv2(p["mix_id"]),
            "tidal_get_user": lambda: s.get_user(p["user_id"]),
            "tidal_get_albums_by_barcode": lambda: page(s.get_albums_by_barcode(p["barcode"])),
            "tidal_get_tracks_by_isrc": lambda: page(s.get_tracks_by_isrc(p["isrc"])),
            "tidal_get_track_radio": lambda: s.track(p["track_id"]).get_track_radio(
                limit=p["limit"] + 1
            ),
            "tidal_get_track_radio_mix": lambda: s.track(p["track_id"]).get_radio_mix(),
            "tidal_get_track_lyrics": lambda: s.track(p["track_id"]).lyrics(),
            "tidal_get_track_playback_info": lambda: s.track(p["track_id"]).get_stream(),
            "tidal_get_track_audio_resolution": lambda: (
                s.track(p["track_id"]).get_stream().get_audio_resolution()
            ),
            "tidal_get_track_url": lambda: s.track(p["track_id"]).get_url(),
            "tidal_get_video_url": lambda: s.video(p["video_id"]).get_url(),
            "tidal_get_video_image": lambda: s.video(p["video_id"]).image(p["width"], p["height"]),
            "tidal_get_album_tracks": lambda: s.album(p["album_id"]).tracks(
                limit=p["limit"] + 1,
                offset=p["offset"],
                sparse_album=p["sparse_album"],
            ),
            "tidal_get_album_items": lambda: s.album(p["album_id"]).items(
                limit=p["limit"] + 1,
                offset=p["offset"],
                sparse_album=p["sparse_album"],
            ),
            "tidal_get_album_review": lambda: s.album(p["album_id"]).review(),
            "tidal_get_album_similar": lambda: page(s.album(p["album_id"]).similar()),
            "tidal_get_album_audio_resolution": lambda: s.album(p["album_id"]).get_audio_resolution(
                p["individual_tracks"]
            ),
            "tidal_get_album_image": lambda: s.album(p["album_id"]).image(p["dimensions"]),
            "tidal_get_album_video": lambda: s.album(p["album_id"]).video(p["dimensions"]),
            "tidal_get_album_page": lambda: s.album(p["album_id"]).page(),
            "tidal_get_artist_albums": lambda: s.artist(p["artist_id"]).get_albums(
                limit=p["limit"] + 1, offset=p["offset"]
            ),
            "tidal_get_artist_ep_singles": lambda: s.artist(p["artist_id"]).get_albums_ep_singles(
                limit=p["limit"] + 1, offset=p["offset"]
            ),
            "tidal_get_artist_other_albums": lambda: s.artist(p["artist_id"]).get_albums_other(
                limit=p["limit"] + 1, offset=p["offset"]
            ),
            "tidal_get_artist_bio": lambda: s.artist(p["artist_id"]).get_bio(),
            "tidal_get_artist_radio": lambda: page(s.artist(p["artist_id"]).get_radio()),
            "tidal_get_artist_radio_mix": lambda: s.artist(p["artist_id"]).get_radio_mix(),
            "tidal_get_artist_similar": lambda: page(s.artist(p["artist_id"]).get_similar()),
            "tidal_get_artist_top_tracks": lambda: s.artist(p["artist_id"]).get_top_tracks(
                limit=p["limit"] + 1, offset=p["offset"]
            ),
            "tidal_get_artist_videos": lambda: s.artist(p["artist_id"]).get_videos(
                limit=p["limit"] + 1, offset=p["offset"]
            ),
            "tidal_get_artist_image": lambda: s.artist(p["artist_id"]).image(p["dimensions"]),
            "tidal_get_artist_page": lambda: s.artist(p["artist_id"]).page(),
            "tidal_get_playlist_items": lambda: self._ordered(
                s.playlist(p["playlist_id"]).items, p, tidal_types.ItemOrder
            ),
            "tidal_get_playlist_track_count": lambda: s.playlist(
                p["playlist_id"]
            ).get_tracks_count(),
            "tidal_get_playlist_item_count": lambda: s.playlist(p["playlist_id"]).get_items_count(),
            "tidal_get_playlist_image": lambda: s.playlist(p["playlist_id"]).image(p["dimensions"]),
            "tidal_get_playlist_wide_image": lambda: s.playlist(p["playlist_id"]).wide_image(
                p["width"], p["height"]
            ),
            "tidal_list_favorite_albums": lambda: self._ordered(
                favorites.albums, p, tidal_types.AlbumOrder
            ),
            "tidal_list_favorite_artists": lambda: self._ordered(
                favorites.artists, p, tidal_types.ArtistOrder
            ),
            "tidal_list_favorite_playlists": lambda: self._ordered(
                favorites.playlists, p, tidal_types.PlaylistOrder
            ),
            "tidal_list_favorite_videos": lambda: self._ordered(
                favorites.videos, p, tidal_types.VideoOrder
            ),
            "tidal_list_favorite_mixes": lambda: self._ordered(
                favorites.mixes, p, tidal_types.MixOrder
            ),
            "tidal_list_playlist_folders": lambda: favorites.playlist_folders(
                limit=p["limit"] + 1,
                offset=p["offset"],
                order=self._enum_value(tidal_types.PlaylistOrder, p.get("order")),
                order_direction=self._enum_value(
                    tidal_types.OrderDirection, p.get("order_direction")
                ),
                parent_folder_id=p["parent_folder_id"],
            ),
            "tidal_get_favorite_counts": lambda: {
                "tracks": favorites.get_tracks_count(),
                "albums": favorites.get_albums_count(),
                "artists": favorites.get_artists_count(),
                "playlists": favorites.get_playlists_count(),
                "videos": favorites.get_videos_count(),
            },
            "tidal_list_public_playlists": lambda: s.user.public_playlists(
                offset=p["offset"], limit=p["limit"] + 1
            ),
            "tidal_list_playlists_and_favorites": lambda: s.user.playlist_and_favorite_playlists(
                offset=p["offset"], limit=p["limit"] + 1
            ),
            "tidal_get_user_image": lambda: s.user.image(p["dimensions"]),
            "tidal_get_mix_items": lambda: page(s.mix(p["mix_id"]).items()),
            "tidal_get_mix_image": lambda: s.mix(p["mix_id"]).image(p["dimensions"]),
            "tidal_get_mix_v2_image": lambda: s.mixv2(p["mix_id"]).image(p["dimensions"]),
            "tidal_browse_home": lambda: s.home(),
            "tidal_browse_explore": lambda: s.explore(),
            "tidal_browse_for_you": lambda: s.for_you(),
            "tidal_browse_genres": lambda: s.genres(),
            "tidal_browse_hires": lambda: s.hires_page(),
            "tidal_browse_local_genres": lambda: s.local_genres(),
            "tidal_browse_mixes": lambda: s.mixes(),
            "tidal_browse_moods": lambda: s.moods(),
            "tidal_browse_videos": lambda: s.videos(),
            "tidal_list_genres": lambda: page(s.genre.get_genres()),
            "tidal_get_genre_items": lambda: self._genre_items(p),
            "tidal_get_folder": lambda: s.folder(p["folder_id"]),
            "tidal_list_folder_items": lambda: s.folder(p["folder_id"]).items(
                offset=p["offset"], limit=p["limit"] + 1
            ),
        }
        try:
            value = handlers[operation]()
        except KeyError as exc:
            raise TidalClientError(f"Unsupported read operation: {operation}") from exc
        except Exception as exc:
            self._raise_operation_error(operation.replace("tidal_", "").replace("_", " "), exc)
        warnings = []
        if operation in {"tidal_get_track_url", "tidal_get_video_url"}:
            warnings.append(
                "Playback URLs are temporary and account-scoped; no media was downloaded."
            )
        return format_catalog_result(
            operation,
            value,
            limit=p.get("limit"),
            offset=p.get("offset"),
            warnings=warnings,
        )

    def preview_mutation(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Resolve enough public metadata to make an exact mutation human-auditable."""
        preview: dict[str, Any] = {"action": action, "parameters": payload}
        try:
            if action == "create_playlist":
                preview["tracks"] = [
                    public_item(self.session.track(track_id)).model_dump(exclude_none=True)
                    for track_id in payload.get("track_ids") or []
                ]
            elif playlist_id := payload.get("playlist_id"):
                preview["target"] = public_item(self.session.playlist(playlist_id)).model_dump(
                    exclude_none=True
                )
            elif folder_id := payload.get("folder_id"):
                preview["target"] = public_item(self.session.folder(folder_id)).model_dump(
                    exclude_none=True
                )
        except Exception as exc:
            self._raise_operation_error(f"preview {action.replace('_', ' ')}", exc)
        return preview

    def execute_mutation(self, action: str, payload: dict[str, Any]) -> MutationResult:
        """Execute one allowlisted mutation after the server has claimed its approval token."""
        p = payload
        s = self.session
        favorites = s.user.favorites

        def playlist() -> Any:
            return s.playlist(p["playlist_id"])

        def folder() -> Any:
            return s.folder(p["folder_id"])

        handlers = {
            "create_playlist": lambda: self._create_playlist_action(p),
            "delete_playlist": lambda: playlist().delete(),
            "edit_playlist": lambda: playlist().edit(p.get("title"), p.get("description")),
            "add_tracks_to_playlist": lambda: playlist().add(
                p["track_ids"], p["allow_duplicates"], p["position"]
            ),
            "add_track_by_isrc_to_playlist": lambda: playlist().add_by_isrc(
                p["isrc"], p["allow_duplicates"], p["position"]
            ),
            "clear_playlist": lambda: playlist().clear(),
            "merge_playlist": lambda: playlist().merge(
                p["source_playlist_id"], p["allow_duplicates"], p["allow_missing"]
            ),
            "move_playlist_item_by_id": lambda: playlist().move_by_id(p["media_id"], p["position"]),
            "move_playlist_item_by_index": lambda: playlist().move_by_index(
                p["index"], p["position"]
            ),
            "move_playlist_items_by_indices": lambda: playlist().move_by_indices(
                p["indices"], p["position"]
            ),
            "remove_playlist_item_by_id": lambda: playlist().remove_by_id(p["media_id"]),
            "remove_playlist_item_by_index": lambda: playlist().remove_by_index(p["index"]),
            "remove_playlist_items_by_indices": lambda: playlist().remove_by_indices(p["indices"]),
            "remove_playlist_items_by_ids": lambda: playlist().delete_by_id(p["media_ids"]),
            "set_playlist_public": lambda: playlist().set_playlist_public(),
            "set_playlist_private": lambda: playlist().set_playlist_private(),
            "favorite_track": lambda: favorites.add_track(p["track_ids"]),
            "favorite_track_by_isrc": lambda: favorites.add_track_by_isrc(p["isrc"]),
            "unfavorite_track": lambda: favorites.remove_track(p["track_id"]),
            "favorite_album": lambda: favorites.add_album(p["album_ids"]),
            "unfavorite_album": lambda: favorites.remove_album(p["album_id"]),
            "favorite_artist": lambda: favorites.add_artist(p["artist_ids"]),
            "unfavorite_artist": lambda: favorites.remove_artist(p["artist_id"]),
            "favorite_playlist": lambda: favorites.add_playlist(
                p["playlist_ids"], p["parent_folder_id"]
            ),
            "unfavorite_playlist": lambda: favorites.remove_playlist(p["playlist_ids"]),
            "favorite_video": lambda: favorites.add_video(p["video_id"]),
            "unfavorite_video": lambda: favorites.remove_video(p["video_id"]),
            "favorite_mix": lambda: favorites.add_mixes(p["mix_ids"]),
            "unfavorite_mix": lambda: favorites.remove_mixes(p["mix_ids"]),
            "create_folder": lambda: s.user.create_folder(p["title"], p["parent_folder_id"]),
            "rename_folder": lambda: folder().rename(p["title"]),
            "delete_folder": lambda: folder().remove(),
            "add_items_to_folder": lambda: folder().add_items(p["item_trns"]),
            "move_items_to_folder": lambda: folder().move_items_to_folder(
                p["item_trns"], p["destination_folder_id"]
            ),
            "move_items_to_root": lambda: folder().move_items_to_root(p["item_trns"]),
            "remove_folder_items": lambda: favorites.remove_folders_playlists(
                p["item_trns"], p["item_type"]
            ),
        }
        try:
            value = handlers[action]()
        except KeyError as exc:
            raise TidalClientError(f"Unsupported mutation action: {action}") from exc
        except PartialPlaylistCreationError as exc:
            old = exc.result
            return MutationResult(
                status="partial",
                action=action,
                message=old.message,
                affected_ids=[old.playlist.id],
                item=public_item(old.playlist),
                details={
                    "tracks_requested": old.tracks_requested,
                    "tracks_added": old.tracks_added,
                },
                warning=old.warning,
            )
        except Exception as exc:
            self._raise_operation_error(action.replace("_", " "), exc)
        if isinstance(value, CommitPlaylistResult):
            return MutationResult(
                status=value.status,
                action=action,
                message=value.message,
                affected_ids=[value.playlist.id],
                item=public_item(value.playlist),
                details={
                    "tracks_requested": value.tracks_requested,
                    "tracks_added": value.tracks_added,
                },
                warning=value.warning,
            )
        item = (
            None
            if isinstance(value, (bool, int, float, str, list, dict, type(None)))
            else public_item(value)
        )
        return MutationResult(
            status="success",
            action=action,
            message=f"TIDAL confirmed {action.replace('_', ' ')}.",
            item=item,
            details={"result": value if item is None else True},
        )

    def _create_playlist_action(self, payload: dict[str, Any]) -> CommitPlaylistResult:
        playlist = self.session.user.create_playlist(
            payload["title"], payload["description"], payload["parent_folder_id"]
        )
        track_ids = payload.get("track_ids") or []
        if track_ids:
            playlist.add(track_ids)
        return CommitPlaylistResult(
            status="success",
            message=f"Created playlist {payload['title']!r}.",
            playlist=format_playlist(playlist),
            tracks_requested=len(track_ids),
            tracks_added=len(track_ids),
        )

    @staticmethod
    def _track_page(
        tracks: list[Track], limit: int, offset: int, *, total: int | None = None
    ) -> TrackPage:
        has_more = len(tracks) > limit if total is None else offset + limit < total
        return TrackPage(
            items=tracks[:limit],
            count=min(len(tracks), limit),
            limit=limit,
            offset=offset,
            has_more=has_more,
            next_offset=offset + limit if has_more else None,
        )

    @staticmethod
    def _favorites_total(favorites: Any) -> int | None:
        try:
            return int(favorites.get_tracks_count())
        except Exception as exc:
            LOGGER.info("TIDAL favorites count unavailable (%s)", type(exc).__name__)
            return None

    @staticmethod
    def _raise_operation_error(operation: str, exc: Exception) -> NoReturn:
        LOGGER.info("TIDAL operation failed: %s (%s)", operation, type(exc).__name__)
        raise TidalClientError(
            f"TIDAL could not {operation}. Try again once; if it persists, run `tidal-auth`."
        ) from exc
