import pathlib
import unittest

README = pathlib.Path(__file__).resolve().parents[3] / "README.md"


class TestReadmeClaims(unittest.TestCase):
    """The README must not state epic 66's undecided engine or pricing as fact."""

    @classmethod
    def setUpClass(cls):
        cls.text = README.read_text(encoding="utf-8")

    def test_no_fixed_credit_cost(self):
        self.assertNotIn("1 credit per request", self.text)
        self.assertNotIn("2 credits for a full 200-sample mailbox", self.text)

    def test_no_fixed_engine_claim(self):
        self.assertNotIn("no outside engine or company sees your email", self.text)
        self.assertNotIn("rules inside the API itself", self.text)

    def test_no_free_credits_cover_build_claim(self):
        self.assertNotIn("cover a typical build", self.text)
        self.assertNotIn("enough to build a voice profile", self.text)

    def test_points_to_api_docs(self):
        self.assertIn("https://api.yourvoice.dev/", self.text)


class TestReadmeLocalReview(unittest.TestCase):
    """Epic 2.1: the KEEP/DROP review runs locally; only kept samples go to the API."""

    @classmethod
    def setUpClass(cls):
        cls.text = README.read_text(encoding="utf-8")
        start = cls.text.index("**What leaves your machine.**")
        cls.paragraph = cls.text[start:cls.text.index("\n", start)]

    def test_no_api_review_wording(self):
        self.assertNotIn("for the KEEP/DROP review", self.text)
        self.assertNotIn("through the API", self.text)
        self.assertNotIn("The review runs in the text analysis API", self.text)
        self.assertNotIn("If the API review fails", self.text)
        self.assertNotIn("marks the ones that really sound like you", self.text)

    def test_what_leaves_paragraph(self):
        p = self.paragraph
        self.assertIn("The KEEP/DROP review runs on your machine and sends nothing anywhere.", p)
        self.assertIn("only the kept samples (up to the 148 extracted, sent in batches of 100;", p)
        self.assertIn("the fingerprint step uses at most 100 of them)", p)
        self.assertIn("only if you opt in, the reference set", p)
        self.assertIn("off by default", p)
        self.assertNotIn("on by default", p)
        self.assertNotIn("up to the 200", p)
        self.assertIn("Rewriting text with `/revoice` never touches the API.", p)

    def test_how_it_works_review_is_local(self):
        self.assertIn("reviews them on your machine", self.text)


class TestReadmePluginInstall(unittest.TestCase):
    """Epic 3: the plugin is the main install; copy-folder is the second option."""

    @classmethod
    def setUpClass(cls):
        cls.text = README.read_text(encoding="utf-8")
        start = cls.text.index("## 1. Install the skill")
        cls.install = cls.text[start:cls.text.index("## 2. ", start)]

    def test_plugin_commands_are_the_main_install(self):
        self.assertIn("/plugin marketplace add samestrin/revoice-skill", self.install)
        self.assertIn("/plugin install revoice@revoice-skill", self.install)
        plugin_pos = self.install.index("/plugin marketplace add")
        copy_pos = self.install.index("copy the skill folder")
        self.assertLess(plugin_pos, copy_pos)

    def test_copy_folder_is_the_second_option(self):
        self.assertIn("Alternative: copy the folder", self.install)
        self.assertIn("~/.claude/skills", self.install)

    def test_command_is_bare_revoice(self):
        self.assertIn("The command is `/revoice`.", self.install)

    def test_voices_location_documented(self):
        self.assertIn("~/.config/revoice/voices/", self.text)
        self.assertNotIn("your voice files in `assets/`", self.text)

    def test_switching_note(self):
        self.assertIn("Switching from the copy-folder install to the plugin", self.install)
        start = self.install.index("Switching from the copy-folder install")
        note = self.install[start:self.install.index("\n", start)]
        self.assertIn("~/.config/revoice/voices/", note)
        self.assertIn("delete `~/.claude/skills/revoice/`", note)
        self.assertIn("takes the bare `/revoice` command", note)

    def test_update_and_uninstall_through_plugin(self):
        self.assertIn("/plugin update revoice@revoice-skill", self.text)
        self.assertIn("/plugin uninstall revoice@revoice-skill", self.text)


class TestReadmeVersion(unittest.TestCase):
    """Epic 16: Upgrading says how to see the installed version and where releases are."""

    @classmethod
    def setUpClass(cls):
        text = README.read_text(encoding="utf-8")
        start = text.index("\n## Upgrading\n")
        cls.upgrading = text[start:text.index("\n## ", start + 1)]

    def test_how_to_see_installed_version(self):
        self.assertIn("To see which version you have", self.upgrading)
        self.assertIn("`/plugin`", self.upgrading)

    def test_releases_link(self):
        self.assertIn("tagged releases", self.upgrading)
        self.assertIn("(https://github.com/samestrin/revoice-skill/releases)", self.upgrading)


class TestReadmeCost(unittest.TestCase):
    """Epic 14: the README says what a build costs and how to save the key on Linux."""

    @classmethod
    def setUpClass(cls):
        cls.text = README.read_text(encoding="utf-8")

    def test_per_text_cost_and_formula(self):
        self.assertIn("1 credit per text", self.text)
        self.assertIn("cost = 1 + kept samples + reference emails + min(kept samples, 100)", self.text)

    def test_examples(self):
        self.assertIn("1 + 30 + 0 + 30 = 61 credits", self.text)
        self.assertIn("1 + 149 + 200 + 100 = 450 credits", self.text)

    def test_default_fits_free_grant(self):
        self.assertIn("at most 148 samples, no reference set", self.text)
        self.assertIn("1 + 148 + 100 = 249 credits, plus 1 for the key check: 250, exactly the free grant", self.text)

    def test_linux_key_command(self):
        self.assertIn("Linux:", self.text)
        self.assertIn("chmod 600 ~/.config/revoice/api-key", self.text)
        self.assertIn("xclip", self.text)

    def test_install_heading_unchanged(self):
        self.assertIn("\n## 1. Install the skill\n", self.text)


class TestReadmeTroubleshooting(unittest.TestCase):
    """Epic 14: the README says what to do when the build stops."""

    @classmethod
    def setUpClass(cls):
        text = README.read_text(encoding="utf-8")
        start = text.index("### If the build stops")
        cls.section = text[start:text.index("\n## ", start)]
        cls.items = [line for line in cls.section.splitlines() if line.startswith("- **")]

    def item(self, name):
        found = [line for line in self.items if line.startswith(f"- **{name}**")]
        self.assertEqual(len(found), 1, f"no single '{name}' item")
        return found[0]

    def test_checks_key_and_balance_before_spending(self):
        self.assertIn("checks your key and your balance before it spends credits", self.section)

    def test_four_cases(self):
        self.assertEqual(len(self.items), 4)

    def test_wrong_key(self):
        line = self.item("Wrong key")
        self.assertIn("HTTP 401", line)
        self.assertIn("~/.config/revoice/api-key", line)

    def test_out_of_credits(self):
        line = self.item("Out of credits")
        self.assertIn('"out of credits", HTTP 402 from the API;', line)
        # "short by N credits" comes from the free cost check, not from a 402.
        self.assertNotIn('"short by N credits", HTTP 402', line)
        self.assertIn('before your samples are sent, "short by N credits" from the cost check', line)
        self.assertIn('"this build costs N credits and you have M credits left"', line)
        self.assertIn("buy a credit pack at https://yourvoice.dev/", line)
        self.assertIn("fewer samples or without the reference set", line)

    def test_too_many_requests(self):
        line = self.item("Too many requests")
        self.assertIn("HTTP 429", line)
        self.assertIn("wait the number of seconds it says", line)

    def test_cannot_reach_the_api(self):
        line = self.item("Cannot reach the API")
        self.assertIn("check your internet connection", line)


if __name__ == "__main__":
    unittest.main()
