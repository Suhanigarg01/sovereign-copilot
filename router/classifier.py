"""
Classifies an incoming task into one of: coding | document | vision | general.
Two-tier: cheap regex/keyword heuristics first (instant, free), then a fallback
call to the tiny router-classifier model only when heuristics are unsure.
This is what makes "auto-pick the right model" demonstrable and cheap.
"""
import json
import re
import httpx
from router.registry import registry

CODE_HINTS = re.compile(
    r"(```|\bdef \b|\bclass \b|\bimport \b|\bfunction\b|traceback|stack ?trace|"
    r"\.py\b|\.js\b|\.cpp\b|\bcompile\b|\bdebug\b|\bunit test\b|write (a |the )?(script|code|function))",
    re.IGNORECASE,
)
SPREADSHEET_HINTS = re.compile(r"\b(spreadsheet|excel|xlsx|\.csv|pivot table|formula)\b", re.IGNORECASE)
DOC_HINTS = re.compile(
    r"\b(summariz|approval note|draft|report|memo|sop|manual|correspondence|minutes of meeting)\b",
    re.IGNORECASE,
)


def classify_task(prompt: str, has_image: bool = False, has_pdf_scan: bool = False) -> str:
    if has_image or has_pdf_scan:
        return "vision"
    if CODE_HINTS.search(prompt):
        return "coding"
    if SPREADSHEET_HINTS.search(prompt):
        return "document"          # spreadsheet tool is invoked by the agent, model stays "document"
    if DOC_HINTS.search(prompt):
        return "document"

    # Heuristics inconclusive -> ask the tiny classifier model
    return _model_classify(prompt)


def _model_classify(prompt: str) -> str:
    clf = registry.get_by_name("router-classifier")
    sys_prompt = (
        "Classify the user's task into exactly one label: coding, document, vision, or general. "
        "Reply with ONLY the label, nothing else.\n\nTask: " + prompt
    )
    try:
        r = httpx.post(
            f"{registry.base_url}/api/generate",
            json={"model": clf.ollama_model, "prompt": sys_prompt, "stream": False, "options": {"num_predict": 5}},
            timeout=20.0,
        )
        label = r.json().get("response", "").strip().lower()
        if label in ("coding", "document", "vision", "general"):
            return label
    except Exception:
        pass
    return registry.default_task_type
