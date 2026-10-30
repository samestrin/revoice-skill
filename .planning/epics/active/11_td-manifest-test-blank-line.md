# Epic Plan 11: plugin manifest test blank line

- **Source:** technical-debt rows (.planning/technical-debt/README.md): skill/revoice/tests/test_plugin_manifest.py:99
- **File scope:** skill/revoice/tests/test_plugin_manifest.py
- **Runs in parallel:** yes. On 2026-10-30, no file in the scope was in another open epic or open PR.
- **Base branch: `main`.** Every PR targets `main`.
- **Estimated time**: under 1 day
- **Last modified**: 2026-10-30 (written by the CTO from technical-debt rows; not yet refined)

## Why

Two blank lines sit between methods inside `PluginJsonTest`.

## Current State

`test_plugin_manifest.py` has two blank lines before `test_icon_is_a_square_png_in_range` (~line 99). Style only; no test can fail first.

## Proposed Solution

Fix the row with a failing test first where a test can fail. No behaviour change beyond what the row asks.

## Scope

Only the files in the File scope line. `CHANGELOG.md` and the technical-debt list are not edited by this epic (`close-epic` edits the list).

## Tasks (canonical)

- **T1** — Remove one of the two blank lines before `test_icon_is_a_square_png_in_range` · `skill/revoice/tests/test_plugin_manifest.py` · depends: none · tier: intern · success: one blank line separates the methods and the test count is unchanged; never by weakening or deleting a test

## Acceptance criteria

- [ ] One blank line separates the methods in `PluginJsonTest`.
- [ ] CI is green.

## Repo rules

- Never run `deploy.sh`; never write to `~/.claude/skills/` or `~/.agents/skills/`.
- Every task ends green on `python3 -m unittest discover -s skill/revoice/tests`, never by weakening or deleting a test.
