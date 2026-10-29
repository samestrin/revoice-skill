# Epic Plan 5: review-samples language filter and table regex

- **Source:** technical-debt rows (.planning/technical-debt/README.md): skill/revoice/build/review-samples.py:ENGLISH_SHARE, skill/revoice/build/review-samples.py:TABLE
- **File scope:** skill/revoice/build/review-samples.py, skill/revoice/tests/test_review_samples.py
- **Runs in parallel:** yes. On 2026-10-29, no file in the scope was in another open epic or open PR.
- **Base branch: `main`.** Every PR targets `main`.
- **Estimated time**: under 1 day
- **Last modified**: 2026-10-29 (written by the CTO from technical-debt rows; not yet refined)

## Why

Two LOW rows from epic 2.1 in the local sample review: the TABLE regex over-matches and the language filter only knows English.

## Current State

`review-samples.py` line ~80: `TABLE = re.compile(r"\|.*\|?|\t\S.*\t|\S {3,}\S.* {3,}\S")` matches any line with one pipe, so prose containing `|` counts as table-like. Line ~54: `ENGLISH_SHARE = 0.12` and the check near line 263 use English function words only, so a non-English author gets no language filter. The refine must confirm both against `main` today.

## Proposed Solution

Fix each row with a failing test first. No behaviour change beyond what the rows ask.

## Scope

Only the files in the File scope line. `CHANGELOG.md` and the technical-debt list are not edited by this epic (`close-epic` edits the list).

## Tasks (canonical)

- **T1** — TABLE: require two pipes (`\|.*\|`); add a failing test where a prose line with one `|` is not table-like and a two-pipe row is · `skill/revoice/build/review-samples.py`, `skill/revoice/tests/test_review_samples.py` · depends: none · tier: junior · success: the new test fails before and passes after; never by weakening or deleting a test
- **T2** — Language: add per-language function-word lists (at least one non-English language chosen in the refine) with detection of the dominant language of the author's samples, keeping English behaviour unchanged; failing test first · `skill/revoice/build/review-samples.py`, `skill/revoice/tests/test_review_samples.py` · depends: T1 · tier: senior · success: a non-English sample set is filtered by its own language and English tests still pass; never by weakening or deleting a test. If the refine judges this row not worth the size, it may drop T2 and leave the row open.

## Acceptance criteria

- [ ] A prose line with a single `|` is not counted as table-like.
- [ ] A non-English author's samples get a language filter.
- [ ] CI is green.

## Repo rules

- Never run `deploy.sh`; never write to `~/.claude/skills/` or `~/.agents/skills/`.
- Every task ends green on `python3 -m unittest discover -s skill/revoice/tests`, never by weakening or deleting a test.

<!-- refine-epic:begin -->
## Refinements (2026-10-29)
### Auto-applied corrections (0)
### Items needing user confirmation (2)
1. **T2 scope: which languages, and is it worth doing.** Current State is partly stale: `review()` (`skill/revoice/build/review-samples.py:247-250`) already follows the author's set. A set whose median English share is under `ENGLISH_AUTHOR_SHARE` runs no language check, and `test_other_language_follows_the_authors_set` (`skill/revoice/tests/test_review_samples.py:213`) pins that a German-only set is kept. What is missing is only dropping stray off-language samples from a non-English author's set. T2 says "at least one non-English language chosen in the refine" and names none.
2. **T2 size and tier.** "Per-language word lists plus dominant-language detection" is open-ended; it adds a data table and changes `review()` and `english_share`. FUNCTION_WORDS is also used by `other_name` (line ~222) and must stay English.
### Advisory observations (2)
- T1 holds: `TABLE` at line 80 is `\|.*\|?`, so one pipe matches; `is_structured` (line 156) is its only user. The one-pipe case needs a line that is otherwise prose; `test_single_list_line_is_not_a_list` (line 159) is the pattern to follow.
- Parallel exception checked: File scope (`review-samples.py`, `test_review_samples.py`) shares no file with plan 4 (`test_plugin_manifest.py`, `.claude-plugin/*`) or plan 6 (`sync.py`, `test_sync.py`), and `gh pr list --state open` returned no PRs. No VISION.md in this repo.
### Verification context
- Code repo: revoice-skill at e645a86. Plan written: 2026-10-29. Commits reviewed since: 0 (file last changed in 9b3cbd5, before the plan)
- Tasks: 2 (limit 7). Components: 1 (limit 3): skill/revoice
- Claims checked: 6. Discovery searches: ENGLISH_SHARE, TABLE, english_share, FUNCTION_WORDS, test_review_samples language tests
- Failure modes: none apply: local offline text filtering, no network, login, money, deploy or client data
- Vision fit: no VISION.md
<!-- refine-epic:end -->
