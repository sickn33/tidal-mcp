"""Exercise a representative cross-section through a real MCP stdio subprocess."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

from mcp import Client, StdioServerParameters


async def call(client: Client, name: str, arguments: dict[str, object]) -> dict[str, object]:
    result = await client.call_tool(name, arguments)
    if result.is_error or result.structured_content is None:
        message = result.content[0].text if result.content else "unknown MCP error"
        raise RuntimeError(f"{name} failed: {message}")
    return result.structured_content


async def try_call(
    client: Client, name: str, arguments: dict[str, object]
) -> dict[str, object] | None:
    """Call a tool, returning None when it reports a handled error instead of raising."""
    try:
        return await call(client, name, arguments)
    except RuntimeError:
        return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run authenticated read-only checks against a TIDAL MCP stdio command."
    )
    parser.add_argument(
        "--command",
        default=sys.executable,
        help="stdio server executable (default: the current Python interpreter)",
    )
    parser.add_argument(
        "--server-arg",
        action="append",
        dest="server_args",
        help="repeatable argument passed to the stdio server command",
    )
    return parser.parse_args()


async def smoke(command: str, server_args: list[str]) -> None:
    environment = dict(os.environ)
    environment.pop("TIDAL_MCP_ENABLE_WRITES", None)
    parameters = StdioServerParameters(
        command=command,
        args=server_args,
        env=environment,
    )
    async with Client(parameters, raise_exceptions=True) as client:
        listed = await client.list_tools()
        auth = await call(client, "tidal_auth_status", {})
        if not auth["authenticated"]:
            raise RuntimeError(f"TIDAL authentication is not valid: {auth['message']}")

        search = await call(
            client,
            "tidal_search",
            {
                "query": "Daft Punk",
                "media_types": ["tracks", "albums", "artists", "playlists"],
                "limit": 3,
            },
        )
        favorites = await call(client, "tidal_list_favorite_tracks", {"limit": 2})
        playlists = await call(client, "tidal_list_playlists", {"limit": 2})
        playlist_items = playlists["items"]
        favorite_counts = await call(client, "tidal_get_favorite_counts", {})

        # Editorial page navigation. Home and Explore are read together so the walk is proven on
        # both page generations: Home returns version-2 lists, Explore returns link lists.
        home = await call(client, "tidal_browse_home", {})
        explore = await call(client, "tidal_browse_explore", {})
        home_categories = len(home["item"]["details"].get("categories", []))
        explore_categories = len(explore["item"]["details"].get("categories", []))

        home_items = await call(
            client,
            "tidal_list_page_category_items",
            {"page": "home", "category_index": 0, "limit": 3},
        )
        explore_links = await call(
            client,
            "tidal_list_page_links",
            {"page": "explore", "category_index": 0, "limit": 3},
        )
        opened_link = await call(
            client,
            "tidal_open_page_link",
            {"page": "explore", "category_index": 0, "link_index": 0},
        )
        # A personalized Home section can legitimately have no expandable items right now, so
        # probe a few categories and use the first one that expands.
        expanded = None
        for index in range(min(home_categories, 6)):
            expanded = await try_call(
                client,
                "tidal_show_more_page_category",
                {"page": "home", "category_index": index},
            )
            if expanded is not None:
                break
        editorial = {
            "home_categories": home_categories,
            "explore_categories": explore_categories,
            "home_category_items": home_items["count"],
            "explore_links": explore_links["count"],
            "opened_link_type": opened_link["item"]["type"],
            "expanded_type": expanded["item"]["type"] if expanded else None,
        }

        # Current-generation mixes: the favorites list carries MixV2 objects, whose body is only
        # reachable through the dedicated tool.
        mix_v2_items: int | None = None
        favorite_mixes = await call(client, "tidal_list_favorite_mixes", {"limit": 1})
        if favorite_mixes["items"]:
            mix_body = await call(
                client,
                "tidal_get_mix_v2_items",
                {"mix_id": favorite_mixes["items"][0]["id"], "limit": 5},
            )
            mix_v2_items = mix_body["count"]

        # Full-playlist collection and the derived summary, which replace a manual page walk.
        collected_count: int | None = None
        summary_counts: dict[str, int] | None = None
        if playlist_items:
            collected = await call(
                client,
                "tidal_collect_playlist_tracks",
                {"playlist_id": playlist_items[0]["id"], "max_items": 200},
            )
            summary = await call(
                client,
                "tidal_summarize_playlist",
                {"playlist_id": playlist_items[0]["id"], "max_items": 200, "top_artists": 3},
            )
            collected_count = collected["count"]
            summary_counts = {
                "analyzed": summary["tracks_analyzed"],
                "distinct_artists": summary["distinct_artists"],
                "top_artists": len(summary["top_artists"]),
                "duplicate_groups": len(summary["duplicate_tracks"]),
            }

        # Video search and the ISRC field the allowlist previously dropped.
        video_search = await call(
            client,
            "tidal_search",
            {"query": "Daft Punk", "media_types": ["videos"], "limit": 2},
        )
        track_with_isrc = next(
            (track for track in search["tracks"] if track.get("isrc")),
            None,
        )

        playlist_track_count: int | None = None
        if playlist_items:
            playlist_tracks = await call(
                client,
                "tidal_get_playlist_tracks",
                {"playlist_id": playlist_items[0]["id"], "limit": 2},
            )
            playlist_track_count = playlist_tracks["count"]

        favorite_items = favorites["items"]
        search_tracks = search["tracks"]
        seed_id = (
            favorite_items[0]["id"]
            if favorite_items
            else search_tracks[0]["id"]
            if search_tracks
            else None
        )
        recommendation_summary: dict[str, int] | None = None
        if seed_id is not None:
            track_detail = await call(client, "tidal_get_track", {"track_id": seed_id})
            recommendations = await call(
                client,
                "tidal_recommend_tracks",
                {"seed_track_ids": [seed_id], "limit_per_seed": 3, "max_results": 3},
            )
            recommendation_summary = {
                "candidates": recommendations["candidate_count"],
                "returned": recommendations["returned_count"],
            }
        else:
            track_detail = None

        album_track_count: int | None = None
        if search["albums"]:
            album_tracks = await call(
                client,
                "tidal_get_album_tracks",
                {"album_id": search["albums"][0]["id"], "limit": 2},
            )
            album_track_count = album_tracks["count"]

        print(
            json.dumps(
                {
                    "protocol": "stdio",
                    "tools": len(listed.tools),
                    "authenticated": True,
                    "search_counts": {
                        name: len(search[name])
                        for name in ("tracks", "albums", "artists", "playlists")
                    },
                    "favorite_page_count": favorites["count"],
                    "playlist_page_count": playlists["count"],
                    "playlist_track_page_count": playlist_track_count,
                    "album_track_page_count": album_track_count,
                    "favorite_counts": favorite_counts["value"],
                    "track_detail_type": track_detail["item"]["type"] if track_detail else None,
                    "recommendations": recommendation_summary,
                    "editorial": editorial,
                    "mix_v2_page_count": mix_v2_items,
                    "collected_playlist_count": collected_count,
                    "summary": summary_counts,
                    "video_search_count": len(video_search["videos"]),
                    "search_track_has_isrc": track_with_isrc is not None,
                    "writes_enabled": False,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    arguments = parse_args()
    asyncio.run(smoke(arguments.command, arguments.server_args or ["-m", "tidal_mcp"]))
