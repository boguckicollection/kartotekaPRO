from __future__ import annotations

from typing import Optional, Tuple, List, Dict
from pathlib import Path
from PIL import Image, ImageOps
import imagehash
import json

_LOGO_HASHES: Dict[str, imagehash.ImageHash] = {}
_SET_NAME_BY_CODE: Dict[str, str] = {}


def _preprocess_symbol(im: Image.Image) -> Image.Image:
    im = ImageOps.fit(im.convert("L"), (64, 64), method=Image.Resampling.LANCZOS)
    im = ImageOps.autocontrast(im)
    return im


def _load_sets(root: Path) -> None:
    global _SET_NAME_BY_CODE
    for p in [root / "tcg_sets.json", root.parent / "tcg_sets.json"]:
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    _SET_NAME_BY_CODE = {str(k): str(v) for k, v in data.items()}
                elif isinstance(data, list):
                    out: Dict[str, str] = {}
                    for it in data:
                        try:
                            c = it.get("code") or it.get("id")
                            n = it.get("name") or it.get("set")
                            if c and n:
                                out[str(c)] = str(n)
                        except Exception:
                            continue
                    _SET_NAME_BY_CODE = out
            except Exception:
                _SET_NAME_BY_CODE = {}
            break


def _load_logos(root: Path) -> None:
    global _LOGO_HASHES
    logo_dir = None
    for p in [root / "set_logos", root.parent / "set_logos"]:
        if p.exists() and p.is_dir():
            logo_dir = p
            break
    if not logo_dir:
        return
    _LOGO_HASHES.clear()
    for f in logo_dir.iterdir():
        if f.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
            continue
        code = f.stem
        try:
            with Image.open(f) as im:
                im = _preprocess_symbol(im)
                _LOGO_HASHES[code] = imagehash.phash(im)
        except Exception:
            continue


def _ensure_loaded() -> None:
    root = Path(__file__).parent.parent.parent
    if not _LOGO_HASHES:
        _load_logos(root)
    if not _SET_NAME_BY_CODE:
        _load_sets(root)


def _candidate_rects(w: int, h: int) -> List[Tuple[int, int, int, int]]:
    if w <= 100 and h <= 100:
        return [(0, 0, w, h)]
    rects: List[Tuple[int, int, int, int]] = []
    upper = int(h * 0.70)
    lower = int(h * 0.25)
    right = int(w * 0.35)
    left = w - right
    rects.append((0, upper, right, h))       # bottom-left
    rects.append((left, upper, w, h))        # bottom-right
    rects.append((0, 0, right, lower))       # top-left (stare karty)
    rects.append((left, 0, w, lower))        # top-right
    return rects


def identify_set_by_symbol(image_path: str) -> Optional[Tuple[str, str]]:
    """Return (set_code, set_name) by matching symbol/logo on the card image.

    Best-effort; returns None if cannot match.
    """
    _ensure_loaded()
    if not _LOGO_HASHES:
        return None
    try:
        with Image.open(image_path) as im:
            w, h = im.size
            best: Tuple[int, str] | None = None
            for rect in _candidate_rects(w, h):
                crop = im.crop(rect)
                crop = _preprocess_symbol(crop)
                ch = imagehash.phash(crop)
                for code, hh in _LOGO_HASHES.items():
                    diff = hh - ch
                    if (best is None) or (diff < best[0]):
                        best = (diff, code)
            if best is None:
                return None
            diff, code = best
            # threshold heuristic
            if diff <= 18:
                name = _SET_NAME_BY_CODE.get(code) or code
                return code, name
    except Exception:
        return None
    return None

