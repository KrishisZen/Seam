"""Transparent wardrobe outfit compatibility scoring."""
from collections import Counter
from itertools import combinations
import colorsys
from PIL import ImageColor
from config import OVERALL_SCORE_CURVE, SCORING_WEIGHTS
from services.style_profile import parse_style_tags

WEIGHTS = SCORING_WEIGHTS
CORE = {"Tops", "Bottoms", "Footwear"}
SHOE_STYLE_AFFINITY = {
    "chunky": {"streetwear", "grunge", "utility", "casual", "athleisure", "avant-garde"},
    "derby": {"formal", "workwear", "minimal", "vintage", "preppy", "smart casual", "business casual"},
    "sneakers": {"streetwear", "casual", "utility", "athleisure", "minimal", "workwear"},
    "loafers": {"preppy", "formal", "minimal", "workwear", "vintage", "smart casual"},
    "boots": {"workwear", "grunge", "utility", "vintage", "streetwear", "casual"},
    "sandals": {"casual", "vacation", "bohemian", "minimal", "resort"},
    "flats": {"minimal", "formal", "casual", "vintage", "preppy"},
    "heels": {"formal", "evening", "elegant", "minimal", "dressy"},
    "oxfords": {"formal", "workwear", "vintage", "preppy", "business casual"},
}
SHOE_STYLE_MISMATCH = {
    "chunky": {"formal", "evening", "business"},
    "derby": {"athleisure", "beachwear", "resort"},
    "sneakers": {"formal", "evening"},
    "loafers": {"athleisure", "grunge"},
    "sandals": {"business", "formal"},
    "oxfords": {"athleisure", "beachwear"},
}


def _hex(value):
    value = (value or "").strip().lstrip("#")
    try:
        return ImageColor.getrgb("#" + value if len(value) == 6 else value)[:3]
    except (ValueError, TypeError):
        return None


def _shoe_pairing_score(garments, tags):
    """Score shoe-style alignment with non-footwear style tags (heuristic)."""
    shoes = [g for g in garments if g.get("category") == "Footwear" and (g.get("shoe_style") or "").strip()]
    if not shoes:
        return None
    outfit_tags = set().union(*(tag_set for garment, tag_set in zip(garments, tags)
                                if garment.get("category") != "Footwear"))
    if not outfit_tags:
        return 62.0
    scores = []
    for shoe in shoes:
        style = shoe["shoe_style"].strip().lower()
        if outfit_tags & SHOE_STYLE_MISMATCH.get(style, set()):
            scores.append(38.0)
            continue
        overlap = outfit_tags & SHOE_STYLE_AFFINITY.get(style, set())
        scores.append(min(96.0, 78.0 + 6.0 * len(overlap)) if overlap else 62.0)
    return sum(scores) / len(scores)


def score_outfit(garments, weights=None):
    """Score garments with five deterministic dimensions, each from 0 to 100."""
    garments = list(garments)
    if not garments:
        return {"color": 0, "style": 0, "silhouette": 0, "completeness": 0, "balance": 0, "overall": 0}
    weights = dict(weights or WEIGHTS)
    if set(weights) != set(WEIGHTS) or any(value < 0 for value in weights.values()) or sum(weights.values()) <= 0:
        raise ValueError("Scoring weights must include all five dimensions, be non-negative, and have a positive total.")
    total_weight = sum(weights.values())
    weights = {key: value / total_weight for key, value in weights.items()}
    colors = []
    for g in garments:
        color = _hex(g.get("color"))
        if color:
            colors.append(colorsys.rgb_to_hsv(*(c / 255 for c in color)))
    if len(colors) < 2:
        color_score = 62.0 if colors else 50.0
    else:
        distances = []
        for (h1, s1, v1), (h2, s2, v2) in combinations(colors, 2):
            hue_dist = min(abs(h1 - h2), 1 - abs(h1 - h2)) * 2
            distances.append(min(1, .55 * hue_dist + .25 * abs(s1 - s2) + .20 * abs(v1 - v2)))
        # Moderate separation is useful; very similar or very distant combinations score lower.
        mean = sum(distances) / len(distances)
        color_score = 100 * max(0, 1 - abs(mean - .34) / .66)
    tags = [set(tag.casefold() for tag in parse_style_tags(g.get("style_tags") or "")) for g in garments]
    nonempty = [t for t in tags if t]
    if len(nonempty) < 2:
        style_score = 58.0 if nonempty else 50.0
    else:
        style_score = 100 * sum(len(a & b) / len(a | b) if a | b else 0 for a, b in combinations(nonempty, 2)) / len(list(combinations(nonempty, 2)))
    footwear_score = _shoe_pairing_score(garments, tags)
    if footwear_score is not None:
        # Footwear rules have lower influence than the user's own garment tags.
        style_score = .75 * style_score + .25 * footwear_score
    fits = [g.get("fit", "").strip().lower() for g in garments if g.get("fit", "").strip()]
    silhouette_score = 72.0 if len(fits) < 2 else max(45.0, 100 - 14 * (len(set(fits)) - 1))
    cats = {g.get("category") for g in garments}
    completeness_score = min(100.0, 48 + 19 * len(cats & CORE) + 8 * bool(cats & {"Outerwear", "Accessories"}))
    category_counts = Counter(g.get("category") for g in garments)
    balance_score = 100 - min(55, 20 * sum(max(0, count - 1) for cat, count in category_counts.items() if cat in CORE))
    scores = {"color": color_score, "style": style_score, "silhouette": silhouette_score,
              "completeness": completeness_score, "balance": balance_score}
    scores = {key: round(max(0, min(100, value)), 1) for key, value in scores.items()}
    weighted_score = sum(scores[k] * weights[k] for k in weights)
    # Compress the top end so a heuristic estimate does not imply easy certainty.
    scores["overall"] = round(100 * (weighted_score / 100) ** OVERALL_SCORE_CURVE, 1)
    return scores


def improvement_suggestions(selected, wardrobe):
    """Try each one-for-one replacement and return real re-scored improvements."""
    current = score_outfit(selected)
    if not selected:
        return current, []
    weakest = min(WEIGHTS, key=lambda key: current[key])
    suggestions = []
    selected_ids = {g["id"] for g in selected}
    selected_by_category = {g["category"]: g for g in selected}
    for original in selected:
        for candidate in wardrobe:
            if candidate["id"] in selected_ids or candidate["category"] != original["category"]:
                continue
            trial = [candidate if g["id"] == original["id"] else g for g in selected]
            revised = score_outfit(trial)
            if revised["overall"] > current["overall"]:
                suggestions.append({"remove": original, "add": candidate, "scores": revised,
                                    "gain": round(revised["overall"] - current["overall"], 1), "weakest": weakest})
    suggestions.sort(key=lambda s: s["gain"], reverse=True)
    return current, suggestions[:3]
