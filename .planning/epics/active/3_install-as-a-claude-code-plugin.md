# Epic Plan 3: Install as a Claude Code plugin

- **Estimated time**: 1–2 days
- **Last modified**: 2026-10-27 (written by Sam with Claude Code; not yet refined)
- **Tasks/Components**: 6/3
- **Components, counted by top-level path — three:**
  - `.claude-plugin/` — new `plugin.json` and `marketplace.json`
  - `skill/revoice/` (moves to `skills/revoice/` if the plugin layout requires it) — `SKILL.md`, `build.md`, `sync.py`, the build helpers, tests
  - root — `README.md`, `CHANGELOG.md`
- **Base branch: `main`.** Every PR targets `main`.
- **Depends on:** epic 2 merged (both edit `skill/revoice/build.md` and the README).

## Goal

A user installs and updates revoice from inside Claude Code, with no git clone and no copying:

```
/plugin marketplace add samestrin/revoice-skill
/plugin install revoice@revoice-skill
```

Copying the folder (today's install, epic 1 T4) stays documented as the second option. Owner decision 2026-10-27; epic 1 had kept the copy-folder install and left the plugin for later (its open question 3).

## Why this is more than packaging

1. **User data lives inside the skill folder today.** Voice profiles are `assets/<slug>.md` next to `SKILL.md`, and `sync.py` writes there (`ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")`). A plugin's folder belongs to Claude Code and is replaced on update, so a user's voice files would be lost. They move to `~/.config/revoice/voices/` (the config and API key already live in `~/.config/revoice/`). `example.md` ships with the plugin and stays inside it.
2. **The install path is hard-coded.** `SKILL.md` and `build.md` name `~/.claude/skills/revoice/` 13 times, including the `allowed-tools` entry for `sync.py`. Under a plugin those paths are wrong. Use the plugin root variable Claude Code provides for plugin files (check the current docs for its exact name and where it is expanded, including in `allowed-tools`), and fall back to the copy-folder path so both installs work.
3. **The command name may change.** Plugin skills are namespaced by plugin. Check the current docs and a real install: if the slash command becomes `/revoice:revoice`, the README and every example say so; natural-language use ("revoice this...") must keep working.

## Tasks (canonical)

- **T1** — Plugin and marketplace manifests per the current Claude Code plugin docs (name `revoice`, version from `CHANGELOG.md`, description, author, license MIT, homepage); move the skill folder only if the plugin layout requires `skills/<name>/` · `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `skill/revoice/` · depends: none · success: `claude plugin validate .` (or the documented equivalent) passes, and the tests still find the skill
- **T2** — Voices out of the skill folder: `SKILL.md` and `sync.py` read and write `~/.config/revoice/voices/`; `example.md` is read from the plugin when no user voice of that name exists · `skill/revoice/SKILL.md`, `skill/revoice/sync.py`, tests · depends: T1 · success: tests show sync writes only under `~/.config/revoice/voices/` and the example voice still resolves
- **T3** — One-time migration: when `~/.config/revoice/voices/` is empty and the old `~/.claude/skills/revoice/assets/` has voice files other than `example.md` and `README.md`, copy them over (never move or delete) and say so once · `skill/revoice/SKILL.md` (or a small helper), tests · depends: T2 · success: a test with a fake old assets folder ends with the files in both places and one notice
- **T4** — Replace every hard-coded `~/.claude/skills/revoice/` with the plugin root variable, with the copy-folder path as fallback, including `allowed-tools` · `skill/revoice/SKILL.md`, `skill/revoice/build.md`, tests · depends: T1 · success: a test fails on any remaining hard-coded install path; `test_skill_md.py` still passes
- **T5** — README and CHANGELOG: the two plugin commands as the main install, update and uninstall through `/plugin`, the copy-folder install as the second option, where voices live now, and the real command name · `README.md`, `CHANGELOG.md` · depends: T2-T4 · success: `test_readme_claims.py` covers the new install section
- **T6** — Clean-machine check, same as epic 1's T4/T6: in a fresh `node:24` container with Claude Code, run the two commands, then `/revoice --voice=example <text>`; then upgrade from a copy-folder install that has a voice file and confirm the voice survives · README (fixes only) · depends: T5 · success: (manual) Trigger: the owner runs both checks and records the output on the card

## Acceptance criteria

- [ ] `/plugin marketplace add samestrin/revoice-skill` then `/plugin install revoice@revoice-skill` installs a working skill on a clean machine. (manual, T6)
- [ ] Updating the plugin never deletes a user's voice files.
- [ ] An existing copy-folder user's voices are copied to `~/.config/revoice/voices/` once, and the old folder is left untouched.
- [ ] No hard-coded `~/.claude/skills/revoice/` path remains outside the fallback.
- [ ] The README shows the plugin install first, the copy-folder install second, and the real command name.
- [ ] CI is green.

## Open questions

1. If the command becomes `/revoice:revoice`, is that acceptable, or should the plugin be named so the command reads better? Check what Claude Code allows before asking.
