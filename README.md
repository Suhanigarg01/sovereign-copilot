# Sovereign AI Workbench — SIH 26117 Prototype

A self-hosted, air-gapped AI workbench: multi-model auto-routing + an agent
that plans, calls local tools, reads scanned documents, and produces real
Word/Excel/PowerPoint deliverables — with a live network monitor proving
nothing leaves the machine.

```
sih-workbench/
├── config/models.yaml        <- add/swap models HERE, no code change needed
├── router/                   <- FastAPI service: classifies task -> picks model -> forwards
├── agent/                    <- plan-act-observe loop + sandboxed code exec + tool registry
├── knowledge_base/           <- FAISS-based local RAG over SOPs/manuals
├── vision/                   <- OCR + local vision-LLM for scans/handwriting/drawings
├── deliverables/             <- docx / xlsx / pptx generators (real files, not chat text)
├── network_monitor/          <- live proof of "no external calls"
├── demo/                     <- scripted end-to-end scenario
├── ui/app.py                 <- Streamlit dashboard judges will actually watch
└── workspace/, kb_docs/, kb_index/   <- runtime data dirs (empty at first)
```

---

## Step 0 — Decide hardware and fallback models

- Ideal: one workstation/server with a mid-range GPU (16–24GB VRAM covers everything below comfortably).
- If you only have a laptop GPU or CPU at the venue, swap `config/models.yaml` to smaller quantized
  variants (`qwen2.5-coder:1.5b`, `qwen2.5:3b-instruct`, `llava:7b`) — same code, just edit the YAML.
- This single file is the whole point of "no redesign to add a model": every model swap or addition
  is a YAML edit + `ollama pull`, nothing in `router/` or `agent/` changes.

## Step 1 — Install the model runtime and pull models

```bash
curl -fsSL https://ollama.com/install.sh | sh     # or use vLLM if you prefer OpenAI-style serving
ollama pull qwen2.5-coder:7b
ollama pull llama3.1:8b-instruct-q4_K_M
ollama pull qwen2-vl:7b
ollama pull qwen2.5:1.5b-instruct-q4_K_M
```

Before building anything else, confirm each model answers **fully offline** — pull an ethernet
cable / disable Wi-Fi and re-test. This is your highest-risk dependency; don't build on top of it
until it's verified.

## Step 2 — Install project dependencies

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
sudo apt-get install tesseract-ocr poppler-utils   # for pytesseract + pdf2image
```

Docker is required for the sandboxed code tool:

```bash
sudo apt-get install docker.io
docker pull python:3.11-slim
sudo usermod -aG docker $USER   # then re-login
```

Pre-download the embedding model once (while online), then work offline from here on:

```bash
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
```

## Step 3 — Start the model router

```bash
uvicorn router.main:app --port 8000 --reload
```

Check auto-selection is wired up:

```bash
curl -X POST localhost:8000/route -H "Content-Type: application/json" \
  -d '{"prompt": "Write a Python function to parse a CSV and sum a column"}'
# -> task_type: coding, model_used: coder-primary

curl -X POST localhost:8000/route -H "Content-Type: application/json" \
  -d '{"prompt": "Summarize the key risks in this vendor negotiation and draft a note"}'
# -> task_type: document, model_used: reasoner-general
```

That single request/response pair (different prompt -> different `model_used`) **is** your
"model auto-selection across at least two task types" demo requirement — screenshot it or run it live.

## Step 4 — Build the local knowledge base

Drop a few sample SOPs/manuals (plain text, markdown, or PDF) into `kb_docs/`, then:

```bash
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
python -m knowledge_base.ingest
```

This builds `kb_index/kb.index` + `kb_index/kb_meta.pkl`. The `doc_search` tool (in
`agent/tools.py`) queries this at agent-run time — nothing here calls out to the network.

## Step 5 — Verify the sandbox

```bash
python -c "from agent.sandbox import run_code; print(run_code('print(2+2)'))"
# -> {'stdout': '4\n', 'stderr': '', 'exit_code': 0, 'timed_out': False}
```

The container runs with `network_disabled=True`, capped CPU/memory, and a read-only mount of
just the snippet — this is your "coding task run and verified in a sandbox" requirement.

## Step 6 — Verify OCR + vision on a real scan

Drop a scanned PDF or photo at `workspace/inspection_report.pdf`, then:

```bash
python -c "from vision.ocr_pipeline import extract_document; \
import json; print(json.dumps(extract_document('workspace/inspection_report.pdf'), indent=2)[:1000])"
```

You should get both a raw OCR pass and a vision-model structured read. This is your
"multimodal task involving image/scanned document understanding" requirement.

## Step 7 — Run the flagship end-to-end scenario

```bash
python -m demo.run_inspection_report_demo
```

This runs the full plan-act-observe loop: OCR/vision-read the scan → pull key findings →
check the knowledge base for a relevant SOP → write `workspace/approval_note.docx`. The
printed trace **is** the "show this trace visibly" requirement in text form; the Streamlit
UI (next step) shows the same trace as a live, clickable UI.

## Step 8 — Start the network monitor (its own terminal, visible to judges)

```bash
python network_monitor/watch.py
```

Leave this running for the whole demo. A clean scroll of `clean (loopback/LAN only)` lines —
with zero red `EXTERNAL CONNECTION` lines — is your literal, undeniable proof of the sovereign
claim. Physically unplug the ethernet/disable Wi-Fi before the demo if you want to make the
point even harder.

## Step 9 — Start the dashboard

```bash
streamlit run ui/app.py
```

Walk judges through, in this order:
1. Type a coding prompt → point at the "Model fleet" panel / trace → note which model answered.
2. Type a document/summarization prompt → same thing, different model — **this is the auto-selection proof**.
3. Run the inspection-report task → watch the step-by-step trace expand live → download the
   resulting `approval_note.docx` — **this is the agentic, multi-tool, multimodal, real-deliverable proof**.
4. Point at the network monitor panel (or its terminal) the whole time — **this is the air-gap proof**.

---

## Extending later (the "no redesign" requirement in practice)

To add a 5th model (say, a bigger reasoning model once more VRAM is available):
1. `ollama pull <new-model>`
2. Add one entry to `config/models.yaml` with its `task_types`
3. Restart the router. Nothing in `router/`, `agent/`, or `ui/` needs to change.

## Known corners cut for a hackathon timeline (say this proactively, judges respect it)

- The classifier is heuristic-first + tiny-model fallback, not a trained classifier — fine for a
  demo, swap for a fine-tuned router if this became a real product.
- Sandbox supports Python/shell only; add more `IMAGE_BY_LANG` entries in `agent/sandbox.py` for
  more languages.
- Single-node only — no multi-GPU model sharding. For 30B+ class models you'd add vLLM tensor
  parallelism, same router interface.
- Auth/RBAC on the FastAPI router is not implemented — needed before any real deployment on
  confidential data.
