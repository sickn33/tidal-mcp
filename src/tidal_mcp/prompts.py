"""Reusable MCP prompts that turn common TIDAL intents into a concrete tool sequence.

Prompts are guidance, not capability: every prompt names only read-only tools, or names the
preview tool together with the rule that the user must approve before the commit tool runs. That
keeps a prompt from becoming a way to bypass the approval gate.
"""

from __future__ import annotations

from typing import Literal

from mcp.server import MCPServer

Message = dict[str, str]


def _user(content: str) -> Message:
    return {"role": "user", "content": content}


def register_prompts(server: MCPServer, runtime: object) -> None:
    """Register the built-in prompts on an MCP server.

    `runtime` is accepted so prompts can grow context-aware behavior later; the current prompts
    return static guidance and never touch TIDAL, so they cannot fail on a missing session.
    """

    @server.prompt(
        name="tidal_playlist_from_description",
        title="Build a playlist from a description",
        description=(
            "Plan a playlist from a mood or theme, then prepare it for explicit approval. "
            "Read-only until you approve, and it never commits on its own."
        ),
    )
    def playlist_from_description(
        description: str,
        target_track_count: int = 20,
    ) -> list[Message]:
        """Turn a free-text theme into search, recommendations, a preview, and an approval."""
        return [
            _user(
                "\n".join(
                    [
                        f"Build a TIDAL playlist of about {target_track_count} tracks for this "
                        f"brief: {description}",
                        "",
                        "Work in this order:",
                        "1. Use `tidal_search` with the most specific artists, genres, or phrases "
                        "from the brief, across tracks and albums.",
                        "2. Seed `tidal_recommend_tracks` from two or three strong track ids you "
                        "found, and use its metadata filters (year, duration, explicit) to match "
                        "the brief. Treat mood as your own judgement; TIDAL does not filter by it.",
                        "3. Pick the final ordered track ids and state the total duration.",
                        "4. Call `tidal_preview_create_playlist` with the title, description, and "
                        "ordered ids to produce an approval token.",
                        "",
                        "Stop there and show the preview. Do not call `tidal_commit_action` "
                        "until the user approves that exact preview. If the brief is too "
                        "vague to search, ask one clarifying question instead of guessing.",
                    ]
                )
            )
        ]

    @server.prompt(
        name="tidal_playlist_review",
        title="Review one of my playlists",
        description="Summarize, critique, and suggest concrete edits for a playlist you own.",
    )
    def playlist_review(
        playlist_id: str,
        focus: Literal["flow", "variety", "length", "duplicates"] = "flow",
    ) -> list[Message]:
        """Ground a review in the derived summary instead of guessing about the contents."""
        return [
            _user(
                "\n".join(
                    [
                        f"Review the TIDAL playlist `{playlist_id}`, focusing on {focus}.",
                        "",
                        "1. Call `tidal_summarize_playlist` for that id to get duration, top "
                        "artists, decade spread, explicit count, and exact duplicates.",
                        "2. Read the tracks with `tidal_collect_playlist_tracks` if you need the "
                        "actual order.",
                        "3. Report the numbers you measured, then give a short critique and "
                        "concrete edits. Name exact track ids when you propose a change.",
                        "4. If the user wants the current version on disk, offer "
                        "`tidal_export_playlist`; it writes only inside the private export "
                        "directory and never overwrites an existing file.",
                        "",
                        "Describe anything you did not measure as unknown rather than implying it. "
                        "Do not modify the playlist unless the user asks; if they do, go through "
                        "`tidal_preview_*` and wait for approval.",
                    ]
                )
            )
        ]

    @server.prompt(
        name="tidal_discovery_digest",
        title="Digest today's TIDAL recommendations",
        description="Summarize what Home, For You, and mixes are offering, with no writes.",
    )
    def discovery_digest(
        sections: int = 5,
    ) -> list[Message]:
        """Walk the personalized pages and report, while staying inside the read surface."""
        return [
            _user(
                "\n".join(
                    [
                        f"Summarize what TIDAL is recommending for me right now, across about "
                        f"{sections} sections.",
                        "",
                        "1. Read `tidal_browse_home`, `tidal_browse_for_you`, and "
                        "`tidal_browse_mixes`.",
                        "2. Each editorial page returns categories. Use "
                        "`tidal_list_page_category_items` to open the categories that look most "
                        "interesting, and `tidal_show_more_page_category` to expand one when you "
                        "need more than the first screen.",
                        "3. Group what you find by theme and name the specific artists, albums, "
                        "and playlists worth a listen, with ids.",
                        "",
                        "This is a read-only digest. Do not add anything to the library. If a "
                        "category reports that it has no expandable items, treat that as a normal "
                        "empty section and move on.",
                    ]
                )
            )
        ]

    @server.prompt(
        name="tidal_library_audit",
        title="Audit my saved collection",
        description="Report the shape of favorites and flag overlaps or gaps.",
    )
    def library_audit() -> list[Message]:
        """Use the exact counters and paginated listings instead of a partial walk."""
        return [
            _user(
                "\n".join(
                    [
                        "Audit my saved TIDAL collection.",
                        "",
                        "1. Start with `tidal_get_favorite_counts` for the exact totals.",
                        "2. Read the favorites you care about with the `tidal_list_favorite_*` "
                        "tools. Walk pages until `has_more` is false; a short or empty page is not "
                        "the end of the collection, only `has_more` is authoritative.",
                        "3. Report the totals, then flag anything notable: artists saved but never "
                        "played, playlist folders that look abandoned, overlaps between your saved "
                        "playlists.",
                        "",
                        "Report only what the tools return. Do not remove or reorder anything. "
                        "`tidal_compare_playlists` is useful for spotting overlap between two "
                        "saved playlists.",
                    ]
                )
            )
        ]
