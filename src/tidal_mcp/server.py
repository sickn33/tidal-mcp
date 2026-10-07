"""MCP Python SDK v2 server for safe, local TIDAL access."""

from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Annotated, Any

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from tidal_mcp.catalog import (
    MUTATION_TOOL_SPECS,
    READ_TOOL_SPECS,
    MutationToolSpec,
    ReadToolSpec,
)
from tidal_mcp.exceptions import DraftError, TidalMCPError
from tidal_mcp.filtering import filter_recommendations
from tidal_mcp.models import (
    ActionDraft,
    AuthStatus,
    CatalogResult,
    CollectedTracks,
    MutationResult,
    PlaylistPage,
    PlaylistSummary,
    RecommendationFilters,
    RecommendationResponse,
    SearchResponse,
    SearchType,
    Track,
    TrackPage,
)
from tidal_mcp.prompts import register_prompts
from tidal_mcp.runtime import Runtime

READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=True)
LOCAL_PREVIEW = ToolAnnotations(
    read_only_hint=False,
    destructive_hint=False,
    idempotent_hint=False,
    open_world_hint=True,
)
SAFE_COMMIT = ToolAnnotations(
    read_only_hint=False,
    destructive_hint=True,
    idempotent_hint=True,
    open_world_hint=True,
)


def _as_tool_error(exc: TidalMCPError) -> ToolError:
    return ToolError(str(exc))


def _merge_recommendations(items: list[Track]) -> list[Track]:
    merged: dict[str, Track] = {}
    for track in items:
        existing = merged.get(track.id)
        if existing is None:
            merged[track.id] = track
            continue
        sources = list(dict.fromkeys([*existing.source_seed_ids, *track.source_seed_ids]))
        merged[track.id] = existing.model_copy(update={"source_seed_ids": sources})
    return list(merged.values())


def _tool_signature(
    spec: ReadToolSpec | MutationToolSpec, result_type: type[Any]
) -> inspect.Signature:
    parameters = [
        inspect.Parameter(
            parameter.name,
            inspect.Parameter.KEYWORD_ONLY,
            default=parameter.default,
            annotation=parameter.annotation,
        )
        for parameter in spec.params
    ]
    return inspect.Signature(parameters=parameters, return_annotation=result_type)


def _make_read_handler(runtime: Runtime, spec: ReadToolSpec) -> Any:
    async def handler(**kwargs: Any) -> CatalogResult:
        try:
            return await asyncio.to_thread(runtime.client().execute_read, spec.name, kwargs)
        except TidalMCPError as exc:
            raise _as_tool_error(exc) from exc

    handler.__name__ = spec.name
    handler.__doc__ = spec.description
    handler.__signature__ = _tool_signature(spec, CatalogResult)
    return handler


def _make_preview_handler(runtime: Runtime, spec: MutationToolSpec) -> Any:
    async def handler(**kwargs: Any) -> ActionDraft:
        payload = {key: value for key, value in kwargs.items() if value is not None}
        if spec.action == "create_playlist":
            payload.setdefault("track_ids", [])
        if spec.action == "edit_playlist" and not ({"title", "description"} & payload.keys()):
            raise ToolError("Provide at least one of title or description for a playlist edit.")
        try:
            preview = await asyncio.to_thread(
                runtime.client().preview_mutation,
                spec.action,
                payload,
            )
            record = runtime.draft_store.create_action(
                action=spec.action,
                payload=payload,
                preview=preview,
                destructive=spec.destructive,
            )
        except TidalMCPError as exc:
            raise _as_tool_error(exc) from exc
        return ActionDraft(
            approval_token=record.approval_token,
            action=record.action,
            payload=record.payload,
            preview=record.preview,
            created_at=record.created_at,
            expires_at=record.expires_at,
            writes_enabled=runtime.settings.writes_enabled,
            destructive=record.destructive,
            next_step=(
                "After the user approves this exact preview, call tidal_commit_action with "
                "approval_token."
                if runtime.settings.writes_enabled
                else "Remote writes are disabled. Restart with TIDAL_MCP_ENABLE_WRITES=1 only "
                "after the user explicitly enables mutations."
            ),
        )

    handler.__name__ = spec.name
    handler.__doc__ = spec.description + " This preview changes only a private local draft file."
    handler.__signature__ = _tool_signature(spec, ActionDraft)
    return handler


def create_server(runtime: Runtime | None = None) -> MCPServer:
    active_runtime = runtime or Runtime.from_settings()
    server = MCPServer(
        "tidal_mcp",
        title="TIDAL MCP",
        description="Local-first catalog, library, recommendation, and approved-playlist tools.",
        instructions=(
            "Use read-only tools freely when relevant. Never claim mood filtering is performed by "
            "TIDAL. Playlist creation requires an exact preview followed by an approved commit "
            "token."
        ),
        version="1.1.1",
    )

    @server.tool(title="Check TIDAL authentication", annotations=READ_ONLY)
    async def tidal_auth_status() -> AuthStatus:
        """Check the local TIDAL session without exposing OAuth credentials."""
        return await asyncio.to_thread(active_runtime.auth_status)

    @server.tool(title="Search the TIDAL catalog", annotations=READ_ONLY)
    async def tidal_search(
        query: Annotated[
            str,
            Field(min_length=1, max_length=200, description="Artist, album, track, or phrase."),
        ],
        media_types: Annotated[
            list[SearchType] | None,
            Field(
                min_length=1,
                max_length=5,
                description="Catalog result types to return; defaults to tracks.",
            ),
        ] = None,
        limit: Annotated[int, Field(ge=1, le=50, description="Results per requested type.")] = 20,
        offset: Annotated[int, Field(ge=0, le=10_000)] = 0,
    ) -> SearchResponse:
        """Search TIDAL. This tool reads public catalog metadata and changes nothing."""
        try:
            return await asyncio.to_thread(
                active_runtime.client().search,
                query,
                media_types or [SearchType.TRACKS],
                limit,
                offset,
            )
        except TidalMCPError as exc:
            raise _as_tool_error(exc) from exc

    @server.tool(title="List favorite TIDAL tracks", annotations=READ_ONLY)
    async def tidal_list_favorite_tracks(
        limit: Annotated[int, Field(ge=1, le=50)] = 20,
        offset: Annotated[int, Field(ge=0, le=100_000)] = 0,
    ) -> TrackPage:
        """List saved tracks ordered from most recently added, with pagination metadata."""
        try:
            return await asyncio.to_thread(
                active_runtime.client().list_favorite_tracks,
                limit,
                offset,
            )
        except TidalMCPError as exc:
            raise _as_tool_error(exc) from exc

    @server.tool(title="List TIDAL playlists", annotations=READ_ONLY)
    async def tidal_list_playlists(
        limit: Annotated[int, Field(ge=1, le=50)] = 20,
        offset: Annotated[int, Field(ge=0, le=100_000)] = 0,
    ) -> PlaylistPage:
        """List the authenticated user's playlists without changing them."""
        try:
            return await asyncio.to_thread(active_runtime.client().list_playlists, limit, offset)
        except TidalMCPError as exc:
            raise _as_tool_error(exc) from exc

    @server.tool(title="Read tracks from a TIDAL playlist", annotations=READ_ONLY)
    async def tidal_get_playlist_tracks(
        playlist_id: Annotated[str, Field(min_length=1, max_length=100)],
        limit: Annotated[int, Field(ge=1, le=50)] = 50,
        offset: Annotated[int, Field(ge=0, le=100_000)] = 0,
    ) -> TrackPage:
        """Read one playlist page by exact TIDAL playlist ID."""
        try:
            return await asyncio.to_thread(
                active_runtime.client().get_playlist_tracks,
                playlist_id,
                limit,
                offset,
            )
        except TidalMCPError as exc:
            raise _as_tool_error(exc) from exc

    @server.tool(title="Collect every track in a playlist", annotations=READ_ONLY)
    async def tidal_collect_playlist_tracks(
        playlist_id: Annotated[str, Field(min_length=1, max_length=100)],
        max_items: Annotated[
            int,
            Field(
                ge=1,
                le=2000,
                description=(
                    "Hard cap on collected tracks. The walk stops here and reports truncated."
                ),
            ),
        ] = 500,
    ) -> CollectedTracks:
        """Walk a playlist's pages and return the tracks, instead of paging by hand.

        The walk follows the page cursor until the end of the playlist or `max_items`. A short or
        empty page never ends the walk early. `truncated` is true when the cap was reached before
        the end, so a capped result is never mistaken for the complete playlist.
        """
        try:
            return await asyncio.to_thread(
                active_runtime.client().collect_playlist_tracks,
                playlist_id,
                max_items,
            )
        except TidalMCPError as exc:
            raise _as_tool_error(exc) from exc

    @server.tool(title="Summarize a TIDAL playlist", annotations=READ_ONLY)
    async def tidal_summarize_playlist(
        playlist_id: Annotated[str, Field(min_length=1, max_length=100)],
        max_items: Annotated[int, Field(ge=1, le=2000)] = 500,
        top_artists: Annotated[int, Field(ge=1, le=25)] = 5,
    ) -> PlaylistSummary:
        """Derive a summary of a playlist: duration, top artists, decades, duplicates.

        Every field is computed from metadata the read tools already return. Release-date decades
        count only tracks that carry a parseable year, and `tracks_without_release_date` reports the
        rest instead of silently folding them into a bucket. Duplicates are keyed on the normalized
        title and artist pair, because TIDAL serves distinct track ids for the same recording.
        """
        try:
            return await asyncio.to_thread(
                active_runtime.client().summarize_playlist,
                playlist_id,
                max_items,
                top_artists,
            )
        except TidalMCPError as exc:
            raise _as_tool_error(exc) from exc

    @server.tool(title="Recommend TIDAL tracks", annotations=READ_ONLY)
    async def tidal_recommend_tracks(
        seed_track_ids: Annotated[
            list[str],
            Field(min_length=1, max_length=10, description="One to ten exact TIDAL track IDs."),
        ],
        limit_per_seed: Annotated[int, Field(ge=1, le=25)] = 10,
        max_results: Annotated[int, Field(ge=1, le=100)] = 30,
        filters: RecommendationFilters | None = None,
    ) -> RecommendationResponse:
        """Get Track Radio candidates, deduplicate them, and apply deterministic metadata filters.

        Mood or acoustic character are not claimed as API-level filters. The returned metadata can
        be assessed by the calling model, while year, duration, explicitness, exclusions, and
        per-artist diversity are enforced here.
        """
        resolved_filters = filters or RecommendationFilters()
        exclusions = list(dict.fromkeys([*resolved_filters.exclude_track_ids, *seed_track_ids]))
        resolved_filters = resolved_filters.model_copy(update={"exclude_track_ids": exclusions})
        try:
            candidates: list[Track] = []
            for seed_id in seed_track_ids:
                candidates.extend(
                    await asyncio.to_thread(
                        active_runtime.client().get_track_radio,
                        seed_id,
                        limit_per_seed,
                    )
                )
            merged = _merge_recommendations(candidates)
            accepted, rejected = filter_recommendations(merged, resolved_filters)
            returned = accepted[:max_results]
            return RecommendationResponse(
                seed_track_ids=seed_track_ids,
                items=returned,
                candidate_count=len(merged),
                returned_count=len(returned),
                filtered_out_count=rejected + max(0, len(accepted) - len(returned)),
                filters=resolved_filters,
            )
        except TidalMCPError as exc:
            raise _as_tool_error(exc) from exc

    async def commit_action(
        approval_token: str, *, required_action: str | None = None
    ) -> MutationResult:
        if not active_runtime.settings.writes_enabled:
            raise ToolError(
                "Remote writes are disabled. Set TIDAL_MCP_ENABLE_WRITES=1 and restart the server "
                "only after the user explicitly enables mutations."
            )
        try:
            record = active_runtime.draft_store.load_action(approval_token, allow_expired=True)
            if required_action is not None and record.action != required_action:
                raise DraftError(
                    f"This token approves {record.action}, not {required_action}. "
                    "Use tidal_commit_action."
                )
            if record.state == "committed" and record.result is not None:
                return record.result
            record = active_runtime.draft_store.load_action(approval_token)
            if record.state == "committing":
                raise DraftError(
                    "This draft was interrupted while committing. Inspect TIDAL before retrying "
                    "to avoid duplicating the mutation."
                )
            if record.state == "failed":
                raise DraftError(
                    "This draft previously failed and cannot be retried safely. Inspect TIDAL and "
                    "create a fresh preview if needed."
                )
            active_runtime.draft_store.claim(record)
            committing = active_runtime.draft_store.mark_action_committing(record)
            try:
                result = await asyncio.to_thread(
                    active_runtime.client().execute_mutation,
                    committing.action,
                    committing.payload,
                )
            except TidalMCPError as exc:
                active_runtime.draft_store.mark_action_failed(
                    committing,
                    "TIDAL did not confirm whether the mutation completed.",
                )
                raise DraftError(
                    "TIDAL did not confirm the write. Inspect the target before creating a fresh "
                    "preview; this token is locked to prevent duplicate effects."
                ) from exc
            active_runtime.draft_store.mark_action_committed(committing, result)
            return result
        except TidalMCPError as exc:
            raise _as_tool_error(exc) from exc

    @server.tool(title="Commit an approved TIDAL action", annotations=SAFE_COMMIT)
    async def tidal_commit_action(
        approval_token: Annotated[
            str,
            Field(min_length=32, max_length=128, description="Token from an exact preview."),
        ],
    ) -> MutationResult:
        """Commit one exact action draft; a successful replay returns the stored result."""
        return await commit_action(approval_token)

    @server.tool(title="Commit approved playlist creation", annotations=SAFE_COMMIT)
    async def tidal_commit_create_playlist(
        approval_token: Annotated[
            str,
            Field(min_length=32, max_length=128, description="Token from playlist preview."),
        ],
    ) -> MutationResult:
        """Backward-compatible commit alias restricted to create_playlist drafts."""
        return await commit_action(approval_token, required_action="create_playlist")

    for spec in READ_TOOL_SPECS:
        server.tool(
            name=spec.name,
            title=spec.title,
            description=spec.description,
            annotations=READ_ONLY,
        )(_make_read_handler(active_runtime, spec))

    for spec in MUTATION_TOOL_SPECS:
        server.tool(
            name=spec.name,
            title=spec.title,
            description=spec.description,
            annotations=LOCAL_PREVIEW,
        )(_make_preview_handler(active_runtime, spec))

    register_prompts(server, active_runtime)
    return server


mcp = create_server()


def main() -> None:
    logging.getLogger("tidalapi").setLevel(logging.WARNING)
    mcp.run()
