# Bundled voices

This folder ships with the skill and is replaced when the skill is updated. It holds only `example.md`. Do not put your own voices here.

Your voice profiles live in `~/.config/revoice/voices/`, one Markdown file per voice: `<slug>.md` (for example `joe-smith.md`). Set `default_voice` in your config to that slug. A voice there takes precedence over a bundled voice with the same name.

Optional audience overlays go next to it as `<slug>-<audience>.md` (for example `joe-smith-formal.md`). An overlay holds only the differences from the base voice, and wins where the two disagree.

Run `/revoice --build` to build a voice profile from your own email; it saves to `~/.config/revoice/voices/`.
