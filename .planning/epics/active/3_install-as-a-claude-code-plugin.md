# Epic Plan 3: Install as a Claude Code plugin

- **Estimated time**: 1–2 days
- **Last modified**: 2026-10-28 (written by Sam with Claude Code; not yet refined)
- **Tasks/Components**: 5/3
- **Components, counted by top-level path — three:**
  - `.claude-plugin/` — new `plugin.json` and `marketplace.json`
  - `skill/revoice/` (moves to `skills/revoice/` if the plugin layout requires it) — `SKILL.md`, `build.md`, `sync.py`, the build helpers, tests
  - root — `README.md`, `CHANGELOG.md`
- **Base branch: `main`.** Every PR targets `main`.
- **Depends on:** epic 2.1 merged (it replaced epic 2; both edit `skill/revoice/build.md` and the README).

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
3. **The short command keeps working, on one condition.** Plugin skills are namespaced (`/revoice:revoice`), but a plugin skill whose `SKILL.md` has a `name:` field also answers to the bare name when no other command uses it. Tested 2026-10-27 on Claude Code 2.1.311 with `claude -p --plugin-dir`: a plugin and skill both named `zzsame` ran on `/zzsame`; a skill with `name: zzhello` ran on `/zzhello` and `/zzplug:zzhello`; a skill without a `name:` field did not answer to its bare name. `SKILL.md` already has `name: revoice`, so `/revoice` keeps working. The catch: a leftover copy-folder install at `~/.claude/skills/revoice` takes the bare name, so the README tells anyone who switches to remove it after moving their voice files.
4. **No migration code.** revoice has no users yet (owner, 2026-10-28), so there is no copy-folder install to migrate except the owner's own. The owner moves their voice files by hand once. The plan therefore has no automatic migration task.

## Tasks (canonical)

- **T1** — Plugin and marketplace manifests per the current Claude Code plugin docs (name `revoice`, version from `CHANGELOG.md`, description, author, license MIT, homepage); move the skill folder only if the plugin layout requires `skills/<name>/` · `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `skill/revoice/` · depends: none · success: `claude plugin validate .` (or the documented equivalent) passes, and the tests still find the skill
- **T2** — Voices out of the skill folder: `SKILL.md` and `sync.py` read and write `~/.config/revoice/voices/`; `example.md` is read from the plugin when no user voice of that name exists · `skill/revoice/SKILL.md`, `skill/revoice/sync.py`, tests · depends: T1 · success: tests show sync writes only under `~/.config/revoice/voices/` and the example voice still resolves
- **T3** — Replace every hard-coded `~/.claude/skills/revoice/` with the plugin root variable, with the copy-folder path as fallback, including `allowed-tools` · `skill/revoice/SKILL.md`, `skill/revoice/build.md`, tests · depends: T1 · success: a test fails on any remaining hard-coded install path, and a test fails if `SKILL.md` loses its `name: revoice` field (it keeps the bare `/revoice` command); `test_skill_md.py` still passes
- **T4** — README and CHANGELOG: the two plugin commands as the main install, update and uninstall through `/plugin`, the copy-folder install as the second option, where voices live now (`~/.config/revoice/voices/`), a short note that someone switching from the copy-folder install moves their voice files there and removes `~/.claude/skills/revoice/` (it takes the bare `/revoice` name), and `/revoice` as the command · `README.md`, `CHANGELOG.md` · depends: T2, T3 · success: `test_readme_claims.py` covers the new install section
- **T5** — Clean-machine check, same as epic 1's T4/T6: in a fresh `node:24` container with Claude Code, run the two commands, then `/revoice --voice=example <text>` (the bare command, not `/revoice:revoice`); then run `/plugin` update and confirm a voice file in `~/.config/revoice/voices/` survives · README (fixes only) · depends: T4 · success: (manual) Trigger: the owner runs both checks and records the output on the card

## Acceptance criteria

- [ ] `/plugin marketplace add samestrin/revoice-skill` then `/plugin install revoice@revoice-skill` installs a working skill on a clean machine. (manual, T5)
- [ ] Updating the plugin never deletes a user's voice files.
- [ ] No hard-coded `~/.claude/skills/revoice/` path remains outside the fallback.
- [ ] `/revoice` (bare) runs the plugin's skill on a clean machine; `/revoice:revoice` also works.
- [ ] The README shows the plugin install first, the copy-folder install second, and `/revoice` as the command.
- [ ] CI is green.

## Open questions

None. (The command-name question was settled by the 2026-10-27 test above.)
