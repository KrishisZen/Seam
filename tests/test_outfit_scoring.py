import unittest
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
        self.assertEqual(score["overall"], round(.30 * score["color"] + .25 * score["style"] + .20 * score["silhouette"] + .15 * score["completeness"] + .10 * score["balance"], 1))


if __name__ == "__main__":
    unittest.main()
