import unittest
import io
from pathlib import Path
from PIL import Image, ImageDraw

import database
import app as seam_app
from config import STYLE_TAGS


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
        self.assertIn("style tags", accessory_missing)

    def test_style_tags_are_curated_and_limited_to_five_without_a_minimum(self):
        self.assertGreaterEqual(len(STYLE_TAGS), 20)
        self.assertLessEqual(len(STYLE_TAGS), 30)
        no_tags = self.client.post("/garments/new", data={"name": "Plain shirt", "category": "Tops"})
        self.assertEqual(no_tags.status_code, 302)
        self.assertEqual(database.row("SELECT style_tags FROM garments WHERE name='Plain shirt'")["style_tags"], "")

        chosen = STYLE_TAGS[:5]
        five_tags = self.client.post("/garments/new", data={"name": "Tagged shirt", "category": "Tops", "style_tags": chosen})
        self.assertEqual(five_tags.status_code, 302)
        self.assertEqual(database.row("SELECT style_tags FROM garments WHERE name='Tagged shirt'")["style_tags"], ",".join(chosen))

        too_many = self.client.post("/garments/new", data={"name": "Too many", "category": "Tops", "style_tags": STYLE_TAGS[:6]})
        self.assertEqual(too_many.status_code, 200)
        self.assertIsNone(database.row("SELECT id FROM garments WHERE name='Too many'"))

        arbitrary = self.client.post("/garments/new", data={"name": "Custom tag", "category": "Tops", "style_tags": "My made up style"})
        self.assertEqual(arbitrary.status_code, 200)
        self.assertIsNone(database.row("SELECT id FROM garments WHERE name='Custom tag'"))

    def test_quick_rename_and_bulk_delete(self):
        for name in ("Garment 1", "Garment 2", "Garment 3"):
            self.client.post("/garments/new", data={"name": name, "category": "Bottoms", "color": "#222222"})
        wardrobe_response = self.client.get("/wardrobe")
        self.assertEqual(wardrobe_response.status_code, 200)
        wardrobe_html = wardrobe_response.get_data(as_text=True)
        self.assertIn('role="tooltip"', wardrobe_html)
        self.assertIn("Style tags <em>optional</em>", wardrobe_html)
        self.assertIn("<b>Silhouette</b>", wardrobe_html)
        response = self.client.post("/garments/1/rename", data={"name": "Black jeans", "category": "Bottoms"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(database.row("SELECT name FROM garments WHERE id=1")["name"], "Black jeans")
        edit_form = self.client.get("/garments/1/edit").get_data(as_text=True)
        self.assertIn('name="color_name" value="Charcoal"', edit_form)
        self.assertNotIn('name="color_name" value="#222222"', edit_form)
        response = self.client.post("/garments/1/edit", data={"name": "Black jeans", "category": "Bottoms", "fit": "Regular", "color_name": "Charcoal"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(database.row("SELECT color FROM garments WHERE id=1")["color"], "#222222")
        self.assertEqual(seam_app.missing_analysis_details(dict(database.row("SELECT * FROM garments WHERE id=1"))), ["style tags"])
        response = self.client.post("/garments/bulk-delete", data={"garment_ids": ["1", "2"]})
        self.assertEqual(response.status_code, 302)
        remaining = database.rows("SELECT name FROM garments ORDER BY id")
        self.assertEqual([item["name"] for item in remaining], ["Garment 3"])

    def test_wardrobe_sort_can_be_alphabetical_or_latest(self):
        for name in ("Zulu coat", "Alpha tee", "Middle jeans"):
            self.client.post("/garments/new", data={"name": name, "category": "Tops"})
        alphabetic = self.client.get("/wardrobe").get_data(as_text=True)
        self.assertLess(alphabetic.index("Alpha tee"), alphabetic.index("Middle jeans"))
        self.assertLess(alphabetic.index("Middle jeans"), alphabetic.index("Zulu coat"))
        self.assertIn('value="alpha" selected', alphabetic)
        latest = self.client.get("/wardrobe?sort=latest").get_data(as_text=True)
        self.assertLess(latest.index("Middle jeans"), latest.index("Alpha tee"))
        self.assertIn('value="latest" selected', latest)

    def test_dashboard_color_notes_use_readable_names(self):
        self.client.post("/garments/new", data={"name": "Teal shirt", "category": "Tops", "color_name": "Teal"})
        self.assertEqual(database.row("SELECT color FROM garments WHERE name='Teal shirt'")["color"], "#008080")
        dashboard = self.client.get("/").get_data(as_text=True)
        self.assertIn(">Teal <b>1</b></span>", dashboard)
        self.assertIn(">Teal</span></div></article>", dashboard)
        self.assertNotIn("#008080</", dashboard)

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
        response = self.client.post("/outfits/new", data={"name": "Weekend", "garment_ids": ["1", "2", "3"],
                                                           "fit_pic": (self.sample_photo("#c83228"), "weekend.png")},
                                   content_type="multipart/form-data")
        self.assertEqual(response.status_code, 302)
        outfit = database.row("SELECT * FROM outfits WHERE id=1")
        self.assertTrue(outfit["fit_pic_path"])
        studio_html = self.client.get("/outfits").get_data(as_text=True)
        self.assertIn("Create new outfit", studio_html)
        self.assertIn(outfit["fit_pic_path"], studio_html)
        self.assertNotIn("Choose pieces", studio_html)
        self.assertIn("Choose pieces", self.client.get("/outfits/new").get_data(as_text=True))
        self.client.post("/outfits/new", data={"name": "No photo", "garment_ids": ["1"]})
        no_photo_html = self.client.get("/outfits").get_data(as_text=True)
        self.assertIn("No fit pic, boohoo.", no_photo_html)
        self.assertIn("☹", no_photo_html)
        self.assertEqual(self.client.get("/outfits/1").status_code, 200)
        self.assertIn(outfit["fit_pic_path"], self.client.get("/outfits/1").get_data(as_text=True))
        edit_html = self.client.get("/outfits/1/edit").get_data(as_text=True)
        self.assertEqual(self.client.get("/outfits/1/edit").status_code, 200)
        self.assertIn("Remove current fit pic", edit_html)
        recommendations_html = self.client.get("/recommendations").get_data(as_text=True)
        self.assertIn('class="rec-copy"', recommendations_html)
        self.assertLess(recommendations_html.index('class="rec-photo"'), recommendations_html.index('class="rec-copy"'))
        self.assertEqual(self.client.get("/style-profile").status_code, 200)
        response = self.client.post("/outfits/1/edit", data={"name": "Weekend revised", "garment_ids": ["1", "2", "3"]})
        self.assertEqual(response.status_code, 302)
        response = self.client.post("/outfits/1/replace", data={"remove_id": "1", "add_id": "4"})
        self.assertEqual(response.status_code, 302)
        response = self.client.post("/outfits/1/edit", data={"name": "Weekend revised", "garment_ids": ["1", "2", "3"],
                                                               "remove_fit_pic": "1"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(database.row("SELECT fit_pic_path FROM outfits WHERE id=1")["fit_pic_path"], "")
        self.assertEqual(self.client.get("/").status_code, 200)


if __name__ == "__main__":
    unittest.main()
