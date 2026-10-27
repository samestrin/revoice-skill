# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- README install steps start with cloning the repository, and an Upgrading section documents the upgrade and uninstall commands for Windows and macOS/Linux.
- README "Getting an API key" section: sign up at yourvoice.dev (250 free credits), create a key on the dashboard, save it to `~/.config/revoice/api-key`; notes that only `--build` uses it, that only the chosen samples leave the machine, and gives the work-folder delete commands. The requirements note now says only `--sync` needs PyYAML.
- `extract-samples.py --max-samples` (default 200, `0` = no cap) keeps the longest samples, so `--build` reads a bounded number of emails on a large mailbox.

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
