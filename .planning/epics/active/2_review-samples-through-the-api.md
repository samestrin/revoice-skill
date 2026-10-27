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

- **T1** — Add `build/review-samples.py` (standard library only, like the other helpers): read `samples/index.csv`, post the samples to `/analyze/sample-review` in batches of at most 100, and write `verdict,score,reason` into `index.csv`, keeping existing columns and rows (write to a temp file in the same folder and move it over `index.csv` only after every batch succeeded). Copy the key lookup and the `--api` / `--api-key` / `--api-key-file` flags from `build-profile.py:90-103` into `review-samples.py`; do not edit `build-profile.py`. Give each request a 60 s timeout (the API's metered limit is 25 s). Clear exits for 401 (wrong key), 402 (out of credits) and a timeout or 5xx (say the API is down, write nothing). Add `tests/test_review_samples.py` with the HTTP call stubbed (no network) · `skill/revoice/build/review-samples.py`, `skill/revoice/tests/test_review_samples.py` · depends: none · success: tests cover a 150-sample batch split, the columns written in order, and each error exit leaving `index.csv` unchanged; `python3 skill/revoice/build/review-samples.py --help` exits 0
- **T2** — Rewrite phase 3 of `build.md` to run `review-samples.py` and report KEEP vs DROP counts and the top drop reasons from the CSV, without reading the samples. Keep the "fewer than 15 KEEP" warning. Phase 4 (the key check) moves before phase 3, since phase 3 now needs the key; renumber the phases, and update the phase 5 line that sends the user back to "phase 4", the phase 0 helper list (add `review-samples.py`) and the rules line that names `build-profile.py` as the only helper that sends samples. After PR #11 merges, reword its phase 2 sentence that says extraction is capped "because you read every one in phase 3". If the API review fails, say why (wrong key, out of credits, API down) and offer the Claude review that phase 3 has today (keep that text as the fallback), saying plainly that the samples would then go to Claude's model provider, and run it only if the user says yes; amend the rule "Do not send samples anywhere except the text analysis API" to name this opt-in fallback. Move the phase 2 hint about another address of the user's to phase 6 ("while reading the profile's samples") · `skill/revoice/build.md` · depends: T1 · success: (manual) the owner runs `/revoice --build` on a test export and the transcript shows no sample text read before phase 6. Trigger: owner, after epic 66 is deployed.
- **T3** — README: the "What leaves your machine" paragraph says samples go to the text analysis API for review and building, and that Claude reads only the samples the profile is built from (15 by default, `--top`) to write the voice file; the "Running the steps by hand" order adds `review-samples.py`; a credits line per epic 66's price; the "How it works" step 2 ("has Claude pick the ones that really sound like you") and the build walkthrough ("reviewing") reworded to match; and, because review sends every extracted sample (including the ones it drops), the paragraph says that, and names any outside engine epic 66 adds. CHANGELOG Unreleased entry · `README.md`, `CHANGELOG.md` · depends: T2 · success: the README matches what `build.md` does, step by step, and no README line still says Claude picks the samples

## Open Questions

1. **(Decided 2026-10-27: (b).)** **Fallback when the API review fails.** (a) Stop and tell the user to try later. (b) Offer the old Claude review, with a clear note that the samples then go to Claude's model provider, and run it only if the user says yes. Recommendation: (b).
2. **(Decided 2026-10-27: keep it in phase 6.)** **Address hint.** Phase 2 tells Claude to point out another address of the user's that it notices "while reading". With no reading in phase 3, that hint only works in phase 6. Drop it, or keep it in phase 6? Recommendation: keep it in phase 6.

## Out of scope

- How the API decides KEEP or DROP. That is rust-text-analysis-api epic 66.
- Phase 6 (Claude reads the profile's samples to write the voice file).

<!-- refine-epic:begin -->
## Refinements (2026-10-27)
### Auto-applied corrections (5)
1. T1: write `index.csv` through a temp file and rename after every batch succeeds, so the "each error exit leaves `index.csv` unchanged" criterion also holds for a failure in batch 2 (evidence: T1 success text).
2. T1: a 60 s per-request timeout; `build-profile.py:47` uses 600 s, and epic 66 caps a metered request at 25 s (`METERING_HANDLER_TIMEOUT_SECS`).
3. T2: the other `build.md` lines the phase move breaks: phase 5 "send the user back to phase 4", the phase 0 helper list, the rule "Do not send samples anywhere except … `build-profile.py`", and (after PR #11) the phase 2 cap sentence "because you read every one in phase 3" (PR #11 `build.md` phase 2).
4. T3: README `README.md:16` ("has Claude pick the ones that really sound like you") and `README.md:128` ("reviewing") also go stale; added to T3, with the success criterion.
5. T3: review sends every extracted sample, including ones it drops (pasted articles, forwards), so the API now sees more than the 100 KEEP samples it sees today; the README paragraph must say so, and name any outside engine epic 66 adds (epic 66 open question 1 option b makes TypeSafe a processor).
### Items needing user confirmation (3)
1. Open question 1 (plan): fallback when the API review fails. Owner's call.
2. Open question 2 (plan): the "another address" hint, phase 2 vs phase 6. Owner's call.
3. T1 "Reuse `build-profile.py`'s key lookup and API base": the lookup is inline in `main()` (`build-profile.py:99-103`) and the base is an argparse default (`:90`); neither is a function. Copy the six lines, or extract a shared module, or edit `build-profile.py` (a file no task lists).
### Advisory observations (4)
- Not dispatchable yet: epic 66 must be merged **and deployed** (its branch `docs/epic-66-sample-review` is an unmerged plan today; no `sample-review` code in rust-text-analysis-api `main`), and PR #11 (EST-3022) must be merged first. It edits the same `build.md` phase 2 line, `README.md` privacy paragraph and `CHANGELOG.md` Unreleased list that T2/T3 edit.
- Epic 66 removes near-duplicates only inside one request; T1 sends batches of 100, so a form letter whose copies land in different batches is not caught. Epic 66 open question 1 also says rules-only review cannot spot "someone else's voice" or another language, so quality may drop against Claude's review. The T2 criterion is manual; compare KEEP/DROP counts with Claude's on a real export.
- A failure in batch 2 leaves batch 1 charged; a rerun pays again. Epic 66's price is undecided (open question 2: `PerText(1)` is up to 200 credits, `Flat(1)` is 2); the README credits line (T3) waits on it.
- The 200-sample cap from PR #11 existed because Claude read every sample; after this epic it only bounds API credits. Left as is.
### Verification context
- Code repo: revoice-skill at 8bfae93 (plan commit 60a8830). Plan written: 2026-10-27. Commits reviewed since: 0 on `main`; PR #11 read as a diff.
- Tasks: 3 (limit 7). Components: 2 (limit 3): `skill/revoice/`, root (`README.md`, `CHANGELOG.md`)
- Claims checked: 9 (MAX_DOCS = 100, key lookup order, X-API-Key, `ranked_files` reads verdict/score, CI `--help` glob over `build/*.py`, phase 3/4 text, README privacy text, PR #11 contents, epic 66 contract). Discovery searches: `index.csv`, `verdict`, `phase [0-9]`, `Claude`, `MAX_DOCS|urlopen`
- Failure modes: caller (key via X-API-Key, 401/402 handled in T1); slow or down (timeout added); stops halfway (temp file and rename added; double charge noted); what leaves (all extracted samples now go to the API; README line added); input forms (CSV quoting: `csv` module, not string split). No write route or login is added.
- Vision fit: no VISION.md
<!-- refine-epic:end -->

<!-- refine-epic:begin -->
## Refinements (2026-10-27, answers from EST-3026)
### Auto-applied corrections (2)
1. T1: copy the key lookup and the three API flags instead of "reusing" them; the lookup is inline in `main()` and the script cannot be imported (`build-profile.py:90-103`, `tests/_load.py:3-4`). Answer Q3, EST-3026.
2. T3: Claude reads `--top` samples (default 15), not "at most 100" (`build-profile.py:94,112,154`). Found while answering Q2, EST-3026.
### Items needing user confirmation (2)
1. Open question 1: fallback when the API review fails (recommended: b, opt-in Claude fallback; build.md:9 rule must be amended).
2. Open question 2: address hint (recommended: keep in phase 6, where it sees about 15 samples, not 200).
### Advisory observations (0)
### Verification context
- Code repo: revoice-skill at 8bfae93. Tasks: 3 (limit 7). Components: 2 (limit 3).
- Claims checked: 3 more. Failure modes: see the report above.
- Vision fit: no VISION.md
<!-- refine-epic:end -->

<!-- refine-epic:begin -->
## Refinements (2026-10-27, owner answers)
### Auto-applied corrections (2)
1. Open question 1 answered (b) by the owner on EST-3025: T2 now keeps the Claude review as an opt-in fallback with disclosure, and amends the `build.md:9` rule.
2. Open question 2 answered "keep in phase 6" by the owner: T2 moves the address hint to phase 6.
### Items needing user confirmation (0)
### Advisory observations (1)
- Do not dispatch until rust-text-analysis-api epic 66 is merged **and deployed**, and PR #11 (EST-3022) is merged.
### Verification context
- Code repo: revoice-skill at 8bfae93. Tasks: 3 (limit 7). Components: 2 (limit 3).
- Vision fit: no VISION.md
<!-- refine-epic:end -->
