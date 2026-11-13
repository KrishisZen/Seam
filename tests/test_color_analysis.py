import io
import unittest
from PIL import Image
from services.color_analysis import analyze_image


class ColorAnalysisTests(unittest.TestCase):
    def test_extracts_palette_and_normalized_metrics(self):
        image = Image.new("RGB", (40, 20), "#cc3322")
        pixels = image.load()
        for x in range(20):
            for y in range(20):
                pixels[x, y] = (20, 40, 180)
        buffer = io.BytesIO(); image.save(buffer, format="PNG")
        result = analyze_image(buffer.getvalue())
        self.assertGreaterEqual(len(result["palette"]), 1)
        self.assertTrue(all(color.startswith("#") for color in result["palette"]))
        self.assertGreaterEqual(result["brightness"], 0)
        self.assertLessEqual(result["brightness"], 1)
        self.assertGreaterEqual(result["saturation"], 0)
        self.assertLessEqual(result["saturation"], 1)


if __name__ == "__main__":
    unittest.main()
