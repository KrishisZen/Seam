import unittest
from pathlib import Path

import database
import app as seam_app


class AppRouteTests(unittest.TestCase):
    def setUp(self):
        database.DATABASE_PATH = Path(__file__).resolve().parent / "test.sqlite3"
        database.DATABASE_PATH.unlink(missing_ok=True)
        database.init_db()
        seam_app.app.config["TESTING"] = True
        self.client = seam_app.app.test_client()

    def tearDown(self):
        database.DATABASE_PATH.unlink(missing_ok=True)

    def test_garment_outfit_recommendation_and_edit_pages(self):
        items = [("Everyday tee", "Tops", "#e8e4d9"),
                 ("Straight trousers", "Bottoms", "#333c36"),
                 ("Canvas shoes", "Footwear", "#b8a37a")]
        for name, category, color in items:
            response = self.client.post("/garments/new", data={"name": name, "category": category,
                                        "color": color, "style_tags": "Minimal", "fit": "Regular"})
            self.assertEqual(response.status_code, 302)
        self.client.post("/garments/new", data={"name": "Dark tee", "category": "Tops",
                                                "color": "#222222", "style_tags": "Minimal", "fit": "Regular"})
        response = self.client.post("/outfits", data={"name": "Weekend", "garment_ids": ["1", "2", "3"]})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get("/outfits/1").status_code, 200)
        self.assertEqual(self.client.get("/outfits/1/edit").status_code, 200)
        self.assertEqual(self.client.get("/outfits").status_code, 200)
        self.assertEqual(self.client.get("/recommendations").status_code, 200)
        self.assertEqual(self.client.get("/style-profile").status_code, 200)
        response = self.client.post("/outfits/1/edit", data={"name": "Weekend revised", "garment_ids": ["1", "2", "3"]})
        self.assertEqual(response.status_code, 302)
        response = self.client.post("/outfits/1/replace", data={"remove_id": "1", "add_id": "4"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get("/").status_code, 200)


if __name__ == "__main__":
    unittest.main()
