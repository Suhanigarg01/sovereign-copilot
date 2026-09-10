"""
On-device OCR (tesseract, for clean typed text) + local vision-LLM understanding
(for handwriting, engineering drawings, and anything OCR mangles). Both run
fully offline. Used by the agent's `ocr_extract` / `vision_understand` tools.
"""
import base64
from pathlib import Path

import httpx
import pytesseract
from PIL import Image
from pdf2image import convert_from_path

from router.registry import registry


def pdf_to_images(pdf_path: str, out_dir: str) -> list:
    """Rasterize a scanned PDF's pages to PNGs for OCR/vision processing."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    pages = convert_from_path(pdf_path, dpi=250)
    paths = []
    for i, page in enumerate(pages):
        p = out / f"page_{i+1}.png"
        page.save(p, "PNG")
        paths.append(str(p))
    return paths


def ocr_image(image_path: str) -> str:
    """Fast path: plain tesseract OCR for clean typed text."""
    return pytesseract.image_to_string(Image.open(image_path))


def vision_understand(image_path: str, prompt: str) -> str:
    """
    Slow-but-smart path: sends the image to the local vision-language model
    (e.g. Qwen2-VL) for handwriting, stamps, tables, or engineering drawings
    that plain OCR gets wrong. Never leaves localhost.
    """
    model = registry.get_for_task("vision")
    img_b64 = base64.b64encode(Path(image_path).read_bytes()).decode("utf-8")
    r = httpx.post(
        f"{registry.base_url}/api/generate",
        json={"model": model.ollama_model, "prompt": prompt, "images": [img_b64], "stream": False},
        timeout=300.0,
        trust_env=False,  # ignore HTTP_PROXY/ALL_PROXY etc. — this is loopback-only traffic to Ollama
    )
    r.raise_for_status()
    return r.json().get("response", "")


def extract_document(pdf_or_image_path: str, hint_prompt: str = None) -> dict:
    """
    Convenience wrapper the agent calls for "read this scanned inspection report":
    - runs OCR for a fast raw-text pass
    - runs the vision model for a structured, corrected read (handles handwriting/tables/stamps)
    Returns both so the agent/user can cross-check.
    """
    path = Path(pdf_or_image_path)
    images = pdf_to_images(str(path), str(path.parent / "_pages")) if path.suffix.lower() == ".pdf" else [str(path)]

    ocr_text, vision_text = [], []
    default_prompt = (
        "Transcribe and structure the readable content of this document image. "
        "Note any handwritten annotations, stamps, or table data separately."
    )
    for img in images:
        ocr_text.append(ocr_image(img))
        vision_text.append(vision_understand(img, hint_prompt or default_prompt))

    return {"pages": len(images), "ocr_text": "\n\n".join(ocr_text), "vision_text": "\n\n".join(vision_text)}