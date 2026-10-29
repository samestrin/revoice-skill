# Epic Plan 4: Plugin manifest tests and icon

- **Source:** technical-debt rows (.planning/technical-debt/README.md): skill/revoice/tests/test_plugin_manifest.py:28, skill/revoice/tests/test_plugin_manifest.py:80, .claude-plugin/plugin.json:1
- **File scope:** skill/revoice/tests/test_plugin_manifest.py, .claude-plugin/plugin.json, .claude-plugin/icon.png (new)
- **Runs in parallel:** yes. On 2026-10-29, no file in the scope was in another open epic or open PR.
- **Base branch: `main`.** Every PR targets `main`.
- **Estimated time**: under 1 day
- **Last modified**: 2026-10-29 (written by the CTO from technical-debt rows; not yet refined)

## Why

Three LOW rows left by epic 3's reviews: the manifest test helpers have unexercised guards, one test repeats others, and the plugin has no icon (`ICON_MISSING` from `claude plugin validate`).

## Current State

`test_plugin_manifest.py` has helpers `newest_released_version` and `skill_md_version` that raise `AssertionError` in three guard branches (lines 28, 36, 41) that no test feeds bad input. `test_skill_md_version_reads_quoted_value` (line 87) only asserts a semver regex, which the version-match tests already prove. `.claude-plugin/plugin.json` has no icon field.

## Proposed Solution

Fix each row with a failing test first. No behaviour change beyond what the rows ask.

## Scope

Only the files in the File scope line. `CHANGELOG.md` and the technical-debt list are not edited by this epic (`close-epic` edits the list).

## Tasks (canonical)

- **T1** — Guard tests: make the helpers take the text/path as a parameter (or accept a root override) so each of the three `AssertionError` guards is hit by a test with bad input (no released heading, no frontmatter, no `metadata.version`); drop `test_skill_md_version_reads_quoted_value` or fold its assertion into the version-match tests · `skill/revoice/tests/test_plugin_manifest.py` · depends: none · tier: junior · success: three new tests fail before the helper change and pass after; the redundant test is gone with no loss of assertion; never by weakening or deleting a test beyond the one named row
- **T2** — Icon: add an icon file to `.claude-plugin/` and a square PNG, 512 to 2048 px per side and under 2 MB (the `claude plugin validate` limits; SVG and WebP are not accepted), generated with the standard library only; reference it with an `icon` key in `plugin.json`; extend the manifest test to check the referenced file exists, is a PNG, and its IHDR size is square and within 512-2048 px (read with `struct`, no new dependency) · `.claude-plugin/plugin.json`, `.claude-plugin/icon.png`, `skill/revoice/tests/test_plugin_manifest.py` · depends: T1 · tier: junior · success: the new test fails without the file or with a wrong-size file, and `claude plugin validate . --strict` no longer reports `ICON_MISSING` (output pasted on the PR); never by weakening or deleting a test

## Acceptance criteria

- [x] Each of the three guards has a test that feeds it bad input. _(verified 2026-10-29: `HelpersTest.test_changelog_without_released_heading`, `test_skill_md_without_frontmatter`, `test_skill_md_without_metadata_version` in skill/revoice/tests/test_plugin_manifest.py, each feeding one guard bad text; CI green on b4b7eb4 (Python 3.10 and 3.11))_
- [x] The repeated test is dropped or folded in. _(verified 2026-10-29: `test_skill_md_version_reads_quoted_value` is gone; its regex assertion is now in `test_version_matches_skill_md` (test_plugin_manifest.py:94-97))_
- [x] `plugin.json` references a square PNG icon (512-2048 px, under 2 MB) that exists, and a test pins it; `claude plugin validate . --strict` no longer reports `ICON_MISSING`. _(verified 2026-10-29: `.claude-plugin/plugin.json:13` has `"icon": ".claude-plugin/icon.png"`; `test_icon_is_a_square_png_in_range` and `test_icon_rejects_bad_files` pin it (green in CI on b4b7eb4); `claude plugin validate . --strict` run on main 2026-10-29: "Validation passed", nothing to report)_
- [x] CI is green. _(verified 2026-10-29: CI run on main at b4b7eb4: success)_

## Repo rules

- Never run `deploy.sh`; never write to `~/.claude/skills/` or `~/.agents/skills/`.
- Every task ends green on `python3 -m unittest discover -s skill/revoice/tests`, never by weakening or deleting a test.

<!-- refine-epic:begin -->
## Refinements (2026-10-29)
### Auto-applied corrections (3)
1. Plan said "line ~80" for `test_skill_md_version_reads_quoted_value`; it is at line 87 of `test_plugin_manifest.py` (the debt row's 80 has drifted). Guards at 28, 36, 41 are exact.
2. T2 now carries the icon format the validator demands (`claude plugin validate . --strict` run today on main: ICON_MISSING says square PNG, 512-2048 px, under 2 MB, no SVG/WebP), and the test checks size via the PNG header, so a wrong-size file cannot pass.
3. AC3 now states the format and the validate result.
### Items needing user confirmation (0)
### Advisory observations (2)
- The validator notes the icon may become the listing icon only the first time the plugin is submitted; a later change does not update it. The artwork is a taste call, so the builder should keep it plain.
- `claude plugin validate` is not in CI, so its result is proven by the output pasted on the PR (the plan says so).
### Verification context
- Code repo: revoice-skill at e645a86. Plan written: 2026-10-29. Commits reviewed since: 0
- Tasks: 2 (limit 7). Components: 2 (limit 3): skill/revoice/tests, .claude-plugin
- Claims checked: 6. Discovery searches: test_plugin_manifest.py, plugin.json, validate run, technical-debt rows
- Parallel check: File scope (test_plugin_manifest.py, plugin.json, icon.png) shares no file with plans 5 (review-samples.py, test_review_samples.py) or 6 (sync.py, test_sync.py), no open PRs, and no open epic other than sibling refines EST-3208/3209. Scope not widened.
- Failure modes: none apply: a test file and a static image, no route, data, money or deploy.
- Vision fit: no VISION.md
<!-- refine-epic:end -->
