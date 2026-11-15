"""Foreground-first, explainable garment image analysis using OpenCV."""
from io import BytesIO
import cv2
import numpy as np
from PIL import Image, ImageOps
from sklearn.cluster import KMeans


def _foreground_mask(rgb: np.ndarray, garment_box=None) -> np.ndarray:
    """Find the garment with GrabCut, using image borders as background seeds.

    ``garment_box`` is an optional normalized (x, y, width, height) box. A
    user supplied box is valuable for off-center products and busy scenes.
    """
    height, width = rgb.shape[:2]
    if garment_box:
        x, y, box_w, box_h = garment_box
        left = max(0, min(width - 2, round(x * width)))
        top = max(0, min(height - 2, round(y * height)))
        right = max(left + 2, min(width, round((x + box_w) * width)))
        bottom = max(top + 2, min(height, round((y + box_h) * height)))
        rect = (left, top, right - left, bottom - top)
        mask = np.full((height, width), cv2.GC_BGD, dtype=np.uint8)
        mask[top:bottom, left:right] = cv2.GC_PR_FGD
        margin_x = max(1, round((right - left) * .035))
        margin_y = max(1, round((bottom - top) * .035))
        mask[top + margin_y:bottom - margin_y, left + margin_x:right - margin_x] = cv2.GC_FGD
        mode = cv2.GC_INIT_WITH_MASK
    else:
        margin = max(2, round(min(width, height) * .035))
        rect = (margin, margin, width - 2 * margin, height - 2 * margin)
        mask = np.full((height, width), cv2.GC_PR_FGD, dtype=np.uint8)
        mask[:margin, :] = cv2.GC_BGD
        mask[-margin:, :] = cv2.GC_BGD
        mask[:, :margin] = cv2.GC_BGD
        mask[:, -margin:] = cv2.GC_BGD
        mode = cv2.GC_INIT_WITH_MASK
    background_model = np.zeros((1, 65), np.float64)
    foreground_model = np.zeros((1, 65), np.float64)
    cv2.grabCut(rgb, mask, rect, background_model, foreground_model, 5, mode)
    foreground = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)

    # Remove isolated noise and fill tiny gaps without changing garment colors.
    kernel = np.ones((3, 3), np.uint8)
    foreground = cv2.morphologyEx(foreground, cv2.MORPH_OPEN, kernel)
    foreground = cv2.morphologyEx(foreground, cv2.MORPH_CLOSE, kernel)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(foreground, 8)
    if count > 1:
        areas = stats[1:, cv2.CC_STAT_AREA]
        largest = int(areas.max())
        keep = [i + 1 for i, area in enumerate(areas) if area >= max(12, largest * .015)]
        foreground = np.where(np.isin(labels, keep), 255, 0).astype(np.uint8)
    return foreground


def _surface_detail(rgb: np.ndarray, mask: np.ndarray) -> tuple[str, float]:
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 55, 135)
    garment_pixels = mask > 0
    edge_ratio = float(np.count_nonzero((edges > 0) & garment_pixels) / max(1, garment_pixels.sum()))
    if edge_ratio < .045:
        label = "Low visible surface detail"
    elif edge_ratio < .13:
        label = "Some visible surface detail"
    else:
        label = "High visible surface detail"
    return label, edge_ratio


def _silhouette_hint(mask: np.ndarray) -> str:
    """Describe broad vertical outline changes without naming a garment type."""
    ys, xs = np.where(mask > 0)
    if not len(xs):
        return "Unclear outline"
    crop = mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1] > 0
    row_widths = crop.sum(axis=1).astype(float)
    length = len(row_widths)
    if length < 12:
        return "Unclear outline"
    section = max(1, length // 10)
    top = float(np.median(row_widths[section:section * 3]))
    middle = float(np.median(row_widths[length * 4 // 10:length * 6 // 10]))
    hem = float(np.median(row_widths[length * 7 // 10:length * 9 // 10]))
    if middle <= 0:
        return "Unclear outline"
    if top > hem * 1.28:
        return "Broader at top"
    if hem > top * 1.28:
        return "Wider toward hem"
    if abs(top - hem) / max(top, hem, 1) < .16 and abs(middle - top) / max(middle, top, 1) < .18:
        return "Mostly straight outline"
    return "Uneven or tapered outline"


def analyze_image(image_bytes: bytes, clusters: int = 4, garment_box=None) -> dict:
    """Analyze foreground pixels; returns palette, visual estimates, and cutout PNG.

    Foreground segmentation is strongest for one centered item on a fairly
    distinct background. The caller can supply a normalized garment box for
    off-center or cluttered photos. No material or semantic garment claim is
    inferred from pixels.
    """
    image = Image.open(BytesIO(image_bytes))
    image = ImageOps.exif_transpose(image).convert("RGB")
    image.thumbnail((480, 480))
    rgb = np.asarray(image, dtype=np.uint8)
    mask = _foreground_mask(rgb, garment_box)
    height, width = mask.shape
    foreground = mask > 0
    foreground_ratio = float(foreground.mean())
    if foreground_ratio < .025 or foreground_ratio > .92:
        raise ValueError("SEAM could not isolate a garment confidently. Draw a closer box around the item and try again.")

    samples = rgb[foreground]
    distinct = len(np.unique(samples, axis=0))
    k = max(1, min(clusters, len(samples), distinct))
    model = KMeans(n_clusters=k, random_state=42, n_init=5)
    labels = model.fit_predict(samples)
    counts = np.bincount(labels, minlength=k)
    centers = np.clip(model.cluster_centers_, 0, 255).astype(int)
    order = np.argsort(counts)[::-1]
    palette = ["#%02x%02x%02x" % tuple(centers[i]) for i in order]

    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    selected_hsv = hsv[foreground]
    ys, xs = np.where(foreground)
    box_width = int(xs.max() - xs.min() + 1)
    box_height = int(ys.max() - ys.min() + 1)
    surface_label, edge_ratio = _surface_detail(rgb, mask)

    rgba = np.dstack((rgb, mask))
    cutout = Image.fromarray(rgba, mode="RGBA")
    cutout.thumbnail((480, 480))
    output = BytesIO()
    cutout.save(output, format="PNG", optimize=True)

    # Border leakage is a useful warning signal, not a quality guarantee.
    border = np.zeros_like(mask, dtype=bool)
    border[:max(1, height // 30), :] = True
    border[-max(1, height // 30):, :] = True
    border[:, :max(1, width // 30)] = True
    border[:, -max(1, width // 30):] = True
    edge_leak = float((foreground & border).sum() / max(1, foreground.sum()))
    if edge_leak > .08:
        note = "Check the cutout: background may remain around the garment. Adjust the selection box if needed."
    else:
        note = "Palette uses the extracted foreground. Review the cutout, especially for patterned or low-contrast items."

    return {
        "palette": palette,
        "brightness": round(float(selected_hsv[:, 2].mean() / 255), 3),
        "saturation": round(float(selected_hsv[:, 1].mean() / 255), 3),
        "foreground_ratio": round(foreground_ratio, 3),
        "shape_ratio": round(box_width / max(1, box_height), 3),
        "silhouette_hint": _silhouette_hint(mask),
        "surface_detail": surface_label,
        "edge_ratio": round(edge_ratio, 3),
        "analysis_note": note,
        "foreground_png": output.getvalue(),
    }
