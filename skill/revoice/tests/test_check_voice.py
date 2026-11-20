"""Tests for check/check-voice.py (Epic 18 T4).

Both ways: the bundled assets/example.md passes (this pins the example
against the build.md phase 6 format), and copies broken one way at a time
fail with exactly the line the plan names.
"""
import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _load import SKILL, load, run_main

SCRIPT = SKILL / "check" / "check-voice.py"
cv = load(SCRIPT, "check_voice")
EXAMPLE = SKILL / "assets" / "example.md"
EXAMPLE_TEXT = EXAMPLE.read_text(encoding="utf-8")

# The 11 section headings from build.md phase 6 step 2, in order.
EXPECTED_SECTIONS = (
    "The voice in one paragraph",
    "Core traits",
    "Sentences",
    "Word choice and signature phrases",
    "Punctuation and formatting habits",
    "Paragraphs and structure",
    "Pronouns",
    "Stats reference",
    "Do not",
    "Short examples from the corpus",
    "Before and after",
)


def section_span(text: str, name: str) -> tuple[int, int]:
    """Line range [start, end) of one `## <name>` section, heading included."""
    lines = text.splitlines(keepends=True)
    start = next(i for i, l in enumerate(lines) if l.rstrip("\r\n") == f"## {name}")
    end = start + 1
    while end < len(lines) and not lines[end].startswith("## "):
        end += 1
    return start, end


def without_section(text: str, name: str) -> str:
    lines = text.splitlines(keepends=True)
    start, end = section_span(text, name)
    return "".join(lines[:start] + lines[end:])


def with_section_body(text: str, name: str, body: str) -> str:
    lines = text.splitlines(keepends=True)
    start, end = section_span(text, name)
    return "".join(lines[:start + 1]) + "\n" + body + "\n" + "".join(lines[end:])


def move_section_after(text: str, name: str, after: str) -> str:
    """Move the `## <name>` section to just after the `## <after>` section."""
    lines = text.splitlines(keepends=True)
    start, end = section_span(text, name)
    block = lines[start:end]
    rest = "".join(lines[:start] + lines[end:])
    _, after_end = section_span(rest, after)
    rest_lines = rest.splitlines(keepends=True)
    return "".join(rest_lines[:after_end] + block + rest_lines[after_end:])


class CheckVoice(unittest.TestCase):
    def check(self, text: str):
        with tempfile.TemporaryDirectory() as tmp:
            voice = Path(tmp) / "voice.md"
            voice.write_text(text, encoding="utf-8")
            return run_main(cv, "--voice", str(voice))

    def run_cli(self, *argv: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(SCRIPT), *argv],
                              capture_output=True, text=True, timeout=60)

    # -- the good way ------------------------------------------------------

    def test_bundled_example_passes(self):
        result, out = run_main(cv, "--voice", str(EXAMPLE))
        self.assertEqual(result, 0)
        self.assertEqual(out, "")

    def test_bundled_example_passes_on_the_command_line(self):
        proc = self.run_cli("--voice", str(EXAMPLE))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(proc.stdout, "")

    def test_curly_quoted_phrases_in_do_not_count(self):
        start, end = section_span(EXAMPLE_TEXT, "Do not")
        lines = EXAMPLE_TEXT.splitlines(keepends=True)
        # Replace every straight double quote pair with curly quotes.
        body = "".join(lines[start + 1:end])
        out_text = []
        open_quote = True
        for ch in body:
            if ch == '"':
                out_text.append("“" if open_quote else "”")
                open_quote = not open_quote
            else:
                out_text.append(ch)
        text = with_section_body(EXAMPLE_TEXT, "Do not", "".join(out_text).strip())
        result, out = self.check(text)
        self.assertEqual(result, 0, out)

    def test_utf8_bom_and_crlf_do_not_break_the_title(self):
        # A voice file saved by a Windows editor: BOM plus CRLF line ends.
        text = "\ufeff" + EXAMPLE_TEXT.replace("\n", "\r\n")
        with tempfile.TemporaryDirectory() as tmp:
            voice = Path(tmp) / "voice.md"
            voice.write_bytes(text.encode("utf-8"))
            result, out = run_main(cv, "--voice", str(voice))
        self.assertEqual(result, 0, out)

    def test_invent_rule_in_any_word_order_counts(self):
        body = ('- Do not use AI tells: "delve", "robust".\n'
                "- Do not invent names, numbers or facts.\n")
        result, out = self.check(with_section_body(EXAMPLE_TEXT, "Do not", body))
        self.assertEqual(result, 0, out)

    # -- one broken copy per problem ---------------------------------------

    def test_do_not_removed_reports_missing_section(self):
        result, out = self.check(without_section(EXAMPLE_TEXT, "Do not"))
        self.assertEqual(result, 1)
        self.assertEqual(out.splitlines(), ["MISSING-SECTION Do not"])

    def test_do_not_removed_on_the_command_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            voice = Path(tmp) / "voice.md"
            voice.write_text(without_section(EXAMPLE_TEXT, "Do not"), encoding="utf-8")
            proc = self.run_cli("--voice", str(voice))
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stdout.splitlines(), ["MISSING-SECTION Do not"])

    def test_another_section_removed_reports_missing_section(self):
        result, out = self.check(without_section(EXAMPLE_TEXT, "Stats reference"))
        self.assertEqual(result, 1)
        self.assertEqual(out.splitlines(), ["MISSING-SECTION Stats reference"])

    def test_pronouns_after_do_not_reports_out_of_order(self):
        text = move_section_after(EXAMPLE_TEXT, "Pronouns", "Do not")
        result, out = self.check(text)
        self.assertEqual(result, 1)
        self.assertEqual(out.splitlines(), ["OUT-OF-ORDER Pronouns"])

    def test_do_not_without_a_quoted_phrase(self):
        body = ("- Do not use AI tells or long opening pleasantries.\n"
                "- Do not copy the author's typos.\n"
                "- Do not invent facts, numbers or names.\n")
        result, out = self.check(with_section_body(EXAMPLE_TEXT, "Do not", body))
        self.assertEqual(result, 1)
        self.assertEqual(out.splitlines(), ["NO-QUOTED-PHRASE Do not"])

    def test_emoji_reports_its_line_number(self):
        lines = EXAMPLE_TEXT.splitlines(keepends=True)
        lines.insert(4, "Ship it \U0001F680\n")  # becomes line 5
        result, out = self.check("".join(lines))
        self.assertEqual(result, 1)
        self.assertEqual(out.splitlines(), ["EMOJI line 5"])

    def test_each_emoji_line_is_reported_once(self):
        lines = EXAMPLE_TEXT.splitlines(keepends=True)
        lines.insert(4, "Ship it \U0001F680 \U0001F389\n")
        lines.insert(10, "Nice ✅\n")  # becomes line 11
        result, out = self.check("".join(lines))
        self.assertEqual(result, 1)
        self.assertEqual(out.splitlines(), ["EMOJI line 5", "EMOJI line 11"])

    # -- further shape rules from Proposed Solution item 4 ------------------

    def test_first_line_must_be_a_writing_profile_title(self):
        text = EXAMPLE_TEXT.replace("# Alex Example: Writing Profile",
                                    "# Alex Example", 1)
        result, out = self.check(text)
        self.assertEqual(result, 1)
        self.assertIn("BAD-TITLE line 1", out.splitlines())

    def test_do_not_without_the_invent_rule(self):
        body = '- Do not use AI tells: "delve", "robust", "seamless".\n'
        result, out = self.check(with_section_body(EXAMPLE_TEXT, "Do not", body))
        self.assertEqual(result, 1)
        self.assertEqual(out.splitlines(), ["NO-INVENT-RULE Do not"])

    def test_empty_do_not_section(self):
        result, out = self.check(with_section_body(EXAMPLE_TEXT, "Do not", ""))
        self.assertEqual(result, 1)
        self.assertEqual(out.splitlines(), ["EMPTY-SECTION Do not"])

    def test_two_problems_are_two_lines(self):
        lines = without_section(EXAMPLE_TEXT, "Do not").splitlines(keepends=True)
        lines.insert(4, "Ship it \U0001F680\n")
        result, out = self.check("".join(lines))
        self.assertEqual(result, 1)
        self.assertEqual(out.splitlines(), ["MISSING-SECTION Do not", "EMOJI line 5"])

    # -- the heading tuple is pinned to build.md and the example ------------

    def test_sections_tuple_holds_the_11_build_md_headings_in_order(self):
        self.assertEqual(cv.SECTIONS, EXPECTED_SECTIONS)
        self.assertIsInstance(cv.SECTIONS, tuple)
        build_md = (SKILL / "build.md").read_text(encoding="utf-8")
        phase6 = build_md.split("## Phase 6")[1].split("## Phase 7")[0]
        step2 = phase6.split("2. Write the voice file")[1].split("\n3.")[0]
        positions = []
        for name in cv.SECTIONS:
            self.assertIn(f"**{name}", step2)
            positions.append(step2.index(f"**{name}"))
        self.assertEqual(positions, sorted(positions))
        for name in cv.SECTIONS:
            self.assertIn(f"## {name}\n", EXAMPLE_TEXT)

    # -- arguments and unreadable files -------------------------------------

    def test_help_exits_0(self):
        proc = self.run_cli("--help")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("--voice", proc.stdout)

    def test_no_arguments_exits_2(self):
        proc = self.run_cli()
        self.assertEqual(proc.returncode, 2)

    def test_missing_file_exits_2_with_one_stderr_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = str(Path(tmp) / "no-such-voice.md")
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                result, out = run_main(cv, "--voice", missing)
        self.assertEqual(result, 2)
        self.assertEqual(out, "")
        self.assertEqual(len(err.getvalue().splitlines()), 1)
        self.assertIn("no-such-voice.md", err.getvalue())

    def test_directory_exits_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                result, out = run_main(cv, "--voice", tmp)
        self.assertEqual(result, 2)
        self.assertEqual(out, "")
        self.assertEqual(len(err.getvalue().splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
