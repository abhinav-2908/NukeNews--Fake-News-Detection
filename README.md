# NukeNews

Evidence-first news analysis with four input modes, a local TF-IDF classifier, optional OpenRouter analysis, configurable web search, and locally persisted analysis history. The interface keeps classifier output separate from evidence assessment. It abstains when evidence is unavailable.

## Current implementation status

The core application and training pipeline are implemented. The ISOT `Fake.csv` and `True.csv` files supplied for this task were inspected (23,481 fake and 21,417 real records; title, text, subject, date columns) and copied into `data/raw/` for local training. They are excluded from Git. Model results are written only by a real training run; no results are fabricated. The training command compares Logistic Regression, Multinomial Naive Bayes, and calibrated Linear SVM. DistilBERT training is not included in this environment-sized initial pass. No Hindi performance claim is made; ISOT is English-only.

## Architecture

- `frontend/`: React, Vite, TypeScript dashboard with text, URL, PDF, and image modes; history and evaluation pages.
- `backend/app/`: FastAPI routes, extraction, inference, search/OpenRouter adapters, and SQLAlchemy history.
- `scripts/train.py`: reproducible ISOT loading, deduplication, stratified train/validation/test split, model comparison, held-out evaluation, artifact saving.
- `data/raw/`, `models/`, `artifacts/`: local datasets, trained weights, and evaluation outputs; excluded from Git.

## Requirements

Python 3.11 recommended, Node.js 20+, Tesseract OCR (English `eng` pack by default; install `hin` and set `OCR_LANGUAGES=eng+hin` for Hindi OCR). PDF extraction uses PyMuPDF. Scanned PDFs and images use Tesseract OCR when installed. PDF text extraction uses PyMuPDF; image OCR requires the Tesseract `eng` language data.

## Dataset and training

The supplied ISOT files are in `data/raw/`. For another checkout, download ISOT separately and place `True.csv` and `Fake.csv` there (accepted real variants: `true.csv`, `real.csv`; fake variants: `fake.csv`). Expected columns include `title` and `text`; `subject` and `date` are ignored to avoid source/metadata leakage. Exact article duplicates are removed before a seeded stratified split. Near-duplicate/source-separated/temporal stress tests are future work, and ISOT collection/style artifacts may cause shortcut learning.

```bash
python3 -m venv backend/.venv
source backend/.venv/bin/activate
python -m pip install -r backend/requirements.txt
python scripts/train.py
```

The script chooses on validation macro-F1 and touches the test set only for one final held-out score. It writes `models/selected.joblib` and `artifacts/metrics.json`. Model probability calibration is included for Linear SVM; Logistic Regression and Naive Bayes provide probability estimates. The selected model is refit on train+validation before saving.

## Configure and start

```bash
cp .env.example .env
# Add OPENROUTER_API_KEY and OPENROUTER_MODEL to .env for LLM verification.
# Optional: set SEARCH_PROVIDER=brave and BRAVE_SEARCH_API_KEY.
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload
```

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`; backend API docs are at `http://localhost:8000/docs`. Set `VITE_API_BASE_URL` at frontend build time if the backend is hosted elsewhere. `.env` settings are loaded from the project root, where the example file lives.

## API

- `GET /api/health`, `/api/models`, `/api/metrics`
- `POST /api/analyze/text` (`{ "title": "...", "text": "..." }`)
- `POST /api/analyze/url` (`{ "url": "https://..." }`)
- `POST /api/analyze/pdf`, `/api/analyze/image` (multipart `file`)
- `GET /api/history`, `GET /api/history/{id}`, `DELETE /api/history/{id}`

SQLite is the default; set `DATABASE_URL` to a PostgreSQL SQLAlchemy URL for deployment. History is local to the installation and has no account isolation/authentication. Configure `FRONTEND_ORIGINS` as a comma-separated CORS allowlist.

## Evidence and security notes

Bing News is the no-key default search provider; it returns publisher URLs and short snippets. NukeNews fetches up to four result pages through the SSRF-checked extractor when possible and uses short excerpts. Google News RSS is the fallback if Bing is unavailable; it may provide titles without article excerpts. These public search pages can change or rate-limit access. Search snippets and excerpts are limited evidence, not proof. Configure Brave Search if desired, subject to its current account plan, quota, and terms. OpenRouter model IDs are configured, not hard-coded; choose an available text model from the [current model catalog](https://openrouter.ai/models) and check [current pricing and limits](https://openrouter.ai/pricing) before use. The free plan currently lists 50 requests/day; free-model request caps and paid-provider costs can change. The API uses OpenRouter’s bearer-key chat completions endpoint and JSON response mode. If either provider is not configured or fails, analysis returns an inconclusive result with limitations.

URL fetching restricts schemes, rejects credentials, checks DNS addresses, blocks non-public IPs, revalidates each redirect, limits redirects and body size, and uses timeouts. SSRF checks are best-effort; DNS rebinding defenses are not equivalent to network egress controls. Uploads have a 15 MB cap; PDF files are capped at 100 pages and image dimensions at 25 megapixels. Uploaded binaries are not persisted. Do not expose this single-user local installation to untrusted networks without authentication, rate limiting, stronger egress isolation, and security review.

## Limitations

- Classifier predictions are pattern estimates trained on a narrow English dataset and are not factual truth probabilities.
- LLM checks use sources returned by search, but current result snippets are not independently fetched or validated passages. A final `REAL`/`FAKE` result is therefore only an LLM assessment of supplied evidence; review the source yourself.
- Hindi text is detected and surfaced as unvalidated; ISOT training does not establish Hindi capability. Hindi OCR requires the Tesseract `hin` language pack and `OCR_LANGUAGES=eng+hin`.
- DistilBERT comparison, robust near-duplicate grouping, temporal/source/topic-separated tests, multilingual labeled evaluation, API rate limiting, and auth are not implemented. Scanned PDF OCR is attempted through Tesseract when installed; availability depends on the host and language packs.
- This is a development/academic demonstration, not a production-ready fact-checking service.

## Checks

```bash
cd backend && python -m pytest -q tests
cd ../frontend && npm run build
npm audit
```
