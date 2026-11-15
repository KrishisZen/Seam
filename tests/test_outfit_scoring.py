import unittest
from config import OVERALL_SCORE_CURVE
from services.outfit_scoring import score_outfit


class OutfitScoringTests(unittest.TestCase):
    def test_empty_outfit_scores_zero(self):
        self.assertEqual(score_outfit([])["overall"], 0)

    def test_returns_weighted_dimensions_between_zero_and_100(self):
        garments = [
            {"id": 1, "category": "Tops", "color": "#345678", "style_tags": "Minimal, Workwear", "fit": "Relaxed"},
            {"id": 2, "category": "Bottoms", "color": "#b7a37b", "style_tags": "Minimal", "fit": "Regular"},
            {"id": 3, "category": "Footwear", "color": "#222222", "style_tags": "Workwear", "fit": "Regular"},
        ]
        score = score_outfit(garments)
        self.assertEqual(set(score), {"color", "style", "silhouette", "completeness", "balance", "overall"})
        self.assertTrue(all(0 <= value <= 100 for value in score.values()))
        weighted = (.30 * score["color"] + .25 * score["style"] + .20 * score["silhouette"]
                    + .15 * score["completeness"] + .10 * score["balance"])
        self.assertEqual(score["overall"], round(100 * (weighted / 100) ** OVERALL_SCORE_CURVE, 1))
        self.assertLessEqual(score["overall"], weighted)

    def test_shoe_style_pairing_uses_outfit_style_tags(self):
        base = [
            {"id": 1, "category": "Tops", "color": "#345678", "style_tags": "Formal", "fit": "Regular"},
            {"id": 2, "category": "Bottoms", "color": "#b7a37b", "style_tags": "Formal", "fit": "Regular"},
        ]
        chunky = {"id": 3, "category": "Footwear", "color": "#222222", "style_tags": "", "shoe_style": "Chunky", "fit": ""}
        derby = {**chunky, "shoe_style": "Derby"}
        self.assertGreater(score_outfit(base + [derby])["style"], score_outfit(base + [chunky])["style"])


if __name__ == "__main__":
    unittest.main()
