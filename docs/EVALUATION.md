# Stable read-only evaluation set

These prompts exercise complex, safe workflows without modifying an account. Expected answers
must cite returned IDs and distinguish TIDAL metadata from model inference.

1. Find the five newest non-explicit favorite tracks, grouped by artist, and include TIDAL links.
2. Compare an artist's main albums, EPs/singles, and other appearances; identify exact overlaps.
3. Resolve an ISRC, return all matching TIDAL recordings, and compare their album metadata.
4. For an album, list tracks, mixed media items, editorial review, audio resolutions, and similar
   albums without claiming that every track has the album's maximum resolution.
5. Build a 20-track recommendation set from three seed tracks, exclude the seeds, enforce at most
   two tracks per artist, and explain every deterministic filter applied.
6. Inspect a playlist's metadata, exact item count, track count, first page of mixed items, and
   first page of audio-only tracks; explain any count difference.
7. List the user's playlist folders and summarize the contents of one selected folder with IDs.
8. Compare Home, For You, and Mixes discovery pages and identify items present in more than one.
9. Retrieve lyrics for a track and report whether synchronized subtitles are available without
   reproducing more copyrighted text than needed.
10. Prepare, but do not commit, a preview that adds selected recommendations to a new playlist;
    verify title, description, ordered IDs, expiry, write state, and destructive flag.

The live smoke script intentionally samples representative operations instead of executing all 73
reads against the real account on every run. The exhaustive route matrix is deterministic and runs
offline in the test suite.

