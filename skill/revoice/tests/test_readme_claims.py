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

    def test_points_to_api_docs(self):
        self.assertIn("https://text-analysis-api.estr.in/", self.text)


if __name__ == "__main__":
    unittest.main()
