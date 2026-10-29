# Technical Debt Tracking

Small technical debt items found during development.

### [2026-10-29] From: refine/epic-5

| Group | | Severity | File | Problem | Fix | Category | Est Minutes | Source | Attempts |
|-------|---|----------|------|---------|-----|----------|-------------|--------|----------|
| 1 | [ ] | LOW | skill/revoice/build/review-samples.py:FUNCTION_WORDS | Epic 5 adds a language filter for German only; authors writing in Spanish, French or other languages still get no filter for stray off-language samples. | Add function-word lists for the further languages. | feature | 20 | paperclip-cto | 0 |

### [2026-10-29] From: epic 4

| Group | | Severity | File | Problem | Fix | Category | Est Minutes | Source | Attempts |
|-------|---|----------|------|---------|-----|----------|-------------|--------|----------|
| 1 | [ ] | LOW | skill/revoice/tests/test_plugin_manifest.py:99 | Two blank lines sit between methods inside `PluginJsonTest`, before `test_icon_is_a_square_png_in_range`. | Remove one blank line. | style | 2 | paperclip-cto | 0 |

### [2026-10-29] From: epic 3

| Group | | Severity | File | Problem | Fix | Category | Est Minutes | Source | Attempts |
|-------|---|----------|------|---------|-----|----------|-------------|--------|----------|
| 2 | [ ] | LOW | .gitignore:1 | `.claude/settings.local.json` is not ignored, so it shows up as untracked. | Add `.claude/settings.local.json` to `.gitignore`. | config | 5 | paperclip-reviewer | 0 |
| 3 | [ ] | LOW | CHANGELOG.md:17 | The Unreleased `Voice profiles now live` entry is longer than the one-or-two-sentence limit. | Shorten it to two sentences. | docs | 10 | paperclip-reviewer | 0 |
| 3 | [ ] | LOW | skill/revoice/SKILL.md:115 | `python3 ${CLAUDE_SKILL_DIR}/sync.py` is unquoted, and the `allowed-tools` pattern matches the unquoted form, so a skill path with spaces breaks. | Quote the path in the command and in `allowed-tools`. | correctness | 15 | paperclip-reviewer | 0 |

### [2026-10-28] From: epic 2.1

| Group | | Severity | File | Problem | Fix | Category | Est Minutes | Source | Attempts |
|-------|---|----------|------|---------|-----|----------|-------------|--------|----------|
| 1 | [ ] | LOW | CHANGELOG.md:19 | Unreleased has two `### Changed` headings. | Merge the second entry into the first `### Changed` block. | docs | 5 | paperclip-reviewer | 0 |
| 1 | [ ] | LOW | CHANGELOG.md:25 | The Unreleased `### Fixed` entry still says Claude reads the extracted samples "to pick the best"; README.md:140 now says the review is local and Claude reads only the 15 `--top` profile samples. | Reword that clause to match the README. | docs | 10 | paperclip-reviewer | 0 |
| 2 | [/] | LOW | skill/revoice/build/review-samples.py:ENGLISH_SHARE | The language check only knows English function words, so a non-English author gets no language filter. | Add per-language word lists if needed. → epic 5 | feature | 30 | paperclip-builder | 0 |
| 2 | [/] | LOW | skill/revoice/build/review-samples.py:TABLE | The TABLE regex `\|.*\|?` matches any line containing one pipe, so a prose line with `\|` counts as table-like. | Require two pipes. → epic 5 | correctness | 10 | paperclip-cto | 0 |

## Stats

| Severity | Open | Deferred | Resolved |
|----------|------|----------|----------|
| CRITICAL | 0 | 0 | 0 |
| HIGH | 0 | 0 | 0 |
| MEDIUM | 0 | 0 | 0 |
| LOW | 6 | 2 | 0 |