"""SEAM: Computational Wardrobe & Personal Style Intelligence."""
from pathlib import Path
from io import BytesIO
import json
import uuid
from flask import Flask, abort, flash, redirect, render_template, request, url_for
from PIL import Image
from werkzeug.utils import secure_filename
from config import ALLOWED_EXTENSIONS, MAX_CONTENT_LENGTH, SECRET_KEY, STYLE_TAGS, STYLE_TAG_GROUPS, UPLOAD_FOLDER
from database import get_db, init_db, row, rows
from services.color_analysis import analyze_image
from services.outfit_recommendation import recommend
from services.outfit_scoring import improvement_suggestions, score_outfit
from services.style_profile import parse_style_tags, summarize

app = Flask(__name__)
app.config.update(SECRET_KEY=SECRET_KEY, MAX_CONTENT_LENGTH=MAX_CONTENT_LENGTH)
Path(UPLOAD_FOLDER).mkdir(parents=True, exist_ok=True)
init_db()
CATEGORIES = ["Tops", "Bottoms", "Outerwear", "Footwear", "Accessories"]
APPAREL_CATEGORIES = {"Tops", "Bottoms", "Outerwear"}
FIT_OPTIONS = ["Slim", "Regular", "Relaxed", "Oversized", "Structured", "Loose"]
SHOE_STYLES = ["Chunky", "Derby", "Sneakers", "Loafers", "Boots", "Sandals", "Flats", "Heels", "Oxfords", "Other"]
ACCESSORY_TYPES = ["Bag", "Belt", "Jewelry", "Hat", "Scarf", "Sunglasses", "Other"]


def missing_analysis_details(garment):
    """Return only category-relevant details that can improve outfit analysis."""
    missing = []
    if garment.get("category") in APPAREL_CATEGORIES:
        if not garment.get("fit"):
            missing.append("silhouette")
    elif garment.get("category") == "Footwear" and not garment.get("shoe_style"):
        missing.append("shoe style")
    if not garment.get("color"):
        missing.append("color information")
    return missing


def get_garment(garment_id):
    garment = row("SELECT * FROM garments WHERE id = ?", (garment_id,))
    if garment is None:
        abort(404)
    return dict(garment)


def get_outfit(outfit_id):
    outfit = row("SELECT * FROM outfits WHERE id = ?", (outfit_id,))
    if outfit is None:
        abort(404)
    outfit = dict(outfit)
    outfit["garments"] = [dict(g) for g in rows("""SELECT g.* FROM garments g
        JOIN outfit_garments og ON og.garment_id = g.id WHERE og.outfit_id = ? ORDER BY g.category, g.name""", (outfit_id,))]
    return outfit


def _parse_garment_box(value):
    if not value:
        return None
    try:
        box = tuple(float(part) for part in value.split(","))
    except ValueError as exc:
        raise ValueError("The garment selection is invalid. Draw the box again.") from exc
    if len(box) != 4 or any(part < 0 or part > 1 for part in box) or box[2] <= .02 or box[3] <= .02 or box[0] + box[2] > 1 or box[1] + box[3] > 1:
        raise ValueError("Draw a selection box around the garment, then try again.")
    return box


def save_image(file, garment_box="", keep_unanalyzed=False):
    if not file or not file.filename:
        return "", None, "", ""
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError("Use a PNG, JPG, JPEG, or WEBP image.")
    data = file.read()
    if not data:
        raise ValueError("The selected image is empty.")
    if len(data) > 8 * 1024 * 1024:
        raise ValueError("Each image must be 8 MB or smaller.")
    issue = ""
    try:
        analysis = analyze_image(data, garment_box=_parse_garment_box(garment_box))
    except ValueError as exc:
        if not keep_unanalyzed or not str(exc).startswith("SEAM could not isolate"):
            raise
        analysis = None
        issue = str(exc)
    filename = secure_filename(f"{uuid.uuid4().hex}.{ext}")
    (Path(UPLOAD_FOLDER) / filename).write_bytes(data)
    cutout_path = ""
    if analysis:
        cutout_name = f"{Path(filename).stem}-cutout.png"
        (Path(UPLOAD_FOLDER) / cutout_name).write_bytes(analysis.pop("foreground_png"))
        cutout_path = f"uploads/{cutout_name}"
    return f"uploads/{filename}", analysis, cutout_path, issue


def save_fit_pic(file):
    """Save an optional outfit photo without treating it as a garment analysis image."""
    if not file or not file.filename:
        return ""
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError("Use a PNG, JPG, JPEG, or WEBP fit pic.")
    data = file.read()
    if not data:
        raise ValueError("The selected fit pic is empty.")
    if len(data) > 8 * 1024 * 1024:
        raise ValueError("The fit pic must be 8 MB or smaller.")
    try:
        with Image.open(BytesIO(data)) as image:
            image.verify()
    except (OSError, ValueError) as exc:
        raise ValueError("SEAM couldn't read that fit pic. Try a PNG, JPG, JPEG, or WEBP image.") from exc
    filename = secure_filename(f"{uuid.uuid4().hex}.{ext}")
    (Path(UPLOAD_FOLDER) / filename).write_bytes(data)
    return f"uploads/{filename}"


def insert_garment(name, category, image_path, analysis=None, cutout_path=""):
    analysis = analysis or {}
    with get_db() as db:
        db.execute("""INSERT INTO garments(name,category,color,image_path,palette,brightness,saturation,cutout_path,analysis_json)
            VALUES(?,?,?,?,?,?,?,?,?)""", (name, category, analysis.get("palette", [""])[0] if analysis else "", image_path,
            json.dumps(analysis["palette"]) if analysis else "", analysis.get("brightness"), analysis.get("saturation"), cutout_path,
            json.dumps(analysis)))


@app.errorhandler(413)
def too_large(_error):
    flash("Choose smaller images. Each photo can be up to 8 MB, and a batch can contain up to 25 photos.", "error")
    if request.path.startswith("/outfits/") and request.path != "/outfits/new":
        return redirect(url_for("outfit_edit", outfit_id=request.view_args["outfit_id"]))
    endpoint = "outfit_new" if request.path == "/outfits/new" else ("garment_bulk" if request.path.endswith("/bulk") else "garment_new")
    return redirect(url_for(endpoint))


@app.route("/")
def dashboard():
    garments = [dict(g) for g in rows("SELECT * FROM garments ORDER BY created_at DESC LIMIT 6")]
    for garment in garments:
        try:
            garment["analysis"] = json.loads(garment.get("analysis_json") or "{}")
        except (TypeError, json.JSONDecodeError):
            garment["analysis"] = {}
        garment["missing_details"] = missing_analysis_details(garment)
    category_counts = rows("SELECT category, COUNT(*) AS count FROM garments GROUP BY category ORDER BY count DESC")
    outfits = row("SELECT COUNT(*) AS count FROM outfits")["count"]
    style = summarize([dict(g) for g in rows("SELECT style_tags FROM garments")])
    color_counts = rows("SELECT color, COUNT(*) AS count FROM garments WHERE color != '' GROUP BY color ORDER BY count DESC LIMIT 6")
    return render_template("dashboard.html", garments=garments, garment_count=row("SELECT COUNT(*) AS count FROM garments")["count"],
                           outfit_count=outfits, category_counts=category_counts, style=style[:4], color_counts=color_counts)


@app.route("/wardrobe")
def wardrobe():
    category = request.args.get("category", "")
    query = "SELECT * FROM garments"
    params = ()
    if category in CATEGORIES:
        query += " WHERE category = ?"; params = (category,)
    query += " ORDER BY created_at DESC"
    garments = [dict(g) for g in rows(query, params)]
    for garment in garments:
        garment["missing_details"] = missing_analysis_details(garment)
    return render_template("wardrobe.html", garments=garments, categories=CATEGORIES, selected=category)


def garment_form(garment=None, selected_style_tags=None):
    if garment and garment.get("palette"):
        try:
            garment["palette"] = json.loads(garment["palette"])
        except (TypeError, json.JSONDecodeError):
            garment["palette"] = []
    if garment and garment.get("analysis_json"):
        try:
            garment["analysis"] = json.loads(garment["analysis_json"])
        except (TypeError, json.JSONDecodeError):
            garment["analysis"] = {}
    if selected_style_tags is None:
        selected_style_tags = garment.get("style_tags", "") if garment else ""
    return render_template("garment_form.html", garment=garment, categories=CATEGORIES,
                           apparel_categories=APPAREL_CATEGORIES, fit_options=FIT_OPTIONS,
                           shoe_styles=SHOE_STYLES, accessory_types=ACCESSORY_TYPES,
                           style_tag_groups=STYLE_TAG_GROUPS, selected_style_tags=parse_style_tags(selected_style_tags))


def selected_tags_from_form():
    submitted = request.form.getlist("style_tags")
    selected = parse_style_tags(submitted)
    if len(selected) != len(set(value.strip().casefold() for value in submitted)):
        raise ValueError("Choose style tags from SEAM's list only.")
    if len(selected) > 5:
        raise ValueError("Choose up to five style tags. You can also leave them empty.")
    return ",".join(selected)


@app.route("/garments/new", methods=["GET", "POST"])
def garment_new():
    if request.method == "GET":
        return garment_form()
    try:
        name = request.form.get("name", "").strip()
        category = request.form.get("category", "")
        if not name or len(name) > 100 or category not in CATEGORIES:
            raise ValueError("Add a name (up to 100 characters) and choose a category.")
        fit = request.form.get("fit", "").strip() if category in APPAREL_CATEGORIES else ""
        shoe_style = request.form.get("shoe_style", "").strip() if category == "Footwear" else ""
        accessory_type = request.form.get("accessory_type", "").strip() if category == "Accessories" else ""
        if fit and fit not in FIT_OPTIONS or shoe_style and shoe_style not in SHOE_STYLES or accessory_type and accessory_type not in ACCESSORY_TYPES:
            raise ValueError("Choose a valid category-specific option.")
        style_tags = selected_tags_from_form()
        path, analysis, cutout_path, _issue = save_image(request.files.get("image"), request.form.get("garment_box", ""))
        color = request.form.get("color", "").strip()[:50]
        if not color and analysis:
            color = analysis["palette"][0]
        with get_db() as db:
            db.execute("""INSERT INTO garments(name,category,color,material,fit,style_tags,image_path,description,palette,brightness,saturation,cutout_path,analysis_json,shoe_style,accessory_type)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (name, category, color, request.form.get("material", "").strip()[:60],
                fit, style_tags, path,
                request.form.get("description", "").strip()[:500], json.dumps(analysis["palette"]) if analysis else "",
                analysis["brightness"] if analysis else None, analysis["saturation"] if analysis else None,
                cutout_path, json.dumps(analysis) if analysis else "{}", shoe_style, accessory_type))
        flash("Garment added to your wardrobe.", "success")
        return redirect(url_for("wardrobe"))
    except (ValueError, OSError) as exc:
        flash(str(exc), "error")
        return garment_form(selected_style_tags=request.form.getlist("style_tags"))


@app.route("/garments/bulk", methods=["GET", "POST"])
def garment_bulk():
    if request.method == "GET":
        return render_template("garment_bulk.html", categories=CATEGORIES)
    category = request.form.get("category", "")
    uploads = request.files.getlist("images") + request.files.getlist("folder_images")
    uploads = [upload for upload in uploads if upload and upload.filename]
    if category not in CATEGORIES:
        flash("Choose a category for this batch.", "error")
        return render_template("garment_bulk.html", categories=CATEGORIES), 400
    if not uploads:
        flash("Choose multiple photos or select a folder of photos.", "error")
        return render_template("garment_bulk.html", categories=CATEGORIES), 400
    if len(uploads) > 25:
        flash("A batch can contain up to 25 photos. Split larger folders into smaller batches.", "error")
        return render_template("garment_bulk.html", categories=CATEGORIES), 400

    next_number = row("SELECT COALESCE(MAX(id), 0) + 1 AS next_number FROM garments")["next_number"]
    added = 0
    issues = []
    for index, upload in enumerate(uploads):
        try:
            image_path, analysis, cutout_path, issue = save_image(upload, keep_unanalyzed=True)
            insert_garment(f"Garment {next_number + index}", category, image_path, analysis, cutout_path)
            added += 1
            if issue:
                issues.append(upload.filename)
        except (ValueError, OSError) as exc:
            issues.append(f"{upload.filename} ({exc})")
    if added:
        flash(f"Added {added} {category.lower()} garment{'s' if added != 1 else ''}. Each is named Garment {next_number} onward; edit details any time.", "success")
    if issues:
        names = ", ".join(issues[:5])
        extra = f" and {len(issues) - 5} more" if len(issues) > 5 else ""
        flash(f"Some photos need attention: {names}{extra}. Items that could not be isolated were still added without color analysis so you can adjust their image individually.", "error")
    if not added:
        flash("No usable photos were added. Use PNG, JPG, JPEG, or WEBP images.", "error")
    return redirect(url_for("wardrobe"))


@app.route("/garments/<int:garment_id>/edit", methods=["GET", "POST"])
def garment_edit(garment_id):
    garment = get_garment(garment_id)
    if request.method == "GET":
        return garment_form(garment)
    try:
        name = request.form.get("name", "").strip(); category = request.form.get("category", "")
        if not name or len(name) > 100 or category not in CATEGORIES:
            raise ValueError("Add a name (up to 100 characters) and choose a category.")
        fit = request.form.get("fit", "").strip() if category in APPAREL_CATEGORIES else ""
        shoe_style = request.form.get("shoe_style", "").strip() if category == "Footwear" else ""
        accessory_type = request.form.get("accessory_type", "").strip() if category == "Accessories" else ""
        if fit and fit not in FIT_OPTIONS or shoe_style and shoe_style not in SHOE_STYLES or accessory_type and accessory_type not in ACCESSORY_TYPES:
            raise ValueError("Choose a valid category-specific option.")
        style_tags = selected_tags_from_form()
        path, analysis, cutout_path, _issue = save_image(request.files.get("image"), request.form.get("garment_box", ""))
        color = request.form.get("color", "").strip()[:50] or (analysis["palette"][0] if analysis else garment["color"])
        with get_db() as db:
            db.execute("""UPDATE garments SET name=?,category=?,color=?,material=?,fit=?,style_tags=?,image_path=?,description=?,
                palette=CASE WHEN ? != '' THEN ? ELSE palette END, brightness=COALESCE(?,brightness), saturation=COALESCE(?,saturation),
                cutout_path=CASE WHEN ? != '' THEN ? ELSE cutout_path END, analysis_json=CASE WHEN ? != '{}' THEN ? ELSE analysis_json END,
                shoe_style=?,accessory_type=? WHERE id=?""",
                (name, category, color, request.form.get("material", "").strip()[:60], fit,
                 style_tags, path or garment["image_path"], request.form.get("description", "").strip()[:500],
                 json.dumps(analysis["palette"]) if analysis else "", json.dumps(analysis["palette"]) if analysis else "",
                 analysis["brightness"] if analysis else None, analysis["saturation"] if analysis else None,
                 cutout_path, cutout_path, json.dumps(analysis) if analysis else "{}", json.dumps(analysis) if analysis else "{}",
                 shoe_style, accessory_type, garment_id))
        flash("Garment updated.", "success"); return redirect(url_for("wardrobe"))
    except (ValueError, OSError) as exc:
        flash(str(exc), "error"); return garment_form(garment, request.form.getlist("style_tags"))


@app.post("/garments/<int:garment_id>/delete")
def garment_delete(garment_id):
    garment = get_garment(garment_id)
    with get_db() as db:
        db.execute("DELETE FROM garments WHERE id=?", (garment_id,))
    if garment["image_path"]:
        (Path(app.static_folder) / garment["image_path"]).unlink(missing_ok=True)
    if garment.get("cutout_path"):
        (Path(app.static_folder) / garment["cutout_path"]).unlink(missing_ok=True)
    flash("Garment deleted.", "success"); return redirect(url_for("wardrobe"))


@app.post("/garments/<int:garment_id>/rename")
def garment_rename(garment_id):
    get_garment(garment_id)
    name = request.form.get("name", "").strip()
    category = request.form.get("category", "")
    if not name or len(name) > 100:
        flash("Enter a name with 1 to 100 characters.", "error")
    else:
        with get_db() as db:
            db.execute("UPDATE garments SET name=? WHERE id=?", (name, garment_id))
        flash("Garment renamed.", "success")
    return redirect(url_for("wardrobe", category=category if category in CATEGORIES else ""))


@app.post("/garments/bulk-delete")
def garments_bulk_delete():
    ids = list(dict.fromkeys(request.form.getlist("garment_ids", type=int)))
    if not ids:
        flash("Select at least one garment to delete.", "error")
        return redirect(url_for("wardrobe"))
    selected = rows(f"SELECT id,image_path,cutout_path FROM garments WHERE id IN ({','.join('?' for _ in ids)})", ids)
    with get_db() as db:
        db.execute(f"DELETE FROM garments WHERE id IN ({','.join('?' for _ in ids)})", ids)
    for garment in selected:
        for column in ("image_path", "cutout_path"):
            if garment[column]:
                (Path(app.static_folder) / garment[column]).unlink(missing_ok=True)
    flash(f"Deleted {len(selected)} garment{'s' if len(selected) != 1 else ''}.", "success")
    return redirect(url_for("wardrobe"))


@app.get("/outfits")
def outfits():
    saved = rows("""SELECT o.*, COUNT(og.garment_id) AS garment_count FROM outfits o
        LEFT JOIN outfit_garments og ON og.outfit_id=o.id GROUP BY o.id ORDER BY o.created_at DESC""")
    return render_template("outfits.html", outfits=saved)


@app.route("/outfits/new", methods=["GET", "POST"])
def outfit_new():
    garments = rows("SELECT * FROM garments ORDER BY category,name")
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        ids = list(dict.fromkeys(request.form.getlist("garment_ids", type=int)))
        valid = rows(f"SELECT * FROM garments WHERE id IN ({','.join('?' for _ in ids)})", ids) if ids else []
        if not name or len(name) > 100 or not valid:
            flash("Give the outfit a name and select at least one garment.", "error")
        else:
            try:
                fit_pic_path = save_fit_pic(request.files.get("fit_pic"))
            except (ValueError, OSError) as exc:
                flash(str(exc), "error")
                return render_template("outfit_new.html", garments=garments)
            scores = score_outfit([dict(g) for g in valid])
            with get_db() as db:
                cursor = db.execute("INSERT INTO outfits(name,description,fit_pic_path) VALUES(?,?,?)",
                                    (name, request.form.get("description", "").strip()[:500], fit_pic_path))
                outfit_id = cursor.lastrowid
                db.executemany("INSERT INTO outfit_garments(outfit_id,garment_id) VALUES(?,?)", [(outfit_id, g["id"]) for g in valid])
                db.execute("INSERT INTO outfit_scores(outfit_id,color_score,style_score,silhouette_score,completeness_score,balance_score,overall_score) VALUES(?,?,?,?,?,?,?)",
                           (outfit_id, scores["color"], scores["style"], scores["silhouette"], scores["completeness"], scores["balance"], scores["overall"]))
            return redirect(url_for("outfit_detail", outfit_id=outfit_id))
    return render_template("outfit_new.html", garments=garments)


@app.context_processor
def template_helpers():
    return {}


@app.route("/outfits/<int:outfit_id>")
def outfit_detail(outfit_id):
    outfit = get_outfit(outfit_id)
    scores, alternatives = improvement_suggestions(outfit["garments"], [dict(g) for g in rows("SELECT * FROM garments")])
    return render_template("outfit_detail.html", outfit=outfit, scores=scores, alternatives=alternatives)


@app.route("/outfits/<int:outfit_id>/edit", methods=["GET", "POST"])
def outfit_edit(outfit_id):
    outfit = get_outfit(outfit_id)
    garments = rows("SELECT * FROM garments ORDER BY category,name")
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        ids = list(dict.fromkeys(request.form.getlist("garment_ids", type=int)))
        selected = rows(f"SELECT * FROM garments WHERE id IN ({','.join('?' for _ in ids)})", ids) if ids else []
        if not name or len(name) > 100 or not selected:
            flash("Give the outfit a name and select at least one garment.", "error")
        else:
            try:
                uploaded_fit_pic = save_fit_pic(request.files.get("fit_pic"))
            except (ValueError, OSError) as exc:
                flash(str(exc), "error")
                return render_template("outfit_edit.html", outfit=outfit, garments=garments,
                                       selected_ids={g["id"] for g in outfit["garments"]})
            old_fit_pic = outfit.get("fit_pic_path", "")
            if request.form.get("remove_fit_pic"):
                fit_pic_path = ""
            else:
                fit_pic_path = uploaded_fit_pic or old_fit_pic
            scores = score_outfit([dict(g) for g in selected])
            with get_db() as db:
                db.execute("UPDATE outfits SET name=?,description=?,fit_pic_path=? WHERE id=?",
                           (name, request.form.get("description", "").strip()[:500], fit_pic_path, outfit_id))
                db.execute("DELETE FROM outfit_garments WHERE outfit_id=?", (outfit_id,))
                db.executemany("INSERT INTO outfit_garments(outfit_id,garment_id) VALUES(?,?)", [(outfit_id, g["id"]) for g in selected])
                db.execute("INSERT INTO outfit_scores(outfit_id,color_score,style_score,silhouette_score,completeness_score,balance_score,overall_score) VALUES(?,?,?,?,?,?,?)",
                           (outfit_id, scores["color"], scores["style"], scores["silhouette"], scores["completeness"], scores["balance"], scores["overall"]))
            if old_fit_pic and old_fit_pic != fit_pic_path:
                (Path(app.static_folder) / old_fit_pic).unlink(missing_ok=True)
            flash("Outfit updated and rescored.", "success")
            return redirect(url_for("outfit_detail", outfit_id=outfit_id))
    return render_template("outfit_edit.html", outfit=outfit, garments=garments,
                           selected_ids={g["id"] for g in outfit["garments"]})


@app.post("/outfits/<int:outfit_id>/replace")
def outfit_replace(outfit_id):
    outfit = get_outfit(outfit_id)
    remove_id = request.form.get("remove_id", type=int)
    add_id = request.form.get("add_id", type=int)
    candidate = row("SELECT * FROM garments WHERE id=?", (add_id,))
    if not any(g["id"] == remove_id for g in outfit["garments"]) or not candidate or not any(g["category"] == candidate["category"] for g in outfit["garments"] if g["id"] == remove_id):
        abort(400)
    selected = [dict(candidate) if g["id"] == remove_id else g for g in outfit["garments"]]
    scores = score_outfit(selected)
    with get_db() as db:
        db.execute("DELETE FROM outfit_garments WHERE outfit_id=? AND garment_id=?", (outfit_id, remove_id))
        db.execute("INSERT INTO outfit_garments(outfit_id,garment_id) VALUES(?,?)", (outfit_id, add_id))
        db.execute("INSERT INTO outfit_scores(outfit_id,color_score,style_score,silhouette_score,completeness_score,balance_score,overall_score) VALUES(?,?,?,?,?,?,?)",
                   (outfit_id, scores["color"], scores["style"], scores["silhouette"], scores["completeness"], scores["balance"], scores["overall"]))
    flash(f"Outfit updated. Recalculated compatibility: {scores['overall']:.0f}/100.", "success")
    return redirect(url_for("outfit_detail", outfit_id=outfit_id))


@app.post("/outfits/<int:outfit_id>/delete")
def outfit_delete(outfit_id):
    outfit = get_outfit(outfit_id)
    with get_db() as db: db.execute("DELETE FROM outfits WHERE id=?", (outfit_id,))
    if outfit.get("fit_pic_path"):
        (Path(app.static_folder) / outfit["fit_pic_path"]).unlink(missing_ok=True)
    flash("Outfit deleted.", "success"); return redirect(url_for("outfits"))


@app.route("/recommendations")
def recommendations():
    garments = [dict(g) for g in rows("SELECT * FROM garments")]
    return render_template("recommendations.html", recommendations=recommend(garments), garment_count=len(garments))


@app.route("/style-profile")
def style_profile():
    garments = [dict(g) for g in rows("SELECT * FROM garments")]
    return render_template("style_profile.html", profile=summarize(garments), garment_count=len(garments))


if __name__ == "__main__":
    app.run(debug=True)
