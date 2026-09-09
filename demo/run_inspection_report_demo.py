"""
Flagship demo scenario required by the problem statement:
  "reading a scanned inspection report, pulling out key findings and
   drafting an approval note as a Word file"

Usage:
  1. Drop a scanned inspection report at workspace/inspection_report.pdf (or .png/.jpg)
  2. python -m demo.run_inspection_report_demo
  3. Open workspace/approval_note.docx

This calls the SAME agent loop / tools the Streamlit UI uses — it's just a
scripted trigger so you can run the scenario headlessly during rehearsal.
"""
from agent.loop import run_agent

REPORT_FILE = "inspection_report.pdf"   # relative to workspace/, swap to your sample file

TASK = f"""
An inspection report has been scanned and saved at '{REPORT_FILE}' in the workspace.
1. Use ocr_extract on '{REPORT_FILE}' to read its contents (use the vision_text field,
   it's more reliable for stamps/handwriting than raw OCR).
2. Identify the 3-5 most important findings (defects, deviations from spec, safety flags).
3. Use doc_search to check whether any relevant SOP or manual is in the knowledge base
   that should be cited as a reference for the recommendation.
4. Use write_approval_note to produce 'approval_note.docx' with those findings, a
   clear recommendation (approve / approve with conditions / reject and re-inspect),
   and cite any SOPs found in step 3.
Give a final_answer summarizing what you found and where the file was written.
"""

if __name__ == "__main__":
    final_answer, trace = run_agent(TASK)

    print("=" * 70)
    print("AGENT TRACE")
    print("=" * 70)
    for step in trace:
        print(f"\n--- Step {step.get('step')} ---")
        print("Thought:", step.get("thought"))
        if step.get("action"):
            print("Action:", step["action"])
            print("Observation:", step.get("observation"))
        if step.get("final_answer"):
            print("Final answer:", step["final_answer"])
        if step.get("error"):
            print("Error:", step["error"])

    print("\n" + "=" * 70)
    print("RESULT:", final_answer)
    print("=" * 70)
