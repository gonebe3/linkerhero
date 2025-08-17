from __future__ import annotations

from typing import List
import base64
import io
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import traceback

from flask import current_app
import traceback


def _pil_to_jpeg_bytes(img) -> bytes:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def render_pdf_to_images(pdf_bytes: bytes, *, max_pages: int = 6, scale: float = 1.5) -> List[bytes]:
    """Render PDF to JPEG bytes using pypdfium2 (no poppler required)."""
    try:
        # Ensure Pillow is available for pypdfium2.to_pil()
        try:
            from PIL import Image as _PILImage  # noqa: F401
        except ModuleNotFoundError as e:
            py_info = f"python={sys.executable or 'unknown'} version={sys.version.split()[0]}"
            raise RuntimeError(
                f"Pillow (PIL) is not installed in the running interpreter ({py_info})."
            ) from e

        try:
            import pypdfium2 as pdfium  # type: ignore
        except ModuleNotFoundError as e:
            py_info = f"python={sys.executable or 'unknown'} version={sys.version.split()[0]}"
            raise RuntimeError(
                f"pypdfium2 is not installed in the running interpreter ({py_info})."
            ) from e

        images: List[bytes] = []
        pdf = pdfium.PdfDocument(io.BytesIO(pdf_bytes))
        n = min(len(pdf), max_pages)
        for i in range(n):
            page = pdf.get_page(i)
            pil = page.render(scale=scale).to_pil()
            images.append(_pil_to_jpeg_bytes(pil))
        if not images:
            raise RuntimeError("No pages rendered from PDF")
        return images
    except Exception as e:
        raise RuntimeError(f"PDF render error: {e}")


def _extract_with_anthropic(
    image_pages: List[bytes], *, api_key: str, timeout_s: float = 45.0, deadline: float | None = None, pages_per_batch: int = 4
) -> str:
    from anthropic import Anthropic

    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not configured")
    client = Anthropic(api_key=api_key)

    system = (
        "Extract plain text and tables as Markdown from the provided document page. "
        "Do NOT summarize or add commentary. Preserve language."
    )
    out_parts: List[str] = []
    # batch multiple pages in a single request for speed
    for i in range(0, len(image_pages), max(1, pages_per_batch)):
        if deadline and time.monotonic() > deadline:
            break
        batch = image_pages[i : i + pages_per_batch]
        content = [{"type": "text", "text": "Extract plain text and tables as Markdown. Preserve language."}]
        for b in batch:
            b64 = base64.b64encode(b).decode("ascii")
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": "image/jpeg", "data": b64},
            })
        resp = client.messages.create(
            model="claude-3-5-sonnet-20240620",
            system=system,
            max_tokens=1500,
            messages=[{"role": "user", "content": content}],
            timeout=timeout_s,
        )
        chunk_md = "".join([c.text for c in resp.content if getattr(c, "text", None)])
        if chunk_md:
            out_parts.append(chunk_md)
        if sum(len(p) for p in out_parts) > 9000:
            break
    return "\n\n".join(out_parts)


def _extract_with_openai(
    image_pages: List[bytes], *, api_key: str, timeout_s: float = 45.0, deadline: float | None = None, pages_per_batch: int = 4
) -> str:
    from openai import OpenAI

    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not configured")
    client = OpenAI(api_key=api_key)

    system = (
        "Extract plain text and tables as Markdown from the provided document page. "
        "Do NOT summarize or add commentary. Preserve language."
    )
    out_parts: List[str] = []
    for i in range(0, len(image_pages), max(1, pages_per_batch)):
        if deadline and time.monotonic() > deadline:
            break
        batch = image_pages[i : i + pages_per_batch]
        user_content = [{"type": "text", "text": "Extract plain text and tables as Markdown. Preserve language."}]
        for b in batch:
            b64 = base64.b64encode(b).decode("ascii")
            user_content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ]
        chat = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=1500,
            timeout=timeout_s,
        )
        chunk_md = chat.choices[0].message.content or ""
        if chunk_md:
            out_parts.append(chunk_md)
        if sum(len(p) for p in out_parts) > 9000:
            break
    return "\n\n".join(out_parts)


def extract_markdown_from_pdf_via_vision(pdf_bytes: bytes, *, max_pages: int = 6) -> str:
    # Allow config overrides
    try:
        cfg_pages = int(current_app.config.get("PDF_VISION_MAX_PAGES", max_pages) or max_pages)
    except Exception:
        cfg_pages = max_pages
    try:
        cfg_scale = float(current_app.config.get("PDF_VISION_SCALE", 1.5) or 1.5)
    except Exception:
        cfg_scale = 1.5
    try:
        timeout_s = float(current_app.config.get("PDF_VISION_TIMEOUT", 45.0) or 45.0)
    except Exception:
        timeout_s = 45.0
    try:
        pages_per_batch = int(current_app.config.get("PDF_VISION_PAGES_PER_BATCH", 4) or 4)
    except Exception:
        pages_per_batch = 4
    try:
        max_workers = int(current_app.config.get("PDF_VISION_MAX_WORKERS", 3) or 3)
    except Exception:
        max_workers = 3

    start = time.monotonic()
    overall_budget = timeout_s * cfg_pages  # rough upper bound

    images = render_pdf_to_images(pdf_bytes, max_pages=cfg_pages, scale=cfg_scale)
    provider = (current_app.config.get("LLM_PROVIDER", "anthropic") or "").lower()
    anthropic_key = current_app.config.get("ANTHROPIC_API_KEY")
    openai_key = current_app.config.get("OPENAI_API_KEY")

    # Split into batches
    batches: list[list[bytes]] = [
        images[i : i + pages_per_batch] for i in range(0, len(images), pages_per_batch)
    ]

    def _run_batch(batch: list[bytes]) -> tuple[str, str | None]:
        remaining = max(0.0, (start + overall_budget) - time.monotonic())
        per_call_timeout = min(timeout_s, remaining or timeout_s)
        if provider in {"openai", "gpt", "gpt5", "chatgpt"}:
            try:
                return _extract_with_openai(batch, api_key=openai_key or "", timeout_s=per_call_timeout, deadline=start + overall_budget, pages_per_batch=pages_per_batch), None
            except Exception as e:
                return "", f"openai_error: {e}"
        else:
            try:
                return _extract_with_anthropic(batch, api_key=anthropic_key or "", timeout_s=per_call_timeout, deadline=start + overall_budget, pages_per_batch=pages_per_batch), None
            except Exception as e:
                return "", f"anthropic_error: {e}"

    parts: list[str] = []
    errors: list[str] = []
    try:
        with ThreadPoolExecutor(max_workers=min(max_workers, len(batches) or 1)) as pool:
            futures = [pool.submit(_run_batch, b) for b in batches]
            for fut in as_completed(futures, timeout=max(1.0, overall_budget)):
                try:
                    chunk, err = fut.result()
                    if err:
                        errors.append(err)
                    if chunk:
                        parts.append(chunk)
                except Exception as e:
                    # skip failed batch; continue with others
                    errors.append(str(e))
    except Exception as e:
        raise RuntimeError(f"Vision LLM extraction error: {e}")

    md = "\n\n".join([p for p in parts if p])
    if not md.strip():
        # Cross-provider fallback if available
        alt_provider = "openai" if provider not in {"openai", "gpt", "gpt5", "chatgpt"} else "anthropic"
        try:
            def _run_alt(batch: list[bytes]) -> str:
                remaining = max(0.0, (start + overall_budget) - time.monotonic())
                per_call_timeout = min(timeout_s, remaining or timeout_s)
                if alt_provider in {"openai", "gpt", "gpt5", "chatgpt"}:
                    return _extract_with_openai(batch, api_key=openai_key or "", timeout_s=per_call_timeout, deadline=start + overall_budget, pages_per_batch=pages_per_batch)
                else:
                    return _extract_with_anthropic(batch, api_key=anthropic_key or "", timeout_s=per_call_timeout, deadline=start + overall_budget, pages_per_batch=pages_per_batch)
            alt_parts: list[str] = []
            with ThreadPoolExecutor(max_workers=min(max_workers, len(batches) or 1)) as pool:
                futures2 = [pool.submit(_run_alt, b) for b in batches]
                for fut in as_completed(futures2, timeout=max(1.0, overall_budget)):
                    try:
                        chunk2 = fut.result()
                        if chunk2:
                            alt_parts.append(chunk2)
                    except Exception:
                        pass
            md = "\n\n".join([p for p in alt_parts if p])
        except Exception:
            pass

    if not md.strip():
        # Fallback: try lightweight server-side text extraction with pdfplumber for selectable-text PDFs
        try:
            import pdfplumber  # type: ignore
            text_parts: list[str] = []
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                page_count = min(len(pdf.pages), cfg_pages)
                for i in range(page_count):
                    try:
                        p = pdf.pages[i]
                        txt = (p.extract_text() or "").strip()
                        if txt:
                            text_parts.append(txt)
                    except Exception:
                        # ignore per-page failures
                        pass
            fallback_text = "\n\n".join(text_parts).strip()
            if len(fallback_text) >= 100:
                return fallback_text
        except Exception:
            # Ignore fallback failure and continue to raise detailed error below
            pass

        stats = (
            f"provider={provider}, pages_rendered={len(images)}, "
            f"bytes_per_page={[len(b) for b in images][:5]}, errors={errors[:3]}"
        )
        raise RuntimeError(f"Vision LLM returned empty content (\n{stats}\n)")
    return md


