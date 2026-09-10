"""
Judge-facing dashboard. Shows, live:
  - which task type was detected and which model handled it (auto-selection proof)
  - the agent's step-by-step thought/action/observation trace (agent, not chatbot)
  - generated deliverable files, ready to download
  - a tail of the network monitor log (air-gap proof)

Run: streamlit run ui/app.py   (run router + network_monitor/watch.py separately first)
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

sys.path.insert(0, str(Path(__file__).parent.parent))  # allow `agent.*`, `router.*` imports

import streamlit as st
from agent.loop import run_agent
from agent.tools import WORKSPACE
from router.registry import registry
from knowledge_base.ingest import build_index, DOCS_DIR as KB_DOCS_DIR
from vision.ocr_pipeline import extract_document

UPLOAD_TYPES = ("pdf", "txt", "md", "png", "jpg", "jpeg")
TEXT_TYPES = (".pdf", ".txt", ".md")

st.set_page_config(page_title="SIH-26117 | Sovereign AI Workbench", layout="wide")
st.title("🔒 On-Premise AI Workbench — SIH 26117")
st.caption("Fully local. No request in this app ever leaves the machine it runs on.")

col_main, col_side = st.columns([2, 1])

with col_side:
    st.subheader("📄 Upload a document")
    uploaded = st.file_uploader(
        "pdf/txt/md go straight into the local knowledge base; "
        "photos/scans are OCR'd first, then indexed",
        type=list(UPLOAD_TYPES),
    )
    if uploaded is not None and st.button("Index this document", type="secondary"):
        raw_bytes = uploaded.getvalue()
        WORKSPACE.mkdir(exist_ok=True)
        (WORKSPACE / uploaded.name).write_bytes(raw_bytes)  # reachable by file_read / ocr_extract too

        suffix = Path(uploaded.name).suffix.lower()
        with st.spinner(f"Indexing '{uploaded.name}' locally — no network calls..."):
            KB_DOCS_DIR.mkdir(exist_ok=True)
            if suffix in TEXT_TYPES:
                (KB_DOCS_DIR / uploaded.name).write_bytes(raw_bytes)
            else:
                # scanned/photographed doc: OCR + vision-read it, index the extracted text
                extracted = extract_document(str(WORKSPACE / uploaded.name))
                text = extracted.get("vision_text") or extracted.get("ocr_text") or ""
                (KB_DOCS_DIR / f"{Path(uploaded.name).stem}_ocr.txt").write_text(text)
            build_index()

        st.success(f"'{uploaded.name}' is indexed. Ask about it in the task box →")
        st.session_state["task_box"] = f"Using the knowledge base, answer about '{uploaded.name}': "

    if KB_DOCS_DIR.exists():
        indexed = sorted(p.name for p in KB_DOCS_DIR.glob("*") if p.is_file())
        if indexed:
            st.caption("Currently in the knowledge base:")
            st.markdown("\n".join(f"- {name}" for name in indexed))

    st.subheader("Model fleet")
    for m in registry.models:
        st.markdown(f"**{m.name}** — `{m.ollama_model}`  \nhandles: {', '.join(m.task_types)}")

    st.subheader("Network monitor")
    log_path = Path(__file__).parent.parent / "network_monitor" / "network_activity.log"
    if log_path.exists():
        lines = log_path.read_text().strip().splitlines()[-8:]
        flagged_any = any("EXTERNAL" in l for l in lines)
        st.markdown("🔴 external connection seen" if flagged_any else "🟢 loopback/LAN only")
        st.code("\n".join(lines), language="text")
    else:
        st.info("Start `python network_monitor/watch.py` in a terminal to show live proof here.")

with col_main:
    task = st.text_area(
        "Give the workbench a task",
        key="task_box",
        placeholder="e.g. Read workspace/inspection_report.pdf, pull out the key findings, "
                    "and draft an approval note as approval_note.docx\n\n"
                    "or, after uploading a document on the left: "
                    "'What does the uploaded report say about pressure limits?'",
        height=120,
    )
    max_steps = st.slider("Max agent steps", 2, 15, registry.max_agent_steps)

    if st.button("Run", type="primary") and task.strip():
        trace_container = st.container()
        with st.spinner("Agent working..."):
            final_answer, trace = run_agent(task, max_steps=max_steps)

        st.subheader("Result")
        st.success(final_answer)

        st.subheader("Agent trace")
        for step in trace:
            with st.expander(f"Step {step.get('step')}" +
                              (f" — tool: {step['action']['tool']}" if step.get("action") else " — final answer")):
                st.markdown(f"**Thought:** {step.get('thought', '—')}")
                if step.get("action"):
                    st.markdown(f"**Action:** `{step['action']['tool']}`")
                    st.json(step["action"].get("args", {}))
                    st.markdown("**Observation:**")
                    st.json(step.get("observation"))
                if step.get("error"):
                    st.error(step["error"])

        st.subheader("Files in workspace")
        for f in sorted(WORKSPACE.glob("*")):
            if f.is_file():
                st.download_button(f"Download {f.name}", data=f.read_bytes(), file_name=f.name)