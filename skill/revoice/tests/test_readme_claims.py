import pathlib
import re
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

    def test_you_approve_the_samples_before_the_upload(self):
        start = self.text.index("## 3. Build your voice profile")
        build = self.text[start:self.text.index("**What leaves your machine.**", start)]
        self.assertIn("You review and approve the samples before the upload", build)
        self.assertIn("You review and approve the samples before the upload", self.paragraph)


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


class TestReadmeExampleOutput(unittest.TestCase):
    """Epic 16: the README shows the example voice's before-and-after before the API key step."""

    @classmethod
    def setUpClass(cls):
        cls.text = README.read_text(encoding="utf-8")
        start = cls.text.index("\n### What it looks like\n")
        cls.start = start
        cls.section = cls.text[start:cls.text.index("\n#", start + 1)]
        example = (README.parent / "skill" / "revoice" / "assets" / "example.md").read_text(encoding="utf-8")
        pair = example[example.index("\n## Before and after\n"):]
        quotes = re.findall(r"(?m)((?:^>.*\n?)+)", pair)
        cls.draft, cls.rewrite = (q.rstrip("\n") for q in quotes[:2])
        do_not = example[example.index("\n## Do not\n"):example.index("\n## ", example.index("\n## Do not\n") + 1)]
        cls.banned = re.findall(r'"([^"]+)"', do_not)

    def test_before_save_api_key(self):
        self.assertLess(self.start, self.text.index("\n## 2. Save your API key\n"))

    def test_names_voice_example(self):
        self.assertIn("--voice=example", self.section)

    def test_says_fictional(self):
        self.assertIn("fictional", self.section)

    def test_shows_draft_and_rewrite_verbatim(self):
        self.assertIn(self.draft, self.section)
        self.assertIn(self.rewrite, self.section)
        self.assertLess(self.section.index(self.draft), self.section.index(self.rewrite))

    def test_rewrite_has_no_banned_phrase(self):
        self.assertIn("I hope this email finds you well", self.banned)
        self.assertIn("Kindly", self.banned)
        for phrase in self.banned:
            self.assertNotIn(phrase.lower(), self.rewrite.lower())
        self.assertNotIn("—", self.rewrite)


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


class TestReadmeThreeSources(unittest.TestCase):
    """Epic 17: the README names the three sources and their honest counts."""

    @classmethod
    def setUpClass(cls):
        cls.text = README.read_text(encoding="utf-8")
        start = cls.text.index("## 3. Build your voice profile")
        cls.build = cls.text[start:cls.text.index("\n## ", start + 1)]

    def subsection(self, heading):
        start = self.build.index(heading)
        end = self.build.find("\n### ", start + 1)
        return self.build[start:end if end != -1 else len(self.build)]

    def test_intro_names_three_sources(self):
        intro = self.text[:self.text.index("## How it works")]
        self.assertIn("your email, your writing, or your brand's documents", intro)

    def test_how_it_works_names_three_sources(self):
        start = self.text.index("## How it works")
        section = self.text[start:self.text.index("\n## ", start + 1)]
        self.assertIn("an email export (MBOX), a folder of your own writing, or a folder of brand documents", section)

    def test_three_subsections_in_order(self):
        headings = ["### From an email export", "### From a folder of your writing",
                    "### From a folder of brand documents"]
        positions = [self.build.index(h) for h in headings]
        self.assertEqual(positions, sorted(positions))

    def test_first_question_is_the_source(self):
        intro = self.build[:self.build.index("### From an email export")]
        self.assertIn("The first question is where your writing is: an email export, a folder of your own writing, or a folder of brand documents.", intro)

    def test_email_subsection_keeps_takeout_and_upfront_answers(self):
        sub = self.subsection("### From an email export")
        self.assertIn("Google Takeout", sub)
        self.assertIn(".mbox", sub)
        self.assertIn("mbox=", sub)
        self.assertIn("from=", sub)

    def test_file_types(self):
        for sub in (self.subsection("### From a folder of your writing"),
                    self.subsection("### From a folder of brand documents")):
            for ext in (".md", ".txt", ".html", ".docx", ".pdf"):
                self.assertIn(ext, sub)

    def test_pdftotext_note(self):
        sub = self.subsection("### From a folder of your writing")
        self.assertIn("pdftotext", sub)
        self.assertIn("poppler", sub)
        self.assertIn("save it as `.docx` or `.txt`", sub)

    def test_urls_list(self):
        sub = self.subsection("### From a folder of your writing")
        self.assertIn("--urls", sub)
        self.assertIn("a text file with one `http` or `https` URL per line, for pages you own", sub)

    def test_passages_and_cap(self):
        sub = self.subsection("### From a folder of your writing")
        self.assertIn("passages of about 350 words (150 to 500)", sub)
        self.assertIn("At most 148 passages are kept, taken in turn from each document.", sub)

    def test_writing_confirmations(self):
        sub = self.subsection("### From a folder of your writing")
        self.assertIn("your own writing, not AI-assisted", sub)
        self.assertIn("you may send it to the text analysis API and to Claude", sub)

    def test_counts_table(self):
        self.assertIn("| Email | 1 KEEP sample | 15 KEEP samples | 20+ samples |", self.build)
        self.assertIn("| Writing | 10 KEEP passages | 20 KEEP passages from at least 5 documents | 40+ passages from 10+ documents (about 15,000 words) |", self.build)
        self.assertIn("| Brand | 10 KEEP passages from at least 3 documents | 20 KEEP passages from at least 5 documents | 40+ passages from 12+ documents by at least 3 authors if known |", self.build)

    def test_below_floor_and_minimum(self):
        self.assertIn("Below the hard floor the build stops before anything is uploaded and tells you how many more documents or words you need.", self.build)
        self.assertIn("Between the floor and the minimum it says the profile will be weaker and asks whether to continue.", self.build)

    def test_brand_subsection_confidentiality(self):
        sub = self.subsection("### From a folder of brand documents")
        self.assertIn("Brand documents are often confidential.", sub)
        self.assertIn("confirm", sub)
        self.assertIn("several authors, one brand voice", sub)


class TestReadmeDocumentCost(unittest.TestCase):
    """Epic 17: the cost section gives the passages formula and the 20-document example."""

    @classmethod
    def setUpClass(cls):
        cls.text = README.read_text(encoding="utf-8")
        start = cls.text.index("### What a build costs")
        cls.section = cls.text[start:cls.text.index("\n## ", start + 1)]

    def test_passages_formula(self):
        self.assertIn("cost = 1 + kept passages + min(kept passages, 100)", self.section)

    def test_twenty_document_example(self):
        self.assertIn("20 documents of about 1,500 words give about 85 passages: 1 + 85 + 85 = 171 credits", self.section)

    def test_no_reference_set_for_documents(self):
        self.assertIn("no reference set", self.section)


class TestReadmePrivacyPerMode(unittest.TestCase):
    """Epic 17: What leaves your machine is stated per mode, with the brand warning."""

    @classmethod
    def setUpClass(cls):
        cls.text = README.read_text(encoding="utf-8")

    def paragraph(self, marker):
        start = self.text.index(marker)
        return self.text[start:self.text.index("\n", start)]

    def test_email_paragraph_is_first_and_labels_the_mode(self):
        p = self.paragraph("**What leaves your machine.**")
        self.assertIn("Email: the full mailbox never does.", p)

    def test_writing_paragraph(self):
        p = self.paragraph("**Writing samples:**")
        self.assertIn("the folder never leaves the machine as a whole", p)
        self.assertIn("only the kept passages (up to 148, sent in batches of 100; the fingerprint step uses at most 100 of them) go to the text analysis API over HTTPS", p)
        self.assertIn("the 15 passages the profile is built from are read by Claude", p)
        self.assertIn("your machine fetches the pages", p)
        self.assertIn("only after you approve them", p)

    def test_brand_confidentiality_paragraph(self):
        p = self.paragraph("**Brand documents are often confidential.**")
        self.assertIn("take anything you may not send to a third-party API or to Claude out of the folder", p)
        self.assertIn("the build asks you to confirm you may send these documents", p)
        self.assertIn("only the kept passages", p)


class TestReadmeDocumentHelpers(unittest.TestCase):
    """Epic 17: the by-hand helper list covers the document path."""

    @classmethod
    def setUpClass(cls):
        text = README.read_text(encoding="utf-8")
        start = text.index("## Running the steps by hand")
        cls.section = text[start:text.index("\n## ", start + 1)]

    def test_document_helper_order(self):
        self.assertIn("extract-documents.py", self.section)
        self.assertIn("review-samples.py --mode writing|brand", self.section)
        self.assertIn("build-profile.py --source-type writing|brand", self.section)

    def test_email_helper_order_kept(self):
        self.assertIn("mbox-filter-before.py", self.section)
        self.assertIn("extract-samples.py", self.section)


if __name__ == "__main__":
    unittest.main()
