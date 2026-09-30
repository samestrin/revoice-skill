# revoice

A Claude Code skill that rewrites text so it sounds like you wrote it, not an AI. It works from a voice profile built from your own email, written before AI tools existed.

```
/revoice <text>
/revoice @draft.md
/revoice --audience=formal --output-path=out\letter.md @draft.md
```

The repository has two parts:

- `skill/revoice/`: the skill itself.
- `profile/`: helpers that build your voice profile from an email export.

## How it works

1. Export your sent email as an MBOX file.
2. The helpers keep only emails from before AI tools, pull out what you wrote yourself, and send the best ones to a text analysis API that measures your style.
3. Claude turns the measurements plus your real emails into a readable voice profile, one Markdown file.
4. `/revoice` uses that file to rewrite any text in your voice.

## Requirements

- Claude Code.
- Python 3.10 or newer. The helpers use only the standard library.
- An API key for `https://text-analysis-api.estr.in` (docs: `https://text-analysis-api.estr.in/swagger-ui/`). The key is only needed to build the profile, not to use the skill.

On Windows, run Python as `python`. `python3` on Windows is usually a Microsoft Store shortcut, not real Python.

## Install the skill

PowerShell:

```powershell
Copy-Item -Recurse skill\revoice "$HOME\.claude\skills\revoice"
New-Item -ItemType Directory -Force "$HOME\.config\revoice" | Out-Null
Copy-Item config.example.yaml "$HOME\.config\revoice\config.yaml"
```

macOS or Linux:

```bash
cp -R skill/revoice ~/.claude/skills/revoice
mkdir -p ~/.config/revoice && cp config.example.yaml ~/.config/revoice/config.yaml
```

Then open the config and set `default_voice` to your slug, for example `joe-smith`. Your voice file will be `assets/joe-smith.md` inside the installed skill folder. Start a new Claude Code session so it picks up the skill.

## Build your voice profile

Run these from the repository folder. The examples are PowerShell. Your email stays on your machine except for the samples sent to the API in step 4.

**1. Export your sent mail.** For Gmail, use Google Takeout, choose Mail, and pick only the "Sent" label. You get an `.mbox` file. Large exports are fine; the helpers read them one message at a time.

**2. Keep only emails from before AI tools.**

```powershell
python profile\mbox-filter-before.py Sent.mbox --before 2022-09-01 -o pre-ai.mbox
```

`2022-09-01` is three months before ChatGPT launched. Emails with no readable date are dropped.

**3. Pull out what you wrote.** Use every address you have sent from:

```powershell
python profile\extract-samples.py pre-ai.mbox --from you@example.com --from you@work.com -o samples
python profile\extract-samples.py pre-ai.mbox --from you@example.com --from you@work.com --others -o reference
```

The first command writes one file per email you wrote, with quoted replies, signatures, forwards and duplicates removed. The second is optional but recommended: it collects other people's emails from the same mailbox, so the API can tell which phrases are really yours rather than just common. Without it, your "signature phrases" come out generic ("let me know", "need to").

**4. Review the samples with Claude.** In Claude Code, from the repository folder:

> Follow step A in profile/INSTRUCTIONS.md on the samples folder.

Claude marks each email KEEP or DROP and scores it. Aim for 15 or more KEEP.

**5. Build the profile.**

```powershell
$env:TEXT_ANALYSIS_API_KEY = "<your key>"
python profile\build-profile.py --samples samples --reference reference --author "Your Name" --from you@example.com --cutoff 2022-09-01 -o voice-profile.json
```

Leave out `--reference reference` if you skipped it in step 3.

**6. Write the voice file with Claude.**

> Follow step B in profile/INSTRUCTIONS.md. Save it to voice/your-name.md.

Read the result and fix anything that does not sound like you. It is plain Markdown, and you can edit it any time. Then copy it into the installed skill (Claude Code treats its own skills folder as protected, so do this step yourself):

```powershell
Copy-Item voice\your-name.md "$HOME\.claude\skills\revoice\assets\your-name.md"
```

After any later edit to `voice/your-name.md`, copy it again.

**Keep private files private.** The `.mbox`, `samples/`, `reference/`, `voice-profile.json` and `voice/` are all personal. `.gitignore` keeps them out of Git.

## Use the skill

| Command | What it does |
|---|---|
| `/revoice <text>` | Rewrites the text and shows it. |
| `/revoice @draft.md` | Rewrites a file. |
| `--output-path=<path>` | Also saves the result. If the file exists, it asks before overwriting. |
| `--template=<path>` | Follows a template's layout (for example an email record format). The voice still controls the wording. |
| `--audience=casual\|business\|formal` | Steers the tone. Without it, you get your plain voice. |
| `--voice=<slug>` | Uses a different voice file. |

The skill keeps every fact, number, name and ask from the input. It does not add new ones.

**Tuning.** To change how it writes, edit your voice file. For example, add a line to its "Do not" section. To tune one audience, create `assets/<slug>-formal.md` with only the differences (for example "no idioms, sign off with Regards,").

## Optional: SilverBullet

If you keep notes in SilverBullet, `sb:` paths let `--output-path` and `--template` read and write notes there, and `/revoice --sync` copies voice profiles from SilverBullet into the skill. This needs the SilverBullet MCP server and the `sb_*` config keys. If you do not use SilverBullet, leave those keys empty. Everything else works with local files.
