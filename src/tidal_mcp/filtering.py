"""Deterministic filters for TIDAL recommendation candidates."""

from __future__ import annotations

from collections import defaultdict

from tidal_mcp.models import RecommendationFilters, Track


def _year(value: str | None) -> int | None:
    if not value or len(value) < 4:
        return None
    try:
        return int(value[:4])
    except ValueError:
        return None


def filter_recommendations(
    tracks: list[Track],
    filters: RecommendationFilters,
) -> tuple[list[Track], int]:
    """Apply strict metadata filters and per-artist diversity limits."""
    excluded_ids = set(filters.exclude_track_ids)
    artist_counts: defaultdict[str, int] = defaultdict(int)
    accepted: list[Track] = []
    rejected = 0

    for track in tracks:
        release_year = _year(track.release_date)
        artist_key = track.artist_id or track.artist.casefold()

        keep = track.id not in excluded_ids
        if filters.release_year_min is not None:
            keep = keep and release_year is not None and release_year >= filters.release_year_min
        if filters.release_year_max is not None:
            keep = keep and release_year is not None and release_year <= filters.release_year_max
        if filters.duration_seconds_min is not None:
            keep = (
                keep
                and track.duration_seconds is not None
                and track.duration_seconds >= filters.duration_seconds_min
            )
        if filters.duration_seconds_max is not None:
            keep = (
                keep
                and track.duration_seconds is not None
                and track.duration_seconds <= filters.duration_seconds_max
            )
        if filters.explicit is not None:
            keep = keep and track.explicit is not None and track.explicit is filters.explicit
        if artist_counts[artist_key] >= filters.max_tracks_per_artist:
            keep = False

        if keep:
            artist_counts[artist_key] += 1
            accepted.append(track)
        else:
            rejected += 1

    return accepted, rejected
