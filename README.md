# revoice

A Claude Code skill that rewrites text so it sounds like you wrote it, not an AI. It works from a voice profile built from your own corpus of text: your email, your writing, or your brand's documents.

```
/revoice <text>
/revoice @draft.md
/revoice --audience=formal --output-path=out\letter.md @draft.md
```

Getting started is three steps: install the skill, save your API key, and run `/revoice --build`. Claude then walks you through building your voice profile.

## How it works

1. You point the build at your writing: an email export (MBOX), a folder of your own writing, or a folder of brand documents.
2. `/revoice --build` pulls out what you wrote yourself — for email, only messages from before AI tools — and reviews them on your machine with plain rules to keep the ones that really sound like you.
3. A text analysis API measures the style of the kept samples.
4. Claude turns the measurements plus your real writing into a voice file, one readable Markdown file.
5. `/revoice` uses that file to rewrite any text in your voice.

## Requirements

- Claude Code.
- Python 3.10 or newer. The helpers use only the standard library, except `--sync`, which needs PyYAML (`pip install pyyaml`). Reading `.pdf` files also uses the `pdftotext` program (poppler) when it is installed; without it, PDFs are skipped. On Windows, Python runs as `python`; `python3` there is usually a Microsoft Store shortcut.
- An API key for the text analysis API. It is only needed to build the profile, not to use the skill.

## Getting an API key

1. Sign up at https://yourvoice.dev/ — you get 250 free credits on sign-up. Buy a credit pack only if you need more.
2. On the dashboard, create an API key.
3. Save the key to `~/.config/revoice/api-key` (step 2 below shows how).

Only `--build` uses the key, and only to call `https://api.yourvoice.dev/`. Using `/revoice` to rewrite text never touches the API.

### What a build costs

The API charges 1 credit per text it analyzes. A build sends one joined text, every kept sample, every reference email, and up to 100 of the kept samples again for the fingerprint, so:

```text
cost = 1 + kept samples + reference emails + min(kept samples, 100)
```

- A small mailbox with 30 kept samples and no reference set: 1 + 30 + 0 + 30 = 61 credits.
- 149 kept samples plus 200 reference emails: 1 + 149 + 200 + 100 = 450 credits (add 1 for the key check).

A default build (at most 148 samples, no reference set) costs at most 1 + 148 + 100 = 249 credits, plus 1 for the key check: 250, exactly the free grant. The re-check before the build spends anything is the free `--estimate`. Adding the reference set costs more: one extra credit per reference email, so you need to buy a credit pack first if that takes the total over your balance. The build checks your balance before it spends and stops if it cannot cover the cost. The API's docs at https://api.yourvoice.dev/ list what each request costs.

For documents (your writing or brand documents), a passage is a sample and there is no reference set, so the same formula counts passages:

```text
cost = 1 + kept passages + min(kept passages, 100)
```

20 documents of about 1,500 words give about 85 passages: 1 + 85 + 85 = 171 credits, plus 1 for the key check — well inside the 250 free credits.

## Text analysis API

- API: https://api.yourvoice.dev/
- Docs: https://api.yourvoice.dev/swagger-ui/

Every request needs your key in an `X-API-Key` header. The build already points at this API and reads the key from a file (step 2 below), so you never call the API by hand and never paste the key into Claude.

## 1. Install the skill

The recommended way is the Claude Code plugin. In Claude Code, run these two commands:

```
/plugin marketplace add samestrin/revoice-skill
/plugin install revoice@revoice-skill
```

Start a new Claude Code session so it picks up the skill. The command is `/revoice`. The first `/revoice --build` creates your config at `~/.config/revoice/config.yaml`, and your voice files live in `~/.config/revoice/voices/`, outside the plugin folder, so updating the plugin never deletes them.

### Alternative: copy the folder

You can also copy the skill folder into Claude Code's skills folder. First get the repository (the same commands work in PowerShell, Terminal and any shell with git):

```bash
git clone https://github.com/samestrin/revoice-skill.git
cd revoice-skill
```

Then, from that folder:

Windows (PowerShell):

```powershell
New-Item -ItemType Directory -Force "$HOME\.claude\skills" | Out-Null
Copy-Item -Recurse skill\revoice "$HOME\.claude\skills\revoice"
```

macOS or Linux:

```bash
mkdir -p ~/.claude/skills
cp -R skill/revoice ~/.claude/skills/revoice
```

Start a new Claude Code session so it picks up the skill.

**Switching from the copy-folder install to the plugin:** move your voice files from the copied folder's `assets/` to `~/.config/revoice/voices/`, then delete `~/.claude/skills/revoice/`. If you leave it there, it takes the bare `/revoice` command and the plugin's copy does not run.

You can try the skill before building your own voice, with the fictional example voice that ships with it. No config is needed for this:

```
/revoice --voice=example Thanks for the quick reply
```

Until you have a config, always pass `--voice`: without it the skill does not know which voice to use and asks you to create the config. Without a config there is no default audience, relative paths are relative to the current folder, and SilverBullet (`sb:` paths and `--sync`) is off.

### What it looks like

This is the before-and-after that ships in the example voice file, `skill/revoice/assets/example.md`. The voice belongs to "Alex Example", a fictional person; nothing in it comes from a real mailbox. Pass a draft like the first one to `/revoice --voice=example` and you get text in that voice, like the second one.

Generic AI-style draft:

> Hello, I hope this email finds you well. I wanted to reach out regarding the project timeline. After careful consideration, it's worth noting that the current schedule is not robust. I would recommend that we add a buffer. Please let me know your thoughts at your earliest convenience.

In the example voice:

> Hi team,
>
> Quick note on the timeline. I think the current schedule is too tight, since one late delivery pushes everything back. Can we add a week of buffer?
>
> Happy to update the plan if that works.
>
> Thanks,
> Alex

## Upgrading

To see which version you have, run `/plugin` and open the installed `revoice` plugin; its screen shows the version.

Fixes reach plugin users in tagged releases: `/plugin update` gets a new version only after one is released. See the [Releases page](https://github.com/samestrin/revoice-skill/releases) for each version and what changed.

With the plugin install, update through `/plugin`:

```
/plugin update revoice@revoice-skill
```

To uninstall:

```
/plugin uninstall revoice@revoice-skill
```

Your voice files in `~/.config/revoice/voices/` and your config and API key under `~/.config/revoice/` are not touched by an update or uninstall. Start a new Claude Code session to pick up the new version.

With the copy-folder install, from the cloned repository folder, pull the latest version and copy the skill's files over the installed copy:

Windows (PowerShell):

```powershell
git pull
Copy-Item -Recurse -Force skill\revoice\* "$HOME\.claude\skills\revoice\"
```

macOS or Linux:

```bash
git pull
cp -R skill/revoice/. ~/.claude/skills/revoice/
```

To uninstall the copy-folder install, delete the `revoice` folder from `~/.claude/skills/`. Either way, delete `~/.config/revoice/` too if you also want to remove your voice files, config and API key.

## 2. Save your API key

Save the key in a file that only you read. Claude checks that the file exists but never opens it, so the key stays out of your chat transcripts.

Windows (PowerShell):

```powershell
New-Item -ItemType Directory -Force "$HOME\.config\revoice" | Out-Null
notepad "$HOME\.config\revoice\api-key"
```

Paste the key, save, and close Notepad.

macOS: copy the key, then:

```bash
mkdir -p ~/.config/revoice && pbpaste > ~/.config/revoice/api-key
```

Linux: copy the key, then:

```bash
mkdir -p ~/.config/revoice && (xclip -selection clipboard -o 2>/dev/null || wl-paste) > ~/.config/revoice/api-key && chmod 600 ~/.config/revoice/api-key
```

No clipboard tool? Run `mkdir -p ~/.config/revoice && cat > ~/.config/revoice/api-key`, paste the key, press Enter, then Ctrl-D, then `chmod 600 ~/.config/revoice/api-key`.

## 3. Build your voice profile

In Claude Code:

```
/revoice --build
```

The first question is where your writing is: an email export, a folder of your own writing, or a folder of brand documents. Claude then asks only what that source needs and does the rest: extracting, reviewing the samples on your machine, building the profile, and writing your voice file. You review and approve the samples before the upload: before any sample is sent to the API, Claude stops, tells you how many are kept and that they are plain files in the work folder's `samples/`, and waits for your go. To keep one from being sent, change its `verdict` to DROP in `samples/index.csv`. Claude Code asks you to approve when it saves the voice file to `~/.config/revoice/voices/`. At the end it rewrites a sample text so you can see the result.

### From an email export

Export your sent mail. For Gmail, use Google Takeout, choose Mail, and pick only the "Sent" label. You get an `.mbox` file. Large exports are fine.

Claude asks for the `.mbox` path, the addresses you send from, your name, and a few defaults, including the cutoff date that keeps AI-assisted writing out.

You can also give the answers up front:

```
/revoice --build mbox=C:\Users\you\Downloads\Sent.mbox from=you@example.com,you@work.com name="Your Name"
```

### From a folder of your writing

Point the build at a folder (or single files) of your own articles, posts or essays. It reads `.md`, `.txt`, `.html`/`.htm`, `.docx` and `.pdf`. A `.pdf` needs the `pdftotext` program (poppler) on your PATH; without it, the file is skipped: install poppler, or save it as `.docx` or `.txt`. Other types are skipped and counted.

You can also give a `--urls` list: a text file with one `http` or `https` URL per line, for pages you own. Your machine fetches the pages one at a time; the build never follows links.

Each document is split into passages of about 350 words (150 to 500), never cutting a paragraph; code, tables, navigation, footers, legal lines and duplicates are dropped, and the review on your machine also drops quoted AI model output (a model's answer pasted into the document) and one-cell-per-line table text. One passage is one sample. At most 148 passages are kept, taken in turn from each document.

Claude asks for your name and two confirmations: that this is your own writing, not AI-assisted, and that you may send it to the text analysis API and to Claude. A cutoff date is optional and only checks a `date:` in a document's front matter; undated documents are kept.

### From a folder of brand documents

Point the build at a folder of a business's documents: several authors, one brand voice. It reads the same `.md`, `.txt`, `.html`/`.htm`, `.docx` and `.pdf` files (the same `pdftotext` note applies) and the same `--urls` list. The profile is named for the brand, and every author's passages are kept.

Brand documents are often confidential. The build says so plainly and asks you to confirm you may send these documents before it reads them; take anything you may not send to a third-party API or to Claude (client names, prices, internal project names) out of the folder first.

### How much writing you need

A passage is about 350 words. The review counts what it keeps:

| Source | Hard floor (the build stops) | Minimum (warns, asks to continue) | Recommended |
|---|---|---|---|
| Email | 1 KEEP sample | 15 KEEP samples | 20+ samples |
| Writing | 10 KEEP passages | 20 KEEP passages from at least 5 documents | 40+ passages from 10+ documents (about 15,000 words) |
| Brand | 10 KEEP passages from at least 3 documents | 20 KEEP passages from at least 5 documents | 40+ passages from 12+ documents by at least 3 authors if known |

Below the hard floor the build stops before anything is uploaded and tells you how many more documents or words you need. Between the floor and the minimum it says the profile will be weaker and asks whether to continue.

Read the voice file it wrote (`~/.config/revoice/voices/<your-slug>.md`) and fix anything that does not sound like you. It is plain Markdown, and you can edit it any time.

**What leaves your machine.** Email: the full mailbox never does. The build pulls out up to 148 of your longest emails as samples (change this with `--max-samples` if you run the steps by hand). The KEEP/DROP review runs on your machine and sends nothing anywhere. You review and approve the samples before the upload: none of your samples is sent until you say go, and a sample you mark DROP is never sent. To build the profile, the text analysis API gets, over HTTPS, only the kept samples (up to the 148 extracted, sent in batches of 100; the fingerprint step uses at most 100 of them) plus, only if you opt in, the reference set: up to 148 emails from other senders in the same mailbox, which the build compares your writing against so your signature phrases come out specific. The reference set is off by default and costs extra credits; leave it off to keep other people's email off the API. Claude reads only the samples the profile is built from — 15 by default, `--top` if you run the steps by hand — to write the voice file, so those go to your Claude model provider like anything else you show Claude. Rewriting text with `/revoice` never touches the API. The work folder (default `~/revoice-build/<your-slug>`) holds your extracted email; delete it once you are happy with the voice file:

Windows (PowerShell): `Remove-Item -Recurse -Force "$HOME\revoice-build\<your-slug>"`

macOS or Linux: `rm -rf ~/revoice-build/<your-slug>`

**Writing samples:** the folder never leaves the machine as a whole. Extraction and the KEEP/DROP review run on your machine. To build the profile, only the kept passages (up to 148, sent in batches of 100; the fingerprint step uses at most 100 of them) go to the text analysis API over HTTPS, and only after you approve them; the 15 passages the profile is built from are read by Claude, so those go to your Claude model provider like anything else you show Claude. For a `--urls` list, your machine fetches the pages; nothing is sent to the API before you approve the samples. There is no reference set. The work folder holds your passages; delete it the same way once you are happy with the voice file.

**Brand documents are often confidential.** Before you build, take anything you may not send to a third-party API or to Claude out of the folder: client names, prices, internal project names. The warning is plain, and the build asks you to confirm you may send these documents before it reads them. What leaves is the same as for writing samples: only the kept passages go to the text analysis API over HTTPS after you approve them, and the 15 the profile is built from are read by Claude. Several authors is the point: every author's passages are kept, and the profile is named for the brand.

### If the build stops

The build checks your key and your balance before it spends credits on the build: its first step spends 1 credit to test the key and read the balance, before the mbox steps, and it counts the build's cost before it sends your samples. If something goes wrong, it stops with one plain line:

- **Wrong key** ("the API rejected the key", HTTP 401): check `~/.config/revoice/api-key` holds the key from your yourvoice.dev dashboard with nothing else in the file, save it again (see "2. Save your API key"), then rerun `/revoice --build`.
- **Out of credits** ("out of credits", HTTP 402 from the API; or, before your samples are sent, "short by N credits" from the cost check or "this build costs N credits and you have M credits left"): buy a credit pack at https://yourvoice.dev/, or rebuild with fewer samples or without the reference set, then rerun.
- **Too many requests** ("rate limited", HTTP 429): wait the number of seconds it says (or a few minutes), then rerun.
- **Cannot reach the API** ("cannot reach the API"): check your internet connection and that https://api.yourvoice.dev/ answers, then rerun.

## Use the skill

| Command | What it does |
|---|---|
| `/revoice <text>` | Rewrites the text and shows it. |
| `/revoice @draft.md` | Rewrites a file. |
| `--output-path=<path>` | Also saves the result. If the file exists, it asks before overwriting. |
| `--template=<path>` | Follows a template's layout (for example an email record format). The voice still controls the wording. |
| `--audience=casual\|business\|formal` | Steers the tone. Without it, you get your plain voice. |
| `--voice=<slug>` | Uses a different voice file. |
| `--build` | Builds a new voice profile (above). |

The skill keeps every fact, number, name and ask from the input. It does not add new ones.

**Tuning.** To change how it writes, edit your voice file, for example by adding a line to its "Do not" section. To tune one audience, create `~/.config/revoice/voices/<slug>-formal.md` next to it with only the differences (for example "no idioms, sign off with Regards,"). It adds to your voice file rather than replacing it. Without one, the skill uses its own built-in steering for that audience.

## Checks on every rewrite

After Claude rewrites your text it runs three small checks on the rewrite, and the build runs a fourth on the voice file it writes. They run on your machine, with no network call, and use only Python's standard library:

| Script | What it lists |
|---|---|
| `check/check-facts.py` | A number, date, URL or email address from your input that is missing from the rewrite, or one the rewrite adds. It catches numbers, dates, URLs and email addresses only: names and other facts are not checked. |
| `check/check-do-not.py` | A phrase from your voice file's "Do not" section, or a phrase the voice allows once that the rewrite uses more often. |
| `check/check-format.py` | A hard-wrap: prose broken across lines instead of one paragraph per line. |
| `check/check-voice.py` | A problem in the voice file's shape when the build writes it: the title, the 11 sections in order, a filled "Do not" section, and no emoji. |

Claude fixes only what the lines list and runs the checks once more. A line still listed is shown under "Notes" after the rewrite, not hidden. These checks catch only what code can: they cannot tell whether a rewrite sounds like you, and they cannot judge a name, a claim or a changed detail, so read the result as well.

## Running the steps by hand

The helpers are in `skill/revoice/build/` and each has `--help`. For email the order is `mbox-filter-before.py`, `extract-samples.py` (again with `--others` for the reference set), `review-samples.py` (runs locally, no network or API key), then `build-profile.py`. For documents it is `extract-documents.py`, `review-samples.py --mode writing|brand`, then `build-profile.py --source-type writing|brand`. `skill/revoice/build.md` describes each step and the voice file format.

The checks are in `skill/revoice/check/`, each with `--help` and no network call: `check-facts.py --original <file> --rewrite <file>`, `check-do-not.py --voice <voice file> --rewrite <file>`, `check-format.py --rewrite <file>`, and `check-voice.py --voice <voice file>`. Each prints one line per problem and exits 0 when it finds nothing, 1 when it lists a problem and 2 for bad arguments or an unreadable file. `SKILL.md` Step 4 and `build.md` phase 6 say when Claude runs them.

## Optional: SilverBullet

If you keep notes in SilverBullet, `sb:` paths let `--output-path` and `--template` read and write notes there, and `/revoice --sync` copies voice profiles from SilverBullet into the skill. This needs the SilverBullet MCP server and the `sb_*` config keys. If you do not use SilverBullet, leave those keys empty. Everything else works with local files.
