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

Someone who is not Sam can install revoice, build a voice profile from their own email, and use it, from the README alone, and every release is tested in CI. "Release ready" means: tested helpers, CI green on every PR, a license, a version and changelog, and docs that a new user can follow. The owner decided (2026-10-26) that the repo goes public after this epic. Flipping the repo to public is the owner's own action once the epic is done; no task does it. Because the repo will be public, CI runs on GitHub-hosted runners, never on the self-hosted gauntlet runner (T2; owner, 2026-10-26).

## Current State

- Private repo `samestrin/revoice-skill`, branch `main` at bc8726e (2026-10-26; the only commit after the last code commit 1943825 of 2026-10-21 adds this plan). No CI, no tests, no license, no version, no `.planning/` before this plan.
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

## Tasks (canonical)

- **T1** — Add `unittest` tests (standard library, to match the helpers) in `skill/revoice/tests/`, with small synthetic fixtures only (a hand-made `.mbox` with fictional people; never real email). Cover: the date cut-off in `mbox-filter-before.py`; quoted-reply and signature stripping and the `--others` reference set in `extract-samples.py`; the request body and error handling of `build-profile.py` with the HTTP call stubbed (no network in tests); `sync.py` argument handling without SilverBullet. Make `sync.py` import `yaml` lazily (inside `main()` after argument parsing) and give it an argparse `--help` that exits 0 without reading the config; tests stub `yaml`. The helper file names contain hyphens, so tests load them with `importlib` or run them as subprocesses · `skill/revoice/tests/`, `skill/revoice/sync.py` · depends: none · success: `python3 -m unittest discover skill/revoice/tests` passes on Python 3.10 and newer without PyYAML installed, and `python3 skill/revoice/sync.py --help` exits 0
- **T2** — Add `.github/workflows/ci.yml` on GitHub-hosted runners (`runs-on: ubuntu-latest`), never the self-hosted gauntlet runner, with a Python matrix `3.10`, `3.11`, `3.12`, `3.13` through `actions/setup-python` (pinned to a major version). The workflow uses the `pull_request` trigger (never `pull_request_target`) and sets `permissions: contents: read`; fork PRs may run, since they run on GitHub's machines with a read-only token. Steps: run the T1 tests; `python3 <helper> --help` for each helper; a personal-data guard that fails when `git ls-files -ci --exclude-standard` prints anything (a tracked file that `.gitignore` would ignore, so the `!` exceptions in `.gitignore` apply by themselves) · `.github/workflows/ci.yml` · depends: T1 · success: CI runs on every PR to `main` on Python 3.10 to 3.13 and fails on a planted voice file, and `ci.yml` carries `runs-on: ubuntu-latest`, the `pull_request` trigger and `permissions: contents: read`
- **T3** — Add `LICENSE` (MIT, decided 2026-10-26), `CHANGELOG.md` with the first entry, and the version (`0.1.0` unless the owner says otherwise) as `metadata: {version: ...}` in the `skill/revoice/SKILL.md` front matter (Claude Code has no `version` field and ignores unknown ones, but `metadata` is a free-form map it accepts) with the same number in the `CHANGELOG.md` heading · `LICENSE`, `CHANGELOG.md`, `skill/revoice/SKILL.md`, `README.md` · depends: none · success: a `v0.1.0` tag can be cut from `main` and the `SKILL.md` version equals the `CHANGELOG.md` heading
- **T4** — Decide how users install: copy the folder as today, or a Claude Code plugin (open question 3). Whichever is chosen, one documented install command and one upgrade command, on Windows and macOS/Linux · `README.md` · depends: T3 · success: (manual) a clean machine installs from the README and the `revoice` skill runs. Trigger: the owner, on a machine or user account that has no `~/.claude/skills/revoice`, runs only the README install command, starts a new Claude Code session and runs `/revoice Thanks for the quick reply`; a rewrite appears. Cleanup: delete the installed folder.
- **T5** — Add a README section on how a new user gets a text analysis API key: sign up at yourvoice.dev (250 free credits on sign-up), buy a pack if needed, create a key on the dashboard, save it to `~/.config/revoice/api-key`; it is used only by `--build` against `https://text-analysis-api.estr.in/`. Also fix the README line "The helpers use only the standard library" (only `--sync` needs PyYAML: `pip install pyyaml`), and say what leaves the machine (only the chosen samples), and how to delete the work folder · `README.md` · depends: T4 · success: the README answers "where do I get a key" and "what is sent" without outside help
- **T6** — Add `skill/revoice/assets/example.md`: a fictional person's voice file in the real format (see `skill/revoice/build.md`), so a new user sees what `--build` produces and can try `/revoice --voice=example` before building their own. Add `!skill/revoice/assets/example.md` to `.gitignore` (the T2 guard follows `.gitignore`, so it needs no edit) · `skill/revoice/assets/example.md`, `.gitignore` · depends: T2 · success: (manual) `/revoice --voice=example` works on a fresh install. Trigger: the owner, after the T4 install, runs `/revoice --voice=example Thanks for the quick reply` and a rewrite appears; and CI stays green with `example.md` tracked.

## Decisions (owner, 2026-10-26)

1. **Public release:** yes, after this epic; the owner flips the repo. T2 runs CI on GitHub-hosted runners only, so a fork PR never reaches gauntlet (owner, 2026-10-26). Git history checked at bc8726e: no voice file, mbox or key in any commit; the only address is the author's git email and `you@example.com` placeholders.
2. **License:** MIT.
3. **Install:** keep copying the folder; a plugin is not in this epic.
4. **API key:** yourvoice.dev (EST-2794).
5. **Version:** 0.1.0.

## Out of scope

- Changing how the rewrite sounds. Voice quality is the owner's judgment, not a task.
- Any real voice profile or real email in the repo, ever.
- Syncing Sam's installed copy; that happens after the release, from this repo.

<!-- refine-epic:begin -->
## Refinements (2026-10-26)
### Auto-applied corrections (5)
1. Current State named `main` at 1943825; `main` is bc8726e (plan-only commit; code unchanged since 1943825). Evidence: `git log`.
2. `## Tasks (canonical)` written from the proposed tasks, with `depends:` on every task. Edges: T2→T1 (CI runs T1's tests); T4→T3 (both edit `README.md`, T3 owns `SKILL.md` front matter); T5→T4 (both edit `README.md`); T6→T2 (its success needs CI green with `example.md` tracked). T1 and T3 need nothing.
3. T3: version moved to `metadata.version` in `SKILL.md`. The Claude Code skills docs list no `version` field and say unknown fields are ignored; `metadata` is a free-form map. "One place that README and SKILL.md agree on" was self-contradictory, so the version now lives in `SKILL.md` and the `CHANGELOG.md` heading.
4. T2/T6: guard is `git ls-files -ci --exclude-standard` (tested in a scratch repo: lists a tracked file matching an ignore pattern, skips a `!` exception). It covers every `.gitignore` pattern in any folder, and T6 no longer edits the guard (the plan said it would, which would have made T6 edit `ci.yml` too).
5. T4/T6 `(manual)` criteria got `Trigger:` steps. T4's "`/revoice --help`-style usage" referred to a flag `SKILL.md` does not have (its flags are `--voice`, `--audience`, `--template`, `--output-path`, `--sync`, `--build`); it now says a rewrite runs.
### Items needing user confirmation (6)
1. Public or private release (open question 1).
2. License (open question 2).
3. Install method (open question 3). A plugin needs `.claude-plugin/plugin.json` and `skills/<name>/SKILL.md` at the plugin root, which moves `skill/revoice/`, adds a fourth component (limit 3), and namespaces the command as `/<plugin>:<skill>`.
4. API key source (open question 4).
5. Starting version (open question 5).
6. `sync.py` is not standard library only: `import yaml` (PyYAML) at `skill/revoice/sync.py:21`, and it has no `--help` (running it with `--help` reads the config and crashes). The plan and README say "standard library only" and "each has `--help`"; T1 would fail to import it on a clean runner and T2's `--help` step would fail.
### Advisory observations (6)
- No VISION.md in this repo.
- T1 criterion "Python 3.10 and newer": CI runs on gauntlet's one Python, so only that version is proven. Closed 2026-10-26: T2 moved to GitHub-hosted runners with a 3.10 to 3.13 matrix.
- `skill/revoice/tests/` is copied to users by the `cp -R skill/revoice` install. Harmless (synthetic fixtures), and putting tests at top level would add a fourth component.
- Windows install (T4) cannot be proven in CI; it is a manual criterion with a trigger.
- `build-profile.py` also reads the key from `--api-key` and `TEXT_ANALYSIS_API_KEY`; the README only documents the key file (a key on the command line shows in the process list). T5 can mention it.
- The helper file names have hyphens, so tests cannot `import` them directly (noted in T1).
### Verification context
- Code repo: revoice-skill at bc8726e. Plan written: 2026-10-26. Commits reviewed since: 0
- Tasks: 6 (limit 7). Components: 3 (limit 3): `skill/revoice/`, `.github/`, root
- Claims checked: 22 (line counts of 10 files, `.gitignore` list, helper `--help`, stdlib-only, flag list, config path, API URL and key file, README claims, skills docs, plugin docs, GitHub self-hosted runner guidance, gauntlet `runs-on` in sibling repos). Discovery searches: `rg yaml|import`, `rg timeout|urlopen`, `rg --help`, `git ls-files`, sibling `ci.yml`
- Failure modes: Who can call it: CI runs on a self-hosted runner, so fork PRs are the risk if public (GitHub docs: self-hosted runners "should almost never be used for public repositories"); handled in question 1. Slow or down: `build-profile.py` sets timeouts (600 s, 30 s). What leaves: only chosen samples; guard added in T2. Every form of input: guard uses git's own ignore rules, not a copy of the patterns.
- Vision fit: no VISION.md
<!-- refine-epic:end -->

<!-- refine-epic:begin -->
## Refinements (2026-10-26, second pass)
### Auto-applied corrections (2)
1. Open question 4 answered by EST-2794 (auto-apply): a new user gets a key at yourvoice.dev (`text-analysis-portal` README lines 1-3, its epic 54 plan, `https://yourvoice.dev` returns 200). T5 now says so.
2. Finding 6 (`sync.py` needs PyYAML and has no `--help`) settled by EST-2794 (auto-apply): T1 makes the `yaml` import lazy and adds argparse `--help`; T5 corrects the README "standard library only" line and scopes PyYAML to `--sync` (`skill/revoice/SKILL.md:109` already says it needs PyYAML). T1's success now also requires no PyYAML installed.
### Items needing user confirmation (4)
1. Public or private release (recommended: private).
2. License (recommended: MIT).
3. Install method (recommended: keep copying the folder).
5. Starting version (recommended: 0.1.0).
### Advisory observations (0)
### Verification context
- Code repo: revoice-skill at bc8726e. Plan written: 2026-10-26. Commits reviewed since: 0
- Tasks: 6 (limit 7). Components: 3 (limit 3)
- Claims checked: 4 (answers in EST-2794 re-verified against `sync.py:21` and `SKILL.md:109`). Discovery searches: none new
- Failure modes: unchanged from the first report; if question 1 is answered "public", T2 must add the fork guard.
- Vision fit: no VISION.md
<!-- refine-epic:end -->

<!-- refine-epic:begin -->
## Refinements (2026-10-26, third pass)
### Auto-applied corrections (4)
1. Question 1 answered **public** (card 522ddb2b, owner). T2 now has the same-repo `if:`, the `pull_request` trigger and `permissions: contents: read`, with a manual criterion and trigger for the fork case. Evidence: GitHub secure-use docs, self-hosted runners "should almost never be used for public repositories".
2. Question 2 answered MIT: T3 says MIT.
3. Questions 3 and 5 answered (copy the folder, 0.1.0); T4 and T3 already match.
4. Goal and "Open questions" rewritten as "Decisions". Git history checked for the move to public: clean.
### Items needing user confirmation (0)
### Advisory observations (2)
- Repo settings, not plan text: when the owner flips the repo to public, also set Actions > Fork pull request workflows to require approval for all outside collaborators. The `if:` stops the job for forks; this setting is a second layer, and it is the owner's call. (2026-10-26: T2 moved to GitHub-hosted runners and dropped the `if:`; the setting is now optional.)
- A public repo means the sample voice file in T6 and all test fixtures are world-readable; they are already required to be fictional.
### Verification context
- Code repo: revoice-skill at bc8726e. Plan written: 2026-10-26. Commits reviewed since: 0
- Tasks: 6 (limit 7). Components: 3 (limit 3)
- Claims checked: 3 (history scan of all commits for voice files, mbox, keys, addresses). Discovery searches: `git log --all -p`
- Failure modes: fork PR on a self-hosted runner covered by T2; what leaves: history clean.
- Vision fit: no VISION.md
<!-- refine-epic:end -->
