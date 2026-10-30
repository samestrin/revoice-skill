# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- `review-samples.py` now recognises Spanish and French authors as well as English and German ones, so a stray sample in another language is dropped ("not in the author's language") from a Spanish or French author's set too. Only the words that tell Spanish and French apart count, so a French sample is not taken for Spanish or the other way round.
- Plugin icon: `.claude-plugin/icon.png` (512x512 PNG) referenced by an `icon` key in `plugin.json`, which clears `ICON_MISSING` from `claude plugin validate`. A test checks the file exists, is a PNG, and is square within 512-2048 px and under 2 MB.
- Claude Code plugin manifests: `.claude-plugin/plugin.json` (plugin `revoice`, version 0.1.0, skill loaded from `skill/`) and `.claude-plugin/marketplace.json` (marketplace `revoice-skill`), so the repo can be added as a plugin marketplace. A test keeps the plugin version equal to the newest released CHANGELOG version and `SKILL.md` `metadata.version`.
- README install steps start with cloning the repository, and an Upgrading section documents the upgrade and uninstall commands for Windows and macOS/Linux.
- README "Getting an API key" section: sign up at yourvoice.dev (250 free credits), create a key on the dashboard, save it to `~/.config/revoice/api-key`; notes that only `--build` uses it, that only the chosen samples leave the machine, and gives the work-folder delete commands. The requirements note now says only `--sync` needs PyYAML.
- `extract-samples.py --max-samples` (default 200, `0` = no cap) keeps the longest samples, so `--build` reads a bounded number of emails on a large mailbox.

### Changed

- Voice profiles now live in `~/.config/revoice/voices/`, outside the skill folder, so updating the skill (or the plugin) never deletes them: `--build` saves the new voice there, `--sync` writes there, and `/revoice` reads a voice from there first, then from the skill's own `assets/` (which now ships only `example.md`, so `--voice=example` still works). Move any voice files you kept in the skill's `assets/` folder to `~/.config/revoice/voices/`; `sync.py` refuses a voice slug that is not a plain file name.
- `SKILL.md` names its own folder with `${CLAUDE_SKILL_DIR}` instead of `~/.claude/skills/revoice/` (in the body and in `allowed-tools`), so the skill finds `build.md`, `sync.py` and the bundled voices whether it was installed as a plugin or by copying the folder. A test fails on any hard-coded install path, and on a `SKILL.md` without `name: revoice` (the field that keeps the bare `/revoice` command under a plugin).
- README: the plugin commands (`/plugin marketplace add samestrin/revoice-skill`, then `/plugin install revoice@revoice-skill`) are now the main install, with update and uninstall through `/plugin update` and `/plugin uninstall`; the copy-folder install stays as the second option. The README says voices live in `~/.config/revoice/voices/`, tells anyone switching from the copy-folder install to move their voice files there and delete `~/.claude/skills/revoice/` (a leftover copy takes the bare `/revoice` command), and keeps `/revoice` as the command. `test_readme_claims.py` covers the new install section.
- `--build` now reviews the extracted samples locally: `build.md` phase 4 runs `review-samples.py --author "<Name>"` on your machine and reports the KEEP/DROP counts and top reasons, with no network access. Phase 6 tells Claude to set aside any kept sample that is clearly not the author's own voice or language, and to say so in the report.
- README updated to match: the "What leaves your machine" paragraph says the KEEP/DROP review runs on your machine and sends nothing anywhere, that the API gets only the kept samples (up to the 200 extracted, in batches of 100) plus the reference set to build the profile, that Claude reads only the 15 (`--top`) profile samples, and that rewriting never touches the API; the "How it works" steps, the build walkthrough and the "Running the steps by hand" order say the review is local; and the API key section says a build charges credits per text sent. The README no longer states the review engine, the per-request credit cost, or that the 250 free credits cover a build — those are undecided in the API — and points to the API's docs for cost instead.
- The example voice's fictional person is now "Alex Example" (was "Sam Example"), so it no longer reads as a real person's voice.

### Fixed

- README now says the extracted samples go to the text analysis API during `--build` (along with the reference set of other senders' emails), and that Claude reads only the samples the profile is built from — 15 by default, `--top` if you run the steps by hand — which go to Claude's model provider.
- `/revoice --voice=<slug>` now rewrites on a fresh install with no `~/.config/revoice/config.yaml` (no default audience, relative paths from the current folder), so `/revoice --voice=example <text>` works straight after install. Without `--voice`, and for `sb:` paths and `--sync`, it still stops and asks for the config. README install step shows the example command.
- `SKILL.md` Step 6 quotes the sync script path (`python3 "${CLAUDE_SKILL_DIR}/sync.py"`), so `--sync` works when the skill is installed in a folder whose path has spaces.

## [0.1.0] - 2026-10-26

### Added

- `/revoice` rewrites text in a voice profile, with `--voice`, `--audience`, `--template` and `--output-path`.
- `--sync` pulls voice profiles from SilverBullet.
- `--build` walks you through building a voice profile from an email export.
- A closing grammar pass and a cap on signature phrases.
- MIT `LICENSE`.
