import io
import unittest
from PIL import Image, ImageDraw
from services.color_analysis import analyze_image


def product_photo(position=(45, 20, 115, 180)):
    image = Image.new("RGB", (200, 200), "#e9e5dc")
    draw = ImageDraw.Draw(image)
    draw.rectangle(position, fill="#c83228")
    # A contrasting background patch checks that border clutter does not win.
    draw.rectangle((0, 0, 18, 18), fill="#2448bd")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


class ColorAnalysisTests(unittest.TestCase):
    def test_palette_comes_from_foreground_not_background(self):
        result = analyze_image(product_photo())
        red = result["palette"][0]
        rgb = tuple(int(red[index:index + 2], 16) for index in (1, 3, 5))
        self.assertGreater(rgb[0], 150)
        self.assertGreater(rgb[0], rgb[2] * 2)
        self.assertGreaterEqual(result["brightness"], 0)
        self.assertLessEqual(result["brightness"], 1)
        self.assertGreaterEqual(result["saturation"], 0)
        self.assertLessEqual(result["saturation"], 1)
        self.assertTrue(result["foreground_png"].startswith(b"\x89PNG"))
        self.assertIn("surface_detail", result)
        self.assertIn(result["silhouette_hint"], {"Broader at top", "Wider toward hem", "Mostly straight outline", "Uneven or tapered outline"})
        self.assertGreater(result["foreground_ratio"], .2)
        self.assertLess(result["foreground_ratio"], .8)

    def test_user_box_can_locate_off_center_item(self):
        result = analyze_image(product_photo((10, 35, 82, 190)), garment_box=(.02, .12, .42, .83))
        self.assertGreater(result["foreground_ratio"], .15)
        self.assertTrue(result["palette"][0].startswith("#"))


if __name__ == "__main__":
    unittest.main()
