"""
Fixed toolset for the agent. Every tool is scoped and returns structured
JSON-able results so the model can reason over them. File tools refuse any
path that escapes the workspace directory.
"""
import json
from pathlib import Path

import pandas as pd

from agent.sandbox import run_code
from knowledge_base.search import doc_search as _doc_search
from vision.ocr_pipeline import extract_document
from deliverables.docx_writer import generate_approval_note
from deliverables.xlsx_writer import generate_calc_sheet
from deliverables.pptx_writer import generate_summary_deck

WORKSPACE = (Path(__file__).parent.parent / "workspace").resolve()
WORKSPACE.mkdir(exist_ok=True)


def _safe_path(rel_path: str) -> Path:
    p = (WORKSPACE / rel_path).resolve()
    if WORKSPACE not in p.parents and p != WORKSPACE:
        raise PermissionError(f"Path '{rel_path}' escapes the scoped workspace directory. Refused.")
    return p


# ---- tool implementations -------------------------------------------------

def file_read(path: str) -> str:
    p = _safe_path(path)
    if not p.exists():
        return f"ERROR: {path} does not exist in workspace."
    return p.read_text(errors="ignore")


def file_write(path: str, content: str) -> str:
    p = _safe_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return f"Wrote {len(content)} chars to {path}"


def code_execute(code: str, language: str = "python") -> dict:
    return run_code(code, language=language)


def spreadsheet_read(path: str) -> dict:
    p = _safe_path(path)
    df = pd.read_excel(p) if p.suffix in (".xlsx", ".xlsm") else pd.read_csv(p)
    return {"columns": list(df.columns), "rows": df.head(50).to_dict(orient="records"), "n_rows": len(df)}


def spreadsheet_write_calc(path: str, title: str, headers: list, rows: list, formula_note: str = None) -> str:
    p = _safe_path(path)
    generate_calc_sheet(str(p), title, headers, rows, formula_note)
    return f"Wrote calculation sheet to {path}"


def doc_search(query: str, top_k: int = 4) -> list:
    return _doc_search(query, top_k=top_k)


def ocr_extract(path: str, hint_prompt: str = None) -> dict:
    p = _safe_path(path)
    return extract_document(str(p), hint_prompt=hint_prompt)


def write_approval_note(path: str, subject: str, findings: list, recommendation: str, reference_docs: list = None) -> str:
    p = _safe_path(path)
    generate_approval_note(str(p), subject, findings, recommendation, reference_docs=reference_docs)
    return f"Wrote approval note to {path}"


def write_summary_deck(path: str, title: str, slides: list) -> str:
    p = _safe_path(path)
    generate_summary_deck(str(p), title, slides)
    return f"Wrote deck to {path}"


# ---- registry the agent loop introspects -----------------------------------

TOOL_REGISTRY = {
    "file_read": {"fn": file_read, "desc": "Read a text file from the scoped workspace. Args: {path}"},
    "file_write": {"fn": file_write, "desc": "Write text to a file in the scoped workspace. Args: {path, content}"},
    "code_execute": {"fn": code_execute, "desc": "Run code in a network-disabled sandbox. Args: {code, language}"},
    "spreadsheet_read": {"fn": spreadsheet_read, "desc": "Read a .xlsx/.csv file. Args: {path}"},
    "spreadsheet_write_calc": {"fn": spreadsheet_write_calc, "desc": "Write a calc sheet. Args: {path, title, headers, rows, formula_note}"},
    "doc_search": {"fn": doc_search, "desc": "Semantic search over the local SOP/manual knowledge base. Args: {query, top_k}"},
    "ocr_extract": {"fn": ocr_extract, "desc": "OCR + vision-read a scanned PDF/image in workspace. Args: {path, hint_prompt}"},
    "write_approval_note": {"fn": write_approval_note, "desc": "Generate a Word approval note. Args: {path, subject, findings, recommendation, reference_docs}"},
    "write_summary_deck": {"fn": write_summary_deck, "desc": "Generate a PowerPoint deck. Args: {path, title, slides}"},
}


def tool_specs_for_prompt() -> str:
    lines = [f"- {name}: {spec['desc']}" for name, spec in TOOL_REGISTRY.items()]
    return "\n".join(lines)


def call_tool(name: str, args: dict):
    if name not in TOOL_REGISTRY:
        return {"error": f"Unknown tool '{name}'. Available: {list(TOOL_REGISTRY.keys())}"}
    try:
        return TOOL_REGISTRY[name]["fn"](**args)
    except Exception as e:
        return {"error": str(e)}
