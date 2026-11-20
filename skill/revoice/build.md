# revoice --build: build a voice profile

Walk the user from their writing (an email export, a folder of their own writing, or a folder of brand documents) to an installed voice file. Do the phases in order. Keep each message to the user short: what you did, the numbers, and what you need next.

Paths below: `SKILL` is this skill's folder (the Skill dir in `SKILL.md`'s Paths, which is also the folder this file is in), `WORK` is the work folder chosen in phase 1.

The source chosen in phase 1 sets the mode for every later phase: `email`, `writing` or `brand`. Where a phase differs by source, it has a subsection per source; follow only the one for this build's mode.

Rules for the whole build:

- **The email is private.** The review in phase 4 runs on this machine and sends nothing anywhere. The only step that sends samples off the machine is `build-profile.py` in phase 5, which sends the kept samples to the text analysis API, and only after the user has approved them at the end of phase 4. Do not send samples anywhere else. In chat, quote at most a short line when asked.
- **Documents are private too** (`writing` and `brand`). The folder never leaves the machine as a whole: extraction (phase 2) and review (phase 4) run on this machine. The kept passages (up to 148) go to the text analysis API over HTTPS in phase 5, after the user approves them. In phase 6 you read the passages the profile was built from (about 15), so those also go to the model provider that runs Claude for the user. For a `--urls` list, the user's machine fetches the pages in phase 2 and nothing is sent to the API before phase 5; never fetch a URL yourself. In chat, quote at most a short line when asked.
- **Brand documents are often confidential.** Say so plainly in phase 1, tell the user to take out anything they may not send to a third-party API or to Claude, and have them confirm before phase 2.
- **Never read, print, or ask for the API key.** It lives in a key file (default `~/.config/revoice/api-key`). Only check that the file exists and is not empty (`test -s`). If the user pastes a key into the chat anyway, do not repeat it, and tell them it is now in the transcript and they may want a new key.
- **Python:** use `python` if `python --version` reports Python 3.10 or newer, else `python3`. On Windows, `python3` is often a Microsoft Store shortcut; do not use it there.
- **Long runs:** the helpers read big files one message at a time. If the mbox is over 500 MB, or the `--urls` list is long (one page a second), run the filter and extract steps in the background and wait for them to finish.
- If a helper fails, show the last lines of its output and stop. Do not guess a workaround.

## Phase 0: Check the setup

1. Find Python (see above). Stop if there is no Python 3.10+.
2. Check the helpers exist: `SKILL/build/mbox-filter-before.py`, `extract-samples.py`, `extract-documents.py`, `review-samples.py`, `build-profile.py`.
3. If `~/.config/revoice/config.yaml` does not exist, copy `SKILL/config.example.yaml` there.
4. Check the API key file: `test -s ~/.config/revoice/api-key`. If it is missing or empty, tell the user to create it themselves and wait. Give them the command for their system:
   - Windows: `notepad "$HOME\.config\revoice\api-key"` (in PowerShell), paste the key, save, close.
   - macOS: copy the key, then `pbpaste > ~/.config/revoice/api-key`.
   - Linux: `nano ~/.config/revoice/api-key`, paste, save.
5. Run `<python> SKILL/build/build-profile.py --check`. It spends 1 credit and says whether the key works and what the balance is. Note the balance: phase 3 uses it. If it fails, say what it printed in plain words (see phase 5 for 401, 402, 429 and "cannot reach the API") and stop, so a wrong key or an empty balance shows before the extract steps.

## Phase 1: Ask

Take any answers already given in the arguments (for example `source=...` or `name=...`).

1. **Source:** unless the arguments already say, ask this first, on its own, and wait: "Where is your writing: an email export, a folder of your own writing, or a folder of brand documents?" The answer sets the mode: an email export is `email`, a folder of the user's own writing (articles, posts, essays) is `writing`, a folder of a business's documents (several authors, one brand voice) is `brand`.

Then ask for the rest that source needs in **one** message, and wait.

### Email

Arguments such as `mbox=...` and `from=...` answer the first two.

1. **Email export:** path to the `.mbox` file. (Gmail: Google Takeout, Mail, only the "Sent" label.)
2. **Addresses:** every address the user has sent from.
3. **Name:** their full name. Suggest a slug from it (`joe-smith`) and use it unless they give another.
4. **Cutoff date:** default `2022-09-01` (three months before ChatGPT launched), to keep AI-assisted writing out.
5. **Reference set:** default no. Offer it as opt-in, and say it costs extra API credits. It compares their writing with other people's email in the same export, so their signature phrases come out specific instead of generic.
6. **Work folder:** default `~/revoice-build/<slug>`. Their samples go here, not in the skill.

Then check the mbox path exists, and create `WORK`.

### Writing and brand

1. **Documents:** the folder (or files) to read, and/or a `--urls` file: a text file with one `http` or `https` URL per line, for pages the user owns. It reads `.md`, `.txt`, `.html`, `.docx` and `.pdf` (a `.pdf` needs the `pdftotext` program from poppler; without it, save the file as `.docx` or `.txt`). Other types are skipped. 20 documents of about 1,500 words each is a good set.
2. **Name:** `writing`: their full name. `brand`: the brand's name. Suggest a slug from it (`joe-smith`, `acme`) and use it unless they give another.
3. **Cutoff date:** optional, default none. Only a `date:` in a document's front matter is checked; undated documents are kept.
4. **Confirmations** (both must be a clear yes; do not go on without them):
   - `writing`: "This is my own writing, not AI-assisted." `brand`: "These are the brand's own documents, not AI-assisted."
   - "I may send these to a third-party API and to Claude." For `brand`, first say plainly that brand documents are often confidential, and ask the user to confirm they may send these documents: the kept passages go to the text analysis API, and about 15 of them are read by Claude. Tell them to take anything they may not send (client names, prices, internal projects) out of the folder before going on.
5. **Work folder:** default `~/revoice-build/<slug>`. Their passages go here, not in the skill.

There is no reference set for documents. Then check the folder and the `--urls` file exist, and create `WORK`.

## Phase 2: Filter and extract

Run from `WORK`:

### Email

```
<python> SKILL/build/mbox-filter-before.py "<mbox>" --before <cutoff> -o pre-ai.mbox
<python> SKILL/build/extract-samples.py pre-ai.mbox --from <addr1> --from <addr2> -o samples
<python> SKILL/build/extract-samples.py pre-ai.mbox --from <addr1> --from <addr2> --others -o reference   (only if the reference set is on; it is off by default)
```

Report: messages kept by the date filter, samples written, and the top drop reasons. If there are fewer than 20 samples, say so and offer to rerun extraction with `--min-words 100` (the default is 150). Extraction keeps at most 148 samples, the longest first; if it reports samples over the cap, say how many were left out.

### Writing and brand

```
<python> SKILL/build/extract-documents.py "<folder>" --urls <urls-file> --before <cutoff> -o samples
```

Leave out `--urls` if there is no URL list, `"<folder>"` if there are only URLs, and `--before` unless the user gave a cutoff date. It splits each document into passages of about 350 words (one passage is one sample) and drops code, tables, navigation, footers, legal lines and duplicates.

Report: documents read, documents skipped by reason, passages written, the top drop reasons, and how many were undated if a cutoff was given. If PDFs were skipped because `pdftotext` is missing, say so and offer the two ways out (install poppler, or save them as `.docx` or `.txt`). It keeps at most 148 passages, taken in turn from each document; if it reports passages over the cap, say how many were left out.

## Phase 3: Check the cost

After extraction, run from `WORK`:

```
<python> SKILL/build/build-profile.py --estimate --balance <balance> --samples samples --reference reference
```

`<balance>` is the balance phase 0 printed; leave out `--balance` if it said "unknown". This calls no API and spends nothing: phase 0 already checked the key, and the 148-sample default with one paid check fits the 250 free credits exactly. Leave out `--reference reference` if the reference set is off (it always is for documents). Report the estimated credit cost and the balance. If the balance is short, say so and ask before going on.

## Phase 4: Review the samples

Run from `WORK`, with the mode from phase 1 (`email`, `writing` or `brand`):

```
<python> SKILL/build/review-samples.py --author "<Name>" --mode <mode>
```

It runs on this machine with no network and no API key. It marks each sample KEEP or DROP and adds `verdict,score,reason` columns to `samples/index.csv`. `--author` lets it drop a sample signed (email) or bylined (writing) with a clearly different name; for `brand` give the brand name, it is not used. Do not read the samples yourself. Report the KEEP vs DROP counts it prints, and the top 3 drop reasons from the CSV's `reason` column.

### Email

If fewer than 15 are KEEP, tell the user the profile will be weaker and ask whether to continue.

### Writing and brand

With `--mode writing` or `--mode brand` it also prints a `coverage:` line (KEEP passages, and the documents they come from). Report it.

- **Below the floor** it exits with status 3: `writing` needs at least 10 KEEP passages; `brand` needs 10 KEEP passages from at least 3 documents. Stop the build here: nothing has been uploaded and phase 5 does not run. Tell the user how much more they need, in documents and words (a passage is about 350 words), then rerun phases 2 to 4 once they have added documents.
- **Below the minimum** (20 KEEP passages from at least 5 documents) it says the profile will be weaker. Tell the user the profile will be weaker and ask whether to continue.

### Stop: the user approves the samples

No sample has left the machine yet; phase 5 is the first upload. Before it, tell the user:

- How many samples are KEEP: those are what phase 5 sends to the API.
- They are plain files in `WORK/samples/`, one email or one passage each, and they can open any of them.
- To keep a sample from being sent, they change that row's `verdict` to DROP in `samples/index.csv`. Only KEEP rows are sent.

Then wait for an explicit go. Do not start phase 5 on silence or on an answer that is not a clear yes. Do not read the samples yourself at this step: the user reviews them, not you. When they say go, count the KEEP rows in `samples/index.csv` again (for documents, also the distinct `source` values among them). Email: if they dropped so many that fewer than 15 are KEEP, tell them the profile will be weaker and ask whether to continue, as above. Documents: below the floor, stop as above; below the minimum, warn and ask as above.

## Phase 5: Build the profile JSON

From `WORK`:

### Email

```
<python> SKILL/build/build-profile.py --samples samples --reference reference --author "<Name>" --source-type email --from <addr1> --from <addr2> --cutoff <cutoff> -o voice-profile.json
```

Leave out `--reference reference` if the reference set is off.

### Writing and brand

```
<python> SKILL/build/build-profile.py --samples samples --author "<Name>" --source-type <mode> --cutoff <cutoff> -o voice-profile.json
```

`<mode>` is `writing` or `brand`; for `brand`, `<Name>` is the brand's name. Leave out `--cutoff` unless the user gave a cutoff date. Do not pass `--from`.

### Both

It sends the kept samples to the API at https://api.yourvoice.dev/ and can take a minute. If it fails, tell the user in one plain line and stop:

- 401: the key is wrong; send the user back to phase 0.
- 402: out of credits; they need to add credits, then rerun.
- 429: too many requests; wait a few minutes and rerun.
- cannot reach the API: check the internet connection, then rerun.

## Phase 6: Write the voice file

1. Read `voice-profile.json`. Its `meta.samples.voice_profile` lists the samples the profile was built from. Read those samples in full. The local review is rule-based and can miss things: set aside any kept sample that clearly is not the author's own voice or language, and do not learn from it when writing the voice file. Say so in your report, with how many you set aside and why. **The samples are the authority on how the author sounds; the JSON numbers are averages.** When they disagree, trust the samples.
2. Write the voice file with these sections, in order, changed for the source as its subsection below says:
   - `# <Name>: Writing Profile`, then one short paragraph on what this file is and that samples beat stats.
   - **The voice in one paragraph.**
   - **Core traits:** 4 to 7 bullets, each with a short real example.
   - **Sentences:** length and variety, fragments, questions, typical openers.
   - **Word choice and signature phrases:** grouped by use (openers, structuring topics, stance and hedging, offers and warmth, closings, informal color). Use `fingerprint.distinctive_phrases` and `first_person_patterns`, but only list a phrase you actually see used that way in the samples. Without a reference set those phrases are ranked by how often they appear, so common phrases rise to the top: prefer the ones you see in the samples, and say so in your report. Include the rule "Use these naturally. Do not stack them." The one or two phrases that mark the voice most strongly are the ones a rewrite will overuse, so mark how often each may appear (see the subsection), and name any close stand-in it must not swap in instead (for example "Regarding" for "With regards to").
   - **Punctuation and formatting habits:** parentheses, quotes, dashes, exclamation points, lists, contractions.
   - **Paragraphs and structure:** paragraph length and the usual shape of one piece from start to finish (see the subsection).
   - **Pronouns:** when they write "I" and when "we".
   - **Stats reference:** a small table of features where the author differs from `comparison.baseline` mean, in words ("higher", "lower"), marked as calibration only.
   - **Do not:** AI tells to avoid (see the subsection), anything this author never does, "do not copy the author's typos", and "do not invent facts, numbers or names".
   - **Short examples from the corpus:** 4 to 6 short quotes, each labeled with the habit it shows.
   - **Before and after:** one invented generic AI-style draft and the same text in this voice.
3. **Privacy in quotes.** The file may be shared. Skip quotes with other people's private details: money about third parties, disputes, health, family, client rates, or anything addressed by name to someone the user works with now. Pick another line that shows the same habit.
4. One paragraph per line (never hard-wrap prose). No emojis.
5. Save it to `~/.config/revoice/voices/<slug>.md` (`mkdir -p` the folder first). Never save it inside `SKILL`: an update replaces that folder. Claude Code may ask the user to approve the write; tell them to expect that prompt. If the write is blocked, save to `WORK/<slug>.md` instead and give them the exact copy command for their system.

### Email

- If you notice another address of the user's while reading the profile's samples (for example in their signature) that is not in the list, tell them and offer to rerun extraction with it added.
- Mark the strongest one or two phrases "once per email at most".
- Punctuation and formatting habits also cover greetings and sign-offs.
- Paragraphs and structure: the usual shape of an email from start to finish.
- Do not: "delve", "I hope this email finds you well", "it's worth noting", "robust", "seamless", em-dash chains.

### Writing

- Mark the strongest one or two phrases "once per piece at most".
- No greetings or sign-offs.
- Paragraphs and structure: the usual shape of an article or post: title and opening, how it builds, how it ends.
- Do not: "in today's fast-paced world", "unlock", "game-changer", "delve", "it's worth noting", em-dash chains.

### Brand

- The heading is `# <Brand>: Writing Profile`.
- A brand voice is what the authors share: each core trait must show in passages from at least 3 different documents (the `source` column of `samples/index.csv`). Leave out a habit you see in one document only.
- Mark the strongest one or two phrases "once per piece at most".
- No greetings or sign-offs.
- Paragraphs and structure: the usual shape of a brand document: how it opens, how it makes its point, how it ends (call to action or not).
- Pronouns: when it writes "we" and "you", and when the brand names itself.
- Do not: "in today's fast-paced world", "unlock", "game-changer", "delve", "it's worth noting", em-dash chains.
- Privacy in quotes also skips client names, prices and internal project names.

## Phase 7: Make it the default

In `~/.config/revoice/config.yaml`, set `default_voice: <slug>`. If it already names a different real voice (anything other than `your-name`), ask before changing it.

## Phase 8: Show it working

Rewrite the demo text for the source in the new voice (base voice, no audience, no template) and show it.

### Email

> Hi team, I hope this email finds you well! I wanted to circle back on the budget review. After careful consideration, it's worth noting that the current plan is not robust — it leaves no room for delays. I would recommend we add a two-week buffer. Please let me know your thoughts at your earliest convenience.

### Writing

> In today's fast-paced world, planning a project is more important than ever. It's worth noting that most plans fail not because of bad ideas, but because they leave no room for delays. By adding a simple two-week buffer, you can unlock a more robust and seamless way of working — and that is a true game-changer.

### Brand

> We're thrilled to announce a game-changing update! In today's fast-paced world, our customers deserve tools that are robust and seamless. Starting next month, every plan includes a two-week planning buffer, so you can unlock more time for what matters most. Stay tuned for more exciting news!

### Both

Then finish with:

- Where everything is: the voice file, `WORK` (samples, JSON), and that `WORK` holds a private copy of their writing they can delete once they are happy.
- The 3 traits you are most and least sure about, so they know what to check first.
- How to use it: `/revoice <text>`, `/revoice @file`, and `--audience=casual|business|formal`, with the tip that they can add `~/.config/revoice/voices/<slug>-<audience>.md` holding only the differences for an audience.
