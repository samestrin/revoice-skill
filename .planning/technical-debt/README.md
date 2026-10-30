# Technical Debt Tracking

Small technical debt items found during development.

### [2026-10-30] From: epic 10

| Group | | Severity | File | Problem | Fix | Category | Est Minutes | Source | Attempts |
|-------|---|----------|------|---------|-----|----------|-------------|--------|----------|
| 1 | [ ] | LOW | skill/revoice/SKILL.md:5 | `Bash(test:*)` is listed twice in `allowed-tools`. | Remove the second `Bash(test:*)`. | docs | 5 | paperclip-cto | 0 |

### [2026-10-29] From: epic 4

| Group | | Severity | File | Problem | Fix | Category | Est Minutes | Source | Attempts |
|-------|---|----------|------|---------|-----|----------|-------------|--------|----------|
| 1 | [/] | LOW | skill/revoice/tests/test_plugin_manifest.py:99 | Two blank lines sit between methods inside `PluginJsonTest`, before `test_icon_is_a_square_png_in_range`. | Remove one blank line. → epic 11 | style | 2 | paperclip-cto | 0 |

### [2026-10-29] From: epic 3

| Group | | Severity | File | Problem | Fix | Category | Est Minutes | Source | Attempts |
|-------|---|----------|------|---------|-----|----------|-------------|--------|----------|
| 2 | [/] | LOW | .gitignore:1 | `.claude/settings.local.json` is not ignored, so it shows up as untracked. | Add `.claude/settings.local.json` to `.gitignore`. → epic 12 | config | 5 | paperclip-reviewer | 0 |

## Stats

| Severity | Open | Deferred | Resolved |
|----------|------|----------|----------|
| CRITICAL | 0 | 0 | 0 |
| HIGH | 0 | 0 | 0 |
| MEDIUM | 0 | 0 | 0 |
| LOW | 1 | 2 | 0 |
