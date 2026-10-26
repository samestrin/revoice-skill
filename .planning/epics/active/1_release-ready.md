# Epic Plan 1: Make revoice release ready

- **Estimated time**: 2-3 days
- **Last modified**: 2026-10-26 (written by Sam with Claude Code; not yet refined)
- **Tasks/Components**: 6/3
- **Components, counted by top-level path — three:**
  - `skill/revoice/` — the skill and its Python helpers (tests go in `skill/revoice/tests/`).
  - `.github/` — CI.
  - root — `README.md`, `LICENSE`, `CHANGELOG.md`, packaging metadata.
- **Base branch: `main`.** Every PR targets `main`.
- **Depends on:** nothing.

## Goal

Someone who is not Sam can install revoice, build a voice profile from their own email, and use it, from the README alone, and every release is tested in CI. "Release ready" means: tested helpers, CI green on every PR, a license, a version and changelog, and docs that a new user can follow. It does not mean making the repo public; that is a separate decision for the owner (open question 1).

## Current State

- Private repo `samestrin/revoice-skill`, branch `main` at 1943825 (2026-10-21). No CI, no tests, no license, no version, no `.planning/` before this plan.
- `skill/revoice/SKILL.md` (111 lines): the rewrite skill, `--voice`, `--audience`, `--template`, `--output-path`, `--sync` (SilverBullet, optional), `--build`.
- `skill/revoice/build.md` (110 lines): the `--build` walkthrough that turns a sent-mail `.mbox` into a voice file.
- Helpers, standard library only: `build/mbox-filter-before.py` (72 lines), `build/extract-samples.py` (219), `build/build-profile.py` (178), `sync.py` (86). Each has `--help`. None has a test.
- `config.example.yaml` (32 lines); the real config is `~/.config/revoice/config.yaml`.
- `.gitignore` keeps personal data out: `*.mbox`, `samples/`, `reference/`, `voice-profile.json`, `config.yaml`, `voice/`, `api-key`, and every `skill/revoice/assets/*.md` except `assets/README.md`.
- The build sends chosen samples to the text analysis API (`https://text-analysis-api.estr.in/`, `X-API-Key` header, key read from `~/.config/revoice/api-key`). The README does not say how a new user gets a key.
- Copies drift: Sam's installed copy at `~/.claude/skills/revoice` and the backup in the `research` repo are older than this repo (no `--build`, Sam-specific wording). This repo is the source of truth.

## Pain Points

- No tests: a change to the mbox filter or sample extraction can silently drop or leak email content.
- No CI, so nothing runs those checks on a PR.
- Nothing stops a voice file or email sample from being committed except `.gitignore`.
- No license, version or changelog, so there is nothing to call a release.
- The README assumes the reader already has an API key.

## Tasks (proposed; the refine turns these into canonical tasks)

- **T1 — Tests for the helpers.** `unittest` (standard library, to match the helpers) in `skill/revoice/tests/`, with small synthetic fixtures only (a hand-made `.mbox` with fictional people; never real email). Cover: the date cut-off in `mbox-filter-before.py`; quoted-reply and signature stripping and the `--others` reference set in `extract-samples.py`; the request body and error handling of `build-profile.py` with the HTTP call stubbed (no network in tests); `sync.py` argument handling without SilverBullet. Success: `python3 -m unittest discover skill/revoice/tests` passes on Python 3.10 and newer.
- **T2 — CI on gauntlet.** `.github/workflows/ci.yml` with `runs-on: [self-hosted, gauntlet]` (the private-repo runner; see the other private repos). Steps: run the T1 tests; `python3 <helper> --help` for each helper; a personal-data guard that fails if a tracked file matches the `.gitignore` personal-data patterns, or if any `skill/revoice/assets/*.md` other than `README.md` is tracked. Success: CI runs on every PR to `main` and fails on a planted voice file.
- **T3 — License, version, changelog.** `LICENSE` (owner picks, open question 2), a version (`0.1.0` unless the owner says otherwise) in one place that the README and `SKILL.md` front matter agree on, and `CHANGELOG.md` with the first entry. Success: a `v0.1.0` tag can be cut from `main`.
- **T4 — Packaging and install.** Decide how users install: copy the folder as today, or a Claude Code plugin (open question 3). Whichever is chosen, one documented install command and one upgrade command, on Windows and macOS/Linux. Success: a clean machine installs from the README and `/revoice --help`-style usage works.
- **T5 — Getting an API key and privacy notes.** README section on how a new user gets a text analysis API key (open question 4), what leaves the machine (only the chosen samples), and how to delete the work folder. Success: the README answers "where do I get a key" and "what is sent" without outside help.
- **T6 — Example voice file.** `skill/revoice/assets/example.md`: a fictional person's voice file in the real format, so a new user sees what `--build` produces and can try `/revoice --voice=example` before building their own. Add it as an explicit exception in `.gitignore` and the T2 guard. Success: `/revoice --voice=example` works on a fresh install.

## Open questions for the owner

1. **Public or private release?** Release ready can stay private. If it goes public, CI on a self-hosted runner needs a rule that PRs from forks never run on gauntlet.
2. **License:** MIT, Apache-2.0, or proprietary/all rights reserved?
3. **Install:** keep "copy the folder", or package as a Claude Code plugin?
4. **API key:** is yourvoice.dev (the text analysis portal) where a new user gets a key and credits, or is the API key handed out another way?
5. **Version:** start at `0.1.0`?

## Out of scope

- Changing how the rewrite sounds. Voice quality is the owner's judgment, not a task.
- Any real voice profile or real email in the repo, ever.
- Syncing Sam's installed copy; that happens after the release, from this repo.
