---
name: revoice
description: Rewrite a body of text so it reads like a specific person wrote it, using a voice profile stored as a local asset (default voice from config). Input is inline text or an @file. Optional --voice= picks a profile, --audience=casual|business|formal steers it (using an <voice>-<audience>.md overlay if one exists), --template= supplies a structure to follow (local path, or sb:<note> for SilverBullet), --output-path= saves the result (local path, or sb:<note> for SilverBullet); with no output path the rewrite is only shown. SilverBullet support is optional; without it everything works with local files. --sync pulls voice profiles from SilverBullet into the skill's assets. Use when the user runs /revoice or asks to rewrite, redraft, or convert text "in my voice" / "like me".
argument-hint: '[--voice=<slug>] [--audience=casual|business|formal] [--template=[sb:]<path>] [--output-path=[sb:]<path>] (@file | <text>)  |  --sync[=<slug>]'
allowed-tools: Read, Write, Bash(ls:*), Bash(test:*), Bash(mkdir:*), Bash(cat:*), Bash(python3 ~/.claude/skills/revoice/sync.py:*), Bash(python ~/.claude/skills/revoice/sync.py:*), mcp__silverbullet__read-note, mcp__silverbullet__create-note
---

# revoice

Arguments: `$ARGUMENTS`

## Paths

- Skill dir: `~/.claude/skills/revoice/`
- Voices: `~/.claude/skills/revoice/assets/<slug>.md` (one file per voice)
- Audience overlays: `~/.claude/skills/revoice/assets/<slug>-<audience>.md` (optional, only the differences from the base voice)
- Config: `~/.config/revoice/config.yaml` (owned by the user; read it every run)

Config keys:

- `default_voice`: slug used when `--voice` is not given.
- `fs_base`: base dir for relative local paths (`--output-path`, `--template`). Empty = current working directory. `~` expands to home.
- `sb_base`: SilverBullet folder prefix for relative `sb:` paths. Empty = use the path as given.
- `default_template`: template ref (same `sb:` rule as flags) used only when saving to SilverBullet and `--template` is not given. Empty = no default.
- `default_audience`: audience used when `--audience` is not given. Empty = base voice only, no audience layer.
- `audiences`: the audience names `--audience` accepts.
- `sb_url`: SilverBullet server, used only by `--sync`.
- `voices.<slug>.sb_source`: SilverBullet note that is the master copy of that voice. Used only by `--sync`.

The SilverBullet keys (`sb_base`, `default_template` when it is an `sb:` ref, `sb_url`, `voices`) are optional. Leave them empty if you do not use SilverBullet.

If the config file is missing, stop and tell the user to create it from `config.example.yaml`. Do not guess defaults.

If an `sb:` ref is used but the SilverBullet MCP tools are not available, stop and say so. Do not fall back to a local path.

## Step 1: Parse arguments

Pull these flags out of `$ARGUMENTS`. Everything left over is the input.

- `--voice=<slug>`: default `default_voice`.
- `--audience=<name>`: default `default_audience`. Must be in `audiences`; otherwise stop and list the valid names.
- `--template=<ref>`: optional. `--template=none` turns off the default template for this run.
- `--output-path=<ref>`: optional.
- `--sync` or `--sync=<slug>`: sync mode. Go to Step 6 and skip everything else.

Resolving a `<ref>` (same rule for `--template` and `--output-path`):

- Starts with `sb:` → SilverBullet note. Strip `sb:`. If the rest is relative (does not already start with `sb_base`) and `sb_base` is set, prefix `sb_base/`. Append `.md` if missing.
- Anything else → local file. Expand `~`. If relative, resolve against `fs_base` (or the cwd when `fs_base` is empty).

## Step 2: Load the input

- If the input is an `@file` (Claude Code has already attached its contents) or a bare path that exists on disk, use that file's contents.
- Otherwise the leftover text is the input.
- If there is no input, stop and ask for it.

## Step 3: Load the voice and template

- Read `assets/<voice>.md`. If it does not exist, list the files in `assets/` and stop.
- Pick the audience: the flag, else `default_audience`, else none. Never infer one from the input.
- No audience → use the base voice only. Skip the rest of this audience block.
- Load the audience layer:
  - If `assets/<voice>-<audience>.md` exists, read it. It is an overlay on the base voice: the base still applies, and where the two conflict the overlay wins.
  - Otherwise use the built-in steering below, applied on top of the base voice. The base voice's rules still apply; the steering only turns its dials.
- Built-in steering (fallback only):
  - `casual`: peer or friend. Use the voice's informal color (idioms, casual words) where it fits. Contractions freely. Short fragments and short sign-offs are fine.
  - `business`: client, partner, or colleague. No slang, no emoticons, idioms only if mild. Contractions are fine. Keep the voice's first person, reasoning, and signature phrases. Clear next step.
  - `formal`: application, proposal, official letter, or essay. No idioms or casual words. Fewer contractions. Fuller sentences and fewer fragments. Still first person, still plain words, still no passive-voice hedging or AI tells. Model it on the voice's essay-style writing if the profile describes one.
- Pick the template:
  - `--template=none` → no template.
  - `--template=<ref>` → that template.
  - No `--template`, `--output-path` is `sb:`, and `default_template` is set → `default_template`.
  - Otherwise → no template.
- Load it: `sb:` → `mcp__silverbullet__read-note` (`suggestSimilar: true`); local → Read. If it cannot be found, stop and say so.

## Step 4: Rewrite

Follow the voice profile as the authority on how the text should sound. Rules:

- **Keep the meaning.** Every fact, number, name, date, ask, and commitment in the input stays. Do not add new facts, claims, promises, or details. Do not drop any.
- **Keep the form.** An email stays an email, a doc stays a doc, a note stays a note. Keep roughly the same length unless the voice profile calls for tighter prose.
- **Rewrite first, then fill the template.** The rewrite is always the plain text. If a template is in use, build a second version: the template filled in with the rewrite.
  - Keep the template's layout, section order, and fixed text (including any conventions section).
  - Put the rewritten message where the template's body/message goes.
  - Fill a field only when the input gives the value (subject, recipient, sender, etc.). Leave the rest as the template's placeholders. Never guess names, emails, or times.
  - Set any draft/sent status to Draft, and any "written" date to today.
  - Remove blocks that exist only for later use, such as empty reply sections.
  - The template's instructional placeholder text (e.g. "The actual message. Paste...") is replaced, not kept.
- **Apply the profile's "Do not" list and pronoun rules strictly.**
- **Markdown output:** one paragraph per line. Never hard-wrap prose.
- If something in the input is ambiguous enough that a rewrite would have to guess (for example, who "we" refers to), make the safest choice and list it under "Notes" after the output. Keep notes to 3 bullets max, and skip the section if there is nothing to note.

## Step 5: Output

- Always show the plain rewritten text in chat, in full. Do not show the filled template in chat.
- If `--output-path` is set:
  - `sb:` target: check with `mcp__silverbullet__read-note` (`suggestSimilar: false`). If the note exists, stop and ask before overwriting. Then write with `mcp__silverbullet__create-note` (`overwrite: true` only after the user says yes).
  - Local target: `test -e`. If the file exists, stop and ask before overwriting. `mkdir -p` the parent dir, then Write.
  - Report the exact path saved.
- Save the filled template if one is in use, otherwise the plain rewritten text. No notes, no preamble.

## Step 6: Sync (`--sync`)

- Run `python3 ~/.claude/skills/revoice/sync.py` (add the slug for `--sync=<slug>`). On Windows use `python` instead of `python3` (there `python3` is a Microsoft Store shortcut). It needs PyYAML (`pip install pyyaml`). It fetches the raw notes over HTTP so they never pass through context. Do not use the SilverBullet MCP for sync, and do not write asset files by hand.
- It syncs each voice's base note and any audience overlay notes named `<base note> (<audience>).md`. SilverBullet is the master copy; never write the other way.
- Report its output: which files were updated, skipped, or missing. If it exits non-zero, show the error.
