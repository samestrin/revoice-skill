# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- README install steps start with cloning the repository, and an Upgrading section documents the upgrade and uninstall commands for Windows and macOS/Linux.
- README "Getting an API key" section: sign up at yourvoice.dev (250 free credits), create a key on the dashboard, save it to `~/.config/revoice/api-key`; notes that only `--build` uses it, that only the chosen samples leave the machine, and gives the work-folder delete commands. The requirements note now says only `--sync` needs PyYAML.
- `extract-samples.py --max-samples` (default 200, `0` = no cap) keeps the longest samples, so `--build` reads a bounded number of emails on a large mailbox.

### Changed

- `build.md` phase 4 now runs `review-samples.py --author "<Name>"` locally and reports the KEEP/DROP counts and top reasons; the API error handling and the Claude fallback are gone. Phase 6 tells Claude to set aside any kept sample that is clearly not the author's own voice or language, and to say so in the report.
- `--build` now reviews the extracted samples through the text analysis API (`review-samples.py`, new phase 4) instead of Claude reading every sample; Claude reads only the samples the profile is built from. If the API review fails, an opt-in Claude review is offered as a fallback, with a clear note that the samples then go to Claude's model provider.
- README updated to match: the "What leaves your machine" paragraph says the API gets every extracted sample for review (including the ones it drops) and that Claude reads only the 15 (`--top`) profile samples; the "How it works" steps, the build walkthrough and the "Running the steps by hand" order now name the API review and `review-samples.py`; and the API key section says a build charges credits per text sent. The README no longer states the review engine, the per-request credit cost, or that the 250 free credits cover a build — those are undecided in the API — and points to the API's docs for cost instead.

### Changed

- The example voice's fictional person is now "Alex Example" (was "Sam Example"), so it no longer reads as a real person's voice.

### Fixed

- README now says the extracted samples go to Claude's model provider during `--build` (Claude reads them to pick the best), and that the text analysis API gets the reference set of other senders' emails as well as the chosen samples.
- `/revoice --voice=<slug>` now rewrites on a fresh install with no `~/.config/revoice/config.yaml` (no default audience, relative paths from the current folder), so `/revoice --voice=example <text>` works straight after install. Without `--voice`, and for `sb:` paths and `--sync`, it still stops and asks for the config. README install step shows the example command.

## [0.1.0] - 2026-10-26

### Added

- `/revoice` rewrites text in a voice profile, with `--voice`, `--audience`, `--template` and `--output-path`.
- `--sync` pulls voice profiles from SilverBullet.
- `--build` walks you through building a voice profile from an email export.
- A closing grammar pass and a cap on signature phrases.
- MIT `LICENSE`.
