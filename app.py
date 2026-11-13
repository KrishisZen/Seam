"""SEAM: Computational Wardrobe & Personal Style Intelligence."""
from pathlib import Path
import json
from flask import Flask, abort, flash, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename
from config import ALLOWED_EXTENSIONS, MAX_CONTENT_LENGTH, SECRET_KEY, UPLOAD_FOLDER
from database import get_db, init_db, row, rows
from services.color_analysis import analyze_image
from services.outfit_recommendation import recommend
from services.outfit_scoring import improvement_suggestions, score_outfit
from services.style_profile import summarize

app = Flask(__name__)
app.config.update(SECRET_KEY=SECRET_KEY, MAX_CONTENT_LENGTH=MAX_CONTENT_LENGTH)
Path(UPLOAD_FOLDER).mkdir(parents=True, exist_ok=True)
init_db()
CATEGORIES = ["Tops", "Bottoms", "Outerwear", "Footwear", "Accessories"]


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


def save_image(file):
    if not file or not file.filename:
        return "", None
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError("Use a PNG, JPG, JPEG, or WEBP image.")
    data = file.read()
    if not data:
        raise ValueError("The selected image is empty.")
    analysis = analyze_image(data)
    filename = secure_filename(f"{__import__('uuid').uuid4().hex}.{ext}")
    (Path(UPLOAD_FOLDER) / filename).write_bytes(data)
    return f"uploads/{filename}", analysis


@app.errorhandler(413)
def too_large(_error):
    flash("Images must be 8 MB or smaller.", "error")
    return redirect(url_for("garment_new"))


@app.route("/")
def dashboard():
    garments = rows("SELECT * FROM garments ORDER BY created_at DESC LIMIT 6")
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
    return render_template("wardrobe.html", garments=rows(query, params), categories=CATEGORIES, selected=category)


def garment_form(garment=None):
    if garment and garment.get("palette"):
        try:
            garment["palette"] = json.loads(garment["palette"])
        except (TypeError, json.JSONDecodeError):
            garment["palette"] = []
    return render_template("garment_form.html", garment=garment, categories=CATEGORIES)


@app.route("/garments/new", methods=["GET", "POST"])
def garment_new():
    if request.method == "GET":
        return garment_form()
    try:
        name = request.form.get("name", "").strip()
        category = request.form.get("category", "")
        if not name or len(name) > 100 or category not in CATEGORIES:
            raise ValueError("Add a name (up to 100 characters) and choose a category.")
        path, analysis = save_image(request.files.get("image"))
        color = request.form.get("color", "").strip()[:50]
        if not color and analysis:
            color = analysis["palette"][0]
        with get_db() as db:
            db.execute("""INSERT INTO garments(name,category,color,material,fit,style_tags,image_path,description,palette,brightness,saturation)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""", (name, category, color, request.form.get("material", "").strip()[:60],
                request.form.get("fit", "").strip()[:40], request.form.get("style_tags", "").strip()[:250], path,
                request.form.get("description", "").strip()[:500], json.dumps(analysis["palette"]) if analysis else "",
                analysis["brightness"] if analysis else None, analysis["saturation"] if analysis else None))
        flash("Garment added to your wardrobe.", "success")
        return redirect(url_for("wardrobe"))
    except (ValueError, OSError) as exc:
        flash(str(exc), "error")
        return garment_form()


@app.route("/garments/<int:garment_id>/edit", methods=["GET", "POST"])
def garment_edit(garment_id):
    garment = get_garment(garment_id)
    if request.method == "GET":
        return garment_form(garment)
    try:
        name = request.form.get("name", "").strip(); category = request.form.get("category", "")
        if not name or len(name) > 100 or category not in CATEGORIES:
            raise ValueError("Add a name (up to 100 characters) and choose a category.")
        path, analysis = save_image(request.files.get("image"))
        color = request.form.get("color", "").strip()[:50] or (analysis["palette"][0] if analysis else garment["color"])
        with get_db() as db:
            db.execute("""UPDATE garments SET name=?,category=?,color=?,material=?,fit=?,style_tags=?,image_path=?,description=?,
                palette=CASE WHEN ? != '' THEN ? ELSE palette END, brightness=COALESCE(?,brightness), saturation=COALESCE(?,saturation) WHERE id=?""",
                (name, category, color, request.form.get("material", "").strip()[:60], request.form.get("fit", "").strip()[:40],
                 request.form.get("style_tags", "").strip()[:250], path or garment["image_path"], request.form.get("description", "").strip()[:500],
                 json.dumps(analysis["palette"]) if analysis else "", json.dumps(analysis["palette"]) if analysis else "",
                 analysis["brightness"] if analysis else None, analysis["saturation"] if analysis else None, garment_id))
        flash("Garment updated.", "success"); return redirect(url_for("wardrobe"))
    except (ValueError, OSError) as exc:
        flash(str(exc), "error"); return garment_form(garment)


@app.post("/garments/<int:garment_id>/delete")
def garment_delete(garment_id):
    garment = get_garment(garment_id)
    with get_db() as db:
        db.execute("DELETE FROM garments WHERE id=?", (garment_id,))
    if garment["image_path"]:
        (Path(app.static_folder) / garment["image_path"]).unlink(missing_ok=True)
    flash("Garment deleted.", "success"); return redirect(url_for("wardrobe"))


@app.route("/outfits", methods=["GET", "POST"])
def outfits():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        ids = list(dict.fromkeys(request.form.getlist("garment_ids", type=int)))
        valid = rows(f"SELECT * FROM garments WHERE id IN ({','.join('?' for _ in ids)})", ids) if ids else []
        if not name or len(name) > 100 or not valid:
            flash("Give the outfit a name and select at least one garment.", "error")
        else:
            with get_db() as db:
                cursor = db.execute("INSERT INTO outfits(name,description) VALUES(?,?)", (name, request.form.get("description", "").strip()[:500]))
                outfit_id = cursor.lastrowid
                db.executemany("INSERT INTO outfit_garments(outfit_id,garment_id) VALUES(?,?)", [(outfit_id, g["id"]) for g in valid])
                scores = score_outfit([dict(g) for g in valid])
                db.execute("INSERT INTO outfit_scores(outfit_id,color_score,style_score,silhouette_score,completeness_score,balance_score,overall_score) VALUES(?,?,?,?,?,?,?)",
                           (outfit_id, scores["color"], scores["style"], scores["silhouette"], scores["completeness"], scores["balance"], scores["overall"]))
            return redirect(url_for("outfit_detail", outfit_id=outfit_id))
    garments = rows("SELECT * FROM garments ORDER BY category,name")
    saved = rows("SELECT o.*, COUNT(og.garment_id) AS garment_count FROM outfits o LEFT JOIN outfit_garments og ON og.outfit_id=o.id GROUP BY o.id ORDER BY o.created_at DESC")
    return render_template("outfits.html", garments=garments, outfits=saved)


@app.context_processor
def template_helpers():
    def outfit_preview(outfit_id):
        return rows("""SELECT g.* FROM garments g JOIN outfit_garments og ON og.garment_id=g.id
            WHERE og.outfit_id=? ORDER BY g.category LIMIT 4""", (outfit_id,))
    return {"outfit_preview": outfit_preview}


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
            scores = score_outfit([dict(g) for g in selected])
            with get_db() as db:
                db.execute("UPDATE outfits SET name=?,description=? WHERE id=?", (name, request.form.get("description", "").strip()[:500], outfit_id))
                db.execute("DELETE FROM outfit_garments WHERE outfit_id=?", (outfit_id,))
                db.executemany("INSERT INTO outfit_garments(outfit_id,garment_id) VALUES(?,?)", [(outfit_id, g["id"]) for g in selected])
                db.execute("INSERT INTO outfit_scores(outfit_id,color_score,style_score,silhouette_score,completeness_score,balance_score,overall_score) VALUES(?,?,?,?,?,?,?)",
                           (outfit_id, scores["color"], scores["style"], scores["silhouette"], scores["completeness"], scores["balance"], scores["overall"]))
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
    get_outfit(outfit_id)
    with get_db() as db: db.execute("DELETE FROM outfits WHERE id=?", (outfit_id,))
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
