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
        favorite_counts = await call(client, "tidal_get_favorite_counts", {})

        playlist_track_count: int | None = None
        playlist_items = playlists["items"]
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
                    "writes_enabled": False,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    arguments = parse_args()
    asyncio.run(smoke(arguments.command, arguments.server_args or ["-m", "tidal_mcp"]))
