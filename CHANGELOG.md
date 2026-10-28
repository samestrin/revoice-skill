# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- README install steps start with cloning the repository, and an Upgrading section documents the upgrade and uninstall commands for Windows and macOS/Linux.
- README "Getting an API key" section: sign up at yourvoice.dev (250 free credits), create a key on the dashboard, save it to `~/.config/revoice/api-key`; notes that only `--build` uses it, that only the chosen samples leave the machine, and gives the work-folder delete commands. The requirements note now says only `--sync` needs PyYAML.
- `extract-samples.py --max-samples` (default 200, `0` = no cap) keeps the longest samples, so `--build` reads a bounded number of emails on a large mailbox.

### Changed

- `--build` now reviews the extracted samples locally: `build.md` phase 4 runs `review-samples.py --author "<Name>"` on your machine and reports the KEEP/DROP counts and top reasons, with no network access. Phase 6 tells Claude to set aside any kept sample that is clearly not the author's own voice or language, and to say so in the report.
- README updated to match: the "What leaves your machine" paragraph says the KEEP/DROP review runs on your machine and sends nothing anywhere, that the API gets only the kept samples (up to the 200 extracted, in batches of 100) plus the reference set to build the profile, that Claude reads only the 15 (`--top`) profile samples, and that rewriting never touches the API; the "How it works" steps, the build walkthrough and the "Running the steps by hand" order say the review is local; and the API key section says a build charges credits per text sent. The README no longer states the review engine, the per-request credit cost, or that the 250 free credits cover a build — those are undecided in the API — and points to the API's docs for cost instead.

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
