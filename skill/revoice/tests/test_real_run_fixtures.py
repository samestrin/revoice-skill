"""Guards on the test fixtures (Epic 19 T1, EST-7833).

The real-run fixtures must stay short excerpts of the operator's evidence:
a test fails if any fixture file is over 700 words, if a file named
voice-profile.json or a folder named samples/ is added, if a real_run
excerpt is over 600 words, if a secret-shaped string appears, or if a
fixture mailbox holds a real person's address. Every check is tested both
ways: it must flag the real bad shape and pass the known-good fixtures.
"""
import re
import tempfile
import unittest
from email.utils import getaddresses
from pathlib import Path

from _load import FIXTURES, REAL_RUN, real_run, real_run_body

MAX_WORDS = 700
EXCERPT_MAX_WORDS = 600

# The excerpts Epic 19's tasks build their tests from (real_run/README.md).
EXPECTED = [
    "README.md",
    "prose_comparing13_a.md", "prose_comparing13_b.md",
    "prose_72faster_a.md", "prose_72faster_b.md",
    "prose_llmenv_a.md", "prose_llmenv_b.md",
    "llm_output_docx_a.md", "llm_output_docx_b.md", "llm_output_pdf_a.md",
    "table_docx_numbers.md",
    "brand_icons_widgets.html",
    "copy_article_html.md", "copy_article_pdf.txt", "copy_article_docx.md",
]

SECRET_SHAPES = [
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)\b(?:api[_-]?key|secret|token|password)\b\s*[:=]\s*[\"']?[A-Za-z0-9_./+-]{16,}"),
]
FICTIONAL_DOMAINS = {"example.com", "example.org", "example.net"}


def fixture_violations(root: Path) -> list[str]:
    """Every way `root` breaks the fixture rules (empty when it is clean)."""
    problems = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if path.is_dir():
            if path.name == "samples":
                problems.append(f"forbidden folder: {rel}/")
            continue
        if path.name == "voice-profile.json":
            problems.append(f"forbidden file: {rel}")
        words = len(path.read_text(encoding="utf-8").split())
        if words > MAX_WORDS:
            problems.append(f"over {MAX_WORDS} words ({words}): {rel}")
    return problems


def excerpt_violations(root: Path) -> list[str]:
    problems = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        words = len(path.read_text(encoding="utf-8").split())
        if words > EXCERPT_MAX_WORDS:
            problems.append(f"over {EXCERPT_MAX_WORDS} words ({words}): {path.name}")
    return problems


def secret_hits(text: str) -> list[str]:
    return [m.group(0) for shape in SECRET_SHAPES for m in shape.finditer(text)]


def non_fictional_addresses(mbox_text: str) -> list[str]:
    lines = [l for l in mbox_text.splitlines()
             if l.lower().startswith(("from:", "to:", "cc:", "bcc:"))]
    return [addr for _, addr in getaddresses(lines)
            if addr and addr.split("@")[-1].lower() not in FICTIONAL_DOMAINS]


class FixtureGuardTest(unittest.TestCase):
    def test_fixtures_pass_the_guards(self):
        self.assertEqual(fixture_violations(FIXTURES), [])
        self.assertEqual(excerpt_violations(REAL_RUN), [])

    def test_expected_real_run_excerpts_exist(self):
        for name in EXPECTED:
            self.assertTrue((REAL_RUN / name).is_file(), name)

    def test_no_secret_in_any_fixture(self):
        for path in sorted(FIXTURES.rglob("*")):
            if path.is_file():
                self.assertEqual(secret_hits(path.read_text(encoding="utf-8")), [],
                                 f"secret-shaped text in {path}")

    def test_fixture_mailboxes_hold_only_fictional_people(self):
        mboxes = sorted(FIXTURES.rglob("*.mbox"))
        self.assertTrue(mboxes)
        for path in mboxes:
            self.assertEqual(non_fictional_addresses(path.read_text(encoding="utf-8")),
                             [], f"real address in {path}")

    def test_loader_reads_excerpts(self):
        text = real_run("prose_comparing13_a.md")
        self.assertTrue(text.startswith("# Comparing 13 LLM Providers"))
        body = real_run_body("prose_comparing13_a.md")
        self.assertTrue(body.startswith("Why? Latency measures"))
        self.assertNotIn("# Comparing", body)

    # Each guard both ways: the bad shape is caught, the good one passes.
    def test_word_guard_catches_long_files_and_passes_short_ones(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "good.md").write_text("word " * MAX_WORDS, encoding="utf-8")
            self.assertEqual(fixture_violations(root), [])
            (root / "bad.md").write_text("word " * (MAX_WORDS + 1), encoding="utf-8")
            problems = fixture_violations(root)
            self.assertEqual(len(problems), 1)
            self.assertIn("bad.md", problems[0])

    def test_excerpt_guard_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "good.md").write_text("word " * EXCERPT_MAX_WORDS, encoding="utf-8")
            self.assertEqual(excerpt_violations(root), [])
            (root / "bad.md").write_text("word " * (EXCERPT_MAX_WORDS + 1), encoding="utf-8")
            self.assertEqual(len(excerpt_violations(root)), 1)

    def test_forbidden_names_are_caught(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "voice-profile.json").write_text("{}\n", encoding="utf-8")
            (root / "samples").mkdir()
            (root / "samples" / "a.md").write_text("short\n", encoding="utf-8")
            problems = fixture_violations(root)
            self.assertEqual(len(problems), 2, problems)
            self.assertTrue(any("voice-profile.json" in p for p in problems))
            self.assertTrue(any("samples/" in p for p in problems))

    def test_secret_guard_both_ways(self):
        for bad in ("sk-abcdefghijklmnopqrstuvwx", "AKIAIOSFODNN7EXAMPLE",
                    "-----BEGIN RSA PRIVATE KEY-----",
                    'api_key = "abcdef0123456789abcdef"'):
            self.assertTrue(secret_hits(bad), bad)
        for good in ("the API key file keeps the key out of chat transcripts",
                     "AI21_API_KEY=", "OPENAI_* environment variables",
                     "sha1 b2c86d150d203f356b1710511a0786f0dcbc6b70f58cf6bb1ef97a9cee9df262"):
            self.assertEqual(secret_hits(good), [], good)

    def test_address_guard_both_ways(self):
        bad = "From: Someone <someone@gmail.com>\nTo: a@example.com\n"
        self.assertEqual(non_fictional_addresses(bad), ["someone@gmail.com"])
        good = "From: Alex Rivera <alex@example.com>\nTo: Jordan Lee <jordan@example.org>\n"
        self.assertEqual(non_fictional_addresses(good), [])


if __name__ == "__main__":
    unittest.main()
