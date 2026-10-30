# revoice

A Claude Code skill that rewrites text so it sounds like you wrote it, not an AI. It works from a voice profile built from your own corpus of text, for example your email from before AI tools existed.

```
/revoice <text>
/revoice @draft.md
/revoice --audience=formal --output-path=out\letter.md @draft.md
```

Getting started is three steps: install the skill, save your API key, and run `/revoice --build`. Claude then walks you through building your voice profile.

## How it works

1. You export your sent email as an MBOX file.
2. `/revoice --build` keeps only emails from before AI tools, pulls out what you wrote yourself, and reviews them on your machine with plain rules to keep the ones that really sound like you.
3. A text analysis API measures the style of the kept samples.
4. Claude turns the measurements plus your real emails into a voice file, one readable Markdown file.
5. `/revoice` uses that file to rewrite any text in your voice.

## Requirements

- Claude Code.
- Python 3.10 or newer. The helpers use only the standard library, except `--sync`, which needs PyYAML (`pip install pyyaml`). On Windows, Python runs as `python`; `python3` there is usually a Microsoft Store shortcut.
- An API key for the text analysis API. It is only needed to build the profile, not to use the skill.

## Getting an API key

1. Sign up at https://yourvoice.dev/ — you get 250 free credits on sign-up. Buy a credit pack only if you need more.
2. On the dashboard, create an API key.
3. Save the key to `~/.config/revoice/api-key` (step 2 below shows how).

Only `--build` uses the key, and only to call `https://api.yourvoice.dev/`. Using `/revoice` to rewrite text never touches the API.

Building the profile charges credits per text sent; the API's docs at https://api.yourvoice.dev/ say what each request costs.

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

## Upgrading

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

## 3. Build your voice profile

First export your sent mail. For Gmail, use Google Takeout, choose Mail, and pick only the "Sent" label. You get an `.mbox` file. Large exports are fine.

Then, in Claude Code:

```
/revoice --build
```

Claude asks for the `.mbox` path, the addresses you send from, your name, and a few defaults, then does the rest: filtering, extracting, reviewing the samples on your machine, building the profile, and writing your voice file. Claude Code asks you to approve when it saves the voice file to `~/.config/revoice/voices/`. At the end it rewrites a sample email so you can see the result.

You can also give the answers up front:

```
/revoice --build mbox=C:\Users\you\Downloads\Sent.mbox from=you@example.com,you@work.com name="Your Name"
```

Read the voice file it wrote (`~/.config/revoice/voices/<your-slug>.md`) and fix anything that does not sound like you. It is plain Markdown, and you can edit it any time.

**What leaves your machine.** The full mailbox never does. The build pulls out up to 200 of your longest emails as samples (change this with `--max-samples` if you run the steps by hand). The KEEP/DROP review runs on your machine and sends nothing anywhere. To build the profile, the text analysis API gets, over HTTPS, only the kept samples (up to the 200 extracted, sent in batches of 100; the fingerprint step uses at most 100 of them) plus the reference set: up to 200 emails from other senders in the same mailbox, which the build compares your writing against so your signature phrases come out specific. The reference set is on by default; answer no to it in the build questions to keep other people's email off the API. Claude reads only the samples the profile is built from — 15 by default, `--top` if you run the steps by hand — to write the voice file, so those go to your Claude model provider like anything else you show Claude. Rewriting text with `/revoice` never touches the API. The work folder (default `~/revoice-build/<your-slug>`) holds your extracted email; delete it once you are happy with the voice file:

Windows (PowerShell): `Remove-Item -Recurse -Force "$HOME\revoice-build\<your-slug>"`

macOS or Linux: `rm -rf ~/revoice-build/<your-slug>`

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

## Running the steps by hand

The helpers are in `skill/revoice/build/` and each has `--help`. The order is `mbox-filter-before.py`, `extract-samples.py` (again with `--others` for the reference set), `review-samples.py` (runs locally, no network or API key), then `build-profile.py`. `skill/revoice/build.md` describes each step and the voice file format.

## Optional: SilverBullet

If you keep notes in SilverBullet, `sb:` paths let `--output-path` and `--template` read and write notes there, and `/revoice --sync` copies voice profiles from SilverBullet into the skill. This needs the SilverBullet MCP server and the `sb_*` config keys. If you do not use SilverBullet, leave those keys empty. Everything else works with local files.
