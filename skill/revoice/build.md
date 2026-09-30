# revoice --build: build a voice profile

Walk the user from an email export to an installed voice file. Do the phases in order. Keep each message to the user short: what you did, the numbers, and what you need next.

Paths below: `SKILL` is this skill's folder (`~/.claude/skills/revoice/`), `WORK` is the work folder chosen in phase 1.

Rules for the whole build:

- **The email is private.** Do not send samples anywhere except the text analysis API through `build-profile.py`. In chat, quote at most a short line when asked.
- **Never read, print, or ask for the API key.** It lives in a key file (default `~/.config/revoice/api-key`). Only check that the file exists and is not empty (`test -s`). If the user pastes a key into the chat anyway, do not repeat it, and tell them it is now in the transcript and they may want a new key.
- **Python:** use `python` if `python --version` reports Python 3.10 or newer, else `python3`. On Windows, `python3` is often a Microsoft Store shortcut; do not use it there.
- **Long runs:** the helpers read big files one message at a time. If the mbox is over 500 MB, run the filter and extract steps in the background and wait for them to finish.
- If a helper fails, show the last lines of its output and stop. Do not guess a workaround.

## Phase 0: Check the setup

1. Find Python (see above). Stop if there is no Python 3.10+.
2. Check the helpers exist: `SKILL/build/mbox-filter-before.py`, `extract-samples.py`, `build-profile.py`.
3. If `~/.config/revoice/config.yaml` does not exist, copy `SKILL/config.example.yaml` there.

## Phase 1: Ask

Take any answers already given in the arguments (for example `mbox=...`, `from=...`, `name=...`). Ask for the rest in **one** message, and wait:

1. **Email export:** path to the `.mbox` file. (Gmail: Google Takeout, Mail, only the "Sent" label.)
2. **Addresses:** every address the user has sent from.
3. **Name:** their full name. Suggest a slug from it (`joe-smith`) and use it unless they give another.
4. **Cutoff date:** default `2022-09-01` (three months before ChatGPT launched), to keep AI-assisted writing out.
5. **Reference set:** default yes. It compares their writing with other people's email in the same export, so their signature phrases come out specific instead of generic.
6. **Work folder:** default `~/revoice-build/<slug>`. Their samples go here, not in the skill.

Then check the mbox path exists, and create `WORK`.

## Phase 2: Filter and extract

Run from `WORK`:

```
<python> SKILL/build/mbox-filter-before.py "<mbox>" --before <cutoff> -o pre-ai.mbox
<python> SKILL/build/extract-samples.py pre-ai.mbox --from <addr1> --from <addr2> -o samples
<python> SKILL/build/extract-samples.py pre-ai.mbox --from <addr1> --from <addr2> --others -o reference   (only if the reference set is on)
```

Report: messages kept by the date filter, samples written, and the top drop reasons. If there are fewer than 20 samples, say so and offer to rerun extraction with `--min-words 100` (the default is 150). If you notice another address of the user's while reading (for example in their signature) that is not in the list, tell them and offer to rerun extraction with it added.

## Phase 3: Review the samples

Read every sample listed in `samples/index.csv`, in full (in batches for large folders). For each, decide:

- `verdict`: `KEEP` or `DROP`.
- `score`: 1 to 5. 5 = several paragraphs of the author thinking and explaining in their own words. 1 = barely any real writing.
- `reason`: a few words.

DROP a sample when it is mostly: text the author did not write (pasted articles, quoted email that slipped through, boilerplate, forwards); lists, logs, code, tables or schedules rather than prose; form letters sent many times; written in someone else's name or voice; not in the author's usual language; or broken extraction (cut off, garbled, mostly signature). Do not DROP for being casual, short-ish, having typos, or touching a sensitive topic. Those are real voice.

Add `verdict,score,reason` columns to `samples/index.csv`, keeping the existing columns and rows, as valid CSV. Report KEEP vs DROP counts and the top 3 drop reasons. If fewer than 15 are KEEP, tell the user the profile will be weaker and ask whether to continue.

## Phase 4: Check the API key

Check `test -s ~/.config/revoice/api-key`. If it is missing or empty, tell the user to create it themselves and wait. Give them the command for their system:

- Windows: `notepad "$HOME\.config\revoice\api-key"` (in PowerShell), paste the key, save, close.
- macOS: copy the key, then `pbpaste > ~/.config/revoice/api-key`.
- Linux: `nano ~/.config/revoice/api-key`, paste, save.

## Phase 5: Build the profile JSON

From `WORK`:

```
<python> SKILL/build/build-profile.py --samples samples --reference reference --author "<Name>" --from <addr1> --from <addr2> --cutoff <cutoff> -o voice-profile.json
```

Leave out `--reference reference` if the reference set is off. It sends the kept samples to the API at https://text-analysis-api.estr.in/ and can take a minute. If it reports a 401, the key is wrong; send the user back to phase 4.

## Phase 6: Write the voice file

1. Read `voice-profile.json`. Its `meta.samples.voice_profile` lists the samples the profile was built from. Read those samples in full. **The samples are the authority on how the author sounds; the JSON numbers are averages.** When they disagree, trust the samples.
2. Write the voice file with these sections, in order:
   - `# <Name>: Writing Profile`, then one short paragraph on what this file is and that samples beat stats.
   - **The voice in one paragraph.**
   - **Core traits:** 4 to 7 bullets, each with a short real example.
   - **Sentences:** length and variety, fragments, questions, typical openers.
   - **Word choice and signature phrases:** grouped by use (openers, structuring topics, stance and hedging, offers and warmth, closings, informal color). Use `fingerprint.distinctive_phrases` and `first_person_patterns`, but only list a phrase you actually see used that way in the samples. Include the rule "Use these naturally. Do not stack them."
   - **Punctuation and formatting habits:** parentheses, quotes, dashes, exclamation points, lists, contractions, greetings and sign-offs.
   - **Paragraphs and structure:** paragraph length and the usual shape of an email from start to finish.
   - **Pronouns:** when they write "I" and when "we".
   - **Stats reference:** a small table of features where the author differs from `comparison.baseline` mean, in words ("higher", "lower"), marked as calibration only.
   - **Do not:** AI tells to avoid ("delve", "I hope this email finds you well", "it's worth noting", "robust", "seamless", em-dash chains), anything this author never does, "do not copy the author's typos", and "do not invent facts, numbers or names".
   - **Short examples from the corpus:** 4 to 6 short quotes, each labeled with the habit it shows.
   - **Before and after:** one invented generic AI-style draft and the same message in this voice.
3. **Privacy in quotes.** The file may be shared. Skip quotes with other people's private details: money about third parties, disputes, health, family, client rates, or anything addressed by name to someone the user works with now. Pick another line that shows the same habit.
4. One paragraph per line (never hard-wrap prose). No emojis.
5. Save it to `SKILL/assets/<slug>.md`. Claude Code asks the user to approve writes to its skills folder; tell them to expect that prompt. If the write is blocked, save to `WORK/<slug>.md` instead and give them the exact copy command for their system.

## Phase 7: Make it the default

In `~/.config/revoice/config.yaml`, set `default_voice: <slug>`. If it already names a different real voice (anything other than `your-name`), ask before changing it.

## Phase 8: Show it working

Rewrite this in the new voice (base voice, no audience, no template) and show it:

> Hi team, I hope this email finds you well! I wanted to circle back on the budget review. After careful consideration, it's worth noting that the current plan is not robust — it leaves no room for delays. I would recommend we add a two-week buffer. Please let me know your thoughts at your earliest convenience.

Then finish with:

- Where everything is: the voice file, `WORK` (samples, JSON), and that `WORK` holds private email they can delete once they are happy.
- The 3 traits you are most and least sure about, so they know what to check first.
- How to use it: `/revoice <text>`, `/revoice @file`, and `--audience=casual|business|formal`, with the tip that they can add `assets/<slug>-<audience>.md` holding only the differences for an audience.
