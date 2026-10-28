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
        self.assertIn("https://text-analysis-api.estr.in/", self.text)


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
        self.assertIn("only the kept samples (up to the 200 extracted, sent in batches of 100)", p)
        self.assertIn("plus the reference set", p)
        self.assertIn("Rewriting text with `/revoice` never touches the API.", p)

    def test_how_it_works_review_is_local(self):
        self.assertIn("reviews them on your machine", self.text)


if __name__ == "__main__":
    unittest.main()


if __name__ == "__main__":
    unittest.main()
