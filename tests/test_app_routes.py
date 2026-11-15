import unittest
import io
from pathlib import Path
from PIL import Image, ImageDraw

import database
import app as seam_app


class AppRouteTests(unittest.TestCase):
    def setUp(self):
        database.DATABASE_PATH = Path(__file__).resolve().parent / "test.sqlite3"
        database.DATABASE_PATH.unlink(missing_ok=True)
        self.upload_dir = Path(seam_app.UPLOAD_FOLDER)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.existing_uploads = set(self.upload_dir.iterdir())
        database.init_db()
        seam_app.app.config["TESTING"] = True
        self.client = seam_app.app.test_client()

    def tearDown(self):
        database.DATABASE_PATH.unlink(missing_ok=True)
        for upload in set(self.upload_dir.iterdir()) - self.existing_uploads:
            upload.unlink(missing_ok=True)

    @staticmethod
    def sample_photo(color):
        image = Image.new("RGB", (100, 120), "#e8e4dd")
        ImageDraw.Draw(image).rectangle((25, 8, 75, 112), fill=color)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer

    @staticmethod
    def ambiguous_photo():
        image = Image.new("RGB", (90, 110), "#888888")
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer

    def test_bulk_upload_assigns_names_and_analyzes_images(self):
        data = {
            "category": "Tops",
            "images": [(self.sample_photo("#c83228"), "red.png"), (self.ambiguous_photo(), "low-contrast.png")],
            "folder_images": [(self.sample_photo("#2763a8"), "folder/blue.png")],
        }
        response = self.client.post("/garments/bulk", data=data, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 302)
        garments = database.rows("SELECT * FROM garments ORDER BY id")
        self.assertEqual([g["name"] for g in garments], ["Garment 1", "Garment 2", "Garment 3"])
        self.assertTrue(all(g["category"] == "Tops" for g in garments))
        self.assertTrue(garments[0]["cutout_path"] and garments[2]["cutout_path"])
        self.assertTrue(garments[0]["palette"] and garments[2]["palette"])
        self.assertFalse(garments[1]["cutout_path"])
        self.assertFalse(garments[1]["palette"])
        wardrobe_html = self.client.get("/wardrobe").get_data(as_text=True)
        overview_html = self.client.get("/").get_data(as_text=True)
        self.assertIn("/static/" + garments[0]["image_path"], wardrobe_html)
        self.assertNotIn("/static/" + garments[0]["cutout_path"], wardrobe_html)
        self.assertIn("/static/" + garments[0]["image_path"], overview_html)
        self.assertNotIn("/static/" + garments[0]["cutout_path"], overview_html)
        analysis_html = self.client.get("/garments/1/edit").get_data(as_text=True)
        self.assertIn("/static/" + garments[0]["cutout_path"], analysis_html)

    def test_single_upload_accepts_user_drawn_selection_box(self):
        response = self.client.post("/garments/new", data={
            "name": "Boxed item", "category": "Tops", "color": "",
            "garment_box": "0.18,0.05,0.64,0.9",
            "image": (self.sample_photo("#c83228"), "item.png"),
        }, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 302)
        garment = database.row("SELECT * FROM garments WHERE name='Boxed item'")
        self.assertTrue(garment["cutout_path"])
        self.assertTrue(garment["palette"])

    def test_category_specific_options_save_only_for_relevant_types(self):
        footwear = self.client.post("/garments/new", data={"name": "Chunky shoes", "category": "Footwear", "shoe_style": "Chunky", "fit": "Oversized"})
        self.assertEqual(footwear.status_code, 302)
        shoe = database.row("SELECT * FROM garments WHERE name='Chunky shoes'")
        self.assertEqual(shoe["shoe_style"], "Chunky")
        self.assertEqual(shoe["fit"], "")
        incomplete_shoe = dict(shoe)
        incomplete_shoe["shoe_style"] = ""
        self.assertIn("shoe style", seam_app.missing_analysis_details(incomplete_shoe))

        accessory = self.client.post("/garments/new", data={"name": "Canvas bag", "category": "Accessories", "fit": "Slim"})
        self.assertEqual(accessory.status_code, 302)
        bag = database.row("SELECT * FROM garments WHERE name='Canvas bag'")
        self.assertEqual(bag["accessory_type"], "")
        self.assertEqual(bag["fit"], "")
        accessory_missing = seam_app.missing_analysis_details(dict(bag))
        self.assertNotIn("fit / silhouette", accessory_missing)
        self.assertNotIn("accessory type", accessory_missing)

    def test_quick_rename_and_bulk_delete(self):
        for name in ("Garment 1", "Garment 2", "Garment 3"):
            self.client.post("/garments/new", data={"name": name, "category": "Bottoms", "color": "#222222"})
        wardrobe_response = self.client.get("/wardrobe")
        self.assertEqual(wardrobe_response.status_code, 200)
        wardrobe_html = wardrobe_response.get_data(as_text=True)
        self.assertIn('role="tooltip"', wardrobe_html)
        self.assertIn("Style tags <em>optional</em>", wardrobe_html)
        self.assertLess(wardrobe_html.index("<b>Silhouette</b>"), wardrobe_html.index("<b>Style tags"))
        response = self.client.post("/garments/1/rename", data={"name": "Black jeans", "category": "Bottoms"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(database.row("SELECT name FROM garments WHERE id=1")["name"], "Black jeans")
        response = self.client.post("/garments/1/edit", data={"name": "Black jeans", "category": "Bottoms", "fit": "Regular", "color": "#222222"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(seam_app.missing_analysis_details(dict(database.row("SELECT * FROM garments WHERE id=1"))), ["style tags"])
        response = self.client.post("/garments/bulk-delete", data={"garment_ids": ["1", "2"]})
        self.assertEqual(response.status_code, 302)
        remaining = database.rows("SELECT name FROM garments ORDER BY id")
        self.assertEqual([item["name"] for item in remaining], ["Garment 3"])

    def test_garment_outfit_recommendation_and_edit_pages(self):
        self.assertEqual(self.client.get("/garments/bulk").status_code, 200)
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
