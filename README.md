# Sovereign AI Workbench (sovereign-copilot)

A self-hosted, air-gapped AI workbench for confidential industrial work: multi-model auto-routing, an agent that plans, calls local tools, reads scanned documents, and produces real Word/Excel/PowerPoint deliverables — with a live network monitor proving nothing leaves the machine.

## 1. Project Information

- **Project Title:** Sovereign AI Workbench
- **PS ID:** SIH26117
- **PS Title:** Sovereign On-Premise Agentic AI Workbench using Open-Weight Multimodal LLMs for Confidential Industrial Work
- **Organization:** Mangalore Refinery and Petrochemicals Limited (MRPL)
- **Category:** Software
- **Theme:** Smart Automation

## 2. Problem Statement

Confidential industrial data — maintenance logs, inspection scans, SOPs, engineering documents — cannot safely be sent to cloud-hosted AI tools. Yet teams in sensitive, regulated environments (such as refineries and petrochemical plants) still need modern AI capabilities: coding assistance, document understanding, summarization, and report generation. Existing AI copilots depend on external APIs, which risks leaking proprietary or safety-critical data outside the organization's network.

## 3. Proposed Solution

Sovereign AI Workbench runs entirely on local infrastructure. A FastAPI-based router classifies each incoming task and automatically forwards it to the most suitable locally-hosted open-weight model (coding, reasoning, or vision). An agent layer runs a plan–act–observe loop, calling local tools — a sandboxed code executor, a FAISS-based knowledge base over SOPs/manuals, and an OCR/vision pipeline for scanned or handwritten documents — and produces real `.docx` / `.xlsx` / `.pptx` deliverables instead of chat-only text. A dedicated network monitor runs alongside every session and continuously verifies that no external network call is ever made, giving a live, visible proof of the "sovereign" (air-gapped) claim.

## 4. Key Features

- Automatic model routing across task types (coding, document/reasoning, vision) via a single YAML config, with no code changes needed to add or swap models
- Agentic plan–act–observe loop with a local tool registry
- Sandboxed code execution (Docker, network disabled, capped CPU/memory)
- Local retrieval-augmented knowledge base (FAISS) built from SOPs and manuals
- OCR + local vision-LLM pipeline for scanned documents, handwriting, and drawings
- Automatic generation of real Word/Excel/PowerPoint deliverables
- Live network monitor for continuous, visible air-gap verification
- Streamlit dashboard to walk through routing, agent traces, and deliverables in one place

## 5. Technology Stack

- **Frontend / Dashboard:** Streamlit
- **Backend:** Python, FastAPI (model router)
- **Agent Layer:** Custom plan–act–observe agent with a local tool registry
- **LLMs / Model Runtime:** Ollama (or vLLM), open-weight models (e.g., Qwen2.5-Coder, Llama 3.1, Qwen2-VL)
- **Retrieval / Knowledge Base:** FAISS, Sentence-Transformers embeddings
- **OCR / Vision:** Tesseract OCR (pytesseract), pdf2image, local vision-LLM
- **Sandboxing:** Docker (isolated, network-disabled containers)
- **Deliverable Generation:** Python-based docx / xlsx / pptx generators
- **Deployment:** Fully local / offline, Docker for the sandboxed tool

## 6. Architecture

```
User
  |
  v
Streamlit UI (ui/app.py)
  |
  v
Router (FastAPI) --> classifies task --> selects model
  |
  v
Agent (plan-act-observe loop)
  |
  +--> Sandboxed Code Execution (Docker, network disabled)
  |
  +--> Knowledge Base (FAISS RAG over SOPs/manuals)
  |
  +--> Vision / OCR Pipeline (scans, handwriting)
  |
  v
Deliverables Generator (.docx / .xlsx / .pptx)
  |
  v
Network Monitor (verifies zero external calls throughout)
```

## 7. Repository Structure

```
sovereign-copilot/
├── README.md
├── requirements.txt
├── config/
│   └── models.yaml        <- add/swap models here, no code change needed
├── router/                <- FastAPI service: classifies task -> picks model -> forwards
├── agent/                 <- plan-act-observe loop + sandboxed code exec + tool registry
├── knowledge_base/        <- FAISS-based local RAG over SOPs/manuals
├── vision/                <- OCR + local vision-LLM for scans/handwriting/drawings
├── deliverables/          <- docx / xlsx / pptx generators (real files, not chat text)
├── network_monitor/       <- live proof of "no external calls"
├── demo/                  <- scripted end-to-end demo scenario
├── ui/
│   └── app.py             <- Streamlit dashboard
└── workspace/, kb_docs/, kb_index/   <- runtime data dirs (created on first run)
```

**What goes where?**

| Item | Location |
|---|---|
| Router / model selection logic | `router/` |
| Agent, tools, sandbox | `agent/` |
| Model configuration | `config/models.yaml` |
| OCR / vision pipeline | `vision/` |
| Deliverable generators | `deliverables/` |
| Local knowledge base source docs / index | `knowledge_base/`, `kb_docs/`, `kb_index/` |
| Air-gap / network verification | `network_monitor/` |
| End-to-end demo script | `demo/` |
| Dashboard | `ui/app.py` |
| Project overview | `README.md` |

## 8. Final Presentation

Keep the final SIH presentation in the repository whenever the file size allows it, ideally under a `submission/` directory (e.g. `submission/PRESENTATION.md`).

If the PPT is too large for GitHub, host it on Google Drive/OneDrive and link the accessible viewer version from that file instead.

## 9. Installation

```bash
git clone https://github.com/Suhanigarg01/sovereign-copilot.git
cd sovereign-copilot

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# OCR / PDF dependencies
sudo apt-get install tesseract-ocr poppler-utils

# Docker is required for the sandboxed code tool
sudo apt-get install docker.io
docker pull python:3.11-slim
sudo usermod -aG docker $USER   # then re-login

# Pull local models (requires internet once)
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5-coder:7b
ollama pull llama3.1:8b-instruct-q4_K_M
ollama pull qwen2-vl:7b
ollama pull qwen2.5:1.5b-instruct-q4_K_M

# Pre-download the embedding model once (while online)
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
```

## 10. Run

```bash
# 1. Start the model router
uvicorn router.main:app --port 8000 --reload

# 2. Build the local knowledge base (after adding docs to kb_docs/)
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
python -m knowledge_base.ingest

# 3. Start the network monitor (separate terminal, keep visible during any demo)
python network_monitor/watch.py

# 4. Start the dashboard
streamlit run ui/app.py
```

Optional: run the scripted end-to-end scenario directly:

```bash
python -m demo.run_inspection_report_demo
```

## 11. Future Scope

- Replace the heuristic-first task classifier with a fine-tuned routing model for more accurate model selection
- Extend the sandbox beyond Python/shell to additional languages
- Add multi-GPU tensor-parallel serving (e.g. via vLLM) to support larger (30B+) class models
- Implement authentication and role-based access control on the FastAPI router before any deployment on confidential production data
- Expand the knowledge base ingestion pipeline to more document formats and larger corpora

---

### Important

Before submission, make sure the repository is accessible to reviewers. Do not upload passwords, API keys, access tokens, `.env` files containing secrets, or other confidential credentials.
