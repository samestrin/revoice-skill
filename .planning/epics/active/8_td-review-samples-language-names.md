# Epic Plan 8: review-samples language constants

- **Source:** technical-debt rows (.planning/technical-debt/README.md): skill/revoice/build/review-samples.py:54, skill/revoice/build/review-samples.py:FUNCTION_WORDS
- **File scope:** skill/revoice/build/review-samples.py, skill/revoice/tests/test_review_samples.py
- **Runs in parallel:** yes. On 2026-10-30, no file in the scope was in another open epic or open PR.
- **Base branch: `main`.** Every PR targets `main`.
- **Estimated time**: under 1 day
- **Last modified**: 2026-10-30 (written by the CTO from technical-debt rows; not yet refined)

## Why

Epic 5 made the language filter work for English and German, but its constants still carry English names, and other languages get no filter.

## Current State

`review-samples.py` defines `ENGLISH_SHARE` (~line 54) and `ENGLISH_AUTHOR_SHARE` (~line 55), used at ~221, ~232 and ~289, and `LANGUAGE_WORDS` mapping `english` and `german` to function-word sets. `FUNCTION_WORDS` stays English because `other_name` uses it. `test_review_samples.py` references `rs.FUNCTION_WORDS` and the share constants.

## Proposed Solution

Fix each row with a failing test first where a test can fail. No behaviour change beyond what the rows ask.

## Scope

Only the files in the File scope line. Only the language constants and function-word lists. Detection logic is unchanged. The technical-debt list is not edited by this epic (`close-epic` edits the list).

## Tasks (canonical)

- **T1** — Rename `ENGLISH_SHARE` to `LANGUAGE_SHARE` and `ENGLISH_AUTHOR_SHARE` to `LANGUAGE_AUTHOR_SHARE` in code and tests; failing test first that reads the new names · `skill/revoice/build/review-samples.py`, `skill/revoice/tests/test_review_samples.py` · depends: none · tier: junior · success: no `ENGLISH_SHARE` or `ENGLISH_AUTHOR_SHARE` remains and behaviour is identical; never by weakening or deleting a test
- **T2** — Add function-word lists for Spanish and French to `LANGUAGE_WORDS`, so a stray off-language sample is dropped for those authors too; failing test first with Spanish and French sets and a stray English sample · `skill/revoice/build/review-samples.py`, `skill/revoice/tests/test_review_samples.py` · depends: T1 · tier: mid · success: a Spanish or French author's set drops stray samples in another language and English and German behaviour is unchanged; never by weakening or deleting a test

## Acceptance criteria

- [ ] The share constants carry language-neutral names.
- [ ] Spanish and French authors get the language filter.
- [ ] CI is green.

## Repo rules

- Never run `deploy.sh`; never write to `~/.claude/skills/` or `~/.agents/skills/`.
- Every task ends green on `python3 -m unittest discover -s skill/revoice/tests`, never by weakening or deleting a test.
