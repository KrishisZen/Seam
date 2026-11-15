import unittest
from services.color_names import color_name


class ColorNameTests(unittest.TestCase):
    def test_named_and_hex_colors_are_readable(self):
        self.assertEqual(color_name("#008080"), "Teal")
        self.assertEqual(color_name("#303030"), "Charcoal")
        self.assertEqual(color_name("forest green"), "Forest Green")
        self.assertEqual(color_name(""), "Color not specified")


if __name__ == "__main__":
    unittest.main()
