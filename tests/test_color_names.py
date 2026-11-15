import unittest
from services.color_names import color_name, color_rgb


class ColorNameTests(unittest.TestCase):
    def test_named_and_hex_colors_are_readable(self):
        self.assertEqual(color_name("#008080"), "Teal")
        self.assertEqual(color_name("#303030"), "Graphite Gray")
        self.assertNotEqual(color_name("#303030"), color_name("#b0b0b0"))
        self.assertEqual(color_name("forest green"), "Forest Green")
        self.assertEqual(color_name(""), "Color not specified")

    def test_descriptive_shade_names_can_be_used_for_scoring(self):
        self.assertEqual(len(color_rgb("Muted Aquamarine")), 3)


if __name__ == "__main__":
    unittest.main()
