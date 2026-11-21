# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Changed

- `build.md` phase 6 checks the voice file in code: after saving it, the build runs `check/check-voice.py --voice` on the saved file (or the `WORK/<slug>.md` copy), fixes what it lists, runs it again once, and tells you plainly if a line remains. A script that is absent or exits 2 is named with its error in the build report and the build goes on — the one exception to the stop-on-helper-failure rule. Phase 6 now also says the sections are `## ` headings with the exact listed text, as in the bundled `example.md`, which is what the check requires.
- `SKILL.md` Step 4 checks every rewrite in code after the final grammar pass: it writes the input and the plain rewrite to `~/.config/revoice/check/` and runs `check/check-facts.py`, `check/check-do-not.py` and `check/check-format.py`, fixes only what the lines list, then runs them once more. A line still listed is shown under "Notes" (3 bullets at most); a check script that is absent or exits 2 is named there with its error and skipped, and the rewrite goes on. The filled template is not checked.

### Fixed

- README: the opt-in reference set is up to 148 emails from other senders, not 200; it is extracted with the same `--max-samples` cap as your samples. `test_readme_claims.py` pins the count to the script's default.
- `review-samples.py --mode writing|brand` drops quoted AI model output (reason `quoted model output`: a short lead-in such as "AI21 Studio Response" or "Here is what ChatGPT said:" followed by the answer, or mostly code-like lines) and one-cell-per-line table text (reason `table or numbers`). The lead-in must name a model: a model or vendor name, "the model", "the prompt", or a pair such as "model response" (in a heading, "AI", "model", "assistant" or "bot" counts only right before the response word, so "AI Incident Response" is kept); an ordinary heading or lead-in such as "Incident Response" or "The short answer:" keeps the passage after it. In a real run, model answers quoted in a PDF and a DOCX were kept as the author's own writing and uploaded. Email mode is unchanged.
- `review-samples.py`: the `coverage:` line says "1 document", not "1 documents".
- `.claude-plugin/plugin.json`: the description says `--build` builds a voice from an email export, a folder of your own writing, or a folder of brand documents, not from an email export only. `test_plugin_manifest.py` pins the three sources.
- `extract-documents.py`: one article saved several ways (a URL, a PDF and a DOCX copy) is one document. Sources that lost a passage to a copy in another source, or share half their text with it, are written under one `source` name in `index.csv`, so the document count downstream is the true one, and the report says `read 5 documents (3 distinct)`. Dedupe also drops a passage with half its word 5-grams among the other kept passages, not just within one of them, so a passage that straddles two others is no longer kept twice.
- `build-profile.py --source-type writing|brand` takes the voice profile's passages in turn from each document (best score, then longest, within each), so three documents give 5 each of the default 15. In a real run, 14 of the 15 came from one article because the longest passages won. Email builds, and an index with no `source` column, choose exactly as before.
- `build-profile.py` prints one line when it builds without a reference set (always for documents, the default for email): the baseline is then the author's own mean, so the voice file's Stats reference has nothing to compare. The profile JSON is unchanged.
- `build-profile.py`: `--help` no longer calls `--reference` "(recommended)"; it says the default is none and documents have no reference set. The help says samples come from `extract-samples.py` or `extract-documents.py`, and `meta.source` says "1 document", not "1 documents".
- `extract-documents.py`: the HTML reader drops icon-font words and terminal-style widgets. An element with a `material-symbols`, `material-icons`, `fa-`, `bi-` or `icon-` class, or with `aria-hidden="true"`, is not read, and a block of 3 or more lines, most of them starting with a `$ ` or `> ` prompt, is dropped whole. In a real run a brand page's samples began "hub Where My Work…" and "lock Private by Default…" and kept a status widget's `> Linux | macOS | Windows` lines as prose.
- `extract-documents.py` cleans up four kinds of leftover text. A `--urls` page title loses a trailing ` - Site Name` (or ` | `, en or em dash) when 2 or more of the pages' titles end with the same name, so three dev.to posts are no longer titled "… - DEV Community"; a single page keeps its title. A heading that opens a passage is written without its `#` marks, for every input type. A bare `01` to `99` before a heading or a short title-cased line is kept as a section label, not removed as a page number, unless it is the first or last line of a PDF page. In a PDF, a word broken by a hyphen at a line end (`real-` / `time`) is joined only when the whole word (`realtime`) appears elsewhere in the same document; otherwise the text is left as it is.

## [0.3.0] - 2026-11-20

### Added

- Build a voice from a folder of your own writing (articles, posts, essays): `extract-documents.py` reads `.md`, `.txt`, `.html`/`.htm`, `.docx` and `.pdf` (through the `pdftotext` program from poppler when it is on PATH) plus a `--urls` list of pages you own, drops boilerplate and duplicates, and splits each document into passages of about 350 words (150 to 500), one passage per sample, at most 148 taken in turn from each document. An optional `--before` cutoff checks only a front-matter `date:`; undated documents are kept. The build asks you to confirm the writing is your own and not AI-assisted, and that you may send it to the text analysis API and to Claude.
- Build a voice from a folder of brand documents: several authors, one brand voice, the profile named for the brand. Before anything is read, the build says plainly that brand documents are often confidential and asks you to confirm you may send them; take out anything you may not send to a third-party API or to Claude first.
- `review-samples.py --mode email|writing|brand` (default `email`, unchanged): the document modes turn off the email-only rules, `writing` drops a passage bylined with someone else's name, `brand` keeps every author. Both print a `coverage:` line (KEEP passages and the documents they come from) and exit with status 3 below the floor (10 KEEP passages; `brand` also needs 3 documents), so the build stops before any upload. Below the minimum (20 KEEP passages from at least 5 documents) it warns the profile will be weaker.
- `build-profile.py --source-type email|writing|brand` (default `email`): the profile records an honest `meta.source` and `meta.source_type` with the document count, no sender addresses outside email, and `--from` is rejected for document builds. A default email build's profile is unchanged apart from the new `source_type`.
- README: the intro names the three sources; "3. Build your voice profile" has a subsection per source with the file types, the `pdftotext` note, the `--urls` list, the counts table (floor, minimum, recommended per source) and what happens below them; the cost section gives the passages formula and a 20-document example (about 85 passages, 171 credits); "What leaves your machine" is stated per mode with a plain confidentiality paragraph for brand documents; the by-hand helper list adds `extract-documents.py`. `test_readme_claims.py` pins the new claims.

### Changed

- `--build` asks first where your writing is: an email export, a folder of your own writing, or a folder of brand documents, then asks only what that source needs. The email path asks the same questions as before. Documents go through `extract-documents.py`, `review-samples.py --mode writing|brand` and `build-profile.py --source-type`; the voice file describes the shape of an article or of a brand document instead of an email. The `SKILL.md` description names the three sources.

## [0.2.2] - 2026-11-16

### Changed

- `--build` stops after the local review (phase 4) and before the first upload (phase 5): Claude tells you how many samples are KEEP, that they are plain files in `WORK/samples/`, and that changing a row's `verdict` to DROP in `samples/index.csv` keeps that sample from being sent, then waits for your explicit go. Claude still does not read the samples at this step. If you drop so many that fewer than 15 are left, it warns as the review does. New tests show a sample dropped by hand is never sent and is not counted in the cost estimate.

## [0.2.1] - 2026-11-16

### Added

- `Install test` workflow: on every pull request and push to main it installs Claude Code in a clean `node:24` container, validates the plugin, then installs the skill both ways the README gives (plugin marketplace, copy-folder) into fresh homes and checks the installed copy. A further step writes `~/.config/revoice/voices/me.md` and `config.yaml`, upgrades the plugin from a temp copy raised to the next patch version, and fails unless the update reports the new version, the new version folder is in the plugin cache, both voice files are unchanged and no voice file is in the plugin folder.
- `Release` workflow: pushing a `v0.2.0`-form tag checks that the version without its `v` equals `plugin.json` `version`, `SKILL.md` `metadata.version` and the newest released `CHANGELOG.md` heading, runs the unit tests, then creates the GitHub release with that version's CHANGELOG section as its notes. A tag that disagrees fails before any release is made. Only the release job can write to the repo. `.github/scripts/release-notes.py` prints the section; `test_release_notes.py` covers it.

### Fixed

- `extract-samples.py` gives the same samples and the same `index.csv` whatever the order of messages in the mbox. Samples of equal length used to keep mbox order, so a shuffled mailbox could keep the other copy of a resent message, or a different sample at the `--max-samples` cap. Ties now go by date (earliest first, undated last), then the sample's sha1, then the subject.

## [0.2.0] - 2026-11-03

### Added

- README "What it looks like" section, under the install step and before "2. Save your API key": the before-and-after from the fictional example voice (`skill/revoice/assets/example.md`), a generic draft and its rewrite with `/revoice --voice=example`, so you see a result before you spend credits. `test_readme_claims.py` checks the pair matches `example.md` and the rewrite has none of the phrases that voice bans.
- README "If the build stops" list: what to do for a wrong key (401), out of credits (402), too many requests (429) and an unreachable API, and that the build checks the key and the balance before it spends credits. `test_readme_claims.py` pins the four cases.
- README "What a build costs" section: 1 credit per text, the formula 1 + kept samples + reference emails + min(kept samples, 100), two worked examples, and that a default build (148 samples, no reference set) plus the key check costs 250 credits, the free grant. "2. Save your API key" now has a Linux command.
- README "Upgrading" says how to see the installed version (the `/plugin` screen), that fixes reach plugin users in tagged releases, and links to the repo's Releases page. `test_readme_claims.py` pins the link inside that section.
- `--build` checks the API key and balance first: phase 0 now holds the key-file steps and runs `build-profile.py --check`, phase 3 is "Check the cost" (estimate and balance, ask before going on if short), phase 5 gives a plain line for 401, 402, 429 and an unreachable API, and the reference set is now opt-in (default no) with its credit cost.
- `build-profile.py` counts what a build costs before it spends anything: 1 credit per text sent, so 1 + kept samples + reference texts + min(kept samples, 100). It reads the balance (`X-Credits-Remaining`) from its first call, and if that cannot cover the rest, it stops there (1 credit spent, no profile written) and prints the cost, the balance, and the two ways out: buy credits at yourvoice.dev, or rebuild with fewer samples or without `--reference`. If the API sends no balance, the build goes on.
- `build-profile.py --estimate` prints the estimated cost of a build from `--samples` and `--reference` without calling the API, so it is free and needs no key; with `--balance N` (the balance `--check` printed) it says how short that balance is. `build.md` phase 3 runs it instead of a second paid `--check`.
- `build-profile.py --check` spends 1 credit on a short fixed text, prints whether the key works, the balance and the estimated cost of a build from `--samples` and `--reference`, and writes no profile. `--author` is not needed with `--check`.
- `Attribution check` CI job: a pull request fails if any commit has an author or committer other than the maintainer, or if a commit, the PR title or the PR body has a `Co-authored-by`, `Claude-Session` or `Generated with` line, so no tool or test identity is listed as a contributor.
- `review-samples.py` now recognises Spanish and French authors as well as English and German ones, so a stray sample in another language is dropped ("not in the author's language") from a Spanish or French author's set too. Only the words that tell Spanish and French apart count, so a French sample is not taken for Spanish or the other way round.
- Plugin icon: `.claude-plugin/icon.png` (512x512 PNG) referenced by an `icon` key in `plugin.json`, which clears `ICON_MISSING` from `claude plugin validate`. A test checks the file exists, is a PNG, and is square within 512-2048 px and under 2 MB.
- Claude Code plugin manifests: `.claude-plugin/plugin.json` (plugin `revoice`, version 0.1.0, skill loaded from `skill/`) and `.claude-plugin/marketplace.json` (marketplace `revoice-skill`), so the repo can be added as a plugin marketplace. A test keeps the plugin version equal to the newest released CHANGELOG version and `SKILL.md` `metadata.version`.
- README install steps start with cloning the repository, and an Upgrading section documents the upgrade and uninstall commands for Windows and macOS/Linux.
- README "Getting an API key" section: sign up at yourvoice.dev (250 free credits), create a key on the dashboard, save it to `~/.config/revoice/api-key`; notes that only `--build` uses it, that only the chosen samples leave the machine, and gives the work-folder delete commands. The requirements note now says only `--sync` needs PyYAML.
- `extract-samples.py --max-samples` (default 200, `0` = no cap) keeps the longest samples, so `--build` reads a bounded number of emails on a large mailbox.

### Changed

- `extract-samples.py --max-samples` now defaults to 148 instead of 200, so a default build fits the 250 free credits: 1 credit for the key check in phase 0, then 1 + 148 + 100 for the build with the reference set off. Pass a larger number, or `0` for no cap, to keep more.
- `build-profile.py` turns API failures into one plain line with no traceback: 401 (key rejected), 402 (balance and cost), 429 (seconds to wait from `Retry-After`) and an unreachable API. A failed `/health` call now records the API version as null and still writes the profile.
- `--build` now defaults to the production API, `https://api.yourvoice.dev`, instead of the dev server `https://text-analysis-api.estr.in`; the README and `build.md` name the new address. Pass `--api` to use another server.
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
