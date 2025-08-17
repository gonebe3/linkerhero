from __future__ import annotations

from typing import List
import io
import time

from flask import current_app

from .vision_extractor import render_pdf_to_images  # reuse robust PDF renderer


_EASYOCR_READERS: dict[tuple[str, ...], object] = {}


def _get_easyocr_reader(langs: List[str]):
    key = tuple(sorted(langs))
    if key in _EASYOCR_READERS:
        return _EASYOCR_READERS[key]
    try:
        import easyocr  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "EasyOCR is not installed. Please install with: pip install easyocr opencv-python-headless"
        ) from e
    try:
        reader = easyocr.Reader(langs, gpu=False, verbose=False)
    except Exception as e:
        raise RuntimeError(f"EasyOCR initialization failed: {e}")
    _EASYOCR_READERS[key] = reader
    return reader


def extract_text_from_pdf_via_easyocr(
    pdf_bytes: bytes,
    *,
    max_pages: int = 12,
    render_scale: float = 1.5,
    langs: List[str] | None = None,
    timeout_per_page_s: float = 8.0,
) -> str:
    """OCR a PDF using EasyOCR. Renders pages with pypdfium2 and runs OCR.

    Returns concatenated plain text. Raises RuntimeError with actionable message on failure.
    """
    if langs is None:
        try:
            cfg = current_app.config.get("EASYOCR_LANGS", "en,lt")
            langs = [s.strip() for s in str(cfg).split(",") if s.strip()]
        except Exception:
            langs = ["en", "lt"]

    images = render_pdf_to_images(pdf_bytes, max_pages=max_pages, scale=render_scale)
    if not images:
        raise RuntimeError("No pages rendered from PDF for OCR")

    reader = _get_easyocr_reader(langs)

    parts: list[str] = []
    start = time.monotonic()
    for idx, img_bytes in enumerate(images):
        remaining = timeout_per_page_s
        try:
            import numpy as np  # type: ignore
            from PIL import Image

            img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            np_img = np.array(img)
            result = reader.readtext(np_img, detail=0, paragraph=True)
            page_text = "\n".join([s for s in result if isinstance(s, str)])
            if page_text.strip():
                parts.append(page_text.strip())
        except Exception as e:
            # continue on per-page failures
            parts.append("")
        # crude guard to avoid runaway processing
        if time.monotonic() - start > (timeout_per_page_s * max_pages * 1.2):
            break

    text = "\n\n".join([p for p in parts if p])
    if not text.strip():
        raise RuntimeError(
            f"EasyOCR produced empty text (langs={langs}, pages={len(images)}). Consider increasing EASYOCR_LANGS or PDF_OCR_RENDER_SCALE."
        )
    return text


