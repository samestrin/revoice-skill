# Technical Debt Tracking

Small technical debt items found during development.

### [2026-10-28] From: epic 2.1

| Group | | Severity | File | Problem | Fix | Category | Est Minutes | Source | Attempts |
|-------|---|----------|------|---------|-----|----------|-------------|--------|----------|
| 1 | [ ] | LOW | CHANGELOG.md:19 | Unreleased has two `### Changed` headings. | Merge the second entry into the first `### Changed` block. | docs | 5 | paperclip-reviewer | 0 |
| 1 | [ ] | LOW | CHANGELOG.md:25 | The Unreleased `### Fixed` entry still says Claude reads the extracted samples "to pick the best"; README.md:140 now says the review is local and Claude reads only the 15 `--top` profile samples. | Reword that clause to match the README. | docs | 10 | paperclip-reviewer | 0 |
| 2 | [ ] | LOW | skill/revoice/build/review-samples.py:ENGLISH_SHARE | The language check only knows English function words, so a non-English author gets no language filter. | Add per-language word lists if needed. | feature | 30 | paperclip-builder | 0 |
| 2 | [ ] | LOW | skill/revoice/build/review-samples.py:TABLE | The TABLE regex `\|.*\|?` matches any line containing one pipe, so a prose line with `\|` counts as table-like. | Require two pipes. | correctness | 10 | paperclip-cto | 0 |
