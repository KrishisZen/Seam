"""Generate and rank feasible wardrobe combinations."""
from collections import Counter
from itertools import product
from services.outfit_scoring import score_outfit


def recommend(garments, limit=5, offset=0):
    groups = {category: [g for g in garments if g["category"] == category]
              for category in ("Tops", "Bottoms", "Footwear")}
    if not all(groups.values()):
        return []
    outfits = []
    for top, bottom, shoes in product(groups["Tops"], groups["Bottoms"], groups["Footwear"]):
        base = [top, bottom, shoes]
        optional = [g for g in garments if g["category"] in ("Outerwear", "Accessories")]
        outfits.append({"garments": base, "scores": score_outfit(base)})
        for extra in optional:
            combo = base + [extra]
            outfits.append({"garments": combo, "scores": score_outfit(combo)})
    outfits.sort(key=lambda item: item["scores"]["overall"], reverse=True)
    unique, seen = [], set()
    for item in outfits:
        key = tuple(sorted(g["id"] for g in item["garments"]))
        if key not in seen:
            unique.append(item); seen.add(key)

    # Spread appearances across garments so the page doesn't keep repeating
    # the same few wardrobe staples in slightly different combinations.
    diversified, usage = [], Counter()
    remaining = unique[:]
    while remaining:
        best_index = max(
            range(len(remaining)),
            key=lambda index: (
                remaining[index]["scores"]["overall"]
                - 7 * sum(usage[g["id"]] for g in remaining[index]["garments"]),
                remaining[index]["scores"]["overall"],
            ),
        )
        chosen = remaining.pop(best_index)
        diversified.append(chosen)
        usage.update(g["id"] for g in chosen["garments"])

    if limit is None:
        return diversified[offset:] if offset else diversified
    return diversified[offset:offset + limit]
