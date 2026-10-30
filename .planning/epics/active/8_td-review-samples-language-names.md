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

`review-samples.py` defines `ENGLISH_SHARE` (~line 54) and `ENGLISH_AUTHOR_SHARE` (~line 55), used at lines 232 and 289 (line 221 is a docstring mention), and `LANGUAGE_WORDS` mapping `english` and `german` to function-word sets. `FUNCTION_WORDS` stays English because `other_name` uses it. `test_review_samples.py` references `rs.FUNCTION_WORDS` (line 245) but neither share constant, so T1 adds the test that reads the new names.

## Proposed Solution

Fix each row with a failing test first where a test can fail. No behaviour change beyond what the rows ask.

## Scope

Only the files in the File scope line. Only the language constants and function-word lists. Detection logic is unchanged. The technical-debt list is not edited by this epic (`close-epic` edits the list).

## Tasks (canonical)

- **T1** — Give `ENGLISH_SHARE` the new name `LANGUAGE_SHARE` and `ENGLISH_AUTHOR_SHARE` the new name `LANGUAGE_AUTHOR_SHARE` in code and tests; failing test first that reads the new names · `skill/revoice/build/review-samples.py`, `skill/revoice/tests/test_review_samples.py` · depends: none · tier: junior · success: no `ENGLISH_SHARE` or `ENGLISH_AUTHOR_SHARE` remains and behaviour is identical; never by weakening or deleting a test
- **T2** — Add function-word lists for Spanish and French to `LANGUAGE_WORDS`, so a stray off-language sample is dropped for those authors too; failing test first with Spanish and French sets and a stray English sample · `skill/revoice/build/review-samples.py`, `skill/revoice/tests/test_review_samples.py` · depends: T1 · tier: junior · success: a Spanish or French author's set drops stray samples in another language and English and German behaviour is unchanged; never by weakening or deleting a test

## Acceptance criteria

- [ ] The share constants carry language-neutral names.
- [ ] Spanish and French authors get the language filter.
- [ ] CI is green.

## Repo rules

- Never run `deploy.sh`; never write to `~/.claude/skills/` or `~/.agents/skills/`.
- Every task ends green on `python3 -m unittest discover -s skill/revoice/tests`, never by weakening or deleting a test.

<!-- refine-epic:begin -->
## Refinements (2026-10-30)
### Auto-applied corrections (3)
- Current State: share constants are used at `review-samples.py:232` and `:289`; `:221` is a docstring mention (grep on `origin/main`).
- Current State: `test_review_samples.py` does not reference either share constant (grep finds only `rs.FUNCTION_WORDS`, line 245), so T1 must add a test that reads the new names.
- T2 `tier: mid` is not a valid tier; set to `junior` (fully specified: add two word lists to an existing dict).
### Items needing user confirmation (0)
### Advisory observations (0)
### Verification context
- Code repo: revoice-skill at e6617fb. Plan written: 2026-10-30. Commits reviewed since: 0 touching the scope files
- Tasks: 2 (limit 7). Components: 1 (limit 3): skill/revoice
- Parallel check: no Paperclip `Epic <N>:` parent open in the project; no open PRs; File scope (`review-samples.py`, `test_review_samples.py`) shared with no other plan in `epics/active/` (4, 6, 7, 9).
- Claims checked: 8. Discovery searches: `ENGLISH_` , `FUNCTION_WORDS`, `LANGUAGE_WORDS`, `other_name`
- Failure modes: none apply: local build script, no network, login, money or deploy
- Vision fit: no VISION.md
<!-- refine-epic:end -->

<!-- refine-epic:begin -->
## Refinements (2026-10-30, dispatch follow-up)
### Auto-applied corrections (1)
- T1 wording: "Rename" matched the dispatch router's mechanical-work rule (`routing.py:100,146`) and the tool refused T1. Reworded without changing intent, on the owner's answer (EST-3329 card `dispatch-t1`, option `reword`).
### Items needing user confirmation (0)
### Advisory observations (0)
### Verification context
- Code repo: revoice-skill at e880f34. Tasks: 2 (limit 7). Components: 1 (limit 3): skill/revoice
- Claims checked: 1. Failure modes: none apply: wording change only
- Vision fit: no VISION.md
<!-- refine-epic:end -->
