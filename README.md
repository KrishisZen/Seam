# SEAM

**Computational Wardrobe & Personal Style Intelligence**

SEAM is a local Flask application for cataloguing garments, inspecting approximate image colors, assembling outfits, and exploring a small, transparent outfit scoring model. It uses only the information entered by the user and items in the local SQLite database. Its scores are estimates, not objective judgments of fashion quality.

## Run locally (Windows)

1. Install Python 3.10 or newer.
2. Open PowerShell in this project directory.
3. Create and activate a virtual environment:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

4. Install dependencies and run SEAM:

   ```powershell
   python -m pip install -r requirements.txt
   python app.py
   ```

5. Open http://127.0.0.1:5000.

The SQLite database (`seam.sqlite3`) and uploaded images (`static/uploads/`) are created locally the first time the app runs. Back up those two locations to preserve your data. The Flask development server is intended for local project use.

## What the model calculates

The scoring code is in `services/outfit_scoring.py`. It combines five 0–100 dimensions using the weights in `config.py`: color (30%), style-tag overlap (25%), fit consistency (20%), category completeness (15%), and category balance (10%). Change those values to tune the model; they are normalized when applied. The output is a deterministic heuristic to demonstrate computational reasoning; it is not a learned fashion model. Unknown colors or style tags receive neutral assumptions. A suggestion is shown only when replacing a garment with another item of the same category increases the recalculated total.

Color analysis in `services/color_analysis.py` first uses OpenCV GrabCut to separate the likely foreground from background border pixels, then runs K-Means only on the extracted garment pixels. On a single item with a distinct background, this avoids letting most of the backdrop dominate the palette. For off-center items or busy scenes, the single-garment form lets the user draw a box around the item and rerun the cutout. The edit page shows both the original and transparent cutout so the result can be checked. Segmentation is still an estimate; low contrast, multiple overlapping items, a model wearing the garment, and patterned scenes can confuse it.

The analysis also reports masked brightness and saturation, the garment's approximate foreground area and width-to-height ratio, a coarse outline hint based on width changes from top to hem, plus a simple visible-edge estimate called surface detail. These measurements can be influenced by folds, lighting, and image quality. SEAM does not identify material or reliably recognize garment type from pixels; those details remain optional and user-entered.

For quick setup, **Add multiple photos** lets the user choose up to 25 files or a folder and assign one category to the batch. Each photo is saved with a generated name (Garment 1, Garment 2, and so on); the other form fields can be left until later. Items that cannot be segmented automatically are still added with the original image, ready for a closer box selection on their edit page. Each image can be up to 8 MB, with an 80 MB total request limit. Garments can also be selected for batch deletion or renamed directly from the wardrobe grid.

Recommendations enumerate available top + bottom + footwear combinations, optionally including one outerwear or accessory item, score each combination, and show the top five. The style profile counts the tags manually assigned to garments.

## Project structure

```text
app.py                    Flask routes and request validation
config.py                 Local paths and upload limits
database.py               SQLite schema and connection helpers
services/                 Color analysis, outfit scoring, recommendations, profile
templates/                Responsive server-rendered pages
static/css/style.css      Visual system
static/js/app.js          Batch upload, garment selection, and color-preview interactions
tests/                    Route, scoring, and foreground color-analysis tests
```

## Tests

Run the requested algorithm unit tests with:

```powershell
python -m unittest discover -s tests -v
```
