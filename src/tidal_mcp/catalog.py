"""Declarative inventory for the complete public tidalapi surface exposed over MCP."""

from __future__ import annotations

from dataclasses import dataclass
from inspect import Parameter
from typing import Annotated, Any, Literal

from pydantic import Field

Identifier = Annotated[str, Field(min_length=1, max_length=160)]
IdentifierList = Annotated[list[str], Field(min_length=1, max_length=500)]
Limit = Annotated[int, Field(ge=1, le=100)]
Offset = Annotated[int, Field(ge=0, le=100_000)]
Dimension = Annotated[int, Field(ge=80, le=3000)]
Title = Annotated[str, Field(min_length=1, max_length=120)]
Description = Annotated[str, Field(max_length=500)]
Position = Annotated[int, Field(ge=0, le=100_000)]
Index = Annotated[int, Field(ge=0, le=100_000)]
Indices = Annotated[list[int], Field(min_length=1, max_length=500)]
Direction = Literal["ASC", "DESC"]
GenreKind = Literal["tracks", "albums", "artists", "playlists", "videos"]


@dataclass(frozen=True, slots=True)
class ParamSpec:
    name: str
    annotation: Any
    default: Any = Parameter.empty


@dataclass(frozen=True, slots=True)
class ReadToolSpec:
    name: str
    title: str
    description: str
    params: tuple[ParamSpec, ...]


@dataclass(frozen=True, slots=True)
class MutationToolSpec:
    action: str
    title: str
    description: str
    destructive: bool
    params: tuple[ParamSpec, ...]

    @property
    def name(self) -> str:
        return f"tidal_preview_{self.action}"


def p(name: str, annotation: Any, default: Any = Parameter.empty) -> ParamSpec:
    return ParamSpec(name, annotation, default)


PAGE = (p("limit", Limit, 50), p("offset", Offset, 0))


def ordered_page(order: Any) -> tuple[ParamSpec, ...]:
    return (*PAGE, p("order", order | None, None), p("order_direction", Direction | None, None))


ITEM_PAGE = ordered_page(Literal["ALBUM", "ARTIST", "DATE", "INDEX", "LENGTH", "NAME"])
ALBUM_PAGE = ordered_page(Literal["ARTIST", "DATE", "NAME", "RELEASE_DATE"])
ARTIST_PAGE = ordered_page(Literal["DATE", "NAME"])
PLAYLIST_PAGE = ordered_page(Literal["DATE", "NAME"])
VIDEO_PAGE = ordered_page(Literal["ARTIST", "DATE", "NAME"])
MIX_PAGE = ordered_page(Literal["DATE", "MIX_TYPE", "NAME"])


READ_TOOL_SPECS: tuple[ReadToolSpec, ...] = (
    ReadToolSpec(
        "tidal_get_track",
        "Get a TIDAL track",
        "Return full public metadata for one exact track ID.",
        (p("track_id", Identifier), p("with_album", bool, True)),
    ),
    ReadToolSpec(
        "tidal_get_album",
        "Get a TIDAL album",
        "Return public metadata for one exact album ID.",
        (p("album_id", Identifier),),
    ),
    ReadToolSpec(
        "tidal_get_artist",
        "Get a TIDAL artist",
        "Return public metadata for one exact artist ID.",
        (p("artist_id", Identifier),),
    ),
    ReadToolSpec(
        "tidal_get_playlist",
        "Get a TIDAL playlist",
        "Return public metadata for one exact playlist ID.",
        (p("playlist_id", Identifier),),
    ),
    ReadToolSpec(
        "tidal_get_video",
        "Get a TIDAL video",
        "Return public metadata for one exact video ID.",
        (p("video_id", Identifier),),
    ),
    ReadToolSpec(
        "tidal_get_mix",
        "Get a TIDAL mix",
        "Return public metadata for one exact legacy mix ID.",
        (p("mix_id", Identifier),),
    ),
    ReadToolSpec(
        "tidal_get_mix_v2",
        "Get a TIDAL v2 mix",
        "Return public metadata for one exact current-generation mix ID.",
        (p("mix_id", Identifier),),
    ),
    ReadToolSpec(
        "tidal_get_user",
        "Get a TIDAL user",
        "Return the current user or another public user by numeric ID.",
        (p("user_id", int | None, None),),
    ),
    ReadToolSpec(
        "tidal_get_albums_by_barcode",
        "Find TIDAL albums by barcode",
        "Resolve an exact UPC/EAN barcode to matching albums.",
        (p("barcode", Identifier), *PAGE),
    ),
    ReadToolSpec(
        "tidal_get_tracks_by_isrc",
        "Find TIDAL tracks by ISRC",
        "Resolve an exact ISRC to matching tracks.",
        (p("isrc", Identifier), *PAGE),
    ),
    ReadToolSpec(
        "tidal_get_track_radio",
        "Get TIDAL track radio",
        "List radio recommendations for one seed track.",
        (p("track_id", Identifier), *PAGE),
    ),
    ReadToolSpec(
        "tidal_get_track_radio_mix",
        "Get a track radio mix",
        "Return the reusable mix that powers radio for one track.",
        (p("track_id", Identifier),),
    ),
    ReadToolSpec(
        "tidal_get_track_lyrics",
        "Get TIDAL lyrics",
        "Return available lyrics and synchronized subtitles for one track.",
        (p("track_id", Identifier),),
    ),
    ReadToolSpec(
        "tidal_get_track_playback_info",
        "Get track playback metadata",
        "Return codec, quality, bit depth, and sample-rate metadata; no media is downloaded.",
        (p("track_id", Identifier),),
    ),
    ReadToolSpec(
        "tidal_get_track_audio_resolution",
        "Get track audio resolution",
        "Return the selected playback stream's bit depth and sample rate.",
        (p("track_id", Identifier),),
    ),
    ReadToolSpec(
        "tidal_get_track_url",
        "Get a temporary track URL",
        "Return the temporary playback URL supplied by TIDAL for the authenticated account.",
        (p("track_id", Identifier),),
    ),
    ReadToolSpec(
        "tidal_get_video_url",
        "Get a temporary video URL",
        "Return the temporary playback URL supplied by TIDAL for a video.",
        (p("video_id", Identifier),),
    ),
    ReadToolSpec(
        "tidal_get_video_image",
        "Get a TIDAL video image",
        "Return an image URL at the requested dimensions.",
        (
            p("video_id", Identifier),
            p("width", Annotated[int, Field(ge=160, le=3840)], 1080),
            p("height", Annotated[int, Field(ge=90, le=2160)], 720),
        ),
    ),
    ReadToolSpec(
        "tidal_get_album_tracks",
        "List album tracks",
        "Page through audio tracks on one album.",
        (p("album_id", Identifier), *PAGE, p("sparse_album", bool, False)),
    ),
    ReadToolSpec(
        "tidal_get_album_items",
        "List album items",
        "Page through every album item, including videos.",
        (p("album_id", Identifier), *PAGE, p("sparse_album", bool, False)),
    ),
    ReadToolSpec(
        "tidal_get_album_review",
        "Get an album review",
        "Return TIDAL editorial review text when available.",
        (p("album_id", Identifier),),
    ),
    ReadToolSpec(
        "tidal_get_album_similar",
        "List similar albums",
        "List albums TIDAL considers similar to a seed album.",
        (p("album_id", Identifier), *PAGE),
    ),
    ReadToolSpec(
        "tidal_get_album_audio_resolution",
        "Get album audio resolution",
        "Return available bit-depth and sample-rate pairs for an album.",
        (p("album_id", Identifier), p("individual_tracks", bool, False)),
    ),
    ReadToolSpec(
        "tidal_get_album_image",
        "Get an album cover",
        "Return an album-cover URL at the requested square size.",
        (p("album_id", Identifier), p("dimensions", Dimension, 1280)),
    ),
    ReadToolSpec(
        "tidal_get_album_video",
        "Get an album video image",
        "Return the album's video-art URL when available.",
        (p("album_id", Identifier), p("dimensions", Dimension, 1280)),
    ),
    ReadToolSpec(
        "tidal_get_album_page",
        "Browse an album page",
        "Return the structured TIDAL page associated with an album.",
        (p("album_id", Identifier),),
    ),
    ReadToolSpec(
        "tidal_get_artist_albums",
        "List artist albums",
        "Page through an artist's main album discography.",
        (p("artist_id", Identifier), *PAGE),
    ),
    ReadToolSpec(
        "tidal_get_artist_ep_singles",
        "List artist EPs and singles",
        "Page through an artist's EPs and singles.",
        (p("artist_id", Identifier), *PAGE),
    ),
    ReadToolSpec(
        "tidal_get_artist_other_albums",
        "List other artist appearances",
        "Page through compilations and other album appearances.",
        (p("artist_id", Identifier), *PAGE),
    ),
    ReadToolSpec(
        "tidal_get_artist_bio",
        "Get an artist biography",
        "Return TIDAL's artist biography text when available.",
        (p("artist_id", Identifier),),
    ),
    ReadToolSpec(
        "tidal_get_artist_radio",
        "Get artist radio",
        "Page through radio tracks for an artist.",
        (p("artist_id", Identifier), *PAGE),
    ),
    ReadToolSpec(
        "tidal_get_artist_radio_mix",
        "Get an artist radio mix",
        "Return the reusable mix that powers artist radio.",
        (p("artist_id", Identifier),),
    ),
    ReadToolSpec(
        "tidal_get_artist_similar",
        "List similar artists",
        "Page through artists related to a seed artist.",
        (p("artist_id", Identifier), *PAGE),
    ),
    ReadToolSpec(
        "tidal_get_artist_top_tracks",
        "List artist top tracks",
        "Page through an artist's most prominent tracks.",
        (p("artist_id", Identifier), *PAGE),
    ),
    ReadToolSpec(
        "tidal_get_artist_videos",
        "List artist videos",
        "Page through an artist's videos.",
        (p("artist_id", Identifier), *PAGE),
    ),
    ReadToolSpec(
        "tidal_get_artist_image",
        "Get an artist image",
        "Return an artist-image URL at the requested square size.",
        (p("artist_id", Identifier), p("dimensions", Dimension, 750)),
    ),
    ReadToolSpec(
        "tidal_get_artist_page",
        "Browse an artist page",
        "Return the structured TIDAL page associated with an artist.",
        (p("artist_id", Identifier),),
    ),
    ReadToolSpec(
        "tidal_get_playlist_items",
        "List playlist items",
        "Page through every playlist item, including videos.",
        (p("playlist_id", Identifier), *ITEM_PAGE),
    ),
    ReadToolSpec(
        "tidal_get_playlist_track_count",
        "Count playlist tracks",
        "Return the exact number of audio tracks in a playlist.",
        (p("playlist_id", Identifier),),
    ),
    ReadToolSpec(
        "tidal_get_playlist_item_count",
        "Count playlist items",
        "Return the exact number of tracks and videos in a playlist.",
        (p("playlist_id", Identifier),),
    ),
    ReadToolSpec(
        "tidal_get_playlist_image",
        "Get a playlist image",
        "Return a square playlist-image URL.",
        (p("playlist_id", Identifier), p("dimensions", Dimension, 1080)),
    ),
    ReadToolSpec(
        "tidal_get_playlist_wide_image",
        "Get a wide playlist image",
        "Return a wide playlist-image URL at requested dimensions.",
        (
            p("playlist_id", Identifier),
            p("width", Annotated[int, Field(ge=160, le=3840)], 1080),
            p("height", Annotated[int, Field(ge=90, le=2160)], 720),
        ),
    ),
    ReadToolSpec(
        "tidal_list_favorite_albums",
        "List favorite albums",
        "Page through albums saved in My Collection.",
        ALBUM_PAGE,
    ),
    ReadToolSpec(
        "tidal_list_favorite_artists",
        "List favorite artists",
        "Page through artists saved in My Collection.",
        ARTIST_PAGE,
    ),
    ReadToolSpec(
        "tidal_list_favorite_playlists",
        "List favorite playlists",
        "Page through playlists saved in My Collection.",
        PLAYLIST_PAGE,
    ),
    ReadToolSpec(
        "tidal_list_favorite_videos",
        "List favorite videos",
        "Page through videos saved in My Collection.",
        VIDEO_PAGE,
    ),
    ReadToolSpec(
        "tidal_list_favorite_mixes",
        "List favorite mixes",
        "Page through mixes saved in My Collection.",
        MIX_PAGE,
    ),
    ReadToolSpec(
        "tidal_list_playlist_folders",
        "List playlist folders",
        "Page through the authenticated user's playlist folders.",
        (*PLAYLIST_PAGE, p("parent_folder_id", Identifier, "root")),
    ),
    ReadToolSpec(
        "tidal_get_favorite_counts",
        "Count favorite media",
        "Return exact saved track, album, artist, playlist, and video counts.",
        (),
    ),
    ReadToolSpec(
        "tidal_list_public_playlists",
        "List public user playlists",
        "Page through the authenticated user's public playlists.",
        PAGE,
    ),
    ReadToolSpec(
        "tidal_list_playlists_and_favorites",
        "List owned and favorite playlists",
        "Page through the combined playlist view used by TIDAL.",
        PAGE,
    ),
    ReadToolSpec(
        "tidal_get_user_image",
        "Get the user image",
        "Return the authenticated user's profile-image URL.",
        (p("dimensions", Dimension, 750),),
    ),
    ReadToolSpec(
        "tidal_get_mix_items",
        "List mix items",
        "Page through the tracks and videos in a TIDAL mix.",
        (p("mix_id", Identifier), *PAGE),
    ),
    ReadToolSpec(
        "tidal_get_mix_image",
        "Get a mix image",
        "Return a legacy mix image URL at a supported size.",
        (p("mix_id", Identifier), p("dimensions", Literal[320, 640, 1500], 640)),
    ),
    ReadToolSpec(
        "tidal_get_mix_v2_image",
        "Get a v2 mix image",
        "Return a current-generation mix image URL at a supported size.",
        (p("mix_id", Identifier), p("dimensions", Literal[320, 640, 1500], 640)),
    ),
    ReadToolSpec(
        "tidal_browse_home", "Browse TIDAL Home", "Return the personalized Home page.", ()
    ),
    ReadToolSpec("tidal_browse_explore", "Browse TIDAL Explore", "Return the Explore page.", ()),
    ReadToolSpec(
        "tidal_browse_for_you", "Browse TIDAL For You", "Return the personalized For You page.", ()
    ),
    ReadToolSpec("tidal_browse_genres", "Browse genre hubs", "Return TIDAL's genre-hub page.", ()),
    ReadToolSpec(
        "tidal_browse_hires",
        "Browse hi-res music",
        "Return TIDAL's high-resolution audio page.",
        (),
    ),
    ReadToolSpec(
        "tidal_browse_local_genres", "Browse local genres", "Return the localized genre page.", ()
    ),
    ReadToolSpec(
        "tidal_browse_mixes", "Browse personal mixes", "Return the personalized mixes page.", ()
    ),
    ReadToolSpec("tidal_browse_moods", "Browse moods", "Return TIDAL's mood page.", ()),
    ReadToolSpec("tidal_browse_videos", "Browse videos", "Return TIDAL's video page.", ()),
    ReadToolSpec("tidal_list_genres", "List TIDAL genres", "List every catalog genre.", PAGE),
    ReadToolSpec(
        "tidal_get_genre_items",
        "List items in a genre",
        "Page through tracks, albums, artists, playlists, or videos in one genre.",
        (p("genre_path", Identifier), p("kind", GenreKind), *PAGE),
    ),
    ReadToolSpec(
        "tidal_get_folder",
        "Get a playlist folder",
        "Return public metadata for one exact playlist-folder ID.",
        (p("folder_id", Identifier),),
    ),
    ReadToolSpec(
        "tidal_list_folder_items",
        "List playlist-folder items",
        "Page through playlists contained in one folder.",
        (p("folder_id", Identifier), *PAGE),
    ),
)


MUTATION_TOOL_SPECS: tuple[MutationToolSpec, ...] = (
    MutationToolSpec(
        "create_playlist",
        "Preview playlist creation",
        "Preview a new playlist and its exact ordered track IDs.",
        False,
        (
            p("title", Title),
            p("track_ids", Annotated[list[str] | None, Field(max_length=500)], None),
            p("description", Description, ""),
            p("parent_folder_id", Identifier, "root"),
        ),
    ),
    MutationToolSpec(
        "delete_playlist",
        "Preview playlist deletion",
        "Preview permanently deleting one owned playlist.",
        True,
        (p("playlist_id", Identifier),),
    ),
    MutationToolSpec(
        "edit_playlist",
        "Preview playlist edit",
        "Preview changing an owned playlist's title or description.",
        False,
        (
            p("playlist_id", Identifier),
            p("title", Title | None, None),
            p("description", Description | None, None),
        ),
    ),
    MutationToolSpec(
        "add_tracks_to_playlist",
        "Preview adding playlist tracks",
        "Preview adding exact track IDs to an owned playlist.",
        False,
        (
            p("playlist_id", Identifier),
            p("track_ids", IdentifierList),
            p("allow_duplicates", bool, False),
            p("position", int, -1),
        ),
    ),
    MutationToolSpec(
        "add_track_by_isrc_to_playlist",
        "Preview adding a track by ISRC",
        "Preview resolving and adding an ISRC to an owned playlist.",
        False,
        (
            p("playlist_id", Identifier),
            p("isrc", Identifier),
            p("allow_duplicates", bool, False),
            p("position", int, -1),
        ),
    ),
    MutationToolSpec(
        "clear_playlist",
        "Preview clearing a playlist",
        "Preview removing every item from an owned playlist.",
        True,
        (p("playlist_id", Identifier),),
    ),
    MutationToolSpec(
        "merge_playlist",
        "Preview playlist merge",
        "Preview copying one playlist into another.",
        False,
        (
            p("playlist_id", Identifier),
            p("source_playlist_id", Identifier),
            p("allow_duplicates", bool, False),
            p("allow_missing", bool, True),
        ),
    ),
    MutationToolSpec(
        "move_playlist_item_by_id",
        "Preview moving a playlist item",
        "Preview moving an item identified by media ID.",
        False,
        (p("playlist_id", Identifier), p("media_id", Identifier), p("position", Position)),
    ),
    MutationToolSpec(
        "move_playlist_item_by_index",
        "Preview moving a playlist index",
        "Preview moving an item identified by its current index.",
        False,
        (p("playlist_id", Identifier), p("index", Index), p("position", Position)),
    ),
    MutationToolSpec(
        "move_playlist_items_by_indices",
        "Preview moving playlist indices",
        "Preview moving several current indices as one operation.",
        False,
        (p("playlist_id", Identifier), p("indices", Indices), p("position", Position)),
    ),
    MutationToolSpec(
        "remove_playlist_item_by_id",
        "Preview removing a playlist item",
        "Preview removing one media ID from an owned playlist.",
        True,
        (p("playlist_id", Identifier), p("media_id", Identifier)),
    ),
    MutationToolSpec(
        "remove_playlist_item_by_index",
        "Preview removing a playlist index",
        "Preview removing one item by current index.",
        True,
        (p("playlist_id", Identifier), p("index", Index)),
    ),
    MutationToolSpec(
        "remove_playlist_items_by_indices",
        "Preview removing playlist indices",
        "Preview removing several items by current indices.",
        True,
        (p("playlist_id", Identifier), p("indices", Indices)),
    ),
    MutationToolSpec(
        "remove_playlist_items_by_ids",
        "Preview removing playlist media IDs",
        "Preview removing several exact media IDs from an owned playlist.",
        True,
        (p("playlist_id", Identifier), p("media_ids", IdentifierList)),
    ),
    MutationToolSpec(
        "set_playlist_public",
        "Preview making a playlist public",
        "Preview changing an owned playlist to public visibility.",
        False,
        (p("playlist_id", Identifier),),
    ),
    MutationToolSpec(
        "set_playlist_private",
        "Preview making a playlist private",
        "Preview changing an owned playlist to private visibility.",
        False,
        (p("playlist_id", Identifier),),
    ),
    MutationToolSpec(
        "favorite_track",
        "Preview favoriting a track",
        "Preview saving one or more tracks to My Collection.",
        False,
        (p("track_ids", IdentifierList),),
    ),
    MutationToolSpec(
        "favorite_track_by_isrc",
        "Preview favoriting by ISRC",
        "Preview resolving and saving one track by ISRC.",
        False,
        (p("isrc", Identifier),),
    ),
    MutationToolSpec(
        "unfavorite_track",
        "Preview removing a favorite track",
        "Preview removing one track from My Collection.",
        True,
        (p("track_id", Identifier),),
    ),
    MutationToolSpec(
        "favorite_album",
        "Preview favoriting an album",
        "Preview saving one or more albums to My Collection.",
        False,
        (p("album_ids", IdentifierList),),
    ),
    MutationToolSpec(
        "unfavorite_album",
        "Preview removing a favorite album",
        "Preview removing one album from My Collection.",
        True,
        (p("album_id", Identifier),),
    ),
    MutationToolSpec(
        "favorite_artist",
        "Preview favoriting an artist",
        "Preview saving one or more artists to My Collection.",
        False,
        (p("artist_ids", IdentifierList),),
    ),
    MutationToolSpec(
        "unfavorite_artist",
        "Preview removing a favorite artist",
        "Preview removing one artist from My Collection.",
        True,
        (p("artist_id", Identifier),),
    ),
    MutationToolSpec(
        "favorite_playlist",
        "Preview favoriting a playlist",
        "Preview saving one or more playlists to My Collection.",
        False,
        (p("playlist_ids", IdentifierList), p("parent_folder_id", Identifier, "root")),
    ),
    MutationToolSpec(
        "unfavorite_playlist",
        "Preview removing a favorite playlist",
        "Preview removing one or more playlists from My Collection.",
        True,
        (p("playlist_ids", IdentifierList),),
    ),
    MutationToolSpec(
        "favorite_video",
        "Preview favoriting a video",
        "Preview saving one video to My Collection.",
        False,
        (p("video_id", Identifier),),
    ),
    MutationToolSpec(
        "unfavorite_video",
        "Preview removing a favorite video",
        "Preview removing one video from My Collection.",
        True,
        (p("video_id", Identifier),),
    ),
    MutationToolSpec(
        "favorite_mix",
        "Preview favoriting a mix",
        "Preview saving one or more mixes to My Collection.",
        False,
        (p("mix_ids", IdentifierList),),
    ),
    MutationToolSpec(
        "unfavorite_mix",
        "Preview removing a favorite mix",
        "Preview removing one or more mixes from My Collection.",
        True,
        (p("mix_ids", IdentifierList),),
    ),
    MutationToolSpec(
        "create_folder",
        "Preview folder creation",
        "Preview creating a playlist folder.",
        False,
        (p("title", Title), p("parent_folder_id", Identifier, "root")),
    ),
    MutationToolSpec(
        "rename_folder",
        "Preview folder rename",
        "Preview renaming one playlist folder.",
        False,
        (p("folder_id", Identifier), p("title", Title)),
    ),
    MutationToolSpec(
        "delete_folder",
        "Preview folder deletion",
        "Preview deleting one playlist folder.",
        True,
        (p("folder_id", Identifier),),
    ),
    MutationToolSpec(
        "add_items_to_folder",
        "Preview adding folder items",
        "Preview adding playlist or folder TRNs to a folder.",
        False,
        (p("folder_id", Identifier), p("item_trns", IdentifierList)),
    ),
    MutationToolSpec(
        "move_items_to_folder",
        "Preview moving folder items",
        "Preview moving playlist or folder TRNs into a folder.",
        False,
        (
            p("folder_id", Identifier),
            p("item_trns", IdentifierList),
            p("destination_folder_id", Identifier),
        ),
    ),
    MutationToolSpec(
        "move_items_to_root",
        "Preview moving items to root",
        "Preview moving playlist or folder TRNs to collection root.",
        False,
        (p("folder_id", Identifier), p("item_trns", IdentifierList)),
    ),
    MutationToolSpec(
        "remove_folder_items",
        "Preview removing folder items",
        "Preview removing playlist or folder TRNs from the collection tree.",
        True,
        (p("item_trns", IdentifierList), p("item_type", Literal["folder", "playlist"], "folder")),
    ),
)


def all_tool_names() -> set[str]:
    """Return the declarative tool-name set for verification and documentation."""
    return {spec.name for spec in READ_TOOL_SPECS} | {spec.name for spec in MUTATION_TOOL_SPECS}
