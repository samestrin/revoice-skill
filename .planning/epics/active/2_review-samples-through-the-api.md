# Epic Plan 2: Review samples through the text analysis API, not Claude

- **Estimated time**: 1 day
- **Last modified**: 2026-10-27 (written by Sam with Claude Code; not yet refined)
- **Tasks/Components**: 3/2
- **Components, counted by top-level path — two:**
  - `skill/revoice/` — new `build/review-samples.py`, its test, and `build.md`
  - root — `README.md`, `CHANGELOG.md`
- **Base branch: `main`.** Every PR targets `main`.
- **Depends on:** rust-text-analysis-api epic 66 (`POST /analyze/sample-review`) merged **and deployed** to the API that `build-profile.py` calls. Also builds on PR #11 (EST-3022: `--max-samples`, README privacy paragraph).

## Goal

`/revoice --build` no longer sends every extracted email to Claude's model provider. The KEEP/DROP review moves from Claude (phase 3 of `skill/revoice/build.md`) to the text analysis API, which already receives the kept samples. Claude still reads the samples the profile is built from in phase 6, to write the voice file; that stays.

## Current State

- Phase 3 of `skill/revoice/build.md`: "Read every sample listed in `samples/index.csv`, in full", then add `verdict,score,reason` columns. After PR #11 extraction keeps at most 200 samples, so up to 200 emails go through Claude.
- `build/build-profile.py` reads `verdict` and `score` from `samples/index.csv` (`ranked_files`), sends at most `MAX_DOCS = 100` KEEP samples, reads the key from `--api-key`, `TEXT_ANALYSIS_API_KEY` or `~/.config/revoice/api-key`, and posts with `X-API-Key`.
- CI runs `--help` on every `skill/revoice/build/*.py`, so a new helper is covered by the glob.

## Tasks (canonical)

- **T1** — Add `build/review-samples.py` (standard library only, like the other helpers): read `samples/index.csv`, post the samples to `/analyze/sample-review` in batches of at most 100, and write `verdict,score,reason` into `index.csv`, keeping existing columns and rows. Reuse `build-profile.py`'s key lookup and API base. Clear exits for 401 (wrong key), 402 (out of credits) and a timeout or 5xx (say the API is down, write nothing). Add `tests/test_review_samples.py` with the HTTP call stubbed (no network) · `skill/revoice/build/review-samples.py`, `skill/revoice/tests/test_review_samples.py` · depends: none · success: tests cover a 150-sample batch split, the columns written in order, and each error exit leaving `index.csv` unchanged; `python3 skill/revoice/build/review-samples.py --help` exits 0
- **T2** — Rewrite phase 3 of `build.md` to run `review-samples.py` and report KEEP vs DROP counts and the top drop reasons from the CSV, without reading the samples. Keep the "fewer than 15 KEEP" warning. Phase 4 (the key check) moves before phase 3, since phase 3 now needs the key. If the API review fails, follow open question 1 · `skill/revoice/build.md` · depends: T1 · success: (manual) the owner runs `/revoice --build` on a test export and the transcript shows no sample text read before phase 6. Trigger: owner, after epic 66 is deployed.
- **T3** — README: the "What leaves your machine" paragraph says samples go to the text analysis API for review and building, and that Claude reads only the samples the profile is built from (at most 100) to write the voice file; the "Running the steps by hand" order adds `review-samples.py`; a credits line per epic 66's price. CHANGELOG Unreleased entry · `README.md`, `CHANGELOG.md` · depends: T2 · success: the README matches what `build.md` does, step by step

## Open Questions

1. **Fallback when the API review fails.** (a) Stop and tell the user to try later. (b) Offer the old Claude review, with a clear note that the samples then go to Claude's model provider, and run it only if the user says yes. Recommendation: (b).
2. **Address hint.** Phase 2 tells Claude to point out another address of the user's that it notices "while reading". With no reading in phase 3, that hint only works in phase 6. Drop it, or keep it in phase 6? Recommendation: keep it in phase 6.

## Out of scope

- How the API decides KEEP or DROP. That is rust-text-analysis-api epic 66.
- Phase 6 (Claude reads the profile's samples to write the voice file).
