# SEAM

**Computational Wardrobe & Personal Style Intelligence**

SEAM is a local Flask application for cataloguing garments, inspecting approximate image colors, assembling outfits, and exploring a small, transparent outfit scoring model. It uses only the information entered by the user and items in the local SQLite database. Its scores are estimates, not objective judgments of fashion quality.

## Run locally (Windows)

1. Install Python 3.10 or newer.
2. Open PowerShell in this project directory.
3. Create and activate a virtual environment:

   ```powershell
   py -m venv .venv
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

Color analysis in `services/color_analysis.py` resizes an uploaded image, groups RGB pixels using scikit-learn K-Means, and calculates mean OpenCV HSV brightness and saturation. Background pixels affect the result, so tightly cropped garment images work best. Color names and all other descriptive attributes remain user-entered and editable.

Recommendations enumerate available top + bottom + footwear combinations, optionally including one outerwear or accessory item, score each combination, and show the top five. The style profile counts the tags manually assigned to garments.

## Project structure

```text
app.py                    Flask routes and request validation
config.py                 Local paths and upload limits
database.py               SQLite schema and connection helpers
services/                 Color analysis, outfit scoring, recommendations, profile
templates/                Responsive server-rendered pages
static/css/style.css      Visual system
static/js/app.js          Small upload and color-preview interactions
tests/                    Unit tests for scoring and color analysis
```

## Tests

Run the requested algorithm unit tests with:

```powershell
python -m unittest discover -s tests -v
```
