import unittest
from versioning import in_force, guess_meta_from_name
from desk_extra import _is_public, _slug, DESK_BUILD

class AsOf(unittest.TestCase):
    def test_in_force_window(self):
        self.assertTrue(in_force("2024-01-01", "2025-01-01", "2024-06-01"))
        self.assertFalse(in_force("2025-01-01", "", "2024-06-01"))
        self.assertTrue(in_force("", "", "2024-06-01"))

    def test_filename_date(self):
        meta = guess_meta_from_name("LifestyleProtector_2024-06.pdf")
        self.assertEqual(meta["effective_from"], "2024-06-01")

    def test_localhost_not_public(self):
        self.assertFalse(_is_public("http://127.0.0.1:8000/m/joe"))
        self.assertTrue(_is_public("https://fortitudostudios.site/m/joe"))

    def test_slug_flyer(self):
        self.assertEqual(_slug("Joe Plumbing"), "joe-plumbing")

    def test_build_stamp(self):
        self.assertTrue(DESK_BUILD.startswith("wire"))

if __name__ == "__main__":
    unittest.main()
