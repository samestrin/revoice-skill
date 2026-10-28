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

- **T1** — Plugin and marketplace manifests per the current Claude Code plugin docs (name `revoice`, version from `CHANGELOG.md`, description, author, license MIT, homepage); move the skill folder only if the plugin layout requires `skills/<name>/` · `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `skill/revoice/` · depends: none · tier: senior · success: `claude plugin validate .` (or the documented equivalent) passes, and the tests still find the skill
- **T2** — Voices out of the skill folder: `SKILL.md`, `build.md` (phase 6 saves to `SKILL/assets/<slug>.md`, line 92; line 108 names `assets/`) and `sync.py` read and write `~/.config/revoice/voices/`; `example.md` is read from the plugin when no user voice of that name exists · `skill/revoice/SKILL.md`, `skill/revoice/build.md`, `skill/revoice/sync.py`, tests · depends: T1 · tier: senior · success: tests show sync writes only under `~/.config/revoice/voices/` and the example voice still resolves
- **T3** — Replace every hard-coded `~/.claude/skills/revoice/` with the plugin root variable, with the copy-folder path as fallback, including `allowed-tools` · `skill/revoice/SKILL.md`, `skill/revoice/build.md`, tests · depends: T2 · tier: senior · success: a test fails on any remaining hard-coded install path, and a test fails if `SKILL.md` loses its `name: revoice` field (it keeps the bare `/revoice` command); `test_skill_md.py` still passes
- **T4** — README and CHANGELOG: the two plugin commands as the main install, update and uninstall through `/plugin`, the copy-folder install as the second option, where voices live now (`~/.config/revoice/voices/`), a short note that someone switching from the copy-folder install moves their voice files there and removes `~/.claude/skills/revoice/` (it takes the bare `/revoice` name), and `/revoice` as the command · `README.md`, `CHANGELOG.md` · depends: T3 · tier: junior · success: `test_readme_claims.py` covers the new install section
- **T5** — Clean-machine check, same as epic 1's T4/T6: in a fresh `node:24` container with Claude Code, run the two commands, then `/revoice --voice=example <text>` (the bare command, not `/revoice:revoice`); then run `/plugin` update and confirm a voice file in `~/.config/revoice/voices/` survives · README (fixes only) · depends: T4 · tier: junior · success: (manual) Trigger: the owner runs both checks and records the output on the card

## Acceptance criteria

- [ ] `/plugin marketplace add samestrin/revoice-skill` then `/plugin install revoice@revoice-skill` installs a working skill on a clean machine. (manual, T5)
- [ ] Updating the plugin never deletes a user's voice files.
- [ ] No hard-coded `~/.claude/skills/revoice/` path remains outside the fallback.
- [ ] `/revoice` (bare) runs the plugin's skill on a clean machine; `/revoice:revoice` also works.
- [ ] The README shows the plugin install first, the copy-folder install second, and `/revoice` as the command.
- [ ] CI is green.

## Open questions

None. (The command-name question was settled by the 2026-10-27 test above.)

<!-- refine-epic:begin -->
## Refinements (2026-10-28)
### Auto-applied corrections (4)
1. Why #2: `~/.claude/skills/revoice/` appears 8 times in `SKILL.md` (7: lines 5 twice, 16, 17, 18, 43, 114) and `build.md` (1: line 5), not 13. Evidence: `grep -o` on `origin/main` at 1b8cba3.
2. T2 now lists `skill/revoice/build.md`: line 92 saves the built voice to `SKILL/assets/<slug>.md` and line 108 tells the user to put overlays in `assets/`; without it `--build` would write voices into the plugin folder, which an update replaces.
3. Dependencies: T3 depends on T2 (both edit `SKILL.md` and `build.md`; parallel edits conflict). T1 follows through T2 so it is dropped from T3. T4 depends on T3 only (T2 follows through T3).
4. Added `tier:` to all five tasks (T1-T3 senior: layout decision, data-loss risk, permission semantics; T4-T5 junior).
### Items needing user confirmation (3)
1. T1: where the skill lives in the plugin (move to `skills/revoice/` or keep `skill/revoice/` via the manifest).
2. T3: the path variable and the path after it differ between plugin and copy-folder installs.
3. T1: `claude plugin validate` is not run by CI.
### Advisory observations (3)
1. Version has three homes (CHANGELOG, `SKILL.md` `metadata.version` "0.1.0", and the new `plugin.json`); T1 should say which is the source and a test should keep them equal. `/plugin update` does nothing for users unless the version changes.
2. The marketplace entry will use the repo root as the plugin, so the install cache holds `.planning/` and the tests too. Harmless, but the plan does not say so.
3. Open technical-debt rows touch `CHANGELOG.md` (Unreleased has two `### Changed` headings); T4 edits the same file and may fold them in. Claude Code here is 2.1.306; the plan's name-resolution test was on 2.1.311, which I could not re-run.
### Verification context
- Code repo: revoice-skill at 1b8cba3. Plan written: 2026-10-28. Commits reviewed since: 0 (epic 2.1 shipped before; its build.md and README changes are in the checked files).
- Tasks: 5 (limit 7). Components: 3 (limit 3): `.claude-plugin/`, `skill/revoice/`, root.
- Claims checked: 14. Discovery searches: `claude/skills`, `assets`, `ASSETS`, `CLAUDE_PLUGIN_ROOT` in the installed `claude` binary (also `CLAUDE_SKILL_DIR`, `CLAUDE_PLUGIN_DATA` exist there), CI workflow, test loaders.
- Failure modes: update stopping halfway (voices live outside the plugin folder, so safe once T2 covers `build.md`); what is published (`.gitignore` keeps voice files out, and must follow any folder move); other forms of input and network routes: none apply, no route, login or money.
- Vision fit: no VISION.md
<!-- refine-epic:end -->
