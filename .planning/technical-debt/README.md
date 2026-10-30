# Technical Debt Tracking

Small technical debt items found during development.

### [2026-10-29] From: epic 5

| Group | | Severity | File | Problem | Fix | Category | Est Minutes | Source | Attempts |
|-------|---|----------|------|---------|-----|----------|-------------|--------|----------|
| 1 | [/] | LOW | skill/revoice/build/review-samples.py:54 | `ENGLISH_SHARE` and `ENGLISH_AUTHOR_SHARE` keep English names although they now apply to the author's language (English or German). | Rename them to `LANGUAGE_SHARE` and `LANGUAGE_AUTHOR_SHARE`, updating the tests. → epic 8 | style | 10 | paperclip-cto | 0 |

### [2026-10-30] From: EST-3330-refine-revoice-skill-epic-9-skill-md-quoted-sync-path

| Group | | Severity | File | Problem | Fix | Category | Est Minutes | Source | Attempts |
|-------|---|----------|------|---------|-----|----------|-------------|--------|----------|
| 1 | [ ] | LOW | skill/revoice/SKILL.md:5 | The `allowed-tools` patterns `Bash(python3 ${CLAUDE_SKILL_DIR}/sync.py:*)` and `Bash(python ${CLAUDE_SKILL_DIR}/sync.py:*)` are redundant with `Bash(python:*)` and `Bash(python3:*)` on the same line. | Delete the two sync-specific patterns and the matching assertions in test_skill_md.py (~178-179). | docs | 10 | paperclip-cto | 0 |

### [2026-10-29] From: refine/epic-5

| Group | | Severity | File | Problem | Fix | Category | Est Minutes | Source | Attempts |
|-------|---|----------|------|---------|-----|----------|-------------|--------|----------|
| 1 | [/] | LOW | skill/revoice/build/review-samples.py:FUNCTION_WORDS | Epic 5 adds a language filter for German only; authors writing in Spanish, French or other languages still get no filter for stray off-language samples. | Add function-word lists for the further languages. → epic 8 | feature | 20 | paperclip-cto | 0 |

### [2026-10-29] From: epic 4

| Group | | Severity | File | Problem | Fix | Category | Est Minutes | Source | Attempts |
|-------|---|----------|------|---------|-----|----------|-------------|--------|----------|
| 1 | [ ] | LOW | skill/revoice/tests/test_plugin_manifest.py:99 | Two blank lines sit between methods inside `PluginJsonTest`, before `test_icon_is_a_square_png_in_range`. | Remove one blank line. | style | 2 | paperclip-cto | 0 |

### [2026-10-29] From: epic 3

| Group | | Severity | File | Problem | Fix | Category | Est Minutes | Source | Attempts |
|-------|---|----------|------|---------|-----|----------|-------------|--------|----------|
| 2 | [ ] | LOW | .gitignore:1 | `.claude/settings.local.json` is not ignored, so it shows up as untracked. | Add `.claude/settings.local.json` to `.gitignore`. | config | 5 | paperclip-reviewer | 0 |
| 3 | [/] | LOW | CHANGELOG.md:17 | The Unreleased `Voice profiles now live` entry is longer than the one-or-two-sentence limit. | Shorten it to two sentences. → epic 7 | docs | 10 | paperclip-reviewer | 0 |

### [2026-10-28] From: epic 2.1

| Group | | Severity | File | Problem | Fix | Category | Est Minutes | Source | Attempts |
|-------|---|----------|------|---------|-----|----------|-------------|--------|----------|
| 1 | [/] | LOW | CHANGELOG.md:19 | Unreleased has two `### Changed` headings. | Merge the second entry into the first `### Changed` block. → epic 7 | docs | 5 | paperclip-reviewer | 0 |
| 1 | [/] | LOW | CHANGELOG.md:25 | The Unreleased `### Fixed` entry still says Claude reads the extracted samples "to pick the best"; README.md:140 now says the review is local and Claude reads only the 15 `--top` profile samples. | Reword that clause to match the README. → epic 7 | docs | 10 | paperclip-reviewer | 0 |

## Stats

| Severity | Open | Deferred | Resolved |
|----------|------|----------|----------|
| CRITICAL | 0 | 0 | 0 |
| HIGH | 0 | 0 | 0 |
| MEDIUM | 0 | 0 | 0 |
| LOW | 3 | 5 | 0 |