# Voice files

Put voice profiles here, one Markdown file per voice: `<slug>.md` (for example `joe-smith.md`). Set `default_voice` in your config to that slug.

Optional audience overlays go next to it as `<slug>-<audience>.md` (for example `joe-smith-formal.md`). An overlay holds only the differences from the base voice, and wins where the two disagree.

Run `/revoice --build` to build a voice profile from your own email.
