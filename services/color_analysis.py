"""Lightweight, explainable color analysis using OpenCV and K-Means."""
from io import BytesIO
import cv2
import numpy as np
from PIL import Image, ImageOps
from sklearn.cluster import KMeans


def analyze_image(image_bytes: bytes, clusters: int = 4) -> dict:
    """Return dominant RGB colors, average brightness, and saturation."""
    image = Image.open(BytesIO(image_bytes))
    image = ImageOps.exif_transpose(image).convert("RGB")
    image.thumbnail((160, 160))
    pixels = np.asarray(image, dtype=np.uint8)
    samples = pixels.reshape(-1, 3)
    k = max(1, min(clusters, len(samples), len(np.unique(samples, axis=0))))
    model = KMeans(n_clusters=k, random_state=42, n_init=5)
    labels = model.fit_predict(samples)
    counts = np.bincount(labels, minlength=k)
    centers = np.clip(model.cluster_centers_, 0, 255).astype(int)
    order = np.argsort(counts)[::-1]
    palette = ["#%02x%02x%02x" % tuple(centers[i]) for i in order]
    hsv = cv2.cvtColor(pixels, cv2.COLOR_RGB2HSV)
    return {
        "palette": palette,
        "brightness": round(float(hsv[:, :, 2].mean() / 255), 3),
        "saturation": round(float(hsv[:, :, 1].mean() / 255), 3),
    }
