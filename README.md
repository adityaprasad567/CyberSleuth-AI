# CyberSleuth AI

A full-stack system that helps a victim of cybercrime (UPI fraud, phishing, OTP scams, sextortion, etc.) understand what happened, which Indian laws apply, and generates a ready-to-file complaint — end to end, from a plain-text description to a downloadable PDF/DOCX report.

**Live demo:**  https://cybersleuth-ai-1.onrender.com
**Backend API docs:** `/docs` here_

---

## What it does

1. **Classifies** a free-text complaint into a crime category (UPI fraud, phishing, OTP scam, fake job offer, investment scam, sextortion, SIM swap)
2. **Retrieves** the specific IT Act / Bharatiya Nyaya Sanhita (BNS) / IPC sections that apply, scoped correctly to whether the incident happened before or after BNS took effect (1 July 2024)
3. **Explains** the crime in plain language and lists immediate next steps (freeze funds, report to cybercrime.gov.in / helpline 1930, etc.)
4. **Generates** a formal draft complaint plus a full investigation report as PDF, DOCX, or TXT
5. **Tracks evidence** (screenshots, files) and builds a timeline per case, linked by a complaint ID
6. **Persists** everything (Postgres + object storage) so cases survive across sessions and deployments

---

## Architecture

```
React (Vite + TypeScript)
        |  REST
        v
FastAPI backend
        |
        +--> Classifier (swappable - see below)
        +--> RAG legal retriever (swappable - see below)
        +--> LLM reasoning layer (Gemini, or offline template fallback)
        +--> Report generator (ReportLab / python-docx)
        +--> Storage (Postgres + object storage, or SQLite + local disk)
```

### Swappable backends

This was a deliberate design choice, not an afterthought: classification and legal retrieval are each behind a small interface, selected by an environment variable, so the same API contract works whether you want maximum accuracy, zero API cost, or minimum deploy size.

| Component | Backend | How | Tradeoff |
|---|---|---|---|
| Classifier | `local` (default) | Fine-tuned DistilBERT | Best ceiling on accuracy with more data; ~1GB+ install (torch/transformers), needs training |
| Classifier | `sklearn` | TF-IDF + Logistic Regression | ~200MB install, no GPU, trains in <1s, no API key |
| Classifier | `gemini` | Gemini API | No training/local model at all, strong out-of-the-box accuracy, needs an API key + network call |
| Retriever | `faiss` (default) | Sentence-transformer embeddings + FAISS | Best for a large legal corpus |
| Retriever | `lite` | Tag-based filtering, no ML | Appropriate here since the legal knowledge base is a small, curated set of statutes, not a large corpus |

Set via `.env`:
```
CLASSIFIER_BACKEND=sklearn   # or: local, gemini
RETRIEVER_BACKEND=lite       # or: faiss
```

---

## Being upfront about the classifier

The `local`/`sklearn` classifiers are trained on **147 synthetically generated examples** (template + slot-filled sentences, not scraped or hand-labeled real complaints - see `data/generate_dataset.py`). On a held-out split from the same generator, both hit high accuracy; that reflects the model learning the templates well, **not** a validated claim about generalizing to arbitrary real-world phrasing.

Two things were built specifically to be honest about this limitation rather than hide it:
- **Confidence gating**: predictions below `MIN_CONFIDENCE_THRESHOLD` (see `data/taxonomy.py`) are flagged as `low_confidence`, and the UI shows an explicit "not enough detail" state instead of a confident-looking result.
- **The Gemini backend exists as the accuracy-first option** - for a deployment where classification quality matters more than cost, that's the one to use.

Improving this further would mean expanding the synthetic dataset (more templates/slot variety per category - currently imbalanced, `upi_fraud` has ~7x the examples of `sextortion`) or sourcing real anonymized complaint text.

---

## Tech stack

**Backend:** FastAPI, Pydantic, scikit-learn / DistilBERT (transformers) / Gemini API, FAISS + sentence-transformers (optional), ReportLab, python-docx, SQLite or Postgres (Supabase), local disk or Supabase Storage

**Frontend:** React, TypeScript, Vite, Tailwind, shadcn/ui

**Deployment:** Render (backend), Vercel (frontend), Supabase (Postgres + object storage)

---

## Running locally

```bash
git clone <this-repo>
cd cybercrime-advisor
python -m venv .venv
.venv\Scripts\activate        # Windows; use `source .venv/bin/activate` on Mac/Linux
pip install -r requirements.txt
cp .env.example .env          # then fill in CLASSIFIER_BACKEND + key, if using Gemini
```

**Lightweight path (no API key, no GPU, no large model download):**
```bash
cd classifier
python train_lite.py          # trains in under a second
```
Set in `.env`:
```
CLASSIFIER_BACKEND=sklearn
RETRIEVER_BACKEND=lite
```

**Run the backend:**
```bash
cd backend
uvicorn main:app --reload --port 8000
```
Check `http://127.0.0.1:8000/health` - both `classifier_loaded` and `retriever_loaded` should be `true`.

**Run the frontend:**
```bash
cd frontend
npm install
npm run dev
```

---

## Project structure

```
backend/          FastAPI app, request/response schemas
classifier/        Training + inference for all 3 classifier backends
rag/                Legal retrieval (FAISS-based and lite tag-based)
data/               Taxonomy (crime categories, legal tags, safety recs), synthetic dataset generator
legal_kb/           Curated IT Act / BNS / IPC statute text
case_builder/       Complaint draft + timeline construction
reports/            PDF / DOCX / TXT report generation
evidence/           File upload, hashing, entity extraction, storage (SQLite/Postgres, local/Supabase)
frontend/           React + TypeScript UI
```

---

## Known limitations / next steps

- Classifier accuracy is bounded by a small synthetic dataset - see above
- `complaint_id` is an opaque string, not tied to user authentication - fine for a demo, would need auth before handling real cases
- Free-tier Render backend sleeps after 15 minutes of inactivity (cold start ~30-60s on first request after idle)
