from __future__ import annotations

from typing import Tuple, Dict

import base64
import io
import numpy as np
from PIL import Image, ImageOps
import imagehash

try:
    import cv2  # type: ignore
except Exception:  # pragma: no cover
    cv2 = None  # type: ignore


def normalize_card_image(image: Image.Image, size: Tuple[int, int] = (256, 256)) -> np.ndarray:
    image = ImageOps.exif_transpose(image)
    image = ImageOps.fit(image.convert("L"), size, method=Image.Resampling.LANCZOS)
    return np.array(image)


def _hash_to_array(hash_obj: imagehash.ImageHash) -> np.ndarray:
    return np.array(hash_obj.hash, dtype=np.uint8)


def compute_fingerprint(image: Image.Image, *, tile_grid: Tuple[int, int] = (2, 2), use_orb: bool | None = False) -> Dict[str, np.ndarray]:
    normalised = normalize_card_image(image)
    pil_gray = Image.fromarray(normalised)

    phash = _hash_to_array(imagehash.phash(pil_gray))
    dhash = _hash_to_array(imagehash.dhash(pil_gray))

    rows, cols = tile_grid
    h, w = normalised.shape
    tiles: list[np.ndarray] = []
    for r in range(rows):
        for c in range(cols):
            tile = normalised[r * h // rows : (r + 1) * h // rows, c * w // cols : (c + 1) * w // cols]
            tiles.append(_hash_to_array(imagehash.phash(Image.fromarray(tile))))
    tile_phash = np.stack(tiles)

    orb_desc = np.empty((0, 32), dtype=np.uint8)
    if use_orb and cv2 is not None:  # pragma: no cover
        detector = cv2.ORB_create()
        _kps, descriptors = detector.detectAndCompute(normalised, None)
        if descriptors is not None:
            orb_desc = descriptors.astype(np.uint8)

    return {"phash": phash, "dhash": dhash, "tile_phash": tile_phash, "orb": orb_desc}


def pack_ndarray(arr: np.ndarray) -> str:
    buf = io.BytesIO()
    np.save(buf, arr)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def unpack_ndarray(data: str) -> np.ndarray:
    buf = io.BytesIO(base64.b64decode(data.encode("ascii")))
    buf.seek(0)
    return np.load(buf, allow_pickle=False)


def hamming_distance(a: np.ndarray, b: np.ndarray) -> int:
    a = np.asarray(a, dtype=bool)
    b = np.asarray(b, dtype=bool)
    if a.shape != b.shape:
        return 999999
    return int(np.count_nonzero(a != b))

