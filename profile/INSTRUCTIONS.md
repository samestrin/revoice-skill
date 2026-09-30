# Instructions for Claude: building a voice profile

These are the two steps of the profile build that need judgment rather than a script. The user will point you at one of them. Do only the step you are asked to do, then stop and report.

Throughout: the samples are the user's private email. Do not send them anywhere, do not quote them in chat beyond what a step asks for, and do not modify the sample `.md` files.

## Step A: Review the samples

Input: a `samples/` folder made by `extract-samples.py`, with one `.md` file per email and an `index.csv` listing them (`file,date,words,subject`).

Goal: mark which samples truly show how the author writes when they are writing for themselves, in their own words.

1. Read every sample listed in `index.csv`. For large folders, work in batches, but read each file in full.
2. For each sample, decide:
   - `verdict`: `KEEP` or `DROP`.
   - `score`: 1 to 5, how well it shows the author's natural voice. 5 = several paragraphs of the author thinking and explaining in their own words. 1 = barely any real writing.
   - `reason`: a few words.
3. DROP a sample when it is mostly one of these:
   - Text the author did not write: pasted articles, quoted emails that slipped past the reply-cutting, legal or boilerplate text, forwarded content.
   - Lists, logs, code, tables, addresses, or schedules rather than prose.
   - Form letters or templates sent many times.
   - Written in another person's name, or clearly ghostwritten in a different voice.
   - Not in the author's usual language.
   - Broken extraction: cut off mid-thought, garbled characters, or mostly a signature.
4. Do not DROP a sample just because it is casual, short-ish, has typos, or covers a sensitive topic. Those are all real voice. Sensitivity matters later, in step B, when choosing what to quote.
5. Write the three columns into `index.csv` (keep the existing columns and rows; add `verdict,score,reason`). Keep it valid CSV (quote fields that contain commas).
6. Report: how many KEEP vs DROP, the score spread, and the 3 most common DROP reasons. If fewer than 15 samples are KEEP, say so: the profile works best with about 15 or more.

## Step B: Write the voice profile Markdown

Input: `voice-profile.json` from `build-profile.py`, and the reviewed `samples/` folder.

Goal: a Markdown file that tells a model how to write like this author, named `<slug>.md` (for example `joe-smith.md`). Save it where the user says, usually `voice/<slug>.md` in this repository. The user copies it into the skill's `assets/` folder, where `/revoice` loads it.

1. Read `voice-profile.json`. Its `meta.samples.voice_profile` lists the samples the profile was built from.
2. Read those samples in full. **The samples are the authority on how the author sounds. The JSON numbers are averages.** When they disagree, trust the samples.
3. Write the file with these sections, in this order:
   - **Title and intro**: `# <Author>: Writing Profile`, then one short paragraph on what this file is and that samples beat stats.
   - **The voice in one paragraph**: how this person sounds, in plain words.
   - **Core traits**: 4 to 7 bullets, each with a short real example.
   - **Sentences**: length and variety, fragments, questions, typical sentence openers.
   - **Word choice and signature phrases**: grouped by use (openers, structuring topics, stance and hedging, offers and warmth, closings, informal color). Use `fingerprint.distinctive_phrases` and `first_person_patterns` from the JSON, but only list a phrase if you actually see it used that way in the samples. Add the rule "Use these naturally. Do not stack them."
   - **Punctuation and formatting habits**: parentheses, quotes, dashes, exclamation points, lists, contractions, greetings and sign-offs.
   - **Paragraphs and structure**: paragraph length and the typical shape of an email from start to finish.
   - **Pronouns**: whether they write as "I" or "we", and when.
   - **Stats reference**: a small table of the JSON features where this author differs from the `comparison.baseline` mean, in words ("higher", "lower"), marked as calibration only.
   - **Do not**: AI tells to avoid (for example "delve", "I hope this email finds you well", "it's worth noting", "robust", "seamless", em-dash chains), anything this author never does, "do not copy the author's typos", and "do not invent facts, numbers or names".
   - **Short examples from the corpus**: 4 to 6 short quotes, each labeled with the habit it shows.
   - **Before and after**: one invented generic AI-style draft and the same message rewritten in this voice.
4. **Privacy in quotes.** The profile may be shared. When you choose quotes, skip anything with other people's private details: money figures about third parties, disputes, health, family matters, client rates, or anything addressed by name to someone the user works with now. Pick a different line that shows the same habit.
5. Formatting: one paragraph per line (never hard-wrap prose), no emojis.
6. Report the file path and the 3 traits you are most and least confident about, so the user knows what to check first.
