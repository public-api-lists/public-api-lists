# Remove RapidProxy Sponsorship

## Goal

Remove every RapidProxy advertisement, reference, and dedicated image from the repository while leaving all other sponsors unchanged.

## Changes

- Remove the RapidProxy advertisement block from `README.md`.
- Remove the RapidProxy sponsor block from `.github/SPONSORS.md`.
- Remove the RapidProxy advertisement template from `.github/scripts/build_api.py` so generated output cannot restore it.
- Delete `assets/rapidproxy.png`.

## Safety

Edits must be limited to the complete RapidProxy-specific blocks and image. The unrelated untracked file `broken_links.json` must remain untouched and must not be included in a commit.

## Verification

- Search the entire repository, excluding Git internals, for case-insensitive matches of `rapidproxy` and `rapid proxy`; expect no matches.
- Confirm `assets/rapidproxy.png` no longer exists.
- Review the diff to ensure no unrelated sponsor or content changes are present.
