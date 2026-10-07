"""Verify a packaged server through a real MCP stdio subprocess."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile

from mcp import Client, StdioServerParameters

from tidal_mcp.catalog import MUTATION_TOOL_SPECS, READ_TOOL_SPECS

EXPECTED_TOOLS = {
    "tidal_auth_status",
    "tidal_search",
    "tidal_list_favorite_tracks",
    "tidal_list_playlists",
    "tidal_get_playlist_tracks",
    "tidal_recommend_tracks",
    "tidal_collect_playlist_tracks",
    "tidal_summarize_playlist",
    *(spec.name for spec in READ_TOOL_SPECS),
    *(spec.name for spec in MUTATION_TOOL_SPECS),
    "tidal_commit_action",
    "tidal_commit_create_playlist",
}


async def smoke() -> None:
    with tempfile.TemporaryDirectory(prefix="tidal-mcp-smoke-") as directory:
        environment = dict(os.environ)
        environment["TIDAL_MCP_DATA_DIR"] = directory
        environment.pop("TIDAL_MCP_ENABLE_WRITES", None)
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "tidal_mcp"],
            env=environment,
        )
        async with Client(parameters, raise_exceptions=True) as client:
            listed = await client.list_tools()
            names = {tool.name for tool in listed.tools}
            if names != EXPECTED_TOOLS or len(names) != 119:
                raise RuntimeError(f"Unexpected tool set: {sorted(names)}")
            auth = await client.call_tool("tidal_auth_status", {})
            if auth.is_error or auth.structured_content is None:
                raise RuntimeError("tidal_auth_status did not return structured output")
            print(
                json.dumps(
                    {
                        "protocol": "stdio",
                        "tools": len(names),
                        "authenticated": auth.structured_content["authenticated"],
                        "writes_enabled": False,
                    },
                    indent=2,
                )
            )


if __name__ == "__main__":
    asyncio.run(smoke())
