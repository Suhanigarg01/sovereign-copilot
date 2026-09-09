"""
Judge-facing dashboard. Shows, live:
  - which task type was detected and which model handled it (auto-selection proof)
  - the agent's step-by-step thought/action/observation trace (agent, not chatbot)
  - generated deliverable files, ready to download
  - a tail of the network monitor log (air-gap proof)

Run: streamlit run ui/app.py   (run router + network_monitor/watch.py separately first)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))  # allow `agent.*`, `router.*` imports

import streamlit as st
from agent.loop import run_agent
from agent.tools import WORKSPACE
from router.registry import registry

st.set_page_config(page_title="SIH-26117 | Sovereign AI Workbench", layout="wide")
st.title("🔒 On-Premise AI Workbench — SIH 26117")
st.caption("Fully local. No request in this app ever leaves the machine it runs on.")

col_main, col_side = st.columns([2, 1])

with col_side:
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
        placeholder="e.g. Read workspace/inspection_report.pdf, pull out the key findings, "
                    "and draft an approval note as approval_note.docx",
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
