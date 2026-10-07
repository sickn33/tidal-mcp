"""Fail the build when the documented tool counts drift from the code.

The README, coverage contract, registry metadata, landing page, and llms files all quote a tool
count. Those numbers had already drifted twice, so they are now derived from the executable
inventory and asserted here instead of being trusted by hand.
"""

from __future__ import annotations

from pathlib import Path

from scripts.smoke_stdio import EXPECTED_TOOLS
from tidal_mcp.catalog import MUTATION_TOOL_SPECS, READ_TOOL_SPECS

ROOT = Path(__file__).resolve().parents[1]

TOTAL = len(EXPECTED_TOOLS)
REQUIRED_TOTAL = len(READ_TOOL_SPECS) + len(MUTATION_TOOL_SPECS)
# Handwritten registrations: auth, search, favorite tracks, playlists, playlist tracks, collection,
# summary, comparison, recommendation, export, and the two commit tools.
HANDWRITTEN = 13
# The catalog inventory plus the handwritten read tools. The two commit aliases are the only
# registered tools that can write, and the mutation previews are counted separately.
READS = TOTAL - len(MUTATION_TOOL_SPECS) - 2


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_the_registered_surface_matches_the_declared_inventory() -> None:
    assert REQUIRED_TOTAL + HANDWRITTEN == TOTAL
    assert READS == 84
    assert TOTAL == 122


def test_both_expected_tool_sets_agree() -> None:
    """The smoke test keeps its own list; it must not fall behind the contract.

    A stale list here would make the packaged smoke check pass while silently ignoring a newly
    registered tool, which is exactly how the counts drifted before.
    """
    from tests.test_server import EXPECTED_TOOLS as SERVER_EXPECTED

    assert EXPECTED_TOOLS == SERVER_EXPECTED


def test_every_document_quotes_the_same_counts() -> None:
    readme = read("README.md")
    assert f"**{TOTAL} typed MCP tools**" in readme
    assert f"**{TOTAL} discoverable tools:** {READS} reads" in readme

    coverage = read("docs/API_COVERAGE.md")
    assert f"- {TOTAL} MCP tools with input and output schemas." in coverage
    assert f"- {READS} read-only tools." in coverage

    llms = read("llms.txt")
    assert f"- {TOTAL} registered MCP tools with bounded input" in llms
    assert (
        f"- {READS} read-only tools, {len(MUTATION_TOOL_SPECS)} local mutation-preview tools"
        in llms
    )

    registry = read("server.json")
    assert f"{TOTAL} typed MCP tools" in registry

    package = read("package.json")
    assert f"{TOTAL} typed tools" in package

    smoke = read("scripts/smoke_stdio.py")
    assert f"len(names) != {TOTAL}" in smoke

    site = read("site/index.html")
    assert f"{TOTAL} Tools for AI Music Workflows" in site
    assert f"{TOTAL} TIDAL MCP tools across eight capability groups" in site

    site_llms = read("site/llms.txt")
    assert f"{TOTAL} typed tools" in site_llms
    assert f"{TOTAL} named MCP tools: {READS} reads" in site_llms


def test_no_current_document_quotes_a_stale_count() -> None:
    stale = ("117",)
    for relative in (
        "README.md",
        "docs/API_COVERAGE.md",
        "docs/FAQ.md",
        "server.json",
        "package.json",
        "llms.txt",
        "site/llms.txt",
    ):
        content = read(relative)
        for number in stale:
            assert number not in content, f"{relative} still quotes {number}"


def test_the_dated_comparison_keeps_its_snapshot_number() -> None:
    """The September 4, 2026 comparison must keep the figure that was true at that snapshot."""
    matrix = read("docs/COMPETITIVE_MATRIX.md")
    assert "| **TIDAL MCP 1.0** | **112** |" in matrix
    assert "exposed **112** named tools on September 4, 2026" in matrix
    assert f"now exposes **{TOTAL}**" in matrix

    site_llms = read("site/llms.txt")
    assert "112 tools at the reviewed snapshot" in site_llms


def test_the_coverage_document_accounts_for_every_exclusion() -> None:
    """The coverage contract must list every excluded method, and its group sizes must add up."""
    import re

    from tests.test_tidalapi_surface import SURFACE

    coverage = read("docs/API_COVERAGE.md")
    covered = sum(len(methods) for methods, _ in SURFACE.values())
    excluded = sum(len(methods) for _, methods in SURFACE.values())

    assert f"There are {covered} covered methods and {excluded}" in coverage
    assert f"The {excluded} exclusions fall into" in coverage

    # Parse the counts out of the document's own table so the assertion tests the document rather
    # than a number duplicated in this test.
    table_rows = re.findall(r"^\| ([A-Z][^|]+?) \| (\d+) \|", coverage, re.MULTILINE)
    assert table_rows, "the exclusion table is missing"
    assert sum(int(count) for _, count in table_rows) == excluded, table_rows

    # Every group must name at least one real member, and the families summarized by example must
    # name a member that actually exists in the exclusion set.
    all_excluded = {method for _, methods in SURFACE.values() for method in methods}
    for _, _, members in re.findall(
        r"^\| ([A-Z][^|]+?) \| (\d+) \| ([^|]+?) \|", coverage, re.MULTILINE
    ):
        names = re.findall(r"`([A-Za-z_][A-Za-z0-9_.]*)`", members)
        leafs = {name.split(".")[-1] for name in names}
        assert leafs & all_excluded, (members, "names no real excluded method")


def test_the_readme_tool_table_sums_to_the_registered_total() -> None:
    """The README groups the surface into a table; the group sizes must add up to the real total.

    The table is the first thing a reader uses to size the project, so a row that silently counts
    two tools while saying three is a real defect, not a rounding detail. Prompts are guidance over
    the tools and must not be counted as tools.
    """
    import re

    readme = read("README.md")
    block = readme[readme.index("## Tool coverage") :]
    rows = re.findall(r"^\| ([^|]+?) \| (\d+) \|", block, re.MULTILINE)
    assert rows, "the README tool table is missing"

    labels = [label.strip() for label, _ in rows]
    assert all("prompt" not in label.lower() for label in labels), (
        "prompts must not be counted as tools"
    )
    assert sum(int(count) for _, count in rows) == TOTAL, rows

    # The prompt count is stated separately and must match the registered prompts.
    prompts = read("src/tidal_mcp/prompts.py")
    registered = prompts.count("@server.prompt(")
    assert registered == 4, registered
    assert f"The table sums to the **{TOTAL}** registered tools." in readme
    assert "Four MCP prompts are registered alongside them" in readme


def test_the_landing_page_capability_ranges_cover_every_tool_once() -> None:
    """The landing page numbers its capability groups; the ranges must tile 1..TOTAL exactly.

    A range that overlaps or leaves a gap misstates the surface as surely as a wrong total, and
    the ranges had already drifted twice while the headline number stayed correct.
    """
    import re

    site = read("site/index.html")
    labels = re.findall(r'<span class="cap-number">(?:(\d+)|(\d+)\u2014(\d+))</span>', site)
    assert labels, "the landing page capability ranges are missing"

    ranges: list[tuple[int, int]] = []
    for single, start, end in labels:
        if single:
            ranges.append((int(single), int(single)))
        else:
            ranges.append((int(start), int(end)))
    ranges.sort()

    assert ranges[0][0] == 1, ranges
    assert ranges[-1][1] == TOTAL, ranges
    for index in range(len(ranges) - 1):
        assert ranges[index][1] + 1 == ranges[index + 1][0], (ranges, "gap or overlap")
    assert sum(end - start + 1 for start, end in ranges) == TOTAL
